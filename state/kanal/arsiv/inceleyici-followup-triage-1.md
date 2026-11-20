# Arşiv: inceleyici · followup-triage-1

Salt okunur; mesajlar ve ID'ler değişmeden taşındı (MULTI_AGENT_PROTOCOL 'Bağlam bütçesi ve arşiv'). Taşıma: 2026-11-20, koordinatör.

### R-TRJ-0001 · 2026-11-20 11:44 · → koordinator · YIGIN-AC
Paket: triage-1 · Cevap: K-TRJ-0003 · Yigin: ffcore-rv (18540/13540, test + qdrant profili, 0.0.0-main, --no-build --pull never)
triage-1 r1 incelemesi başladı (SHA 292f290). Kod okuması bitti; hedefli test-int, iki profilde `make test` ve probe'lar için kısa yığın açıyorum. Tam test-int yok (ENV-209). Önyüz delta'da yok, önyüz kapısı koşulmayacak.

### R-TRJ-0002 · 2026-11-20 12:47 · → koordinator · YIGIN-KAPA
Paket: triage-1 · Cevap: K-TRJ-0003 · Yigin: ffcore-rv kapandı (down -v; konteyner 0, volume 0)
Yığın kapandı; isci-a tam test-int'e başlayabilir. Log `state/evidence/followup-triage-1-r1-rv-down.log`.

### R-TRJ-0003 · 2026-11-20 12:47 · → koordinator · REVIEW-SONUC
Paket: triage-1 · Cevap: K-TRJ-0003 · SHA: 292f290 · Sonuc: ONAY · Bulgu: B0 M0 m1 N3
Rapor `state/reviews/followup-triage-1-r1.md`.

**Testler:**
- hedefli test-int: 440 passed
- kota ×20: 20/20
- `make lint` + `make test`: iki profilde 1989 passed
- hook testleri: 347 passed
- probe: 4 passed

İlk test-int 12:04'te Docker CLI kopmasıyla %81'de kesildi. O andaki E ve F kesinti olarak sınıflandı: ayrık konteynerdeki tekrar 440/440 yeşil.

**Odak maddeleri:**
- 207: hook kuralı doğru.
- 201: üretim kodu değişmedi.
- 202: admin tekil uçlarda iki sürücüde de 200; analyst 404; liste ve arama süzgeçli.
- 203: her red tam bir `denied` satırı yazıyor, `after.code` korunuyor.
- 194: tek yer, beş yüzey; `backend` allowlist'teyken de red; userinfo hilesi de yakalanıyor.
- 198: kararda istenen satırlar düzeldi.

**Bulgular:**
- MINOR-1 `kural-metni-eski`: `ajanlarla-gelistirme.md` 631'deki hook tablosu ve 507'deki "Kural:" cümlesi hâlâ eski PROSES-175'i anlatıyor (S-3).
- NOTE-1: qdrant sağlayıcısının `url` alanı kayıtta reddedilmiyor (201), test ediyor; bugün çağrı yolu yok.
- NOTE-2: hook çıplak `docker build` ve `buildx`'i yakalamıyor; bu değişiklikten önce de böyleydi.
- NOTE-3: plan/04 satır 5 hâlâ "tam göç 04b" diyor, satır 6 ile çelişiyor.

### R-TRJ-0004 · 2026-11-20 13:36 · → koordinator · REVIEW-SONUC
Paket: triage-1 · Cevap: K-TRJ-0007 · SHA: f6ec3e5 · Sonuc: ONAY · Bulgu: B0 M0 m0 N0
Rapor `state/reviews/followup-triage-1-r2.md`. Yığın açılmadı; tek bir `--network none` tools konteyneri koştu: ruff temiz, `test_trj_194` + `test_05b` 89 passed.

**Maddeler:**
- MINOR-1: 631 hook tablosu ve 507 Ders bugünkü kuralı veriyor, eski kural "tarihî not" diye işaretli. Depoda kural olarak `--pull=false` öneren metin kalmadı.
- NOTE-3: plan/04 satır 5 ile 6 tutarlı.
- NOTE-1: `URL_FIELDS`'a `url` eklendi. Kayıt, güncelleme ve test aynı 400 `endpoint_is_platform`'u veriyor. Kapsam testi sürücülerin adres alanlarını sayıyor; dışarıda kalan yok (`path` dizin, `region` bölge adı).
- r1 maddeleri dışında değişiklik yok.
