"""Home page, people browser and search."""
from __future__ import annotations

from ..http import router as R
from ..http.router import Request
from ..game import registry as game_registry
from ..models import avatars, inventory, users, worlds
from ..social import feed, follows, friends, posts
from .base import render, router


@router.get("/")
def home(req: Request):
    world_rows = []
    for world in worlds.all_worlds():
        status = game_registry.world_status(world["id"])
        stats = worlds.stats(world["id"])
        world_rows.append({"world": world, "status": status, "stats": stats})
    if req.user is None:
        return render(req, "landing.html", worlds=world_rows,
                      site_stats=feed.stats_snapshot(),
                      recent_users=users.recent(10),
                      showcase=inventory.unusual_showcase(6))
    uid = int(req.user["id"])
    return render(
        req, "home.html",
        worlds=world_rows,
        timeline=posts.timeline(uid, 12),
        friends_list=friends.list_friends(uid, 12),
        friend_count=friends.count_friends(uid),
        requests=friends.incoming_requests(uid)[:5],
        activity=feed.recent_activity(14),
        site_stats=feed.stats_snapshot(),
        online=users.online_users(12),
        favourites=worlds.favourites_of(uid),
        avatar=avatars.descriptor(uid, req.user["username"]),
        showcase=inventory.unusual_showcase(6),
        stats=worlds.player_stats(uid),
        leaderboard=worlds.leaderboard(None, 8),
    )


@router.get("/users")
def people(req: Request):
    term = req.query.get("q", "")
    results = users.search(term, 48)
    rows = []
    viewer = int(req.user["id"]) if req.user else 0
    for row in results:
        rows.append({
            "user": row,
            "online": users.is_online(row),
            "friends": friends.count_friends(int(row["id"])),
            "status": friends.status_for(viewer, int(row["id"])) if viewer else "none",
            "following": follows.is_following(viewer, int(row["id"])) if viewer else False,
        })
    return render(req, "people.html", rows=rows, term=term,
                  total=users.count_users())


@router.get("/search")
def search(req: Request):
    term = (req.query.get("q") or "").strip()
    from ..models import market
    items = market.listing(None, "featured", term)[:24] if term else []
    people_rows = users.search(term, 12) if term else []
    world_rows = [w for w in worlds.all_worlds()
                  if term.lower() in w["name"].lower()] if term else []
    return render(req, "search.html", term=term, items=items,
                  people=people_rows, worlds=world_rows)


@router.get("/help")
def help_page(req: Request):
    return render(req, "help.html", page_title="Help")
