"""bge-reranker-v2-m3 cross-encoder, in process (FlagEmbedding's FlagReranker, ARCH-09).

Adapted from PayCore `rag/rerank.py`: normalized scores (0-1), one call at a time (model lock),
always from a worker thread. The floor (RERANK_MIN_SCORE, 0,1 measured for this model) is
applied in search.py so the eliminated candidates are counted (brief D5).
"""

import asyncio
import re
import threading
from functools import lru_cache
from typing import Any, Protocol

from ffcore.core.config import Settings


class Reranker(Protocol):
    model: str

    def score(self, query: str, texts: list[str]) -> list[float]: ...


class BgeReranker:
    def __init__(self, model: str):
        self.model = model
        self._lock = threading.Lock()
        self._instance: Any = None

    def _load(self) -> Any:
        if self._instance is None:
            from FlagEmbedding import FlagReranker

            self._instance = FlagReranker(self.model, use_fp16=False)
        return self._instance

    def load(self) -> None:
        with self._lock:
            self._load()

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        with self._lock:
            scores = self._load().compute_score([[query, t] for t in texts], normalize=True)
        return [float(s) for s in (scores if isinstance(scores, list) else [scores])]


_WORD = re.compile(r"\w+", re.U)


class FakeReranker:
    """Deterministic: share of query words present in the text (FAKE_EMBED=1)."""

    def __init__(self, model: str):
        self.model = model

    def score(self, query: str, texts: list[str]) -> list[float]:
        wanted = set(_WORD.findall(query.lower()))
        if not wanted:
            return [0.0 for _ in texts]
        return [len(wanted & set(_WORD.findall(t.lower()))) / len(wanted) for t in texts]


@lru_cache
def _reranker(fake: bool, model: str) -> Reranker:
    return FakeReranker(model) if fake else BgeReranker(model)


def get_reranker(settings: Settings) -> Reranker:
    return _reranker(settings.fake_embed, settings.rerank_model)


async def rerank_scores(settings: Settings, query: str, texts: list[str]) -> list[float]:
    return await asyncio.to_thread(get_reranker(settings).score, query, texts)
