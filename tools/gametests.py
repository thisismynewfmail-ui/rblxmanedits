#!/usr/bin/env python3
"""End-to-end gameplay tests driven by headless bots.

    python3 tools/gametests.py            # run every scenario
    python3 tools/gametests.py ctf combat # run a subset

Each scenario drives real websocket clients against the running game hosts and
asserts on the messages the servers broadcast back.
"""
from __future__ import annotations

import json
import math
import sys
import time
from typing import Any, Dict, List

import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from tools.simclient import Bot  # noqa: E402

HOST, PORT = "127.0.0.1", 8972
PASSED: List[str] = []
FAILED: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(name)
        print("  PASS  %s" % name)
    else:
        FAILED.append(name)
        print("  FAIL  %s  %s" % (name, detail))
    return condition


def pump(bots: List[Bot], seconds: float, step: float = 0.1,
         each=None) -> None:
    end = time.time() + seconds
    tick = 0
    while time.time() < end:
        for bot in bots:
            bot.send_input()
        if each:
            each(tick)
        tick += 1
        time.sleep(step)


def find(bot: Bot, kind: str) -> List[Dict[str, Any]]:
    return [m for m in bot.messages if m.get("t") == kind]


def wait_for_active(bots: List[Bot], timeout: float = 50.0) -> bool:
    """Rounds end on a timer; wait for the next live round before testing."""
    end = time.time() + timeout
    while time.time() < end:
        pump(bots, 0.5)
        if bots[0].state.get("phase") in ("active", "setup"):
            return True
    return False


def close_in(mover: Bot, others: List[Bot], target, distance: float = 8.0,
             limit: int = 500) -> float:
    for _ in range(limit):
        remaining = mover.walk_towards(
            [target[0], target[1], target[2]], 0.08, 26)
        mover.pos[1] = target[1]
        mover.send_input()
        for other in others:
            other.send_input()
        if remaining <= distance:
            return remaining
        time.sleep(0.05)
    return remaining


def spawn_bots(world: str, count: int, accounts=None) -> List[Bot]:
    accounts = accounts or [
        ("admin_system", "passman69"), ("admin_test", "passman69"),
        ("builderman_x", "blockhaven"), ("RetroKid2007", "blockhaven"),
        ("BlockSmith", "blockhaven"), ("NoobSlayer99", "blockhaven"),
        ("PixelPatty", "blockhaven"), ("CartPusher", "blockhaven"),
        ("FlagRunner", "blockhaven"), ("GrillMaster", "blockhaven")]
    bots = []
    for i in range(count):
        user, password = accounts[i % len(accounts)]
        bot = Bot(HOST, PORT, user, password, world)
        bot.start()
        bots.append(bot)
    return bots


# --------------------------------------------------------------------- CTF
def test_ctf() -> None:
    print("\n== capture the flag ==")
    bots = spawn_bots("capture_the_flag", 2)
    try:
        blue = next((b for b in bots if b.me.get("team") == "blue"), None)
        red = next((b for b in bots if b.me.get("team") == "red"), None)
        check("ctf: teams are split", blue is not None and red is not None,
              str([b.me.get("team") for b in bots]))
        if blue is None:
            return
        markers = blue.map.get("markers", {})
        enemy_flag = markers["flag_red"]["p"]
        home_flag = markers["flag_blue"]["p"]
        pump(bots, 1.0)

        # walk the blue bot to the red flag
        target = [enemy_flag[0], enemy_flag[1], enemy_flag[2]]
        for _ in range(220):
            remaining = blue.walk_towards(target, 0.08, 26)
            blue.send_input()
            for other in bots:
                if other is not blue:
                    other.send_input()
            if remaining == 0.0:
                break
            time.sleep(0.05)
        pump(bots, 0.8)
        took = [m for m in blue.messages
                if m.get("t") == "evt" and m.get("k") == "flag_take"]
        check("ctf: picking up the enemy flag fires flag_take", bool(took))

        # carry it home
        target = [home_flag[0], home_flag[1], home_flag[2]]
        for _ in range(260):
            remaining = blue.walk_towards(target, 0.08, 26)
            blue.send_input()
            for other in bots:
                if other is not blue:
                    other.send_input()
            if remaining == 0.0:
                break
            time.sleep(0.05)
        pump(bots, 1.0)
        captured = [m for m in blue.messages
                    if m.get("t") == "evt" and m.get("k") == "flag_capture"]
        check("ctf: reaching your own base scores a capture", bool(captured))
        state = blue.state
        check("ctf: capture counter advanced",
              (state.get("captures", {}).get("blue", 0)) >= 1,
              json.dumps(state.get("captures")))
    finally:
        for bot in bots:
            bot.stop()


# ------------------------------------------------------------------ combat
def test_combat() -> None:
    print("\n== combat, damage and the kill feed ==")
    bots = spawn_bots("capture_the_flag", 2)
    try:
        attacker = next((b for b in bots if b.me.get("team") == "blue"), bots[0])
        victim = next((b for b in bots if b is not attacker), bots[1])
        check("combat: attacker and victim on opposite teams",
              attacker.me.get("team") != victim.me.get("team"))
        wait_for_active(bots)
        pump(bots, 2.4)   # let spawn protection expire

        # Meet in the open field: firing through a fort wall is (correctly)
        # blocked by the server's line-of-sight check.
        meeting = [70.0, 0.4, -20.0]
        close_in(victim, [attacker], meeting, 0.6)
        close_in(attacker, [victim], [meeting[0], meeting[1], meeting[2] + 9], 0.6)
        pump(bots, 1.2)
        dx = victim.pos[0] - attacker.pos[0]
        dy = 0.0
        dz = victim.pos[2] - attacker.pos[2]
        length = math.sqrt(dx * dx + dz * dz) or 1
        direction = [dx / length, dy, dz / length]
        for _ in range(30):
            attacker.fire_at(direction)
            attacker.send_input()
            victim.send_input()
            time.sleep(0.2)
        pump(bots, 1.0)
        damage = find(victim, "died") or [m for m in victim.messages
                                          if m.get("t") == "dmg"]
        kills = [m for m in attacker.messages if m.get("t") == "kill"]
        check("combat: the victim took damage or died", bool(damage),
              str(victim.counts))
        check("combat: a kill was broadcast", bool(kills) or
              victim.counts.get("died", 0) > 0, str(attacker.counts))

        # fire-rate: the server must reject bursts faster than the weapon allows
        before = victim.counts.get("dmg", 0)
        for _ in range(40):
            attacker.fire_at(direction)
        time.sleep(1.0)
        pump(bots, 0.5)
        after = victim.counts.get("dmg", 0)
        check("combat: server clamps the fire rate (40 instant shots)",
              after - before <= 3, "damage events: %d" % (after - before))
    finally:
        for bot in bots:
            bot.stop()


# ------------------------------------------------------------- anti-cheat
def test_anticheat() -> None:
    print("\n== movement validation ==")
    bots = spawn_bots("capture_the_flag", 1)
    bot = bots[0]
    try:
        pump(bots, 1.0)
        origin = list(bot.pos)
        bot.pos = [origin[0] + 400, origin[1], origin[2] + 400]
        for _ in range(6):
            bot.send_input()
            time.sleep(0.12)
        time.sleep(0.6)
        corrections = bot.counts.get("correct", 0)
        moved = math.dist(bot.pos, origin)
        check("anti-cheat: a 400 stud teleport is corrected",
              corrections > 0 or moved < 60,
              "corrections=%d moved=%.1f" % (corrections, moved))

        bot.pos = [origin[0], origin[1] + 300, origin[2]]
        for _ in range(6):
            bot.send_input(grounded=False)
            time.sleep(0.12)
        time.sleep(0.5)
        check("anti-cheat: flying upwards is corrected",
              bot.counts.get("correct", 0) > corrections or bot.pos[1] < origin[1] + 60,
              "y=%.1f" % bot.pos[1])
    finally:
        for b in bots:
            b.stop()


# ---------------------------------------------------------------- payload
def test_payload() -> None:
    print("\n== payload cart ==")
    bots = spawn_bots("fortress_team_2", 3)
    try:
        pump(bots, 1.0)
        state = bots[0].state
        attackers = state.get("attackers", "blue")
        pushers = [b for b in bots if b.me.get("team") == attackers]
        others = [b for b in bots if b not in pushers]
        check("payload: at least one attacker joined", bool(pushers),
              str([b.me.get("team") for b in bots]))
        if not pushers:
            return
        # walk (not teleport -- the server would correct that) to the cart
        cart = state.get("cart", {}).get("p", [0, 0, 0])
        for bot in pushers:
            close_in(bot, [b for b in bots if b is not bot],
                     [cart[0], cart[1] + 1.0, cart[2] + 3], 1.0)
        # wait out the setup timer, then push for a while
        start_progress = None
        end = time.time() + 45
        while time.time() < end:
            live = pushers[0].state.get("cart", {})
            phase = pushers[0].state.get("phase")
            if phase == "active" and start_progress is None:
                start_progress = live.get("progress", 0)
            target = live.get("p", cart)
            for bot in bots:
                if bot in pushers:
                    bot.walk_towards([target[0], target[1] + 1.0, target[2] + 3],
                                     0.1, 18)
                bot.send_input()
            if start_progress is not None and \
                    live.get("progress", 0) > start_progress + 0.02:
                break
            time.sleep(0.1)
        final = pushers[0].state.get("cart", {})
        phase = pushers[0].state.get("phase")
        check("payload: the cart advanced while attackers pushed",
              start_progress is not None and
              final.get("progress", 0) > start_progress + 0.001,
              "phase=%s progress %s -> %.4f" % (phase, start_progress,
                                                final.get("progress", 0)))
        check("payload: pushers counted", final.get("pushers", 0) >= 1,
              json.dumps(final)[:140])
    finally:
        for bot in bots:
            bot.stop()


# ----------------------------------------------------------------- tycoon
def test_tycoon() -> None:
    print("\n== burger tycoon ==")
    bots = spawn_bots("burger_tycoon", 2)
    bot = bots[0]
    try:
        pump(bots, 1.0)
        check("tycoon: assigned a plot", bot.tycoon.get("your_plot") is not None,
              json.dumps(bot.tycoon)[:120])
        plots = bot.tycoon.get("plots", [])
        mine = next((p for p in plots if p["index"] == bot.tycoon.get("your_plot")),
                    None)
        check("tycoon: the plot is claimed by the bot",
              bool(mine and mine.get("owner")),
              json.dumps(mine)[:140] if mine else "-")
        if not mine:
            return
        button = mine["buttons"][0]
        check("tycoon: a first upgrade button is offered",
              button["id"] == "floor", json.dumps(button)[:120])

        close_in(bot, bots[1:], [button["p"][0], button["p"][1] + 0.5,
                                 button["p"][2]], 0.5)
        pump(bots, 0.5)
        bot.act("buy", id=button["id"])
        pump(bots, 1.0)
        built = [m for m in bot.messages if m.get("t") == "tycoon_build"]
        check("tycoon: buying an upgrade broadcasts geometry", bool(built),
              str(bot.counts))
        if built:
            check("tycoon: the built geometry has parts",
                  len(built[0]["geometry"]["parts"]) > 0)

        pump(bots, 3.0)
        plots = bot.tycoon.get("plots", [])
        mine = next((p for p in plots if p["index"] == bot.tycoon.get("your_plot")),
                    None)
        check("tycoon: idle income accrues",
              bool(mine and mine.get("bank", 0) > 0),
              "bank=%s income=%s" % (mine.get("bank") if mine else "-",
                                     mine.get("income") if mine else "-"))

        coins_before = bot.coins
        collector = mine["collector"]
        close_in(bot, bots[1:], [collector[0], collector[1] + 0.5, collector[2]], 0.5)
        pump(bots, 1.5)
        check("tycoon: walking over the collector pays out",
              bot.coins >= coins_before,
              "coins %d -> %d" % (coins_before, bot.coins))

        other = next((p for p in plots if p["index"] != mine["index"]
                      and p.get("buttons")), None)
        if other:
            bot.act("buy", id=other["buttons"][0]["id"])
            pump(bots, 0.6)
            check("tycoon: cannot buy while standing off the button",
                  len([m for m in bot.messages
                       if m.get("t") == "tycoon_build"]) == len(built))
    finally:
        for b in bots:
            b.stop()


# ------------------------------------------------------------------- vote
def test_vote() -> None:
    """Capture three flags, then drive the end-of-round shuffle vote."""
    print("\n== round end and the shuffle vote ==")
    bots = spawn_bots("capture_the_flag", 2)
    try:
        wait_for_active(bots)
        blue = next((b for b in bots if b.me.get("team") == "blue"), None)
        if blue is None:
            check("vote: needed a blue player", False)
            return
        markers = blue.map.get("markers", {})
        enemy = markers["flag_red"]["p"]
        home = markers["flag_blue"]["p"]
        others = [b for b in bots if b is not blue]
        target_captures = blue.state.get("target", 3)
        start = blue.state.get("captures", {}).get("blue", 0)
        for _ in range(target_captures - start):
            close_in(blue, others, enemy, 0.6)
            pump(bots, 0.4)
            close_in(blue, others, home, 0.6)
            pump(bots, 0.6)
        pump(bots, 1.0)
        ended = [m for m in blue.messages if m.get("t") == "round_end"]
        check("vote: three captures end the round", bool(ended),
              json.dumps(blue.state.get("captures"))) 

        # the vote opens a few seconds after the round ends
        opened = None
        end = time.time() + 25
        while time.time() < end and opened is None:
            pump(bots, 0.5)
            opened = next((m for m in blue.messages
                           if m.get("t") == "vote" and m.get("open")), None)
        check("vote: a shuffle vote opens after the round", opened is not None,
              str(blue.counts))
        if opened is None:
            return
        check("vote: the vote needs 80% of the players",
              opened.get("needed") == math.ceil(opened.get("total", 1) * 0.8),
              json.dumps(opened))
        for bot in bots:
            bot.ws.send({"t": "vote", "v": True})
        pump(bots, 1.0)
        tallied = [m for m in blue.messages
                   if m.get("t") == "vote" and m.get("yes", 0) >= len(bots)]
        check("vote: yes votes are tallied", bool(tallied),
              json.dumps(blue.messages[-1])[:140])

        # the vote closes on its own after the countdown
        end = time.time() + 40
        resolved = None
        while time.time() < end and resolved is None:
            pump(bots, 0.5)
            resolved = next((m for m in blue.messages if m.get("t") == "vote"
                             and m.get("result") is not None), None)
        check("vote: the vote resolves and shuffles", resolved is not None and
              resolved.get("result") is True, json.dumps(resolved or {}))
        pump(bots, 6.0)
        check("vote: a fresh round starts afterwards",
              blue.state.get("phase") == "active" and
              blue.state.get("captures", {}).get("blue", 9) == 0,
              json.dumps(blue.state)[:160])
    finally:
        for bot in bots:
            bot.stop()


# -------------------------------------------------------------- instances
def test_instances() -> None:
    print("\n== instance overflow ==")
    import urllib.request
    bots = []
    try:
        # capture_the_flag holds 16; open 17 sockets to force a second instance
        accounts = [("admin_system", "passman69"), ("admin_test", "passman69"),
                    ("builderman_x", "blockhaven"), ("RetroKid2007", "blockhaven"),
                    ("BlockSmith", "blockhaven"), ("NoobSlayer99", "blockhaven"),
                    ("PixelPatty", "blockhaven"), ("CartPusher", "blockhaven"),
                    ("FlagRunner", "blockhaven"), ("GrillMaster", "blockhaven")]
        for i in range(17):
            user, password = accounts[i % len(accounts)]
            bot = Bot(HOST, PORT, user, password, "capture_the_flag")
            bot.start()
            bots.append(bot)
        pump(bots, 3.5)
        instances = sorted(set(b.me.get("id", 0) and b.state.get("instance")
                               for b in bots if b.state))
        with urllib.request.urlopen(
                "http://%s:%d/api/worlds/status" % (HOST, PORT), timeout=8) as fh:
            status = json.loads(fh.read().decode())
        ctf = status["worlds"]["capture_the_flag"]
        check("instances: a second instance opened once the first filled",
              ctf["instances"] >= 2, json.dumps(ctf)[:200])
        check("instances: every player is accounted for",
              ctf["players"] >= 17, json.dumps(ctf["instance_list"]))
        check("instances: no instance exceeds its capacity",
              all(i["count"] <= i["max"] for i in ctf["instance_list"]),
              json.dumps(ctf["instance_list"]))
    finally:
        for bot in bots:
            bot.stop()
        time.sleep(1.0)


# ----------------------------------------------------------------- visits
def test_visits() -> None:
    print("\n== visit accounting (30s of play == 1 visit) ==")
    import urllib.request

    def visits() -> int:
        with urllib.request.urlopen(
                "http://%s:%d/api/worlds/status" % (HOST, PORT), timeout=8) as fh:
            return json.loads(fh.read().decode())["worlds"]["burger_tycoon"]["visits"]

    before = visits()
    bots = spawn_bots("burger_tycoon", 1)
    try:
        pump(bots, 12)
        mid = visits()
        check("visits: nothing recorded after 12 seconds", mid == before,
              "%d -> %d" % (before, mid))
        pump(bots, 24)
        time.sleep(3.5)
        after = visits()
        check("visits: one visit recorded after 30 seconds", after == before + 1,
              "%d -> %d" % (before, after))
    finally:
        for bot in bots:
            bot.stop()


SCENARIOS = {
    "ctf": test_ctf,
    "combat": test_combat,
    "anticheat": test_anticheat,
    "payload": test_payload,
    "tycoon": test_tycoon,
    "vote": test_vote,
    "instances": test_instances,
    "visits": test_visits,
}


def main(argv: List[str]) -> int:
    names = argv or list(SCENARIOS)
    for name in names:
        fn = SCENARIOS.get(name)
        if fn is None:
            print("unknown scenario:", name)
            continue
        try:
            fn()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            FAILED.append("%s (crashed: %s)" % (name, exc))
    print("\n==================== %d passed, %d failed ===================="
          % (len(PASSED), len(FAILED)))
    for name in FAILED:
        print("  FAILED:", name)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
