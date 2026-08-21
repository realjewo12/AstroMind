"""
data/database.py

SQLite data layer for AstroMind.

Creates and manages 5 tables:
    sessions    — one row per conversation session
    messages    — one row per chat turn (human + AI text)  [content ENCRYPTED]
    mood_scores — one row per turn (wellness, risk, flags)
    alerts      — one row per HIGH-risk detection          [trigger_text ENCRYPTED]
    summaries   — one row per session (Granite narrative summary)

PII fields encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256):
    messages.content      — the astronaut's words and AstroMind's replies
    alerts.trigger_text   — the crisis phrase that triggered the alert

The encryption key is loaded from ASTROMIND_DB_KEY in .env.
Without the key, encrypted fields are unreadable ciphertext.

Public API
----------
    from data.database import Database

    db = Database()
    db.create_session(session_id, astronaut_id, mission_phase)
    db.insert_message(session_id, turn, role, content)
    db.insert_mood_score(session_id, turn, mood, wellness, risk, raw_score, flags)
    db.insert_alert(session_id, turn, trigger_text, flags)
    db.insert_summary(session_id, summary_text)

    db.get_session(session_id)      -> dict | None
    db.get_messages(session_id)     -> List[dict]   (content already decrypted)
    db.get_mood_scores(session_id)  -> List[dict]
    db.get_summary(session_id)      -> str | None
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "astromind.db"


# ── Field-level cipher ─────────────────────────────────────────────────────────

class _FieldCipher:
    """
    Fernet symmetric encryption for individual DB fields.

    Fernet guarantees:
    - AES-128-CBC encryption  (confidentiality)
    - HMAC-SHA256 signature   (tamper detection — raises InvalidToken if modified)
    - Timestamp embedded in token (can enforce key rotation policies later)

    Key is loaded from ASTROMIND_DB_KEY in .env.
    If the key is missing, encryption is disabled with a clear warning —
    the app still runs but fields are stored as plaintext.
    """

    def __init__(self) -> None:
        raw_key = os.environ.get("ASTROMIND_DB_KEY", "")
        if raw_key:
            self._fernet: Optional[Fernet] = Fernet(raw_key.encode())
            self._enabled = True
        else:
            print(
                "[database] WARNING: ASTROMIND_DB_KEY not set. "
                "PII fields will be stored as plaintext."
            )
            self._fernet = None
            self._enabled = False

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string. Returns ciphertext string, or plaintext if key missing."""
        if not self._enabled or self._fernet is None:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, value: str) -> str:
        """
        Decrypt a string. Returns plaintext.
        Returns value unchanged if decryption fails (e.g. field was stored
        unencrypted before the key was set).
        """
        if not self._enabled or self._fernet is None:
            return value
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            # Field may have been stored before encryption was enabled
            return value


# Module-level singleton — one cipher per process
_cipher = _FieldCipher()


# ── Database class ─────────────────────────────────────────────────────────────

class Database:
    """
    Thin wrapper around sqlite3 that manages the AstroMind schema.

    One instance per process is sufficient — SQLite handles concurrent
    reads safely. Writes are serialised by SQLite's file-level lock.

    Usage
    -----
        db = Database()          # connects and creates tables if needed
        db.create_session(...)
        db.insert_message(...)
        db.close()               # or use as context manager:

        with Database() as db:
            db.create_session(...)
    """

    def __init__(self, db_path: Path = DB_PATH):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row   # rows behave like dicts
        self._conn.execute("PRAGMA journal_mode=WAL")  # safe concurrent reads
        self._create_tables()

    # ── Schema ─────────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        """Create all 5 tables if they don't already exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id    TEXT PRIMARY KEY,
                astronaut_id  TEXT NOT NULL DEFAULT 'unknown',
                mission_phase TEXT NOT NULL DEFAULT '',
                started_at    TEXT NOT NULL,
                ended_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn       INTEGER NOT NULL,
                role       TEXT NOT NULL CHECK(role IN ('human', 'ai')),
                content    TEXT NOT NULL,  -- PII: Fernet encrypted
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS mood_scores (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                turn         INTEGER NOT NULL,
                mood         TEXT NOT NULL,
                wellness     INTEGER NOT NULL,
                risk_level   TEXT NOT NULL,
                raw_score    INTEGER NOT NULL,
                flags        TEXT NOT NULL DEFAULT '[]',
                created_at   TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                turn         INTEGER NOT NULL,
                trigger_text TEXT NOT NULL,  -- PII: Fernet encrypted
                flags        TEXT NOT NULL DEFAULT '[]',
                created_at   TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS summaries (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL UNIQUE,
                summary_text TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        """)
        self._conn.commit()

    # ── Write API ──────────────────────────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        astronaut_id: str = "unknown",
        mission_phase: str = "",
    ) -> None:
        """Insert a new session row. Ignores if session_id already exists."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO sessions
                (session_id, astronaut_id, mission_phase, started_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, astronaut_id, mission_phase, _now()),
        )
        self._conn.commit()

    def close_session(self, session_id: str) -> None:
        """Stamp the ended_at timestamp on a session."""
        self._conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        self._conn.commit()

    def insert_message(
        self,
        session_id: str,
        turn: int,
        role: str,
        content: str,
    ) -> None:
        """
        Insert one message row. content is encrypted before storage.

        Parameters
        ----------
        role    : "human" or "ai"
        turn    : zero-based turn index within the session
        content : plaintext — encrypted automatically before insert
        """
        self._conn.execute(
            """
            INSERT INTO messages
                (session_id, turn, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, turn, role, _cipher.encrypt(content), _now()),
        )
        self._conn.commit()

    def insert_mood_score(
        self,
        session_id: str,
        turn: int,
        mood: str,
        wellness: int,
        risk_level: str,
        raw_score: int,
        flags: List[str],
    ) -> None:
        """Insert one mood assessment row (one per AI turn)."""
        self._conn.execute(
            """
            INSERT INTO mood_scores
                (session_id, turn, mood, wellness, risk_level, raw_score, flags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, turn, mood, wellness, risk_level, raw_score,
             json.dumps(flags), _now()),
        )
        self._conn.commit()

    def insert_alert(
        self,
        session_id: str,
        turn: int,
        trigger_text: str,
        flags: List[str],
    ) -> None:
        """Insert a HIGH-risk alert row. trigger_text is encrypted before storage."""
        self._conn.execute(
            """
            INSERT INTO alerts
                (session_id, turn, trigger_text, flags, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, turn, _cipher.encrypt(trigger_text), json.dumps(flags), _now()),
        )
        self._conn.commit()

    def insert_summary(self, session_id: str, summary_text: str) -> None:
        """Insert or replace the session summary."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO summaries
                (session_id, summary_text, created_at)
            VALUES (?, ?, ?)
            """,
            (session_id, summary_text, _now()),
        )
        self._conn.commit()

    # ── Read API ───────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the session row as a dict, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Return all messages for a session, ordered by turn.
        content is decrypted before returning.
        """
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY turn, role",
            (session_id,),
        ).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            row["content"] = _cipher.decrypt(row["content"])  # decrypt PII
            result.append(row)
        return result

    def get_mood_scores(self, session_id: str) -> List[Dict[str, Any]]:
        """Return all mood scores for a session, ordered by turn."""
        rows = self._conn.execute(
            "SELECT * FROM mood_scores WHERE session_id = ? ORDER BY turn",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_summary(self, session_id: str) -> Optional[str]:
        """Return the summary text for a session, or None if not yet generated."""
        row = self._conn.execute(
            "SELECT summary_text FROM summaries WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row["summary_text"] if row else None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
