"""Fortress Team 2 -- "Dustworks": a desert payload map with a bomb cart."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from .builder import MapBuilder

SAND = "#c9b48b"
SAND_DARK = "#b09a72"
ROCK = "#9a8467"
WOOD = "#8a5a2b"
WOOD_DARK = "#5f3d1e"
METAL = "#8f9296"
RED = "#b8383b"
BLUE = "#5885a2"
RED_ROOF = "#8f2b2e"
BLUE_ROOF = "#3f6580"
CONCRETE = "#bdb5a4"

# The rail path the cart follows.  Each node is [x, y, z].
TRACK: List[List[float]] = [
    [-168, 0, 0], [-140, 0, 6], [-108, 0, 16], [-74, 0, 18],
    [-40, 0, 6], [-8, 0, -8], [26, 1.5, -18], [58, 3.5, -14],
    [88, 5.5, 0], [116, 7.5, 16], [146, 9.0, 22], [172, 9.0, 18],
]

CHECKPOINTS = [0.34, 0.68, 1.0]


def track_length(track: List[List[float]]) -> float:
    total = 0.0
    for i in range(len(track) - 1):
        a, c = track[i], track[i + 1]
        total += math.dist(a, c)
    return total


def point_at(track: List[List[float]], distance: float):
    """Return (position, yaw) at ``distance`` along the polyline."""
    distance = max(0.0, distance)
    for i in range(len(track) - 1):
        a, c = track[i], track[i + 1]
        seg = math.dist(a, c)
        if distance <= seg or i == len(track) - 2:
            t = min(1.0, distance / seg if seg else 0.0)
            pos = [a[0] + (c[0] - a[0]) * t,
                   a[1] + (c[1] - a[1]) * t,
                   a[2] + (c[2] - a[2]) * t]
            yaw = math.atan2(c[0] - a[0], c[2] - a[2])
            return pos, yaw
        distance -= seg
    return list(track[-1]), 0.0


def _rails(b: MapBuilder) -> None:
    total = track_length(TRACK)
    steps = int(total / 4.0)
    for i in range(steps + 1):
        d = i * 4.0
        pos, yaw = point_at(TRACK, d)
        b.box([pos[0], pos[1] + 0.35, pos[2]], [9.0, 0.7, 2.6], WOOD_DARK,
              r=[0, yaw, 0], collide=False)
        for side in (-1, 1):
            ox = math.cos(yaw) * side * 3.2
            oz = -math.sin(yaw) * side * 3.2
            b.box([pos[0] + ox, pos[1] + 0.95, pos[2] + oz], [1.0, 0.6, 4.4],
                  METAL, r=[0, yaw, 0], collide=False, material="metal")
    # ground bed under the rails
    for i in range(0, steps + 1, 3):
        pos, yaw = point_at(TRACK, i * 4.0)
        b.box([pos[0], pos[1] - 0.4, pos[2]], [14.0, 1.2, 13.0], SAND_DARK,
              r=[0, yaw, 0], collide=False)


def _spawn_building(b: MapBuilder, team: str, x: float, z: float,
                    facing: float) -> None:
    colour = RED if team == "red" else BLUE
    roof = RED_ROOF if team == "red" else BLUE_ROOF
    b.box([x, 1.0, z], [72, 2.0, 62], CONCRETE, studs=True)
    b.room(x, z, 66, 56, 22, 2.0, colour, wall_t=3.0, roof=True, roof_c=roof,
           door="x+" if facing > 0 else "x-", door_w=16, floor_c=CONCRETE)
    b.box([x, 25.0, z], [70, 2.0, 60], roof, collide=False)
    b.box([x + facing * 34, 14.0, z], [2.0, 8.0, 16.0], "#f2f3f3",
          collide=False, decal="sign_%s" % team)
    # supply lockers
    for i in range(4):
        b.box([x - 26 + i * 16, 6.0, z - 24], [10, 10, 5], METAL,
              material="metal")
    for i in range(9):
        b.spawn(team, x - 16 + (i % 5) * 8, 3.2, z + 12 + (i // 5) * 12,
                math.pi / 2.0 if facing > 0 else -math.pi / 2.0)


def _forward_spawn(b: MapBuilder, key: str, x: float, z: float,
                   yaw: float, count: int = 6) -> None:
    b.box([x, 1.0, z], [40, 2.0, 30], CONCRETE, studs=True)
    b.room(x, z, 36, 26, 16, 2.0, BLUE, roof_c=BLUE_ROOF, door="x+", door_w=12,
           floor_c=CONCRETE)
    spawns = []
    for i in range(count):
        spawns.append({"p": [x - 12 + (i % 3) * 10, 3.2, z - 6 + (i // 3) * 10],
                       "yaw": yaw})
    b.marker(key, spawns)


def build() -> Dict[str, Any]:
    b = MapBuilder(
        "Dustworks",
        sky={"top": "#e8b46a", "horizon": "#f7e4bd", "sun": [0.5, 0.55, 0.2],
             "clouds": 0.7, "tint": "#ffe9c4"},
        ambient="#c9ad84", fog=700.0, ground=SAND)
    rng = random.Random(20070822)

    # ------------------------------------------------------------- baseplate
    b.floor(0, 0, 560, 380, 0.0, SAND, 6.0, studs=True)
    for _ in range(30):
        b.box([rng.uniform(-220, 220), 0.08, rng.uniform(-160, 160)],
              [rng.uniform(20, 60), 0.16, rng.uniform(20, 60)], SAND_DARK,
              collide=False)

    # canyon walls all the way around
    for sx in (-1, 1):
        for i in range(9):
            z = -160 + i * 40
            h = rng.uniform(34, 58)
            b.box([sx * (252 + rng.uniform(-6, 6)), h / 2.0, z],
                  [34, h, 46], ROCK, studs=True)
    for sz in (-1, 1):
        for i in range(12):
            x = -220 + i * 40
            h = rng.uniform(34, 54)
            b.box([x, h / 2.0, sz * (172 + rng.uniform(-5, 5))],
                  [46, h, 30], ROCK, studs=True)

    # ----------------------------------------------------------------- rails
    _rails(b)

    # ------------------------------------------------------- blue side (start)
    _spawn_building(b, "blue", -204, 4, 1)
    b.box([-176, 6.0, -40], [40, 12, 30], WOOD, studs=True)
    b.ramp(-176, 0, -71, 16, 12.0, 30, "z+", WOOD, steps=6)
    b.box([-150, 3.0, 44], [46, 6.0, 36], CONCRETE, studs=True)
    b.room(-150, 44, 40, 30, 14, 6.0, WOOD, roof_c=WOOD_DARK, door="x+",
           door_w=10, floor_c=CONCRETE)

    # ------------------------------------------------------- first checkpoint
    b.box([-74, 2.0, 18], [40, 4.0, 34], CONCRETE, studs=True)
    b.box([-74, 12.0, 40], [44, 20.0, 8], WOOD, studs=True)
    b.ramp(-112, 0, 18, 18, 4.0, 30, "x+", CONCRETE, steps=4)
    for i in range(4):
        b.box([-60 + i * 9, 5.0, -12], [8, 10, 8], WOOD, studs=True)
    b.lamp(-92, 34, 0.0, 18.0)

    # warehouse in the middle with high ground both sides
    b.box([-8, 1.0, -46], [90, 2.0, 60], CONCRETE, studs=True)
    b.room(-8, -46, 84, 54, 24, 2.0, "#cbb99b", wall_t=3.0, roof=True,
           roof_c=METAL, door="z+", door_w=20, floor_c=CONCRETE)
    b.stairs(-44, 2.0, -20, 6, 2.2, 3.0, 12, "z-", WOOD)
    b.box([-44, 14.0, -42], [12, 1.2, 26], WOOD, studs=True)
    b.box([-8, 26.0, -46], [88, 2.0, 58], METAL, studs=True, material="metal")
    for i in range(5):
        b.box([-40 + i * 16, 28.5, -46], [8, 3, 50], METAL, collide=False,
              material="metal")
    b.ramp(50, 2.0, -46, 20, 24.0, 16, "x-", WOOD, steps=8)

    # containers / cover along the middle of the track
    for _ in range(16):
        x = rng.uniform(-120, 130)
        z = rng.uniform(-40, 60)
        if abs(z) < 14 and -60 < x < 60:
            continue
        w = rng.uniform(8, 18)
        b.box([x, w / 4.0, z], [w, w / 2.0, w * 0.7],
              rng.choice([WOOD, METAL, "#a3663a", "#6f7f5c"]), studs=True)

    # ------------------------------------------------- second checkpoint area
    b.box([58, 4.0, -14], [50, 8.0, 44], CONCRETE, studs=True)
    b.ramp(30, 0, -14, 20, 8.0, 40, "x+", CONCRETE, steps=5)
    b.room(58, -44, 40, 26, 16, 8.0, RED, roof_c=RED_ROOF, door="z+",
           door_w=12, floor_c=CONCRETE)
    b.box([58, 22.0, -14], [16, 28.0, 16], WOOD, studs=True)
    b.box([58, 37.0, -14], [22, 2.0, 22], WOOD_DARK, collide=False)

    # elevated flank walkway on the north side
    b.box([40, 20.0, 62], [180, 2.0, 14], WOOD, studs=True)
    for x in range(-40, 130, 30):
        b.box([x, 10.0, 62], [4, 20, 4], WOOD_DARK)
    b.ramp(-74, 0, 62, 24, 20.0, 14, "x+", WOOD, steps=8)
    b.ramp(150, 0, 62, 20, 20.0, 14, "x-", WOOD, steps=8)

    # ------------------------------------------------ red base / final point
    _spawn_building(b, "red", 200, -70, -1)
    b.box([146, 5.5, 22], [70, 11.0, 60], CONCRETE, studs=True)
    b.ramp(89, 0, 22, 22, 11.0, 44, "x+", CONCRETE, steps=6)
    # the pit the cart drops into
    b.box([172, 9.0, 18], [26, 2.0, 26], "#5a4a34", collide=True)
    for sx in (-1, 1):
        b.box([172 + sx * 15, 14.0, 18], [4, 12, 28], METAL, material="metal")
    b.box([172, 20.0, 4], [30, 12, 3], METAL, collide=False, material="metal",
          decal="hazard")
    b.box([186, 16.0, 18], [4, 16, 28], METAL, material="metal")

    # red battlements over the final point
    b.box([150, 24.0, -12], [40, 2.0, 26], WOOD, studs=True)
    for x in range(134, 171, 12):
        b.box([x, 12.0, -12], [4, 22, 4], WOOD_DARK)
    b.ramp(112, 11.0, -12, 18, 13.0, 24, "x+", WOOD, steps=6)

    # ---------------------------------------------------------- forward spawns
    _forward_spawn(b, "forward_blue_1", -70, 62, -math.pi / 2.0, 6)
    _forward_spawn(b, "forward_blue_2", 62, 40, -math.pi / 2.0, 6)

    # --------------------------------------------------------------- scenery
    for _ in range(20):
        x, z = rng.uniform(-215, 215), rng.uniform(-160, 160)
        if abs(z) < 50 and -200 < x < 200:
            continue
        b.rock(x, z, 0.0, rng.uniform(0.9, 2.4), ROCK)
    for _ in range(10):
        x, z = rng.uniform(-200, 200), rng.uniform(-150, 150)
        if abs(z) < 46:
            continue
        b.cyl([x, 5.0, z], [3.0, 10.0, 3.0], "#7a6a4a")
        b.sphere([x, 11.0, z], [10.0, 5.0, 10.0], "#8a9a5a", collide=False)

    # water tower landmark
    b.cyl([-30, 30.0, 90], [26.0, 22.0, 26.0], METAL, material="metal")
    b.cone([-30, 43.0, 90], [28.0, 8.0, 28.0], RED_ROOF, collide=False)
    for ang in range(4):
        a = ang * math.pi / 2.0 + math.pi / 4.0
        b.box([-30 + math.sin(a) * 10, 9.5, 90 + math.cos(a) * 10],
              [2.4, 19.0, 2.4], METAL, material="metal")

    b.marker("mode", "payload")
    b.marker("track", TRACK)
    b.marker("checkpoints", CHECKPOINTS)
    b.marker("track_length", round(track_length(TRACK), 2))
    b.kill_y = -30.0
    return b.to_dict()
