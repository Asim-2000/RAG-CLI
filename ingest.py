"""
Loading and chunking of project documentation / source files.

Supports markdown, plain text, reStructuredText, PDFs, and source code
(chunked with language-aware separators so functions/classes aren't split
mid-body wherever the splitter can help it).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from rag_cli.config import SETTINGS

# Extension -> LangChain Language enum, for language-aware splitting.
CODE_LANGUAGES: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
    ".java": Language.JAVA,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".rb": Language.RUBY,
    ".php": Language.PHP,
    ".cpp": Language.CPP,
    ".c": Language.CPP,
    ".cs": Language.CSHARP,
    ".kt": Language.KOTLIN,
    ".swift": Language.SWIFT,
    ".scala": Language.SCALA,
}

TEXT_EXTENSIONS = {".md", ".mdx", ".txt", ".rst", ".yaml", ".yml", ".json", ".toml"}
PDF_EXTENSIONS = {".pdf"}

SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS | set(CODE_LANGUAGES)

# Directories we never want to walk into.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".rag_store",
}


def discover_files(root: Path, glob: str | None = None) -> list[Path]:
    """Walk `root` and return every file worth ingesting."""
    if root.is_file():
        return [root] if root.suffix.lower() in SUPPORTED_EXTENSIONS else []

    pattern = glob or "**/*"
    found = []
    for path in root.glob(pattern):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            found.append(path)
    return sorted(found)


def _load_raw(path: Path) -> str | None:
    suffix = path.suffix.lower()
    try:
        if suffix in PDF_EXTENSIONS:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover - defensive, surfaced to caller
        print(f"  ! skipped {path} ({exc})")
        return None


def _splitter_for(path: Path) -> RecursiveCharacterTextSplitter:
    suffix = path.suffix.lower()
    if suffix in CODE_LANGUAGES:
        return RecursiveCharacterTextSplitter.from_language(
            language=CODE_LANGUAGES[suffix],
            chunk_size=SETTINGS.chunk_size,
            chunk_overlap=SETTINGS.chunk_overlap,
        )
    if suffix in {".md", ".mdx"}:
        return RecursiveCharacterTextSplitter(
            chunk_size=SETTINGS.chunk_size,
            chunk_overlap=SETTINGS.chunk_overlap,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
        )
    return RecursiveCharacterTextSplitter(
        chunk_size=SETTINGS.chunk_size,
        chunk_overlap=SETTINGS.chunk_overlap,
    )


def chunk_id(source: str, index: int, text: str) -> str:
    """Deterministic id so re-ingesting the same file updates, not duplicates."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{source}::{index}::{digest}"


def load_and_chunk(paths: Iterable[Path], root: Path) -> list[Document]:
    documents: list[Document] = []
    for path in paths:
        raw = _load_raw(path)
        if not raw or not raw.strip():
            continue

        rel_source = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        splitter = _splitter_for(path)
        chunks = splitter.split_text(raw)

        for i, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": rel_source,
                        "chunk_index": i,
                        "chunk_id": chunk_id(rel_source, i, chunk),
                    },
                )
            )
    return documents
