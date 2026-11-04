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
dataset is always named `<project_key>.<suite_key>`; another name is refused with
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
| `sql_result` | the rows of the agent's approved `run_sql`, read again, equal `sql_result` (order-free) |
| `latency_cost` | the run stays within `max_ms` / `max_usd` |

Unanswerable items (`answerable: false`) are scored only by holding back: the agent must not
answer them. An item passes when every scorer that ran passed; a scorer error fails the item.

Prefer the deterministic scorers (`contains`, `cites_source`, `sql_result`). The judge is a
model; on a small local model it is the weakest signal.

### The judge runs in FFCore, not in Langfuse

Langfuse 3.120 OSS ships an LLM-as-a-judge evaluator, but it is configured only in its UI and it
calls the model directly. FFCore's judge instead:

- renders the Langfuse prompt `eval_judge_rubric` (seeded from `backend/prompts/`; edit it in
  Langfuse),
- sends the text through the egress guardrail of the agent's policy first, like any model call,
- calls `EVAL_JUDGE_MODEL` as a background job (model slots, background window, quotas),
- refuses unreadable output (`judge_output_unreadable`) instead of guessing a score.

### SQL results

A run's event log does not keep query rows. `sql_result` therefore reads the agent's last
`run_sql` statement again through the same tool (read-only database, same validator) with the
exam starter's identity, audited as `eval_sql_check`. A cut result (`[truncated: ...]`) fails.
Only statements a person approved are read again: the exam never approves anything.

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

Each item becomes `repeat` background runs of that version for the caller (a project member;
read-only access cannot start one). The background worker advances the exam every
`EVAL_ADVANCE_INTERVAL_S` seconds: it follows the runs (so they are not abandoned), scores
finished items, links each run's trace into the Langfuse dataset run and writes the scores.

Runs that ask the user a question are cancelled (`not_run: waiting_user`). Runs that wait for a
tool approval are cancelled as `not_run: approval_required` unless the suite has
`approve_tools: true`; then they wait in the normal approval queue for a person; one that
expires there makes the item `not_run: approval_expired`. Not-run items are counted apart and
left out of the pass rate, and the summary's `complete` is false: the exam did not finish
unattended.

A tick that keeps failing ends the exam `failed` with the error code; nothing stays `running`
forever. To stop an exam, use `cancel`.

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
