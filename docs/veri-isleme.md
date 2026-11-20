# Data processing record (llmaas)

A template the customer fills in for its legal and information security review before an
`llmaas` installation goes live. In `llmaas` the model runs at an external provider; everything
else (gateway, knowledge base, tools, agents, guardrails, traces, audit) runs inside the
customer's network. The sections marked **(fill in)** are the customer's; the rest describes
what FFCore does and points at how to check it.

An `airgap` installation (`OFFLINE=true`, local model) sends nothing out and does not need
this record.

## 1. Parties and contacts (fill in)

| Item | Value |
|---|---|
| Data controller (the customer) | |
| Responsible person (name, role, contact) | |
| Information security contact | |
| Model provider(s) and contract reference | |
| Provider's data processing agreement / zero data retention reference | |
| Processing region of the provider (as contracted) | |
| Date of this record, reviewed by | |

## 2. What leaves the network

Only model calls leave, only to the hosts in `EGRESS_ALLOWLIST`, and (with the egress profile)
only through the forward proxy (docs/kurulum.md, "Egress"). A model call carries:

| Data | When | Protection before it leaves |
|---|---|---|
| The user's question and the conversation history | every chat turn and agent run | `egress` guardrail stage (below) |
| Retrieved knowledge base passages | when an agent answers from a knowledge base | each passage goes through `egress` on its own; a blocked passage is left out |
| Tool results | when an agent used a tool | part of the message, through `egress` |
| The agent's instructions (system prompt) and tool definitions | every agent model call | through `egress` |
| Exam (evaluation) questions and, with an LLM judge, the judged answers | when an exam runs on an external model | through `egress` |

The `egress` stage is on in every `llmaas` installation (`GUARDRAIL_EGRESS_ENABLED=true`) and
its built-in PII rule is enforced even in a project that stores no policy: Turkish national ID
numbers, phone numbers, IBANs, e-mail addresses and card numbers leave only as placeholders and
are restored in the answer (docs/guardrail.md). Person names are masked too when
`GUARDRAIL_EGRESS_NER=true` (Turkish NER model, local). Secrets (keys, tokens) found at egress
are blocked by the `secrets` rule when the project's policy enforces it.

Channels and sources, when enabled, also connect out to their own hosts (for example Slack,
Microsoft Teams, Confluence); each host must be in `EGRESS_ALLOWLIST` and is listed in
section 5.

## 3. What does not leave

| Data | Where it stays |
|---|---|
| Uploaded documents (raw and converted files) | `knowledge_storage` volume |
| The search index (vectors, keyword index) | Postgres (pgvector) or the customer's Qdrant |
| Embeddings and reranking | computed locally (bge-m3, bge-reranker-v2-m3); no embedding provider |
| Traces (prompts, answers, timings, cost) | Langfuse, inside the network |
| Audit log, guardrail events, run history | Postgres |
| Users, roles, API keys (hashed), provider keys (encrypted) | Postgres |

Patient data and person-level institutional records are not loaded into FFCore at all; that
rule is the customer's to keep at the source (fill in how, section 6).

## 4. Retention

| Data | Retention | Set by |
|---|---|---|
| At the provider (fill in) | as contracted (zero data retention where available) | provider contract |
| Run history, guardrail events, audit log | retention settings per project; old audit partitions are removed only when `RETENTION_AUDIT_DROP_ENABLED=true` | console, `.env` |
| Traces in Langfuse (fill in) | | Langfuse project settings |
| Backups (fill in) | | operations |

## 5. Outbound hosts (fill in)

The firewall request for the network team is generated from the installation's settings:

```bash
python scripts/compose_preflight.py --env-file .env --egress-list
```

Paste the output here and keep it equal to `EGRESS_ALLOWLIST`.

## 6. Evidence of masking

Every egress evaluation is a row in `guardrail_events` (values masked, raw text never stored).
Count by day and outcome for the last 30 days (run as the database owner on the server):

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT date_trunc('day', ts) AS day, rule, action_taken, status, count(*)
FROM guardrail_events
WHERE stage = 'egress' AND ts > now() - interval '30 days'
GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4;
SQL
```

`status = redacted` rows are messages in which identifiers were replaced before they left;
`status = failed` rows were blocked and never sent. Attach the result to this record at each
review. The user and database are the container's own variables (`sh -c`), not the host
shell's; the SQL comes on standard input. Run on a test stack in package 12 (r2); a fresh stack
returns no rows.

## 7. Approval (fill in)

| Role | Name | Date | Decision |
|---|---|---|---|
| Legal | | | |
| Information security | | | |
| Data controller | | | |
