# PR: fix/04a-worker-ready

**Paket:** fix/04a-worker-ready (FOLLOWUP-97, karar A, GOREV K-04aWR-0001) · **Sınıf:** [A] · **Branch:** fix/04a-worker-ready · **Baz commit:** e9583df (main; 28d7a5f + state commit'leri)

## Plan (kodlamadan önce)

1. **Bulunan semboller ve dosyalar** (worktree'de okundu):
   - `backend/ffcore/knowledge/convert/workers.py`: `_worker_main(target, conn, limits)` önce `os.setsid`, `_resolve(target)` (modülü içe aktarır), `_apply_memory_limit`, sonra `conn.recv()` döngüsü. `_Worker.__init__` spawn edip hemen döner. `BoundedPool._dispatch` işçiyi gerekince yaratır, `started = time.time()` alır, `_one(worker, path, started)`; `_one` `send((path, started + timeout))` + `conn.poll(self.timeout)`. `PersistentPool.convert` aynı `_one`'ı `time.time()` ile çağırır. **Sonuç:** taze işçide dosya saati spawn + `ffcore` içe aktarımı + `_resolve` süresini de sayıyor (A-06a-0031 çıkarımı; ölçülmedi, kırmızı test bunu kanıtlayacak).
   - `knowledge/ingest.py:104-129`: `_pools[(timeout, limits)]` → `PersistentPool(timeout=settings.convert_timeout_seconds, ...)`; `result.status == TIMEOUT` → belge `timeout` (düz reindex yeniden denemez); diğer hata durumları → `failed`, `document.error = "<error_code>: <mesaj>"`.
   - `core/config.py:97` `convert_timeout_seconds=600`; `deploy/docker-compose.yml:241` `CONVERT_TIMEOUT_SECONDS`; `.env.example:100`.
   - `BoundedPool` üretimde kullanılmıyor (yalnız `test_04a_9d`); üretim yolu `PersistentPool`.
   - **Model yükleme yeri:** `convert/office.py:31` Docling ve `convert/ocr.py:38` PaddleOCR fonksiyon içinde, ilk dönüşümde içe aktarılır/yüklenir; `pipeline.py` modül düzeyinde model yüklemez. Yani `_resolve` sonrası `ready` **spawn + içe aktarım** süresini dosya saatinden çıkarır, **model yüklemesini çıkarmaz** (bkz. KARAR-GEREK A-04awr-0004).
   - Testler: `tests/unit/test_04a_convert.py:191` (9d, `BoundedPool`, timeout 2) ve `:208` (persistent pool, timeout 2); hedef `tests/unit/_convert_targets.py:target` (`sleep` dosyası 600 s uyur). `test_04a_review_r1_limits.py` `PersistentPool(60, ...)` iki testi (bellek/CPU sınırı) etkilenir ama imza additive kalır.
2. **Kapsam:** işçi `ready` el sıkışması; dosya deadline'ı `ready`'den sonra; kodlu açılış sınırı; iki flaky testin olaya dayandırılması; yeni kırmızı testler; docs tek paragraf. **Kapsam dışı:** model ısıtma (KARAR-GEREK'e bağlı), havuz boyutu, retry politikası.
3. **Değişecek dosyalar:**
   - `knowledge/convert/workers.py`: `_worker_main` `_resolve` + bellek sınırı sonrası tek `conn.send(READY)`; `_Worker.wait_ready(timeout)` (poll + recv; EOF → `worker_died`); `BoundedPool`/`PersistentPool` yeni isteğe bağlı `start_timeout` parametresi (varsayılan `DEFAULT_START_TIMEOUT = 60`); `_one` taze işçide önce `wait_ready`, deadline `ready`'den sonra `time.time() + timeout` ile hesaplanır. Aşım: işçi öldürülür, sonuç `ConversionResult(status=ERROR, error_code="convert_worker_start_timeout", warnings=["worker not ready in N s"])`, log `convert_worker_start_timeout pool=... seconds=...`; havuz sonraki dosyada taze işçi açar.
   - `knowledge/ingest.py`: `PersistentPool(..., start_timeout=settings.convert_worker_start_timeout_seconds)`, havuz anahtarına eklenir.
   - `core/config.py`: `convert_worker_start_timeout_seconds: int = Field(default=60, gt=0)` **(touch-zone eki gerekiyor; WORK_QUEUE satırında yok)**.
   - `.env.example` + `deploy/docker-compose.yml`: `CONVERT_WORKER_START_TIMEOUT_SECONDS` bir satır, `CONVERT_TIMEOUT_SECONDS` yanında **(touch-zone eki; istenmezse yalnız config varsayılanı kalır, compose'da ayarlanamaz)**.
   - `tests/unit/_convert_targets.py` + yeni `tests/unit/_convert_targets_slow_start.py` (içe aktarımda `FFCORE_TEST_START_DELAY` kadar uyur; spawn edilen çocuk ortamı miras alır).
   - `tests/unit/test_04a_convert.py`: iki mevcut test + yeni testler.
   - `docs/bilgi-tabani.md`: 36. satırdaki paragrafa açılış sınırı cümlesi.
4. **Sözleşme / yapılandırma / profil:** CONTRACTS'a dokunmaz (C5/C6 değil). Yeni ayar additive, eski davranışta (`CONVERT_TIMEOUT_SECONDS`) anlam değişikliği: dosya süresi artık yalnız dosyanın kendisi (açılış hariç). Profil farkı yok; testler iki profilde.
5. **Kabul kriteri → test:**
   | # | Kriter | Test |
   |---|---|---|
   | 1 | Taze işçinin açılışı dosya süresine sayılmaz (açılış 3 s, dosya timeout 2 s → CONVERTED); eski kodda TIMEOUT (kırmızı) | `test_04awr_1_slow_start_not_counted_in_file_timeout` (PersistentPool ve BoundedPool parametrik) |
   | 2 | Açılış sınırı aşımı kodlu sonuç, işçi öldürülür, sonraki dosya taze işçiyle | `test_04awr_2_worker_start_timeout_is_coded_and_replaced` |
   | 3 | Açılışta ölen işçi `worker_died` (asılı kalmaz) | `test_04awr_3_worker_dying_before_ready_is_worker_died` |
   | 4 | Mevcut iki test olaya dayalı (hızlı dosya açılışla yarışmaz; duvar saati yalnız geniş asılı kalma tavanı) | `test_04a_9d_*`, `test_04a_persistent_pool_*` (adlar korunur) |
   | 5 | Ayar ingest havuzuna geçer | `test_04awr_5_ingest_pool_uses_start_timeout_setting` |
   | 6 | Yük altında 10 tekrar yeşil | kapı: iki test + 1-3, CPU yükü altında `pytest --count` yerine 10 döngü (betik scratchpad'de, çıktı tee ile dosyaya) |
6. **Migration:** yok.
7. **Geri alma:** tek commit revert; ayar kaldırılırsa eski davranış.
8. **Durma koşulları:** `ready` mesajı bellek sınırı (RLIMIT_AS) sonrası gönderimde sorun çıkarırsa; 04a r1 sınır testleri kırılırsa; açılış süresi Windows host'ta (spawn) ölçülemez derecede oynarsa → koordinatöre.
9. **Felsefe kontrolü:**
   - ARCH-07: her ingest'e değer (CPU profilinde ilk belge ve yük altında flake); kalıcı karmaşıklık ~25 satır, tek el sıkışma.
   - ARCH-09: multiprocessing/arq hazır olma sinyali sunmuyor; Pipe üstünde tek mesaj en küçük çözüm.
   - ARCH-10/06: sessiz davranış yok; açılış aşımı ayrı kod + log, sessiz bekleme yok (sınır zorunlu, varsayılan görünür).

## Varsayımlar
1. Açılış aşımı `status=error` + `error_code=convert_worker_start_timeout` (mevcut `convert_cpu_limit`/`worker_died` kalıbı); belge `failed`, `timeout` değil (dosyanın suçu değil). GOREV'deki "WORKER_START_TIMEOUT durum kodu" bu `error_code` olarak okundu; yeni `status` değeri eklenmez (belge durum kümesi değişmez).
2. `on_result` süresi açılışı da içerir (gözlem; davranış değil).

## Plan onayı
K-04aWR-0002: PLANNED onaylı; touch-zone eki (core/config.py, .env.example, deploy/docker-compose.yml birer satır) kabul; KARAR-GEREK **A** (ready yalnız `_resolve` sonrası; B warm kancası reddedildi, 80/20). `.env.test` değişmedi.

## Sonuç
**HEAD:** `3cecab486a37e9c68b1827f159f8bec95f05109d` · baz `e9583df` (main) · 1 commit · push yok · ağaç temiz.

## Değişen dosyalar
- `backend/ffcore/knowledge/convert/workers.py`: `READY` mesajı (`_worker_main`, `_resolve` + bellek sınırı sonrası); `_Worker.wait_ready(timeout)`; `BoundedPool`/`PersistentPool` isteğe bağlı `start_timeout` (varsayılan `DEFAULT_START_TIMEOUT = 60`); `_one` önce hazır olmayı bekler, dosya deadline'ı `ready` sonrası hesaplanır; aşımda `_start_timeout` (log `convert_worker_start_timeout`, işçi öldürülür, `status=error`, `error_code=convert_worker_start_timeout`).
- `backend/ffcore/knowledge/ingest.py`: havuz `start_timeout=settings.convert_worker_start_timeout_seconds`, havuz anahtarında.
- `backend/ffcore/core/config.py`: `convert_worker_start_timeout_seconds = 60` (gt=0).
- `.env.example`, `deploy/docker-compose.yml`: `CONVERT_WORKER_START_TIMEOUT_SECONDS` (60).
- `backend/tests/unit/_convert_targets_slow_start.py` (yeni test hedefi: içe aktarımda `FFCORE_TEST_START_DELAY` kadar uyur), `backend/tests/unit/test_04a_convert.py` (yeni testler + iki mevcut teste olay açıklaması).
- `docs/bilgi-tabani.md`: dönüşüm paragrafına açılış sınırı ve model yükleme sınırı.

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Açılış dosya süresine sayılmaz | `test_04awr_1_slow_start_not_counted_in_file_timeout[persistent\|bounded]` | geçti; **kırmızı kanıtı:** eski kodda aynı senaryo (`FFCORE_TEST_START_DELAY=3`, timeout 2) → `timeout convert_timeout` (`red-old-timeout.log`); testin kendisi eski kodda `start_timeout` parametresi yok diye düştü (`red.log`) |
| 2 | Açılış sınırı aşımı kodlu, işçi öldürülür, sonraki dosya taze işçiyle | `test_04awr_2_worker_start_timeout_is_coded_and_replaced` | geçti (eski kodda düştü) |
| 3 | `ready` öncesi ölen işçi `worker_died`, asılı kalmaz | `test_04awr_3_worker_dying_before_ready_is_worker_died` | geçti (eski kodda yalnız imza nedeniyle düştü; davranış eski kodda da `worker_died` idi, koruma testi) |
| 4 | İki flaky test olaya dayalı | `test_04a_9d_timeout_kills_worker_and_continues`, `test_04a_persistent_pool_reuses_its_process_and_replaces_it_after_timeout` | geçti; test kodu değişmedi (yalnız açıklama): 2 s artık yalnız dosyayı ölçer, spawn `ready` ile ayrıldı |
| 5 | Ayar ingest havuzuna geçer | `test_04awr_5_ingest_pool_uses_start_timeout_setting` | geçti (eski kodda düştü) |
| 6 | Yük altında 10 tekrar | 1-4'ün 7 testi, 14 CPU yakıcı (nproc 7 × 2) altında 10 döngü | **10/10 yeşil** (`load-10c.log`) |

## Çalıştırılan komutlar
Tümü `MSYS_NO_PATHCONV=1 FFCORE_VERSION=0.0.0-04awr docker compose -p ffcore-04awr --env-file .env.test run --rm --no-deps tools ...` (imaj `ffcore/tools:0.0.0-main` yeniden etiketlendi; bağımlılık değişmedi, kod `/work` bağlamasından). Tam çıktılar `state/pr/04a-worker-ready-kapilar/`.
| Komut | Ortam | Exit | Süre / sonuç |
|---|---|---|---|
| kırmızı: yeni testler eski kodda | | 1 | 5 failed, 2 passed (`red.log`) |
| kırmızı: eski kod + 3 s açılış | | 0 | `OLD_CODE_RESULT timeout convert_timeout` |
| `pytest test_04a_convert.py test_04a_review_r1_limits.py` | | 0 | 40 passed, 62 s |
| `make lint` | | 0 | ruff check + format (291 dosya) (`gates.log`, son hali `lint2.log`) |
| `make test` | `DEPLOY_PROFILE=llmaas` | 0 | 649 passed, 180 s |
| `make test` | `DEPLOY_PROFILE=airgap` | 0 | 649 passed, 163 s |
| yük 10 tekrar (ilk) | 14 CPU yakıcı | — | 9/10; düşen `test_04awr_2` (ikinci yarıda taze işçiye de 2 s açılış sınırı veriyordum, yükte spawn > 2 s; `load-10b.log`) → test düzeltildi: ikinci yarıda `pool.start_timeout = 120` |
| yük 10 tekrar (düzeltme sonrası) | 14 CPU yakıcı | 0 | **10/10**, 7 passed her koşuda (`load-10c.log`) |
| `docker compose --env-file .env.test config --quiet` | | 0 | yeni değişken 5 serviste |
Not: `make test` iki profil, `test_04awr_2` düzeltmesinden **önce** koştu; düzeltme yalnız bu testin ikinci yarısındaki sınır (ürün kodu değişmedi); düzeltilmiş test yük döngüsünde 10 kez ve son lint'te geçti. Yığın açılmadı; test-int/smoke koşulmadı (ürün davranışı yalnız dönüşüm havuzu, birim testleri gerçek spawn ile).

## Varsayımlar ve sınırlar
1. (onaylı, K-04aWR-0002 A) `ready` yalnız `_resolve` + bellek sınırı sonrası; **Docling ve PaddleOCR ilk dönüşümde yüklenir, bu yükleme ilk belgenin dosya süresine sayılmaya devam eder** (ölçülen ~66 s, varsayılan 600 s). K-06a-0029'daki "ilk belgenin model yüklemesiyle kesilmesi de düzelir" cümlesi bu PR'la karşılanmaz; docs'ta açık yazılı.
2. Açılış aşımı `status=error` + `error_code=convert_worker_start_timeout` → belge `failed` (yeni status değeri yok).
3. Kök neden çıkarımı (A-06a-0031) artık ölçüldü: eski kodda 3 s açılış 2 s dosya süresini tüketip `timeout` üretiyor.
4. `on_result` süresi (BoundedPool) açılışı da içerir; davranış değil, gözlem.
5. Test hedefi `_convert_targets_slow_start.py` touch-zone'da adıyla yoktu; test yardımcısı olarak `tests/unit` altına eklendi.

## Kalan riskler
- Gerçek Docling/PaddleOCR'lı ilk belge süresi bu PR'da ölçülmedi (`-m models`, varsayılan kapıda yok).
- `DEFAULT_START_TIMEOUT` 60 s: konteynerde spawn + ffcore içe aktarımı yük altında saniyeler (ölçülmedi, yalnız 14 yakıcı altında 120 s sınırla sorunsuz).
