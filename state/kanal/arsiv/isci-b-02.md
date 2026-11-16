# Arşiv: isci-b · 02

state/kanal/isci-b.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### B-02-0001 · 2026-10-29 02:00 · → koordinator · ACK
Paket: 02   Cevap: K-02-0001 / B-01-0025
Kullanıcı bu oturumda devam talimatı verdi ("Burada devam et"); B-01-0025'teki "yeni oturum" notu geçersiz. Aynı oturum yeni kimlikle (ffcore-isci-b-02), lease ACTIVE. Okuma 01 başında tamamlandı (gruplar 1-8); ek olarak plan/02 tamamı, K-02-0000 taslağı (kurallar a-f, touch-zone), BLOCKERS 7/13/49 okundu.
GOREV alındı: worktree .worktrees/feat/02-langfuse-trace @ 070d8b0 doğrulandı (ağaç temiz). İlk iş LANGFUSE_INIT_* headless init doğrulaması (DRIFT-7), ardından LiteLLM Langfuse callback'inin v3 ile uyumu (DRIFT-13, U16); sonra state/pr/02.md → DURUM: PLANNED. Kod plan onayından sonra. Tüm derleme/up komutları FFCORE_VERSION=0.0.0-02.

### B-02-0002 · 2026-10-29 02:50 · → koordinator · DURUM
Paket: 02   Cevap: K-02-0001
DURUM: PLANNED. Plan: C:\ai_paycore\ffcore\state\pr\02.md (kabul 10 → test; ölçümler M1-M4; kod yok, worktree 070d8b0 temiz; deneme stack'i down -v).
Ölçümler (pinli imajlar, sahte değerler): M1 DRIFT-7 kapanabilir: LANGFUSE_INIT_* 3.120.0'da çalışıyor (proje + anahtar, verilen çift 200, yanlış 401, yeniden başlatmada idempotent, secret DB'de hash'li, logda 0). M2 DRIFT-13 kapanabilir: LiteLLM imajındaki v2 SDK (2.59.7) 'langfuse' callback'i v3 sunucuda iz üretiyor (worker şart): user, session_id, tags, usage stream + stream-dışı. M4: 'langfuse_otel' maliyeti 0 taşıyor.
**01 hatası (M3):** uzlaştırıcı fiyatı yalnız model_info'ya yazıyor; LiteLLM maliyeti yalnız litellm_params'taki input/output_cost_per_token'dan hesaplıyor. Bugün 01'le kurulan modellerde maliyet 0 (başlık yok, Langfuse costDetails {}). litellm_params'a konunca 3.9e-05 tam (Langfuse'ta da). 02 kabul 1 buna bağlı.
Karar isteyen 5 madde (planın sonunda, hepsi A önerili): S1 callback 'langfuse'; S2 01 fiyat hatası bu PR'da düzeltilir (touch-zone eki services/litellm_reconcile.py) ya da ayrı fix PR; S3 backend'e langfuse==4.15.1 (C sınıfı; OTLP exporter SafeOutboundClient dışında, iç host zorunlu, açılışta kontrol); S4 merkezi log stdlib logging (structlog değil); S5 varsayımlar. Cevap gelene kadar kod yok.

### B-02-0003 · 2026-10-28 22:52 · → koordinator · ACK
Paket: 02   Cevap: K-02-0002 / K-02-0003
Alındı: S1-S5 A, [C]; koşullar S2 (ayrı fix(01) commit'i, önce kırmızı, iki render kanıtı), S3 (1-5), S4 (DEBUG + exc_info testi) plana bağlı. Saat damgası düzeltildi: bundan sonra date çıktısı (önceki B-01-0013..B-02-0002 damgaları ileriydi). IMPLEMENTING. Dilim 1: langfuse==4.15.1 bağımlılığı + SDK 4.15.1 ↔ sunucu 3.120 ölçümü (backend'den iz + prompt API, OTel global provider, SDK dış çağrıları); uyumsuzsa dururum.

### B-02-0004 · 2026-10-28 23:01 · → koordinator · DURUM
Paket: 02   Cevap: K-02-0003 (S3 koşul 3-5)
Dilim 1: bağımlılık commit'i (langfuse==4.15.1; geçişli opentelemetry-sdk/exporter-otlp-proto-http 1.45.1, httpx 0.28.1, httpcore 1.0.9, requests 2.34.2, urllib3 2.8.0, protobuf 7.36.2, backoff, wrapt, googleapis-common-protos). Ölçüm (pinli yığın, sahte değerler, tools konteyneri, depo değişmedi):
- S3(3) backend SDK 4.15.1 ↔ sunucu 3.120.0 UYUMLU: iz (user_id, session_id, tags propagate_attributes ile), span + generation gözlemleri; prompt API create_prompt/get_prompt(label=production)/compile çalışıyor.
- Durma koşulu 1 temiz: LiteLLM çağrısı metadata existing_trace_id + parent_observation_id ile SDK span'inin altında; LiteLLM generation parent = bizim span, maliyet 3.9e-05.
- S3(4): SDK varsayılanda OTel global provider'ı kendi TracerProvider'ıyla değiştiriyor (önce Proxy, sonra TracerProvider). Langfuse(tracer_provider=<kendi>) verilince global değişmiyor (Proxy kalıyor) → tracing.py kendi provider'ını verir, test eder.
- S3(5): socket.getaddrinfo izlemesi: SDK yalnız langfuse-web'e (ve probe'un çağırdığı litellm'e) bağlandı; telemetri/sürüm kontrolü yok. SDK'nın varsayılan base_url'i bulut; LANGFUSE_HOST zorunlu (S3(1)) testi tracing dilimine.
Sıradaki: dilim 2 core/logging.py (FOLLOWUP-49), dilim 3 S2 fix(01), dilim 4 tracing/prompts/init/compose.

### B-02-0005 · 2026-10-28 23:32 · → koordinator · DURUM
Paket: 02   Cevap: K-02-0003 (S2)
Dilim 2: 068877a core/logging.py (FOLLOWUP-49; stdlib, ScrubFilter kök + uvicorn handler'ları, üçüncü taraf HTTP/telemetri logger'ları WARNING; 9 test DEBUG altında gerçek HTTP ile: sahte secret, Bearer, başlık değeri, exc_info logda 0). Birim 298 geçti.
Dilim 3: fix(01) commit'i — **iki 01 hatası** (aynı dosya, S2 kapsamı):
1) Fiyat (M3, onaylı S2): input/output_cost_per_token artık litellm_params'ta.
2) **YENİ:** POST /model/update v1.80.0'da 200 dönüp hiçbir şeyi değiştirmiyor (ölçüldü: hash, model, fiyat aynı kaldı). Yani 01'de değişen satır (model_id, fiyat, sağlayıcı anahtarı) LiteLLM'e hiç ulaşmıyordu ve her uzlaştırma aynı modeli 'updated' raporluyordu. 01'in test_01_8'i yalnız raporu kontrol ettiği için kaçtı (review'lar da). Düzeltme: PATCH /model/{id}/update (ölçüldü: litellm_params + model_info kalıcı uygulanıyor). Testler: test_01_8 artık LiteLLM'deki değeri ve ikinci koşu no-op'u kontrol ediyor (önce kırmızıydı); test_02_7 pre-fix dağıtım bir kez güncellenir, ikinci render değişiklik yok, gerçek çağrı maliyeti 3.9e-05 = models.pricing; test_01_6_api_key_encrypted_after_update (PATCH yolunda da anahtar şifreli). Entegrasyon 01+02: 22 geçti.
Ortam bulgusu (KAYIT-TALEBI önerisi, sahibi 12/smoke): yavaş makinede LiteLLM'in ilk 'prisma migrate deploy' denemesi 60 s'de zaman aşımına uğruyor, advisory lock'u bırakmıyor, sonraki denemeler kilidi alamıyor ve LiteLLM **yarım şemayla healthy** açılıyor (/key/info 500, tablo/kolon yok). Restart düzeltiyor. Healthcheck (/health/liveliness) bunu yakalamıyor; smoke'a LiteLLM şema/DB kontrolü (ör. /health/readiness ya da master key ile /key/info hash 404/200) önerilir.
Sıradaki: dilim 4 tracing.py, prompts.py, init.sh, compose, smoke.

### B-02-0006 · 2026-10-29 08:58 · → koordinator · DURUM
Paket: 02   Cevap: K-02-0004
Dilim 4 yazıldı, commit'lenmedi (tracing.py, prompts.py, init.sh, compose/env örnekleri, smoke, cli seed-prompts, Makefile; birim testler yeşil). Entegrasyon: test_02_1 tek başına geçiyor (iz Langfuse'ta 10,5 s'de, maliyet ve iç içelik doğru). Takıldığım yer: dosyanın tamamı koşunca bir test asılı kaldı. Gece arka plan koşusu 9 saat bitmedi; konteyneri sildim. Şüphe test_02_3: erişilemeyen hosta giden kapanış flush'ı. Doğrulanmadı. Şimdi faulthandler ile hangi çağrıda beklediğini ölçüyorum. Bir istek dönüşünü bekletirse bu ürün hatasıdır (kural c) ve düzeltilecek. Yığın 02-langfuse açık.

### B-02-0007 · 2026-10-29 09:38 · → koordinator · DURUM
Paket: 02   Cevap: K-02-0005
Asılmanın nedeni ölçüldü ve düzeltildi. Kök neden SDK'da (langfuse 4.15.1): LangfuseResourceManager public key başına tekil tutuluyor ve shutdown sonrası kayıttan silinmiyor. Aynı anahtarla ikinci Langfuse() durmuş eski örneği alıyor; eski host ve exporter kalıyor, kuyrukların tüketicisi yok. Bu yüzden flush içindeki queue.join() süresiz bekliyor (faulthandler: test_02_6 teardown → client.shutdown → resource_manager.flush → queue.join). Aynı nedenle test_02_3 dosya içinde kırmızıydı: down host'u hiç kullanılmıyordu. Süreçte tek init olduğu için üretimde tetiklenmez, ama yeniden init sessizce eski yapılandırmayı kullanırdı.
Düzeltme (tracing.py):
(1) shutdown_tracing durmuş örneği SDK kaydından siler; init_tracing önce kapatır; test_02_8_reinit_after_shutdown_is_fresh önce kırmızıydı.
(2) İstediğin açık sınırlar: OTLP export timeout=5 s; shutdown en çok SHUTDOWN_TIMEOUT_S=10 s bekler, aşarsa trace_shutdown_timeout ERROR. Testleri: test_02_3_shutdown_is_time_bounded (sonsuz bekleyen sahte shutdown 0,5 s'de döner) ve test_02_3_export_timeout_explicit. Not: bu iki test kodla aynı turda yazıldı, kodsuz kırmızı koşuları kaydedilmedi.
(3) Entegrasyon test_02_3 süre sınırını doğruluyor: Langfuse yokken çağrılar + kapanış 8,4 s; tam dosya 4/4, 22 s.
Ek bulgu: Langfuse açılışta zorunlu olunca 01 olay testlerinin app fixture'ı LANGFUSE_HOST yüzünden açılmıyordu (fail-loud doğru); test ayarlarına langfuse-web eklendi.
Önceki koşu (rebase öncesi): lint temiz; birim 324/324 her iki profil; entegrasyon 139/139 her iki profil.
Commit'ler main 17b0e75 üstüne rebase edildi: a0ad1ab, 34955aa, 73329e2, c166d43. Şimdi temiz yığında tam kapılar koşuyor: down -v, build, up, smoke, iki profil, log kapısı. Ardından Langfuse kapalıyken elle model çağrısı. 04a girince yeniden rebase ederim.

### B-02-0008 · 2026-10-29 10:06 · → koordinator · PR-HAZIR
Paket: 02   Cevap: K-02-0005
PR: state/pr/02.md · Branch feat/02-langfuse-trace · Baz main 17b0e75 · SHA 1d2f31f0ae695669443f0ff1ff2f95ffb865c878 · Sınıf [C] · ağaç temiz, 5 commit, 27 dosya +1760/-17.
DURUM: VERIFIED. Kabul 1-10 geçti. Temiz yığın (down -v, build, up): smoke passed; lint temiz; birim 330/330 iki profil; entegrasyon 140/140 iki profil (son SHA). Log kapısı: .env.test secret değerleri dört servisin logunda 0. Elle kontrol: langfuse-web kapalıyken model çağrıları 7/7 ve /healthz 200.
Kapılarda iki hata daha bulup düzelttim:
(1) Asılma: SDK'nın tekil kaynak yöneticisi yeniden kullanılıyordu. Şimdi kayıttan siliniyor; export 5 s, kapanış 10 s ile sınırlı.
(2) Log filtresi canlı yığında her uvicorn erişim satırını "Logging error" ile bozuyordu (args=None). Şimdi biçim korunuyor; önce kırmızı test vardı.
İnceleyici için öncelikli bakılacaklar:
- tracing.py SDK özel alanları (_resources, _instances; sürüm pinli);
- ScrubFilter yeni dalı;
- 01 düzeltmesi 73329e2 (PATCH ucu);
- Langfuse kapalıyken LiteLLM tarafında yalnız genel bir satır loglanıyor (FOLLOWUP önerisi PR dosyasında).
04a girince rebase yapıp yeni SHA bildiririm. Yığın 02-langfuse açık; review için kalsın mı, yoksa down -v mi?

### B-02-0009 · 2026-10-29 10:08 · → koordinator · ACK
Paket: 02   Cevap: K-02-0008
Yığın 02-langfuse down -v ile kapatıldı (konteyner 0, volume 0). İmajlar 0.0.0-02 duruyor. Review bitene kadar yeni commit yok; 04a rebase'i ve DUZELT bekleniyor.

### B-02-0010 · 2026-10-29 11:04 · → koordinator · ACK
Paket: 02   Cevap: K-02-0010 / K-02-0009
Alındı. Review'daki SHA'yı (1d2f31f) değiştirmemek için DUZELT gelene kadar rebase yapmıyorum. Ön kontrol (git merge-tree, dal değişmedi): main 132d383'e karşı beş dosyada çakışma var: Makefile, cli.py, main.py, pyproject.toml, uv.lock. uv.lock elle birleştirilmez; pyproject birleştirilip uv lock ile yeniden üretilir. DUZELT'te önce rebase, sonra:
- merkezi log yapılandırması ffcore.knowledge.worker girişine bağlanacak;
- K-02-0009 maddeleri yapılacak: erişim logunda query yok, ScrubFilter 08-lite tanıyıcıları + mask_value, tüm handler'lar filtreli, filtre istisna atmaz, süreç çıkışı sınırlı, export toplam bütçe.
Her biri önce kırmızı testle.

### B-02-0011 · 2026-10-29 12:08 · → koordinator · PR-HAZIR
Paket: 02   Cevap: K-02-0011
PR: state/pr/02.md ("Review r1 düzeltmeleri" bölümü) · Branch feat/02-langfuse-trace · Baz main fe0d434 · SHA 9ce1ecba3e981fc4501d8e437002520e4e588a61 · [C] · ağaç temiz.
Rebase:
- main fe0d434 üstüne alındı (132d383'ten sonra FOLLOWUP-84 de girdi).
- uv.lock `uv lock` ile yeniden üretildi; yalnız ekleme var, mevcut sürümler değişmedi.
- Çakışan dosyalarda iki tarafın değişikliği de korundu: main.py, cli.py, Makefile, pyproject.
MAJOR 1-5 ve worker log bağlantısı tamam. Her biri için önce kırmızı test yazıldı; tablo PR dosyasında.
- MAJOR-1/2: temizlik kayıt fabrikasında. Kurulum sırasından bağımsız; arq handler'ı da temiz kayıt görüyor. Hiçbir girdide istisna atmıyor; işlenemeyen kayıt log_scrub_failed sayacıyla geçiyor.
- MAJOR-3: kök neden OTel TracerProvider'ın atexit kapanışıydı. shutdown_on_exit=False yapıldı. Çocuk süreç gerçek SDK ve damlatan loopback sunucuyla kendiliğinden 5,7 s'de çıkıyor (önce 15 s'de öldürülüyordu).
- MAJOR-4: export daemon thread'de mutlak 5 s sınırla koşuyor (5,14 s'de FAILURE, reason=deadline). Takılı export varken yeni parti hemen düşüyor.
- MAJOR-5: yeni AccessLogMiddleware yöntem + yol + durum + süre yazıyor, uvicorn erişim logu kapalı. scrub 08-lite recognize + mask_value kullanıyor. Canlı yığında ham e-posta, TCKN ve query secret'ı beş serviste 0.
Kapılar (yeniden kurulmuş tools/backend/worker imajları):
- smoke passed, lint temiz, 02 testlerinin hepsi iki profilde geçti, log kapısı 0.
**Ortam bulgusu (main'de de var, 02 dışı):** make test 2 ve make test-int 21 başarısız + 4 hata. Aynı imaj ve komutla main fe0d434'te de birebir aynı küme (27 kimlik); 02 hiçbir kırmızı eklemiyor ya da gidermiyor.
- Nedenler: 03b .invalid DNS'i 5 s'de zaman aşımı; 04a Qdrant egress_dns_failed (qdrant profili kapalı); model ağırlığı yok.
- Main merge kapısında test-int yoktu. Sahibi 04a / 12; ayrı kayıt önerilir.
Dürüst not: ilk kapı koşusunda tools imajı bayattı (build tools profilini kapsamıyordu). Yeniden kurup baştan koştum; raporlanan sonuçlar yenilerden.
Yığın down -v ile kapatılıyor.

### B-02-0012 · 2026-10-29 12:12 · → koordinator · ACK
Paket: 02   Cevap: K-02-0013
Alındı. r2 bitene kadar yeni commit yok; yığın kapalı, imajlar 0.0.0-02 duruyor. DUZELT ya da merge haberini bekliyorum.

### B-02-0013 · 2026-10-29 13:00 · → koordinator · DURUM
Paket: 02   Cevap: K-02-0015 / Not (fix/main-test-gates)
r2 MAJOR-1 düzeltildi: commit 9cb9ddb, henüz PR-HAZIR değil.
- Kök neden: Logger.makeRecord extra= alanlarını fabrikadan sonra ekliyor.
- Düzeltme: makeRecord sarmalayıcısı, extra birleşiminden hemen sonra ve handler'dan önce standart dışı tüm öznitelikleri temizliyor: iç içe dict/list/tuple/set, anahtarlar dahil; 08-lite maskesi ve secret.
- Hata yolunda tüm extra'lar log_scrub_failed olur ve sayaç artar; ham değer kalmaz.
Testler (önce kırmızıydı; ham secret ve e-posta yazılıyordu):
- test_02_r2_m1_extra_fields_scrubbed: inceleyicinin senaryosu; önceden kurulan root handler ve sonradan eklenen handler yapılandırılmış formatter'la; secret, e-posta ve TCKN iç içe extra'da 0; msg/args biçimi korunuyor.
- test_02_r2_m1_extra_failure_leaves_no_raw_value.
Kapılar: lint temiz; make test iki profilde 435 geçti, yalnız DRIFT-85'in bilinen 2 hatası.
Fixture: notunuza göre bekliyorum. fix/main-test-gates main'e girince rebase edip Qdrant ACL fixture'ını uyumlu yapacağım (qdrant'ı ortamdaki listeye ekleme; ürün kontrolü aynı). Sonra Qdrant profili açık make test-int iki profil, sonra PR-HAZIR. Merge'ü bana haber verir misiniz?

### B-02-0014 · 2026-10-29 14:18 · → koordinator · PR-HAZIR
Paket: 02   Cevap: K-02-0016 / K-02-0015
PR: state/pr/02.md ("Review r2 düzeltmeleri") · Branch feat/02-langfuse-trace · Baz main 677d9e0 · SHA f4716909429872f7c457a6bc2e3ab1bd3c336cc9 · [C] · ağaç temiz.
r3 delta:
- rebase: 677d9e0'a temiz geçti, çakışma yok; uv lock --check tutarlı, lock değişmedi.
- extra alanları düzeltmesi: makeRecord sarmalayıcısı.
- Qdrant ACL fixture: qdrant artık ortamdaki listeye ekleniyor; ürün kontrolü aynı.
Testlerin hepsi önce kırmızıydı: extra testleri ham secret ve e-posta yazıyordu; ACL testi 4 setup ERROR veriyordu (TracingConfigError).
Kapılar (belgelenen komutla, --profile test --profile qdrant, temiz volume):
- make test: llmaas 439, airgap 439 geçti.
- make test-int: llmaas ve airgap 213 geçti, 3 atlandı (RUN_DNS_TESTS + iki RUN_MODEL_TESTS; main'in NOT_RUN'ları).
- smoke passed, lint temiz.
- Canlı PII/secret negatifi beş serviste 0; log kapısı 0.
Yığın down -v ile kapatılıyor.

### B-02-0015 · 2026-10-29 14:19 · → koordinator · ACK
Paket: 02   Cevap: K-02-0018
Alındı. r3 bitene kadar yeni commit yok; yığın kapalı. 05a GOREV'ini 02 merge'ünden sonra bekliyorum.

### B-02-0016 · 2026-10-29 14:50 · → koordinator · PR-HAZIR
Paket: 02   Cevap: K-02-0019
PR: state/pr/02.md ("Review r3 düzeltmesi") · Branch feat/02-langfuse-trace · Baz main 677d9e0 · SHA 0940628e04c7e2af26ec35f311c50e7211df9f7a · [C] · ağaç temiz.
r4 delta tek commit (0940628), rebase yok.
- Karar A uygulandı: extra'daki int/float değerler string karşılığıyla secret ve 08-lite tanıyıcılarından geçiyor; temizse tip ve değer korunuyor, kirliyse maskeli metin oluyor; bool muaf.
- Testler önce kırmızıydı (int TCKN ve sayısal secret ham yazılıyordu): test_02_r3_m1_numeric_extra_values_scrubbed (önceden/sonradan kurulan handler, iç içe int/float/tuple; metric 12, ratio 0.5, flag True korunur) ve test_02_r3_m1_clean_numbers_keep_type.
Kapılar (belgelenen komut, qdrant açık, temiz volume, yeniden kurulan imaj):
- make test: llmaas ve airgap 441 geçti.
- make test-int: llmaas ve airgap 213 geçti, 3 atlandı (main'in NOT_RUN'ları).
- smoke passed, lint temiz.
- Canlı PII/secret negatifi beş serviste 0; log kapısı 0.
Yığın down -v ile kapatılıyor.

### B-02-0017 · 2026-10-29 14:52 · → koordinator · ACK
Paket: 02 / 05a   Cevap: K-02-0022
Alındı; r4 bitene kadar yeni commit yok. 05a brief'ini ve C7'yi okudum; kod yok, claim yok. Plan için ön notlar (GOREV'den sonra ölçülecek, şimdilik doğrulanmadı):
- 13a demo DB hazır: data/samples/schema/{schema,seed,readonly_role}.sql, schema_descriptions.json, few_shots.json. services/mcp-sql ve mcp-search yalnız README.
- Yeni bağımlılıklar gerekecek: resmi mcp SDK (istemci + sunucu, streamable HTTP) ve sqlglot. İkisi de pyproject'te yok; C sınıfı, pinli sürüm ve U5 ölçümü (forward_user başlıkları oturum açılışında mı) planda olacak.
- few_shots embedding süreç içi bge-m3 ister; ağırlıksız testlerde FAKE_EMBED yolu kullanılacak, gerçek ağırlık testi models işaretli.
- Kabul kriterlerinden guardrail_mode/Superset/mcp_servers 05b'de (brief), 05a'da değil.
- forward_user için 03b'nin X-On-Behalf-Of imzası ve 04a'nın /kb/{id}/search ACL'si kullanılacak; iki kullanıcının eşzamanlı run testi 05a kabulü.
GOREV'i bekliyorum.

### B-02-0018 · 2026-10-29 15:22 · → koordinator · HANDOFF
Paket: 02   Cevap: K-02-0023
### 02 · ffcore-isci-b-02 · 2026-10-29 15:22
- Durum: MERGED (main 5f81457). Son SHA 0940628, review r1-r4. Ayrıntı state/pr/02.md; bulgu → düzeltme tabloları r1, r2, r3.
- Sonraki paketler için:
  - **06a.** `tracing.span(name)` + `run_attributes(run_id, user_id, project_id, tags=[agent_key, agent_version])`; LiteLLM isteğine `metadata=tracing.trace_context(run_id, user_id, tags)` (generation backend span'inin altına iner).
  - **06a.** `langgraph_handler()` langchain gelene kadar açık hata (`TracingConfigError`).
  - **06a.** Langfuse'a giden içerik maskelemesi 06a'nın (08 zinciri); 02 yalnız log maskeler.
  - **Hata tipleri.** `TracingConfigError` (açılış: yarım config ya da dış host); `PromptUnavailable` (503 `prompt_unavailable`).
  - **Prompt.** `PromptStore(client).get(name)`: 60 s önbellek; bayatsa `prompt_cache_stale`; önbellek yoksa açık hata. Seed: `make seed-prompts`.
  - **Log, her süreç.** Yeni bir süreç girişi (worker, CLI, 06a runtime) `configure_logging(settings)` çağırır. Temizlik kayıt fabrikasında ve `Logger.makeRecord`'da: msg/args/exception/stack/extra (iç içe, sayılar dahil) için secret + 08-lite PII maskesi.
  - **Log yazımı.** Kod yine de secret ya da upstream metni loglamaz; temizlik güvenlik ağıdır. Kendi `makeRecord`'unu ezen Logger alt sınıfı yazılmaz.
  - **Erişim logu.** `AccessLogMiddleware`: yöntem + yol + durum + ms; uvicorn erişim logu kapalı. `/mcp/{key}/` (05b) de buradan geçer.
  - **Test ayarı.** Uygulamayı açan test ayarı `ALLOWED_INTERNAL_HOSTS`'u değiştirmez, listeye ekler: aktif `LANGFUSE_HOST` açılışta bu listede aranır (04a ACL fixture örneği).
  - **İzleme / 12.** Langfuse kapalıyken LiteLLM tarafında yalnız v2 SDK'nın genel satırı loglanıyor; uyarı kuralı önerisi PR'da (FOLLOWUP). FOLLOWUP-82 (LiteLLM yarım şema) açık.
- Ortam: 02-langfuse yığını kapalı (down -v); `0.0.0-02` imajları duruyor, silinebilir. Worktree .worktrees/feat/02-langfuse-trace temiz.
Lease: 02 kapandı; aynı oturum 05a'ya geçti (başlık güncellendi).
