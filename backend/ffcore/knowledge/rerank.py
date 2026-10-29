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

# Pair limit (query + chunk) in model tokens. FlagReranker's default is 512, which silently cut
# the end of a full chunk (600 estimated tokens are ~700 real Turkish tokens; A-04a-0020: the
# answer at token 552 scored 0.0009, read in full 0.90). 1024 covers the chunk ceiling; a pair
# that still exceeds it is reported as truncated, never cut silently.
MAX_LENGTH = 1024


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

            from ffcore.knowledge.models import hf_path

            # A local path, never a hub name: missing weights are ModelMissing (r1 MAJOR-6).
            self._instance = FlagReranker(str(hf_path(self.model)), use_fp16=False)
        return self._instance

    def load(self) -> None:
        with self._lock:
            self._load()

    def score_with_truncation(self, query: str, texts: list[str]) -> tuple[list[float], list[bool]]:
        if not texts:
            return [], []
        pairs = [[query, t] for t in texts]
        with self._lock:
            model = self._load()
            truncated = [len(model.tokenizer(query, t)["input_ids"]) > MAX_LENGTH for t in texts]
            scores = model.compute_score(pairs, normalize=True, max_length=MAX_LENGTH)
        values = [float(s) for s in (scores if isinstance(scores, list) else [scores])]
        return values, truncated

    def score(self, query: str, texts: list[str]) -> list[float]:
        return self.score_with_truncation(query, texts)[0]


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
