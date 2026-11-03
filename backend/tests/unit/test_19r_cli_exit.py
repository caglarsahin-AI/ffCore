"""Review r1 MAJOR-1 (K-19R-0013 A): `ingest-raw` exits 1 when a file failed before it was
registered (no document row): fail-loud, a run with such a file never looks clean."""

from pathlib import Path

from ffcore import cli
from ffcore.knowledge import raw_ingest


def test_19r_r1m1_cli_exits_1_on_unregistered_failure(monkeypatch, tmp_path, capsys):
    report = raw_ingest.RawIngestReport()
    report.files.append(("confluence/DEMO/9001.md", "0" * 64, "confluence:DEMO"))
    report.unregistered.append(("confluence:DEMO", "confluence/DEMO/9001.md", "ValueError"))

    async def fake_tree(**_):
        return report

    monkeypatch.setattr(raw_ingest, "ingest_tree", fake_tree)
    raw = tmp_path / "raw"
    raw.mkdir()
    code = cli.main(
        [
            "ingest-raw",
            "--project",
            "p",
            "--kb",
            "k",
            "--raw-dir",
            str(raw),
            "--acl",
            "analyst",
            "--sources",
            "confluence:DEMO",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "failed_unregistered 1" in out
    assert Path("confluence/DEMO/9001.md").as_posix() in out
