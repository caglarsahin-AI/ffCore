# Agents (FFCore Agents, package 06a)

An agent is data: a JSON definition filled in a form, turned into a LangGraph graph at run time.
Agents are versioned and published; runs are queued, streamed as server-sent events, paused for
approvals or questions, and resumed from a Postgres checkpoint.

API contract: `backend/openapi/06a.yaml` (paths under `/api/v1/projects/{project_id}`).

## Definition (contract C8, `schema_version` 1)

| Field | Meaning |
|---|---|
| `model` | Project model key (e.g. `chat-default`); resolved to `<project>.<model>` in LiteLLM (C1). |
| `system_prompt` / `langfuse_prompt` | Exactly one: inline instructions or a managed Langfuse prompt `{name, label}`. `${variable}` placeholders are filled from `variables`. |
| `variables` | `[{key, label, default}]`; a run may override them; an unknown key is refused. |
| `knowledge` | `[{kb_key, mode: always\|tool, top_k, min_score}]`. `always`: searched before the model call. `tool`: offered as the tool `search_documents(query, kb_key, top_k)` (C7/C11). |
| `tools` | `[{tool_key, actions}]` MCP actions (package 05a). |
| `approval` | `{actions: ["<tool>.<action>"], assign_to: analyst\|developer\|admin}`; joined with the action's `needs_approval`. The `user` role never approves. |
| `ask_user` | Adds `ask_user_question`; the run waits for the user's answer. Not counted in `max_tool_calls`, counted in `max_turns`. |
| `guardrail_policy_key` | Guardrail policy (package 08), default `default`. |
| `structured_output` | A JSON schema the final answer must match (checked at save and at the end of the run). |
| `limits` | `max_tool_calls`, `max_turns`, `run_timeout_s` (≤ `RUN_TIMEOUT_S`), `context_tokens`, `output_tokens`. |
| `context_policy` | Shares of the context budget for history, RAG and memory, and the trim order. |
| `answer_rules` | `cite_sources`, `unknown_reply`, `confidence_formula` (`cited` or `max`), `confidence_threshold`, `show_confidence`, `max_answer_tokens`. |
| `reasoning` | `none` (default) or `model_default`. |

Unknown fields are refused (422). Options the runtime does not run yet are refused at save with a
code, never ignored: `answer_rules.verify` (`verify_not_supported`), `confidence_formula:
sentence_max` (`confidence_formula_not_supported`), `knowledge[].filter.scope`
(`knowledge_filter_not_supported`, FOLLOWUP-89). A definition without `schema_version` is version 1.

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

## Runs

`POST /agents/{agent_key}/runs {input, variables, conversation_id?, channel: chat|test, version?}`
answers with an event stream (`text/event-stream`). The first event is `progress` with `run_id`.
Event names (C9): `token, tool_call, tool_result, approval_required, question, sources, progress,
fallback, done, error`; a client ignores names it does not know. Each event has an `id`; the
stream ends after `done`, `error`, `approval_required` or `question`.

- **Reconnect:** `GET /runs/{id}/stream` with `Last-Event-ID` continues after that event. Closing a
  stream never cancels a run. When the live stream has expired (`RUN_EVENT_STREAM_TTL_S`) the run
  is replayed from `run_events`, announced by `progress {"replay": "run_events"}`.
- **Approval:** a run waiting for an approval is `waiting_approval`. `POST /runs/{id}/resume
  {decision: approved|rejected, comment?}` needs the definition's `approval.assign_to` role with
  edit access. The stream continues from the approval. A second resume is 409 `run_not_waiting`.
- **Question:** `waiting_user`; the run's user answers with `POST /runs/{id}/resume {answer}`.
- **Cancel:** `POST /runs/{id}/cancel` (the run's user or a project admin). A queued or waiting run
  ends at once; a running one at its next step.
- **Abandoned:** a running run nobody listens to for `RUN_ABANDON_GRACE_S` stops at its next step
  with status `abandoned` and frees its model slot.
- **Read:** `GET /runs` (filters `agent_id`, `channel`, `status`, `feedback=pending|given`),
  `GET /runs/{id}`, `GET /runs/{id}/events`.
- **Feedback (F9):** `POST /runs/{id}/feedback {vote: correct|partial|wrong, note?}` on a completed
  run, with edit access: stored on the answer and sent to Langfuse as the score `expert_feedback`.

Superadmins run agents only in projects where they are members: the run searches and calls tools
on behalf of its user, where only membership counts (403 `run_needs_membership`).

### What happens in a run

`prepare` (budget) → `retrieve` (`always` knowledge bases, newest sources first) → `guard_in`
(`input.pre`, and `egress` where `GUARDRAIL_EGRESS_ENABLED=true`) → `model` → tool calls through
`tool_guard` (`tool.pre`, counters, approval request) → `approval` / `ask_user` (wait) → `tools`
(`tool.post`) → back to `model` → `guard_out` (`output.pre`) → `finalize` (structured output,
outcome label, confidence).

- A documents-only agent whose search found nothing answers its `unknown_reply` without a model
  call (`progress {"skipped_model": "no_sources"}`, outcome `declined`).
- With an `enforce` policy that checks output, the stream starts with `progress {"stage":
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
| `model_unavailable` | the model (and its configured fallback) could not answer; no implicit fallback |
| `model_not_found` | the agent's model is not active in the project |
| `upstream_error`, `stream_incomplete`, `empty_completion` | the provider answered without a usable result |
| `prompt_unavailable` | Langfuse could not give `platform_rules` or the agent's managed prompt |
| `knowledge_base_not_found`, `search_http_<status>` or the search API's own code | the knowledge search failed |
| `tool_layer_unavailable` | an agent with MCP tools before the tool layer is installed |
| `structured_output_invalid` | the final answer does not match `structured_output` |
| `cancelled`, `abandoned` | explicit cancel; nobody listening past the grace time |
| `worker_retries_exhausted` | the worker was stopped three times during the run |
| `run_error` | anything else; the worker log has the exception |

API errors at start: `agent_not_published` (404), `run_needs_membership` (403), `variable_unknown`
(422), `run_not_waiting` (409), `run_not_completed` (409, feedback). Langfuse delivery problems are
logged as `trace_delivery_failed` and never fail a run or a request.
