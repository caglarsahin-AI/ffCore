# 08-tam-1b r1 inceleme (Türkçe NER + yerleşik v3 egress PERSON + pii_ner ingest + PRSIM guard)

- **SHA:** f6be9ae5c6b3b7be3d6fc8a6a02282b52d23877c (feat/08-tam-1b-ner; merge-base main 7af41e5, 13 commit, 41 dosya +1506/-95, `state/` 0, migration yok)
- **İstek:** K-08T1B-0008 · ACK R-08T1B-0001 · Sınıf [B]
- **İnceleyici worktree:** `.worktrees/review-08t1b-r1` (temiz; integration probe tek dosya mount, mount noktası silindi)
- **Yığın:** tam yığın review08t1b, 18290/13290, `--profile test --profile qdrant` (langfuse, mcp-sql, mcp-search, ticket-desk dahil), `--pull never`, hepsi healthy. Ortam notları:
  - Ana kopyadaki `.env.test` (main) `GUARDRAIL_EGRESS_NER` içermiyor; compose ilk açılışta `required variable GUARDRAIL_EGRESS_NER is missing a value` ile durdu. Bu, DECISION-166 deploy notunun doğrulaması. Yığın dalın kendi `.env.test`'iyle açıldı.
  - Ingest worker'ı `BAAI/bge-m3` ağırlığı olmadığı için yeniden başlama döngüsündeydi. Ağırlık yok (ENV-163); ffcore-09 yığını gibi `FAKE_EMBED=1` ile yeniden açıldı. Bu daldan değil.
- **Yöntem:** diff okuması; 5 boyutlu statik inceleme (iç NER ucu, yerleşik v3, fail-closed, PRSIM/ingest, docs/sözleşme), her bulgu ayrı bir doğrulayıcıyla çürütülmeye çalışıldı; kendi probe'larım (HTTP, motor, açılış); 1a C17 probe'ları yeniden; kapılar iki profilde.
- **Karar: DEGISIKLIK** — BLOCKER 0, MAJOR 4, MINOR 7, NOTE 9

Özet: İç NER ucu, açılış fail-loud'u, NER düşünce yerleşik politikanın bloklaması ve `engine: regex`'in NER'e dokunmaması iddia edildiği gibi çalışıyor. 1a'nın C17 davranışı bozulmadı. Dört MAJOR egress ya da ingest maskesinin bir yolda sessizce eksik kalmasıyla ilgili:

1. v3 projenin kayıtlı `default` PII politikasını egress'ten düşürüyor.
2. 200.000 karakteri aşan belge `pii_ner` ile hiç ingest edilemiyor.
3. `pii_ner` koşusu eski `pii_regex` kayıtlarını kendi etiketi altında yeniden yazıyor.
4. Ek dosya adları maskelenmiyor.

Hiçbiri yerleşik politikanın varsayılan yolunda ham kişi adı ya da kimlik numarası göndermiyor. Ama 1, 3 ve 4 PRSIM guard'ının ya da yerleşik egress'in verdiği sözü bir yolda tutmuyor.

## Odak maddeleri (K-08T1B-0008 1-10)

| # | Konu | Sonuç | Kanıt |
|---|---|---|---|
| 1 | İç NER ucu yetkisi, değer dönmez, SSRF | **TAMAM** | `08t1b-r1-int-probe.log`: anonim 401, superadmin üye 403 `service_account_required`, sahte jeton 401, servis jetonu (model yok) 503 `ner_not_configured`. Sahte NER ile 200 cevapta yalnız span/kategori/skor/kanıt; değer yok (`value-in-body: False`). 200.000 karakter 200, 200.001 karakter 422; boş/yanlış kategori ve fazladan alan (`url`) 422. Uç yalnız `/api/v1/internal/guardrails/ner`'de (kökte `/internal/guardrails/ner` 404). `HttpNer` hedefi yalnız `INTERNAL_API_URL` + sabit yol, `SafeOutboundClient` üzerinden; istekte URL alanı yok, SSRF yüzeyi eklenmedi. 06b-2 SSRF testleri test-int'te (aşağıda). |
| 2 | Yerleşik v3, açılış fail-loud, profil | **TAMAM, MAJOR-1 ve MINOR-3/4 ile** | `08t1b-r1-probe.log` E1: NER açıkken egress'te ad + TC + telefon + e-posta `<<PII_1..4>>`; kapalıyken (`false`) NER çağrısı 0, ad açık, regex kategorileri sürüyor. E3: metin aşamalarında (input.pre, output.pre, tool.pre/post) NER çağrısı 0. `08t1b-r1-startup-probe.log`: `EGRESS_ENABLED=true, EGRESS_NER=true, NER_MODEL=''` → backend exit 3, agent-worker exit 1, ikisi de `ner_not_configured`; `false/true` (airgap) ve `true/false` normal açılıyor. Kodda profil dalı yok. |
| 3 | NER düşünce fail-closed | **Yerleşikte TAMAM; MINOR-1, MINOR-2** | E2: yerleşik politika NER düşünce `block`, metin boş. E4: kayıtlı `on_error: block` → block. `on_error: allow` → MINOR-1. Ingest'te NER düşünce belge `failed`, maskesiz yazılmıyor (birim `test_08t_15_ner_down_fails_the_text_never_unmasked`). Taşıma hatası kodsuz → MINOR-2. |
| 4 | PRSIM guard | **Kısmen; MAJOR-3, MAJOR-4** | Ret DB'den önce: `check_sources` → `check_ner` → `_kb` sırası (kod + `test_08t_15e`: `_kb` çağrılırsa AssertionError). `--accept-personnel-data` çalışıyor ve uyarı logluyor (M3 kipi, `pii_regex`). paycoreLLM tarafı: `_needs_ner` `ffcore_seed_paycore.py`'de, `ffcore_stage_raw.py`'de yok; stager PRSIM'i M3 bayrağı olmadan hâlâ reddediyor (daha sıkı, sızıntı yok); `check_sources`'a eklenen `text_filter` yalnız anahtar kelime, varsayılan `None` davranışı aynı, 19r eşitlik testi bozulmaz → NOTE-6. |
| 5 | `pii_ner@1` ingest | **MAJOR-2, MAJOR-3, MAJOR-4, MINOR-5** | Gövde, `text_md` ve metadata NER'den geçiyor (birim 15/15b); manifest etiketi `pii_ner@1`. Kalan açıklar aşağıda. Gerçek belge ingest probe'u NOT_RUN: ağırlık yok, sahte NER yalnız birim düzeyde. |
| 6 | Sahte NER ile birim/entegrasyon; NOT_RUN açık mı | **TAMAM** | PR ölçüm (kabul 1/3/4), `-m models`, `--network none` kanıtı ve kazanan seçimini NOT_RUN/ertelenmiş olarak açık yazıyor. Ağırlık gelince: ayrı küçük dal; `NER_MODEL`/`NER_REVISION` + `make models` + `-m models` testleri + ölçüm tablosu + `id2label` gerçek etiket kontrolü (`ner_label_unknown`). Pencereleme iddiası yalnız gerçek modelle doğrulanır (NOTE-3). |
| 7 | FOLLOWUP-165 | **TAMAM (url_scan), NOTE-5** | `test_08t_r3_url_scan.py` artık CPU süresi (`process_time`) oranı (4x girdi, sınır 8, en iyi 3) + 20 sn asılı kalma koruması; yük altında iki kez 6/6 (`08t1b-r1-urlscan.log`). `test_08t_secrets_linear.py` hâlâ mutlak duvar saati (2 sn) → NOTE-5. |
| 8 | 1a C17 probe'ları | **BOZULMADI** | r4 adversarial ve r5 kuyruk probe'u 1a r6 kanıtıyla birebir aynı (`diff` boş; 0/200 kayıp, 0 açılma). r6 sınır probe'unda yalnız MINOR-r6-1 düzeltmesinin beklenen farkı: taşınan `<<PII_9999999>>`/`<<PII_9999990>>` artık yok sayılıyor, değerler `<<PII_1>>`'den. HTML istisnası aynı. `08t1b-r1-rerun-*.log`. |
| 9 | Docs, C4/C12 additive, OpenAPI | **MINOR-3, MINOR-7, NOTE** | C4 biçimi değişmedi (`engine: ner` kabulü additive; `engine_unsupported` reddi kalktı). C12'ye `GUARDRAIL_EGRESS_NER`, `NER_MODEL`, `NER_REVISION` eklendi. `08.yaml` yalnız ek. Uyuşmazlıklar aşağıda. |
| 10 | Tam yığın test-int iki profil | **YEŞİL** | llmaas 856 passed / 5 skipped, airgap 854 passed / 7 skipped; 06b-2 dış agent ve SSRF, 08_api, 08t C17 test-int dosyaları iki profilde yeşil |

## Bulgular

### MAJOR-1 · Yerleşik v3, projenin kayıtlı `default` PII politikasını egress'ten sessizce düşürüyor — CONFIRMED (kod okuması)

v2'de yerleşik egress kuralı `pii_policy_key="default"` idi. K-08lite-0006 A gereği `resolve_policy` bunu projenin kayıtlı `default` PII politikasına çözüyordu. Bir proje orada özel desen (müşteri no, plaka) ya da ek kategori tanımladıysa, bu değerler sağlayıcıya `<<PII_n>>` gidiyordu.

v3'te kural `default-egress`'e bakıyor (`builtin.py:63`). `resolve_pii("default-egress")` kayıtlı satır bulamayınca yerleşik regex beşlisini (+ `PERSON`) döndürüyor (`service.py:89-91`). Kayıtlı `default` artık yalnız monitor metin aşamalarını besliyor. Aynı proje bu sürümle güncellenince özel desenli değerler sağlayıcıya **ham** gidiyor. Ne uyarı ne migration ne de docs notu var.

Docs (guardrail.md) `false` varyantını "version 2's egress" diye anlatıyor; bu projeler için doğru değil. PR varsayım 8 yalnız `default-egress`'le geçersiz kılmayı yazıyor.

Etki: kayıtlı guardrail politikası olmayan, kayıtlı `default` PII politikası olan her proje. Yerleşik regex kimlikleri hâlâ maskeleniyor; kaybolan yalnız projenin eklediği desen ve kategoriler. Bu yüzden BLOCKER değil.

**Öneri (koordinatör kararı):**
- **A (önerilen):** kayıtlı `default-egress` yoksa ve kayıtlı `default` varsa egress PII'si kayıtlı `default`'tan türetilsin: onun kategorileri ve özel desenleri, `GUARDRAIL_EGRESS_NER=true` ise `PERSON` eklenmiş ve `engine: ner`. Test: kayıtlı `default`'ta özel desen → egress'te tokenize.
- **B:** egress yalnız yerleşik kalsın; docs ve degisiklikler.md'ye "kayıtlı `default` artık egress'i etkilemez; `default-egress` kaydedin" yazılsın ve yükseltme notu düşülsün. Daha basit ama sessiz davranış değişikliği kullanıcıya kalır.

### MAJOR-2 · `pii_ner` ingest 200.000 karakteri aşan belgeyi hiçbir zaman işleyemiyor, hata "kullanılamıyor" gibi görünüyor — CONFIRMED (kod + HTTP probe)

`ingest_document` dönüştürülmüş belgenin tamamını filtreye veriyor (`ingest.py:467-471`). `PiiNerFilter.mask`, `HttpNer.find` ile metni bölmeden tek istekte gönderiyor. `NerRequest.text` `max_length=200_000` olduğu için API 422 dönüyor (probe: 200.001 karakter → 422 `validation_error`). Sonuçta `NerUnavailable("internal ner failed: 422")` ve belge her yeniden denemede `failed`.

`pii_regex` ile aynı belge ingest ediliyordu; `TEXT_FILTER` varsayılanı artık `pii_ner`. Bu yüzden uzun PDF ya da DOCX (yaklaşık 80+ yoğun sayfa) için regresyon var. `check_ner` kısa metinle geçtiği için koşu başlıyor, belge belge düşüyor. Hata kodu boyutu değil kesintiyi söylüyor.

Fail-closed: sızıntı yok, ama belgeler bilgi tabanına giremiyor.

**Öneri:** `HttpNer` (ya da `PiiNerFilter`) metni sınırın altında, örtüşmeli pencerelerle göndersin ve offset'leri kaydırsın; örtüşmede tekrarlanan span'lar birleştirilsin. Alternatif olarak açık kod `ner_text_too_long` ile reddetsin (fail-loud ama işlevsiz). Test: 250.000 karakterlik metin, sahte HTTP NER, iki pencerenin sınırındaki ad maskeli.

### MAJOR-3 · `pii_ner` koşusu eski `pii_regex@1` kayıtlarını kendi etiketi altında işliyor; manifest yanlış, PRSIM yeniden denemesi adları maskesiz yazıyor — CONFIRMED (kod okuması)

`raw_ingest.ingest_tree`:
- (a) Aynı bayt, durum `indexed`/`skipped` olan dosya `unchanged` sayılıyor, ama `report.files`'a eklenmiş durumda. Manifest tek etiket yazıyor: `text_filter: pii_ner@1`, belgenin kendi `meta.text_filter` değeriyle karşılaştırmadan (`raw_ingest.py:96, 342-347`).
- (b) Aynı bayt, durum `failed`/`timeout`/`embedding` olan kayıt, `ingest_document(existed.id)` ile yeniden işleniyor. `_text_filter(document)` kayıtlı `pii_regex@1`'i kullanıyor (`raw_staging` "the record keeps its filter").

Senaryo: M3 kipinde (`--accept-personnel-data`, `pii_regex`) PRSIM ingest edilmiş, bazı kayıtlar `failed` kalmış. Operatör bayraksız yeniden koşuyor. PRSIM yalnız "adlar maskelenecek" önkoşuluyla kabul ediliyor (`check_sources`: `text_filter == "pii_ner"`). Ama (b) yolu silver, `.raw.md`, chunk ve embedding'i **adlar maskesiz** yazıyor ve manifest `pii_ner@1` diyor.

KARARLAR M3 kipinde maskesiz adı bilinen sınır olarak kabul ediyor. Fakat burada bayraksız bir koşu, kendi beyanının (manifest, CLI yardım metni "PRSIM is ingested with name masking") tersine iş yapıyor: fail-loud ilkesine aykırı.

**Öneri:** belge filtresi koşu filtresinden farklıysa ya açık kodla reddedilsin (`text_filter_mismatch`, sayılır, manifestte ayrı) ya da koşunun filtresiyle yeniden kaydedilsin (yeni sürüm). Manifest filtre başına belge/chunk sayısı yazsın. En azından PRSIM için (b) yolu `pii_regex` kaydını `pii_ner` koşusunda işlememeli. Test: M3 `failed` PRSIM kaydı + bayraksız koşu → ret ya da `pii_ner@1` ile yeniden yazım; manifest gerçek dağılımı veriyor.

### MAJOR-4 · Ek dosya adları maskelenmiyor; PRSIM ekindeki kişi adı silver'a, chunk breadcrumb'ına ve embedding'e giriyor — CONFIRMED (kod okuması)

`ingest_from_raw`, `attachments` anahtarını `mask_metadata`'dan önce `meta`'dan çıkarıyor (`ingest.py:686-688`). `_attachment_texts` yalnız ekin dönüştürülmüş metnini filtreliyor (`ingest.py:383`). Ad olduğu gibi şu yerlere gidiyor:
- `Attachment.filename`;
- kalite kapısının `title`'ı;
- silver'a `# Ek: <ad>` (`ingest.py:498`);
- `_chunks_for` breadcrumb'ına (`… › Ek: <ad>`), oradan embedding'e ve arama sonucuna.

paycoreLLM stager `--attachments` ile `meta["attachments"]` adlarını veriyor (`ffcore_stage_raw.py:372-383`). `Ahmet_Yilmaz_izin_formu.pdf` gibi bir ek adı bu yolla açık kalıyor.

`pii_regex` için de vardı (adda e-posta). Ama bu PR PRSIM'i "adlar maskelenir" önkoşuluyla kabul etmeye başlıyor, bu yüzden açık bu PR'ın vaadini deliyor.

**Öneri:** ek adı da filtreden geçsin; görünen ad, breadcrumb ve silver maskeli, `raw_path` bayt düzeyinde aynı. Alt çizgili adlarda NER zayıf kalabilir: ad bölümlerini boşluğa çevirip tarama, ya da PRSIM eklerinde adı `Ek <n>` ile değiştirme. Koordinatör seçimi; ikinci yol daha basit ve güvenli. Test: PRSIM eki `Ayşe_Demir_izin.pdf` → silver ve chunk'ta ad yok.

### MINOR-1 · Kayıtlı politika `on_error: allow` iken NER düşerse egress'te regex kimlikleri de açık gidiyor — CONFIRMED (probe E4)

`_ner_findings` kuralın `try` bloğunda. `NerUnavailable` (ve API sürecinde `ModelMissing`) genel `except`'e düşüyor; `allow` kuralı tümüyle atlıyor. `engine: ner`, `on_error: allow` kayıtlı egress politikasında NER kesintisi şunlar açık gidiyor: `Ayşe Demir`, `10000000146`, `0532 123 45 67`, `ayse@ornek.com` (probe E4).

docs "follows `on_error`" ve "nothing falls back to regex only" diyor; davranış belgeye uygun, varsayılanlar fail-closed. Ama 1b öncesinde regex kuralının çalışma zamanında düşmesi pratikte yoktu. Şimdi egress'teki checksum'lı kimlik maskesi bir HTTP bağımlılığına bağlandı. 1a, `PlaceholderOutOfRange` için aynı tehlikede `on_error`'dan bağımsız fail-loud seçmişti (C17 f′).

Seçenekler:
- **A (önerilen):** egress aşamasında NER hatası `on_error`'dan bağımsız fail-loud (yalnız egress; metin aşamalarında `on_error` sürer).
- **B:** docs'a "`engine: ner` + `allow`: NER kesintisinde regex kimlikleri de maskesiz çıkar" açıkça yazılsın; politika kaydında uyarı.
- **C:** NER kesintisinde regex bulguları uygulanıp olay `rule_error` ile kaydedilsin. Bu, kayıtlı bir kısmi geri düşüş; "sessiz geri düşüş yok" ilkesine yakın.

### MINOR-2 · `check_ner` ve `HttpNer` taşıma hatalarını sarmıyor; API kapalıyken CLI kodsuz traceback veriyor

`HttpNer.find` yalnız 200 dışı durum, model uyuşmazlığı ve kötü span için `NerUnavailable` atıyor. Bağlantı reddi, DNS ve zaman aşımı `EgressRequestFailed`/`EgressTimeoutError` olarak çıkıyor (`EgressError`). `check_ner` yalnız `(NerConfigError, NerUnavailable)` yakalıyor. Sonuç: `ingest-raw --sources jira:PRSIM` backend kapalıyken `prsim_requires_ner` + çıkış 2 yerine traceback.

Fail-closed: DB'den önce, bir şey yazılmıyor. Ama kayıtlı ve gerekçeli ret kuralı ihlal ediliyor. Motor yolunda (`on_error`) etkisi yok.

**Öneri:** `HttpNer.find` `EgressError`'ı `NerUnavailable`'a sarsın. Test: `ner_client().find` `EgressRequestFailed` atınca CLI 2 + kod.

### MINOR-3 · Eksik ağırlık açılışta değil çağrı başına; docs ve `.env.example` "start-up stops" diyor

KARARLAR "Egress kişi adı (NER)": "ağırlık yoksa **açılışta** fail-loud, çağrı başına değil". Kod `check_egress_ner` ile yalnız `NER_MODEL`/`NER_REVISION`'ın boş olmasını açılışta durduruyor (probe ile doğrulandı). Ağırlık eksikse:
- API açılıyor; `/readyz` `model_missing` (warmup) diyor, compose healthcheck `/healthz` olduğu için konteyner healthy.
- agent worker açılıyor.
- Her egress çağrısı `ModelMissing` → `on_error` (yerleşikte block).

docs/guardrail.md:263 "without them the API and the agent worker stop at start-up, `/readyz` shows `model_missing`" diyor; cümle kendiyle de çelişiyor. `.env.example` "without them the start-up stops" diyor.

**Öneri:** ya `main.py` lifespan'ında `GUARDRAIL_EGRESS_NER=true` iken `hf_path(NER_MODEL, NER_REVISION)` var mı diye bakılsın (yükleme değil, varlık), ya da KARARLAR/docs gerçek davranışa göre düzeltilsin (`/readyz` 503 + fail-closed çağrı). Birincisi kararla uyumlu.

### MINOR-4 · `default-egress` kullanılabilir PII anahtarı değil: yerleşik politika olduğu gibi kaydedilemiyor (422); test paneli `builtin: false`

`available_pii_keys` `{kayıtlılar, "default"}` döndürüyor (`service.py:80`). GET'te yerleşik zincir `pii_policy_key: default-egress` gösteriyor. Aynı zinciri `mode: enforce` ile `default` anahtarıyla POST eden yönetici 422 `pii_policy_not_found` alıyor; oysa `resolve_pii` o anahtarı çözüyor.

Kolay geçici çözüm, egress kuralını `default`'a çevirmek. `GUARDRAIL_EGRESS_NER=true` iken bu, kişi adı maskesini [C] kararı olmadan düşürür. Ayrıca test panelinde yerleşik egress PII'si `builtin: false` raporlanıyor (`api/guardrails.py:422`).

**Öneri:** `EGRESS_PII_KEY` `available_pii_keys`'e eklensin, PII listesinde yerleşik olarak gösterilsin (PR varsayım 8'in "istenirse additive" seçeneği). Test: GET'teki yerleşik spec POST ile 201.

### MINOR-5 · NER adı bir regex bulgusuyla kısmen örtüşürse bütünüyle atılıyor

`engine.py:192-194` ve `ingest_mask.py:81`: herhangi bir kesişimde NER span'ı düşüyor, kalan kısmı maskelenmiyor. Örnek: `Ayşe Kaya05321234567`. Telefon regex'i harfe karşı sınırsız; model adı rakama yapışık tek span verirse `Ayşe Kaya` açık kalır.

Gerçek modelle olasılığı düşük, `aggregation_strategy=simple` genelde sınırda keser. Doğrulanmadı (ağırlık yok).

**Öneri:** NER span'ı regex span'ı dışında kalan parçalara kırpılsın.

### MINOR-6 · NER span'ı mevcut bir `<<PII_n>>` yer tutucusuna değerse iç içe ya da kırık yer tutucu oluşuyor — CONFIRMED (probe E6, sahte NER)

Çok turlu konuşmada egress metni önceki turların yer tutucularını taşıyor.

- **Yer tutucuyu kapsayan span:** NER `Bay <<PII_1>> Hanım`'ı kişi sayarsa yeni değer `<<PII_2>>` olarak bu metni (içinde `<<PII_1>>`) saklıyor. Geri çevirmede kullanıcı `Bay <<PII_1>> Hanım aradı` görüyor, ad değil.
- **İçine düşen span:** span yer tutucunun içine düşerse (`PII_1` → `PERSON`) sağlayıcıya `<<<<PII_3>>>>` gidiyor; geri çevirme `<<PII_1>>` veriyor.

Sızıntı yok, fail-closed. Ama model gerçek bir Türkçe NER'de bağlamsal olarak "`<<PII_1>> Hanım`"ı kişi işaretleyebilir. Doğrulanmadı.

**Öneri:** `_pii_findings` (ve `pii_ner` filtresi) mevcut `<<PII_n>>` span'larıyla kesişen NER bulgularını atsın ya da kırpsın. Regex'in yer tutucuyu zaten eşlememesi gibi. Test: E6'nın iki yazımı.

### MINOR-7 · Docs, DECISION-166'yı kapanmış gibi yazıyor; `.env.example` model notu yanlış; PR C12 notu eksik

- docs/guardrail.md "airgap and the PayCore M3 server: `false` until the NER weights are on the server" diyor. Bu DECISION-166 A; BLOCKERS 166 hâlâ "açık (kullanıcı)". M3 sunucusu llmaas + egress açık, KARARLAR'a göre orada `false` [C] karar.
- `.env.example` "Filled with the measured model when package 08 full 1b closes" diyor; 1b ölçümsüz kapanıyor, kazanan ertelendi.
- PR §4 C12 satırı `GUARDRAIL_EGRESS_NER`'i saymıyor.

**Öneri:** docs'ta PayCore satırı "DECISION-166'ya göre (kullanıcı kararı)" olsun. `.env.example` "08 tam ölçüm dalında doldurulur" desin. PR notu düzeltilsin.

## NOTE

1. Kod yorumları (`ner.py:170` `HttpNer` docstring, `config.py`, `adapters.py`) uca `/internal/ner` diyor; gerçek yol `/api/v1/internal/guardrails/ner` (embed'in tersine `/api/v1` altında). Çalışan kod doğru yolu kullanıyor.
2. `local_ner()` kayıt sözlüğü kilitsiz: warmup iş parçacığı ile ilk istek aynı anda iki `LocalNer` kurup modeli iki kez yükleyebilir (bellek). Ayrıca `_recognize` tüm NER çağrılarını tek kilitle sıralıyor; yük altında egress gecikmesi. Ölçümle bakılmalı.
3. "Uzun metin pencerelere bölünür (`stride=128`)" iddiası tokenizer'ın `model_max_length`'ine bağlı; kartta yoksa pipeline bölmez. Ağırlıkla doğrulanmalı.
4. docs kanıt biçimini tam revizyonla gösteriyor; kod 7 karaktere kısaltıyor. OpenAPI'de iç NER ucunun 503'ü açıklamada var, yanıt listesinde yok; `/readyz` docs'u `ner_label_unknown`'ı saymıyor.
5. FOLLOWUP-165 yalnız `test_08t_r3_url_scan`'i çevirdi; `test_08t_secrets_linear.py` hâlâ 2 sn mutlak duvar saati (1a r6'da yük altında düşmüştü). `test_04a_9d` (bu daldan değil) mutlak 30 sn sınırıyla bu turda yük altında düştü (33,3 sn), tek başına 29/29 geçti. FOLLOWUP-162/165 demetine.
6. paycoreLLM `ffcore_stage_raw.py` PRSIM'i hâlâ yalnız M3 bayrağıyla stage ediyor ve `ffcore_compat.check_sources` `text_filter` almıyor. Bayraksız `pii_ner` PRSIM akışı için stager tarafında ayrı küçük değişiklik gerekecek. Bugün daha sıkı, sızıntı yok. `_needs_ner` `ffcore_seed_paycore.py:57`'de.
7. `--accept-personnel-data` tüm koşuyu `pii_regex`'e indiriyor (aynı koşudaki PRSIM dışı kaynaklar da adları maskesiz). Davranış main ile aynı ve PR varsayım 6'da yazılı; bayrak yalnız M3 için. Bilgi.
8. `pii_ner` her profilde `ingest-raw` varsayılanı: ağırlıksız airgap ya da sunucuda PRSIM dışı kaynaklar da `ner_unavailable` ile duruyor (yalnız M3 bayrağıyla geçer). docs/bilgi-tabani.md bunu yazıyor; guardrail.md'deki "`false` airgap için" notuyla birlikte okununca airgap'te NER gerekmediği izlenimi doğabilir. DECISION-166 A'nın "M3 etkilenmez" cümlesi yalnız bayrakla doğru.
9. Sıra ihlali: 9b49514'te iç uç testi kodla aynı commit'te (PR açıkça yazıyor). Testin içeriği yeterli: `6d` değer dönmediğini doğruluyor. HTTP yetki testi birimde yok (fonksiyon `actor=None` ile çağrılıyor); bu turdaki HTTP probe'u o boşluğu kapattı, işçi testine eklenmesi önerilir.

## Güvenlik turu

- **Yetki (iç NER ucu):** yalnız servis hesabı; üye ve superadmin 403, anonim ve sahte jeton 401. Cevapta değer yok. Gövde sınırı (200.000) ve sıkı şema (fazladan alan 422). Yeni dış hedef yok: `HttpNer` yalnız `INTERNAL_API_URL`'e gidiyor, `SafeOutboundClient` ve `ALLOWED_INTERNAL_HOSTS` üzerinden; 06b-2 `RESERVED_HOSTS`'a dokunulmadı.
- **Egress veri sınırı (llmaas):**
  - Yerleşik v3 NER açıkken ad + kimlikler tokenize; NER düşerse block.
  - Kayıtlı `default` PII'nin egress'ten düşmesi MAJOR-1.
  - `on_error: allow` kesintisinde kimliklerin de açılması MINOR-1.
  - İç içe yer tutucu MINOR-6.
- **Açılış:** `GUARDRAIL_EGRESS_NER` yoksa compose duruyor; `true` + model adı yoksa backend ve agent-worker duruyor. Ağırlık yokluğu açılışta değil (MINOR-3), fail-closed.
- **Ingest veri sınırı (PRSIM):**
  - Ret DB'den önce.
  - Gövde ve metadata adları maskeli.
  - Ek adı açık (MAJOR-4).
  - Eski `pii_regex` kaydının bayraksız koşuda yeniden yazımı ve yanlış manifest (MAJOR-3).
  - Uzun belge fail-closed ama işlevsiz (MAJOR-2).
- **Airgap:** egress kapalı, NER çağrısı yok, açılış normal (probe). Ingest-raw NER ister (NOTE-8).
- **1a C17:** r4/r5/r6 probe'ları aynı; sıfır tık ve akış kuyruğu bozulmadı.
- **Hasta ve kişi verisi:** probe'larda yalnız sentetik ad ve numaralar. Gerçek belge ve paycoreLLM `data/**` okunmadı.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | 1571 passed, 1 failed (`test_04a_9d`, mutlak 30 sn, yük altında 33,3 sn; bu daldan değil) | `state/evidence/08t1b-r1-unit-llmaas.log` |
| `test_04a_convert.py` tek başına | 29 passed (48,8 sn; yük kalkınca yeşil, ortam) | `08t1b-r1-rerun-04a.log` |
| `make test` airgap | 1572 passed | `08t1b-r1-unit-airgap.log` |
| `make lint` | temiz (ruff check + format, 433 dosya) | `08t1b-r1-lint.log` |
| `test_08t_r3_url_scan.py` ×2 (yük altında) | 6/6, 6/6 | `08t1b-r1-urlscan.log` |
| `make test-int` llmaas (tam yığın) | **856 passed, 5 skipped** (23 dk; Langfuse, mcp-*, ticket-desk testleri dahil yeşil: işçinin yalın yığın kırmızıları ortamdı) | `08t1b-r1-int-llmaas.log` |
| `make test-int` airgap (tam yığın) | **854 passed, 7 skipped** (18 dk; atlananlar profil ve ağırlık koşullu: 03b DNS, 04a ×2, 05a, 06b_direct ×2, 19 ×1) | `08t1b-r1-int-airgap.log` |
| İç NER ucu HTTP probe'u | 4 passed (yukarıdaki değerler) | `08t1b-r1-int-probe.log`, `state/reviews/08-tam-1b-r1-int-probe.py` |
| Motor probe'u (yerleşik v3, kesinti, metin aşamaları, yer tutucu) | yukarıda E1-E6 | `08t1b-r1-probe.log`, `state/reviews/08-tam-1b-r1-probe.py` |
| Açılış probe'u (backend, agent-worker × 3 ayar) | `true/true` model yok → exit 3/1 `ner_not_configured`; diğerleri açılıyor | `08t1b-r1-startup-probe.log` |
| 1a C17 probe'ları (r4 adv, r5, r5 kuyruk, r6) | aynı; tek fark MINOR-r6-1 düzeltmesi | `08t1b-r1-rerun-*.log` |
| Ölçüm, `-m models`, `--network none`, gerçek NER ile ingest | NOT_RUN: ağırlık yok (ENV-163, kullanıcıda) | — |
| Önyüz `check:api` | NOT_RUN: `08.yaml` önyüzce tüketilmiyor (PR), önyüz değişmedi | — |

## Sonuç

DEGISIKLIK. Merge öncesi düzeltilecekler: MAJOR-1 (koordinatör A/B kararı), MAJOR-2, MAJOR-3, MAJOR-4. MINOR-1 karar ister (önerim A); MINOR-2..7 aynı turda küçük commit'ler. NOTE'lar FOLLOWUP-162/165 demetine ya da ağırlık dalına. r2 delta turunda: bu dört MAJOR'ın testleri, E4/E6 probe'u, HTTP yetki testi ve hedefli test-int iki profil.
