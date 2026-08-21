"""
knowledge/vectorstore.py

Builds and exposes a ChromaDB vector store backed by the NASA PDF chunks
produced by knowledge/ingestion.py.

On first call, ingest_documents() is run and all chunks are embedded and
persisted to data/chroma/.  On subsequent calls the existing collection is
reused — no re-embedding occurs.

Public API
----------
    from knowledge.vectorstore import similarity_search

    docs = similarity_search("crew stress management", k=3)
    # returns List[Document] — top-k chunks by cosine similarity
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain.embeddings.base import Embeddings
from langchain.schema import Document
from langchain_community.vectorstores import Chroma

from knowledge.ingestion import ingest_documents

# ── Configuration ──────────────────────────────────────────────────────────────

CHROMA_DIR      = Path(__file__).parent.parent / "data" / "chroma"
COLLECTION_NAME = "astromind_nasa"

# ── Adapter: bridges ChromaDB's EF interface to LangChain's embedding interface ─

class _ChromaEFAdapter(Embeddings):
    """
    LangChain's Chroma wrapper expects embed_documents() and embed_query().
    ChromaDB's DefaultEmbeddingFunction uses a callable interface instead.
    This adapter translates between the two — no network, no extra dependencies.
    The underlying model is all-MiniLM-L6-v2 in ONNX format, cached locally
    after its one-time ~79 MB download.
    """

    def __init__(self) -> None:
        self._ef = DefaultEmbeddingFunction()  # type: ignore[assignment]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [list(v) for v in self._ef(texts)]  # type: ignore[misc]

    def embed_query(self, text: str) -> List[float]:
        return list(self._ef([text])[0])  # type: ignore[misc]


# ── Singletons ─────────────────────────────────────────────────────────────────

_embeddings:  _ChromaEFAdapter | None = None
_vectorstore: Chroma | None = None


def _get_embeddings() -> _ChromaEFAdapter:
    global _embeddings
    if _embeddings is None:
        print("[vectorstore] Loading embedding model: all-MiniLM-L6-v2 (ONNX, local)")
        _embeddings = _ChromaEFAdapter()
    return _embeddings


def get_vectorstore() -> Chroma:
    """
    Return the ChromaDB vectorstore, building it from scratch if needed.

    First call (cold start):
        1. Creates data/chroma/ directory if it doesn't exist
        2. Calls ingest_documents() to parse + chunk all PDFs
        3. Embeds all chunks with all-MiniLM-L6-v2
        4. Persists the collection to data/chroma/
        5. Caches the Chroma object in _vectorstore

    Subsequent calls (warm start):
        - Returns the cached _vectorstore immediately
        - No re-embedding, no disk I/O beyond what ChromaDB needs
    """
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = _get_embeddings()

    # ── Try to load existing collection ────────────────────────────────
    existing = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )

    if existing._collection.count() > 0:
        print(f"[vectorstore] Loaded existing collection: {existing._collection.count()} chunks")
        _vectorstore = existing
        return _vectorstore

    # ── Collection is empty — ingest and embed ─────────────────────────
    print("[vectorstore] Collection empty — ingesting documents...")
    documents = ingest_documents()

    _vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
    )
    print(f"[vectorstore] Embedded and stored {len(documents)} chunks.")
    return _vectorstore


# ── Public API ─────────────────────────────────────────────────────────────────

def similarity_search(query: str, k: int = 3) -> List[Document]:
    """
    Return the k most relevant NASA document chunks for the given query.

    Parameters
    ----------
    query : str
        Plain English question or statement, e.g. "crew stress management".
    k : int
        Number of chunks to return. Default 3 — enough context without
        overloading the LLM prompt.

    Returns
    -------
    List[Document]
        Each Document has:
          .page_content  — the raw text of the chunk
          .metadata      — {"source": "filename.pdf", "chunk_index": N}
    """
    vs = get_vectorstore()
    return vs.similarity_search(query, k=k)
    