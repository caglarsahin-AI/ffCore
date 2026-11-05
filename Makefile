# Hedefler tools konteynerinde koşar; host'a make/Node kurulmaz (K-00-0003, K-00-0005):
#   docker compose run --rm tools make <hedef>
# Servisleri başlatma/durdurma doğrudan compose ile: docker compose up -d --wait | down | logs -f
# Önyüz lint'i ayrı konteynerde: docker compose run --rm frontend npm run lint

.PHONY: lint format test test-samples test-int seed e2e eval test-models test-ner-latency models models-check smoke pull seed-models render-litellm reindex langfuse-init seed-prompts seed-sql-demo seed-sql-context seed-eval

lint:
	ruff check backend scripts data/samples/scripts services
	ruff format --check backend scripts data/samples/scripts services

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

# 08 full 1c (ENV-177): the NER latency acceptance (P95 < 300 ms, 1,000 characters, local rules
# and NER) on the target machine, offline; prints the P95. Run before GUARDRAIL_EGRESS_NER=true.
test-ner-latency:
	cd backend && RUN_MODEL_TESTS=1 pytest -m models -s tests/models/test_08t_ner_models.py -k latency

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

# 09: the sample exam sets (13a) into a project's Langfuse datasets and suites; idempotent.
# WITHOUT=llm_judge leaves the judge out when EVAL_JUDGE_MODEL is empty (explicit, never silent).
seed-eval:
	@test -n "$(PROJECT)" || (echo "usage: make seed-eval PROJECT=<project_key> [WITHOUT=llm_judge]" >&2; exit 2)
	cd backend && python -m ffcore.cli seed-eval --project "$(PROJECT)" --suite ../data/samples/eval/suite.json --items ../data/samples/eval/sozlesme-33.json $(if $(WITHOUT),--without $(WITHOUT),)
	cd backend && python -m ffcore.cli seed-eval --project "$(PROJECT)" --suite ../data/samples/eval/suite-sql-20.json --items ../data/samples/eval/sql-20.json $(if $(WITHOUT),--without $(WITHOUT),)

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

# 13b: the PoC demo and scenario data (plan/18 seed, tests/e2e/scenarios/seed.py), idempotent: a
# second run reports "created 0, uploaded 0". Passwords come from the shell, never a file:
#   docker compose --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test #     run --rm -e E2E_ADMIN_EMAIL -e E2E_ADMIN_PASSWORD -e E2E_PASSWORD tools make seed e2e
seed:
	python -m tests.e2e.scenarios.seed

# 13b: every API e2e test (plan/18 scenarios + tests/e2e/negative) against the seeded scenario
# stack, with the F table (F1-F13, NOT_RUN reasons) written to eval/results/ (git-ignored). The
# console's Playwright e2e is its own compose service (docker compose --profile e2e run --rm e2e;
# tools has no Docker socket). Same compose command as `seed`, with -e E2E_PASSWORD.
E2E_STAMP := $(shell date -u +%Y%m%d-%H%M)
e2e:
	RUN_E2E_SCENARIOS=1 pytest tests/e2e -rs --f-table eval/results/e2e-$(E2E_STAMP).md

# 13b: an exam set through the run API, report to eval/results/ (scripts/eval_report.py). MODEL
# names what answered (no default: a fake-llm run is reported as a pipeline check, not a result).
# Default set data/samples/eval/sozlesme-33.json; on the PayCore server DATASET=<S1 path>.
# APPROVE_SQL=1 approves each run_sql call (an explicit choice; without it SQL items are NOT_RUN).
# EVAL_OUT=<dir> writes the report there (19: required for a DATASET outside the repository,
# so the S1 report never lands in a checkout; inside the repository only eval/results/).
# EXCLUDE_SOURCES="prsim" leaves out questions whose metadata.sources name it (19: S1 without
# PRSIM, counted n/N in the report); WARMUP=N runs N questions first, reported apart.
#   make eval MODEL=fake-llm [DATASET=...] [PROJECT=hastane-a] [APPROVE_SQL=1] [EVAL_OUT=dir]
eval:
	@test -n "$(MODEL)" || (echo "usage: make eval MODEL=<what answers> [DATASET=path] [APPROVE_SQL=1]" >&2; exit 2)
	python scripts/eval_report.py --model "$(MODEL)" --project "$(or $(PROJECT),hastane-a)" $(if $(DATASET),--dataset "$(DATASET)",) $(if $(APPROVE_SQL),--approve-sql,) $(if $(EVAL_OUT),--out-dir "$(EVAL_OUT)",) $(if $(EXCLUDE_SOURCES),--exclude-sources $(EXCLUDE_SOURCES),) $(if $(WARMUP),--warmup $(WARMUP),)
