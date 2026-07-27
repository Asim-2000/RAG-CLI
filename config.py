"""
Central configuration for the RAG CLI.

Everything is driven by environment variables (optionally loaded from a
.env file) so the same codebase works with either OpenAI or a local Ollama
setup without code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # picks up a .env file in the current working directory


@dataclass(frozen=True)
class Settings:
    # "openai" or "ollama"
    llm_provider: str = os.getenv("RAG_LLM_PROVIDER", "openai").lower()

    # Model names
    openai_chat_model: str = os.getenv("RAG_OPENAI_CHAT_MODEL", "gpt-4o-mini")
    openai_embed_model: str = os.getenv("RAG_OPENAI_EMBED_MODEL", "text-embedding-3-small")
    ollama_chat_model: str = os.getenv("RAG_OLLAMA_CHAT_MODEL", "llama3.1")
    ollama_embed_model: str = os.getenv("RAG_OLLAMA_EMBED_MODEL", "nomic-embed-text")
    ollama_base_url: str = os.getenv("RAG_OLLAMA_BASE_URL", "http://localhost:11434")

    # Vector store
    persist_dir: Path = Path(os.getenv("RAG_PERSIST_DIR", "./.rag_store")).expanduser()
    default_collection: str = os.getenv("RAG_DEFAULT_COLLECTION", "default")

    # Chunking
    chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))

    # Retrieval
    top_k: int = int(os.getenv("RAG_TOP_K", "5"))
    temperature: float = float(os.getenv("RAG_TEMPERATURE", "0.0"))


SETTINGS = Settings()
SETTINGS.persist_dir.mkdir(parents=True, exist_ok=True)
