"""Turkish NER for person, organization and location names (08 tam 1b, K-08T1-0002 S1/S2).

A transformers `token-classification` pipeline (no Presidio; findings are the same `Finding`
as the regex recognizers). The model is loaded only by the API process (`LocalNer`); the agent
and ingest workers call `POST /api/v1/internal/guardrails/ner` (`HttpNer`), the `/internal/embed`
pattern.

Fail-loud: no model configured is `ner_not_configured`, a missing weight is `model_missing`
(ModelMissing, offline cache only), a label the model knows but no category maps is
`ner_label_unknown` at load; an unreachable API is `NerUnavailable`. At egress an enforce rule
turns it into `NerEgressUnavailable` (503 `ner_unavailable`) whatever `on_error` says (r1 MINOR-1
A); in the text stages it is a rule failure that follows `on_error` (default block). Nothing
falls back to regex only.
"""

import asyncio
import dataclasses
import re
import threading
from collections.abc import Callable, Collection, Mapping
from typing import Protocol

from ffcore.core.errors import ApiError
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
# The internal endpoint's request limit (NerRequest.text). A longer text is sent by HttpNer in
# overlapping windows below it (r1 MAJOR-2): a name cut by one window's edge is whole in the
# next, and the spans the overlap repeats are merged. The overlap is far above any name.
NER_TEXT_MAX_CHARS = 200_000
NER_WINDOW_OVERLAP_CHARS = 2_000


_PLACEHOLDER = re.compile(r"<<PII_[0-9]{1,7}>>")  # masking.PLACEHOLDER (no import cycle)


def trim_names(text: str, names, findings) -> list[Finding]:
    """NER spans cut to the parts outside the regex/custom `findings` and the `<<PII_n>>`
    placeholders already in the text (r1 MINOR-5/6): a name glued to a phone keeps its name
    part, a span never wraps or splits a placeholder. Parts are trimmed of non-alphanumeric
    edges; a part left with fewer than two characters is dropped."""
    blocked = sorted(
        [(f.start, f.end) for f in findings]
        + [(m.start(), m.end()) for m in _PLACEHOLDER.finditer(text)]
    )
    out = []
    for name in names:
        pieces = [(name.start, name.end)]
        for b_start, b_end in blocked:
            cut = []
            for start, end in pieces:
                if b_end <= start or b_start >= end:
                    cut.append((start, end))
                    continue
                if start < b_start:
                    cut.append((start, b_start))
                if b_end < end:
                    cut.append((b_end, end))
            pieces = cut
        for start, end in pieces:
            while start < end and not text[start].isalnum():
                start += 1
            while end > start and not text[end - 1].isalnum():
                end -= 1
            if end - start >= 2:
                out.append(dataclasses.replace(name, start=start, end=end, value=text[start:end]))
    return out


class NerEgressUnavailable(ApiError):
    """NER failed for an enforce rule at egress (r1 MINOR-1 A): loud whatever `on_error` says,
    so the checksummed identifiers never leave unmasked because an HTTP dependency was down
    (the PlaceholderOutOfRange precedent). The text stages keep `on_error`. No value in it."""

    def __init__(self, cause: str) -> None:
        super().__init__(
            503,
            "api_error",
            "ner_unavailable",
            f"The NER the egress PII policy needs is unavailable ({cause}).",
        )


class NerConfigError(GuardrailConfigError):
    """Configuration, not runtime: raised loudly by the engine, never turned into on_error."""


class NerUnavailable(RuntimeError):
    """The internal NER endpoint did not answer usably. The engine raises it as
    `NerEgressUnavailable` at egress (enforce) and follows `on_error` in the text stages."""


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
        import torch
        from torch.ao.quantization import quantize_dynamic
        from transformers import pipeline

        pipe = pipeline(
            "token-classification",
            model=path,
            tokenizer=path,
            # Whole words: "simple" split names into sub-word pieces (masked in part).
            aggregation_strategy="first",
            stride=STRIDE,
            device=-1,
        )
        # int8 linear layers (K-08T1C-0016 A): fp32 BERT-base needs > 300 ms for 1,000
        # characters on a CPU; quality on the PII set is the same (docs/guardrail.md).
        pipe.model = quantize_dynamic(pipe.model, {torch.nn.Linear}, dtype=torch.qint8)
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

    def load(self) -> NerRecognizer:
        """The model, loaded once (warm-up calls this; ModelMissing names the cache path)."""
        if not self.model or not self.revision:
            raise NerConfigError("ner_not_configured", "NER_MODEL and NER_REVISION are not set.")
        with self._lock:
            if self._recognizer is None:
                self._recognizer = NerRecognizer.load(self.model, self.revision)
            return self._recognizer

    def _recognize(self, text: str, categories: Collection[str]) -> list[Finding]:
        recognizer = self.load()
        with self._lock:
            return recognizer.recognize(text, categories)

    async def find(self, text: str, categories: Collection[str]) -> list[Finding]:
        return await asyncio.to_thread(self._recognize, text, categories)


_local: dict[tuple, LocalNer] = {}
# The warm-up thread and the first request may arrive together; one client per key, or the
# model would be loaded twice (FOLLOWUP-168).
_local_lock = threading.Lock()


def local_ner() -> LocalNer:
    from ffcore.core.config import get_settings

    settings = get_settings()
    key = (settings.ner_model, settings.ner_revision)
    with _local_lock:
        if key not in _local:
            _local[key] = LocalNer(*key)
        return _local[key]


def service_authorization(settings) -> dict:
    from ffcore.core.auth import service_authorization as authorization

    return authorization(settings)


class HttpNer:
    """In the agent and ingest workers: POST /api/v1/internal/guardrails/ner (service token)."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self.model, self.revision = settings.ner_model, settings.ner_revision

    async def find(self, text: str, categories: Collection[str]) -> list[Finding]:
        if not self.model or not self.revision:
            raise NerConfigError("ner_not_configured", "NER_MODEL and NER_REVISION are not set.")
        hits = []
        for offset, window in windows(text):
            for category, start, end, score, evidence in await self._post(window, categories):
                hits.append((category, start + offset, end + offset, score, evidence))
        return [
            Finding(category, start, end, score, evidence, text[start:end])
            for category, start, end, score, evidence in merge_spans(hits)
        ]

    async def _post(self, text: str, categories: Collection[str]) -> list[tuple]:
        from ffcore.core import egress

        timeout = egress.EgressTimeout(connect=5, read=120, total=180)
        try:
            async with egress.SafeOutboundClient(
                timeout=timeout, settings=self._settings
            ) as client:
                response = await client.request(
                    "POST",
                    f"{self._settings.internal_api_url.rstrip('/')}/api/v1/internal/guardrails/ner",
                    headers=service_authorization(self._settings),
                    json={"text": text, "categories": sorted(categories)},
                )
        except egress.EgressError as exc:
            # r1 MINOR-2: refused, DNS, timeout are an outage like a 5xx (coded, no traceback);
            # the message names scheme and host only.
            raise NerUnavailable(f"internal ner unreachable: {exc}") from None
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
            out.append((hit["category"], start, end, float(hit["score"]), hit["evidence"]))
        return out


def windows(text: str, size: int = NER_TEXT_MAX_CHARS, overlap: int = NER_WINDOW_OVERLAP_CHARS):
    """(offset, window) pieces of at most `size` characters, each overlapping the previous one by
    `overlap`; a text within `size` is one piece. Nothing is dropped."""
    if len(text) <= size:
        yield 0, text
        return
    start = 0
    while True:
        end = min(start + size, len(text))
        yield start, text[start:end]
        if end == len(text):
            return
        start = end - overlap


def merge_spans(hits: list[tuple]) -> list[tuple]:
    """Overlapping spans (the same name seen by two windows, or cut by one window's edge) become
    their union, with the category, score and evidence of the higher-scored one."""
    merged: list[tuple] = []
    for hit in sorted(hits, key=lambda h: (h[1], -h[2])):
        if merged and hit[1] < merged[-1][2]:
            last = merged[-1]
            best = last if last[3] >= hit[3] else hit
            merged[-1] = (best[0], last[1], max(last[2], hit[2]), best[3], best[4])
        else:
            merged.append(hit)
    return merged
