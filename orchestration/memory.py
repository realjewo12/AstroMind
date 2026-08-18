"""
orchestration/memory.py

Wraps LangChain's ConversationBufferMemory to provide a clean, session-scoped
conversation history store.

Session-scoped means: one ConversationMemory instance is created per user
session (e.g., per Streamlit session_state key).  It lives only in RAM.
Day 3 will add database persistence so sessions survive restarts.
"""

from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage


class ConversationMemory:
    """
    A thin wrapper around ConversationBufferMemory.

    Why wrap it instead of using it directly?
    - Gives us a stable API we can change internally without touching chain.py
    - Lets us add database persistence on Day 3 in one place
    - Keeps session metadata (session_id, astronaut_id) co-located with the history

    Attributes
    ----------
    session_id : str
        Unique identifier for this conversation session.
        Will be used as the primary key when we persist to SQLite on Day 3.
    _memory : ConversationBufferMemory
        The underlying LangChain memory object.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # memory_key="chat_history" tells LangChain to store the formatted
        # history string under the key "chat_history" when you call
        # load_memory_variables().  We'll inject this into prompts manually.
        #
        # return_messages=True means load_memory_variables() returns a list of
        # HumanMessage / AIMessage objects rather than a single flat string.
        # We set it to False here because build_prompt() in llm/prompts.py
        # expects a plain string — we do the formatting ourselves below.
        self._memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=False,   # return a flat string, not a message list
            human_prefix="Crew Member",
            ai_prefix="AstroMind",
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def add_turn(self, human_message: str, ai_message: str) -> None:
        """
        Append one completed conversation turn (a Human message + AI reply)
        to the history buffer.

        Call this AFTER you have received and validated the AI response.
        """
        self._memory.save_context(
            inputs={"input": human_message},
            outputs={"output": ai_message},
        )

    def get_history_string(self) -> str:
        """
        Return the entire conversation history as a plain formatted string,
        ready to be injected into the next prompt.

        Returns an empty string if no turns have been recorded yet.

        Example output:
            Crew Member: I've been struggling to sleep.
            AstroMind: {"mood": "fatigued", ...}
            Crew Member: It's been three nights now.
            AstroMind: {"mood": "fatigued", ...}
        """
        variables = self._memory.load_memory_variables({})
        return variables.get("chat_history", "")

    def clear(self) -> None:
        """
        Wipe the conversation history.  Useful for starting a new session
        without creating a new ConversationMemory object.
        """
        self._memory.clear()

    def turn_count(self) -> int:
        """
        Return how many complete (Human, AI) turns are in the buffer.
        Useful for logging and for Day 3 database writes.
        """
        # chat_memory.messages is the raw list — alternating Human, AI entries
        return len(self._memory.chat_memory.messages) // 2
