"""Turkish NER for person, organization and location names (08 tam 1b, K-08T1-0002 S1/S2).

A transformers `token-classification` pipeline (no Presidio; findings are the same `Finding`
as the regex recognizers). The model is loaded only by the API process (`LocalNer`); the agent
and ingest workers call `POST /internal/ner` (`HttpNer`), the `/internal/embed` pattern.

Fail-loud: no model configured is `ner_not_configured`, a missing weight is `model_missing`
(ModelMissing, offline cache only), a label the model knows but no category maps is
`ner_label_unknown` at load; an unreachable API is `NerUnavailable`, which the engine treats
as a rule failure (`on_error`, default block). Nothing falls back to regex only.
"""

import asyncio
import threading
from collections.abc import Callable, Collection, Mapping
from typing import Protocol

from ffcore.guardrails.findings import Finding
from ffcore.guardrails.schemas import GuardrailConfigError

# The categories NER finds (canonical codes, categories.py).
NER_LABELS = {
    "PER": "PERSON",
    "PERSON": "PERSON",
    "ORG": "ORGANIZATION",
    "ORGANIZATION": "ORGANIZATION",
    "LOC": "LOCATION",
    "LOCATION": "LOCATION",
}
# Labels a Turkish NER model may carry that are no PII category: named, never guessed.
IGNORED_LABELS = ("O", "MISC", "DATE", "TIME", "MONEY", "PERCENT")
_PREFIXES = ("B-", "I-", "E-", "S-", "L-", "U-")
# Long texts are cut into overlapping windows by the pipeline (no silent truncation at 512).
STRIDE = 128


class NerConfigError(GuardrailConfigError):
    """Configuration, not runtime: raised loudly by the engine, never turned into on_error."""


class NerUnavailable(RuntimeError):
    """The internal NER endpoint did not answer usably (a rule failure, `on_error`)."""


class NerClient(Protocol):
    model: str | None

    async def find(self, text: str, categories: Collection[str]) -> list[Finding]: ...


def _base(label: str) -> str:
    for prefix in _PREFIXES:
        if label.startswith(prefix):
            return label[len(prefix) :]
    return label


def _check_labels(labels: Mapping) -> tuple[str, ...]:
    ignored, unknown = set(), set()
    for label in labels.values():
        base = _base(str(label))
        if base in NER_LABELS:
            continue
        if base in IGNORED_LABELS:
            ignored.add(base)
        else:
            unknown.add(str(label))  # the model's own label, as it is in config.json
    if unknown:
        raise NerConfigError(
            "ner_label_unknown",
            f"NER model labels {sorted(unknown)} map to no PII category; "
            "add them to NER_LABELS or IGNORED_LABELS.",
        )
    return tuple(sorted(ignored - {"O"}))


class NerRecognizer:
    """One loaded pipeline; synchronous (callers run it off the event loop under a lock)."""

    def __init__(self, model: str, revision: str, *, pipeline: Callable, labels: Mapping) -> None:
        self.model, self.revision = model, revision
        self.ignored_labels = _check_labels(labels)
        self._pipeline = pipeline

    @classmethod
    def load(cls, model: str, revision: str) -> "NerRecognizer":
        from ffcore.knowledge.models import hf_path

        path = str(hf_path(model, revision))  # ModelMissing, no network request
        from transformers import pipeline

        pipe = pipeline(
            "token-classification",
            model=path,
            tokenizer=path,
            aggregation_strategy="simple",
            stride=STRIDE,
            device=-1,
        )
        return cls(model, revision, pipeline=pipe, labels=pipe.model.config.id2label)

    def evidence(self, score: float) -> str:
        return f"ner {self.model}@{self.revision[:7]} score {score:.2f}"

    def recognize(self, text: str, categories: Collection[str]) -> list[Finding]:
        wanted = set(categories)
        out = []
        for entity in self._pipeline(text):
            category = NER_LABELS.get(_base(str(entity["entity_group"])))
            if category is None or category not in wanted:
                continue
            start, end = entity.get("start"), entity.get("end")
            if start is None or end is None:
                raise NerConfigError(
                    "ner_offsets_unavailable", f"{self.model} gives no character offsets."
                )
            score = float(entity["score"])
            out.append(Finding(category, start, end, score, self.evidence(score), text[start:end]))
        return out


class LocalNer:
    """In the API process: the process-wide model, loaded on first use behind one lock."""

    def __init__(
        self, model: str | None, revision: str | None, recognizer: NerRecognizer | None = None
    ) -> None:
        self.model, self.revision = model, revision
        self._recognizer = recognizer
        self._lock = threading.Lock()

    def _recognize(self, text: str, categories: Collection[str]) -> list[Finding]:
        if not self.model or not self.revision:
            raise NerConfigError("ner_not_configured", "NER_MODEL and NER_REVISION are not set.")
        with self._lock:
            if self._recognizer is None:
                self._recognizer = NerRecognizer.load(self.model, self.revision)
            return self._recognizer.recognize(text, categories)

    async def find(self, text: str, categories: Collection[str]) -> list[Finding]:
        return await asyncio.to_thread(self._recognize, text, categories)


_local: dict[tuple, LocalNer] = {}


def local_ner() -> LocalNer:
    from ffcore.core.config import get_settings

    settings = get_settings()
    key = (settings.ner_model, settings.ner_revision)
    if key not in _local:
        _local[key] = LocalNer(*key)
    return _local[key]


def service_authorization(settings) -> dict:
    from ffcore.core.auth import service_authorization as authorization

    return authorization(settings)


class HttpNer:
    """In the agent and ingest workers: POST /internal/ner with the service token."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self.model, self.revision = settings.ner_model, settings.ner_revision

    async def find(self, text: str, categories: Collection[str]) -> list[Finding]:
        if not self.model or not self.revision:
            raise NerConfigError("ner_not_configured", "NER_MODEL and NER_REVISION are not set.")
        from ffcore.core import egress

        timeout = egress.EgressTimeout(connect=5, read=120, total=180)
        async with egress.SafeOutboundClient(timeout=timeout, settings=self._settings) as client:
            response = await client.request(
                "POST",
                f"{self._settings.internal_api_url.rstrip('/')}/api/v1/internal/guardrails/ner",
                headers=service_authorization(self._settings),
                json={"text": text, "categories": sorted(categories)},
            )
        if response.status_code != 200:
            raise NerUnavailable(f"internal ner failed: {response.status_code}")
        body = response.json()
        if (body.get("model"), body.get("revision")) != (self.model, self.revision):
            raise NerUnavailable(
                f"API runs NER {body.get('model')}@{body.get('revision')}, "
                f"worker expects {self.model}@{self.revision}"
            )
        out = []
        for hit in body["findings"]:
            start, end = int(hit["start"]), int(hit["end"])
            if not 0 <= start < end <= len(text):
                raise NerUnavailable("internal ner returned a span outside the text")
            out.append(
                Finding(
                    hit["category"],
                    start,
                    end,
                    float(hit["score"]),
                    hit["evidence"],
                    text[start:end],
                )
            )
        return out
