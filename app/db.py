"""SQLite persistence layer.

One connection per thread (WAL journalling) so the threaded HTTP server can
read and write concurrently without tripping over sqlite's threading rules.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

from . import config

_local = threading.local()
_write_lock = threading.RLock()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL,
    username_lower  TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL DEFAULT 0,
    last_login      INTEGER NOT NULL DEFAULT 0,
    blurb           TEXT NOT NULL DEFAULT '',
    location        TEXT NOT NULL DEFAULT '',
    credits         INTEGER NOT NULL DEFAULT 0,
    is_admin        INTEGER NOT NULL DEFAULT 0,
    is_banned       INTEGER NOT NULL DEFAULT 0,
    place_visits    INTEGER NOT NULL DEFAULT 0,
    forum_posts     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf        TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL,
    user_agent  TEXT NOT NULL DEFAULT '',
    ip          TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    slot        TEXT NOT NULL,
    price       INTEGER NOT NULL DEFAULT 0,
    rarity      TEXT NOT NULL DEFAULT 'common',
    description TEXT NOT NULL DEFAULT '',
    creator     TEXT NOT NULL DEFAULT 'BLOCKHAVEN',
    data        TEXT NOT NULL DEFAULT '{}',
    on_sale     INTEGER NOT NULL DEFAULT 1,
    is_default  INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL DEFAULT 0
);

-- every owned copy of an item is its own row so per-copy properties
-- (unusual effects, serials, trade history) have somewhere to live.
CREATE TABLE IF NOT EXISTS inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id     TEXT NOT NULL REFERENCES items(id),
    tier        TEXT NOT NULL DEFAULT 'normal',
    effect      TEXT NOT NULL DEFAULT '',
    serial      INTEGER NOT NULL DEFAULT 0,
    acquired_at INTEGER NOT NULL,
    source      TEXT NOT NULL DEFAULT 'market'
);
CREATE INDEX IF NOT EXISTS idx_inv_user ON inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_inv_item ON inventory(item_id);

CREATE TABLE IF NOT EXISTS avatars (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    colors      TEXT NOT NULL DEFAULT '{}',
    equipped    TEXT NOT NULL DEFAULT '{}',
    hotbar      TEXT NOT NULL DEFAULT '[]',
    updated_at  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta         INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    reason        TEXT NOT NULL,
    actor_id      INTEGER,
    created_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_user ON credit_ledger(user_id, id DESC);

CREATE TABLE IF NOT EXISTS friendships (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_low     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    requester_id INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL,
    UNIQUE(user_low, user_high)
);

CREATE TABLE IF NOT EXISTS follows (
    follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followee_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  INTEGER NOT NULL,
    PRIMARY KEY (follower_id, followee_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    likes      INTEGER NOT NULL DEFAULT 0,
    hidden     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(user_id, id DESC);

CREATE TABLE IF NOT EXISTS post_likes (
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, user_id)
);

CREATE TABLE IF NOT EXISTS post_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pcomments_post ON post_comments(post_id, id);

CREATE TABLE IF NOT EXISTS profile_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    author_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    hidden     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_profcomments ON profile_comments(profile_id, id DESC);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    read_at      INTEGER NOT NULL DEFAULT 0,
    del_sender   INTEGER NOT NULL DEFAULT 0,
    del_recipient INTEGER NOT NULL DEFAULT 0,
    reply_to     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_msg_recipient ON messages(recipient_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_msg_sender ON messages(sender_id, id DESC);

CREATE TABLE IF NOT EXISTS world_stats (
    world_id     TEXT PRIMARY KEY,
    visits       INTEGER NOT NULL DEFAULT 0,
    favourites   INTEGER NOT NULL DEFAULT 0,
    likes        INTEGER NOT NULL DEFAULT 0,
    dislikes     INTEGER NOT NULL DEFAULT 0,
    peak_players INTEGER NOT NULL DEFAULT 0,
    updated_at   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS world_votes (
    world_id TEXT NOT NULL,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote     INTEGER NOT NULL,
    PRIMARY KEY (world_id, user_id)
);

CREATE TABLE IF NOT EXISTS world_favourites (
    world_id TEXT NOT NULL,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (world_id, user_id)
);

CREATE TABLE IF NOT EXISTS world_visits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id   TEXT NOT NULL,
    user_id    INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    seconds    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_visits_world ON world_visits(world_id, id DESC);

CREATE TABLE IF NOT EXISTS game_stats (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    world_id   TEXT NOT NULL,
    kills      INTEGER NOT NULL DEFAULT 0,
    deaths     INTEGER NOT NULL DEFAULT 0,
    wins       INTEGER NOT NULL DEFAULT 0,
    rounds     INTEGER NOT NULL DEFAULT 0,
    playtime   INTEGER NOT NULL DEFAULT 0,
    score      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, world_id)
);

CREATE TABLE IF NOT EXISTS badges (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    icon        TEXT NOT NULL DEFAULT 'star',
    color       TEXT NOT NULL DEFAULT '#3a6ea5'
);

CREATE TABLE IF NOT EXISTS user_badges (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_id   TEXT NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
    awarded_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, badge_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id   INTEGER,
    action     TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    detail     TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit ON audit_log(id DESC);

CREATE TABLE IF NOT EXISTS rate_limits (
    bucket     TEXT PRIMARY KEY,
    count      INTEGER NOT NULL DEFAULT 0,
    window_end INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30.0,
                               isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=20000")
        _local.conn = conn
    return conn


def init_db() -> None:
    conn = connect()
    with _write_lock:
        conn.executescript(SCHEMA)


def query(sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
    return connect().execute(sql, tuple(params)).fetchall()


def query_one(sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    return connect().execute(sql, tuple(params)).fetchone()


def scalar(sql: str, params: Iterable[Any] = (), default: Any = 0) -> Any:
    row = query_one(sql, params)
    if row is None:
        return default
    val = row[0]
    return default if val is None else val


def execute(sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    with _write_lock:
        return connect().execute(sql, tuple(params))


def executemany(sql: str, seq: Iterable[Iterable[Any]]) -> None:
    with _write_lock:
        connect().executemany(sql, [tuple(p) for p in seq])


class transaction:
    """Context manager giving an exclusive write transaction."""

    def __enter__(self):
        _write_lock.acquire()
        self.conn = connect()
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.conn.execute("COMMIT")
            else:
                self.conn.execute("ROLLBACK")
        finally:
            _write_lock.release()
        return False


class AttrDict(dict):
    """Dict whose keys are also readable as attributes.

    Templates read ``user.username`` rather than ``user['username']``; every
    mapping that reaches a template goes through here.
    """

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[AttrDict]:
    return AttrDict(row) if row is not None else None


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[AttrDict]:
    return [AttrDict(r) for r in rows]


def get_meta(key: str, default: Optional[str] = None) -> Optional[str]:
    row = query_one("SELECT value FROM meta WHERE key=?", (key,))
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    execute("INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def audit(actor_id: Optional[int], action: str, target: str = "",
          detail: Any = "") -> None:
    if not isinstance(detail, str):
        detail = json.dumps(detail, separators=(",", ":"))[:2000]
    execute("INSERT INTO audit_log(actor_id,action,target,detail,created_at)"
            " VALUES(?,?,?,?,?)", (actor_id, action, target, detail,
                                   int(time.time())))


def rate_limit(bucket: str, limit: int, window: int) -> bool:
    """Return True when the action is allowed; False when throttled."""
    now = int(time.time())
    with _write_lock:
        conn = connect()
        row = conn.execute("SELECT count, window_end FROM rate_limits WHERE bucket=?",
                           (bucket,)).fetchone()
        if row is None or row["window_end"] <= now:
            conn.execute(
                "INSERT INTO rate_limits(bucket,count,window_end) VALUES(?,1,?)"
                " ON CONFLICT(bucket) DO UPDATE SET count=1, window_end=excluded.window_end",
                (bucket, now + window))
            return True
        if row["count"] >= limit:
            return False
        conn.execute("UPDATE rate_limits SET count=count+1 WHERE bucket=?", (bucket,))
        return True
