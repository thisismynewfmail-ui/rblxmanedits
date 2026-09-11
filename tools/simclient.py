#!/usr/bin/env python3
"""A scriptable headless game client.

Used to exercise (and load test) the game hosts without a browser:

    python3 tools/simclient.py --world capture_the_flag --user admin_system \
        --password passman69 --seconds 20 --bots 2

Each bot logs into the website exactly like a browser would, requests a signed
join ticket, opens the proxied websocket and then walks, shoots and chats.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import random
import socket
import struct
import sys
import threading
import time
from http.client import HTTPConnection
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)


class WSClient:
    """Minimal RFC 6455 client (masked frames, text only)."""

    def __init__(self, host: str, port: int, path: str):
        self.sock = socket.create_connection((host, port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            "GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n" % (path, host, port, key))
        self.sock.sendall(request.encode())
        self.rfile = self.sock.makefile("rb", 65536)
        line = self.rfile.readline()
        if b"101" not in line:
            raise RuntimeError("handshake failed: %r" % line)
        while True:
            header = self.rfile.readline()
            if header in (b"\r\n", b"\n", b""):
                break
        self.lock = threading.Lock()
        self.closed = False

    def send(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode()
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i & 3] for i, b in enumerate(data))
        length = len(data)
        if length < 126:
            header = struct.pack("!BB", 0x81, 0x80 | length)
        elif length < (1 << 16):
            header = struct.pack("!BBH", 0x81, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", 0x81, 0x80 | 127, length)
        with self.lock:
            if self.closed:
                return
            try:
                self.sock.sendall(header + mask + masked)
            except OSError:
                self.closed = True

    def _read(self, count: int) -> bytes:
        out = b""
        while len(out) < count:
            chunk = self.rfile.read(count - len(out))
            if not chunk:
                raise ConnectionError("closed")
            out += chunk
        return out

    def recv(self) -> Optional[Dict[str, Any]]:
        try:
            first, second = self._read(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            payload = self._read(length) if length else b""
            if opcode == 0x8:
                self.closed = True
                return None
            if opcode == 0x9:
                return {"t": "_ping"}
            if opcode != 0x1:
                return {"t": "_binary"}
            return json.loads(payload.decode("utf-8"))
        except Exception:
            self.closed = True
            return None

    def close(self) -> None:
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass


class Bot:
    def __init__(self, host: str, port: int, username: str, password: str,
                 world: str, name: Optional[str] = None, verbose: bool = False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.world = world
        self.label = name or username
        self.verbose = verbose
        self.cookie = ""
        self.csrf = ""
        self.ws: Optional[WSClient] = None
        self.state: Dict[str, Any] = {}
        self.messages: List[Dict[str, Any]] = []
        self.counts: Dict[str, int] = {}
        self.pos = [0.0, 10.0, 0.0]
        self.yaw = 0.0
        self.me: Dict[str, Any] = {}
        self.map: Dict[str, Any] = {}
        self.alive = True
        self.running = False
        self.tycoon: Dict[str, Any] = {}
        self.coins = 0

    # ------------------------------------------------------------ website
    def http(self, method: str, path: str, body: Optional[str] = None,
             json_body: bool = False) -> Any:
        conn = HTTPConnection(self.host, self.port, timeout=10)
        headers = {}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if body is not None:
            headers["Content-Type"] = ("application/json" if json_body
                                       else "application/x-www-form-urlencoded")
            if self.csrf:
                headers["X-CSRF-Token"] = self.csrf
        conn.request(method, path, body, headers)
        response = conn.getresponse()
        data = response.read()
        setcookie = response.getheader("Set-Cookie")
        if setcookie:
            self.cookie = setcookie.split(";")[0]
        conn.close()
        return response.status, data

    def login(self) -> None:
        status, _ = self.http("POST", "/login", urlencode(
            {"username": self.username, "password": self.password}))
        if status not in (200, 302, 303):
            raise RuntimeError("login failed (%s)" % status)
        status, body = self.http("GET", "/")
        text = body.decode("utf-8", "replace")
        marker = 'csrf: "'
        index = text.find(marker)
        if index >= 0:
            self.csrf = text[index + len(marker):text.find('"', index + len(marker))]

    def join(self) -> None:
        status, body = self.http("POST", "/api/game/join",
                                 json.dumps({"world_id": self.world}), True)
        payload = json.loads(body.decode())
        if not payload.get("ok"):
            raise RuntimeError("join failed: %s" % payload.get("error"))
        self.ws = WSClient(self.host, self.port, payload["ws"])

    # -------------------------------------------------------------- loop
    def listen(self) -> None:
        while self.running and self.ws and not self.ws.closed:
            message = self.ws.recv()
            if message is None:
                break
            kind = message.get("t", "?")
            self.counts[kind] = self.counts.get(kind, 0) + 1
            if kind in ("chat", "kill", "evt", "round_end", "vote", "notice",
                        "tycoon_build", "died", "sys"):
                self.messages.append(message)
                if self.verbose:
                    print("[%s] %s" % (self.label, json.dumps(message)[:160]))
            if kind == "welcome":
                self.me = message["you"]
                self.map = message["map"]
                self.state = message.get("state", {})
                self.pos = list(message["you"].get("pos", self.pos))
            elif kind == "spawn":
                self.pos = list(message["p"])
                self.yaw = message.get("yaw", 0)
                self.alive = True
            elif kind == "died":
                self.alive = False
            elif kind == "correct":
                self.pos = list(message["p"])
            elif kind == "state":
                self.state = message.get("s", {})
            elif kind == "tycoon_init":
                self.tycoon = {"plots": message.get("plots", []),
                               "your_plot": message.get("your_plot")}
                self.coins = message.get("coins", 0)
            elif kind == "tycoon_state":
                self.tycoon["plots"] = message.get("plots", [])
            elif kind == "coins":
                self.coins = message.get("c", self.coins)

    def start(self) -> None:
        self.login()
        self.join()
        self.running = True
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.thread.start()
        time.sleep(0.6)

    def send_input(self, grounded: bool = True) -> None:
        if not self.ws:
            return
        self.ws.send({"t": "in", "p": [round(v, 2) for v in self.pos],
                      "v": [0, 0, 0], "y": round(self.yaw, 3), "pi": 0,
                      "a": "walk", "g": 1 if grounded else 0})

    def walk_towards(self, target, dt: float, speed: float = 20.0) -> float:
        dx = target[0] - self.pos[0]
        dz = target[2] - self.pos[2]
        distance = (dx * dx + dz * dz) ** 0.5
        if distance < 0.4:
            return 0.0
        step = min(distance, speed * dt)
        self.pos[0] += dx / distance * step
        self.pos[2] += dz / distance * step
        if len(target) > 1:
            self.pos[1] = target[1]
        import math
        self.yaw = math.atan2(dx, dz)
        return distance

    def chat(self, text: str, team: bool = False) -> None:
        if self.ws:
            self.ws.send({"t": "chat", "m": text, "team": team})

    def fire_at(self, direction) -> None:
        if self.ws:
            self.ws.send({"t": "fire", "d": list(direction)})

    def act(self, kind: str, **fields) -> None:
        if self.ws:
            payload = {"t": "act", "k": kind}
            payload.update(fields)
            self.ws.send(payload)

    def stop(self) -> None:
        self.running = False
        if self.ws:
            self.ws.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8972)
    parser.add_argument("--world", default="capture_the_flag")
    parser.add_argument("--user", default="admin_system")
    parser.add_argument("--password", default="passman69")
    parser.add_argument("--bots", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    accounts = [(args.user, args.password)]
    extras = [("admin_test", "passman69"), ("builderman_x", "blockhaven"),
              ("RetroKid2007", "blockhaven"), ("BlockSmith", "blockhaven"),
              ("NoobSlayer99", "blockhaven"), ("PixelPatty", "blockhaven"),
              ("CartPusher", "blockhaven"), ("FlagRunner", "blockhaven"),
              ("GrillMaster", "blockhaven")]
    accounts.extend(extras)
    bots: List[Bot] = []
    for i in range(args.bots):
        user, password = accounts[i % len(accounts)]
        bot = Bot(args.host, args.port, user, password, args.world,
                  verbose=args.verbose)
        try:
            bot.start()
            bots.append(bot)
            print("joined:", user, "team", bot.me.get("team"))
        except Exception as exc:
            print("bot %s failed: %s" % (user, exc))
    if not bots:
        return 1

    start = time.time()
    tick = 0
    while time.time() - start < args.seconds:
        dt = 0.1
        for index, bot in enumerate(bots):
            bot.send_input()
            if tick % 30 == index % 30:
                bot.chat("bot %s reporting in" % bot.label)
        tick += 1
        time.sleep(dt)

    for bot in bots:
        print("--- %s ---" % bot.label)
        print("  message counts:", dict(sorted(bot.counts.items())))
        print("  state:", json.dumps(bot.state)[:220])
        bot.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
