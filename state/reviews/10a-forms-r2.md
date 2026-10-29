# 10a-formlar · r2 · Delta incelemesi

- İstek: `K-10af-0009`; ACK: `R-10af-0006`.
- İncelenen tam SHA: **`275d06d8224e40a02b0dfc1d2bfbcba0b014c98a`**.
- Baz: `070d8b0`; delta başlangıcı: r1 `851de1d8991736850f1144a0d05d303910f436fc`.
- İnceleyici: `ffcore-inceleyici-20261028-0203`; tarih: 29 Ekim 2026.
- Ayrı detached worktree: `.worktrees/review-10af-r2`.
- Sonuç: **ONAY — BLOCKER 0, MAJOR 0, MINOR 0. R1 MINOR-1 kapandı.**

## Delta ve r1 bulgusu

Üç commit/23 dosya (+204/-9) incelendi: test commit'i `c13cb2b`, düzeltme `f08b5b6`, PNG yenilemesi `275d06d`. Üretim deltası üç TSX dosyası ve iki mesaj dosyasıyla sınırlı; backend, deploy, package.json/lock değişmiyor. R1'in kapsamı ve kabul edilmiş FOLLOWUP-79/80 kararları yeniden açılmadı. PR bazına göre `state/` değişikliği yok; main'den miras kalan state dosyaları bulgu sayılmadı.

**R1 MINOR-1 kapandı.** `ModelsPage`, `ModelList`'i `key={projectId}` ile oluşturuyor: seçili proje değişince açık model nesnesi ve taslak state'i atılıyor. Model formu Kaydet'i `<WriteGate projectId={projectId}>`, sağlayıcı formu Kaydet'i `<WriteGate>` içinde. Mevcut `useAccess`/`accessFor` kullanılıyor; model açık proje üyeliğini, tenant kapsamlı sağlayıcı süper yöneticinin erişim modunu izliyor. API güvenlik sınırı korunuyor.

Bağımsız önceki hata probunun r2 tekrarı gerçek tarayıcı/backend ile geçti: alpha'da proje admin'i model düzenlemesini açıp taslak adını değiştirdi; gerçek üst çubuk seçicisinden beta read'e geçti. Sonuç **model-form=0, model-save=0**. Alpha'ya dönünce form kapalı; yeniden açılan form kayıtlı eski adı gösteriyor, taslak geri gelmiyor. Tüm gidiş/dönüş boyunca **model yazma isteği=0**. Bu kez probun koşulları assertion'larla doğrulandı; yalnız gözlem çıktısı değil. Kod: `.worktrees/review-10af-r2-evidence/project-transition.spec.ts`.

Yeni `test_10af_16` aynı salt okunur geçişi ve iki edit proje arasındaki geçişi; `test_10af_17` iki formda read/edit Kaydet durumunu kapsıyor. Test kodları ve PR'daki önce kırmızı kanıtı incelendi; eski commit'e dönüp kırmızı koşu bağımsız tekrarlanmadı (review yalnız istenen SHA'da).

`Models.extraBodyHint` EN/TR JSON örneği ICU literal tırnaklarıyla kaçırılmış. `test_10af_18` her iki dilde tüm mesajların derlenmesini denetliyor; bağımsız Vitest'te geçti. İki tema model PNG'sinde JSON örneği tırnak/fallback sızıntısı olmadan görsel incelendi. Yeni sözleşme, bağımlılık veya mimari yaklaşım yok.

## Bağımsız doğrulama

Kendi proje adı `review-10af-r2`, port `18054`, `FFCORE_VERSION=0.0.0-review-10af`, `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm`. Yerel PG/Redis/LiteLLM/migrate/backend, `.env.test` sentetik değerleri; fake-llm başlatılmadı (belgeli e2e D3). Backend/tools imajları r1'de kaynak hash eşleşmesi doğrulanmış yerel imajlar: backend `sha256:3b5685437c163dfca9298daa82b3c6417d529497a215f379db2e5cae560c3864`, tools `sha256:33a056657cd5f9b371d457cc68b6a2e99f0da74d379ce2c3586ac77ee1be23ea`.

`frontend`, `backend`, `docs` exact SHA kaynağından kendi `review-10af-r2-work` Docker volume'una kopyalandı. Korunan `ffcore-10a-nm(-pw)` volume'ları yalnız salt okunur kaynak; kendi `review-10af-r2-nm` kopyası kullanıldı. Derleme, test çıktıları ve PNG'ler yalnız geçici kopyada. Ek probe ürün kaynağına eklenmedi. Host Node/make çalıştırılmadı; ağdan paket/imaj indirilmedi.

| Kapı | Bağımsız sonuç |
|---|---|
| Tam SHA nesnesi, `070d8b0` atasallığı | geçti |
| `git diff --check 070d8b0 HEAD`; baz diff `state/` | exit 0; state diff boş |
| Node20.19.5 Alpine, ağsız `eslint .` | exit 0 |
| Aynı ortam `tsc --noEmit --incremental false` | exit 0 |
| Aynı ortam `vitest run` | **93 passed / 18 dosya**, 10,32 sn, exit 0 |
| Aynı ortam `npm run check:api` | exit 0; sözleşme kopyası/tipler güncel |
| Kendi temiz backend yığını + CLI test yöneticisi | exit 0; sağlıklı |
| `playwright test test_10af_ review_project_transition --workers=1` | **25 passed, 2,4 dk**, exit 0; 24 ürün 10af testi +1 bağımsız probe |
| Model formu açık/koyu PNG görsel inceleme | ICU JSON ipucu düzgün; testler iki form/iki tema axe kontrolünü kapsıyor |
| Secret artifact/log negatif taraması | 2 dosya/0 ZIP girdisi/0 eşleşme; kendi backend/LiteLLM 77362 bayt logunda 3 sentetik anahtarın her biri 0 eşleşme |

Node komutu: `docker run --rm --network none -e NPM_CONFIG_UPDATE_NOTIFIER=false -v review-10af-r2-work:/work -v review-10af-r2-nm:/work/frontend/node_modules -w /work/frontend node:20.19.5-alpine sh -c './node_modules/.bin/eslint . && ./node_modules/.bin/tsc --noEmit --incremental false && ./node_modules/.bin/vitest run && npm run check:api'`.

Tarayıcı imajı `mcr.microsoft.com/playwright:v1.64.1-noble@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`. `docker run --rm --network review-10af-r2_default --ipc host --env-file .env.test -e FFCORE_BACKEND_URL=http://backend:8000 -e LITELLM_URL=http://litellm:4000 -e NEXT_TELEMETRY_DISABLED=1 -e NPM_CONFIG_UPDATE_NOTIFIER=false -v review-10af-r2-work:/work -v review-10af-r2-nm:/work/frontend/node_modules -w /work/frontend <pinli-imaj> bash -c 'set -o pipefail; ./node_modules/.bin/playwright test test_10af_ review_project_transition --workers=1 2>&1 | tee /work/review-r2-playwright.log'`. Normal proje global-setup, build/start ve gerçek API fixture'ları kullanıldı; retries=0.

## Güvenlik turu — delta

- **Kimlik:** session/çerez/redirect değişikliği yok; mevcut sınır kullanılıyor. R1'in bağımsız kimlik kanıtı geçerli; tüm kimlik E2E dosyaları r2'de yeniden koşulmadı.
- **ACL:** proje key'i eski model/yeni proje adresinin birleşmesini kaldırıyor; güncel erişim Kaydet'i kapılıyor. Read/edit geçişleri ve yazma isteğinin yokluğu gerçek tarayıcıyla doğrulandı; iki form read/edit düğmesi birim testi geçti. API koruması kaldırılmadı.
- **Secret:** kaynak secret değeri eklemiyor; mevcut maskeli config davranışı değişmiyor. Sağlayıcı oluşturma/boş secret koruma testleri 10af kapısında; sentetik değer taraması aşağıdaki sonuçla sınırlı.
- **SQL:** backend/ORM/migration değişmedi; UI yalnız mevcut sözleşmeyi kullanıyor.
- **Egress:** egress/Compose/rewrite değişmedi; yalnız kendi yerel servis ağı kullanıldı. HF/Paddle/model süreci açılmadı; dış satıcı bağlantısı yok.
- **PII:** sentetik kullanıcı/proje/model fixture'ları; kurum verisi veya belge kullanılmadı. PNG yenilemesi sentetik test verisi içeriyor.
- **Log sızıntısı:** yeni üretim logu yok; DNS resolver düzeltmesi r1'de incelenmişti, r2'de yeniden açılmadı. Trace oluşturulmadıysa trace içeriği doğrulandı denmez.

## NOT_RUN ve sınırlar

- Backend iki profil birim/entegrasyon kapıları r2'de **NOT_RUN**: backend/Compose bağımlılıkları değişmedi; r1'de her profilde 292 birim/sözleşme +134 entegrasyon bağımsız geçmişti.
- Tüm 76 testlik E2E takımının r2 bağımsız tekrarı **NOT_RUN**: koordinatör r2 kapısını 10af e2e + Vitest olarak belirledi. İşçinin 76/76 bildirimi bağımsız sonuç diye sunulmadı; r1'de tüm74 bağımsız geçmişti.
- Lighthouse (FOLLOWUP-37), ikinci profil E2E kopyası, tam Langfuse'lı smoke, imaj build/npm ci tekrarı ve dış satıcı bağlantıları **NOT_RUN**. Bunlar geçti sayılmadı.

## Temizlik

Kendi `review-10af-r2` Compose yığını `down -v --remove-orphans` exit 0 ile kaldırıldı; `review-10af-r2-work` ve `review-10af-r2-nm` volume'ları kaldırıldı (exit 0). Kendi volume filtresi boş; korunan `ffcore-10a-nm` ve `ffcore-10a-nm-pw` mevcut. İşçi yığınlarına ve model cache'lerine dokunulmadı.

HEAD exact SHA ve `git status --porcelain --untracked-files=normal` boşluğu kapanışta yeniden doğrulandı. `git worktree remove` exit 0, `--force` yok. Ana çalışma kopyasında checkout/switch, ürün kaynak değişikliği, commit/push yok. R1/R2 sentetik probe kanıtları paket kapanışına kadar kendi `.worktrees/review-10af-r*-evidence/` dizinlerinde kaldı; review imaj etiketleri koordinatörce temizlenebilir.
