"""Account creation, authentication, sessions and presence."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .. import config, db, security
from . import catalog


class AuthError(Exception):
    pass


def _now() -> int:
    return int(time.time())


def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    return db.row_to_dict(db.query_one("SELECT * FROM users WHERE id=?", (user_id,)))


def get_by_username(username: str) -> Optional[Dict[str, Any]]:
    if not username:
        return None
    return db.row_to_dict(db.query_one(
        "SELECT * FROM users WHERE username_lower=?", (username.strip().lower(),)))


def exists(username: str) -> bool:
    return get_by_username(username) is not None


def create_user(username: str, password: str, is_admin: bool = False,
                credits: Optional[int] = None,
                blurb: str = "") -> Dict[str, Any]:
    username = (username or "").strip()
    if not security.valid_username(username):
        raise AuthError(
            "Usernames must be %d-%d characters, letters, numbers and underscores only."
            % (config.USERNAME_MIN, config.USERNAME_MAX))
    if not (config.PASSWORD_MIN <= len(password or "") <= config.PASSWORD_MAX):
        raise AuthError("Passwords must be at least %d characters."
                        % config.PASSWORD_MIN)
    if exists(username):
        raise AuthError("That username is already taken.")

    now = _now()
    start_credits = config.STARTING_CREDITS if credits is None else int(credits)
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO users(username, username_lower, password_hash, created_at,"
            " last_seen, last_login, credits, is_admin, blurb)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (username, username.lower(), security.hash_password(password), now,
             now, now, start_credits, 1 if is_admin else 0,
             security.clean_text(blurb, 400)))
        user_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO credit_ledger(user_id, delta, balance_after, reason,"
            " actor_id, created_at) VALUES(?,?,?,?,?,?)",
            (user_id, start_credits, start_credits, "Welcome bonus", None, now))
        conn.execute(
            "INSERT INTO avatars(user_id, colors, equipped, hotbar, updated_at)"
            " VALUES(?,?,?,?,?)",
            (user_id, _json(catalog.DEFAULT_COLORS), _json({}), _json([]), now))
    # Starter kit is granted through the normal inventory path so every item a
    # player owns exists as a real inventory row.
    from . import inventory, avatars
    for item_id in catalog.STARTER_ITEMS:
        inventory.grant(user_id, item_id, source="starter", allow_unusual=False)
    avatars.apply_defaults(user_id)
    db.audit(user_id, "account.create", username)
    return get_by_id(user_id)  # type: ignore[return-value]


def _json(value: Any) -> str:
    import json
    return json.dumps(value, separators=(",", ":"))


def authenticate(username: str, password: str) -> Dict[str, Any]:
    user = get_by_username(username)
    if not user or not security.verify_password(password, user["password_hash"]):
        raise AuthError("Incorrect username or password.")
    if user["is_banned"]:
        raise AuthError("This account has been suspended.")
    db.execute("UPDATE users SET last_login=?, last_seen=? WHERE id=?",
               (_now(), _now(), user["id"]))
    return user


def change_password(user_id: int, old_password: str, new_password: str) -> None:
    user = get_by_id(user_id)
    if not user:
        raise AuthError("No such account.")
    if not security.verify_password(old_password, user["password_hash"]):
        raise AuthError("Your current password is not correct.")
    if not (config.PASSWORD_MIN <= len(new_password or "") <= config.PASSWORD_MAX):
        raise AuthError("New password is too short.")
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (security.hash_password(new_password), user_id))
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    db.audit(user_id, "account.password_change", user["username"])


# ------------------------------------------------------------------ sessions

def start_session(user_id: int, user_agent: str = "", ip: str = "") -> Dict[str, str]:
    token = security.new_token(32)
    csrf = security.new_token(24)
    now = _now()
    db.execute("INSERT INTO sessions(token,user_id,csrf,created_at,expires_at,"
               "user_agent,ip) VALUES(?,?,?,?,?,?,?)",
               (token, user_id, csrf, now, now + config.SESSION_TTL,
                (user_agent or "")[:200], (ip or "")[:64]))
    return {"token": token, "csrf": csrf}


def get_session(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    row = db.query_one(
        "SELECT s.token, s.user_id, s.csrf, s.expires_at FROM sessions s"
        " WHERE s.token=?", (token,))
    if not row:
        return None
    if row["expires_at"] < _now():
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
        return None
    return dict(row)


def end_session(token: str) -> None:
    if token:
        db.execute("DELETE FROM sessions WHERE token=?", (token,))


def touch(user_id: int) -> None:
    db.execute("UPDATE users SET last_seen=? WHERE id=?", (_now(), user_id))


def purge_expired_sessions() -> None:
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (_now(),))


# ------------------------------------------------------------------ presence
ONLINE_WINDOW = 180


def is_online(user: Dict[str, Any]) -> bool:
    return (_now() - int(user.get("last_seen") or 0)) < ONLINE_WINDOW


def presence_label(user: Dict[str, Any]) -> str:
    from ..game import registry
    playing = registry.player_world(int(user["id"]))
    if playing:
        return "Playing %s" % playing
    return "Online" if is_online(user) else "Offline"


# ------------------------------------------------------------------- profile

def update_profile(user_id: int, blurb: str, location: str) -> None:
    db.execute("UPDATE users SET blurb=?, location=? WHERE id=?",
               (security.clean_text(blurb, 400), security.clean_text(location, 60, False),
                user_id))


def search(term: str, limit: int = 40) -> List[Dict[str, Any]]:
    term = (term or "").strip().lower()
    if term:
        rows = db.query(
            "SELECT * FROM users WHERE username_lower LIKE ? ORDER BY last_seen DESC"
            " LIMIT ?", ("%" + term.replace("%", "") + "%", limit))
    else:
        rows = db.query("SELECT * FROM users ORDER BY last_seen DESC LIMIT ?",
                        (limit,))
    return db.rows_to_dicts(rows)


def recent(limit: int = 12) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)))


def online_users(limit: int = 30) -> List[Dict[str, Any]]:
    cutoff = _now() - ONLINE_WINDOW
    return db.rows_to_dicts(db.query(
        "SELECT * FROM users WHERE last_seen > ? ORDER BY last_seen DESC LIMIT ?",
        (cutoff, limit)))


def count_users() -> int:
    return int(db.scalar("SELECT COUNT(*) FROM users"))


def public(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strip everything that must never leave the server."""
    if not user:
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "blurb": user.get("blurb", ""),
        "location": user.get("location", ""),
        "created_at": user.get("created_at", 0),
        "last_seen": user.get("last_seen", 0),
        "is_admin": bool(user.get("is_admin")),
        "place_visits": user.get("place_visits", 0),
    }
