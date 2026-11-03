# fix/19-dis-inceleme r1 inceleme raporu (iki depo)

- **İstek:** K-19R-0010 (REVIEW-ISTEK). Statik inceleme, paycoreLLM test koşusu ve kısa yığın.
- **SHA'lar:**
  - ffcore `fix/19-ingest-followups` `b7a6d539079021c1fdb3b0f630762a5118a000a1`: b2e9c05 üstüne 3 commit, 8 dosya, +409/-101.
  - paycoreLLM `feat/19-dis-inceleme` `81098f49555aaf2b4710af0e54f68d86e36e5f74`: ca1b287 üstüne 9 commit, 19 dosya, +769/-146.
- **Kod erişimi:**
  - ffcore için detached worktree `.worktrees/review-19r-r1`.
  - paycoreLLM için `git archive` ile çıkarılmış salt okunur kopya `.worktrees/review-19r-pc`. `.env`, `data/**` ve `eval/results/**` okunmadı.
- **state/ diff:** iki depoda da 0.
- **Yığın:** review-19r (18300/13300, `--profile test --profile qdrant`). Backend imajı b7a6d53'ten derlendi. Backend'e `04a-knowledge-core_model_cache:/models:ro` geçici override ile bağlandı (scratchpad'de, depoya girmedi).
- **İnceleyici ve tarih:** inceleyici, 2026-11-03.
- **Bağımsızlık:** PayCore oturumunun paralel raporu (`state/reviews/paycore-19-dis-inceleme-r2.md`) bu rapor yazılırken henüz yoktu ve okunmadı. Karar bağımsızdır.

## Karar: **DEGISIKLIK**

| Sınıf | Adet |
|---|---|
| BLOCKER | 0 |
| MAJOR | 4 (ffcore 3, paycoreLLM 1) |
| MINOR | 7 |
| NOTE | 8 |

Dört MAJOR'un ortak özellikleri:
- Düzeltmeleri küçük; her biri birkaç satır artı bir test.
- Hiçbiri yeni bir mimari karar istemiyor.
- 154, R2, R4, R5, R6, R7 ve R8 temiz. 155, 156 ve R1'in ana kabul davranışı da doğru.

---

## ffcore (b7a6d53)

### (1) FOLLOWUP-154: doğru, yığında kanıtlandı

- **Çözülmüş compose farkı (benim koşum):**
  - `docker compose config` çıktılarını main ve PR için `.env.test` ile, `--profile test --profile qdrant` altında YAML olarak karşılaştırdım.
  - Değişen tek servis `backend`, değişen tek anahtar `ALLOWED_INTERNAL_HOSTS`: `litellm,langfuse-web,mcp-search,mcp-sql,ticket-desk` iken başına `backend,` eklendi.
  - Bağlam ve yol farkları dışında başka fark yok.
  - Üst düzeyde yalnız yeni `x-app-env` uzantı alanı var; bu alan servis üretmez.
  - `worker`, `agent-worker`, `mcp-*`, `migrate` ve `tools` değerleri aynı kaldı.
- **paycoreLLM tarafı (dummy env ile `--profile ffcore --profile server`):** 18 servisin yalnız `ffcore-backend`'i değişti, yalnız `ALLOWED_INTERNAL_HOSTS` anahtarında. Üst düzeyde yalnız `x-ffcore-app-env` eklendi.
- **154c probe'u (`19-dis-inceleme-r1-probe.py`, backend konteynerinde `OFFLINE=true`, gerçek `HttpEmbedClient`):**

  | Durum | Sonuç |
  |---|---|
  | Yeni değer | `EMBED_OK dense 1024` |
  | Eski değer (`backend`'siz) | `EgressDenied egress_offline` (B1'in aynısı) |

- **`ingest-raw` koşu A** (one-off backend konteyneri, `OFFLINE=true`, `data/samples/paycore-like/raw:/raw:ro`):
  - created 5, `status: indexed 4, skipped 1`.
  - gates `gate2:boilerplate 1`.
  - masked EMAIL 1 / TR_NATIONAL_ID 1 / TR_PHONE 1.
  - `prsim_requires_ner 1`.
  - manifest 5 belge, 5 parça, exit 0.
  - Sonuç işçinin tablosuyla aynı.

### (2) FOLLOWUP-155: yeniden deneme doğru; bir fail-loud açığı var

**Doğru olanlar:**
- Aynı sha ve DONE (`indexed`/`skipped`) ise atlanıyor.
- Aynı sha ama başka statüde ise `ingest.ingest_document(existed.id)` ile yeniden deneniyor; sürüm artmıyor.
- İstisnada `failed` yazılıyor ve `meta.error_code` olarak yalnız sınıf adı kaydediliyor (`str(exc)` hiçbir yere yazılmıyor).
- Başarıda `error_code` siliniyor.
- Konsoldaki status satırı ve manifest aynı `current`'tan dolduğu için eşit.

**Yığın kanıtı:**
- **Koşu C:** önceden `failed` olan 1002, aynı baytlarla `retried 1` aldı; DB'de `indexed`, `version 1`, error ve error_code boş.
- Kanıt dosyaları: `19r1-dis-ingest-C.log`, `19r1-dis-db-after-D.log`.

**MAJOR-1: kayıttan önce düşen bir hata konsolda ve manifestte görünmüyor, CLI 0 ile çıkıyor.**

- **Konum:** `backend/ffcore/knowledge/raw_ingest.py`:
  - :108 status satırı `current`'tan hesaplanıyor.
  - :80/:90 manifest `statuses` ve `failed` da `current`'tan.
  - :181-182 `_mark_failed` satır bulamayınca sessizce dönüyor.
  - :322 `report.statuses["failed"]` artık hiçbir çıktıda okunmuyor.
- **Koşu D (yığında):** örnek ağaç artı yeni bir `9001.md` dosyası; `updated_at_source: "not-a-date"` olduğu için `_source_date` commit'ten önce `ValueError` fırlatıyor. Çıktı:
  - `status: indexed 4, skipped 1`, `failed` yok.
  - `manifest: documents 6, chunks 5`.
  - **EXIT 0.**
  - Tek iz `ERROR ... ingest-raw failed path=confluence/DEMO/9001.md error=ValueError` log satırı.
- **Neden MAJOR:**
  - Fail-loud kuralı ve FOLLOWUP-155'in kendi amacı (temiz görünen koşunun arkasında başarısız belge kalmasın) bu yolda karşılanmıyor.
  - `_mark_failed` docstring'indeki "the count stays" ifadesi doğru değil: sayaç artıyor ama hiçbir çıktıya yansımıyor.
- **Öneri:** Satırı olmayan hatalar ayrı bir sayaçla (örneğin `failed_unregistered`) status satırına, manifestteki `failed` alanına ve çıkış koduna yansıtılmalı. Bunu kanıtlayan bir test eklenmeli; koşu D'nin aynısı yeterli.

**MAJOR-2: `new_version` yolunda kayıttan önce düşen hata, eski ve geçerli sürümü `failed` yapıp aramadan düşürüyor.**

- **Konum:** `raw_ingest.py:173-186`. `_mark_failed` satırı `document_id` ile değil `filename` ile buluyor.
- **Koşu B (yığında):** 1002'nin baytları değiştirildi ve `updated_at_source` bozuldu.
  - `register_upload` rollback oldu. DB satırı eski sha (`9744ce45`) ve `version 1` ile kaldı, ama `status failed` ve `error_code ValueError` yazıldı.
  - Arama `status = 'indexed'` ile süzüyor (`search.py:85,146`, `pgvector.py:82`; kod okuması). Bu yüzden önceki geçerli sürüm sessizce yayından çıkıyor.
  - Manifest yine `chunks 5` sayıyor.
  - Koşu B'nin konsolundaki `failed 1` aslında 1002'nin eski satırı. Yeni 9001'in hatası görünmüyor (MAJOR-1).
- **Neden MAJOR:** Bozuk bir meta, daha önce indekslenmiş doğru içeriği kullanıcıya haber vermeden aramadan kaldırıyor. Bunu durum-gerçeklik tutarsızlığı olarak sınıflıyorum.
- **Öneri:** `_mark_failed` yalnız bu koşunun işlediği satırı işaretlemeli:
  - aynı sha dalında `existed.id`;
  - yeni sürüm commit edildikten sonra `document_id`.
  - Kayıttan önce düşen hata eski satıra dokunmamalı; MAJOR-1'deki sayaçla görünür olmalı.
  - Bir test eklenmeli.

- **MINOR-1:** Yeniden deneme dalı (`raw_ingest.py:297-309`) `--acl` ve metadata değişikliklerini uygulamıyor. Belge DB'deki eski ACL ile `indexed` oluyor ve konsol bunu söylemiyor. Bu bir güvenlik gevşemesi değil, çünkü eski ACL operatörün önceki tercihi. Yine de PR notuna varsayım olarak yazılmalı.
- **NOTE-1:** Ara statü testleri yalnız `gated` durumunu kapsıyor; kod yolu aynı.
  - Eşzamanlı iki koşu çift iş yapar ama veri bozmaz (`with_for_update`). Bunu koşmadım.
  - `ingest_document` içinde `document.error`'a metin yazan iki yol bu PR'dan önce de vardı (`ingest.py:419-422`, `:566`). İçerik taşıyıp taşımadıkları doğrulanmadı.

### (3) FOLLOWUP-156: rapor kodu doğru; demo tablosunun eşik satırı yanlış ölçüye bağlanmış

- **Rapor kodu:**
  - `scripts/eval_report.py:161` → `Source accuracy (expected document cited)` yalnız `cites_source` sayıyor.
  - `:177` → `contains` ayrı satırda.
  - `:178` → tam geçiş (`passed`) ayrı satırda.
  - Testler (`test_19_eval_out.py:142-156`, `test_13b_eval_report.py:117`) üç ölçünün birbirinden ayrıştığını gösteriyor.
- **`m3_gate_check`:** diff'te yok. Yalnız dosya yolu desenlerine bakıyor, rapor etiketlerini parse etmiyor. Etkilenmedi.

**MAJOR-3: `docs/demo.md:86` eşik satırı brief'teki "kaynak doğruluğu" ölçüsünü tam geçişe bağlıyor.**

- **Değişiklik:** Satır `Document questions, right source (≥ 16/20 on cpu)` iken `Document questions passed: answer text and source (≥ 16/20 on cpu)` oldu.
- **Çelişki:**
  - Tablonun başlığı "Measure (brief 13)".
  - `plan/13-ornek-veri-demo.md:44` bu ölçüyü "Belge soruları kaynak doğruluğu (20) ≥ 16/20" olarak tanımlıyor; plan/18 F1 de aynı.
  - K-19R-0002 156 için yalnız "kaynak isabeti yalnız cites_source … etiketler güncellenir" diyor; ölçünün değişmesi yok.
- **Etkisi:** Eşik artık `eval_report.py:178`'deki tam geçiş satırından okunacak. B3/ARCH-13'ün çözdüğü karışıklık, etiket düzeyinde yeniden kuruluyor. Fark büyük: 18-kosu-2'de cites_source 19/20 iken tam geçiş 0/20.
- **Öneri:** Satır `Source accuracy (expected document cited) (≥ 16/20 on cpu)` olmalı. Eşiğin tam geçiş olması isteniyorsa bu ayrı bir DECISION-.
- **NOTE-2:** `eval_report.py:176` yedek satırı ("no document question") yeni etiketi kullanmıyor. `contains` ve `passed` satırlarında yüzde yok. Yalnız biçim.

### ffcore'daki diğer konular

- **MINOR-2:** `test_19r_154_internal_hosts.py` yalnız backend değerini kontrol ediyor. `backend,` bir gün `x-app-env`'e taşınırsa `migrate` ve `tools` da genişler ama test yeşil kalır. paycoreLLM'deki eşdeğer testte bu kontrol var (`'backend' not in ffcore-migrate`). ffcore testine de `migrate`/`tools` için bir assert eklenmeli.
- **MINOR-3 (güvenlik, ihtiyaçtan geniş):** `ALLOWED_INTERNAL_HOSTS` süreç genelinde geçerli.
  - Backend sürecinde `backend` artık iç host sayılıyor. Bu yüzden şu hedefler artık egress denetiminden geçiyor:
    - MCP araç kaydı (`mcp_tools.check_endpoint`, `forward_user` dahil);
    - discovery ve test çağrısı;
    - sağlayıcı bağlantı testi;
    - webhook testi.
  - Bu yollar backend'in kendi API'sini hedef alabilir.
  - Hepsi `require_role("admin", write=True)` istiyor (verify ajanı `api/tools.py`'de doğruladı). `SafeOutboundClient` service token eklemiyor. `agent-worker`'ın listesinde `backend` zaten vardı. Pratik risk düşük.
  - K-06b2-0008'in "platform servisi dış hedef olamaz" kuralı (`RESERVED_HOSTS`) yalnız dış agent'larda uygulanıyor.
  - Seçenekler (koordinatöre):
    - **A (önerilen):** araç, sağlayıcı ve webhook hedeflerinde `RESERVED_HOSTS` ya da `INTERNAL_API_URL` host'u açıkça reddedilsin; additive ve testli. Bu PR'da ya da bir FOLLOWUP'ta.
    - **B:** PR notuna kısıt olarak yazılsın ve bir FOLLOWUP açılsın.
    - **C:** olduğu gibi kalsın.
- **NOTE-3:** `backend,${ALLOWED_INTERNAL_HOSTS:-}` boş değişkende `backend,` üretiyor; `_split_commas` boş öğeyi atıyor. Doğru.

---

## paycoreLLM (81098f4)

### Test koşusu (benim)

**Ortam:**
- `paycore-llm-test:local` imajı, `paycore-m3-test_paycore_test_venv` volume'u (salt okunur), `--network none`.
- Arşiv `/app:ro`'ya, ffcore b7a6d53 `backend` ve `deploy` dizinleri `/ffcore/...:ro`'ya bağlandı.

**Sonuç:** **586 passed, 3 failed, 2 skipped** (137 s, `19r1-dis-paycore-tests.log`). Bu sonuç işçinin kanıtıyla aynı.
- **3 failed:** üçü de `No module named 'bs4'` hatası. Aynı üç testi master ca1b287'de koştum, aynı üçü düştü (`19r1-dis-paycore-master-bs4.log`). Bu PR'dan önce de vardı (ENV-138). İşçinin "master'da doğrulanmadı" notu artık doğrulandı.
- **2 skipped:** `fitz` yok; `build_scenario2_eval.py` seti üretilmemiş. İkisi de önceden vardı.
- `test_19r_ffcore_rule.py` atlanmadan koştu (skip listesinde yok).
- **Uyarı:** venv volume'u paycore-m3 projesinden. Kurulu paketlerin bu SHA'nın lock'uyla birebir aynı olduğunu doğrulamadım. `test_19r_r6_*` geçtiği için langfuse ve otel importları çalışıyor.

### (4) R1 dar desen: kabul örnekleri doğru; Jira özetinde gerileme var

**Kabul örnekleri (`19r1-dis-probe-r1.log`, gerçek `_mentions` ile):**

| Girdi | Çıktı |
|---|---|
| `@Component`, `@Transactional(REQUIRES_NEW)`, `@angular/core`, `ad@firma.com` | aynen kaldı |
| `Sonra @ahmet.yilmaz.` | `Sonra [USER].` |
| `@çağlar.şahin` | `[USER]` |
| `[~mehmet.kaya]` | `[USER]` |

- Kod bloğundaki `@Order(1)` testte (`test_19r_stage_raw.py:33`).
- `AT_TECHNICAL` tek sabit; runbook'ta (`m3-sunucu.md:30-36`) anılıyor.
- KARARLAR (a) satırı (ffcore `KARARLAR.md:170`) duruyor, yani kaldırılmadı. Daraltma K-19R-0007/0008'de, runbook'ta, betik docstring'inde ve PR notunda kayıtlı.

**MAJOR-4: Jira özetindeki `@login` artık `[USER]` olmuyor.**

- **Konum:** `scripts/ffcore_stage_raw.py:168-169, 177-178, 188`.
- **Fark:**
  - Bazda (ca1b287:147) tüm gövde, `# KEY — summary` başlığı dahil, `_scrub`'dan geçiyordu.
  - Şimdi `_scrub` yalnız açıklamaya ve yorumlara uygulanıyor; başlığa yalnız `MENTION` (`[~user]`) uygulanıyor.
- **Probe:** özet `Hata @ahmet.yilmaz tarafindan acildi`.
  - Çıktı: `# DEMO-9 — Hata @ahmet.yilmaz tarafindan acildi`, aynı login açıklamada `[USER]`.
- **Neden MAJOR:**
  - Bu, kullanıcının D kararı olan koruma (a)'da ("`@ad` izleri temizlenir") bir gerileme.
  - Kontrol maddesi (4)'teki `@ahmet.yilmaz → [USER]` kabulü özette sağlanmıyor.
  - :177-178'deki "header lines carry no person data" yorumu özet için doğru değil.
- **Öneri:** Özete `_mentions` uygulanmalı ve bir test eklenmeli.
- Meta `title` alanı (`{key} {summary}`, :210) bazda da maskesizdi; bu kısım önceden vardı → NOTE-4.

**MINOR'lar:**
- **MINOR-4:** Geri izleme `(` ve `/` korumasını deliyor. Kod dışında:
  - `@app.get("/x")` → `[USER].get("/x")`;
  - `@pytest.mark.parametrize("a")` → `[USER].parametrize("a")`.
  - Kişi tarafında kısmi sızıntı: `@ahmet.Yilmaz` → `[USER].Yilmaz`, `@ahmet.yilmaz@firma.com` → `[USER].yilmaz@firma.com`.
  - Runbook'taki "`(`/`/` ile devam eden `@` dokunulmaz" cümlesi noktalı adlarda doğru değil.
  - Öneri: lookahead'e `.` eklenmeli (`(?![\w(/@.])`) ya da atomik/possessive gövde kullanılmalı. Bir test eklenmeli.
- **MINOR-5:** `AT_TECHNICAL` yaygın kelimeleri kapsamıyor: `@author`, `@since`, `@version`, `{@code}` (önünde `{` olduğu için `{[USER] foo}`), `@keyframes`, `@font-face`, `@type`, `@example`. Sonuç fazla maskeleme; veri sızmıyor. K-19R-0008 listeyi genişletmeye açık bırakmıştı.
- **MINOR-6:** Jira wiki `{code}`/`{noformat}` blokları fence sayılmıyor (`FENCE` yalnız ``` ve ~~~).
  - Son 8 satırda bir `{code}` bloğu içindeki çıplak `--` satırı imza sayılıp siliniyor.
  - Blok içindeki küçük harfli `@` [USER] oluyor.
  - Kod tabanının başka bir yerinde (`ingest/turkish.py:63-67`) bu bloklar zaten tanınıyor.
- **NOTE-5:** Desenin kapsamadığı yazımlar: büyük harfli login (`@Ahmet`), tablo hücresi `|@ahmet.yilmaz|`, `*@ahmet.yilmaz*` (probe'da aynen kaldı). Büyük harfli login'in kalması kuralın gereği; runbook'taki "bilinen sınır" cümlesine eklenebilir. Lookbehind kümesine `|`, `*`, `_` eklenebilir.

### (5) R2: doğru

- `config.py:363-375` `CREDENTIAL_KEYS` bulgudaki 9 adla aynı ve SecretStr alan adlarıyla birleştiriliyor.
- `_credential_key` için `casefold() in _SECRET_KEYS`; alt dize eşlemesi yok.
- Değer tabanlı maske (Bearer ve secret değerleri) değişmedi.
- Kabul testi (`test_19r_redact.py:25-33`) bulgudaki çağrının aynısı; testler geçti.
- **NOTE-6:** Liste dışındaki adlar (`x-api-key`, `proxy-authorization`, `client_secret`) artık yalnız değer kuralıyla korunuyor.
  - Bugün bu adlarla log yazan bir çağrı bulunmadı (git grep). Reddedilen API key logu değeri yazmıyor.
  - Listeye `x-api-key` ve `proxy-authorization` eklemek ucuz bir sertleştirme olur.

### (6) R3: doğru

- İmza yalnız fence dışında ve son 8 dolu satırda temizleniyor (`stage_raw.py:110,122`).
- Her Jira mesajına ayrı uygulanıyor; `signature_lines_dropped` belge başına sıfırlanıyor (`:254`).
- Testler `test_19r_stage_raw.py:61-120`.
- Kısa sayfada "Teşekkürler" ve ardından gelen madde listesi hâlâ düşebilir; sayaç bunu kaydediyor. Bilgi notu, NOTE-7'ye dahil.

### (7) R4 (96 GB): doğru

**Aritmetik (ajanın, mem_limit değerlerinden; ben de kontrol ettim):**

| Senaryo | Hesap | Toplam |
|---|---|---|
| PayCore | 56 + Langfuse 9,5 | 65,5 |
| FFCore penceresi | 65,5 − 13 + 22 | 74,5 |
| Birlikte | 65,5 + 22 | 87,5 |

- Üçü de ≤ 90 (96 − 6).
- `SERVER_RAM_GB` varsayılanı 96.
- Runbook'ta "aynı anda hangi yığınlar" tablosu var (`m3-sunucu.md:286-296`).
- **MINOR-7:** `test_19_3_mem_budget_within_limit` artık skip etmiyor (bellek.md'ye 96 ve 6 yazıldı). Bu test `ffcore-migrate`'i (2g) de topluyor ve 89,5/90 buluyor; yeni senaryo testi ise migrate'i dışarıda bırakıp 87,5 buluyor. Aynı dosyada iki farklı bütçe tanımı var. FFCore'a 0,5 GB'tan fazla eklenirse eski test düşer, yenisi geçer. Öneri: eski test `ONE_SHOT` kullanmalı ya da kaldırılmalı.
- **NOTE-7:** `OS_SHARE_GB = 6` testte sabit kodlu. Bellek.md'deki "`free -g`" etiketinin yanındaki 96 GB ölçüm değil kullanıcı kararı; satır bunu söylüyor ama etiket yanıltıcı. R3'teki bilgi notu da burada.

### (8) R5, R6, R7, R8: doğru

- **R5:**
  - `embed()` içinde `truncated()` çağrısı yok.
  - Gold yolunda `flag_truncated`, eski `_index_doc` yolunda açık `truncated()` var; tek tokenizasyon, tek log.
  - Sorgu yolu (`retrieve`, `warmup`) kısa metin kullanıyor. Testler geçti.
- **R6:**
  - pyproject'te `langfuse>=4.15,<5`, `opentelemetry-sdk>=1.44` ve `opentelemetry-exporter-otlp-proto-http>=1.44` var.
  - `uv.lock` diff'te yok. Lock'taki sürümler (4.15.1, 1.44.0) bu sınırların içinde.
  - PR notu "master'da da bayat, FOLLOWUP-158" diyor.
  - `test_19r_r6_api_imports` (`import paycore_llm.api`) konteynerde geçti.
  - `uv lock --check`: **NOT_RUN** (ağ gerekebilir; K-19R-0009 A).
  - NOTE-8: lock'taki `requires-dist` artık paycore-llm'in kendi bağımlılığında da pyproject'ten ayrışıyor (`langfuse>=2.50`). FOLLOWUP-158 kapsamına bu satır da yazılmalı.
- **R7:**
  - `def is_prsim` yalnız `src/paycore_llm/ffcore_compat.py:27`'de; yorumunda FFCore kaynak yolu yazıyor.
  - FFCore `_is_prsim` ve `check_sources` ile anlamca aynı; yalnız detay metni farklı, kodlar aynı.
  - Seed, FFCore'un public `check_sources`'ını kullanıyor.
  - Uyum testi modül düzeyinde import ettiği için ffcore yokken toplama hatası veriyor, skip olmuyor. Bu koşuda geçti.
- **R8:**
  - `_secrets()` argümansız `lru_cache(maxsize=1)`; Settings hash'lenmiyor.
  - autouse fixture her testte önbelleği temizliyor; sayaçlı test geçti.
  - İlk logdan sonra değişen bir secret görülmez; `get_settings` da önbellekli olduğu için üretimde tutarlı.

---

## (9) Güvenlik turu (iki depo)

| Konu | Durum |
|---|---|
| `.env`, secret, `data/**`, `eval/results/**` diff'te | Yok (`--name-status`). Compose satırları `${VAR:?}` ya da sabit iç adlar. |
| Log'da secret | R2 değer maskesi aynen. `raw_ingest` log ve DB'ye yalnız `type(exc).__name__` yazıyor (`str(exc)` yok). Probe'da secret basılmadı. |
| Log'da kişi verisi | `embedding_truncated` logu parçanın ilk 120 karakterini yazıyor. Bu PR'dan önce de vardı; delta sorgu yolundaki kopyasını kaldırıyor. M3'te parça başına kişi verisi düşebilir; FOLLOWUP önerisi. |
| Staging'de kişi verisi | **MAJOR-4** (Jira özetinde `@login`), MINOR-4 (noktalı ad kısmi sızıntı), NOTE-5. |
| Staging raw dizinine yazma | Yok. `--out` raw içindeyse duruyor (bazda da vardı). FFCore `ingest-raw` yalnız DB'ye yazıyor; probe ağaçları `:ro` bağlandı ve koşu sorunsuz. |
| Yeni dış ağ çıkışı | Yok. Eklenen tek host iç ad `backend`. **MINOR-3:** backend artık kendini iç host sayıyor (yalnız admin; A/B/C seçenekleri yukarıda). |
| ACL | MINOR-1: yeniden deneme eski ACL'yi koruyor (gevşetme yok). |

## (10) Başka davranış değişikliği

Belgelenmiş olanlar:
- R5: sorgu yolunda truncation logu yok.
- R2: anahtar maskesi daraldı.
- 155: `retried` geldi, status satırı DB'den.

Belgelenmemiş olanlar: MAJOR-1, MAJOR-2, MAJOR-4.

**ffcore testleri (benim koşum, yığın review-19r, b7a6d53):**
- `make test`: **948 passed** llmaas, **948 passed** airgap.
- 04a/06a/19 test-int (llmaas, `RUN_QDRANT_TESTS=1`): **184 passed, 3 skipped**.
  - 2 atlama `RUN_MODEL_TESTS=1` istiyor.
  - 1 atlama `test_19_ingest_raw:156`: root dosya modlarını yok sayıyor; `:ro` testi ayrı.
- Bu sayılar mevcut testlerin yeşil olduğunu gösteriyor. MAJOR-1, MAJOR-2 ve MAJOR-4'ü yakalayan bir test yok; bulgular yığın ve probe'la kanıtlandı.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| SHA doğrulama (iki depo) | commit; 3 ve 9 commit | — |
| ffcore çözülmüş compose farkı (main ve PR) | yalnız `backend.ALLOWED_INTERNAL_HOSTS` | scratchpad (çıktıda `.env.test` değerleri olduğu için state'e konmadı) |
| paycoreLLM çözülmüş compose farkı (ca1b287 ve 81098f4, dummy env) | yalnız `ffcore-backend.ALLOWED_INTERNAL_HOSTS` | aynı |
| paycoreLLM tam pytest | 586 passed / 3 failed (bs4) / 2 skipped | `19r1-dis-paycore-tests.log` |
| paycoreLLM master'da 3 bs4 testi | 3 failed (önceden vardı) | `19r1-dis-paycore-master-bs4.log` |
| R1 probe | yukarıda | `19r1-dis-probe-r1.log` |
| Yığın up (b7a6d53 derlemesi) | healthy | `19r1-dis-stack-up.log` |
| 154c embed probe | `EMBED_OK dense 1024`; eski değerle `egress_offline` | `19r1-dis-probe-embed.log` |
| ingest-raw A, B, C, D | yukarıda | `19r1-dis-ingest-{A,B,C,D}.log`, `19r1-dis-db-after-{B,D}.log` |
| ffcore unit (iki profil) ve 04a/06a/19 test-int | 948/948 ×2; 184 passed, 3 skipped | `19r1-dis-ffcore-{unit-llmaas,unit-airgap,int-llmaas}.log` |

**NOT_RUN:**
- `uv lock --check` (ağ; FOLLOWUP-158).
- ffcore tam `test-int` (807). Yalnız 04a/06a/19 dosyalarını koştum.
- airgap test-int.
- PayCore yığını (`compose.ffcore.yml` up).
- Lint.
- Gerçek PayCore verisi (kural gereği).
- İşçinin 948/807 sayıları bu turda tam koşulmadı. Unit sayısı yukarıda.

## İstenen düzeltmeler (DUZELT için)

1. **MAJOR-1 (ffcore):** Satırı olmayan hata status satırında, manifestteki `failed` alanında ve çıkış kodunda görünmeli. Testi koşu D olmalı.
2. **MAJOR-2 (ffcore):** `_mark_failed` id ile işaretlemeli. Kayıttan önceki hata eski geçerli satıra dokunmamalı; bunun testi eklenmeli.
3. **MAJOR-3 (ffcore):** `docs/demo.md:86` → `Source accuracy (expected document cited) (≥ 16/20 on cpu)`.
4. **MAJOR-4 (paycoreLLM):** Jira özetine `_mentions` uygulanmalı ve test eklenmeli; :177-178'deki yorum düzeltilmeli.
5. **İsteğe bağlı (önerilen):**
   - MINOR-4: lookahead'e `.` ve bir test.
   - MINOR-2: ffcore `migrate`/`tools` assert'i.
   - MINOR-7: eski bütçe testi.
   - Geri kalan MINOR ve NOTE'lar FOLLOWUP ya da PR notu olarak.
6. **MINOR-3:** koordinatör kararı (A/B/C).
