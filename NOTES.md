# AstroMind — Session Notes

## Status: Day 1 Complete ✅

### What was built
- `llm/__init__.py` — package marker
- `llm/client.py` — WatsonxLLM wrapper (langchain-ibm, pydantic.v1 SecretStr, cached singleton)
- `llm/prompts.py` — 5-section system prompt + build_prompt() with RAG + mission context slots
- `test_llm.py` — throwaway test script, confirmed working

### Key decisions made
- Model: `ibm/granite-4-h-small` (Frankfurt region, eu-de endpoint)
- FLAG system added to prompt for behavioral health reporting
- mission_context and context injected dynamically in build_prompt(), NOT in SYSTEM_PROMPT string
- Reporting layer planned for Day 5 (after database is ready)

### Bugs encountered — Day 1
- Wrong import path: `ibm_watsonx_ai.langchain` → correct: `from langchain_ibm import WatsonxLLM`
- Typo in env var: `WATSONX-URL` (hyphen) → correct: `WATSONX_URL` (underscore)
- `WatsonxLLM` does not accept a `Credentials` object → pass `url=` and `apikey=` directly
- `os.getenv()` returns `str | None` → use `os.environ[]` + validate at startup
- `url` and `apikey` require `SecretStr` from `pydantic.v1`, not plain `str`

---

## Status: Day 2 — Not started

### Goal
LangChain Orchestration — Memory + Chain + Parser
Multi-turn conversation works, Granite returns validated JSON every time.

### Files to create
- `orchestration/__init__.py` — package marker
- `orchestration/memory.py` — ConversationBufferMemory, session-scoped
- `orchestration/output_parser.py` — Pydantic model: {mood, score, risk_level, response, coping_strategy} + StructuredOutputParser
- `orchestration/chain.py` — wire memory + prompt + Granite LLM + parser into one LangChain chain
- `test_chain.py` — send 3 back-to-back messages, confirm memory carries context

### Key design decisions for Day 2
- Output is structured JSON on every turn — not free text
- Memory is session-scoped (lives in RAM, not database — persistence comes Day 3)
- Parser uses Pydantic to validate every response field before it reaches the app
- Chain wires: SYSTEM_PROMPT → memory → user message → Granite → parser

### Day 2 success criteria
- 3 consecutive messages remember prior context
- Every response is valid JSON with all 5 fields: mood, score, risk_level, response, coping_strategy
- No free-text responses leak through the parser

### Day 3 preview
- SQLite database to persist sessions across restarts
- FLAGS from Day 1 prompt get stored as structured rows
- Files: `db/database.py`, `db/models.py`