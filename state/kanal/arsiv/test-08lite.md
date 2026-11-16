# Arşiv: test · 08lite

state/kanal/test.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### T-08lite-0001 · 2026-10-28 16:03 · → koordinator · DURUM
Paket: 08-lite (rol talimatı bekleniyor)   Cevap: -
DURUM: OKUMA-TAMAM (yeni oturum; ortak giriş prompt'u ile açıldı, ROL/PAKET satırı henüz verilmedi; kullanıcı "test" dedi, test şeridi varsayıldı).
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE; 3 PLAN v2.5 tamamı; 4 KARARLAR tamamı; 5 handbook INDEX + 12 dosya + templates/PR_SABLONU; 6 WORK_QUEUE, BLOCKERS (1-58), HANDOFF, test kanalı, koordinatör kanalında test'e adresli mesajlar (K-INIT-0005/0008, K-08lite-0000/0001), isci-a A-03a-0017 HANDOFF; 7 plan/08 tamamı (rolün brief'i) + GOREV bağımlı teslimatları (03a, 03b, 13a set yapısı T-13a-0022); 8 BASLATMA.
Okunmayan (doğrulanmadı): diğer 16 brief, koordinatör/isci-a/isci-b/isci-c/inceleyici kanallarının test'e adresli olmayan mesajları; işçi şablonu bunları istemiyor, rol talimatı isterse okurum.
Lease değiştirilmedi (RETIRED kalıyor); K-08lite-0001'e ACK, lease ACTIVE ve oturum kimliği ffcore-test-08-lite rol talimatı gelince.

### T-08lite-0002 · 2026-10-28 17:10 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0002
Not: T-08lite-0001 bu dosyadan 16:10 civarı kaldırılmıştı (kullanıcı önce "rolün test değil" dedi); kullanıcı ardından `ROL=test PAKET=08-lite` verdi, mesaj aynen geri eklendi.
DURUM: OKUMA-TAMAM, lease ACTIVE, oturum ffcore-test-08-lite. Ek tarama: BLOCKERS 59-70, koordinatör kanalı K-08lite-0002'ye kadar.

### T-08lite-0003 · 2026-10-28 17:10 · → koordinator · ACK
Paket: 08-lite   Cevap: K-08lite-0001
GOREV alındı (K-08lite-0000 taslağı dahil). Worktree .worktrees/feat/08-lite-guardrails @ 591aac3, temiz. Sıradaki: plan/06 guard kancaları bölümü, rg ile semboller (03a require_role/write taraması, 03b @audited, 13a pii seti), state/pr/08-lite.md, DURUM: PLANNED.

### T-08lite-0004 · 2026-10-28 17:16 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0001
DURUM: PLANNED talebi. Plan state/pr/08-lite.md (PR_SABLONU 1-9, felsefe üç sorusu, 23 kabul → test satırı, 10 varsayım). Kod yok; worktree @ 591aac3 temiz.
Özet: engine + 7 aşama (C4 bu PR'la donar), regex PII (TC/TR telefon/TR IBAN/e-posta/kart), secrets, tool_args, redact/mask/tokenize (Redis, zaten bağımlılık), monitor/enforce, on_error fail-closed; 3 tablo, Alembic dal 08 + `depends_on=("03a_0001",)` (FK sırası; GOREV yalnız down_revision demişti); politika CRUD, test paneli, `/api/v1/internal/guardrails/evaluate`. Presidio 08-lite'ta alınmıyor (ARCH-09 tartısı planda).
Touch-zone dışı / karar isteyen 5 nokta, ayrıntı planın "S1-S5" bölümünde, hepsinde önerim A:
S1 openapi_export.py'ye paket eşlemesi (yoksa 03a.yaml bayt testi kırılır). S2 test_03a_write_flag WRITE_EXEMPT'e internal evaluate + test paneli. S3 compose &app-env'e GUARDRAIL_EGRESS_ENABLED (varsayılansız) + PII_TOKEN_TTL_S. S4 FOLLOWUP-33: İngilizce, Presidio uyumlu kodlar (TR_NATIONAL_ID, TR_PHONE, EMAIL_ADDRESS, CREDIT_CARD, PERSON…), data/samples/scripts bu PR'da ayrı commit, metin/span bayt aynı. S5 politika yoksa API'de görünen yerleşik `default` (monitor).
Brief çelişkileri planda varsayım 1 ve 4 (on_error block|allow vs open|closed; "paralel" vs sıralı zincir).
Cevap gelince dilim 1 (engine + tanıyıcılar + maskeleme, unit, önce kırmızı test).

### T-08lite-0005 · 2026-10-28 17:21 · → koordinator · ACK
Paket: 08-lite   Cevap: K-08lite-0003
PLANNED onayı alındı, S1-S5 A. openapi_export için 04a 68dcc23 kalıbı salt-okunur alınıyor; kanonik kodlar KARARLAR'dan; C4 donmuş biçim PR'da ayrı başlık. Dilim 1 başlıyor (önce kırmızı).

### T-08lite-0006 · 2026-10-28 17:27 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0003
DURUM: IMPLEMENTING, dilim 1 tamam (kırmızıdan yeşile; 20 unit test).
- ec7847f + 5f9a7f4 (S4): 13a kodları kanonik listeye; yeniden üretimde metin ve span bayt aynı (eşleme sonrası JSON eşitliği doğrulandı), memory çıktısı değişmedi, 13a unittest 20/20 OK, ruff temiz.
- effc381: categories.py (C4 aşama/aksiyon listeleri + kanonik kodlar), 5 regex tanıyıcı (kanıt + bağlam), redact/mask/tokenize (+ detokenize, run kapsamlı store), quality.py ölçüm; docs/guardrail.md tablosu test ile bağlı.
Ölçüm (pii-100): TR_NATIONAL_ID 9/9, TR_PHONE 9/9, TR_IBAN 6/6, EMAIL 8/8, CARD 5/5, precision 1.00, negatiflerde bulgu 0; regex P95 1.000 karakter 0,61 ms. Not: set ile tanıyıcıyı aynı ekip yazdı, 1.00 "bilinen biçimlerde gerileme yok" demek; docs'ta yazılı.
Sıradaki dilim 2: engine (zincir, mod, on_error), secrets, tool_args.

### T-08lite-0007 · 2026-10-28 17:43 · → koordinator · DURUM
Paket: 08-lite   Cevap: -
DURUM: IMPLEMENTING, dilim 2-4 kodu tamam; entegrasyon **PENDING_ENV**.
- 12db669: engine (sıralı zincir, block keser, short_circuit=false kaydı tamamlar, monitor uygulamaz ama kaydeder, on_error fail-closed), secrets (vendor + şifre anahtar kelimesi + entropi), tool_args; doğrulama kodları; yerleşik default (monitor).
- 4cafdbc: 3 tablo + Alembic 08 (depends_on 03a_0001), politika CRUD (audit), test paneli, `/api/v1/internal/guardrails/evaluate` (servis hesabı, olay yazar, Redis tokenize), openapi/08.yaml (04a kalıbı; 03a.yaml bayt aynı), S2 WRITE_EXEMPT, S3 compose/env.
Kapılar (tools konteyneri, --no-deps): ruff check + format 0; tests/unit + tests/contract 180 passed.
Engel: `docker compose -p 08lite --env-file .env.test up -d --wait postgres redis` → initdb "No space left on device". `docker system df`: imaj 56 GB (29,8 GB geri alınabilir), konteyner 14,5 GB (14,45 geri alınabilir; test-oracle 7,5 GB, test-mssql 6,8 GB katmanı), build cache 7,6 GB (0 aktif); host C: %99, 7,5 GB boş. Kendi yığınımı `down -v` ile kaldırdım. 01 ve 04a yığınları ayakta; yeni yazımda aynı duvara çarpabilirler.
`tests/integration/test_08_api.py` yazıldı (12 test: erişim/audit, enforce geçişi, PII referansı, panel kanıtı, internal servis sınırı, block, maskeli olay, Redis TTL, egress bayrağı, migration döngüsü), **koşulmadı**.
Silme yapmadım (başka projelerin verisi). KARAR-GEREK T-08lite-0008.

### T-08lite-0008 · 2026-10-28 17:43 · → koordinator · KARAR-GEREK
Paket: 08-lite   Cevap: T-08lite-0007
Konu: Docker diski dolu; 08 entegrasyon testleri (ve muhtemelen 01/04a yeni yazımları) koşamıyor. Silme kullanıcı onayı ister.
**A (Önerilen):** kullanıcı yalnız aktif olmayan, veri taşımayanları temizler: `docker builder prune` (7,6 GB, aktif 0) + `docker container prune` yalnız "Created" durumdaki boş konteynerler (19 adet, katman 0 B). Etki: ~8 GB (build cache), hiçbir projenin verisi gitmez; sonraki build'ler bir kez cache'siz.
B: A + kapalı büyük konteynerler (test-oracle 7,5 GB, test-mssql 6,8 GB, ffgov_om_*). Etki: ~22 GB; o projelerin konteyner içi verisi gider (kullanıcı bilir).
C: Docker'a dokunmadan host C: diskinde yer açılır ya da Docker Desktop disk sınırı büyütülür. Etki: en güvenli, kullanıcının elle işi, süresi belirsiz.
Karar gelene kadar: unit/contract kapsamındaki işler (docs, PR metni) sürüyor.

### T-08lite-0009 · 2026-10-28 18:15 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-INIT-0011
DURAKLADIM, çalışan komut yok, stack: 08lite (postgres + redis ayakta). Duraklamadan önce biten koşu (imaj `0.0.0-08lite`, K-INIT-0010): make lint 0; make test llmaas 180 / airgap 180 passed; make test-int llmaas 107 / airgap 107 passed (airgap koşusu GUARDRAIL_EGRESS_ENABLED=false). DEVAM sonrası: migrate+backend up ile smoke, sonra PR metni ve PR-HAZIR.

### T-08lite-0010 · 2026-10-28 18:31 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-INIT-0012
DURUM: VERIFIED. HEAD 21812317c05093658b88a8b0c7bfff0dba7ceb52 (duraklamadan beri kod değişmedi). Smoke: `0.0.0-08lite` ile backend + litellm + langfuse up (8000 başka yığında dolu, yalnız bu koşu için BACKEND_PORT=18008), migrate 03a/08/03b sırası doğru, `make smoke` 0, heads 03a_0001 + 03b_0001 + 08_0001, kimliksiz internal evaluate 401. Stack `down -v` (08lite konteyner 0). Dangling imaj: 2 adet (prune sende). state/pr/08-lite.md güncel (VERIFIED, komut tablosu).

### T-08lite-0011 · 2026-10-28 18:31 · → koordinator · PR-HAZIR
Paket: 08-lite   Cevap: K-08lite-0003
PR: state/pr/08-lite.md · Branch: feat/08-lite-guardrails · SHA: 21812317c05093658b88a8b0c7bfff0dba7ceb52 · Sınıf: [A] (S1-S4 paylaşılan dosya dokunuşları onaylı) · baz 591aac3 · 8 commit, 37 dosya · push yok. C4 bu PR'la donar ("C4 donmuş biçim" bölümü). Güvenlik turu gerekli (EXECUTION_HANDBOOK 7: 08).

### T-08lite-0012 · 2026-10-28 18:34 · → koordinator · HANDOFF
Paket: 08-lite   Cevap: K-08lite-0004
TASLAK (oturum review sonucunu bekliyor, kapanmadı). Düzeltme: T-08lite-0011'deki "8 commit" yanlış, **7 commit**; state/pr/08-lite.md düzeltildi.
### 08-lite · ffcore-test-08-lite · 2026-10-28 18:34
- Durum: VERIFIED; REVIEW-ISTEK K-08lite-0005 inceleyicide, SHA 21812317c05093658b88a8b0c7bfff0dba7ceb52. Branch'e commit yok; DUZELT gelirse yeni SHA ile PR-HAZIR.
- Tam sonraki adım: review sonucu. Onaydan sonra bu paket için iş yok; 06a bağlama ve 08 tam aşağıda.
- 06a bağlama notları:
  - İmza: `await ffcore.guardrails.engine.evaluate(text, stage, policy, ctx=EvalContext(run_id, project_id, source, locale, tool, token_store, egress_enabled))` → `Decision(action, text_out, events, message, reference_id)`. Politika: `ffcore.guardrails.service.resolve_policy(session, project_id, definition.guardrail_policy_key or "default")`; olaylar `service.record_events(session, project_id, decision.events, decision.reference_id)` ile yazılır (engine hiçbir şey saklamaz). Ayrı süreçte HTTP gerekirse `POST /api/v1/internal/guardrails/evaluate` (SERVICE_TOKEN) aynı sözleşme.
  - Kanca eşlemesi: `guard_in` → `input.pre` (+ `GUARDRAIL_EGRESS_ENABLED` true ise modele giden pakette `egress`), `tools` → `tool.pre` (metin = argüman JSON'u, `ctx.tool="<tool_key>.<action>"`) ve `tool.post`, `guard_out` → `output.pre`; kullanıcı turunda bir kez `prompt.pre`. Egress kapalıyken çağırmak `EgressStageDisabled` (sessiz geçiş yok); 06a bayrağı okuyup çağırmamalı.
  - `action == "block"` → run `failed`, `error_code=guardrail_block`, `reference_id` = `decision.reference_id`, kullanıcı metni `decision.message` (locale `en|tr`). Diğer aksiyonlarda sonraki adıma `decision.text_out` gider.
  - tokenize: `ctx.run_id` + `service.redis_token_store()` zorunlu; cevapta `masking.detokenize(text, store=..., scope=run_id)` → `(metin, unresolved)`; `unresolved` boş değilse olay olarak yazılmalı (model uydurmuş yer tutucu). Akışta geri çevirme (C17) 08 tam.
  - Yerleşik `default` monitor modunda: 06a bağlandığında hiçbir şey engellenmez, olaylar yazılır; enforce kararı admin'in politika PATCH'i (audit'li).
  - `output.stream.delta` 08-lite'ta reddedilir (kural doğrulaması); 06a akışta aşamayı çağırmamalı.
- 08 tam'a kalanlar: Türkçe NER (`PERSON`, `ORGANIZATION`, `LOCATION`; ad-soyad recall ≥ 0,85 / llmaas 0,90) Presidio ile (tanıyıcı arayüzü `Finding` = `RecognizerResult` + kanıt); `injection` sınıflandırıcısı ve gecikme ölçümü (P95 < 300 ms bütçesinin kalanı); akış tamponlayıcı C17 (`<<PII_` bölünmesi); bağlamlı CVV/PIN tanıyıcıları (brief'te varsayılan açık, 08-lite'ta yok); `egress` kalibrasyonu (R7.4); PRSIM ingest guard'ı (karar 5); `topic`, `output_format`, `banned_words` kural türleri; `guardrail_events` saklama/partition (03c).
- FOLLOWUP-33: kapandı (KARARLAR "08-lite kararları"); kanonik liste `backend/ffcore/guardrails/categories.py`, 13a seti aynı kodlarla, `test_08_21_*` eşitliği koruyor.
- Merge notları: 04a ile çakışma noktaları `api/openapi_export.py` (PACKAGES ve rota listesi), `tests/unit/test_03a_write_flag.py` (`WRITE_EXEMPT |=`), `tests/integration/test_03a_read_side.py` (`PARITY_EXEMPT_PREFIXES` demeti birleşir), `deploy/docker-compose.yml` `&app-env`; `service_actor` kopyası ve `/internal` yol farkı (PR varsayım 15).
- Koşan testler: make lint 0; make test 180 + make test-int 107, llmaas (egress true) ve airgap (egress false), imaj 0.0.0-08lite; make smoke 0. Kalan: yok (NER/injection 08 tam).
- Kararlar: K-08lite-0003 (S1-S5 A), DRIFT-71 (varsayım 1 ve 4), PR varsayımları 1-16.
- Blocker'lar: yok (ENV-73 kapandı).
- Commit edilmemiş durum: yok. Stack `08lite` down -v; worktree .worktrees/feat/08-lite-guardrails temiz.
- Branch ve son commit: feat/08-lite-guardrails @ 21812317c05093658b88a8b0c7bfff0dba7ceb52.

### T-08lite-0013 · 2026-10-28 18:57 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0007
Ön bilgi alındı; branch'e dokunmadım (21812317 sabit, worktree temiz). Dört bulgu için kırmızı test + düzeltme hazır, ayrı detached çalışma kopyasında (scratchpad, `git worktree add --detach`), yama scratchpad'de; DUZELT gelince worktree'ye uygulanır, commit, kapılar, yeni SHA ile PR-HAZIR.
- (1) K-08lite-0006 A: `service.resolve_policy` yerleşik zincirde `pii_policy_key`'i `resolve_pii` ile çözer (proje satırı, yoksa yerleşik). Kırmızı: `test_08_s5_builtin_chain_uses_the_projects_stored_pii_default` (21812317'de düştü).
- (2) Önizleme: `_preview` artık regex PII + `find_secrets` + kuralın bulguları + zincirde önceki kuralların bulduğu her değeri redakte eder; hata yolunda da önizleme dolu ve maskeli. Kırmızı: `test_08_20_preview_never_raw_across_the_chain` (monitor/block, enforce/warn, enforce/log).
- (3) tokenize kimliği ham değer (normalizasyon yok): `a.b@` ve `ab@` ayrı yer tutucu. Kırmızı: `test_08_3_distinct_values_never_share_a_token`. Bedel: biçimi farklı yazılmış aynı numara yeni yer tutucu alır (yanlış değil, yalnız ayrı); PR'da yazılacak.
- (4) Redis: get-or-create tek Lua `EVAL` (HGET → HINCRBY → iki alanlı HSET → EXPIRE atomik). Kırmızı: `test_08_3_redis_store_publishes_both_directions_atomically` (ağ gecikmeli sahte istemci; eski kodda ikinci çağrı ters kayıt yokken token döndü). Gerçek Redis'te 50 eşzamanlı çağrı testi (`test_08_3b_concurrent_tokenize_resolves_every_token`) eski kodda da geçiyor (yerel Redis pencereyi kapatıyor); kanıt sahte istemcili unit testtir.
Hazırlık koşusu (imaj 0.0.0-08lite, proje 08lite-r1, sonra down -v): ruff 0; unit+contract 183 passed; 08 entegrasyon 15 passed. Tam matris (iki profil) DUZELT uygulanınca worktree'de.

### T-08lite-0014 · 2026-10-28 19:00 · → koordinator · ACK
Paket: 08-lite   Cevap: K-08lite-0008
DUZELT r1 alındı (state/reviews/08-lite-r1.md, MAJOR 4). Uygulanıyor: hazır dört düzeltme + MAJOR-1 eki (kısa değerlerde en az bir karakter maskeli, maskeli değer hiçbir zaman ham değere eşit değil, `matches.value` ve API `FindingOut.value` → `masked_value`, C4 donmadan), gerçek DB + API cevabı negatifleri (kısa e-posta, tek haneli değer, zincirde önceki kuralın değeri), MAJOR-3 sınırı PR notunda açık. Tam matris 0.0.0-08lite, yeni SHA ile PR-HAZIR.

### T-08lite-0015 · 2026-10-28 19:14 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0008
DURUM: VERIFIED (r1 düzeltmesi). Commit 7a7dc35 (21812317 üstüne tek fix commit'i). MAJOR-1..4 kapandı; bulgu → düzeltme → kanıt tablosu state/pr/08-lite.md.
Ek (hazırlıktan farklı): kısa değer testi önceki olayın önizlemesinde **sonraki** kuralın özel desen değerini ham buldu; önizlemeler artık zincir bittikten sonra, zincirin tüm bulgularıyla kuruluyor. `masked_value` adı olaylarda ve API FindingOut'ta (08.yaml yeniden üretildi).
Kapılar (imaj 0.0.0-08lite yeniden derlendi): make lint 0; make test 184 + make test-int 110, llmaas (egress true) ve airgap (egress false); smoke 0 (BACKEND_PORT=18008); stack down -v. Scratch worktree kaldırıldı. Dangling imaj: 3 (prune sende).

### T-08lite-0016 · 2026-10-28 19:14 · → koordinator · PR-HAZIR
Paket: 08-lite   Cevap: K-08lite-0008
PR: state/pr/08-lite.md · Branch: feat/08-lite-guardrails · SHA: 7a7dc35e156b17f72e567dad3bfbf584f4f7a898 · Sınıf: [A] · r2 delta: 21812317..7a7dc35 (10 dosya) · push yok.

### T-08lite-0017 · 2026-10-28 19:34 · → koordinator · ACK
Paket: 08-lite   Cevap: K-08lite-0011
DUZELT r2 alındı (state/reviews/08-lite-r2.md, MAJOR 1). Uygulanıyor: önizleme yalnız baş penceresini işler, değerler set ile tekil, örtüşme birleşimi sıralı tek geçiş; ek olarak tanıyıcıların resolve_overlaps'ı da O(n^2) (10.000 tekrar gerçek evaluate yolunda aynı sorunu verir), O(n log n) olacak; CPU yoğun kısım asyncio.to_thread; latency_ms önizleme dahil. Regresyon kapısı gerçek evaluate yolunda (640 / 10.000 tekrar, 200.000 karakter karışık metin; üst sınır, tek CPU konteynerde ayrıca), r1 gizlilik negatifleri birlikte. Yeni SHA ile PR-HAZIR.

### T-08lite-0018 · 2026-10-28 19:46 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0011
DURUM: VERIFIED (r2 düzeltmesi). Commit 199aeb4 (7a7dc35 üstüne tek fix commit'i). Önizleme: ilk 4.096 karakter taranır, en çok 3.840 gösterilir (kesilen değer asla), değerler tekil, örtüşme tek sıralı geçiş; ek olarak tanıyıcıların resolve_overlaps'ı da O(n^2) idi, O(n log n) yapıldı (sonuç aynı). Tarama + önizleme to_thread, latency_ms önizleme dahil.
Kanıt: tests/unit/test_08_cost.py (üst sınır, bitmeme de kırmızı) önce 7a7dc35'te kırmızı, sonra yeşil; tek CPU/512 MB: 640 tekrar 0,036 s (r2'de 12 s+), 10.000 tekrar 0,418 s, 200.000 karışık 0,198 s. r1 gizlilik negatifleri aynı matriste yeşil.
Kapılar (0.0.0-08lite yeniden derlendi): lint 0; make test 190 + make test-int 110, llmaas (egress true) ve airgap (egress false); smoke 0; stack down -v. Dangling imaj: 3 (prune sende).

### T-08lite-0019 · 2026-10-28 19:46 · → koordinator · PR-HAZIR
Paket: 08-lite   Cevap: K-08lite-0011
PR: state/pr/08-lite.md · Branch: feat/08-lite-guardrails · SHA: 199aeb46c813996517332d31ca2cd6f8a178d41a · Sınıf: [A] · r3 delta: 7a7dc35..199aeb4 (4 dosya) · push yok.

### T-08lite-0020 · 2026-10-28 19:49 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0014
Alındı; haklısın, ifade yanıltıcıydı. state/pr/08-lite.md r2 tablosu düzeltildi: tarama penceresi 4.096, gösterim sınırı 3.840 (girdi konumu; arada 256 karakter kenar payı), önizleme 60 karakter (input_preview uzunluğu, değişmedi). Branch'e dokunmadım (199aeb4). Aynı belirsiz ifade docs/guardrail.md gecikme bölümünde de var ("show at most the first 3,840"); commit yasağı nedeniyle düzeltilmedi, PR kalan risklerine yazıldı: r3'te DUZELT gelirse onunla, yoksa merge sonrası tek satırlık docs düzeltmesi. Hangisini istediğini sen seç.

### T-08lite-0021 · 2026-10-28 20:07 · → koordinator · HANDOFF
Paket: 08-lite   Cevap: K-08lite-0017
### 08-lite · ffcore-test-08-lite · 2026-10-28 20:07
- Durum: MERGED (main e651ff4; r3 ONAY 199aeb4). C4 dondu. Bu oturum kapanıyor; lease RETIRED.
- Tam sonraki adım (bu rol için): test kuyruğunda 13b olumsuz senaryo payı (06a/07 MERGED sonrası, yeni oturum). 08 tam M4.
- 06a bağlama notları (T-08lite-0012 taslağı geçerli, r1/r2 güncellemeleriyle):
  - `await ffcore.guardrails.engine.evaluate(text, stage, policy, ctx=EvalContext(run_id, project_id, source, locale, tool, token_store, egress_enabled))` → `Decision(action, text_out, events, message, reference_id)`; politika `service.resolve_policy(session, project_id, definition.guardrail_policy_key or "default")` (yerleşik zincir de projenin PII `default` satırını çözer, K-08lite-0006 A); olaylar `service.record_events(...)`.
  - Kancalar: `guard_in` → `input.pre` (+ egress bayrağı açıksa `egress`), `tools` → `tool.pre` (argüman JSON'u, `ctx.tool="<tool_key>.<action>"`) / `tool.post`, `guard_out` → `output.pre`, kullanıcı turunda `prompt.pre`. Egress kapalıyken çağrı `EgressStageDisabled`. `output.stream.delta` kuralı reddedilir (C17 08 tam).
  - `block` → run `failed`, `error_code=guardrail_block`, `reference_id`, mesaj `decision.message` (en|tr).
  - tokenize: `run_id` + `service.redis_token_store()`; kimlik ham değer (biçimi farklı aynı numara ayrı yer tutucu); Redis yazımı tek Lua EVAL; çıkışta `masking.detokenize` → `unresolved` boş değilse kayıt.
  - Olaylarda ham değer yok: `matches[].masked_value` (r1'de `value`'dan yeniden adlandırıldı, C4'te), önizleme zincir sonunda kurulur. Kural taraması ve önizleme `asyncio.to_thread`; `latency_ms` önizleme dahil.
  - Yerleşik `default` monitor: 06a bağlanınca hiçbir şey engellenmez; enforce admin PATCH'i (audit'li).
- 08 tam'a kalanlar: Türkçe NER (`PERSON`, `ORGANIZATION`, `LOCATION`; recall ≥ 0,85 / llmaas 0,90) Presidio ile (`Finding` = `RecognizerResult` + kanıt); `injection` sınıflandırıcısı ve gecikme bütçesinin kalanı; akış tamponlayıcı C17; bağlamlı CVV/PIN; `egress` kalibrasyonu; PRSIM ingest guard'ı; `topic`, `output_format`, `banned_words`; `guardrail_events` saklama/partition (03c).
- FOLLOWUP-76 (08 tam ya da 06a guardrail PR'ı): (a) `docs/guardrail.md` gecikme bölümündeki "show at most the first 3,840" ifadesi: doğru biçim "tarama penceresi 4.096, girdi konumu sınırı 3.840, önizleme 60 karakter"; (b) `recognizers/regex.py:resolve_overlaps` liste `insert` yüzünden en kötü durumda O(n²) (bellek kaydırma, C hızında; ölçülen bütçeler içinde) ve docstring'deki "O(n log n)" iddiası düzeltilmeli; gerekirse `sortedcontainers` yerine aralık ağacı ya da başlangıca göre sıralı tek geçiş. Davranış değişmez.
- FOLLOWUP-33: kapandı (kanonik liste `guardrails/categories.py`, 13a seti aynı, `test_08_21_*`).
- Merge sonrası 04a ile birleşecek noktalar (bilgi): `api/openapi_export.py` PACKAGES, `test_03a_write_flag.py` `WRITE_EXEMPT`, `test_03a_read_side.py` `PARITY_EXEMPT_PREFIXES`, compose `&app-env`; `service_actor` kopyası tek yardımcıya; `/internal` yol farkı (PR varsayım 15).
- Koşan testler (son: 199aeb4, imaj 0.0.0-08lite): lint 0; make test 190 + make test-int 110, llmaas (egress true) ve airgap (egress false); tek CPU maliyet testleri; smoke 0. Main'de koordinatör lint + smoke geçti.
- Kararlar: K-08lite-0003 (S1-S5 A), K-08lite-0006 (A), K-08lite-0008/0011 (DUZELT r1/r2), K-08lite-0016 (A), DRIFT-71, FOLLOWUP-76; PR varsayımları 1-16 (state/pr/08-lite.md).
- Blocker'lar: yok.
- Commit edilmemiş durum: yok. Worktree, branch ve 08lite imajları koordinatörce silindi; 08lite ve 08lite-r1 stack'leri `down -v`; scratch worktree kaldırıldı.
- Branch ve son commit: feat/08-lite-guardrails (silindi) @ 199aeb46c813996517332d31ca2cd6f8a178d41a → main e651ff4.
