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

Bugün iki değişken birbirinden bağımsızdır: PayCore imajında FFCore yoktur, FFCore servisleri
de PayCore yığınında çalışmaz (Langfuse v3 dışında). FFCore wheel'i sunucuya geldiğinde her
PayCore sürümü hangi `FFCORE_VERSION`'la derlendiğini yazar. Eşleme tablosu o gün PayCore
deposunda `docs/paycore/` altında tutulur.

## PayCore yığınında FFCore servisleri

- `compose.ffcore.yml` (PayCore deposu) bugün yalnızca **Langfuse v3** yığınını taşır: web,
  worker, Postgres, ClickHouse, MinIO, Redis. Pinler FFCore 00'dakilerle aynıdır, imajlar iç
  aynadan çekilir, portlar `127.0.0.1`'e bağlıdır.
- Sunucu yığını üç dosyayla kalkar:

  ```
  docker compose -f compose.yml -f compose.ffcore.yml -f compose.server.yml --profile server up -d
  ```

  Kısayolu `make server`. `compose.server.yml` FFCore dosyasına bağımlı değildir; eski iki
  dosyalı operasyon komutları çalışmaya devam eder.
- Diğer FFCore servisleri kendi paketleriyle eklenir (01 LiteLLM, 04a arama, …). Yer tutucu
  servis yazılmaz.

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
