"""
core/coping.py

Lookup table mapping mood labels to evidence-based coping strategies.
All strategies are grounded in CBT, ACT, and NASA/HRP crew countermeasures.

Public API
----------
    from core.coping import CopeSelector

    selector  = CopeSelector()
    strategies = selector.for_mood("anxious")   # List[CopingStrategy], always 3 items
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


# ── Strategy dataclass ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CopingStrategy:
    """
    A single evidence-based coping technique.

    frozen=True — strategies are constants, never mutated after creation.
    """
    name          : str
    description   : str
    duration      : str
    evidence_base : str


# ── Lookup table ───────────────────────────────────────────────────────────────

_COPING_TABLE: Dict[str, List[CopingStrategy]] = {

    "anxious": [
        CopingStrategy(
            name          = "Box Breathing",
            description   = "Inhale 4 counts, hold 4, exhale 4, hold 4 — repeat 4 cycles.",
            duration      = "2 minutes",
            evidence_base = "CBT / autonomic regulation",
        ),
        CopingStrategy(
            name          = "Grounding - 5-4-3-2-1",
            description   = "Name 5 things you see, 4 you can touch, 3 you hear, 2 you smell, 1 you taste.",
            duration      = "3 minutes",
            evidence_base = "CBT / sensory anchoring",
        ),
        CopingStrategy(
            name          = "Cognitive Reframe",
            description   = "Write the anxious thought, then write one realistic counter-statement.",
            duration      = "5 minutes",
            evidence_base = "CBT / cognitive restructuring",
        ),
    ],

    "fatigued": [
        CopingStrategy(
            name          = "Strategic Nap",
            description   = "Set a 20-minute timer, dim lights, lie still — even light rest restores alertness.",
            duration      = "20 minutes",
            evidence_base = "NASA fatigue countermeasures / sleep science",
        ),
        CopingStrategy(
            name          = "Hydration + Posture Reset",
            description   = "Drink 250ml water, stand, roll shoulders back, take 5 slow breaths.",
            duration      = "2 minutes",
            evidence_base = "HRP performance countermeasures",
        ),
        CopingStrategy(
            name          = "Micro-Movement Break",
            description   = "5 minutes of light stretching or walking — breaks cortisol buildup from sustained focus.",
            duration      = "5 minutes",
            evidence_base = "HRP / exercise physiology",
        ),
    ],

    "stressed": [
        CopingStrategy(
            name          = "Progressive Muscle Relaxation",
            description   = "Tense each muscle group for 5 seconds then release, starting from feet upward.",
            duration      = "8 minutes",
            evidence_base = "CBT / somatic relaxation",
        ),
        CopingStrategy(
            name          = "Priority Triage",
            description   = "List every active stressor, mark each as (a) urgent+important or (b) everything else. Do only (a) today.",
            duration      = "5 minutes",
            evidence_base = "Crew resource management",
        ),
        CopingStrategy(
            name          = "Controlled Ventilation",
            description   = "Breathe in for 4 counts, out for 6 — the longer exhale activates the parasympathetic system.",
            duration      = "3 minutes",
            evidence_base = "CBT / autonomic regulation",
        ),
    ],

    "isolated": [
        CopingStrategy(
            name          = "Scheduled Earth Contact",
            description   = "Write or record a message to one person you miss — even unsent, the act reduces isolation.",
            duration      = "10 minutes",
            evidence_base = "HRP behavioral health / social support",
        ),
        CopingStrategy(
            name          = "Crew Connection Moment",
            description   = "Initiate one non-task interaction with a crewmate — a shared meal, a question, a small favour.",
            duration      = "15 minutes",
            evidence_base = "HRP / interpersonal support",
        ),
        CopingStrategy(
            name          = "Values Journaling",
            description   = "Write 3 sentences about why this mission matters to you personally.",
            duration      = "5 minutes",
            evidence_base = "ACT / values clarification",
        ),
    ],

    "depressed": [
        CopingStrategy(
            name          = "Behavioural Activation",
            description   = "Do one small, completable task right now — completion triggers dopamine regardless of mood.",
            duration      = "10 minutes",
            evidence_base = "CBT / behavioural activation",
        ),
        CopingStrategy(
            name          = "Light Exposure",
            description   = "Sit near the brightest light source available for 10 minutes — regulates circadian rhythm and mood.",
            duration      = "10 minutes",
            evidence_base = "NASA circadian countermeasures",
        ),
        CopingStrategy(
            name          = "Self-Compassion Pause",
            description   = "Place one hand on your chest and say: 'This is a hard moment. I am doing my best.'",
            duration      = "2 minutes",
            evidence_base = "ACT / self-compassion",
        ),
    ],

    "calm": [
        CopingStrategy(
            name          = "Mindful Observation",
            description   = "Spend 5 minutes observing your environment with full attention — reinforce present-moment awareness.",
            duration      = "5 minutes",
            evidence_base = "ACT / mindfulness",
        ),
        CopingStrategy(
            name          = "Gratitude Log",
            description   = "Write 3 specific things that went well today and why.",
            duration      = "5 minutes",
            evidence_base = "Positive psychology / CBT",
        ),
        CopingStrategy(
            name          = "Skill Practice",
            description   = "Use this calm window to rehearse one mission skill or review a procedure you want to strengthen.",
            duration      = "15 minutes",
            evidence_base = "Crew resource management",
        ),
    ],

    "overwhelmed": [
        CopingStrategy(
            name          = "Single-Task Reset",
            description   = "Close or set aside everything except one task. Do only that for 25 minutes.",
            duration      = "25 minutes",
            evidence_base = "Crew resource management / cognitive load",
        ),
        CopingStrategy(
            name          = "Box Breathing",
            description   = "Inhale 4 counts, hold 4, exhale 4, hold 4 — repeat 4 cycles.",
            duration      = "2 minutes",
            evidence_base = "CBT / autonomic regulation",
        ),
        CopingStrategy(
            name          = "Offload Writing",
            description   = "Dump every active concern onto paper — externalising reduces working memory load immediately.",
            duration      = "5 minutes",
            evidence_base = "CBT / cognitive offloading",
        ),
    ],

    "angry": [
        CopingStrategy(
            name          = "Physiological Sigh",
            description   = "Double inhale through the nose (two quick sniffs), then one long slow exhale — fastest known method to reduce acute arousal.",
            duration      = "1 minute",
            evidence_base = "Stanford neuroscience / autonomic regulation",
        ),
        CopingStrategy(
            name          = "Cooling-Off Period",
            description   = "Move to a different area of the habitat for 10 minutes before re-engaging with the trigger.",
            duration      = "10 minutes",
            evidence_base = "Crew resource management / conflict de-escalation",
        ),
        CopingStrategy(
            name          = "Perspective Reframe",
            description   = "Ask: will this matter in 6 months? Write one sentence about the other person's likely intent.",
            duration      = "3 minutes",
            evidence_base = "CBT / cognitive restructuring",
        ),
    ],

    "default": [
        CopingStrategy(
            name          = "Mindful Breathing",
            description   = "Focus attention on the breath for 5 minutes — inhale slowly, exhale slowly.",
            duration      = "5 minutes",
            evidence_base = "ACT / mindfulness",
        ),
        CopingStrategy(
            name          = "Body Scan",
            description   = "Mentally scan from head to toe, noting any tension and consciously releasing it.",
            duration      = "5 minutes",
            evidence_base = "CBT / somatic awareness",
        ),
        CopingStrategy(
            name          = "Reflective Journaling",
            description   = "Write freely for 5 minutes about what you're experiencing right now.",
            duration      = "5 minutes",
            evidence_base = "CBT / expressive writing",
        ),
    ],
}


# ── Selector ───────────────────────────────────────────────────────────────────

class CopeSelector:
    """
    Maps a mood label to 3 evidence-based coping strategies.

    Usage
    -----
        selector   = CopeSelector()
        strategies = selector.for_mood("anxious")
    """

    def for_mood(self, mood: str) -> List[CopingStrategy]:
        """
        Return 3 coping strategies for the given mood label.

        Case-insensitive. Unknown moods fall back to "default" — never raises.

        Parameters
        ----------
        mood : str
            Mood label from MoodReport.mood, e.g. "anxious", "fatigued".

        Returns
        -------
        List[CopingStrategy]
            Always exactly 3 strategies.
        """
        key = mood.lower().strip()
        return _COPING_TABLE.get(key, _COPING_TABLE["default"])