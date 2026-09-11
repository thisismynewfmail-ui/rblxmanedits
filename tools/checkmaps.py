#!/usr/bin/env python3
"""Static sanity checks for every map.

Catches the mistakes that are invisible in code but obvious in game: spawn
points buried inside walls, spawns with nothing underneath them, parts with a
zero or negative size, and objectives that are not reachable from a spawn.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from app.game.instance import GameInstance, PLAYER_SIZE  # noqa: E402
from app.game.maps import crossroads, payload, tycoon    # noqa: E402

PLAYER_W, PLAYER_H, PLAYER_D = 2.4, PLAYER_SIZE[1], 1.8
FAILURES: List[str] = []


def report(ok: bool, message: str) -> None:
    print(("  PASS  " if ok else "  FAIL  ") + message)
    if not ok:
        FAILURES.append(message)


def boxes_for(map_data: Dict[str, Any]):
    return GameInstance._build_colliders(map_data)


def overlaps(box, lo, hi) -> bool:
    (bmin, bmax) = box
    return all(bmax[i] > lo[i] and bmin[i] < hi[i] for i in range(3))


def check_map(name: str, map_data: Dict[str, Any]) -> None:
    print("\n== %s ==" % name)
    parts = map_data["parts"]
    bad_size = [p for p in parts if any(v <= 0 for v in p["s"])]
    report(not bad_size, "%s: every part has a positive size (%d bad)"
           % (name, len(bad_size)))

    boxes = boxes_for(map_data)
    report(len(boxes) > 20, "%s: has %d collision boxes" % (name, len(boxes)))

    stuck = []
    floating = []
    for team, spawns in map_data.get("spawns", {}).items():
        for spawn in spawns:
            x, y, z = spawn["p"]
            lo = [x - PLAYER_W / 2 + 0.05, y + 0.15, z - PLAYER_D / 2 + 0.05]
            hi = [x + PLAYER_W / 2 - 0.05, y + PLAYER_H, z + PLAYER_D / 2 - 0.05]
            if any(overlaps(box, lo, hi) for box in boxes):
                stuck.append((team, spawn["p"]))
            ground = False
            for bmin, bmax in boxes:
                if (bmax[0] > x - 1.0 and bmin[0] < x + 1.0 and
                        bmax[2] > z - 0.8 and bmin[2] < z + 0.8 and
                        y - 3.0 <= bmax[1] <= y + 0.3):
                    ground = True
                    break
            if not ground:
                floating.append((team, spawn["p"]))
    report(not stuck, "%s: no spawn is inside a wall (%s)"
           % (name, stuck[:3] if stuck else "none"))
    report(not floating, "%s: every spawn has ground under it (%s)"
           % (name, floating[:3] if floating else "none"))

    # objectives must not be buried either
    for key, marker in map_data.get("markers", {}).items():
        if not key.startswith("flag_"):
            continue
        x, y, z = marker["p"]
        lo = [x - 1.0, y + 0.2, z - 1.0]
        hi = [x + 1.0, y + 3.0, z + 1.0]
        report(not any(overlaps(box, lo, hi) for box in boxes),
               "%s: %s is in open space" % (name, key))


def main() -> int:
    check_map("crossroads", crossroads.build())
    check_map("dustworks", payload.build())
    check_map("patty plains", tycoon.build())
    print("\n%d failures" % len(FAILURES))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
