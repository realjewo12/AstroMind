"""
orchestration/chain.py

The central orchestration layer for AstroMind.

AstroMindChain wires together:
  - knowledge/vectorstore.py   → RAG: similarity_search() injects NASA context
  - llm/prompts.py             → prompt construction
  - llm/client.py              → WatsonxLLM (Granite) singleton
  - orchestration/memory.py    → ConversationBufferMemory (session-scoped)
  - orchestration/output_parser.py → JSON extraction + Pydantic validation
  - core/mood_engine.py        → MoodEngine: wellness score + dual risk detection
  - core/coping.py             → CopeSelector: 3 evidence-based strategies per mood
  - data/database.py           → SQLite: messages, mood_scores, alerts persisted

Usage
-----
    from orchestration.chain import AstroMindChain

    chain = AstroMindChain(astronaut_id="cmdr-hayes")
    result = chain.chat("I haven't slept well")
    print(result.response.mood)          # "fatigued"
    print(result.report.wellness)        # 22
    print(result.report.risk.value)      # "low"
    print(result.strategies[0].name)     # "Strategic Nap"
    chain.close()                        # stamps session end time in DB
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List

from core.coping import CopeSelector, CopingStrategy
from core.mood_engine import MoodEngine, MoodReport, RiskLevel
from data.database import Database
from knowledge.vectorstore import similarity_search
from llm.client import get_llm
from llm.prompts import build_prompt
from orchestration.memory import ConversationMemory
from orchestration.output_parser import AstroMindOutputParser, AstroMindResponse


# ── ChatResult ─────────────────────────────────────────────────────────────────

@dataclass
class ChatResult:
    """
    The complete output of one AstroMindChain.chat() call.

    This is what the UI and test layer consume — never raw Granite JSON.

    Attributes
    ----------
    response    : AstroMindResponse   Granite's validated JSON output
    report      : MoodReport          Processed mood analysis (wellness, risk, flags)
    strategies  : List[CopingStrategy] 3 evidence-based coping techniques
    rag_used    : bool                 Whether NASA knowledge was injected this turn
    """
    response   : AstroMindResponse
    report     : MoodReport
    strategies : List[CopingStrategy] = field(default_factory=list)
    rag_used   : bool = False


# ── AstroMindChain ─────────────────────────────────────────────────────────────

class AstroMindChain:
    """
    Orchestrates one complete conversation session.

    One instance = one session. Create a new instance for each new user
    session (e.g., per Streamlit session_state entry).

    Parameters
    ----------
    session_id : str, optional
        Unique identifier for this session. Auto-generated as UUID4 if not supplied.
        Used as the SQLite primary key.
    astronaut_id : str, optional
        Identifier for the crew member. Stored in the sessions table.
    mission_context : str, optional
        Free-text description of the current mission phase.
        Injected into every prompt so Granite calibrates its responses.
    db : Database, optional
        Database instance. If not supplied, a default Database() is created.
        Pass a custom instance (e.g. in-memory) for testing.
    """

    def __init__(
        self,
        session_id: str | None = None,
        astronaut_id: str = "unknown",
        mission_context: str = "",
        db: Database | None = None,
    ):
        self.session_id     = session_id or str(uuid.uuid4())
        self.astronaut_id   = astronaut_id
        self.mission_context = mission_context

        # Collaborators
        self._llm      = get_llm()
        self._memory   = ConversationMemory(session_id=self.session_id)
        self._parser   = AstroMindOutputParser()
        self._engine   = MoodEngine()
        self._coping   = CopeSelector()
        self._db       = db or Database()

        # Register session in DB (INSERT OR IGNORE — safe to call multiple times)
        self._db.create_session(
            session_id    = self.session_id,
            astronaut_id  = self.astronaut_id,
            mission_phase = self.mission_context,
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def chat(self, user_message: str, use_rag: bool = True) -> ChatResult:
        """
        Send one user message and return a full ChatResult.

        Steps (in order):
          0. RAG: similarity_search() retrieves NASA chunks as context (if use_rag=True)
          1. Pull conversation history from memory
          2. Build the full prompt (system + RAG + history + format + user msg)
          3. Call Granite via LangChain's .invoke() (with retry)
          4. Parse + validate the raw response into AstroMindResponse
          5. Persist turn to in-memory conversation history
          6. Run MoodEngine to produce MoodReport (wellness, risk, flags)
          7. Run CopeSelector to get 3 coping strategies for the detected mood
          8. Write messages + mood_score to DB; write alert row if risk is HIGH
          9. Return ChatResult

        Parameters
        ----------
        user_message : str
            The raw text typed by the astronaut.
        use_rag : bool
            Whether to retrieve NASA knowledge context for this turn.
            Default True. Set False in tests or when prompt budget is tight.

        Returns
        -------
        ChatResult
            response   — validated AstroMindResponse from Granite
            report     — MoodReport with wellness score, risk level, flags
            strategies — 3 CopingStrategy objects for the detected mood
            rag_used   — True if NASA context was injected this turn

        Raises
        ------
        ValueError
            If the model returns text with no parseable JSON object after retries.
        pydantic.ValidationError
            If the JSON is found but a required field is missing or invalid.
        """
        turn = self._memory.turn_count()   # 0-based index for this turn

        # ── Step 0: RAG — retrieve NASA knowledge context ────────────────────
        # Cap at k=2 chunks, 300 chars each (~600 chars total) so the combined
        # prompt (system ~1800 + RAG ~600 + format ~200) stays well within
        # Granite 4h-small's reliable generation window.
        rag_docs    = similarity_search(user_message, k=2) if use_rag else []
        rag_used    = bool(rag_docs)
        rag_context = "\n\n".join(
            f"[{doc.metadata.get('source', 'NASA')}]\n{doc.page_content[:300]}"
            for doc in rag_docs
        ) if rag_docs else ""

        # ── Step 1: Retrieve conversation history ────────────────────────────
        history = self._memory.get_history_string()

        # ── Step 2: Build the full prompt ────────────────────────────────────
        format_instructions = self._parser.get_format_instructions()

        full_prompt = build_prompt(
            user_message   = user_message,
            context        = rag_context,
            mission_context = self.mission_context,
            chat_history   = history,
        ) + format_instructions

        # ── Step 3: Call Granite (with retry) ────────────────────────────────
        MAX_RETRIES = 3
        raw_response: str = ""
        for attempt in range(1, MAX_RETRIES + 1):
            raw_response = self._llm.invoke(full_prompt)
            if raw_response.strip():
                break
            if attempt < MAX_RETRIES:
                print(f"[AstroMindChain] Empty response on attempt {attempt}, retrying...")
        if not raw_response.strip():
            raise ValueError(
                f"Granite returned an empty response after {MAX_RETRIES} attempts. "
                "Check prompt length and model configuration."
            )

        # ── Step 4: Parse and validate ───────────────────────────────────────
        parsed: AstroMindResponse = self._parser.parse(raw_response)

        # ── Step 5: Persist turn to in-memory history ────────────────────────
        self._memory.add_turn(
            human_message = user_message,
            ai_message    = raw_response,
        )

        # ── Step 6: Mood analysis ─────────────────────────────────────────────
        report: MoodReport = self._engine.analyse(parsed)

        # ── Step 7: Coping strategies ─────────────────────────────────────────
        strategies = self._coping.for_mood(report.mood)

        # ── Step 8: Database writes ───────────────────────────────────────────
        # Human message
        self._db.insert_message(
            session_id = self.session_id,
            turn       = turn,
            role       = "human",
            content    = user_message,
        )
        # AI reply
        self._db.insert_message(
            session_id = self.session_id,
            turn       = turn,
            role       = "ai",
            content    = parsed.response,
        )
        # Mood score
        self._db.insert_mood_score(
            session_id = self.session_id,
            turn       = turn,
            mood       = report.mood,
            wellness   = report.wellness,
            risk_level = report.risk.value,
            raw_score  = report.raw_score,
            flags      = report.flags,
        )
        # Alert — only written when risk is HIGH
        if report.risk == RiskLevel.HIGH:
            self._db.insert_alert(
                session_id   = self.session_id,
                turn         = turn,
                trigger_text = user_message,
                flags        = report.flags,
            )

        # ── Step 9: Return ────────────────────────────────────────────────────
        return ChatResult(
            response   = parsed,
            report     = report,
            strategies = strategies,
            rag_used   = rag_used,
        )

    def close(self) -> None:
        """Stamp session end time in DB. Call when the session ends."""
        self._db.close_session(self.session_id)

    # ── Introspection helpers ──────────────────────────────────────────────────

    def turn_count(self) -> int:
        """How many complete turns have been exchanged this session."""
        return self._memory.turn_count()

    def reset(self) -> None:
        """Clear in-memory history. Does not affect DB rows already written."""
        self._memory.clear()
