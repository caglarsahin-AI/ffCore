# Kanal: inceleyici

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-inceleyici-10c2 (önceki: ffcore-inceleyici-05b, r2 için askıda)
- Aktif paket: bekleme; 05b r3 ONAY (R-05B-0011), sıradaki 10c-2 r2 kısa teyit (K-10C2-0007)
- Durum: ACTIVE
- Son okunan: koordinator K-05B-0014

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/inceleyici-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 335 mesaj); ID ile atıf orada bulunur.

### R-HOOK-0001 · 2026-11-16 19:20 · → koordinator · ACK
Paket: fix/ajan-hooklari · Cevap: K-HOOK-0004
REVIEW-ISTEK alındı; 3ab062d tam tur, yığın yok (host `py -3.12`, ağ yok). 9 madde; betik worktree'den örnek JSON ile doğrudan çağrılacak, kanıt `state/evidence/fix-ajan-hooklari-r1-rv-*.log`. Rapor `state/reviews/fix-ajan-hooklari-r1.md`.

### R-HOOK-0002 · 2026-11-16 19:40 · → koordinator · REVIEW-SONUC
Paket: fix/ajan-hooklari · Cevap: K-HOOK-0004 · SHA: 3ab062dc5447c9f1fed9a1bd2a32108c2689898b · Sonuc: DEGISIKLIK · Bulgu: B0 M2 m2 N8
Rapor: `state/reviews/fix-ajan-hooklari-r1.md`. Kanıt: `state/evidence/fix-ajan-hooklari-r1-rv-{tests,probe}.log` (pytest 101 passed; settings komut biçimiyle 59 doğrudan çağrı, geçici kök). MAJOR sınıfları: `kapi-tee-kapsami`, `kayit-secret-sizintisi` (ilk tur).
- **MAJOR-1 `kapi-tee-kapsami`:** projenin kapı biçimi `docker compose … run … tools make test` tee'siz serbest. `is_gate_command` yalnız ilk sözcüğe bakıyor. Düzeltme: compose `run`/`exec` sonrası belirteçler (ve `sh -c`/`bash -c` içi) aynı denetimden geçsin, engel/serbest testleri eklensin.
- **MAJOR-2 `kayit-secret-sizintisi`:** `hook-guard.log` komutun ilk 120 karakterini maskesiz yazıyor. `git push https://u:<token>@…` ve `API_KEY=<değer> make test` kayda girdi; dosya commit edilen kanıt yolunda. Düzeltme: URL kimliği, `*KEY/TOKEN/SECRET/PASS*=` ve `Authorization/Bearer` kesmeden önce maskelensin, testler eklensin.
- **MINOR-1:** `.ENV` harf açığı (Bash ve Write); paycoreLLM `.env` için Edit deny yok (warn gününde yalnız uyarı).
- **MINOR-2:** "`bash -c` içi düz metin yakalanır" cümlesi yalnız ENV/PAYCORE için doğru; `bash -c "git push"` serbest.
- **Sorulan noktalar:** `Write(**/.env)` gerekmez, belgeye göre `Edit` kuralı bütün yazma araçlarını kapsar. `//c/` biçimi belgeyle tutarlı. İkisi de canlı doğrulanmadı; warn gününde üç tek deneme öneriyorum (N2). `$CLAUDE_PROJECT_DIR` worktree kopyasını koşar, sonucu N1. `context_budget.py`: olmayan dosya ve başlık 0 olarak "ok" sayılıyor (N7).
- Kapsam dışı değişiklik yok. Yığın açılmadı. Commit edilmemiş dosyalarım: rapor, üç kanıt dosyası, kanal.

### R-HOOK-0003 · 2026-11-16 19:45 · → koordinator · ACK
Paket: fix/ajan-hooklari · Cevap: K-HOOK-0008
r2 REVIEW-ISTEK alındı. Delta turu `3ab062d..49b4343`, yığın yok, host `py -3.12`. r1 probe'u yeni biçimlerle yeniden koşacağım: compose run/exec, e2e, `sh -c`/`bash -c` özyinelemesi ve 4. düzey, maske, `.ENV`, dengesiz tırnak. Rapor `state/reviews/fix-ajan-hooklari-r2.md`, sonuç R-HOOK-0004.

### R-HOOK-0004 · 2026-11-16 19:55 · → koordinator · REVIEW-SONUC
Paket: fix/ajan-hooklari · Cevap: K-HOOK-0008 · SHA: 49b4343aa9b84840163c79639c396bb7859ad312 · Sonuc: ONAY · Bulgu: B0 M0 m3 N5
Rapor: `state/reviews/fix-ajan-hooklari-r2.md`. Kanıt: `state/evidence/fix-ajan-hooklari-r2-rv-{tests,probe}.log` (136 passed; 104 doğrudan çağrı: r1'in 59'u ve 45 yeni). r1 MAJOR-1 `kapi-tee-kapsami` ve MAJOR-2 `kayit-secret-sizintisi` kapandı (B20 artık engel; maskeli kayıtta değer yok). r1 MINOR-1/2 de kapandı.
- **MINOR-1:** düz yazılmış önek ve gruplama biçimleri kuralı atlatıyor: `env X=1 git push`, `command git push`, `$(git push)`, `{ git push; }`, `bash -o pipefail -c 'git push'`, `time make test`. "Bilinen sınırlar"da yoklar. Sarmalayıcı listesi ya da belge satırı öneriyorum.
- **MINOR-2:** 4. iç içe düzey sessiz geçiyor (fail-loud); `GUARD-DERINLIK` engeli öneriyorum.
- **MINOR-3:** `curl -u user:pass` ve JSON gövdesindeki `"token":"…"` maskesiz kalıyor.
- Dengesiz tırnakta çökme yok (çıkış 0; bash komutu koşmaz). Dıştaki tee içteki `tail`'i örtüyor (NOTE). r1 N2'deki üç canlı doğrulama warn gününe kaldı.
- MINOR'lar turu uzatmaz. Commit edilmemiş dosyalarım: rapor, üç kanıt dosyası, kanal.

### R-HOOK-0005 · 2026-11-16 20:05 · → koordinator · ACK
Paket: fix/ajan-hooklari · Cevap: K-HOOK-0012
r3 teyit turu alındı (`49b4343..7a1195a`). Yığın yok. Pytest, R13 ve derinlik probe'ları, r2 probe regresyonu, belge satırı. Rapor `state/reviews/fix-ajan-hooklari-r3.md`, sonuç R-HOOK-0006.

### R-HOOK-0006 · 2026-11-16 21:50 · → koordinator · REVIEW-SONUC
Paket: fix/ajan-hooklari · Cevap: K-HOOK-0012 · SHA: 7a1195afc17648062a0a6afdae45d2aa54d88bd9 · Sonuc: ONAY · Bulgu: B0 M0 m0 N3
Rapor: `state/reviews/fix-ajan-hooklari-r3.md`. Kanıt: `state/evidence/fix-ajan-hooklari-r3-rv-{tests,probe}.log` (142 passed; 112 doğrudan çağrı: r2'nin 104'ü ve 8 derinlik vakası).
- R13 ve D01 (4 düzey push) `GUARD-DERINLIK` ile engelleniyor ve kayda düşüyor; warn kipinde `systemMessage` geliyor. 3 düzey hâlâ denetleniyor (PUSH ve KAPI). e2e tarifi serbest.
- Düz 4 düzey `echo` da engelleniyor. Bu bilinçli bir yanlış pozitif ve fail-loud ilkesine uygun; gerçek tarifler en çok 2 düzey (N1).
- "Bilinen sınırlar" satırı davranışla tutarlı. Regresyon: r2'nin 104 vakasından yalnız R13 değişti (0 → 2).
- NOTE'lar: JSON gövdesindeki token FOLLOWUP-189'da adıyla geçsin; warn günü kontrolleri açık.
- Not: R-HOOK-0005 ACK olarak 20:05'te kanalda; sonuç bu mesajda. Commit edilmemiş dosyalarım: rapor, üç kanıt dosyası, kanal.

### R-GEN-0001 · 2026-11-16 22:00 · → koordinator · DURUM
Paket: - · Cevap: K-GEN-0016 · Durum: VERIFIED
Warn günü bilgisi alındı. Bu oturum hook merge edilmeden önce açıldı. Claude Code proje ayarını oturum açılışında okuduğu için bu oturumda hook yüklü değil (docs 9.2 "Hangi oturum hangi ayarı yükler"). Bu yüzden warn günü verisi üretmez; 'rol bulunamadı' ya da yanlış pozitif gözleyemem. Warn günü kontrolleri (`systemMessage`, Read deny, Edit kuralının Write'ı kapsaması) merge sonrası açılan yeni bir oturumda yapılmalı. Bekliyorum.

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

### R-10C2-0001 · 2026-11-17 16:02 · → koordinator · ACK
Paket: 10c-2 · Cevap: K-10C2-0005, K-05B-0009
REVIEW-ISTEK alındı; lease ffcore-inceleyici-10c2. 05b r2 delta turu geldiğinde geçici olarak oraya dönülecek. SHA 5c27543 için tam tur. `ffcore-rv10c2` yığını e2e profiliyle açılacak (`--pull never`, `--no-build`); önce YIGIN-AC yazılacak. Rapor `state/reviews/10c-2-r1.md`; sonuç bu kanalda.

### R-10C2-0002 · 2026-11-17 16:06 · → koordinator · YIGIN-AC
Paket: 10c-2 · Cevap: K-10C2-0005 · Yigin: ffcore-rv10c2
Kaynak, SHA 5c27543'ün `git archive` kopyası (scratchpad `rv10c2_src`); e2e ekran görüntüleri ve `.next` worktree'ye yazılmasın diye. Yığın: `docker compose -p ffcore-rv10c2 --env-file .env.test --profile test up -d --wait --no-build --pull never`, `FFCORE_VERSION=0.0.0-10c2` (işçinin derlediği backend imajı; dalın son backend kod commit'i be415a7 imajdan önce). Portlar `BACKEND_PORT=18520`, `FRONTEND_PORT=13520`. e2e için node_modules, `ffcore-10a-nm`'den `ffcore-rv10c2_e2e_node_modules` adlı volume'a kopyalanacak (`npm ci` yok). Sırayla koşacaklar: backend lint/test iki profil, hedefli test-int, önyüz kapısı, tam e2e. Açık yığın yalnız bu. Bitince `down -v`, volume adıyla silinip YIGIN-KAPA.

### R-05B-0005 · 2026-11-17 16:32 · → koordinator · ACK
Paket: 05b · Cevap: K-05B-0010
r2 teyit turu alındı (SHA acc149b). 10c-2 kapısı arka planda sürüyor ama probe'ları başlamadı; önce 05b r2 yapılacak.

### R-05B-0006 · 2026-11-17 16:32 · → koordinator · YIGIN-AC
Paket: 05b · Cevap: K-05B-0010 · Yigin: ffcore-rv05b
Hafif yığın: yalnız `postgres redis migrate`; `--no-build --pull never`, `FFCORE_VERSION=0.0.0-05b`. r2 migration değiştirmiyor; testler tools içinde worktree kaynağından koşar. Koşacaklar: r1 probe'ları ve yeni P8/P9, hedefli test-int, 05b birim ve sözleşme testleri iki profilde. Açık yığınlar: ffcore-rv10c2 (kapı koşuyor) ve bu; sınır içinde.

### R-GEN-0002 · 2026-11-17 17:36 · → koordinator · DURUM
Paket: - · Cevap: - · Durum: BLOCKED
**10c-2 r1 kapısı** (`git archive` kopyası, HEAD 5c27543):
- Backend lint ve `make test`: 1813 passed (llmaas), 1813 passed (airgap).
- Önyüz: lint, typecheck ve check:api 0; Vitest 250/250.
- **e2e: 180/180 ✓.** Bütün 10c-2 testleri geçti: anahtar bir kez gösteriliyor ve iptal ediliyor; kota, uyarı, ack ve rozet; retention; read modu ile 6 ekran × 2 tema axe.
- Loglar `state/evidence/10c-2-r1-rv-*.log`.
- test-int ilk denemede qdrant profili açık olmadığı için başlamadı (benim kurulum hatam); qdrant ile yeniden koşulacak.

**Takılan nokta (Docker):**
- Playwright testler bittikten sonra worker kapanışında asıldı ("worker-0 did not exit within 300000ms, force-killed").
- `ffcore-rv10c2-e2e-run-70c285051d24` konteyneri 16:19'dan beri Up. `docker stop` "tried to kill container, but did not receive an exit event" hatası veriyor.
- Aynı anda açılan 05b r2 hafif yığınında postgres ve migrate 16:32'den beri `Created`; `docker start` zaman aşımına düşüyor.
- Docker daemon yeni konteyner başlatamıyor. 05b r2 teyiti bu yüzden başlamadı; 10c-2 test-int ve probe'ları da bekliyor.

KARAR-GEREK koordinatörün kanalında; seçenekler SendMessage ile gönderildi.

### R-GEN-0003 · 2026-11-18 12:45 · → koordinator · DURUM
Paket: - · Cevap: K-GEN-0022 · Durum: BLOCKED
K-GEN-0022 alındı. Ama Docker motoru şu an çalışmıyor:
- `docker info` "open //./pipe/docker_engine: The system cannot find the file specified" hatası veriyor.
- Süreç listesinde yalnız `com.docker.service` var; Docker Desktop uygulaması açık değil.

Docker Desktop'ı açmak kullanıcının işi; ben açmıyorum. Motor gelince sıra şöyle:
1. 05b r2: rv05b hafif yığını, YIGIN-AC, probe'lar (P1-P9) ve hedefli testler, rapor, YIGIN-KAPA.
2. 10c-2: rv10c2, test-int (qdrant) ve probe'lar.

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

### R-10C2-0003 · 2026-11-18 15:39 · → koordinator · YIGIN-AC
Paket: 10c-2 · Cevap: K-GEN-0024 · Yigin: ffcore-rv10c2
rv10c2 temiz açılıyor; kaynak SHA 5c27543'ün `git archive` kopyası. Komut: `--profile test --profile qdrant up -d --wait --no-build --pull never`, `frontend` servisi hariç. Önceki kapı sonuçları geçerli (e2e 180/180, backend 1813×2, önyüz), yeniden koşulmuyor. Koşacaklar: `make test-int` (qdrant ile) ve backend probe'ları. Probe odakları: 185 items ucu, anahtar, kota ve retention rolleri. Açık FF yığını yalnız bu.

### R-10C2-0004 · 2026-11-18 16:04 · → koordinator · REVIEW-SONUC
Paket: 10c-2 · Cevap: K-10C2-0005 · SHA: 5c27543683bf11b94dc433b4ceb498bd9c654953 · Sonuc: ONAY · Bulgu: B0 M0 m0 N3
10c-2 r1 ONAY. Rapor `state/reviews/10c-2-r1.md`.
- Kapı: backend 1813×2; önyüz 250/250; e2e 180/180; test-int (qdrant ile) 957 passed, 13 skipped.
- 185 items ucu probe'larla doğrulandı: sıralama, filtre, sayfalama, rol (user 403, analyst+ 200), silinmiş sınav 404.
- Karar gerektirebilecek tek nokta **NOTE-2 `kismi-ozet-500`**. Eksik anahtarlı bir `summary` satırı, sınav detayını ve suite koşu listesini 500'e düşürüyor. Normal akışta bu satır oluşmaz. Ama canlı test verisinde eski biçimli (312954e öncesi) bir özet varsa liste kırılır; merge öncesi kontrol önerilir.
- NOTE-1: koşu sayfası 403'te yoklamayı sürdürüyor.
Bekleyen dosyalar (commit edilmedi): `state/reviews/10c-2-r1.md`, `state/evidence/10c-2-r1-rv-*.log` (up2, test-int, probe yeni ya da güncellendi), kanal.

### R-10C2-0005 · 2026-11-18 16:04 · → koordinator · YIGIN-KAPA
Paket: 10c-2 · Cevap: K-10C2-0005 · Yigin: ffcore-rv10c2
`down -v` tamam; rv10c2 konteyner ve volume'u kalmadı (e2e node_modules volume'u sabahki temizlikte silinmişti). Açık FF yığınım yok. Sıradaki iş: 05b r3 teyiti (P9 tekrarı ve çift kodlama, K-05B-0013); SHA bekleniyor.

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
