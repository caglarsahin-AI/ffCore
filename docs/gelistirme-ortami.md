# Geliştirme ortamı

Host'a yalnızca **Docker Desktop** (Windows) ya da Docker Engine + Compose v2 gerekir. Python, Node, `make`
host'a kurulmaz (KARARLAR "Geliştirme araçları Docker'da", "make de Docker'da"): araçlar `tools` ve
`frontend` konteynerlerinde koşar.

## İlk kurulum

Geliştirme ve CI (yalnızca açıkça sahte değerler; üretimde kullanılmaz):

```bash
cp .env.test .env
docker compose up -d --wait   # depo kökünde; tüm healthcheck'ler yeşil olunca döner (ilk açılış birkaç dk)
docker compose run --rm tools make smoke
```

Gerçek kurulum: `cp .env.example .env`, ardından gizli değerleri kurulumu yapan kişi doldurur (ajanlar ve
scriptler `.env` yazmaz). Boş bırakılan zorunlu değişken varsa `docker compose` hangi değişkenin eksik
olduğunu yazarak durur.

`migrate` servisi her `up`'ta backend'den önce `alembic upgrade heads` koşar (idempotent); başarısızsa backend
başlamaz. Geri alma: `docker compose run --rm migrate alembic downgrade <revizyon>`.

## Günlük komutlar

| İş | Komut |
|---|---|
| Servisleri başlat / durdur | `docker compose up -d --wait` / `docker compose down` |
| Loglar | `docker compose logs -f [servis]` |
| Python lint | `docker compose run --rm tools make lint` |
| Önyüz lint | `docker compose run --rm frontend npm run lint` |
| Unit + sözleşme testleri | `docker compose run --rm tools make test` |
| Entegrasyon testleri | `docker compose --profile test --profile qdrant up -d --wait && docker compose run --rm tools make test-int` |
| Duman testi | `docker compose run --rm tools make smoke` |
| Ollama modellerini çek | `docker compose run --rm tools make pull` |

Testler model ağırlığı istemez: `make test` ve `make test-int` boş `model_cache` ile geçer. Gerçek
ağırlıkla koşan testler `models` işaretlidir (`make models` sonrası `make test-models`). Entegrasyon
testleri varsayılan yığına ek olarak `fake-llm` (profil `test`, 01) ve `qdrant` (profil `qdrant`,
04a) ister; tablodaki komut ikisini de başlatır. Biri erişilemezse `make test-int` tek mesajla, bu
komutu yazarak durur.

`RUN_DNS_TESTS=1` (varsayılan kapalı) gerçek sistem resolver'ıyla bir `.invalid` adı sorgular; Docker bu
sorguyu host'un, kurumda kurum DNS'inin resolver'ına iletir, yani yığın dışına bir DNS sorgusu gider.
Bayrak yokken test `NOT_RUN: needs RUN_DNS_TESTS=1` diye görünür ve hiçbir sorgu yapılmaz. Bayrağı
yalnız dış DNS'e sorgu gönderilmesi uygun olan ortamda verin:
`docker compose run --rm -e RUN_DNS_TESTS=1 tools make test-int`.

`tools` konteyneri depo kökünü `/work` olarak bağlar (compose: `.:/work`) ve servislere compose ağından servis adıyla gider.
Docker soketi bağlanmaz; konteyner içinden `docker` komutu çalışmaz.

## Tüketici olarak kurulum (`import ffcore`)

Backend kurulabilir `ffcore` paketidir (`backend/pyproject.toml`, derleme arka ucu `uv_build` pinli).
Tüketici depo (örneğin PayCore LLM) geliştirmede yol bağımlılığıyla kurar:
`pip install -e ../ffcore/backend` (ya da `uv pip install -e ../ffcore/backend`), ardından `import ffcore`.
`ffcore` tüketiciyi import etmez; `test_00_1_ffcore_never_imports_consumer` bunu korur.

## Profiller

- `llmaas` (varsayılan): `COMPOSE_PROFILES` boş; Ollama servisi kalkmaz, `make smoke` Ollama adımını
  `skipped: ollama profile inactive` diye yazar.
- `airgap` + `INFERENCE_BACKEND=ollama`: `.env`'de `COMPOSE_PATH_SEPARATOR=,`,
  `COMPOSE_FILE=compose.yaml,deploy/docker-compose.ollama.yml` ve `COMPOSE_PROFILES=ollama`. Ollama servisi
  ayrı dosyadadır, çünkü compose `${VAR:?}` kontrolünü profil elemesinden önce yapar; böylece llmaas
  Ollama değerleri olmadan kalkar, Ollama eklendiğinde `OLLAMA_CONTEXT_LENGTH` ve `OLLAMA_MEM_LIMIT` boşsa
  compose değişken adını yazarak durur. Model listesi `deploy/ollama/models.airgap.txt` (yalnızca chat modeli; embedding süreç içi); `make pull` çeker.
  Model çekilmemişse `make smoke` `model_not_pulled: <ad>; make pull` hatasıyla durur.

## İç registry (`REGISTRY_PREFIX`)

Tüm imaj adları `${REGISTRY_PREFIX}` ile başlar; Dockerfile'lardaki base imajlar da (`ARG REGISTRY_PREFIX`).
Boşsa imajlar kaynak registry'den (Docker Hub, ghcr.io, cgr.dev) çekilir. İç registry için sonunda `/`
ile verin: `REGISTRY_PREFIX=registry.ic/`. Kontrol:

```bash
docker compose config | grep 'image:'
```

## Sabitlenmiş imajlar

| Servis | İmaj |
|---|---|
| postgres | `pgvector/pgvector:0.8.1-pg16` |
| redis, langfuse-redis | `redis:7.4.6-alpine` |
| ollama (profil `ollama`) | `ollama/ollama:0.12.6` |
| litellm | `ghcr.io/berriai/litellm:v1.80.0-stable` |
| langfuse-web / langfuse-worker | `langfuse/langfuse:3.120.0` / `langfuse/langfuse-worker:3.120.0` |
| langfuse-postgres | `postgres:17.6-alpine` |
| langfuse-clickhouse | `clickhouse/clickhouse-server:25.8.2.29` |
| langfuse-minio | `cgr.dev/chainguard/minio@sha256:e70b2b1e74d79457f808710483bd726ff364529ca30736eaa15a6ab547d3a5a7` (DECISION-23: resmi `minio/minio` Docker Hub'da erişilemez; chainguard yalnızca `latest` yayınlar, digest ile pinli) |
| backend / tools base | `python:3.12.10-slim-bookworm`, `ghcr.io/astral-sh/uv:0.10.12` |
| frontend base | `node:20.19.5-alpine` |

## Yerelde Langfuse arayüzü

Langfuse ve LiteLLM dışarıya port yayınlamaz. Yerelde arayüze bakmak için depoya girmeyen bir
`compose.override.yaml` ile yalnızca `127.0.0.1`'e bağlayın (`127.0.0.1:3001:3000`).
