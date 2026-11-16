# Arşiv: isci-b · 05a

state/kanal/isci-b.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### B-05a-0001 · 2026-10-29 15:24 · → koordinator · ACK
Paket: 05a   Cevap: K-05a-0001
GOREV alındı. Worktree .worktrees/feat/05a-tools-mcp @ 5c338ae. paycoreLLM uv.lock'ta mcp ve sqlglot yok, bu yüzden sürüm seçimi ölçümle yapılacak. İlk iş U5/DRIFT-6 ölçümü: pinli mcp SDK + streamable HTTP, başlıklar çağrı başına mı oturum açılışında mı. Ölçüm depo dışında; kod ve commit yok. Sonra state/pr/05a.md → DURUM PLANNED. Tüm build/up FFCORE_VERSION=0.0.0-05a.

### B-05a-0002 · 2026-10-29 15:28 · → koordinator · DURUM
Paket: 05a   Cevap: K-05a-0001 (kural a)
U5 / DRIFT-6 ölçüldü; DRIFT-6 kapanabilir. Ölçüm ortamı: depo dışı scratch venv, mcp==2.3.0, 127.0.0.1, sahte değerler. Sunucu her POST'un gövdesinden JSON-RPC yöntemini ve X-On-Behalf-Of başlığını kaydetti.
- Kaynak (mcp/client): streamable_http_client(url, http_client: httpx2.AsyncClient). Kimlik başlıkları yalnız bu istemcinin başlıklarından geliyor. call_tool'da çağrı başına HTTP başlığı parametresi yok; ClientMessageMetadata.headers SDK'nın kendi başlıkları için (protokol sürümü, Mcp-Param-*).
- M1 (tek oturum, iki çağrı arasında istemci başlığı değişti): initialize=[A], tools/call=[A, B]. Başlık oturum açılışında dondurulmuyor; her istekte paylaşılan istemciden okunuyor.
- M2 (tek ortak oturum, iki kullanıcı eşzamanlı): tools/call=[D, D]. C kullanıcısının çağrısı D'nin kimliğiyle gitti, yani ACL karışması kanıtlandı.
- M3 (çağrı başına oturum, kendi istemcisiyle, eşzamanlı): initialize=[E, F], tools/call=[E, F]. Doğru.
Sonuç: forward_user'da havuz yok, oturum ve httpx2 istemcisi çağrı başına, JWT çağrı başına (brief ile aynı). none/bearer/header/basic'te başlık sabit, oturum havuzlanabilir.
C5 için ek bulgu: SDK httpx2 istemcisi alıyor ve FFCore'un pinned transport'u bağlantı anında host + adres kontrol ediyor. SDK'ya policy'li istemci vermek için core/egress.py'ye eklemeli bir fabrika gerekecek; dosya dokunma listesinde olduğu için planda KARAR-GEREK.
Sürümler (uv lock kopyada; yalnız ekleme, mevcut paket değişmedi): mcp 2.3.0 (2 Ekim; mcp-types 2.3.0, httpx2 zaten var); sqlglot 30.23.0; sse-starlette 3.5.0 (en az iki hafta eski sürümler; en yenileri 26 ve 25 Ekim). Plan yazılıyor.

### B-05a-0003 · 2026-10-29 15:35 · → koordinator · DURUM
Paket: 05a   Cevap: K-05a-0001
DURUM: PLANNED. Plan: C:\ai_paycore\ffcore\state\pr\05a.md. İçinde felsefe üç soru, kabul → test tablosu (11 kalem + U5 gerilemesi + C7), dilimler 1-6, migration ve geri alma. Kod ve claim yok; worktree 5c338ae temiz.
Karar isteyen 8 madde; hepsinde A önerili.
- S1 bağımlılıklar [C]: mcp 2.3.0, sqlglot 30.23.0, sse-starlette <3.6 kısıtı.
- S2 SDK'ya egress: core/egress.py'ye eklemeli policy_http_client (dokunma listesinde).
- **S3 forward_user aud:** brief ve GOREV aud=<tool_key> diyor, ama backend resolve_actor yalnız aud=ffcore-backend kabul ediyor (auth.py:239). mcp-search ve mcp-sql aktarıcı olduğu için önerim aud = doğrulayan servis: aktarıcılar token'ı değiştirmeden iletir, imzalama anahtarını tutmaz; diğer kurallar aynen (çağrı başına yeni JWT/jti, ≤300 s, yalnız iç host). B'de servisler imzalama anahtarını tutup yeniden imzalar; bu daha zayıf.
- S4 kb_key çevirisi: KB listesi ucu kullanılır; knowledge/ değişmez.
- S5 demo DB: mevcut postgres'te ayrı agent_demo veritabanı, make seed-sql-demo; parola .env'de, kullanıcı yazar.
- S6 few_shots: backend DB'de pgvector kolonu; mcp-sql backend'in sql-context ucunu OBO ile çağırır; model yalnız API'de kalır.
- S7 iki servis varsayılan profilde.
- S8 keşfedilen aksiyonlar enabled=false + needs_approval=true.
Ayrıca varsayımlar: kırpma işareti İngilizce yüzeyde; brief'teki Türkçe biçimle çelişki PR notunda.
Cevap gelene kadar kod yok.

### B-05a-0004 · 2026-10-29 15:37 · → koordinator · ACK
Paket: 05a   Cevap: K-05a-0002
Alındı: plan onaylı; S3 aud listesi [<tool_key>, "ffcore-backend"]; auth.py ve egress.py yalnız eklemeli; kırpma işareti İngilizce. IMPLEMENTING.
Dilim 2: bağımlılıklar (uv lock, yalnız ekleme) + migration 05a_0001 + modeller + tool CRUD + şifreleme/maskeleme + kayıtta SSRF ve forward_user iç host kontrolü. Önce kırmızı test.

### B-05a-0005 · 2026-10-29 16:08 · → koordinator · DURUM
Paket: 05a   Cevap: K-05a-0002
Dilim 2-3 tamam (commit'ler e81cf58 build, 7efecba registry, cb9d994 mcp_client). Testlerin hepsi önce kırmızıydı.
- Kayıt: CRUD, kimlik şifreli ve maskeli, kayıtta SSRF (400 egress_*), forward_user iç host kuralı (400 forward_user_not_internal). Migration 05a dalı; dal düzeyinde downgrade/upgrade turu temiz.
- MCP istemcisi gerçek MCP sunucusuna karşı (127.0.0.1):
  - U5 gerilemesi: dört eşzamanlı kullanıcının her biri kendi token'ıyla gitti.
  - forward_user: çağrı başına yeni jti; aud=[tool_key, ffcore-backend]; backend ve araç kabul ediyor, başka araç 403 audience_mismatch.
  - Çağrı anında egress reddi (sunucuya istek ulaşmıyor).
  - [truncated: N/M chars] işareti ve truncated=true log alanı; kodlu zaman aşımı; basic başlığı gidiyor, logda yok.
- API: discover (S8: yeni aksiyon kapalı + onaylı; ayarlar korunuyor; kalkan aksiyon missing), aksiyon ayarları, invoke (audit'li, argüman/sonuç audit'te yok).
- core/auth.py ve core/egress.py yalnız eklemeli; 03b testleri değişmedi.
Kapılar: birim 454/454, API 21/21, lint temiz.
Not (S1): sse-starlette<3.6 kısıtı 3.5.1'i seçti (24 Ekim, 5 günlük). Onaylanan iki hafta kuralı için kısıtı ==3.5.0 yaptım; PR notunda.
Varsayım: 05a'da oturum her kimlik türünde çağrı başına açılıyor (havuz yok). Havuz yalnız none/bearer/header/basic'te izinli; ölçülen gecikme gerektirirse eklenir.
Sıradaki: dilim 4 mcp-search.

### B-05a-0006 · 2026-10-29 16:18 · → koordinator · ACK
Paket: 05a   Cevap: K-05a-0003
Alındı. Değişken AGENT_DEMO_DB_PASSWORD; .env.example yer tutucu + açıklama; .env.test'te agent_demo; kodda varsayılan yok; logda ve API'de görünmez (SecretStr, 02 temizliği).
Bir not (karar sende, itiraz değil): parola tahmin edilebilir. Demo için kabul edilebilir: veri sentetik, kullanıcı salt okunur, Postgres iç ağda. Ama compose'da Postgres portu host'a açıksa host'taki herkes demo DB'yi okuyabilir. docs/araclar.md'ye "demo dışı kullanımda parolayı değiştirin" satırı koyuyorum.

### B-05a-0007 · 2026-10-29 16:43 · → koordinator · DURUM
Paket: 05a   Cevap: K-05a-0003
Dilim 4-5 tamam: 64c8865 mcp-search, c1e9ef9 mcp-sql. Testlerin hepsi önce kırmızıydı.
- mcp-search: gerçek zincir test edildi (mcp_client → mcp-search → HTTP üzerinden gerçek backend → 04a arama).
  - analyst yalnız açık belgeyi, admin ikisini görüyor; eşzamanlı 6 çağrıda ACL karışmadı;
  - süresi dolmuş token 401 token_expired; başka araca tekrar oynatma 403 audience_mismatch.
- mcp-sql: doğrulayıcı 25 birim testi; DELETE DB'ye gitmeden reddediliyor; 500 satır kırpması işaretli; salt okunur giriş kullanıcısı yazamıyor; statement_timeout kodlu; get_schema daraltma + 5 örnek.
  - Gerçek bge-m3 ile few-shot testi mevcut ağırlıklarla çevrimdışı geçti (04a-knowledge-core_model_cache ro; indirme yok).
Kendi bulduğum iki tutarlılık sorunu, ikisi de düzeltildi:
(1) C2 sözleşme testi: jwt.decode yalnız auth.py'de olmalı. Aktarıcı servislerin imzasız yönlendirme okuması auth.py'ye eklemeli fonksiyon olarak taşındı (unverified_on_behalf_of_claims).
(2) Backend Settings OBO_JWT_SECRET, FERNET_KEY, SECRET_KEY ve DATABASE_URL istiyor. Servisler app-env'le kurulsaydı bunlar servislere de giderdi (S3 gerekçesinin tersi). Bunun yerine servisler dar bir McpServiceSettings ile açılıyor; compose env'leri açık liste. Testle sabit: servis env'inde OBO_JWT_SECRET, DATABASE_URL, FERNET_KEY, SECRET_KEY, REDIS_URL yok.
K-05a-0003 uygulanışında bir sapma:
- .env.test'te değer dummy-not-secret-agent-demo, agent_demo değil.
- Neden: 00'ın kuralı (test_00_1) .env.test'teki her secret'ın dummy-not-secret işareti taşımasını istiyor.
- Kullanıcı kararı gerçek .env içindir; .env.example açıklaması "demo agent_demo kullanır, başka kullanımda değiştirin" diyor.
- Kural yerine agent_demo'nun kendisini istersen söyle; o zaman test_00'a istisna eklerim.
Sıradaki: dilim 6 (compose servisleri eklendi; smoke, OpenAPI, docs, canlı yığın doğrulaması).

### B-05a-0008 · 2026-10-29 17:10 · → koordinator · DURUM
Paket: 05a   Cevap: K-05a-0005
Takılı değilim, izin bekleyen istem de yok. Dilim 6 kodda tamam (commit'lenmedi).
- compose: mcp-search ve mcp-sql varsayılan profilde, healthcheck'li; env'leri açık liste.
- smoke iki servisi kontrol ediyor; .env.example/.env.test güncel.
- openapi/05a.yaml ve sözleşme testi; docs/araclar.md; canlı servis testi (test_05a_live_services).
Temiz yığında kapılar koşuyor (belgelenen komut, qdrant açık):
- iki servis healthy; servis env'lerinde OBO_JWT_SECRET, DATABASE_URL, FERNET_KEY, SECRET_KEY, REDIS_URL sayısı 0;
- smoke passed (mcp-search ve mcp-sql /healthz 200); lint temiz;
- llmaas: make test 492 geçti; test-int 257 geçti, 2 başarısız (test_03a_2_read_mode_get_parity, test_05a_live_run_sql_on_demo_database).
İkisini şimdi inceliyorum. airgap koşusu sürüyor.
K-05a-0005 (1): "yalnız yönlendirme" testi eklenecek.

### B-05a-0009 · 2026-10-29 17:51 · → koordinator · PR-HAZIR
Paket: 05a   Cevap: K-05a-0005
PR: state/pr/05a.md · Branch feat/05a-tools-mcp · Baz main 5c338ae · SHA a55ca54c128ac682e6891d4ae04aa1c6bf647f4c · [A] + bağımlılıklar [C] · 6 commit, 43 dosya +5043/-21.
DURUM: VERIFIED. Kabul 1-11 + U5 gerilemesi + C7 testlerle; her dilimde önce kırmızı.
Kapılar (belgelenen komut, qdrant açık, temiz volume, yeniden kurulan imajlar):
- make test: llmaas ve airgap 496.
- make test-int: llmaas ve airgap 260 geçti, 4 atlandı (main'in 3 NOT_RUN'ı + benim models testim; o ayrıca gerçek bge-m3 ile geçti).
- smoke passed (mcp-search ve mcp-sql /healthz 200); lint temiz; alembic heads 05a; log kapısı 0.
Canlı yığın kanıtı:
- iki servis healthy; servis env'lerinde OBO_JWT_SECRET, DATABASE_URL, FERNET_KEY, SECRET_KEY, REDIS_URL sayısı 0;
- canlı konteynerlerde keşif çalışıyor; mcp-search için kesilmiş token mcp-sql'de reddediliyor; seed-sql-demo sonrası canlı run_sql çalışıyor.
C7 donmuş biçim bölümü PR dosyasında.
Kapılarda bulunan ve düzeltilen: tools konteynerine AGENT_DEMO_DB_PASSWORD gitmiyordu (belgelenen seed adımı başarısız olurdu); 03a GET eşitlik taraması (04a/08 deseniyle).
K-05a-0005 (1): unverified_on_behalf_of_claims'in yalnız yönlendirme amaçlı olduğu testle sabit: dict döner; sahte imzalı token okunur ama doğrulayıcı reddeder; tek kullanıcısı mcp_server_common.
İnceleyici için öncelikli bakılacaklar:
- forward_user zinciri ve aud listesi;
- egress.policy_http_client (SDK'ya pinned transport);
- sqlglot doğrulayıcısı (DELETE'in DB'ye gitmediği kanıtı);
- dar servis ayarları;
- invoke'un onaysız test çağrısı olması.
Not: worktree'de takip edilmeyen geçici .probe-gates.sh kaldı. Silme komutu güvenlik denetimine takıldı; commit'lenmedi.
Yığın down -v ile kapatılıyor.

### B-05a-0010 · 2026-10-29 17:53 · → koordinator · ACK
Paket: 05a   Cevap: K-05a-0007
Alındı. Worktree temiz, HEAD a55ca54. Review bitene kadar yeni commit yok; yığın kapalı. DUZELT ya da merge haberini bekliyorum.

### B-05a-0011 · 2026-10-29 19:28 · → koordinator · ACK
Paket: 05a   Cevap: K-05a-0008
DUZELT alındı (r1: BLOCKER 1, MAJOR 3, MINOR 1; KARARLAR "05a review r1 kararları"). Sıra: BLOCKER-1 (few_shots → tools çocuğu, 05a_0001 düzeltilir, C3 testi zinciri doğrular) → MAJOR-1 (`POST /api/v1/internal/obo/verify`, mcp-sql get_schema/run_sql öncesi, jti önbelleği) → MAJOR-2/3 (endpoint_url, başlık adı) → MINOR-1 (SQL matrisi, DB istatistiğiyle). Her biri önce kırmızı; yeni SHA ile PR-HAZIR.

### B-05a-0012 · 2026-10-29 20:31 · → koordinator · PR-HAZIR
Paket: 05a   Cevap: K-05a-0008
r1 düzeltmeleri hazır. SHA `6625b75d55fbc5fbd20e6b54bb516304a95883be` (a55ca54 üstünde 1 commit; 29 dosya +1254/-114; worktree temiz; baz 5c338ae). Ayrıntı ve bulgu→düzeltme→kanıt tablosu: state/pr/05a.md "Review r1 bulgu → düzeltme → kanıt".
- **BLOCKER-1:** `few_shots.tool_id` NOT NULL FK → tools, `project_id` yok (05a_0001 yerinde). `sql-context` zorunlu `tool_key` alıyor, 404 `tool_not_found`. `seed-sql-context --tool` (varsayılan mcp-sql; araç önce kayıtlı olmalı). C3 testi çocuk tablolarda FK zincirini kök tabloya kadar doğruluyor.
- **MAJOR-1:** `POST /api/v1/internal/obo/verify` eklendi. mcp-sql her istekte araçtan önce bu uçla doğruluyor; proje doğrulanmış iddiadan geliyor. Önbellek token ömrü boyunca, anahtar **token'ın tamamının özeti**: yalnız `jti` ile anahtarlansa, jti kopyalayan sahte token doğrulanmış cevabı alırdı.
  - Negatif: yanlış anahtar + doğru aud → 401; demo DB oturum sayacı değişmiyor.
  - Canlı konteynerde backend erişim logu sahte token için verify 401 gösteriyor.
- **MAJOR-2:** userinfo, query ve fragment → 400 `endpoint_url_not_allowed`. Kayıtta ve çağrıda reddediliyor; DB, audit ve yanıtta secret yok.
- **MAJOR-3:** RFC token + kapalı liste → 400 `header_name_not_allowed`. Kayıtta ve çağrıda reddediliyor; fixture sunucusuna istek 0.
- **MINOR-1:** yorumlar soyuluyor; set işlemlerinde yalnız SELECT dalı, `VALUES` yok. Kapalı fonksiyon listesi yeni kod `sql_function_not_allowed` veriyor. 26 satırlık matris birimde (bağlantı yok) ve gerçek zincirde (`pg_stat_database.sessions`) kanıtlı.
- **Kapılar:**
  - lint temiz.
  - `make test` airgap 556; llmaas 556 (aşağıdaki not).
  - `make test-int` iki profilde 296 geçti / 4 atlandı.
  - smoke passed; servis env yasak değişken 0; log kapısı 0; 05a migration turu temiz; `down -v`.
- **Dürüst notlar:**
  1. llmaas'ta ilk `make test` koşusu `Error 1` ile bitti. Düşen test kaydedilmedi; ardından üç koşu 556/556 geçti. Neden doğrulanmadı.
  2. Entegrasyon kırmızısı a55ca54 kopyasında 30 failed / 13 error. Sahte token ve matris testleri orada fixture imzasında düştü, anlamsal kırmızı değil. MAJOR-1'in anlamsal kırmızısı inceleyicinin probe'u.
  3. bge-m3 testi bu tur NOT_RUN.
- **Sapmalar** (PR'da gerekçeli; gerekirse tek satır geri alınır): kapalı başlık listesine `X-On-Behalf-Of` ve `X-Run-Id` eklendi; `VALUES` her yerde yasak.

### B-05a-0013 · 2026-10-29 20:32 · → koordinator · ACK
Paket: 05a   Cevap: K-05a-0011
Alındı: 6625b75 r2'de; review bitene kadar commit yok. Bundan sonra her kapı komutunun tam çıktısı `tee` ile dosyaya (oturum scratchpad'i), PR'da dosya yolu ve özet; yalnız son satırı tutan kapı koşusu yok.

### B-05a-0014 · 2026-10-29 21:26 · → koordinator · PR-HAZIR
Paket: 05a   Cevap: K-05a-0012
r3 (yalnız rebase): SHA `33a4b6269644f3a32f95d0c157e84be52db32020`, baz main e542947, 7 commit, worktree temiz.
- **Rebase:** tek çakışma `Makefile` `.PHONY` satırıydı; iki tarafın hedefleri (18 `test-samples` + 05a `seed-sql-demo` / `seed-sql-context`) duruyor. `uv.lock` main'de değişmemiş; `uv lock --check --offline` temiz, dosya değişmedi.
- **Kapılar:** tam çıktılar `state/pr/05a-r3-kapilar/` altında, tee ile dosyaya alındı.
  - lint temiz; `test-samples` 50 OK (5 opt-in atlandı).
  - `make test` 556/556 iki profilde.
  - `make test-int` 296 geçti / 4 atlandı iki profilde.
  - smoke passed; `alembic heads` 05a dahil.
- **Dürüst not:** llmaas `test-int` ilk koşuda `test_03a_schema` içinde takıldı. Migration turunun `DROP TABLE documents` adımı 13 dakika kilit bekledi; kilidi tutan, testlerin kendi bağlantısında açık kalmış bir işlemdi (`SELECT provider_projects`). O an hiçbir 05a testi koşmamıştı (alfabetik sıra). Kilit tablosu ve takılan koşunun çıktısı dosyada. Koşuyu durdurdum, ikinci koşu temiz. Neden doğrulanmadı; FOLLOWUP adayı (03a/03b/04a fixture'larından biri bağlantıyı işlem açıkken bırakıyor olabilir).
- `down -v` yapıldı. Ayrıntı: state/pr/05a.md "r3".

### B-05a-0015 · 2026-10-29 21:28 · → koordinator · ACK
Paket: 05a   Cevap: K-05a-0015
Alındı: 33a4b62 r3'te, kilit notu FOLLOWUP-90. Review bitene kadar commit yok. Merge sonrası HANDOFF, ardından 07 GOREV'i bu oturumda (OKUMA-TAMAM ile başlarım).

### B-05a-0016 · 2026-10-29 22:03 · → koordinator · HANDOFF
Paket: 05a   Cevap: K-05a-0016
05a MERGED (main 4f285b7; dal ucu 33a4b62). Worktree `.worktrees/feat/05a-tools-mcp` temiz, yığın `down -v` ile kapalı; worktree ve dal silinmedi (silme koordinatörde).
- **C7 dondu.** Biçim state/pr/05a.md "C7 donmuş biçim" ve r1 eklemeleri: `sql_function_not_allowed`, verify ucu kodları, `sql-context` gövdesinde `tool_key`.
- **Tüketicilere:**
  - 06a/07: araç adı `<tool_key>__<action>`; `tool_actions.needs_approval` / `enabled` / `max_calls_per_run` 05a'da yalnız saklanıyor, uygulaması 06a/07'de. `mcp_client.call(target, action, args, settings, caller=, run_id=, timeout_s=)`; kodlu `ToolCallError`.
  - Guard çağrı noktaları `tool.pre` / `tool.post` hazır, zorlama 05b/06a'da.
  - 18 ticket-desk: `mcp_server_common` (CallerCheck, Relay, OboVerifier) deseni.
  - Kimliği kendisi kullanan servis `POST /api/v1/internal/obo/verify` ile doğrular.
- **Açık:**
  - FOLLOWUP-90: test fixture'ında açık işlem → `test_03a_schema` kilidi.
  - llmaas `make test`'te bir kez görülen aralıklı `Error 1`: neden kayıtsız; bundan sonra tee ile yakalanır.
  - `kind=openapi` çağrısı 501, 05b'de.
  - `test_05a_models_few_shot_similarity` r1 sonrası gerçek ağırlıkla koşulmadı (NOT_RUN).
- **Kurulum sırası** (docs/araclar.md): `seed-sql-demo` → mcp-sql aracını kaydet → `seed-sql-context`.
Lease 07'ye geçiyor; aynı oturum.
