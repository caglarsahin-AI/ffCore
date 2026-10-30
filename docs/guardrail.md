# Guardrails and PII (FFCore Guard, package 08-lite)

FFCore Guard scans every text that goes to the model or comes back from it, and every tool call,
against a project's policy. It can block, rewrite (redact, mask, tokenize), warn or only log.
There is no guardrail hook inside LiteLLM: the backend is the single control point (06a runtime,
06b facade).

08-lite delivers the engine, regex PII recognizers, secrets and tool-argument rules, the policy
API, a test panel and an internal evaluation endpoint. Turkish NER (person, organization,
location), the prompt-injection classifier, the streaming buffer and egress calibration arrive
with the full package (08).

## Stages (CONTRACTS C4, frozen when 08 merges)

| Stage | When |
|---|---|
| `prompt.pre` | once per user turn |
| `input.pre` | before every model call |
| `output.pre` | before the answer reaches the caller |
| `output.stream.delta` | during streaming (needs the C17 buffer; refused in 08-lite) |
| `tool.pre` | tool name and arguments, before the call |
| `tool.post` | tool result, before it goes back to the model |
| `egress` | the final packet sent to the model provider (llmaas) |

`egress` runs only when `GUARDRAIL_EGRESS_ENABLED=true` (llmaas installations). With `false`
(airgap) an egress evaluation is an explicit error (`409 egress_stage_disabled`), never a silent
pass.

## Decision (CONTRACTS C4)

`evaluate(text, stage, policy, *, ctx) -> Decision(action, text_out, events, message,
reference_id)`

- `action`: `allow` or one of the `action_taken` values `block`, `redact`, `mask`, `tokenize`,
  `warn`, `log`. The strongest action of the chain wins
  (`block` > `redact`/`mask`/`tokenize` > `warn` > `log` > `allow`).
- `text_out`: the rewritten text; empty on `block`.
- `message`: on `block`, the policy's `block_message` in the caller's locale (`en`, `tr`), English
  when the locale has no text.
- `reference_id`: on `block`, the id shown to the user and stored with the events.
- `events`: one per evaluated rule (see "Events").

The internal endpoint returns the same shape (`DecisionOut` in `backend/openapi/08.yaml`).

## Policies

Two entities, both per project:

- **PII policy** (`pii_policies`): engine (`regex`; `ner` with 08 full), default action, languages,
  minimum confidence, context boost, categories (each with enabled, severity, action, language)
  and custom patterns.
- **Guardrail policy** (`guardrail_policies`): an ordered rule chain, mode, `short_circuit`,
  `on_error` and the block message.

### Rule types

| Type | Finds | Action |
|---|---|---|
| `pii` | categories enabled in the referenced PII policy (`pii_policy_key`) | the rule's action; without one, each category's action, else the PII policy's default action |
| `secrets` | vendor keys (`sk-`, AWS, GitHub, Slack), JSON web tokens, private key blocks, connection strings with a password, values after a password keyword, high-entropy tokens (≥ 24 characters, ≥ 3.5 bits per character; UUIDs excluded, and names made of plain words and numbers such as `SZL-2025-003_temizlik-hizmet`: every `-`/`_` segment is digits, a word (case-normalized: at least 30 % vowels, no run of 3 consonants), a short tag (`v2`, `q3`, `kdv`) or an upper-case code of 2-6 letters directly before a number (`PRSIM-1234`); one other segment, or more than 15 tag and code letters in three or more segments, keeps the value under the check), hex strings of 32+ characters with letters and digits | required |
| `tool_args` | regex `patterns` in the arguments of `tools` (`<tool_key>.<action>`, wildcards allowed); `args` limits the search to named arguments of a JSON object | `block`, `warn` or `log`; only at `tool.pre` |

`injection`, `topic`, `output_format` and `banned_words` are refused with
`422 rule_type_unsupported` until they are delivered. A category without a recognizer (for example
`PERSON`) can only be enabled together with a custom pattern; otherwise `422
category_unsupported`. Nothing that looks enabled is silently ignored.

### Chain, modes and errors

- Rules bound to the stage run in order; each rule's output is the next rule's input (a redacted
  value is not seen again).
- `block` ends the chain. With `short_circuit=false` the remaining rules still run so the record
  is complete; the decision stays `block`.
- `mode`: `off` evaluates nothing; `monitor` evaluates and records everything and applies nothing
  (measure on real traffic first); `enforce` applies. A new policy starts in `monitor`; switching
  to `enforce` is an audited update (before and after state). A rule may set its own `mode`
  (`monitor` or `enforce`); without one it follows the policy. Only enforce-mode rules change
  the text or block; a monitor-mode rule only records.
- `on_error`: a rule that fails (`block`, the default, is fail-closed) blocks the text; `allow`
  lets it through and records the failure.
- Text longer than 200,000 characters is refused (`422 text_too_long`), never cut.

### Built-in default policy

A project without a stored policy keyed `default` uses the built-in one (version 2, shown in the
API with `builtin: true`):

| Rule | Stages | Action | Mode |
|---|---|---|---|
| `secrets` | all text stages and `egress` | `block` | policy (`monitor`) |
| `pii` (built-in PII policy) | `prompt.pre`, `input.pre`, `output.pre`, `tool.pre`, `tool.post` | `redact` | policy (`monitor`) |
| `pii` (built-in PII policy) | `egress` | `tokenize` | `enforce` |

The policy is `monitor`: it blocks and redacts nothing until an administrator stores an
enforce policy. The egress rule is enforced regardless: with `GUARDRAIL_EGRESS_ENABLED=true`
(llmaas) identifiers leave for an external provider only as placeholders, also in a project
that set no policy. Version 1 kept the egress rule in monitor, so the provider received raw
identifiers (plan/18 F4). The built-in PII policy enables the
five regex categories that are on by default in the brief: `TR_NATIONAL_ID`, `TR_PHONE`,
`TR_IBAN`, `EMAIL_ADDRESS`, `CREDIT_CARD`. `CVV` and `PIN` are on by default in the brief but
need context-aware recognition; they arrive with 08 full. Storing a policy with key `default`
replaces the built-in one.

## Masking

| Action | Result |
|---|---|
| `redact` | `[TR_NATIONAL_ID]` (the category code) |
| `mask` | at most the last four characters and never more than half stay visible: `*******0146`, CVV `**8`, a one-digit value `*`; e-mail keeps the first letter (none if the local part has one letter) and the domain: `a***@ornek.com`, `*@example.org`. A masked value never equals the raw one |
| `tokenize` | `<<PII_1>>`; exactly the same value gets the same placeholder within a run (no normalisation: `a.b@x` and `ab@x` are different; the same number written differently gets a separate placeholder, never a wrong one). The mapping lives in Redis for the run (`PII_TOKEN_TTL_S`, renewed on use) and is created in one atomic Redis script, so no caller sees a placeholder whose reverse entry is missing. It is reversed on output; a placeholder the run never issued is reported, not guessed |

Tokenize needs a run id (`run_id` in the internal request); without one the rule fails and
follows `on_error`.

## PII categories (canonical list)

English, Presidio-compatible codes; the 13a set uses the same list (a test keeps them equal).

| Code | Meaning | Recognizer in 08-lite | On in the built-in default |
|---|---|---|---|
| `TR_NATIONAL_ID` | Turkish national ID (TC, checksum) | regex | yes |
| `TR_PHONE` | Turkish phone number | regex | yes |
| `TR_IBAN` | Turkish IBAN (mod-97) | regex | yes |
| `TR_TAX_ID` | Turkish tax number (VKN) | custom pattern | no |
| `TR_PLATE` | licence plate | custom pattern | no |
| `TR_PASSPORT` | passport number | custom pattern | no |
| `TR_ADDRESS` | address | custom pattern | no |
| `PERSON` | person name | NER (08 full) | no |
| `ORGANIZATION` | organization name | NER (08 full) | no |
| `LOCATION` | location | NER (08 full) | no |
| `EMAIL_ADDRESS` | e-mail address | regex | yes |
| `CREDIT_CARD` | card number (Luhn) | regex | yes |
| `CVV` | card security code | 08 full | no |
| `PIN` | PIN | 08 full | no |
| `GPS` | coordinates | custom pattern | no |
| `MAC_ADDRESS` | MAC address | custom pattern | no |
| `API_TOKEN` | API token | `secrets` rule | no |
| `PASSWORD` | password | `secrets` rule | no |
| `DATE_OF_BIRTH` | date of birth | custom pattern | no |

Every finding carries evidence, for example `checksum valid · context word 'kimlik'`. A context
word in the 30 characters before a hit raises its score by 0.1 (`context_boost`).

## Events

`guardrail_events` gets one row per evaluated rule from the internal endpoint: policy, stage,
rule (`<type>#<index>`), `action_taken`, `status` (`passed`, `redacted`, `failed`), mode,
source, run, reference id, latency, severity, error type, findings (category, score, severity,
evidence, action) and matches (offsets and `masked_value`). `input_preview` is the first 60
characters with every regex PII value, every secret and every value found by any rule of the
chain redacted, whatever the mode and the rule order. Raw values are never stored. The test panel stores
nothing.

## API

The contract is `backend/openapi/08.yaml`
(`python -m ffcore.api.openapi_export 08 > openapi/08.yaml`).

| Endpoint | Who |
|---|---|
| `GET/POST /api/v1/projects/{project_id}/pii-policies`, `GET/PATCH/DELETE .../{policy_id}` | read: analyst; write: admin with edit access |
| `GET/POST /api/v1/projects/{project_id}/guardrail-policies`, `GET/PATCH/DELETE .../{policy_id}` | same |
| `POST /api/v1/projects/{project_id}/guardrails/test` | analyst, also with read access (dry run) |
| `POST /api/v1/internal/guardrails/evaluate` | the internal service account (`SERVICE_TOKEN`) only |

The test panel runs a PII policy with an action (`detect`, `redact`, `mask`, `tokenize`) or a
guardrail policy as if it were enforced, and returns the output text and the findings with
evidence, offsets and masked values. A PII policy still referenced by a guardrail policy cannot be
deleted (`409 pii_policy_in_use`).

## Configuration

| Variable | Meaning |
|---|---|
| `GUARDRAIL_EGRESS_ENABLED` | mandatory; `true` for llmaas, `false` for airgap |
| `PII_TOKEN_TTL_S` | tokenize mapping lifetime in seconds (default 1800) |
| `REDIS_URL` | the compose Redis (already set) |

## Latency

Regex path (all five recognizers), 1,000 characters, 200 runs in the tools container:
**P95 0.61 ms** (`python -m ffcore.guardrails.quality`). The brief budget of P95 < 300 ms covers
local rules, NER and the injection model together; NER and injection are measured with 08 full.

Whole evaluation on the real path (built-in policy, `input.pre`: `secrets` + `pii` rules, event
previews included), one CPU and 512 MB (`docker run --cpus=1 --memory=512m`), single runs:

| Input | Characters | Time |
|---|---|---|
| the same e-mail repeated 640 times | 10,240 | 0.036 s |
| the same e-mail repeated 10,000 times | 160,000 | 0.418 s |
| mixed text with all five regex categories (the 200,000 limit) | 200,000 | 0.198 s |

`test_08_cost.py` keeps upper bounds on these (0.5 s, 1 s, 1 s); a run over the bound fails.
Rule scanning and previews run in a worker thread (`asyncio.to_thread`), so they do not hold the
event loop, and each event's `latency_ms` includes its preview. Previews read only the first
4,096 characters (and show at most the first 3,840), search each distinct value once and merge
overlaps in one sorted pass; the findings themselves always cover the whole text.

## PII quality report (regex recognizers)

Measured on the synthetic 13a set `data/samples/pii/pii-100.jsonl` (100 sentences, 10 negatives).
A prediction counts when it overlaps a gold span of the same category. Regenerate with
`docker compose run --rm tools sh -c "cd backend && python -m ffcore.guardrails.quality ../data/samples/pii/pii-100.jsonl"`;
a test keeps this table equal to the measurement.

| Category | Support | Predicted | Recall | Precision |
|---|---|---|---|---|
| `TR_NATIONAL_ID` | 9 | 9 | 1.00 | 1.00 |
| `TR_PHONE` | 9 | 9 | 1.00 | 1.00 |
| `TR_IBAN` | 6 | 6 | 1.00 | 1.00 |
| `EMAIL_ADDRESS` | 8 | 8 | 1.00 | 1.00 |
| `CREDIT_CARD` | 5 | 5 | 1.00 | 1.00 |

Limits of this measurement:

- Support is small (9 national IDs, 9 phones): one miss drops recall to 0.89. The acceptance
  threshold (national ID and phone recall ≥ 0.98, brief 08) is met only with 9 of 9; the llmaas
  threshold (0.99) the same way.
- The set and the recognizers were written by the same team; the formats in the set are known.
  Treat 1.00 as "no regression on the known formats", not as a field recall.
- `PERSON`, `ORGANIZATION` and `LOCATION` need the Turkish NER model (08 full); they are not
  measured here.
