"""Spawns and babysits the per-world game host processes."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

from .. import config
from ..models import worlds as world_registry
from . import registry


def free_port(preferred: int) -> int:
    for candidate in range(preferred, preferred + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((config.INTERNAL_BIND, candidate))
                return candidate
            except OSError:
                continue
    raise RuntimeError("no free port near %d" % preferred)


class HostProcess:
    def __init__(self, world_id: str, port: int, web_port: int):
        self.world_id = world_id
        self.port = port
        self.web_port = web_port
        self.process: Optional[subprocess.Popen] = None
        self.restarts = 0
        self.started_at = 0.0

    def start(self) -> None:
        env = dict(os.environ)
        env.setdefault("PYTHONUNBUFFERED", "1")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "app.game.host",
             "--world", self.world_id,
             "--port", str(self.port),
             "--web-port", str(self.web_port)],
            cwd=str(config.BASE_DIR), env=env)
        self.started_at = time.time()
        registry.register_backend(self.world_id, config.INTERNAL_BIND, self.port)

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass


class Supervisor:
    def __init__(self, web_port: int):
        self.web_port = web_port
        self.hosts: Dict[str, HostProcess] = {}
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.running = True
        port = config.GAME_HOST_PORT_BASE
        for world in world_registry.all_worlds():
            chosen = free_port(port)
            port = chosen + 1
            host = HostProcess(world["id"], chosen, self.web_port)
            host.start()
            self.hosts[world["id"]] = host
            print("[supervisor] %-18s -> 127.0.0.1:%d" % (world["id"], chosen),
                  flush=True)
        self._thread = threading.Thread(target=self._watch, daemon=True,
                                        name="game-supervisor")
        self._thread.start()

    def _watch(self) -> None:
        while self.running:
            time.sleep(2.0)
            for world_id, host in list(self.hosts.items()):
                if self.running and not host.alive():
                    host.restarts += 1
                    print("[supervisor] %s exited -- restarting (#%d)"
                          % (world_id, host.restarts), flush=True)
                    time.sleep(1.0)
                    try:
                        host.port = free_port(host.port)
                        host.start()
                    except Exception as exc:
                        print("[supervisor] restart failed: %s" % exc,
                              flush=True)

    def status(self) -> List[Dict[str, object]]:
        rows = []
        for world_id, host in self.hosts.items():
            rows.append({
                "world": world_id,
                "port": host.port,
                "alive": host.alive(),
                "pid": host.process.pid if host.process else 0,
                "restarts": host.restarts,
                "uptime": round(time.time() - host.started_at, 1)
                if host.started_at else 0,
            })
        return rows

    def stop(self) -> None:
        self.running = False
        for host in self.hosts.values():
            host.stop()
