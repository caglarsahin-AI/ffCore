# Arşiv: isci-c · MRK

state/kanal/isci-c.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### C-MRK-0001 · 2026-10-29 21:30 · → koordinator · DURUM
Paket: 10-marka   Cevap: -
DURUM: OKUMA-TAMAM. Okunan gruplar:
- 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE; 3 PLAN; 4 KARARLAR (29 Ekim eklemeleri dahil); 5 handbook tümü + PR şablonu; 8 BASLATMA.
- 6 WORK_QUEUE, BLOCKERS, isci-c kanalı (C-10bp1-0011 HANDOFF dahil); koordinatör kanalı K-MRK-0000'a kadar; diğer kanallarda yalnız lease'ler.
- 7 brief 10 (Kapsam, Ortak, Teslimatlar, Kabul); assets/icons/README ve varlıklar (boyut, alfa); docs/onyuz.md başlıkları.
Lease: ffcore-isci-c-marka ACTIVE (önceki 10bp1 RETIRED). Kullanıcı talimatı: ROL=isci-c PAKET=10-marka.
Not: bu oturum daha önce "C Main" adıyla rol almadan kapatılmıştı (kullanıcı kararı); şimdi kullanıcı isci-c olarak açtı. "C Main (fork)" oturumundan haberim yok; isci-c tek oturum bu.

### C-MRK-0002 · 2026-10-29 21:30 · → koordinator · ACK
Paket: 10-marka   Cevap: K-MRK-0000
ACK: taslak, GOREV metni olarak alındı (K-MRK-0001 yazıldığında aynı içerikse ayrıca ACK verilmez). Worktree `.worktrees/feat/10-brand-icon` @ b6fc3d8, temiz. `FFCORE_VERSION=0.0.0-marka`, compose proje adı `marka`, node volume'ları `ffcore-10a-nm(-pw)`. Touch-zone GOREV'deki gibi; ek dosya: `tests/e2e/test_10mrk_*.spec.ts` (önyüz testleri).

### C-MRK-0003 · 2026-10-29 21:31 · → koordinator · DURUM
Paket: 10-marka   Cevap: K-MRK-0000
DURUM: PLANNED. Plan: state/pr/10-marka.md (5 e2e + 1 birim, felsefe kontrolü). Onaysız kod yok.
KARAR-GEREK (ayrıntı ve etkiler planda, öneri önce):
- D1 Kenar çubuğu logosu. Kutu 32 px; README kuralı "128 px altı dar FF zorunlu".
  - A (öneri): kenar çubuğunda icon-128 dar FF, girişte 256 rozet.
  - B: GOREV'deki gibi 256 rozet 32 px'te.
  - C: kutu 48 px'e büyür; sidebar-07 sapması.
- D2 Giriş görseli. variant-b'de İngilizce "FFCore / LLM Agent Runtime" yazısı gömülü ve zemin opak lacivert.
  - Çatışmalar: metin json'da değil; README "açık zeminde C"; slogan `Home.subtitle` "Enterprise LLM platform" ile ARCH-13 çelişkisi.
  - A (öneri): girişte yazısız saydam rozet + json'dan ad ve alt başlık. variant-b-512 üretilir, `public/brand/`'a tanıtım için konur, ekranda kullanılmaz.
  - B: GOREV'deki gibi variant-b-512 iki temada.
  - C: temaya göre B ve C görseli.
  - Slogan seçimi marka kararıdır, kullanıcıya gider; A PR'ı beklemez.
- D3 assets/icons/README "FastFlow ürün ailesi (ffengine.com)" ve "bağlama 10b'nin işi" der; PLAN 1b "FF ürün ailesi" der.
  - A (öneri): bu PR yalnız paket atfını düzeltir; aile adı için DRIFT kaydı.
  - B: aile adını da "FF" yaparım.

### C-MRK-0004 · 2026-10-29 21:40 · → koordinator · ACK
Paket: 10-marka   Cevap: K-MRK-0001
ACK: D1 A, D2 A, D3 A (README: paket atfı ve "vektör yok" cümlesi; concepts/ altında 3 kavram × 2 SVG, ürün ikonu PNG'den). DURUM: IMPLEMENTING. Sıra: kırmızı Playwright (test_10mrk_1-5) → üretim scripti (`--check` ile deterministiklik) → bağlama → docs.

### C-MRK-0005 · 2026-10-29 22:05 · → koordinator · ACK
Paket: 10-marka   Cevap: K-MRK-0002
ACK: madde 1-4 bu PR'a eklenir; aile adına dokunulmaz.
Madde 1 için uygulama notu: statik `public/manifest.webmanifest` json'u okuyamaz. Bu yüzden Next.js dosya kuralı `app/manifest.ts` (ARCH-09) kullanılır: name `Home.title`, description `Home.subtitle`, kaynak `en.json`. Adres yine `/manifest.webmanifest`; link'i Next ekler, `metadata.manifest` kalkar. Touch-zone'da `public/manifest.webmanifest` yerine `app/manifest.ts` olur.
Ara durum: hedefli e2e 10/10 yeşil (kırmızı 10/10 doğru nedenle düştükten sonra). lint 0, tsc 0, Vitest 114/114. `make_web_brand.py --check` 9 dosya güncel ve deterministik.
Bulgu: docs/onyuz.md'deki `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm` komutu 02'den beri backend'i açmıyor (LANGFUSE_HOST izinli host değil). Komut `litellm,langfuse-web,fake-llm` olarak düzeltildi.
Tam e2e regresyon koşusu (iki aşama) sürüyor. Slogan değişikliği koşu bitince uygulanacak.

### C-MRK-0006 · 2026-10-30 00:05 · → koordinator · DURUM
Paket: 10-marka   Cevap: K-MRK-0002 / K-MRK-0003 / K-MRK-0004 / K-INIT-0014
DURUM: IMPLEMENTED (VERIFIED değil). HEAD 92cc9a35da5a4f5927124d182e35e652d79d46ae (feat/10-brand-icon, tek commit b6fc3d8 üstüne). Ayrıntı: state/pr/10-marka.md.
Uygulanan: D1-D3 A; K-MRK-0002 md. 1-4 (alt başlık EN/TR, README satır 3/22/26, pyproject description, test beklentileri); K-MRK-0003 "FastFlow (FF) ürün ailesi"; K-MRK-0004 `app/manifest.ts` (lint için tek satırlık gerekçeli disable, renk tek sabitte).
Kanıt:
- Kırmızı 10/10 → yeşil 10/10 (slogan öncesi).
- Son HEAD'de eslint 0, tsc 0, Vitest 114/114 (çıkış kodları borusuz).
- `make_web_brand.py --check` 0, deterministik.
- Not: önceki mesajdaki "lint 0" `tail`'in çıkış koduydu. Gerçek koşu `manifest.ts` renk ihlalini yakaladı, düzeltildi.
NOT_RUN (ENV-92):
- Slogan sonrası 10mrk e2e ve `10mrk-*.png`. Bu PNG'ler eski alt başlığı gösteriyor.
- Tam e2e regresyonu.
  - Koşu 1: 92 ✓ / 9 ✘, hepsi bilgi tabanı. Backend aşama 2'de `FAKE_EMBED=1` almadan kaldı; docs'a `--force-recreate` + `printenv` eklendi.
  - Koşu 2: env doğrulandı, 79 ✓ / 6 ✘ (`10bp1_10/11/18/2`, `10af_12 provider form dark`), sonra motor takıldı ve iptal ettim. Neden doğrulanmadı.
Docker dönünce tek koşu (iki aşama) yapıp PR-HAZIR göndereceğim. Yığın `marka` ayakta bırakıldı (talimat).

### C-MRK-0007 · 2026-10-30 00:54 · → koordinator · DURUM
Paket: 10-marka   Cevap: K-INIT-0015
DURUM: tek e2e koşusu sürüyor; izin istemi beklemiyorum. HEAD 92cc9a35da5a4f5927124d182e35e652d79d46ae, yığın `marka` (`0.0.0-marka`).
- 00:30: backend ve worker `FAKE_EMBED=0` ile zorla yeniden yaratıldı (doğrulandı: 0). Aşama 1 `@model-missing` çıkış 0.
- 00:34: `FAKE_EMBED=1` ile zorla yeniden yaratıldı (backend=1, worker=1 doğrulandı). Aşama 2 00:36'da başladı (~27 dk).
Bitince sonuç ve PR-HAZIR, ardından `down -v`.

### C-MRK-0008 · 2026-10-30 01:10 · → koordinator · DURUM
Paket: 10-marka   Cevap: K-INIT-0015
Ara sonuç (tek koşu):
- Aşama 1: 1/1.
- Aşama 2: 92 ✓ / 9 ✘. Marka testleri 10mrk 10/10 ✓ (yeni slogan dahil); 10af_12 de ✓.
- 9 düşüşün hepsi 10bp1 bilgi tabanı testi. Kök neden bulundu, marka değil.
Kök neden: e2e servisi `depends_on: backend`. `docker compose run e2e`, backend'i kabuğun o anki değerleriyle yeniden yaratıyor (log: "marka-backend-1 Recreate"). Önek olarak verilen `FAKE_EMBED=1` bu `run`'da yok; backend 0'a dönüyor, worker 1 kalıyor. `/readyz` `model_missing`.
Belgelenen 10bp1 prosedürü (docs/onyuz.md "Acceptance tests") bu yüzden sessizce yanlış ortamda koşuyor. 10bp1 kanıtının nasıl yeşil olduğu doğrulanmadı; compose sürüm farkı olabilir.
Düzeltme (bu PR, docs/onyuz.md): aşama 2'de `export FAKE_EMBED=1`, nedeni açıklamada. Önceki commit'teki `--force-recreate` satırı geri alındı (gereksiz).
Şimdi aşama 2 export ile yeniden koşuyor. Bitince commit, PR-HAZIR, `down -v`.

### C-MRK-0009 · 2026-10-30 01:40 · → koordinator · PR-HAZIR
Paket: 10-marka   Cevap: K-INIT-0015
PR-HAZIR: feat/10-brand-icon @ 62c8b21cfa857a16f0300c9629ec4d06503a0b8f, [A]. Commit'ler:
- 92cc9a3: kod, varlıklar, testler, docs.
- 62c8b21: docs `export FAKE_EMBED=1` + yeni sloganlı ekran görüntüleri.
PR: state/pr/10-marka.md.
Kanıt:
- 10mrk kırmızı 10/10 → yeşil 10/10.
- Tek tam koşu (92cc9a3): aşama 1 1/1, aşama 2 92 ✓ / 9 ✘.
- 10mrk 10/10 yeni sloganla; 10a, 10ab, 10af hepsi ✓.
- eslint 0, tsc 0, Vitest 114/114, `make_web_brand.py --check` 0.
NOT_RUN: 9 `10bp1` bilgi tabanı testi.
- Neden kanıtlı ve ortamsal: `run e2e` backend'i `FAKE_EMBED=0` ile yeniden yarattı, `/readyz` `model_missing`.
- Export ile tekrar koşusu Docker motoru yüzünden başlamadı ("error waiting for container", çıkış 125; `docker ps` 2 dk yanıtsız). ENV-92 tekrarı olabilir.
- Bu PR o testlere ya da backend davranışına dokunmuyor.
- Yeniden koşu isteyip istemediğin sende; istersen tek komut aşama 2.
Yığın `marka`: `down -v` Docker yanıt vermediği için yapılamadı. Motor dönünce yaparım ya da sen kapat.

### C-MRK-0010 · 2026-10-30 01:45 · → koordinator · ACK
Paket: 10-marka   Cevap: K-INIT-0016
ACK: docker komutu yok; sıra 3. Motor dönüp sıra gelince önce "YIGIN-AÇ marka" yazacağım (mevcut `marka` yığını Docker çökmesinden önce açıktı; ilk iş durumunu kontrol edip gerekirse `down -v`). Sonra export'lu aşama 1+2 tek koşu, "YIGIN-KAPA marka", sonuç DURUM. Branch HEAD 62c8b21 değişmeyecek (yalnız kanıt).

### C-MRK-0011 · 2026-10-30 08:46 · → koordinator · DURUM
Paket: 10-marka   Cevap: K-MRK-0006
YIGIN-AÇ marka (açık yığınlar: 06a + marka). HEAD 62c8b21, `0.0.0-marka`, export'lu tek koşu (aşama 1 + 2), çıktı tee ile dosyaya.

### C-MRK-0012 · 2026-10-30 09:12 · → koordinator · PR-HAZIR
Paket: 10-marka   Cevap: K-MRK-0006
YIGIN-KAPA marka: `down -v`, konteyner 0, volume 0.
Export'lu tek koşu (62c8b21 kodu):
- Aşama 1 1/1.
- Aşama 2 **108/108**: 10mrk 10/10; 10bp1 bilgi tabanı 9 testi dahil.
- Backend `FAKE_EMBED=1` koşu öncesi ve sonrası doğrulandı. 1147 s, çıktı tee ile dosyada.
PR-HAZIR: feat/10-brand-icon @ **2843d40d8fe0e1641bea80947b6bc90b7e5b7ebd**, [A].
- Koşu 27 ekran görüntüsünü yeniden üretti; 10bp1 ekranları yeni kenar çubuğu logosunu gösteriyor.
- Bu yüzden 62c8b21 üstüne yalnız `docs/images` commit'i geldi; kod 62c8b21 ile aynı.
- Dal: b6fc3d8 üstüne 3 commit (92cc9a3, 62c8b21, 2843d40); ağaç temiz.
PR: state/pr/10-marka.md (kabul tablosu ve komutlar güncel). NOT_RUN: yalnız backend `make test` (yalnız description değişti) ve Lighthouse (FOLLOWUP-37).

### C-MRK-0013 · 2026-10-30 09:07 · → koordinator · ACK
Paket: 10-marka   Cevap: K-MRK-0007
ACK: review bitene kadar feat/10-brand-icon'a commit yok (HEAD 2843d40). Saat damgası bundan sonra `date` çıktısından. DUZELT ya da ONAY bekliyorum.

### C-MRK-0014 · 2026-10-30 09:50 · → koordinator · HANDOFF
Paket: 10-marka   Cevap: K-MRK-0010 (zil; merge git'te doğrulandı: 2843d40 main 4628219'un atası)
### 10-marka · ffcore-isci-c-marka · 2026-10-30 09:50
- **Durum:** MERGED (r1 ONAY 2843d40 → main 4628219). Lease RETIRED; bu oturum kapanır.
- **Tam sonraki adım:** yok. isci-c sıradaki paket 10b-poc-2, yeni oturumda, 06a merge sonrası.
- **Kararlar:**
  - D1-D3 A.
  - Slogan: `Home.subtitle` EN "Enterprise AI Agent Platform", TR "Kurumsal Yapay Zekâ Platformu". Tek anahtar; metadata, giriş ve manifest bundan okur.
  - Aile adı: FastFlow (FF).
  - Manifest `app/manifest.ts`'den üretiliyor; içindeki lacivert renk kodun tek sabit renk değeri, tek satırlık gerekçeli lint istisnası var.
- **Kalıplar (sonraki önyüz işleri):**
  - Marka dosyaları elle değil `py -3.12 assets/icons/scripts/make_web_brand.py` (`--check`) ile üretilir.
  - Ekranda yazı gömülü görsel kullanılmaz.
  - Kenar çubuğu logosu `data-testid="sidebar-logo"`, giriş rozeti `login-brand-logo`.
  - e2e aşama 2'de `FAKE_EMBED=1` **export** edilir. `run e2e` backend'i kabuğun değerleriyle yeniden yaratır; önek olarak verilirse ayar 0'a döner.
  - `ALLOWED_INTERNAL_HOSTS` listesi `langfuse-web`'i içermeli.
- **Koşan / kalan testler:**
  - Export'lu tek koşu: aşama 1 1/1, aşama 2 108/108.
  - eslint 0, tsc 0, Vitest 114/114.
  - NOT_RUN: backend `make test` (yalnız description değişti), Lighthouse (FOLLOWUP-37).
- **Açık takip:** FOLLOWUP-96 (Pillow ortamı, review MINOR-1). `public/brand/ffcore-brand-variant-b-512.png` eski sloganı gömülü taşıyor; yeni render gelince yeniden üretilmeli ya da kaldırılmalı.
- **Süreç dersleri:**
  - Kapı çıkış kodu boru içinden alınmaz (`tail`'in kodu); `PIPESTATUS` ya da dosyaya yönlendirme kullanılır.
  - Uzun koşu `&` ile değil arka plan aracıyla başlatılır.
  - Saat damgası `date`'ten alınır.
- **Blocker'lar:** yok.
- **Commit edilmemiş durum:** yok. Worktree `.worktrees/feat/10-brand-icon` ve branch duruyor; kaldırma koordinatörde.
- **Branch ve son commit:** feat/10-brand-icon @ 2843d40d8fe0e1641bea80947b6bc90b7e5b7ebd → main 4628219.
- **Ortam:** `marka` yığını `down -v` (konteyner 0, volume 0). `ffcore/*:0.0.0-marka` imajları ve `ffcore-10a-nm(-pw)` duruyor; imaj silme koordinatörde. Scratchpad logları oturuma özel.
