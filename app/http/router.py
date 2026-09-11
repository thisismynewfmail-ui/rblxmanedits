"""Request/Response objects and a tiny pattern based router."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote

from .templating import render as render_template

STATUS_TEXT = {
    200: "OK", 201: "Created", 204: "No Content", 302: "Found",
    303: "See Other", 304: "Not Modified", 400: "Bad Request",
    401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
    405: "Method Not Allowed", 409: "Conflict", 413: "Payload Too Large",
    429: "Too Many Requests", 500: "Internal Server Error",
    501: "Not Implemented", 503: "Service Unavailable",
}


class Request:
    __slots__ = ("method", "path", "raw_query", "query", "headers", "body",
                 "cookies", "remote_addr", "params", "user", "session",
                 "_form", "_json", "start_time", "host")

    def __init__(self, method: str, path: str, raw_query: str,
                 headers: Dict[str, str], body: bytes, remote_addr: str):
        self.method = method
        self.path = path
        self.raw_query = raw_query
        self.query = _flatten(parse_qs(raw_query, keep_blank_values=True))
        self.headers = headers
        self.body = body
        self.remote_addr = remote_addr
        self.cookies = _parse_cookies(headers.get("cookie", ""))
        self.params: Dict[str, str] = {}
        self.user: Optional[Dict[str, Any]] = None
        self.session: Optional[Dict[str, Any]] = None
        self._form: Optional[Dict[str, str]] = None
        self._json: Any = None
        self.start_time = time.time()
        self.host = headers.get("host", "")

    @property
    def form(self) -> Dict[str, str]:
        if self._form is None:
            ctype = self.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in ctype:
                self._form = _flatten(parse_qs(self.body.decode("utf-8", "replace"),
                                               keep_blank_values=True))
            else:
                self._form = {}
        return self._form

    @property
    def json(self) -> Any:
        if self._json is None:
            try:
                self._json = json.loads(self.body.decode("utf-8"))
            except Exception:
                self._json = {}
        return self._json

    def data(self) -> Dict[str, Any]:
        """Body params from either a urlencoded form or a JSON payload."""
        ctype = self.headers.get("content-type", "")
        if "application/json" in ctype:
            payload = self.json
            return payload if isinstance(payload, dict) else {}
        return dict(self.form)

    def get(self, key: str, default: Any = "") -> Any:
        d = self.data()
        if key in d:
            return d[key]
        return self.query.get(key, default)

    @property
    def wants_json(self) -> bool:
        return ("application/json" in self.headers.get("accept", "")
                or self.path.startswith("/api/")
                or self.headers.get("x-requested-with") == "fetch")

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None


class Response:
    __slots__ = ("status", "body", "headers", "cookies")

    def __init__(self, body: Any = b"", status: int = 200,
                 content_type: str = "text/html; charset=utf-8",
                 headers: Optional[Dict[str, str]] = None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body: bytes = body or b""
        self.status = status
        self.headers: Dict[str, str] = {"Content-Type": content_type}
        if headers:
            self.headers.update(headers)
        self.cookies: List[str] = []

    def set_cookie(self, name: str, value: str, max_age: Optional[int] = None,
                   http_only: bool = True, same_site: str = "Lax",
                   path: str = "/") -> "Response":
        parts = ["%s=%s" % (name, value), "Path=%s" % path,
                 "SameSite=%s" % same_site]
        if max_age is not None:
            parts.append("Max-Age=%d" % max_age)
        if http_only:
            parts.append("HttpOnly")
        self.cookies.append("; ".join(parts))
        return self

    def delete_cookie(self, name: str, path: str = "/") -> "Response":
        self.cookies.append("%s=; Path=%s; Max-Age=0; HttpOnly; SameSite=Lax"
                            % (name, path))
        return self

    def no_cache(self) -> "Response":
        self.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        self.headers["Pragma"] = "no-cache"
        return self


def html(body: str, status: int = 200) -> Response:
    return Response(body, status)


def template(path: str, status: int = 200, /, **ctx: Any) -> Response:
    """Positional-only so a context key named "path" or "status" is fine."""
    return Response(render_template(path, **ctx), status)


def json_response(payload: Any, status: int = 200) -> Response:
    body = json.dumps(payload, separators=(",", ":"), default=_json_default)
    return Response(body, status, "application/json; charset=utf-8").no_cache()


def text(body: str, status: int = 200) -> Response:
    return Response(body, status, "text/plain; charset=utf-8")


def redirect(location: str, status: int = 303) -> Response:
    return Response(b"", status, headers={"Location": location})


def error(status: int, message: str = "") -> Response:
    from .templating import render as _r
    try:
        body = _r("error.html", status=status,
                  status_text=STATUS_TEXT.get(status, "Error"),
                  message=message)
    except Exception:
        body = "<h1>%d %s</h1><p>%s</p>" % (status, STATUS_TEXT.get(status, ""),
                                            message)
    return Response(body, status)


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "keys"):
        return dict(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _flatten(multi: Dict[str, List[str]]) -> Dict[str, str]:
    return {k: (v[-1] if v else "") for k, v in multi.items()}


def _parse_cookies(header: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for chunk in header.split(";"):
        if "=" in chunk:
            k, _, v = chunk.partition("=")
            out[k.strip()] = unquote(v.strip())
    return out


PARAM_RE = re.compile(r"<([a-zA-Z_][a-zA-Z0-9_]*)(?::(int|path|str))?>")


class Route:
    __slots__ = ("methods", "regex", "handler", "name", "raw")

    def __init__(self, pattern: str, handler: Callable, methods: Tuple[str, ...],
                 name: str):
        self.raw = pattern
        self.handler = handler
        self.methods = methods
        self.name = name
        self.regex = re.compile("^" + PARAM_RE.sub(self._sub, pattern) + "$")

    @staticmethod
    def _sub(m: "re.Match") -> str:
        kind = m.group(2) or "str"
        pat = {"int": r"\d+", "path": r".+", "str": r"[^/]+"}[kind]
        return "(?P<%s>%s)" % (m.group(1), pat)


class Router:
    def __init__(self) -> None:
        self.routes: List[Route] = []

    def add(self, pattern: str, handler: Callable,
            methods: Tuple[str, ...] = ("GET",), name: str = "") -> None:
        self.routes.append(Route(pattern, handler, methods, name or pattern))

    def route(self, pattern: str, methods: Tuple[str, ...] = ("GET",),
              name: str = "") -> Callable:
        def deco(fn: Callable) -> Callable:
            self.add(pattern, fn, methods, name or fn.__name__)
            return fn
        return deco

    def get(self, pattern: str, **kw: Any) -> Callable:
        return self.route(pattern, ("GET",), **kw)

    def post(self, pattern: str, **kw: Any) -> Callable:
        return self.route(pattern, ("POST",), **kw)

    def any(self, pattern: str, **kw: Any) -> Callable:
        return self.route(pattern, ("GET", "POST"), **kw)

    def match(self, method: str, path: str):
        allowed = set()
        for route in self.routes:
            m = route.regex.match(path)
            if not m:
                continue
            if method not in route.methods:
                allowed.update(route.methods)
                continue
            return route, m.groupdict()
        return (None, allowed) if allowed else (None, None)
