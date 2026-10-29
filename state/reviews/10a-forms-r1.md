# 10a-formlar · r1 · Bağımsız inceleme

- İstek: K-10af-0005; ACK: R-10af-0001.
- İncelenen tam SHA: `851de1d8991736850f1144a0d05d303910f436fc`; baz: `070d8b0`.
- İnceleyici: `ffcore-inceleyici-20261028-0203`; tarih: 29 Ekim 2026.
- Detached worktree: `.worktrees/review-10af-r1`; yalnız bu commit incelendi.
- Karar: **ONAY; BLOCKER 0, MAJOR 0, MINOR 1.** Aşağıdaki UI kusuru açık bulgudur; giderildiği veya ertelenmesinin kabul edildiği iddia edilmez. Merge ve takip kaydı koordinatörün sorumluluğundadır.

## Bulgular

### MINOR-1 — Açık model formu proje değişiminde eski modeli koruyor; salt okunur projede Kaydet aktif

Kaynak: `frontend/app/(console)/models/page.tsx:25,36,60-61`, `frontend/components/model-form.tsx:82,381`, `frontend/lib/api/queries.ts:176-178`.

`ModelList` proje kimliğiyle yeniden oluşturulmuyor; form state'i önceki projedeki Model nesnesini tutuyor. ModelForm anahtarı yalnız model id'si olduğundan proje değişiminde bu form da korunuyor. Yeni `projectId` mutasyon hook'una geçerken eski model id'si aynı kalıyor. Formun Kaydet kapısı yalnız `pending || !ready`; güncel edit/read yetkisi burada kontrol edilmiyor.

Bağımsız Chromium probu, gerçek backend: proje admin'i alpha'da düzenleme formunu açtı; üst çubuktaki gerçek proje seçicisinden admin+read yetkili beta'ya geçti. Salt okunur rozeti görünürken `formVisible=true`, `saveEnabled=true` ölçüldü. Kaydet, **beta proje yolu + alpha model id** ile PATCH gönderdi ve backend **403** verdi. Yetki aşımı veya veri değişikliği doğrulanmadı; backend koruması çalışıyor. Bu nedenle önem derecesi MINOR; salt okunur UI kabul kriterindeki “hiçbir kaydet düğmesi aktif değildir” koşulu bu geçişte karşılanmıyor.

Beklenen: proje değişince eski formu kapat/sıfırla ve tüm form mutasyonlarını güncel proje yetkisiyle kapıla. Taslağı korumak isteniyorsa proje sahibi açıkça sabit tutulmalı; eski model ile yeni proje adresi birleştirilmemeli. Negatif test: alpha edit formu → beta read; eski form yok veya Kaydet pasif, beta/alpha-model PATCH isteği sıfır. Beta edit geçişini de ayrıca kapsa.

Kanıt: `.worktrees/review-10af-r1-evidence/project-transition.spec.ts` ve `result.txt`. Gözlem probunun 1 passed sonucu yalnız gözlemlerin tamamlandığını belirtir; salt okunur UI kriterinin geçtiği anlamına gelmez.

## Bağımsız kapılar ve ortam

Kendi Compose projesi `review-10af-r1`, backend host portu `18054`, `FFCORE_VERSION=0.0.0-review-10af`, `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm`. Yalnız yerel test servisleri ve `.env.test` sahte değerleri kullanıldı. Gerçek `.env` okunmadı/değiştirilmedi. İşçi yığınlarına müdahale edilmedi.

Kaynaklar exact-SHA worktree'den kendi Docker çalışma volume'una kopyalandı; derleme/test/PNG çıktıları bu kopyada üretildi. Kullanıcının `ffcore-10a-nm` ve `ffcore-10a-nm-pw` bağımlılık volume'ları salt okunur kaynak olarak kopyalandı; testler kendi `review-10af-r1-work` ve `review-10af-r1-nm` volume'larında çalıştı. Node veya make host üzerinde çalıştırılmadı.

Backend imajı `sha256:3b5685437c163dfca9298daa82b3c6417d529497a215f379db2e5cae560c3864`: `/app/ffcore` içindeki **54 Python dosyası**, exact SHA `/backend/ffcore` kaynaklarıyla LF normalize SHA256 eşit. Tools imajı `sha256:33a056657cd5f9b371d457cc68b6a2e99f0da74d379ce2c3586ac77ee1be23ea`; backend testlerinde kaynak worktree `/work:ro` bağlandı, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_ADDOPTS=-p no:cacheprovider` kullanıldı.

| Kontrol / komut | Sonuç |
|---|---|
| `git diff --check 070d8b0 HEAD`; `git diff --name-only 070d8b0 HEAD -- state/` | exit 0; state diff boş |
| Node20.19.5 Alpine: lint, `tsc --noEmit --incremental false`, `check:api` | exit 0 |
| Node20 Vitest | exit 0; 89 test / 16 dosya, 7,23 sn |
| Backend `make lint` | exit 0; 134 dosya |
| Backend `DEPLOY_PROFILE=llmaas make test` | exit 0; 292 passed, 40,79 sn |
| Backend `DEPLOY_PROFILE=airgap make test` | exit 0; 292 passed, 40,33 sn |
| Backend `DEPLOY_PROFILE=llmaas make test-int` | exit 0; 134 passed, 130,83 sn |
| Backend `DEPLOY_PROFILE=airgap make test-int` | exit 0; 134 passed, 117,91 sn |
| `docker compose --profile e2e config --quiet` | exit 0; interpolasyon doğrulandı, değerler basılmadı |
| Temiz kendi PG/Redis/LiteLLM/migrate/backend, test yöneticisi CLI | exit 0; sağlıklı |
| Tam Playwright `playwright test --workers=1` | exit 0; **74 passed, 5,2 dk**, retries=0 |
| Ek gerçek proje geçişi probu | gözlem tamamlandı; MINOR-1 doğrulandı |
| İki tema form PNG'leri | dört yeni form PNG'si görsel incelendi; tema/axe/EN-TR testleri tam takımda geçti |
| Test artifact/log anahtar taraması | 2 dosya, 0 ZIP girdisi, 0 eşleşme; kendi backend/LiteLLM 197750 bayt logunda üç sentetik anahtarın her biri 0 eşleşme |

Backend kapısı komut kalıbı: `docker compose -p review-10af-r1 --env-file .env.test run --rm --no-deps -v C:/ai_paycore/ffcore/.worktrees/review-10af-r1:/work:ro -e PYTHONDONTWRITEBYTECODE=1 -e 'PYTEST_ADDOPTS=-p no:cacheprovider' -e DEPLOY_PROFILE=<profil> -e GUARDRAIL_EGRESS_ENABLED=true tools make <test veya test-int>`. Entegrasyon öncesi yalnız kendi `--profile test up -d --no-build fake-llm` servisi başlatıldı; tam Playwright sırasında fake-llm başlatılmamıştı (D3).

Playwright imajı `mcr.microsoft.com/playwright:v1.64.1-noble@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`. Komut: `docker run --rm --network review-10af-r1_default --ipc host --env-file .env.test -e FFCORE_BACKEND_URL=http://backend:8000 -e LITELLM_URL=http://litellm:4000 -e NEXT_TELEMETRY_DISABLED=1 -v review-10af-r1-work:/work -v review-10af-r1-nm:/work/frontend/node_modules -w /work/frontend <pinli-imaj> bash -c 'set -o pipefail; ./node_modules/.bin/playwright test --workers=1 2>&1 | tee /work/review-playwright.log'`. Proje konfigürasyonu build/start ve gerçek global-setup/API fixture'larını çalıştırdı. Tarayıcı imajındaki Node sürümüyle E2E; lint/tip/birim ayrıca Node20.

İşçinin önceki workers=2 koşusunda düşen üç eski test, bağımsız tam workers=1 koşusunda geçti. Bu, önceki hataların kesin kök nedenini kanıtlamaz; ürün hatası veya kalıcı flake diye sınıflandırılmadı. İlk bağımsız entegrasyon başlatma isteği Docker API `containers/json` 500 ile testler başlamadan düştü; yeniden denemede tam llmaas kapısı geçti. Geçici Docker erişim sorunu test hatasıyla karıştırılmadı. İlk tarayıcı başlatma denemesinde Debian sh `pipefail` desteklemedi; bash ile düzeltildi, ürün bulgusu değildir.

## Güvenlik turu

03b egress değişikliği nedeniyle ayrı güvenlik turu uygulandı.

- **Kimlik:** session/401/goToLogin/safeNext mevcut sınırları korunuyor. Tam bağımsız E2E; çerezsiz giriş, yanlış parola, çıkış/jeton iptali ve 401 geri dönüş testleri geçti. Kimlik protokolü değişmedi.
- **ACL:** sağlayıcı tenant yetkisi ve modellerin proje WriteGate sınırları incelendi. Proje admin'i sağlayıcı listesi istemeden model düzenleyebiliyor; ekle açık gerekçeyle pasif (D1). Gerçek read-only API 403 testleri geçti. Açık form/proje geçişi MINOR-1; aynı probun backend 403'ü yetki sınırının çalıştığını gösteriyor.
- **Secret:** düzenlemede saklı secret boş; değiştirilmemiş değer API'ye `***` gidiyor; API maskeli döndürüyor. Tam E2E oluşturma/boş bırakarak düzenleme testleri geçti. Yeni secret girilirken parolanın input/local form state'inde geçici bulunması gönderim için gereklidir; saklı secret API'den veya query cache'den geri alınmıyor. Compose anahtar değeri içermiyor; `${LITELLM_MASTER_KEY:?...}` interpolasyonu ve test-side LiteLLM header kullanımı doğrulandı. Değerleri basmadan yapılan rapor/log negatif taraması yukarıda. Başarılı koşu trace tutmadığından ZIP sayısı sıfırdır; oluşmamış trace için içerik temizliği kanıtı iddia edilmez.
- **SQL:** üretim SQL/ORM/migration değişikliği yok; mevcut API ve parametreli backend servisleri kullanılıyor. İki profil entegrasyon kapılarının sonuçları yukarıda; UI kapısı güvenlik sınırı sayılmadı.
- **Egress:** `check_host` resolver'dan önce; resolve sonrası private-address kontrolü aynı yerde; allowlist/offline gevşemedi. Resolver `OSError` sabit `egress_dns_failed` / `name does not resolve` tipli hataya `from None` ile dönüşüyor, ham sistem hata metni taşınmıyor. Ek unit negatifleri ve kaydedilmemiş/kayıtlı provider API 200+`connection_failed` testleri tam backend takımlarında geçti. Gerçek satıcı ağına bağlantı NOT_RUN; yerel fake sağlayıcı ve negatif resolver yolları kullanıldı.
- **PII:** yeni üretim log/audit içeriği eklenmiyor; UI dinamik alan etiketleri EN/TR kaynaklarında. Kurum belgesi veya kişisel müşteri verisi kullanılmadı; yalnız sentetik hesap/proje fixture'ları.
- **Log sızıntısı:** DNS sistem mesajı kaynakta kapalı; kendi backend/LiteLLM ve Playwright raporunda sentetik anahtarlar sıfır. Test sırasında HTTP DEBUG genel sızıntısı kapsamındaki FOLLOWUP-49 yeniden açılmadı; 02'nin sorumluluğu devam ediyor.

## Kapsam ve sınırlar

K-10af-0002 D1/D4 ve FOLLOWUP-79/80 kabul edilmiş sınırlardır: proje admin'i model ekleyemez; responses yeni seçimde pasif, mevcut model düzenlenebilir ve gateway-dışı rozeti görünür; secret silme desteklenmiyor. Bu kararlar yeniden açılmadı. DNS düzeltmesi ayrı fix(03b) commit'i ve koordinatörce genişletilmiş touch-zone kapsamında incelendi; sözleşme değişikliği yok.

**NOT_RUN:** Lighthouse (mevcut FOLLOWUP-37); aynı E2E takımının ikinci profil kopyası (UI profil bağımsız, backend matris ayrı çalıştı); dış satıcı/model bağlantıları; ağdan `npm ci`/imaj build tekrarı (mevcut pinli yerel imaj/dependency kopyaları); tam `make smoke` (bu review yığınında Langfuse açılmadı, backend/LiteLLM sağlığı ve gerçek E2E ayrıca doğrulandı). Bu kapılar geçti sayılmadı. Yeni, brief'in zorunlu tuttuğu eksik Makefile hedefi saptanmadı.

## Temizlik

Kendi `docker compose -p review-10af-r1 --env-file .env.test --profile test down -v --remove-orphans` exit 0; kendi çalışma/bağımlılık volume'ları `docker volume rm review-10af-r1-work review-10af-r1-nm` exit 0. Son `docker volume ls --filter name=review-10af-r1` çıktısı boş; korunan `ffcore-10a-nm` ve `ffcore-10a-nm-pw` mevcut. Yalnız kendi review kaynakları kaldırıldı.

HEAD tam SHA eşit, `git status --porcelain --untracked-files=normal` boş olarak yeniden doğrulandı; `git worktree remove C:\ai_paycore\ffcore\.worktrees\review-10af-r1` exit 0; `--force` kullanılmadı. Ana çalışma kopyasında checkout/switch, ürün kaynak değişikliği, commit/push yapılmadı. Küçük sentetik probe/sonuç kanıtları `.worktrees/review-10af-r1-evidence/` altında paket kapanışına kadar kaldı; review imaj etiketlerini koordinatör temizleyebilir.

Paket kapanışı (2026-10-29 09:33): K-10af-0012 uyarınca r1/r2 geçici evidence dizinleri, mutlak hedefler ve reparse-point yokluğu doğrulandıktan sonra kaldırıldı; ikisinin de bulunmadığı doğrulandı. Rapor ve kanaldaki sonuç kanıtı korunuyor.
