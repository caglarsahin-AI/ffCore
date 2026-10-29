"""bge-m3 dense + sparse embeddings, in process (C10 reversed, PLAN 2d); only the API loads it.

Adapted from PayCore `rag/embed.py` and the 00i fix: one call into the model at a time
(model lock), always from a worker thread (`asyncio.to_thread`) so the event loop stays free
(brief D6). A text longer than the model's 8192-token limit is reported in `truncated`; the
ingest marks that chunk `flagged/embedding_truncated` instead of pretending it was embedded
whole. FAKE_EMBED=1 selects a deterministic hashing embedder for tests: an explicit setting,
never a fallback when the real model fails.
"""

import asyncio
import hashlib
import math
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from ffcore.core.config import Settings

MAX_TOKENS = 8192


@dataclass(frozen=True)
class Embeddings:
    dense: list[list[float]]
    sparse: list[dict[int, float]]
    truncated: list[bool]


class Embedder(Protocol):
    model: str
    dim: int

    def encode(self, texts: list[str]) -> Embeddings: ...


class BgeM3Embedder:
    def __init__(self, model: str, dim: int):
        self.model = model
        self.dim = dim
        self._lock = threading.Lock()
        self._instance: Any = None

    def _load(self) -> Any:
        if self._instance is None:
            from FlagEmbedding import BGEM3FlagModel

            from ffcore.knowledge.models import hf_path

            # A local path, never a hub name: missing weights are ModelMissing (r1 MAJOR-6).
            self._instance = BGEM3FlagModel(str(hf_path(self.model)), use_fp16=False)
        return self._instance

    def load(self) -> None:
        with self._lock:
            self._load()

    def _truncated(self, model: Any, texts: list[str]) -> list[bool]:
        # One token per character is the floor: shorter strings cannot reach the limit.
        flags = []
        for text in texts:
            if len(text) <= MAX_TOKENS:
                flags.append(False)
                continue
            flags.append(len(model.tokenizer(text)["input_ids"]) > MAX_TOKENS)
        return flags

    def encode(self, texts: list[str]) -> Embeddings:
        with self._lock:
            model = self._load()
            truncated = self._truncated(model, texts)
            out = model.encode(
                texts, return_dense=True, return_sparse=True, return_colbert_vecs=False
            )
        dense = [list(map(float, row)) for row in out["dense_vecs"]]
        if dense and len(dense[0]) != self.dim:
            raise RuntimeError(f"{self.model} returned {len(dense[0])} dimensions, not {self.dim}")
        sparse = [{int(k): float(v) for k, v in w.items()} for w in out["lexical_weights"]]
        return Embeddings(dense, sparse, truncated)


_WORD = re.compile(r"\w+", re.U)


class FakeEmbedder:
    """Deterministic: each lower-cased word adds to a hashed dimension (dense, L2-normalized)
    and gets a hashed sparse id. Texts sharing words are close; identical texts are equal."""

    def __init__(self, model: str, dim: int):
        self.model = model
        self.dim = dim

    @staticmethod
    def _bucket(word: str, size: int) -> int:
        return int.from_bytes(hashlib.sha256(word.encode()).digest()[:8], "big") % size

    def encode(self, texts: list[str]) -> Embeddings:
        dense, sparse = [], []
        for text in texts:
            vector = [0.0] * self.dim
            weights: dict[int, float] = {}
            for word in _WORD.findall(text.lower()):
                vector[self._bucket(word, self.dim)] += 1.0
                token = self._bucket(word, 250_000)
                weights[token] = weights.get(token, 0.0) + 0.1
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            dense.append([x / norm for x in vector])
            sparse.append(weights)
        return Embeddings(dense, sparse, [len(t) > MAX_TOKENS * 6 for t in texts])


@lru_cache
def _embedder(fake: bool, model: str, dim: int) -> Embedder:
    return FakeEmbedder(model, dim) if fake else BgeM3Embedder(model, dim)


def get_embedder(settings: Settings) -> Embedder:
    return _embedder(settings.fake_embed, settings.embed_model, settings.embed_dim)


async def embed(settings: Settings, texts: list[str]) -> Embeddings:
    """Never on the event loop: CPU-bound model call in a worker thread (D6)."""
    return await asyncio.to_thread(get_embedder(settings).encode, texts)


async def probe_dimension(config: dict[str, str], model_id: str, settings: Settings) -> int:
    """03a embedding probe for the `local_flagembedding` driver: the measured vector length.
    Only the installation's model can be measured in process (one model per installation)."""
    if model_id != settings.embed_model:
        from ffcore.core.errors import ApiError

        raise ApiError(
            400,
            "invalid_request_error",
            "embed_model_mismatch",
            f"Only the installation's embedding model {settings.embed_model} runs in process.",
        )
    result = await embed(settings, ["dimension probe"])
    return len(result.dense[0])


@lru_cache
def _tokenizer(model: str) -> Any:
    from transformers import AutoTokenizer

    from ffcore.knowledge.models import hf_path

    return AutoTokenizer.from_pretrained(str(hf_path(model)))


def token_counter(settings: Settings):
    """Chunk limits in the embedding model's own tokens (K-04a-0010). The tokenizer alone loads
    in the worker (no model weights); FAKE_EMBED=1 uses the estimate, explicitly."""
    from ffcore.knowledge.chunking import approx_tokens

    if settings.fake_embed:
        return approx_tokens
    tokenizer = _tokenizer(settings.embed_model)

    def count(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    return count
