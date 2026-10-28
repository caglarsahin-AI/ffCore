# Geliştirme ortamı

Host'a yalnızca **Docker Desktop** (Windows) ya da Docker Engine + Compose v2 gerekir. Python, Node, `make`
host'a kurulmaz (KARARLAR "Geliştirme araçları Docker'da", "make de Docker'da"): araçlar `tools` ve
`frontend` konteynerlerinde koşar.

## İlk kurulum

Geliştirme ve CI (yalnızca açıkça sahte değerler; üretimde kullanılmaz):

```bash
cp .env.test .env
docker compose up -d          # depo kökünde; compose.yaml -> deploy/docker-compose.yml
docker compose run --rm tools make smoke
```

Gerçek kurulum: `cp .env.example .env`, ardından gizli değerleri kurulumu yapan kişi doldurur (ajanlar ve
scriptler `.env` yazmaz). Boş bırakılan zorunlu değişken varsa `docker compose` hangi değişkenin eksik
olduğunu yazarak durur.

## Günlük komutlar

| İş | Komut |
|---|---|
| Servisleri başlat / durdur | `docker compose up -d` / `docker compose down` |
| Loglar | `docker compose logs -f [servis]` |
| Python lint | `docker compose run --rm tools make lint` |
| Önyüz lint | `docker compose run --rm frontend npm run lint` |
| Unit + sözleşme testleri | `docker compose run --rm tools make test` |
| Entegrasyon testleri | `docker compose run --rm tools make test-int` |
| Duman testi | `docker compose run --rm tools make smoke` |
| Ollama modellerini çek | `docker compose run --rm tools make pull` |

`tools` konteyneri depo kökünü `/work` olarak bağlar (compose: `.:/work`) ve servislere compose ağından servis adıyla gider.
Docker soketi bağlanmaz; konteyner içinden `docker` komutu çalışmaz.

## Profiller

- `llmaas` (varsayılan): `COMPOSE_PROFILES` boş; Ollama servisi kalkmaz, `make smoke` Ollama adımını
  `skipped: ollama profile inactive` diye yazar.
- `airgap` + `INFERENCE_BACKEND=ollama`: `.env`'de `COMPOSE_PROFILES=ollama`. `OLLAMA_CONTEXT_LENGTH` ve
  `OLLAMA_MEM_LIMIT` zorunludur. Model listesi `deploy/ollama/models.airgap.txt` (yalnızca chat modeli; embedding süreç içi); `make pull` çeker.
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
