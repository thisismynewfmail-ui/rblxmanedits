"""Friend requests and friendships.

Stored as a single row per pair (lowest id first) so a friendship can never be
duplicated or half-accepted.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .. import db

MAX_FRIENDS = 200


class FriendError(Exception):
    pass


def _pair(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _now() -> int:
    return int(time.time())


def relationship(user_a: int, user_b: int) -> Optional[Dict[str, Any]]:
    if user_a == user_b:
        return None
    low, high = _pair(user_a, user_b)
    return db.row_to_dict(db.query_one(
        "SELECT * FROM friendships WHERE user_low=? AND user_high=?", (low, high)))


def status_for(viewer_id: int, other_id: int) -> str:
    """One of: self, none, pending_out, pending_in, friends."""
    if viewer_id == other_id:
        return "self"
    rel = relationship(viewer_id, other_id)
    if rel is None:
        return "none"
    if rel["status"] == "accepted":
        return "friends"
    if rel["status"] == "pending":
        return "pending_out" if rel["requester_id"] == viewer_id else "pending_in"
    return "none"


def request(from_id: int, to_id: int) -> str:
    if from_id == to_id:
        raise FriendError("You cannot befriend yourself. Try a hobby.")
    if db.query_one("SELECT 1 FROM users WHERE id=?", (to_id,)) is None:
        raise FriendError("No such player.")
    if count_friends(from_id) >= MAX_FRIENDS:
        raise FriendError("Your friends list is full.")
    if not db.rate_limit("friendreq:%d" % from_id, 30, 3600):
        raise FriendError("Slow down -- too many friend requests.")
    low, high = _pair(from_id, to_id)
    existing = relationship(from_id, to_id)
    now = _now()
    if existing:
        if existing["status"] == "accepted":
            return "friends"
        if existing["requester_id"] == from_id:
            return "pending_out"
        # They already asked us -- treat this as an accept.
        accept(from_id, to_id)
        return "friends"
    db.execute("INSERT INTO friendships(user_low,user_high,requester_id,status,"
               "created_at,updated_at) VALUES(?,?,?,'pending',?,?)",
               (low, high, from_id, now, now))
    return "pending_out"


def accept(user_id: int, other_id: int) -> None:
    rel = relationship(user_id, other_id)
    if not rel or rel["status"] != "pending":
        raise FriendError("There is no pending request from that player.")
    if rel["requester_id"] == user_id:
        raise FriendError("You cannot accept your own request.")
    if count_friends(user_id) >= MAX_FRIENDS:
        raise FriendError("Your friends list is full.")
    db.execute("UPDATE friendships SET status='accepted', updated_at=?"
               " WHERE id=?", (_now(), rel["id"]))


def decline(user_id: int, other_id: int) -> None:
    rel = relationship(user_id, other_id)
    if not rel:
        return
    db.execute("DELETE FROM friendships WHERE id=?", (rel["id"],))


def remove(user_id: int, other_id: int) -> None:
    decline(user_id, other_id)


def are_friends(user_a: int, user_b: int) -> bool:
    rel = relationship(user_a, user_b)
    return bool(rel and rel["status"] == "accepted")


def friend_ids(user_id: int) -> List[int]:
    rows = db.query(
        "SELECT user_low, user_high FROM friendships"
        " WHERE status='accepted' AND (user_low=? OR user_high=?)",
        (user_id, user_id))
    return [r["user_high"] if r["user_low"] == user_id else r["user_low"]
            for r in rows]


def list_friends(user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT u.* FROM friendships f"
        " JOIN users u ON u.id = CASE WHEN f.user_low=? THEN f.user_high"
        "                             ELSE f.user_low END"
        " WHERE f.status='accepted' AND (f.user_low=? OR f.user_high=?)"
        " ORDER BY u.last_seen DESC LIMIT ?",
        (user_id, user_id, user_id, limit))
    return db.rows_to_dicts(rows)


def count_friends(user_id: int) -> int:
    return int(db.scalar(
        "SELECT COUNT(*) FROM friendships WHERE status='accepted'"
        " AND (user_low=? OR user_high=?)", (user_id, user_id)))


def incoming_requests(user_id: int) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT u.*, f.created_at AS requested_at FROM friendships f"
        " JOIN users u ON u.id=f.requester_id"
        " WHERE f.status='pending' AND f.requester_id<>?"
        " AND (f.user_low=? OR f.user_high=?) ORDER BY f.created_at DESC",
        (user_id, user_id, user_id))
    return db.rows_to_dicts(rows)


def outgoing_requests(user_id: int) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT u.*, f.created_at AS requested_at FROM friendships f"
        " JOIN users u ON u.id = CASE WHEN f.user_low=? THEN f.user_high"
        "                             ELSE f.user_low END"
        " WHERE f.status='pending' AND f.requester_id=?"
        " AND (f.user_low=? OR f.user_high=?) ORDER BY f.created_at DESC",
        (user_id, user_id, user_id, user_id))
    return db.rows_to_dicts(rows)


def pending_count(user_id: int) -> int:
    return int(db.scalar(
        "SELECT COUNT(*) FROM friendships WHERE status='pending'"
        " AND requester_id<>? AND (user_low=? OR user_high=?)",
        (user_id, user_id, user_id)))


def mutual_friends(user_a: int, user_b: int) -> List[int]:
    return sorted(set(friend_ids(user_a)) & set(friend_ids(user_b)))
