"""
orchestration/chain.py

The central orchestration layer for AstroMind.

AstroMindChain wires together:
  - llm/prompts.py       → prompt construction (system prompt + history + user message)
  - llm/client.py        → WatsonxLLM (Granite) singleton
  - orchestration/memory.py        → ConversationBufferMemory (session-scoped)
  - orchestration/output_parser.py → JSON extraction + Pydantic validation

Usage
-----
    from orchestration.chain import AstroMindChain

    chain = AstroMindChain()                    # one chain per session
    result = chain.chat("I haven't slept well") # returns AstroMindResponse
    print(result.mood)                          # "fatigued"
    print(result.score)                         # 4
    print(result.response)                      # the message shown to the astronaut
"""

import uuid
from llm.client import get_llm
from llm.prompts import build_prompt
from orchestration.memory import ConversationMemory
from orchestration.output_parser import AstroMindOutputParser, AstroMindResponse


class AstroMindChain:
    """
    Orchestrates one complete conversation session.

    One instance = one session.  Create a new instance for each new user
    session (e.g., per Streamlit session_state entry).

    Parameters
    ----------
    session_id : str, optional
        Unique identifier for this session.  Auto-generated as a UUID4
        if not supplied.  Will become the SQLite primary key on Day 3.
    mission_context : str, optional
        Free-text description of the current mission phase, e.g.:
        "Day 187 of Mars transit. EVA scheduled in 36 hours."
        Injected into every prompt so Granite calibrates its responses
        to operational significance.
    """

    def __init__(
        self,
        session_id: str | None = None,
        mission_context: str = "",
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.mission_context = mission_context

        # Instantiate collaborators
        self._llm = get_llm()
        self._memory = ConversationMemory(session_id=self.session_id)
        self._parser = AstroMindOutputParser()

    # ── Public API ────────────────────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        rag_context: str = "",
    ) -> AstroMindResponse:
        """
        Send one user message and return a validated AstroMindResponse.

        Steps (in order):
          1. Pull conversation history from memory
          2. Build the full prompt string (system + history + JSON instructions + user msg)
          3. Call Granite via LangChain's .invoke()
          4. Parse + validate the raw response into AstroMindResponse
          5. Persist this turn to memory so future calls have context
          6. Return the typed response object

        Parameters
        ----------
        user_message : str
            The raw text typed by the astronaut.
        rag_context : str, optional
            Retrieved document chunks from the knowledge base (Day 4).
            Empty string = no RAG context injected this turn.

        Returns
        -------
        AstroMindResponse
            Validated object with: mood, score, risk_level, response, coping_strategy

        Raises
        ------
        ValueError
            If the model returns text with no parseable JSON object.
        pydantic.ValidationError
            If the JSON is found but a field is missing or invalid.
        """

        # ── Step 1: Retrieve conversation history ────────────────────────────
        history = self._memory.get_history_string()

        # ── Step 2: Build the full prompt ────────────────────────────────────
        # get_format_instructions() returns the JSON schema block that tells
        # Granite exactly what shape its response must be.
        format_instructions = self._parser.get_format_instructions()

        full_prompt = build_prompt(
            user_message=user_message,
            context=rag_context,
            mission_context=self.mission_context,
            chat_history=history,
        ) + format_instructions
        # Why append format_instructions here instead of inside build_prompt()?
        # Because format_instructions are a parser concern, not a prompt concern.
        # build_prompt() knows nothing about the output format — that separation
        # means on Day 4 (RAG) we can swap the parser without touching prompts.py.

        # ── Step 3: Call Granite (with retry) ───────────────────────────────
        # Granite 4h-small occasionally returns an empty string on long
        # structured prompts.  We retry up to 3 times before giving up.
        # This is a known Granite 4h-small behaviour on watsonx (non-deterministic
        # empty responses at the boundary of its comfortable prompt length).
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

        # ── Step 5: Persist turn to memory ───────────────────────────────────
        # We store the raw text (not the parsed object) because memory will
        # format it as "AstroMind: <text>" in the history string.
        # The next turn's prompt will include this line verbatim, so Granite
        # can see what it said before.
        self._memory.add_turn(
            human_message=user_message,
            ai_message=raw_response,
        )

        # ── Step 6: Return typed response ────────────────────────────────────
        return parsed

    # ── Introspection helpers ─────────────────────────────────────────────────

    def turn_count(self) -> int:
        """How many complete turns have been exchanged this session."""
        return self._memory.turn_count()

    def reset(self) -> None:
        """Clear memory and start a fresh session with the same session_id."""
        self._memory.clear()
