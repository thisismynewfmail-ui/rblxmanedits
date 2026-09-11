"""Private messaging.

Reads are strictly scoped: a message row is only ever returned to its sender
or its recipient, and deletion is per-side so one player cannot destroy the
other's copy.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .. import db, security

SUBJECT_MAX = 80
BODY_MAX = 2000


class MessageError(Exception):
    pass


def send(sender_id: int, recipient_name: str, subject: str, body: str,
         reply_to: Optional[int] = None) -> int:
    from ..models import users
    recipient = users.get_by_username(recipient_name)
    if recipient is None:
        raise MessageError("There is nobody called '%s'." % recipient_name)
    if int(recipient["id"]) == sender_id:
        raise MessageError("You cannot message yourself.")
    subject = security.clean_text(subject, SUBJECT_MAX, allow_newlines=False) or "(no subject)"
    body = security.clean_text(body, BODY_MAX)
    if not body:
        raise MessageError("Your message is empty.")
    if not db.rate_limit("msg:%d" % sender_id, 20, 600):
        raise MessageError("You are sending messages too quickly.")
    cur = db.execute(
        "INSERT INTO messages(sender_id,recipient_id,subject,body,created_at,"
        "reply_to) VALUES(?,?,?,?,?,?)",
        (sender_id, int(recipient["id"]), subject, body, int(time.time()),
         reply_to))
    return int(cur.lastrowid)


def inbox(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT m.*, u.username AS sender_name FROM messages m"
        " JOIN users u ON u.id=m.sender_id"
        " WHERE m.recipient_id=? AND m.del_recipient=0"
        " ORDER BY m.id DESC LIMIT ?", (user_id, limit)))


def sent(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT m.*, u.username AS recipient_name FROM messages m"
        " JOIN users u ON u.id=m.recipient_id"
        " WHERE m.sender_id=? AND m.del_sender=0 ORDER BY m.id DESC LIMIT ?",
        (user_id, limit)))


def get(message_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT m.*, s.username AS sender_name, r.username AS recipient_name"
        " FROM messages m JOIN users s ON s.id=m.sender_id"
        " JOIN users r ON r.id=m.recipient_id WHERE m.id=?", (message_id,))
    if row is None:
        return None
    data = dict(row)
    if user_id not in (int(data["sender_id"]), int(data["recipient_id"])):
        return None
    if user_id == int(data["recipient_id"]) and data["del_recipient"]:
        return None
    if user_id == int(data["sender_id"]) and data["del_sender"] and \
            user_id != int(data["recipient_id"]):
        return None
    return data


def mark_read(message_id: int, user_id: int) -> None:
    db.execute("UPDATE messages SET read_at=? WHERE id=? AND recipient_id=?"
               " AND read_at=0", (int(time.time()), message_id, user_id))


def delete(message_id: int, user_id: int) -> None:
    row = db.query_one("SELECT sender_id, recipient_id FROM messages WHERE id=?",
                       (message_id,))
    if row is None:
        return
    if int(row["recipient_id"]) == user_id:
        db.execute("UPDATE messages SET del_recipient=1 WHERE id=?", (message_id,))
    if int(row["sender_id"]) == user_id:
        db.execute("UPDATE messages SET del_sender=1 WHERE id=?", (message_id,))
    db.execute("DELETE FROM messages WHERE id=? AND del_sender=1 AND"
               " del_recipient=1", (message_id,))


def unread_count(user_id: int) -> int:
    return int(db.scalar(
        "SELECT COUNT(*) FROM messages WHERE recipient_id=? AND read_at=0"
        " AND del_recipient=0", (user_id,)))


def total() -> int:
    return int(db.scalar("SELECT COUNT(*) FROM messages"))
