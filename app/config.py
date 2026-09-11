"""Global configuration for the BLOCKHAVEN platform.

Everything is intentionally dependency free -- the whole stack runs on the
Python standard library so the project can be dropped onto any machine with
Python 3.9+ and started with ``python3 main.py``.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"

DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "blockhaven.sqlite3"
SECRET_PATH = DATA_DIR / "secret.key"

SITE_NAME = "BLOCKHAVEN"
SITE_TAGLINE = "Build it. Play it. Live it."

# ---------------------------------------------------------------- networking
HTTP_PORT = int(os.environ.get("BLOCKHAVEN_PORT", "8972"))
HTTP_HOST = os.environ.get("BLOCKHAVEN_HOST", "0.0.0.0")

# Internal loopback range used by the game host subprocesses.  Nothing outside
# the machine ever talks to these -- the public facing HTTP server reverse
# proxies websocket upgrades into them.
GAME_HOST_PORT_BASE = int(os.environ.get("BLOCKHAVEN_GAME_PORT_BASE", "8990"))
INTERNAL_BIND = "127.0.0.1"

# ---------------------------------------------------------------- economy
STARTING_CREDITS = 2000
UNUSUAL_CHANCE = 0.005  # 0.5% on hat-slot cosmetics only
MAX_CREDITS = 1_000_000_000

# ---------------------------------------------------------------- accounts
ADMIN_USERNAME = "admin_system"
ADMIN_PASSWORD = "passman69"
DEMO_ADMIN_TEST_USERNAME = "admin_test"
DEMO_ADMIN_TEST_PASSWORD = "passman69"

PASSWORD_MIN = 4
PASSWORD_MAX = 128
USERNAME_MIN = 3
USERNAME_MAX = 20

SESSION_COOKIE = "bh_session"
SESSION_TTL = 60 * 60 * 24 * 30  # 30 days

PBKDF2_ROUNDS = 120_000

# ---------------------------------------------------------------- gameplay
VISIT_THRESHOLD_SECONDS = 30  # 30s of playtime == one recorded visit
TICK_RATE = 20                # server simulation / broadcast rate
SHUFFLE_VOTE_SECONDS = 30
SHUFFLE_VOTE_RATIO = 0.80
GAME_TICKET_TTL = 120         # seconds a signed join ticket stays valid

# ---------------------------------------------------------------- misc
DEBUG = os.environ.get("BLOCKHAVEN_DEBUG", "") not in ("", "0", "false")


def load_secret() -> bytes:
    """Persistent server secret used for HMAC signing (sessions, tickets)."""
    if SECRET_PATH.exists():
        raw = SECRET_PATH.read_bytes().strip()
        if len(raw) >= 32:
            return raw
    raw = secrets.token_bytes(48).hex().encode()
    SECRET_PATH.write_bytes(raw)
    try:
        os.chmod(SECRET_PATH, 0o600)
    except OSError:
        pass
    return raw


SECRET = load_secret()
