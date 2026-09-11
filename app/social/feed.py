"""Site-wide activity feed assembled from the other social modules."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from .. import db


def recent_activity(limit: int = 18) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for row in db.query(
            "SELECT p.id, p.body, p.created_at, u.username FROM posts p"
            " JOIN users u ON u.id=p.user_id WHERE p.hidden=0"
            " ORDER BY p.id DESC LIMIT ?", (limit,)):
        events.append({"kind": "post", "username": row["username"],
                       "text": row["body"], "at": row["created_at"],
                       "link": "/profile/%s" % row["username"]})
    for row in db.query(
            "SELECT i.acquired_at, i.tier, u.username, i.item_id FROM inventory i"
            " JOIN users u ON u.id=i.user_id WHERE i.source='market'"
            " ORDER BY i.id DESC LIMIT ?", (limit,)):
        from ..models import catalog
        item = catalog.get(row["item_id"])
        if not item:
            continue
        events.append({
            "kind": "unusual" if row["tier"] == "unusual" else "purchase",
            "username": row["username"],
            "text": ("unboxed an UNUSUAL %s!" if row["tier"] == "unusual"
                     else "bought %s") % item["name"],
            "at": row["acquired_at"],
            "link": "/market?q=%s" % item["name"].replace(" ", "+")})
    for row in db.query(
            "SELECT f.updated_at, a.username AS ua, b.username AS ub"
            " FROM friendships f JOIN users a ON a.id=f.user_low"
            " JOIN users b ON b.id=f.user_high WHERE f.status='accepted'"
            " ORDER BY f.updated_at DESC LIMIT ?", (limit,)):
        events.append({"kind": "friend", "username": row["ua"],
                       "text": "is now friends with %s" % row["ub"],
                       "at": row["updated_at"],
                       "link": "/profile/%s" % row["ub"]})
    for row in db.query(
            "SELECT v.created_at, v.world_id, u.username FROM world_visits v"
            " JOIN users u ON u.id=v.user_id ORDER BY v.id DESC LIMIT ?",
            (limit,)):
        from ..models import worlds
        world = worlds.get(row["world_id"])
        if not world:
            continue
        events.append({"kind": "visit", "username": row["username"],
                       "text": "played %s" % world["name"],
                       "at": row["created_at"],
                       "link": "/worlds/%s" % row["world_id"]})
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]


def stats_snapshot() -> Dict[str, int]:
    now = int(time.time())
    day = now - 86400
    return {
        "users": int(db.scalar("SELECT COUNT(*) FROM users")),
        "new_users_today": int(db.scalar(
            "SELECT COUNT(*) FROM users WHERE created_at > ?", (day,))),
        "posts": int(db.scalar("SELECT COUNT(*) FROM posts")),
        "messages": int(db.scalar("SELECT COUNT(*) FROM messages")),
        "friendships": int(db.scalar(
            "SELECT COUNT(*) FROM friendships WHERE status='accepted'")),
        "items_owned": int(db.scalar("SELECT COUNT(*) FROM inventory")),
        "unusuals": int(db.scalar(
            "SELECT COUNT(*) FROM inventory WHERE tier='unusual'")),
        "visits": int(db.scalar("SELECT COALESCE(SUM(visits),0) FROM world_stats")),
    }
