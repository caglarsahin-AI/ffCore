"""FOLLOWUP-116: the sources kept in the checkpointed run state carry no chunk text."""

from ffcore.runtime import graph
from ffcore.runtime.prompting import Source


def _source(n: int, score: float) -> Source:
    return Source(
        n=n,
        kb_key="sozlesmeler",
        chunk_id=f"c{n}",
        document_id=f"d{n}",
        document_name="fesih.md",
        page=None,
        breadcrumb="Fesih",
        text="gizli-parca-116",
        updated_at_source=None,
        rerank_score=score,
    )


def test_116_8_source_state_has_no_text():
    kept = graph._source_payload([_source(1, 0.9), _source(2, 0.4)])
    assert all("text" not in s for s in kept)
    assert kept == [_source(1, 0.9).public(), _source(2, 0.4).public()]
    # finalize reads only n and rerank_score from the kept sources.
    assert graph._cited("Otuz gün [1].", kept) == [kept[0]]


def test_116_9_checkpoint_sweep_cron_on_background_worker_only():
    from ffcore.runtime.contracts import JobClass
    from ffcore.runtime.worker import cron_jobs_for, sweep_checkpoints

    [job] = [j for j in cron_jobs_for(JobClass.background) if j.coroutine is sweep_checkpoints]
    assert job.unique and job.second == 30 and job.minute is None
    assert cron_jobs_for(JobClass.interactive) == []
