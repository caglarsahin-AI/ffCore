# PayCore 00i + 19 dış inceleme raporu (paycoreLLM)

- **Kapsam:** paycoreLLM `81e3609..ca1b287`. İki merge: `8594bb0` (00i, FFCore entegrasyon tabanı) ve `ca1b287` (19, M3 sunucu paketi). 43 dosya, +4710/-775.
- **Yöntem:** statik okuma (`git diff`, `git show` ile SHA'dan). Yığın açılmadı, test koşulmadı.
- **İnceleyici:** PayCore oturumu (dış inceleme). Tarih: 2026-11-03.

## Karar: **DEĞİŞİKLİK İSTENİYOR**

BLOCKER 0, MAJOR 3 (R1, R2, R4), MINOR 4 (R3, R5, R6, R7), NOTE 1 (R8).

Her bulgu için: sorun, etki, önerilen düzeltme, kabul testi. Düzeltmeleri ayrı commit'lerde
yap ve commit mesajına bulgu numarasını (R1…R8) yaz. Bir bulguya katılmıyorsan düzeltme yerine
gerekçeni PR açıklamasına yaz.

---

## R1 (MAJOR) — ffcore_stage_raw: @-mention temizliği teknik içeriği bozuyor

**Dosya:** `scripts/ffcore_stage_raw.py:43` (`AT_MENTION`)

**Sorun:** Desen `@` + harf ile başlayan her diziyi `[USER]` yapıyor. Teknik sayfalardaki Java
anotasyonları (`@Component`, `@Order`, `@Transactional(REQUIRES_NEW)`) ve npm paket adları
(`@angular/core`) da kullanıcı adı sanılıp siliniyor.

**Etki:**
- OCR'daki "OLTP PostProcess İşlemleri 2026" sayfası anotasyonlarını kaybediyor.
- S1'in 2-4. soruları tam olarak bu anotasyonları soruyor.
- Sonuç: M3 ölçümünde FFCore, staging'in bozduğu metinle PayCore'a karşı ölçülmüş olur.

**Düzeltme:**
- Jira'nın kendi mention biçimi `[~user]` kalsın (`MENTION`); kesin bir işaret.
- Serbest `@ad` desenini kaldır ya da yalnızca şu koşulların hepsi tutarsa uygula:
  - fenced/inline kod bloğu dışında,
  - satır başında ya da boşluktan sonra,
  - büyük harfle başlayan CamelCase tanımlayıcı değil, ve ardından `(` gelmiyor.
- Kişi adları 08 full (NER) gelene kadar bilinen bir sınırlama olarak kalır; runbook zaten
  söylüyor. Yanlış temizlik, eksik temizlikten daha kötü.

**Kabul testi:**
- `@Component`, `@Transactional(REQUIRES_NEW)`, `@angular/core` ve kod bloğu içindeki `@Order(1)`
  metinde aynen kalır.
- `[~ahmet.yilmaz]` → `[USER]` olur.

## R2 (MAJOR) — Log maskeleme gizli olmayan alanları da maskeliyor

**Dosya:** `src/paycore_llm/config.py:355` (`_CREDENTIAL_NAME`), `redact`

**Sorun:** Anahtar adı `token|_key$|secret|…` desenine uyan her log alanı `***` oluyor. Bu,
`tokens`, `max_tokens`, `issue_key`, `doc_key` gibi sıradan alanları da kapsıyor.

**Etki:**
- `embedding_truncated tokens=18455` satırı `tokens=***` olarak yazılıyor; uyarının bildirmek
  için var olduğu sayı kayboluyor.
- `*_key` alan adlarıyla yazılan kayıt kimlikleri de maskelenir; iş izlenemez.

**Düzeltme:**
- Ad tabanlı maskelemeyi açık bir listeye ve **tam ad** eşleşmesine (casefold) çevir:
  - `authorization`, `password`, `secret`, `api_key`, `token`, `access_token`, `refresh_token`,
    `cookie`, `set-cookie`,
  - Settings'teki secret alanlarının adları.
- Alt dize eşleşmesi kullanma.
- Asıl koruma zaten değer tabanlı: bilinen secret değerleri ve `Bearer …` her string'de
  maskeleniyor. Ad tabanlı maskeleme yalnızca ek önlem.

**Kabul testi:**
- `log.warning("x", tokens=5, issue_key="PRSIM-1", api_key="abc", password="p")` şu çıktıyı
  verir: `tokens=5`, `issue_key=PRSIM-1`, `api_key=***`, `password=***`.
- Secret değeri serbest metin içinde geçerse yine `***` olur (mevcut test kalır).

## R3 (MINOR) — İmza temizliği içerik ve kod satırı siliyor

**Dosya:** `scripts/ffcore_stage_raw.py:44` (`SIGNATURE`, `_drop_signatures`)

**Sorun:** Sezgisel kural bütün gövdeye uygulanıyor, kod blokları dahil. Yalnızca `--` olan bir
satır (SQL yorum ayracı), tek başına bir "Teşekkürler" ya da "Regards" satırı, kendisini ve
altındaki 4 dolu satırı siliyor.

**Etki:**
- SQL kod bloğundaki satırlar ve toplantı notlarında "Teşekkürler"den sonra gelen aksiyon
  maddeleri sessizce kayboluyor.
- Yalnızca toplam sayı basılıyor; kaybın hangi belgede olduğu görünmüyor.

**Düzeltme:**
- Fenced kod bloklarını (```) atla.
- İmzayı yalnızca metnin **son** bloğunda ara (son ~8 satır).
- Silinen satır sayısını belge bazında meta'ya yaz (`signature_lines_dropped`).

**Kabul testi:**
- İçinde `--` satırı olan bir SQL kod bloğu aynen kalır.
- Ortasında "Teşekkürler" ve altında 3 madde olan bir sayfa değişmez.
- Son satırları "Saygılarımla / Ad Soyad / Unvan" olan metinden yalnızca o blok düşer.

## R4 (MAJOR) — Sunucu yığınının bellek tavanları 64 GB'ı aşıyor

**Dosya:** `compose.ffcore.yml` (`ffcore-backend mem_limit: 8g` ve diğerleri)

**Sorun:**
- `mem_limit` toplamı ≈ 88 GB: PayCore ~56 GB (Ollama 40g dahil), Langfuse v3 ~9,5 GB,
  FFCore ~22 GB. Sunucu 64 GB.
- bge-m3 ve reranker iki kez yükleniyor: `api` (8g) ve `ffcore-backend` (8g).
- paycoreLLM CLAUDE.md kuralı: "bellek bütçesi aşılmaz."
- `docs/paycore/bellek.md` bütün yeni satırları "ölçülmedi" diye işaretliyor.

**Etki:** M3 ölçümünde iki yığın ve 35B model aynı anda çalışırsa swap ya da OOM olur, süre
ölçümleri geçersizleşir. Ollama 36g sınırında aynı swap etkisi PayCore'da zaten görüldü.

**Düzeltme:**
- Runbook'a (`docs/paycore/m3-sunucu.md`) hangi yığınların **aynı anda** çalışacağını yaz.
  Önerim: M3 ölçümünde PayCore `api` ve `worker` durdurulsun, FFCore ölçülsün; sonra tersi.
- `bellek.md`'ye senaryo başına toplam tavan tablosu ekle: yalnızca PayCore / yalnızca FFCore /
  ikisi birlikte.
- İkisi birlikte gerekiyorsa iki yoldan biri:
  - embedding ve reranker tek yerde (FFCore) kalsın, PayCore `api` oradan çağırsın;
  - ya da tavanlar 64 GB içine indirilsin.

**Kabul testi:** Seçilen senaryoda `docker compose … config` çıktısındaki `mem_limit` toplamı
≤ 58 GB (OS için ~6 GB pay). Bunu doğrulayan bir test `tests/test_19_compose.py`'ye eklenir.

## R5 (MINOR) — Gold'da kesilme kontrolü iki kez çalışıyor

**Dosya:** `src/paycore_llm/ingest/sync.py:1506`, `src/paycore_llm/rag/embed.py:63`

**Sorun:** `flag_truncated`, `truncated()`'ı çağırıyor; hemen ardından `embed()` aynı metinler
için `truncated()`'ı bir daha çağırıyor. Uzun her parça iki kez tokenize ediliyor ve uyarısı iki
kez loglanıyor.

**Düzeltme:**
- `embed()` içindeki `truncated(texts)` çağrısını kaldır; kontrol yalnızca gold'da
  (`flag_truncated`) yapılsın.
- Sorgu tarafı (`retrieve.search`) sorgular kısa olduğu için kontrol etmeyebilir.
- Alternatif: `embed(texts, check_truncation=False)` parametresi.

**Kabul testi:** 9.000 token'lık bir parçayla bir gold batch'inde `embedding_truncated` tam bir
kez loglanır ve tokenizer bir kez çağrılır (mock sayacıyla).

## R6 (MINOR) — Langfuse sürüm tabanı kodla uyumsuz

**Dosya:** `pyproject.toml:16`

**Sorun:**
- `trace.py` Langfuse v3/v4 API'sini kullanıyor (`start_observation`, `span_exporter=`,
  `base_url=`).
- Aynı dosya `opentelemetry.sdk` ve `opentelemetry.exporter.otlp`'yi doğrudan import ediyor.
- pyproject ise hâlâ `langfuse>=2.50` diyor ve opentelemetry paketlerini bildirmiyor.

**Etki:** Lock dışı bir kurulum langfuse 2.x seçebilir (lock yenileme, pyproject'ten üretilen
offline wheel paketi). O zaman API ya import sırasında ya da `Langfuse(span_exporter=…)`
çağrısında açılmaz.

**Düzeltme:**
- `langfuse>=4.15,<5` (lock'taki sürüm).
- Doğrudan import edilen `opentelemetry-sdk` ve `opentelemetry-exporter-otlp-proto-http`
  açıkça bildirilsin.
- `uv lock` yenilenip lock değişikliği gözden geçirilsin.

**Kabul testi:** `uv lock --check` temiz geçer; `import paycore_llm.api` test konteynerinde
hatasız çalışır.

## R7 (MINOR) — FFCore kuralları PayCore'a kopyalanmış

**Dosya:** `scripts/ffcore_stage_raw.py:51-60` (`StagingError`, `_is_prsim`),
`scripts/ffcore_seed_paycore.py:57` (`is_prsim`)

**Sorun:**
- FFCore'un `ffcore.knowledge.raw_staging` hata kodları ve PRSIM önek kuralı burada yeniden
  yazılmış; `is_prsim` ikinci kez seed script'inde de var.
- paycoreLLM CLAUDE.md kural 3: "FFCore kodu buraya kopyalanmaz."
- Uyum testi yalnızca `../ffcore` bağlı test konteynerinde koşuyor.

**Etki:** FFCore kuralı değişince iki PayCore kopyası kayar; PRSIM verisi FFCore'un artık
uygulamadığı bir kurala göre staging'e alınabilir.

**Düzeltme** (en azından biri):
- (a) Bu script'ler FFCore backend imajında koşuyor (seed zaten öyle):
  `ffcore.knowledge.raw_staging`'ten import edilsin, kopya silinsin.
- (b) İmaj kısıtı yüzünden import mümkün değilse:
  - kural tek bir PayCore modülünde (`paycore_llm/ffcore_compat.py`) tutulsun, iki script
    oradan alsın;
  - kopyanın gerekçesi ve FFCore'daki kaynak yolu yorum olarak yazılsın;
  - uyum testi CI'da zorunlu koşsun.

**Kabul testi:** `is_prsim` tanımı depoda tek yerde; uyum testi `make test`'te atlanmadan koşar.

## R8 (NOTE) — Secret listesi her log satırında yeniden hesaplanıyor

**Dosya:** `src/paycore_llm/config.py:398` (`redact`), `:376` (`scrub`)

**Sorun:** `secret_values(get_settings())` her log olayında bütün Settings alanlarını tarayıp
sıralıyor. Oysa Settings süreç boyunca zaten önbellekte.

**Etki:** convert ve gold koşularında binlerce log satırının her biri boşuna bir tam alan
taraması yapıyor.

**Düzeltme:** `secret_values` sonucunu `get_settings` ile aynı ömürde önbelleğe al (ör.
`@lru_cache def _secrets() -> tuple[str, ...]`). Testlerde settings değişiyorsa önbellek
temizlensin.

**Kabul testi:** 1.000 log satırında `secret_values` bir kez çağrılır (sayaçla); maskeleme
davranış testleri değişmeden geçer.
