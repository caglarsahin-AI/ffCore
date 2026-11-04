"""08 tam 1b r1 MAJOR-2: `HttpNer` sends a long text in overlapping windows below the request
limit, shifts the offsets back and merges the spans the overlap repeats.

Before: a document over 200,000 characters was one request, the API answered 422 and the
document failed on every retry under `pii_ner`. A name cut by a window edge is found whole in the
next window (the overlap), so it is masked.
"""

import asyncio

from ffcore.core import egress
from ffcore.guardrails.recognizers import ner
from ffcore.knowledge import ingest_mask

NAME = "Ayşe Demir"
MODEL, REVISION = "acme/turkish-ner", "0123456789abcdef"
NER_TEXT_MAX_CHARS = 200_000  # NerRequest.text max_length (test_08t_20d)


def _fake_api(requests: list[str]):
    """An internal NER endpoint: 422 over the limit like the real schema; a name cut at the end of
    the window is reported as the cut part (a real model sees only what it is sent)."""

    class Response:
        def __init__(self, status, body=None):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, headers=None, json=None):
            text = json["text"]
            requests.append(text)
            if len(text) > NER_TEXT_MAX_CHARS:
                return Response(422)
            hits, at = [], 0
            while (start := text.find(NAME, at)) != -1:
                hits.append((start, start + len(NAME)))
                at = start + 1
            for cut in range(len(NAME) - 1, 2, -1):
                if text.endswith(NAME[:cut]):
                    hits.append((len(text) - cut, len(text)))
                    break
            findings = [
                {
                    "category": "PERSON",
                    "start": s,
                    "end": e,
                    "score": 0.95,
                    "evidence": f"ner {MODEL}@{REVISION[:7]} score 0.95",
                }
                for s, e in hits
            ]
            return Response(200, {"model": MODEL, "revision": REVISION, "findings": findings})

    return Client


def _settings():
    from ffcore.core.config import get_settings

    return get_settings().model_copy(
        update={
            "internal_api_url": "http://backend:8000",
            "ner_model": MODEL,
            "ner_revision": REVISION,
        }
    )


def _long_text(boundary_at: int, total: int = 250_000) -> str:
    """Filler with one name across `boundary_at` and one far from any edge."""
    filler = "kayıt satırı "
    body = (filler * (total // len(filler) + 1))[:total]
    first = boundary_at - 4  # the window edge cuts "Ayşe" after 4 characters
    body = body[:first] + NAME + body[first + len(NAME) :]
    second = total - 30_000
    return body[:second] + NAME + body[second + len(NAME) :]


def test_08t_20_long_text_windows_below_the_limit(monkeypatch):
    requests: list[str] = []
    monkeypatch.setattr(egress, "SafeOutboundClient", _fake_api(requests))
    monkeypatch.setattr(ner, "service_authorization", lambda s: {"Authorization": "x"})
    text = _long_text(NER_TEXT_MAX_CHARS)
    found = asyncio.run(ner.HttpNer(_settings()).find(text, ["PERSON"]))
    assert len(requests) >= 2 and all(len(r) <= NER_TEXT_MAX_CHARS for r in requests)
    assert [f.value for f in found] == [NAME, NAME]
    assert [text[f.start : f.end] for f in found] == [NAME, NAME]


def test_08t_20b_pii_ner_masks_the_name_on_the_window_edge(monkeypatch):
    requests: list[str] = []
    monkeypatch.setattr(egress, "SafeOutboundClient", _fake_api(requests))
    monkeypatch.setattr(ner, "service_authorization", lambda s: {"Authorization": "x"})
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: ner.HttpNer(_settings()))
    masked, counts = asyncio.run(ingest_mask.PiiNerFilter().mask(_long_text(NER_TEXT_MAX_CHARS)))
    assert NAME not in masked and "Ayşe" not in masked
    assert counts["PERSON"] == 2


def test_08t_20d_window_limit_is_the_request_limit():
    from ffcore.api import guardrails  # noqa: F401  (api_schemas imports through the router)
    from ffcore.guardrails.api_schemas import NerRequest

    limit = next(m.max_length for m in NerRequest.model_fields["text"].metadata if m.max_length)
    assert ner.NER_TEXT_MAX_CHARS == limit == NER_TEXT_MAX_CHARS
    assert ner.NER_WINDOW_OVERLAP_CHARS < ner.NER_TEXT_MAX_CHARS // 2


def test_08t_20c_short_text_is_one_request(monkeypatch):
    requests: list[str] = []
    monkeypatch.setattr(egress, "SafeOutboundClient", _fake_api(requests))
    monkeypatch.setattr(ner, "service_authorization", lambda s: {"Authorization": "x"})
    found = asyncio.run(ner.HttpNer(_settings()).find(f"Bay {NAME} geldi", ["PERSON"]))
    assert len(requests) == 1 and [(f.start, f.end) for f in found] == [(4, 14)]
