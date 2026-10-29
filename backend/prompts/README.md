# Prompt seed

Each `<name>.md` here becomes the Langfuse prompt `<name>` with label `production` on first
install (`docker compose run --rm tools make seed-prompts`). After that, Langfuse owns the prompt:
edit and version it there; the seed never overwrites an existing prompt. The backend reads
prompts with `ffcore.core.prompts.PromptStore` (60 s cache; stale copy logged, no copy is an
error). Prompts arrive with the packages that use them (agents, 06a).
