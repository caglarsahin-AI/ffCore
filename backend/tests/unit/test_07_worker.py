"""07: the approval sweep runs on the background agent worker only, once per minute (S4)."""

from ffcore.runtime.contracts import JobClass
from ffcore.runtime.worker import cron_jobs_for, expire_approvals


def test_07_sweep_cron_on_background_worker_only():
    # The background worker carries other sweeps too (FOLLOWUP-116); this is the 07 one.
    [job] = [j for j in cron_jobs_for(JobClass.background) if j.coroutine is expire_approvals]
    assert job.unique and job.second == 0 and job.minute is None
    assert cron_jobs_for(JobClass.interactive) == []
