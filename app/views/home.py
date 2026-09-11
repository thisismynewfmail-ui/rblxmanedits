"""Home page, people browser and search."""
from __future__ import annotations

from ..http import router as R
from ..http.router import Request
from ..game import registry as game_registry
from ..models import avatars, events, inventory, users, worlds
from ..social import feed, follows, friends, posts
from .base import render, router


def _event_items(event):
    """The seasonal pieces to show beside the event copy.

    Hats first because they are the ones that can roll Unusual, then whatever
    else the collection has, capped at three so the row stays a row.
    """
    if not event or not event.get("tag"):
        return []
    from ..models import market
    rows = market.listing("all", "featured", "", event["tag"])
    rows.sort(key=lambda r: (r["slot"] != "hat", r.get("sort_order", 0)))
    return rows[:3]


def _hero_showcase():
    """One randomised character for the signed-out hero.

    Random build, random pose, random cosmetics, so the front page is never
    the same twice.  It is generated per request rather than per session --
    a reload is meant to roll a new one.
    """
    import random
    from ..models import catalog

    def pick(slot, chance=1.0):
        options = [i for i in catalog.ALL_ITEMS
                   if i["slot"] == slot and not i.get("hidden")]
        if not options or random.random() > chance:
            return None
        return random.choice(options)

    body = random.choice(catalog.BODY_TYPES)
    skin = random.choice(HERO_SKINS)
    shirt = pick("shirt", 0.85)
    pants = pick("pants", 0.85)
    items = {}
    for slot, chance in (("face", 1.0), ("hat", 0.9), ("back", 0.5)):
        chosen = pick(slot, chance)
        if chosen:
            items[slot] = {"item_id": chosen["id"], "slot": slot,
                           "data": chosen.get("data", {})}
    if shirt:
        items["shirt"] = {"item_id": shirt["id"], "slot": "shirt",
                          "data": shirt.get("data", {})}
    if pants:
        items["pants"] = {"item_id": pants["id"], "slot": "pants",
                          "data": pants.get("data", {})}
    # Roughly one roll in six wears an Unusual, so the front page shows off
    # the thing the whole economy is built around without pretending it is
    # common.  effect_def is the particle definition the preview needs; the
    # client would otherwise have to look it up itself.
    if "hat" in items and random.random() < 0.17:
        effect_id = random.choice(list(catalog.UNUSUAL_EFFECTS))
        items["hat"]["effect"] = effect_id
        items["hat"]["effect_def"] = catalog.UNUSUAL_EFFECTS[effect_id]
        items["hat"]["tier"] = "unusual"
    trousers = random.choice(HERO_TROUSERS)
    return {
        "body_type": body,
        "colors": {"head": skin, "torso": random.choice(HERO_SHIRTS),
                   "left_arm": skin, "right_arm": skin,
                   # both legs the same, or the character looks like it was
                   # assembled from two different people
                   "left_leg": trousers, "right_leg": trousers},
        "items": items,
        "pose": random.choice(HERO_POSES),
    }


# Body colours drawn from the palette the avatar editor offers, so a rolled
# character always looks like one somebody could actually have built.
HERO_SKINS = ["#f5cd30", "#e8b07a", "#c98a5b", "#8d5a3b", "#f2d5b8", "#a4bd47"]
HERO_SHIRTS = ["#0d69ac", "#c4281c", "#3f8f45", "#7a34c4", "#f2b01e", "#22303c"]
HERO_TROUSERS = ["#1b2a35", "#3b4a5a", "#a4bd47", "#6b4a2f", "#2f5fa8"]
HERO_POSES = ["idle", "walk", "run", "jump", "sit"]


@router.get("/")
def home(req: Request):
    world_rows = []
    for world in worlds.all_worlds():
        status = game_registry.world_status(world["id"])
        stats = worlds.stats(world["id"])
        world_rows.append({"world": world, "status": status, "stats": stats})
    spotlight = events.current()
    if spotlight["id"] == "world_spotlight" and world_rows:
        # point the world spotlight at whichever world is busiest right now
        featured = max(world_rows, key=lambda r: (r["status"]["players"],
                                                  r["stats"]["visits"]))
        spotlight = dict(spotlight)
        spotlight["title"] = "World Spotlight: %s" % featured["world"]["name"]
        spotlight["href"] = "/worlds/%s" % featured["world"]["id"]
        spotlight["cta"] = "Open %s" % featured["world"]["name"]
    # A running season takes the top strip; the weekly spotlight is what the
    # rest of the year gets, so the page always has something true on it.
    event = events.active_event()
    event_items = _event_items(event)
    if req.user is None:
        return render(req, "landing.html", worlds=world_rows,
                      site_stats=feed.stats_snapshot(),
                      recent_users=users.recent(10),
                      spotlight=spotlight,
                      spotlight_left=events.seconds_left(),
                      upcoming=events.upcoming(2),
                      event=event, event_items=event_items,
                      hero=_hero_showcase(),
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
        spotlight=spotlight,
        spotlight_left=events.seconds_left(),
        upcoming=events.upcoming(2),
        event=event,
        event_items=event_items,
    )


@router.get("/api/hero")
def hero_roll(req: Request):
    """A fresh randomised character for the welcome page.

    The roll lives on the server so it draws from the same catalogue the rest
    of the site does -- add a hat and it can show up here with no client
    change -- and so the markup and the reroll button agree about what a
    character is.
    """
    from .base import api_ok
    return api_ok(hero=_hero_showcase())


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
