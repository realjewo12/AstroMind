"""
core/mood_engine.py

Processes a raw AstroMindResponse from Granite into a structured MoodReport
with a normalised wellness score (0-100), a final risk level (LOW/MEDIUM/HIGH),
and any safety flags raised by the keyword scanner.

Public API
----------
    from core.mood_engine import MoodEngine, MoodReport, RiskLevel

    engine = MoodEngine()
    report = engine.analyse(astromind_response)
    print(report.wellness)    # 0-100
    print(report.risk)        # RiskLevel.LOW / MEDIUM / HIGH
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from orchestration.output_parser import AstroMindResponse


# ── Risk level enum ────────────────────────────────────────────────────────────

class RiskLevel(Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# ── Output dataclass ───────────────────────────────────────────────────────────

@dataclass
class MoodReport:
    """
    Application-level mood assessment produced by MoodEngine.
    Consumed by the UI and reporting layer — never raw Granite JSON.

    Attributes
    ----------
    mood      : str        Mood label from Granite, e.g. "anxious"
    wellness  : int        Normalised score 0-100 (Granite's 1-10 scaled up)
    risk      : RiskLevel  Final risk level after dual detection
    flags     : List[str]  Keywords that triggered a safety escalation, if any
    raw_score : int        Original Granite score 1-10, preserved for logging
    """
    mood      : str
    wellness  : int
    risk      : RiskLevel
    flags     : List[str] = field(default_factory=list)
    raw_score : int        = 0


# ── Safety keyword scanner ─────────────────────────────────────────────────────
#
# Any match forces risk to HIGH regardless of what Granite returned.
# Phrases are lowercase; the scanner lowercases input before matching.
# Conservative by design — false positives are safer than false negatives
# in a psychological safety system.

_HIGH_RISK_KEYWORDS: List[str] = [
    # Self-harm / suicidal ideation
    "don't want to be here",
    "don't want to live",
    "end it all",
    "hurt myself",
    "harm myself",
    "kill myself",
    "suicide",
    "no reason to continue",
    # Severe psychological break
    "can't go on",
    "completely hopeless",
    "nothing matters",
    "give up on everything",
    # Immediate danger signals
    "emergency",
    "serious accident",
    "critical failure",
]


# ── Engine ─────────────────────────────────────────────────────────────────────

class MoodEngine:
    """
    Analyses an AstroMindResponse and produces a MoodReport.

    Usage
    -----
        engine = MoodEngine()
        report = engine.analyse(response)
    """

    def analyse(self, response: AstroMindResponse, user_message: str = "") -> MoodReport:
        """Full pipeline: score normalise → keyword scan → risk classify → MoodReport.

        Parameters
        ----------
        response     : AstroMindResponse  Granite's validated output
        user_message : str                The astronaut's raw message — scanned for
                                          crisis keywords. Falls back to response.response
                                          if not supplied (backwards compatible).
        """
        wellness = self._to_wellness(response.score)
        # Scan the astronaut's message — that's where crisis phrases appear,
        # not in the AI's reply.
        scan_target = user_message if user_message else response.response
        flags    = self._scan_keywords(scan_target)
        risk     = self._classify_risk(response.risk_level, flags)

        return MoodReport(
            mood      = response.mood.lower().strip(),
            wellness  = wellness,
            risk      = risk,
            flags     = flags,
            raw_score = response.score,
        )

    @staticmethod
    def _to_wellness(granite_score: int) -> int:
        """
        Map Granite's 1-10 score to 0-100.
        Formula: round((score - 1) / 9 * 100)
        1->0, 5->44, 8->78, 10->100
        """
        return round((granite_score - 1) / 9 * 100)

    @staticmethod
    def _scan_keywords(text: str) -> List[str]:
        """Return high-risk keyword phrases found in text. Empty = no flags."""
        lowered = text.lower()
        return [kw for kw in _HIGH_RISK_KEYWORDS if kw in lowered]

    @staticmethod
    def _classify_risk(granite_level: str, flags: List[str]) -> RiskLevel:
        """
        Dual detection — keyword scanner can only raise the level, never lower it.

        flags present       → HIGH  (override)
        no flags + granite  → map granite_level directly
        unknown level       → MEDIUM (safe default)
        """
        if flags:
            return RiskLevel.HIGH

        return {
            "low":    RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high":   RiskLevel.HIGH,
        }.get(granite_level.lower(), RiskLevel.MEDIUM)