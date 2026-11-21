# Evaluation (exams)

FFCore Eval runs an agent version through a fixed set of questions, scores every answer, and
tells you per question *where* it failed: retrieval, reranking, the model, or not at all.

## Where things live

| What | Where |
|---|---|
| Questions (dataset items), exam runs, per-question scores | Langfuse (datasets, dataset runs, scores) |
| Suite (which dataset, scorers, threshold, gated agent), exam run summary | FFCore (`eval_suites`, `eval_runs`) |
| The answering itself | ordinary agent runs, `channel=test`, background class (`llm-background`) |

Votes on ordinary runs are other Langfuse scores and never count in an exam: `expert_feedback` is an
expert's review (F9, the runs screen), `user_feedback` the chat user's own vote on their answer
(11-2, docs/chat.md). Filter on the score name to keep the two apart.

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
- sends the text through the egress guardrail of the agent's policy first, like any model call
  (with `GUARDRAIL_EGRESS_NER=true` that check asks the API's NER endpoint for person names; if
  it is down nothing is sent and the item is not run, `ner_unavailable`, counted apart: an
  outage is not the agent's score; the exam's `complete` is then false, so it cannot pass a
  publish gate that asks for a complete exam until it is run again; an NER endpoint that
  answers with one of its configuration codes (`ner_not_configured`, `model_missing`,
  `ner_label_unknown`, `ner_offsets_unavailable`), refuses the request (any 4xx) or runs another
  model than the worker expects (`ner_model_mismatch`) is a configuration error instead: the
  tick fails loudly and the exam ends `failed(advance_failed:ner_misconfigured)` after
  `MAX_ATTEMPTS` ticks; a 5xx without such a code or no answer at all is the outage. The worker
  decides by the API's status and error code, never by the text of a message),
- calls `EVAL_JUDGE_MODEL` as a background job (model slots, background window, quotas),
- keeps the question, expected answer and answer between markers and tells the model that
  text inside them is data, not instructions,
- reads the score from the JSON reply (a code fence is taken off) or from exactly one whole
  `SCORE: n` line; anything else is `judge_output_unreadable` / `judge_output_ambiguous`,
  never a guessed score.

Seeding never overwrites a prompt Langfuse already has. A new rubric text therefore ships under
a new prompt name (`eval_judge_rubric` → `eval_judge_rubric_v2`); after an upgrade run
`make seed-prompts` once so the new prompt exists. The old prompt stays in Langfuse, unused.

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

A tick has a budget, shared by the exams it advances in a fixed order (the oldest progress
first). Its deadline is 30 s before the tick's own 600 s timeout (570 s after it starts); of
that, a tick may spend up to 30 s before its first item, which leaves a usable window of 540 s
(`TICK_PLAN_S`). A judge call is planned at `EVAL_JUDGE_CALL_S`, an estimate;
`LLM_CALL_TIMEOUT_S` stays the hard limit of each call. An item without a judge is planned at
one `EVAL_JUDGE_CALL_S` too. Rules:

- No judge call while `BACKGROUND_WINDOW` is closed (the judge is a background model call).
- Every item, a tick's first one too, starts only if its planned time fits before the
  deadline; otherwise the exam waits, still `running`, nothing committed, and keeps its place.
- The first item of an exam in a tick ignores `EVAL_JUDGE_CALLS_PER_TICK`; a later one starts
  only if its judge calls fit in what is left of it. So a tick makes at most
  `EVAL_JUDGE_CALLS_PER_TICK` judge calls per exam, or the first item's calls (`repeat`) when
  that is more.
- A plan up to 540 s can start in a tick; a longer one can start in none. Such an item ends
  at once (`judge_out_of_time`, note `planned_exceeds_tick_budget`), and starting an exam with
  `llm_judge` whose `repeat` x `EVAL_JUDGE_CALL_S` is over 540 s is refused up front:
  `422 eval_plan_exceeds_tick`. Nothing in between waits forever, as long as a tick's own
  work before its first exam stays under `TICK_OVERHEAD_S` (30 s); when it does not, the
  worker logs the warning `eval_tick_overhead_exceeded overhead_s=<seconds>` (once per tick).
- An item running past the deadline is cut. The cut counts only if the item started with a
  full window: its calls at `LLM_CALL_TIMEOUT_S`, at most 540 s. A cut in a shorter window
  (earlier exams used the tick) counts nothing and commits nothing; the exam keeps its place
  and gets a full window first. An item cut in a full window `MAX_ATTEMPTS` ticks in a row ends
  as an error (`judge_out_of_time`) and the exam moves on. So `EVAL_JUDGE_CALL_S` only decides
  whether an item is worth starting in a tick, never whether it fails.
- A single call is never longer than the tick allows: with `LLM_CALL_TIMEOUT_S` above 540 s
  the tick still cuts it at its deadline (at most 570 s after the tick starts), and that cut
  counts when the item had the full 540 s window.
- The first item of the first exam a tick advances always counts its cut, whatever its window:
  nothing ran before it in that tick, so a tick whose own work keeps eating the window still
  ends a hung item after `MAX_ATTEMPTS` ticks.
- Scores an earlier, cut attempt of such an item already wrote to Langfuse stay there (upserted
  by id); the exam's own result in FFCore is the error.

A closed window or a slow judge never fails an exam by itself. Set `EVAL_JUDGE_CALL_S` to an
upper-end estimate of one judge call (on airgap with a CPU judge, `LLM_CALL_TIMEOUT_S` 600 s,
measure it), and keep `repeat` x `EVAL_JUDGE_CALL_S` at most 540 s.

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
timeout included) ends the exam `failed` with the error code. Only a tick that committed
something (an item scored, the item runs started) starts the count again; a tick that saved
nothing leaves it as it is. Nothing stays `queued` or `running` forever. The
exam lock is renewed and released only by its holder; when a renewal fails the tick stops
rather than work on without the lock. To stop an exam, use `cancel`.

## Comparing two exams

```
GET /api/v1/projects/{project_id}/eval-runs/compare?a=<eval_run_id>&b=<eval_run_id>
```

Both exams must be `completed` and of the same suite (else `422 eval_runs_not_comparable`).
The comparison reads FFCore's own item results (the same per-item combination the summary
uses), not Langfuse. Each item gets a `change`: `fixed`, `regressed`, `same`, `not_comparable`
(not run in either exam: nothing is guessed), `only_a`, `only_b`; with `mean_delta` (b - a over
the scorers that ran). The answer also has the summary differences (pass rate, scored, passed
items, scorer means, outcome counts, not-run counts), the 10 worst items (regressions first,
then the largest drops), each exam's `complete` and `config_differs` (scorers, threshold,
`repeat` or `approve_tools` differ: compare with care). A reader can compare.

## The publish gate

A suite bound to an agent (`agent_id`) gates `POST /agents/{id}/publish {version}`. For every
live suite bound to the agent, the version needs a latest completed exam that:

- examined the version as it is now: an exam records the digest of the definition it examines
  (`config.definition_sha256`, sha256 of the definition's canonical JSON); a draft edited after
  its exam no longer matches, and the exam is `stale_exam` (so is an exam without a digest),
- ran with the suite as it is now: the suite's `scorers`, `pass_threshold` and `repeat` must be
  the ones in the exam's snapshot, else `stale_suite` (`approve_tools` is not compared: a
  change to `false` is `suite_not_gateable` or an incomplete exam already; the scorer list is
  compared as it is stored, so reordering it also asks for a new exam). The suite's
  Langfuse dataset items are not compared: an item edited or added in Langfuse after the exam
  does not make it stale; run the exam again after changing the dataset,
- `passed` (pass rate at least the suite's threshold),
- is `complete` and has nothing in `not_run` (an approval rejected or never given, a user
  question, an NER outage: the exam did not finish unattended).

Otherwise publishing is `409 eval_gate_failed`; the message names each suite as
`<key>=<reason>`: `no_exam`, `stale_exam`, `stale_suite`, `not_passed`, `incomplete`, or
`suite_not_gateable`. The last one: a suite with `approve_tools: false` cannot gate a version
that binds an action asking for approval (the exam can never complete unattended); set
`approve_tools: true` on that suite, or leave it unbound. A suite on an agent without such
actions gates with `approve_tools: false`.

A draft edit that changes the definition (`PUT .../versions/{n}`) ends the version's queued and
running exams `failed(definition_changed)` in the same transaction, even if a later edit puts
the old definition back: item runs may already have run with the other one. Their item runs
still going finish unscored. The advancer also checks the digest at every tick, so an exam that
has no digest (started before this check existed) ends `failed(definition_changed)` too.
Publishing and editing a draft of the same agent lock the agent row and run one after the
other, so a publish never takes a definition that changed while the gate was checked.

The published version keeps the exam that opened the gate in `eval_run_id` (with several suites,
the latest of the exams that passed). It is null when the agent has no bound suite or when the
publish was forced past a failing gate; a `force` on a gate that passes keeps the exam.

An admin may publish past the gate: `{"version": n, "force": true, "force_reason": "..."}`.
Anyone else gets `403 force_requires_admin`; a force without a reason (or a blank one) is
`422 force_reason_required`, a `force_reason` without `force` is `422
force_reason_without_force`. A forced publish past a failing gate is audited as
`eval_gate_forced` with each failing suite (`suite_id`, `key`, `eval_run_id`, `reason`) and the
reason as given (trimmed); through an API key the audit row carries the key (`via_key_id`).
`rollback` is not gated: it returns to a version that was published before. An agent without a
bound suite publishes as before.

## An exam item from a run

```
POST /api/v1/projects/{project_id}/eval-suites/{suite_id}/items/from-run/{run_id}
{"expected": {"answer": "...", "must_contain": ["..."]}, "style": "dolayli", "answerable": true}
```

Saves a run's question (and its variables) as an item of the suite's Langfuse dataset, with the
expected output given here (keys as in "Item format"). The caller is an editor of the project
(analyst or above, edit mode); the run must be `completed` and in the project (another
project's run is 404).

Before anything leaves for Langfuse the question, its variables and the expected output go
through the egress stage of the agent version's guardrail policy in the API process, with one
token store: identifiers are tokenized (`<<PII_n>>`), and a value the question and the expected
output share gets the same placeholder, so `must_contain` still matches what the agent is asked.
The answer's `masking` says what the agent's egress rules really mask, as the engine runs them:

- `none`: nothing (the policy is `off`, its egress PII rule only monitors, or no masking
  category is on). The item is stored as the run was asked.
- `regex`: identifiers only (TC number, e-mail, phone, IBAN, card). **With
  `GUARDRAIL_EGRESS_NER=false` a person's name is written to the Langfuse item as it was asked.**
  Langfuse runs in-house; this is the accepted behaviour for tests and airgap. An installation
  whose runs carry personnel or patient names sets `GUARDRAIL_EGRESS_NER=true`.
- `regex+ner`: person names are masked too (the API's NER, `engine: ner` at egress, `PERSON`
  on).

`masked_fields` lists which of `message`, `variables`, `answer` and `must_contain` were saved
masked. A placeholder in `answer` or `must_contain` is what the masked question leads to; but an
agent that reads the real value from another source (a tool, a document) answers with it, and
such an item then fails `contains`: give these expectations without personal data where you can.
`sql_result`, `must_cite` and `regex` are compared with real rows, ids or text, where a
placeholder never matches: if masking would change one of them the request is
`422 expected_would_be_masked` and nothing is saved.

The exam then asks the agent the masked question (placeholders, not the original values): the
mapping is not kept.

A blocked text is `422 run_input_blocked`; a guardrail policy error is a coded `422` (its own
code, e.g. `rule_type_unsupported`), a text over the engine's limit `422 text_too_long`; an NER
outage is `503 ner_unavailable` and an NER that is not configured `503 ner_not_configured` (or
the API's other NER code); a failed Langfuse call is `502`. Nothing is saved then, but the
refusal is audited as `eval_item_from_run` with outcome `error` and its `error_code` (no text);
a blocked text keeps the guardrail events that blocked it. The item id is
`<suite_key>-run-<run_id>` (saving the same run again updates it); its metadata says
`source: from_run`. Audited as `eval_item_from_run` without the text. The console's "add to
exam" button is FOLLOWUP-170.

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
reported as `warmup_ms` and left out of `latency_ms`. Its shape is the `EvalSummary` schema of
09.yaml (10c-2): every key `summarize()` writes, typed; a unit test holds the two together. A
stored summary that does not fit it (an older shape, a partial write) is answered as
`summary: null` and logged as `eval_summary_invalid` with the exam id and the missing or invalid
keys; the exam and the suite's exam list still answer 200.

**Every item** (10c-2, FOLLOWUP-185): `GET /projects/{pid}/eval-runs/{id}/items` with
`status=all|failed|passed|not_run` (default `all`), `limit` 1-200 (default 50) and `offset`
answers `{data, total, limit, offset}`. Each row is the item combined from its runs exactly as
the summary and compare combine it (`passed`, `mean`, `outcome`, `note`, `repeats_not_run`,
`attempts`, `run_ids`, and every scorer's `value`, `passed`, `status`, `comment`), read from
FFCore's own results, never from Langfuse. Order: failed, not run, passed, not yet scored, then
item id; a not-yet-scored item (`scored=false`) is listed only under `all`. Analyst and read
access; another project's exam is 404.

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
| `EVAL_JUDGE_CALL_S` | planned seconds of one judge call, an upper-end estimate (default 60, at most 540); not the hard limit (`LLM_CALL_TIMEOUT_S`) |
