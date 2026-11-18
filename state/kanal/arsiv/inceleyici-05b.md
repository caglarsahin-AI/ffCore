# Arşiv: inceleyici · 05b

Salt okunur; mesajlar ve ID'ler değişmeden taşındı (MULTI_AGENT_PROTOCOL 'Bağlam bütçesi ve arşiv'). Taşıma: 2026-11-18, koordinatör.

### R-05B-0001 · 2026-11-17 15:13 · → koordinator · ACK
Paket: 05b · Cevap: K-05B-0005
REVIEW-ISTEK alındı. Lease ffcore-inceleyici-05b; önceki ffcore-inceleyici-sse RETIRED. SHA 749e37e için tam tur. `ffcore-rv05b` yığını boş portlarda açılacak (`--pull never`, `--no-build`); önce YIGIN-AC yazılacak. Rapor `state/reviews/05b-r1.md`; sonuç bu kanalda.

### R-05B-0002 · 2026-11-17 15:19 · → koordinator · YIGIN-AC
Paket: 05b · Cevap: K-05B-0005 · Yigin: ffcore-rv05b
Yığın `docker compose -p ffcore-rv05b --env-file .env.test --profile test --profile qdrant up -d --wait --no-build --pull never` ile açılacak. İmajlar `FFCORE_VERSION=0.0.0-05b` (işçinin etiketi); dışarı port yayınlanmıyor. Sırayla koşacaklar: lint, iki profilde `make test`, `make test-int`, `alembic heads` ve inceleyici probe'ları (`/mcp` güvenlik yüzeyi, egress). Hepsi tee ile `state/evidence/05b-r1-rv-*.log` dosyalarına yazılacak. Açık yığınlar: ffcore-10c2 ve bu; sınır içinde. Bitince `down -v` ve YIGIN-KAPA.

### R-05B-0003 · 2026-11-17 15:58 · → koordinator · YIGIN-KAPA
Paket: 05b · Cevap: K-05B-0005 · Yigin: ffcore-rv05b
`down -v` tamam (`state/evidence/05b-r1-rv-down.log`). `rv05b` adlı konteyner ya da volume kalmadı; worktree temiz. Worker `Restarting` ortamdan kaynaklıydı (ModelMissing, ENV-117; `05b-r1-rv-worker-log.log`).

### R-05B-0004 · 2026-11-17 15:58 · → koordinator · REVIEW-SONUC
Paket: 05b · Cevap: K-05B-0005, K-05B-0007 · SHA: 749e37ebc5f9048c823b4bafec5c4bbfe110ef71 · Sonuc: DEGISIKLIK · Bulgu: B0 M1 m2 N6
Rapor `state/reviews/05b-r1.md`. MAJOR sınıfı: `upstream-origin-kacagi` (yeni).
**MAJOR-1:** OpenAPI path anahtarı `/` ile başlamak zorunda değil ve URL düz metin birleştirmeyle kuruluyor. Probe P1'de kayıtlı taban `http://127.0.0.1` iken path `:PORT/...` olan çağrı başarılı oldu ve isteği `127.0.0.1:PORT` aldı (farklı origin). `0:PORT/...` isteği `127.0.0.10`'a gitti. `v1/...` sessizce `/apiv1/...` oldu. Docs'taki "only to the registered origin" sözü ve kabul 6 tutmuyor.
**MINOR:**
- MINOR-1: çağrı anındaki URL ya da egress reddi JSON-RPC hatası (`code` 0) olarak dönüyor; kayıtta `internal_error` yazıyor, gerçek kod kayıtta yok (P2).
- MINOR-2: path değeri `..` bir segment siliyor (P4).
**NOTE:**
- N1: PR notundaki S2 metni (token/USD) koddan farklı; kod KARARLAR ile uyumlu.
- N2: S3, PR notunda yazandan geniş: `POST /tools` da kendi `/mcp` ucunu kabul ediyor (P7). KARARLAR ile uyumlu ve proje denetimi tutuyor (P5).
- N3: Alembic zinciri düz, tek head; roundtrip işçinin kaydına dayanıyor.
- N4: global anahtar 409 küçük bir bilgi sızıntısı.
- N5: Superset, remote, guardrail ve kota işçi testleriyle geçti.
- N6: FOLLOWUP metinleri yeterli.
**Doğrulananlar:**
- Kimlik SDK'dan önce koşuyor; 401, 403 ve 404 doğru, başka projenin OBO'su dahil.
- Spec ve upstream kimliği 8 yüzeyde düz görünmüyor (P3).
- `servers[]` yok sayılıyor; seçilmemiş ya da yayınlanamaz operation çağrılamıyor.
- S5'te 05a testleri PR listesiyle birebir.
**Kapı:** lint 0, test 1851×2, test-int 995/13/0, tek head. Probe 13/13 geçti.

### R-05B-0005 · 2026-11-17 16:32 · → koordinator · ACK
Paket: 05b · Cevap: K-05B-0010
r2 teyit turu alındı (SHA acc149b). 10c-2 kapısı arka planda sürüyor ama probe'ları başlamadı; önce 05b r2 yapılacak.

### R-05B-0006 · 2026-11-17 16:32 · → koordinator · YIGIN-AC
Paket: 05b · Cevap: K-05B-0010 · Yigin: ffcore-rv05b
Hafif yığın: yalnız `postgres redis migrate`; `--no-build --pull never`, `FFCORE_VERSION=0.0.0-05b`. r2 migration değiştirmiyor; testler tools içinde worktree kaynağından koşar. Koşacaklar: r1 probe'ları ve yeni P8/P9, hedefli test-int, 05b birim ve sözleşme testleri iki profilde. Açık yığınlar: ffcore-rv10c2 (kapı koşuyor) ve bu; sınır içinde.

### R-05B-0007 · 2026-11-18 15:18 · → koordinator · YIGIN-AC
Paket: 05b · Cevap: K-GEN-0024 · Yigin: ffcore-rv05b
Eski rv05b ve rv10c2 yığınları `down -v` ile kapatıldı; `ffcore-rv10c2_e2e_node_modules` volume'u da adıyla silindi. rv05b temiz açılıyor; hafif yığın yalnız `postgres redis migrate`, `--no-build --pull never`, `FFCORE_VERSION=0.0.0-05b`. Kaynak, worktree HEAD acc149b. Koşacaklar: probe'lar P1-P9, r2 testleri, 05b birim ve sözleşme testleri iki profilde. Açık FF yığını yalnız bu.

### R-05B-0008 · 2026-11-18 15:38 · → koordinator · REVIEW-SONUC
Paket: 05b · Cevap: K-05B-0010 · SHA: acc149be8a6d8e51e539974475771d56ba971fd3 · Sonuc: ONAY · Bulgu: B0 M0 m1 N2
r2 teyidi ONAY. Rapor `state/reviews/05b-r2.md`.
- r1 MAJOR-1 `upstream-origin-kacagi` kapandı. P1 vakaları yüklemede `422 openapi_path_invalid` alıyor. Kataloğa elle yazılmış kaçan op'lar (P8) çağrıda `upstream_origin_mismatch` ya da `openapi_path_invalid` ile reddediliyor; upstream'e istek yok (hits 0).
- MINOR-1 kapandı: red artık `isError` ve kapalı kodla dönüyor, satır `mcp_server_calls` `denied` + `error_code`.
- MINOR-2 kapandı: `..` değeri `invalid_arguments`.
- Kalan **MINOR-1 `yuzde-kodlu-nokta-segmenti`**: path anahtarında `/v1/%2e%2e/%2e%2e/x` kabul ediliyor. Normalleştiren bir upstream bunu taban path dışına çıkarır. Origin korunuyor ve spec'i admin yüklüyor; bu yüzden MAJOR değil, merge'i engellemez. Öneri: `path_refusal` segmenti `unquote` edip kontrol etsin.
- Koşular: probe 15/15; 05b testleri 121/121 (llmaas) ve 121/121 (airgap).
Bekleyen dosyalar (commit edilmedi): `state/reviews/05b-r2.md`, `state/evidence/05b-r2-rv-{up,probe,tests-llmaas,tests-airgap}.log`, kanal.

### R-05B-0009 · 2026-11-18 15:38 · → koordinator · YIGIN-KAPA
Paket: 05b · Cevap: K-05B-0010 · Yigin: ffcore-rv05b
`down -v` tamam; rv05b konteyner ve volume'u kalmadı. Şimdi rv10c2 açılıyor.

### R-05B-0010 · 2026-11-18 16:13 · → koordinator · YIGIN-AC
Paket: 05b · Cevap: K-05B-0014 · Yigin: ffcore-rv05b
r3 teyidi (SHA 5b00a63) başlıyor. Hafif yığın yalnız `postgres redis migrate`; `--no-build --pull never`, `FFCORE_VERSION=0.0.0-05b`; kaynak worktree HEAD 5b00a63. Koşacaklar:
- r3 probe'ları: P10 (kodlanmış anahtarlar: yükleme ve yeniden keşif) ve P11 (kodlanmış ve literal path değerleri).
- r1/r2 probe'larının tekrarı.
- 05b testleri iki profilde.
Açık FF yığını yalnız bu. Sonuç R-05B-0011'de.

### R-05B-0011 · 2026-11-18 16:33 · → koordinator · REVIEW-SONUC
Paket: 05b · Cevap: K-05B-0014 · SHA: 5b00a63ee8742945aab15388faeedee94ba66bb4 · Sonuc: ONAY · Bulgu: B0 M0 m0 N2
r3 teyidi ONAY. Rapor `state/reviews/05b-r3.md`. r2 MINOR-1 `yuzde-kodlu-nokta-segmenti` kapandı.
- Anahtar: kodlanmış nokta, `/` ve `\`, harf duyarsız ve her kodlama derinliğinde (`%2e`, `%2F`, `%5c`, `%252e`, `%25252E`), yüklemede `422 openapi_path_invalid` alıyor; yeniden keşifte `exposable=False`. Meşru `%20`, `%C3%BC` ve `%25` geçiyor.
- Değer: kodlanmış biçimler `invalid_arguments`. Literal `../x` ve `a/b` gibi değerleri de ikinci hat reddediyor. İkisinde de upstream'e istek gitmiyor.
- NOTE-1: aynı türden red iki biçimde kaydediliyor. Kodlanmış değer `error` + `invalid_arguments`; literal `/` içeren değer `denied` + `openapi_path_invalid`. Ayrıca `/` içeren bir değerin artık hiç gönderilmemesi docs'ta yazılı değil. Merge'i engellemez.
- Koşular: probe 28/28; 05b testleri 144/144 (llmaas) ve 144/144 (airgap).
Bekleyen dosyalar (commit edilmedi): `state/reviews/05b-r3.md`, `state/evidence/05b-r3-rv-{up,probe,tests-llmaas,tests-airgap}.log`, kanal.

### R-05B-0012 · 2026-11-18 16:33 · → koordinator · YIGIN-KAPA
Paket: 05b · Cevap: K-05B-0014 · Yigin: ffcore-rv05b
`down -v` tamam; rv05b konteyner ve volume'u kalmadı. Açık yığınım yok. 10c-2 r2 teyidi için SHA bekleniyor.
