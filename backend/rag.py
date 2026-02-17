"""
Document ingestion and retrieval pipeline.

Loads PDF/TXT files → splits into chunks → embeds → stores in FAISS → retrieves.
"""

from __future__ import annotations

import os
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from config import EMBEDDING_DEFAULTS, UPLOAD_DIR, VECTORSTORE_DIR

# ---------------------------------------------------------------------------
# Embedding factory
# ---------------------------------------------------------------------------


def get_embeddings(provider: str | None = None, model: str | None = None):
    """Return an embeddings instance based on provider config."""
    provider = provider or EMBEDDING_DEFAULTS["provider"]
    model = model or EMBEDDING_DEFAULTS["model"]

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model)

    if provider == "fake":
        from langchain_core.embeddings import FakeEmbeddings

        return FakeEmbeddings(size=1536)

    raise ValueError(f"Unknown embedding provider: {provider}")


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------


def load_pdf(path: Path) -> list[Document]:
    """Extract pages from a PDF file as individual Documents."""
    reader = PdfReader(str(path))
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": path.name, "page": i + 1},
                )
            )
    return docs


def load_txt(path: Path) -> list[Document]:
    """Load a plain text file as a single Document."""
    text = path.read_text(encoding="utf-8")
    return [Document(page_content=text, metadata={"source": path.name, "page": 1})]


def load_files(directory: str | Path) -> list[Document]:
    """Load all PDF and TXT files from a directory."""
    directory = Path(directory)
    docs: list[Document] = []

    for file_path in sorted(directory.iterdir()):
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            docs.extend(load_pdf(file_path))
        elif suffix == ".txt":
            docs.extend(load_txt(file_path))

    return docs


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def split_documents(
    docs: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """Split documents into smaller chunks, preserving metadata."""
    chunk_size = chunk_size or EMBEDDING_DEFAULTS["chunk_size"]
    chunk_overlap = chunk_overlap or EMBEDDING_DEFAULTS["chunk_overlap"]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------


def build_vectorstore(
    chunks: list[Document],
    embeddings=None,
    persist_dir: str | None = None,
) -> FAISS:
    """Create a FAISS vectorstore from document chunks."""
    embeddings = embeddings or get_embeddings()
    store = FAISS.from_documents(chunks, embeddings)

    persist_dir = persist_dir or VECTORSTORE_DIR
    os.makedirs(persist_dir, exist_ok=True)
    store.save_local(persist_dir)

    return store


def load_vectorstore(
    persist_dir: str | None = None,
    embeddings=None,
) -> FAISS:
    """Load an existing FAISS vectorstore from disk."""
    persist_dir = persist_dir or VECTORSTORE_DIR
    embeddings = embeddings or get_embeddings()
    return FAISS.load_local(
        persist_dir, embeddings, allow_dangerous_deserialization=True
    )


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def retrieve(query: str, k: int = 5, store: FAISS | None = None) -> list[Document]:
    """Retrieve the top-k most relevant chunks for a query."""
    if store is None:
        store = load_vectorstore()
    return store.similarity_search(query, k=k)


def retrieve_with_sources(
    query: str,
    k: int = 5,
    store: FAISS | None = None,
) -> str:
    """
    Retrieve relevant passages and format them with source citations.

    Returns a formatted string with numbered passages and file/page references.
    """
    docs = retrieve(query, k=k, store=store)

    if not docs:
        return "Ingen relevante passasjer funnet."

    sections: list[str] = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "ukjent")
        page = doc.metadata.get("page", "?")
        text = doc.page_content.strip()
        sections.append(f"[{i}] (Kilde: {source}, s. {page})\n{text}")

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Full ingest pipeline
# ---------------------------------------------------------------------------


def ingest(
    directory: str | Path,
    embeddings=None,
    persist_dir: str | None = None,
) -> FAISS:
    """End-to-end: load files → split → embed → store. Returns the vectorstore."""
    docs = load_files(directory)
    if not docs:
        raise ValueError(f"No documents found in {directory}")

    chunks = split_documents(docs)
    store = build_vectorstore(chunks, embeddings=embeddings, persist_dir=persist_dir)

    print(f"Ingested {len(docs)} page(s) → {len(chunks)} chunks from {directory}")
    return store


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    target_dir = sys.argv[1] if len(sys.argv) > 1 else UPLOAD_DIR

    # Use fake embeddings for testing without an API key
    emb = get_embeddings(provider="fake")

    print(f"Loading files from: {target_dir}")
    store = ingest(target_dir, embeddings=emb)

    test_query = "Hva er forskjellen mellom rasjonalisme og empirisme?"
    print(f"\nTest-query: {test_query}\n")
    print(retrieve_with_sources(test_query, k=3, store=store))
