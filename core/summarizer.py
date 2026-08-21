"""
core/summarizer.py

Generates a clinical session summary by sending the full conversation
transcript to Granite with a summarisation prompt, then stores the result
in the summaries table.

This is a separate chain from AstroMindChain.chat() — same LLM singleton,
different prompt register (third-person clinical, not first-person companion).

Public API
----------
    from core.summarizer import summarize_session

    summary = summarize_session(session_id, db)
    # Returns the summary string and stores it in summaries table.
"""

from __future__ import annotations

from data.database import Database
from llm.client import get_llm


# ── Summarisation prompt ───────────────────────────────────────────────────────

_SUMMARY_PROMPT_TEMPLATE = """\
You are a behavioral health observer reviewing a completed AstroMind session.
Your task is to write a concise clinical handover note for the flight surgeon.

The note must include:
1. Overall mood trajectory across the session (did it improve, worsen, or stay stable?)
2. The primary stressor or concern raised by the crew member
3. The highest risk level reached and whether any safety flags were raised
4. The coping strategies that were recommended
5. Any follow-up actions recommended for the next session

Write in plain clinical prose. Be factual and specific. Do not use bullet points.
Keep the summary to 150-200 words. Do not address the crew member directly.

Session transcript:
{transcript}

Clinical handover note:"""


# ── Transcript formatter ───────────────────────────────────────────────────────

def _format_transcript(messages: list) -> str:
    """
    Format a list of message dicts into a readable transcript string.

    Groups human + AI messages under [Turn N] headers so Granite
    sees a coherent conversation rather than a flat alternating list.
    """
    if not messages:
        return "No messages recorded."

    turns: dict = {}
    for msg in messages:
        t = msg["turn"]
        if t not in turns:
            turns[t] = {}
        role_label = "Crew Member" if msg["role"] == "human" else "AstroMind"
        turns[t][role_label] = msg["content"]

    lines = []
    for t in sorted(turns):
        lines.append(f"[Turn {t}]")
        for role_label, content in turns[t].items():
            lines.append(f"{role_label}: {content}")
        lines.append("")

    return "\n".join(lines).strip()


# ── Public API ─────────────────────────────────────────────────────────────────

def summarize_session(session_id: str, db: Database | None = None) -> str:
    """
    Generate and store a clinical summary for a completed session.

    Fetches all messages from the DB, builds a transcript, sends it to
    Granite with a clinical summarisation prompt, stores the result in
    the summaries table, and returns the text.

    Parameters
    ----------
    session_id : str
        The session to summarise. Must already exist in the DB.
    db : Database, optional
        Database instance. Defaults to a new Database(). Pass the same
        instance used by AstroMindChain to share the DB connection in tests.

    Returns
    -------
    str
        The generated summary text (also stored in summaries table).
        Never empty — returns a fallback string if Granite gives no output.
    """
    _db = db or Database()
    messages = _db.get_messages(session_id)

    if not messages:
        summary = "No messages recorded for this session."
        _db.insert_summary(session_id, summary)
        return summary

    transcript = _format_transcript(messages)
    prompt     = _SUMMARY_PROMPT_TEMPLATE.format(transcript=transcript)

    llm     = get_llm()
    summary = llm.invoke(prompt).strip()

    if not summary:
        summary = "Summary could not be generated — model returned empty response."

    _db.insert_summary(session_id, summary)
    return summary