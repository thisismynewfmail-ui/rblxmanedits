#!/usr/bin/env python3
"""BLOCKHAVEN -- a block-world game platform.

Starts the website (profiles, avatar editor, market, world browser) on
port 8972 and supervises one game-host process per world.  Every game world is
served from a sub-page of that same port, e.g. http://<your-ip>:8972/burger_tycoon

Usage::

    python3 main.py                # normal start
    python3 main.py --port 9000    # different port
    python3 main.py --no-games     # website only (no game hosts)
    python3 main.py --reset        # wipe the database and re-seed
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from app import config  # noqa: E402


def local_ip() -> str:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0.4)
        probe.connect(("10.255.255.255", 1))
        address = probe.getsockname()[0]
        probe.close()
        return address
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the BLOCKHAVEN platform")
    parser.add_argument("--port", type=int, default=config.HTTP_PORT)
    parser.add_argument("--host", default=config.HTTP_HOST)
    parser.add_argument("--no-games", action="store_true",
                        help="serve the website without starting game hosts")
    parser.add_argument("--reset", action="store_true",
                        help="delete the database and start fresh")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--status-interval", type=float, default=10.0,
                        help="seconds between terminal status blocks "
                             "(0 turns the live read-out off)")
    args = parser.parse_args(argv)

    if args.debug:
        config.DEBUG = True
        os.environ["BLOCKHAVEN_DEBUG"] = "1"
    config.HTTP_PORT = args.port

    if args.reset and config.DB_PATH.exists():
        for suffix in ("", "-wal", "-shm"):
            path = str(config.DB_PATH) + suffix
            if os.path.exists(path):
                os.remove(path)
        print("[main] database reset")

    from app import bootstrap, webapp
    from app.http import server as http_server
    from app.views import admin as admin_views

    bootstrap.seed()

    supervisor = None
    if not args.no_games:
        from app.game.supervisor import Supervisor
        supervisor = Supervisor(args.port)
        supervisor.start()
        admin_views.set_supervisor(supervisor)

    application = webapp.create_app()
    try:
        server = http_server.serve(application, args.host, args.port)
    except OSError as exc:
        print("[main] could not bind %s:%d -- %s" % (args.host, args.port, exc))
        if supervisor:
            supervisor.stop()
        return 1

    address = local_ip()
    from app import console
    from app.models import worlds as world_registry

    dashboard = console.Dashboard(application, args.port, address,
                                  supervisor=supervisor,
                                  interval=max(2.0, args.status_interval or 10.0))
    print(dashboard.intro(world_registry.all_worlds(),
                          (config.ADMIN_USERNAME, config.ADMIN_PASSWORD),
                          not args.no_games), flush=True)
    dashboard.note("web server listening on port %d" % args.port)
    if supervisor is not None:
        dashboard.note("supervising %d game host%s"
                       % (len(world_registry.all_worlds()),
                          "" if len(world_registry.all_worlds()) == 1 else "s"))
    if args.status_interval and args.status_interval > 0:
        dashboard.start()

    stopping = threading.Event()

    def shutdown(signum=None, frame=None):
        if stopping.is_set():
            return
        stopping.set()
        dashboard.stop()
        print("\n[main] shutting down...", flush=True)
        threading.Thread(target=server.shutdown, daemon=True).start()
        if supervisor:
            supervisor.stop()

    signal.signal(signal.SIGINT, shutdown)
    try:
        signal.signal(signal.SIGTERM, shutdown)
    except (AttributeError, ValueError):
        pass

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        shutdown()
    finally:
        if not stopping.is_set():
            shutdown()
        server.server_close()
    print(console.dim("  served %s requests over %s"
                      % (f"{getattr(application, 'request_count', 0):,}",
                         console.human_time(time.time() - dashboard.started))))
    print("[main] bye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
