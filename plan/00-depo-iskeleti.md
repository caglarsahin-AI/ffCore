# 00. Depo iskeleti ve altyapı compose [FFCore Platform]

**Bağımlılık:** yok. **Süre:** 1 gün. **Dalga:** 1.

## Amaç

Monorepo iskeletini, geliştirme ortamını ve altyapı servislerini (Postgres+pgvector, Redis, Ollama, LiteLLM, Langfuse) tek `docker compose up` ile ayağa kaldırmak. Sonraki tüm paketler bunun üstüne gelir.

## Kapsam

1. PLAN.md bölüm 4'teki klasör yapısını oluştur. Her klasörde kısa README.
2. `backend/`: FastAPI "merhaba" uygulaması, `pyproject.toml` (Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, psycopg, redis, pytest, ruff), `Dockerfile`, `/healthz` endpoint'i. Alembic başlatılmış, boş ilk migration.
3. `frontend/`: `create-next-app` ile Next.js 15 + TypeScript + Tailwind + shadcn/ui; `messages/tr.json` ile i18n iskeleti (next-intl); `next-themes` kurulu, `styles/tokens.css` içinde açık ve koyu tema değişkenleri (başlangıç paleti), `/` sayfasında "FFCore" başlığı ve tema anahtarı; `Dockerfile`.
4. `deploy/docker-compose.yml`: servisler `postgres` (pgvector imajı), `redis`, `ollama`, `litellm`, `langfuse` (+ kendi Postgres ve ClickHouse'u, resmi compose'dan), `backend`, `frontend`. Sağlık kontrolleri, kalıcı volume'lar, tek `.env.example`.
5. `deploy/ollama/models.txt` profil bazlı (`models.llmaas.txt`: yalnızca embedding `bge-m3`; `models.airgap.txt`: Qwen 3.5 35B + `bge-m3`) ve `pull.sh` `DEPLOY_PROFILE`'a göre doğru listeyi çeker. Sunucuda modeller zaten varsa `OLLAMA_MODELS` volume'u mevcut dizine bağlanır.
6. `Makefile`: `make up`, `make down`, `make logs`, `make smoke` (tüm `/healthz`'leri, Ollama `/api/tags`'i ve `OLLAMA_CONTEXT_LENGTH` doğrulamasını kontrol eder; `/readyz` 04a ile gelir), `make lint`, `make test`.
7. `.gitignore`, `.editorconfig`, `ruff.toml`, `.pre-commit-config.yaml`. `.gitattributes` (`* text=auto eol=lf`, ikili dosyalar `binary`) main'de zaten var; değiştirme, `.editorconfig` `end_of_line = lf` ile uyumlu olsun.
7b. `.env.example` varsayılanı `DEPLOY_PROFILE=llmaas` (PLAN.md 2b); `airgap` için ayrı örnek blok yorum satırlarında.
8. `docs/gelistirme-ortami.md`: Windows'ta Docker Desktop ile çalıştırma, iç registry kullanımı için `REGISTRY_PREFIX` değişkeni (tüm imaj adları `${REGISTRY_PREFIX}` ile başlar; boşsa Docker Hub).

## Teslimatlar

- Çalışan compose; `make smoke` yeşil.
- `backend/app/main.py`, `frontend/app/page.tsx`, boş Alembic.
- `.env.example` içinde her değişkenin Türkçe açıklaması.

## Kabul kriterleri

- Temiz makinede `cp .env.example .env && make up && make smoke` 10 dakikada geçer (model indirme hariç).
- `REGISTRY_PREFIX=registry.ic/` verildiğinde compose'daki hiçbir imaj Docker Hub'a gitmez (`docker compose config` ile doğrulanır).
- `ruff check` ve `npm run lint` temiz.

## Teknik notlar

- pgvector için `pgvector/pgvector:pg16` imajı.
- Langfuse v3 compose'u ClickHouse, MinIO ve Redis ister; kendi Redis'imizi paylaşmayın, Langfuse'un kendi servisleri ayrı adla kalsın (çakışmayı önler).
- LiteLLM için bu pakette yalnızca `general_settings` içeren bir `config.yaml` şablonu (`model_list` yok; modeller LiteLLM DB'sinde, 01 C1) ve servis tanımı; içerik 01'de.
- Ollama CPU'da çalışır; `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=-1` (model bellekte kalsın), `OLLAMA_MAX_LOADED_MODELS` yüklü model sayısına göre (R1.6: Ollama'da yalnızca chat ve embedding modelleri; reranker 04'te süreç içi sentence-transformers'tır, Ollama'da değil; `airgap` cpu'da 2, `memory-extract` için ayrı model varsa 3).
- (PayCore düzeltmesi D6) **`OLLAMA_CONTEXT_LENGTH` zorunlu, compose'da sabit (PayCore: 32768):** Ollama'nın varsayılanı 4.096 token ve prompt'u **sessizce** kırpar; PayCore'da 12 parçalı ~7.000 token'lık RAG prompt'u ~2.050 token'a inmiş, seçilen kaynakların ~%70'i modele hiç ulaşmamıştı. OpenAI uyumlu uçtan (LiteLLM) `num_ctx` istek başına verilemez; sunucu ortam değişkeni olarak ayarlanmalı. Bağlam her yüklü model için baştan ayrılır; bellek bütçesine (12) yazılır. `make smoke` bu değişkenin set olduğunu ve `/api/show` ile modelin bağlam uzunluğunu doğrular.
- (PayCore düzeltmesi D6) **Isınma 04a'da:** `warmup` görevi ve `/readyz` uygulama kodu olduğu için 04a paketinde teslim edilir (reranker ve embedding yükleme orada); bu paket yalnızca `/healthz` verir ve compose'da `OLLAMA_KEEP_ALIVE=-1` ile modelin bellekte kalmasını sağlar. Ölçüm (PayCore): ilk yükleme ~85 sn (35B ~54, 4B ~13, bge-m3 ~14).
- (PayCore düzeltmesi D6) Compose'da Ollama ve ingest işçileri için `mem_limit` ölçülerek verilir; PayCore'da Ollama 36 GB sınırı koşu boyunca dolup swap'a düştü. Başlangıç değerleri 12'deki bellek bütçesi tablosundan.

## Kapsam dışı

Uygulama kodu, kimlik, veri modeli (03), LiteLLM yapılandırması (01), Langfuse bağlantısı (02).
