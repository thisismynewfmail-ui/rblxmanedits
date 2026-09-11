"""Capture The Flag on Crossroads."""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

from ..instance import GameInstance, Player, now
from ..maps import crossroads

CAPTURES_TO_WIN = 3
FLAG_RETURN_SECONDS = 22.0
ROUND_SECONDS = 600.0
PICKUP_RADIUS = 7.0
CAPTURE_RADIUS = 12.0


class Flag:
    __slots__ = ("team", "home", "pos", "state", "carrier", "dropped_at")

    def __init__(self, team: str, home: List[float]):
        self.team = team
        self.home = list(home)
        self.pos = list(home)
        self.state = "home"      # home | carried | dropped
        self.carrier: Optional[int] = None
        self.dropped_at = 0.0

    def payload(self) -> Dict[str, Any]:
        return {"team": self.team, "state": self.state,
                "p": [round(v, 2) for v in self.pos],
                "carrier": self.carrier or 0,
                "home": [round(v, 2) for v in self.home]}


class CaptureTheFlag(GameInstance):
    mode = "captures"
    friendly_fire = False

    @staticmethod
    def build_map() -> Dict[str, Any]:
        return crossroads.build()

    def setup(self) -> None:
        markers = self.map.get("markers", {})
        self.flags: Dict[str, Flag] = {}
        for team in ("red", "blue"):
            marker = markers.get("flag_%s" % team, {"p": [0, 6, 0]})
            self.flags[team] = Flag(team, list(marker["p"]))
        self.captures = {"red": 0, "blue": 0}
        self.round_ends = now() + ROUND_SECONDS
        self.phase = "active"

    def team_names(self) -> List[str]:
        return ["red", "blue"]

    def enemy_of(self, team: str) -> str:
        return "blue" if team == "red" else "red"

    # ------------------------------------------------------------------ flow
    def round_state(self) -> Dict[str, Any]:
        return {
            "captures": dict(self.captures),
            "flags": {team: flag.payload() for team, flag in self.flags.items()},
            "time_left": max(0, int(self.round_ends - now())),
            "target": CAPTURES_TO_WIN,
            "teams": self.team_counts(),
        }

    def team_counts(self) -> Dict[str, int]:
        counts = {"red": 0, "blue": 0}
        for player in self.players.values():
            if player.team in counts:
                counts[player.team] += 1
        return counts

    def on_player_leave(self, player: Player) -> None:
        for flag in self.flags.values():
            if flag.carrier == player.pid:
                self.drop_flag(flag, player.pos)

    def on_kill(self, killer: Optional[Player], victim: Player,
                weapon_name: str) -> None:
        for flag in self.flags.values():
            if flag.carrier == victim.pid:
                self.drop_flag(flag, victim.pos)
                if killer is not None:
                    killer.score += 15
                    self.system_message("%s defended the %s flag!"
                                        % (killer.username, flag.team))

    def drop_flag(self, flag: Flag, position) -> None:
        flag.state = "dropped"
        flag.carrier = None
        flag.pos = [position[0], max(position[1], flag.home[1] - 4.0),
                    position[2]]
        flag.dropped_at = now()
        self.push_event("flag_drop", team=flag.team, p=flag.pos)
        self.broadcast({"t": "flags",
                        "f": {t: f.payload() for t, f in self.flags.items()}})

    def return_flag(self, flag: Flag, by: Optional[Player] = None) -> None:
        flag.state = "home"
        flag.carrier = None
        flag.pos = list(flag.home)
        self.push_event("flag_return", team=flag.team,
                        by=by.username if by else "")
        if by is not None:
            by.score += 8
            self.system_message("%s returned the %s flag."
                                % (by.username, flag.team))
        else:
            self.system_message("The %s flag returned to base." % flag.team)
        self.broadcast({"t": "flags",
                        "f": {t: f.payload() for t, f in self.flags.items()}})

    def on_tick(self, dt: float) -> None:
        if self.phase != "active":
            return
        moment = now()
        for flag in self.flags.values():
            if flag.state == "carried":
                carrier = self.players.get(flag.carrier or 0)
                if carrier is None or not carrier.alive:
                    self.drop_flag(flag, flag.pos)
                    continue
                flag.pos = [carrier.pos[0], carrier.pos[1] + 5.6, carrier.pos[2]]
            elif flag.state == "dropped":
                if moment - flag.dropped_at > FLAG_RETURN_SECONDS:
                    self.return_flag(flag)

        for player in list(self.players.values()):
            if not player.alive:
                continue
            enemy_flag = self.flags[self.enemy_of(player.team)]
            own_flag = self.flags[player.team]
            # pick up the enemy flag
            if enemy_flag.state in ("home", "dropped"):
                if math.dist(player.pos, enemy_flag.pos) < PICKUP_RADIUS:
                    enemy_flag.state = "carried"
                    enemy_flag.carrier = player.pid
                    player.score += 5
                    self.push_event("flag_take", team=enemy_flag.team,
                                    by=player.username, pid=player.pid)
                    self.system_message("%s picked up the %s flag!"
                                        % (player.username, enemy_flag.team))
                    self.broadcast({"t": "flags", "f": {
                        t: f.payload() for t, f in self.flags.items()}})
                    continue
            # return our own dropped flag by touching it
            if own_flag.state == "dropped" and \
                    math.dist(player.pos, own_flag.pos) < PICKUP_RADIUS:
                self.return_flag(own_flag, player)
                continue
            # capture
            if enemy_flag.state == "carried" and enemy_flag.carrier == player.pid:
                if own_flag.state == "home" and \
                        math.dist(player.pos, own_flag.home) < CAPTURE_RADIUS:
                    self.capture(player, enemy_flag)

        if moment >= self.round_ends:
            leader = max(self.captures, key=lambda t: self.captures[t])
            other = self.enemy_of(leader)
            if self.captures[leader] == self.captures[other]:
                self.end_round("", "Time up -- it's a draw!")
            else:
                self.end_round(leader, "Time up -- %s leads %d-%d"
                               % (leader.upper(), self.captures[leader],
                                  self.captures[other]))

    def capture(self, player: Player, flag: Flag) -> None:
        self.captures[player.team] += 1
        player.score += 60
        flag.state = "home"
        flag.carrier = None
        flag.pos = list(flag.home)
        self.push_event("flag_capture", team=player.team, by=player.username,
                        score=dict(self.captures))
        self.system_message("%s CAPTURED the %s flag! (%s %d - %d %s)"
                            % (player.username, flag.team,
                               "RED", self.captures["red"],
                               self.captures["blue"], "BLUE"))
        self.broadcast({"t": "flags",
                        "f": {t: f.payload() for t, f in self.flags.items()}})
        if self.captures[player.team] >= CAPTURES_TO_WIN:
            self.end_round(player.team,
                           "%s captured %d flags" % (player.team.upper(),
                                                     CAPTURES_TO_WIN))

    def restart_round(self) -> None:
        self.captures = {"red": 0, "blue": 0}
        for flag in self.flags.values():
            flag.state = "home"
            flag.carrier = None
            flag.pos = list(flag.home)
        self.round_ends = now() + ROUND_SECONDS
        super().restart_round()
        self.broadcast({"t": "flags",
                        "f": {t: f.payload() for t, f in self.flags.items()}})
