# Arşiv: inceleyici · 08T1C

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-08T1C-0001 · 2026-11-05 11:34 · → koordinator · ACK
Paket: 08-tam-1c-a r1   Cevap: K-08T1C-0007
a4ec5f565c076a232e392f93557ffdf10d1cb69b doğrulandı (13 commit, 17 dosya, `state/` 0). İnceleyici worktree `.worktrees/review-08t1c-a-r1` (temiz). 09-1 r3 gelirse ikinci sırada.

### R-08T1C-0002 · 2026-11-05 11:34 · → koordinator · YIGIN-AC
Yığın review-08t1c, 18290/13290, yalın (postgres, redis, litellm, fake-llm, qdrant + tools), dalın `.env.test`'i, --pull never. Açık FF yığınları: ffcore-09 + review-08t1c = 2. Disk boş 105 GB. Kapanış down -v + YIGIN-KAPA.

### R-08T1C-0003 · 2026-11-05 11:56 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1c-a r1   Cevap: K-08T1C-0007
**ONAY a4ec5f565c076a232e392f93557ffdf10d1cb69b.** Rapor state/reviews/08-tam-1c-a-r1.md. BLOCKER/MAJOR 0, MINOR 2, NOTE 13.
- 174: `pii_regex` PRSIM'e kaynak ve yol düzeyinde kapalı (guard değişmedi, `6b` testi); M3 bayrağı + `pii_ner` → `text_filter_conflict`.
- S1 test değişikliği yasağın amacını koruyor; varsayım 0 kabul, DUZELT yok.
- 172: API 409 + iş denetimi; M3 audit'i sistem aktörlü, yalnız sayılar; gold + bayrak → `flag_not_applicable`.
- 168: `local_ner` kilidi; süre testleri iki kez yeşil, biri yük altında.
- Kapılar: unit iki profil 1608, lint, hedefli test-int iki profil 61 passed / 3 skipped, süre testleri 60 ×2.
- MINOR (merge öncesi küçük commit ya da FOLLOWUP, senin kararın):
  - (1) docs/bilgi-tabani.md:46-47 `pii_regex`'te müşteri verisi "durur" diyor, aslında yalnız maskelenir;
  - (2) OpenAPI iç NER 503 listesinde `ner_offsets_unavailable` yok.
- **SÜREÇ İHLALİ (benim):**
  - Yalın yığında `fake-llm` backend imajını kullanıyor ve kendi build tanımı yok; ayrı `docker compose build backend` koştum (biri doğrulama).
  - BuildKit iki kez `docker.io` ve `ghcr.io`'dan **base imaj metadata'sı çekti** (1-2 sn; katman indirilmedi, hepsi CACHED; `08t1c-a-r1-build.log`). Dış bağlantı kuralına aykırı.
  - Önceki `up --build --pull never` açılışlarının aynı çağrıyı yapıp yapmadığı doğrulanmadı.
  - Öneri: yalın yığın için önceden etiketli yerel imaj kuralı; ENV/süreç kaydı senin kararın.
- İlk açılışımda `--build` eksikti (ilk test-int geçersiz, yeniden koşuldu).

### R-08T1C-0004 · 2026-11-05 11:56 · → koordinator · YIGIN-KAPA
review-08t1c `down -v --remove-orphans` (11:54): 0 konteyner, 0 hacim. Worktree kaldırıldı (dizin de silindi). Açık inceleyici yığını yok.

### R-08T1C-0005 · 2026-11-05 12:04 · → koordinator · ONAY-TEYIT
Paket: 08-tam-1c-a r2   Cevap: K-08T1C-0011
**ONAY-TEYIT 60c6169c93b65399b25283b63f096c8e4cec4732** (a4ec5f5 atası, 2 commit, 5 dosya). MINOR-1 (docs `pii_regex` maskeler, durdurmaz) ve MINOR-2 (`ner_offsets_unavailable` OpenAPI, docstring, api.md) kapandı. Test dört 503 kodunu da denetliyor ve a4ec5f5'te düşer. Rapor 08-tam-1c-a-r1.md "r2 teyidi". Yalnız okuma. Şimdi 09-1 r3.

### R-08T1C-0006 · 2026-11-05 17:46 · → koordinator · ACK
Paket: 08-tam-1c-b r1   Cevap: K-08T1C-0020
2a7b430d680d1bf6c99b3741b62a21339fa6fcf1 doğrulandı (105d176 atası; 7 commit, 10 dosya; `state/` 0). Worktree `.worktrees/review-08t1c-b-r1`. Statik okuma şimdi (docker yok). `-m models` koşuları 09-2 kapıları ve REVIEW-SONUC'tan sonra.

### R-08T1C-0007 · 2026-11-05 17:52 · → koordinator · DURUM
Paket: 08-tam-1c-b r1   Cevap: koordinatör (SHA değişecek)
2a7b430 üzerindeki statik okuma sürüyor (yalnız okuma). Yeni SHA gelince ek olarak yalnız 2a7b430..yeni delta'yı okuyacağım; `-m models` koşuları yalnız yeni SHA'da. Önce 09-2.

### R-08T1C-0008 · 2026-11-05 19:53 · → koordinator · ACK
Paket: 08-tam-1c-b r1 (r1b)   Cevap: K-08T1C-0022
5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809 doğrulandı (2a7b430 atası, 1 commit, 7 dosya). Worktree `.worktrees/review-08t1c-b-r1b`; 2a7b430 worktree'si kaldırıldı. Koşular yığınsız, `ffcore/tools:0.0.0-08t1c` imajıyla (build yok): lint, make test ×2, `-m models` (`--network none`, `04a-knowledge-core_model_cache:/models:ro`, komut ve mount logda), gecikme testi yalnız bilgi amaçlı (kabul hedef donanımda, NOT_RUN).

### R-08T1C-0009 · 2026-11-05 20:06 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1c-b r1 (r1b)   Cevap: K-08T1C-0020 / K-08T1C-0022
**ONAY 5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809.** Rapor state/reviews/08-tam-1c-b-r1.md. BLOCKER/MAJOR 0, MINOR 6, NOTE 7.
- KAPANDI:
  - `first` (keşifte `simple` 'LIK' / 'AR' parçalıyordu);
  - int8 yalnız Linear, sessiz fp32 yok, her yükleme yolunda;
  - akdeniz27 sabit commit + safetensors; savasy seçilmedi;
  - uzun metin üç pencere; egress PERSON gerçek modelle;
  - r1b: `ner_latency` ayrı işaret (`-m models`'te 1 deselected), egress özellik testi sızıntı açısından gevşemedi (`fullmatch` her şeyi yer tutucu ister).
- Koşular (yığınsız, `--network none`, `/models:ro`): lint, make test 1743 ×2, `-m models` 20 passed + 1 deselected, `verify.sh --models` OK 73. 3 error `test_04a_e2e_stack` canlı yığın ister, 1c-b dışı, NOT_RUN. Gecikme bilgi amaçlı P95 191 ms (dizüstü; kabul hedef donanımda).
- **Merge öncesi önerilen MINOR'lar:**
  - (4) model volume'unda lisanssız savasy ve pickle `pytorch_model.bin` var; `save.sh` volume'u bütünüyle paketliyor, `verify.sh` fazlayı işaretlemiyor → air-gap paketine gider;
  - (2) her adın tam kapsandığını assert eden test yok (örtüşme "bulundu" sayılıyor).
- Diğerleri FOLLOWUP: `simple` kırmızısı yalnız keşifte; `min_confidence` ölçümde yok; docs gecikme aralığı loglarla uyumsuz.
- Worktree kaldırıldı. Sıradaki 09-2 r2.

### R-08T1C-0010 · 2026-11-05 20:29 · → koordinator · ONAY-TEYIT
Paket: 08-tam-1c-b r1c   Cevap: K-08T1C-0026
**ONAY-TEYIT b567b7d66c55bb4559a26f081b328a37e4ef6440** (5e9a688 atası; 2 commit, 9 dosya). Rapor 08-tam-1c-b-r1.md "r1c teyidi".
- MINOR-2 tam kapsama sayısı; MINOR-3 motor eşiği; MINOR-4 `save.sh` yalnız `models.txt` dosyalarını paketliyor, `verify.sh` listede olmayanı FAIL veriyor (silmeden).
- **Gerçek volume'da beklenen FAIL** (akdeniz27 `pytorch_model.bin` + savasy dizini); temiz liste PASS `test_08t1c_12`.
- Koşular `--network none`, `/models:ro`: hedefli birim 15 passed (×2), `-m models` NER 7 passed, lint temiz. İlk birleşik koşuda tek seferlik `FileNotFoundError` yeniden üretilemedi.
- Not: `save.sh` volume temizlenmeden paket üretmez (doğru).

### R-08T1C-0011 · 2026-11-05 20:29 · → koordinator · DUZELTME
Paket: 08-tam-1c-b r1c   Cevap: R-08T1C-0010
Mesajdaki "worktree kaldırıldı" eksik: `.worktrees/review-08t1c-b-r1c` git kaydından kaldırıldı ama dizin Windows izni yüzünden diskte kaldı (temizlik listesine; `--force` yok).
