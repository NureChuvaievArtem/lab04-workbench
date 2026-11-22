"""Модуль генерації ембедингів (Gemini API та детермінований HashEmbedder для тестів/демо)."""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Literal


class HashEmbedder:
    """Локальний лексичний ембедер (n-грами слів) для офлайн-тестів та демо без мережі."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"[0-9A-Za-zА-Яа-яІіЇїЄєҐґ_]+", (text or "").lower())
        features: list[str] = list(tokens)
        for tok in tokens:
            if len(tok) >= 3:
                for i in range(len(tok) - 2):
                    features.append(tok[i : i + 3])
        if not features:
            features = ["empty"]

        for feat in features:
            h = hashlib.sha256(feat.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if (h[4] & 1) == 0 else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(
        self,
        texts: list[str],
        task_type: Literal["retrieval_document", "retrieval_query"] = "retrieval_document",
    ) -> list[list[float]]:
        _ = task_type
        return [self._embed_one(t) for t in texts]


class KnowledgeEmbedder:
    """Генератор ембедингів Gemini з автоматичним fallback на HashEmbedder."""

    def __init__(self, model_name: str = "gemini-embedding-001", api_key: str | None = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = None
        self._fallback = HashEmbedder(dim=768)

        if self.api_key:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)

    def embed(
        self,
        texts: list[str],
        task_type: Literal["retrieval_document", "retrieval_query"] = "retrieval_document",
    ) -> list[list[float]]:
        """Генерує векторні представлення для списку текстів."""
        if not texts:
            return []

        if self._client:
            formatted = [f"[{task_type}] {t}" for t in texts]
            result = self._client.models.embed_content(
                model=self.model_name,
                contents=formatted,
            )
            return [list(e.values) for e in result.embeddings]

        return self._fallback.embed(texts, task_type=task_type)
