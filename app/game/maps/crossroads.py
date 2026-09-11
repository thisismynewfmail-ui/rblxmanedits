"""Capture The Flag -- "Crossroads": two stone forts across a green valley."""
from __future__ import annotations

import math
import random
from typing import Any, Dict

from .builder import MapBuilder

STONE = "#c8cbcd"
STONE_DARK = "#a3a2a5"
STONE_TRIM = "#6d6e6c"
ROAD = "#d8d8d0"
GRASS = "#4b974b"
GRASS_DARK = "#3d7d3f"
WOOD = "#7c503a"

TEAM_COLORS = {"red": "#c4281c", "blue": "#0d69ac"}
BASE_Z = 118.0


def _fort(b: MapBuilder, team: str, facing: int) -> None:
    """Build one fort.

    ``facing`` points from the fort towards the middle of the map: +1 for the
    red fort (which sits at -Z) and -1 for the blue fort (at +Z).  Every part
    of the layout is expressed relative to that direction so the two forts are
    exact mirrors of each other.
    """
    colour = TEAM_COLORS[team]
    cz = -BASE_Z * facing            # red: -118, blue: +118
    front_z = cz + facing * 37       # the wall that looks at the battlefield
    back_z = cz - facing * 37
    keep_z = cz - facing * 4     # the keep sits just behind the courtyard
    spawn_z = cz - facing * 30   # spawn platform behind the keep

    # raised stone platform the fort sits on
    b.box([0, 1.0, cz], [116, 2.0, 74], STONE_DARK, studs=True)
    # ramp up onto the platform, ascending from the field towards the fort
    b.ramp(0, 0, front_z + facing * 13, 13, 2.0, 30,
           "z-" if facing > 0 else "z+", STONE_DARK, steps=4)

    # outer walls
    b.wall(-56, cz, 4, 74, 20, 2.0, STONE)
    b.wall(56, cz, 4, 74, 20, 2.0, STONE)
    b.wall(0, back_z, 116, 4, 20, 2.0, STONE)

    # front wall with a big gateway facing the field
    b.wall(-38, front_z, 40, 4, 20, 2.0, STONE)
    b.wall(38, front_z, 40, 4, 20, 2.0, STONE)
    b.wall(0, front_z, 36, 4, 6, 16.0, STONE)
    b.box([0, 15.0, front_z], [36, 2.0, 4.4], colour, collide=False)

    # battlements along the top of every wall
    for x in range(-56, 57, 8):
        b.box([x, 22.5, back_z], [5, 3, 4], STONE_DARK, collide=False)
        b.box([x, 22.5, front_z], [5, 3, 4], STONE_DARK, collide=False)
    for z in range(int(min(cz - 36, cz + 36)), int(max(cz - 36, cz + 36)) + 1, 8):
        b.box([-56, 22.5, z], [4, 3, 5], STONE_DARK, collide=False)
        b.box([56, 22.5, z], [4, 3, 5], STONE_DARK, collide=False)

    # corner towers
    for tx in (-56, 56):
        for tz in (back_z, front_z):
            b.cyl([tx, 15.0, tz], [16, 30.0, 16], STONE)
            b.cyl([tx, 30.5, tz], [18, 2.0, 18], STONE_DARK, collide=False)
            for i in range(8):
                ang = i * math.pi / 4.0
                b.box([tx + math.sin(ang) * 7.4, 33.0, tz + math.cos(ang) * 7.4],
                      [3.4, 3.0, 3.4], STONE_DARK, collide=False)
            b.cone([tx, 36.0, tz], [19, 9.0, 19], colour, collide=False)
            b.cyl([tx, 42.0, tz], [0.6, 6.0, 0.6], STONE_TRIM, collide=False)
            b.box([tx + 2.6, 43.5, tz], [5.0, 3.2, 0.3], colour, collide=False)

    # keep (inner building holding the flag), door facing the battlefield
    # doors front and back so the spawn behind it runs straight through
    b.room(0, keep_z, 46, 34, 18, 2.0, STONE, roof_c=colour, door_w=28,
           floor_c=STONE_DARK, doors=("z+", "z-"))
    b.box([0, 3.0, keep_z], [12, 2.0, 12], colour, studs=True)
    b.box([0, 4.6, keep_z], [8, 1.2, 8], STONE_DARK, studs=True)

    # side stairs onto the keep roof + a wall walk along the back
    b.stairs(-31, 2.0, keep_z - facing * 15, 8, 2.2, 2.6, 10,
             "z+" if facing > 0 else "z-", STONE_DARK)
    b.box([-31, 20.5, keep_z + facing * 6], [10, 1.0, 26], STONE_DARK)
    b.box([0, 20.5, spawn_z], [46, 1.0, 12], STONE_DARK)

    # spawn platform tucked behind the keep
    b.box([0, 2.5, spawn_z], [50, 1.0, 12], colour, studs=True)
    for i in range(8):
        x = -10.5 + i * 3.0
        yaw = 0.0 if facing > 0 else math.pi
        b.spawn(team, x, 3.2, spawn_z, yaw)

    # banners either side of the gate
    for x in (-24, 24):
        b.box([x, 12.0, front_z + facing * 2.4], [8, 14, 0.6], colour,
              collide=False, decal="banner_%s" % team)

    # crates for cover in the courtyard
    rng = random.Random(hash(team) & 0xFFFF)
    for _ in range(7):
        x = rng.uniform(-48, 48)
        z = cz + rng.uniform(-28, 28)
        if abs(x) < 30 and abs(z - keep_z) < 24:
            continue
        size = rng.uniform(5, 8)
        b.box([x, size / 2.0 + 2.0, z], [size, size, size], WOOD, studs=True)

    b.marker("flag_%s" % team, {"p": [0, 5.6, keep_z], "team": team})
    b.marker("base_%s" % team, {"p": [0, 5.6, keep_z], "radius": 14.0})


def build() -> Dict[str, Any]:
    b = MapBuilder(
        "Crossroads",
        sky={"top": "#7fb2e5", "horizon": "#e8f0f8", "sun": [0.35, 0.7, -0.25],
             "clouds": 0.5, "tint": "#ffffff"},
        ambient="#9db4c9", fog=760.0, ground=GRASS)
    rng = random.Random(20061012)

    # ------------------------------------------------------------- baseplate
    b.floor(0, 0, 420, 340, 0.0, GRASS, 6.0, studs=True, material="grass")
    # slightly darker grass patches for texture
    for _ in range(26):
        x = rng.uniform(-190, 190)
        z = rng.uniform(-150, 150)
        b.box([x, 0.06, z], [rng.uniform(16, 44), 0.12, rng.uniform(16, 44)],
              GRASS_DARK, collide=False, studs=False)

    # ----------------------------------------------------------- the crossing
    b.box([0, 0.15, 0], [40, 0.3, 300], ROAD, collide=False)
    b.box([0, 0.15, 0], [380, 0.3, 40], ROAD, collide=False)

    # central raised plaza with a broken arch (the landmark of the map)
    b.box([0, 1.5, 0], [72, 3.0, 72], STONE_DARK, studs=True)
    b.box([0, 4.0, 0], [52, 2.0, 52], STONE, studs=True)
    for side in (-1, 1):
        b.ramp(side * 44, 0, 0, 16, 3.0, 34, "x+" if side < 0 else "x-",
               STONE_DARK, steps=5)
        b.ramp(0, 0, side * 44, 16, 3.0, 34, "z+" if side < 0 else "z-",
               STONE_DARK, steps=5)
    # arch pillars
    for x in (-18, 18):
        b.box([x, 15.0, 0], [7, 22, 7], STONE)
        b.box([x, 26.5, 0], [9, 3, 9], STONE_DARK, collide=False)
    b.box([0, 27.5, 0], [45, 4, 8], STONE)
    b.box([0, 31.0, 0], [30, 3, 6], STONE_DARK, collide=False)
    b.box([0, 6.0, 0], [10, 2, 10], "#f5c518", collide=False, studs=True)

    # ------------------------------------------------------------ side hills
    for sx in (-1, 1):
        for sz in (-1, 1):
            hx, hz = sx * 118.0, sz * 84.0
            b.box([hx, 3.0, hz], [86, 6.0, 62], GRASS_DARK, studs=True,
                  material="grass")
            b.box([hx, 7.5, hz], [58, 3.0, 40], "#59a659", studs=True,
                  material="grass")
            b.ramp(hx - sx * 46, 0, hz, 18, 6.0, 34,
                   "x+" if sx > 0 else "x-", GRASS_DARK, steps=6)
            # a small stone outpost on each hill
            b.room(hx, hz, 26, 20, 12, 9.0, STONE, roof_c="#8a5a2b",
                   door="z-" if sz > 0 else "z+", door_w=8, floor_c=STONE_DARK)
            b.tree(hx + sx * 26, hz + sz * 20, 9.0, 1.2)
            b.tree(hx - sx * 24, hz - sz * 16, 9.0, 0.9)

    # -------------------------------------------------------------- scenery
    for _ in range(26):
        x = rng.uniform(-195, 195)
        z = rng.uniform(-155, 155)
        if abs(x) < 60 and abs(z) < 60:
            continue
        if abs(z) > 80 and abs(x) < 70:
            continue
        if rng.random() < 0.35:
            b.pine(x, z, 0.0, rng.uniform(0.8, 1.5))
        else:
            b.tree(x, z, 0.0, rng.uniform(0.8, 1.4))
    for _ in range(14):
        b.rock(rng.uniform(-190, 190), rng.uniform(-150, 150), 0.0,
               rng.uniform(0.7, 1.7))

    # bridges over a shallow stream running east-west
    b.water(-150, 0, 120, 26, 0.0)
    b.water(150, 0, 120, 26, 0.0)
    for sx in (-1, 1):
        bx = sx * 150.0
        b.box([bx, 4.0, 0], [46, 2.0, 30], WOOD, studs=True)
        for zz in (-14, 14):
            b.fence(bx - 22, zz, bx + 22, zz, 4.0, 5.0, "#8a5a2b", 11)
        b.ramp(bx - 30, 0, 0, 14, 4.0, 30, "x+", WOOD, steps=5)
        b.ramp(bx + 30, 0, 0, 14, 4.0, 30, "x-", WOOD, steps=5)

    # perimeter walls so nobody wanders into the void
    for sx in (-1, 1):
        b.wall(sx * 208, 0, 6, 340, 26, 0.0, STONE_DARK)
    for sz in (-1, 1):
        b.wall(0, sz * 168, 420, 6, 26, 0.0, STONE_DARK)

    # ----------------------------------------------------------------- forts
    _fort(b, "red", 1)     # red sits at -Z and faces +Z
    _fort(b, "blue", -1)   # blue sits at +Z and faces -Z

    # lamps down the main road
    for z in range(-90, 91, 45):
        b.lamp(-24, z, 0.0, 15.0)
        b.lamp(24, z, 0.0, 15.0)

    b.marker("mode", "ctf")
    b.marker("captures_to_win", 3)
    b.kill_y = -40.0
    return b.to_dict()
