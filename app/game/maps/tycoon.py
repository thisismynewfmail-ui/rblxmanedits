"""Burger Tycoon -- "Patty Plains": eight claimable plots around a plaza."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from .builder import MapBuilder

GRASS = "#5aa84f"
GRASS_DARK = "#4a9142"
ROAD = "#b9b9b1"
KERB = "#d8d8d0"
PLATE = "#cdd0d3"
PLATE_EDGE = "#9fa3a6"

PLOT_COLORS = [
    "#c4281c", "#0d69ac", "#f2b01e", "#4b974b",
    "#8b3fd6", "#e2621b", "#19a7c8", "#d94f8a",
]
PLOT_NAMES = [
    "Ketchup Corner", "Blue Bun", "Golden Grill", "Green Griddle",
    "Purple Patty", "Orange Onion", "Cyan Cheese", "Pink Pickle",
]

PLOT_W = 118.0
PLOT_D = 104.0


def plot_layout() -> List[Dict[str, Any]]:
    """Origin, facing direction and colour of each of the eight plots."""
    plots = []
    xs = [-207.0, -69.0, 69.0, 207.0]
    for row, (z, direction) in enumerate(((-96.0, 1.0), (96.0, -1.0))):
        for col, x in enumerate(xs):
            index = row * 4 + col
            plots.append({
                "index": index,
                "id": "plot_%d" % index,
                "name": PLOT_NAMES[index],
                "origin": [x, 0.0, z],
                "dir": direction,
                "color": PLOT_COLORS[index],
            })
    return plots


def local_to_world(plot: Dict[str, Any], point) -> List[float]:
    d = plot["dir"]
    ox, oy, oz = plot["origin"]
    return [ox + point[0] * d, oy + point[1], oz + point[2] * d]


def build() -> Dict[str, Any]:
    b = MapBuilder(
        "Patty Plains",
        sky={"top": "#8fc4ef", "horizon": "#ffeec4", "sun": [0.3, 0.75, 0.4],
             "clouds": 0.42, "tint": "#fff6e0"},
        ambient="#a8bccd", fog=820.0, ground=GRASS)
    rng = random.Random(20081123)

    b.floor(0, 0, 620, 400, 0.0, GRASS, 6.0, studs=True, material="grass")
    for _ in range(30):
        b.box([rng.uniform(-290, 290), 0.08, rng.uniform(-185, 185)],
              [rng.uniform(20, 50), 0.16, rng.uniform(20, 50)], GRASS_DARK,
              collide=False)

    # ------------------------------------------------------------- main road
    b.box([0, 0.2, 0], [600, 0.4, 46], ROAD, collide=False)
    for x in range(-280, 281, 24):
        b.box([x, 0.35, 0], [12, 0.2, 2.0], "#f5e07a", collide=False)
    for sz in (-1, 1):
        b.box([0, 0.6, sz * 24], [600, 1.2, 3.0], KERB, collide=False)
    # feeder roads to each plot
    for x in (-207.0, -69.0, 69.0, 207.0):
        b.box([x, 0.2, 0], [26, 0.4, 240], ROAD, collide=False)

    # ---------------------------------------------------------- central plaza
    b.box([0, 0.8, 0], [90, 1.6, 90], "#e2e2da", studs=True, collide=True)
    b.cyl([0, 2.4, 0], [40, 3.2, 40], "#cfd4d8", studs=True)
    b.cyl([0, 5.0, 0], [26, 2.6, 26], "#9fd8e8", material="glass", alpha=0.8)
    b.cyl([0, 8.0, 0], [6, 8.0, 6], "#cfd4d8")
    b.sphere([0, 13.0, 0], [7, 7, 7], "#9fd8e8", material="glass", alpha=0.7,
             collide=False)
    for i in range(8):
        ang = i * math.pi / 4.0
        b.box([math.sin(ang) * 34, 4.6, math.cos(ang) * 34], [4, 4, 4],
              "#f2b01e", collide=False)

    # welcome arch + billboard
    for sx in (-1, 1):
        b.box([sx * 52, 14.0, -46], [6, 28, 6], "#8a5a2b")
    b.box([0, 29.0, -46], [110, 6, 6], "#8a5a2b", collide=False)
    b.box([0, 29.0, -46], [92, 10, 1.2], "#f2f3f3", collide=False,
          decal="sign_tycoon")

    # spawn ring around the plaza
    for i in range(12):
        ang = i * math.pi / 6.0
        b.spawn("lobby", math.sin(ang) * 30.0, 2.2, math.cos(ang) * 30.0,
                ang + math.pi)

    # -------------------------------------------------------------- the plots
    plots = plot_layout()
    for plot in plots:
        ox, _, oz = plot["origin"]
        colour = plot["color"]
        d = plot["dir"]
        # the flat plate the restaurant grows out of
        b.box([ox, 1.0, oz], [PLOT_W, 2.0, PLOT_D], PLATE, studs=True)
        b.box([ox, 2.2, oz], [PLOT_W - 8, 0.4, PLOT_D - 8], PLATE_EDGE,
              collide=False)
        # coloured kerb marking the plot's team colour
        for sx in (-1, 1):
            b.box([ox + sx * (PLOT_W / 2.0 - 1.5), 2.6, oz], [3, 3.2, PLOT_D],
                  colour, collide=False)
        for sz in (-1, 1):
            b.box([ox, 2.6, oz + sz * (PLOT_D / 2.0 - 1.5)], [PLOT_W, 3.2, 3],
                  colour, collide=False)
        # entrance sign facing the road
        # the sign stands at the road-facing edge (local +Z)
        sign_z = oz + d * (PLOT_D / 2.0 + 8.0)
        b.cyl([ox, 6.0, sign_z], [2.4, 12.0, 2.4], "#6d6e6c")
        b.box([ox, 14.0, sign_z], [30, 10, 1.4], colour, collide=False,
              decal="plot_%d" % plot["index"])
        b.marker("plot_sign_%d" % plot["index"], [ox, 14.0, sign_z])

    b.marker("plots", plots)
    b.marker("mode", "tycoon")
    b.marker("plot_size", [PLOT_W, PLOT_D])

    # ---------------------------------------------------------- outer scenery
    for _ in range(46):
        x, z = rng.uniform(-300, 300), rng.uniform(-190, 190)
        if abs(z) < 170 and abs(x) < 285:
            # keep the built-up area clear
            near_plot = any(abs(x - p["origin"][0]) < PLOT_W / 2 + 20 and
                            abs(z - p["origin"][2]) < PLOT_D / 2 + 20
                            for p in plots)
            if near_plot or abs(z) < 34:
                continue
        if rng.random() < 0.4:
            b.pine(x, z, 0.0, rng.uniform(0.9, 1.6))
        else:
            b.tree(x, z, 0.0, rng.uniform(0.9, 1.5))

    for sx in (-1, 1):
        b.wall(sx * 306, 0, 8, 400, 24, 0.0, "#8fa87f")
    for sz in (-1, 1):
        b.wall(0, sz * 196, 620, 8, 24, 0.0, "#8fa87f")

    # a few lamps along the road
    for x in range(-260, 261, 52):
        if abs(x) < 40:          # keep the lobby spawn ring clear
            continue
        b.lamp(x, 30, 0.0, 16.0)
        b.lamp(x, -30, 0.0, 16.0)

    b.kill_y = -30.0
    return b.to_dict()
