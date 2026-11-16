# Arşiv: koordinator · MRK

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-MRK-0000 · 2026-10-29 21:17 · → kullanici · DURUM
Paket: 10-marka (ürün ikonu ve marka görseli)   Cevap: -
TASLAK; yeni isci-c oturumu (`ROL=isci-c PAKET=10-marka`) OKUMA-TAMAM yazınca K-MRK-0001 GOREV olur. Kullanıcı kararı (29 Ekim 2026): ürün ikonu `assets/icons/png/ffcore-brand-variant-b.png` ailesi; kaynak `assets/icons/**` main'de (commit). Sınıf [A], yalnız önyüz + assets; 05a/06a'dan bağımsız, hemen.
İş: (1) Favicon ve uygulama ikonları: `frontend/app/favicon.ico` ← `assets/icons/favicon/favicon.ico`; Next 15 dosya kuralıyla `frontend/app/icon.png` (`ffcore-icon-32x32.png` ya da 48) ve `frontend/app/apple-icon.png` (`apple-touch-icon-180x180.png`); `layout.tsx` metadata'da `icons` ve `manifest` (`public/manifest.webmanifest`: 192/512 PNG, ad "FFCore", tema rengi `#0A192F`). (2) Konsol logosu: kenar çubuğu başlığı ve giriş sayfası marka alanı `public/brand/ffcore-icon-256.png` (rozet, yazı yok); giriş/landing görseli için `public/brand/ffcore-brand-variant-b-512.png` **üretilir** (1024'ten deterministik küçültme, `assets/icons/proposal/make_ffcore_mark.py` deseniyle ya da Pillow tek komut; üretim scripti ve komutu `assets/icons/README.md`'ye; 800 KB'lık 1024 dosyası web'e konmaz). (3) `<img>` yerine `next/image`, `alt` metni en/tr json'dan ("FFCore"); sabit renk yok, koyu/açık temada rozet aynı (zemin rozetin içinde). (4) Belge: docs/onyuz.md "Marka" bölümü (hangi dosya nerede, nasıl üretildi). Kanıt: Playwright'ta favicon ve apple-icon 200 + doğru boyut, kenar çubuğu/giriş sayfasında logo görünür, iki tema PNG; Lighthouse yok (FOLLOWUP-37). Branch feat/10-brand-icon (main'den, açıldı) · Worktree C:/ai_paycore/ffcore/.worktrees/feat/10-brand-icon · `FFCORE_VERSION=0.0.0-marka`. Touch-zone: frontend/app/{favicon.ico,icon.png,apple-icon.png,layout.tsx}, frontend/public/{brand,manifest.webmanifest}, kenar çubuğu/giriş bileşenleri (yalnız logo alanı), frontend/messages/{en,tr}.json, assets/icons/README.md + üretim scripti, docs/onyuz.md. Dokunma: backend, compose, diğer ekranlar. Önce PLANNED (kısa).

### K-MRK-0001 · 2026-10-29 21:30 · → isci-c · GOREV
Paket: 10-marka   Cevap: C-MRK-0001 / C-MRK-0003
Taslak K-MRK-0000 bu GOREV'in parçası; plan onaylı; oturum ffcore-isci-c-marka. Kararlar:
- D1 **A**: kenar çubuğunda `ffcore-icon-128x128.png` (dar FF, README kuralı), 32 px kutuda; girişte 256 rozet.
- D2 **A**: girişte yazısız saydam rozet (`ffcore-badge-transparent-1024`'ten 256/512 üretilir) + ad ve alt başlık en/tr json'dan; gömülü İngilizce yazılı variant-b yalnız tanıtım için `public/brand/`'a 512 kopya, ekranda kullanılmaz. Slogan (`Home.subtitle`) şimdilik olduğu gibi kalır; marka kararı kullanıcıya ayrıca soruldu, PR'ı beklemez.
- D3 **A**: bu PR yalnız README'deki paket atfını düzeltir ("bağlama 10b'nin işi" → 10-marka); aile adı DRIFT-91 (kullanıcı kararı). README'deki "vektör kaynak yok" cümlesi de yanlış: `assets/icons/concepts/**` altında üç SVG var; cümleyi düzelt (kavram taslakları, ürün ikonu PNG'den).
Üretilen her görsel tek komutla deterministik (script + komut README'de). Koda geç; önce kırmızı Playwright.

### K-MRK-0002 · 2026-10-29 22:00 · → isci-c · GOREV-EK
Paket: 10-marka   Cevap: C-MRK-0004
Kullanıcı marka kararı (29 Ekim 2026; önceki GOREV ile çelişirse bu geçerli): alt başlık TR "Kurumsal Yapay Zekâ Platformu", EN "Enterprise AI Agent Platform"; "LLM Agent Runtime" slogan değil ("Agent Runtime" yalnız 06 modül adı); Türkçe metinde "ajan" yok (teknik ekranda "agent" kalır); "LLM" teknik belgede kalır, ürün kapısındaki yazıdan çıkar. Senin PR'ına eklenir, ayrı paket yok:
1. `frontend/messages/en.json` `Home.subtitle` → "Enterprise AI Agent Platform"; `tr.json` → "Kurumsal Yapay Zekâ Platformu". `metadata.description`, giriş sayfası ve manifest aynı anahtardan okur; ikinci sabit metin yok (ARCH-13).
2. `assets/icons/README.md`: satır 3 "FFCore (LLM Agent Runtime)" → "FFCore (Kurumsal Yapay Zekâ Platformu / Enterprise AI Agent Platform)"; 22 ve 26'daki "LLM Agent Runtime"/"Agent Runtime" notları "render'da gömülü eski slogan, ekranda kullanılmaz" diye işaretlenir. `png/` render'ları yeniden üretilmez.
3. `backend/pyproject.toml` satır 4 `description` → "FFCore enterprise AI agent platform backend (import ffcore)" (touch-zone eki, tek satır, lock değişmez).
4. e2e `test_10mrk_*` slogan beklentileri yeni değerlerle.
PLAN/README/CLAUDE/KARARLAR/TERMINOLOGY değişiklikleri bende (main, docs). Aile adı (DRIFT-91) kullanıcıda açık; sen dokunma. Bitince DURUM'da değişen dosyalar ve commit SHA.

### K-MRK-0003 · 2026-10-29 22:07 · → isci-c · CEVAP
Paket: 10-marka   Cevap: C-MRK-0003 (D3)
Kullanıcı kararı: ürün ailesi FastFlow; FF kısa ad, açılımı Fast Flow (DRIFT-91 kapandı; PLAN 1b, KARARLAR, TERMINOLOGY bende güncellendi). `assets/icons/README.md` satır 3'teki "FastFlow ürün ailesinin (`ffengine.com`)" ifadesi doğru; "FastFlow (FF) ürün ailesi" biçimine getir. Başka değişiklik yok.

### K-MRK-0004 · 2026-10-29 22:10 · → isci-c · CEVAP
Paket: 10-marka   Cevap: C-MRK-0005
`app/manifest.ts` kabul (statik manifest json okuyamaz; Next dosya kuralı, tek kaynak `Home.title`/`Home.subtitle`); touch-zone buna göre. docs/onyuz.md komut düzeltmesi (`ALLOWED_INTERNAL_HOSTS=litellm,langfuse-web,fake-llm`) doğru, PR'da "02'den beri bozuk belge" diye not; aynı komut `docs/gelistirme-ortami.md`'de de varsa orayı da düzelt. Tam e2e bitince slogan ekini uygula, tek PR-HAZIR.

### K-MRK-0005 · 2026-10-30 01:14 · → isci-c · CEVAP
Paket: 10-marka   Cevap: C-MRK-0008
Kök neden bulgun kabul (compose `run e2e` backend'i kabuğun o anki ortamıyla yeniden yaratıyor; önek `FAKE_EMBED=1` `run`'a geçmiyor). Düzeltme docs/onyuz.md'de `export FAKE_EMBED=1` + neden; PR'da "10bp1 prosedürü sessizce yanlış ortamda koşuyordu" diye yaz; 10bp1'in kendi kanıtının nasıl yeşil olduğunu doğrulama, yalnız not. Daha kalıcı çözüm (compose `e2e` servisinin `depends_on`'unu backend'i yeniden yaratmayacak biçime almak ya da `--no-deps`) FOLLOWUP olarak benden. Koşu bitince PR-HAZIR.

### K-MRK-0006 · 2026-10-30 08:28 · → isci-c · GOREV-EK
Paket: 10-marka   Cevap: C-MRK-0010
Sıra sende: ffmain kapandı, açık yığın yalnız 06a. Kanala "YIGIN-AÇ marka" yaz, `up -d --wait`, `export FAKE_EMBED=1` ile tek e2e koşusu (K-MRK-0005), kanıtı PR'a; bitince `down -v` + "YIGIN-KAPA"; sonra PR-HAZIR'ı (62c8b21 ya da yeni SHA) doğrula ve yaz, REVIEW-ISTEK'i ben açarım.

### K-MRK-0007 · 2026-10-30 09:07 · → isci-c · CEVAP
Paket: 10-marka   Cevap: C-MRK-0012
PR-HAZIR alındı; 2843d40 doğrulandı (3 commit, ağaç temiz, son commit yalnız docs/images). YIGIN-KAPA alındı, sıra teste geçti. REVIEW-ISTEK K-MRK-0008 gitti; inceleyici 06a r2'yi bitirince bakar. Review bitene kadar branch'e commit yok. Saat damgan ileri (09:12 yazdın, gerçek 09:06): `date` çıktısını kullan.

### K-MRK-0008 · 2026-10-30 09:07 · → inceleyici · REVIEW-ISTEK
Paket: 10-marka   Cevap: C-MRK-0012
Sıra: 06a r2'den **sonra**. PR: state/pr/10-marka.md · Branch feat/10-brand-icon · Worktree C:/ai_paycore/ffcore/.worktrees/feat/10-brand-icon · Baz main b6fc3d8 · SHA 2843d40d8fe0e1641bea80947b6bc90b7e5b7ebd (koordinatör doğruladı: 3 commit, 55 dosya +341/-21, ağaç temiz; kod 62c8b21 ile aynı, son commit yalnız yeniden üretilen docs/images). Sınıf [A]. Tur r1, kısa: (1) önyüz: favicon, icons, `app/manifest.ts`, kenar çubuğu icon-128, giriş ekranı; UI metni yalnız messages/{en,tr}.json (alt başlık EN "Enterprise AI Agent Platform" / TR "Kurumsal Yapay Zekâ Platformu"), kodda sabit metin yok, açık/koyu tema; (2) `assets/icons/README.md` "FastFlow (FF) ürün ailesi"; (3) docs/onyuz.md `export FAKE_EMBED=1` düzeltmesi ve "10bp1 prosedürü sessizce yanlış ortamda koşuyordu" notu; (4) e2e kanıtı: aşama 2 108/108 (10mrk 10, 10bp1 KB 9 dahil). Yığın gerekmez (kanıt dosyada); gerekirse YIGIN-AÇ kuralı. Çıktı: state/reviews/10-marka-r1.md + REVIEW-SONUC.

### K-MRK-0009 · 2026-10-30 09:25 · → isci-c · CEVAP
Paket: 10-marka   Cevap: C-MRK-0013
r1 ONAY (R-MRK-0002; MINOR-1 Pillow ortamı FOLLOWUP-96, senin işin değil). main'e `--no-ff` merge ediyorum, kapılar benden. MERGED yazınca kısa HANDOFF (10-marka) + lease RETIRED; sonraki paket (10b-poc-2, 06a merge sonrası) yeni oturumda.

### K-MRK-0010 · 2026-10-30 09:50 · → isci-c · CEVAP
Paket: 10-marka   Cevap: C-MRK-0013
10-marka **MERGED**: main'e `--no-ff` 4628219; main kapısı yeşil (lint, alembic heads, make test 583/583 iki profil, test-samples, test-int 299 + 4 atlandı, smoke, önyüz lint/tsc/check:api). Worktree, branch, `0.0.0-marka` imajı kaldırıldı. Kısa HANDOFF (10-marka) yaz, lease'i RETIRED yap; bu oturum kapanır. Sonraki isci-c paketi 10b-poc-2 (06a merge sonrası) yeni oturumda. Teşekkürler.
