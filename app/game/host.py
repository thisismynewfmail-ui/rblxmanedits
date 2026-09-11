"""Game host process.

One host process per world.  It owns every running instance of that world,
runs the simulation, and speaks websocket to players whose connections the
main web server reverse proxies in.  Splitting the hosts into their own
processes keeps the simulation off the web server's GIL, so a busy match never
slows the website down.

Run directly::

    python3 -m app.game.host --world capture_the_flag --port 8991 --web-port 8972
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import socketserver
import sys
import threading
import time
import traceback
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

if __package__ in (None, ""):  # allow "python3 app/game/host.py"
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))

from app import config, security
from app.game import protocol
from app.game.instance import GameInstance, TICK_DT
from app.models import worlds as world_registry

WORLD_CLASSES = {}


def load_world_class(world_id: str):
    if world_id in WORLD_CLASSES:
        return WORLD_CLASSES[world_id]
    if world_id == "capture_the_flag":
        from app.game.worlds.capture_the_flag import CaptureTheFlag as cls
    elif world_id == "fortress_team_2":
        from app.game.worlds.fortress_team2 import FortressTeam2 as cls
    elif world_id == "burger_tycoon":
        from app.game.worlds.burger_tycoon import BurgerTycoon as cls
    else:
        raise SystemExit("unknown world %r" % world_id)
    WORLD_CLASSES[world_id] = cls
    return cls


class GameHost:
    def __init__(self, world_id: str, port: int, web_port: int):
        self.world_id = world_id
        self.world = world_registry.get(world_id)
        if self.world is None:
            raise SystemExit("no such world: %s" % world_id)
        self.port = port
        self.web_port = web_port
        self.cls = load_world_class(world_id)
        self.map = self.cls.build_map()
        self.instances: List[GameInstance] = []
        self.lock = threading.RLock()
        self.next_instance_id = 1
        self.started = time.time()
        self.tick_ms = 0.0
        self.reports: List[Dict[str, Any]] = []
        self.report_lock = threading.Lock()
        self.running = True
        self.connections = 0
        self.ensure_instance()

    # ------------------------------------------------------------ instances
    def ensure_instance(self) -> GameInstance:
        with self.lock:
            instance = self.cls(self, self.world, self.next_instance_id, self.map)
            self.next_instance_id += 1
            self.instances.append(instance)
            return instance

    def pick_instance(self, prefer: Optional[int] = None) -> GameInstance:
        with self.lock:
            if prefer:
                for instance in self.instances:
                    if instance.instance_id == prefer and not instance.is_full():
                        return instance
            for instance in self.instances:
                if not instance.is_full():
                    return instance
        return self.ensure_instance()

    def cull_instances(self) -> None:
        with self.lock:
            if len(self.instances) <= 1:
                return
            keep: List[GameInstance] = []
            for instance in self.instances:
                if instance.is_empty() and len(keep) + 1 < len(self.instances):
                    continue
                keep.append(instance)
            if len(keep) != len(self.instances):
                self.instances = keep or self.instances[:1]

    # ---------------------------------------------------------------- ticks
    def tick_loop(self) -> None:
        next_tick = time.monotonic()
        cull_at = time.monotonic() + 30.0
        while self.running:
            started = time.monotonic()
            with self.lock:
                instances = list(self.instances)
            for instance in instances:
                try:
                    instance.tick()
                except Exception:
                    traceback.print_exc()
            self.tick_ms = (time.monotonic() - started) * 1000.0
            if time.monotonic() > cull_at:
                cull_at = time.monotonic() + 30.0
                self.cull_instances()
            next_tick += TICK_DT
            delay = next_tick - time.monotonic()
            if delay < -0.25:
                next_tick = time.monotonic()
                delay = 0
            if delay > 0:
                time.sleep(delay)

    # -------------------------------------------------------------- reports
    def report_visit(self, instance: GameInstance, player) -> None:
        self.queue_report({"kind": "visit", "world": self.world_id,
                           "user_id": player.user_id,
                           "seconds": int(time.monotonic() - player.joined_at)})

    def report_player(self, instance: GameInstance, player,
                      final: bool = False) -> None:
        self.queue_report({
            "kind": "stats", "world": self.world_id,
            "user_id": player.user_id, "kills": player.kills,
            "deaths": player.deaths, "score": player.score,
            "playtime": int(player.playtime), "final": bool(final),
        })

    def report_round(self, instance: GameInstance, player, won: bool) -> None:
        self.queue_report({"kind": "round", "world": self.world_id,
                           "user_id": player.user_id, "won": bool(won)})

    def queue_report(self, payload: Dict[str, Any]) -> None:
        with self.report_lock:
            self.reports.append(payload)
            del self.reports[:-400]

    def heartbeat_loop(self) -> None:
        while self.running:
            time.sleep(2.5)
            try:
                self.send_heartbeat()
            except Exception:
                if config.DEBUG:
                    traceback.print_exc()

    def send_heartbeat(self) -> None:
        with self.lock:
            instances = [i.describe() for i in self.instances]
        with self.report_lock:
            reports = self.reports
            self.reports = []
        payload = {
            "world": self.world_id,
            "players": sum(i["count"] for i in instances),
            "instances": instances,
            "uptime": round(time.time() - self.started, 1),
            "tick_ms": round(self.tick_ms, 2),
            "pid": os.getpid(),
            "reports": reports,
        }
        body = json.dumps(payload).encode()
        signature = security.service_signature(body)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", self.web_port,
                                              timeout=6)
            conn.request("POST", "/internal/heartbeat", body, {
                "Content-Type": "application/json",
                "X-Service-Signature": signature,
            })
            response = conn.getresponse()
            response.read()
            conn.close()
        except Exception:
            with self.report_lock:
                # keep the reports so the next beat can retry them
                self.reports = reports + self.reports

    # ---------------------------------------------------------- connections
    def handle_socket(self, sock: socket.socket, address) -> None:
        rfile = sock.makefile("rb", 65536)
        try:
            method, target, headers = protocol.read_http_request(rfile)
        except Exception:
            sock.close()
            return
        if headers.get("upgrade", "").lower() != "websocket":
            try:
                sock.sendall(b"HTTP/1.1 400 Bad Request\r\n"
                             b"Content-Length: 0\r\n\r\n")
            finally:
                sock.close()
            return
        query = parse_qs(urlparse(target).query)
        ticket_raw = (query.get("ticket") or [""])[0]
        ticket = security.unsign(ticket_raw)
        if not ticket or ticket.get("world") != self.world_id:
            try:
                sock.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            finally:
                sock.close()
            return
        try:
            sock.sendall(protocol.handshake_response(headers))
        except Exception:
            sock.close()
            return
        sock.settimeout(None)
        ws = protocol.WebSocket(sock, rfile)
        prefer = None
        try:
            prefer = int((query.get("instance") or ["0"])[0]) or None
        except ValueError:
            prefer = None
        instance = self.pick_instance(prefer)
        player = instance.add_player(
            int(ticket.get("uid", 0)), str(ticket.get("name", "Player")),
            ticket.get("avatar") or {}, ws, bool(ticket.get("admin")))
        self.connections += 1
        try:
            while True:
                raw = ws.recv()
                if raw is None:
                    break
                if not raw:
                    continue
                try:
                    message = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if not isinstance(message, dict):
                    continue
                try:
                    instance.handle(player, message)
                except Exception:
                    if config.DEBUG:
                        traceback.print_exc()
        except Exception:
            if config.DEBUG:
                traceback.print_exc()
        finally:
            self.connections -= 1
            instance.remove_player(player.pid)
            ws.close()

    def serve(self) -> None:
        host = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self_inner):
                try:
                    self_inner.request.settimeout(20)
                    host.handle_socket(self_inner.request,
                                       self_inner.client_address)
                except Exception:
                    if config.DEBUG:
                        traceback.print_exc()

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True
            request_queue_size = 64

            def handle_error(self, request, client_address):
                if config.DEBUG:
                    traceback.print_exc()

        server = Server((config.INTERNAL_BIND, self.port), Handler)
        threading.Thread(target=self.tick_loop, daemon=True,
                         name="tick-%s" % self.world_id).start()
        threading.Thread(target=self.heartbeat_loop, daemon=True,
                         name="beat-%s" % self.world_id).start()
        print("[game:%s] host ready on %s:%d (pid %d)"
              % (self.world_id, config.INTERNAL_BIND, self.port, os.getpid()),
              flush=True)
        try:
            server.serve_forever(poll_interval=0.4)
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            server.shutdown()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="BLOCKHAVEN game host")
    parser.add_argument("--world", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--web-port", type=int, default=config.HTTP_PORT)
    args = parser.parse_args(argv)
    host = GameHost(args.world, args.port, args.web_port)
    host.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
