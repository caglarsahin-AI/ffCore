"""08 tam 1b, dilim 4: the `pii_ner` ingest filter and the PRSIM guard (KARARLAR karar 5).

`pii_ner@1` = the `pii_regex` categories plus person names from the NER model (asked over HTTP:
ingest runs in the worker or the ingest-raw CLI, never in the API process). PRSIM is accepted
with `pii_ner`; without it `prsim_requires_ner`, except the old M3 flag. `pii_regex@1` stays
as it was, so documents ingested before keep their label and text.
"""

import asyncio

import pytest

from ffcore.guardrails.findings import Finding
from ffcore.guardrails.recognizers import ner
from ffcore.knowledge import ingest, ingest_mask, raw_ingest, raw_staging
from ffcore.knowledge.raw_staging import StagingError


class FakeNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    def __init__(self, names=(), error=None):
        self.names, self.error, self.calls = names, error, []

    async def find(self, text, categories):
        self.calls.append(list(categories))
        if self.error is not None:
            raise self.error
        out = []
        for name in self.names:
            start = text.find(name)
            if start != -1:
                out.append(Finding("PERSON", start, start + len(name), 0.97, "ner", name))
        return out


@pytest.fixture
def fake_ner(monkeypatch):
    client = FakeNer(names=["Ayşe Demir", "Demir ayse.demir"])
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: client)
    return client


def test_08t_15_pii_ner_filter(fake_ner):
    f = ingest_mask.resolve("pii_ner")
    assert f.label == "pii_ner@1"
    text = "Talep Ayşe Demir tarafından açıldı; ayse.demir@ornek.com ile yazın."
    masked, counts = asyncio.run(f.mask(text))
    assert masked == "Talep [PERSON] tarafından açıldı; [EMAIL_ADDRESS] ile yazın."
    assert counts == {"PERSON": 1, "EMAIL_ADDRESS": 1}
    assert fake_ner.calls == [["PERSON"]]


def test_08t_15_pii_ner_never_overrides_regex(fake_ner):
    # The NER span "Demir ayse.demir" overlaps the e-mail address: the regex finding keeps the
    # whole address, the span is cut to its name part (r1 MINOR-5).
    masked, counts = asyncio.run(ingest_mask.resolve("pii_ner").mask("Demir ayse.demir@ornek.com"))
    assert masked == "[PERSON] [EMAIL_ADDRESS]"
    assert counts == {"PERSON": 1, "EMAIL_ADDRESS": 1}


def test_08t_15_metadata_masked_by_pii_ner(fake_ner):
    meta = {"title": "Ayşe Demir izin talebi", "source": "jira:PRSIM", "tags": ["Ayşe Demir"]}
    masked, counts = asyncio.run(ingest_mask.mask_metadata(ingest_mask.resolve("pii_ner"), meta))
    assert masked == {"title": "[PERSON] izin talebi", "source": "jira:PRSIM", "tags": ["[PERSON]"]}
    assert counts == {"PERSON": 2}


def test_08t_15_ner_down_fails_the_text_never_unmasked(monkeypatch):
    client = FakeNer(error=ner.NerUnavailable("internal ner failed: 503"))
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: client)
    with pytest.raises(ner.NerUnavailable):
        asyncio.run(ingest_mask.resolve("pii_ner").mask("Ayşe Demir"))


def test_08t_15_counting_filter_is_awaited(fake_ner):
    masking = ingest._CountingFilter("pii_ner")
    assert asyncio.run(masking("Ayşe Demir geldi")) == "[PERSON] geldi"
    assert masking.counts == {"PERSON": 1}


def test_08t_15b_prsim_accepted_with_ner(tmp_path):
    assert raw_staging.check_sources(["jira:PRSIM"], text_filter="pii_ner") == ["jira:PRSIM"]
    doc = tmp_path / "jira" / "PRSIM" / "PRSIM-1.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("Bir kayıt.\n", encoding="utf-8")
    (tmp_path / "jira" / "PRSIM" / "PRSIM-1.md.meta.json").write_text(
        '{"source": "jira:PRSIM", "source_item_id": "PRSIM-1"}', encoding="utf-8"
    )
    items = list(raw_staging.iter_staged(tmp_path, ["jira:PRSIM"], text_filter="pii_ner"))
    assert [type(i).__name__ for i in items] == ["StagedItem"]


@pytest.mark.parametrize("text_filter", [None, "pii_regex"])
def test_08t_15d_prsim_refused_without_ner(text_filter):
    with pytest.raises(StagingError) as raised:
        raw_staging.check_sources(["jira:PRSIM"], text_filter=text_filter)
    assert raised.value.code == "prsim_requires_ner"
    # The old M3 flag keeps working (deprecated, logged).
    assert raw_staging.check_sources(["jira:PRSIM"], accept_personnel_data=True) == ["jira:PRSIM"]


def test_08t_15c_old_manifest_untouched():
    f = ingest_mask.resolve("pii_regex")
    assert f.label == "pii_regex@1"
    assert f.apply("ayse.demir@ornek.com") == ("[EMAIL_ADDRESS]", {"EMAIL_ADDRESS": 1})
    with pytest.raises(ValueError):
        ingest_mask.resolve("pii_none")


@pytest.mark.parametrize(
    ("source", "code"),
    [("jira:PRSIM", "prsim_requires_ner"), ("confluence:OCR", "ner_unavailable")],
)
def test_08t_15e_ingest_raw_checks_ner_before_any_work(monkeypatch, tmp_path, source, code):
    client = FakeNer(error=ner.NerUnavailable("internal ner failed: 503"))
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: client)

    async def no_db(*args, **kwargs):
        raise AssertionError("database opened before the NER check")

    monkeypatch.setattr(raw_ingest, "_kb", no_db)
    with pytest.raises(raw_ingest.RawIngestError) as raised:
        asyncio.run(
            raw_ingest.ingest_tree(
                project_key="p",
                kb_key="k",
                raw_dir=tmp_path,
                acl_roles=["analyst"],
                sources=[source],
                limit=None,
                settings=None,
                text_filter="pii_ner",
            )
        )
    assert raised.value.code == code
