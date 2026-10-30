# Approvals (FFCore Agents, package 07)

A tool action marked `needs_approval` stops its run before it executes. A person sees the call,
with its arguments masked by the guardrail, and approves or rejects it. Who decided, when and why
is recorded. An approval nobody decides expires and the run is closed.

LangGraph's `interrupt` and checkpoint (06a) hold the run; 07 adds the queue, the decision rules
and the expiry. There is no second state machine.

## Flow

1. The run reaches a tool call that needs approval. 07 opens one approval for that tool call
   (`run_id`, `tool_call_id`), 06a interrupts, the run becomes `waiting_approval` and the SSE
   stream sends `approval_required` with `approval_id` and `expires_at`.
2. A person approves or rejects. The run continues from its checkpoint; on reject the model gets
   "The approver rejected this action." with the note.
3. If nobody decides within `APPROVAL_TTL_MIN` minutes, a scheduled job marks the approval
   `expired` and closes the run as `failed` with the code `approval_expired`.

The same action with the same arguments in the same run is not asked twice once approved. The
run records `approval_reused` with the approval's id; nothing is skipped silently. A run whose
worker has no approval queue fails with `approval_gate_missing` instead of running the call.

## Who sees and who decides

| Caller | List and detail | Approve or reject |
|---|---|---|
| Project member, `analyst` or above, `edit` | yes | if role ≥ the approval's `assigned_role` |
| Project member, `analyst` or above, `read` | yes | no, 403 `read_only_access` |
| Project member with role `user` | no, 403 | no |
| Service account, API key, or a user reached through `X-On-Behalf-Of` | no | no, 403 `approval_requires_user_session` |

`assigned_role` comes from the agent definition (`approval.assign_to`, default `analyst`; never
`user`). Each item carries `can_decide` for the console buttons; the decision route checks
again. Every decision is audited as `approval.approved` or `approval.rejected` with the actor,
the masked arguments and the note. Refusals are audited as `denied`.

## API

All routes are under `/api/v1/projects/{project_id}/approvals` (contract: `backend/openapi/07.yaml`).

| Route | Purpose |
|---|---|
| `GET /` with optional `status` | the project's approvals, newest first |
| `GET /count` with `status` (default `pending`) | count for the console badge |
| `GET /{approval_id}` | one approval; another project's id is 404 |
| `POST /{approval_id}/approve` with `{"note"?}` | approve and continue the run |
| `POST /{approval_id}/reject` with `{"note"?}` | reject; the model gets the note and goes on |

A decision answers with the approval and `stream_after`. The client follows the rest of the run
with `GET /api/v1/projects/{project_id}/runs/{run_id}/stream` and `Last-Event-ID: <stream_after>`.

| Error | When |
|---|---|
| 404 `approval_not_found` | unknown id, or an id of another project |
| 409 `approval_not_pending` | already decided or expired, or a second click |
| 409 `approval_expired` | the TTL passed before the expiry job marked it |
| 409 `run_not_waiting` | the run was cancelled meanwhile; the approval stays pending until it expires |

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `APPROVAL_TTL_MIN` | 60 | minutes an approval waits before it expires |
| `APPROVAL_ALERT_AGE_MIN` | 30 | a still pending approval older than this is reported once as `approval_pending_age` |

Waiting time does not count against the run timeout (`RUN_TIMEOUT_S`); the approval TTL is
counted separately. The background agent worker (`agent-worker-bg`) runs the sweep every minute:
it expires what is due, closes those runs (`failed`, `approval_expired`, events
`approval_expired` and `error`) and reports old pending approvals. Expiring an approval and
closing its run are one transaction: if closing fails, both stay as they were and the next minute
tries again; an approval already expired while its run still waits is closed on the next run.

Events are stored before they are sent live. If the live send fails after the close is stored
(Redis error), the run is still `failed` with its `error` event in `run_events`, and the sweep
logs the failure. A client that follows the run, or reconnects with `Last-Event-ID`, gets the
stored `error` after two empty keepalive turns and the stream ends; it does not wait forever.

### Test hook: run the sweep now

End-to-end tests cannot wait the TTL. With `FFCORE_TEST_HOOKS=1` (default off; never set it in
a deployment) the backend has `POST /api/v1/internal/approvals/sweep?now=<ISO 8601 with time
zone>`. It is for the service account only and runs the same sweep as the minute job with that
`now`. The answer is `{"expired": [<approval ids>]}`. A second call with the same `now` expires
nothing more. When the flag is off, the path answers 404 like an unknown path, before any
identity check. The hook is not in the OpenAPI contract.

| Answer | When |
|---|---|
| 404 `not_found` | `FFCORE_TEST_HOOKS` off |
| 403 `service_account_required` | any caller but the service account |
| 422 `now_without_timezone` | `now` without a time zone |

## Not yet

- E-mail notification and the `approval_pending_age` alert come with 03c (notification
  settings, alerts). Until then the console badge, the SSE event and the log line are the
  signals.
- Approving from a chat channel (Slack, Teams) is package 15, through a verified channel
  identity only.
- Conditional approval rules ("amount above X") are out of scope.
