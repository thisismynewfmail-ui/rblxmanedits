"""World browser, world detail pages and the in-browser Game View."""
from __future__ import annotations

from .. import config, db, security
from ..game import registry as game_registry
from ..http import router as R
from ..http.router import Request
from ..models import avatars, users, worlds
from .base import api_error, api_ok, login_required, render, router


def _world_rows(viewer_id: int = 0):
    rows = []
    favourites = set(worlds.favourites_of(viewer_id)) if viewer_id else set()
    for world in worlds.all_worlds():
        status = game_registry.world_status(world["id"])
        stats = worlds.stats(world["id"])
        rows.append({
            "world": world,
            "status": status,
            "stats": stats,
            "favourite": world["id"] in favourites,
            "vote": worlds.user_vote(world["id"], viewer_id) if viewer_id else 0,
        })
    rows.sort(key=lambda r: (-r["status"]["players"], -r["stats"]["visits"]))
    return rows


@router.get("/worlds")
def world_browser(req: Request):
    viewer = int(req.user["id"]) if req.user else 0
    return render(req, "worlds.html", rows=_world_rows(viewer),
                  total_players=game_registry.total_players(),
                  total_visits=worlds.total_visits())


@router.get("/worlds/<world_id>")
def world_detail(req: Request, world_id: str = ""):
    world = worlds.get(world_id)
    if world is None:
        return R.error(404, "That world does not exist.")
    viewer = int(req.user["id"]) if req.user else 0
    status = game_registry.world_status(world_id)
    return render(req, "world_detail.html", world=world, status=status,
                  stats=worlds.stats(world_id),
                  favourite=worlds.is_favourite(world_id, viewer) if viewer else False,
                  vote=worlds.user_vote(world_id, viewer) if viewer else 0,
                  leaderboard=worlds.leaderboard(world_id, 10),
                  players=game_registry.players_in(world_id),
                  recent_visits=db.rows_to_dicts(db.query(
                      "SELECT v.created_at, u.username FROM world_visits v"
                      " JOIN users u ON u.id=v.user_id WHERE v.world_id=?"
                      " ORDER BY v.id DESC LIMIT 10", (world_id,))))


def _game_view(req: Request, world_id: str):
    world = worlds.get(world_id)
    if world is None:
        return R.error(404, "That world does not exist.")
    if req.user is None:
        return R.redirect("/login?next=/%s" % world_id)
    return render(req, "game.html", world=world,
                  avatar=avatars.descriptor(int(req.user["id"]),
                                            req.user["username"]),
                  status=game_registry.world_status(world_id),
                  instance=req.query.get("instance", ""))


def register_world_routes() -> None:
    """Each world gets its own top level page, e.g. /burger_tycoon."""
    for world in worlds.all_worlds():
        world_id = world["id"]

        def handler(req: Request, _wid=world_id):
            return _game_view(req, _wid)

        handler.__name__ = "game_view_%s" % world_id
        router.add("/%s" % world_id, handler, ("GET",),
                   name="game_%s" % world_id)
        router.add("/play/%s" % world_id, handler, ("GET",),
                   name="play_%s" % world_id)


@router.post("/api/game/join")
@login_required
def join_ticket(req: Request):
    data = req.data()
    world_id = str(data.get("world_id", ""))
    world = worlds.get(world_id)
    if world is None:
        return api_error("Unknown world.", 404)
    backend = game_registry.backend_for(world_id)
    if backend is None:
        return api_error("That world's server is still starting up. Try again "
                         "in a moment.", 503)
    uid = int(req.user["id"])
    if not db.rate_limit("join:%d" % uid, 40, 300):
        return api_error("You are joining servers too quickly.")
    avatar = avatars.descriptor(uid, req.user["username"])
    ticket = security.sign({
        "uid": uid,
        "name": req.user["username"],
        "world": world_id,
        "avatar": avatar,
        "admin": bool(req.user["is_admin"]),
    }, config.GAME_TICKET_TTL)
    instance = str(data.get("instance", "") or "")
    ws_path = "/ws/game/%s?ticket=%s" % (world_id, ticket)
    if instance.isdigit():
        ws_path += "&instance=%s" % instance
    db.audit(uid, "game.join", world_id)
    return api_ok(ticket=ticket, ws=ws_path, world=world,
                  status=game_registry.world_status(world_id))


@router.get("/api/worlds/status")
def worlds_status(req: Request):
    payload = {}
    for world in worlds.all_worlds():
        status = game_registry.world_status(world["id"])
        stats = worlds.stats(world["id"])
        payload[world["id"]] = {
            "players": status["players"],
            "instances": status["instances"],
            "online": status["online"],
            "capacity": world["max_players"],
            "visits": stats["visits"],
            "rating": stats["rating"],
            "instance_list": [
                {"id": i["id"], "count": i["count"], "max": i["max"],
                 "phase": i.get("phase", ""), "round": i.get("round", 1)}
                for i in status.get("instance_list", [])],
        }
    return api_ok(worlds=payload, total=game_registry.total_players())


@router.post("/api/worlds/vote")
@login_required
def world_vote(req: Request):
    data = req.data()
    world_id = str(data.get("world_id", ""))
    if worlds.get(world_id) is None:
        return api_error("Unknown world.")
    stats = worlds.vote(world_id, int(req.user["id"]),
                        str(data.get("vote", "up")) == "up")
    return api_ok(stats=stats,
                  vote=worlds.user_vote(world_id, int(req.user["id"])))


@router.post("/api/worlds/favourite")
@login_required
def world_favourite(req: Request):
    world_id = str(req.data().get("world_id", ""))
    if worlds.get(world_id) is None:
        return api_error("Unknown world.")
    state = worlds.toggle_favourite(world_id, int(req.user["id"]))
    return api_ok(favourite=state, stats=worlds.stats(world_id))
