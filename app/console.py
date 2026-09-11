"""The live terminal read-out.

``run.sh`` (and ``main.py``) print a status block every few seconds instead of
a one-off banner, so the window the server runs in actually tells you what the
platform is doing: who is online, what the worlds are carrying, how much
traffic the web server has taken and what has just happened.

The block re-flows for the terminal it is printed into.  A wide window gets a
table; a narrow or tall one gets the same numbers stacked, which is what makes
it readable on a phone-shaped SSH window or a vertical monitor.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

BANNER = r"""
  ____  _     ___   ____ _  ___   _    ___     _______ _   _
 | __ )| |   / _ \ / ___| |/ / | | |  / \ \   / / ____| \ | |
 |  _ \| |  | | | | |   | ' /| |_| | / _ \ \ / /|  _| |  \| |
 | |_) | |__| |_| | |___| . \|  _  |/ ___ \ V / | |___| |\  |
 |____/|_____\___/ \____|_|\_\_| |_/_/   \_\_/  |_____|_| \_|
"""

# Colour is opt-in: only when the stream is a terminal and NO_COLOR is unset.
_COLOR = (sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
          and os.environ.get("TERM", "") not in ("", "dumb"))


def _c(code: str, text: str) -> str:
    return "\033[%sm%s\033[0m" % (code, text) if _COLOR else text


def bold(t: str) -> str: return _c("1", t)
def dim(t: str) -> str: return _c("2", t)
def cyan(t: str) -> str: return _c("36", t)
def green(t: str) -> str: return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def red(t: str) -> str: return _c("31", t)


def term_size() -> Tuple[int, int]:
    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return max(38, size.columns), max(10, size.lines)
    except Exception:
        return 80, 24


def human_bytes(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "%.0f %s" % (value, unit) if unit == "B" else "%.1f %s" % (value, unit)
        value /= 1024.0
    return "%.1f GB" % value


def human_time(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % (seconds // 60, seconds % 60)
    if seconds < 86400:
        return "%dh %02dm" % (seconds // 3600, (seconds % 3600) // 60)
    return "%dd %02dh" % (seconds // 86400, (seconds % 86400) // 3600)


def rule(width: int, char: str = "-") -> str:
    return dim(char * width)


def bar(value: float, total: float, width: int) -> str:
    """A small ASCII meter -- clamped so it never wraps the line."""
    width = max(4, width)
    if total <= 0:
        filled = 0
    else:
        filled = int(round(min(1.0, value / total) * width))
    return "[" + "#" * filled + "." * (width - filled) + "]"


# The running dashboard, so any module can drop a line into the read-out
# without threading a reference through the whole application.
_active: Optional["Dashboard"] = None


def attach(dashboard: "Dashboard") -> None:
    global _active
    _active = dashboard


def note(text: str) -> None:
    """Record an event for the next status block (a no-op with no console)."""
    board = _active
    if board is not None:
        board.note(text)


class Dashboard:
    """Collects the numbers and renders the periodic status block."""

    def __init__(self, application: Any, port: int, address: str,
                 supervisor: Any = None, interval: float = 10.0):
        self.app = application
        self.port = port
        self.address = address
        self.supervisor = supervisor
        self.interval = max(2.0, float(interval))
        self.started = time.time()
        self.last_requests = 0
        self.last_sample = time.time()
        self.events: List[str] = []
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        attach(self)
        self._thread = threading.Thread(target=self._loop, name="console",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # first block a beat after boot so the game hosts have reported in
        if self._stop.wait(3.0):
            return
        while not self._stop.is_set():
            try:
                self.render()
            except Exception as exc:            # never let the read-out kill the server
                print("[console] %s" % exc, flush=True)
            if self._stop.wait(self.interval):
                return

    # ---------------------------------------------------------------- events
    def note(self, text: str) -> None:
        """Record a one-line event for the next status block."""
        stamp = time.strftime("%H:%M:%S")
        with self._lock:
            self.events.append("%s %s" % (stamp, text))
            del self.events[:-40]

    def _drain_events(self, limit: int) -> List[str]:
        with self._lock:
            rows = self.events[-limit:]
            return list(rows)

    # ----------------------------------------------------------------- data
    def snapshot(self) -> Dict[str, Any]:
        from . import config
        from .game import registry as game_registry
        from .models import worlds as world_registry
        from .social import feed

        now = time.time()
        requests = getattr(self.app, "request_count", 0)
        sockets = getattr(self.app, "ws_count", 0)
        elapsed = max(0.001, now - self.last_sample)
        rate = (requests - self.last_requests) / elapsed
        self.last_requests = requests
        self.last_sample = now

        try:
            stats = feed.stats_snapshot()
        except Exception:
            stats = {"users": 0, "visits": 0, "items_owned": 0, "unusuals": 0,
                     "posts": 0, "messages": 0, "friendships": 0}
        try:
            from .models import users
            online = len(users.online_users(500))
        except Exception:
            online = 0

        world_rows = []
        try:
            for world in world_registry.all_worlds():
                status = game_registry.world_status(world["id"])
                world_rows.append({
                    "id": world["id"],
                    "name": world["name"],
                    "players": status["players"],
                    "instances": status["instances"],
                    "capacity": world["max_players"],
                    "online": status["online"],
                    "tick_ms": status.get("tick_ms", 0),
                })
        except Exception:
            pass

        hosts = []
        if self.supervisor is not None:
            try:
                hosts = self.supervisor.status()
            except Exception:
                hosts = []

        db_bytes = 0
        try:
            for suffix in ("", "-wal", "-shm"):
                path = str(config.DB_PATH) + suffix
                if os.path.exists(path):
                    db_bytes += os.path.getsize(path)
        except Exception:
            pass

        return {
            "uptime": now - self.started,
            "requests": requests,
            "rate": rate,
            "sockets": sockets,
            "threads": threading.active_count(),
            "accounts": stats.get("users", 0),
            "online": online,
            "visits": stats.get("visits", 0),
            "items": stats.get("items_owned", 0),
            "unusuals": stats.get("unusuals", 0),
            "messages": stats.get("messages", 0),
            "worlds": world_rows,
            "hosts": hosts,
            "db_bytes": db_bytes,
            "in_game": sum(w["players"] for w in world_rows),
        }

    # -------------------------------------------------------------- rendering
    def render(self) -> None:
        sys.stdout.write(self.block())
        sys.stdout.flush()

    def block(self) -> str:
        width, height = term_size()
        data = self.snapshot()
        # A narrow window (a phone-shaped SSH session, a vertical monitor,
        # a split pane) gets the stacked layout instead of the table.
        narrow = width < 72
        lines: List[str] = [""]
        lines.append(rule(width, "="))
        title = " BLOCKHAVEN  %s  " % time.strftime("%H:%M:%S")
        lines.append(bold(cyan(title)) + dim("up " + human_time(data["uptime"])))
        lines.append(rule(width, "="))

        lines.extend(self._section_traffic(data, width, narrow))
        lines.extend(self._section_worlds(data, width, narrow))
        lines.extend(self._section_hosts(data, width, narrow))

        # Events fill whatever room is left, so a short window drops them
        # rather than scrolling the numbers off the top.
        used = len(lines) + 3
        room = max(0, height - used)
        if room >= 2:
            events = self._drain_events(min(room - 1, 6))
            if events:
                lines.append("")
                lines.append(bold("Recent"))
                for row in events:
                    lines.append("  " + dim(row[:width - 2]))
        lines.append(rule(width))
        lines.append(dim("  http://%s:%d/   Ctrl+C to stop" % (self.address, self.port)))
        lines.append("")
        return "\n".join(lines) + "\n"

    def _section_traffic(self, data: Dict[str, Any], width: int,
                         narrow: bool) -> List[str]:
        pairs = [
            ("requests", "%s  (%.1f/s)" % (f"{data['requests']:,}", data["rate"])),
            ("sockets", str(data["sockets"])),
            ("threads", str(data["threads"])),
            ("accounts", f"{data['accounts']:,}"),
            ("online", "%d on the site, %d in game" % (data["online"], data["in_game"])),
            ("items", "%s owned, %s Unusual" % (f"{data['items']:,}",
                                                f"{data['unusuals']:,}")),
            ("visits", f"{data['visits']:,}"),
            ("database", human_bytes(data["db_bytes"])),
        ]
        lines = [bold("Server")]
        if narrow:
            for key, value in pairs:
                lines.append("  %-10s %s" % (key, value))
        else:
            half = (len(pairs) + 1) // 2
            column = max(28, (width - 4) // 2)
            for index in range(half):
                left = pairs[index]
                cell = "%-9s %s" % (left[0], left[1])
                row = "  " + cell.ljust(column)
                if index + half < len(pairs):
                    right = pairs[index + half]
                    row += "%-9s %s" % (right[0], right[1])
                lines.append(row[:width])
        return lines

    def _section_worlds(self, data: Dict[str, Any], width: int,
                        narrow: bool) -> List[str]:
        rows = data["worlds"]
        if not rows:
            return []
        lines = ["", bold("Worlds")]
        if narrow:
            for row in rows:
                flag = green("up") if row["online"] else red("down")
                lines.append("  %s  %s" % (row["name"][:width - 8], flag))
                lines.append("    %s %d/%d players, %d instance%s, %d ms tick"
                             % (bar(row["players"], max(1, row["capacity"]), 10),
                                row["players"], row["capacity"], row["instances"],
                                "" if row["instances"] == 1 else "s",
                                row["tick_ms"]))
        else:
            name_w = max(14, min(22, width - 48))
            meter_w = max(5, min(12, width - name_w - 42))
            # the meter plus " nn/nn" is what sets the players column width
            players_w = meter_w + 8
            head = "  %-*s %-*s %-9s %-7s %s" % (name_w, "world", players_w,
                                                 "players", "instances",
                                                 "tick", "state")
            lines.append(dim(head[:width]))
            for row in rows:
                meter = bar(row["players"], max(1, row["capacity"]), meter_w)
                state = green("running") if row["online"] else red("offline")
                players = "%s %d/%d" % (meter, row["players"], row["capacity"])
                lines.append("  %-*s %-*s %-9s %-7s %s"
                             % (name_w, row["name"][:name_w],
                                players_w, players,
                                str(row["instances"]),
                                "%dms" % row["tick_ms"], state))
        return lines

    def _section_hosts(self, data: Dict[str, Any], width: int,
                       narrow: bool) -> List[str]:
        hosts = data["hosts"]
        if not hosts:
            return []
        alive = sum(1 for h in hosts if h.get("alive"))
        restarts = sum(int(h.get("restarts", 0)) for h in hosts)
        summary = "%d/%d host processes alive" % (alive, len(hosts))
        if restarts:
            summary += ", %d restart%s" % (restarts, "" if restarts == 1 else "s")
        lines = ["", bold("Hosts"), "  " + (green(summary) if alive == len(hosts)
                                            else yellow(summary))]
        if not narrow:
            for host in hosts:
                lines.append("    %-18s pid %-7s port %-6s up %s"
                             % (str(host.get("world", ""))[:18],
                                host.get("pid", "-"), host.get("port", "-"),
                                human_time(host.get("uptime", 0))))
        return lines

    # ------------------------------------------------------------- start-up
    def intro(self, world_rows: List[Dict[str, Any]], admin: Tuple[str, str],
              games: bool) -> str:
        from . import config
        width, _ = term_size()
        lines = [BANNER if width >= 64 else bold("  BLOCKHAVEN")]
        lines.append("  %s  --  %s" % (bold(config.SITE_NAME), config.SITE_TAGLINE))
        lines.append(rule(width))
        lines.append("  Website     " + cyan("http://%s:%d/" % (self.address, self.port)))
        lines.append("  Local       " + cyan("http://127.0.0.1:%d/" % self.port))
        lines.append("  Admin       http://%s:%d/admin-dashboard  (%s / %s)"
                     % (self.address, self.port, admin[0], admin[1]))
        if games:
            for world in world_rows:
                lines.append("  World       http://%s:%-5d /%-16s %s"
                             % (self.address, self.port, world["id"], world["name"]))
        else:
            lines.append("  " + yellow("Game hosts disabled (--no-games)"))
        lines.append(rule(width))
        lines.append("  Status refreshes every %ds. Ctrl+C to stop."
                     % int(self.interval))
        lines.append("")
        return "\n".join(lines)
