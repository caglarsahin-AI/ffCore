# PR: 10-marka (ürün ikonu ve marka görseli)

**Paket:** 10-marka · **Sınıf:** [A] · **Branch:** feat/10-brand-icon · **Baz commit:** b6fc3d8 · **Oturum:** ffcore-isci-c-marka

## Plan (kodlamadan önce)

1. **Bulunan semboller ve dosyalar:**
   - `frontend/app/layout.tsx`: `generateMetadata()` yalnız `title` ve `description` döndürüyor. `icons`, `manifest` ve `viewport` yok.
   - `frontend/app/favicon.ico`: Next iskeletinden gelen dosya (16/32/48/64). `assets/icons/favicon/favicon.ico` ile bayt bayt farklı.
   - `frontend/public/`: yok, yeni açılacak.
   - `components/app-sidebar.tsx:83-94`: `SidebarHeader` içinde `BrainCircuitIcon`, `size-8` rozet ve `bg-sidebar-primary`. Kenar çubuğu daraltılınca yalnız bu 32 px'lik kutu kalıyor.
   - `app/(auth)/login/page.tsx`: kartta yalnız başlık var, marka alanı yok.
   - `messages/{en,tr}.json` `Home.title` "FFCore", `Home.subtitle` "Enterprise LLM platform".
   - `middleware.ts` yok; `public/` ve `app/icon.png` girişsiz sunulur.
   - `package-lock.json` `sharp` 0.35.5 ve `@img/sharp-linuxmusl-x64`: `next/image` alpine üretim imajında optimize eder, `unoptimized` gerekmez.
   - Varlıklar: `assets/icons/png/*`. İkonlar RGBA, köşeleri saydam ve zemini rozetin içinde. `ffcore-brand-variant-b.png` RGB, 1024² ve 816 KB. Görselde **yazı gömülü**: "FFCore" ve "LLM Agent Runtime". `ffcore-badge-transparent-1024.png` 992 KB, RGBA, yazısız.
2. **Kapsam:** GOREV K-MRK-0000/0001'in (1)-(4) maddeleri.
   - Favicon, `icon.png`, `apple-icon.png`, `manifest.webmanifest`.
   - Kenar çubuğu ve giriş sayfası marka alanı. `next/image` kullanılır, `alt` json'dan gelir.
   - Üretim scripti ve README.
   - docs/onyuz.md "Brand" bölümü.

   **Kapsam dışı:** `tokens.css` paletinin marka renklerine (`#0A192F` / `#1E88E5`) yaklaştırılması. Brief 10 "Kurumsal Mavi" der; bu fark FOLLOWUP önerisidir. Diğer ekranlara dokunulmaz.
3. **Değişecek dosyalar:**
   - `frontend/app/{favicon.ico, icon.png, apple-icon.png, layout.tsx}`
   - `frontend/public/manifest.webmanifest` ve `frontend/public/brand/*.png` (üretilmiş)
   - `components/app-sidebar.tsx` (yalnız logo alanı) ve `app/(auth)/login/page.tsx` (yalnız marka alanı)
   - `messages/{en,tr}.json` (`Brand.logoAlt` ve D2'ye göre slogan)
   - `assets/icons/scripts/make_web_brand.py` (Pillow, LANCZOS, deterministik; çıktı `frontend/public/brand/`) ve `assets/icons/README.md` ("Web" bölümü, komut)
   - `docs/onyuz.md` "Brand"
   - `tests/e2e/test_10mrk_*.spec.ts`
4. **Sözleşme, profil:**
   - Donmuş sözleşme yok. C13'e yalnız yeni çeviri anahtarı eklenir (additive).
   - Profilden bağımsız; backend ve compose değişmez.
   - `theme_color` `#0A192F` manifest'te düz değer olarak durur, çünkü manifest CSS değişkeni okuyamaz. Sabit renk lint'i yalnız bileşenleri tarar; bu durum docs'ta not edilir.
5. **Kabul kriteri → test:**
   - `test_10mrk_1_favicon_icons`: `/favicon.ico`, `/icon.png` ve `/apple-icon.png` 200 döner, doğru içerik türünü ve PNG boyutunu taşır. HTML `<head>` içinde `link rel=icon`, `apple-touch-icon` ve `manifest` var.
   - `test_10mrk_2_manifest`: `/manifest.webmanifest` 200 döner; `name` "FFCore", 192 ve 512 ikonlar 200 ve doğru boyutta, `theme_color` doğru.
   - `test_10mrk_3_sidebar_logo`: kenar çubuğunda logo görünür, açık ve daraltılmış hâlde de; `alt` iki dilde doğru; `naturalWidth > 0`.
   - `test_10mrk_4_login_brand`: giriş sayfasında marka görseli görünür ve yüklenir.
   - `test_10mrk_5_both_themes`: giriş ve kenar çubuğunun açık/koyu PNG'leri alınır, axe 0 ihlal.
   - Birim: `make_web_brand.py` iki kez koşunca çıktı bayt bayt aynı (deterministik).
6. **Migration:** yok.
7. **Geri alma:** commit revert. Varlıklar `public/` altında, veri yok.
8. **Durma koşulları:**
   - `next/image` imajda optimize etmezse (sharp yüklenmez), `unoptimized` ile sessizce geçmem; koordinatöre dönerim.
   - Touch-zone dışında bir dosya gerekirse koordinatöre dönerim.
9. **Felsefe kontrolü:**
   - ARCH-07: her ekranın ve sekmenin markası; kalıcı karmaşıklık yalnız bir üretim scripti.
   - ARCH-09: Next 15'in dosya kuralı (`icon.png`, `apple-icon.png`, `favicon.ico`) ve `metadata.manifest` kullanılır. Elle yazılan `<link>` ve kendi optimizasyonumuz yok, `next/image` yeter.
   - ARCH-10/06: tema ya da boyuta göre gizli görsel değişimi yok. Hangi dosyanın nerede kullanıldığı docs'ta tablo olarak yazılır. Eksik varlık build'de ya da e2e'de açık hata verir.

## Koordinatöre karar soruları (KARAR-GEREK C-MRK-0003)

- **D1 Kenar çubuğu logosu.** GOREV 256 tam rozeti istiyor. Ancak `SidebarHeader` kutusu 32 CSS px; assets/icons/README kuralı "128 px altında dar FF kırpması zorunlu" der.
  - **A (önerilen):** kenar çubuğunda `ffcore-icon-128` (dar FF), 32 px'te gösterilir (2x ekranda 64 px). Giriş sayfasında 256 tam rozet. README kuralına uyar ve küçükte okunur.
  - **B:** GOREV'deki gibi 256 rozet 32 px'te. Halka ve rozet küçülür, iki F ufalır.
  - **C:** kenar çubuğu kutusu 48 px'e büyür ve 256 rozet kullanılır. sidebar-07 düzeninden sapma olur; inceleyici bunu bulgu sayar.
- **D2 Giriş görseli.** `ffcore-brand-variant-b.png` içinde İngilizce "FFCore / LLM Agent Runtime" yazısı gömülü ve zemini opak lacivert kare. Bu üç kuralla çatışıyor: (a) metin json'da olmalı, TR yerelde slogan İngilizce kalır; (b) README "açık zeminde C, koyu zeminde B" der, B açık temada koyu kare olur; (c) slogan "LLM Agent Runtime", uygulamadaki `Home.subtitle` "Enterprise LLM platform" ile çelişir (ARCH-13).
  - **A (önerilen):** giriş sayfasında yazısız saydam rozet (`ffcore-badge-transparent-1024` → `public/brand/ffcore-badge-256.png` ve 512) ile json'dan "FFCore" ve `Home.subtitle`. İki temada aynı görünür, metin çevrilir ve terim tek kalır. variant-b-512 yine üretilir; yalnız dışa dönük tanıtım ve splash için `public/brand/`'a konur, ekranda kullanılmaz.
  - **B:** GOREV'deki gibi variant-b-512 iki temada. Hızlı ama yukarıdaki üç çatışma kalır.
  - **C:** temaya göre B (koyu) ve C (açık) görseli. İki görsel olur, yazı yine gömülü kalır.
  - Slogan kararı ("LLM Agent Runtime" mi, "Enterprise LLM platform" mu) markadır ve kullanıcıya gider. A seçilirse PR mevcut `Home.subtitle` ile çıkar; slogan sonradan yalnız json'da değişir.
- **D3 Doküman tutarlılığı (DRIFT önerisi).** assets/icons/README "FastFlow ürün ailesi (`ffengine.com`)" ve "Frontend'e bağlama 10b paketinin işidir" der. PLAN 1b "FF ürün ailesi" der; bağlama bu pakette yapılıyor. README bu PR'da yalnız "Web" bölümü ve 10b → 10-marka düzeltmesiyle güncellenir. Aile adı (FastFlow mu, FF mi) marka kararıdır, DRIFT kaydı önerilir.
  - **A (önerilen):** README'de yalnız paket atfı düzeltilir, aile adı koordinatör ya da kullanıcı kararına kalır.
  - **B:** README'de aile adını PLAN'a göre "FF" yaparım.

## Değişen dosyalar
(kodlama sonrası)

## Kabul kriterleri → testler
(kodlama sonrası)

## Çalıştırılan komutlar
(kodlama sonrası)

## Varsayımlar ve brief'teki çelişkiler
- `apple-touch-icon-180x180.png` köşeleri saydam. iOS saydam alanı siyahla doldurur; rozet zemini koyu olduğu için görünür fark beklenmez. Doğrulanmadı (cihaz yok).

## Kalan riskler
