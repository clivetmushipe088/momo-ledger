import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
COLUMNS = "id, sms_ref, transaction_type, amount, party, date, status, raw_sms"
EDITABLE = ("transaction_type", "amount", "party", "date", "status")
SESSION_LIFETIME = "-1 day"  # a login lasts one day


@contextmanager
def connect():
    """Open the database, commit if everything worked, and always close it."""
    conn = sqlite3.connect(os.environ.get("MOMO_DB", "momo.db"))
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_FILE.read_text())


def _clean(values: dict) -> dict:
    """Keep only editable columns and turn datetimes into 'YYYY-MM-DD HH:MM:SS'."""
    row = {key: values[key] for key in EDITABLE if key in values}
    if isinstance(row.get("date"), datetime):
        row["date"] = row["date"].strftime("%Y-%m-%d %H:%M:%S")
    return row


#  users and sessions 

def create_user(username: str, password_hash: str) -> bool:
    """Returns False if the username is already taken."""
    try:
        with connect() as conn:
            conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                         (username, password_hash))
        return True
    except sqlite3.IntegrityError:
        return False


def find_user(username: str):
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_session(token: str, user_id: int) -> None:
    with connect() as conn:
        # tidy up: expired sessions are useless, so remove them while we're here
        conn.execute("DELETE FROM sessions WHERE created_at <= datetime('now', ?)", (SESSION_LIFETIME,))
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))


def user_for_session(token: str):
    """The user who owns this token, or None if it's unknown or older than a day."""
    with connect() as conn:
        return conn.execute(
            """SELECT users.id, users.username
               FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.token = ? AND sessions.created_at > datetime('now', ?)""",
            (token, SESSION_LIFETIME),
        ).fetchone()


def delete_session(token: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


#  importing a backup 

def save_import(user_id: int, records: list[dict], unmatched: list[dict]) -> dict:
    """Insert parsed records. Ones already in the database (same sms_ref) are skipped."""
    imported = 0
    with connect() as conn:
        for r in records:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO transactions
                       (user_id, sms_ref, transaction_type, amount, party, date, raw_sms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, r["sms_ref"], r["transaction_type"], r["amount"],
                 r["party"], r["date"], r["raw_sms"]),
            )
            imported += cursor.rowcount  # 1 if inserted, 0 if it was a duplicate
        for u in unmatched:
            conn.execute("INSERT OR IGNORE INTO unmatched_sms (user_id, body, date) VALUES (?, ?, ?)",
                         (user_id, u["body"], u["date"]))
    return {"imported": imported, "duplicates": len(records) - imported}


def list_unmatched(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT id, body, date FROM unmatched_sms WHERE user_id = ? ORDER BY date",
                            (user_id,)).fetchall()
    return [dict(row) for row in rows]


#  transactions 

def list_transactions(user_id, txn_type=None, status=None, min_amount=None,
                      max_amount=None, page=1, limit=20) -> dict:
    """One page of the user's transactions, newest first, with optional filters."""
    conditions = ["user_id = ?"]
    params = [user_id]
    if txn_type:
        conditions.append("transaction_type = ?")
        params.append(txn_type)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if min_amount is not None:
        conditions.append("amount >= ?")
        params.append(min_amount)
    if max_amount is not None:
        conditions.append("amount <= ?")
        params.append(max_amount)
    where = " AND ".join(conditions)  # only our own fixed strings, the values are still ?s

    with connect() as conn:
        count = conn.execute(f"SELECT COUNT(*) FROM transactions WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM transactions WHERE {where} "
            "ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            params + [limit, (page - 1) * limit],
        ).fetchall()

    return {
        "count": count,
        "page": page,
        "limit": limit,
        "pages": max(1, math.ceil(count / limit)),
        "transactions": [dict(row) for row in rows],
    }


def get_transaction(user_id: int, txn_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(f"SELECT {COLUMNS} FROM transactions WHERE id = ? AND user_id = ?",
                           (txn_id, user_id)).fetchone()
    return dict(row) if row else None


def create_transaction(user_id: int, values: dict) -> dict:
    row = _clean(values)
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with connect() as conn:
        cursor = conn.execute(f"INSERT INTO transactions (user_id, {columns}) VALUES (?, {marks})",
                              [user_id, *row.values()])
        new_id = cursor.lastrowid
    return get_transaction(user_id, new_id)


def update_transaction(user_id: int, txn_id: int, changes: dict) -> dict | None:
    """Change some fields of a transaction. Returns None if it doesn't exist."""
    row = _clean(changes)
    if row:
        assignments = ", ".join(f"{column} = ?" for column in row)
        with connect() as conn:
            conn.execute(f"UPDATE transactions SET {assignments} WHERE id = ? AND user_id = ?",
                         [*row.values(), txn_id, user_id])
    return get_transaction(user_id, txn_id)


def delete_transaction(user_id: int, txn_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (txn_id, user_id))
    return cursor.rowcount > 0
