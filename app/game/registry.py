"""Live game-host registry (web-server side).

Game hosts are separate processes.  They push a heartbeat into the web server
every couple of seconds describing their instances; the world browser, the
profile presence badge and the admin dashboard all read from this cache.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from ..db import AttrDict

_lock = threading.RLock()
_hosts: Dict[str, Dict[str, Any]] = {}       # world_id -> heartbeat payload
_backends: Dict[str, Tuple[str, int]] = {}   # world_id -> (host, port)
STALE_AFTER = 20.0


def register_backend(world_id: str, host: str, port: int) -> None:
    with _lock:
        _backends[world_id] = (host, port)


def backend_for(world_id: str) -> Optional[Tuple[str, int]]:
    with _lock:
        return _backends.get(world_id)


def all_backends() -> Dict[str, Tuple[str, int]]:
    with _lock:
        return dict(_backends)


def heartbeat(world_id: str, payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload["received_at"] = time.time()
    with _lock:
        _hosts[world_id] = payload


def raw(world_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _hosts.get(world_id)
    if not data:
        return None
    if time.time() - data.get("received_at", 0) > STALE_AFTER:
        return None
    return data


def world_status(world_id: str) -> Dict[str, Any]:
    data = raw(world_id)
    if not data:
        return AttrDict({"online": False, "players": 0, "instances": 0,
                         "instance_list": []})
    instances = data.get("instances", [])
    return AttrDict({
        "online": True,
        "players": int(data.get("players", 0)),
        "instances": len(instances),
        "instance_list": instances,
        "uptime": data.get("uptime", 0),
        "tick_ms": data.get("tick_ms", 0),
    })


def all_status() -> Dict[str, Dict[str, Any]]:
    from ..models import worlds
    return {w["id"]: world_status(w["id"]) for w in worlds.WORLDS}


def total_players() -> int:
    return sum(s["players"] for s in all_status().values())


def player_world(user_id: int) -> Optional[str]:
    from ..models import worlds
    for world_id in list(_hosts.keys()):
        data = raw(world_id)
        if not data:
            continue
        for inst in data.get("instances", []):
            for player in inst.get("players", []):
                if int(player.get("user_id", 0)) == int(user_id):
                    world = worlds.get(world_id)
                    return world["name"] if world else world_id
    return None


def players_in(world_id: str) -> List[Dict[str, Any]]:
    data = raw(world_id)
    if not data:
        return []
    out: List[Dict[str, Any]] = []
    for inst in data.get("instances", []):
        for player in inst.get("players", []):
            entry = dict(player)
            entry["instance"] = inst.get("id")
            out.append(entry)
    return out


def online_player_ids() -> List[int]:
    ids = []
    for world_id in list(_hosts.keys()):
        for player in players_in(world_id):
            ids.append(int(player.get("user_id", 0)))
    return ids
