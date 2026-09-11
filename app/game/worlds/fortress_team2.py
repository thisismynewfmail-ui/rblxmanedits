"""Fortress Team 2 -- payload push on Dustworks."""
from __future__ import annotations

import math
from typing import Any, Dict, List

from ..instance import GameInstance, now
from ..maps import payload as payload_map

SETUP_SECONDS = 18.0
ROUND_SECONDS = 420.0
CHECKPOINT_BONUS = 90.0
CART_RADIUS = 11.0
PUSH_SPEED = 5.2          # units per second with a single pusher
PUSH_BONUS = 0.55         # extra multiplier per additional pusher (capped)
MAX_PUSHERS = 4
ROLLBACK_DELAY = 9.0
ROLLBACK_SPEED = 3.0
ROUND_WINS_TO_MATCH = 3
CART_HEAL_PER_SEC = 3.0


class FortressTeam2(GameInstance):
    mode = "payload"
    friendly_fire = False

    @staticmethod
    def build_map() -> Dict[str, Any]:
        return payload_map.build()

    def setup(self) -> None:
        markers = self.map.get("markers", {})
        self.track: List[List[float]] = markers.get("track", [[0, 0, 0], [10, 0, 0]])
        self.track_length: float = float(markers.get(
            "track_length", payload_map.track_length(self.track)))
        self.checkpoint_fractions: List[float] = list(
            markers.get("checkpoints", [0.34, 0.68, 1.0]))
        self.forward_spawns = {
            1: markers.get("forward_blue_1", []),
            2: markers.get("forward_blue_2", []),
        }
        self.cart_distance = 0.0
        self.cart_pos, self.cart_yaw = payload_map.point_at(self.track, 0.0)
        self.checkpoints_reached = 0
        self.round_wins = {"red": 0, "blue": 0}
        self.attackers = "blue"
        self.defenders = "red"
        self.last_push = now()
        self.pushers = 0
        self.blocked = False
        self.phase = "setup"
        self.phase_until = now() + SETUP_SECONDS
        self.round_ends = self.phase_until + ROUND_SECONDS
        self.match_over = False

    def team_names(self) -> List[str]:
        return ["red", "blue"]

    # ------------------------------------------------------------- spawning
    def spawn_points(self, team: str):
        if team == self.attackers and self.checkpoints_reached > 0:
            forward = self.forward_spawns.get(
                min(self.checkpoints_reached, 2), [])
            if forward:
                return forward
        return super().spawn_points(team)

    # ------------------------------------------------------------------ flow
    def round_state(self) -> Dict[str, Any]:
        progress = self.cart_distance / max(1.0, self.track_length)
        return {
            "cart": {
                "p": [round(v, 2) for v in self.cart_pos],
                "yaw": round(self.cart_yaw, 3),
                "progress": round(progress, 4),
                "pushers": self.pushers,
                "blocked": self.blocked,
                "distance": round(self.cart_distance, 1),
            },
            "attackers": self.attackers,
            "defenders": self.defenders,
            "checkpoints": [round(f, 3) for f in self.checkpoint_fractions],
            "checkpoints_reached": self.checkpoints_reached,
            "round_wins": dict(self.round_wins),
            "time_left": max(0, int(self.round_ends - now())),
            "setup_left": max(0, int(self.phase_until - now()))
            if self.phase == "setup" else 0,
            "target_wins": ROUND_WINS_TO_MATCH,
            "track": self.track,
            "track_length": self.track_length,
            "teams": self.team_counts(),
            "match_over": self.match_over,
        }

    def team_counts(self) -> Dict[str, int]:
        counts = {"red": 0, "blue": 0}
        for player in self.players.values():
            if player.team in counts:
                counts[player.team] += 1
        return counts

    def on_tick(self, dt: float) -> None:
        moment = now()
        if self.phase == "setup":
            if moment >= self.phase_until:
                self.phase = "active"
                self.round_ends = moment + ROUND_SECONDS
                self.system_message("The gates are open -- push the cart!")
                self.push_event("setup_end")
            return
        if self.phase != "active":
            return

        attackers = 0
        defenders = 0
        for player in self.players.values():
            if not player.alive:
                continue
            if math.dist(player.pos, self.cart_pos) <= CART_RADIUS:
                if player.team == self.attackers:
                    attackers += 1
                else:
                    defenders += 1
        self.pushers = attackers
        self.blocked = defenders > 0 and attackers > 0

        if attackers > 0 and defenders == 0:
            multiplier = 1.0 + PUSH_BONUS * min(attackers - 1, MAX_PUSHERS - 1)
            self.cart_distance = min(self.track_length,
                                     self.cart_distance + PUSH_SPEED * multiplier * dt)
            self.last_push = moment
            for player in self.players.values():
                if player.alive and player.team == self.attackers and \
                        math.dist(player.pos, self.cart_pos) <= CART_RADIUS:
                    self.heal(player, CART_HEAL_PER_SEC * dt)
                    player.score += 0 if self.tick_count % 20 else 1
        elif defenders > 0:
            self.last_push = moment
        elif moment - self.last_push > ROLLBACK_DELAY:
            floor_distance = self.checkpoint_distance(self.checkpoints_reached)
            self.cart_distance = max(floor_distance,
                                     self.cart_distance - ROLLBACK_SPEED * dt)

        self.cart_pos, self.cart_yaw = payload_map.point_at(
            self.track, self.cart_distance)

        progress = self.cart_distance / max(1.0, self.track_length)
        while self.checkpoints_reached < len(self.checkpoint_fractions) and \
                progress >= self.checkpoint_fractions[self.checkpoints_reached] - 1e-6:
            self.checkpoints_reached += 1
            if self.checkpoints_reached >= len(self.checkpoint_fractions):
                self.finish_round(self.attackers,
                                  "%s pushed the cart home!" % self.attackers.upper())
                return
            self.round_ends += CHECKPOINT_BONUS
            self.system_message(
                "Checkpoint %d captured! +%d seconds."
                % (self.checkpoints_reached, int(CHECKPOINT_BONUS)))
            self.push_event("checkpoint", n=self.checkpoints_reached,
                            team=self.attackers)

        if moment >= self.round_ends:
            self.finish_round(self.defenders,
                              "%s held the line!" % self.defenders.upper())

    def checkpoint_distance(self, index: int) -> float:
        if index <= 0:
            return 0.0
        fraction = self.checkpoint_fractions[min(index, len(self.checkpoint_fractions)) - 1]
        return fraction * self.track_length

    def finish_round(self, winner: str, reason: str) -> None:
        self.round_wins[winner] = self.round_wins.get(winner, 0) + 1
        if self.round_wins[winner] >= ROUND_WINS_TO_MATCH:
            self.match_over = True
            self.system_message("%s WINS THE MATCH %d-%d!"
                                % (winner.upper(), self.round_wins["red"],
                                   self.round_wins["blue"]))
            self.end_round(winner, reason)
        else:
            self.system_message(
                "%s wins round %d! (%d-%d) Teams swap ends."
                % (winner.upper(), self.round_number, self.round_wins["red"],
                   self.round_wins["blue"]))
            self.phase = "intermission"
            self.phase_until = now() + 8.0
            self.broadcast({"t": "round_end", "winner": winner,
                            "reason": reason, "match_over": False,
                            "scores": self.scoreboard(),
                            "round_wins": dict(self.round_wins)})
            for player in self.players.values():
                self.host.report_round(self, player,
                                       won=player.team == winner)

    def tick(self) -> None:
        super().tick()
        with self.lock:
            if self.phase == "intermission" and now() >= self.phase_until:
                self.swap_and_restart()

    def swap_and_restart(self) -> None:
        """Swap ends and start the next round of the same match."""
        self.attackers, self.defenders = self.defenders, self.attackers
        for player in self.players.values():
            player.team = "red" if player.team == "blue" else "blue"
            player.send({"t": "team", "team": player.team})
        self.reset_cart()
        self.round_number += 1
        self.phase = "setup"
        self.phase_until = now() + SETUP_SECONDS
        self.round_ends = self.phase_until + ROUND_SECONDS
        for player in self.players.values():
            player.kills = 0
            player.deaths = 0
            self.spawn_player(player)
        self.system_message("Round %d -- %s is attacking. Setup: %ds"
                            % (self.round_number, self.attackers.upper(),
                               int(SETUP_SECONDS)))
        self.broadcast({"t": "round_start", "round": self.round_number,
                        "state": self.full_state()})
        self.broadcast({"t": "teams",
                        "map": {p.pid: p.team for p in self.players.values()}})

    def reset_cart(self) -> None:
        self.cart_distance = 0.0
        self.checkpoints_reached = 0
        self.cart_pos, self.cart_yaw = payload_map.point_at(self.track, 0.0)
        self.last_push = now()
        self.pushers = 0
        self.blocked = False

    def restart_round(self) -> None:
        """Called after the post-match shuffle vote: brand new match."""
        self.round_wins = {"red": 0, "blue": 0}
        self.match_over = False
        self.attackers, self.defenders = "blue", "red"
        self.reset_cart()
        self.round_number = 1
        self.phase = "setup"
        self.phase_until = now() + SETUP_SECONDS
        self.round_ends = self.phase_until + ROUND_SECONDS
        for player in self.players.values():
            player.vote = None
            player.kills = 0
            player.deaths = 0
            self.spawn_player(player)
        self.broadcast({"t": "round_start", "round": self.round_number,
                        "state": self.full_state(), "new_match": True})
        self.system_message("New match! %s attacks first." % self.attackers.upper())
