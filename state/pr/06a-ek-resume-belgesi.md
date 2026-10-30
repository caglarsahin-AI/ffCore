# 06a ek: `docs/agentlar.md` için `resume_run` bölümü (taslak, K-06a-0019)

Review r2 bitince tek commit'le `docs/agentlar.md`'ye "## Runs" altına, "### What happens in a run"dan önce eklenecek. Metin İngilizce (uygulama belgesi). `docs/agent-runtime.md` adında dosya yok; 06a'nın belgesi GOREV gereği `docs/agentlar.md`, yeni dosya açmak tek konuyu ikiye böler.

---

### Resuming a run from another package (07 approvals)

`POST /runs/{id}/resume` and 07's approval endpoints share one function:

```python
from ffcore.runtime.resume import resume_run

after = await resume_run(
    session,            # AsyncSession; committed inside
    queue,              # RunQueue (ffcore.runtime.queue.get_run_queue(settings))
    settings,           # Settings
    project_id=...,     # UUID; the run must belong to this project (else 404 run_not_found)
    run_id=...,         # UUID
    actor=...,          # ffcore.core.auth.Actor of the caller
    decision="approved",  # or "rejected"; for a run in waiting_approval
    answer=None,        # the user's answer; for a run in waiting_user
    comment=None,       # shown to the model with a rejection
    request_id=None,    # audit; a new id when omitted
    ip=None,            # audit
)
```

It returns the id of the last live event (`<seq>-<n>`, or `None` before any), so the caller can
follow the stream from there (`GET /runs/{id}/stream` with `Last-Event-ID`).

What the function checks (the same for every caller):

| Rule | Error |
|---|---|
| The run is `waiting_approval` or `waiting_user` | 409 `run_not_waiting` |
| `waiting_approval` takes a decision and no answer; `waiting_user` an answer and no decision | 422 `decision_required` / `answer_required` |
| A decision comes from a signed-in user: `actor_type == "user"` and not `via_service` | 403 `approval_requires_user_session` |
| An answer comes from the run's own user | 403 `not_run_user` |
| One resume per wait: the status change to `queued` is the lock | 409 `run_not_waiting` |

What the caller checks: the role. `/resume` requires the definition's `approval.assign_to` (default
`analyst`) with `edit` access; 07 applies the approval's assigned role. The function writes the
audit event (`resolve_approval` or `answer_run_question`) in the same transaction, marks the run
as listened and queues the next attempt; the worker continues from the checkpoint.
