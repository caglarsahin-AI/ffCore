# PoC demo (draft)

> Draft from package 18-hazirlik (plan/18 stage 1). Package 13b owns this page and fills in the
> commands, screenshots and measured results once the PoC packages are merged. Every step uses
> synthetic data from `data/samples/`; nothing here connects to a real ticket, mail or chat system.

Each step shows one PoC use case from `plan/18-kullanim-senaryolari.md` and names the evidence
that proves it. A step whose evidence has not run yet is shown as `NOT_RUN`, never as passed.

| Step | Use case | What the audience sees | Evidence | Data |
|---|---|---|---|---|
| 1 | F1 Document assistant with sources | Ask the contract assistant about a notice period; the answer cites the contract and page. Ask something the contracts do not cover; the assistant says so instead of guessing. | `make eval` on `sozlesme-33` (≥ 80 % source-correct), `outcome_label=declined` for the unanswerable question | `data/samples/contracts/`, `eval/sozlesme-33.json` |
| 2 | F2 Ticket triage with an approved draft reply | The triage agent reads a ticket from the fake ticket desk, picks a class and drafts a reply. The reply waits in the approval queue; only after approval does the fake desk record it. A ticket with personal data reaches the model masked. | 13b e2e: class accuracy ≥ 80 % on 20 tickets; no `send_reply` without approval (`/_sent` empty); no raw PII in the request the fake provider received | `data/samples/tickets/` |
| 3 | F3 Read-only data questions | Ask the data assistant how many devices are under maintenance; it runs one SQL query on the read-only presentation DB and answers. Try a disguised write (a `DELETE` inside a CTE); it is refused with a code and the row counts do not change. | `make eval` on `sql-20` (≥ 80 %), negative e2e with `sql-write-attempts.json` | `data/samples/schema/`, `eval/sql-20.json`, `eval/sql-write-attempts.json` |
| 4 | F4 Managed LLM gateway | Send a message with a synthetic national ID through the gateway; show that the provider only ever saw a placeholder, and follow the trace from the run to the LiteLLM call to Langfuse. Quotas: `NOT_RUN` until 03c. | 13b e2e on the fake provider's recorded requests (`fake-llm` `GET /_requests`) | `data/samples/pii/` |
| 5 | F9 Expert review queue (PoC-lite) | On a finished run, an expert marks the answer correct / partly / wrong with a note; the "pending" view lists only runs not yet reviewed. A read-only user cannot review (403). | 13b e2e after 06a and 10b-poc-2 | runs of `sozlesme-33` |
