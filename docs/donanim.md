# Hardware sizing

How much machine an FFCore installation needs, for the two ways the model runs: on CPU
(`airgap` with Ollama: proof of concept and small installations) and on GPU (`airgap` with vLLM:
production). An `llmaas` installation runs no model locally and needs only the "Platform" rows.
The purchase decision is the customer's; this page gives examples and the method, not an offer.

Every number names its source. A cell that was never measured says **not measured**; fill it
in from your own hardware (method at the end) rather than from a guess.

## Measured on CPU (PayCore server, airgap, Qwen 3.5 35B on Ollama)

Source: plan/12 5b (PayCore measurements D6), Ollama with `OLLAMA_NUM_PARALLEL=1`.

| What | Measured |
|---|---|
| Prompt processing (prefill) | ~112 tokens/s |
| Generation | ~11 tokens/s |
| Knowledge base answer (RAG), end to end | 84-114 s |
| One agent turn with a tool call (`mode: tool`) | ~3 min |
| Concurrent users | one model call at a time: 10 users queue behind each other |

Consequences: CPU is for the proof of concept, a pilot group, and background work (exams run
inside `BACKGROUND_WINDOW`). Set `LLM_SLOTS=1` (one model slot) and a long `RUN_TIMEOUT_S`
(`.env.example`, airgap example). `OLLAMA_CONTEXT_LENGTH` is mandatory (Ollama's default 4096
truncates prompts silently; `make smoke` checks it) and is reserved for every loaded model.

## GPU example (production)

Source: plan/12 5b (PayCore correction D8). An example configuration, **not measured** on
FFCore:

| Item | Example |
|---|---|
| GPU | 1 x 96 GB class (for example RTX PRO 6000 Blackwell) |
| Chat model | Qwen 3.5 35B-A3B FP8, ~35 GB |
| Plus a small routing model, bge-m3 and the reranker | ~45 GB in total with the chat model |
| Left for the context (KV cache) | the rest of the 96 GB |
| Target | 10 concurrent users |
| Growth | a code model or a larger agent model needs 2-4 GPUs: choose a chassis ready for 4 |
| Virtualisation | GPU passthrough; vGPU needs a yearly licence |

Serving: `INFERENCE_BACKEND=vllm` with `deploy/docker-compose.vllm.yml` (profile `vllm`);
LiteLLM routes the same model name to it, the application does not change. Embedding and
reranking stay in the backend process (CPU or the same GPU through PyTorch).

| GPU measurement | Result |
|---|---|
| 10 concurrent RAG questions, P50 | not measured (needs the GPU; `NOT_RUN (PENDING_ENV)`) |
| 10 concurrent RAG questions, P95 | not measured (same) |

## Memory budget

Every container's `mem_limit` is a measured value or a ceiling the operator sets from this
table; a limit too small swaps or kills (PayCore: Ollama at 36 GB went into swap, plan/12 5b).
The context length is reserved per loaded model, up front.

### CPU installation (example: the PayCore server, 96 GB RAM)

Source: KARARLAR "PayCore sunucu belleği 96 GB" (FFCore and PayCore stacks together: about
88 GB of ceilings plus a 6 GB operating system share), compose limits in
`deploy/docker-compose.yml`.

| Component | Memory | Source |
|---|---|---|
| Ollama (chat model + context) | `OLLAMA_MEM_LIMIT`, 36 GB in the PayCore example | `.env.example` airgap example |
| Ingest worker (one converter process: Docling 2.3 GB, PaddleOCR 1.7 GB peak) | `WORKER_MEM_LIMIT=6g` | measured 2026-10-29, compose comment |
| Each MCP server (mcp-search, mcp-sql) | `MCP_MEM_LIMIT=512m` | compose |
| Backend (API, embedding with bge-m3, reranker) | not measured | |
| Agent workers (interactive and background) | not measured | |
| Postgres (pgvector) | not measured | |
| Qdrant (when used) | not measured | |
| Langfuse (web, worker, Postgres, ClickHouse, MinIO, Redis) | not measured | |
| LiteLLM | not measured | |
| Egress proxy / TLS proxy (llmaas overlays) | ceilings 256 MB / 128 MB | `EGRESS_PROXY_MEM_LIMIT`, `TLS_PROXY_MEM_LIMIT` |
| Operating system | 6 GB share | KARARLAR |

### GPU installation

| Component | Memory | Source |
|---|---|---|
| vLLM (host RAM; the model is in GPU memory) | `VLLM_MEM_LIMIT`: not measured | |
| GPU memory | weights + KV cache under `VLLM_GPU_MEMORY_UTILIZATION` (0.90) | GPU example above |
| The platform rows | as in the CPU table, without Ollama | |

## Disk

| Data | Size | Where |
|---|---|---|
| Raw and silver files of the knowledge bases | the corpus plus its converted text; not measured | `knowledge_storage` volume |
| Gold layer (chunks, vectors) | not measured | Postgres (or Qdrant) |
| Model weights (bge-m3, reranker, Docling, PaddleOCR) | `deploy/offline/models.txt` lists every file and its size | `model_cache` volume |
| Ollama models | not measured here (the GPU example's FP8 chat model is ~35 GB) | `OLLAMA_MODELS_DIR` |
| vLLM image | ~11.9 GB compressed | `deploy/offline/images-vllm.txt` |
| Langfuse (traces, ClickHouse) | grows with use; not measured | ClickHouse volume |
| Backups | about the Postgres dumps plus the storage volume | `deploy/backup.sh --out` |

## How to measure your own

1. Memory per container under load: `docker stats --no-stream` while an ingest and a few chat
   runs are going; set each `mem_limit` about 20 % above the peak.
2. CPU answer time: `make eval MODEL=<name>` on the sample exam set reports the time per
   question (docs/evaluation.md).
3. GPU P50/P95: ten concurrent chat runs against one agent with a knowledge base; record the
   time to the last token of each and take the median and the 95th percentile.

Write the results into this page with the date and the machine, replacing **not measured**.
