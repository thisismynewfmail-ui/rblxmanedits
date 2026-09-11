"""Wires the routers, session handling and static files into one dispatcher."""
from __future__ import annotations

import hmac
import time
from typing import Optional

from . import config, db, security
from .http import router as R
from .http.router import Request, Response
from .http.server import Application, serve_static
from .models import users

# importing the view modules registers their routes on the shared router
from .views import base as views_base
from .views import (admin, auth, avatar_view, home, internal, market_view,  # noqa: F401
                    profile, social_views, worlds_view)

router = views_base.router
worlds_view.register_world_routes()

SAFE_METHODS = ("GET", "HEAD")
CSRF_EXEMPT_PREFIXES = ("/internal/",)


def _load_session(req: Request) -> None:
    token = req.cookies.get(config.SESSION_COOKIE, "")
    session = users.get_session(token) if token else None
    if session is None:
        req.session = None
        req.user = None
        return
    user = users.get_by_id(int(session["user_id"]))
    if user is None or user["is_banned"]:
        users.end_session(token)
        req.session = None
        req.user = None
        return
    session["token"] = token
    req.session = session
    req.user = user
    last = int(user.get("last_seen") or 0)
    if time.time() - last > 45:
        users.touch(int(user["id"]))


def _csrf_ok(req: Request) -> bool:
    if req.method in SAFE_METHODS:
        return True
    if any(req.path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
        return True
    if req.session is None:
        # Unauthenticated POSTs (login / register) are protected by their own
        # rate limits; there is no session state to forge yet.
        return True
    expected = req.session["csrf"]
    supplied = (req.headers.get("x-csrf-token")
                or req.data().get("csrf")
                or req.query.get("csrf") or "")
    return bool(expected) and hmac.compare_digest(str(supplied),
                                                 str(expected))


def dispatch(req: Request) -> Response:
    if req.path.startswith("/static/"):
        return serve_static(str(config.STATIC_DIR), req.path[len("/static/"):],
                            req)
    if req.path == "/favicon.ico":
        return serve_static(str(config.STATIC_DIR), "img/favicon.svg", req)
    _load_session(req)
    if not _csrf_ok(req):
        if req.wants_json:
            return R.json_response(
                {"ok": False, "error": "Your session expired. Reload the page."},
                403)
        return R.error(403, "Security token mismatch -- reload and try again.")
    route, params = router.match(req.method, req.path)
    if route is None:
        if isinstance(params, set):
            return R.error(405, "That address does not accept %s." % req.method)
        return R.error(404, "There is nothing at %s." % req.path)
    req.params = params
    response = route.handler(req, **params)
    if isinstance(response, Response):
        if req.method not in SAFE_METHODS:
            response.no_cache()
        return response
    if isinstance(response, str):
        return R.html(response)
    return R.error(500, "Handler returned an unexpected value.")


def ws_backend(path: str):
    """Resolve /ws/game/<world_id> to the game host that owns that world."""
    from .game import registry as game_registry
    if not path.startswith("/ws/game/"):
        return None
    world_id = path[len("/ws/game/"):].strip("/")
    if not world_id:
        return None
    return game_registry.backend_for(world_id)


def create_app() -> Application:
    return Application(dispatch, ws_backend, str(config.STATIC_DIR))
