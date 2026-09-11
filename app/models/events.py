"""The rotating spotlight shown at the top of the home page.

These are presentation only: each one points at a corner of the site that is
already there (the hat aisle, a world, the Unusual showcase) and says "look
here this week".  Nothing in the schedule changes prices, drop rates or
gameplay -- the rotation is derived from the clock so every player sees the
same spotlight at the same time without any stored state.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

WEEK = 7 * 86400
# Monday 00:00 UTC of the week containing the epoch-anchored rotation.
ANCHOR = 345600  # 1970-01-05, a Monday


SPOTLIGHTS: List[Dict[str, Any]] = [
    {
        "id": "hat_week",
        "kicker": "This week",
        "title": "Hat Week",
        "blurb": "Every hat in the catalogue in one place -- and hats are the only "
                 "slot that can roll Unusual.",
        "cta": "Browse the hat aisle",
        "href": "/market?slot=hat",
    },
    {
        "id": "world_spotlight",
        "kicker": "This week",
        "title": "World Spotlight",
        "blurb": "One world takes the front page. Drop in, take a plot or a flag, "
                 "and put a score on the board.",
        "cta": "Open the world browser",
        "href": "/worlds",
    },
    {
        "id": "unusual_watch",
        "kicker": "This week",
        "title": "Unusual Watch",
        "blurb": "Twelve particle effects, 0.5% a hat. Every pull that lands shows "
                 "up on the board below.",
        "cta": "See the latest finds",
        "href": "/market",
    },
    {
        "id": "fresh_faces",
        "kicker": "This week",
        "title": "Fresh Faces",
        "blurb": "New expression, new character. Faces are the cheapest way to make "
                 "an avatar yours.",
        "cta": "Try on a face",
        "href": "/market?slot=face",
    },
    {
        "id": "loadout_lab",
        "kicker": "This week",
        "title": "Loadout Lab",
        "blurb": "Five hotbar slots, one body type, six colourable parts. Rebuild "
                 "yourself before the next round.",
        "cta": "Open the avatar editor",
        "href": "/avatar",
    },
    {
        "id": "meet_the_crew",
        "kicker": "This week",
        "title": "Meet the Crew",
        "blurb": "Nothing on this platform is better with strangers. Find somebody, "
                 "add them, take a plot together.",
        "cta": "Browse the player list",
        "href": "/users",
    },
]


def _slot(now: float) -> int:
    return int((now - ANCHOR) // WEEK)


def _week_bounds(now: float) -> Dict[str, int]:
    slot = _slot(now)
    start = ANCHOR + slot * WEEK
    return {"starts_at": int(start), "ends_at": int(start + WEEK)}


def _build(index: int, now: float, offset: int = 0) -> Dict[str, Any]:
    entry = dict(SPOTLIGHTS[index % len(SPOTLIGHTS)])
    bounds = _week_bounds(now)
    entry["starts_at"] = bounds["starts_at"] + offset * WEEK
    entry["ends_at"] = bounds["ends_at"] + offset * WEEK
    if offset:
        entry["kicker"] = "Next week" if offset == 1 else "Coming up"
    return entry


def current(now: float = 0.0) -> Dict[str, Any]:
    now = now or time.time()
    return _build(_slot(now), now)


def upcoming(count: int = 2, now: float = 0.0) -> List[Dict[str, Any]]:
    now = now or time.time()
    slot = _slot(now)
    return [_build(slot + step, now, step) for step in range(1, count + 1)]


def seconds_left(now: float = 0.0) -> int:
    now = now or time.time()
    return max(0, int(_week_bounds(now)["ends_at"] - now))
