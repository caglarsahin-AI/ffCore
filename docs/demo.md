# PoC demo

The M3 demo of FFCore: what to run, what to show in 15 minutes, and what each step proves. Every
step uses synthetic data from `data/samples/`; nothing here connects to a real ticket, mail or chat
system. Use cases are those of `plan/18-kullanim-senaryolari.md` (F1-F13).

Two kinds of evidence, never mixed:

- **Pipeline evidence** comes from the scenario stack with `fake-llm` (`make e2e`, `make eval
  MODEL=fake-llm`): the platform's own behaviour (sources, approvals, masking, isolation, outages).
  `fake-llm` answers "hello"; a check that depends on what a real model answers is **NOT_RUN**,
  never passed.
- **Quality evidence** comes from a real model: `make eval` on the PayCore server (`airgap`, Qwen
  CPU) by the user, or on an `llmaas` provider. Its results fill the tables at the end.

## Run it

The scenario stack is the test stack with the `e2e.env` overlay (`tests/e2e/scenarios/README.md`).
Passwords come from your shell, never from a file.

```bash
export FFCORE_VERSION=0.0.0 E2E_ADMIN_EMAIL=e2e-admin@example.test E2E_ADMIN_PASSWORD=... E2E_PASSWORD=...
C="docker compose --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test"
$C up -d --wait
$C run --rm -e E2E_ADMIN_EMAIL -e E2E_ADMIN_PASSWORD -e E2E_PASSWORD tools make seed
$C run --rm -e E2E_PASSWORD tools make e2e
$C run --rm -e E2E_PASSWORD tools make eval MODEL=fake-llm APPROVE_SQL=1
```

- `make seed` (idempotent): two projects (`hastane-a`, `klinik-b`) and their members (admin edit,
  admin read, analyst edit), the fake-llm models, knowledge bases with the contracts, poisoned
  procedures and two contract versions, the `mcp-sql` and `ticket-desk` tools, the demo database,
  every agent template. Its last line says what it changed; a second run says `created 0,
  uploaded 0`.
- `make e2e`: every API e2e test (plan/18 scenarios and the negative set) and the **F table**
  (one row per use case: passed / failed / NOT_RUN with reasons) in `eval/results/e2e-<time>.md`.
- `make eval`: the exam set through the run API, report in `eval/results/eval-<time>.md`:
  outcome labels, source accuracy (expected document cited), answers holding the expected text,
  unanswerable questions held, SQL results, answer time, LLM calls per question. `MODEL` names what answered (required); `APPROVE_SQL=1` approves each `run_sql`
  call (without it SQL items are NOT_RUN); `llm_judge` is NOT_RUN until M3 picks a judge model.
- The console's own browser tests are a separate service: `docker compose --profile e2e run --rm
  e2e` (docs/onyuz.md).

Last pipeline run (main 3f2bc31 + feat/13b-e2e-eval, 30 October 2026): stack up 88 s, first seed
60 s (36 created, 15 uploaded), second seed 27 s (0, 0), `make e2e` 70 s: **62 passed, 0 failed,
23 not run**, every F row passed; `make eval MODEL=fake-llm APPROVE_SQL=1` 28 s for 33 items
(pipeline only: the right contract is among the sources for 19 of 20 document questions; the
answers are "hello").

## The 15 minutes

Sign in to the console as `hastane-a-analyst-edit@example.test` (project `hastane-a`); one step
needs `hastane-a-admin-read`, one `klinik-b-admin-edit`.

| Min | Use case | Screen | What the audience sees | Evidence |
|---|---|---|---|---|
| 0-1 | (context) | Home, System status | One gateway, every model call through it; the status page shows the knowledge worker ready and the model list. | `/readyz`; Setup row of the F table |
| 1-3 | F1 Document assistant with sources | Agents → `sozlesme-asistani` → test panel | Ask about the notice period of the device maintenance contract: the answer names the contract and clause it used; the run shows a `sources` event with the document and its breadcrumb (article number and short title, never clause text). | `test_18_f1_1`, `f1_1b` passed; exam score → real model |
| 3-5 | F2 Ticket reply with approval | Agents → `e2e-bilet`, then Approvals | The assistant drafts a reply to ticket `tkt-001`; `send_reply` waits in the approval queue. Switch to `hastane-a-admin-read`: the decide buttons are off and the API says 403. Approve as the analyst: the fake ticket desk records exactly one reply. Reject another: nothing is sent. | `test_18_f2_7`-`f2_10` passed |
| 5-7 | F3 Read-only data questions | Agents → `e2e-sql`, Approvals, Runs | One `run_sql` call waits for approval, then runs on the read-only demo database. Fifteen disguised writes are refused with their codes; table row counts stay the same. | `test_18_f3_8`, `f3_9` passed; `sql-20` ≥ 80 % → real model |
| 7-9 | F4 Managed LLM gateway | Runs → run detail | A message with a synthetic national ID: the provider receives only a placeholder (built-in egress rule, enforced). Follow the run to its LiteLLM call id and its Langfuse trace. | `test_18_f4_1`, `f4_1c`, `f4_2`, `f4_2b` passed; quotas → 03c |
| 9-10 | F9 Expert review (PoC-lite) | Runs | Vote correct / partly / wrong with a note; the run leaves the "pending" view. A read-only user gets 403. | `test_18_f9_1`, `f9_2` passed |
| 10-12 | F10 Project isolation and audit trail | Knowledge, Runs (as `klinik-b-admin-edit`) | `klinik-b`'s admin cannot see `hastane-a`'s knowledge bases, documents, tools, agents or runs, in lists or by direct id (404, nothing leaks). Delete a document after a run: the run still names it, its breadcrumb reads `[deleted]`. | `test_18_f10_4`-`f10_7` passed (FOLLOWUP-103, 108 closed) |
| 12-13 | F11 Poisoned documents (PoC-lite) | Agents → `zehirli-belge-asistani` | Five procedures hide an instruction; it reaches the model only inside SOURCES, framed as data, and no tool is called. | `test_18_f11_5[P1-P5]` passed; following or resisting it → real model |
| 13-14 | F12 Outage behaviour | Runs | The provider fails: the run ends `failed`, `model_unavailable`, no answer. Drop the live stream: the run still completes; reconnecting brings only the later events. | `test_18_f12_2`, `f12_3` passed; service stops → compose-level runner |
| 14-15 | F13 Document freshness | Knowledge → `surumler`, Agents → `surum-asistani` | Two versions of a contract; the newer one carries its source date (01.09.2025) and is listed first in SOURCES. | `test_18_f13_3` passed (FOLLOWUP-101 closed); the answer → real model |

After the PoC the same page gains F5 (quality monitoring, 09), F6 (long-document summary and
comparison, 04b), F7 (personal memory, 14) and F8 (channel assistant, 15/17).

## Real-model results (filled by the user's runs)

PoC acceptance uses the `cpu` column only (PayCore server, `airgap`, Qwen 3.5 35B on Ollama CPU);
`llmaas` and `gpu` are NOT_RUN until a provider or hardware is there (brief 13).

```bash
# on the PayCore server, by the user (the S1 set stays there; never copied into this repo)
make eval MODEL="qwen3.5:35b cpu" DATASET=<path to S1 questions> PROJECT=<project> APPROVE_SQL=1
make eval MODEL="qwen3.5:35b cpu" APPROVE_SQL=1     # sozlesme-33
```

| Measure (brief 13) | `llmaas` | `gpu` | `cpu` |
|---|---|---|---|
| `make seed && make e2e` total | NOT_RUN | NOT_RUN | to be measured |
| One RAG answer (≤ 4 min on cpu) | NOT_RUN | NOT_RUN | to be measured |
| Source accuracy (expected document cited) (≥ 16/20 on cpu) | NOT_RUN | NOT_RUN | to be measured |
| Unanswerable questions held (≥ 7/8 on cpu) | NOT_RUN | NOT_RUN | to be measured |
| SQL questions (≥ 4/5) | NOT_RUN | NOT_RUN | to be measured |

S1 comparison (brief 13): the baseline is `docs/paycore/s1-taban.md`. Run 1 (`rewrite=false`,
the PoC default) decides acceptance (S1 ≥ 80 %). Run 2 (`rewrite=true`) is **NOT_RUN in the PoC**:
query rewriting is package 04b (K-13b-0006 S3); the column stays empty with that reason.

| | Baseline (PayCore) | Run 1, `rewrite=false` | Run 2, `rewrite=true` |
|---|---|---|---|
| Source accuracy (expected document cited) | `docs/paycore/s1-taban.md` | to be measured | NOT_RUN (04b) |
| Median / P95 answer time | idem | to be measured | NOT_RUN (04b) |
| Extra LLM calls per question | idem | to be measured | NOT_RUN (04b) |

## What the stack cannot show

- DOCX contracts go in as text: the test stack has no Docling weights, so `seed` uploads DOCX as
  `<stem>.txt` (PDFs index as they are). The Docling path is 04a's own `models` test.
- Approval time-outs: the sweep runs every 60 minutes on the stack; the test hook
  (`FFCORE_TEST_HOOKS=1` in `e2e.env`, FOLLOWUP-111) is on, its negative test is the test worker's.
