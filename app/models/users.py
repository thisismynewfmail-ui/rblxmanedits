"""Account creation, authentication, sessions and presence."""
from __future__ import annotations

import json
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
            "INSERT INTO avatars(user_id, colors, equipped, hotbar, body_type,"
            " updated_at) VALUES(?,?,?,?,?,?)",
            (user_id, _json(catalog.DEFAULT_COLORS), _json({}), _json([]),
             catalog.DEFAULT_BODY_TYPE, now))
    # Starter kit is granted through the normal inventory path so every item a
    # player owns exists as a real inventory row.
    from . import inventory, avatars
    for item_id in catalog.STARTER_ITEMS:
        inventory.grant(user_id, item_id, source="starter", allow_unusual=False)
    avatars.apply_defaults(user_id)
    db.audit(user_id, "account.create", username)
    from .. import console
    console.note("new account: %s" % username)
    return get_by_id(user_id)  # type: ignore[return-value]


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def authenticate(username: str, password: str) -> Dict[str, Any]:
    user = get_by_username(username)
    if not user or not security.verify_password(password, user["password_hash"]):
        raise AuthError("Incorrect username or password.")
    if user["is_banned"]:
        raise AuthError("This account has been suspended.")
    db.execute("UPDATE users SET last_login=?, last_seen=? WHERE id=?",
               (_now(), _now(), user["id"]))
    from .. import console
    console.note("%s signed in" % user["username"])
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


# -------------------------------------------------------------- preferences
THEMES = ("auto", "light", "dark")

# Who may see a given part of a profile.  "friends" means accepted friends
# only; "private" means nobody but the owner (and administrators).
VISIBILITIES = ("public", "friends", "private")

PRIVACY_FIELDS = {
    "friends_list": "public",
    "stats": "public",
    "inventory": "public",
    "server": "friends",
    "wall": "public",
    "online": "public",
}

PRIVACY_LABELS = [
    ("friends_list", "Who can see my friends list"),
    ("inventory", "Who can see my inventory"),
    ("stats", "Who can see my deaths and K/D"),
    ("server", "Who can see the server I am playing on"),
    ("online", "Who can see when I am online"),
    ("wall", "Who can leave comments on my profile"),
]

MAX_PINNED = 3


def theme_of(user: Optional[Dict[str, Any]]) -> str:
    value = (user or {}).get("theme") or "auto"
    return value if value in THEMES else "auto"


def set_theme(user_id: int, theme: str) -> str:
    theme = (theme or "").lower()
    if theme not in THEMES:
        theme = "auto"
    db.execute("UPDATE users SET theme=? WHERE id=?", (theme, user_id))
    return theme


def privacy_of(user: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Merged privacy settings; unknown or missing keys fall back to default."""
    settings = dict(PRIVACY_FIELDS)
    raw = (user or {}).get("privacy") or "{}"
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError):
        stored = {}
    if isinstance(stored, dict):
        for key, value in stored.items():
            if key in settings and value in VISIBILITIES:
                settings[key] = value
    return settings


def set_privacy(user_id: int, settings: Dict[str, Any]) -> Dict[str, str]:
    merged = privacy_of(get_by_id(user_id))
    for key, value in (settings or {}).items():
        if key in PRIVACY_FIELDS and value in VISIBILITIES:
            merged[key] = value
    db.execute("UPDATE users SET privacy=? WHERE id=?", (_json(merged), user_id))
    return merged


def can_view(owner: Dict[str, Any], field: str, viewer_id: int,
             viewer_is_admin: bool = False) -> bool:
    """Apply one privacy field for a given viewer."""
    owner_id = int(owner["id"])
    if viewer_id == owner_id or viewer_is_admin:
        return True
    level = privacy_of(owner).get(field, "public")
    if level == "public":
        return True
    if level == "private":
        return False
    if not viewer_id:
        return False
    from ..social import friends as friends_model
    return friends_model.are_friends(owner_id, viewer_id)


def pinned_of(user: Optional[Dict[str, Any]]) -> List[int]:
    raw = (user or {}).get("pinned") or "[]"
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(stored, list):
        return []
    out = []
    for value in stored:
        try:
            inv_id = int(value)
        except (TypeError, ValueError):
            continue
        if inv_id > 0 and inv_id not in out:
            out.append(inv_id)
    return out[:MAX_PINNED]


def set_pinned(user_id: int, inv_ids: List[Any]) -> List[int]:
    """Pin up to three owned inventory rows to the top of the profile."""
    from . import inventory
    clean: List[int] = []
    for value in (inv_ids or []):
        try:
            inv_id = int(value)
        except (TypeError, ValueError):
            continue
        if inv_id <= 0 or inv_id in clean:
            continue
        if inventory.get_row(user_id, inv_id) is None:
            continue
        clean.append(inv_id)
        if len(clean) >= MAX_PINNED:
            break
    db.execute("UPDATE users SET pinned=? WHERE id=?", (_json(clean), user_id))
    return clean
