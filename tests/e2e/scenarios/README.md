# Use-case scenario tests (plan/18)

End-to-end tests of the plan/18 use cases (F1-F13) against a running stack, through the
public API only. Results and NOT_RUN reasons: `state/pr/18-e2e.md`; the demo page:
`docs/demo.md`.

## Stack

The scenario stack is the test stack (`--profile test`: fake-llm, ticket-desk) with one overlay,
`e2e.env`, given as a **second** `--env-file` to **every** compose command, `run` included.
A `run` without it recreates services with the other environment (FOLLOWUP-93).

`e2e.env` sets `FAKE_EMBED=1` (deterministic embedding and rerank stand-ins; the stack has no
model weights) and adds `fake-llm` to `ALLOWED_INTERNAL_HOSTS`. The backend needs that entry
even though LiteLLM, not the backend, connects to fake-llm: before writing a model to LiteLLM
the backend checks the provider's base URL against the egress policy
(`services/litellm_reconcile.py`, `check_url`). No secret is in the file;
`test_18_env_overlay` keeps its host list equal to `.env.test`'s plus `fake-llm`.

Passwords come from the shell, never a file:

| Variable | Used by |
|---|---|
| `E2E_ADMIN_EMAIL`, `E2E_ADMIN_PASSWORD` | `seed.py`: the superadmin it creates (`create-superadmin --password-stdin`) |
| `E2E_PASSWORD` | `seed.py` and the tests: every seeded member (≥ 12 characters) |

```bash
export FFCORE_VERSION=0.0.0-18e2e E2E_ADMIN_EMAIL=e2e-admin@example.test E2E_ADMIN_PASSWORD=... E2E_PASSWORD=...
C="docker compose -p ffcore-18e2e --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test"
$C up -d --wait
$C run --rm --no-deps -e E2E_ADMIN_EMAIL -e E2E_ADMIN_PASSWORD -e E2E_PASSWORD tools python -m tests.e2e.scenarios.seed
$C run --rm --no-deps -e E2E_PASSWORD -e RUN_E2E_SCENARIOS=1 tools pytest tests/e2e/scenarios -v
$C down -v
```

## Seed (`seed.py`)

Public API and the documented CLI only; idempotent (a 409 is looked up by key). 13b takes it
over. It creates: the superadmin; the Langfuse prompts (`seed-prompts`, `platform_rules` is
required by every run); the two projects and their members from `projects/projects.json`; the
fake-llm provider with the models `chat-default` (answers "hello"), `chat-fail` (500) and
`chat-slow` (slow stream), `chat-tools` (upstream `tool-default`: calls the first tool once, then
answers; fix/fake-llm-tool-mode); each project's knowledge bases from `projects.json` plus `zehirli`
(F11) and `surumler` (F13) in `hastane-a`; the tools `mcp-sql` (forward_user) and `ticket-desk`
(auth none) with reads open and writes needing approval, the demo database and its SQL context;
every agent template in `hastane-a`, the agents `projects.json` names elsewhere, and the F12
agents `e2e-yavas` / `e2e-hatali`, and `e2e-sql` (F3: one approved `run_sql`) and `e2e-bilet` (F2:
`send_reply` waits for an analyst) on `chat-tools`.

## What fake-llm can and cannot prove

fake-llm answers "hello"; its `tool-*` mode calls the first offered tool once with sample
arguments, never one the user's text chose. A criterion that depends on the model's answer
or on a tool call the model chooses is NOT_RUN with the reason "gerçek model" (PayCore S1 /
llmaas), never passed on a fake answer: a "hello" without a canary proves nothing. Without
`RUN_E2E_SCENARIOS=1` every stack test is skipped as NOT_RUN; `test_18_env_overlay` always runs.
