# PayCore LLM entegrasyonu

PayCore LLM (`C:\ai_paycore\paycoreLLM`, ayrı depo) FFCore'un ilk tüketicisi ve canlı test
yeridir: internetsiz sunucu, Ollama üzerinde CPU'da Qwen, Qdrant, Confluence/Jira korpusu. PayCore
müşteridir, ürün FFCore'dur (PLAN 2d). Bu belge iki deponun nasıl bağlandığını anlatır; PayCore'un
kendi kuralları PayCore deposunda `docs/paycore/KURALLAR.md`'dedir.

## Depo modeli

- **İki depo, tek yönlü bağımlılık:** `paycore_llm` → `ffcore`. FFCore hiçbir yerde
  `paycore_llm` import etmez. İki tarafta da test bunu kanıtlar: FFCore'da `test_00_package`,
  PayCore'da `test_00i_1b_ffcore_never_imports_paycore` (`ffcore` paketinin kaynağında AST
  taraması).
- **Geliştirmede path bağımlılığı:** PayCore `pyproject.toml`:

  ```toml
  [tool.uv.sources]
  ffcore = { path = "../ffcore/backend", editable = true }

  [dependency-groups]
  ffcore = ["ffcore"]
  ```

  İki depo kardeş klasördür: `C:\ai_paycore\ffcore` ve `C:\ai_paycore\paycoreLLM`.
  Kurulum: `uv sync --extra dev --group ffcore`. Dağıtım adı ve içe aktarılan paket `ffcore`,
  kökü `backend/` (00, KARARLAR "Backend paketi `ffcore`").
- **Neden bağımlılık grubu, ana bağımlılık değil:** PayCore imajı `.` bağlamıyla derlenir ve
  `../ffcore` bu bağlamda yoktur. Dockerfile `uv sync --frozen` ile kilidi yeniden çözmeden kurar
  ve `ffcore` grubunu atlar. `--frozen` olmadan uv path kaynağını okumaya çalışır ve
  "Distribution not found" ile düşer (PayCore `test_00i_1c_frozen_sync_without_ffcore`).
- **Sunucuda:** FFCore iç registry'den (`nexus.paycore.com`) wheel ve imaj olarak gelir. Bu yol
  FFCore bir wheel yayınladığında açılır (12); o güne kadar sunucu imajında `ffcore` yoktur.
- **Ortak kilit dosyası:** `uv.lock` grup dahil bütün projeyi tek kez çözer. FFCore'un pinleri
  PayCore'un ortak paketlerini de belirler. 00i'de yükselenler: fastapi 0.141.1 → 0.162.0,
  pydantic 2.13.5 → 2.14.1, pydantic-core 2.46.5 → 2.50.1, pydantic-settings 2.15.0 → 2.16.1,
  uvicorn 0.52.4 → 0.54.0, psycopg 3.3.5 → 3.3.6. FFCore'da bir pin değişince PayCore kilidi de
  yeniden çözülür ve PayCore testleri koşar.

## Uzantı noktaları (CONTRACTS C14)

PayCore'a özgü modüller PayCore deposunda kalır ve FFCore'a yalnızca entry point gruplarıyla
kayıt olur. FFCore kodu PayCore'a kopyalanmaz; PayCore kodu da FFCore'a kopyalanmaz, terfi eden
parça C14 üzerinden gelir.

| Grup | PayCore'da aday | Hangi paketle bağlanır |
|---|---|---|
| `ffcore.sources` | Confluence/Jira sürücüsü (`ingest/`) | 04a/16 |
| `ffcore.tools` | Jira öneri yorumu (`jira/`, yazma kapısı arkasında) | 05a/07 |
| `ffcore.guardrail_rules` | PRSIM kişi verisi kuralı (DECISION-14, ertelendi) | 08 |
| `ffcore.seeds` | uzman profilleri (`experts/*.yaml`) | 06/12 |

00i'de hiçbir grup kayıtlı değildir. Bu paket yalnızca bağlantıyı kurar; kayıtlar ilgili
paketlerde gelir. Kayıt imzaları C14'te donar (M2).

## Sürüm eşlemesi

| Değişken | Nerede | Anlamı |
|---|---|---|
| `FFCORE_VERSION` | FFCore compose (`deploy/docker-compose.yml`) | FFCore imaj etiketi |
| `PAYCORE_LLM_VERSION` | PayCore compose (`compose.yml`), Jenkins verir | PayCore imaj etiketi (`3.12.<n>-test`) |

İki değişken birbirinden bağımsızdır: PayCore imajında FFCore yoktur; 19'dan beri FFCore
servisleri PayCore yığınında FFCore'un kendi imajlarıyla (`FFCORE_VERSION`, `deploy/offline`
arşivi) çalışır. FFCore wheel'i sunucuya geldiğinde her
PayCore sürümü hangi `FFCORE_VERSION`'la derlendiğini yazar. Eşleme tablosu o gün PayCore
deposunda `docs/paycore/` altında tutulur.

## PayCore yığınında FFCore servisleri

- `compose.ffcore.yml` (PayCore deposu) **Langfuse v3** yığınını (profil `server`, 00i) ve 19'dan
  beri **FFCore yığınının tamamını** (profil `ffcore`) taşır: `ffcore-postgres` (pgvector),
  `ffcore-redis`, `ffcore-qdrant`, `ffcore-litellm`, `ffcore-backend`, `ffcore-worker`,
  `ffcore-mcp-search`, `ffcore-mcp-sql`, `ffcore-agent-worker`, `ffcore-agent-worker-bg`,
  `ffcore-frontend`, `ffcore-migrate`. PayCore'un `postgres` ve `qdrant` servisleri ad olarak
  çakıştığı için FFCore'unkiler `ffcore-*` adlıdır; diğerleri FFCore adını ağ takma adı olarak
  taşır (`backend`, `litellm`, `redis`, `mcp-search`, `mcp-sql`). FFCore PayCore'un Qdrant'ını ve
  Postgres'ini kullanmaz (K-M3S-0003). Portlar `127.0.0.1`'e bağlıdır.
- Ortam anahtarları FFCore `deploy/docker-compose.yml` `&app-env` ile birebir aynıdır (paycoreLLM
  `tests/test_19_compose.py` anahtar kümesini karşılaştırır); PayCore `POSTGRES_*`'a sahip
  olduğu için FFCore'un veritabanı, Redis ve LiteLLM secret'ları `FFCORE_*` adlıdır.
- Sunucu yığını:

  ```
  docker compose -f compose.yml -f compose.ffcore.yml -f compose.server.yml --profile server --profile ffcore up -d --no-build
  ```

  `compose.server.yml` FFCore dosyasına bağımlı değildir; eski iki dosyalı komutlar çalışır.
- Kurulum, korpus girişi ve S1 ölçümü: paycoreLLM `docs/paycore/m3-sunucu.md` (19).

## M3 sunucu paketi (19)

| Parça | Yer | Ne yapar |
|---|---|---|
| `python -m ffcore.cli ingest-raw` | FFCore | nötr raw-staging ağacını (dosya + `<dosya>.meta.json`) C6 `ingest_from_raw` ile içeri alır; PII regex maskesi her zaman, PRSIM yalnız `--accept-personnel-data`; manifest (`--manifest-out`) |
| `deploy/offline/` | FFCore | `images.txt` (registry digest + image id), `models.txt` (HF revision + SHA-256), `save.sh` / `load.sh` / `verify.sh` |
| `scripts/m3_preflight.py`, `scripts/m3_gate_check.py` | FFCore | sağlık kontrol listesi (değer basmaz); izlenen S1/rapor dosyası kapısı |
| `make eval EVAL_OUT=… EXCLUDE_SOURCES=… WARMUP=…` | FFCore | depo dışı rapor, kaynağa göre dışlama (n/N), ayrı ısınma |
| `scripts/ffcore_stage_raw.py` | paycoreLLM (C14) | PayCore raw → staging; kişi alanları taşınmaz |
| `scripts/ffcore_seed_paycore.py` | paycoreLLM | proje, ölçüm hesabı, kaynak başına bilgi tabanı, agent'lar |
| `scripts/ffcore_s1_dataset.py` | paycoreLLM | S1 → `make eval` biçimi, depo dışına |

## 00i ile PayCore'da kapanan açıklar

| Açık | Kaynak | Kanıt (PayCore testi) |
|---|---|---|
| API kimliksizdi; Open WebUI `local` anahtarıyla bağlanıyordu | v10 B3 | `test_00i_2_*`: `/health` dışında anahtar zorunlu, ham anahtar logda yok |
| `CHANGE_ME` varsayılanları, açık Qdrant/Ollama/Langfuse portları | v10 B4 | `test_00i_3_*`: gerçek `docker compose config`, her secret için negatif test |
| Embedding ve reranker event loop'u donduruyordu | v9 P9 | `test_00i_4`: 10 eşzamanlı soru altında `/health` < 1 sn (düzeltmeden önce 4,0 sn) |
| Kesilen chunk yalnızca log satırıydı | v9 P9 | `test_00i_4c_*`: chunk `flagged` + `embedding_truncated` |
| Langfuse yapılandırması vardı, gönderen kod yoktu | v10 P5 | `test_00i_8_*`: her cevap bir gözlem; başarısız gönderim `trace_delivery_failed` |
| Jira yazma kapısı | PayCore kuralı | `test_00i_7_*`: varsayılan kapalı, tek yazma yolu kapının arkasında |

## Açık noktalar

- **U1 (DRIFT-12):** Open WebUI son kullanıcı kimliğini imzalı iletmiyor. Audit aktörü
  `openwebui_service`'tir; kişi gibi gösterilmez. 03b gelince `resolve_actor()`'a bağlanır.
- **U16 (DRIFT-13):** PayCore'un kilitli Langfuse SDK'sı 4.15.1, OTel uç noktasına
  (`/api/public/otel/v1/traces`) gönderir. Sunucu 3.120.0 ile uçtan uca gönderim sunucuda
  doğrulanacak; testler yerel bellek içi exporter'la koşar.
- Bellek ölçümü (`docs/paycore/bellek.md`) ve S1 tabanı (`docs/paycore/s1-taban.md`) kullanıcının
  sunucu çıktısını bekliyor.
