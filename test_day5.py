"""
test_day5.py

Full integration test for Day 5 — Sprint 1 backend pipeline.

Tests
-----
1. 5-turn session via AstroMindChain.chat()
   - Each turn returns a valid ChatResult
   - 10 message rows written to DB (5 turns x 2 roles)
   - 5 mood_score rows written
   - Fernet encryption round-trip confirmed
   - session ended_at stamped by chain.close()

2. HIGH-risk keyword triggers alert row
   - "Can't go on feeling this isolated" contains "can't go on"
   - At least 1 alert row in DB for the session

3. summarize_session() generates and stores a summary
   - Summary text is non-empty (> 50 chars)
   - Stored summary matches returned summary

Uses a dedicated test DB (data/test_day5.db) — deleted on completion.
"""

import sys
import uuid
from pathlib import Path

TEST_DB_PATH = Path("data/test_day5.db")

from data.database import Database
from orchestration.chain import AstroMindChain, ChatResult
from core.summarizer import summarize_session
from core.mood_engine import RiskLevel


# ── Cleanup ────────────────────────────────────────────────────────────────────

def _cleanup(db: "Database | None" = None):
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
        print(f"[cleanup] Removed {TEST_DB_PATH}")


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_full_session(db: Database):
    print("\n[TEST 1] 5-turn session -- DB rows written correctly")

    session_id = f"test-{uuid.uuid4()}"

    chain = AstroMindChain(
        session_id      = session_id,
        astronaut_id    = "test-astronaut",
        mission_context = "Day 45 of lunar outpost rotation.",
        db              = db,
    )

    messages = [
        "I haven't been sleeping well for the past three nights.",
        "The EVA tomorrow is weighing on me. I keep running scenarios.",
        "I snapped at Chen during dinner. I feel bad about it.",
        "I tried the breathing exercise. It helped a little.",
        "I think I just need to talk. Can't go on feeling this isolated.",
    ]

    results = []
    for i, msg in enumerate(messages):
        print(f"  Turn {i}: {msg[:60]}...")
        result = chain.chat(msg, use_rag=False)  # RAG tested separately in test_knowledge.py
        results.append(result)

        assert isinstance(result, ChatResult),      f"Turn {i}: expected ChatResult"
        assert result.response.mood,                f"Turn {i}: mood is empty"
        assert 0 <= result.report.wellness <= 100,  \
            f"Turn {i}: wellness {result.report.wellness} out of range"
        assert len(result.strategies) == 3,         f"Turn {i}: expected 3 strategies"

        print(f"    mood={result.response.mood}, "
              f"wellness={result.report.wellness}, "
              f"risk={result.report.risk.value}, "
              f"rag={'yes' if result.rag_used else 'no'}")

    chain.close()

    # ── Assert DB state ────────────────────────────────────────────────────
    session_row = db.get_session(session_id)
    assert session_row is not None,                "session row missing"
    assert session_row["ended_at"] is not None,    "ended_at not stamped by chain.close()"
    assert session_row["astronaut_id"] == "test-astronaut"
    print(f"  session row OK: started={session_row['started_at'][:19]}, "
          f"ended={session_row['ended_at'][:19]}")

    db_messages = db.get_messages(session_id)
    assert len(db_messages) == 10, \
        f"Expected 10 message rows (5 turns x 2 roles), got {len(db_messages)}"
    # Encryption round-trip: decrypted content must match original
    human_msgs = [m for m in db_messages if m["role"] == "human"]
    assert human_msgs[0]["content"] == messages[0], \
        "Fernet round-trip FAILED: decrypted content does not match original"
    print(f"  messages: {len(db_messages)} rows, Fernet round-trip OK")

    mood_scores = db.get_mood_scores(session_id)
    assert len(mood_scores) == 5, \
        f"Expected 5 mood_score rows, got {len(mood_scores)}"
    for score in mood_scores:
        assert 0 <= score["wellness"] <= 100
        assert score["risk_level"] in {"low", "medium", "high"}
    print(f"  mood_scores: {len(mood_scores)} rows, all valid")

    print("[TEST 1] PASSED")
    return session_id


def test_alert_written(session_id: str, db: Database):
    print("\n[TEST 2] HIGH risk keyword -> alert row written")

    alert_rows = db._conn.execute(
        "SELECT * FROM alerts WHERE session_id = ?", (session_id,)
    ).fetchall()

    assert len(alert_rows) >= 1, (
        "Expected at least 1 alert row — "
        "message 5 contains 'can't go on' which should trigger HIGH risk"
    )
    print(f"  alert rows: {len(alert_rows)}")
    print("[TEST 2] PASSED")


def test_summary_generated(session_id: str, db: Database):
    print("\n[TEST 3] summarize_session() -> summary stored in DB")

    summary = summarize_session(session_id=session_id, db=db)

    assert summary,              "summary is empty"
    assert len(summary) > 50,   f"summary too short ({len(summary)} chars): {summary!r}"

    stored = db.get_summary(session_id)
    assert stored == summary,   "stored summary does not match returned summary"

    print(f"  summary ({len(summary)} chars):")
    print(f"  {summary[:200].strip()!r}...")
    print("[TEST 3] PASSED")


# ── Runner ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("AstroMind -- Day 5 Integration Test")
    print("=" * 60)

    db = Database(db_path=TEST_DB_PATH)
    try:
        session_id = test_full_session(db)
        test_alert_written(session_id, db)
        test_summary_generated(session_id, db)

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED -- Sprint 1 backend complete")
        print("=" * 60)
        sys.exit(0)

    except AssertionError as e:
        print(f"\nASSERTION FAILED: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        raise

    finally:
        _cleanup(db)


if __name__ == "__main__":
    main()