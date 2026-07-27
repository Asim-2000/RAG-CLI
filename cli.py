"""
rag - a terminal RAG assistant over your project docs and source code.

Usage:
    rag ingest ./docs --collection api-docs
    rag ask "How do I authenticate against the billing API?" --collection api-docs
    rag chat --collection api-docs
    rag collections
"""
from __future__ import annotations

import time
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from rag_cli.config import SETTINGS
from rag_cli.ingest import discover_files, load_and_chunk
from rag_cli.retriever import ask as run_ask
from rag_cli.retriever import get_vectorstore

console = Console()


@click.group()
@click.version_option(package_name="rag-cli")
def main() -> None:
    """rag - answer developer questions directly from your project docs."""


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--collection", "-c", default=SETTINGS.default_collection, show_default=True,
              help="Vector store collection to ingest into.")
@click.option("--glob", "glob_pattern", default=None,
              help="Optional glob (e.g. '**/*.md') to restrict which files are ingested.")
def ingest(path: Path, collection: str, glob_pattern: str | None) -> None:
    """Ingest a file or directory of docs/code into COLLECTION."""
    root = path if path.is_dir() else path.parent
    files = discover_files(path, glob_pattern)

    if not files:
        console.print("[yellow]No supported files found.[/yellow] "
                       "(supported: markdown, txt, rst, pdf, and common source files)")
        return

    console.print(f"Found [bold]{len(files)}[/bold] file(s) under [cyan]{path}[/cyan]")
    t0 = time.time()
    documents = load_and_chunk(files, root)
    console.print(f"Split into [bold]{len(documents)}[/bold] chunks")

    from rag_cli.retriever import upsert_documents

    with console.status("Embedding and storing chunks..."):
        count = upsert_documents(documents, collection)

    elapsed = time.time() - t0
    console.print(
        f"[green]Ingested {count} chunks from {len(files)} files into "
        f"'{collection}' in {elapsed:.1f}s[/green]"
    )
    console.print(f"Store location: [dim]{SETTINGS.persist_dir}[/dim]")


@main.command()
@click.argument("question")
@click.option("--collection", "-c", default=SETTINGS.default_collection, show_default=True)
@click.option("--k", default=SETTINGS.top_k, show_default=True, help="Number of chunks to retrieve.")
@click.option("--show-sources/--no-show-sources", default=True, help="Print retrieved source files.")
def ask(question: str, collection: str, k: int, show_sources: bool) -> None:
    """Ask a one-off QUESTION against COLLECTION."""
    _ask_and_print(question, collection, k, show_sources)


@main.command()
@click.option("--collection", "-c", default=SETTINGS.default_collection, show_default=True)
@click.option("--k", default=SETTINGS.top_k, show_default=True)
@click.option("--show-sources/--no-show-sources", default=True)
def chat(collection: str, k: int, show_sources: bool) -> None:
    """Interactive REPL for repeated questions against COLLECTION."""
    console.print(Panel.fit(
        f"[bold]rag chat[/bold] — collection: [cyan]{collection}[/cyan]  "
        f"(provider: {SETTINGS.llm_provider})\nType a question, or 'exit' / Ctrl-D to quit.",
    ))
    while True:
        try:
            question = console.input("[bold cyan]›[/bold cyan] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\nbye")
            break
        if not question.strip():
            continue
        if question.strip().lower() in {"exit", "quit"}:
            break
        _ask_and_print(question, collection, k, show_sources)


@main.command()
def collections() -> None:
    """List collections found in the local vector store."""
    import chromadb

    client = chromadb.PersistentClient(path=str(SETTINGS.persist_dir))
    cols = client.list_collections()
    if not cols:
        console.print("[yellow]No collections yet. Run `rag ingest` first.[/yellow]")
        return

    table = Table(title="Collections")
    table.add_column("Name", style="cyan")
    table.add_column("Chunks", justify="right")
    for col in cols:
        table.add_row(col.name, str(col.count()))
    console.print(table)


@main.command()
@click.argument("source_substring")
@click.option("--collection", "-c", default=SETTINGS.default_collection, show_default=True)
def forget(source_substring: str, collection: str) -> None:
    """Delete all chunks whose source path contains SOURCE_SUBSTRING."""
    store = get_vectorstore(collection)
    existing = store.get(include=["metadatas"])
    ids_to_delete = [
        _id for _id, meta in zip(existing["ids"], existing["metadatas"])
        if source_substring in meta.get("source", "")
    ]
    if not ids_to_delete:
        console.print(f"[yellow]No chunks matched '{source_substring}'.[/yellow]")
        return
    store.delete(ids=ids_to_delete)
    console.print(f"[green]Deleted {len(ids_to_delete)} chunks matching '{source_substring}'.[/green]")


def _ask_and_print(question: str, collection: str, k: int, show_sources: bool) -> None:
    with console.status("Thinking..."):
        try:
            answer, sources = run_ask(question, collection, k)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")
            return

    console.print(Markdown(answer))

    if show_sources and sources:
        console.print()
        table = Table(title="Sources", show_lines=False)
        table.add_column("#", width=3)
        table.add_column("File")
        table.add_column("Chunk", justify="right")
        for i, doc in enumerate(sources, 1):
            table.add_row(str(i), doc.metadata.get("source", "?"), str(doc.metadata.get("chunk_index", "?")))
        console.print(table)


if __name__ == "__main__":
    main()
