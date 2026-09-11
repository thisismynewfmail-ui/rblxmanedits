"""Internal endpoints used by the game host processes.

Requests are authenticated with an HMAC over the raw body using the server
secret, and are only accepted from the loopback interface.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict

from .. import config, db, security
from ..game import registry as game_registry
from ..http import router as R
from ..http.router import Request
from ..models import worlds
from .base import router

_visit_guard: Dict[str, float] = {}


@router.post("/internal/heartbeat")
def heartbeat(req: Request):
    if req.remote_addr not in ("127.0.0.1", "::1", "localhost"):
        return R.json_response({"ok": False}, 403)
    if not security.check_service_signature(
            req.body, req.headers.get("x-service-signature", "")):
        return R.json_response({"ok": False, "error": "bad signature"}, 403)
    try:
        payload = json.loads(req.body.decode("utf-8"))
    except Exception:
        return R.json_response({"ok": False, "error": "bad json"}, 400)
    world_id = str(payload.get("world", ""))
    if worlds.get(world_id) is None:
        return R.json_response({"ok": False, "error": "unknown world"}, 400)
    game_registry.heartbeat(world_id, payload)
    players = int(payload.get("players", 0))
    if players:
        worlds.note_peak(world_id, players)
    for report in payload.get("reports", []) or []:
        try:
            _apply_report(world_id, report)
        except Exception:
            if config.DEBUG:
                import traceback
                traceback.print_exc()
    return R.json_response({"ok": True, "at": int(time.time())})


def _apply_report(world_id: str, report: Dict[str, Any]) -> None:
    kind = str(report.get("kind", ""))
    user_id = int(report.get("user_id", 0) or 0)
    if user_id <= 0:
        return
    if kind == "visit":
        key = "%s:%d" % (world_id, user_id)
        last = _visit_guard.get(key, 0.0)
        if time.time() - last < 25:
            return
        _visit_guard[key] = time.time()
        worlds.record_visit(world_id, user_id, int(report.get("seconds", 30)))
        db.execute("UPDATE users SET last_seen=? WHERE id=?",
                   (int(time.time()), user_id))
    elif kind == "stats":
        worlds.add_game_stats(
            user_id, world_id,
            kills=int(report.get("kills", 0)),
            deaths=int(report.get("deaths", 0)),
            playtime=int(report.get("playtime", 0)),
            score=int(report.get("score", 0)))
        db.execute("UPDATE users SET last_seen=? WHERE id=?",
                   (int(time.time()), user_id))
    elif kind == "round":
        worlds.add_game_stats(user_id, world_id, rounds=1,
                              wins=1 if report.get("won") else 0)
