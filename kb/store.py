"""Модуль векторного сховища ChromaDB."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


class KnowledgeStore:
    """Векторне сховище Chroma для SmartLease (Persistent / Http / custom client)."""

    def __init__(
        self,
        collection_name: str = "smartlease_kb",
        persist_dir: str | Path = "./chroma_data",
        host: str | None = None,
        port: int | None = None,
        client: chromadb.ClientAPI | None = None,
    ):
        self.collection_name = collection_name
        self.persist_dir = Path(persist_dir).resolve()
        self.host = host or os.getenv("CHROMA_HOST")
        self.port = port or int(os.getenv("CHROMA_PORT", "8000"))

        if client is not None:
            self.client = client
        elif self.host:
            self.client = chromadb.HttpClient(host=self.host, port=self.port)
        else:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": os.getenv("EMBED_MODEL", "gemini-embedding-001"),
                "description": "SmartLease Knowledge Base Collection",
            },
        )

    def add_chunks(self, chunks: list[Any], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "rel_path": c.rel_path,
                "note_title": c.note_title,
                "section_heading": c.section_heading,
                "reference": c.reference,
                "source": c.source,
                "tags": ",".join(c.tags),
            }
            for c in chunks
        ]
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def delete_by_path(self, rel_path: str) -> None:
        self.collection.delete(where={"rel_path": rel_path})

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 4,
        tag_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        count = self.collection.count()
        if count == 0:
            return []
        fetch_k = min(n_results * 4, count) if tag_filter else min(n_results, count)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_k,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if not results or not results["ids"] or not results["ids"][0]:
            return output

        for cid, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            strict=False,
        ):
            tags_list = [
                t.strip().lower()
                for t in str(meta.get("tags", "")).split(",")
                if t.strip()
            ]
            if tag_filter and not any(
                tag_filter.lower() in t or t in tag_filter.lower() for t in tags_list
            ):
                continue
            output.append(
                {
                    "chunk_id": cid,
                    "text": doc,
                    "metadata": meta,
                    "distance": float(dist),
                }
            )
            if len(output) >= n_results:
                break
        return output
