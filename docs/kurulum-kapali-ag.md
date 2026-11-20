# Closed-network installation (airgap)

The `airgap` profile: no outbound network at all, the model runs on the server (Ollama on CPU,
or vLLM on GPU). Read [kurulum.md](kurulum.md) first: settings, first start, superadmin, health
check, database role, backup, update and rollback are the same. This page adds only what is
different, on the FFCore side. The full server procedure for the PayCore server (preparation
machine, transport, corpus, measurement) is the package 19 runbook in the consumer repository
(`docs/paycore/m3-sunucu.md`); this page does not repeat it.

Every command here was run on a local test stack or with `--dry-run`/`--help` unless it says
**not verified**.

## What changes against llmaas

| Setting | airgap |
|---|---|
| `DEPLOY_PROFILE` | `airgap` |
| `OFFLINE` | `true`: every outbound host is refused |
| `EGRESS_ALLOWLIST` | empty; no `egress` or `tls`-for-egress overlay (the preflight refuses `egress` in airgap) |
| `GUARDRAIL_EGRESS_ENABLED` | `false` (no external provider; the egress stage answers `409 egress_stage_disabled`) |
| `INFERENCE_BACKEND` | `ollama` (CPU) or `vllm` (GPU) |
| `REGISTRY_PREFIX` | the internal registry, or empty when the images are loaded from the archive |
| `LLM_SLOTS`, `BACKGROUND_WINDOW`, `RUN_TIMEOUT_S` | CPU values: `.env.example`, "airgap example"; sizing in [donanim.md](donanim.md) |
| `APP_DB_USER`, `APP_DB_PASSWORD` | recommended as in llmaas, both together; both empty runs the application as the owner (the preflight names it); one without the other is refused (`db_role_incomplete`) |

## Images and model weights

Nothing is pulled on the server. On an internet-connected preparation machine
`deploy/offline/save.sh` pulls every image by its pinned digest, builds the FFCore images and
packs the model weights; on the server `deploy/offline/load.sh` checks the archive, loads it and
runs `deploy/offline/verify.sh` against the lists in git (`images.txt`, `models.txt`). See
`deploy/offline/README.md`.

```bash
deploy/offline/load.sh <archive_dir> --models-dir /opt/data/ffcore/models --dry-run
```

The GPU path's vLLM image is listed apart (`deploy/offline/images-vllm.txt`, ~11.9 GB) so the
CPU archive does not carry it: `IMAGES_TXT=deploy/offline/images-vllm.txt deploy/offline/save.sh ...`
on the preparation machine and `IMAGES_TXT=... deploy/offline/verify.sh --images` on the server
(**not verified**: the image was never pulled in development).

Building the images needs a Python package source: PyPI on the preparation machine, or an
internal mirror (`--build-arg UV_INDEX_URL=...`, wheels from `deploy/offline/wheels.sh`).

## Ollama (CPU)

Either the compose service or an Ollama already on the host:

- **Compose service:** add the overlay and the profile, and set the three mandatory values:

  ```
  COMPOSE_PATH_SEPARATOR=,
  COMPOSE_FILE=compose.yaml,deploy/docker-compose.ollama.yml
  COMPOSE_PROFILES=ollama
  OLLAMA_CONTEXT_LENGTH=32768
  OLLAMA_MEM_LIMIT=36g
  OLLAMA_MODELS_DIR=/opt/data/ollama
  ```

  `OLLAMA_CONTEXT_LENGTH` is mandatory (the default 4096 truncates prompts silently) and is
  reserved for every loaded model; `OLLAMA_MEM_LIMIT` comes from the memory budget
  ([donanim.md](donanim.md)). Models travel as the `~/.ollama/models` directory of a machine
  that ran `ollama pull`, copied to `OLLAMA_MODELS_DIR`.
- **Ollama on the host** (the PayCore server): no overlay, no profile; the seed's provider
  address `SEED_OLLAMA_BASE_URL=http://host.docker.internal:11434`. The preflight prints
  `ollama: external`.

`make smoke` checks the models are pulled and that each model's trained context is at least
`OLLAMA_CONTEXT_LENGTH` (compose service only).

## vLLM (GPU)

```
COMPOSE_PATH_SEPARATOR=,
COMPOSE_FILE=compose.yaml,deploy/docker-compose.vllm.yml
COMPOSE_PROFILES=vllm
INFERENCE_BACKEND=vllm
SEED_VLLM_MODEL=<served model name>
VLLM_MODELS_DIR=/opt/data/vllm
VLLM_MODEL=<directory under VLLM_MODELS_DIR>
VLLM_MAX_MODEL_LEN=<context length>
VLLM_MEM_LIMIT=<host memory limit>
```

vLLM serves the weights read-only from `VLLM_MODELS_DIR/VLLM_MODEL` under the name
`SEED_VLLM_MODEL`, the same name `deploy/seed/models.airgap.yaml` registers, so LiteLLM routes the
model to it without code changes. The host needs the NVIDIA container toolkit. Checked here:
`docker compose config` with the overlay; serving and the P50/P95 of ten concurrent questions
are **not verified** (no GPU; [donanim.md](donanim.md) says how to measure).

## Knowledge base weights

bge-m3, the reranker, Docling and PaddleOCR weights are files in the models directory
(`models.txt`); the backend never downloads them (`HF_HUB_OFFLINE=1`). Check them on the server:

```bash
docker compose run --rm tools make models-check
```

## Database role, backup, update

As in [kurulum.md](kurulum.md). The backup leaves out the model weights and the Ollama/vLLM model
directories: they come from the archive again.
