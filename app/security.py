"""Password hashing, session tokens, CSRF, signed game tickets, sanitising."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata
from typing import Any, Dict, Optional

from . import config

# --------------------------------------------------------------- passwords


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                             config.PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        config.PBKDF2_ROUNDS, base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                 int(rounds))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# --------------------------------------------------------------- tokens


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sign(payload: Dict[str, Any], ttl: int) -> str:
    """Compact HMAC signed blob: base64(json).base64(sig)."""
    body = dict(payload)
    body["_exp"] = int(time.time()) + ttl
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    b = base64.urlsafe_b64encode(raw).rstrip(b"=")
    sig = hmac.new(config.SECRET, b, hashlib.sha256).digest()
    s = base64.urlsafe_b64encode(sig).rstrip(b"=")
    return (b + b"." + s).decode()


def unsign(token: str, secret: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
    secret = secret or config.SECRET
    try:
        b_str, s_str = token.split(".", 1)
        b = b_str.encode()
        pad = b"=" * (-len(b) % 4)
        expected = hmac.new(secret, b, hashlib.sha256).digest()
        got = base64.urlsafe_b64decode(s_str.encode() + b"=" * (-len(s_str) % 4))
        if not hmac.compare_digest(expected, got):
            return None
        data = json.loads(base64.urlsafe_b64decode(b + pad))
        if int(data.get("_exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


def service_signature(body: bytes) -> str:
    """Signature used for internal game-host -> web-server callbacks."""
    return hmac.new(config.SECRET, body, hashlib.sha256).hexdigest()


def check_service_signature(body: bytes, sig: str) -> bool:
    try:
        return hmac.compare_digest(service_signature(body), sig or "")
    except Exception:
        return False


# --------------------------------------------------------------- validation

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{%d,%d}$" % (config.USERNAME_MIN,
                                                     config.USERNAME_MAX))
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def valid_username(name: str) -> bool:
    return bool(name) and bool(USERNAME_RE.match(name))


def valid_color(value: str) -> bool:
    return bool(value) and bool(HEX_COLOR_RE.match(value))


CONTROL_CHARS = dict.fromkeys(
    c for c in range(0x20) if c not in (0x09, 0x0A))


def clean_text(value: Any, max_len: int = 500, allow_newlines: bool = True) -> str:
    """Normalise arbitrary user input into safe, storable plain text.

    HTML escaping happens at render time (templates auto-escape); this strips
    control characters, collapses abusive whitespace and enforces length.
    """
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = text.translate(CONTROL_CHARS)
    if not allow_newlines:
        text = text.replace("\n", " ")
    else:
        text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"[ \t]{6,}", "     ", text)
    return text.strip()[:max_len]


def escape_html(value: Any) -> str:
    s = "" if value is None else str(value)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))
