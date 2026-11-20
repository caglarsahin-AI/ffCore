# Arşiv: inceleyici · 12

Salt okunur; mesajlar ve ID'ler değişmeden taşındı (MULTI_AGENT_PROTOCOL 'Bağlam bütçesi ve arşiv'). Taşıma: 2026-11-20, koordinatör.

### R-12-0001 · 2026-11-20 13:17 · → koordinator · YIGIN-AC
Paket: 12-1 · Cevap: K-12-0006 · Yigin: ffcore-rv (18540/13540; egress + tls + test overlay, 0.0.0-main, --no-build --pull never)
12-1 r1 incelemesi başladı (SHA fc688b0). Kod okuması bitti. Egress/TLS test yığınını açıyorum: işçinin `test_12_*` testleri, preflight matrisi, probe'lar. Tam test-int yok (ENV-209).

### R-12-0002 · 2026-11-20 13:31 · → koordinator · YIGIN-KAPA
Paket: 12-1 · Cevap: K-12-0006 · Yigin: ffcore-rv kapandı (down -v; konteyner, volume ve ağ 0)
Overlay'li yığın kapandı. Rapor birazdan; log `state/evidence/12-1-r1-rv-down.log`.

### R-12-0003 · 2026-11-20 13:33 · → koordinator · REVIEW-SONUC
Paket: 12-1 · Cevap: K-12-0006 · SHA: fc688b0 · Sonuc: ONAY · Bulgu: B0 M0 m1 N5
Rapor `state/reviews/12-1-r1.md`.

**Testler:**
- işçi `test_12_*` + reserved hosts: 100 passed, 0 skipped (egress ve TLS kabulü dahil)
- probe: 3 passed
- preflight matrisi: 19 durum
- `make smoke`: red ve geçiş yolları ikisi de doğru
- FOLLOWUP-82 benzetimi: tablo gizliyken `/key/info` 500 ve healthcheck exit 1; geri gelince 404

**Odak maddeleri:**
- Egress: izinli 200, izinsiz 403, proxy'siz `ConnectError`, LiteLLM proxy'den; rebind ve IP 403; logda yol yok; 208 belgeli.
- TLS: public dinleyicide başka her yol proxy'nin 404'ü; sertifika operatörden.
- İmaj ID'leri `images.txt` digest'leriyle aynı; `compose config` dört dosyayla geçerli.
- `RESERVED_HOSTS` doğru.

**Bulgular:**
- MINOR-1 `ham-yol-iletimi`: public `proxy_pass`'ta URI yok, ham yol backend'e gidiyor (ör. `/api/v1/auth/me/..%2F..%2F..%2F..%2Fchannels/teams/messages`). Bugün atlatma yok, backend 404 veriyor. Öneri: sabit URI.
- NOTE-1: port aralığı denetlenmiyor (99999 geçiyor).
- NOTE-2: Squid CONNECT dışı method'lara izin veriyor (karar metni "yalnız CONNECT").
- NOTE-3: `to_private` listesinde 198.18/15, 240/4 ve IPv4-mapped yok (doğrulanmadı).
- NOTE-4: preflight'ta mutlak yol ve satır içi yorumda yanlış pozitif (fail-loud).
- NOTE-5: sorun giderme komutunda `$POSTGRES_USER` hostta açılıyor.

### R-12-0004 · 2026-11-20 14:32 · → koordinator · YIGIN-AC
Paket: 12-1 · Cevap: K-12-0011 · Yigin: ffcore-rv (18540/13540; egress + tls + test overlay, 0.0.0-main, --no-build --pull never)
12-1 r2 teyidi başladı (SHA 12e4d54). Delta okundu. Kısa overlay yığını açıyorum: ham yol, Squid aralıkları, port, preflight. Tam test-int yok.

### R-12-0005 · 2026-11-20 14:47 · → koordinator · YIGIN-KAPA
Paket: 12-1 · Cevap: K-12-0011 · Yigin: ffcore-rv kapandı (down -v; konteyner, volume ve ağ 0)
r2 overlay yığını kapandı. Rapor birazdan; log `state/evidence/12-1-r2-rv-down.log`.

### R-12-0006 · 2026-11-20 15:28 · → koordinator · REVIEW-SONUC
Paket: 12-1 · Cevap: K-12-0011 · SHA: 12e4d54 · Sonuc: ONAY · Bulgu: B0 M0 m0 N0
Rapor `state/reviews/12-1-r2.md`.

**Testler:**
- işçi testleri: 84 passed, 0 skipped
- probe: 4 passed

**Maddeler:**
- MINOR-1: backend access logunda public dinleyiciden gelen her istek yalnız `/channels/teams/messages`; ham yol gitmiyor.
- NOTE-3: IP biçimli allowlist girdileriyle sınandı. `198.18.0.x`, `240.0.0.1`, `[::]` ve `[::ffff:198.18.0.10]` 403; kontrol `198.51.100.10` 200.
- NOTE-2: yorum ve docs açık (FOLLOWUP-211).
- NOTE-1: `99999`, `0` ve `abc` preflight'ta, `--egress-list`'te ve `start.sh`'ta açık hata.
- NOTE-4: mutlak yol ve ` #` yorumu geçiyor, sonek tuzağı red; 19 durum r1 ile aynı, `absolute` artık geçiyor.
- NOTE-5: iki `sh -c` komutu hostta değişken yokken çalıştı; sorun giderme sırası LiteLLM'i healthy'ye döndürdü.
- r1 dışı tek değişiklik: `start.sh` chmod, gerekçeli fail-loud düzeltmesi.

### R-12-0007 · 2026-11-20 17:14 · → koordinator · YIGIN-AC
Paket: 12-2 · Cevap: K-12-0020 · Yigin: ffcore-rv (18540/13540; yedek provası projesi, imaj 0.0.0-12 = 080facf backend kaynağı, --pull never)
12-2 r1 incelemesi başladı (SHA 080facf). Kod okuması bitti. Önce yedek/restore provası hostta (`RUN_BACKUP_TESTS=1`, kendi `down -v`/`up`'ı), sonra geri yüklenmiş yığında rol/fonksiyon probe'ları ve hedefli testler. Tam test-int yok.

### R-12-0008 · 2026-11-20 17:31 · → koordinator · YIGIN-KAPA
Paket: 12-2 · Cevap: K-12-0020 · Yigin: ffcore-rv kapandı (down -v; konteyner, volume ve ağ 0)
Yığın kapandı. Rapor birazdan; log `state/evidence/12-2-r1-rv-down.log`.

### R-12-0009 · 2026-11-20 17:33 · → koordinator · REVIEW-SONUC
Paket: 12-2 · Cevap: K-12-0020 · SHA: 080facf · Sonuc: DEGISIKLIK · Bulgu: B0 M2 m0 N3
Rapor `state/reviews/12-2-r1.md`.

**Testler:**
- yedek provası hostta 1 passed: sayılar ve sha eşit, dolu hedefe restore red
- geri yüklenmiş DB'de PUBLIC EXECUTE f, `ffcore_app` X, default privileges yerinde
- hedefli testler 205 passed; `make lint` temiz
- docs komutları (`app-role.sql` ×2, `/readyz`, smoke, superadmin) çalıştı
- vLLM `config -q` ok; preflight Python 3.8 ayrıştırması ve hostun 3.9'u ok

**Bulgular:**
- MAJOR-1 `denetim-bolum-kapisi`: tanımlayıcı fonksiyonlar bölüm yaşına bakmıyor. Yalnız `ffcore_app` ile bu ayın bölümü ayrıldı: audit yazımı durdu ("no partition … found for row"; `ensure_partition` geri bağlamıyor). Ayrılmış bölümde append-only tetikleyici yok ve default DML var: UPDATE 1, DELETE 1. Sonra drop ile bu ayın audit'i silindi. Öneri: fonksiyonlarda retention tabanı (ay sonu ≤ now()−365 gün) ve audit bölümlerinde `ffcore_app`'e yalnız SELECT.
- MAJOR-2 `rol-kullanici-parola-tutarsiz`: `.env.example` `APP_DB_USER=ffcore_app` ve boş parola ile geliyor. Airgap'te (boş parola belgede izinli) compose backend'e kullanıcı olarak `ffcore_app`, parola olarak sahibinkini verir; initdb rolü oluşturmaz, backend açılamaz. Preflight ise "connects as the owner" diyor.
- NOTE-1: `api.md` listesinde `api_base` ve `url` eksik.
- NOTE-2: `tests/deploy` `make lint` dışında (1 E501, 1 format).
- NOTE-3: yedek sırasında yazma tutarlılığı için rehbere bir cümle.

### R-12-0010 · 2026-11-20 18:00 · → koordinator · YIGIN-AC
Paket: 12-2 · Cevap: K-12-0024 · Yigin: ffcore-rv (18540/13540; test profili, imaj 0.0.0-12 + kaynaktan `alembic upgrade head` ile 12_0002, --no-build --pull never)
12-2 r2 teyidi başladı (SHA 5ff32ed). Delta okundu. Kısa yığın: rol probe'u tekrarı, hedefli testler, initdb boş parola denemesi. Tam test-int yok.

### R-12-0011 · 2026-11-20 18:10 · → koordinator · YIGIN-KAPA
Paket: 12-2 · Cevap: K-12-0024 · Yigin: ffcore-rv kapandı (down -v; konteyner, volume ve ağ 0; initdb deneme konteynerleri de silindi)
Yığın kapandı. Rapor birazdan; log `state/evidence/12-2-r2-rv-down.log`.

### R-12-0012 · 2026-11-20 18:11 · → koordinator · REVIEW-SONUC
Paket: 12-2 · Cevap: K-12-0024 · SHA: 5ff32ed · Sonuc: ONAY · Bulgu: B0 M0 m0 N2
Rapor `state/reviews/12-2-r2.md`.

**Testler:** `make lint` temiz (`tests/deploy` dahil), hedefli testler 142 passed. 12_0002 kaynaktan uygulandı.

**Maddeler:**
- `ffcore_app` ile bu ayın ve 12 ay önceki bölümün detach/drop'u `audit_partition_too_recent`. Bu ayın bölümünde UPDATE/DELETE permission denied, INSERT sürüyor. 13 ay önceki bölüm detach, okuma ve drop'tan geçiyor. Ayrılmış bölümde yalnız SELECT. `ensure_partition` ayrılmış ayda `audit_partition_detached`.
- Preflight: altı yarım-çift durum (üç profil) `db_role_incomplete`.
- initdb: `ffcore_app` + boş parola exit 1.
- Docs, `api.md` alanları ve `.env.example` doğru.

**Yeni notlar:**
- NOTE-1: initdb yalnız-parola durumunda durmuyor; `.env.example` yorumu durduğunu söylüyor.
- NOTE-2: `db_role_owner` mesajı yalnız parolayı söylüyor.
