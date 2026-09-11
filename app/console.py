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
        # The first sample has nothing to compare against, so its "rate" is
        # the whole count divided by a fraction of a second.  Suppress it.
        self.sampled = False
        self.events: List[str] = []
        # how many lines the last block took, so the next one can walk the
        # cursor back over it instead of scrolling
        self._last_height = 0
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
        rate = (requests - self.last_requests) / elapsed if self.sampled else 0.0
        self.last_requests = requests
        self.last_sample = now
        self.sampled = True

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
        """Draw the block, in place when we are attached to a terminal.

        Printing a fresh block every few seconds turns a long session into
        thousands of screens of scrollback and makes the numbers hard to
        follow -- your eye has to find the new copy each time.  On a terminal
        the cursor is walked back over the previous block and the area
        cleared, so the read-out updates where it stands, the way top does,
        and everything printed before it (the banner, the host start-up
        lines) stays put above.  Piped to a file there is no cursor to move,
        so it falls back to appending.
        """
        text = self.block()
        out = sys.stdout
        if _COLOR and self._last_height:
            # up N lines, then erase from the cursor to the end of the screen
            out.write("\033[%dA\033[J" % self._last_height)
        self._last_height = text.count("\n")
        out.write(text)
        out.flush()

    def block(self) -> str:
        width, height = term_size()
        data = self.snapshot()
        # Everything is sized to fit a portrait terminal, so the wide layout
        # is the exception rather than the default: two columns of figures
        # only when there is genuinely room for them.
        inner = min(width, 78)
        narrow = inner < 62
        lines: List[str] = []
        lines.append(rule(inner, "="))
        head = " BLOCKHAVEN " + time.strftime("%H:%M:%S")
        tail = "up " + human_time(data["uptime"]) + " "
        pad = max(1, inner - len(head) - len(tail))
        lines.append(bold(cyan(head)) + " " * pad + dim(tail))
        lines.extend(self._section_traffic(data, inner, narrow))
        lines.extend(self._section_worlds(data, inner, narrow))
        lines.extend(self._section_hosts(data, inner, narrow))

        # Events take whatever room is left over.  The block has a hard
        # ceiling of the window height so the in-place redraw above can
        # always walk back over it.
        fixed = len(lines) + 3
        room = max(0, min(4, height - fixed - 2))
        if room:
            events = self._drain_events(room)
            if events:
                lines.append(rule(inner))
                for row in events:
                    lines.append(" " + dim(row[:inner - 1]))
        lines.append(rule(inner, "="))
        lines.append(dim(" http://%s:%d/  \u00b7  Ctrl+C to stop"
                         % (self.address, self.port)))
        # never taller than the window, or the cursor walk-back overshoots
        if len(lines) > height - 1:
            lines = lines[:height - 1]
        return "\n".join(lines) + "\n"

    def _grid(self, pairs: List[Tuple[str, str]], width: int,
              narrow: bool) -> List[str]:
        """Key/value figures, two columns wide and one column narrow."""
        if narrow:
            return [" %-7s %s" % (key, value[:width - 10]) for key, value in pairs]
        column = (width - 2) // 2
        lines = []
        half = (len(pairs) + 1) // 2
        for index in range(half):
            key, value = pairs[index]
            cell = ("%-7s %s" % (key, value))[:column - 1]
            row = " " + cell.ljust(column - 1) + " "
            if index + half < len(pairs):
                key, value = pairs[index + half]
                row += ("%-7s %s" % (key, value))[:column - 1]
            lines.append(row.rstrip()[:width])
        return lines

    def _section_traffic(self, data: Dict[str, Any], width: int,
                         narrow: bool) -> List[str]:
        # Short keys, compact values: this block is read at a glance, not
        # studied, and every character spent on a label is one not spent on
        # a number.
        pairs = [
            ("req", "%s %s" % (f"{data['requests']:,}",
                               dim("%.1f/s" % data["rate"]))),
            ("ws", str(data["sockets"])),
            ("thr", str(data["threads"])),
            ("db", human_bytes(data["db_bytes"])),
            ("accts", f"{data['accounts']:,}"),
            ("online", "%d site %s %d game"
             % (data["online"], dim("\u00b7"), data["in_game"])),
            ("items", "%s %s %s unu" % (f"{data['items']:,}", dim("\u00b7"),
                                        f"{data['unusuals']:,}")),
            ("visits", f"{data['visits']:,}"),
        ]
        return [rule(width)] + self._grid(pairs, width, narrow)

    def _section_worlds(self, data: Dict[str, Any], width: int,
                        narrow: bool) -> List[str]:
        rows = data["worlds"]
        if not rows:
            return []
        lines = [rule(width)]
        # One line per world whatever the width: the name, a meter, the count
        # and the tick.  A header row costs a line and says nothing the
        # columns do not.
        meter_w = 10 if width >= 58 else 6
        # capped, so a wide window puts the meters near the names instead of
        # stranding them on the far side of the screen
        name_w = max(10, min(22, width - meter_w - 24))
        for row in rows:
            meter = bar(row["players"], max(1, row["capacity"]), meter_w)
            state = green("up") if row["online"] else red("DOWN")
            line = " %-*s %s %s %s" % (
                name_w, row["name"][:name_w], meter,
                "%2d/%-2d" % (row["players"], row["capacity"]),
                dim("%di %dms" % (row["instances"], row["tick_ms"])))
            # the state flag is appended last so the colour codes do not
            # throw the column padding out
            lines.append(line + " " + state)
        return lines

    def _section_hosts(self, data: Dict[str, Any], width: int,
                       narrow: bool) -> List[str]:
        hosts = data["hosts"]
        if not hosts:
            return []
        alive = sum(1 for h in hosts if h.get("alive"))
        restarts = sum(int(h.get("restarts", 0)) for h in hosts)
        summary = "hosts %d/%d alive" % (alive, len(hosts))
        if restarts:
            summary += ", %d restart%s" % (restarts, "" if restarts == 1 else "s")
        pids = " ".join(str(h.get("pid", "-")) for h in hosts)
        if width - len(summary) - 8 > len(pids):
            summary += "  " + dim("pid " + pids)
        return [rule(width),
                " " + (green(summary) if alive == len(hosts) else yellow(summary))]

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
