"""Server authoritative credit balances.

Every balance change in the entire platform funnels through :func:`adjust`,
which runs inside a single write transaction and appends to an immutable
ledger.  Clients never send balances -- only intents ("buy item X") -- so a
tampered request can never mint credits.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .. import config, db


class EconomyError(Exception):
    pass


def balance(user_id: int) -> int:
    return int(db.scalar("SELECT credits FROM users WHERE id=?", (user_id,), 0))


def adjust(user_id: int, delta: int, reason: str,
           actor_id: Optional[int] = None,
           allow_negative: bool = False) -> int:
    """Apply ``delta`` to a balance atomically. Returns the new balance."""
    delta = int(delta)
    reason = (reason or "adjustment")[:120]
    with db.transaction() as conn:
        row = conn.execute("SELECT credits FROM users WHERE id=?",
                           (user_id,)).fetchone()
        if row is None:
            raise EconomyError("No such account.")
        current = int(row["credits"])
        new_balance = current + delta
        if new_balance < 0 and not allow_negative:
            raise EconomyError("Not enough credits.")
        new_balance = max(0, min(config.MAX_CREDITS, new_balance))
        applied = new_balance - current
        conn.execute("UPDATE users SET credits=? WHERE id=?",
                     (new_balance, user_id))
        conn.execute(
            "INSERT INTO credit_ledger(user_id, delta, balance_after, reason,"
            " actor_id, created_at) VALUES(?,?,?,?,?,?)",
            (user_id, applied, new_balance, reason, actor_id, int(time.time())))
    return new_balance


def set_balance(user_id: int, amount: int, reason: str,
                actor_id: Optional[int] = None) -> int:
    """Used by the admin dashboard -- routed through the same ledger path."""
    amount = max(0, min(config.MAX_CREDITS, int(amount)))
    current = balance(user_id)
    return adjust(user_id, amount - current, reason, actor_id,
                  allow_negative=True)


def spend(user_id: int, amount: int, reason: str) -> int:
    amount = int(amount)
    if amount < 0:
        raise EconomyError("Invalid amount.")
    if amount == 0:
        return balance(user_id)
    return adjust(user_id, -amount, reason)


def history(user_id: int, limit: int = 25) -> List[Dict[str, Any]]:
    return db.rows_to_dicts(db.query(
        "SELECT * FROM credit_ledger WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)))


def totals() -> Dict[str, int]:
    return {
        "circulating": int(db.scalar("SELECT COALESCE(SUM(credits),0) FROM users")),
        "granted": int(db.scalar(
            "SELECT COALESCE(SUM(delta),0) FROM credit_ledger WHERE delta>0")),
        "spent": int(db.scalar(
            "SELECT COALESCE(-SUM(delta),0) FROM credit_ledger WHERE delta<0")),
        "transactions": int(db.scalar("SELECT COUNT(*) FROM credit_ledger")),
    }
