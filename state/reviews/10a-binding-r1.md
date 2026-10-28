# 10a-bağlama · r1 · Bağımsız inceleme

- İstek: `K-10ab-0007`; ACK: `R-10ab-0001`.
- İncelenen tam SHA: `7229da702f843c44d320bea519def2f356f46572`.
- Baz: `591aac3`; detached worktree: `.worktrees/review-10ab-r1`.
- İnceleyici: `ffcore-inceleyici-20261028-0203`; 28 Ekim 2026.
- Karar: **DUZELT / merge-ready değil. BLOCKER 0, MAJOR 1, MINOR 1.**

## Bulgular

### MAJOR-1 — Yardımcı sorgu hataları boş seçenek listesine dönüşüyor

`frontend/components/member-form.tsx:23-29` kullanıcı sorgusunun pending/error durumlarını işlemiyor; `(users.data ?? [])` ile hatayı boş aday listesine çeviriyor. `frontend/components/project-switcher.tsx:17-19` aynı şeyi süper yönetici proje listesinde yapıyor. Bu, ARCH-06 fail-loud kuralına aykırı. Üye ekleme veya proje seçme engelleniyor ama kullanıcı sebebini göremiyor; hata kodu/ayrıntısı da kayboluyor. `useReportError` yalnız mutasyonlara bağlı ve bu sorgular `ListState` içinden geçmiyor.

Bağımsız Chromium probe: gerçek backend'de giriş yapıldı, gerçek proje/üyelik sayfası açıldı; yalnız tarayıcıdaki `GET /api/v1/users` yanıtına 503 `review_users_unavailable` hata enjeksiyonu uygulandı. Sonuç: kullanıcı seçeneği yalnız **“Choose a user”**, `list-error` sayısı **0**, görünen hata kodu **yok**; global toaster'ın boş alert düğümü hata bildirimi sayılmadı. Gerçek üyelik listesi aynı anda çalışıyordu. `GET /api/v1/projects` için 503 `review_projects_unavailable` enjekte edilip `/providers` açılınca proje seçicide de yalnız placeholder kaldı, hata/ayrıntı görünmedi. Sentetik kodlar probe'a aittir, backend sözleşmesine eklenmedi.

Beklenen düzeltme: bu iki yardımcı sorgunun yüklenme, başarı/gerçek boş liste ve hata durumları ayrılmalı; başarısızlıkta lokalize hata + backend kodu/ayrıntısı görünmeli. Başarısız sorgu “aday/proje yok” gibi sunulmamalı; 401 ortak oturum davranışını izlemeli. Her iki yardımcı sorgunun hata senaryosu için anlamlı negatif test gerekli.

### MINOR-1 — Liste sorgusundaki 401 girişe yönlendirmiyor

`frontend/components/screen.tsx` içindeki `ListState` her query hatasını doğrudan mesaj olarak çiziyor. Buna karşılık `components/use-report-error.ts:18-20` yalnız mutasyon hatalarında 401 → `/login` yapıyor. Aynı API hatası için davranış ayrışıyor; docs/onyuz.md ve PR'daki 401 sınırı tam uygulanmıyor.

Bağımsız tarayıcı probe'unda `/api/v1/providers` 401 `unauthenticated` yanıtından sonra URL **`/providers`** kaldı, ekranda “Your session has ended. Sign in again.” yazdı; otomatik giriş yönlendirmesi olmadı. Bu bir yetki aşımı değil; backend reddediyor ve kullanıcıya mesaj veriliyor. Ortak sorgu hata yolu/oturum yönlendirmesi önerilir. Tam sayfa isteğindeki `GET /auth/me` 401 yönlendirmesi ayrı olarak çalışıyor.

## Bağımsız doğrulama

Kaynaklar exact SHA'daki worktree'den salt okunur bağlanarak yalnız `frontend/`, `backend/`, `docs/` kendi geçici Docker volume'una kopyalandı. Derleme, ekran görüntüsü ve test çıktıları bu kopyada kaldı; inceleme worktree'sine yazılmadı. Kullanıcının `ffcore-10a-nm` ve `ffcore-10a-nm-pw` volume'ları salt okunur kaynak olarak kullanıldı, silinmedi/değiştirilmedi. İlk denemede bağımlılık mount düzeni yüzünden ESLint `debug` çözemedi; kendi volume'umdaki node_modules yolu düzeltildikten sonra tam kontroller geçti. Bu ortam hatası ürün bulgusu yapılmadı.

Backend imajı `sha256:04f185fa1727dc3813dcb4e5c5df3fa51fa40851edbdfdbea9ec3149d592be04` içindeki 40 Python kaynak dosyası (`ffcore`, `alembic`) SHA kaynağıyla bayt bayt karşılaştırıldı: **0 fark**. Kendi compose projesi `review-10ab-r1`, host backend portu 18000; `.env.test` sahte değerleri ve belgelenmiş sahte yönetici kullanıldı. İmaj override'ı yalnız bu review'e aitti. İşçi stack'lerine dokunulmadı, dış ağ kullanılmadı.

| Kontrol | Sonuç |
|---|---|
| Node `20.19.5-alpine`, `npm run lint` | **passed** |
| Aynı ortam, `npx tsc --noEmit --incremental false` | **passed** |
| Aynı ortam, `npm test` | **47 passed / 11 dosya**, 7,30 sn |
| Aynı ortam, `npm run check:api` | **passed**; bayt kopyası ve üretilen tipler güncel |
| Ayrı temiz compose PG/Redis + migrate + backend `up -d --wait` | **passed**; gerçek 03a/03b ve katalog |
| CLI `create-superadmin`, yalnız sahte parola stdin | **passed** |
| Playwright gerçek backend, exact digest imaj | **48 passed**, 1,8 dk; build/start dahil |
| Tema/EN-TR/7 ekran × 2 PNG/axe | **passed**; 14 axe testi dahil; üyeler koyu tema PNG ayrıca görsel incelendi |
| Yardımcı users/projects 503 probe | **FAILED** beklenen hata görünürlüğü: MAJOR-1 |
| Liste 401 probe | `/providers` kaldı: MINOR-1 |
| Bilinmeyen ana liste hata kodu | **passed**; Details açılınca `review_unknown_code: review unknown detail` görünür |
| Gerçek browser login çerezi | **passed**; HttpOnly=true, Secure=true, SameSite=Strict; JS göremiyor |
| `git diff --check 591aac3 HEAD`, baz diff `state/` | **passed / boş** |

Playwright imajı: `mcr.microsoft.com/playwright:v1.64.1-noble@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`. E2E Node sürümü bu onaylı imajın sürümüdür; lint/birim/tip kapıları ayrıca proje Node20 sürümünde koştu. Test kaynağı değiştirilmedi. Compose e2e'nin ağdan `npm ci` adımı bağımsız tekrar edilmedi; güncel yerel bağımlılık kopyaları kullanıldı. Konteynerde Docker soketi yok.

## Güvenlik turu

- **Kimlik:** tek sunucu session boundary `lib/session.ts` → `session-core`; yalnız `ffcore_session` backend'e iletiliyor, cache no-store. Sahte session yolu silinmiş. Gerçek login, yanlış parola, çerezsiz sayfa, üyeliksiz sayfa ve logout sonrası eski token'ın reddi bağımsız Playwright'ta geçti. Gerçek çerez bayrakları ayrıca ölçüldü. Query 401 UX ayrışması MINOR-1; yetki aşımı doğrulanmadı.
- **ACL:** seçili proje üyeliğinden edit/read; URL üyeler ekranında açık projectId; süper yönetici kendi access değerini kullanıyor. Backend gerçek read-only mutasyonu 403 reddediyor; açık sayfada yetki düşürme sonrası “Read-only access” doğrulandı. Menü tenant bayrağı ve reserved role seçenekleri incelendi. UI kapısı güvenlik sınırı sayılmadı.
- **Secret:** frontend'e session token veya provider credential prop'u verilmedi. Secret/.env okunmadı. Fixture'lar sahte `dummy-not-secret-*`; test çıktısında session token yazılmadı. İlk probe'daki elle yerleştirilmiş çerezin metadata'sı güvenlik kanıtı alınmadı; gerçek form girişinde Secure=true ayrıca doğrulandı.
- **SQL:** bu PR SQL/ORM değiştirmiyor; üretilmiş API tipleri ve backend guard'ları kullanılıyor. Parametreli sorgu/transaction davranışı için backend tam testleri bu PR'da yeniden koşulmadı.
- **Egress:** tarayıcı same-origin `/api/v1` rewrite kullanıyor; backend origin build-time ve server runtime yapılandırmasında açık. CORS/credentials açılmadı. Yerel backend dışındaki gerçek satıcı bağlantısı **NOT_RUN**. FFCORE_BACKEND_URL eksikliği unit'te fail-loud; arg'sız gerçek Docker build bağımsız tekrar **NOT_RUN**, işçi kanıtı kaynakla uyumlu.
- **PII:** ekranlar yalnız backend'in yetkili döndürdüğü kullanıcı e-postası/isim/üyelik bilgilerini çiziyor; tarayıcı fixture'ları `example.org`, müşteri verisi kullanılmadı. Genel PII temizliği var sayılmadı.
- **Log sızıntısı:** yeni frontend kaynaklarında credential/session loglama görülmedi; fetch hataları kullanıcıya kod/mesaj olarak sunuluyor. Merkezi backend log sanitizer kapsamı bu değişiklikle genişletilmiş sayılmadı. Yardımcı sorguların hata yutması MAJOR-1.

## Kapsam, süreç ve NOT_RUN

Koordinatörün açık kabulleri korundu: msw yok/gerçek backend; sağlayıcı ve model formları 10a-formlar'a; Lighthouse ve edit/read görsel karşılaştırması 10c'ye; FOLLOWUP-66 HTTPS/ters vekil ve FOLLOWUP-67 proje-admin üye ekleme. Makefile e2e hedefi eksikliği bu pakette **onaylı DRIFT-61** olduğundan yeni bulgu değil. Generated API sözleşmesi backend'i değiştirmiyor; C13 mesaj anahtarları additive, FOLLOWUP-44 SidebarRail/breadcrumb çevirisi ve gerçek ESLint negatifleri tamam.

PR sapma 8'deki dört modül için önce-kırmızı kanıtı **yok**; geçmişe dönük geçti sayılmadı. Sapma 9'daki iki ara commit'in tek başına typecheck geçmemesi süreç kusuru; inceleme yalnız final SHA'ya verilir, geçmiş commit'lere onay verilmez. Bunlar PR'da açıkça işaretli, sonraki dilimlerde test-önce ve her dilim kapısı uygulanmalı. Final SHA'nın bağımsız yeşil kapılarına rağmen bu rapor MAJOR-1 nedeniyle zaten DUZELT; sürecin geriye dönük kurala uygun olduğu iddia edilmiyor.

**NOT_RUN:** backend `make lint/test/test-int` (backend değişmedi, K-10ab-0007 sınırı); iki profil E2E (profil bağımsız frontend, llmaas gerçek koşu); Lighthouse; gerçek kurum sunucusu/dış provider; arg'sız Docker build'in bağımsız tekrarı. Kabul edilen boş provider/model satırı E2E veri sınırı korunuyor; dolu satır render'ı bu koşuda doğrulanmadı.

## Temizlik

Review'e ait probe konteyneri durdurulup kaldırıldı; `review-10ab-r1` stack'i `down -v` ile temizlendi. Kendi work/node_modules volume'ları kaldırıldı; kullanıcı volume'ları korundu. Tam HEAD `7229da702f843c44d320bea519def2f356f46572` ve boş `git status --porcelain --untracked-files=normal` doğrulandı; `git worktree remove` exit0, `--force` yok. Kendi compose override dosyası kaldırıldı. Kaynak kod değişikliği, commit/push, ana kopyada checkout/switch ve dış/kurum sistemi erişimi yapılmadı.
