"""Shared view plumbing: the router, auth decorators and template context."""
from __future__ import annotations

import functools
import time
from typing import Any, Callable, Dict, Optional

from .. import config, security
from ..http import router as R
from ..http.router import Request, Response
from ..models import users
from ..social import friends, messages

router = R.Router()


def flash_redirect(location: str, message: str = "", kind: str = "ok") -> Response:
    if message:
        sep = "&" if "?" in location else "?"
        location = "%s%smsg=%s&kind=%s" % (
            location, sep, _quote(message), kind)
    return R.redirect(location)


def _quote(value: str) -> str:
    from urllib.parse import quote
    return quote(value, safe="")


def current_flash(req: Request) -> Optional[Dict[str, str]]:
    message = req.query.get("msg")
    if not message:
        return None
    return {"text": security.clean_text(message, 240, False),
            "kind": "bad" if req.query.get("kind") == "bad" else "ok"}


TICKER_CACHE = {"at": 0.0, "text": ""}


def site_ticker() -> str:
    """Rolling headline strip in the site header (refreshed once a minute)."""
    if time.time() - TICKER_CACHE["at"] < 60 and TICKER_CACHE["text"]:
        return TICKER_CACHE["text"]
    from ..game import registry as game_registry
    from ..models import inventory, worlds
    from ..social import feed
    bits = []
    stats = feed.stats_snapshot()
    bits.append("%d builders registered" % stats["users"])
    playing = game_registry.total_players()
    bits.append("%d player%s in game right now" % (playing, "" if playing == 1 else "s"))
    bits.append("%d place visits logged" % stats["visits"])
    for row in inventory.unusual_showcase(3):
        bits.append("%s unboxed an UNUSUAL %s (%s)"
                    % (row["username"], row["name"], row["effect_name"]))
    for world in worlds.all_worlds():
        status = game_registry.world_status(world["id"])
        if status["players"]:
            bits.append("%s: %d playing across %d instance%s"
                        % (world["name"], status["players"], status["instances"],
                           "" if status["instances"] == 1 else "s"))
    bits.append("New here? Grab 2,000 credits and go buy a hat.")
    text = "  \u2022  ".join(bits)
    TICKER_CACHE["at"] = time.time()
    TICKER_CACHE["text"] = text
    return text


def context(req: Request, **extra: Any) -> Dict[str, Any]:
    user = req.user
    ctx: Dict[str, Any] = {
        "page_title": "Home",
        "page_script": "",
        "search_term": req.query.get("q", ""),
        "ticker": site_ticker(),
        "user": user,
        "csrf": req.session["csrf"] if req.session else "",
        "flash": current_flash(req),
        "now": int(time.time()),
        "path": req.path,
        "nav_unread": messages.unread_count(user["id"]) if user else 0,
        "nav_requests": friends.pending_count(user["id"]) if user else 0,
        "nav_friends": friends.count_friends(user["id"]) if user else 0,
        "is_admin": bool(user and user["is_admin"]),
        "fmt_time": fmt_time,
        "fmt_date": fmt_date,
        "fmt_num": fmt_num,
        "ago": ago,
        "to_json": to_json,
    }
    ctx.update(extra)
    return ctx


def render(req: Request, template: str, status: int = 200, /,
           **extra: Any) -> Response:
    return R.template(template, status, **context(req, **extra))


def login_required(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(req: Request, *args, **kwargs):
        if req.user is None:
            if req.wants_json:
                return R.json_response({"ok": False, "error": "Sign in first."},
                                       401)
            return R.redirect("/login?next=%s" % _quote(req.path))
        return fn(req, *args, **kwargs)
    return wrapper


def admin_required(fn: Callable) -> Callable:
    """Non-admins are quietly dropped back to the home page."""
    @functools.wraps(fn)
    def wrapper(req: Request, *args, **kwargs):
        if req.user is None or not req.user["is_admin"]:
            if req.wants_json:
                return R.json_response({"ok": False, "error": "Not found."}, 404)
            return R.redirect("/")
        return fn(req, *args, **kwargs)
    return wrapper


def api_error(message: str, status: int = 400) -> Response:
    return R.json_response({"ok": False, "error": message}, status)


def api_ok(**payload: Any) -> Response:
    payload["ok"] = True
    return R.json_response(payload)


def to_json(value: Any) -> str:
    """JSON safe to embed either in an HTML attribute or inside <script>.

    The template escapes quotes for the attribute case; the replacements here
    stop a value from closing the script tag or breaking a JS string.
    """
    import json
    text = json.dumps(value, separators=(",", ":"), default=str)
    return (text.replace("<", "\\u003c").replace(">", "\\u003e")
                .replace("&", "\\u0026")
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


# ------------------------------------------------------------------ filters

def fmt_num(value: Any) -> str:
    try:
        return "{:,}".format(int(value))
    except (TypeError, ValueError):
        return str(value)


def fmt_date(timestamp: Any) -> str:
    try:
        return time.strftime("%d %b %Y", time.localtime(int(timestamp)))
    except (TypeError, ValueError, OSError):
        return "--"


def fmt_time(timestamp: Any) -> str:
    try:
        return time.strftime("%d %b %Y, %H:%M", time.localtime(int(timestamp)))
    except (TypeError, ValueError, OSError):
        return "--"


def ago(timestamp: Any) -> str:
    try:
        delta = int(time.time()) - int(timestamp)
    except (TypeError, ValueError):
        return "--"
    if delta < 0:
        delta = 0
    if delta < 60:
        return "%d seconds ago" % delta
    if delta < 3600:
        return "%d minute%s ago" % (delta // 60, "" if delta // 60 == 1 else "s")
    if delta < 86400:
        return "%d hour%s ago" % (delta // 3600, "" if delta // 3600 == 1 else "s")
    if delta < 86400 * 30:
        return "%d day%s ago" % (delta // 86400, "" if delta // 86400 == 1 else "s")
    return fmt_date(timestamp)
