"""The admin dashboard at /admin-dashboard.

Any signed-in player who is not an administrator is silently redirected to the
home page, and every mutation goes through exactly the same server side code
paths a normal player's actions would use (economy.adjust, inventory.grant,
...), so the dashboard can never create state the game cannot.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict

from .. import config, db
from ..game import registry as game_registry
from ..http import router as R
from ..http.router import Request
from ..models import avatars, catalog, economy, inventory, users, worlds
from ..social import comments, feed, posts
from .base import admin_required, api_error, api_ok, render, router

SUPERVISOR = None  # set by main.py so the dashboard can show host processes


def set_supervisor(supervisor) -> None:
    global SUPERVISOR
    SUPERVISOR = supervisor


def _live_payload() -> Dict[str, Any]:
    world_rows = []
    for world in worlds.all_worlds():
        status = game_registry.world_status(world["id"])
        stats = worlds.stats(world["id"])
        world_rows.append({
            "id": world["id"], "name": world["name"],
            "players": status["players"], "instances": status["instances"],
            "capacity": world["max_players"], "online": status["online"],
            "visits": stats["visits"], "rating": stats["rating"],
            "tick_ms": status.get("tick_ms", 0),
            "instance_list": status.get("instance_list", []),
        })
    snapshot = feed.stats_snapshot()
    money = economy.totals()
    return {
        "at": int(time.time()),
        "worlds": world_rows,
        "site": snapshot,
        "money": money,
        "online_users": len(users.online_users(200)),
        "in_game": game_registry.total_players(),
        "hosts": SUPERVISOR.status() if SUPERVISOR else [],
        # NOTE: not called "items" -- that name collides with dict.items in templates
        "item_stats": inventory.global_stats(),
    }


@router.get("/admin-dashboard")
@admin_required
def dashboard(req: Request):
    term = req.query.get("q", "")
    return render(req, "admin.html",
                  live=_live_payload(),
                  user_rows=users.search(term, 40),
                  term=term,
                  audit=db.rows_to_dicts(db.query(
                      "SELECT a.*, u.username FROM audit_log a"
                      " LEFT JOIN users u ON u.id=a.actor_id"
                      " ORDER BY a.id DESC LIMIT 40")),
                  ledger=db.rows_to_dicts(db.query(
                      "SELECT l.*, u.username FROM credit_ledger l"
                      " JOIN users u ON u.id=l.user_id"
                      " ORDER BY l.id DESC LIMIT 25")),
                  catalogue=catalog.ALL_ITEMS,
                  effects=catalog.UNUSUAL_EFFECTS,
                  server={
                      "pid": os.getpid(),
                      "port": config.HTTP_PORT,
                      "python": "%d.%d" % (os.sys.version_info[:2]),
                      "db": str(config.DB_PATH),
                  })


@router.get("/api/admin/live")
@admin_required
def live(req: Request):
    return api_ok(**_live_payload())


@router.get("/api/admin/user")
@admin_required
def admin_user(req: Request):
    target = users.get_by_username(req.query.get("username", ""))
    if target is None:
        return api_error("No such player.", 404)
    uid = int(target["id"])
    return api_ok(user=users.public(target),
                  credits=economy.balance(uid),
                  inventory=inventory.list_for_user(uid),
                  ledger=economy.history(uid, 20),
                  avatar=avatars.descriptor(uid, target["username"]),
                  stats=worlds.player_stats(uid))


@router.post("/api/admin/credits")
@admin_required
def admin_credits(req: Request):
    data = req.data()
    target = users.get_by_username(str(data.get("username", "")))
    if target is None:
        return api_error("No such player.")
    mode = str(data.get("mode", "add"))
    try:
        amount = int(data.get("amount", 0))
    except (TypeError, ValueError):
        return api_error("Amount must be a whole number.")
    reason = str(data.get("reason", "")).strip()[:100] or "Admin adjustment"
    actor = int(req.user["id"])
    uid = int(target["id"])
    try:
        if mode == "set":
            balance = economy.set_balance(uid, amount, "Admin set: %s" % reason,
                                          actor)
        else:
            balance = economy.adjust(uid, amount, "Admin: %s" % reason, actor,
                                     allow_negative=True)
    except economy.EconomyError as exc:
        return api_error(str(exc))
    db.audit(actor, "admin.credits", target["username"],
             {"mode": mode, "amount": amount, "balance": balance,
              "reason": reason})
    return api_ok(balance=balance, username=target["username"])


@router.post("/api/admin/grant")
@admin_required
def admin_grant(req: Request):
    data = req.data()
    target = users.get_by_username(str(data.get("username", "")))
    if target is None:
        return api_error("No such player.")
    item_id = str(data.get("item_id", ""))
    if catalog.get(item_id) is None:
        return api_error("Unknown item.")
    tier = str(data.get("tier", "normal"))
    effect = str(data.get("effect", "")) or None
    if tier not in catalog.TIERS:
        return api_error("Unknown tier.")
    if tier == "unusual" and catalog.get(item_id)["slot"] != "hat":
        return api_error("Only hats can be Unusual.")
    row = inventory.grant(int(target["id"]), item_id, source="admin",
                          allow_unusual=False, force_tier=tier,
                          force_effect=effect)
    db.audit(int(req.user["id"]), "admin.grant", target["username"], row)
    return api_ok(item=row)


@router.post("/api/admin/revoke")
@admin_required
def admin_revoke(req: Request):
    data = req.data()
    target = users.get_by_username(str(data.get("username", "")))
    if target is None:
        return api_error("No such player.")
    try:
        inv_id = int(data.get("inv_id", 0))
    except (TypeError, ValueError):
        return api_error("Bad item.")
    row = inventory.get_row(int(target["id"]), inv_id)
    if row is None:
        return api_error("They do not own that.")
    db.execute("DELETE FROM inventory WHERE id=?", (inv_id,))
    avatars.unequip_missing(int(target["id"]))
    db.audit(int(req.user["id"]), "admin.revoke", target["username"],
             {"inv_id": inv_id, "item": row["item_id"]})
    return api_ok()


@router.post("/api/admin/ban")
@admin_required
def admin_ban(req: Request):
    data = req.data()
    target = users.get_by_username(str(data.get("username", "")))
    if target is None:
        return api_error("No such player.")
    if bool(target["is_admin"]):
        return api_error("Administrators cannot be suspended.")
    state = 0 if int(target["is_banned"]) else 1
    db.execute("UPDATE users SET is_banned=? WHERE id=?", (state, target["id"]))
    if state:
        db.execute("DELETE FROM sessions WHERE user_id=?", (target["id"],))
    db.audit(int(req.user["id"]), "admin.ban", target["username"],
             {"banned": bool(state)})
    return api_ok(banned=bool(state))


@router.post("/api/admin/announce")
@admin_required
def admin_announce(req: Request):
    text = str(req.data().get("text", "")).strip()[:200]
    if not text:
        return api_error("Nothing to announce.")
    db.set_meta("announcement", text)
    db.set_meta("announcement_at", str(int(time.time())))
    db.audit(int(req.user["id"]), "admin.announce", "", text)
    return api_ok(text=text)


@router.post("/api/admin/moderate")
@admin_required
def admin_moderate(req: Request):
    data = req.data()
    kind = str(data.get("kind", ""))
    try:
        target_id = int(data.get("id", 0))
    except (TypeError, ValueError):
        return api_error("Bad id.")
    actor = int(req.user["id"])
    if kind == "post":
        posts.delete(target_id, actor, True)
    elif kind == "profile_comment":
        comments.delete_profile_comment(target_id, actor, True)
    elif kind == "post_comment":
        comments.delete_post_comment(target_id, actor, True)
    else:
        return api_error("Unknown target.")
    db.audit(actor, "admin.moderate", kind, {"id": target_id})
    return api_ok()
