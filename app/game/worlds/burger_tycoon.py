"""Burger Tycoon -- eight plots, endless lunch rush.

Local plot space: the origin is the centre of the plate, +Y is up from the top
of the plate and +Z faces the road.  Each plot is transformed into world space
by ``dir`` (+1 for the south row, -1 for the north row), which is a 180 degree
rotation, so one set of geometry serves all eight plots.

Coins here are *plot coins* -- a per-world scratch currency.  They are never
converted to site credits and never touch the accounts database.
"""
from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, List, Optional

from ..instance import GameInstance, Player, now
from ..maps import tycoon as tycoon_map

PLOT_CAPACITY = 4
# Starting float for a fresh crew. Override with BLOCKHAVEN_TYCOON_COINS
# when you want to look at a finished restaurant without grinding one.
START_COINS = int(os.environ.get("BLOCKHAVEN_TYCOON_COINS", "200"))
COLLECTOR_LOCAL = [-44.0, 0.0, 34.0]
CLAIM_LOCAL = [0.0, 0.0, 44.0]
BUTTON_RADIUS = 7.0
COLLECT_RADIUS = 8.0
BANK_CAP = 250000

WOOD = "#8a5a2b"
TILE = "#e6e6e0"
BRICK = "#c98b5e"
GLASS = "#9fd8e8"
METAL = "#a8adb2"
RED = "#c4281c"
YELLOW = "#f2b01e"
DARK = "#4a3728"


def U(uid, name, cost, income=0.0, req=None, active=None, button=None,
      parts=None, desc=""):
    return {
        "id": uid, "name": name, "cost": cost, "income": income,
        "req": req or [], "active": active, "button": button or [0, 0, 0],
        "parts": parts or [], "desc": desc,
    }


UPGRADES: List[Dict[str, Any]] = [
    U("floor", "Restaurant Floor", 75, 2.0, [], None, [-30, 0, 30], [
        {"t": "box", "p": [0, 0.4, -10], "s": [78, 0.8, 52], "c": TILE, "st": 1},
        {"t": "box", "p": [0, 0.5, -10], "s": [70, 0.8, 44], "c": "#f5f5ef"},
    ], "A clean tiled floor. Every empire starts here."),

    U("grill", "Basic Grill", 150, 5.0, ["floor"], None, [-30, 0, 18], [
        {"t": "box", "p": [-22, 2.6, -28], "s": [22, 5.2, 10], "c": METAL,
         "m": "metal"},
        {"t": "box", "p": [-22, 5.6, -28], "s": [20, 0.8, 8], "c": "#3b3b3b"},
        {"t": "box", "p": [-22, 6.4, -28], "s": [4, 1.2, 4], "c": "#7c4a2a"},
        {"t": "box", "p": [-14, 6.4, -28], "s": [4, 1.2, 4], "c": "#7c4a2a"},
        {"t": "cyl", "p": [-30, 8.0, -30], "s": [3, 6.0, 3], "c": METAL,
         "m": "metal"},
    ], "Two patties at a time. It is a start."),

    U("counter", "Service Counter", 400, 9.0, ["grill"], None, [-30, 0, 6], [
        {"t": "box", "p": [0, 3.0, 8], "s": [52, 6.0, 6], "c": WOOD},
        {"t": "box", "p": [0, 6.4, 8], "s": [56, 0.8, 8], "c": "#d9b88a"},
        {"t": "box", "p": [18, 8.4, 8], "s": [8, 4.0, 5], "c": "#2f3640"},
        {"t": "box", "p": [18, 8.4, 10.8], "s": [7, 3.2, 0.4], "c": "#7fd8ff",
         "m": "neon"},
    ], "Somewhere for the queue to end."),

    U("walls", "Walls & Windows", 700, 7.0, ["counter"], None, [30, 0, 30], [
        {"t": "box", "p": [0, 11, -35], "s": [76, 22, 3], "c": BRICK},
        {"t": "box", "p": [-37, 11, -10], "s": [3, 22, 53], "c": BRICK},
        {"t": "box", "p": [37, 11, -10], "s": [3, 22, 53], "c": BRICK},
        {"t": "box", "p": [-27, 11, 15], "s": [22, 22, 3], "c": BRICK},
        {"t": "box", "p": [27, 11, 15], "s": [22, 22, 3], "c": BRICK},
        {"t": "box", "p": [0, 19.5, 15], "s": [34, 5, 3], "c": BRICK},
        {"t": "box", "p": [-27, 13, 15.4], "s": [16, 10, 0.6], "c": GLASS,
         "m": "glass", "a": 0.55},
        {"t": "box", "p": [27, 13, 15.4], "s": [16, 10, 0.6], "c": GLASS,
         "m": "glass", "a": 0.55},
        {"t": "box", "p": [0, 1.4, 15], "s": [34, 2.8, 4], "c": "#cfd4d8"},
    ], "Weatherproofing. The health inspector insisted."),

    U("fryer", "Fry Station", 1100, 0.0, ["walls"],
      {"payout": 95, "cooldown": 3.5, "pos": [16, 0, -26],
       "label": "Cook fries"}, [30, 0, 18], [
        {"t": "box", "p": [16, 3.0, -28], "s": [18, 6.0, 9], "c": METAL,
         "m": "metal"},
        {"t": "box", "p": [12, 6.4, -28], "s": [6, 1.0, 6], "c": "#e0b055"},
        {"t": "box", "p": [20, 6.4, -28], "s": [6, 1.0, 6], "c": "#e0b055"},
        {"t": "box", "p": [16, 8.2, -32], "s": [16, 4.0, 1.4], "c": "#d94f2a"},
        {"t": "cyl", "p": [26, 4.0, -28], "s": [5, 8.0, 5], "c": "#c9a227"},
    ], "Hands-on income: stand here and press E for a batch."),

    U("roof", "Roof & Trim", 1600, 11.0, ["walls"], None, [30, 0, 6], [
        {"t": "box", "p": [0, 23.5, -10], "s": [82, 2.0, 58], "c": RED,
         "st": 1},
        {"t": "box", "p": [0, 25.5, -10], "s": [76, 2.0, 52], "c": "#a3221a"},
        {"t": "box", "p": [0, 24.6, 16], "s": [82, 3.6, 3], "c": YELLOW},
        {"t": "cyl", "p": [-34, 27.5, -32], "s": [4, 6, 4], "c": METAL,
         "m": "metal"},
    ], "Keeps the rain off the fryer."),

    U("sign", "Neon Sign", 2200, 16.0, ["roof"], None, [-30, 0, -6], [
        {"t": "box", "p": [0, 31.0, 15], "s": [46, 10, 2], "c": "#2f3640"},
        {"t": "box", "p": [0, 31.0, 16.4], "s": [42, 7.4, 0.6], "c": YELLOW,
         "m": "neon", "dec": "burger"},
        {"t": "cyl", "p": [-20, 27.5, 15], "s": [2, 7, 2], "c": METAL},
        {"t": "cyl", "p": [20, 27.5, 15], "s": [2, 7, 2], "c": METAL},
    ], "Visible from the plaza. Free advertising."),

    U("grill2", "Double Grill", 3000, 25.0, ["sign"], None, [-30, 0, -18], [
        {"t": "box", "p": [-22, 2.6, -16], "s": [22, 5.2, 10], "c": METAL,
         "m": "metal"},
        {"t": "box", "p": [-22, 5.6, -16], "s": [20, 0.8, 8], "c": "#3b3b3b"},
        {"t": "box", "p": [-27, 6.4, -16], "s": [4, 1.2, 4], "c": "#7c4a2a"},
        {"t": "box", "p": [-19, 6.4, -16], "s": [4, 1.2, 4], "c": "#7c4a2a"},
        {"t": "box", "p": [-11, 6.4, -16], "s": [4, 1.2, 4], "c": "#7c4a2a"},
        {"t": "box", "p": [-22, 9.0, -20], "s": [24, 1.2, 4], "c": METAL,
         "m": "metal"},
    ], "Twice the patties, twice the profit."),

    U("seating", "Seating Area", 4200, 32.0, ["grill2"], None, [30, 0, -6], [
        {"t": "box", "p": [0, 0.4, 34], "s": [76, 0.8, 30], "c": "#cfd4d8",
         "st": 1},
        {"t": "cyl", "p": [-24, 3.0, 30], "s": [10, 6, 10], "c": "#e2e2da"},
        {"t": "cyl", "p": [-24, 6.2, 30], "s": [14, 0.8, 14], "c": WOOD},
        {"t": "cyl", "p": [0, 3.0, 38], "s": [10, 6, 10], "c": "#e2e2da"},
        {"t": "cyl", "p": [0, 6.2, 38], "s": [14, 0.8, 14], "c": WOOD},
        {"t": "cyl", "p": [24, 3.0, 30], "s": [10, 6, 10], "c": "#e2e2da"},
        {"t": "cyl", "p": [24, 6.2, 30], "s": [14, 0.8, 14], "c": WOOD},
        {"t": "box", "p": [-24, 9.0, 30], "s": [3, 5, 3], "c": YELLOW},
        {"t": "box", "p": [0, 9.0, 38], "s": [3, 5, 3], "c": RED},
        {"t": "box", "p": [24, 9.0, 30], "s": [3, 5, 3], "c": YELLOW},
    ], "Customers linger. Lingering customers buy dessert."),

    U("drivethru", "Drive-Thru", 6000, 50.0, ["seating"], None, [30, 0, -18], [
        {"t": "box", "p": [-52, 0.3, -6], "s": [18, 0.6, 66], "c": "#6d6e6c"},
        {"t": "box", "p": [-52, 0.5, -6], "s": [2, 0.8, 60], "c": "#f5e07a"},
        {"t": "box", "p": [-40, 6.0, 4], "s": [6, 12, 8], "c": BRICK},
        {"t": "box", "p": [-40, 8.0, 8.4], "s": [5, 5, 0.6], "c": GLASS,
         "m": "glass", "a": 0.5},
        {"t": "box", "p": [-52, 5.0, 26], "s": [4, 10, 4], "c": "#2f3640"},
        {"t": "box", "p": [-52, 8.5, 28.2], "s": [6, 5, 0.6], "c": YELLOW,
         "m": "neon"},
        {"t": "box", "p": [-52, 14.0, -30], "s": [16, 1.6, 12], "c": RED},
        {"t": "cyl", "p": [-58, 7.0, -30], "s": [2, 14, 2], "c": METAL},
        {"t": "cyl", "p": [-46, 7.0, -30], "s": [2, 14, 2], "c": METAL},
    ], "They never even leave the car."),

    U("freezer", "Walk-in Freezer", 8500, 0.0, ["drivethru"],
      {"payout": 380, "cooldown": 6.0, "pos": [30, 0, -30],
       "label": "Restock freezer"}, [-30, 0, -30], [
        {"t": "box", "p": [30, 8.0, -30], "s": [20, 16, 14], "c": "#dfe6ea",
         "m": "metal"},
        {"t": "box", "p": [30, 6.0, -22.6], "s": [8, 12, 1.2], "c": METAL,
         "m": "metal"},
        {"t": "box", "p": [30, 16.6, -30], "s": [10, 2, 8], "c": METAL},
        {"t": "box", "p": [34, 11.0, -22.6], "s": [3, 3, 0.8], "c": "#7fd8ff",
         "m": "neon"},
    ], "Cold storage. Restock it by hand for a big payout."),

    U("floor2", "Second Floor", 12000, 72.0, ["freezer"], None, [30, 0, -30], [
        {"t": "box", "p": [0, 26.5, -10], "s": [78, 1.6, 54], "c": TILE,
         "st": 1},
        {"t": "box", "p": [0, 37, -35], "s": [76, 20, 3], "c": BRICK},
        {"t": "box", "p": [-37, 37, -10], "s": [3, 20, 53], "c": BRICK},
        {"t": "box", "p": [37, 37, -10], "s": [3, 20, 53], "c": BRICK},
        {"t": "box", "p": [0, 37, 15], "s": [76, 20, 3], "c": BRICK},
        {"t": "box", "p": [-18, 36, 16.4], "s": [26, 12, 0.6], "c": GLASS,
         "m": "glass", "a": 0.5},
        {"t": "box", "p": [18, 36, 16.4], "s": [26, 12, 0.6], "c": GLASS,
         "m": "glass", "a": 0.5},
        {"t": "box", "p": [0, 47.5, -10], "s": [82, 2, 58], "c": RED, "st": 1},
        {"t": "box", "p": [42, 13, -30], "s": [8, 26, 8], "c": METAL,
         "m": "metal"},
    ], "Upstairs dining. Very fancy."),

    U("rooftop", "Rooftop Garden", 17000, 105.0, ["floor2"], None, [-30, 0, -30], [
        {"t": "box", "p": [0, 49.5, -10], "s": [78, 2, 54], "c": "#5aa84f",
         "st": 1},
        {"t": "cyl", "p": [-24, 53, -24], "s": [4, 6, 4], "c": "#7c503a"},
        {"t": "sph", "p": [-24, 58, -24], "s": [14, 12, 14], "c": "#287f47"},
        {"t": "cyl", "p": [22, 53, 2], "s": [4, 6, 4], "c": "#7c503a"},
        {"t": "sph", "p": [22, 58, 2], "s": [14, 12, 14], "c": "#287f47"},
        {"t": "box", "p": [0, 52, 14], "s": [70, 5, 2], "c": "#d9b88a"},
        {"t": "box", "p": [-30, 52.5, -10], "s": [10, 4, 40], "c": "#8a5a2b"},
    ], "Herbs, hedges and a view of the plaza."),

    U("arches", "Golden Arches", 26000, 160.0, ["rooftop"], None, [30, 0, 30], [
        {"t": "torus", "p": [-16, 62, 8], "s": [26, 5, 26], "c": "#f5c518",
         "m": "metal"},
        {"t": "torus", "p": [16, 62, 8], "s": [26, 5, 26], "c": "#f5c518",
         "m": "metal"},
        {"t": "box", "p": [0, 51, 8], "s": [46, 4, 4], "c": "#e0ac10",
         "m": "metal"},
        {"t": "box", "p": [0, 4, 46], "s": [30, 8, 3], "c": "#f5c518",
         "m": "metal", "dec": "burger"},
    ], "The final flex. Everyone on the plaza can see it."),
]

UPGRADES_BY_ID = {u["id"]: u for u in UPGRADES}
TOTAL_COST = sum(u["cost"] for u in UPGRADES)


class Plot:
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self.index = spec["index"]
        self.id = spec["id"]
        self.name = spec["name"]
        self.origin = spec["origin"]
        self.dir = spec["dir"]
        self.color = spec["color"]
        self.members: List[int] = []
        self.owner: Optional[int] = None
        self.owner_name = ""
        self.built: List[str] = []
        self.bank = 0.0
        self.income = 0.0
        self.active_ready: Dict[str, float] = {}
        self.claimed_at = 0.0
        self.total_earned = 0.0

    # ---------------------------------------------------------------- space
    def to_world(self, local) -> List[float]:
        return [self.origin[0] + local[0] * self.dir,
                self.origin[1] + 2.0 + local[1],
                self.origin[2] + local[2] * self.dir]

    def reset(self) -> None:
        self.members = []
        self.owner = None
        self.owner_name = ""
        self.built = []
        self.bank = 0.0
        self.income = 0.0
        self.active_ready = {}
        self.claimed_at = 0.0
        self.total_earned = 0.0

    def recompute_income(self) -> None:
        self.income = sum(UPGRADES_BY_ID[u]["income"] for u in self.built
                          if u in UPGRADES_BY_ID)

    def available(self) -> List[Dict[str, Any]]:
        out = []
        for upgrade in UPGRADES:
            if upgrade["id"] in self.built:
                continue
            if all(req in self.built for req in upgrade["req"]):
                out.append({
                    "id": upgrade["id"], "name": upgrade["name"],
                    "cost": upgrade["cost"], "income": upgrade["income"],
                    "desc": upgrade["desc"],
                    "p": self.to_world(upgrade["button"]),
                })
        return out

    def actives(self) -> List[Dict[str, Any]]:
        out = []
        for uid in self.built:
            upgrade = UPGRADES_BY_ID.get(uid)
            if not upgrade or not upgrade.get("active"):
                continue
            active = upgrade["active"]
            out.append({
                "id": uid, "label": active["label"],
                "payout": active["payout"], "cooldown": active["cooldown"],
                "p": self.to_world(active["pos"]),
                "ready_in": max(0.0, round(self.active_ready.get(uid, 0.0) - now(), 1)),
            })
        return out

    def payload(self, full: bool = False) -> Dict[str, Any]:
        data = {
            "index": self.index, "id": self.id, "name": self.name,
            "color": self.color, "origin": self.origin, "dir": self.dir,
            "owner": self.owner_name, "members": len(self.members),
            "capacity": PLOT_CAPACITY, "built": list(self.built),
            "bank": int(self.bank), "income": round(self.income, 1),
            "buttons": self.available(), "actives": self.actives(),
            "claim": self.to_world(CLAIM_LOCAL),
            "collector": self.to_world(COLLECTOR_LOCAL),
            "progress": round(len(self.built) / float(len(UPGRADES)), 3),
            "total_earned": int(self.total_earned),
        }
        if full:
            data["geometry"] = [self.geometry_for(uid) for uid in self.built]
        return data

    def geometry_for(self, uid: str) -> Dict[str, Any]:
        upgrade = UPGRADES_BY_ID.get(uid)
        if not upgrade:
            return {"id": uid, "parts": []}
        parts = []
        for part in upgrade["parts"]:
            clone = dict(part)
            clone["p"] = self.to_world(part["p"])
            if self.dir < 0:
                clone["r"] = [0, math.pi, 0]
            parts.append(clone)
        return {"id": uid, "parts": parts}


class BurgerTycoon(GameInstance):
    mode = "endless"
    friendly_fire = False
    shuffle_enabled = False
    respawn_seconds = 3.0

    @staticmethod
    def build_map() -> Dict[str, Any]:
        return tycoon_map.build()

    def setup(self) -> None:
        specs = self.map.get("markers", {}).get("plots", [])
        self.plots: List[Plot] = [Plot(spec) for spec in specs]
        self.phase = "active"
        self.income_accum = 0.0
        self.last_state_push = 0.0

    def team_names(self) -> List[str]:
        return [plot.id for plot in self.plots]

    # ---------------------------------------------------------------- teams
    def pick_team(self, player: Player) -> str:
        free = [p for p in self.plots if not p.members]
        if free:
            return free[0].id
        with_space = [p for p in self.plots if len(p.members) < PLOT_CAPACITY]
        if with_space:
            with_space.sort(key=lambda p: len(p.members))
            return with_space[0].id
        return self.plots[0].id if self.plots else ""

    def plot_by_id(self, plot_id: str) -> Optional[Plot]:
        for plot in self.plots:
            if plot.id == plot_id:
                return plot
        return None

    def plot_of(self, player: Player) -> Optional[Plot]:
        return self.plot_by_id(player.team)

    def on_player_join(self, player: Player) -> None:
        plot = self.plot_of(player)
        player.coins = START_COINS
        if plot is None:
            return
        plot.members.append(player.pid)
        player.plot = plot.index
        if plot.owner is None:
            plot.owner = player.pid
            plot.owner_name = player.username
            plot.claimed_at = now()
            self.system_message("%s claimed %s!" % (player.username, plot.name))
        self.broadcast_plot(plot, full=True)

    def on_player_ready(self, player: Player) -> None:
        plot = self.plot_of(player)
        if plot is None:
            return
        player.send({"t": "tycoon_init",
                     "plots": [p.payload(full=True) for p in self.plots],
                     "upgrades": [{"id": u["id"], "name": u["name"],
                                   "cost": u["cost"], "income": u["income"],
                                   "desc": u["desc"], "req": u["req"],
                                   "active": bool(u.get("active"))}
                                  for u in UPGRADES],
                     "your_plot": plot.index, "coins": player.coins})

    def on_player_leave(self, player: Player) -> None:
        plot = self.plot_of(player)
        if plot is None:
            return
        if player.pid in plot.members:
            plot.members.remove(player.pid)
        if plot.owner == player.pid:
            plot.owner = plot.members[0] if plot.members else None
            if plot.owner:
                owner = self.players.get(plot.owner)
                plot.owner_name = owner.username if owner else ""
        if not plot.members:
            plot.reset()
            self.system_message("%s was reset -- the crew all left."
                                % plot.name)
            self.broadcast({"t": "tycoon_reset", "plot": plot.index})
        self.broadcast_plot(plot)

    def broadcast_plot(self, plot: Plot, full: bool = False) -> None:
        self.broadcast({"t": "tycoon_plot", "plot": plot.payload(full=full)})

    # -------------------------------------------------------------- actions
    def on_action(self, player: Player, message: Dict[str, Any]) -> None:
        kind = message.get("k")
        if kind == "buy":
            self.buy_upgrade(player, str(message.get("id", "")))
        elif kind == "use":
            self.use_active(player, str(message.get("id", "")))
        elif kind == "claim":
            self.claim_plot(player, message.get("plot"))

    def claim_plot(self, player: Player, index: Any) -> None:
        try:
            index = int(index)
        except (TypeError, ValueError):
            return
        target = next((p for p in self.plots if p.index == index), None)
        if target is None:
            return
        current = self.plot_of(player)
        if current is target:
            return
        if len(target.members) >= PLOT_CAPACITY:
            player.send({"t": "notice", "m": "%s is full." % target.name,
                         "bad": True})
            return
        claim_world = target.to_world(CLAIM_LOCAL)
        if math.dist(player.pos, claim_world) > 12.0:
            player.send({"t": "notice", "m": "Stand on the claim pad first.",
                         "bad": True})
            return
        if current is not None:
            if player.pid in current.members:
                current.members.remove(player.pid)
            if current.owner == player.pid:
                current.owner = current.members[0] if current.members else None
                owner = self.players.get(current.owner or 0)
                current.owner_name = owner.username if owner else ""
            if not current.members:
                current.reset()
                self.broadcast({"t": "tycoon_reset", "plot": current.index})
            self.broadcast_plot(current)
        target.members.append(player.pid)
        player.team = target.id
        player.plot = target.index
        if target.owner is None:
            target.owner = player.pid
            target.owner_name = player.username
            target.claimed_at = now()
            self.system_message("%s claimed %s!" % (player.username, target.name))
        else:
            self.system_message("%s joined the %s crew."
                                % (player.username, target.name))
        player.send({"t": "team", "team": player.team, "plot": target.index})
        self.broadcast_plot(target, full=True)

    def buy_upgrade(self, player: Player, upgrade_id: str) -> None:
        plot = self.plot_of(player)
        upgrade = UPGRADES_BY_ID.get(upgrade_id)
        if plot is None or upgrade is None:
            return
        if player.pid not in plot.members:
            player.send({"t": "notice", "m": "That is not your plot.",
                         "bad": True})
            return
        if upgrade_id in plot.built:
            return
        if not all(req in plot.built for req in upgrade["req"]):
            player.send({"t": "notice", "m": "Build the earlier pieces first.",
                         "bad": True})
            return
        button_world = plot.to_world(upgrade["button"])
        if math.dist(player.pos, button_world) > BUTTON_RADIUS * 2.2:
            player.send({"t": "notice", "m": "Stand on the button to buy it.",
                         "bad": True})
            return
        if player.coins < upgrade["cost"]:
            player.send({"t": "notice", "m": "Not enough coins (%d needed)."
                         % upgrade["cost"], "bad": True})
            return
        player.coins -= upgrade["cost"]
        plot.built.append(upgrade_id)
        plot.recompute_income()
        if upgrade.get("active"):
            plot.active_ready[upgrade_id] = 0.0
        player.score += 20
        player.send({"t": "coins", "c": player.coins})
        self.broadcast({"t": "tycoon_build", "plot": plot.index,
                        "upgrade": upgrade_id,
                        "geometry": plot.geometry_for(upgrade_id),
                        "by": player.username})
        self.broadcast_plot(plot)
        self.system_message("%s built %s at %s."
                            % (player.username, upgrade["name"], plot.name))

    def use_active(self, player: Player, upgrade_id: str) -> None:
        plot = self.plot_of(player)
        upgrade = UPGRADES_BY_ID.get(upgrade_id)
        if plot is None or upgrade is None or not upgrade.get("active"):
            return
        if player.pid not in plot.members or upgrade_id not in plot.built:
            return
        moment = now()
        if plot.active_ready.get(upgrade_id, 0.0) > moment:
            return
        station = plot.to_world(upgrade["active"]["pos"])
        if math.dist(player.pos, station) > BUTTON_RADIUS * 2.0:
            player.send({"t": "notice", "m": "Move closer to the station.",
                         "bad": True})
            return
        plot.active_ready[upgrade_id] = moment + float(upgrade["active"]["cooldown"])
        payout = float(upgrade["active"]["payout"])
        held = player.weapon()
        if held and (held.get("data", {}).get("stats", {}) or {}).get("build_bonus"):
            payout *= 1.0 + float(held["data"]["stats"]["build_bonus"])
        plot.bank = min(BANK_CAP, plot.bank + payout)
        plot.total_earned += payout
        player.score += 2
        self.broadcast({"t": "tycoon_active", "plot": plot.index,
                        "id": upgrade_id, "by": player.username,
                        "payout": int(payout),
                        "cooldown": upgrade["active"]["cooldown"]})
        self.broadcast_plot(plot)

    # ----------------------------------------------------------------- tick
    def on_tick(self, dt: float) -> None:
        for plot in self.plots:
            if plot.income > 0 and plot.members:
                plot.bank = min(BANK_CAP, plot.bank + plot.income * dt)
                plot.total_earned += plot.income * dt
        # collectors
        for player in self.players.values():
            plot = self.plot_of(player)
            if plot is None or not player.alive:
                continue
            collector = plot.to_world(COLLECTOR_LOCAL)
            if math.dist(player.pos, collector) <= COLLECT_RADIUS and plot.bank >= 1:
                amount = int(plot.bank)
                plot.bank -= amount
                player.coins += amount
                player.score += max(1, amount // 50)
                player.send({"t": "coins", "c": player.coins, "gained": amount})
                self.broadcast({"t": "tycoon_collect", "plot": plot.index,
                                "by": player.username, "amount": amount})
        moment = now()
        if moment - self.last_state_push > 1.0:
            self.last_state_push = moment
            self.broadcast({"t": "tycoon_state",
                            "plots": [p.payload() for p in self.plots]})

    def round_state(self) -> Dict[str, Any]:
        return {
            "plots": [{"index": p.index, "name": p.name, "owner": p.owner_name,
                       "members": len(p.members), "income": round(p.income, 1),
                       "built": len(p.built), "total": len(UPGRADES),
                       "color": p.color, "earned": int(p.total_earned)}
                      for p in self.plots],
            "endless": True,
        }

    # Endless world: never ends, never shuffles.
    def end_round(self, winner: str, reason: str = "") -> None:
        return

    def start_vote(self) -> None:
        return
