# PR: 10-marka (ürün ikonu ve marka görseli)

**Paket:** 10-marka · **Sınıf:** [A] · **Branch:** feat/10-brand-icon · **Baz commit:** b6fc3d8 · **HEAD:** 92cc9a35da5a4f5927124d182e35e652d79d46ae (IMPLEMENTED; VERIFIED değil, ENV-92) · **Oturum:** ffcore-isci-c-marka

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

## Koordinatöre karar soruları (KARAR-GEREK C-MRK-0003; cevap K-MRK-0001: D1 A, D2 A, D3 A; ek K-MRK-0002 slogan, K-MRK-0003 aile adı, K-MRK-0004 app/manifest.ts)

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
- **Üretim:** `assets/icons/scripts/make_web_brand.py` (yeni). `assets/icons/README.md`: FastFlow (FF) ailesi, yeni slogan, eski slogan notları, vektör cümlesi, "Önyüz (10-marka)" tablosu.
- **Önyüz varlıkları (üretilmiş):** `frontend/app/{favicon.ico,icon.png,apple-icon.png}`, `frontend/public/brand/{ffcore-icon-128,192,512, ffcore-badge-256,512, ffcore-brand-variant-b-512}.png`.
- **Önyüz kodu:**
  - `frontend/app/manifest.ts` (yeni; K-MRK-0004 ile `public/manifest.webmanifest` yerine)
  - `frontend/app/layout.tsx` (yorum)
  - `frontend/components/app-sidebar.tsx` (yalnız logo alanı; `BrainCircuitIcon` kalktı)
  - `frontend/app/(auth)/login/page.tsx` (marka alanı)
  - `frontend/messages/{en,tr}.json` (`Brand.logoAlt`; `Home.subtitle` yeni slogan)
- **Testler:** `frontend/tests/e2e/brand.ts`, `test_10mrk_{1..5}_*.spec.ts`.
- **Backend:** `backend/pyproject.toml` `description` tek satır (K-MRK-0002 md. 3; lock değişmedi).
- **Docs:**
  - `docs/onyuz.md`: "Brand" bölümü; kabul komutunda `langfuse-web`; aşama 2'de `--force-recreate` + `printenv` kontrolü; ekran görüntüsü satırları.
  - `docs/images/10mrk-*.png` (4 yeni) ve `10a-*.png` (16, yeni kenar çubuğu/giriş markasıyla yeniden üretildi).

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | favicon, icon, apple-icon bağlı; 200, doğru tür ve boyut | `test_10mrk_1_favicon_icons` | kırmızı (link yok) → yeşil (21:5x, slogan öncesi); slogan sonrası NOT_RUN (ENV-92) |
| 2 | manifest bağlı; ad/açıklama `Home.*`'dan; 192/512 ikonlar | `test_10mrk_2_manifest` | kırmızı → yeşil (statik manifest ile); `app/manifest.ts` + description beklentisiyle NOT_RUN (ENV-92) |
| 3 | kenar çubuğunda logo, açık ve daraltılmış, en/tr alt | `test_10mrk_3_sidebar_logo` ×2 | kırmızı → yeşil; slogan sonrası NOT_RUN |
| 4 | girişte rozet + ad + yeni alt başlık, başlık ve meta açıklama | `test_10mrk_4_login_brand` ×2 | kırmızı → yeşil (eski alt başlıkla); yeni slogan beklentileriyle NOT_RUN |
| 5 | iki tema PNG + axe 0 ihlal (giriş, projeler) | `test_10mrk_5_both_themes` ×4 | kırmızı → yeşil; yeni slogan PNG'leri NOT_RUN (`10mrk-*.png` eski alt başlığı gösteriyor, yeniden üretilmeli) |
| 6 | üretim deterministik | `make_web_brand.py --check` | geçti: 9 dosya güncel; iki koşu md5 aynı (Pillow 12.2.0) |
| - | messages anahtarları eşit, sabit renk/metin yok | Vitest `test_10a_8`, `test_10a_3`, `test_10ab_12` | geçti (114/114) |

## Çalıştırılan komutlar
| Komut | Ortam | Exit | Not |
|---|---|---|---|
| `make_web_brand.py --check` (önce) | host py 3.12, Pillow 12.2.0 | 1 | kırmızı: 9 dosya eksik |
| `make_web_brand.py` ×2 + `--check` | aynı | 0 | deterministik |
| `npx eslint` / `npx tsc --noEmit` / `npx vitest run` | node:20.19.5-alpine + `ffcore-10a-nm`, son HEAD | 0 / 0 / 0 | Vitest 114/114 |
| Playwright `10mrk` (kırmızı) | `-p marka`, `FFCORE_VERSION=0.0.0-marka`, `ALLOWED_INTERNAL_HOSTS=litellm,langfuse-web,fake-llm` | 1 | 10 failed (doğru nedenler) |
| Playwright `10mrk` (yeşil, slogan öncesi) | aynı | 0 | 10 passed |
| Tam e2e koşu 1 | aynı | 1 | aşama 1: 1/1. Aşama 2: 92 passed, 9 failed. Hepsi bilgi tabanı testi. Neden: backend aşama 2'de yeniden yaratılmadı, `FAKE_EMBED=0` kaldı, `/internal/embed` 500 (ortam). |
| Tam e2e koşu 2 (`--force-recreate`, backend ve worker `FAKE_EMBED=1` doğrulandı) | aynı | durduruldu | Aşama 1: 1/1. Aşama 2: 79 ✓, 6 ✘ (`10bp1_10/11/18/2` ve `10af_12 provider form dark`), sonra Docker motoru takıldı (ENV-92, K-INIT-0014), koşu iptal edildi. Hata ayrıntısı rapora yazılmadı; neden doğrulanmadı. 10mrk testleri bu koşuda sıraya gelmedi. |

**NOT_RUN:**
- Slogan ekinden sonra 10mrk e2e ve yeni PNG'ler (ENV-92).
- Tam e2e regresyonu temiz geçmedi. 10bp1 bilgi tabanı ve 10af_12 düşüşlerinin marka değişikliğiyle ilgisi doğrulanmadı. Değişiklik bu ekranlara dokunmuyor, ama kanıt yok.
- Backend `make test`: yalnız `pyproject` description değişti.
- Lighthouse (FOLLOWUP-37).

## Varsayımlar ve brief'teki çelişkiler
- `apple-touch-icon-180x180.png` köşeleri saydam. iOS saydam alanı siyahla doldurur; rozet zemini koyu olduğu için görünür fark beklenmez. Doğrulanmadı (cihaz yok).
- Manifest dilsizdir. Ad ve açıklama kaynak dil `en.json`'dan gelir (K-MRK-0004).
- Kenar çubuğunda alt metin "FFCore" ve hemen yanında "FFCore" yazısı var. Ekran okuyucu adı iki kez okur. GOREV alt metni json'dan istediği için bu bilinçli; dekoratif `alt=""` alternatifi koordinatör kararına açık.
- Belge düzeltmesi: `docs/onyuz.md` kabul komutu 02'den beri backend'i açmıyordu (`LANGFUSE_HOST` izinli host değil); `langfuse-web` eklendi.

## Kalan riskler
- `public/brand/ffcore-brand-variant-b-512.png` eski slogan "LLM Agent Runtime"ı gömülü taşıyor. Konsolda kullanılmıyor ama `/brand/` altında herkese açık. Yeni slogan render'ı gelince yeniden üretilmeli ya da kaldırılmalı.
- `docs/images/10mrk-*.png` eski alt başlığı gösteriyor. Docker dönünce `test_10mrk_5` ile yeniden üretilecek.
