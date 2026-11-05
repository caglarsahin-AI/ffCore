"""19: `ingest-raw` input boundary (plan/19 Güvenlik şartları 1-2).

The staging tree is a file plus `<file>.meta.json`; nothing outside `--raw-dir` is read, PRSIM is
refused until 08 full, the masking filter is always on and cannot be named away.
"""

import json
import os
from pathlib import Path

import pytest

from ffcore import cli
from ffcore.knowledge import ingest_mask, raw_staging
from ffcore.knowledge.raw_staging import StagingError


def _stage(root: Path, rel: str, body: str = "Bir sayfa.\n", **meta) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    fields = {"source": "confluence:DEMO", "source_item_id": path.stem} | meta
    Path(f"{path}.meta.json").write_text(json.dumps(fields), encoding="utf-8")
    return path


def _codes(results) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in results:
        if isinstance(r, raw_staging.Rejected):
            out[r.code] = out.get(r.code, 0) + 1
    return out


def _items(results) -> list[raw_staging.StagedItem]:
    return [r for r in results if isinstance(r, raw_staging.StagedItem)]


# --- S1: PRSIM ---


@pytest.mark.parametrize("source", ["jira:PRSIM", "PRSIM", "jira:prsim", " Jira:PrSim "])
def test_19_s1_prsim_requires_ner(source):
    with pytest.raises(StagingError) as err:
        raw_staging.check_sources(["confluence:DEMO", source])
    assert err.value.code == "prsim_requires_ner"


def test_19_s1_prsim_in_meta_rejected_even_if_not_selected(tmp_path):
    _stage(tmp_path, "jira/PRSIM/PRSIM-1.md", source="jira:PRSIM")
    _stage(tmp_path, "confluence/DEMO/1.md")
    results = list(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"]))
    assert _codes(results) == {"prsim_requires_ner": 1}
    assert [i.meta["source_item_id"] for i in _items(results)] == ["1"]


def test_19_s1_cli_refuses_prsim_before_any_work(tmp_path, capsys):
    # No database, no stack: the refusal comes before anything is opened.
    code = cli.main(
        [
            "ingest-raw",
            "--project",
            "p",
            "--kb",
            "k",
            "--raw-dir",
            str(tmp_path),
            "--acl",
            "analyst",
            "--sources",
            "jira:PRSIM",
        ]
    )
    assert code == 2
    assert "prsim_requires_ner" in capsys.readouterr().err


def test_19_s1_cli_sources_required(tmp_path):
    with pytest.raises(SystemExit) as err:
        cli.main(
            [
                "ingest-raw",
                "--project",
                "p",
                "--kb",
                "k",
                "--raw-dir",
                str(tmp_path),
                "--acl",
                "analyst",
            ]
        )
    assert err.value.code == 2


def test_19_s1_pii_masked_and_counted():
    text = (
        "Destek: ayse@ornek.com, tel 0532 256 60 38, TC 10000000146, "
        "IBAN TR33 0006 1005 1978 6457 8413 26, kart 4111 1111 1111 1111."
    )
    masked, counts = ingest_mask.resolve("pii_regex").apply(text)
    for value in ("ayse@ornek.com", "0532 256 60 38", "10000000146", "4111 1111 1111 1111"):
        assert value not in masked
    assert "TR33" not in masked
    assert counts == {
        "EMAIL_ADDRESS": 1,
        "TR_PHONE": 1,
        "TR_NATIONAL_ID": 1,
        "TR_IBAN": 1,
        "CREDIT_CARD": 1,
    }
    assert "[EMAIL_ADDRESS]" in masked


def test_19_s1_text_filter_name_and_version():
    f = ingest_mask.resolve("pii_regex")
    assert f.label == f"pii_regex@{ingest_mask.PII_REGEX_VERSION}"
    with pytest.raises(ValueError):
        ingest_mask.resolve("none")


def test_19_s1_masking_cannot_be_disabled():
    parser_help = cli.build_parser().format_help()
    sub = cli.build_parser()._subparsers._group_actions[0].choices["ingest-raw"]
    options = {o: a for a in sub._actions for o in a.option_strings}
    # 08 tam 1c, FOLLOWUP-174 (K-08T1C-0005): the one filter option chooses between two masking
    # filters; no choice turns masking off and no other option names masking or a filter.
    named = {o for o in options if "mask" in o or "filter" in o}
    assert named == {"--text-filter"}, named
    assert set(options["--text-filter"].choices) == {"pii_ner", "pii_regex"}
    assert "ingest-raw" in parser_help


# --- S2: path boundary ---


def test_19_s2_symlink_and_dotdot_path_outside_base(tmp_path):
    base = tmp_path / "raw"
    outside = tmp_path / "secret.md"
    outside.write_text("dışarıda", encoding="utf-8")
    _stage(base, "confluence/DEMO/ok.md")
    link = base / "confluence" / "DEMO" / "link.md"
    try:
        os.symlink(outside, link)
        os.symlink(tmp_path, base / "confluence" / "up")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need privileges on this host; the container test covers them")
    Path(f"{link}.meta.json").write_text(
        json.dumps({"source": "confluence:DEMO", "source_item_id": "link"}), encoding="utf-8"
    )
    results = list(raw_staging.iter_staged(base, ["confluence:DEMO"]))
    assert _codes(results) == {"path_outside_base": 2}
    assert [i.path.name for i in _items(results)] == ["ok.md"]


def test_19_s2_dotdot_in_meta_attachment_rejected(tmp_path):
    _stage(tmp_path, "confluence/DEMO/a.md", attachments=["../../etc/passwd"])
    results = list(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"]))
    assert _codes(results) == {"path_outside_base": 1}


def test_19_s2_oversize_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(raw_staging.scope, "PLAINTEXT_MAX_BYTES", 10)
    _stage(tmp_path, "confluence/DEMO/big.txt", body="x" * 11)
    results = list(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"]))
    assert _codes(results) == {"too_large": 1}


def test_19_s2_meta_missing_or_invalid(tmp_path):
    (tmp_path / "confluence").mkdir()
    (tmp_path / "confluence" / "orphan.md").write_text("x", encoding="utf-8")
    bad = _stage(tmp_path, "confluence/bad.md")
    Path(f"{bad}.meta.json").write_text("{not json", encoding="utf-8")
    results = list(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"]))
    assert _codes(results) == {"meta_missing": 1, "meta_invalid": 1}


def test_19_s2_raw_dir_unchanged(tmp_path):
    _stage(tmp_path, "confluence/DEMO/a.md")
    before = sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*"))
    list(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"]))
    assert sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*")) == before


def test_19_s2_selection_limit_and_order(tmp_path):
    for name in ("c", "a", "b"):
        _stage(tmp_path, f"confluence/DEMO/{name}.md")
    # Walked before DEMO (path order); the limit stops the walk, it never skips silently.
    _stage(tmp_path, "confluence/A_OTHER/z.md", source="confluence:OTHER")
    results = list(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"], limit=2))
    assert [i.path.name for i in _items(results)] == ["a.md", "b.md"]
    assert _codes(results) == {"source_not_selected": 1}


def test_19_s2_metadata_for_ingest(tmp_path):
    path = _stage(
        tmp_path,
        "confluence/DEMO/7.md",
        title="Kurulum",
        breadcrumb="DEMO › Kurulum",
        source_url="https://wiki.example.test/7",
        updated_at_source="2026-09-01",
        author="Ayşe Yılmaz",
    )
    (item,) = _items(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"]))
    meta = raw_staging.metadata_for(item, kb_id="kb-1")
    assert meta == {
        "kb_id": "kb-1",
        "filename": "confluence/DEMO/7.md",
        "source": "confluence:DEMO",
        "source_item_id": "7",
        "title": "Kurulum",
        "breadcrumb": "DEMO › Kurulum",
        "source_url": "https://wiki.example.test/7",
        "updated_at_source": "2026-09-01",
        "attachments": [],
    }
    assert item.path == path.resolve()


# --- PRSIM in M3 (KARARLAR "PRSIM M3 ölçümüne girer", K-M3S-0008): explicit flag only ---


def test_19_s1_prsim_accepted_only_with_the_flag():
    assert raw_staging.check_sources(["jira:PRSIM"], accept_personnel_data=True) == ["jira:PRSIM"]
    with pytest.raises(StagingError):
        raw_staging.check_sources(["jira:PRSIM"])


def test_19_s1_prsim_meta_needs_the_flag_too(tmp_path):
    _stage(tmp_path, "jira/PRSIM/PRSIM-1.md", source="jira:PRSIM")
    flagged = list(raw_staging.iter_staged(tmp_path, ["jira:PRSIM"], accept_personnel_data=True))
    assert [i.relpath for i in _items(flagged)] == ["jira/PRSIM/PRSIM-1.md"]
    assert _items(flagged)[0].personnel_data is True
    plain = list(raw_staging.iter_staged(tmp_path, ["confluence:DEMO"]))
    assert _codes(plain) == {"prsim_requires_ner": 1}


def test_19_s1_cli_flag_is_named_and_explicit():
    sub = cli.build_parser()._subparsers._group_actions[0].choices["ingest-raw"]
    flag = next(a for a in sub._actions if "--accept-personnel-data" in a.option_strings)
    assert flag.default is False and flag.const is True


# --- r1 MINOR-1: PRSIM by source or by path, any `prsim*` segment ---


@pytest.mark.parametrize("source", ["jira:PRSIM2", "confluence:PRSIM-DOCS", "prsim_x"])
def test_19_r1_prsim_prefixed_sources_need_the_flag(source):
    with pytest.raises(StagingError):
        raw_staging.check_sources([source])


def test_19_r1_prsim_path_needs_the_flag_whatever_the_meta_says(tmp_path):
    _stage(tmp_path, "jira/PRSIM/PRSIM-1.md", source="jira:DEMO")
    plain = list(raw_staging.iter_staged(tmp_path, ["jira:DEMO"]))
    assert _codes(plain) == {"prsim_requires_ner": 1}
    flagged = list(raw_staging.iter_staged(tmp_path, ["jira:DEMO"], accept_personnel_data=True))
    assert _items(flagged)[0].personnel_data is True
