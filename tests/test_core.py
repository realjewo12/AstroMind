"""
test_core.py

Unit tests for the Day 4 AI Core layer.
No LLM calls — AstroMindResponse objects are constructed manually.

Tests
-----
1. calm / score=9 / risk=low    -> LOW risk, wellness=89, calm strategies
2. anxious / score=4 / medium   -> MEDIUM risk, wellness=33, anxious strategies
3. fatigued / score=3 / low     -> LOW risk, wellness=22, fatigued strategies
4. unknown mood 'melancholic'   -> default coping fallback (no crash)
5. keyword override             -> Granite=medium + crisis phrase -> HIGH + flags
"""

import sys
from orchestration.output_parser import AstroMindResponse
from core.mood_engine import MoodEngine, MoodReport, RiskLevel
from core.coping import CopeSelector, CopingStrategy

# ── Shared fixtures ────────────────────────────────────────────────────────────

engine   = MoodEngine()
selector = CopeSelector()


def make_response(
    mood: str,
    score: int,
    risk_level: str,
    response: str = "I hear you.",
    coping_strategy: str = "Take a breath.",
) -> AstroMindResponse:
    """Build an AstroMindResponse without calling Granite."""
    return AstroMindResponse(
        mood=mood,
        score=score,
        risk_level=risk_level,
        response=response,
        coping_strategy=coping_strategy,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_calm_low_risk():
    print("\n[TEST 1] calm / score=9 / risk=low")

    resp   = make_response(mood="calm", score=9, risk_level="low")
    report = engine.analyse(resp)

    assert report.mood     == "calm",         f"mood: {report.mood}"
    assert report.wellness == 89,             f"wellness: {report.wellness}"
    assert report.risk     == RiskLevel.LOW,  f"risk: {report.risk}"
    assert report.flags    == [],             f"flags: {report.flags}"

    strategies = selector.for_mood(report.mood)
    assert len(strategies) == 3,             f"expected 3 strategies, got {len(strategies)}"
    assert all(isinstance(s, CopingStrategy) for s in strategies)

    print(f"  wellness={report.wellness}, risk={report.risk.value}")
    print(f"  strategies: {[s.name for s in strategies]}")
    print("[TEST 1] PASSED")


def test_anxious_medium_risk():
    print("\n[TEST 2] anxious / score=4 / risk=medium")

    resp   = make_response(mood="anxious", score=4, risk_level="medium")
    report = engine.analyse(resp)

    assert report.mood     == "anxious",          f"mood: {report.mood}"
    assert report.wellness == 33,                 f"wellness: {report.wellness}"
    assert report.risk     == RiskLevel.MEDIUM,   f"risk: {report.risk}"
    assert report.flags    == [],                 f"flags: {report.flags}"

    strategies = selector.for_mood(report.mood)
    assert len(strategies) == 3
    assert any("Breathing" in s.name for s in strategies), \
        "Expected Box Breathing in anxious strategies"

    print(f"  wellness={report.wellness}, risk={report.risk.value}")
    print(f"  strategies: {[s.name for s in strategies]}")
    print("[TEST 2] PASSED")


def test_fatigued_low_wellness():
    print("\n[TEST 3] fatigued / score=3 / risk=low")

    resp   = make_response(mood="fatigued", score=3, risk_level="low")
    report = engine.analyse(resp)

    assert report.wellness == 22,            f"wellness: {report.wellness}"
    assert report.risk     == RiskLevel.LOW, f"risk: {report.risk}"

    strategies = selector.for_mood(report.mood)
    assert any("Nap" in s.name for s in strategies), \
        "Expected Strategic Nap in fatigued strategies"

    print(f"  wellness={report.wellness}, risk={report.risk.value}")
    print(f"  strategies: {[s.name for s in strategies]}")
    print("[TEST 3] PASSED")


def test_unknown_mood_default_coping():
    print("\n[TEST 4] unknown mood 'melancholic' -> default coping fallback")

    resp   = make_response(mood="melancholic", score=5, risk_level="medium")
    report = engine.analyse(resp)

    strategies = selector.for_mood(report.mood)
    assert len(strategies) == 3, f"expected 3 strategies, got {len(strategies)}"
    assert any("Breathing" in s.name for s in strategies), \
        "Expected Mindful Breathing in default strategies"

    print(f"  mood='{report.mood}' not in table -> default strategies returned")
    print(f"  strategies: {[s.name for s in strategies]}")
    print("[TEST 4] PASSED")


def test_keyword_overrides_granite_risk():
    print("\n[TEST 5] keyword override: Granite=medium + crisis keyword -> HIGH")

    resp = make_response(
        mood       = "distressed",
        score      = 2,
        risk_level = "medium",
        response   = "I just can't go on like this.",
    )
    report = engine.analyse(resp)

    assert report.risk     == RiskLevel.HIGH, f"risk should be HIGH, got {report.risk}"
    assert len(report.flags) > 0,            f"flags should be non-empty, got {report.flags}"
    assert "can't go on" in report.flags,    f"expected flag not found: {report.flags}"
    assert report.wellness == 11,            f"wellness: {report.wellness}"

    print(f"  Granite said: medium | keyword found: {report.flags}")
    print(f"  Final risk: {report.risk.value} (keyword won)")
    print("[TEST 5] PASSED")


# ── Runner ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("AstroMind -- Day 4 Core Layer Test")
    print("=" * 60)

    try:
        test_calm_low_risk()
        test_anxious_medium_risk()
        test_fatigued_low_wellness()
        test_unknown_mood_default_coping()
        test_keyword_overrides_granite_risk()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)

    except AssertionError as e:
        print(f"\nASSERTION FAILED: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        raise


if __name__ == "__main__":
    main()