# FFCore Trace: monitoring with Langfuse

Every model call, and the backend work around it, is traced to Langfuse on the internal network
(Langfuse 3.120.0: `langfuse-web` + `langfuse-worker`). This page covers package 02: first
install, how a run is found, how cost is reported, prompts, and what happens when Langfuse is
down.

## First install

Langfuse creates its organisation, project, API key pair and admin user on start from the
`LANGFUSE_INIT_*` variables. Nothing writes them for you:

1. `docker compose run --rm tools make langfuse-init` prints a new key pair and admin password
   once (it writes no file).
2. Copy the three lines into `.env`, and set `LANGFUSE_INIT_USER_EMAIL`.
3. `make up`. LiteLLM and the backend use the same key pair (compose derives `LANGFUSE_PUBLIC_KEY`
   and `LANGFUSE_SECRET_KEY` from `LANGFUSE_INIT_PROJECT_*`; one source).
4. `make smoke` checks that the keys exist and that Langfuse accepts them
   (`/api/public/projects` 200); a missing or rejected key is an error.

Starting again with the same values changes nothing. Langfuse keeps the secret key hashed.

## Configuration rules

| Setting | Rule |
|---|---|
| `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | all three or none. None: tracing is off, `langfuse_disabled` is logged once. Some but not all: the backend does not start. |
| `LANGFUSE_HOST` | an `http(s)` URL whose host is in `ALLOWED_INTERNAL_HOSTS` (default `langfuse-web`). An external host is refused at start-up; the SDK's cloud default is never used. |

The backend gives the Langfuse SDK a tracer provider of its own; the global OpenTelemetry
provider is not changed.

## What is traced

- **Model calls**: LiteLLM's `langfuse` callback sends one generation per call, streamed or
  not, with model, tokens, cost, user, session and tags.
- **Backend work**: `ffcore.core.tracing.span(name)` opens an observation. Inside it,
  `trace_context(run_id, user_id, tags)` gives the LiteLLM request metadata that puts LiteLLM's
  generation under that observation, so one trace shows the run with its model calls as
  children.
- **Run attributes**: `run_attributes(run_id, user_id, project_id, tags)` sets session = run id,
  user, `metadata.project_id` and tags (agent key and version, package 06a) on every observation
  inside.

Content goes to Langfuse after masking (package 08). Until masking is wired (06a), development
data must be synthetic.

## Finding a run

In the Langfuse UI (project FFCore):

- **Sessions**: the session id is the run id. A session lists every trace of the run.
- **Traces**: filter by user id, tag (agent key or version) or metadata `project_id`.
- Open a trace: the backend span, and under it each model call with its prompt, answer, tokens,
  latency and cost.

Through the API, with the project key pair as Basic auth:

```
GET /api/public/traces?sessionId=<run_id>
GET /api/public/traces/<trace_id>
```

A trace appears within a few seconds (measured: 6-11 s on the development stack). The worker
must be running; without it nothing is shown.

## Cost

Prices have one source: `models.pricing` in the console (package 03a), as `input_per_1m` and
`output_per_1m` USD. The reconciler writes them to LiteLLM as `input_cost_per_token` and
`output_cost_per_token`; LiteLLM computes the cost of each call and sends it to Langfuse with the
generation. Langfuse has no price table of its own. A local model's notional price is also set
in `models.pricing`.

Cost reports: Langfuse **Dashboard** (cost by model, user, tag, over time) or the daily metrics
API:

```
GET /api/public/metrics/daily?fromTimestamp=...&toTimestamp=...&tags=...
```

A model without a price shows cost 0; set the price in the console, it reaches LiteLLM within
seconds.

## Prompts

Prompts live in Langfuse prompt management, by name and label `production`. The backend reads
them with `ffcore.core.prompts.PromptStore`:

- cached for 60 s;
- Langfuse unreachable, cached copy present: the copy is served and `prompt_cache_stale` is
  logged;
- no cached copy: the call fails with `prompt_unavailable` (503). There is no silent local
  fallback.

`backend/prompts/*.md` are only the first-install seed: `docker compose run --rm tools make
seed-prompts` creates each one missing in Langfuse; it never overwrites a prompt that exists.
After that, edit and version prompts in Langfuse.

## When Langfuse is down

The backend and model calls keep working; traces of that time are lost. The backend logs
`trace_delivery_failed spans=<n> reason=<type>` (the error type only, never its text). LiteLLM's
callback logs only the Langfuse SDK's generic line `Unexpected error occurred. Please check your
request and contact support` for each batch it could not send; it does not say which calls were
lost. Prompts follow the rules above.

## Logs

The backend and the ingest worker share one log configuration (`ffcore.core.logging`). Every
log record is scrubbed when it is created, so every output sees only the scrubbed record:

- tokens, keys, `Authorization` values, URL passwords and every configured secret become `***`;
- personal data (e-mail, TR national ID, phone, IBAN, card; the guardrail recognizers) is
  masked as the guardrails mask it;
- a record that cannot be scrubbed is written as `log_scrub_failed` with a counter, never raw.

The access line is `access method=GET path=/api/... status=200 ms=12`: no query string, no
headers, no client address. HTTP client and telemetry libraries log at `WARNING` or above even
when `LOG_LEVEL=DEBUG`.

Langfuse tracing never holds a request or the process: one export has a 5 s budget, shutdown
waits at most 10 s (`trace_shutdown_timeout` after that), and what is not sent is reported as
`trace_delivery_failed`.
