# Hedefler tools konteynerinde koşar; host'a make/Node kurulmaz (K-00-0003, K-00-0005):
#   docker compose run --rm tools make <hedef>
# Servisleri başlatma/durdurma doğrudan compose ile: docker compose up -d --wait | down | logs -f
# Önyüz lint'i ayrı konteynerde: docker compose run --rm frontend npm run lint

.PHONY: lint format test test-samples test-int test-models models models-check smoke pull seed-models render-litellm reindex langfuse-init seed-prompts seed-sql-demo seed-sql-context

lint:
	ruff check backend scripts data/samples/scripts
	ruff format --check backend scripts data/samples/scripts

format:
	ruff check --fix backend scripts
	ruff format backend scripts

# vitest 10a ile eklenecek; 00'da yalnızca pytest.
test:
	cd backend && pytest tests/unit tests/contract

# Sample data generators and their acceptance tests (13a, 18-hazirlik): stdlib unittest, no
# Docker socket, so the opt-in Postgres tests report NOT_RUN here (host: RUN_PG_TESTS=1).
test-samples:
	python -m unittest discover -s data/samples/scripts/tests -v

# Qdrant tests need the qdrant profile up (docker compose --profile qdrant up -d qdrant); the
# defaults are the Compose service, so every run uses the same values (review r1). `$(or)`, not
# `?=`: Compose passes QDRANT_URL to tools as an empty value, which `?=` leaves empty (FOLLOWUP-84).
QDRANT_URL := $(or $(QDRANT_URL),http://qdrant:6333)
RUN_QDRANT_TESTS := $(or $(RUN_QDRANT_TESTS),1)
test-int:
	cd backend && QDRANT_URL=$(QDRANT_URL) RUN_QDRANT_TESTS=$(RUN_QDRANT_TESTS) pytest tests/integration

# 04a: real model weights (bge-m3, reranker, Docling, PaddleOCR); required for VERIFIED (S4).
test-models:
	cd backend && RUN_MODEL_TESTS=1 pytest -m models -s tests

# 04a: the one step that downloads model weights (bge-m3, reranker, Docling, PaddleOCR tr) into
# the model_cache volume. It connects out (airgap: HF_ENDPOINT = the internal mirror) and is
# run by the user, once per installation; everything else is offline (r1 MAJOR-6, K-04a-0020).
models:
	cd backend && HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python -m ffcore.knowledge.models download

# Every weight and where it is looked for; offline; exit 1 when one is missing.
models-check:
	cd backend && python -m ffcore.knowledge.models check

smoke:
	python scripts/smoke.py

# 04a: make reindex PROJECT=<key> KB=<key> LAYER=silver|gold [FULL=1]. gold never reads raw or
# the source (D3); the worker logs reused=N embedded=M.
reindex:
	cd backend && python -m ffcore.cli reindex --project $(PROJECT) --kb $(KB) --layer $(LAYER) $(if $(FULL),--full,)

pull:
	sh deploy/ollama/pull.sh

# 01: first-install providers and models of one project from deploy/seed/models.<profile>.yaml,
# then reconcile LiteLLM. Existing rows are left as they are. Usage: make seed-models PROJECT=<key>
seed-models:
	@test -n "$(PROJECT)" || (echo "usage: make seed-models PROJECT=<project_key>" >&2; exit 2)
	cd backend && python -m ffcore.cli seed-models --project "$(PROJECT)" --path ../deploy/seed/models.$${DEPLOY_PROFILE:?DEPLOY_PROFILE is not set}.yaml
	cd backend && python -m ffcore.cli render-litellm

# 01: make LiteLLM's model list equal to the providers/models tables (no restart, no config file).
# CHECK=1 only reports the difference and exits 1 if there is one.
render-litellm:
	cd backend && python -m ffcore.cli render-litellm $(if $(CHECK),--check,)

# 02: print a new Langfuse key pair and admin password once (copy into .env; nothing is written).
langfuse-init:
	sh deploy/langfuse/init.sh

# 02: first-install prompts (backend/prompts/*.md) into Langfuse; existing prompts stay.
seed-prompts:
	cd backend && python -m ffcore.cli seed-prompts --path prompts

# 05a: mcp-sql's demo database (13a, synthetic) with its read-only login user; idempotent.
# Needs AGENT_DEMO_DB_PASSWORD in .env.
seed-sql-demo:
	cd backend && python -m ffcore.cli seed-sql-demo --path ../data/samples/schema

# 05a: table descriptions and SQL examples for get_schema, into one project (a reload replaces).
seed-sql-context:
	@test -n "$(PROJECT)" || (echo "usage: make seed-sql-context PROJECT=<project_key> [TOOL=mcp-sql]" >&2; exit 2)
	cd backend && python -m ffcore.cli seed-sql-context --project "$(PROJECT)" --tool "$(or $(TOOL),mcp-sql)" --path ../data/samples/schema
