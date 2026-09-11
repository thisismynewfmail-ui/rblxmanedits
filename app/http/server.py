"""A threaded HTTP/1.1 server with websocket reverse-proxy support.

Written directly on top of ``socketserver`` (rather than ``http.server``) so we
keep full control of the socket when a connection is upgraded to a websocket:
game traffic is piped, byte for byte, into the matching game-host process while
the ordinary website keeps being served from the very same port.
"""
from __future__ import annotations

import gzip
import mimetypes
import os
import select
import socket
import socketserver
import sys
import threading
import time
import traceback
from typing import Callable, Dict, Optional, Tuple

from .. import config
from .router import Request, Response, STATUS_TEXT, error

MAX_HEADER_BYTES = 32 * 1024
MAX_BODY_BYTES = 2 * 1024 * 1024
KEEPALIVE_TIMEOUT = 45
SERVER_NAME = "BlockhavenHTTP/1.0"

GZIP_TYPES = ("text/", "application/javascript", "application/json",
              "image/svg+xml")

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")


class Application:
    """Holds the dispatch callable plus the websocket backend resolver."""

    def __init__(self, dispatch: Callable[[Request], Response],
                 ws_resolver: Optional[Callable[[str], Optional[Tuple[str, int]]]] = None,
                 static_root: Optional[str] = None):
        self.dispatch = dispatch
        self.ws_resolver = ws_resolver
        self.static_root = static_root or str(config.STATIC_DIR)
        self.started = time.time()
        self.request_count = 0
        self.ws_count = 0
        self._lock = threading.Lock()

    def bump(self, ws: bool = False) -> None:
        with self._lock:
            self.request_count += 1
            if ws:
                self.ws_count += 1


class ConnectionHandler(socketserver.StreamRequestHandler):
    rbufsize = 65536
    wbufsize = 0
    timeout = KEEPALIVE_TIMEOUT
    app: Application = None  # type: ignore[assignment]

    # ------------------------------------------------------------------ core
    def handle(self) -> None:
        try:
            self.connection.settimeout(KEEPALIVE_TIMEOUT)
            while True:
                if not self.handle_one():
                    break
        except (socket.timeout, TimeoutError):
            pass
        except (ConnectionResetError, BrokenPipeError):
            pass
        except OSError:
            pass
        except Exception:
            if config.DEBUG:
                traceback.print_exc()

    def handle_one(self) -> bool:
        line = self.rfile.readline(MAX_HEADER_BYTES + 1)
        if not line:
            return False
        try:
            request_line = line.decode("latin-1").rstrip("\r\n")
        except Exception:
            return False
        if not request_line:
            return True
        parts = request_line.split()
        if len(parts) != 3:
            self.send_simple(400, "Bad Request")
            return False
        method, target, version = parts
        headers: Dict[str, str] = {}
        total = len(line)
        while True:
            hline = self.rfile.readline(MAX_HEADER_BYTES + 1)
            if not hline:
                return False
            total += len(hline)
            if total > MAX_HEADER_BYTES:
                self.send_simple(431, "Headers too large")
                return False
            if hline in (b"\r\n", b"\n"):
                break
            try:
                raw = hline.decode("latin-1").rstrip("\r\n")
                name, _, value = raw.partition(":")
                key = name.strip().lower()
                if key:
                    if key in headers:
                        headers[key] += "," + value.strip()
                    else:
                        headers[key] = value.strip()
            except Exception:
                continue

        path, _, raw_query = target.partition("?")
        path = _normalise_path(path)

        # ------------------------------------------------ websocket upgrade
        if (headers.get("upgrade", "").lower() == "websocket"
                and self.app.ws_resolver is not None):
            backend = self.app.ws_resolver(path)
            if backend is None:
                self.send_simple(404, "No such realtime endpoint")
                return False
            self.app.bump(ws=True)
            self.proxy_websocket(backend, request_line, headers)
            return False

        body = b""
        length = headers.get("content-length")
        if length:
            try:
                n = int(length)
            except ValueError:
                self.send_simple(400, "Bad Content-Length")
                return False
            if n > MAX_BODY_BYTES:
                self.send_simple(413, "Payload too large")
                return False
            remaining = n
            chunks = []
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    return False
                chunks.append(chunk)
                remaining -= len(chunk)
            body = b"".join(chunks)

        keep_alive = version.upper() != "HTTP/1.0"
        if headers.get("connection", "").lower() == "close":
            keep_alive = False

        req = Request(method, path, raw_query, headers, body,
                      self.client_address[0])
        self.app.bump()
        try:
            resp = self.app.dispatch(req)
        except Exception:
            traceback.print_exc()
            resp = error(500, "Something went wrong on the server.")
        if resp is None:
            resp = error(500, "Handler returned nothing.")

        self.send_response(req, resp, keep_alive)
        return keep_alive

    # ---------------------------------------------------------------- output
    def send_response(self, req: Request, resp: Response, keep_alive: bool) -> None:
        body = resp.body
        headers = dict(resp.headers)
        ctype = headers.get("Content-Type", "")
        if (len(body) > 900 and any(ctype.startswith(t) for t in GZIP_TYPES)
                and "gzip" in req.headers.get("accept-encoding", "")):
            body = gzip.compress(body, 5)
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"
        headers["Content-Length"] = str(len(body))
        headers["Server"] = SERVER_NAME
        headers["Connection"] = "keep-alive" if keep_alive else "close"
        headers.setdefault("X-Content-Type-Options", "nosniff")
        out = ["HTTP/1.1 %d %s" % (resp.status,
                                   STATUS_TEXT.get(resp.status, "OK"))]
        for k, v in headers.items():
            out.append("%s: %s" % (k, v))
        for cookie in resp.cookies:
            out.append("Set-Cookie: %s" % cookie)
        head = ("\r\n".join(out) + "\r\n\r\n").encode("latin-1")
        try:
            self.wfile.write(head)
            if body and req.method != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_simple(self, status: int, message: str) -> None:
        body = message.encode()
        try:
            self.wfile.write(
                ("HTTP/1.1 %d %s\r\nContent-Type: text/plain\r\n"
                 "Content-Length: %d\r\nConnection: close\r\n\r\n"
                 % (status, STATUS_TEXT.get(status, "Error"), len(body))
                 ).encode("latin-1") + body)
        except OSError:
            pass

    # ------------------------------------------------------------- ws proxy
    def proxy_websocket(self, backend: Tuple[str, int], request_line: str,
                        headers: Dict[str, str]) -> None:
        """Pipe the upgrade handshake and every following byte to a game host."""
        try:
            upstream = socket.create_connection(backend, timeout=8)
        except OSError:
            self.send_simple(503, "Game server unavailable")
            return
        try:
            upstream.settimeout(None)
            self.connection.settimeout(None)
            rebuilt = [request_line]
            for key, value in headers.items():
                rebuilt.append("%s: %s" % (key, value))
            rebuilt.append("X-Real-IP: %s" % self.client_address[0])
            upstream.sendall(("\r\n".join(rebuilt) + "\r\n\r\n").encode("latin-1"))
            self._pump(upstream)
        finally:
            try:
                upstream.close()
            except OSError:
                pass

    def _pump(self, upstream: socket.socket) -> None:
        """Shuttle bytes both ways until either side hangs up.

        The client -> upstream direction reads through ``self.rfile`` with
        ``read1`` so anything the buffered reader already swallowed while
        parsing the request headers is forwarded rather than lost, and it never
        blocks waiting for data that has not arrived.
        """
        client = self.connection
        stop = threading.Event()

        def client_to_upstream():
            try:
                while not stop.is_set():
                    data = self.rfile.read1(65536)
                    if not data:
                        break
                    upstream.sendall(data)
            except (OSError, ValueError):
                pass
            finally:
                stop.set()
                try:
                    upstream.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        pump = threading.Thread(target=client_to_upstream, daemon=True,
                                name="ws-up")
        pump.start()
        try:
            while not stop.is_set():
                try:
                    data = upstream.recv(65536)
                except (ConnectionResetError, OSError):
                    break
                if not data:
                    break
                try:
                    client.sendall(data)
                except OSError:
                    break
        finally:
            stop.set()
            try:
                upstream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _normalise_path(path: str) -> str:
    from urllib.parse import unquote
    path = unquote(path)
    if not path.startswith("/"):
        path = "/" + path
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    return path


class ThreadedHTTPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def __init__(self, addr, handler_cls, app: Application):
        self.app = app
        handler_cls.app = app
        super().__init__(addr, handler_cls)

    def handle_error(self, request, client_address):  # noqa: D401
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError,
                            socket.timeout, TimeoutError)):
            return
        if config.DEBUG:
            traceback.print_exc()


def serve(app: Application, host: str, port: int) -> ThreadedHTTPServer:
    server = ThreadedHTTPServer((host, port), ConnectionHandler, app)
    return server


# ---------------------------------------------------------------- static files
_static_cache: Dict[str, Tuple[float, bytes, str]] = {}
_static_lock = threading.Lock()


def serve_static(root: str, rel_path: str, req: Request) -> Response:
    rel_path = rel_path.lstrip("/")
    if ".." in rel_path or rel_path.startswith("/"):
        return error(403, "Nope.")
    full = os.path.normpath(os.path.join(root, rel_path))
    if not full.startswith(os.path.normpath(root)):
        return error(403, "Nope.")
    try:
        stat = os.stat(full)
    except OSError:
        return error(404, "File not found: %s" % rel_path)
    if not os.path.isfile(full):
        return error(404, "Not a file")
    key = full
    with _static_lock:
        hit = _static_cache.get(key)
    if hit and hit[0] == stat.st_mtime:
        data, ctype = hit[1], hit[2]
    else:
        with open(full, "rb") as fh:
            data = fh.read()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",
                                                  "application/json",
                                                  "image/svg+xml"):
            ctype += "; charset=utf-8"
        with _static_lock:
            _static_cache[key] = (stat.st_mtime, data, ctype)
    etag = '"%x-%x"' % (int(stat.st_mtime), stat.st_size)
    if req.headers.get("if-none-match") == etag:
        return Response(b"", 304, ctype, {"ETag": etag})
    max_age = 0 if config.DEBUG else 3600
    return Response(data, 200, ctype, {
        "ETag": etag,
        "Cache-Control": "public, max-age=%d" % max_age,
    })
