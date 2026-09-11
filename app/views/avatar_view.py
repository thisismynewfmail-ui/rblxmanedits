"""The avatar editor: body colours, cosmetic slots and the 5-slot hotbar."""
from __future__ import annotations

from ..http import router as R
from ..http.router import Request
from ..models import avatars, catalog, inventory
from .base import api_error, api_ok, login_required, render, router


@router.get("/avatar")
@login_required
def avatar_editor(req: Request):
    uid = int(req.user["id"])
    owned = inventory.list_for_user(uid)
    by_slot = {}
    for item in owned:
        by_slot.setdefault(item["slot"], []).append(item)
    raw = avatars.raw_avatar(uid)
    return render(
        req, "avatar.html",
        avatar=avatars.descriptor(uid, req.user["username"]),
        raw=raw,
        owned=owned,
        by_slot=by_slot,
        palette=catalog.BODY_PALETTE,
        body_parts=catalog.BODY_PARTS,
        slots=catalog.SLOTS,
        slot_labels=catalog.SLOT_LABELS,
        hotbar_size=catalog.HOTBAR_SIZE,
        welcome=req.query.get("welcome") == "1",
        tiers=catalog.TIERS,
    )


@router.post("/api/avatar/colors")
@login_required
def set_colors(req: Request):
    data = req.data()
    colors = data.get("colors")
    if not isinstance(colors, dict):
        colors = {k: v for k, v in data.items() if k in catalog.BODY_PARTS}
    try:
        merged = avatars.set_colors(int(req.user["id"]), colors)
    except avatars.AvatarError as exc:
        return api_error(str(exc))
    return api_ok(colors=merged,
                  avatar=avatars.descriptor(int(req.user["id"]),
                                            req.user["username"]))


@router.post("/api/avatar/equip")
@login_required
def equip(req: Request):
    data = req.data()
    try:
        inv_id = int(data.get("inv_id", 0) or 0)
    except (TypeError, ValueError):
        return api_error("Bad item.")
    try:
        avatars.equip(int(req.user["id"]), str(data.get("slot", "")), inv_id)
    except avatars.AvatarError as exc:
        return api_error(str(exc))
    return api_ok(avatar=avatars.descriptor(int(req.user["id"]),
                                            req.user["username"]))


@router.post("/api/avatar/hotbar")
@login_required
def hotbar(req: Request):
    data = req.data()
    try:
        index = int(data.get("index", -1))
        inv_id = int(data.get("inv_id", 0) or 0)
    except (TypeError, ValueError):
        return api_error("Bad slot.")
    try:
        slots = avatars.set_hotbar_slot(int(req.user["id"]), index, inv_id)
    except avatars.AvatarError as exc:
        return api_error(str(exc))
    return api_ok(hotbar=slots,
                  avatar=avatars.descriptor(int(req.user["id"]),
                                            req.user["username"]))


@router.get("/api/avatar")
@login_required
def my_avatar(req: Request):
    return api_ok(avatar=avatars.descriptor(int(req.user["id"]),
                                            req.user["username"]))
