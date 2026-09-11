"""Asymmetric following (no approval needed, unlike friendships)."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from .. import db


class FollowError(Exception):
    pass


def follow(follower_id: int, followee_id: int) -> bool:
    if follower_id == followee_id:
        raise FollowError("You already follow yourself quite closely.")
    if db.query_one("SELECT 1 FROM users WHERE id=?", (followee_id,)) is None:
        raise FollowError("No such player.")
    if not db.rate_limit("follow:%d" % follower_id, 120, 3600):
        raise FollowError("Slow down.")
    db.execute("INSERT OR IGNORE INTO follows(follower_id,followee_id,created_at)"
               " VALUES(?,?,?)", (follower_id, followee_id, int(time.time())))
    return True


def unfollow(follower_id: int, followee_id: int) -> bool:
    db.execute("DELETE FROM follows WHERE follower_id=? AND followee_id=?",
               (follower_id, followee_id))
    return False


def toggle(follower_id: int, followee_id: int) -> bool:
    if is_following(follower_id, followee_id):
        return unfollow(follower_id, followee_id)
    return follow(follower_id, followee_id)


def is_following(follower_id: int, followee_id: int) -> bool:
    return db.query_one(
        "SELECT 1 FROM follows WHERE follower_id=? AND followee_id=?",
        (follower_id, followee_id)) is not None


def following_ids(user_id: int) -> List[int]:
    return [r["followee_id"] for r in db.query(
        "SELECT followee_id FROM follows WHERE follower_id=?", (user_id,))]


def followers(user_id: int, limit: int = 60) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT u.* FROM follows f JOIN users u ON u.id=f.follower_id"
        " WHERE f.followee_id=? ORDER BY f.created_at DESC LIMIT ?",
        (user_id, limit)))


def following(user_id: int, limit: int = 60) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT u.* FROM follows f JOIN users u ON u.id=f.followee_id"
        " WHERE f.follower_id=? ORDER BY f.created_at DESC LIMIT ?",
        (user_id, limit)))


def counts(user_id: int) -> Dict[str, int]:
    return {
        "followers": int(db.scalar(
            "SELECT COUNT(*) FROM follows WHERE followee_id=?", (user_id,))),
        "following": int(db.scalar(
            "SELECT COUNT(*) FROM follows WHERE follower_id=?", (user_id,))),
    }
