# Review followup-triage-1 r1 · FOLLOWUP 207, 201, 202, 203, 194, DRIFT-198
SHA: 292f2907d56486b1476644d194211b6ebfdde1d0 · Sonuc: ONAY · Bulgu: B0 M0 m1 N3

- **İncelenen tam SHA:** `292f2907d56486b1476644d194211b6ebfdde1d0`, main a60228d üstünde.
- **Delta** `a60228d..292f290`: 13 commit, 26 dosya, +598/−82. Test, kod ve docs commit'leri ayrı.
- **İstek:** K-TRJ-0003. Kararlar: KARARLAR "triage-1 plan kararları" (S-1..S-4).
- **Yöntem:**
  - Delta satır satır okundu.
  - `is_platform_target` taşındıktan sonra 05b çağıranları kontrol edildi.
  - Bir `@audited` uçta `authorize()` hatasını yutan, dönüştüren ya da stream içinde geç çağıran yer arandı. Bulunmadı: `runs.py`'de tek audited uç `give_feedback`, o da stream etmiyor. Facade uçları audited değil.
  - Hook kuralı yerelde 13 komut biçimiyle sınandı.
  - Yığın `ffcore-rv` (`--no-build --pull never`, `0.0.0-main`, test + qdrant profili) açıldı; kaynak `git archive` kopyası.
  - Testler: hedefli test-int, 20 tekrarlık kota koşusu, iki profilde `make lint` + `make test`, probe. Kapı adımları ayrık konteynerde (`compose run -d` + `docker wait`), çıktı `docker logs` ile dosyaya.
  - Tam test-int koşulmadı (ENV-209). Önyüz delta'da yok, önyüz kapısı koşulmadı.
- **Karar: ONAY.** Beş odak maddesinin hepsi kodda ve probe'da doğru. Tek MINOR bir belge metni (207, S-3 kapsamı); merge öncesi mi sonrası mı kararı koordinatörde.

## Testler
`HEAD=` satırlı loglar `state/evidence/followup-triage-1-r1-rv-*.log`.

| Koşu | Sonuç |
|---|---|
| Yığın (`-up.log`) | exit 0 |
| Hook testleri, host (`-hooks.log`) | 347 passed |
| Hedefli test-int, `RUN_QDRANT_TESTS=1` (`-test-int.log`): `test_trj_{194,202,203}*`, `test_06b_direct`, `test_04b_r3_upload_acl`, `test_06b2_external_agent`, `test_03a_{providers,nonmember_404,obo_scope,read_side,models}`, `test_03c_alerts`, `test_05a_tools_api`, `test_06a_agents`, `test_01_events`, `test_04a_api`, birim `test_trj_194_platform_targets`, `test_05b_platform_targets` | 440 passed, exit 0 |
| FOLLOWUP-201: kota testleri 20 kez (`-quota20.log`) | 20/20 pass (`test_06b_6_quota*`, koşu başına 2 test) |
| `make lint` + `make test`, llmaas (`-backend-llmaas.log`) | ruff temiz; 1989 passed, exit 0 |
| Aynı, airgap (`-backend-airgap.log`) | ruff temiz; 1989 passed, exit 0 |
| Probe (`-probe.log`) | 4 passed; sonuçlar aşağıda |
| `down -v` (`-down.log`) | konteyner ve volume kalmadı |

**İlk test-int denemesi kesildi, kod hatası değil.** İlk koşu (11:48, bağlı `compose run`) 12:04'te %81'de `error waiting for container` ile koptu. Tools konteyneri gitti, CLI asılı kaldı. O anda logda bir E ve bir F görünüyordu. Bu, ENV-209/173 ailesinden bir Docker CLI kopması. Aynı test kümesi ayrık konteynerde (`compose run -d` + `docker wait`) yeniden koşuldu ve 440/440 yeşil geçti. E ve F bu yüzden **kesinti** olarak sınıflandı. Yukarıdaki log ayrık koşunun logu.

## Kontrol listesi (K-TRJ-0003)

| # | Madde | Sonuç |
|---|---|---|
| 1 | **207: hook kuralı** | `check_compose` 13 biçimle sınandı: <br>• `up --build --pull never` ve `--pull=never` sessiz <br>• `--pull never`'sız `up --build` ve `--pull missing` PROSES-175 <br>• her `compose build` biçimi PROSES-175: `--pull=false`, `-f a -f b build`, `--profile x build`, `docker-compose build` <br>• `up --no-build --pull never` sessiz; çıplak `up -d` PROSES-175 <br>Testler: üç yığın sayımı `up --build`'de de çalışıyor; mesaj `up --build --pull never`'ı adıyla veriyor. `ENVIRONMENT_AND_COMMANDS.md` doğru. `ajanlarla-gelistirme.md` iki yerde eski kalmış (MINOR-1). `docker build` / `buildx` için NOTE-2'ye bakın. |
| 2 | **201: kota saati** | Üretim kodu değişmedi (delta'da `services/quota.py` yok). Test `quota.time`'ı yamalıyor. İkinci test, dakika sınırını bilerek geçince iki pencere oluştuğunu doğruluyor; yani yama gerçekten motorun okuduğu saate ulaşıyor. 20/20 yeşil. |
| 3 | **202: admin tekil uçlar** | Tek kural `_manages_acl`; yalnız GET, PATCH ve DELETE (`_managed_document`) kullanıyor, liste, arama ve ingest raporu `acl_for` ile kalıyor. <br>Probe, iki sürücüde de aynı sonuç: <br>• A1: admin GET 200, gövdede içerik yok (yalnız meta) <br>• A2: admin aramada 0 sonuç alıyor, analyst 1 <br>• A3: read-only admin GET 200 <br>• A4: read-only admin ACL PATCH'i 403 `read_only_access` <br>• A7: admin ACL'i `analyst` rolüne açınca peer aramada buluyor (vektör deposuna ulaştı) <br>• A8: admin DELETE 204; analyst aramada 0, sonra GET 404 <br>İşçi testleri: peer GET, PATCH ve DELETE için 404 `document_not_found`; süperadmin read 200 ama DELETE 403, edit DELETE 204; listede admin de belgeyi görmüyor. |
| 4 | **203: bir red, bir `denied`** | Kod: `authorize()` audited uç içinde satır yazmıyor; sebebini `error.audit_detail` ile sarmalayıcıya veriyor. Sarmalayıcı `after=detail` ile tek satır yazıyor. `resource_type` ve `resource_id` kaynağın kendisi. 404 gizli proje de `denied` sayılıyor (`or detail`). <br>Probe: <br>• A6 analyst ACL PATCH: tek satır, `(update_document, document, insufficient_role)` <br>• A4 read-only, route düzeyi: tek satır, `(update_document, route, read_only_access)` <br>• A5 yabancı, gizli proje: tek satır, `route` 404 `project_not_found`, `after.reason=not_member` korunuyor <br>06b2 ve 04b_r3 testleri `after.code` ve `min_role`'ü doğruluyor. Audit tablosu append-only kaldı: probe'un DELETE denemesi `InsufficientPrivilege` ile reddedildi. |
| 5 | **194: platform hedefi** | `is_platform_target` tek yerde (`core/egress.py`); `mcp_client` aynı adı yeniden dışa veriyor, 05b birim testi yeşil. Beş yüzeyin hepsi bağlı: sağlayıcı kayıt ve güncelleme (`refuse_platform_urls`), `test_connection`, `litellm_reconcile`, alert webhook kayıt ve güncelleme (proje ve tenant), bildirim varsayılan webhook'u ve `post_webhook` çağrı anı. İşçi testleri üç URL biçimini, `ALLOWED_INTERNAL_HOSTS` boşken ve `backend`'li hâliyle sınıyor. <br>Probe (`ALLOWED_INTERNAL_HOSTS`'a `backend` ekli): <br>• platform sayılıyor: `BACKEND:9999`, `backend.`, `https://backend`, `evil.test@backend:8000` (userinfo hilesi) <br>• platform sayılmıyor, doğru: `backend:8000@evil.test` (host `evil.test`) <br>• `0.0.0.0:8000`, `127.1:8000`, `2130706433:8000` ve konteyner adı `ffcore-rv-backend-1:8000` platform sayılmıyor ama egress `not_allowlisted` ile reddediyor. Operatör bu adları allowlist'e yazmadıkça kapalı; bilgi notu, bulgu değil. <br>• API: `backend.:8000`, `BACKEND:8000` ve `evil.test@backend:8000` kayıtta 400 `endpoint_is_platform`; mesaj URL'yi geri yazmıyor. <br>• qdrant sürücüsünün `url` alanı için NOTE-1'e bakın. |
| 6 | **198: plan metni** | plan/04 satır 6 ve PLAN 209/233, kararda yazıldığı gibi düzeltildi; PLAN 89 ve 273'e dokunulmadı (DOC-18). Satır 5 için NOTE-3'e bakın. |

## Bulgular

### MINOR-1 · `kural-metni-eski` · docs/takim/ajanlarla-gelistirme.md:631 ve :507
S-3 bu dosyadaki kural metninin de düzeltilmesini istiyor. 6.3 bölümü (satır 423) düzeldi, ama aynı dosyada iki yer eski kuralı hâlâ geçerli kural olarak veriyor:
- **Satır 631, hook tablosu, PROSES-175 satırı:** "`compose build` yalnız `--pull=false`; `up --build` yok". Yeni kural bunun tersi: `up --build --pull never` kabul, her `compose build` red. Tablodaki "geçen örnek" ve "reddedilen örnek" sütunları da buna göre değişmeli (`up --build` artık reddedilen değil).
- **Satır 507, "Ders" paragrafı:** "Kural: … gerçekten derlenecekse `build --pull=false`" ve kapı betiği için `docker compose build --pull=false`. Ders tarihî bir kayıt olarak kalabilir, ama "Kural:" cümlesi bugünkü kuralı söylemeli ya da 207 ile değiştiğini belirtmeli. Kapı betiği cümlesi ayrıca koordinatörün `gate09.sh`'ının bu kurala uyup uymadığı sorusunu doğuruyor (bu PR'ın dışında).
- **Etki:** bu belgeyi okuyan bir işçi, hook'un artık reddettiği komutu öğrenir.

### NOTE-1 · qdrant sağlayıcısının `url` alanı kayıt kuralına girmiyor
- `URL_FIELDS = ("base_url", "api_base")`. qdrant sürücüsünün adres alanı `url`. Probe: `{"url": "http://backend:8000"}` kaydı **201** döndü, `/providers/test` ise `endpoint_is_platform` dedi.
- Bugün zararsız: vektör deposu `settings.qdrant_url`'u kullanıyor, sağlayıcı satırının `url`'ünü kullanan bir çağrı yolu bulamadım; tek çağrı `test_connection`, o da reddediyor.
- Ama `URL_FIELDS`'ın docstring'i "sağlayıcının adresini tutan alanlar" diyor ve kayıtla test arasında tutarsızlık var. Öneri: `url`'ü listeye eklemek ya da neden dışarıda olduğunu yazmak. Karar koordinatörde; kararın "sağlayıcı base_url" ifadesi `url`'ü açıkça kapsamıyor.

### NOTE-2 · hook çıplak `docker build` / `docker buildx build`'i yakalamıyor
- `check_compose` yalnız compose alt komutlarına bakıyor. `docker build -t x .` ve `docker buildx build` sessiz geçiyor (probe).
- Bu değişiklikten önce de böyleydi, yani regresyon değil. BuildKit metadata sorunu (5 Kasım) bu komutlar için de geçerli. Kararın "her biçimde standalone `build`" ifadesi compose dışını kapsıyor mu, koordinatörün yorumu.

### NOTE-3 · plan/04 satır 5 hâlâ DuckDB göçünü 04b'ye bağlıyor
- 04a paragrafı: "`KnowledgeStore` bağdaştırıcısı DuckDB + silver dosyalarını sarar … (tam göç 04b)".
- Satır 6 artık göçü anmıyor ve "DuckDB yok; DEBT-10 kapalı" diyor. Karar yalnız satır 6'yı istiyordu, kapsam doğru uygulanmış; ama iki satır birbirini yalanlıyor.
- 04a satırı tarihî kapsamı anlatıyorsa DOC-18 gereği dokunulmayabilir; değilse "tam göç 04b" ifadesi DRIFT-198'e bağlanabilir.

## Bekleyen dosyalar (commit edilmedi)
- `state/reviews/followup-triage-1-r1.md`
- `state/evidence/followup-triage-1-r1-rv-{up,hooks,test-int,quota20,backend-llmaas,backend-airgap,probe,down}.log`
- `state/kanal/inceleyici.md`
