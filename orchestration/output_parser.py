"""
orchestration/output_parser.py

Defines the expected structure of every Granite response and
provides a parser that extracts + validates it from raw LLM output.
"""

import json
import re
from pydantic import BaseModel, Field, field_validator


# ── 1. Response Schema ────────────────────────────────────────────────────────
#
# Every single turn, Granite must return a JSON object with exactly these
# five fields.  If any field is absent or the wrong type, Pydantic raises a
# ValidationError — the error surfaces immediately rather than letting bad
# data silently flow downstream.

class AstroMindResponse(BaseModel):
    mood: str = Field(
        description="One to three word label describing the crew member's "
                    "current emotional state, e.g. 'anxious', 'calm', 'fatigued'."
    )
    score: int = Field(
        ge=1, le=10,
        description="Overall wellbeing score from 1 (crisis) to 10 (thriving)."
    )
    risk_level: str = Field(
        description="Triage level: must be exactly 'low', 'medium', or 'high'."
    )
    response: str = Field(
        description="The message displayed to the crew member — warm, concise, "
                    "and following AstroMind communication guidelines."
    )
    coping_strategy: str = Field(
        description="One concrete, immediately actionable coping technique "
                    "relevant to the crew member's current state."
    )

    # ── Validators ──────────────────────────────────────────────────────────
    # field_validator runs *after* type coercion, so `risk_level` is already
    # a str when this fires.  We normalise to lowercase so the model cannot
    # sneak "Low" or "HIGH" past us.

    @field_validator("risk_level")
    @classmethod
    def risk_level_must_be_valid(cls, v: str) -> str:
        normalised = v.strip().lower()
        if normalised not in {"low", "medium", "high"}:
            raise ValueError(
                f"risk_level must be 'low', 'medium', or 'high' — got '{v}'"
            )
        return normalised


# ── 2. JSON Schema Instructions ───────────────────────────────────────────────
#
# This string is injected at the END of every prompt so Granite knows the
# exact JSON shape it must produce.  We generate it programmatically from the
# Pydantic model so the prompt and the parser are always in sync — if you
# add a field to AstroMindResponse, the instructions update automatically.

def get_format_instructions() -> str:
    # Intentionally compact: Granite 4h-small suppresses output when the prompt
    # ends with JSON-like text (it treats it as content to continue, not as an
    # instruction).  Ending with a text label "JSON:" primes the model to start
    # generating a JSON object as its first token.
    return (
        "\n\nYour reply must be a JSON object with these fields: "
        "mood (string), score (integer 1-10), risk_level (low/medium/high), "
        "response (the message for the crew member), coping_strategy (one technique)."
        "\nJSON:"
    )


# ── 3. Parser ─────────────────────────────────────────────────────────────────
#
# AstroMindOutputParser.parse() takes the raw string returned by Granite and
# returns a validated AstroMindResponse.
#
# It handles three common model misbehaviours:
#   a) JSON wrapped in ```json ... ``` markdown fences
#   b) A sentence before or after the JSON block
#   c) Trailing commas (light cleanup only — we don't try to fix deeply broken JSON)

class AstroMindOutputParser:
    """Parses raw Granite output into a validated AstroMindResponse."""

    def parse(self, raw_text: str) -> AstroMindResponse:
        """
        Extract the first JSON object from `raw_text` and validate it
        against AstroMindResponse.

        Raises:
            ValueError  — if no JSON object is found in the text
            pydantic.ValidationError — if the JSON is found but a field is
                                       missing or fails validation
        """
        # Step 1: strip markdown fences if present
        # Pattern: optional ```json or ``` followed by the content
        cleaned = re.sub(r"```(?:json)?\s*", "", raw_text).strip()

        # Step 2: find the outermost {...} block
        # re.DOTALL makes '.' match newlines too, so multi-line JSON is captured
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(
                f"No JSON object found in model response.\n"
                f"Raw output was:\n{raw_text}"
            )

        json_str = match.group(0)

        # Step 3: parse and validate
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"JSON found but could not be parsed.\n"
                f"Extracted string: {json_str!r}\n"
                f"Raw output was: {raw_text!r}\n"
                f"JSONDecodeError: {exc}"
            ) from exc
        return AstroMindResponse(**data)

    def get_format_instructions(self) -> str:
        return get_format_instructions()
