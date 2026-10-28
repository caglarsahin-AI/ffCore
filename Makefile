# Hedefler tools konteynerinde koşar; host'a make/Node kurulmaz (K-00-0003, K-00-0005):
#   docker compose run --rm tools make <hedef>
# Servisleri başlatma/durdurma doğrudan compose ile: docker compose up -d --wait | down | logs -f
# Önyüz lint'i ayrı konteynerde: docker compose run --rm frontend npm run lint

.PHONY: lint format test test-int test-models smoke pull seed-models render-litellm

lint:
	ruff check backend scripts data/samples/scripts
	ruff format --check backend scripts data/samples/scripts

format:
	ruff check --fix backend scripts
	ruff format backend scripts

# vitest 10a ile eklenecek; 00'da yalnızca pytest.
test:
	cd backend && pytest tests/unit tests/contract

test-int:
	cd backend && pytest tests/integration

# 04a: real model weights (bge-m3, reranker, Docling, PaddleOCR); required for VERIFIED (S4).
test-models:
	cd backend && RUN_MODEL_TESTS=1 pytest -m models -s tests

smoke:
	python scripts/smoke.py

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
