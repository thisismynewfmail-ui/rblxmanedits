"""World registry and world statistics.

The registry is the single source of truth shared by the website (world
browser, previews) and by the game host processes (round rules, capacity).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .. import db

WORLDS: List[Dict[str, Any]] = [
    {
        "id": "burger_tycoon",
        "name": "Burger Tycoon",
        "genre": "Tycoon",
        "creator": "BLOCKHAVEN",
        "tagline": "Claim a plot. Flip the burgers. Build the empire.",
        "description": (
            "Eight plots, eight crews, one endless lunch rush. Claim an empty "
            "plate of land, buy your first grill and let the passive income "
            "roll in. Every building you unlock is welded onto your restaurant "
            "in real time. Nothing ever ends here -- players drift in and out "
            "and the world keeps cooking."),
        "max_players": 24,
        "team_count": 8,
        "mode": "endless",
        "shuffle": False,
        "round_label": "Endless world",
        "colors": ["#f2b01e", "#e2621b", "#8a5a2b"],
        "thumb": "burger",
        "features": ["8 claimable plots", "Idle + active income",
                     "Animated build-up", "No round timer"],
    },
    {
        "id": "capture_the_flag",
        "name": "Capture The Flag",
        "genre": "Classic Shooter",
        "creator": "BLOCKHAVEN",
        "tagline": "Crossroads never died. It just respawned.",
        "description": (
            "The classic. Two forts either side of a green valley, a bridge "
            "nobody survives, and a flag that will not carry itself. First "
            "team to three captures takes the round. Shuffle vote after every "
            "match."),
        "max_players": 16,
        "team_count": 2,
        "mode": "captures",
        "shuffle": True,
        "round_label": "First to 3 captures",
        "colors": ["#4b974b", "#0d69ac", "#c4281c"],
        "thumb": "ctf",
        "features": ["2 teams", "Flag carrying + returns", "Round shuffle vote",
                     "Classic block map"],
    },
    {
        "id": "fortress_team_2",
        "name": "Fortress Team 2",
        "genre": "Objective Shooter",
        "creator": "BLOCKHAVEN",
        "tagline": "Push the cart. Stop the cart. Repeat forever.",
        "description": (
            "Blue pushes the bomb cart along the rails towards Red's fortress. "
            "Stand near it and it rolls; leave it alone and it slides back. "
            "Three checkpoints, three round wins, and teams swap ends after "
            "every round."),
        "max_players": 24,
        "team_count": 2,
        "mode": "payload",
        "shuffle": True,
        "round_label": "First to 3 round wins",
        "colors": ["#b8383b", "#5885a2", "#c9b48b"],
        "thumb": "payload",
        "features": ["Payload cart", "3 checkpoints", "Team swap each round",
                     "Setup timer"],
    },
]

WORLDS = [db.AttrDict(w) for w in WORLDS]
WORLDS_BY_ID: Dict[str, Dict[str, Any]] = {w["id"]: w for w in WORLDS}


def get(world_id: str) -> Optional[Dict[str, Any]]:
    return WORLDS_BY_ID.get(world_id)


def all_worlds() -> List[Dict[str, Any]]:
    return list(WORLDS)


# ------------------------------------------------------------------- stats

def ensure_rows() -> None:
    now = int(time.time())
    for world in WORLDS:
        db.execute("INSERT OR IGNORE INTO world_stats(world_id, updated_at)"
                   " VALUES(?,?)", (world["id"], now))


def stats(world_id: str) -> Dict[str, Any]:
    row = db.query_one("SELECT * FROM world_stats WHERE world_id=?", (world_id,))
    if row is None:
        ensure_rows()
        row = db.query_one("SELECT * FROM world_stats WHERE world_id=?",
                           (world_id,))
    data = db.AttrDict(row) if row else db.AttrDict({"world_id": world_id, "visits": 0,
                                  "favourites": 0, "likes": 0, "dislikes": 0,
                                  "peak_players": 0})
    total = data.get("likes", 0) + data.get("dislikes", 0)
    data["rating"] = int(round(100.0 * data.get("likes", 0) / total)) if total else 0
    data["rating_votes"] = total
    return data


def record_visit(world_id: str, user_id: int, seconds: int) -> None:
    now = int(time.time())
    with db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO world_stats(world_id, updated_at)"
                     " VALUES(?,?)", (world_id, now))
        conn.execute("UPDATE world_stats SET visits=visits+1, updated_at=?"
                     " WHERE world_id=?", (now, world_id))
        conn.execute("INSERT INTO world_visits(world_id,user_id,created_at,seconds)"
                     " VALUES(?,?,?,?)", (world_id, user_id, now, int(seconds)))
        conn.execute("UPDATE users SET place_visits=place_visits+1 WHERE id=?",
                     (user_id,))


def note_peak(world_id: str, players: int) -> None:
    db.execute("UPDATE world_stats SET peak_players=MAX(peak_players,?),"
               " updated_at=? WHERE world_id=?",
               (int(players), int(time.time()), world_id))


def vote(world_id: str, user_id: int, like: bool) -> Dict[str, Any]:
    if world_id not in WORLDS_BY_ID:
        raise ValueError("Unknown world")
    value = 1 if like else -1
    with db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO world_stats(world_id, updated_at)"
                     " VALUES(?,?)", (world_id, int(time.time())))
        prev = conn.execute(
            "SELECT vote FROM world_votes WHERE world_id=? AND user_id=?",
            (world_id, user_id)).fetchone()
        if prev is not None and int(prev["vote"]) == value:
            conn.execute("DELETE FROM world_votes WHERE world_id=? AND user_id=?",
                         (world_id, user_id))
        else:
            conn.execute(
                "INSERT INTO world_votes(world_id,user_id,vote) VALUES(?,?,?)"
                " ON CONFLICT(world_id,user_id) DO UPDATE SET vote=excluded.vote",
                (world_id, user_id, value))
        likes = int(conn.execute(
            "SELECT COUNT(*) FROM world_votes WHERE world_id=? AND vote=1",
            (world_id,)).fetchone()[0])
        dislikes = int(conn.execute(
            "SELECT COUNT(*) FROM world_votes WHERE world_id=? AND vote=-1",
            (world_id,)).fetchone()[0])
        conn.execute("UPDATE world_stats SET likes=?, dislikes=? WHERE world_id=?",
                     (likes, dislikes, world_id))
    return stats(world_id)


def user_vote(world_id: str, user_id: int) -> int:
    return int(db.scalar(
        "SELECT vote FROM world_votes WHERE world_id=? AND user_id=?",
        (world_id, user_id), 0))


def toggle_favourite(world_id: str, user_id: int) -> bool:
    existing = db.query_one(
        "SELECT 1 FROM world_favourites WHERE world_id=? AND user_id=?",
        (world_id, user_id))
    if existing:
        db.execute("DELETE FROM world_favourites WHERE world_id=? AND user_id=?",
                   (world_id, user_id))
        favourited = False
    else:
        db.execute("INSERT INTO world_favourites(world_id,user_id,created_at)"
                   " VALUES(?,?,?)", (world_id, user_id, int(time.time())))
        favourited = True
    count = int(db.scalar("SELECT COUNT(*) FROM world_favourites WHERE world_id=?",
                          (world_id,)))
    db.execute("UPDATE world_stats SET favourites=? WHERE world_id=?",
               (count, world_id))
    return favourited


def favourites_of(user_id: int) -> List[str]:
    return [r["world_id"] for r in db.query(
        "SELECT world_id FROM world_favourites WHERE user_id=? ORDER BY created_at DESC",
        (user_id,))]


def is_favourite(world_id: str, user_id: int) -> bool:
    return db.query_one(
        "SELECT 1 FROM world_favourites WHERE world_id=? AND user_id=?",
        (world_id, user_id)) is not None


# ------------------------------------------------------------- player stats

def add_game_stats(user_id: int, world_id: str, kills: int = 0, deaths: int = 0,
                   wins: int = 0, rounds: int = 0, playtime: int = 0,
                   score: int = 0) -> None:
    db.execute(
        "INSERT INTO game_stats(user_id,world_id,kills,deaths,wins,rounds,"
        "playtime,score) VALUES(?,?,?,?,?,?,?,?)"
        " ON CONFLICT(user_id,world_id) DO UPDATE SET"
        " kills=kills+excluded.kills, deaths=deaths+excluded.deaths,"
        " wins=wins+excluded.wins, rounds=rounds+excluded.rounds,"
        " playtime=playtime+excluded.playtime, score=score+excluded.score",
        (user_id, world_id, kills, deaths, wins, rounds, playtime, score))


def player_stats(user_id: int) -> Dict[str, Any]:
    rows = db.rows_to_dicts(db.query(
        "SELECT * FROM game_stats WHERE user_id=?", (user_id,)))
    total = {"kills": 0, "deaths": 0, "wins": 0, "rounds": 0, "playtime": 0,
             "score": 0}
    per_world = {}
    for row in rows:
        for key in total:
            total[key] += int(row.get(key, 0))
        per_world[row["world_id"]] = row
    total["kdr"] = round(total["kills"] / max(1, total["deaths"]), 2)
    return {"total": total, "worlds": per_world}


def leaderboard(world_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    if world_id:
        rows = db.query(
            "SELECT g.*, u.username FROM game_stats g JOIN users u ON u.id=g.user_id"
            " WHERE g.world_id=? ORDER BY g.score DESC, g.kills DESC LIMIT ?",
            (world_id, limit))
    else:
        rows = db.query(
            "SELECT u.username, u.id AS user_id, SUM(g.kills) AS kills,"
            " SUM(g.deaths) AS deaths, SUM(g.score) AS score,"
            " SUM(g.playtime) AS playtime"
            " FROM game_stats g JOIN users u ON u.id=g.user_id"
            " GROUP BY g.user_id ORDER BY score DESC, kills DESC LIMIT ?",
            (limit,))
    return db.rows_to_dicts(rows)


def total_visits() -> int:
    return int(db.scalar("SELECT COALESCE(SUM(visits),0) FROM world_stats"))
