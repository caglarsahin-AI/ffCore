"""04b-1: the `migrate-vectors` command (exit 1 on any count mismatch, fail-loud) and the
`reindex --preset` checks that refuse before anything is queued (exit 2)."""

import uuid

import pytest

from ffcore import cli
from ffcore.knowledge import migrate


def _report(source: int, target: int) -> migrate.MigrationReport:
    return migrate.MigrationReport(
        source="pgvector",
        target="qdrant",
        dry_run=False,
        kbs=[
            migrate.KbMigration(
                kb_id=uuid.uuid4(),
                kb_key="sozlesme",
                source_count=source,
                target_count=target,
                written=source,
            )
        ],
    )


@pytest.mark.parametrize("source,target,code", [(5, 5, 0), (5, 6, 1), (5, 4, 1)])
def test_04b_1_migrate_vectors_exit_code_follows_counts(monkeypatch, capsys, source, target, code):
    seen = {}

    async def fake_run(**kwargs):
        seen.update(kwargs)
        return _report(source, target)

    monkeypatch.setattr(migrate, "run", fake_run)
    result = cli.main(
        ["migrate-vectors", "--project", "p", "--from", "pgvector", "--to", "qdrant", "--dry-run"]
    )
    out = capsys.readouterr().out
    assert result == code
    assert "sozlesme" in out and f"source={source}" in out and f"target={target}" in out
    assert seen["project_key"] == "p" and seen["kb_key"] is None and seen["dry_run"] is True
    assert seen["drop_target"] is False


def test_04b_1_migrate_vectors_same_driver_refused(capsys):
    code = cli.main(["migrate-vectors", "--project", "p", "--from", "qdrant", "--to", "qdrant"])
    assert code == 2 and "migrate_same_driver" in capsys.readouterr().err


def test_04b_1_mismatch_line_names_drop_target():
    lines = _report(5, 6).lines()
    assert any("mismatch" in line and "--drop-target" in line for line in lines)
    assert _report(5, 5).ok and not _report(5, 6).ok


@pytest.mark.parametrize(
    "argv,code",
    [
        (["--layer", "gold", "--preset", "timeout"], "preset_requires_silver"),
        (["--layer", "silver", "--preset", "bogus"], "preset_unknown"),
    ],
)
def test_04b_6_reindex_preset_refused_before_queue(capsys, argv, code):
    result = cli.main(["reindex", "--project", "p", "--kb", "k", *argv])
    assert result == 2 and code in capsys.readouterr().err
