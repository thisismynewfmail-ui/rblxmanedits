"""Two flavours of comment: replies on posts, and comments on a profile wall."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from .. import db, security

MAX_LEN = 300


class CommentError(Exception):
    pass


# ------------------------------------------------------------- post comments

def add_to_post(post_id: int, user_id: int, body: str) -> int:
    body = security.clean_text(body, MAX_LEN)
    if not body:
        raise CommentError("Write something first.")
    if db.query_one("SELECT 1 FROM posts WHERE id=?", (post_id,)) is None:
        raise CommentError("That post no longer exists.")
    if not db.rate_limit("comment:%d" % user_id, 25, 300):
        raise CommentError("You are commenting too quickly.")
    cur = db.execute(
        "INSERT INTO post_comments(post_id,user_id,body,created_at)"
        " VALUES(?,?,?,?)", (post_id, user_id, body, int(time.time())))
    return int(cur.lastrowid)


def for_post(post_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT c.*, u.username FROM post_comments c JOIN users u ON u.id=c.user_id"
        " WHERE c.post_id=? ORDER BY c.id ASC LIMIT ?", (post_id, limit)))


def delete_post_comment(comment_id: int, actor_id: int,
                        is_admin: bool = False) -> None:
    row = db.query_one(
        "SELECT c.user_id, p.user_id AS owner FROM post_comments c"
        " JOIN posts p ON p.id=c.post_id WHERE c.id=?", (comment_id,))
    if row is None:
        return
    if actor_id not in (int(row["user_id"]), int(row["owner"])) and not is_admin:
        raise CommentError("You cannot remove that comment.")
    db.execute("DELETE FROM post_comments WHERE id=?", (comment_id,))


# ---------------------------------------------------------- profile comments

def add_to_profile(profile_id: int, author_id: int, body: str) -> int:
    body = security.clean_text(body, MAX_LEN)
    if not body:
        raise CommentError("Write something first.")
    if db.query_one("SELECT 1 FROM users WHERE id=?", (profile_id,)) is None:
        raise CommentError("No such profile.")
    if not db.rate_limit("profcomment:%d" % author_id, 20, 300):
        raise CommentError("You are commenting too quickly.")
    cur = db.execute(
        "INSERT INTO profile_comments(profile_id,author_id,body,created_at)"
        " VALUES(?,?,?,?)", (profile_id, author_id, body, int(time.time())))
    return int(cur.lastrowid)


def for_profile(profile_id: int, limit: int = 40) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT c.*, u.username FROM profile_comments c"
        " JOIN users u ON u.id=c.author_id"
        " WHERE c.profile_id=? AND c.hidden=0 ORDER BY c.id DESC LIMIT ?",
        (profile_id, limit)))


def delete_profile_comment(comment_id: int, actor_id: int,
                           is_admin: bool = False) -> None:
    row = db.query_one("SELECT profile_id, author_id FROM profile_comments"
                       " WHERE id=?", (comment_id,))
    if row is None:
        return
    if actor_id not in (int(row["author_id"]), int(row["profile_id"])) and not is_admin:
        raise CommentError("You cannot remove that comment.")
    db.execute("DELETE FROM profile_comments WHERE id=?", (comment_id,))


def count_for_profile(profile_id: int) -> int:
    return int(db.scalar(
        "SELECT COUNT(*) FROM profile_comments WHERE profile_id=? AND hidden=0",
        (profile_id,)))


def total() -> int:
    return int(db.scalar("SELECT COUNT(*) FROM profile_comments")) + \
           int(db.scalar("SELECT COUNT(*) FROM post_comments"))
