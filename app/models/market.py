"""The item market.

Prices are read from the server side catalogue only.  The client sends an item
id and nothing else, so a modified request cannot change a price, grant a free
item, or force an Unusual roll.
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from .. import config, db
from . import catalog, inventory


class MarketError(Exception):
    pass


def listing(slot: Optional[str] = None, sort: str = "featured",
            search: str = "") -> List[Dict[str, Any]]:
    items = [it for it in catalog.ALL_ITEMS if not it.get("hidden")]
    if slot and slot != "all":
        items = [it for it in items if it["slot"] == slot]
    term = (search or "").strip().lower()
    if term:
        items = [it for it in items
                 if term in it["name"].lower() or term in it["id"].lower()]
    if sort == "price_asc":
        items.sort(key=lambda i: (i.get("price", 0), i["name"]))
    elif sort == "price_desc":
        items.sort(key=lambda i: (-i.get("price", 0), i["name"]))
    elif sort == "name":
        items.sort(key=lambda i: i["name"].lower())
    else:
        order = {"hat": 0, "face": 1, "shirt": 2, "pants": 3, "back": 4,
                 "usable": 5}
        items.sort(key=lambda i: (order.get(i["slot"], 9),
                                  i.get("sort_order", 0), i["name"]))
    return [_card(it) for it in items]


def _card(item: Dict[str, Any]) -> Dict[str, Any]:
    return db.AttrDict({
        "id": item["id"],
        "name": item["name"],
        "slot": item["slot"],
        "slot_label": catalog.SLOT_LABELS.get(item["slot"], item["slot"]),
        "price": item.get("price", 0),
        "rarity": item.get("rarity", "common"),
        "description": item.get("description", ""),
        "data": item.get("data", {}),
        "free": item.get("price", 0) <= 0,
        "unusual_capable": item["slot"] == "hat",
    })


def purchase(user_id: int, item_id: str) -> Dict[str, Any]:
    """Buy one copy of an item. Atomic: charge + grant happen together."""
    item = catalog.get(item_id)
    if item is None:
        raise MarketError("That item is not in the catalogue.")
    price = int(item.get("price", 0))
    if price < 0:
        raise MarketError("That item is not for sale.")
    if price == 0 and inventory.owns_item(user_id, item_id):
        raise MarketError("You already own %s." % item["name"])

    # Unusual roll happens here, server side, before anything is written.
    unusual = (item["slot"] == "hat"
               and random.random() < config.UNUSUAL_CHANCE)
    effect = random.choice(catalog.EFFECT_IDS) if unusual else ""
    tier = "unusual" if unusual else "normal"
    now = int(time.time())

    with db.transaction() as conn:
        row = conn.execute("SELECT credits, username FROM users WHERE id=?",
                           (user_id,)).fetchone()
        if row is None:
            raise MarketError("No such account.")
        credits = int(row["credits"])
        if credits < price:
            raise MarketError("You need %s more credits for %s."
                              % (f"{price - credits:,}", item["name"]))
        new_balance = credits - price
        conn.execute("UPDATE users SET credits=? WHERE id=?",
                     (new_balance, user_id))
        conn.execute(
            "INSERT INTO credit_ledger(user_id,delta,balance_after,reason,"
            "actor_id,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, -price, new_balance, "Bought %s" % item["name"],
             None, now))
        serial = int(conn.execute(
            "SELECT COUNT(*) FROM inventory WHERE item_id=?",
            (item_id,)).fetchone()[0]) + 1
        cur = conn.execute(
            "INSERT INTO inventory(user_id,item_id,tier,effect,serial,"
            "acquired_at,source) VALUES(?,?,?,?,?,?,?)",
            (user_id, item_id, tier, effect, serial, now, "market"))
        inv_id = int(cur.lastrowid)

    db.audit(user_id, "market.purchase", item_id,
             {"price": price, "tier": tier, "effect": effect, "inv_id": inv_id})
    result = {
        "inv_id": inv_id, "item_id": item_id, "name": item["name"],
        "slot": item["slot"], "price": price, "tier": tier, "effect": effect,
        "effect_name": (catalog.UNUSUAL_EFFECTS[effect]["name"] if effect else ""),
        "balance": new_balance, "serial": serial,
    }
    return result


def sell_back(user_id: int, inv_id: int) -> Dict[str, Any]:
    """Refund an owned copy for 40% of its catalogue price."""
    row = inventory.get_row(user_id, inv_id)
    if row is None:
        raise MarketError("You do not own that item.")
    item = catalog.get(row["item_id"])
    if item is None:
        raise MarketError("Unknown item.")
    if item.get("is_default"):
        raise MarketError("Starter equipment cannot be sold.")
    refund = int(item.get("price", 0) * 0.4)
    now = int(time.time())
    with db.transaction() as conn:
        owned = conn.execute("SELECT 1 FROM inventory WHERE id=? AND user_id=?",
                             (inv_id, user_id)).fetchone()
        if owned is None:
            raise MarketError("You do not own that item.")
        conn.execute("DELETE FROM inventory WHERE id=? AND user_id=?",
                     (inv_id, user_id))
        if refund > 0:
            credits = int(conn.execute("SELECT credits FROM users WHERE id=?",
                                       (user_id,)).fetchone()["credits"])
            new_balance = min(config.MAX_CREDITS, credits + refund)
            conn.execute("UPDATE users SET credits=? WHERE id=?",
                         (new_balance, user_id))
            conn.execute(
                "INSERT INTO credit_ledger(user_id,delta,balance_after,reason,"
                "actor_id,created_at) VALUES(?,?,?,?,?,?)",
                (user_id, refund, new_balance, "Sold %s" % item["name"], None, now))
    from . import avatars
    avatars.unequip_missing(user_id)
    db.audit(user_id, "market.sell", row["item_id"], {"refund": refund})
    return {"refund": refund, "item_id": row["item_id"]}
