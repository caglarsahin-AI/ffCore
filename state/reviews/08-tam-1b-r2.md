# 08-tam-1b r2 inceleme (delta, r1 DEGISIKLIK kapanışı)

- **SHA:** 4567ed62f63f0f0d0276c88e909c0d16838bfaa8 (feat/08-tam-1b-ner; f6be9ae üstüne 21 commit, her bulgu test + kod ayrı commit; 29 dosya +1184/-109; merge-base main 7af41e5; `state/` 0)
- **İstek:** K-08T1B-0013 · ACK R-08T1B-0005 · Kararlar: KARARLAR "08 tam 1b r1 kararları"
- **İnceleyici worktree:** `.worktrees/review-08t1b-r2` (temiz; integration probe tek dosya mount, mount noktası silindi)
- **Yığın:** tam yığın review08t1b, 18290/13290, `--profile test --profile qdrant` (langfuse, mcp, ticket-desk dahil), dalın `.env.test`'i, `FAKE_EMBED=1`, `--pull never`, hepsi healthy.
- **Yöntem:** delta diff; her r1 bulgusu için ayrı statik denetim (kapandı mı, regresyon var mı, test f6be9ae'de düşer mi), her yeni bulgu ayrı doğrulayıcıyla; r1 probe'ları (E1-E6, HTTP yetki, açılış, 1a C17) bu SHA'da yeniden, yeni probe'lar (E7-E9, MAJOR-1/MINOR-4 HTTP, eksik ağırlıkla açılış); kapılar iki profilde.
- **Karar: ONAY** — BLOCKER 0, MAJOR 0, MINOR 4, NOTE 6

r1'in 4 MAJOR'ı ve 7 MINOR'ı karara göre kapandı; kapanışların hepsi ya probe ya da f6be9ae'de düşecek bir testle kanıtlı. Kalan 4 MINOR yeni ve dar; hiçbiri ham kişi adını ya da kimliği varsayılan yolda dışarı göndermiyor. Merge'ü engellemiyorlar; küçük bir commit ya da FOLLOWUP.

## r1 bulgularının kapanışı

| r1 | Durum | Kanıt |
|---|---|---|
| MAJOR-1 kayıtlı `default` egress'ten düşüyor | **KAPANDI** | `08t1b-r2-int-probe.log`: kayıtlı `default`'ta özel plaka deseni (`34 ABC 123`) + e-posta → yerleşik zincirle egress `<<PII_1>>`, `<<PII_2>>`; `input.pre` monitor, metin aynen (beklenen). Kod: kayıtlı `default-egress` önce, yoksa kayıtlı `default` (NER açıkken `PERSON` + `engine: ner` eklenmiş kopya), ikisi de yoksa yerleşik beşli (`builtin.py:46-66`, `service.py:90-97`); bütün çalışma zamanı yolları `resolve_pii`'den. Testler `test_08t_19_*` (19a f6be9ae'de düşer). |
| MAJOR-2 200.000 sınırı | **KAPANDI** | `HttpNer` metni ≤ 200.000 karakterlik, 2.000 örtüşmeli pencerelerle gönderiyor, offset kaydırıyor, örtüşen span'ları birleştiriyor; bir pencere düşerse bütün metin düşüyor (kısmi maske yok). İstek sınırı tek sabit (`NER_TEXT_MAX_CHARS`). `test_08t_20*`: 250.000 karakter, pencere sınırındaki ad maskeli. |
| MAJOR-3 başka filtreli kayıt | **KAPANDI** | Aynı bayt + farklı filtre → `text_filter_mismatch` ile ret, eski filtreyle işlenmiyor; manifest filtre başına dağılım (`raw_ingest.py:362-369`). Yeni sınır MINOR-r2-4. |
| MAJOR-4 ek adları | **KAPANDI** (meta kaynağı PRSIM olanlarda ve PRSIM dışında) | PRSIM eki `Ek <n>`, diğer eklerde ad filtreden geçiyor, `raw_path` aynı (`ingest.py:369-375`). Yola göre PRSIM sayılan dosya için açık: MINOR-r2-1. |
| MINOR-1 `on_error: allow` + NER kesintisi | **KAPANDI** | `08t1b-r2-probe-E.log` E2/E4: yerleşik ve kayıtlı `on_error: allow` egress'te NER düşünce `NerEgressUnavailable` (`ner_unavailable`, 503), sızıntı yok; E8: metin aşamaları `on_error`'a uymaya devam ediyor. |
| MINOR-2 taşıma hataları | **KAPANDI** | `EgressError` → `NerUnavailable` (`ner.py:251-264`); CLI 2 + kod (birim test). Bozuk 200 gövdesi kodsuz kalıyor: NOTE-2. |
| MINOR-3 eksik ağırlık açılışta | **KAPANDI** | `08t1b-r2-startup-probe.log`: model adı var, ağırlık yok → backend exit 3 `model_missing`; ad yok → exit 3 `ner_not_configured`; agent-worker ağırlıksız açılıyor (modeli yüklemez, doğru); airgap açılıyor. Varlık denetimi yükleme değil (`check_ner_weights`, `local_files_only`). |
| MINOR-4 `default-egress` anahtarı | **KAPANDI** | Probe: GET'teki yerleşik zincir aynen POST → 201; PII listesinde `default` ve `default-egress` `builtin: true`; test paneli `default-egress` → `builtin: true`. |
| MINOR-5 kısmi örtüşme | **KAPANDI** (yerleşik regex için) | E7: `Ayşe Kaya05321234567` → ad ve telefon ayrı yer tutucu, ad açık değil. Skor eşiği kenarı: MINOR-r2-2. |
| MINOR-6 yer tutucuya değen span | **KAPANDI** | E6: kapsayan span → `<<PII_2>> <<PII_1>> <<PII_3>>`, geri çevirme `Bay Ayşe Demir Hanım`; içine düşen span → yer tutucu bozulmuyor, geri çevirme `Ayşe Demir bilgi`. Desen C17 `PLACEHOLDER` ile aynı. |
| MINOR-7 docs | **KAPANDI** | docs/guardrail.md PayCore satırı DECISION-166'ya bağlı (açık, kullanıcı); `.env.example` modeli ölçüm dalının dolduracağını yazıyor. |
| NOTE-1 yol yorumları | **KAPANDI** | grep: eski `/internal/ner` kalmadı. |
| NOTE-9 HTTP yetki testi | **KAPANDI** | `test_08t_28_internal_ner_service_account_only`; probe: anonim 401, superadmin 403, servis 503 (model yok). |
| 1a C17 | **BOZULMADI** | r4 adversarial, r5, r5 kuyruk ve r6 probe çıktıları r1 turundakiyle bayt bayt aynı (`08t1b-r2-rerun-*.log`). |

## Yeni bulgular

### MINOR-r2-1 · `Ek <n>` kararı yalnız meta `source`'una bakıyor; staging dosyayı yolundan da PRSIM sayıyor

`iter_staged` kişi verisini `_is_prsim(source) or _prsim_path(rel)` ile belirliyor (`raw_staging.py:169`). `ingest_document` ise `Ek <n>` kararını yalnız `document.meta['source']`'tan yeniden hesaplıyor (`ingest.py:484-493`).

Örnek: `confluence/PRSIM-ARSIV/123/123.md`, meta `source: confluence:HR`. Kişi verisi sayılıyor, sayaçta ve müşteri verisi durağında öyle işleniyor. Ama eki `Ek 1` olmuyor, adı yalnız NER'den geçiyor. Alt çizgili ya da küçük harfli adda NER kaçırırsa ad silver `# Ek:` başlığına, breadcrumb'a, embedding'e ve `attachments.filename`'e gidiyor.

paycoreLLM stager kaynakla dizini tutarlı yazdığı için olasılık düşük. Ama iki karar ayrışabiliyor.

**Öneri:** `entry.personnel_data` ingest'e taşınsın (ya da aynı `_is_prsim or _prsim_path` kuralı). Test: yolu PRSIM, kaynağı değil → `Ek 1`.

### MINOR-r2-2 · NER span'ı skor eşiğinden önce kırpılıyor; sonradan düşen bir bulgu adın o kısmını maskesiz bırakıyor

`trim_names` (`engine.py:193`), NER span'ını `resolve_overlaps` ve `min_confidence`'dan **önce** bütün regex/özel desen bulgularına göre kırpıyor. Bulgu sonra eşik altında kalıp atılırsa, adın onun kapladığı kısmı hiçbir bulguya ait olmuyor.

Örnekler:
- `min_confidence: 0.85` ve 0.8 skorlu özel desen `Ayşe Kaya 12345`'i kaplarsa ad ve numara ham gidiyor.
- `min_confidence: 0.8` iken bağlamsız telefon (0.75) `Ayşe Kaya05321234567`'de adı da kırpıp düşüyor.

f6be9ae'de de aynıydı (regresyon değil), ama MINOR-5 kararı ("asla bütünüyle düşmez") bu yolda sağlanmıyor. Varsayılan politikada `min_confidence` bu değerleri düşürmüyor.

**Öneri:** kırpma, eşik ve çakışma çözümünden sonra kalan bulgulara göre yapılsın. Test: eşik altı özel desen + NER adı → ad maskeli.

### MINOR-r2-3 · `ner_unavailable` iç evaluate ucunda, api.md'de ve agentlar.md'de belgelenmemiş; NER docstring'leri hâlâ "on_error" diyor

İç evaluate ucu egress'te NER düşünce artık 503 `ner_unavailable` dönüyor. Docstring'i (`08.yaml` açıklaması) yalnız `placeholder_out_of_range`'ı `on_error` istisnası sayıyor.

docs/api.md:540-545 ve agentlar.md:95 koşu hata kodlarında `ner_unavailable` yok. Facade agent koşusunda istemciye koşu koduyla 502 gidiyor; guardrail.md:86 "503" diyor.

`ner.py:10-11` ve `NerUnavailable` docstring'i hâlâ "rule failure (`on_error`)" diyor.

**Öneri:** belgeler ve docstring düzeltilsin; facade yolundaki gerçek durum kodu yazılsın.

### MINOR-r2-4 · Manifest `text_filters`, kayıt olmadan düşen dosyaları `none` kovasına koyuyor

Kayıttan önce düşen dosya `report.files`'ta, `report.current`'ta değil. `manifest()` onu `text_filters: {"none": {...}}` altında sayıyor. Aynı kovada metadata'sında `text_filter` olmayan gerçek eski kayıtlar da var.

Manifesti okuyan "filtresiz yazılmış belge var" sonucuna varabilir; oysa satır yok ve dosya `failed_unregistered` altında zaten listeli.

**Öneri:** kayıtsız dosyalar ayrı kovaya (`unregistered`) ya da dağılım dışı kalsın; `none` yalnız gerçek filtresiz kayıt için.

## NOTE

1. Kayıtlı `default` silinirken, ondan türetilen `default-egress`'i kullanan kayıtlı zincir varsa 409 yok. Silme 204 dönüyor ve egress yerleşik beşliye düşüyor (özel desen kaybolur). Canlı türetme kararıyla uyumlu, silme audit'li; ama dolaylı bağımlılık ne korunuyor ne de açıkça yazılı. Kullanım denetimi genişletilsin ya da docs'a tek cümle eklensin.
2. `HttpNer` taşıma hatalarını sarıyor; bozuk 200 gövdesi (`KeyError`/`ValueError`) hâlâ kodsuz çıkıyor (CLI'da traceback). Fail-closed.
3. Taşınan yer tutucu etrafında kırpma `Bay`/`Hanım` gibi unvan ve ek parçalarını ayrı `PERSON` yer tutucusu yapıyor (E6). Geri çevirme doğru; yalnız fazla maske.
4. `PiiNerFilter.mask` docstring'i hâlâ "a name overlapping a regex finding is dropped" diyor.
5. M3'te `failed` kalmış PRSIM `pii_regex` kaydı, bayraksız bir `make reindex LAYER=silver` ile yine adlar maskesiz işleniyor. MAJOR-3 kararının kapsamı `pii_ner` koşusu; reindex kendi kaydının filtresini uygular ve bu tasarım gereği. M3 sınırının reindex'i de kapsayıp kapsamayacağı koordinatör kararı.
6. Monitor kipindeki kayıtlı egress kuralı NER düşünce `allow` (E5/E9). Monitor metni zaten hiç değiştirmediği için NER çalışsa da çalışmasa da çıktı aynı; MINOR-1 kararının enforce'a sınırlanması tutarlı. Bilgi.

## Güvenlik turu

- **Egress veri sınırı:**
  - Kayıtlı `default`'ın özel desenleri egress'te yine tokenize (MAJOR-1 kapandı, HTTP probe).
  - NER kesintisi `on_error`'dan bağımsız fail-loud (E2/E4).
  - Kısmi örtüşme ve yer tutucu kenarları kapalı (E6/E7).
  - Kalan dar kenar MINOR-r2-2.
- **Açılış:** ağırlık yoksa ya da model adı yoksa API açılmıyor; agent-worker ve airgap açılıyor (probe).
- **Ingest veri sınırı (PRSIM):**
  - Başka filtreli kayıt reddediliyor (MAJOR-3).
  - Ek adları maskeli ya da `Ek <n>` (MAJOR-4).
  - Uzun belge pencereleniyor (MAJOR-2).
  - Kalan: yol tabanlı PRSIM'de ek adı (MINOR-r2-1), reindex kapsamı (NOTE-5).
- **İç NER ucu:** HTTP yetki testi eklendi; probe aynı (401/403/servis).
- **1a C17:** bütün probe'lar bayt bayt aynı.
- **Veri:** yalnız sentetik değerler.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | 1598 passed | `state/evidence/08t1b-r2-r-unit-llmaas.log` |
| `make test` airgap | 1598 passed | `08t1b-r2-r-unit-airgap.log` |
| `make lint` | temiz (443 dosya) | `08t1b-r2-r-lint.log` |
| `test_08t_r3_url_scan.py` ×2 (yük altında) | 6/6, 6/6 | `08t1b-r2-r-urlscan.log` |
| `make test-int` llmaas (tam yığın) | 863 passed, 5 skipped | `08t1b-r2-r-int-llmaas.log` |
| `make test-int` airgap (tam yığın) | 861 passed, 7 skipped | `08t1b-r2-r-int-airgap.log` |
| Motor probe'u (r1 E1-E6 + E7-E9) | yukarıda | `08t1b-r2-probe-E.log`, `state/reviews/08-tam-1b-r2-probe.py` |
| HTTP probe'u (MAJOR-1, MINOR-4, NER yetki) | 3 passed, yukarıdaki değerler | `08t1b-r2-int-probe.log`, `state/reviews/08-tam-1b-r2-int-probe.py` |
| Açılış probe'u (ağırlık yok / ad yok / agent-worker / airgap) | exit 3 `model_missing`, exit 3 `ner_not_configured`, açılıyor, açılıyor | `08t1b-r2-startup-probe.log` |
| 1a C17 probe'ları | r1 ile bayt bayt aynı | `08t1b-r2-rerun-*.log` |
| Gerçek NER ölçümü, `-m models`, `--network none` | NOT_RUN: ağırlık yok (ENV-163); ölçüm dalı ONAY sonrası | — |

## Sonuç

ONAY (4567ed62f63f0f0d0276c88e909c0d16838bfaa8). MINOR-r2-1..4 merge öncesi küçük bir commit ya da FOLLOWUP (koordinatör kararı; MINOR-r2-1 ve MINOR-r2-2 kişi adı sınırına değdiği için küçük commit önerilir). NOTE-5 koordinatör kararı.

Merge sırası notu (09-1 r1 MINOR-9): 09-1'den önce merge edilirse, 09-1'in judge `EgressGuard`'ına `ner=HttpNer(settings)` 09-1 dalında eklenmeli. Önce ONAY alan merge edilir.
