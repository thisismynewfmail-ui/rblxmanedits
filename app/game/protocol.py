"""RFC 6455 websocket server implementation (stdlib only) + wire helpers."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
from typing import Any, Dict, Optional, Tuple

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_CONT = 0x0
OP_TEXT = 0x1
OP_BIN = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

MAX_FRAME = 1 << 20  # 1 MiB is far larger than any legitimate game message


class WebSocketError(Exception):
    pass


def accept_key(client_key: str) -> str:
    digest = hashlib.sha1((client_key + GUID).encode()).digest()
    return base64.b64encode(digest).decode()


def handshake_response(headers: Dict[str, str]) -> bytes:
    key = headers.get("sec-websocket-key", "")
    if not key:
        raise WebSocketError("missing Sec-WebSocket-Key")
    return ("HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: %s\r\n\r\n" % accept_key(key)).encode()


class WebSocket:
    """A blocking server-side websocket bound to an accepted socket."""

    def __init__(self, sock: socket.socket, rfile=None):
        self.sock = sock
        self.rfile = rfile or sock.makefile("rb", 65536)
        self._send_lock = threading.Lock()
        self.closed = False

    # ----------------------------------------------------------------- read
    def _read_exact(self, count: int) -> bytes:
        chunks = []
        remaining = count
        while remaining > 0:
            chunk = self.rfile.read(remaining)
            if not chunk:
                raise WebSocketError("connection closed")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def recv(self) -> Optional[str]:
        """Return the next text message, or None when the peer closed."""
        buffer = bytearray()
        opcode = None
        while True:
            try:
                header = self._read_exact(2)
            except (WebSocketError, OSError):
                return None
            first, second = header[0], header[1]
            fin = bool(first & 0x80)
            frame_op = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            try:
                if length == 126:
                    length = struct.unpack("!H", self._read_exact(2))[0]
                elif length == 127:
                    length = struct.unpack("!Q", self._read_exact(8))[0]
                if length > MAX_FRAME:
                    self.close(1009)
                    return None
                mask = self._read_exact(4) if masked else b""
                payload = self._read_exact(length) if length else b""
            except (WebSocketError, OSError):
                return None
            if masked and payload:
                payload = bytes(b ^ mask[i & 3] for i, b in enumerate(payload))

            if frame_op == OP_CLOSE:
                self.close(1000)
                return None
            if frame_op == OP_PING:
                self._send_frame(OP_PONG, payload)
                continue
            if frame_op == OP_PONG:
                continue
            if frame_op in (OP_TEXT, OP_BIN):
                opcode = frame_op
                buffer = bytearray(payload)
            elif frame_op == OP_CONT:
                buffer.extend(payload)
            else:
                self.close(1002)
                return None
            if fin:
                if opcode == OP_TEXT:
                    try:
                        return buffer.decode("utf-8")
                    except UnicodeDecodeError:
                        self.close(1007)
                        return None
                return ""
            if len(buffer) > MAX_FRAME:
                self.close(1009)
                return None

    # ---------------------------------------------------------------- write
    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self.closed:
            return
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", 0x80 | opcode, length)
        elif length < (1 << 16):
            header = struct.pack("!BBH", 0x80 | opcode, 126, length)
        else:
            header = struct.pack("!BBQ", 0x80 | opcode, 127, length)
        with self._send_lock:
            if self.closed:
                return
            try:
                self.sock.sendall(header + payload)
            except OSError:
                self.closed = True

    def send_text(self, text: str) -> None:
        self._send_frame(OP_TEXT, text.encode("utf-8"))

    def send_json(self, payload: Any) -> None:
        self.send_text(json.dumps(payload, separators=(",", ":")))

    def ping(self) -> None:
        self._send_frame(OP_PING, b"")

    def close(self, code: int = 1000) -> None:
        if self.closed:
            return
        try:
            self._send_frame(OP_CLOSE, struct.pack("!H", code))
        except Exception:
            pass
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def read_http_request(rfile) -> Tuple[str, str, Dict[str, str]]:
    """Parse the upgrade request the web server proxied to us."""
    line = rfile.readline(8192)
    if not line:
        raise WebSocketError("empty request")
    parts = line.decode("latin-1").strip().split()
    if len(parts) < 2:
        raise WebSocketError("bad request line")
    method, target = parts[0], parts[1]
    headers: Dict[str, str] = {}
    while True:
        header_line = rfile.readline(8192)
        if not header_line or header_line in (b"\r\n", b"\n"):
            break
        raw = header_line.decode("latin-1").rstrip("\r\n")
        name, _, value = raw.partition(":")
        if name:
            headers[name.strip().lower()] = value.strip()
    return method, target, headers


def json_message(kind: str, **fields: Any) -> str:
    fields["t"] = kind
    return json.dumps(fields, separators=(",", ":"))
