"""
tests/test_day5.py

Full integration test for Day 5 — Sprint 1 backend pipeline.

Tests
-----
1. test_full_session  — 5-turn session, DB rows written, Fernet round-trip
2. test_alert_written — HIGH-risk keyword triggers alert row
3. test_summary_generated — summarize_session() stores a clinical summary

All three tests share a single session fixture (module scope) so Granite
is called only once for the whole file — the 5-turn session is set up once,
then tests 2 and 3 query the same DB state.

Uses a dedicated test DB (data/test_day5.db) — deleted in fixture teardown.
"""

import uuid
from pathlib import Path

import pytest

from core.mood_engine import RiskLevel
from core.summarizer import summarize_session
from data.database import Database
from orchestration.chain import AstroMindChain, ChatResult

TEST_DB_PATH = Path(__file__).parent.parent / "data" / "test_day5.db"

MESSAGES = [
    "I haven't been sleeping well for the past three nights.",
    "The EVA tomorrow is weighing on me. I keep running scenarios.",
    "I snapped at Chen during dinner. I feel bad about it.",
    "I tried the breathing exercise. It helped a little.",
    "I think I just need to talk. Can't go on feeling this isolated.",
]


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def session_state():
    """
    Run a complete 5-turn session once for the whole module.

    Yields a dict with:
        db         — open Database instance
        session_id — UUID string for this test session
        results    — List[ChatResult] from the 5 turns
        messages   — the 5 input strings

    Teardown: closes DB and deletes the test DB file.
    """
    db         = Database(db_path=TEST_DB_PATH)
    session_id = f"test-{uuid.uuid4()}"

    chain = AstroMindChain(
        session_id      = session_id,
        astronaut_id    = "test-astronaut",
        mission_context = "Day 45 of lunar outpost rotation.",
        db              = db,
    )

    results = []
    for msg in MESSAGES:
        result = chain.chat(msg, use_rag=False)  # RAG tested in test_knowledge.py
        results.append(result)

    chain.close()

    yield {
        "db":         db,
        "session_id": session_id,
        "results":    results,
        "messages":   MESSAGES,
    }

    # ── Teardown ───────────────────────────────────────────────────────────────
    db.close()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_full_session(session_state):
    """5-turn session: ChatResult shape, DB rows, Fernet round-trip."""
    db         = session_state["db"]
    session_id = session_state["session_id"]
    results    = session_state["results"]
    messages   = session_state["messages"]

    # ── ChatResult assertions ──────────────────────────────────────────────
    assert len(results) == 5
    for i, result in enumerate(results):
        assert isinstance(result, ChatResult),     f"Turn {i}: expected ChatResult"
        assert result.response.mood,               f"Turn {i}: mood is empty"
        assert 0 <= result.report.wellness <= 100, f"Turn {i}: wellness out of range"
        assert len(result.strategies) == 3,        f"Turn {i}: expected 3 strategies"

    # ── Session row ────────────────────────────────────────────────────────
    session_row = db.get_session(session_id)
    assert session_row is not None,             "session row missing"
    assert session_row["ended_at"] is not None, "ended_at not stamped by chain.close()"
    assert session_row["astronaut_id"] == "test-astronaut"

    # ── Message rows ───────────────────────────────────────────────────────
    db_messages = db.get_messages(session_id)
    assert len(db_messages) == 10, \
        f"Expected 10 message rows (5 turns x 2 roles), got {len(db_messages)}"

    # Fernet round-trip: decrypted content must match original plaintext
    human_msgs = [m for m in db_messages if m["role"] == "human"]
    assert human_msgs[0]["content"] == messages[0], \
        "Fernet round-trip FAILED: decrypted content does not match original"

    # ── Mood score rows ────────────────────────────────────────────────────
    mood_scores = db.get_mood_scores(session_id)
    assert len(mood_scores) == 5, \
        f"Expected 5 mood_score rows, got {len(mood_scores)}"
    for score in mood_scores:
        assert 0 <= score["wellness"] <= 100
        assert score["risk_level"] in {"low", "medium", "high"}


def test_alert_written(session_state):
    """'Can't go on' in message 5 must produce at least 1 alert row."""
    db         = session_state["db"]
    session_id = session_state["session_id"]

    alert_rows = db._conn.execute(
        "SELECT * FROM alerts WHERE session_id = ?", (session_id,)
    ).fetchall()

    assert len(alert_rows) >= 1, (
        "Expected at least 1 alert row — "
        "message 5 contains 'can't go on' which triggers HIGH risk"
    )


def test_summary_generated(session_state):
    """summarize_session() must return non-empty text and persist it to DB."""
    db         = session_state["db"]
    session_id = session_state["session_id"]

    summary = summarize_session(session_id=session_id, db=db)

    assert summary,             "summary is empty"
    assert len(summary) > 50,  f"summary too short ({len(summary)} chars)"

    stored = db.get_summary(session_id)
    assert stored == summary,  "stored summary does not match returned summary"
