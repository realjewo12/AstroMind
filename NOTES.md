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

## Status: Day 2 Complete ✅

### Goal
LangChain Orchestration — Memory + Chain + Parser
Multi-turn conversation works, Granite returns validated JSON every time.

### Files created
- `orchestration/__init__.py` — package marker
- `orchestration/memory.py` — ConversationBufferMemory, session-scoped
- `orchestration/output_parser.py` — Pydantic v2 model: {mood, score, risk_level, response, coping_strategy} + AstroMindOutputParser
- `orchestration/chain.py` — AstroMindChain: wires memory + prompt + Granite LLM + parser
- `test_chain.py` — 3-turn conversation test, all assertions pass

### Files modified
- `llm/prompts.py` — added `chat_history` parameter to `build_prompt()` with its own `## Conversation History` block
- `llm/client.py` — added `min_new_tokens: 10`, raised `max_new_tokens` to 600, lowered `temperature` to 0.1

### Key design decisions made
- Output parser is intentionally compact — no JSON Schema block in the prompt. Granite 4h-small suppresses output when the prompt ends with JSON-like content.
- Format instructions end with `\nJSON:` — this is a continuation-priming technique: the model sees it as "I need to generate what comes after JSON:" and starts the object immediately.
- Retry loop (max 3 attempts) added to `chain.chat()` — Granite 4h-small produces empty output non-deterministically on long prompts.
- `min_new_tokens: 10` added to LLM params to force at least some output on every call.
- Pydantic v2 BaseModel used for `AstroMindResponse` (app models). `pydantic.v1` still used only for LangChain internals (SecretStr in client.py).
- History is stored as raw LLM text (not parsed JSON) in memory — Granite needs to "see" its own prior phrasing to maintain voice consistency.

### Bugs encountered — Day 2
- **Empty response on long prompts**: Granite 4h-small returns `''` when the combined prompt (system prompt + JSON schema block) exceeds ~3000 chars. Fix: strip the JSON Schema dump, use a compact continuation-style instruction (`\nJSON:`).
- **Non-deterministic empty responses**: Even with a valid prompt, Granite occasionally returns `''`. Fix: retry loop (3 attempts) + `min_new_tokens: 10`.
- **JSONDecodeError on truncated output**: With `max_new_tokens=512`, complex turn-2 responses were cut off mid-field. Fix: raised to 600.
- **Windows console UnicodeEncodeError**: Box-drawing chars (`═`, `─`) crash on cp1252 terminals. Fix: use plain ASCII `=` and `-` in test scripts.

---

## Status: Day 3 — Not started

### Goal
Docling PDF Ingestion + ChromaDB Vector Store — Knowledge Layer
NASA documents are parsed, chunked, embedded, and stored so that any
psychological query can surface the most relevant NASA passages as RAG context.

### Milestones

| # | Task | Output |
|---|------|--------|
| M1 | Download NASA-STD-3001 Vol 2 + HRP Behavioral Health PDF → `knowledge/docs/` | 2 PDF files on disk |
| M2 | Write `knowledge/__init__.py` | Package marker |
| M3 | Write `knowledge/ingestion.py` — Docling parses each PDF, LangChain `RecursiveCharacterTextSplitter` chunks into ~500-token segments | `ingest_documents()` returns a list of `Document` objects |
| M4 | Write `knowledge/vectorstore.py` — ChromaDB persists chunks + embeddings, exposes `similarity_search(query, k)` | `get_vectorstore()` singleton, `similarity_search()` public function |
| M5 | Write `test_knowledge.py` — query "crew stress management", assert top 3 chunks are returned and contain relevant text | All assertions pass |
| M6 | Update `NOTES.md` | Day 3 complete log |

### Files to create
- `knowledge/__init__.py` — package marker
- `knowledge/ingestion.py` — Docling PDF → text, `RecursiveCharacterTextSplitter` → `List[Document]`
- `knowledge/vectorstore.py` — ChromaDB collection backed by `data/chroma/`, `similarity_search(query, k=3)`
- `test_knowledge.py` — integration test: ingest + query + assert

### Files to place (manual download step)
- `knowledge/docs/NASA-STD-3001-Vol2.pdf` — NASA Space Human Factors and Ergonomics standard
- `knowledge/docs/HRP-Behavioral-Health.pdf` — Human Research Program Behavioral Health & Performance Element

### Key design decisions for Day 3
- **Docling over PyPDF**: Docling preserves document structure (headings, tables, lists) — critical for NASA standards where section context matters
- **ChromaDB on disk** (`data/chroma/`): persists across restarts; no separate server needed
- **Embedding model**: `all-MiniLM-L6-v2` via `langchain-community` `HuggingFaceEmbeddings` — small, fast, runs fully local with no extra API key
- **Chunk size ~500 tokens / 2000 chars**, overlap 200 chars — balances context preservation with retrieval precision
- **Metadata per chunk**: `source` (filename), `page` (page number from Docling), `chunk_index` — needed on Day 4 to cite sources in responses
- **Singleton pattern** for `get_vectorstore()` — same as `get_llm()` in client.py; one ChromaDB connection per process
- **Re-ingestion guard**: `ingestion.py` checks whether the collection already has documents before embedding — avoids duplicates on repeated runs

### Day 3 success criteria
- `similarity_search("crew stress management")` returns exactly 3 chunks
- Each chunk is a non-empty string from one of the two NASA PDFs
- Metadata on each chunk includes `source` filename
- Re-running `test_knowledge.py` a second time does not duplicate chunks in the DB

### Day 4 preview
- Wire `similarity_search()` into `AstroMindChain.chat()` — top-k chunks injected as `rag_context` into `build_prompt()`
- The `rag_context` slot in `build_prompt()` is already wired and waiting (built Day 1)
- Files: update `orchestration/chain.py` only — no new files needed