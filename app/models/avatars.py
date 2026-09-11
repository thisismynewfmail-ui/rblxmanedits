"""The avatar base system: body colours, cosmetic slots and the hotbar.

The whole system is slot driven so new slots or new items only need a
catalogue entry.  Everything that leaves this module is a *descriptor*: a
plain, fully resolved dict the renderer (browser) and the game hosts consume
without needing database access.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from .. import db, security
from . import catalog, inventory


class AvatarError(Exception):
    pass


def _now() -> int:
    return int(time.time())


def _load_json(raw: Any, fallback: Any) -> Any:
    try:
        value = json.loads(raw)
        if isinstance(value, type(fallback)):
            return value
    except Exception:
        pass
    return fallback


def raw_avatar(user_id: int) -> Dict[str, Any]:
    row = db.query_one("SELECT * FROM avatars WHERE user_id=?", (user_id,))
    if row is None:
        db.execute("INSERT OR IGNORE INTO avatars(user_id,colors,equipped,hotbar,"
                   "updated_at) VALUES(?,?,?,?,?)",
                   (user_id, json.dumps(catalog.DEFAULT_COLORS), "{}", "[]", _now()))
        row = db.query_one("SELECT * FROM avatars WHERE user_id=?", (user_id,))
    colors = _load_json(row["colors"], {})
    equipped = _load_json(row["equipped"], {})
    hotbar = _load_json(row["hotbar"], [])
    merged = dict(catalog.DEFAULT_COLORS)
    for part in catalog.BODY_PARTS:
        value = colors.get(part)
        if isinstance(value, str) and security.valid_color(value):
            merged[part] = value
    hotbar = [int(x) if isinstance(x, (int, float)) and int(x) > 0 else 0
              for x in hotbar][:catalog.HOTBAR_SIZE]
    hotbar += [0] * (catalog.HOTBAR_SIZE - len(hotbar))
    clean_equipped: Dict[str, int] = {}
    for slot in catalog.SLOTS:
        value = equipped.get(slot)
        if isinstance(value, (int, float)) and int(value) > 0:
            clean_equipped[slot] = int(value)
    return {"user_id": user_id, "colors": merged, "equipped": clean_equipped,
            "hotbar": hotbar, "updated_at": row["updated_at"]}


def _save(user_id: int, colors: Dict[str, str], equipped: Dict[str, int],
          hotbar: List[int]) -> None:
    db.execute("UPDATE avatars SET colors=?, equipped=?, hotbar=?, updated_at=?"
               " WHERE user_id=?",
               (json.dumps(colors, separators=(",", ":")),
                json.dumps(equipped, separators=(",", ":")),
                json.dumps(hotbar, separators=(",", ":")), _now(), user_id))


def apply_defaults(user_id: int) -> None:
    """Equip the free starter cosmetics and fill the default hotbar."""
    avatar = raw_avatar(user_id)
    equipped = dict(avatar["equipped"])
    for slot, item_id in catalog.DEFAULT_EQUIPPED.items():
        if not item_id or slot in equipped:
            continue
        row = inventory.first_of(user_id, item_id)
        if row:
            equipped[slot] = row["id"]
    hotbar = list(avatar["hotbar"])
    for index, item_id in enumerate(catalog.DEFAULT_HOTBAR):
        if index >= catalog.HOTBAR_SIZE or not item_id or hotbar[index]:
            continue
        row = inventory.first_of(user_id, item_id)
        if row:
            hotbar[index] = row["id"]
    _save(user_id, avatar["colors"], equipped, hotbar)


# ------------------------------------------------------------------- mutation

def set_colors(user_id: int, colors: Dict[str, str]) -> Dict[str, str]:
    avatar = raw_avatar(user_id)
    merged = dict(avatar["colors"])
    for part, value in (colors or {}).items():
        if part not in catalog.BODY_PARTS:
            continue
        if not isinstance(value, str) or not security.valid_color(value):
            raise AvatarError("Invalid colour for %s." % part)
        merged[part] = value.lower()
    _save(user_id, merged, avatar["equipped"], avatar["hotbar"])
    return merged


def equip(user_id: int, slot: str, inv_id: int) -> Dict[str, Any]:
    """Equip an owned copy into a cosmetic slot. ``inv_id`` 0 clears the slot."""
    if slot not in catalog.SLOTS:
        raise AvatarError("Unknown slot.")
    avatar = raw_avatar(user_id)
    equipped = dict(avatar["equipped"])
    inv_id = int(inv_id or 0)
    if inv_id <= 0:
        equipped.pop(slot, None)
    else:
        row = inventory.get_row(user_id, inv_id)
        if row is None:
            raise AvatarError("You do not own that item.")
        item = catalog.get(row["item_id"])
        if item is None:
            raise AvatarError("That item no longer exists.")
        if item["slot"] != slot:
            raise AvatarError("A %s cannot go in the %s slot."
                              % (item["slot"], slot))
        equipped[slot] = inv_id
    _save(user_id, avatar["colors"], equipped, avatar["hotbar"])
    return equipped


def set_hotbar_slot(user_id: int, index: int, inv_id: int) -> List[int]:
    index = int(index)
    if not (0 <= index < catalog.HOTBAR_SIZE):
        raise AvatarError("Hotbar slot out of range.")
    avatar = raw_avatar(user_id)
    hotbar = list(avatar["hotbar"])
    inv_id = int(inv_id or 0)
    if inv_id <= 0:
        hotbar[index] = 0
    else:
        row = inventory.get_row(user_id, inv_id)
        if row is None:
            raise AvatarError("You do not own that item.")
        item = catalog.get(row["item_id"])
        if item is None or item["slot"] != "usable":
            raise AvatarError("Only usable items go on the hotbar.")
        for other in range(catalog.HOTBAR_SIZE):
            if other != index and hotbar[other] == inv_id:
                hotbar[other] = 0
        hotbar[index] = inv_id
    _save(user_id, avatar["colors"], avatar["equipped"], hotbar)
    return hotbar


def unequip_missing(user_id: int) -> None:
    """Drop references to inventory rows that no longer exist."""
    avatar = raw_avatar(user_id)
    equipped = {slot: inv for slot, inv in avatar["equipped"].items()
                if inventory.get_row(user_id, inv)}
    hotbar = [inv if inv and inventory.get_row(user_id, inv) else 0
              for inv in avatar["hotbar"]]
    if equipped != avatar["equipped"] or hotbar != avatar["hotbar"]:
        _save(user_id, avatar["colors"], equipped, hotbar)


# ----------------------------------------------------------------- descriptor

def descriptor(user_id: int, username: Optional[str] = None) -> Dict[str, Any]:
    """Fully resolved avatar used by every renderer and by the game hosts."""
    avatar = raw_avatar(user_id)
    if username is None:
        username = db.scalar("SELECT username FROM users WHERE id=?",
                             (user_id,), "Player")
    items: Dict[str, Any] = {}
    for slot, inv_id in avatar["equipped"].items():
        row = inventory.get_row(user_id, inv_id)
        if row is None:
            continue
        item = catalog.get(row["item_id"])
        if item is None or item["slot"] != slot:
            continue
        items[slot] = _item_payload(item, row)
    hotbar: List[Optional[Dict[str, Any]]] = []
    for inv_id in avatar["hotbar"]:
        entry = None
        if inv_id:
            row = inventory.get_row(user_id, inv_id)
            if row:
                item = catalog.get(row["item_id"])
                if item and item["slot"] == "usable":
                    entry = _item_payload(item, row)
        hotbar.append(entry)
    return {
        "user_id": user_id,
        "username": username,
        "colors": avatar["colors"],
        "items": items,
        "hotbar": hotbar,
        "updated_at": avatar["updated_at"],
    }


def _item_payload(item: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    tier = catalog.TIERS.get(row.get("tier", "normal"), catalog.TIERS["normal"])
    effect_id = row.get("effect") or ""
    payload = {
        "inv_id": row["id"],
        "item_id": item["id"],
        "name": item["name"],
        "slot": item["slot"],
        "tier": tier["id"],
        "tier_color": tier["color"],
        "effect": effect_id,
        "data": item.get("data", {}),
    }
    if effect_id and effect_id in catalog.UNUSUAL_EFFECTS:
        payload["effect_def"] = catalog.UNUSUAL_EFFECTS[effect_id]
    return payload


def default_descriptor(username: str = "Guest") -> Dict[str, Any]:
    face = catalog.get("face_smile")
    return {
        "user_id": 0,
        "username": username,
        "colors": dict(catalog.DEFAULT_COLORS),
        "items": {"face": {"inv_id": 0, "item_id": "face_smile",
                           "name": "Smile", "slot": "face", "tier": "normal",
                           "tier_color": "#e8b71a", "effect": "",
                           "data": face["data"] if face else {}}},
        "hotbar": [None] * catalog.HOTBAR_SIZE,
        "updated_at": 0,
    }
