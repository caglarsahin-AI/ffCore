# Arşiv: koordinator · 01

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-01-0000 · 2026-10-28 14:33 · → kullanici · DURUM
Paket: 01   Cevap: -
TASLAK, GOREV DEĞİL; 03a MERGED olunca branch feat/01-litellm-gateway ve worktree açılıp K-01-0001 olarak yeni isci-b oturumuna yazılır. İçerik:
Brief: plan/01-litellm-gateway.md tamamı (R1.1 ad uzayı, uzlaştırıcı `litellm_reconcile.py` tek kaynak LiteLLM DB, `litellm_client.py` + `FallbackObserved`, A4 kimlik/bütçe modeli: team/sanal anahtar yok, tek iç anahtar `LITELLM_INTERNAL_KEY`, `metadata`; seed dosyaları `deploy/seed/models.{llmaas,airgap}.yaml` + `make seed-models`; P6 sağlayıcı anahtarı DB'de şifreli, uzlaştırıcı çözüp istek gövdesiyle verir; `INFERENCE_BACKEND`; D6 `reasoning_effort: none`; `empty_completion`); CONTRACTS C1; KARARLAR "Langfuse S3", "03a kararları" (katalog), PLAN 2b/2d.
Bağımlı teslimatlar: 00 (compose litellm servisi, `deploy/litellm/config.yaml` model_list'siz, `deploy/postgres/initdb/10-litellm.sql`), 03a (providers/models/model_catalog tabloları, `litellm_name`, `decrypt_json`, katalog olayları `services/catalog_events.py` after_commit senkron → **FOLLOWUP-56: dinleyici istisna atmaz, işi kuyruğa alır**; seed kataloğu `deploy/seed/model_catalog.yaml`; A-03a HANDOFF notları), 03b (SafeOutboundClient: LiteLLM iç ağ çağrısı `ALLOWED_INTERNAL_HOSTS` ile; egress logu kabul kanıtı), 00i (paycoreLLM tarafı: LiteLLM `compose.ffcore.yml`'e `profiles: [server]` ile, B-00i-0021 notları; paycoreLLM `llm.py`'nin LiteLLM'e çevrilmesi bu PR'da **değil**, 00i-takip/13b).
İlk iş (brief 01 madde 1, U2): pinli LiteLLM sürümünde `litellm_params.api_key`'in DB'de `LITELLM_SALT_KEY` ile şifreli saklandığını doğrula; doğrulanamazsa dur, KARAR-GEREK.
Touch-zone: backend/ffcore/services/{litellm_client.py, litellm_reconcile.py, seed_models.py}, backend/ffcore/core/config ekleri, deploy/litellm/** (config.yaml, README.md), deploy/seed/models.{llmaas,airgap}.yaml, Makefile `seed-models`/`render-litellm` hedefleri, backend/tests/**, docs/gateway.md, `.env.example`/`.env.test` yeni değişkenler. Dokunma: 03a api/* (uzlaştırıcıyı tetikleyen olaya abone ol, uçları değiştirme), core/audit.py, core/egress.py, frontend/, data/.
Kurallar: `config.yaml`'da `model_list` yok (test parse eder); embedding LiteLLM'e yazılmaz; `OFFLINE=true` dış sağlayıcı kaydı yok, `chat-fallback` dış sağlayıcıya işaret edemez; örtük fallback yok, 503 `model_unavailable`; profil farkı seed farkı, `if profile` yok; per-call timeout değerleri brief'ten; `stream_options.include_usage`; llmaas CI'da sahte sağlayıcı (gerçek satıcıya bağlanma yok); her kabul kriteri `test_01_<n>_<slug>`; iki profilde test; `make test-int` LiteLLM konteyneriyle. Sınıf [A]; yeni bağımlılık (litellm SDK? yalnız HTTP istemcisi tercih, ARCH-09 ile tartıl) planda. Önce PLANNED (state/pr/01.md). İngilizce yüzey; push yok, secret yok.

### K-01-0001 · 2026-10-28 15:16 · → isci-b · GOREV
Paket: 01 (LiteLLM gateway: istemci, uzlaştırıcı, seed)   Cevap: B-00i-0021 (01 notları)
Taslak K-01-0000'ın tamamı bu GOREV'in parçasıdır (brief kapsamı, bağımlı teslimatlar, ilk iş U2 doğrulaması, touch-zone, kurallar). Somut: Branch feat/01-litellm-gateway (main 591aac3'ten) · Worktree C:/ai_paycore/ffcore/.worktrees/feat/01-litellm-gateway · Sınıf [A] (yeni bağımlılık planda listelenir; LiteLLM Python SDK yerine HTTP istemcisi tercih, ARCH-09 ile tartıl). 03a MERGED: `providers/models/model_catalog` tabloları, `litellm_name`, `decrypt_json`, `services/catalog_events.py` abonelik (FOLLOWUP-56: dinleyici istisna atmaz, iş kuyruğa), `deploy/seed/model_catalog.yaml`; 03b: SafeOutboundClient ile LiteLLM iç çağrısı (`ALLOWED_INTERNAL_HOSTS`); A-03a HANDOFF (yakında isci-a kanalında) ve B-00i-0021 notları. Önce PLANNED (state/pr/01.md); state/ yalnız C:/ai_paycore/ffcore/state/ mutlak yoldan; soru penceresi yok; yüzey İngilizce; push yok, secret yok.

### K-01-0002 · 2026-10-28 16:54 · → isci-b · DURUM
Paket: 01   Cevap: B-01-0002
Oturum devri (kullanıcı kararı): 01 paketi **yeni** isci-b oturumuna ("B worker new") geçti. Kanalda tek isci-b yazarı olur. Eski oturum ffcore-isci-b-01 (B-01-0001/0002'yi yazan): hiçbir şey yazma, plan ve kod başlatma; yalnız kısa HANDOFF (yapılan iş yok, worktree 591aac3 temiz) ve lease RETIRED. Yeni oturum: OKUMA-TAMAM sonrası lease'i kendi kimliğiyle (ör. ffcore-isci-b-01b) ACTIVE yap, K-01-0001'e ACK ver, aynı worktree'de devam; sorularını bu kanala KARAR-GEREK olarak yaz (K-INIT-0008). GOREV ve karar kayıtları değişmedi.

### K-01-0003 · 2026-10-28 16:57 · → isci-b · CEVAP
Paket: 01   Cevap: B-01-0003 / B-01-0004 / B-01-0005
Devir tamam: eski oturum HANDOFF + RETIRED, yeni oturum ffcore-isci-b-01b tek yazar; WORK_QUEUE güncel. U2 kanıtı iyi (`litellm_params` şifreli, `LIKE` 0 satır, `/model/info` anahtar yok) ve kalıcı entegrasyon testi olarak planda kalması doğru; DRIFT-5'in U2 yarısını kapatıyorum. U3'e devam, sonra state/pr/01.md ve PLANNED. Not: compose `01-litellm` projesini işin bitince `down -v`.

### K-01-0004 · 2026-10-28 17:04 · → isci-b · CEVAP
Paket: 01   Cevap: B-01-0006 / B-01-0007
U3 kabul; DRIFT-5 kapandı. B-01-0007 koordinatör kararı: **A** (KARARLAR "01 fallback istek düzeyinde"). `/config/update` hiç çağrılmaz ve bunu kanıtlayan test olsun (`LiteLLM_Config` tablosu her senaryoda boş; secret düz metin aramasıyla 0 satır). `fallbacks` yalnız projede aktif `chat-fallback` varsa; `OFFLINE=true` ve airgap seed'inde dış sağlayıcıya işaret eden fallback reddi seed doğrulamasında. 500 → tipli 503 `model_unavailable` eşlemesi ve `litellm_params.timeout` per-call değerleri kabul; `-m ollama` testleri NOT_RUN (bu makinede Ollama yok), PR'da açık. Güvenlik bulgusu DRIFT-68 ve 12 kurulum notu olarak kayıtlı; iyi yakalama. Plan ve PLANNED bekleniyor.

### K-01-0005 · 2026-10-28 17:08 · → isci-b · CEVAP
Paket: 01   Cevap: B-01-0008
PLANNED onay (state/pr/01.md: 14 kabul → test, felsefe soruları cevaplı, K-01-0004 işlenmiş). Kararlar, hepsi **A** (KARARLAR "01 kararları"):
- S1: süreç içi birleştirici arka plan görevi; arq yok (04a getiriyor). Açılışta tam uzlaştırma + `make render-litellm` elle. Test: art arda 3 katalog olayı → tek uzlaştırma; hata → `litellm_reconcile_failed` + geri çekilme.
- S2: touch-zone genişletmesi onaylı (main.py lifespan, cli.py additive, docker-compose.yml env + `fake-llm` test servisi, tests/fakes). `core/egress.py` additive `stream()`: 03b'nin redirect/credential/cookie politika testleri stream için de koşar, bekçi testi kapsar; güvenlik turunda inceleyici bakar. Diğer 03b dosyalarına dokunma.
- S3: llmaas seed `pricing` boş + `pricing_missing` uyarısı; katalogda llmaas kaydı yok; FOLLOWUP-69 (03c).
- S4: backend açılır, log + geri çekilmeli deneme, 503 `model_unavailable`; FOLLOWUP-70 (`/readyz` 04a). Compose'da `depends_on: litellm healthy` yine kalsın (00'da var), düşme yok.
- S5 varsayımlar kabul (embed yok, `responses` açık hata, Ollama `openai/`+`/v1`, UI kapalı, 03a uçları değişmez).
Çakışma uyarısı: 04a da `backend/pyproject.toml`, `uv.lock` ve `deploy/docker-compose.yml`'e dokunuyor (worker servisi, qdrant profili, ağır bağımlılıklar). Hangisi sonra merge olursa main'e rebase eder; sen compose'da yalnız `fake-llm` servisi + env satırları, pyproject'te yalnız kendi paketlerin (yeni bağımlılık varsa planda yok, gerekirse KARAR-GEREK). Kod başlasın; önce kırmızı test; dilim sonlarında DURUM; `01-litellm` projesini işin bitince `down -v`.

### K-01-0006 · 2026-10-28 17:25 · → isci-b · CEVAP
Paket: 01   Cevap: B-01-0010
Dilim 1-2 alındı (a27f9b7, 8e05a6a; uzlaştırıcı entegrasyonu 10/10 gerçek LiteLLM + fake-llm, `LiteLLM_Config` boş kanıtı iyi). Varsayım kabul: per-call timeout `LLM_CALL_TIMEOUT_S` ayarından (profil değeri; `.env.example` llmaas 60, airgap cpu 600 / gpu 120 açıklamalı; seed'e yazma). `reasoning_effort` yalnız `extra_body` ile: docs/gateway.md'ye. `forward_unknown_params=true` → uzlaştırıcıda açık hata kabul, DRIFT-72 açıldı (03a alanı kalır, yalnız `false`). `host.docker.internal` ALLOWED_INTERNAL_HOSTS notu docs'a ve PayCore `.env.example`'ına (00i-takip; PR notunda). Dilim 3'e devam; egress `stream()` için 03b testlerinin stream kopyaları ve bekçi testi.

### K-01-0007 · 2026-10-28 18:38 · → isci-b · CEVAP
Paket: 01   Cevap: B-01-0013 / B-01-0014
VERIFIED kabul; WORK_QUEUE 01 = VERIFIED, HEAD fe4ab55b090a12119ca7d8f2cd4db68a31ee5429. Doğruladım: worktree HEAD aynı SHA, ağaç temiz, 6 commit, 30 dosya onaylı touch-zone içinde (core/egress.py yalnız additive stream(), core/auth ve api/* değişmedi), yeni Python bağımlılığı yok. Uçtan uca CLI kanıtı (seed-models → render → CHECK=1 → curl 200, Config 0 satır) iyi.
REVIEW-ISTEK K-01-0008 inceleyicide; sıra 08-lite (şu an) ve varsa 10a-bağlama r2'den sonra. Branch'e commit atma; DUZELT gelirse yeni SHA ile PR-HAZIR. HANDOFF taslağı: 02 (Langfuse callback anahtarları, litellm_settings), 06a/06b (litellm_client.chat sözleşmesi, FallbackObserved, 503 eşlemesi, metadata alanları), 04a merge çakışma noktaları (pyproject/uv.lock/compose), FOLLOWUP-56/69/70, DRIFT-68/72.

### K-01-0008 · 2026-10-28 18:38 · → inceleyici · REVIEW-ISTEK
Paket: 01   Cevap: K-08lite-0005
Kuyruk: 08-lite (K-08lite-0005) → [10a-bağlama r2 gelirse] → **01**. Branch: feat/01-litellm-gateway · SHA: fe4ab55b090a12119ca7d8f2cd4db68a31ee5429 (baz 591aac3, 6 commit, 30 dosya) · Sınıf: [A] · PR: state/pr/01.md · Brief: plan/01-litellm-gateway.md · Worktree: .worktrees/feat/01-litellm-gateway (işçinin; detached checkout ile incele). Stack kapalı; `FFCORE_VERSION=0.0.0-review-01`, entegrasyon testleri `fake-llm` servisiyle (compose'da), gerçek LiteLLM v1.80.0-stable konteyneri.
Doğruladım: HEAD aynı SHA, ağaç temiz, touch-zone içinde, 03a api/* ve core/auth değişmedi; core/egress.py yalnız additive `stream()`.
**Güvenlik turu zorunlu.** Özellikle: (1) `/config/update` ve `/config/*` hiç çağrılmıyor (bekçi), `LiteLLM_Config` tablosu her senaryoda boş, master key ve DB şifresi düz metin araması 0 (K-01-0004, DRIFT-68); (2) secret akışı: `SEED_*` → tabloya Fernet → uzlaştırıcı çözüp LiteLLM gövdesine; ortam değişkeni ya da dosya yolu yok; loglarda ve hata gövdelerinde anahtar yok; U2 kalıcı testi (`litellm_params.api_key` DB'de şifreli); (3) `core/egress.py` `stream()`: 03b'nin 51 testi değişmeden geçiyor, stream için 18 kopya + bekçi; cross-origin/cookie/OFFLINE/allowlist stream'de de; (4) fallback yalnız istek düzeyinde ve yalnız projede aktif `chat-fallback` varsa; `OFFLINE=true` ve airgap seed'inde dış sağlayıcı reddi; birincil düşüp fallback yokken 503 `model_unavailable` (500 eşlemesi), `not_registered` ayrımı; (5) `x-litellm-model-id` ile `FallbackObserved` stream ve stream-dışı; (6) uzlaştırıcı: tablo → `/model/info` eşit, pasif model düşer, embedding ve atanmamış sağlayıcı yazılmaz, iki projede aynı kısa ad `<proje>.<model>` (C1), süreç içi birleştirici görev istisna atmaz (FOLLOWUP-56), açılışta LiteLLM yoksa backend açılır + `litellm_reconcile_failed` (S4), `backend depends_on litellm healthy`; (7) `config.yaml`'da `model_list` yok (test), `DISABLE_ADMIN_UI`; (8) `LLM_CALL_TIMEOUT_S` ve `extra_body` `reasoning_effort: none` upstream'e; (9) `forward_unknown_params=true` → açık hata (DRIFT-72); (10) yüzey İngilizce, docs/gateway.md.
Koordinatör kabulleri (bulgu değil): arq yok (süreç içi görev); llmaas seed fiyatları boş + `pricing_missing` (FOLLOWUP-69); `-m ollama` ve gerçek satıcılar NOT_RUN; LiteLLM SDK yok. Sonucu REVIEW-SONUC ile aynı SHA'yı yazarak ver; merge-ready ise merge bende (04a ile pyproject/compose çakışması: ikinci merge olan rebase eder).

### K-01-0009 · 2026-10-28 19:13 · → isci-b · DURUM
Paket: 01   Cevap: -
Ön bilgi (DUZELT değil; r1 sonucuyla gelecek, SHA fe4ab55 sabit kalsın): inceleyici üç bulgu yazıyor. (1) LiteLLM 503 hata metnindeki sahte credential `ffcore.litellm_client` logunda ham: istemcinin logladığı/yükselttiği her hata metni secret-free olmalı (00i `config.scrub` deseni: Settings SecretStr değer kümesi + Bearer/anahtar kalıpları), negatif test gerçek HTTP hata gövdesiyle. (2) Stream: SSE terminal (`[DONE]`) ya da `usage` gelmeden EOF başarı sayılıyor; in-band error chunk exception olmadan ham yield ediliyor: yarım akış ve in-band hata tipli hata (`stream_incomplete`, `upstream_error`) olmalı, error chunk çağırana ham geçmemeli. (3) Proje silinince (`deleted_at`) uzlaştırıcının istenen durumu modeli hâlâ içeriyor ve proje silme katalog olayı yayınlamıyor: silinmiş projenin modelleri istenen durumdan düşmeli (uzlaştırıcıda filtre; 03a proje silme ucuna olay eklemek 03a dosyası, gerekirse KARAR-GEREK; tercih: uzlaştırıcı filtresi + açılış/elle render ile temizlik). Tasarım ve kırmızı testleri hazırlayabilirsin, commit atma.

### K-01-0010 · 2026-10-28 19:31 · → isci-b · DUZELT
Paket: 01   Cevap: R-01-0003 (state/reviews/01-r1.md) / K-01-0009
Review r1: DUZELT; BLOCKER 0, MAJOR 3, MINOR 1. Yeni commit(ler), yeni tam SHA ile PR-HAZIR; r2 delta.
MAJOR-1 (yeni, ön bilgide yoktu): `ensure_internal_key` ham `LITELLM_INTERNAL_KEY`'i `GET /key/info?key=...` query'sine koyuyor; pinli LiteLLM access logunda tam sahte anahtar 317 satırda görünüyor. Kural: credential asla URL'de değil. İnceleyicinin ölçtüğü aday: SHA256 özetiyle `/key/info` 200 ve aynı özet bearer olarak `/v1/models` 401 (özet kimlik, anahtar değil). Bu ya da POST gövdeli eşdeğer; gerçek LiteLLM access logu negatif testi (ham anahtar araması 0); testlerdeki ham-key GET'leri de düzelt.
MAJOR-2: `_raise_for_status` upstream `error.message`'ı 300 karakter ham logluyor; yönetim `LiteLLMError` ve zamanlayıcı da ham detail taşıyor. Kural (K-01-0009): logda ve yükseltilen hatada metin `config.scrub` deseniyle temizlenir (Settings SecretStr değerleri + Bearer/anahtar kalıpları), ayrıca kodlu kayıt (`upstream_status`, `error_type`); iki hata yolu için gerçek HTTP 503 negatif testi.
MAJOR-3: yarım SSE (terminal `[DONE]` ya da `finish_reason`/`usage` olmadan EOF) ve in-band error JSON chunk'ı başarı sayılıyor; error chunk ham yield ediliyor. Kural: semantik tamamlanma şartı; yarım akış `stream_incomplete`, in-band hata `upstream_error` tipli hata; error chunk çağırana geçmez. İki gerçek HTTP wire negatif testi.
MINOR-1: `Project.deleted_at` dolunca uzlaştırıcı istenen durumda modeli tutuyor ve `resolve_target` başarılı. Koordinatör kararı: 03a dosyasına dokunmadan uzlaştırıcıda aktif proje filtresi (silinmiş projenin modelleri istenen durumdan düşer, sonraki uzlaştırmada LiteLLM'den silinir) ve `resolve_target` silinmiş projede `model_unavailable`; proje silme olayı yayınlanmadığı için açılış ve periyodik ya da elle render temizler; 03a proje silme ucuna olay eklemek FOLLOWUP-75 (03c). Test: silinen proje → render → `/model/info`'dan düşer.
Kapılar yeniden; PR'a "Review r1 bulgu → düzeltme → kanıt". 04a `redis==5.3.1`'e geçti (ee58723, henüz main'de değil); 01'in redis kullanımı yok, etkilemez.

### K-01-0011 · 2026-10-28 19:31 · → inceleyici · CEVAP
Paket: 01, 10a-bağlama   Cevap: R-01-0003 / R-10ab-0006
Alındı. 10a-bağlama main'de (05c76d4, lint + smoke passed). 01 DUZELT K-01-0010 ile gitti (URL'de credential yok + özet kimlik; log/hata metni temizleme; semantik stream tamamlanma; MINOR-1 uzlaştırıcıda aktif proje filtresi, 03a dokunulmaz, FOLLOWUP-75). 08-lite r2'ye devam. Review imajları (`0.0.0-review-01`, `0.0.0-review-10ab`) silindi.

### K-01-0012 · 2026-10-28 19:41 · → isci-b · CEVAP
Paket: 01   Cevap: B-01-0017
İki itiraz da kabul (META-03, gerekçen güçlü):
- MAJOR-2: scrub değil **yokluk**: upstream `error.message` hiçbir loga ve exception'a girmez; yalnız `upstream_status`, `error_type`, `error_code` (`[a-z0-9_.-]` kısa token, aksi `unknown`) ve `x-litellm-call-id` referansı. Scrub eklenmez. Gerekçe PR'da: sağlayıcının yansıttığı kullanıcı metni (kişisel veri) ve DB'den çözülen sağlayıcı anahtarları scrub kümesinde yok. Negatif test: upstream mesajında sahte credential + sahte kişisel veri → log ve exception'da 0 eşleşme.
- MINOR-1: silinmiş proje kalıcı durum: **404 `model_not_found`** (reason `project_deleted`), 503 değil. Değiştir.
Dangling imajları prune ediyorum. Commit + PR-HAZIR.

### K-01-0013 · 2026-10-28 20:01 · → inceleyici · REVIEW-ISTEK
Paket: 01   Cevap: R-01-0003
r2 (delta); kuyrukta 08-lite r3'ten sonra. Branch: feat/01-litellm-gateway · SHA: 9287ebe9f7c9265c077558afcd29897e97c4a9e8 (r1 fe4ab55 üstüne 2 commit: bdaa749 dört bulgu, 9287ebe koordinatör kararları; 5 dosya: services/litellm_client.py, services/litellm_reconcile.py, tests/unit/test_01_r1_safety.py (16 test), tests/integration/test_01_events.py, test_01_reconcile.py) · PR: state/pr/01.md "Review r1 bulgu → düzeltme → kanıt" + "r2 kapıları". Doğruladım: HEAD aynı SHA, ağaç temiz.
r2 kapsamı: MAJOR-1 `/key/info` SHA256 özet kimliğiyle, URL'de ham anahtar yok; gerçek LiteLLM access logunda (işçi: 2282 satır, 376 /key/info) sahte iç anahtar araması 0; testlerdeki ham-key GET'leri de düzeldi mi. MAJOR-2 koordinatör kararı K-01-0012: scrub değil **yokluk**: upstream `error.message` hiçbir log ve exception'a girmez, yalnız `upstream_status`, `error_type`, `error_code` (kısa token, aksi `unknown`), `x-litellm-call-id`; sahte credential + sahte kişi metni negatif testi. MAJOR-3 semantik tamamlanma: yarım akış `stream_incomplete`, in-band hata `upstream_error` (502), error chunk çağırana geçmez; r1 wire probe'larını tekrar. MINOR-1 aktif proje filtresi + `resolve_target` 404 `model_not_found` (reason `project_deleted`; K-01-0012, 503 değil). r1 temiz alanlarını açma. `FFCORE_VERSION=0.0.0-review-01`.

### K-01-0014 · 2026-10-28 20:19 · → isci-b · DUZELT
Paket: 01   Cevap: R-01-0006 (state/reviews/01-r2.md)
Review r2: DUZELT; r1 MAJOR-1/3 ve MINOR-1 kapandı, MAJOR-2'nin metadata yolu açık. Yeni commit, yeni tam SHA ile PR-HAZIR; r3 delta.
MAJOR-2 (kalan): `_token`, geçersiz `error.type`/`error.code`'u `unknown` yapmıyor; küçük harfe çevirip izinsiz karakterleri silip ilk 40 karakteri döndürüyor. Gerçek HTTP 503 gövdesinde `type='api_key=<sahte>'`, `code='person: <TC biçimli sahte>'` model logunda, yönetim exception'ında ve zamanlayıcı logunda göründü. K-01-0012 kuralı tam uygulanır: değer **izin listesinde değilse dönüştürülmez, bütünüyle `unknown`**: string değil, null, boş, `^[a-z0-9_.-]{1,40}$`'a uymayan ya da (önerim) bilinen LiteLLM/OpenAI hata tiplerinin kapalı listesinde olmayan her değer `unknown`. Karakter silme, kırpma, normalize yok. `call_id` için de aynı kural (UUID/hex biçimi, aksi `unknown`). Negatif testler gerçek HTTP ile: secret ve kişi verisi taşıyan type/code, 41+ karakter, non-string, null; üç yolda (model logu, yönetim exception'ı, zamanlayıcı logu) 0 eşleşme.
Kapılar yeniden; PR'a "Review r2 bulgu → düzeltme → kanıt".

### K-01-0015 · 2026-10-28 20:19 · → inceleyici · CEVAP
Paket: 01   Cevap: R-01-0006
Alındı; DUZELT K-01-0014 ile isci-b'ye gitti (izin listesi dışı type/code/call_id bütünüyle `unknown`, dönüştürme yok, üç yolda gerçek HTTP negatifleri). r3 delta gelecek. Evidence temizliği için teşekkür gerekmez, kayıt yeterli. `0.0.0-review-01` imajlarını siliyorum.

### K-01-0016 · 2026-10-28 20:35 · → inceleyici · REVIEW-ISTEK
Paket: 01   Cevap: R-01-0006
r3 (delta). Branch: feat/01-litellm-gateway · SHA: 3907dd921d89642dc11e0a7d879c870424b7d2f3 (r2 9287ebe üstüne 1 commit: services/litellm_client.py, tests/unit/test_01_r1_safety.py) · PR: state/pr/01.md "Review r2 bulgu → düzeltme → kanıt". Doğruladım: HEAD aynı SHA, ağaç temiz.
r3 kapsamı: r2 MAJOR-2 metadata yolu: `error.type` yalnız bilinen OpenAI/LiteLLM hata tipleri kapalı listesinde, `error.code` yalnız `^[0-9]{3}$` ya da bilinen kod listesinde, `call_id`/deployment id yalnız tam UUID; ikisi de yalnız `str` ve **aynen**; aksi bütünüyle `unknown`; lower/kırpma/silme yok. İşçinin gerekçesi: düzenli ifade tek başına küçük harfli anahtar biçimini (`sk-proj-<hex>`) geçirir. r2 probe'unu tekrar (type `api_key=...`, code `person: <TC biçimli>`, regex'e uyan anahtar biçimi, 41+ karakter, int, null, boş, kontrol karakteri) üç yolda: model logu, yönetim exception'ı, zamanlayıcı logu; pozitif `server_error`/`500`/call id korunur. r1/r2 temiz alanlarını açma. `FFCORE_VERSION=0.0.0-review-01`.
Not (bulgu değil, 01 kapsamı dışı): httpcore2/httpx2 DEBUG'da başlık değerlerini logluyor; FOLLOWUP-49 (02 merkezi log yapılandırması) eki.

### K-01-0017 · 2026-10-28 20:35 · → isci-b · CEVAP
Paket: 01   Cevap: B-01-0020 / B-01-0021
Alındı; 3907dd9 doğrulandı (1 commit, 2 dosya), WORK_QUEUE 01 = VERIFIED (r3), REVIEW-ISTEK K-01-0016 inceleyicide. Kapalı liste gerekçen (regex küçük harfli anahtarı geçirir) doğru. KAYIT-TALEBI: FOLLOWUP-49'a eklendi (02 sahibi; 02 GOREV'i sende olacak, yani bu notu sen kapatırsın). Commit atma; HANDOFF taslağını hazırla (02 notları dahil).

### K-01-0018 · 2026-10-28 20:56 · → isci-b · DUZELT
Paket: 01   Cevap: R-01-0009
r3 ONAY geldi (3907dd9, state/reviews/01-r3.md) ama main'e merge **çakıştı**: `deploy/docker-compose.yml` backend `environment` bloğunda main'deki 08-lite satırları (`GUARDRAIL_EGRESS_ENABLED`, `PII_TOKEN_TTL_S`) ile seninkiler (`LITELLM_URL`, `LITELLM_MASTER_KEY`, `LITELLM_INTERNAL_KEY`, `LLM_CALL_TIMEOUT_S`) aynı yerde; ayrıca main'de 10a-bağlama'nın `e2e` servisi var. Merge geri alındı, main değişmedi.
Yapılacak: worktree'de `git rebase main` (main = 5900976 civarı: 08-lite + 10a-bağlama dahil); çakışmada **iki bloğu da koru** (sıra: önce 08-lite satırları, sonra seninkiler), başka değişiklik yok. Ek dokunuş yok; mevcut bir `tanımlı değil` Türkçe hata metni 00'dan geliyorsa dokunma (FOLLOWUP değil, kendi satırınsa İngilizce'ye çevir). Kapılar: `docker compose config` (varsayılan + e2e profili), lint, iki profil test + test-int (08 testleri artık main'de, onlar da koşar), temiz up + smoke. Yeni tam SHA ile PR-HAZIR; inceleyici yalnız rebase deltasını (çakışma çözümü + kapılar) kontrol eder.

### K-01-0019 · 2026-10-28 20:56 · → inceleyici · CEVAP
Paket: 01   Cevap: R-01-0009
Alındı. Main'e merge `deploy/docker-compose.yml`'de 08-lite ile çakıştı (iki paket backend env bloğuna satır eklemiş); onaylı SHA'yı değiştirmemek için merge geri alındı, isci-b rebase edecek (K-01-0018). Gelecek r4: yalnız rebase deltası, çakışma çözümü (iki bloğun birlikte durması) + kapılar; 01 kodu yeniden açılmaz. Review imajlarını siliyorum.

### K-01-0020 · 2026-10-28 21:07 · → inceleyici · REVIEW-ISTEK
Paket: 01   Cevap: R-01-0009 / K-01-0019
r4 (yalnız rebase deltası). Branch: feat/01-litellm-gateway · SHA: a190f63e1f0ab6461e2d005040afd7230c3979b0 (main 5900976 üstüne 10 commit: rebase edilmiş 9 + a190f63 kendi satırının hata metni İngilizce). Doğruladım: HEAD aynı SHA, ağaç temiz, main'in atası; compose backend env'de önce 08-lite (`GUARDRAIL_EGRESS_ENABLED`, `PII_TOKEN_TTL_S`) sonra 01 satırları, `e2e` servisi yerinde.
Kontrol: `git range-diff 591aac3..3907dd9 5900976..a190f63` ile kod deltasının yalnız çakışma çözümü + a190f63 olduğu; `docker compose config` (varsayılan, e2e profili) 0; işçinin kapıları 289 + 133 iki profil (08-lite testleri dahil), temiz up + smoke, log kapısı 0. 01 kodunu ve r1-r3'ü yeniden açma. Onaysa merge bende.

### K-01-0021 · 2026-10-28 21:29 · → isci-b · CEVAP
Paket: 01   Cevap: R-01-0012
01 MERGED: r4 ONAY (a190f63, state/reviews/01-r4.md); main'e `--no-ff` merge 070d8b0; main'de compose config + lint + smoke passed. Worktree, branch ve `0.0.0-01` imajları kaldırıldı. Sıradaki paketin 02: GOREV K-02-0001 aşağıda. Oturum talimatın paket devamına izin veriyorsa bu oturumda HANDOFF'u kısa tutup 02'ye ACK ver; izin vermiyorsa HANDOFF yaz, lease RETIRED, kullanıcı yeni oturum açar (DURUM'da yaz).
