# PR: 10a-bağlama (konsolun gerçek backend'e bağlanması)

**Paket:** 10a-bağlama · **Sınıf:** [C] (compose: `frontend` build arg + ortam, profilli `e2e` servisi; koordinatör onayı K-10ab-0004); geri kalanı [A] · **Branch:** feat/10a-binding · **Baz commit:** 591aac3 · **HEAD:** e9fe396678f84fe2b074a1babdefa8b2cf4de240 (8 commit; r1 7229da7 → 89953ca + 628d416; r2 628d416 → e9fe396) · **İşçi:** isci-c (ffcore-isci-c-10ab)

GOREV: K-10ab-0001 (+ taslak K-10ab-0000, düzeltme K-10ab-0002, K-10ab-0003). Sözleşme: `backend/openapi/03a.yaml` @ 591aac3 (3491 satır, 22 yol). GOREV metniyle çelişirse dosya kazanır.

## Plan (kodlamadan önce)

### 1. Bulunan semboller ve dosyalar (worktree 591aac3'te okundu)

Önyüz (10a, 891cf3a):
- `frontend/lib/session.ts` `getSession()`: yalnız `FAKE_API=1` → `ffcore_fake_session` çerezi; aksi `null` → "Session unavailable". Tek oturum sınırı.
- `frontend/lib/access.ts`: elle yazılmış `ROLES`/`ACCESS_MODES`, `Session = {role, access}`, `hasRole`, `parseSession` (geçici; "03a enum'undan üretilecek" notu).
- `frontend/lib/navigation.ts` `NAV_GROUPS`/`visibleGroups`/`itemForPath`: menü ve rota bekçisinin tek kaynağı; `providers`, `models`, `projects`, `users` `minRole: "admin"`.
- `frontend/components/{screen,login-form,nav-user}.tsx` → `notConnected()` (`components/not-connected.ts`, toast). `project-switcher.tsx` yalnız "proje seçilmedi". `session-provider.tsx` `useAccess()` → `canWrite = access === "edit"`. `write-gate.tsx` `<WriteGate>`. `route-guard.tsx` rol dışı → `StatusPage kind="forbidden"`.
- `app/(console)/layout.tsx` (sunucu bileşeni, `getSession()`), `app/page.tsx` (ilk ekran ya da `/login`), ekranlar `app/(console)/{projects,projects/[id]/members,providers,models}/page.tsx` yalnız `Screen` kabuğu.
- `next.config.ts`: **rewrite yok** (C6 aynı origin henüz kurulmamış). `playwright.config.ts`: `FAKE_API=1`, port 3100, `webServer` `next build && next start`. `tests/e2e/support.ts` `signIn()` sahte çerez yazar; `test_10a_7_login_project_flow.spec.ts` `test.fixme`.
- `package.json`: msw, @tanstack/react-query, openapi-typescript **yok** (10a'da bilinçli çıkarıldı, K-10a-0004).

Backend (03a/03b, 591aac3):
- Oturum: `core/session.py` `COOKIE_NAME="ffcore_session"`, HttpOnly + `SameSite=Strict` + `Secure` (`session_cookie_secure=True`, config yorumu: "browsers treat localhost as secure"). `check_same_origin()`: güvensiz metotta `Sec-Fetch-Site in (cross-site, same-site)` ya da `Origin ∉ CONSOLE_ORIGINS` → 403 `cross_origin_forbidden`. `.env.test` `CONSOLE_ORIGINS=http://localhost:3000`.
- `GET /api/v1/auth/me` → `MeResponse {user: CurrentUser{id,email,full_name,is_superadmin}, role: Role|null, access: AccessMode|null, memberships: Membership[{project_id, project_key, role, access}]}`. `role/access`: süper yöneticide kendi değeri (`admin`, `superadmin_access`), değilse en yüksek üyelik rolü ve o üyeliğin modu; üyelik yoksa null. "API re-checks per project."
- `POST /auth/login` (`LoginRequest{email,password}` → `MeResponse`, yanlış e-posta/şifre aynı 401 `invalid_credentials`), `POST /auth/logout` 204.
- Yetki: `users` ve `providers` CRUD `require_superadmin` (tenant); `projects` GET `require_role("analyst")`, oluşturma `require_superadmin(write=True)` (TenantWriter), proje güncelleme/üyeler `require_role("admin", write=True)`; `models` proje kapsamlı `require_role`. Üye eklemek `user_id` ister; kullanıcı listesi (`GET /users`) yalnız süper yönetici.
- Hata gövdesi `ErrorBody {error: {message, type, code}}` (tüm 4xx). Kodlar: `read_only_access`, `insufficient_role`, `cross_origin_forbidden`, `obo_project_scope`, `invalid_credentials`, `validation_error`, `provider_in_use`, ...
- e2e kullanıcısı: `python -m ffcore.cli create-superadmin --email ... --full-name ... --password-stdin` (backend konteynerinde); ikinci kullanıcılar `POST /users` (`is_superadmin`, `superadmin_access`) ve `POST /projects/{id}/members` ile API'den.
- Compose: kök `compose.yaml` → `deploy/docker-compose.yml` include. `frontend` servisinde ortam değişkeni yok (backend adresi verilmiyor); `backend` 8000, `frontend` 3000 yayınlı.

### 2. Kapsam / kapsam dışı

Kapsam:
1. **Sözleşme ve tipler:** `backend/openapi/03a.yaml` → `frontend/mocks/openapi-03a.yaml` (bayt bayt kopya), `openapi-typescript` ile `frontend/lib/api/schema.d.ts`, `npm run gen:api` ve `npm run check:api` (kopya + üretilen tip güncel mi). Elle API tipi yok; `lib/access.ts` `Role`/`AccessMode` üretilen `components["schemas"]`'tan türer.
2. **İstemci:** `lib/api/client.ts` ince, tipli `fetch` sarmalayıcısı (yol tipleri `paths`'ten; aynı origin `/api/v1/...`), `ApiError` (`status`, `code`, `type`, `message`; gövde ErrorBody değilse yine ApiError `code="unexpected_response"`, sessiz yutma yok). TanStack Query sağlayıcısı (liste sorguları + mutasyon sonrası invalidation).
3. **C6 aynı origin:** `next.config.ts` `rewrites` `/api/v1/:path*` → `${FFCORE_BACKEND_URL}/api/v1/:path*`. `FFCORE_BACKEND_URL` zorunlu: yoksa `next start`/`build` açık hatayla durur (ARCH-06/10; gizli varsayılan adres yok). Tarayıcı yalnız konsol origin'ini görür; çerez ve `Origin` aynı kalır.
4. **Oturum:** `lib/session.ts` `getSession()` sunucuda `GET /api/v1/auth/me`'yi gelen `Cookie` başlığıyla çağırır. 401 → `/login`'e yönlendirme; ağ hatası/5xx/beklenmeyen gövde → "Backend unavailable" durum sayfası (oturum yok sayılmaz, girişe sessizce atılmaz). `role === null` (üyeliksiz, süper yönetici değil) → "No project membership" durum sayfası. `ffcore_fake_session` çerez yolu kaldırılır.
5. **Proje bağlamı ve yazma yetkisi:** proje seçici `memberships` (süper yöneticide `GET /projects`) listeler; seçim `ffcore_project` çerezinde (UI tercihi, güvenlik değil). `useAccess()` seçili projenin üyeliğinden `role/access`'i verir (süper yöneticide `admin` + `superadmin_access`); `<WriteGate>` buna bağlanır. Menüde tenant ekranları (`providers`, `users`) için `NavItem.superadmin: true` (additive alan): proje admin'i bu ekranları görmez, çünkü API onlarda 403 `insufficient_role` döner (bugün menü gösterir, ekran 403 alırdı).
6. **Ekranlar (veri gerçek):** Giriş (POST /auth/login, 401 `invalid_credentials` → form hatası), çıkış (POST /auth/logout → `/login`); Projeler (liste + oluştur formu: key/name/description, zod sözleşmedeki desenle); Üyeler (liste + ekle: kullanıcı seçimi `GET /users`, rol yalnız `admin|analyst` atanabilir — Role açıklaması "developer ve user PoC'de atanamaz", erişim modu; rol/mod değiştir; çıkar); Sağlayıcılar ve Modeller: **gerçek liste** (ad, sürücü/kategori, durum) — CRUD formları kapsam sorusu C-10ab-0006.
7. **Hata gösterimi:** `lib/api/errors.ts` kod → `messages` anahtarı eşlemesi: `read_only_access` → "Read-only access" / "Salt-okunur erişim", `insufficient_role`, `cross_origin_forbidden`, `obo_project_scope`, `invalid_credentials`, `validation_error` (alan hataları), bilinmeyen kod → genel mesaj + "Details" altında `code` ve backend `message` (brief 10 "teknik ayrıntı 'ayrıntı' altında"). 401 → `/login`.
8. **FOLLOWUP-44:** `components/ui/sidebar.tsx` SidebarRail `aria-label`/`title` → `t("toggleSidebar")`; eslint `react/jsx-no-literals` ayarına ek olarak `aria-label`, `title`, `placeholder`, `alt` öz niteliklerinde sabit metni yakalayan kural (no-restricted-syntax seçicisi) + test.
9. **Testler gerçek backend'e karşı:** Playwright compose stack'e (`-p 10ab`) karşı; 10a spec'leri sahte çerez yerine gerçek girişle koşar (K-10a-0004'te sahte API testlerinin entegrasyonu kanıtlamadığı yazılıydı; bu PR kapatır). Tema PNG'leri gerçek veriyle yenilenir.
10. `docs/onyuz.md`: "fake API stage" bölümü gerçek bağlamayla değişir; ekran durumu, rol matrisi (+ süper yönetici kolonu), e2e koşturma komutu, hata kodu eşlemesi.

Kapsam dışı: 10b-poc ekranları ve `openapi-04-07.yaml`; Lighthouse (FOLLOWUP-37, 10c); her ana ekranda edit/read ekran görüntüsü karşılaştırması (10c, A3); Kullanıcılar ve Audit ekranları (menüde `ready:false`, 10c); proje readiness kartı (`GET /projects/{id}/readiness`, "Hazırlık n/5" — 10b/10c'de ilgili ekranlarla, öneri; itiraz varsa eklenir); backend değişikliği (yok; gerekirse KAYIT-TALEBI).

### 3. Değişecek dosyalar ve neden

- `frontend/mocks/openapi-03a.yaml` (yeni, kopya), `frontend/lib/api/{schema.d.ts (üretilen), client.ts, errors.ts, queries.ts}` (yeni), `frontend/scripts/check-api.mjs` (yeni; kopya ve üretim farkı).
- `frontend/lib/{session.ts, access.ts, navigation.ts}` (gerçek oturum, üretilen enum, `superadmin` alanı), `frontend/lib/project.ts` (yeni; seçili proje çerezi).
- `frontend/components/{screen.tsx, login-form.tsx, nav-user.tsx, project-switcher.tsx, session-provider.tsx, status-page.tsx, query-provider.tsx (yeni)}`; `not-connected.ts` silinir (artık çağıran yok).
- `frontend/app/(console)/{layout.tsx, projects/page.tsx, projects/[id]/members/page.tsx, providers/page.tsx, models/page.tsx}`, `app/page.tsx`, `app/(auth)/login/page.tsx`.
- `frontend/components/ui/sidebar.tsx` (FOLLOWUP-44, tek satır grubu), `frontend/eslint.config.mjs` (öz nitelik kuralı).
- `frontend/messages/{en,tr}.json` (yeni anahtarlar; eski anahtar silinmez, C13).
- `frontend/next.config.ts` (rewrite), `frontend/package.json` + `package-lock.json` (`@tanstack/react-query`, `openapi-typescript`; msw C-10ab-0004'e bağlı), `frontend/playwright.config.ts` (gerçek backend, port 3000), `frontend/tests/**`.
- `docs/onyuz.md`, `docs/images/10a-*.png` (yenilenen).
- **Touch-zone dışı, KARAR-GEREK C-10ab-0005:** `deploy/docker-compose.yml` (`frontend` servisine `FFCORE_BACKEND_URL`; e2e servisi), Makefile `e2e`.

### 4. Sözleşme, yapılandırma, profil etkisi

- C13: `messages/{en,tr}.json` yalnız ekleme; token değişikliği yok. C12: yeni ortam değişkeni `FFCORE_BACKEND_URL` önyüz için (backend `.env.example` C12 listesine değil, compose `frontend` servis ortamına; `.env.example`'a dokunulmaz, değer servis adıdır, secret değil).
- 03a OpenAPI tüketilir, değiştirilmez. CONTRACTS C9 (bilinmeyen event yok say) bu PR'da SSE yok.
- Profil: önyüz `DEPLOY_PROFILE`'dan bağımsız (PLAN 2b profil farkı olan paketler listesinde 10 yok). Backend stack `.env.test` ile (llmaas varsayılanı) kalkar; e2e iki profilde koşturulmaz, gerekçe PR'da. `make test` (backend) dokunulmadığı için iki profilde koşar, değişmez.

### 5. Kabul kriteri → test adı

| # | Kriter | Test |
|---|---|---|
| 1 | Gerçek backend'le giriş: doğru bilgi → ilk ekran, rol ve mod kullanıcı menüsünde; yanlış şifre → `invalid_credentials` form mesajı, çerez yok | `test_10ab_1_login.spec.ts` |
| 2 | Süper yönetici proje oluşturur, listede görür; geçersiz key → alan hatası (422 `validation_error` eşlemesi) | `test_10ab_2_project_create.spec.ts` (eski `test_10a_7` fixme'si kaldırılır, bu spec'e yönlendirilir) |
| 3 | Üyeler: analyst üye ekle → listede; modu `read` yap; çıkar | `test_10ab_3_members.spec.ts` |
| 4 | `admin+read` (süper yönetici, `superadmin_access=read`): 10a ekranlarının hepsinde mutasyon düğmeleri pasif, "Read-only" rozeti; sayfa bağlamından doğrudan `POST /api/v1/projects` → 403 `read_only_access` | `test_10ab_4_read_only.spec.ts` |
| 5 | Önyüz 403'ü mesajla gösterir: eski (stale) sayfada yazma yetkisi kaldırılan kullanıcı düğmeye basar → API 403 `read_only_access` → "Read-only access" bildirimi; hata eşlemesi birim testi (dört 403 kodu + bilinmeyen kod) | `test_10ab_5_forbidden_message.spec.ts`, `tests/unit/test_10ab_5_error_mapping.test.ts` |
| 6 | Rol dışı ekran: analyst kullanıcıda Sağlayıcılar/Projeler menüde yok, URL ile "You do not have access"; proje admin'i (süper yönetici değil) Sağlayıcılar'ı görmez | `test_10ab_6_role_screens.spec.ts`, `tests/unit/test_10a_5_role_menu_visibility.test.ts` (genişler) |
| 7 | Oturum sınırı fail-loud: çerezsiz → `/login`; backend erişilemez → "Backend unavailable" (girişe atmaz); üyeliksiz kullanıcı → "No project membership"; çıkış → çerez silinir, konsol `/login`'e döner | `test_10ab_7_session_boundary.spec.ts`, `tests/unit/test_10ab_7_session.test.ts` |
| 8 | Bir ekran iki locale'de (en, tr) gerçek oturumla | `test_10a_8_locale_switch.spec.ts` (gerçek girişe taşınır) |
| 9 | Tema: geçiş + yenilemede korunur + yanıp sönme yok; her 10a ekranı gerçek veriyle iki tema PNG; axe WCAG AA iki tema 0 ihlal | `test_10a_1`, `test_10a_2`, `test_10a_4` (gerçek girişe taşınır) |
| 10 | Sözleşme kopyası `backend/openapi/03a.yaml` ile bayt aynı; `schema.d.ts` güncel; `lib/access.ts` üretilen enumla aynı küme | `tests/unit/test_10ab_10_contract_copy.test.ts` + `npm run check:api` |
| 11 | C6: önyüz yalnız aynı origin'den çağırır (kodda mutlak backend adresi yok, rewrite tek yer); `FFCORE_BACKEND_URL` yoksa açık hata | `tests/unit/test_10ab_11_same_origin.test.ts` |
| 12 | FOLLOWUP-44: SidebarRail etiketi çeviriden; lint `aria-label`/`title`/`placeholder`/`alt` sabit metnini yakalar (eslint'i örnek dosyada koşan test) | `tests/unit/test_10ab_12_attr_literals.test.ts` |
| 13 | Sabit renk yok, her anahtar iki dosyada (10a testleri değişmeden geçer) | `test_10a_3`, `test_10a_8_messages_keys` |

### 6. Migration

Yok (önyüz). Backend'e dokunulmaz; stack `migrate` servisiyle 03a+03b'yi koşar (K-10ab-0003).

### 7. Geri alma

Branch revert; backend etkilenmez. Rewrite ve oturum tek dosyada (`next.config.ts`, `lib/session.ts`). Compose değişikliği (karara bağlı) tek servis ortamı + profilli e2e servisi; kaldırmak önceki davranışı geri getirir.

### 8. Durma koşulları

- Sözleşmede ekranın gerektirdiği alan yoksa (ör. üye eklemede kullanıcı arama) → backend'e dokunmam, KAYIT-TALEBI.
- `Secure` çerez Playwright Chromium'da `http://localhost`'ta tutulmazsa → `SESSION_COOKIE_SECURE=false` yalnız test stack'inde mi, HTTPS mi: KARAR-GEREK (secret değil ama güvenlik davranışı).
- Next.js rewrite `Set-Cookie`'yi ya da `Origin`'i değiştiriyorsa (C6 403) → durur, ölçümle DURUM.
- Touch-zone dışı her dosya (deploy/, Makefile) karar gelmeden yazılmaz.

### 9. Felsefe kontrolü

- **ARCH-07:** Değer: konsolun ilk gerçek kullanımı (giriş, proje, üye) ve salt-okunur modun uçtan uca kanıtı; çekirdek "proje/kota" ve "audit" özelliklerinin yüzü. Kalıcı karmaşıklık: tek istemci sarmalayıcısı, tek hata eşlemesi. msw'yi bu PR'da eklemek 10a için ölü kod olur (C-10ab-0004).
- **ARCH-09:** Next.js rewrite (proxy yazmıyorum), TanStack Query (önbellek/invalidation elle yazılmaz), openapi-typescript (elle tip yok), backend'in kendi 403/401 kodları (önyüzde yetki hesabı yok; `WriteGate` yalnız kolaylık). `openapi-fetch` gibi onaylı listede olmayan paket eklenmez; ince `fetch` sarmalayıcısı ~60 satır.
- **ARCH-10/06:** Gizli varsayılan backend adresi yok (`FFCORE_BACKEND_URL` zorunlu). Backend hatası "oturum yok" diye yutulmaz; bilinmeyen hata kodu genel mesaja sessizce eşlenmez, kod ve ayrıntı görünür. Proje seçimi açık (çerez), otomatik "ilk projeyi seç" yok: seçim yoksa proje kapsamlı ekran "Select a project" der. Kullanıcıya atanamayan rol (`developer`, `user`) formda sunulmaz; sunulsaydı 422 ile reddedilirdi.

## Varsayımlar ve brief'teki çelişkiler (plan aşaması)

1. `/auth/me` `role/access` en yüksek üyeliğe aittir; ekran yazma yetkisi seçili projenin üyeliğinden hesaplanır (aksi halde bir projede `read` olan kullanıcı orada aktif düğme görür). Brief 10 tek global mod varsayar; 03a sözleşmesi proje başınadır. Sözleşme kazanır.
2. Menü görünürlüğü `MeResponse.role` (en yüksek rol) + `is_superadmin`; tenant ekranları süper yönetici ister (03a `require_superadmin`). Brief 10 rol matrisinde "admin: sağlayıcılar, kullanıcılar" der; 03a'da bunlar tenant düzeyi. DRIFT önerisi: brief 10 rol matrisine "süper yönetici" satırı.
3. Proje oluşturma yalnız süper yönetici (03a `TenantWriter`); proje admin'i "Create project" düğmesini görmez (WriteGate değil, rol: düğme yok). docs'ta yazılı.
4. E2E iki profilde koşturulmaz: önyüz profil bağımsız; backend stack `.env.test` (llmaas).
5. e2e kullanıcı şifreleri `tests/e2e/fixtures` altında sahte değer (`dummy-not-secret-*` düzeni), secret değil.

## Plan onayı ve sapmalar

Plan onayı K-10ab-0004: C-10ab-0004/0005/0006 hepsi A (msw yok, gerçek backend; compose iki dokunuş; sağlayıcı/model salt-okuma liste, formlar `10a-formlar`), varsayım 1 kabul, varsayım 2 DRIFT-62, "make e2e" DRIFT-61.

| # | Sapma | Gerekçe |
|---|---|---|
| 1 | `FFCORE_BACKEND_URL` compose'da `:?` değil literal `http://backend:8000`; ayrıca `frontend.build.args`'ta ve Dockerfile'da `ARG` | Next.js rewrite'ı build anında sabitler; yalnız çalışma anı ortamı yetmez. Değer servis adıdır; `.env*` dosyalarına dokunmamak için literal. C-10ab-0008 ile bildirildi |
| 2 | `useAccess(projectId?)` ve `<WriteGate projectId>` | Üyeler ekranının projesi URL'den gelir; yazma yetkisi o projenin üyeliğinden (varsayım 1'in ekran karşılığı) |
| 3 | Üye ekleme formu yalnız süper yöneticide; proje admin'ine açıklama metni | Kullanıcı seçimi `GET /users` ister, 03a'da `require_superadmin`; proje kapsamlı kullanıcı arama ucu yok (kalan risk 3) |
| 4 | Sağlayıcı/model ekranlarında "Add" düğmesi kaldırıldı | Formlar `10a-formlar`'da; işlevsiz düğme yanlış vaat (ARCH-13). Mesaj anahtarları silinmedi (C13) |
| 5 | Vendor `components/ui/breadcrumb.tsx` `aria-label="breadcrumb"` çeviriye alındı | FOLLOWUP-44'ün yeni lint kuralı yakaladı |
| 6 | `test_10a_5_forbidden_route` ve `test_10a_7` fixme spec'i silindi | Sahte çerez senaryoları; yerine `test_10ab_6_role_screens` ve `test_10ab_1/2` (gerçek kullanıcılar) |
| 7 | "Backend unavailable" e2e'de yok | e2e servisi kendi stack'inin backend'ini durduramaz; `tests/unit/test_10ab_7_session.test.ts` (500, bozuk gövde, ağ hatası) kanıtlar |
| 8 | Test sırası ihlali: `lib/backend.ts`, `session-core.ts`, `project.ts`, `api/client.ts` testleri yazıldı ama kod yazılmadan önce kırmızı koşulmadı (test ve kod aynı adımda) | Açıkça yazıyorum. Kırmızı koşu kanıtı olanlar: `test_10ab_10` (kopya yokken 2/2 kırmızı), `test_10ab_12` (kural yokken 4/6 kırmızı) |
| 9 | Ara commit'ler 43c9196 ve 67a553d tek başına tip kontrolünden geçmez; a971e34 ve sonrası geçer | Dilim sınırı dosya bağımlılığını kesti; merge `--no-ff` |

## Değişen dosyalar

- Sözleşme ve tipler: `frontend/mocks/openapi-03a.yaml` (03a.yaml bayt kopyası), `frontend/lib/api/schema.d.ts` (üretilen), `frontend/scripts/check-api.mjs`, `frontend/package.json` (`gen:api`, `check:api`; `@tanstack/react-query` 5.105.0, `openapi-typescript` 7.13.0 dev; exact pin), `frontend/package-lock.json`.
- Backend bağlantısı: `frontend/next.config.ts` (rewrite), `frontend/lib/{backend,session,session-core,project}.ts`, `frontend/Dockerfile` (`ARG FFCORE_BACKEND_URL`), `deploy/docker-compose.yml` (frontend build arg + ortam; `e2e` servisi + `e2e_node_modules` volume'u).
- İstemci ve hata: `frontend/lib/api/{client,errors,queries}.ts`, `frontend/components/{query-provider.tsx,use-report-error.ts}`.
- Oturum ve gezinme: `frontend/lib/{access,navigation}.ts`, `frontend/components/{session-provider,route-guard,app-sidebar,nav-user,project-switcher,status-page,session-status-page,sign-out-button,write-gate}.tsx`, `frontend/app/page.tsx`, `frontend/app/(console)/layout.tsx`, `frontend/app/(auth)/login/page.tsx`; `components/not-connected.ts` silindi.
- Ekranlar: `frontend/app/(console)/{projects,projects/[id]/members,providers,models}/page.tsx`, `frontend/components/{screen,login-form,project-form,member-form}.tsx`.
- FOLLOWUP-44: `frontend/components/ui/{sidebar,breadcrumb}.tsx`, `frontend/eslint.config.mjs`.
- Metin: `frontend/messages/{en,tr}.json` (yalnız ekleme; eski anahtarlar silinmedi, C13).
- Testler: `frontend/tests/unit/test_10ab_{4,5,6,7,10,11,12}_*`, `test_10a_5`/`test_10a_6` güncel; `frontend/tests/e2e/{fixtures,global-setup,support}.ts`, `test_10ab_{1..7}_*.spec.ts`; `test_10a_{1,2,4,8}` gerçek girişe taşındı; `test_10a_5_forbidden_route` ve `test_10a_7_login_project_flow` silindi; `frontend/playwright.config.ts`.
- Docs: `docs/onyuz.md`, `docs/images/10a-*.png` (11 görüntü gerçek veriyle yenilendi; kalan 3'ü bayt aynı).

## Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Gerçek giriş; yanlış şifre `invalid_credentials`, çerez yok | `test_10ab_1_login.spec.ts` (2) | geçti |
| 2 | Süper yönetici proje oluşturur; geçersiz key alan hatası; kullanılmış key backend reddi; proje admin'inde düğme yok | `test_10ab_2_project_create.spec.ts` (3) | geçti |
| 3 | Üye ekle, `read` yap, çıkar; ayrılmış roller sunulmaz | `test_10ab_3_members.spec.ts` (2) | geçti |
| 4 | `admin+read`: 4 ekranda rozet, tüm değişiklik kontrolleri pasif, aynı liste; sayfadan `POST /projects` → 403 `read_only_access`; yazma yetkisi projeye göre | `test_10ab_4_read_only.spec.ts` (3), `unit/test_10ab_4_project_access` (4) | geçti |
| 5 | Açık sayfada yetkisi `read`'e çekilen kullanıcı → API 403 → "Read-only access"; kod eşlemesi | `test_10ab_5_forbidden_message.spec.ts` (1), `unit/test_10ab_5_error_mapping` (5) | geçti |
| 6 | Rol dışı ekran menüde yok, URL ile "no access"; proje admin'i tenant ekranlarını görmez | `test_10ab_6_role_screens.spec.ts` (2), `unit/test_10ab_6_role_screens` (3), `unit/test_10a_5_role_menu_visibility` (5) | geçti |
| 7 | Çerezsiz → giriş; üyeliksiz → "No project yet"; çıkış token'ı backend'de iptal eder; backend hatası "unavailable" | `test_10ab_7_session_boundary.spec.ts` (3), `unit/test_10ab_7_session` (5) | geçti |
| 8 | Bir ekran iki locale'de, gerçek oturum | `test_10a_8_locale_switch.spec.ts` (3) | geçti |
| 9 | Tema geçişi/kalıcılık/yanıp sönme yok; 7 ekran × 2 tema PNG; axe WCAG A/AA 0 ihlal | `test_10a_1` (1), `test_10a_2` (14), `test_10a_4` (14) | geçti |
| 10 | Sözleşme kopyası bayt aynı; roller/modlar enumla aynı; üretilen tip güncel | `unit/test_10ab_10_contract_copy` (2), `npm run check:api` | geçti |
| 11 | Backend adresi zorunlu ve http(s) origin; rewrite tek yer; tarayıcı kodunda mutlak adres yok | `unit/test_10ab_11_same_origin` (4); imaj build'i (komutlar tablosu) | geçti |
| 12 | FOLLOWUP-44 etiket çeviriden; `aria-label`/`title`/`placeholder`/`alt` sabit metni lint hatası | `unit/test_10ab_12_attr_literals` (6) | geçti |
| 13 | Sabit renk yok; her anahtar iki dosyada; WriteGate | `test_10a_3` (7), `test_10a_8_messages_keys`, `test_10a_6_write_gate` (2) | geçti |

Brief 10 kabullerinden bu PR dışı: Lighthouse ≥ 90 (FOLLOWUP-37, 10c); her ana ekranda edit/read görüntü karşılaştırması (10c, A3); sihirbaz ve onay akışları (10b-poc).

## Çalıştırılan komutlar

Ortam: Windows, Docker Desktop; Node yalnız konteynerde. Birim/lint: `node:20.19.5-alpine` + volume `ffcore-10a-nm`. e2e: compose `e2e` servisi (Playwright 1.64.1 imajı, digest pinli), stack `-p 10ab --env-file .env.test` (llmaas).

| Komut | Exit | Süre / sonuç |
|---|---|---|
| `npx tsc --noEmit` | 0 | |
| `npm run lint` | 0 | |
| `npx vitest run` | 0 | 11 dosya, 47 test |
| `npm run check:api` | 0 | kopya ve tip güncel |
| `docker compose --env-file .env.test config -q` / `--profile e2e config -q` | 0 / 0 | |
| `docker compose -p 10ab --env-file .env.test up -d --wait backend` | 0 | 25,5 s; migrate 03a+03b |
| `create-superadmin` (backend konteyneri, şifre stdin, sahte değer) | 0 | |
| `docker compose -p 10ab --env-file .env.test --profile e2e run --rm e2e` (1. koşu) | ≠0 | `npm ci` ETIMEDOUT (aynı anda imaj build'i ağı kullanıyordu); test koşmadı |
| aynı komut (2. koşu) | 0 | **48 passed (2,0 dk)**; toplam 2 dk 54 s (npm ci + next build dahil) |
| `docker build --build-arg FFCORE_BACKEND_URL=http://backend:8000 frontend` | 0 | 1 dk 39 s (`next build` imaj içinde) |
| `docker build frontend` (arg'sız, beklenen açık hata) | 1 | `Error: FFCORE_BACKEND_URL must be the backend origin (scheme://host:port), got "".` |
| `docker compose -p 10ab ... --profile e2e down -v` | 0 | konteyner 0, volume 0 kaldı |

NOT_RUN: backend `make test`/`make lint` (backend'e dokunulmadı); iki profil e2e (önyüz profil bağımsız, varsayım 4); Lighthouse (FOLLOWUP-37).

## Çıktı özeti ve post-state

Her e2e koşusu yeni sonekli 6 kullanıcı ve 2-3 proje yazar; stack geçici, `down -v` ile silinir. Kalıcı çıktı yalnız `docs/images/10a-*.png`. Log ve görüntülerde secret yok; şifre sahte (`dummy-not-secret-e2e-pw`), e-postalar `example.org`.

## Review r1 bulgu → düzeltme → kanıt

Review: state/reviews/10a-binding-r1.md (7229da7, DUZELT: MAJOR 1, MINOR 1); DUZELT K-10ab-0008.

| Bulgu | Düzeltme | Kanıt |
|---|---|---|
| MAJOR-1: `MemberForm` kullanıcı ve `ProjectSwitcher` proje sorgusu hata/pending'i boş seçeneğe çeviriyor (ARCH-06) | Ortak `QueryError` (`components/screen.tsx`; `ListState` de onu kullanır): eşlenmiş mesaj + kod + Details. İki seçicide üç durum ayrı: pending → pasif seçici "Loading…"; hata → seçici yerine `QueryError`, seçenek yok; gerçek boş → açık metin (`Members.noCandidates`, `ProjectSwitcher.noProjects`). Tarama: üçüncü örnek bulundu, üye formu `members.data ?? []` alıyordu; form artık üye listesi yüklenince açılır. Üye (süper yönetici değil) proje seçicisi `GET /projects` çağırmaz, üyelikleri kullanır | Birim `test_10ab_13_query_states` (5: 503 → kod görünür + seçici yok, pending → pasif, gerçek boş metni, süper yönetici proje 503, üye için çağrı yok). e2e `test_10ab_8_query_failures` (users 503 ve projects 503 tarayıcıda enjekte, backend gerçek) |
| MINOR-1: `ListState` 401'i mesaj yapıyor, `/login`'e yönlendirmiyor | `QueryCache` + `MutationCache` `onError`: her 401 (`invalid_credentials` hariç) → `/login?next=<yol>` (`lib/login-redirect.ts`); `useReportError` aynı yol. Giriş sayfası ve formu `next`'i yalnız `safeNext` (aynı origin göreli yol; `//`, mutlak URL, ters bölü reddedilir) ile kullanır | Birim `test_10ab_14_unauthenticated` (3: `loginUrl`, `safeNext` 6 güvensiz değer, sorgu 401 → `goToLogin`). e2e: oturum backend'de iptal, sekmeye dönüşte gerçek 401 → `/login?next=%2Fprojects` → yeniden giriş → `/projects` |

Önce kırmızı: birim testler kod yazılmadan önce koşuldu, 5 test kırmızı + `@/lib/login-redirect` import hatası (nedenler doğru: `query-error`/`member-no-candidates` yok, üye için fetch çağrıldı). e2e negatifleri 7229da7'de ayrı geçici worktree'de koşuldu: 3/3 kırmızı (users ve projects hatası görünmüyor; 401'de URL `/projects` kaldı ve sayfada eski "Your session has ended" mesajı var, yönlendirme yok).

Koşu notları (açıkça):
- İlk e2e kırmızı koşusunda 401 testi `visibilitychange`'i yalnız `document`'e gönderiyordu; TanStack Query v5 `window`'u dinler (konteynerde `@tanstack/query-core/build/modern/focusManager.js` okundu). O koşudaki 401 kırmızısı bu yüzden geçersiz sayıldı; test her ikisine gönderecek şekilde düzeltildi ve kırmızı koşu 7229da7'de yinelendi (yukarıdaki sonuç düzeltilmiş testindir).
- Düzeltme sonrası ilk tam koşu 49/51: düzeltilmemiş 401 testi ve `test_10ab_3` ayrılmış roller (form artık üye listesi yüklenince açıldığından test seçenekleri hemen okuyordu; test forma bekleyecek şekilde düzeltildi). İkinci koşu 50/51: 401 yönlendirmesi çalıştı (`/login?next=%2Fprojects`), ama test yardımcısı `signIn()` önce düz `/login`'e gittiği için `next` düşüyordu; `fillSignIn()` ile giriş mevcut sayfada yapıldı. Üçü de test sorunu; ürün kodu 89953ca'dan sonra değişmedi.

| Komut (r1, imaj `ffcore/backend:0.0.0-10ab`) | Exit | Sonuç |
|---|---|---|
| `npx tsc --noEmit`, `npm run lint`, `npm run check:api` | 0 | |
| `npx vitest run` | 0 | 13 dosya, 55 test |
| e2e negatif spec, 7229da7 geçici worktree (düzeltilmiş test) | 1 | 3/3 kırmızı, beklenen nedenler |
| `FFCORE_VERSION=0.0.0-10ab docker compose -p 10ab --env-file .env.test --profile e2e run --rm e2e` (628d416 test kodu) | 0 | **51 passed (2,4 dk)**, toplam 3 dk 16 s |
| `... --profile e2e down -v` | 0 | 10ab konteyner 0, volume 0 |
- ENV-74: ilk koşu denemelerinde paylaşılan `ffcore/backend:0.0.0` etiketi başka oturumlarca yeniden derlenmişti (DB'de `04a_0001` revizyonu); stack `down -v` + bu worktree'den `ffcore/backend:10ab`, sonra koordinatör kuralıyla `0.0.0-10ab` olarak yeniden etiketlendi (aynı imaj). Sonuç koşuları bu imajla.
- TanStack dinleyicisini okumak için `alpine:3` (pinsiz) bir kez çekildi ve hemen silindi; ürün ya da compose'a girmedi.

## Review r2 bulgu → düzeltme → kanıt

Review: state/reviews/10a-binding-r2.md (628d416, DUZELT: MAJOR 1; r1 bulguları kapandı); DUZELT K-10ab-0012.

| Bulgu | Düzeltme | Kanıt |
|---|---|---|
| MAJOR-1: `safeNext` TAB/LF/CR'ı reddetmiyor; `/` + TAB + `/backend:8000/healthz` URL ayrıştırıcısında `//backend:8000` olup girişten sonra başka origin'e gidiyor (açık yönlendirme) | `lib/login-redirect.ts`: (1) ham C0 (`\x00-\x1F`), DEL ve ters bölü; ayrıca yüzde kodlu `%00-%1F`, `%7F`, `%5C` reddi; (2) `new URL(next, REFERENCE)` ve `origin === REFERENCE`; (3) dönüş yalnız `pathname + search + hash` (ham değer değil); (4) reddedilen her değer `/`. Ek bulgu: `"/..//x"` nokta segmenti normalleşince yol `//x` oluyor (Node ile doğrulandı) ve yeniden kullanılınca başka origin; sonuç yolu `//` ile başlarsa da red | Birim `test_10ab_14_unauthenticated`: 20 güvensiz değer (TAB, LF, CR, NUL, DEL, `%09/%0A/%0d`, `//`, `/\`, `\/`, `http:`, `javascript:`, boşluklu ön ek, `/..//`, `%5C`, eski 6 değer) → `/`; "hiçbir sonuç başka origin'e çözülmez" özelliği; aynı origin yol/query/hash pozitifi. e2e `test_10ab_8`: gerçek giriş `/login?next=%2F%09%2Fbackend%3A8000%2Fhealthz` → origin konsolda kalır |

Önce kırmızı: birim 9 test kırmızı (TAB/LF/CR/NUL/DEL, üç kodlu varyant, origin özelliği); e2e gerçek girişte kırmızı: `Received: "http://backend:8000"` (inceleyicinin bulgusu birebir). Düzeltme sonrası ilk birim koşusunda origin özelliği `/..//x` ile bir kez daha kırmızı (yukarıdaki ek bulgu), ikinci satırla kapandı.

Not: `safeNext` giriş sayfasında sunucuda da koşar (`window` yok). Koordinatörün "`window.location.origin` ile karşılaştır" kuralı sabit bir referans origin'le (`http://console.invalid`, RFC 2606 ayrılmış ad) uygulandı: kontrol "referansla aynı origin" olduğundan sonuç aynıdır. `test_10ab_11` tarayıcı kodunda mutlak adres taramasına bu ad istisna eklendi.

| Komut (r2, imaj `ffcore/backend:0.0.0-10ab`) | Exit | Sonuç |
|---|---|---|
| `npx tsc --noEmit`, `npm run lint` | 0 | |
| `npx vitest run` | 0 | 13 dosya, 76 test |
| e2e "another origin" testi, düzeltme öncesi (628d416 ürün kodu) | 1 | kırmızı, origin `http://backend:8000` |
| `FFCORE_VERSION=0.0.0-10ab docker compose -p 10ab --env-file .env.test --profile e2e run --rm e2e` (e9fe396) | 0 | **52 passed (3,1 dk)** |
| `... --profile e2e down -v` | 0 | 10ab konteyner 0 |

## Kontrol listesi
- [x] Felsefe ile çelişen bir nokta varsa işaretlendi, sessizce geçilmedi (sapma 8: test sırası)
- [x] Donmuş sözleşme kırılmadı (C13 yalnız ekleme; 03a OpenAPI tüketildi, değişmedi)
- [ ] İki profil testi: NOT_RUN, gerekçe varsayım 4 (önyüz profil bağımsız; backend kodu değişmedi)
- [x] Salt-okunur mod: API 403 (`test_10ab_4`), önyüz gösterimi (`test_10ab_5`); audit backend'in (03a/03b)
- [x] Log, API, audit, hata gövdesi secret-free (önyüz secret görmez; çerez HttpOnly)
- [x] Metinler `en.json` kaynak + `tr.json`; iki tema test edildi (PNG + axe)
- [x] Docs güncel (`docs/onyuz.md`)
- [x] Durum kanal mesajıyla bildirildi

## Kalan riskler

1. `Secure` çerez yalnız `localhost` ya da HTTPS üzerinde tutulur. Sunucuda konsol `http://<ip>:3000` ile açılırsa giriş çalışmaz; kurulum HTTPS ya da ters vekil ister (12; şu an belgede yok). FOLLOWUP önerisi.
2. Rewrite adresi imaja build anında gömülür (`http://backend:8000`): imaj, backend servis adının `backend` olduğu kurulumlara bağlı. 12 paketleme farklı topoloji isterse build arg değişir.
3. Proje admin'i (süper yönetici değil) üye ekleyemez: 03a'da kullanıcı listesi tenant düzeyi, proje kapsamlı kullanıcı arama ucu yok. FOLLOWUP önerisi: e-postayla üye ekleme ya da aday listesi ucu (03 additive).
4. Sağlayıcı ve model ekranlarında e2e verisi boş durumda (oluşturma formları `10a-formlar`'da); satır çizimi yalnız tip kontrolüyle doğrulandı. `10a-formlar` e2e'si gerçek satırla kapatır.
5. İlk e2e koşusu ağ zaman aşımıyla düştü (npm ci); CI'da npm önbelleği/aynası gerekir (12).
6. `/auth/me` her sunucu sayfa isteğinde bir kez çağrılır (önbellek yok); pilot ölçeğinde sorun beklenmez, ölçülmedi.
