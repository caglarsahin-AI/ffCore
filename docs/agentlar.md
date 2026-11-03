# Agents (FFCore Agents, package 06a)

An agent is data: a JSON definition filled in a form, turned into a LangGraph graph at run time.
Agents are versioned and published; runs are queued, streamed as server-sent events, paused for
approvals or questions, and resumed from a Postgres checkpoint.

API contract: `backend/openapi/06a.yaml` (paths under `/api/v1/projects/{project_id}`).

## Definition (contract C8, `schema_version` 1)

| Field | Meaning |
|---|---|
| `model` | Project model key (e.g. `chat-default`); resolved to `<project>.<model>` in LiteLLM (C1). |
| `system_prompt` / `langfuse_prompt` | Exactly one: inline instructions or a managed Langfuse prompt `{name, label}`. `{{variable}}` placeholders (the Langfuse prompt syntax) are filled from `variables`; a placeholder without a variable is refused at save (`variable_undefined`) and at run start (`variable_unresolved`). |
| `variables` | `[{key, label, default}]`; a run may override them; an unknown key is refused. |
| `knowledge` | `[{kb_key, mode: always\|tool, top_k, min_score}]`. `always`: searched before the model call. `tool`: offered as the tool `search_documents(query, kb_key, top_k)` (C7/C11). |
| `tools` | `[{tool_key, actions}]` MCP actions registered and discovered in the project (package 05a). The model sees each as `<tool_key>__<action>`; the action's `enabled`, `needs_approval`, `max_calls_per_run` and `timeout_s` apply. |
| `approval` | `{actions: ["<tool>.<action>"], assign_to: analyst\|developer\|admin}` (default `analyst`); an action needs approval when it is listed here or its own `needs_approval` is on. The `user` role never approves. |
| `ask_user` | Adds `ask_user_question`; the run waits for the user's answer. Not counted in `max_tool_calls`, counted in `max_turns`. |
| `guardrail_policy_key` | Guardrail policy (package 08), default `default`. |
| `structured_output` | A JSON schema the final answer must match (checked at save and at the end of the run). |
| `limits` | `max_tool_calls`, `max_turns`, `run_timeout_s` (≤ `RUN_TIMEOUT_S`; time spent waiting for an approval or an answer does not count), `context_tokens`, `output_tokens`. |
| `context_policy` | Shares of the context budget for history, RAG and memory, and the trim order. |
| `answer_rules` | `cite_sources`, `unknown_reply`, `confidence_formula` (`cited` or `max`), `confidence_threshold`, `show_confidence`, `max_answer_tokens`. |
| `reasoning` | `none` (default) or `model_default`. |
| `runtime_profile` | Reserved; the first version has one value, `default`. Any other value is refused (422). |

Unknown fields are refused (422). Options the runtime does not run yet are refused at save with a
code, never ignored: `answer_rules.verify` (`verify_not_supported`), `confidence_formula:
sentence_max` (`confidence_formula_not_supported`), `knowledge[].filter.scope`
(`knowledge_filter_not_supported`, FOLLOWUP-89). A definition without `schema_version` is version 1.
Every definition check answers 422 `invalid_request_error` with its own code in `error.code`
(`prompt_source`, `variable_duplicate`, `variable_undefined`, `knowledge_duplicate`,
`knowledge_filter_not_supported`, `tool_duplicate`, `approval_action_unknown`,
`verify_not_supported`, `confidence_formula_not_supported`, `output_reserve_too_small`,
`structured_output_invalid`) and the field path in the message; a wrong type or an unknown field
is `validation_error` (FOLLOWUP-105).

Saving or publishing checks the budget against the model (C13): `context_tokens` above the model's
`context_window`, or above `OLLAMA_CONTEXT_LENGTH` on an Ollama model, is 400
`context_configuration_invalid`. `/readyz` repeats the Ollama check for every published agent.

## Lifecycle

1. `POST /agents` with `key`, `name`, `description`, `model`: the agent and draft version 1.
2. `PUT /agents/{id}/versions/{v}` fills the definition of a draft. A published version is never
   edited (409 `version_published`); `POST /agents/{id}/versions` opens a new draft from one.
3. `POST /agents/{id}/publish {version}`; `POST /agents/{id}/rollback {version}` (only to a version
   that was published before). Runs without an explicit version use the published one.

Analysts with edit access build and publish agents; read-only access gets 403 on every mutation.
Every mutation is audited.

### Manifest (06b)

- `GET /agents/{id}/manifest?version=&format=json|yaml`: the agent (`key`, `name`, `description`,
  `kind`) and one version's definition (default: the published one, else the latest), with
  `manifest_version: 1`. No secrets are in it.
- `POST /agents/import?dry_run=true|false` (body `application/json` or `application/yaml`): a new
  agent with draft version 1, or the next draft version of the agent with the same key. Nothing is
  published. The definition is validated as on save (C8; a definition without `schema_version` is
  version 1) and so is the model and context budget (C13). `dry_run=true` answers what would
  happen and writes nothing. An external agent is neither exported nor imported (422
  `external_agent_not_available`): its endpoint and key stay in the installation.
  Edit access, audited (`import_agent`).

### External agents (06b-2)

An external agent (`kind: external`) is an OpenAI-compatible agent running elsewhere, put behind
FFCore's single entry: a project administrator registers its base URL, remote model and API key
(`POST .../agents/external`), then publishes it (`.../external/publish`). It has no definition and
no versions; FFCore does not run it, it forwards the conversation and checks both directions with
the project's `default` guardrail policy. Its answer is text only: tool calls it returns are never
executed. Calls are not runs (they are in the audit log, not on the Runs screen) and are outside
token and USD quotas. Details: docs/api.md, "External agent path".

### Through the OpenAI-compatible facade (06b)

`agent:<project_key>/<agent_key>` on `/v1/chat/completions` runs the published version as the API
key, or as the user the key acts for (docs/api.md, facade). A run started by the key itself has no
user: its searches use the key's `acl_role` (the backend reads it from the key row), tools that
forward the user's identity cannot run (`tool_needs_run_user`), approvals are decided in the
console only.

Personal data tokenized at `egress` (llmaas) leaves for the provider as placeholders (`<<PII_n>>`).
Placeholders go back to their values at the exit only (C17, 08-tam-1a): the run's own user on
the console (live stream and replay) and the caller of a facade request see the values; any
other reader (another analyst, an admin, an approver) sees the placeholders, as stored. The
stored answer, `messages`, `run_events` and the history sent to the model keep placeholders,
never values: an earlier run's placeholder in the conversation becomes this run's placeholder for
the same value (read in the earlier run's scope, without renewing it there), and a facade agent
client's earlier turns are stored as `egress` left them, in the run's scope. Before its first
value a run's counter passes every placeholder number (up to 8 digits) in its question and
history, so a carried placeholder never reads as one of this run's values (numbers stay at 8
digits; past it the run fails with `placeholder_out_of_range`). A placeholder on a URL line
stays for every reader: a line with an HTML tag, a URL scheme such as `http:`, or a markdown,
CSS or attribute marker (`](`, `]:`, `//`, `url(`, `src=`, `href=`, `style=`, `data=`; the full
rule and its carry-over in docs/guardrail.md), logged as `detokenize_skipped_url` with a count;
an upstream could otherwise make a client that loads images send the value to its host. A
reader that reconnects (`Last-Event-ID`, the console after an approval) rebuilds this line state
from the live token entries; when it cannot, its first line keeps the placeholders. When the run's guardrail policy enforces a `pii` rule on the output, the
placeholders stay for everyone (the output was checked with them in it; logged as
`detokenize_skipped_policy` with a count). A placeholder whose
mapping is gone (`PII_TOKEN_TTL_S`, default 1800 s after its last use; the run's own reads and
the exit renew it, a later run reading the history does not) or that the run never issued stays as it is and is logged with its count
(`detokenize_unresolved`, no value). Stored views (`GET /runs/{id}`, `GET /runs/{id}/events`,
approvals) are not reversed.

## Runs

`POST /agents/{agent_key}/runs {input, variables, conversation_id?, channel: chat|test, version?}`
answers with an event stream (`text/event-stream`). The first event is `progress` with `run_id`.
Event names (C9): `token, tool_call, tool_result, approval_required, question, sources, progress,
fallback, done, error`; a client ignores names it does not know. Each event has an `id`; the
stream ends after `done`, `error`, `approval_required` or `question`.
A `sources` event names each source (document id and name, page, breadcrumb, source date),
never its text. Each source passes `egress` on its own (llmaas): a source the guardrail blocks
(an encoded blob under the `secrets` rule, say) is left out of the model's input and listed
under `blocked` with `reason: guardrail_block` and the guardrail `reference_id`; the answer goes
on with the other sources, and the run fails `guardrail_block` only when none is left
(FOLLOWUP-107). The same holds for `search_documents` results. When a document is deleted later, the stored event and the live stream keep the
reference, and every read shows its breadcrumb as `[deleted]`: `GET /runs/{id}/events`, a
reconnect to the live stream (Redis, within `RUN_EVENT_STREAM_TTL_S`) and a replay from
`run_events` (FOLLOWUP-108).

- **Reconnect:** `GET /runs/{id}/stream` with `Last-Event-ID` continues after that event. Closing a
  stream never cancels a run. When the live stream has expired (`RUN_EVENT_STREAM_TTL_S`) the run
  is replayed from `run_events`, announced by `progress {"replay": "run_events"}`.
- **Approval:** a run waiting for an approval is `waiting_approval`. `POST /runs/{id}/resume
  {decision: approved|rejected, comment?}` needs the definition's `approval.assign_to` role with
  edit access, from a signed-in user: a service account acting on someone's behalf (or an API
  key) gets 403 `approval_requires_user_session`. The stream continues from the approval. A
  second resume is 409 `run_not_waiting`.
- **Question:** `waiting_user`; the run's user answers with `POST /runs/{id}/resume {answer}`.
- **Cancel:** `POST /runs/{id}/cancel` (the run's user or a project admin). A queued or waiting run
  ends at once; a running one at its next step.
- **Abandoned:** a running run nobody listens to for `RUN_ABANDON_GRACE_S` stops at its next step
  with status `abandoned` and frees its model slot.
- **Read:** `GET /runs` (filters `agent_id`, `channel`, `status`, `feedback=pending|given`),
  `GET /runs/{id}`, `GET /runs/{id}/events`, `GET /runs/{id}/stream`. Analysts and above read
  every run of the project; a `user` member reads the runs that ran for them (`user_id`) and
  lists only those; another user's run is 404.
- **Feedback (F9):** `POST /runs/{id}/feedback {vote: correct|partial|wrong, note?}` on a completed
  run, with edit access: stored on the answer and sent to Langfuse as the score `expert_feedback`.

Superadmins run agents only in projects where they are members: the run searches and calls tools
on behalf of its user, where only membership counts (403 `run_needs_membership`).

### Resuming a run from another package (07 approvals)

`POST /runs/{id}/resume` and 07's approval endpoints share one function:

```python
from ffcore.runtime.resume import resume_run

after = await resume_run(
    session,            # AsyncSession; committed inside
    queue,              # RunQueue (ffcore.runtime.queue.get_run_queue(settings))
    settings,           # Settings
    project_id=...,     # UUID; the run must belong to this project (else 404 run_not_found)
    run_id=...,         # UUID
    actor=...,          # ffcore.core.auth.Actor of the caller
    decision="approved",  # or "rejected"; for a run in waiting_approval
    answer=None,        # the user's answer; for a run in waiting_user
    comment=None,       # shown to the model with a rejection
    request_id=None,    # audit; a new id when omitted
    ip=None,            # audit
)
```

It returns the id of the last live event (`<seq>-<n>`, or `None` before any), so the caller can
follow the stream from there (`GET /runs/{id}/stream` with `Last-Event-ID`).

What the function checks (the same for every caller):

| Rule | Error |
|---|---|
| The run is `waiting_approval` or `waiting_user` | 409 `run_not_waiting` |
| `waiting_approval` takes a decision and no answer; `waiting_user` an answer and no decision | 422 `decision_required` / `answer_required` |
| A decision comes from a signed-in user: `actor_type == "user"` and not `via_service` | 403 `approval_requires_user_session` |
| An answer comes from the run's own user | 403 `not_run_user` |
| One resume per wait: the status change to `queued` is the lock | 409 `run_not_waiting` |

What the caller checks: the role. `/resume` requires the definition's `approval.assign_to` (default
`analyst`) with `edit` access; 07 applies the approval's assigned role. The function writes the
audit event (`resolve_approval` or `answer_run_question`) in the same transaction, marks the run
as listened and queues the next attempt; the worker continues from the checkpoint.

### What happens in a run

`prepare` (budget) → `retrieve` (`always` knowledge bases, newest sources first) → `guard_in`
(`input.pre`, and `egress` where `GUARDRAIL_EGRESS_ENABLED=true`) → `model` → tool calls through
`tool_guard` (`tool.pre`, counters, approval request) → `approval` / `ask_user` (wait) → `tools`
(`tool.post`) → back to `model` → `guard_out` (`output.pre`) → `finalize` (structured output,
outcome label, confidence).

- A documents-only agent whose search found nothing answers its `unknown_reply` without a model
  call (`progress {"skipped_model": "no_sources"}`, outcome `declined`).
- When a rule that checks output is in enforce mode (its own mode, or the policy's when it has
  none), the stream starts with `progress {"stage":
  "output_buffered", "reason": "guardrail_enforce"}` and the answer arrives in one piece after
  `output.pre`; otherwise tokens stream as they are written.
- A model fallback happens only with an active `chat-fallback` model; it is a `fallback` event.

### Workers, queues and the model slot (C10)

Runs are arq jobs: `agent-worker` serves `llm-interactive` (chat, test panel), `agent-worker-bg`
serves `llm-background`. Every model call holds a slot of the Redis pool `LLM_SLOTS`; a free slot
goes to interactive work first, then interactive-low, then background. Background work takes the
slot only inside `BACKGROUND_WINDOW`. `/readyz` reports the pool (`llm_slots`).

A worker that stops (deploy, restart) does not lose a run: arq runs the job again and the run
continues from its last checkpoint, announced by `progress {"attempt":
"resumed_after_worker_stop", "step": ...}` (the interrupted step's tokens come again). After three
aborted attempts the run fails with `worker_retries_exhausted`.

| Setting | llmaas | airgap CPU | airgap GPU |
|---|---|---|---|
| `LLM_SLOTS` | provider concurrency (default 4) | 1 | vLLM parallelism |
| `BACKGROUND_WINDOW` | empty | `19:00-07:00` (+ `BACKGROUND_WINDOW_WEEKENDS=true`) | empty |
| `RUN_TIMEOUT_S` | 120 | 900 | 300 |
| `RUN_ABANDON_GRACE_S` | 120 | 120 | 120 |

`LANGSMITH_TRACING` or `LANGCHAIN_TRACING_V2` set to true stops every process at start: it would
send prompts to LangSmith. Traces go to Langfuse only.

### Tools

An agent's MCP actions come from the project's tool registry (05a) when the run starts. A tool
that is not registered, not discovered, or an action that is missing or disabled ends the run at
start with a code (below); the model never sees a partial tool list. Calls go through 05a's MCP
client with the run's user as caller (`forward_user` tools get a token for that user, audience
the tool and the backend) and `X-Run-Id`. Each call is a `tool_call` and a `tool_result` event (arguments as the guardrail's
`tool.pre` output: masked, or `{"redacted": true, "reason": "guardrail_block"}` when blocked; the
raw arguments reach no event, approval record or later model request);
a result longer than `TOOL_RESULT_MAX_CHARS` is cut with `[truncated: N/M chars]` and
`truncated: true`. A call that fails is given to the model as an error and recorded with its
code (`tool_result.error_code`, e.g. `tool_unreachable`, `tool_timeout`). An action's
`max_calls_per_run` stops the run with `limit_reached` (`limit: max_calls_per_run`).

### Checkpoints and deleted documents

The checkpoint holds the run's model conversation, so also the text of the passages the model
read; it lives only as long as the run can go on. The sources the run state keeps carry no text
(document, page, breadcrumb, scores). When a run ends, its LangGraph thread is deleted
(`runs.checkpoint_deleted_at`); a per-minute sweep on `agent-worker-bg` deletes the threads of
runs that ended elsewhere (cancel, approval expiry) or whose deletion failed, and logs
`checkpoint_purge_overdue` for a run still not cleaned after 24 hours. Deleting a document (or
its knowledge base) marks the running and waiting runs that listed it as a source
(`runs.source_deleted_at`): a running run stops at its next step, a resume stops before the graph
runs, and the sweep closes waiting runs (a question has no time limit); each ends `failed` with
`source_deleted` and its thread is deleted. Until then a waiting run's checkpoint still holds the
deleted passages, for at most one sweep interval (60 s; the sweep runs every minute and has no
setting). A run the sweep cannot close (for example Redis unreachable) is logged as
`source_deleted_close_failed`, stays waiting and is tried again on the next sweep; the others in
the same sweep are not held up. In the run's events the source keeps its document
name and the breadcrumb reads `[deleted]`. Text the run wrote into its own events (`llm_call`
request messages, the answer) follows the content retention class (03c).

## Tracing

Each run is one Langfuse trace (`runs.langfuse_trace_id`): a span `agent-run`, one span per graph
step, and LiteLLM's generation under the `agent.model` span. `run_events` holds the same steps in
order; `llm_call` events carry `litellm_call_id`. Platform rules come from the Langfuse prompt
`platform_rules` (seeded by `make seed-prompts` from `backend/prompts/platform_rules.md`).

## Error codes

Every stop is a coded `error` event and the run's `error_code`; nothing ends silently.

| Code | When |
|---|---|
| `limit_reached` | `max_turns`, `max_tool_calls` or the run timeout; partial output kept with `partial=true` |
| `guardrail_block` | a policy blocked input, output or egress; `reference_id` shown to the user |
| `guardrail_text_too_long` | a single message to the model is over the guardrail engine's text limit (200,000 characters); nothing is cut |
| `unsupported_message_content` | a message to the model has content that is not text (or tool call arguments that are not JSON); egress cannot check it, so the run stops |
| `model_unavailable` | the model (and its configured fallback) could not answer; no implicit fallback |
| `model_not_found` | the agent's model is not active in the project |
| `upstream_error`, `stream_incomplete`, `empty_completion` | the provider answered without a usable result |
| `prompt_unavailable` | Langfuse could not give `platform_rules` or the agent's managed prompt |
| `knowledge_base_not_found`, `search_http_<status>` or the search API's own code | the knowledge search failed |
| `tool_not_found`, `tool_not_discovered`, `tool_action_unavailable`, `tool_name_invalid`, `tool_needs_run_user` | an agent's MCP tool or action cannot be used (05a registry); the run ends at start |
| `structured_output_invalid` | the final answer does not match `structured_output` |
| `cancelled`, `abandoned` | explicit cancel; nobody listening past the grace time |
| `worker_retries_exhausted` | the worker was stopped three times during the run |
| `source_deleted` | a document the run showed as a source was deleted while the run was still going or waiting; the run does not continue with its text |
| `quota_exceeded` | a blocking quota of the project, the run's API key or its user has no room for the model call (03c; `limit` names the window, `detail` the quota); the console run fails, the facade (06b) answers 429 |
| `pricing_missing` | a USD budget applies but the model has no price, so the call could not be counted (03c, FOLLOWUP-69) |
| `quota_unavailable` | the quota counters (Redis) could not be read or written; the call is not made unlimited |
| `run_error` | anything else; the worker log has the exception |

API errors at start: `agent_not_published` (404), `run_needs_membership` (403), `variable_unknown`
(422), `external_agent_not_runnable` (422: an external agent is called through the facade, never
run), `run_not_waiting` (409), `run_not_completed` (409, feedback). Langfuse delivery problems are
logged as `trace_delivery_failed` and never fail a run or a request.
