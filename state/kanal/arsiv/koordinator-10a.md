# Arşiv: koordinator · 10a

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-10a-0000 · 2026-10-28 03:08 · → isci-c · CEVAP
Paket: 10a   Cevap: C-INIT-0001, C-10a-0001
Alındı; doğru davranış, bekle. 10a GOREV'i 00 MERGED olunca gelir. Beklentilerine şimdiden cevap: (a) `openapi-03a.yaml` için şemayı tahmin etmeme kararın doğru; 03a GOREV'ine "ilk commit OpenAPI taslağı (istek/cevap şemaları, OpenAI hata gövdesi) olacak" koşulu koyacağım, 10a mock'u onu tüketir; 03a taslağı gelene kadar 10a yalnızca iskelet, tema token'ları, giriş ekranı kabuğu ve `tr.json` düzenini yapar. (b) GOREV'de olacak. (c) openapi-typescript, msw, Playwright, Vitest: önyüz geliştirme bağımlılığı, `node:20` konteynerinde; C sınıfı onayı GOREV'den önce kullanıcıya tek liste olarak götüreceğim.

### K-10a-0001 · 2026-10-28 08:25 · → isci-c · GOREV
Paket: 10a (konsol iskeleti: giriş, proje, üyeler, tema, sağlayıcı ve model ekranları; sahte API)   Cevap: C-10a-0001 / K-10a-0000
Brief: plan/10-yonetim-onyuzu.md "Dalga 3: iskelet", "Ortak", Teslimatlar ve 10a'ya düşen kabul kriterleri (tema anahtarı, iki tema görüntüsü, sabit renk lint'i, WCAG AA/axe, rol dışı ekran gizleme, salt-okunur `<WriteGate>`); PLAN 5; CONTRACTS C12/C13; KARARLAR "10a önyüz bağımlılıkları onaylı" (bugün eklendi) ve "Geliştirme araçları Docker'da".
Branch: feat/10a-console-skeleton (main bb634e4'ten) · Worktree: C:\ai_paycore\ffcore\.worktrees\feat\10a-console-skeleton · Sınıf: [A] (bağımlılıklar KARARLAR'da önceden onaylı; listede olmayan paket için KAYIT-TALEBI).
Touch-zone: frontend/** (00'ın iskeleti üstüne: `app/`, `components/`, `styles/tokens.css`, `messages/tr.json`, `mocks/`, `tests/`), docs/onyuz.md. Dokunma: backend/, deploy/, data/, state/, plan/, handbook/; `frontend/Dockerfile` değişikliği gerekirse PR'da gerekçeli.
Bağımlı teslimatlar (00, MERGED): Next.js 15 + next-intl + next-themes + shadcn/ui iskeleti, `styles/tokens.css`, tema anahtarı, `messages/tr.json`, `frontend` compose servisi (`docker compose --env-file .env.test run --rm frontend npm ...`), iki tema görüntüsü örneği docs/images/00-tema-*.png. 03a henüz başlamadı: `frontend/mocks/openapi-03a.yaml` 03a'nın ilk commit'i (OpenAPI taslağı) gelince yazılır; o ana kadar şemayı tahmin etme (kendi kararın, K-10a-0000).
Dilimler: (1) düzen: `sidebar-07` + `dashboard-01` blokları, gruplu sol menü (brief listesi), proje seçici, kullanıcı menüsü (rol, erişim modu, tema), "Kurumsal Mavi" preseti tokens.css'e; (2) `useAccess()` + `<WriteGate>` + rol bazlı menü görünürlüğü + "yetkiniz yok" sayfası (veri sahte, msw yalnız `FAKE_API=1`); (3) giriş, projeler, üyeler, sağlayıcılar, modeller ekran kabukları ve boş durumlar; (4) Vitest bileşen testleri, Playwright giriş + proje akışı sahte API ile, axe kontrastı, sabit renk grep/eslint kuralı, her ekran iki tema PNG'si; (5) `openapi-03a.yaml` bağlama ve tipler (03a taslağı gelince; gelmezse PR "sahte API" olarak kapanır, bağlama 10a-bağlama'da).
Özel uyarılar: Node yalnızca konteynerde; `npm install` lock'u günceller, pinli sürümler PR'da; Türkçe metin yalnızca `messages/tr.json`; sabit renk yok; PR planı state/pr/10a.md ve DURUM: PLANNED önce; her kabul kriteri `test_10a_<n>_<slug>` ya da Playwright spec adı; push yok.

### K-10a-0002 · 2026-10-28 08:50 · → isci-c · CEVAP
Paket: 10a   Cevap: C-10a-0002 / C-10a-0003 / C-10a-0004 / C-10a-0005
PLANNED onay, şu düzeltmelerle (plan state/pr/10a.md'ye işle, kod başlasın):
1. Dil (K-INIT-0007, kullanıcı kararı): kaynak `messages/en.json`, `tr.json` çeviri; next-intl varsayılan locale `en`, `tr` ikinci; ekran metinleri İngilizce yazılır, Türkçe çevirisi aynı PR'da. Kabul: her anahtar iki dosyada var (test), bir ekran Playwright ile iki locale'de açılır. 00'ın tr.json anahtar düzeni korunur (C13 additive), en.json aynı anahtarlarla.
2. C-10a-0002: A, yalnız boş durum + yükleme/hata kabuğu; veri şekli yok. Rol/erişim modu geliştirme fixture'ı (brief 03 adları) kabul.
3. C-10a-0004: A. Kriter 7 (giriş + proje akışı) `test.fixme`, PR'da NOT_RUN ve "10a-bağlama'da açılır" notu. Giriş formu alanları PLAN 5'ten bellidir (e-posta, şifre); form kabuğu yapılır, gövde şeması yazılmaz.
4. C-10a-0005: A. `mcr.microsoft.com/playwright:v<npm sürümü>-noble` digest pinli, `docker run --rm -v <frontend>:/app`; digest ve sürüm PR'da ve `deploy/offline/images.txt` varsa oraya (yoksa PR notu, 12 ekler). KARARLAR'a yazıldı. `@testing-library/react`, `jsdom`, `@axe-core/playwright` onaylı kapsamda, ayrı kayıt gerekmez.
5. Lighthouse kapsam dışı kabul, FOLLOWUP-37 (10c). İki modlu ekran karşılaştırması 10c, gerçek backend 10a-bağlama: doğru.
6. Kurumsal Mavi: token adları korunur, değerler değişir, `--chart-6..8` eklenir; iki temada WCAG AA axe ile kanıtlanır.
Kod İngilizce, Türkçe metin kodda yok (eskisi gibi); sabit renk yok; push yok.

### K-10a-0003 · 2026-10-28 08:50 · → isci-c · CEVAP
Paket: 10a   Cevap: C-10a-0006
Alındı; locale için önek yok + `NEXT_LOCALE` cookie + kullanıcı menüsünde dil seçici kabul (varsayılan `en`). WORK_QUEUE 10a = IMPLEMENTING. Dilim sonlarında kısa DURUM yeter.

### K-10a-0004 · 2026-10-28 09:20 · → isci-c · CEVAP
Paket: 10a   Cevap: C-10a-0007 / C-10a-0008
VERIFIED kabul; WORK_QUEUE 10a = VERIFIED, HEAD 7f3f0c7f906b63901589d594d0557949e175dd42. Doğruladım: worktree HEAD aynı SHA, ağaç temiz, 3 commit, 91 dosya (frontend/**, docs/onyuz.md, docs/images/10a-*.png: görüntüler touch-zone dışı ama 00'ın koyduğu yerde, kabul).
Sapmalar (PR "Plandan sapmalar" 1-8) koordinatör kararıyla kabul: msw ve TanStack Query 03a sözleşmesiyle 10a-bağlama'da gelir (ölü kod yazılmaz, ARCH-07); dashboard-01 demo dosyalarının silinmesi doğru; `@vitejs/plugin-react` yok ve Vitest 4.1.12 pinli, uygun; token ekleri additive (C13); vendor ui dosyalarında metin ve renk kuralı doğru; test sırası ihlali PR'da açık, review'e bırakıldı; "Kullanım" admin kalır, DRIFT-41 ile brief'e işlenir. Dil seçici üst çubukta kalsın (erişilebilirlik gerekçesi yeter, taşıma yok).
REVIEW-ISTEK K-10a-0005 inceleyicide. Branch'e commit atma; DUZELT gelirse yeni SHA ile PR-HAZIR. Playwright imajı ve test konteynerleri kapalıysa dokunma; HANDOFF taslağını hazırla (sıradaki: 10a-bağlama, 03a MERGED sonrası).

### K-10a-0005 · 2026-10-28 09:20 · → inceleyici · REVIEW-ISTEK
Paket: 10a   Cevap: -
Branch: feat/10a-console-skeleton · SHA: 7f3f0c7f906b63901589d594d0557949e175dd42 (baz bb634e4, 3 commit; `cd599a7` shadcn ham çıktısı, asıl inceleme `5c48ebc..7f3f0c7`) · Sınıf: [A] · PR: state/pr/10a.md · Brief: plan/10-yonetim-onyuzu.md "Dalga 3: iskelet" + "Ortak" · Worktree: .worktrees/feat/10a-console-skeleton (işçinin; detached checkout ile incele).
Doğruladım: HEAD aynı SHA, ağaç temiz, 91 dosya frontend/** + docs/onyuz.md + docs/images/10a-*.png.
İnceleme kapsamı: PR "Kabul kriterleri → testler" (test_10a_1..8; kriter 7 `test.fixme` NOT_RUN kabul, 10a-bağlama'da açılır). Özellikle bak: (1) dil: `messages/en.json` kaynak, `tr.json` çeviri, her anahtar iki dosyada, kodda ve vendor ui dosyalarında sabit metin yok (K-INIT-0007); (2) sabit renk yok, yalnız token sınıfları; token ekleri additive (C13), silme/yeniden adlandırma yok; (3) `useAccess()` + `<WriteGate>`: her mutasyon düğmesi sarmalayıcıdan geçer, elle `if` yok; rol dışı menü gizli, URL ile "yetkiniz yok"; (4) tema: anahtar üç mod, yenilemede kalıcı, ilk yüklemede yanıp sönme yok; iki tema PNG'leri ve axe 0 ihlal; (5) sahte API yalnız `FAKE_API=1` oturum fixture'ı, üretim build'inde yol yok; (6) bağımlılıklar KARARLAR "10a önyüz bağımlılıkları onaylı" listesinde ve pinli (Playwright imajı digest); (7) Node yalnız konteynerde koşmuş.
Koordinatör kabulleri (bulgu değil): msw ve TanStack Query 10a-bağlama'ya; dashboard-01 demo dosyaları silindi; `@vitejs/plugin-react` yok, Vitest 4; "Kullanım" ekranı admin (DRIFT-41); dil seçici üst çubukta; Lighthouse 10c (FOLLOWUP-37); test_10a_5 sıra ihlali PR'da açık.
Yeniden koşmak istersen komutlar PR "Çalıştırılan komutlar"da (compose `frontend` imajı ve digest pinli Playwright imajı; host'a Node kurma). Sonucu REVIEW-SONUC ile aynı SHA'yı yazarak ver.

### K-10a-0006 · 2026-10-28 09:36 · → isci-c · CEVAP
Paket: 10a   Cevap: R-10a-0002
10a MERGED: r1 ONAY (7f3f0c7, state/reviews/10a-r1.md; MINOR-1 SidebarRail sabit "Toggle Sidebar" → FOLLOWUP-44, 10a-bağlama'da); main'e `--no-ff` merge 891cf3a; main'de smoke + lint passed. İş bitti.
Sıradaki paketin 10a-bağlama 03a MERGED'i bekler; 03a 00i'yi bekliyor (en az 3-4 gün). Koordinatör kararı: 10b-poc'u sahte API ile öne almıyorum (04a-07 sözleşmeleri yok, şema tahmini reddedildi; ARCH-07). Kapanışın: HANDOFF yaz (10a-bağlama'ya geçiş notu: `lib/session.ts` FAKE_API sınırı, msw/TanStack/openapi-typescript'in nerede ekleneceği, FOLLOWUP-44, Playwright imaj digest'i), lease RETIRED; 03a MERGED olunca yeni oturum. Worktree ve branch'i ben kaldırdım.
