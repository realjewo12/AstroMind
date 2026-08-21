"""
test_chain.py -- Day 2 integration test

Sends 3 back-to-back messages through AstroMindChain and verifies:
  1. Every response has all 5 required fields
  2. score is between 1 and 10
  3. risk_level is one of low / medium / high
  4. Memory carries context (turn_count grows correctly)

Run with:
    python test_chain.py
"""

import sys
from orchestration.chain import AstroMindChain
from orchestration.output_parser import AstroMindResponse

# -- Test messages -------------------------------------------------------------
# Message 3 deliberately references "three nights" from message 1 without
# repeating it.  If memory is working, Granite should connect the dots.

MESSAGES = [
    "I haven't been able to sleep properly for three nights now.",
    "My bunkmate's breathing sounds bother me at night -- I feel bad even saying that.",
    "Given everything I've told you, do you think this is getting serious?",
]

MISSION_CONTEXT = (
    "Day 214 of Mars transit. Low operational tempo -- no EVA scheduled this week. "
    "The crew is in a maintenance and rest rotation."
)

# -- Helpers -------------------------------------------------------------------

VALID_RISK_LEVELS = {"low", "medium", "high"}

def print_separator(char="-", width=70):
    print(char * width)

def print_response(turn, user_msg, r):
    print_separator("=")
    print("  TURN %d" % turn)
    print_separator("-")
    print("  User  : %s" % user_msg)
    print("  Mood  : %s" % r.mood)
    print("  Score : %d/10" % r.score)
    print("  Risk  : %s" % r.risk_level)
    print("  Cope  : %s" % r.coping_strategy)
    snippet = r.response[:200] + ("..." if len(r.response) > 200 else "")
    print("  Reply :\n    %s" % snippet)

def assert_response(r, turn):
    """
    Hard assertions -- if any of these fail the test exits with code 1.
    These mirror the Day 2 success criteria from NOTES.md.
    """
    errors = []

    if not r.mood or not isinstance(r.mood, str):
        errors.append("'mood' is empty or not a string")

    if not isinstance(r.score, int) or not (1 <= r.score <= 10):
        errors.append("'score' out of range: %r" % r.score)

    if r.risk_level not in VALID_RISK_LEVELS:
        errors.append("'risk_level' invalid: %r" % r.risk_level)

    if not r.response or not isinstance(r.response, str):
        errors.append("'response' is empty or not a string")

    if not r.coping_strategy or not isinstance(r.coping_strategy, str):
        errors.append("'coping_strategy' is empty or not a string")

    if errors:
        print("\n  TURN %d FAILED:" % turn)
        for e in errors:
            print("     * %s" % e)
        sys.exit(1)
    else:
        print("  [PASS] All 5 fields valid")

# -- Main ----------------------------------------------------------------------

def main():
    print("\n" + "=" * 70)
    print("  AstroMind -- Day 2 Chain Integration Test")
    print("=" * 70)

    chain = AstroMindChain(
        session_id="test-session-day2",
        mission_context=MISSION_CONTEXT,
    )

    for i, message in enumerate(MESSAGES, start=1):
        print("\n  --> Sending turn %d to Granite..." % i)
        result = chain.chat(message)

        print_response(turn=i, user_msg=message, r=result)
        assert_response(r=result, turn=i)

        expected_turns = i
        actual_turns = chain.turn_count()
        if actual_turns != expected_turns:
            print("\n  [FAIL] turn_count() expected %d, got %d" % (expected_turns, actual_turns))
            sys.exit(1)
        print("  [MEM]  %d turn(s) recorded in memory" % actual_turns)

    print_separator("=")
    print("  [ALL PASS] 3 turns -- memory, JSON shape, and field validation OK")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
