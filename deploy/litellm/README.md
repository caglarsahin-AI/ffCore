# LiteLLM

The model gateway on the internal network (package 01). Full description: `docs/gateway.md`.

- `config.yaml` holds general settings only. There is no `model_list` and there must never be
  one: models live in LiteLLM's database and are written from the `providers` and `models`
  tables by the reconciler.
- Add a model: create it in the console (or `make seed-models` on first install). The backend
  reconciles within seconds; `make render-litellm` does it by hand, `CHECK=1` only reports.
- Never call LiteLLM's `/config/update`: it stores the master key in plain text in its database.
- Fallback: only a project's `chat-fallback` model, sent with each request. Without one a
  provider failure is `503 model_unavailable`.
- The LiteLLM admin UI is off (`DISABLE_ADMIN_UI`); its port is not published.
- Version is pinned in `deploy/docker-compose.yml` (`ghcr.io/berriai/litellm:v1.80.0-stable`). On
  an upgrade, re-run the 01 integration tests: they check key encryption at rest, the
  `x-litellm-model-id` header used for fallback detection, and the empty `LiteLLM_Config` table.
