"""Catalogue browsing, buying and the personal inventory."""
from __future__ import annotations

from ..http import router as R
from ..http.router import Request
from ..models import avatars, catalog, economy, inventory, market
from .base import api_error, api_ok, login_required, render, router

SLOT_TABS = [("all", "Everything"), ("hat", "Hats"), ("face", "Faces"),
             ("shirt", "Shirts"), ("pants", "Pants"), ("back", "Back"),
             ("usable", "Usables")]


@router.get("/market")
def market_page(req: Request):
    slot = req.query.get("slot", "all")
    sort = req.query.get("sort", "featured")
    term = req.query.get("q", "")
    items = market.listing(slot, sort, term)
    owned = {}
    if req.user:
        for row in inventory.list_for_user(int(req.user["id"])):
            owned[row["item_id"]] = owned.get(row["item_id"], 0) + 1
    return render(req, "market.html", items=items, slot=slot, sort=sort,
                  term=term, tabs=SLOT_TABS, owned=owned,
                  tiers=catalog.TIERS,
                  unusual_chance=0.5,
                  effects=catalog.UNUSUAL_EFFECTS,
                  showcase=inventory.unusual_showcase(8))


@router.get("/inventory")
@login_required
def inventory_page(req: Request):
    uid = int(req.user["id"])
    slot = req.query.get("slot", "all")
    items = inventory.list_for_user(uid)
    if slot != "all":
        items = [i for i in items if i["slot"] == slot]
    raw = avatars.raw_avatar(uid)
    equipped_ids = set(raw["equipped"].values())
    hotbar_ids = set(x for x in raw["hotbar"] if x)
    return render(req, "inventory.html", items=items, slot=slot,
                  tabs=SLOT_TABS, summary=inventory.summary(uid),
                  equipped=equipped_ids, hotbar=hotbar_ids,
                  tiers=catalog.TIERS, ledger=economy.history(uid, 12))


@router.get("/inventory/<username>")
def inventory_of(req: Request, username: str = ""):
    from ..models import users
    target = users.get_by_username(username)
    if target is None:
        return R.error(404, "No such player.")
    uid = int(target["id"])
    return render(req, "inventory_public.html", target=target,
                  items=inventory.list_for_user(uid),
                  summary=inventory.summary(uid), tiers=catalog.TIERS)


@router.post("/api/market/buy")
@login_required
def buy(req: Request):
    item_id = str(req.data().get("item_id", ""))
    try:
        result = market.purchase(int(req.user["id"]), item_id)
    except market.MarketError as exc:
        return api_error(str(exc))
    return api_ok(**result)


@router.post("/api/market/sell")
@login_required
def sell(req: Request):
    try:
        inv_id = int(req.data().get("inv_id", 0))
    except (TypeError, ValueError):
        return api_error("Bad item.")
    try:
        result = market.sell_back(int(req.user["id"]), inv_id)
    except market.MarketError as exc:
        return api_error(str(exc))
    return api_ok(balance=economy.balance(int(req.user["id"])), **result)


@router.get("/api/catalog")
def catalog_json(req: Request):
    return api_ok(items=market.listing(req.query.get("slot", "all")),
                  tiers=catalog.TIERS, effects=catalog.UNUSUAL_EFFECTS,
                  palette=catalog.BODY_PALETTE)


@router.get("/api/inventory")
@login_required
def inventory_json(req: Request):
    uid = int(req.user["id"])
    return api_ok(items=inventory.list_for_user(uid),
                  summary=inventory.summary(uid),
                  balance=economy.balance(uid))
