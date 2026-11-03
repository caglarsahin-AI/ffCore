# PayCore 19 dış inceleme raporu, ikinci tur (paycoreLLM)

- **Kapsam:** paycoreLLM `feat/19-dis-inceleme`, worktree `C:\ai_paycore\paycoreLLM-19r`.
  - İstenen SHA `81098f4`. Worktree'nin HEAD'i `5663b7b`; `81098f4` bunun atası.
  - İncelenen aralık `ca1b287..5663b7b`: R1–R8 düzeltme commit'leri, sonrasındaki `ebf50dd`, `5aed66f`, `5663b7b` ve FOLLOWUP-154 (`a051cc6`).
  - Bu aralık master'daki merge `530be09` ile aynı içerik.
- **Yöntem:** statik okuma, `make test` ve lint (konteynerde) ve `_scrub` için kendi deneme betiğim (konteynerde, depoya yazılmadı). Sunucuya bağlanılmadı; `.env`, `data/` ve `eval/results/` okunmadı.
- **Önceki rapor:** `paycore-19-dis-inceleme.md` (R1–R8).
- **İnceleyici:** PayCore oturumu. Tarih: 2026-11-03.

## Karar: **DEĞİŞİKLİK İSTENİYOR** (tek MAJOR: R9)

- R1–R8'in sekizinin de kabul testi geçti.
- Yeni bulgular: MAJOR 1 (R9), MINOR 2 (R10, R11).
- R9 kapanmadan PRSIM staging'i (`--accept-personnel-data`) koşulmamalı. R9, R1/R3 düzeltmesinin getirdiği bir kişi verisi açığı.

## Test durumu

| Komut | Sonuç |
|---|---|
| `pytest` (compose.test.yml, `--extra dev --group ffcore`) | 599 geçti, 2 atlandı, 4 kaldı |
| `ruff check`, `ruff format --check` | temiz |
| `mypy src` | 3 hata |

Kalan 4 test bu dalla ilgili değil:
- `test_data_dump`, `test_mhtml` ve `test_reconvert` testleri `ModuleNotFoundError: bs4` ile kalıyor. `beautifulsoup4` `ingest` extra'sında; CLAUDE.md'deki test komutu `--extra ingest` kurmuyor.
- `test_workers::test_a_slow_file_times_out…` zamanlamaya bağlı.
- Bu dosyaların hiçbirine dalda dokunulmadı.

mypy hataları da dalın dışında: `yaml`/`bs4` stub'ları ve `diagram.py:76`.

Ayrı bir iş olarak ele alınmalı: ya test komutuna `--extra ingest` eklenir ya da bu testler extra yokken atlanır.

---

## R1–R8 kapanışı

| No | Karar / kapsam | Değişiklik | Kabul testi | Durum |
|---|---|---|---|---|
| R1 | Desen kaldırılmadı, daraltıldı | `AT_MENTION` yalnız küçük harfli login biçimini maskeliyor. Arkasından `(`, `/`, `@` ya da harf gelen biçimler, `AT_TECHNICAL` sözcükleri, satır içi kod ve kod çitleri korunuyor. Jira özeti de bu kurala giriyor. | `test_19r_r1_*` (6 test) | **Geçti.** `@Component`, `@Transactional(...)`, `@angular/core`, `@app.get(` korunuyor; `@ahmet.yilmaz` → `[USER]`. Yan etkiler R9 ve R10'da. |
| R2 | | Log anahtarı maskesi tam ad listesi (`CREDENTIAL_KEYS`) artı Settings'teki SecretStr alan adları. Değer maskesi aynen duruyor. | `test_19r_r2_*` | **Geçti.** `tokens` ve `issue_key` görünüyor; serbest metindeki secret değeri hâlâ maskeleniyor. |
| R3 | | İmza yalnız son 8 dolu satırda ve çit dışında aranıyor. Her mesaj (açıklama, yorum) ayrı işleniyor. Düşen satır sayısı meta'ya `signature_lines_dropped` olarak yazılıyor. | `test_19r_r3_*` (5 test) | **Geçti.** Çit tanıma hatası R9'da. |
| R4 | Sunucu 96 GB (K-19R-0005), tavanlar değişmedi | `bellek.md`'ye senaryo tablosu eklendi; değerler compose'dan hesaplanıyor. Eşik 90 GB. | `test_19r_r4_*`, `test_19r_mem_budget_tests_agree` | **Geçti.** 65,5 / 74,5 / 87,5 GB ≤ 90. "Birlikte" senaryosunda pay 2,5 GB; runbook bu senaryoyu ölçüm dışı tutuyor, doğru. 96 GB'ın `free -g` ile teyidi kullanıcıda. |
| R5 | | `truncated()` artık `embed()` içinde değil. Çağıran tarafta: gold'da `flag_truncated` (sync.py:1508), legacy yolda `_index_doc` (sync.py:1186). | `test_19r_r5_truncation_checked_once` | **Geçti.** `embed()`'i çağıranların hepsine baktım; warmup ve sorgu yolu kısa metin, kontrol gerekmiyor. |
| R6 | Yalnız pyproject sınırları | `langfuse>=4.15,<5`, `opentelemetry-sdk>=1.44`, `opentelemetry-exporter-otlp-proto-http>=1.44` | `test_19r_r6_*` | **Geçti.** `uv.lock`'ta langfuse 4.15.1 ve otel 1.44.0 var; sınırlarla uyumlu. Lock yenileme ayrı dalda (FOLLOWUP-158). |
| R7 | | Staging, tek PayCore kopyası `paycore_llm/ffcore_compat.py`'yi kullanıyor (ingest imajında ffcore yok). Seed doğrudan `ffcore.knowledge.raw_staging`'i çağırıyor. Kopyanın FFCore'la eşitliği testle tutuluyor. | `test_19r_r7_*` | **Geçti.** Seed'de kalan bir hata R11'de. |
| R8 | | `_secrets()` `lru_cache` ile önbellekte; conftest her testte önbelleği temizliyor. | `test_19r_r8_secret_values_cached` | **Geçti.** |

---

## R9 (MAJOR): kod çiti tanıma hatası mesajın geri kalanında kişi verisini açık bırakıyor

**Dosya:** `scripts/ffcore_stage_raw.py:85` (`FENCE`), `:105` (`_fenced`), `:144` (`_mentions`)

**Sorun:** Çit durumu satır başındaki işaretle aç/kapa yapılıyor:
- Bir satırda çit hem açılıp hem kapanırsa (`{code}SELECT 1{code}`) yalnız açılış sayılıyor; mesajın geri kalanı "kod içi" kabul ediliyor.
- Kapanmamış bir çit için de aynısı oluyor.
- `_mentions` tek sayıdaki backtick'te de aynı şekilde davranıyor: satırın kalanı kod sayılıyor.

Kod içi sayılan satırlarda ne `@login` maskeleniyor ne de imza düşürülüyor. Hata kapalı değil açık yönde: şüphede kişi verisi kalıyor.

Konteynerde doğrulandı (`_scrub` çıktıları):

```
{code}SELECT 1{code}               -> aynen
lutfen @ahmet.yilmaz bakar misin   -> aynen (maskelenmedi)
Saygılarımla / Ahmet Yılmaz / PayCore -> aynen (imza düşmedi, dropped 0)

```\nx=1\nsonra @mehmet.kaya ...    -> @mehmet.kaya maskelenmedi (kapanmamış çit)
dosya `a.txt ve @ali.veli ekle     -> @ali.veli maskelenmedi (tek backtick)
```

**Etki:** Jira wiki'de tek satırlık `{code}…{code}` ve `{noformat}…{noformat}` sık görülür. PRSIM kayıtlarında, böyle bir satırdan sonraki tüm mention'lar ve imzadaki ad-soyad FFCore staging'ine geçer. Bu, plan/19 şart 1'i (kişi verisi) ve KARARLAR "PRSIM M3 ölçümüne girer" (a)'yı ihlal eder. R1 öncesinde bu açık yoktu (desen her yerde uygulanıyordu): açık, düzeltmeyle geldi.

**Düzeltme:**
1. **Çit yalnız kendi satırında sayılsın.**
   - Açılış: `^\s*(```|~~~)[\w+-]*\s*$` ya da `^\s*\{(code|noformat)(:[^}]*)?\}\s*$`.
   - Kapanış: `^\s*(```|~~~|\{code\}|\{noformat\})\s*$`.
   - Aynı satırda açılıp kapanan çit çit sayılmasın. O satırın içindeki kod kısmını korumak isteniyorsa satır içi kod gibi ele alınsın.
2. **Kapanmamış çit hiç açılmamış sayılsın.** `_fenced` sonda hâlâ "içerde" ise son açılıştan sonraki satırlar çit dışı işaretlensin. İlke: şüphede maskele.
3. **Satır içi kod yalnız çift backtick'te.** `_mentions` satırdaki backtick sayısı tekse son parçayı kod saymasın.
   - Jira'nın satır içi kodu `{{…}}`. `_jira_plain` bunu dönüştürmüyor; ister dönüştürülür ister `{{…}}` de satır içi kod sayılır. Hangisi seçildiyse runbook'a yazılsın.

**Kabul testi:** `test_19r_r9_*`. Yukarıdaki üç girdi:
- `@…` → `[USER]`;
- ilk girdide imza düşer (`signature_lines_dropped ≥ 3`);
- iki satıra ayrılmış `{code}` bloğu içindeki `@Inject`/`@foo` aynen kalır (R1/R3 testleri de geçmeye devam eder).

---

## R10 (MINOR): çit dışındaki küçük harfli teknik `@` sözcükleri `[USER]` oluyor

**Dosya:** `scripts/ffcore_stage_raw.py:56` (`AT_MENTION`), `:62` (`AT_TECHNICAL`)

**Sorun:** Konteynerde doğrulandı. Çit dışında şu satırlar `[USER]` oluyor:

```
@property, @dataclass, @pytest.fixture   -> [USER]
DECLARE @tran_id INT                     -> DECLARE [USER] INT
@echo off                                -> [USER] off
```

`AT_TECHNICAL` yalnız Javadoc/CSS sözcüklerini kapsıyor. Python dekoratörleri, T-SQL değişkenleri ve batch komutları bu listede yok.

**Etki:** R1'in amacı teknik içeriği korumaktı. Jira açıklamalarında çitsiz yapıştırılmış SQL ve Python sık görülür. Örneğin `DECLARE @tran_id` metinden çıkınca o kayıtla ilgili sorularda retrieval ve cevap bozulur. Kişi verisi açısından risk yok (fazla maskeleme), etkisi ölçüm kalitesinde.

**Düzeltme:** Kişi maskesi daraltılmadan iki kural:
1. Önünde SQL anahtar sözcüğü (`DECLARE`, `SET`, `SELECT`, `@x =`) olan `@ad` maskelenmesin.
2. Satırda tek başına duran `@ad` ya da `@a.b` (dekoratör biçimi) maskelenmesin. Mention tek başına satırda nadirdir; olursa da R9'daki "şüphede maskele" ilkesine karşı bir istisna olarak runbook'a yazılsın.

Alternatif: `AT_TECHNICAL`'a `property`, `staticmethod`, `classmethod`, `dataclass`, `abstractmethod`, `echo` eklenir. Ama bu bir liste ve eksik kalır; kural tercih edilmeli.

**Kabul testi:** `test_19r_r10_*`. Yukarıdaki dört satır aynen kalır; `lutfen @ahmet.yilmaz bak` → `[USER]` olmaya devam eder.

---

## R11 (MINOR): seed, FFCore'un tanımadığı bir red kodunu "sorun yok" sayıyor

**Dosya:** `scripts/ffcore_seed_paycore.py:57` (`_needs_ner`)

**Sorun:** `_needs_ner`, `raw_staging.check_sources`'tan gelen `StagingError`'ı yalnız `prsim_requires_ner` koduyla ayırt ediyor. Başka her kod `False` dönüyor ve plan devam ediyor.

**Etki:** Bugünkü tek diğer kod `sources_required`; boş liste önceden yakalandığı için bugün zararsız. Ama FFCore yarın yeni bir red kodu eklerse (örneğin bilinmeyen kaynak), seed bu reddi sessizce yutar ve bilgi tabanını yine kurar. R7'nin amacı "kural tek yerde" idi; red, FFCore'da olup PayCore'da kaybolmamalı (fail-loud).

**Düzeltme:** `prsim_requires_ner` dışındaki kodlarda `SeedError(exc.code + ": " + str(exc))` fırlatılsın.

**Kabul testi:** `test_19r_r11_seed_reraises_other_codes`. `raw_staging.check_sources` monkeypatch ile `StagingError("other", …)` fırlatır ve `plan()` `SeedError` yükseltir.

---

## Not (tek satır, düzeltme istemiyor)

- `AT_MENTION` en az 3 karakterli login'i yakalıyor: `@al` maskelenmiyor. PayCore login'leri `ad.soyad` biçiminde olduğu için kabul edilebilir; runbook'taki "bilinen sınır" listesine eklenebilir.
- `_scrub`'daki `blocks` sayısı (uyarı) tüm mesajı sayarken `dropped` yalnız son satırları sayıyor. Uyarı eşiği biraz gürültülü ama zararsız.

## Sunucu .env

Bu turda değişiklik yok. R4'teki 96 GB bir kullanıcı kararı; `.env`'e girmiyor. `SERVER_RAM_GB` yalnız testte okunuyor, varsayılanı 96.
