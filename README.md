# rag-cli

A terminal RAG (retrieval-augmented generation) tool built with LangChain that
answers developer questions directly from your project's docs and source code
— so engineers stop grepping through wikis and READMEs to find how an
internal API works.

```
$ rag ask "How do I get a bearer token for the billing API?" -c internal-docs

The billing API uses JWT bearer tokens obtained via POST /v1/auth/token,
passing client_id and client_secret in the JSON body. The token is valid
for 1 hour. [source: auth.md]

Example:
  curl -X POST https://internal.api/v1/auth/token \
    -d '{"client_id": "x", "client_secret": "y"}'

┌─── Sources ──────────────────────────┐
│ #  File       Chunk                  │
│ 1  auth.md    0                      │
│ 2  client.py  0                      │
└───────────────────────────────────────┘
```

## How it works

1. **Ingest** — point `rag ingest` at a docs folder (or a whole repo). Files
   are chunked with format-aware splitters: markdown is split on headers,
   source code is split on language-aware boundaries (functions/classes),
   everything else uses recursive character splitting.
2. **Embed & store** — chunks are embedded and stored in a local, persistent
   [Chroma](https://www.trychroma.com/) vector store on disk. Re-ingesting a
   file updates its chunks in place (deterministic chunk IDs) instead of
   duplicating them.
3. **Ask** — `rag ask "<question>"` retrieves the top-k most relevant chunks
   and passes them to an LLM with a prompt that forces it to answer only from
   what was retrieved (and say so when the docs don't cover it), citing the
   source file for each claim.

Works with **OpenAI** or a fully local **Ollama** setup — swap providers with
one environment variable, no code changes.

## Install

```bash
cd rag-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # then edit .env
```

At minimum, set `OPENAI_API_KEY` in `.env` (or set `RAG_LLM_PROVIDER=ollama`
and run `ollama pull llama3.1 && ollama pull nomic-embed-text` for a fully
local setup with no API key).

## Usage

```bash
# Ingest a docs folder into a named collection
rag ingest ./docs --collection internal-docs

# Ingest only certain files
rag ingest ./services/billing --collection billing --glob "**/*.md"

# Also index the source itself, so answers can reference real function names
rag ingest ./services/billing/src --collection billing --glob "**/*.py"

# Ask a one-off question
rag ask "What's the rate limit on /v1/invoices?" -c billing

# Interactive session (keeps asking until you type 'exit')
rag chat -c billing

# See what's been indexed
rag collections

# Remove a file's chunks (e.g. after it's deleted or rewritten) before re-ingesting
rag forget "old_auth_guide.md" -c billing
```

### Options

| Flag | Applies to | Meaning |
|---|---|---|
| `-c, --collection` | ingest/ask/chat/forget | Named vector store collection (default: `default`) |
| `--glob` | ingest | Restrict ingestion, e.g. `"**/*.md"` |
| `--k` | ask/chat | Number of chunks retrieved per question (default: 5) |
| `--show-sources/--no-show-sources` | ask/chat | Toggle the sources table |

## Configuration

All configuration is via environment variables / `.env` (see
`.env.example`), including chunk size and overlap, retrieval `k`, LLM
temperature, and where the vector store lives on disk (`RAG_PERSIST_DIR`,
default `./.rag_store`).

## Project layout

```
rag_cli/
  config.py      # env-driven settings
  ingest.py       # file discovery + language-aware chunking
  retriever.py    # embeddings, vector store, RAG chain (LangChain LCEL)
  cli.py          # click CLI: ingest / ask / chat / collections / forget
```

## Notes

- Supported input formats: `.md`, `.mdx`, `.txt`, `.rst`, `.yaml`, `.yml`,
  `.json`, `.toml`, `.pdf`, plus source code (`.py`, `.js/.ts`, `.go`,
  `.java`, `.rs`, `.rb`, `.php`, `.c/.cpp`, `.cs`, `.kt`, `.swift`, `.scala`).
- The vector store is local (Chroma, on-disk) — nothing is sent anywhere
  except the LLM/embedding calls to whichever provider you configure.
- Multiple collections let you keep separate doc sets (e.g. per-service or
  per-team) queryable independently.
