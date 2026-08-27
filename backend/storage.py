"""Neon PostgreSQL persistence for SENTRY.

Replaces the local SQLite layer. All data lives in the Neon cloud database
(connection in dbconfig.py — gitignored).

Key differences from the SQLite version:
- Connection pool (psycopg_pool), %s placeholders, dict rows.
- Users have BOTH email and username (login accepts either).
- Screenings/queries are owned by an account (owner_user_id) — per-account
  history; new accounts start empty.
- Soft delete: deleted_at set → record lives in the trash bin until
  restored (cleared) or purged (hard delete + image file removed).
"""
import json
from datetime import datetime, timedelta

import psycopg
from psycopg_pool import ConnectionPool

from dbconfig import DATABASE_URL

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        # Neon serverless suspends idle computes (~5 min), which kills open
        # connections. `check` pings pooled connections before use (dead ones
        # are replaced), and `max_lifetime` recycles them before Neon does.
        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=0, max_size=5,
            max_lifetime=240,
            check=ConnectionPool.check_connection,
            kwargs={"row_factory": psycopg.rows.dict_row, "autocommit": True},
            open=True,
        )
    return _pool


def _run(action):
    with _get_pool().connection() as conn:
        return action(conn)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    username      TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    passport_no   TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS screenings (
    id              TEXT PRIMARY KEY,
    owner_user_id   INTEGER,
    doc_type        TEXT,
    fields_json     TEXT,
    validation_json TEXT,
    tampering_json  TEXT,
    face_json       TEXT,
    risk_score      INTEGER,
    risk_tier       TEXT,
    reasons_json    TEXT,
    decision        TEXT,
    officer         TEXT,
    note            TEXT,
    created_at      TEXT,
    image_path      TEXT,
    deleted_at      TEXT
);
CREATE TABLE IF NOT EXISTS queries (
    id            TEXT PRIMARY KEY,
    owner_user_id INTEGER,
    user_name     TEXT,
    query_text    TEXT,
    screening_id  TEXT,
    status        TEXT DEFAULT 'pending',
    created_at    TEXT,
    deleted_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_screenings_owner ON screenings (owner_user_id, deleted_at);
CREATE INDEX IF NOT EXISTS idx_queries_owner ON queries (owner_user_id, deleted_at);
"""

_IMAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id            SERIAL PRIMARY KEY,
    owner_user_id INTEGER,
    kind          TEXT,
    data          BYTEA,
    mime          TEXT,
    created_at    TEXT
);
"""

_WATCHLIST_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    id          SERIAL PRIMARY KEY,
    doc_number  TEXT NOT NULL,
    person_name TEXT,
    reason      TEXT,
    severity    TEXT DEFAULT 'high',
    added_by    TEXT,
    created_at  TEXT
);
"""

_STATEMENTS = [stmt.strip() + ";" for stmt in _SCHEMA.split(";") if stmt.strip()]
_STATEMENTS += [stmt.strip() + ";" for stmt in _IMAGE_SCHEMA.split(";") if stmt.strip()]
_STATEMENTS += [stmt.strip() + ";" for stmt in _WATCHLIST_SCHEMA.split(";") if stmt.strip()]


def init_db() -> None:
    def action(conn) -> None:
        for stmt in _STATEMENTS:
            conn.execute(stmt)
        # additive columns for existing deployments (idempotent)
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image_id INTEGER")
        conn.execute("ALTER TABLE screenings ADD COLUMN IF NOT EXISTS image_id INTEGER")

    _run(action)


# ------------------------------------------------------------------ images
def insert_image(owner_user_id: int, kind: str, data: bytes, mime: str) -> int:
    def action(conn) -> int:
        cur = conn.execute(
            """INSERT INTO images (owner_user_id, kind, data, mime, created_at)
               VALUES (%s,%s,%s,%s,%s) RETURNING id""",
            (owner_user_id, kind, data, mime, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.fetchone()["id"]

    return _run(action)


def get_image(image_id: int) -> dict | None:
    def action(conn) -> dict | None:
        cur = conn.execute("SELECT data, mime FROM images WHERE id = %s", (image_id,))
        return cur.fetchone()

    return _run(action)


def delete_image(image_id: int) -> None:
    _run(lambda conn: conn.execute("DELETE FROM images WHERE id = %s", (image_id,)))


def set_profile_picture(user_id: int, image_id: int | None) -> None:
    _run(lambda conn: conn.execute(
        "UPDATE users SET profile_image_id = %s WHERE id = %s", (image_id, user_id),
    ))


def get_profile_picture_id(user_id: int) -> int | None:
    def action(conn) -> int | None:
        cur = conn.execute("SELECT profile_image_id FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return row["profile_image_id"] if row else None

    return _run(action)


# ------------------------------------------------------------------- users
def create_user(email: str, username: str, name: str, password_hash: str, role: str,
                passport_no: str | None = None, created_at: str | None = None) -> int | None:
    def action(conn) -> int:
        cur = conn.execute(
            """INSERT INTO users (email, username, name, passport_no, password_hash, role, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (email, username, name, passport_no, password_hash, role, created_at),
        )
        return cur.fetchone()["id"]

    try:
        return _run(action)
    except psycopg.errors.UniqueViolation:
        return None  # email or username already taken


def get_user_by_login(login: str) -> dict | None:
    """Look up a user by email OR username (case-insensitive)."""
    def action(conn) -> dict | None:
        cur = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s)",
            (login, login),
        )
        return cur.fetchone()

    row = _run(action)
    if not row:
        return None
    return {
        "id": row["id"], "email": row["email"], "username": row["username"],
        "name": row["name"], "passportNo": row["passport_no"], "role": row["role"],
        "profileImageId": row["profile_image_id"],
    }


def get_user_by_username(username: str) -> dict | None:
    def action(conn) -> dict | None:
        cur = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(%s)", (username,)
        )
        return cur.fetchone()

    return _run(action)


def update_user_profile(user_id: int, name: str, email: str) -> bool | str:
    """Update name/email. True on success; 'email' if the email is taken;
    False if the user id is unknown."""
    def action(conn) -> int:
        cur = conn.execute(
            "UPDATE users SET name = %s, email = %s WHERE id = %s",
            (name, email, user_id),
        )
        return cur.rowcount

    try:
        return _run(action) > 0
    except psycopg.errors.UniqueViolation:
        return "email"


def get_password_hash(login: str) -> str | None:
    def action(conn) -> str | None:
        cur = conn.execute(
            "SELECT password_hash FROM users WHERE LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s)",
            (login, login),
        )
        row = cur.fetchone()
        return row["password_hash"] if row else None

    return _run(action)


# ---------------------------------------------------------------- sessions
def create_session(token: str, user_id: int, expires_at: str) -> None:
    _run(lambda conn: conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s,%s,%s)",
        (token, user_id, expires_at),
    ))


def get_session_user(token: str) -> dict | None:
    def action(conn) -> dict | None:
        cur = conn.execute(
            """SELECT u.id, u.email, u.username, u.name, u.passport_no, u.role,
                      u.profile_image_id, s.expires_at
               FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = %s""",
            (token,),
        )
        return cur.fetchone()

    row = _run(action)
    if not row:
        return None
    if row["expires_at"] <= datetime.now().isoformat(timespec="seconds"):
        return None  # expired
    return {
        "id": row["id"], "email": row["email"], "username": row["username"],
        "name": row["name"], "passportNo": row["passport_no"], "role": row["role"],
        "profileImageId": row["profile_image_id"],
    }


def delete_session(token: str) -> None:
    _run(lambda conn: conn.execute("DELETE FROM sessions WHERE token = %s", (token,)))


# -------------------------------------------------------------- screenings
def next_doc_id() -> str:
    """Sequential DOC-XXXXX id continuing from the highest stored one."""
    def action(conn) -> str:
        cur = conn.execute("SELECT id FROM screenings")
        highest = 88232
        for row in cur.fetchall():
            digits = "".join(ch for ch in row["id"] if ch.isdigit())
            if digits:
                highest = max(highest, int(digits))
        return f"DOC-{highest + 1}"

    return _run(action)


def insert_screening(payload: dict, image_id: int, owner_user_id: int) -> None:
    def action(conn) -> None:
        conn.execute(
            """INSERT INTO screenings
               (id, owner_user_id, doc_type, fields_json, validation_json, tampering_json,
                face_json, risk_score, risk_tier, reasons_json, decision, officer, note,
                created_at, image_path, deleted_at, image_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s)""",
            (
                payload["id"], owner_user_id, payload["docType"],
                json.dumps(payload["fields"]), json.dumps(payload["validation"]),
                json.dumps(payload["tampering"]), json.dumps(payload["face"]),
                payload["risk"]["score"], payload["risk"]["tier"],
                json.dumps(payload["risk"]["reasons"]),
                None, None, None,
                payload["createdAt"], image_id,
            ),
        )

    _run(action)


def _row_to_payload(row: dict) -> dict:
    return {
        "id": row["id"],
        "docType": row["doc_type"],
        "fields": json.loads(row["fields_json"] or "{}"),
        "validation": json.loads(row["validation_json"] or "[]"),
        "tampering": json.loads(row["tampering_json"] or "[]"),
        "face": json.loads(row["face_json"] or "{}"),
        "risk": {
            "score": row["risk_score"],
            "tier": row["risk_tier"],
            "reasons": json.loads(row["reasons_json"] or "[]"),
        },
        "decision": row["decision"],
        "officer": row["officer"],
        "note": row["note"],
        "createdAt": row["created_at"],
        "imageId": row["image_id"],
        "deletedAt": row["deleted_at"],
    }


def list_screenings(owner_user_id: int, limit: int = 50, trashed: bool = False) -> list[dict]:
    filter_sql = "deleted_at IS NOT NULL" if trashed else "deleted_at IS NULL"

    def action(conn) -> list[dict]:
        cur = conn.execute(
            f"""SELECT * FROM screenings WHERE owner_user_id = %s AND {filter_sql}
                ORDER BY created_at DESC, id DESC LIMIT %s""",
            (owner_user_id, limit),
        )
        return [_row_to_payload(r) for r in cur.fetchall()]

    return _run(action)


def get_screening(doc_id: str, owner_user_id: int | None = None) -> dict | None:
    owner_sql = ""
    params: list = [doc_id]
    if owner_user_id is not None:
        owner_sql = " AND owner_user_id = %s"
        params.append(owner_user_id)

    def action(conn) -> dict | None:
        cur = conn.execute(f"SELECT * FROM screenings WHERE id = %s{owner_sql}", params)
        row = cur.fetchone()
        return _row_to_payload(row) if row else None

    return _run(action)


def record_decision(doc_id: str, decision: str, officer: str, note: str | None) -> bool:
    def action(conn) -> int:
        cur = conn.execute(
            "UPDATE screenings SET decision = %s, officer = %s, note = %s WHERE id = %s",
            (decision, officer, note, doc_id),
        )
        return cur.rowcount

    return _run(action) > 0


def soft_delete_screening(doc_id: str, owner_user_id: int) -> bool:
    """Move a record to the trash bin (recoverable)."""
    def action(conn) -> int:
        cur = conn.execute(
            """UPDATE screenings SET deleted_at = %s
               WHERE id = %s AND owner_user_id = %s AND deleted_at IS NULL""",
            (datetime.now().isoformat(timespec="seconds"), doc_id, owner_user_id),
        )
        return cur.rowcount

    return _run(action) > 0


def restore_screening(doc_id: str, owner_user_id: int) -> bool:
    """Recover a record from the trash bin."""
    def action(conn) -> int:
        cur = conn.execute(
            "UPDATE screenings SET deleted_at = NULL WHERE id = %s AND owner_user_id = %s",
            (doc_id, owner_user_id),
        )
        return cur.rowcount

    return _run(action) > 0


def purge_screening(doc_id: str, owner_user_id: int) -> int | None:
    """Permanently delete a trashed record. Returns its image_id (so the
    caller can delete the stored image), or None if the record was not found."""
    def action(conn) -> int | None:
        cur = conn.execute(
            "SELECT image_id FROM screenings WHERE id = %s AND owner_user_id = %s",
            (doc_id, owner_user_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        conn.execute(
            "DELETE FROM screenings WHERE id = %s AND owner_user_id = %s",
            (doc_id, owner_user_id),
        )
        return row["image_id"]

    return _run(action)


# -------------------------------------------------------------- watchlist
def add_watchlist_entry(doc_number: str, person_name: str | None, reason: str | None,
                        severity: str, added_by: str, created_at: str) -> int:
    def action(conn) -> int:
        cur = conn.execute(
            """INSERT INTO watchlist (doc_number, person_name, reason, severity, added_by, created_at)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (doc_number.strip().upper(), person_name, reason, severity, added_by, created_at),
        )
        return cur.fetchone()["id"]

    return _run(action)


def list_watchlist() -> list[dict]:
    def action(conn) -> list[dict]:
        cur = conn.execute(
            "SELECT * FROM watchlist ORDER BY created_at DESC, id DESC LIMIT 200"
        )
        return [
            {
                "id": r["id"], "docNumber": r["doc_number"], "personName": r["person_name"],
                "reason": r["reason"], "severity": r["severity"], "addedBy": r["added_by"],
                "createdAt": r["created_at"],
            }
            for r in cur.fetchall()
        ]

    return _run(action)


def remove_watchlist_entry(entry_id: int) -> bool:
    def action(conn) -> int:
        cur = conn.execute("DELETE FROM watchlist WHERE id = %s", (entry_id,))
        return cur.rowcount

    return _run(action) > 0


def match_watchlist(doc_number: str | None, person_name: str | None) -> dict | None:
    """Check a screening's document number / holder name against the
    watchlist. Returns the matched entry dict, or None."""
    if not doc_number and not person_name:
        return None

    def action(conn) -> dict | None:
        cur = conn.execute("SELECT * FROM watchlist")
        for row in cur.fetchall():
            if doc_number and row["doc_number"] and \
                    row["doc_number"].replace(" ", "") == doc_number.replace(" ", "").upper():
                return dict(row)
            if person_name and row["person_name"] and \
                    row["person_name"].strip().lower() == person_name.strip().lower():
                return dict(row)
        return None

    return _run(action)


# ----------------------------------------------------------------- queries
def next_query_id() -> str:
    def action(conn) -> str:
        cur = conn.execute("SELECT id FROM queries")
        highest = 51042
        for row in cur.fetchall():
            digits = "".join(ch for ch in row["id"] if ch.isdigit())
            if digits:
                highest = max(highest, int(digits))
        return f"QRY-{highest + 1}"

    return _run(action)


def insert_query(query_id: str, owner_user_id: int, user_name: str, query_text: str,
                 screening_id: str | None, created_at: str) -> None:
    def action(conn) -> None:
        conn.execute(
            """INSERT INTO queries (id, owner_user_id, user_name, query_text, screening_id,
               status, created_at, deleted_at) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL)""",
            (query_id, owner_user_id, user_name, query_text, screening_id, "pending", created_at),
        )

    _run(action)


def list_queries(owner_user_id: int, limit: int = 20, trashed: bool = False) -> list[dict]:
    filter_sql = "deleted_at IS NOT NULL" if trashed else "deleted_at IS NULL"

    def action(conn) -> list[dict]:
        cur = conn.execute(
            f"""SELECT * FROM queries WHERE owner_user_id = %s AND {filter_sql}
                ORDER BY created_at DESC, id DESC LIMIT %s""",
            (owner_user_id, limit),
        )
        return [
            {
                "id": r["id"], "userName": r["user_name"], "queryText": r["query_text"],
                "screeningId": r["screening_id"], "status": r["status"],
                "createdAt": r["created_at"], "deletedAt": r["deleted_at"],
            }
            for r in cur.fetchall()
        ]

    return _run(action)
