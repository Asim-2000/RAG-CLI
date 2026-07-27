"""
Provider wiring (OpenAI / Ollama) plus the vector store and RAG chain.
"""
from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from rag_cli.config import SETTINGS

SYSTEM_PROMPT = """You are an internal engineering assistant. Answer the \
developer's question using ONLY the provided documentation excerpts.

Rules:
- If the excerpts don't contain the answer, say so plainly instead of guessing.
- Be concise and technical; prefer code blocks and exact names (endpoints, \
function signatures, config keys) over prose.
- When you use a fact from an excerpt, cite it inline like [source: path].
- Never invent an API, parameter, or file that isn't in the excerpts.

Documentation excerpts:
{context}
"""

ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{question}"),
    ]
)


def get_embeddings():
    if SETTINGS.llm_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=SETTINGS.ollama_embed_model, base_url=SETTINGS.ollama_base_url)

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=SETTINGS.openai_embed_model)


def get_llm():
    if SETTINGS.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=SETTINGS.ollama_chat_model,
            base_url=SETTINGS.ollama_base_url,
            temperature=SETTINGS.temperature,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=SETTINGS.openai_chat_model, temperature=SETTINGS.temperature)


def get_vectorstore(collection: str) -> Chroma:
    return Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=str(SETTINGS.persist_dir),
    )


def upsert_documents(documents: list[Document], collection: str, batch_size: int = 100) -> int:
    if not documents:
        return 0
    store = get_vectorstore(collection)
    ids = [doc.metadata["chunk_id"] for doc in documents]
    for start in range(0, len(documents), batch_size):
        batch_docs = documents[start : start + batch_size]
        batch_ids = ids[start : start + batch_size]
        store.add_documents(batch_docs, ids=batch_ids)
    return len(documents)


def _format_context(docs: list[Document]) -> str:
    blocks = []
    for doc in docs:
        src = doc.metadata.get("source", "unknown")
        blocks.append(f"### {src}\n{doc.page_content}")
    return "\n\n".join(blocks)


def build_chain(collection: str, k: int):
    store = get_vectorstore(collection)
    retriever = store.as_retriever(search_kwargs={"k": k})
    llm = get_llm()

    chain = (
        {
            "context": retriever | _format_context,
            "question": RunnablePassthrough(),
        }
        | ANSWER_PROMPT
        | llm
        | StrOutputParser()
    )
    return retriever, chain


def ask(question: str, collection: str, k: int) -> tuple[str, list[Document]]:
    retriever, chain = build_chain(collection, k)
    sources = retriever.invoke(question)
    answer = chain.invoke(question)
    return answer, sources
