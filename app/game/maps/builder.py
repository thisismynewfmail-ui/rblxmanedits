"""Map construction helpers.

A map is a list of *parts*.  Keys are short because the whole thing is shipped
to every client as JSON on join:

    t   primitive: box | cyl | sph | cone | wedge | torus
    p   centre position [x, y, z]
    s   size [w, h, d]
    c   colour "#rrggbb"
    r   euler rotation [x, y, z] in radians (decoration only)
    st  1 = draw studs on the top face
    col 1 = solid (axis aligned collision box)
    m   material: plastic (default) | metal | neon | glass | grass | wood
    a   alpha 0..1 for transparency
    dec decal name drawn on the +Z face
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Sequence


class MapBuilder:
    def __init__(self, name: str, sky: Optional[Dict[str, Any]] = None,
                 ambient: str = "#8f9fb5", fog: float = 620.0,
                 ground: str = "#4b974b"):
        self.name = name
        self.parts: List[Dict[str, Any]] = []
        self.spawns: Dict[str, List[Dict[str, Any]]] = {}
        self.markers: Dict[str, Any] = {}
        self.sky = sky or {
            "top": "#6fa8dc", "horizon": "#cfe3f5", "sun": [0.4, 0.72, 0.35],
            "clouds": 0.55, "tint": "#ffffff",
        }
        self.ambient = ambient
        self.fog = fog
        self.ground = ground
        self.kill_y = -60.0

    # ------------------------------------------------------------- primitives
    def add(self, t: str, p: Sequence[float], s: Sequence[float], c: str,
            r: Optional[Sequence[float]] = None, studs: bool = False,
            collide: bool = True, material: str = "", alpha: float = 1.0,
            decal: str = "", tag: str = "") -> Dict[str, Any]:
        part: Dict[str, Any] = {
            "t": t,
            "p": [round(float(v), 3) for v in p],
            "s": [round(float(v), 3) for v in s],
            "c": c,
        }
        if r and any(abs(v) > 1e-6 for v in r):
            part["r"] = [round(float(v), 4) for v in r]
        if studs:
            part["st"] = 1
        if collide:
            part["col"] = 1
        if material:
            part["m"] = material
        if alpha < 1.0:
            part["a"] = round(alpha, 3)
        if decal:
            part["dec"] = decal
        if tag:
            part["tag"] = tag
        self.parts.append(part)
        return part

    def box(self, p, s, c, **kw) -> Dict[str, Any]:
        return self.add("box", p, s, c, **kw)

    def cyl(self, p, s, c, **kw) -> Dict[str, Any]:
        return self.add("cyl", p, s, c, **kw)

    def sphere(self, p, s, c, **kw) -> Dict[str, Any]:
        return self.add("sph", p, s, c, **kw)

    def cone(self, p, s, c, **kw) -> Dict[str, Any]:
        return self.add("cone", p, s, c, **kw)

    def wedge(self, p, s, c, **kw) -> Dict[str, Any]:
        return self.add("wedge", p, s, c, **kw)

    # ----------------------------------------------------------- compositions
    def floor(self, x: float, z: float, w: float, d: float, y: float = 0.0,
              c: str = "#4b974b", thickness: float = 2.0, studs: bool = True,
              material: str = "") -> None:
        self.box([x, y - thickness / 2.0, z], [w, thickness, d], c,
                 studs=studs, material=material)

    def wall(self, x: float, z: float, w: float, d: float, h: float,
             y: float = 0.0, c: str = "#c8cbcd", studs: bool = False,
             **kw) -> None:
        self.box([x, y + h / 2.0, z], [w, h, d], c, studs=studs, **kw)

    def room(self, cx: float, cz: float, w: float, d: float, h: float,
             y: float = 0.0, c: str = "#d7c59a", wall_t: float = 2.0,
             roof: bool = True, roof_c: Optional[str] = None,
             door: str = "z-", door_w: float = 8.0, floor_c: Optional[str] = None,
             doors: Optional[Sequence[str]] = None) -> None:
        """A hollow block building with one or more doorway gaps.

        ``doors`` overrides ``door`` when several sides need an opening (a keep
        you can run straight through, for instance).
        """
        openings = set(doors) if doors else {door}
        half_w, half_d = w / 2.0, d / 2.0
        if floor_c:
            self.floor(cx, cz, w, d, y, floor_c, 1.0, studs=True)
        segments = [
            ("z-", cx, cz - half_d, w, wall_t),
            ("z+", cx, cz + half_d, w, wall_t),
            ("x-", cx - half_w, cz, wall_t, d),
            ("x+", cx + half_w, cz, wall_t, d),
        ]
        for side, sx, sz, sw, sd in segments:
            if side in openings:
                if side in ("z-", "z+"):
                    gap = door_w
                    left = (sw - gap) / 2.0
                    self.wall(sx - (gap + left) / 2.0, sz, left, sd, h, y, c)
                    self.wall(sx + (gap + left) / 2.0, sz, left, sd, h, y, c)
                    self.wall(sx, sz, gap, sd, h - 7.0, y + 7.0, c)
                else:
                    gap = door_w
                    front = (sd - gap) / 2.0
                    self.wall(sx, sz - (gap + front) / 2.0, sw, front, h, y, c)
                    self.wall(sx, sz + (gap + front) / 2.0, sw, front, h, y, c)
                    self.wall(sx, sz, sw, gap, h - 7.0, y + 7.0, c)
            else:
                self.wall(sx, sz, sw, sd, h, y, c)
        if roof:
            self.box([cx, y + h + 0.5, cz], [w + wall_t, 1.0, d + wall_t],
                     roof_c or "#a3392b", studs=True)

    def stairs(self, x: float, y: float, z: float, steps: int, rise: float,
               run: float, width: float, direction: str = "z+",
               c: str = "#c8cbcd") -> None:
        for i in range(steps):
            h = rise * (i + 1)
            if direction == "z+":
                self.box([x, y + h / 2.0, z + run * (i + 0.5)],
                         [width, h, run], c, studs=False)
            elif direction == "z-":
                self.box([x, y + h / 2.0, z - run * (i + 0.5)],
                         [width, h, run], c, studs=False)
            elif direction == "x+":
                self.box([x + run * (i + 0.5), y + h / 2.0, z],
                         [run, h, width], c, studs=False)
            else:
                self.box([x - run * (i + 0.5), y + h / 2.0, z],
                         [run, h, width], c, studs=False)

    def ramp(self, x: float, y: float, z: float, length: float, height: float,
             width: float, direction: str = "z+", c: str = "#c8cbcd",
             steps: int = 8) -> None:
        self.stairs(x, y, z, steps, height / steps, length / steps, width,
                    direction, c)

    def tree(self, x: float, z: float, y: float = 0.0, scale: float = 1.0,
             trunk_c: str = "#7c503a", leaf_c: str = "#287f47") -> None:
        h = 9.0 * scale
        self.cyl([x, y + h / 2.0, z], [2.0 * scale, h, 2.0 * scale], trunk_c)
        self.sphere([x, y + h + 3.0 * scale, z],
                    [9.0 * scale, 8.0 * scale, 9.0 * scale], leaf_c,
                    collide=False)
        self.sphere([x + 2.4 * scale, y + h + 0.6 * scale, z - 1.6 * scale],
                    [6.0 * scale, 5.4 * scale, 6.0 * scale], leaf_c,
                    collide=False)

    def pine(self, x: float, z: float, y: float = 0.0, scale: float = 1.0,
             trunk_c: str = "#6b4a2a", leaf_c: str = "#1f6b38") -> None:
        self.cyl([x, y + 3.0 * scale, z], [1.8 * scale, 6.0 * scale, 1.8 * scale],
                 trunk_c)
        for i in range(3):
            self.cone([x, y + 7.0 * scale + i * 3.6 * scale, z],
                      [(10.0 - i * 2.4) * scale, 6.0 * scale,
                       (10.0 - i * 2.4) * scale], leaf_c, collide=False)

    def rock(self, x: float, z: float, y: float = 0.0, scale: float = 1.0,
             c: str = "#8f9296") -> None:
        self.sphere([x, y + 1.6 * scale, z],
                    [5.0 * scale, 3.4 * scale, 4.4 * scale], c)

    def fence(self, x1: float, z1: float, x2: float, z2: float, y: float = 0.0,
              h: float = 5.0, c: str = "#c8cbcd", post_every: float = 10.0
              ) -> None:
        dx, dz = x2 - x1, z2 - z1
        length = math.hypot(dx, dz)
        if length < 0.01:
            return
        angle = math.atan2(dx, dz)
        self.box([(x1 + x2) / 2.0, y + h - 0.5, (z1 + z2) / 2.0],
                 [0.6, 0.8, length], c, r=[0, angle, 0], collide=False)
        self.box([(x1 + x2) / 2.0, y + h * 0.55, (z1 + z2) / 2.0],
                 [0.5, 0.6, length], c, r=[0, angle, 0], collide=False)
        count = max(2, int(length / post_every) + 1)
        for i in range(count):
            t = i / float(count - 1)
            self.box([x1 + dx * t, y + h / 2.0, z1 + dz * t], [1.0, h, 1.0], c)

    def lamp(self, x: float, z: float, y: float = 0.0, h: float = 14.0,
             c: str = "#6d6e6c") -> None:
        self.cyl([x, y + h / 2.0, z], [1.2, h, 1.2], c)
        self.box([x, y + h + 0.6, z], [3.0, 1.2, 3.0], c, collide=False)
        self.box([x, y + h - 0.3, z], [2.2, 0.6, 2.2], "#fff3b0",
                 material="neon", collide=False)

    def sign(self, x: float, y: float, z: float, w: float, h: float,
             text_decal: str, post: bool = True, c: str = "#f2f3f3",
             rot: float = 0.0) -> None:
        if post:
            self.cyl([x, y / 2.0, z], [1.0, y, 1.0], "#6b4a2a")
        self.box([x, y + h / 2.0, z], [w, h, 0.6], c, r=[0, rot, 0],
                 decal=text_decal, collide=False)

    def water(self, x: float, z: float, w: float, d: float, y: float = 0.0,
              c: str = "#2f8fd8") -> None:
        self.box([x, y - 0.4, z], [w, 0.8, d], c, collide=False,
                 material="glass", alpha=0.72)

    # ------------------------------------------------------------------ meta
    def spawn(self, team: str, x: float, y: float, z: float,
              yaw: float = 0.0) -> None:
        self.spawns.setdefault(team, []).append(
            {"p": [round(x, 2), round(y, 2), round(z, 2)], "yaw": round(yaw, 3)})

    def marker(self, key: str, value: Any) -> None:
        self.markers[key] = value

    # ------------------------------------------------------------------ build
    def colliders(self) -> List[Dict[str, Any]]:
        """Axis aligned collision boxes, used by both server and client."""
        out = []
        for part in self.parts:
            if not part.get("col"):
                continue
            if "r" in part:
                # Rotated geometry is decoration; approximate with its bounds
                # only when the rotation is a multiple of a quarter turn.
                rx, ry, rz = part["r"]
                if abs(rx) > 1e-3 or abs(rz) > 1e-3:
                    continue
                quarter = abs((ry % (math.pi / 2.0))) < 1e-3
                if not quarter:
                    continue
                turns = int(round(ry / (math.pi / 2.0))) % 2
                w, h, d = part["s"]
                size = [d, h, w] if turns else [w, h, d]
            else:
                size = list(part["s"])
            if part["t"] == "sph":
                size = [size[0] * 0.78, size[1] * 0.78, size[2] * 0.78]
            elif part["t"] == "cyl":
                size = [size[0] * 0.86, size[1], size[2] * 0.86]
            elif part["t"] == "cone":
                size = [size[0] * 0.6, size[1], size[2] * 0.6]
            out.append({"p": part["p"], "s": size})
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "parts": self.parts,
            "spawns": self.spawns,
            "markers": self.markers,
            "sky": self.sky,
            "ambient": self.ambient,
            "fog": self.fog,
            "ground": self.ground,
            "kill_y": self.kill_y,
        }


def jitter(rng: random.Random, value: float, amount: float) -> float:
    return value + rng.uniform(-amount, amount)
