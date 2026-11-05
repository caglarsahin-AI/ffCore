# Evaluation (exams)

FFCore Eval runs an agent version through a fixed set of questions, scores every answer, and
tells you per question *where* it failed: retrieval, reranking, the model, or not at all.

## Where things live

| What | Where |
|---|---|
| Questions (dataset items), exam runs, per-question scores | Langfuse (datasets, dataset runs, scores) |
| Suite (which dataset, scorers, threshold, gated agent), exam run summary | FFCore (`eval_suites`, `eval_runs`) |
| The answering itself | ordinary agent runs, `channel=test`, background class (`llm-background`) |

FFCore keeps no copy of the questions: edit them in Langfuse (its own CSV/JSON import) or seed
them with `make seed-eval`. One Langfuse project serves every FFCore project, so a suite's
dataset is named `<project_key>.` followed by lower-case letters, digits, `.`, `_` or `-`
(default `<project_key>.<suite_key>`, no `..`); another name is refused with
`422 dataset_name_not_in_project`.

## Item format

A Langfuse dataset item:

- `input`: `{"message": "...", "variables": {...}}`
- `expectedOutput`: `answer`, `must_contain[]`, `must_cite[]`, `sql_result[[...]]`, `regex`, `json`
  (each optional; a scorer with nothing to compare reports `not_run`, never a guess)
- `metadata`: `tags[]`, `answerable` (bool), `style` (`dogrudan`, `dolayli`, `alan_ici_cevapsiz`,
  `alan_disi_cevapsiz`), `expected_docs[]`

Write unanswerable questions about the *same* domain (a field that does not exist in a real
document) and indirect questions (the answer is in a document, the words are not): a set of
direct questions only makes quality look better than it is.

## Scorers

| Scorer | Passes when |
|---|---|
| `contains` | every `must_contain` text is in the answer (case and spacing ignored) |
| `regex` | `regex` matches the answer |
| `json_schema` | the answer is JSON valid against `json` |
| `cites_source` | every expected document is among the run's sources (matched by file stem) |
| `semantic` | cosine similarity of answer and `answer` ≥ `threshold` (default 0.8; bge-m3 dense) |
| `llm_judge` | the rubric judge gives ≥ `pass_min` of 5 (default 4) |
| `sql_result` | the rows of the agent's last executed `run_sql`, read again, equal `sql_result` (order-free) |
| `latency_cost` | the run stays within `max_ms` / `max_usd` |

Unanswerable items (`answerable: false`) are scored only by holding back: the agent must not
answer them. An item passes when every scorer that ran passed; a scorer error fails the item,
and so does an item no scorer could check (`nothing_scored`: suite and item do not fit).
`llm_judge` needs an expected `answer` (or `must_contain`); without one it is not run.

Prefer the deterministic scorers (`contains`, `cites_source`, `sql_result`). The judge is a
model; on a small local model it is the weakest signal.

### The judge runs in FFCore, not in Langfuse

Langfuse 3.120 OSS ships an LLM-as-a-judge evaluator, but it is configured only in its UI and it
calls the model directly. FFCore's judge instead:

- renders the Langfuse prompt `eval_judge_rubric_v2` (seeded from `backend/prompts/`; edit it
  in Langfuse),
- sends the text through the egress guardrail of the agent's policy first, like any model call,
- calls `EVAL_JUDGE_MODEL` as a background job (model slots, background window, quotas),
- keeps the question, expected answer and answer between markers and tells the model that
  text inside them is data, not instructions,
- reads the score from the JSON reply (a code fence is taken off) or from exactly one whole
  `SCORE: n` line; anything else is `judge_output_unreadable` / `judge_output_ambiguous`,
  never a guessed score.

Seeding never overwrites a prompt Langfuse already has. A new rubric text therefore ships under
a new prompt name (`eval_judge_rubric` → `eval_judge_rubric_v2`); after an upgrade run
`make seed` once so the new prompt exists. The old prompt stays in Langfuse, unused.

### SQL results

A run's event log does not keep query rows. `sql_result` therefore reads the agent's last
executed `run_sql` statement again through the same tool (read-only database, same validator)
with the exam starter's identity, audited as `eval_sql_check` (outcome `failure` when the read
was refused, failed or could not be made). Only a call the run really made is read again: the
last one with a successful tool result and, when it asked for an approval, approved by a person
(the exam never approves anything); the tool must be one the agent version was given,
discovered, its action available and enabled.

mcp-sql returns a refused query and a database error (timeout, connection, unknown column) as a
tool error whose text starts with its code (`sql_rejected: …`, `sql_error: …`); the run records
`is_error` and the code. The agent's model still reads the code and can correct the query; such
a call is never taken for a result.

The exam could not check (the item is not run, apart from the pass rate):

- a person rejected the agent's only `run_sql` (`approval_rejected`): the agent never saw rows;
- the read could not be made, e.g. the tool timed out (`sql_reread_failed`);
- the tool of the executed call was removed or disabled since (`tool_removed`).

The agent's failure (`sql_result` fails):

- no executed call (none, only failed ones, a tool it was not given): `no_executed_sql`;
- the read is refused or fails (`no_sql_result:sql_rejected`, `no_sql_result:sql_error`,
  `no_sql_result:tool_error`) or is cut (`sql_result_truncated`), never an empty result.

## Stage diagnosis (`outcome`)

Each answered item gets one `outcome`, the first stage it fell at (the order follows the search
code: the rerank floor is applied before the `top_k` cut):

| outcome | meaning |
|---|---|
| `not_retrieved` | an expected document is not among the hybrid candidates |
| `below_rerank_floor` | every candidate of an expected document is under the rerank floor |
| `not_reranked` | above the floor but not among the sources given to the model |
| `declined` | the model said it could not find it (the answer text is kept) |
| `below_threshold` | answered, confidence under the agent's threshold |
| `answered` | answered |
| `unanswerable_held` / `unanswerable_answered` | unanswerable item held back / answered |

`outcome` is the exam's own label and differs from a run's `outcome_label`. A retrieval failure
stays a retrieval failure whatever the judge thinks of the answer.

## Running an exam

```bash
docker compose run --rm tools make seed-eval PROJECT=<project_key>   # sample sets (13a), idempotent
```

```
POST /api/v1/projects/{project_id}/eval-suites/{suite_id}/run?agent_version_id=<uuid>
GET  /api/v1/projects/{project_id}/eval-runs/{id}          # status, items, scored, summary
GET  /api/v1/projects/{project_id}/eval-runs/{id}/stream   # SSE progress, then done
POST /api/v1/projects/{project_id}/eval-runs/{id}/cancel
```

Suites:

```
GET    /api/v1/projects/{project_id}/eval-suites
POST   /api/v1/projects/{project_id}/eval-suites        # creates the Langfuse dataset if missing
GET    /api/v1/projects/{project_id}/eval-suites/{id}
PATCH  /api/v1/projects/{project_id}/eval-suites/{id}   # given fields; agent_id null: no gate
DELETE /api/v1/projects/{project_id}/eval-suites/{id}   # soft; the dataset and its runs stay
GET    /api/v1/projects/{project_id}/eval-suites/{id}/runs
```

Starting checks every item first (a text `input.message`, known text variables) and the size
(items x `repeat` at most `EVAL_MAX_ITEM_RUNS`, else `422 eval_too_many_runs`), then writes
the exam `queued` with a snapshot of the suite (`config`: scorers, threshold, `repeat`,
`approve_tools`). A suite change applies to the next exam, never to a running one.

The background worker then starts `repeat` background runs per item of that version for the
caller (a project member; read-only access cannot start one) and turns the exam `running`. It
advances each exam every `EVAL_ADVANCE_INTERVAL_S` seconds, one worker at a time (a lock per
exam): it scores finished items, links each run's trace into the Langfuse dataset run, writes
the scores and commits each item on its own. A separate follower task of the worker keeps the
item runs listened, so a long tick never abandons them.

A tick has a budget per exam: at most `EVAL_JUDGE_CALLS_PER_TICK` judge calls; no judge call
while `BACKGROUND_WINDOW` is closed (the judge is a background model call); and a deadline 30 s
before the tick's own 600 s timeout. The first item of a tick always starts (cut at the
deadline if it takes longer); a later item starts only if its judge calls, planned at
`LLM_CALL_TIMEOUT_S` each, fit before the deadline. When the budget runs out the exam simply
stays `running` and the next tick goes on: a closed window or a slow CPU judge never fails an
exam.

Runs that ask the user a question are cancelled (`not_run: waiting_user`). Runs that wait for a
tool approval are cancelled as `not_run: approval_required` (their pending approval is closed,
the cancel audited) unless the suite has `approve_tools: true`; then they wait in the normal
approval queue for a person and go on in the background queue after the decision; one that
expires there makes the item `not_run: approval_expired`. The exam never approves anything.
Not-run items are counted apart and left out of the pass rate, and the summary's `complete`
is false: the exam did not finish unattended. With `repeat > 1` a not-run repeat is left out
of the item's result and counted in `not_run` as `partial:<code>` (so `complete` is false too);
a scorer error in any repeat stays an error.

A tick that keeps failing without saving any item (`MAX_ATTEMPTS` ticks in a row, a tick
timeout included) ends the exam `failed` with the error code; a failed tick that saved an item
made progress and starts the count again. Nothing stays `queued` or `running` forever. The
exam lock is renewed and released only by its holder; when a renewal fails the tick stops
rather than work on without the lock. To stop an exam, use `cancel`.

## Langfuse 3.120 notes (measured)

- The Python SDK cannot read this server's dataset items; FFCore uses the REST API (L13).
- `GET /scores` ignores trace filters in v1 and v2 and returns every score: FFCore reads
  scores only by their deterministic ids (`<traceId>-<scorer>`, v2 `scoreIds`) and fails loud
  on any row it did not ask for (L12).
- Dataset run items and trace scores written a moment ago may not be readable yet; a reader
  polls for a short, bounded time (L17).
- A connection error or timeout towards Langfuse is `langfuse_unreachable`, counted per item
  like any other Langfuse failure.

## Summary and threshold

`summary`: items and how many were scored, pass rate, `passed` (pass rate ≥ the suite's
`pass_threshold`), mean per scorer, `outcome` counts, per-`style` breakdown, the 10 worst items,
errors, and timing. There is no model-server reset before an exam: the first run's time is
reported as `warmup_ms` and left out of `latency_ms`.

Thresholds are configuration, not code: `EVAL_PASS_THRESHOLD` is the default for new suites
(`llmaas` 0.85, `airgap` 0.8); a suite may set its own. Calibrate it on a few exam runs of a
version you trust, not on one run.

## Configuration

| Variable | Meaning |
|---|---|
| `EVAL_PASS_THRESHOLD` | default pass threshold of a new suite; empty: every suite names its own |
| `EVAL_JUDGE_MODEL` | model key (in the suite's project) of `llm_judge`; empty: `llm_judge` refused |
| `EVAL_ADVANCE_INTERVAL_S` | advancer tick; divides 60 and stays below `RUN_ABANDON_GRACE_S` |
| `EVAL_MAX_ITEM_RUNS` | most items x `repeat` in one exam (default 500) |
| `EVAL_JUDGE_CALLS_PER_TICK` | judge calls per exam per advancer tick (default 20) |
