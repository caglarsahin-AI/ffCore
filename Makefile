# Hedefler tools konteynerinde koşar; host'a make/Node kurulmaz (K-00-0003, K-00-0005):
#   docker compose run --rm tools make <hedef>
# Servisleri başlatma/durdurma doğrudan compose ile: docker compose up -d --wait | down | logs -f
# Önyüz lint'i ayrı konteynerde: docker compose run --rm frontend npm run lint

.PHONY: lint format test test-int smoke pull

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

smoke:
	python scripts/smoke.py

pull:
	sh deploy/ollama/pull.sh
