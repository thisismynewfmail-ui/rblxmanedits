"""Short status posts ("shouts") with likes."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .. import db, security

MAX_LEN = 400


class PostError(Exception):
    pass


def create(user_id: int, body: str) -> int:
    body = security.clean_text(body, MAX_LEN)
    if not body:
        raise PostError("Say something first.")
    if not db.rate_limit("post:%d" % user_id, 12, 300):
        raise PostError("You are posting too quickly. Take a breath.")
    cur = db.execute("INSERT INTO posts(user_id, body, created_at) VALUES(?,?,?)",
                     (user_id, body, int(time.time())))
    return int(cur.lastrowid)


def delete(post_id: int, actor_id: int, is_admin: bool = False) -> None:
    row = db.query_one("SELECT user_id FROM posts WHERE id=?", (post_id,))
    if row is None:
        return
    if int(row["user_id"]) != actor_id and not is_admin:
        raise PostError("That is not your post.")
    db.execute("DELETE FROM posts WHERE id=?", (post_id,))


def get(post_id: int) -> Optional[Dict[str, Any]]:
    return db.row_to_dict(db.query_one(
        "SELECT p.*, u.username FROM posts p JOIN users u ON u.id=p.user_id"
        " WHERE p.id=?", (post_id,)))


def for_user(user_id: int, limit: int = 20, viewer_id: Optional[int] = None
             ) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT p.*, u.username FROM posts p JOIN users u ON u.id=p.user_id"
        " WHERE p.user_id=? AND p.hidden=0 ORDER BY p.id DESC LIMIT ?",
        (user_id, limit))
    return _decorate(rows, viewer_id)


def timeline(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    """Posts from the viewer, their friends and everyone they follow."""
    from . import friends, follows
    ids = set(friends.friend_ids(user_id)) | set(follows.following_ids(user_id))
    ids.add(user_id)
    placeholders = ",".join("?" * len(ids))
    rows = db.query(
        "SELECT p.*, u.username FROM posts p JOIN users u ON u.id=p.user_id"
        " WHERE p.user_id IN (%s) AND p.hidden=0 ORDER BY p.id DESC LIMIT ?"
        % placeholders, tuple(ids) + (limit,))
    return _decorate(rows, user_id)


def latest(limit: int = 20, viewer_id: Optional[int] = None) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT p.*, u.username FROM posts p JOIN users u ON u.id=p.user_id"
        " WHERE p.hidden=0 ORDER BY p.id DESC LIMIT ?", (limit,))
    return _decorate(rows, viewer_id)


def _decorate(rows, viewer_id: Optional[int]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["comment_count"] = int(db.scalar(
            "SELECT COUNT(*) FROM post_comments WHERE post_id=?", (row["id"],)))
        item["liked"] = bool(viewer_id) and db.query_one(
            "SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?",
            (row["id"], viewer_id)) is not None
        out.append(item)
    return out


def toggle_like(post_id: int, user_id: int) -> Dict[str, Any]:
    if db.query_one("SELECT 1 FROM posts WHERE id=?", (post_id,)) is None:
        raise PostError("That post is gone.")
    with db.transaction() as conn:
        existing = conn.execute(
            "SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?",
            (post_id, user_id)).fetchone()
        if existing:
            conn.execute("DELETE FROM post_likes WHERE post_id=? AND user_id=?",
                         (post_id, user_id))
            liked = False
        else:
            conn.execute("INSERT INTO post_likes(post_id,user_id) VALUES(?,?)",
                         (post_id, user_id))
            liked = True
        count = int(conn.execute("SELECT COUNT(*) FROM post_likes WHERE post_id=?",
                                 (post_id,)).fetchone()[0])
        conn.execute("UPDATE posts SET likes=? WHERE id=?", (count, post_id))
    return {"liked": liked, "likes": count}


def count_for(user_id: int) -> int:
    return int(db.scalar("SELECT COUNT(*) FROM posts WHERE user_id=?", (user_id,)))


def total() -> int:
    return int(db.scalar("SELECT COUNT(*) FROM posts"))
