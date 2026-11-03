# fix/19-dis-inceleme r2 inceleme raporu (delta, r1 DUZELT kapanışı, iki depo)

- **İstek:** K-19R-0015 (REVIEW-ISTEK, delta turu ve r1 probe'larının yeniden koşusu).
- **SHA'lar:**
  - ffcore `aacdd96b32a57b5d79fa2e07bbeb65fae3a4e671`: r1 b7a6d53 üstüne 3 commit, 7 dosya, +170/-13.
  - paycoreLLM `5663b7b8640710fe9d61ebca9715abe31aac635c`: r1 81098f4 üstüne 3 commit, 7 dosya, +109/-16.
- **state/ diff:** iki depoda 0.
- **Kod erişimi:**
  - ffcore için detached worktree `.worktrees/review-19r-r2`.
  - paycoreLLM için `git archive` kopyası `.worktrees/review-19r2-pc`. `.env`, `data/**` ve `eval/results/**` okunmadı.
- **Yığın:** review-19r (18300/13300). Backend aacdd96'dan derlendi. `04a-knowledge-core_model_cache:/models:ro` bağlandı.
- **Kararlar:** K-19R-0012, K-19R-0013 A.
- **Dış inceleme:** PayCore'un paralel raporu (`paycore-19-dis-inceleme-r2.md`) bu tur yazılırken yoktu.
- **İnceleyici ve tarih:** inceleyici, 2026-11-03.

## Karar: **ONAY**

BLOCKER 0, MAJOR 0, MINOR 1 (yeni, kalan), NOTE 2. r1'deki dört MAJOR'un dördü de kapandı; probe'lar yığında aynı koşullarla yeniden koşuldu.

## r1 MAJOR'larının kapanışı

### MAJOR-1 (155, kayıt öncesi hata görünmüyordu): kapandı

- **Kod:** `raw_ingest.py`. `report.unregistered` listesi `(source, relpath, code)` tutuyor.
  - Konsolda `failed_unregistered n` ve her biri için bir `unregistered:` satırı.
  - Manifestte `failed = statuses.failed + len(unregistered)` ve `failed_unregistered` listesi (`source`, `path`, `error_code`; içerik yok).
  - CLI `manifest["failed"]` > 0 olunca 1 ile çıkıyor.
  - Yer tutucu satır oluşturulmuyor (K-19R-0013 A).
- **Koşu D (r1 ile aynı ağaç: örnek ağaç artı `9001.md`, `updated_at_source: not-a-date`):**
  - `status: indexed 4, skipped 1`.
  - `failed_unregistered 1` ve `unregistered: confluence:DEMO confluence/DEMO/9001.md ValueError`.
  - **EXIT 1** (r1'de 0'dı).
  - DB'de 9001 satırı yok.
  - D, koşu B'den sonra koştu ve aynı dosyayı yeniden denedi; dosya hâlâ bozuk olduğu için yine sayıldı. "Sonraki koşu yeniden dener" davranışı bununla görülüyor.
- **Testler:**
  - `test_19r_r1m1_error_before_registration_counted`: manifestte kayıt var, `failed == 1`, `not-a-date` manifestte geçmiyor, yer tutucu satır yok.
  - `test_19r_r1m1_cli_exits_1_on_unregistered_failure`: exit 1.

### MAJOR-2 (155, eski sürüm aramadan düşüyordu): kapandı

- **Kod:** `_mark_failed` artık `Document.sha256 == sha256` koşuluyla, yani yalnız bu koşunun kaydettiği baytları taşıyan satırı işaretliyor. Kayıt rollback olduysa eski sürüm satırına dokunmuyor; dosya `unregistered`'a giriyor.
- **Koşu B (r1 ile aynı: 1002'nin baytı değişti ve `updated_at_source` bozuldu, artı 9001):**
  - `failed_unregistered 2` (1002 ve 9001), **EXIT 1**.
  - DB'de 1002 `indexed`, `version 1`, eski sha `9744ce45`, `error_code` yok. r1'de bu satır `failed` olmuştu.
  - Arama (`POST …/search`, "üye işyeri sözleşmesi fesih bildirim süresi otuz gün"): tek isabet `confluence/DEMO/1002.md`, rerank skoru 0,991. Eski sürüm aramada kaldı.
  - Koşu D sonrası arama aynı.
- **Test:** `test_19r_r1m2_new_version_error_keeps_old_version_searchable`. `(indexed, 1)` ve `error_code` yok kontrol ediliyor; arama isabeti analist rolüyle alınıyor.
- **Not:** Aynı sha ile yeniden deneme dalında satırın sha'sı eşleştiği için `_mark_failed` yine doğru satırı işaretliyor. r1 koşu C'deki davranış, yani `failed` olan bir belgenin yeniden denenip `indexed` olması, kod okumasına göre değişmedi. Bu turda o yolu yeniden koşmadım; B'de 1002 hiç `failed` olmadığı için bu yol tetiklenmedi. Entegrasyon testi `test_19r_155_*` aşağıdaki test-int koşusunda yer alıyor.

### MAJOR-3 (156, demo eşiği): kapandı

- `docs/demo.md:86` artık `Source accuracy (expected document cited) (≥ 16/20 on cpu)`; plan/13:44 ve plan/18 F1 ile aynı ölçü.
- `test_19r_156_demo_threshold_is_source_accuracy` bu satırı ve eski satırın yokluğunu sabitliyor.
- **NOTE-2 kapandı:** yedek satır aynı etiketi taşıyor (testli). `contains` ve `passed` satırlarına `_pct` ile yüzde eklendi; `cited[1] == 0` iken boş, bölme hatası yok.

### MAJOR-4 (R1, Jira özeti): kapandı

- `_heading()` = `_mentions(MENTION.sub(...))`; hem `jira_body`'deki başlıkta hem `_jira` meta `title`'ında kullanılıyor. Bu NOTE-4'ü de (meta title) kapatıyor.
- **Probe (`19r2-dis-probe-r1.log`, gerçek modül):**
  - Özet `Hata @ahmet.yilmaz ve [~mehmet.kaya] acti`.
  - Başlık `# DEMO-9 — Hata [USER] ve [USER] acti`.
  - Meta title `DEMO-9 Hata [USER] ve [USER] acti`.
- **Test:** `test_19r_r1_jira_summary_and_title_mentions_cleaned`. `@Component` özette aynen kalıyor.

## MINOR ve NOTE kapanışı (r1 numaralarıyla)

| r1 | Durum |
|---|---|
| MINOR-1 (yeniden denemede ACL/metadata) | PR notunda kısıt olarak var (`19-dis-inceleme.md:219`); davranış bilinçli. ✔ |
| MINOR-2 (yalnız backend genişler) | `test_19r_154_other_services_not_widened`: `x-app-env`, `migrate` ve `tools`'ta `backend` yok. ✔ |
| MINOR-3 (backend kendini hedefleyebilir) | Karar A, FOLLOWUP-159 ayrı dalda; PR notunda kısıt olarak var (`:221`). ✔ (bu PR için) |
| MINOR-4 (geri izleme / kısmi maske) | **Nokta için kapandı:** `@app.get("/x")`, `@pytest.mark.parametrize(...)`, `@ahmet.Yilmaz` ve `@ahmet.yilmaz@firma.com` artık bütün kalıyor. **`-` ve `_` için kalan:** aşağıda MINOR-r2-1. |
| MINOR-5 (`AT_TECHNICAL`) | `author`, `since`, `version`, `code`, `type`, `example`, `keyframes`, `font-face` eklendi; probe'da `@author ahmet`, `{@code foo}`, `@keyframes`, `@font-face` aynen kaldı. Runbook listesi kodla aynı. ✔ |
| MINOR-6 (`{code}`/`{noformat}`) | `FENCE` deseni bunları tanıyor. Probe: `{code:sql}` içindeki `--` ve `@ahmet.yilmaz` olduğu gibi kalıyor; `{noformat}` içindeki `--` imza sayılmıyor. ✔ |
| MINOR-7 (iki bütçe tanımı) | Eski test `ONE_SHOT` kullanıyor. `test_19r_mem_budget_tests_agree` iki testin aynı toplamı (`Birlikte`) bulduğunu sabitliyor. ✔ |
| NOTE-5 (`\|`, `*`, `_` önekleri) | Lookbehind'e eklendi; `\|@ahmet.yilmaz\|`, `*…*`, `_…_` → `[USER]`. Büyük harfli `@Ahmet` ve `@ahmet.Yilmaz` runbook'ta "bilinen sınır" olarak yazılı. ✔ |
| NOTE-6 (`x-api-key`, `proxy-authorization`) | `CREDENTIAL_KEYS`'e eklendi; casefold testi var (`Proxy-Authorization`). ✔ |
| NOTE-7 (96 GB etiketi) | `bellek.md:75` artık "kullanıcı kararı K-19R-0005; `free -g` teyidi kullanıcıda". `OS_SHARE_GB` sabiti testte duruyor (bilgi). ✔ |
| NOTE-8 (lock requires-dist) | Koordinatör FOLLOWUP-158'e ekledi (K-19R-0016). ✔ |
| NOTE-1, NOTE-3 | Bilgi notuydu; değişiklik gerekmiyordu. |

## R4 (96 GB)

- Bütçe tek tanım: iki test de `ONE_SHOT`'ı dışarıda bırakıyor ve 87,5 GB'ı aynı biçimde hesaplıyor.
- Eşik `(96 − 6) = 90 GB`. Senaryo testi `SERVER_RAM_GB` (varsayılan 96) kullanıyor; eski test bellek.md'yi okuyor.
- 96 GB satırı "karar" olarak etiketlendi.
- Testler bu koşuda geçti (`test_19_compose.py` 600 passed içinde).

## Yeni bulgular

- **MINOR-r2-1: `-` ve `_` sonrasında geri izleme hâlâ kısmi maske üretiyor.**
  - Konum: `ffcore_stage_raw.py:56-57`. Lookahead `(?![(/@]|\.?[A-Za-z0-9…])` noktayı kapsıyor ama `-` ve `_` ayırıcılarını kapsamıyor. En uzun eşleşme reddedilince regex ayırıcıdan önceki öneke geri çekiliyor.
  - Probe sonuçları:
    - `@ahmet-yilmaz@firma.com` → `[USER]-yilmaz@firma.com`
    - `@ahmet_yilmaz(` → `[USER]_yilmaz(`
    - `@app_get("/x")` → `[USER]_get("/x")`
    - `@ahmet.yilmaz-Ext` → `[USER]-Ext`
  - Sıradan metinde (`@ahmet_yilmaz` tek başına, ardından boşluk ya da noktalama) tam eşleşme var, sızıntı yok. Kısmi maske yalnız ayırıcının hemen ardından `(`, `/`, `@` ya da harf geldiğinde oluşuyor. Bu durumda kalan parça `yilmaz@firma.com` biçimindeyse FFCore'un e-posta maskesine düşüyor.
  - Testteki "no partial mask that leaves a name part behind" ifadesi yalnız noktalı biçim için doğru.
  - Öneri: lookahead'e `[-_]` eklenmeli (`(?![(/@]|[._-]?[A-Za-z0-9…])`) ya da gövde possessive/atomik yapılmalı; artı iki test satırı. Bu ONAY'ı bekletmez; FOLLOWUP ya da 08 tam 1b sırasında yapılabilir.
- **NOTE-r2-1:** `@ahmet.Yilmaz` artık bütün kalıyor; r1'de `[USER].Yilmaz` idi. Kısmi sızıntı yerine bütün login kalıyor. Bu, runbook'taki "bilinen sınır" cümlesiyle uyumlu ve kurumsal login'ler küçük harfli, ama koruma (a) açısından bu biçimde maske tamamen kalkmış oluyor. Bilgi; NER (08 tam) ile kapanır.
- **NOTE-r2-2:** Koşu B'de 1002 ve 9001'in hata nedeni aynı (`ValueError`). Konsol yalnız kodu gösteriyor, mesajı göstermiyor (tasarım gereği, fail-loud ve içerik yok). Operatörün nedeni bulması için log satırı ve dosya yolu yeterli.

## Güvenlik turu (delta)

| Konu | Durum |
|---|---|
| `.env`, secret, `data/**` diff'te | Yok. |
| Konsol ve manifestte içerik | Yalnız kaynak, yol ve sınıf adı; `not-a-date` değeri manifestte yok (test ve koşu çıktısı). |
| Log'da secret | NOTE-6 ile anahtar listesi genişledi; değer maskesi aynı. |
| Kişi verisi (staging) | MAJOR-4 kapandı (özet ve meta title). Kalan: MINOR-r2-1 (`-`/`_` kısmi) ve NOTE-r2-1 (büyük harf). |
| Arama görünürlüğü | Hatalı yeni sürüm, eski geçerli sürümü yayından düşürmüyor (MAJOR-2). |
| Ağ | Yeni egress yok. Probe'lar `OFFLINE=true` ile koştu. |

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| SHA doğrulama | iki depo, 3 ve 3 commit; state/ 0 | — |
| paycoreLLM tam pytest (5663b7b, ffcore aacdd96 bağlı, `--network none`) | **600 passed, 3 failed (bs4, master'dan beri), 2 skipped** | `19r2-dis-paycore-tests.log` |
| R1 probe (gerçek modül) | yukarıda | `19r2-dis-probe-r1.log` |
| Yığın up (aacdd96 derlemesi) | healthy | `19r2-dis-stack-up.log` |
| 154 embed probe | `EMBED_OK dense 1024`; eski değerle `egress_offline` | `19r2-dis-probe-embed.log` |
| ingest-raw A, B, C, D ve DB, arama | yukarıda (A exit 0, B exit 1, C exit 0, D exit 1) | `19r2-dis-ingest-{A,B,C,D}.log`, `19r2-dis-db-after-*.log`, `19r2-dis-search-after-{B,D}.log` |
| ffcore `make test` (llmaas, airgap) ve 04a/06a/19 test-int (llmaas, `RUN_QDRANT_TESTS=1`) | **952/952 ×2**; **186 passed, 3 skipped** (2 `RUN_MODEL_TESTS`, 1 root dosya modu; r1'dekiyle aynı atlamalar, +2 yeni test geçti) | `19r2-dis-ffcore-{unit-llmaas,unit-airgap,int-llmaas}.log` |

Probe betikleri: `19-dis-inceleme-r1-probe.py` (r1, aynen) ve `19-dis-inceleme-r2-search.py`. Parolalar ortamdan geldi, basılmadı.

**NOT_RUN:**
- ffcore tam `test-int` (işçinin 809) ve airgap test-int.
- `uv lock --check` (FOLLOWUP-158).
- PayCore yığını.
- Lint.

İşçinin 952/952 ve 809 sayılarını tam koşmadım; unit sayısı yukarıda.
