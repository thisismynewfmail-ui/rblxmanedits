"""Per-account item ownership.

Each owned copy of an item is its own row, which is what makes per-copy
properties (Unusual tiers, effects, serial numbers) possible.  Equipping always
references an inventory *row id*, so a player wearing an Unusual hat is wearing
that specific copy.
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from .. import config, db
from . import catalog


class InventoryError(Exception):
    pass


def _now() -> int:
    return int(time.time())


def roll_tier(item: Dict[str, Any], allow_unusual: bool = True) -> Dict[str, str]:
    """Unusual rolls only ever apply to hat-slot cosmetics."""
    if allow_unusual and item.get("slot") == "hat":
        if random.random() < config.UNUSUAL_CHANCE:
            return {"tier": "unusual",
                    "effect": random.choice(catalog.EFFECT_IDS)}
    return {"tier": "normal", "effect": ""}


def grant(user_id: int, item_id: str, source: str = "market",
          allow_unusual: bool = True, force_tier: Optional[str] = None,
          force_effect: Optional[str] = None) -> Dict[str, Any]:
    item = catalog.get(item_id)
    if item is None:
        raise InventoryError("Unknown item.")
    if force_tier:
        tier = {"tier": force_tier,
                "effect": force_effect or (random.choice(catalog.EFFECT_IDS)
                                           if force_tier == "unusual" else "")}
    else:
        tier = roll_tier(item, allow_unusual)
    serial = int(db.scalar("SELECT COUNT(*) FROM inventory WHERE item_id=?",
                           (item_id,))) + 1
    cur = db.execute(
        "INSERT INTO inventory(user_id,item_id,tier,effect,serial,acquired_at,source)"
        " VALUES(?,?,?,?,?,?,?)",
        (user_id, item_id, tier["tier"], tier["effect"], serial, _now(), source))
    return {"id": int(cur.lastrowid), "item_id": item_id, "tier": tier["tier"],
            "effect": tier["effect"], "serial": serial}


def owns_item(user_id: int, item_id: str) -> bool:
    return db.query_one(
        "SELECT 1 FROM inventory WHERE user_id=? AND item_id=? LIMIT 1",
        (user_id, item_id)) is not None


def count_of(user_id: int, item_id: str) -> int:
    return int(db.scalar(
        "SELECT COUNT(*) FROM inventory WHERE user_id=? AND item_id=?",
        (user_id, item_id)))


def get_row(user_id: int, inv_id: int) -> Optional[Dict[str, Any]]:
    return db.row_to_dict(db.query_one(
        "SELECT * FROM inventory WHERE id=? AND user_id=?", (inv_id, user_id)))


def first_of(user_id: int, item_id: str) -> Optional[Dict[str, Any]]:
    return db.row_to_dict(db.query_one(
        "SELECT * FROM inventory WHERE user_id=? AND item_id=?"
        " ORDER BY (tier='unusual') DESC, id ASC LIMIT 1", (user_id, item_id)))


def decorate(row: Dict[str, Any]) -> Dict[str, Any]:
    """Merge an inventory row with its catalogue entry for display/render."""
    item = catalog.get(row["item_id"]) or {
        "id": row["item_id"], "name": row["item_id"], "slot": "unknown",
        "price": 0, "rarity": "common", "description": "", "data": {}}
    tier = catalog.TIERS.get(row.get("tier", "normal"), catalog.TIERS["normal"])
    effect = catalog.UNUSUAL_EFFECTS.get(row.get("effect") or "")
    return db.AttrDict({
        "inv_id": row["id"],
        "item_id": item["id"],
        "name": item["name"],
        "slot": item["slot"],
        "slot_label": catalog.SLOT_LABELS.get(item["slot"], item["slot"]),
        "price": item.get("price", 0),
        "rarity": item.get("rarity", "common"),
        "description": item.get("description", ""),
        "data": item.get("data", {}),
        "tier": tier["id"],
        "tier_label": tier["label"],
        "tier_color": tier["color"],
        "tier_text": tier["text"],
        "tier_border": tier["border"],
        "tier_glow": tier["glow"],
        "effect": row.get("effect") or "",
        "effect_name": effect["name"] if effect else "",
        "serial": row.get("serial", 0),
        "acquired_at": row.get("acquired_at", 0),
        "source": row.get("source", ""),
        "is_default": bool(item.get("is_default")),
    })


def list_for_user(user_id: int, slot: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = db.rows_to_dicts(db.query(
        "SELECT * FROM inventory WHERE user_id=? ORDER BY id DESC", (user_id,)))
    items = [decorate(r) for r in rows]
    if slot:
        items = [i for i in items if i["slot"] == slot]
    return items


def summary(user_id: int) -> Dict[str, int]:
    rows = db.query(
        "SELECT tier, COUNT(*) AS n FROM inventory WHERE user_id=? GROUP BY tier",
        (user_id,))
    out = {"total": 0, "normal": 0, "unusual": 0}
    for row in rows:
        out[row["tier"]] = out.get(row["tier"], 0) + int(row["n"])
        out["total"] += int(row["n"])
    return out


def global_stats() -> Dict[str, int]:
    return {
        "copies": int(db.scalar("SELECT COUNT(*) FROM inventory")),
        "unusuals": int(db.scalar(
            "SELECT COUNT(*) FROM inventory WHERE tier='unusual'")),
        "catalogue": len(catalog.ALL_ITEMS),
    }


def unusual_showcase(limit: int = 12) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT i.*, u.username FROM inventory i JOIN users u ON u.id=i.user_id"
        " WHERE i.tier='unusual' ORDER BY i.id DESC LIMIT ?", (limit,))
    out = []
    for row in rows:
        data = decorate(dict(row))
        data["username"] = row["username"]
        out.append(data)
    return out
