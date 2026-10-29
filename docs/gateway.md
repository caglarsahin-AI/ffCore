# FFCore Gateway: model calls through LiteLLM

Every model call of FFCore goes through the LiteLLM proxy on the internal network. LiteLLM is
never published outside; external clients use the backend (facade, package 06b). This page
covers package 01: where LiteLLM's model list comes from, how the backend calls it, and what
happens when a provider fails.

## One source: the tables

The `providers` and `models` tables (console, package 03a) are the only source of LiteLLM's
models. `deploy/litellm/config.yaml` has no `model_list`. The reconciler compares the tables with
LiteLLM's `/model/info` and applies the difference with `/model/new`, `PATCH /model/{id}/update` and
`/model/delete`:

- when the backend starts,
- after every provider or model change (in the background, a few seconds),
- by hand: `docker compose run --rm tools make render-litellm` (`CHECK=1` only reports).

No restart and no config reload: a stream that is running keeps running. A model is written only
if it is active, its category is `llm`, its provider is active and assigned to the model's
project. Embedding models never go to LiteLLM; embeddings run inside the backend (package 04a).

Rows that cannot be written are not skipped silently. They are reported with a code (in the log
as `litellm_model_not_written`, and by `render-litellm`):

| Code | Meaning |
|---|---|
| `egress_offline` | `OFFLINE=true` and the provider's address is not an internal host |
| `egress_not_allowlisted` | the provider's address is neither in `EGRESS_ALLOWLIST` nor in `ALLOWED_INTERNAL_HOSTS` |
| `provider_not_assigned` | the provider is not assigned to the model's project |
| `upstream_api_unsupported` | `upstream_api` is `responses`; only `chat` is wired |
| `forward_unknown_params_unsupported` | LiteLLM has no per-model switch for it; leave it off |

The same egress rules as for every outbound call apply (`core/egress.py`). An Ollama on the host
(PayCore: `http://host.docker.internal:11434`) therefore needs `host.docker.internal` in
`ALLOWED_INTERNAL_HOSTS`, and `litellm` itself must be there too.

## Names

The LiteLLM name of a model is `<project_key>.<model_key>`, for example `hastane.chat-default`
(CONTRACTS C1). The backend resolves the short name within a project. Each LiteLLM model carries
`model_info.id` = the `models.id` of its row.

## Keys

- `LITELLM_MASTER_KEY`: used only by the reconciler for the management API.
- `LITELLM_INTERNAL_KEY`: the one key the backend sends model calls with. The reconciler registers
  it in LiteLLM once. There are no per-project LiteLLM teams or virtual keys (decision A4);
  project, user and run go with every call in `user` and `metadata`, quotas are kept by the
  backend.
- Provider keys are stored encrypted in `providers` (Fernet) and sent to LiteLLM in the body of
  `/model/new`. LiteLLM stores them encrypted with `LITELLM_SALT_KEY` (checked on
  v1.80.0-stable: no key in plain text in its tables, `/model/info` does not return it).

FFCore never calls LiteLLM's `/config/update`: on v1.80.0 it writes the master key and the
database URL in plain text into LiteLLM's `LiteLLM_Config` table. A test checks that the table
stays empty.

## Fallback

Fallback is explicit. A project's `chat-default` falls back only if the project has an active
`chat-fallback` model; the backend then sends `fallbacks: ["<project>.chat-fallback"]` with the
request. There is no global fallback in LiteLLM and no implicit switch to another provider. The
airgap seed has no `chat-fallback`, and with `OFFLINE=true` no model can point outside.

When the fallback answered, the client returns `FallbackObserved(source_model, target_model,
reason)`. It recognises this from the `x-litellm-model-id` response header (present in streamed
and non-streamed answers) compared with the requested model's id. Agents record it as a
`fallback` run event (package 06a).

Without a fallback, or when the fallback fails too, the call fails with
`503 model_unavailable`. A model the tables know but LiteLLM does not serve yet (reconcile pending
or failed) is also `503 model_unavailable`. An empty answer is `502 empty_completion`, never an
empty string.

## Request settings

| Setting | Where | Value |
|---|---|---|
| Per-call timeout | `LLM_CALL_TIMEOUT_S` | llmaas 60 s, airgap CPU 600 s, airgap GPU 120 s |
| Retries | reconciler | 2 per model; LiteLLM backs off on 429 |
| Usage in streams | client | `stream_options.include_usage` (last chunk carries the token counts) |
| Parallel tool calls | client | off whenever tools are sent |
| Extra request body | model `request_policy.extra_body` | e.g. `{"reasoning_effort": "none"}` |
| Dropped parameters | model `request_policy.reject_params` | LiteLLM `additional_drop_params` |
| Prices | model `pricing` | written as LiteLLM cost per token |

Qwen thinking stays off through `extra_body.reasoning_effort: none` (PayCore measurement D6).
Give it there, not as a separate parameter: LiteLLM v1.80.0 refuses `reasoning_effort` as a
direct parameter for models it does not know.

## Profiles and the seed

The profile difference is the seed file, not code: `deploy/seed/models.llmaas.yaml` and
`deploy/seed/models.airgap.yaml`. On first install:

```bash
docker compose run --rm tools make seed-models PROJECT=hastane
```

The project must exist. Secret values come from `SEED_*` variables in `.env` and are stored
encrypted; remove them from `.env` afterwards. Existing rows are left as they are; after the
first install the console owns providers and models.

- **llmaas:** Anthropic `chat-default` and `memory-extract`; Azure OpenAI `chat-fallback` if the
  `SEED_AZURE_OPENAI_*` variables are set (otherwise skipped, and reported). Prices are empty:
  enter them in the console, until then costs read 0 and the log says `pricing_missing`.
- **airgap:** Ollama (`INFERENCE_BACKEND=ollama`) or vLLM (`vllm`), `chat-default` and
  `memory-extract`, no fallback, virtual prices 0.

## Embedding dimension

`EMBED_DIM` in `.env` is the one embedding dimension of the installation (pgvector column size,
package 04a). Changing the embedding model means re-indexing (`migrate-vectors`, package 04b).
