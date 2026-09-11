"""The rotating spotlight shown at the top of the home page.

These are presentation only: each one points at a corner of the site that is
already there (the hat aisle, a world, the Unusual showcase) and says "look
here this week".  Nothing in the schedule changes prices, drop rates or
gameplay -- the rotation is derived from the clock so every player sees the
same spotlight at the same time without any stored state.
"""
from __future__ import annotations

import calendar
import time
from typing import Any, Dict, List

WEEK = 7 * 86400
# Monday 00:00 UTC of the week containing the epoch-anchored rotation.
ANCHOR = 345600  # 1970-01-05, a Monday


# ------------------------------------------------------------------- events
# A seasonal event is a spotlight with a scene attached.  The scene name picks
# which animated panel the home page draws; everything else is copy.  Like the
# weekly rotation it is derived from the clock, so every player sees the same
# thing at the same time with nothing stored.
EVENTS: List[Dict[str, Any]] = [
    {
        "id": "hollow_harvest",
        "scene": "halloween",
        "kicker": "Seasonal event",
        "title": "Hollow Harvest",
        "blurb": "The lanterns are lit and something is wearing the hats. "
                 "Five seasonal pieces are in the market until the nights "
                 "get short again.",
        "cta": "Visit the night market",
        "href": "/market?tag=halloween",
        "tag": "halloween",
        # Inclusive month/day window, evaluated in UTC.  It opens at the
        # start of September because the build-up is half the event -- the
        # market fills before the night it is all for.
        "from": (9, 1),
        "to": (11, 2),
        "facts": [
            ("5", "seasonal pieces"),
            ("0.5%", "Unusual on any hat"),
            ("12", "particle effects"),
        ],
    },
]


def active_event(now: float = 0.0) -> Dict[str, Any]:
    """The seasonal event running right now, or an empty dict.

    Windows are month/day pairs rather than timestamps so the event comes
    back every year without anybody editing a date.
    """
    now = now or time.time()
    stamp = time.gmtime(now)
    today = (stamp.tm_mon, stamp.tm_mday)
    for event in EVENTS:
        start, end = event["from"], event["to"]
        inside = (start <= today <= end if start <= end
                  else today >= start or today <= end)
        if inside:
            entry = dict(event)
            entry["ends_at"] = _event_end(now, end)
            entry["seconds_left"] = max(0, entry["ends_at"] - int(now))
            return entry
    return {}


def _event_end(now: float, end: tuple) -> int:
    """Midnight UTC at the end of the event's last day, this year or next."""
    stamp = time.gmtime(now)
    year = stamp.tm_year
    for bump in (0, 1):
        try:
            when = calendar.timegm(
                (year + bump, end[0], end[1], 23, 59, 59, 0, 0, 0))
        except ValueError:
            continue
        if when > now:
            return int(when)
    return int(now)


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
