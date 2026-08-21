"""
knowledge/ingestion.py

Parses all PDFs in knowledge/docs/ using PyMuPDF (fitz), splits them into
~500-token chunks with LangChain's RecursiveCharacterTextSplitter,
and returns a flat list of LangChain Document objects ready for embedding.

PyMuPDF reads the PDF text layer directly — no neural models, no network,
no C++ compiler required. Ideal for clean digital PDFs like NASA standards.

Public API
----------
    from knowledge.ingestion import ingest_documents

    docs = ingest_documents()   # returns List[Document]
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pymupdf as fitz  # PyMuPDF (fitz alias for compatibility)
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ── Configuration ──────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent / "docs"

CHUNK_SIZE    = 2000   # characters ≈ 500 tokens (1 token ≈ 4 chars)
CHUNK_OVERLAP = 200    # characters of overlap between adjacent chunks

# ── Splitter (module-level singleton) ─────────────────────────────────────────

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)

# ── Public API ─────────────────────────────────────────────────────────────────

def ingest_documents(docs_dir: Path = DOCS_DIR) -> List[Document]:
    """
    Parse every PDF in docs_dir with PyMuPDF and split into chunks.

    PyMuPDF reads the PDF text layer page-by-page and joins all pages into
    a single text blob before splitting. Page breaks become double newlines
    so the splitter treats them as natural paragraph boundaries.

    Parameters
    ----------
    docs_dir : Path
        Directory containing the PDF files. Defaults to knowledge/docs/.

    Returns
    -------
    List[Document]
        Flat list of chunked LangChain Documents, one entry per chunk.
        Each Document carries metadata: source (filename), chunk_index.
    """
    all_documents: List[Document] = []

    pdf_files = sorted(docs_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {docs_dir}")

    for pdf_path in pdf_files:
        print(f"[ingestion] Parsing: {pdf_path.name}")

        # ── PyMuPDF extract ─────────────────────────────────────────────
        # fitz.open() reads the PDF text layer — no OCR, no models.
        # Each page's text is joined with \n\n so paragraph boundaries
        # are preserved across pages for the splitter.
        doc = fitz.open(str(pdf_path))
        pages_text = [page.get_text() for page in doc]
        doc.close()

        full_text = "\n\n".join(pages_text)

        if not full_text.strip():
            print(f"[ingestion] WARNING: no text extracted from {pdf_path.name}, skipping.")
            continue

        # ── Split into chunks ───────────────────────────────────────────
        chunks: List[str] = _splitter.split_text(full_text)

        # ── Wrap each chunk in a Document with metadata ─────────────────
        for i, chunk in enumerate(chunks):
            all_documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": pdf_path.name,
                        "chunk_index": i,
                    },
                )
            )

        print(f"[ingestion]   -> {len(chunks)} chunks from {pdf_path.name}")

    print(f"[ingestion] Total chunks: {len(all_documents)}")
    return all_documents
