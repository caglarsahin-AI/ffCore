"""14: user memory. What the platform learned about a member (role, preferences, recurring
context, explicit decisions) kept inside the organisation and given to the model as a short note.

- `ffcore.models.memory`: `memories`, `memory_settings`, `memory_opt_outs` (migration 14_0001).
- `settings`: the effective settings of a run (agent row, else project row, else off) and the
  user's opt-out.
- `pii`: the one PII check every memory text passes (08 engine, `pii` rule in `block`).
- `store`: write (threshold, PII, embedding, dedupe/supersede, item limit) and recall.
- `extract`: the extraction call (prompt, JSON schema) the background job makes.
- `jobs`: the arq job and its enqueue after the run's `done` event.
- `recall`: the worker's client for recall and the system prompt block.
- `retention`: the retention executor of the `memory` class.

Embeddings and NER live in the API process only (06a: no model in the worker), so the worker
reaches recall and writes through internal routes (api/memories.py, `memories-internal`).
"""
