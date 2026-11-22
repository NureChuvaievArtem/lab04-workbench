"""Інструменти пошуку і читання бази знань для ADK та WorkbenchService."""

from __future__ import annotations

import os
from pathlib import Path

from kb.chunker import MarkdownChunker
from kb.embedder import KnowledgeEmbedder
from kb.store import KnowledgeStore
from kb.vault import ObsidianVault


def index_vault(vault: ObsidianVault | Path, store: KnowledgeStore, embedder) -> int:
    """Швидка індексація сховища (зручно для тестів та демо-режиму)."""
    v = vault if isinstance(vault, ObsidianVault) else ObsidianVault(vault)
    chunker = MarkdownChunker()
    total = 0
    for note_path in v.list_notes():
        rel = str(note_path.relative_to(v.vault_path)).replace("\\", "/")
        note = v.read_note(rel)
        chunks = chunker.chunk_note(note)
        if chunks:
            embs = embedder.embed([c.text for c in chunks], task_type="retrieval_document")
            store.add_chunks(chunks, embs)
            total += len(chunks)
    return total


class KnowledgeTools:
    """Адаптер пошуку та безпечного читання нотаток Obsidian/ChromaDB."""

    def __init__(
        self,
        store: KnowledgeStore,
        vault: ObsidianVault | Path,
        embedder=None,
        top_k: int = 3,
        max_distance: float = 0.28,
    ):
        self.store = store
        self.vault_obj = vault if isinstance(vault, ObsidianVault) else ObsidianVault(vault)
        self.vault = self.vault_obj.vault_path
        self.embedder = embedder or KnowledgeEmbedder(
            model_name=os.getenv("EMBED_MODEL", "gemini-embedding-001")
        )
        self.top_k = top_k
        self.max_distance = max_distance

    def search_knowledge(self, query: str, tag: str | None = None) -> str:
        """Семантичний пошук у БЗ. Повертає <fragment source="[[...]]" path="..."> або NOT_FOUND."""
        if not (query or "").strip():
            return "NOT_FOUND: Порожній пошуковий запит."
        q_vec = self.embedder.embed([query.strip()], task_type="retrieval_query")[0]
        results = self.store.query(q_vec, n_results=self.top_k, tag_filter=tag or None)
        valid = [r for r in results if r["distance"] <= self.max_distance]
        if not valid:
            return "NOT_FOUND: Жодного релевантного фрагмента нижче порогу відстані не знайдено."

        blocks = []
        for r in valid:
            meta = r["metadata"]
            ref = meta.get("reference", "[[SmartLease]]")
            rel_path = meta.get("rel_path", "")
            dist = r["distance"]
            blocks.append(
                f'<fragment source="{ref}" path="{rel_path}" distance="{dist:.3f}">\n'
                f"{r['text'].strip()}\n</fragment>"
            )
        return "\n\n".join(blocks)

    def read_note(self, rel_path: str) -> str:
        """Читає повну нотатку зі сховища із захистом від Path Traversal."""
        try:
            note = self.vault_obj.read_note(rel_path)
            return (
                f'<note title="{note.title}" path="{note.rel_path}">\n'
                f"Джерело: {note.source} | Оновлено: {note.updated}\n"
                f"Теги: {', '.join(note.tags)}\n\n"
                f"{note.content}\n</note>"
            )
        except Exception as exc:
            return f"ERROR_READ_NOTE: {exc}"


def build_tools() -> KnowledgeTools:
    """Створює KnowledgeTools зі змінних оточення (.env)."""
    vault_raw = os.getenv("OBSIDIAN_VAULT") or os.getenv("KB_VAULT_PATH")
    if not vault_raw:
        raise RuntimeError("Не задано OBSIDIAN_VAULT або KB_VAULT_PATH у .env")
    chroma_dir = os.getenv("CHROMA_PERSIST_DIR") or os.getenv("CHROMA_PATH")
    if not chroma_dir:
        raise RuntimeError("Не задано CHROMA_PERSIST_DIR або CHROMA_PATH у .env")
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Не задано GEMINI_API_KEY у .env")

    collection = os.getenv("CHROMA_COLLECTION", "smartlease_kb")
    max_dist = float(os.getenv("KB_MAX_DISTANCE", "0.28"))
    vault = ObsidianVault(vault_raw)
    store = KnowledgeStore(collection_name=collection, persist_dir=chroma_dir)
    if store.collection.count() == 0:
        raise RuntimeError(
            f"Колекція '{collection}' у '{chroma_dir}' порожня; виконайте індексацію з ЛР 2."
        )
    embedder = KnowledgeEmbedder(model_name=os.getenv("EMBED_MODEL", "gemini-embedding-001"))
    return KnowledgeTools(store=store, vault=vault, embedder=embedder, max_distance=max_dist)
