# PoC demo (draft)

> Package 18 keeps this page in step with the scenario evidence; package 13b owns it from `make
> e2e` on and adds the commands, screenshots and real-model results. Every step uses synthetic
> data from `data/samples/`; nothing here connects to a real ticket, mail or chat system.

Each step shows one PoC use case from `plan/18-kullanim-senaryolari.md` and names the test that
proves it. Results are from the scenario stack (`tests/e2e/scenarios/README.md`): the test stack
with `fake-llm` and the `e2e.env` overlay, seeded by `seed.py`. Last full run: 32 passed, 2 failed,
24 not run (main 6deb0c1 + feat/18-f2-stage3, 30 October 2026).

`fake-llm` answers "hello" and, in its `tool-*` mode, calls the first offered tool once. So the
platform's own behaviour is proven here; what depends on a real model's answer (exam scores,
declining, resisting an instruction) is **NOT_RUN** until a run on a real model (PayCore S1 or an
llmaas model), never shown as passed.

| Step | Use case | What the audience sees | Evidence (test → result) | Data |
|---|---|---|---|---|
| 1 | F1 Document assistant with sources | Ask the contract assistant about a notice period; the answer comes with the contract it used, and the model receives the passages as a SOURCES block behind the platform rules. | `test_18_f1_1`, `f1_1b` → passed. Exam ≥ 80 % (`make eval` on `sozlesme-33`) and declining an unanswerable question → NOT_RUN (real model) | `data/samples/contracts/`, `eval/sozlesme-33.json` |
| 2 | F2 Ticket reply with approval | The ticket assistant drafts a reply to `tkt-001`; the reply waits in the approval queue (Approvals screen, `can_decide` per user). A read-only admin cannot decide. Approve: the fake ticket desk records exactly one reply. Reject: nothing is sent and the model is told. | `test_18_f2_7` (06a resume), `f2_8`, `f2_9`, `f2_10` (07 queue, feat/18-f2-stage3) → passed. Triage accuracy ≥ 80 %, masked PII tickets, "declined" after a rejection → NOT_RUN (real model + triage agent) | `data/samples/tickets/`, `services/ticket-desk/` |
| 3 | F3 Read-only data questions | The data assistant calls `run_sql` once; the call waits for an analyst's approval, then runs over the real tool chain on the read-only demo DB. Fifteen disguised writes (CTE, UNION, comment, second statement, `SELECT INTO`, functions) are refused with their codes and the row counts stay the same. | `test_18_f3_8` → passed (one approved `mcp-sql__run_sql`); `f3_9` → 15/15 refused, 6 tables unchanged. `sql-20` ≥ 80 % → NOT_RUN (real model) | `data/samples/schema/`, `eval/sql-20.json`, `eval/sql-write-attempts.json` |
| 4 | F4 Managed LLM gateway | Send a message with a synthetic national ID: the provider only ever sees a placeholder, in a project with its own policy and, since the 08 fix, with the built-in default too. Follow the run to its LiteLLM call id and its Langfuse trace. | `test_18_f4_1` → passed (5 samples, no raw value); `f4_1c` → passed after 6deb0c1 (was the FOLLOWUP-102 finding); `f4_2`, `f4_2b` → passed. Masked tool arguments → NOT_RUN (real model); quotas → NOT_RUN (03c) | `data/samples/pii/` |
| 5 | F9 Expert review queue (PoC-lite) | On a finished run, an expert votes correct / partly / wrong with a note; the "pending" view drops the run. A read-only user gets 403. | `test_18_f9_1`, `f9_2` → passed. Dataset automation → NOT_RUN (09) | runs of `sozlesme-33` |
| 6 | F10 Project isolation and audit trail | A `klinik-b` admin cannot see `hastane-a`'s knowledge bases, documents, tools, agents or runs, in lists or by direct id. One `hastane-a` run is followed from its source documents to the LiteLLM call id and the Langfuse trace. | `test_18_f10_5`, `f10_6` → passed. **Open:** `f10_4` → direct ids answer 403 `insufficient_role` on 12 endpoints instead of 404 (FOLLOWUP-103); `f10_7` → a deleted document's heading text stays in the run's source breadcrumb (FOLLOWUP-108) | `data/samples/projects/` |
| 7 | F11 Poisoned documents and tickets (PoC-lite) | Five procedures each hide one instruction ("ignore your rules", "call run_sql", "write this code word", base64). The poisoned text reaches the model only inside SOURCES, framed as data by the platform rules, and no tool is called. | `test_18_f11_5[P1-P5]` → passed. The model not following the instruction, ticket injection, the 08 full recognizer → NOT_RUN. Note: with the secrets rule enforced, P5's base64 blob blocks every answer that retrieves it (FOLLOWUP-107); the demo project logs secrets | `data/samples/poison/`, `agents/zehirli-belge-asistani.json` |
| 8 | F12 Outage behaviour | The model provider fails: the run ends `failed` with `model_unavailable` and no answer. The client drops the live stream: the run still completes, and reconnecting with `Last-Event-ID` brings only the later events. | `test_18_f12_2`, `f12_3` → passed. Langfuse / Qdrant stopped, full `LLM_SLOTS`, airgap provider down → NOT_RUN (compose-level runner, 13b) | none |
| 9 | F13 Document freshness | Ask the version assistant about a clause that changed in version 2: the answer uses version 2 and names its date (01.09.2025). | Ordering v2 before v1 → NOT_RUN (FOLLOWUP-101: uploads get no source date); the answer → NOT_RUN (real model); the two-version diff → 04b | `data/samples/versions/`, `agents/surum-asistani.json` |

Conversion of DOCX contracts with Docling needs model weights the test stack does not have; the
seed uploads DOCX as text (PDFs index as they are). The Docling path is 04a's own `models` test.

After the PoC the same page gains F5 (quality monitoring, 09), F6 (long-document summary and
comparison, 04b), F7 (team and personal memory, 14) and F8 (channel assistant, 15/17); their
evidence lives in those packages' acceptance tests.
