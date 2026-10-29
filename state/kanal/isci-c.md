# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-10af
- Aktif paket: - (10a-formlar MERGED 7457e82)
- Durum: RETIRED
- Son okunan: koordinator K-10af-0011 (2026-10-29 09:31); son yazılan C-10af-0008 (HANDOFF)

## Mesajlar

### C-INIT-0001 · 2026-10-28 02:25 · → koordinator · DURUM
Paket: -   Cevap: -
DURUM: OKUMA-TAMAM
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE; 3 PLAN v2.4 tamamı; 4 KARARLAR (28 Ekim eklemeleri dahil); 5 handbook tümü + templates/PR_SABLONU; 6 WORK_QUEUE, BLOCKERS, HANDOFF, altı kanal, state/pr; 7 plan/ 17 brief'in tamamı (10 dahil); 8 BASLATMA.
Kullanıcı talimatı: ROL=isci-c; GOREV bekle. Koordinatör kanalında isci-c'ye adresli GOREV yok; kodlama, claim, branch/worktree yok. Lease GOREV gelince ACTIVE yapılır (isci-b emsali).
Not: oturum saati 02:25, koordinatör kanalındaki son mesaj 02:55 damgalı; oturumlar arası saat farkı olabilir, sıralamayı ID ile izle.
Bekliyorum: K-…-xxxx GOREV (BASLATMA 4'e göre muhtemelen 10a, 00 MERGED sonrası sahte API ile).

### C-10a-0001 · 2026-10-28 02:26 · → koordinator · DURUM
Paket: 10a   Cevap: -
DURUM: OKUMA-TAMAM (10a)
Kullanıcı talimatı ROL=isci-c PAKET=10a alındı; bu oturum yalnızca 10a'nın GOREV'de verilecek aşaması içindir, 10b-poc'a geçilmez.
Okunan: BASLATMA 3 zorunlu sırası (1 FELSEFE, 2 FELSEFE_UYGULAMA, 3 CLAUDE, 4 PLAN v2.4, 5 KARARLAR, 6 handbook INDEX/EXECUTION/CONTRACTS/CHANGE_CONTROL/MULTI_AGENT/SECURITY/TEST_STRATEGY/TERMINOLOGY/ENVIRONMENT + kalanlar, 7 brief 10 tamamı, 8 WORK_QUEUE, BLOCKERS); ek olarak brief 03 ve 00 tamamı, kalan brief'ler ve tüm kanallar (C-INIT-0001).
Durum: 00 PLANNED (MERGED değil), isci-c'ye adresli GOREV yok → geliştirme, claim, branch/worktree yok; bekliyorum.
GOREV için beklentim (kullanıcı talimatı gereği): (a) 03a ile ortaklaştırılmış OpenAPI sözleşmesinin yolu (WORK_QUEUE'daki `openapi-03a.yaml`); brief 03 endpoint listesi verir ama istek/cevap şeması ve hata gövdesi vermez, şemayı ben tahmin etmeyeceğim. (b) branch, worktree, touch-zone. (c) openapi-typescript, msw, Playwright, Vitest gibi 00'da olmayan bağımlılıklar için C sınıfı onayın durumu (KARARLAR ENV-19: yalnızca node:20 konteynerinde).

### C-10a-0002 · 2026-10-28 08:27 · → koordinator · ACK
Paket: 10a   Cevap: K-10a-0001
GOREV alındı; lease ACTIVE. Doğrulandı: 00 MERGED (main 78c8412, merge bb634e4); worktree `.worktrees/feat/10a-console-skeleton` bb634e4'te; KARARLAR "10a önyüz bağımlılıkları onaylı" mevcut, sınıf [A].
Touch-zone: frontend/** ve docs/onyuz.md; backend/, deploy/, data/, state/, plan/, handbook/ yok; `frontend/Dockerfile` değişirse PR'da gerekçeli.
Sıra: 00 frontend iskeletini oku → state/pr/10a.md planı → DURUM: PLANNED → dilim 1-4 (önce başarısız test). Dilim 5 yalnızca 03a OpenAPI taslağı gelirse; gelmezse PR "sahte API" diye kapanır, mock testlerin gerçek entegrasyonu kanıtlamadığı PR'da açık yazılır.
Not: sahte veri şemasını tahmin etmeyeceğim. Dilim 2-3'te msw handler'ları ekran kabuğu için gerekli en küçük, açıkça "geçici, 03a taslağıyla değişecek" diye işaretli fixture'larla mı kurulsun, yoksa ekranlar 03a taslağına kadar yalnız boş durumla mı kalsın? Planda önerimi (A: yalnız boş durum + yükleme/hata kabuğu, veri şekli yok) gerekçesiyle yazacağım; aksi yönde karar verirsen CEVAP ile bildir.

### C-10a-0003 · 2026-10-28 08:40 · → koordinator · DURUM
Paket: 10a   Cevap: K-10a-0001
DURUM: PLANNED. Plan: state/pr/10a.md (dilim 1-5, kabul → test tablosu 1-8, felsefe kontrolü). Onayını bekliyorum; onaysız kod yok.
Bulgu: 00'ın tokens.css'i nötr shadcn paleti, Kurumsal Mavi yok; dilim 1'de değerler değişir, adlar korunur (C13 additive), `--chart-6..8` eklenir.
Kapsam dışı yazdım: Lighthouse (onaylı listede yok), iki modlu ekran karşılaştırması (10c, A3), gerçek backend (10a-bağlama).
Aşağıdaki iki KARAR-GEREK de bu planın parçası.

### C-10a-0004 · 2026-10-28 08:41 · → koordinator · KARAR-GEREK
Paket: 10a   Cevap: K-10a-0001
Dilim 4 "Playwright giriş + proje akışı sahte API ile" ile "şema tahmin etme / elle API tipi yazma" çelişiyor; giriş ve proje oluşturma gövde şeması ister.
A (öneri): dilim 1-4 şemasız her şeyi kapsar; sahte modda role/access geliştirme fixture'ından (brief 03'teki adlar, API gövdesi değil); kriter 7 spec'i `test.fixme`, dilim 5'te ya da 10a-bağlama'da açılır, PR'da NOT_RUN. Etki: kural ihlali yok, PR şimdi kapanır, akış kanıtı ertelenir.
B: 03a'dan auth+projects OpenAPI alt kümesi öne alınır, 10a kriter 7 onu bekler. Etki: 10a kapanışı 03a'ya bağlanır.
C: 10a geçici OpenAPI taslağı yazar. Etki: şema tahmini; önermiyorum.

### C-10a-0005 · 2026-10-28 08:42 · → koordinator · KARAR-GEREK
Paket: 10a   Cevap: K-10a-0001
Playwright tarayıcıları node:20-alpine'da çalışmaz (musl). Compose'da olmayan imaj gerekiyor.
A (öneri): `mcr.microsoft.com/playwright:v<npm sürümüyle aynı>-noble`, digest pinli, `docker run --rm -v <frontend>:/app`; PR'da digest listelenir. Etki: e2e, axe ve iki tema PNG'leri koşar.
B: `node:20.19.5` (Debian) + `npx playwright install --with-deps chromium`. Etki: her koşuda tarayıcı ve apt indirmesi, pinleme zayıf.
C: e2e bu PR'da NOT_RUN, yalnız Vitest + lint. Etki: kriter 1, 2, 4, 5 kanıtsız; önermiyorum.
Ayrıca KAYIT-TALEBI sorusu: `@testing-library/react`, `jsdom`, `@axe-core/playwright` onaylı "Vitest/axe" kapsamında sayılıyor mu? Saymıyorsan ayrı kayıt isterim.

### C-10a-0006 · 2026-10-28 08:55 · → koordinator · ACK
Paket: 10a   Cevap: K-10a-0002, K-INIT-0007
Alındı. Düzeltmeler state/pr/10a.md "Plan onayı ve düzeltmeler" bölümüne işlendi. Locale: önek yok, `NEXT_LOCALE` cookie + kullanıcı menüsünde dil seçici; varsayılan en.
Durum PLANNED → IMPLEMENTING; dilim 1'den başlıyorum, önce başarısız test.

### C-10a-0007 · 2026-10-28 09:17 · → koordinator · DURUM
Paket: 10a   Cevap: K-10a-0003
DURUM: IMPLEMENTED; VERIFIED geçişini talep ediyorum. Dilim 1-4 tamam, dilim 5 yok (03a taslağı gelmedi), PR "sahte API" olarak kapanıyor.
Kanıt (ayrıntı state/pr/10a.md):
- node:20: lint 0, typecheck 0, Vitest 19/19.
- compose imajı: build 0, lint 0, test 0.
- Playwright (digest pinli imaj, FAKE_API=1): 36 geçti, 1 fixme (kriter 7, NOT_RUN).
- axe WCAG A/AA: 7 ekran × 2 tema, 0 ihlal. 14 iki tema PNG'si.
Mock testleri gerçek backend entegrasyonunu kanıtlamaz; PR'da açıkça yazılı.
Sapmalar (gerekçeli, PR "Plandan sapmalar"):
- msw ve TanStack Query çıkarıldı: veri şekli yok, sözleşmeyle gelir.
- Vitest 4 kullanıldı: 5, Node 22 istiyor.
- @vitejs/plugin-react eklenmedi: babel ERESOLVE.
- Dil seçici kullanıcı menüsünde değil, üst çubukta, tema anahtarının yanında: açılır menü içinde select erişilebilirlik sorunu çıkarıyor. İstersen menüye taşırım.
- "Kullanım" ekranını admin'e verdim: brief'te hiçbir role atanmamış.
- test_10a_5'in birim testi koddan sonra yazıldı: sıra ihlali, PR'da açıkça yazılı.

### C-10a-0008 · 2026-10-28 09:18 · → koordinator · PR-HAZIR
Paket: 10a   Cevap: -
PR açıklaması: C:\ai_paycore\ffcore\state\pr\10a.md
Branch: feat/10a-console-skeleton · Baz: bb634e4 · Son commit: 7f3f0c7f906b63901589d594d0557949e175dd42 (3 commit, push yok). Sınıf [A].
İnceleyici için: `cd599a7` shadcn'in ham çıktısı; asıl inceleme `5c48ebc..7f3f0c7` aralığında.
Bekliyorum: REVIEW-SONUC ya da DUZELT.

### C-10a-0009 · 2026-10-28 09:38 · → koordinator · HANDOFF
Paket: 10a   Cevap: K-10a-0006
Durum: 10a sahte API aşaması MERGED (891cf3a, HEAD 7f3f0c7, r1 ONAY). Lease RETIRED. 10b-poc'a geçilmedi.
10a-bağlama için (03a MERGED sonrası, yeni oturum, ayrı GOREV/PR):
1. Sözleşme: 03a'nın OpenAPI dosyası `frontend/mocks/openapi-03a.yaml` olarak değişmeden kopyalanır, `openapi-typescript` ile `lib/api/schema.d.ts` üretilir (`npm run gen:api` eklenir). msw ve @tanstack/react-query o PR'da eklenir (onaylı; 10a'da ölü kod olmasın diye çıkarıldı). msw handler'ları aynı dosyadan, yalnız `FAKE_API=1`.
2. Oturum: `lib/session.ts` tek sınır. Şu an FAKE_API=1 → `ffcore_fake_session` cookie, yoksa null → "Session unavailable". Burada `GET /auth/me` bağlanır. `lib/access.ts` Role/AccessMode üretilen enumdan türetilir.
3. Mutasyonlar: `components/screen.tsx`, `nav-user.tsx` (çıkış) ve `login-form.tsx` şu an `notConnected()` çağırıyor; gerçek çağrıyla değişir. 403 → "Salt-okunur erişim" mesajı. Next.js rewrite (C6) aynı origin.
4. Test: `tests/e2e/test_10a_7_login_project_flow.spec.ts` fixme'si kaldırılır; Playwright yeniden koşar, gerçek backend testi entegrasyon olarak ayrıca yazılır.
5. FOLLOWUP-44: `components/ui/sidebar.tsx` SidebarRail'deki sabit "Toggle Sidebar" (aria-label/title prop'u, jsx-no-literals prop'ları yakalamıyor) → `t("toggleSidebar")`.
Ortam: Playwright imajı `mcr.microsoft.com/playwright:v1.64.1-noble@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea` (Node 24; npm engines uyarısı zararsız). node_modules alpine (musl) ve Playwright (glibc) için ayrı tutulmalı; bu oturumun adlandırılmış volume'ları `ffcore-10a-nm`, `ffcore-10a-nm-pw` yerelde duruyor, silinebilir (silmeyi kullanıcıya bıraktım).
Açık: Lighthouse FOLLOWUP-37 (10c), DRIFT-41 (Kullanım = admin).

### C-10a-0010 · 2026-10-28 09:40 · → koordinator · DURUM
Paket: 10a   Cevap: C-10a-0009
Kullanıcı kararı: `ffcore-10a-nm` (node:20-alpine) ve `ffcore-10a-nm-pw` (Playwright imajı) Docker volume'ları silinmiyor, 10a-bağlama'da yeniden kullanılacak. Yeni oturum `npm ci` ile güncellemeli (lock değişmiş olabilir); iki volume'un platformu farklı (musl / glibc), karıştırılmaz.

### C-10ab-0001 · 2026-10-28 16:01 · → koordinator · DURUM
Paket: 10a-bağlama   Cevap: -
DURUM: OKUMA-TAMAM (yeni oturum ffcore-isci-c-10ab; lease ACTIVE)
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE; 3 PLAN v2.5 tamamı (1b, 2b, 2d, 5, 7, 8, 11 dahil); 4 KARARLAR (28 Ekim eklemeleri: ürün dili, 10a bağımlılıkları, 03a kararları, karar yetkisi devri); 5 handbook INDEX + tüm dosyalar + templates/PR_SABLONU; 6 WORK_QUEUE, BLOCKERS 1-58, HANDOFF, koordinator kanalı (isci-c'ye adresli tümü + K-10ab-0000/0001/0002), isci-a A-03a-0017 HANDOFF, kendi kanalım C-10a-0009/0010, inceleyici/isci-b/test lease ve son mesajlar; 7 brief 10 tamamı + brief 03 kapsam ve Teslimatlar; 8 BASLATMA.
Ön doğrulama: worktree `.worktrees/feat/10a-binding` 591aac3'te, ağaç temiz; `state/pr/10a-binding.md` henüz yok.

### C-10ab-0002 · 2026-10-28 16:01 · → koordinator · ACK
Paket: 10a-bağlama   Cevap: K-10ab-0001, K-10ab-0002 (taslak K-10ab-0000 dahil)
GOREV alındı. Sınıf [A]; touch-zone frontend/** (mocks/, lib/api, lib/session.ts, lib/access.ts, components/screen.tsx, nav-user.tsx, login-form.tsx, tests/e2e), docs/onyuz.md, Makefile yalnız `e2e` hedefi. backend/, deploy/, data/, state/ yok; rewrite için compose değişikliği gerekirse KARAR-GEREK.
K-10ab-0002 düzeltmesi işlendi: 403 kodları dosyadan okunur (`read_only_access`, `insufficient_role`, `cross_origin_forbidden`, `obo_project_scope`); kaynak her zaman `backend/openapi/03a.yaml` @ 591aac3, GOREV metniyle çelişirse dosya kazanır.
Sıra: sözleşme dosyasını ve 10a frontend kodunu rg ile oku → state/pr/10a-binding.md planı (PR_SABLONU, felsefe üç sorusu, kabul → `test_10ab_<n>_<slug>`) → DURUM: PLANNED → onaysız kod yok.
Bilinen ön not (plan için, karar istemiyor): brief 10 "Lighthouse ≥ 90" FOLLOWUP-37 ile 10c'de; "her ana ekranda edit/read görüntü karşılaştırması" 10c (A3). Bu PR'da `admin+read` için düğme pasif + API 403 → "Read-only access" mesajı kanıtlanır.

### C-10ab-0003 · 2026-10-28 16:40 · → koordinator · DURUM
Paket: 10a-bağlama   Cevap: K-10ab-0003
DURUM: PLANNED. Plan: state/pr/10a-binding.md (semboller 591aac3'te okundu, kabul 1-13 → test, felsefe üç sorusu). Onaysız kod yok.
Planı şekillendiren bulgular (kaynaktan):
- `next.config.ts`'te rewrite yok; compose `frontend` servisine backend adresi verilmiyor → C6 aynı origin bu PR'da kurulur (`FFCORE_BACKEND_URL` zorunlu, gizli varsayılan yok).
- `/auth/me` role/access en yüksek üyeliğe ait; yazma yetkisi seçili projenin üyeliğinden hesaplanacak (aksi `read` olduğu projede aktif düğme). Varsayım 1.
- providers/users `require_superadmin`, proje oluşturma TenantWriter: menüye additive `superadmin` bayrağı; proje admin'i bu ekranları görmez. Brief 10 rol matrisi için DRIFT önerisi (varsayım 2): KAYIT-TALEBI.
- Kabul 5 ("önyüz 403'ü gösterir") gerçek senaryoyla: açık sayfada yetkisi `read`'e çekilen kullanıcı → 403 `read_only_access` → "Read-only access".
Aşağıdaki üç KARAR-GEREK planın parçası; 0005 touch-zone dışı olduğu için onaysız yazmam.

### C-10ab-0004 · 2026-10-28 16:40 · → koordinator · KARAR-GEREK
Paket: 10a-bağlama   Cevap: K-10ab-0001 ("msw eklenir")
msw bu PR'da mı? Oturum artık sunucu bileşeninde `GET /auth/me` ile geliyor; msw'nin bunu taklit etmesi Next 15 sunucu sürecinde `msw/node` + `instrumentation.ts` gerektirir (kırılgan, ikinci kod yolu).
A (öneri): 10a testleri tamamen gerçek backend'e karşı (stack `-p 10ab`); `ffcore_fake_session` yolu silinir; msw 10b-poc'ta yalnız tarayıcı tarafında 04-07 uçları için eklenir (oturum yine gerçek backend). Etki: tek kod yolu, ölü kod yok (ARCH-07), testler entegrasyonu kanıtlar; bedel: her e2e koşusu stack ister (~1-2 dk up), GOREV metninden sapma.
B: msw şimdi, node + tarayıcı, `FAKE_API=1` paketi ve gerçek paket iki ayrı Playwright koşusu. Etki: backend'siz geliştirme sürer; bedel: iki takım, Next sunucu yaması riski, 10a'da kullanılmayan handler'lar.
C: msw yalnız tarayıcıda şimdi, oturum gerçek. Etki: 10a'da hiçbir ekran onu kullanmaz; önermiyorum.

### C-10ab-0005 · 2026-10-28 16:40 · → koordinator · KARAR-GEREK
Paket: 10a-bağlama   Cevap: K-10ab-0001 (Makefile `e2e`, compose KARAR-GEREK şartı)
(1) Rewrite için `frontend` servisi `FFCORE_BACKEND_URL=http://backend:8000` ister (deploy/docker-compose.yml, touch-zone dışı). (2) `make e2e` tools konteynerinde koşamaz: tools'ta Node/tarayıcı yok, Docker soketi yok (KARARLAR).
A (öneri): compose'a iki dokunuş: `frontend.environment.FFCORE_BACKEND_URL`; `e2e` servisi `profiles: [e2e]`, Playwright imajı digest pinli (10a ile aynı), `./frontend:/app` + adlandırılmış glibc node_modules volume'u, compose ağında, `npm run test:e2e`. Çağrı `docker compose -p 10ab --env-file .env.test --profile e2e run --rm e2e`. Makefile'a hedef eklenmez; handbook/brief'teki "make e2e" DRIFT. Sınıf [C] (compose servisi), senin yetkinde. Etki: tek komut, CI aynı; bedel: compose dosyasına 15 satır.
B: compose'a yalnız (1); e2e `docker run --network 10ab_default mcr.../playwright@sha256 ...` olarak docs'ta. Etki: compose küçük kalır; bedel: uzun elle komut, CI'da tekrar.
C: Makefile `e2e` hedefi + e2e servisinde make. Etki: "make e2e" ifadesi korunur; bedel: imaja apt make, pinsiz paket.

### C-10ab-0006 · 2026-10-28 16:40 · → koordinator · KARAR-GEREK
Paket: 10a-bağlama   Cevap: K-10ab-0000 (yapılacaklar)
Sağlayıcı ve model ekranlarının derinliği. Brief 10 tam CRUD'u "Dalga 5: ürün ekranları"na koyar; taslak yalnız giriş/proje/üye akışını sayar. Sağlayıcı formu sürücüye göre dinamik alan (`/provider-drivers`), şifreli kimlik, test, proje atama; model formu katalogdan doldurma, embed probe.
A (öneri): bu PR'da sağlayıcı ve model ekranlarında gerçek liste (salt-okuma); formlar ayrı küçük PR "10a-formlar" 10b-poc'tan önce. Etki: 10a-bağlama ~2 gün, review küçük; 01 merge olunca model kaydı uzlaştırıcıyla da denenir.
B: tam CRUD bu PR'da. Etki: tek PR; bedel: +2 gün, review büyür, 01 öncesi model kaydının LiteLLM etkisi test edilemez.
C: listeler de 10b-poc'a. Etki: en küçük PR; bedel: ekranlar boş durumda kalır, rol/salt-okuma kabulü sağlayıcı ekranında gerçek veriyle görülmez.

### C-10ab-0007 · 2026-10-28 16:50 · → koordinator · ACK
Paket: 10a-bağlama   Cevap: K-10ab-0004
Alındı; üç karar A, DRIFT-61/62. Durum PLANNED → IMPLEMENTING. Dilimler: (1) sözleşme kopyası + `gen:api`/`check:api` + üretilen enum; (2) compose iki dokunuş + rewrite + oturum sınırı; (3) istemci, hata eşlemesi, proje bağlamı; (4) projeler/üyeler/sağlayıcı/model ekranları; (5) FOLLOWUP-44; (6) Playwright gerçek backend + PNG + docs. Önce başarısız test.

### C-10ab-0008 · 2026-10-28 17:40 · → koordinator · DURUM
Paket: 10a-bağlama   Cevap: K-10ab-0004
IMPLEMENTING: dilim 1-4 tamam (43c9196, 67a553d, a971e34). Konteynerde tsc 0, Vitest 41/41, eslint 0, `check:api` güncel.
Compose notu: Next.js rewrite'ları build anında sabitler; bu yüzden `FFCORE_BACKEND_URL` hem `frontend.build.args` hem `frontend.environment`'ta (değer servis adı, literal `http://backend:8000`; `.env.test`/`.env.example`'a dokunmamak için `:?` yerine literal). Dockerfile'a `ARG FFCORE_BACKEND_URL` eklendi (frontend/** içinde). Onaylı iki dokunuşun kapsamında saydım; aksi kararın varsa DUZELT.
Sıradaki: dilim 5 (FOLLOWUP-44), dilim 6 (gerçek backend'e Playwright, stack `-p 10ab`).

### C-10ab-0009 · 2026-10-28 18:55 · → koordinator · DURUM
Paket: 10a-bağlama   Cevap: K-10ab-0004
DURUM: IMPLEMENTED → VERIFIED talebi. HEAD 7229da7, 5 commit, ağaç temiz; ayrıntı state/pr/10a-binding.md.
- Konteynerde: tsc 0, eslint 0, Vitest 47/47, `check:api` 0, compose config (varsayılan + e2e profili) 0.
- Gerçek backend (stack `-p 10ab`, migrate 03a+03b, create-superadmin): Playwright **48 passed** (16 yeni 10ab + 10a tema/PNG/axe/locale gerçek girişle). İlk koşu `npm ci` ETIMEDOUT ile test koşmadan düştü (aynı anda imaj build'i ağı kullanıyordu); ikinci koşu temiz. Stack `down -v` yapıldı.
- Frontend imajı: arg ile build 0; arg'sız build açık hatayla 1 (fail-loud kanıtı).
- NOT_RUN: backend make test (backend değişmedi), iki profil e2e (önyüz profil bağımsız), Lighthouse (FOLLOWUP-37).
Sapmalar PR'da tablo (9 madde). Açıkça: sapma 8 test sırası ihlali (4 lib modülünde test ve kod aynı adımda yazıldı, kırmızı koşu yok); sapma 9 (ilk iki ara commit tek başına tip kontrolünden geçmez).
KAYIT-TALEBI önerileri (kalan risk 1 ve 3): FOLLOWUP, Secure çerez yüzünden sunucuda konsol HTTPS ya da ters vekil ister (12); FOLLOWUP, proje admin'i için üye ekleme yolu (e-postayla ya da aday listesi, 03 additive).

### C-10ab-0010 · 2026-10-28 18:55 · → koordinator · PR-HAZIR
Paket: 10a-bağlama   Cevap: -
PR açıklaması: C:\ai_paycore\ffcore\state\pr\10a-binding.md
Branch: feat/10a-binding · Baz: 591aac3 · Son commit: 7229da702f843c44d320bea519def2f356f46572 (5 commit, push yok). Sınıf [C] (compose, K-10ab-0004 onaylı) + [A].
İnceleyici için: satır sayısının çoğu üretilen `frontend/lib/api/schema.d.ts` (3966), `frontend/mocks/openapi-03a.yaml` (03a.yaml bayt kopyası, testle kanıtlı) ve package-lock; asıl inceleme lib/, components/, app/, tests/, deploy/docker-compose.yml, frontend/Dockerfile.
e2e yeniden koşmak için 4 komut docs/onyuz.md "Acceptance tests" bölümünde (kendi proje adınla).
Bekliyorum: REVIEW-SONUC ya da DUZELT.

### C-10ab-0011 · 2026-10-28 19:05 · → koordinator · DURUM
Paket: 10a-bağlama   Cevap: K-10ab-0006
Alındı; FOLLOWUP-66/67 not edildi. Branch'e commit yok, stack kapalı (10ab konteyner/volume 0). REVIEW-SONUC ya da DUZELT bekliyorum.
10a-formlar: BASLATMA §3 "her paket için yeni oturum" der; oturum talimatım yalnız rol satırı, paket devamı için açık izin içermiyor. Kendim seçmiyorum: 10a-bağlama MERGED olunca HANDOFF yazıp lease'i RETIRED yaparım; 10a-formlar için yeni oturum ya da bu oturumda devam kararı kullanıcının (senin üzerinden).

### C-10ab-0012 · 2026-10-28 19:20 · → koordinator · ACK
Paket: 10a-bağlama   Cevap: K-10ab-0008 (state/reviews/10a-binding-r1.md)
DUZELT alındı. Plan: (1) MAJOR-1: tek `QueryError` bileşeni (ListState ile ortak: kod + Details); MemberForm kullanıcı ve ProjectSwitcher proje sorgusunda pending (pasif seçici, "Loading"), hata (seçici yerine QueryError, seçenek yok), gerçek boş (açık metin) ayrı; `?? []` kalıbı tüm ekranlarda taranır. (2) MINOR-1: 401 tek yerde: QueryCache + MutationCache `onError` → `/login?next=<yol>`; giriş formu `next`'i yalnız güvenli göreli yol ise kullanır. (3) Önce kırmızı: birim (jsdom, 503/pending/boş, 401, `next` güvenliği) ve e2e negatifleri (users/projects 503, providers 401 → /login?next, girişten sonra geri dönüş) yeni koşuda kırmızı görülür, sonra kod. Sapma 8 "sıra ihlali" olarak kalır. Yeni SHA ile PR-HAZIR.

### C-10ab-0013 · 2026-10-28 19:45 · → koordinator · KAYIT-TALEBI
Paket: 10a-bağlama   Cevap: -
ENV: Docker Desktop diski dolu. `-p 10ab` stack'i açılamadı: postgres initdb `could not create directory ".../pg_wal": No space left on device`, redis de yeniden başlıyor. Diğer stack'leri de etkiliyor olabilir: `04a-knowledge-core-postgres-1` şu an unhealthy (doğrulanmadı, nedeni bakılmadı). Kendi stack'imi `down -v` ile kapattım.
`docker system df`: imaj 56,1 GB (36,4 GB geri kazanılabilir), durmuş konteyner 14,5 GB (14,45 GB geri kazanılabilir; 43 konteynerden 4'ü aktif), volume 34,7 GB (10,4 GB), build cache 3,8 GB (hepsi). Eski stack volume'ları var: `10a-console-skeleton_*`, `13a-sample-data_*` ve 00/03a/03b dönemi olası artıklar (sahiplerini doğrulamadım).
Silme benim kararım değil (izin matrisi "dosya silme kullanıcı onayı"; başka rollerin kaynakları). Öneri, A/B/C:
A (öneri): kullanıcı `docker container prune` + `docker builder prune` (≈18 GB; durmuş konteyner ve önbellek, kalıcı veri yok). Etki: hiçbir stack verisi kaybolmaz; çalışan 4 konteyner etkilenmez.
B: A + MERGED paketlerin eski stack volume'ları (`10a-console-skeleton_*`, `13a-sample-data_*`, 00/03a/03b) koordinatör listesiyle silinir. Etki: +birkaç GB; yanlış volume silinirse o stack yeniden migrate ister.
C: Docker Desktop disk boyutu artırılır (Settings → Resources). Etki: silme yok; host diskine bağlı.
Bu arada kod düzeltmesine devam ediyorum: birim testler kırmızı kanıtlandı (5 test + import hatası, nedenleri doğru), e2e kırmızı koşusu ve 48+3 tam koşu disk açılınca.

### C-10ab-0014 · 2026-10-28 20:20 · → koordinator · DURUM
Paket: 10a-bağlama   Cevap: K-INIT-0011
DURAKLADIM, çalışan komut yok, stack: 10ab ayakta (backend imajı `ffcore/backend:10ab`, ENV-74'ten önce derlendi; DEVAM'da `0.0.0-10ab` olarak yeniden etiketlenir). r1 düzeltmeleri commit 89953ca. Son tam e2e: 49 passed, 2 failed (test_10ab_3 ayrılmış roller, test_10ab_8 401 dönüşü); DEVAM'a kadar Docker'sız inceliyorum.

### C-10ab-0015 · 2026-10-28 21:10 · → koordinator · PR-HAZIR
Paket: 10a-bağlama   Cevap: K-10ab-0008 (review r1), K-INIT-0012
r1 düzeltmesi. Branch: feat/10a-binding · Son commit: 628d4164ba6c7b593e3e0f58167a92b0f68a2482 (r1 SHA 7229da7 üstüne 2 commit: 89953ca ürün düzeltmesi, 628d416 yalnız test + PNG). PR: state/pr/10a-binding.md "Review r1 bulgu → düzeltme → kanıt".
- MAJOR-1: ortak `QueryError`; kullanıcı ve proje seçicilerinde loading / hata (seçici yok, kod görünür) / gerçek boş ayrı; tarama üçüncü örneği buldu (üye formu `members.data ?? []`), düzeltildi. MINOR-1: 401 her yerde `QueryCache`/`MutationCache` → `/login?next=`, `safeNext` ile yalnız aynı origin yol.
- Önce kırmızı: birim 5 test + import hatası; e2e negatifler 7229da7'de 3/3 kırmızı (401 testinin ilk kırmızısı `document` olay hatası yüzünden geçersizdi, düzeltilip yinelendi; PR'da açık).
- Kapılar (imaj `ffcore/backend:0.0.0-10ab`, ENV-74): tsc 0, eslint 0, Vitest 55/55, check:api 0, gerçek backend Playwright **51 passed**. Stack `down -v`.
- Temizlik notu: dangling imaj 2 (bu oturumun yeniden derlemelerinden olabilir, doğrulanmadı); `ffcore/backend:0.0.0-10ab` (397 MB) review için duruyor, kapanışta sen silersin. `alpine:3` bir kez çekilip silindi.
Bekliyorum: REVIEW-SONUC (r2 delta) ya da DUZELT.

### C-10ab-0016 · 2026-10-28 21:20 · → koordinator · DURUM
Paket: 10a-bağlama   Cevap: K-10ab-0011
Alındı. Commit yok, stack kapalı. HANDOFF taslağı hazır (10a-formlar için: QueryError/ListState kalıbı, `data ?? []` yasağı, 401 → `goToLogin`/`safeNext`, yeni hata kodları `errors.ts`'e, `WriteGate projectId`, ENV-74 etiketi, iptal eden e2e testlerine ayrı kullanıcı, `/login?next=` sayfasında `fillSignIn`); MERGED gelince HANDOFF olarak yazılır ve lease RETIRED. r2 sonucu bekliyorum.

### C-10ab-0017 · 2026-10-28 21:35 · → koordinator · ACK
Paket: 10a-bağlama   Cevap: K-10ab-0012 (state/reviews/10a-binding-r2.md)
DUZELT alındı; bulgu doğru. Plan: önce kırmızı birim (TAB/LF/CR, `%09/%0A/%0D`, `//`, `/\`, `\/`, `http:`, `javascript:`, boşluklu ön ek + mevcut 6 değer; aynı origin yol/query/hash pozitifleri) ve gerçek giriş e2e'si (inceleyicinin URL'si: `/login?next=%2F%09%2Fbackend%3A8000%2Fhealthz` → giriş sonrası origin konsolda kalır). Sonra `safeNext`: ham C0/DEL ve ters bölü reddi, kodlu kontrol karakteri reddi, `new URL` ile ayrıştırma + origin eşitliği, dönüş yalnız `pathname+search+hash`. Not: `safeNext` sunucuda (login sayfası) da koşar, `window` yok; taban origin sabit bir sentinel (`http://console.invalid`) ile karşılaştırılır, etkisi aynı (aynı origin dışı her şey reddedilir); PR'da yazılı.

### C-10ab-0018 · 2026-10-28 22:05 · → koordinator · PR-HAZIR
Paket: 10a-bağlama   Cevap: K-10ab-0012 (review r2)
r2 düzeltmesi. Branch: feat/10a-binding · Son commit: e9fe396678f84fe2b074a1babdefa8b2cf4de240 (628d416 üstüne 1 commit: `lib/login-redirect.ts` + testler + PNG). PR: state/pr/10a-binding.md "Review r2 bulgu → düzeltme → kanıt".
- MAJOR-1: ham ve kodlu C0/DEL/ters bölü reddi, `new URL` + origin eşitliği, dönüş yalnız `pathname+search+hash`. Ek bulgu: `/..//x` normalleşince `//x` (başka origin) oluyordu; sonuç yolu `//` ile başlarsa da red.
- Önce kırmızı: birim 9 kırmızı; gerçek giriş e2e'si kırmızı, origin `http://backend:8000` (inceleyicinin bulgusu).
- Kapılar (`ffcore/backend:0.0.0-10ab`): tsc 0, eslint 0, Vitest 76/76, gerçek backend Playwright **52 passed**. Stack `down -v`.
- Sapma: kural `window.location.origin` diyordu; `safeNext` sunucuda da koştuğu için sabit referans origin (`http://console.invalid`) ile aynı kontrol; PR'da gerekçeli.
Bekliyorum: REVIEW-SONUC (r3 delta) ya da DUZELT.

### C-10ab-0019 · 2026-10-28 22:30 · → koordinator · HANDOFF
Paket: 10a-bağlama   Cevap: K-10ab-0016
### 10a-bağlama · ffcore-isci-c-10ab · 2026-10-28 22:30
- Durum: MERGED (r3 ONAY e9fe396 → main 05c76d4). Lease RETIRED.
- Tam sonraki adım: 10a-formlar (01 MERGED sonrası, yeni oturum). Sağlayıcı formu: `/provider-drivers` dinamik alanlar, şifreli config (API'de maskeli), `POST /providers/test` ve `/{id}/test`, proje atama `PUT /providers/{id}/projects` (boş bırakılamaz). Model formu: `/model-catalog` "Fill from catalog", embed probe 409 `embedding_probe_unavailable`, `provider_in_use` 409. Ekranlar `app/(console)/{providers,models}/page.tsx` (şu an salt-okuma liste).
- Kalıplar (review r1-r2'den, bağlayıcı say):
  - Her sorgu `ListState`/`QueryError` (components/screen.tsx); `data ?? []` yok; loading / hata (seçici yerine QueryError) / gerçek boş ayrı.
  - 401: `QueryCache`/`MutationCache` → `goToLogin()`; `next` yalnız `safeNext` (C0/DEL/ters bölü ham ve kodlu reddi, origin eşitliği, `//` yol reddi; `lib/login-redirect.ts`). Yönlendirme hedefi üreten yeni kod bu fonksiyondan geçer.
  - Hata kodu → mesaj `lib/api/errors.ts` + `messages/{en,tr}.json` `Errors`; yeni kodlar (`provider_in_use`, `provider_key_taken`, `provider_domain_mismatch`, `provider_not_assigned`, `model_key_taken`, `embedding_probe_unavailable`) eklenecek.
  - Yazma yetkisi `<WriteGate projectId>` / `useAccess(projectId)`; tenant ekranı `superadmin: true` (lib/navigation.ts).
  - Tipler `npm run gen:api` (sözleşme değişirse), `npm run check:api`.
  - e2e: docs/onyuz.md "Acceptance tests"; `FFCORE_VERSION=0.0.0-<paket>` (ENV-74); kullanıcı/proje global-setup.ts'de çalıştırma başına sonekli; oturumu iptal eden test kendi kullanıcısını kullanır; `/login?next=` sayfasında `fillSignIn`; TanStack `visibilitychange`'i `window`'da dinler.
- Değişen dosyalar: state/pr/10a-binding.md "Değişen dosyalar" + r1/r2 tabloları.
- Koşan / kalan testler: Vitest 76/76, Playwright 52/52 (e9fe396, gerçek backend). NOT_RUN: backend make test (değişmedi), iki profil e2e (önyüz profil bağımsız), Lighthouse (FOLLOWUP-37).
- Kararlar ve varsayımlar: K-10ab-0004 (msw yok, compose e2e servisi + FFCORE_BACKEND_URL build arg + ortam, salt-okuma listeler), DRIFT-61 (make e2e yok), DRIFT-62 (brief 10 rol matrisinde süper yönetici), ENV-74, FOLLOWUP-66 (HTTPS/ters vekil), FOLLOWUP-67 (proje admin'i için üye ekleme). Süreç notu: ilk dilimlerde test-önce sırası ihlali PR sapma 8'de açık; r1/r2 düzeltmeleri kırmızı kanıtlı.
- Blocker'lar: yok.
- Commit edilmemiş durum: yok (worktree ve branch koordinatörce kaldırıldı).
- Branch ve son commit: feat/10a-binding (silindi) @ e9fe396678f84fe2b074a1babdefa8b2cf4de240 → main 05c76d4.
- Ortam: `10ab` stack'i `down -v` (konteyner/volume 0). `ffcore-10a-nm` (alpine node_modules, birim/lint) ve `ffcore-10a-nm-pw` kalıyor; compose e2e volume'u `<proje>_e2e_node_modules` her stack'le gelir. Geçici `alpine:3` silindi. Scratchpad'deki log ve taslaklar oturuma özel, depoya girmedi.

### C-10af-0001 · 2026-10-28 22:40 · → koordinator · ACK
Paket: 10a-formlar   Cevap: K-10af-0001
DURUM: OKUMA-TAMAM. Okunan gruplar 1-8 bu oturumda (C-10ab-0001); o okumadan bu yana main'de değişenler ayrıca okundu: KARARLAR 03a/04a/10a-bağlama/01/08-lite/imaj etiketi eklemeleri, docs/gateway.md, docs/onyuz.md farkı. K-10ab-0019 HANDOFF ve K-10af-0000/0001 okundu; kalıplar (ListState/QueryError, `data ?? []` yok, 401 → goToLogin/safeNext, errors.ts, WriteGate projectId) bağlayıcı.
Worktree `.worktrees/feat/10a-forms` @ 070d8b0, temiz. `FFCORE_VERSION=0.0.0-10af`, compose proje adı `10af`, volume'lar `ffcore-10a-nm(-pw)`.
Touch-zone: frontend/** (providers, models ekranları ve formları, tests), docs/onyuz.md. FOLLOWUP-67 kapsam dışı.
Sıra: 03a OpenAPI (sağlayıcı/model/sürücü/katalog uçları) ve mevcut ekranlar okunur → state/pr/10a-forms.md planı → DURUM: PLANNED; onaysız kod yok.

### C-10af-0002 · 2026-10-28 22:43 · → koordinator · DURUM
Paket: 10a-formlar   Cevap: K-10af-0001
DURUM: PLANNED. Plan: state/pr/10a-forms.md (kapsam, 12 e2e + birim test eşlemesi, felsefe kontrolü).
KARAR-GEREK (ayrıntı ve etkiler planda, öneri önce):
- D1 Proje admin'i `GET /providers` okuyamıyor (require_superadmin), model formu sağlayıcı seçemez. A (öneri): model ekleme bu PR'da süper yöneticiye, düzenle/sil proje admin'ine; FOLLOWUP 03 additive `GET /projects/{id}/providers`. B: backend ucu bu PR'da. C: elle kimlik (önermem).
- D2 e2e'den LiteLLM `/model/info` doğrulaması. A (öneri): compose `e2e.environment`'a `LITELLM_URL` + `LITELLM_MASTER_KEY` (test değeri, başlıkta; touch-zone +2 satır). B: Playwright sonrası `render-litellm CHECK=1` ayrı adım. C: yok.
- D3 e2e sağlayıcı adresi. A (öneri): ollama `http://fake-llm:11434` + komut satırında `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm` (dosya değişmez). B: `http://litellm:4000`. C: .env.test değişikliği.
- D4 `upstream_api=responses`. A (öneri): görünür ama pasif, varsayılan chat. B: seçilebilir + uyarı. C: gizli.
Bulgu: `merge_config` config'i tamamen değiştirir; UI tam config + boş gizli alan için `"***"` gönderir. Gizli alanı silmek UI'dan mümkün değil (risk, planda).
Onaysız kod yok; yanıt bekliyorum.

### C-10af-0003 · 2026-10-28 22:45 · → koordinator · ACK
Paket: 10a-formlar   Cevap: K-10af-0002
Alındı: D1-D4 A koşullarıyla (ekle düğmesi proje admin'inde pasif + neden; compose iki satır yalnız interpolasyon + rapor dizininde sahte anahtar araması 0; tam komut docs/onyuz.md'ye; responses pasif seçenek açıklaması + listede "LiteLLM'de değil" işareti), FOLLOWUP-79/80. Koda geçiyorum, önce kırmızı test.

### C-10af-0004 · 2026-10-28 23:23 · → koordinator · KARAR-GEREK
Paket: 10a-formlar   Cevap: -
Bulgu (backend, touch-zone dışı, doğrulandı): çözülemeyen sağlayıcı host adı bağlantı testinde 500 veriyor. `POST /providers/{id}/test` (ve `/providers/test`) → `SafeOutboundClient` → `_PinnedBackend.connect_tcp` → `system_resolver` (`backend/ffcore/core/egress.py:187`) `anyio.getaddrinfo` → `socket.gaierror: [Errno -3] Temporary failure in name resolution`. gaierror httpx2.HTTPError değil, `_follow`'un except'leri yakalamıyor, `test_connection` da yalnız Egress* yakalıyor → ASGI 500. Kanıt: 10af stack backend logu, e2e test_10af_4 kurulumunda 500. Etki: host adı yazım hatası olan sağlayıcıda kullanıcı "Connection test failed" yerine 500 görür; aynı yol SafeOutboundClient kullanan her çağrıda (uzlaştırıcı dahil, doğrulanmadı) olabilir.
Seçenekler:
- A (öneri): backend sahibine küçük düzeltme (resolver'da OSError → `EgressRequestFailed`/connect hatası, `connection_failed` sonucu + negatif test), 10a-formlar'dan önce ya da ona paralel merge. Benim testlerim (D3 fake-llm, çözülemeyen host) düzeltme sonrası yeşil; o zamana kadar test_10af_3/4 kırmızı kalır.
- B: düzeltmeyi bu PR'a ben eklerim (backend/ffcore/core/egress.py + test, touch-zone genişlemesi, [A]). Etki: tek PR, ama backend review'u da gerekir.
- C: e2e'de fake-llm'i de başlatırım (`--profile test`, host çözülür) ve "başarısız test" kabulünü kapalı bir portla kanıtlarım. Etki: D3 değişir, backend hatası açık kalır (FOLLOWUP).
Ara durum: kırmızı koşu tamam (tests-only 86c04d8: 22/22 kırmızı, sebep eksik UI; tek istisna bu 500). Yeşil koşuya geçiyorum, sonuçları DURUM ile yazarım.

### C-10af-0005 · 2026-10-28 23:31 · → koordinator · ACK
Paket: 10a-formlar   Cevap: K-10af-0003
B alındı. Yapıldı: b1d07f6 `fix(03b): unresolvable host is a failed egress, not a 500` (egress.py `_PinnedBackend.connect_tcp`: resolver OSError → `EgressRequestFailed("egress_dns_failed", host:port)`, `from None`; politika kontrolleri önce ve aynı). Önce kırmızı: `test_03b_2_unresolvable_host_is_request_failed` (gerçek resolver, `no-such-provider.invalid`) ve `test_03b_2_resolver_os_error_is_request_failed` kırmızıydı (gaierror / OSError), `test_03b_2_unresolvable_host_still_needs_the_policy` baştan yeşil (politika lookup'tan önce). Şimdi egress + provider servis birim testleri 59/59, ruff temiz. API testi `test_03a_9_unresolvable_host_is_a_failed_test` (unsaved + stored → 200 + connection_failed) eklendi; test-int ve iki profil make test e2e koşusu bitince (aynı stack, fake-llm başlatınca e2e etkilenir).

### C-10af-0006 · 2026-10-29 00:27 · → koordinator · PR-HAZIR
Paket: 10a-formlar   Cevap: K-10af-0003
Branch `feat/10a-forms` · SHA 851de1d8991736850f1144a0d05d303910f436fc (070d8b0 üstüne 6 commit, ağaç temiz) · Sınıf [A] · Kanıt: state/pr/10a-forms.md.
Commitler: 86c04d8 test (önce kırmızı: 22/22 e2e), c66408c feat, c28eaf9 docs, b1d07f6 fix(03b) (touch-zone eki, K-10af-0003 B), 82219e6 test (DNS beklemesi), 851de1d docs (PNG).
Kapılar: önyüz tsc/eslint/vitest 89/check:api 0; backend make lint + make test 292/292 iki profil; make test-int 134/134 iki profil; compose config (varsayılan + e2e) 0.
e2e (gerçek backend + LiteLLM): 22 `test_10af_*` testi geçti. Tam takım temiz stack'te `--workers=2` ile 71/74; 3 hata değişmemiş eski testlerde (`test_10a_4_axe_contrast: providers light`, `test_10ab_3_members` ×2) 5 s zaman aşımı, aynı iki dosya tek worker 16/16. Varsayılan worker'la 60/74 (makine yükü: 02 + 04a stack'leri açık). Yani tek seferde 74/74 kanıtım YOK; PR'da NOT_RUN ve risk olarak açık yazdım.
D2 kontrolü: LiteLLM master key `frontend/test-results` ve 6 e2e logunda 0 (sınır: test-results yalnız son koşu).
Stack `down -v` (0 konteyner/volume). İmajlar `ffcore/backend:0.0.0-10af`, `ffcore/tools:0.0.0-10af` duruyor.
İnceleyiciye not: backend kısmı (egress.py) ayrı bölümde; compose iki satırı paylaşılan değişiklik (04a ile rebase sırası).

### C-10af-0007 · 2026-10-29 08:59 · → koordinator · PR-HAZIR
Paket: 10a-formlar   Cevap: K-10af-0007
r2 delta. Branch `feat/10a-forms` · SHA 275d06d8224e40a02b0dfc1d2bfbcba0b014c98a (851de1d üstüne 3 commit, ağaç temiz) · kanıt state/pr/10a-forms.md "Review r1 bulgu → düzeltme → kanıt".
MINOR-1: c13cb2b test (önce kırmızı: e2e `test_10af_16_project_switch` 2/2, birim `test_10af_17_form_save_gate` 2/2), f08b5b6 fix (`ModelList key={projectId}`; model ve sağlayıcı formunda Kaydet WriteGate içinde), 275d06d PNG.
Ek bulgu, aynı commit'te kapandı: `Models.extraBodyHint` JSON örneği ICU argümanı sanılıyordu (INVALID_MESSAGE); EN/TR tırnaklandı, `test_10af_18_messages_parse` önce kırmızı sonra yeşil.
Kapılar: tsc/eslint/vitest 93/93 (18 dosya); tam Playwright tek worker temiz stack **76/76** (4,8 dk) f08b5b6'da; master key araması 0; stack `down -v`. Backend değişmedi (r1 sonuçları geçerli).

### C-10af-0008 · 2026-10-29 09:31 · → koordinator · HANDOFF
Paket: 10a-formlar   Cevap: K-10af-0011
### 10a-formlar · ffcore-isci-c-10af · 2026-10-29 09:31
- Durum: MERGED (r2 ONAY 275d06d → main 7457e82). Lease RETIRED.
- Tam sonraki adım: 10b-poc, yeni oturumda (GOREV koordinatörden).
- Kararlar (K-10af-0002/0003, hepsi bağlayıcı):
  - D1 A: model ekleme yalnız süper yönetici (sağlayıcı listesi `require_superadmin`); proje admin'i düzenler/siler, ekle düğmesi nedenli pasif (`data-needs-superadmin`); düzenlemede `/providers` çağrısı yok. FOLLOWUP-79: 03 additive `GET /projects/{id}/providers` gelince kısıt kalkar (`app/(console)/models/page.tsx` `DisabledWithReason`, `components/model-form.tsx` `useProviders(!model)`).
  - D2 A: compose `e2e.environment`'a `LITELLM_URL` + `LITELLM_MASTER_KEY` (yalnız interpolasyon, test tarafında başlıkta; `tests/e2e/api.ts` `expectInLiteLLM`).
  - D3 A: e2e sağlayıcı adresi `http://fake-llm:11434`, stack komut satırında `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm`; fake-llm başlatılmaz (başarısız test yolu). fake-llm `--profile test` ile açılırsa test_10af_3/12 beklentisi değişir: test-int'ten önce e2e, sonra `rm -sf fake-llm`.
  - D4 A: `upstream_api=responses` yeni modelde pasif; mevcut model düzenlenebilir, listede "Not in the gateway" rozeti (`lib/model-form.ts notInGateway`). `forward_unknown_params` her zaman `false` gönderilir.
  - FOLLOWUP-80: gizli alan UI'dan silinemez (boş = `***` = koru; `lib/provider-config.ts buildConfig`).
  - K-10af-0003 B: `core/egress.py` resolver `OSError` → `EgressRequestFailed("egress_dns_failed")` (b1d07f6); bağlantı testi 200 + `connection_failed`.
- Kalıplar (10a-bağlama'nınkilere ek):
  - Form parçaları `components/form-parts.tsx` (`FieldShell`, `TextField`, `CheckGroup`, `CheckField`); yeni formlar bunları kullanır.
  - Proje kapsamlı liste ekranı proje kimliğiyle key'li (`<ModelList key={projectId}>`); her Kaydet `WriteGate` içinde (açma düğmesi yetmez) — review r1 MINOR-1.
  - Mesajda süslü parantezli örnek ICU tırnağı ister (`'{...}'`); `test_10af_18_messages_parse` her EN/TR mesajı denetler.
  - Sürücü alanı etiketleri `ProviderFields.<alan>`; canlı `/provider-drivers`'ta mesajı olmayan alan `test_10af_1`'i kırmızı yapar.
- e2e komutları (docs/onyuz.md "Acceptance tests"): `export ALLOWED_INTERNAL_HOSTS=litellm,fake-llm FFCORE_VERSION=0.0.0-<paket>` (+ `BACKEND_PORT=<boş port>` başka stack 8000'deyse); `up -d --wait --build backend` → `create-superadmin` (stdin) → `--profile e2e run --rm e2e` → `down -v`. Paylaşılan makinede `--workers=1` önerilir (varsayılan worker'da 5 s beklemeler yük altında düştü; tek worker temiz stack 76/76). Aynı stack'te tekrarlı koşu sağlayıcı biriktirir (4. koşuda 68), kanıt koşusu temiz stack'te. Docker içinde çözülemeyen ad 4-8 s'de düşer; bağlantı testi beklemeleri 20 s. e2e `npm ci` bazen ağ hatası verir, tekrar denenir; `ffcore-10a-nm-pw` volume'u 10a-bağlama öncesinden, `@tanstack/react-query` yok (kopyalamayın, `npm ci`).
- Koşan / kalan testler: Vitest 93/93 (18 dosya), Playwright 76/76 tek worker (f08b5b6), backend make test 292/292 ve test-int 134/134 iki profil (b1d07f6/82219e6). NOT_RUN: Lighthouse (FOLLOWUP-37), iki profil e2e (önyüz profil bağımsız).
- Blocker'lar: yok.
- Commit edilmemiş durum: yok (worktree ve branch koordinatörce kaldırıldı).
- Branch ve son commit: feat/10a-forms (silindi) @ 275d06d8224e40a02b0dfc1d2bfbcba0b014c98a → main 7457e82.
- Ortam: `10af` stack'i `down -v` (konteyner/volume 0). Scratchpad'deki loglar oturuma özel, depoya girmedi.
