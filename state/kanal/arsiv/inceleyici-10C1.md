# Arşiv: inceleyici · 10C1

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-10C1-0001 · 2026-11-16 11:05 · → koordinator · ACK
Paket: 10c-1   Cevap: K-10C1-0004
REVIEW-ISTEK alındı; lease `ffcore-inceleyici-10c1` ACTIVE (önceki `ffcore-inceleyici-09-2-teyit` RETIRED).
Tam SHA 2ac405197efc01463beb75500ecf184fa53095ab yerel commit nesnesi olarak doğrulandı; delta ff142a5..2ac4051 71 dosya, frontend/** + docs dışında dosya yok (backend dokunulmadı).
r1 tam tur: detached worktree `.worktrees/review-10c1-r1`, yığın `review10c1` (18320/13320, `.env.test`, `--pull never`, `0.0.0-10c1` imajları); yığın açmadan önce ayrı YIGIN-AC. Kontrol listesi 10 madde + güvenlik turu; rapor `state/reviews/10c-1-r1.md`.

### R-10C1-0002 · 2026-11-16 11:20 · → koordinator · YIGIN-AC
Paket: 10c-1 r1   Cevap: K-10C1-0004
(1) Statik kapılar: `docker run --rm --network none` `node:20.19.5-alpine`, worktree `.worktrees/review-10c1-r1` (2ac4051) + `ffcore-10a-nm` volume'u (yalnız okuma amaçlı; install yok): lint, typecheck, check:api, Vitest.
(2) Yığın `review10c1`: `-p review10c1 --env-file .env.test --profile test`, BACKEND_PORT 18320 / FRONTEND_PORT 13320, `FFCORE_VERSION=0.0.0-10c1`, `up -d --wait --no-build --pull never`; seed-prompts + create-superadmin; e2e `--profile e2e run --rm e2e` (`review10c1_e2e_node_modules` ağsız `ffcore-10a-nm` kopyası, `npx playwright test`, npm ci yok): 10c1 22 + tam 159 + probe'lar (SSE kopuş, bozuk summary). Açık başka FF yığını yok (`docker compose ls`: yalnız airflow_project_dev, FF dışı).
Kapanış `down -v --remove-orphans` + YIGIN-KAPA.

### R-10C1-0003 · 2026-11-16 11:50 · → koordinator · REVIEW-SONUC
Paket: 10c-1 r1   Cevap: K-10C1-0004
İncelenen tam SHA: 2ac405197efc01463beb75500ecf184fa53095ab. **Karar: DEGISIKLIK.** Rapor: state/reviews/10c-1-r1.md.
BLOCKER 0 · **MAJOR 1** · MINOR 3 · NOTE 8 · MAJOR sınıfları: `sse-sessiz-kopus` (yeni, r1).
- MAJOR-1 `sse-sessiz-kopus`: `lib/eval-stream.ts:42` `reader.read()` zaman aşımsız; yarı açık bağlantıda akış asılı kalır. Canlı probe: bekleyen sınavda backend `docker kill` → sayfa 190 s `streaming` + bayat "Queued", `lost`/GET yoklaması yok; iptal sonrası backend `cancelled` (psql), sayfa ~95 s sonra hâlâ "Running". Öneri A: deneme başına hareketsizlik bekçisi (~3×2 s progress aralığı) → mevcut yeniden açma/`lost` yolu; Vitest sahte zamanlayıcı testi. Kapanan/500 akış ve bilinmeyen olay doğru (probe P2/P2b).
- MINOR-1 tr `outcomes.not_retrieved` "Aranamadı" anlam değiştiriyor; MINOR-2 compare ekranı scorer/outcome kodlarını çevirmeden gösteriyor; MINOR-3 read e2e yalnız superadmin-read, kapı paneli axe testte yok (probe ile davranış doğru).
- İşçi notları: Langfuse UI bağlantısı yok → kabul, FOLLOWUP adayı (tek Langfuse UI adresi değeri; koşu/suite/sınav bağlantıları, plan/10 "Langfuse'ta aç"). Kabul 1 fake-llm + from-run → kabul kriterini karşılıyor (NOTE-6). Ayrıca FOLLOWUP adayı: 06a `lib/sse.ts:110` aynı bekçisiz okuma (NOTE-7).
- Doğrulanan: delta yalnız frontend+docs (backend 0); lint/typecheck/check:api 0, Vitest 180/180, e2e 10c1 22/22, tam e2e 159/159; özet fail-loud (bozuk 4 şekil → "could not be read" + alan yolu); read 403 `read_only_access`, force 403/422 kodları; XSS yok; axe iki tema temiz; klavyeyle suite oluşturma. Bu sürümde atanabilir rol yalnız analyst/admin (developer/user `role_reserved`), "yetkiniz yok" yalnız Vitest'le kanıtlı (NOTE-4).
Kanıt: state/evidence/10c-1-r1-rv-*.log (+ probe spec kopyası). Kod değişikliği ve commit yok.

### R-10C1-0004 · 2026-11-16 11:51 · → koordinator · YIGIN-KAPA
Paket: 10c-1 r1   Cevap: R-10C1-0002
`review10c1` `down -v --remove-orphans` exit 0; `review10c1_e2e_node_modules` silindi; konteyner 0, volume 0 (`state/evidence/10c-1-r1-rv-down.log`). Açık FF yığını yok (`docker compose ls`: yalnız airflow_project_dev). `ffcore-10a-nm` yalnız okundu. İnceleme worktree'si `.worktrees/review-10c1-r1` kaldırıldı (--force yok; ekran görüntüleri önce geri alındı, HEAD 2ac4051 değişmedi). `ffcore/*:0.0.0-10c1` imajlarına dokunulmadı.

### R-10C1-0005 · 2026-11-16 13:49 · → koordinator · ACK
Paket: 10c-1 · Cevap: K-10C1-0009
REVIEW-ISTEK r2 alındı; lease `ffcore-inceleyici-10c1` ACTIVE. Tam SHA b28cdc1c19b7cee4582c0d5740b0fba14b02e736 yerel commit nesnesi; delta 2ac4051..b28cdc1 21 commit, 29 dosya (backend: runs.py, eval.py + testler). Detached worktree `.worktrees/review-10c1-r2`; 8 kontrol maddesi + tur kuralı (`sse-sessiz-kopus`). Rapor `state/reviews/10c-1-r2.md`.

### R-10C1-0006 · 2026-11-16 13:50 · → koordinator · YIGIN-AC
Paket: 10c-1 · Cevap: K-10C1-0009 · Yigin: review10c1
(1) Statik: `docker run --rm --network none node:20.19.5-alpine` + `ffcore-10a-nm` (yalnız okuma, install yok): lint, typecheck, check:api, Vitest. (2) `review10c1` (`--env-file .env.test`, 18320/13320, `FFCORE_VERSION=0.0.0-10c1`, `up -d --wait --no-build --pull never`, `--profile test`): tools `make lint`, `make test` DEPLOY_PROFILE airgap + llmaas, hedefli test-int (06a runs stream, 09); seed-prompts + create-superadmin; e2e `--profile e2e run --rm e2e` (`review10c1_e2e_node_modules` ağsız `ffcore-10a-nm` kopyası): 10c1 + tam e2e + probe'lar (SIGKILL `docker kill review10c1-backend-1`, proxy üzerinden gzip isteyen canlı akış 09 + 06a). Açık başka FF yığını yok (`docker compose ls`: yalnız airflow_project_dev). Kapanış `down -v --remove-orphans` + YIGIN-KAPA.

### R-10C1-0007 · 2026-11-16 14:38 · → koordinator · REVIEW-SONUC
Paket: 10c-1 · Cevap: K-10C1-0009 · SHA: b28cdc1c19b7cee4582c0d5740b0fba14b02e736 · Sonuc: ONAY · Bulgu: B0 M0 m1 N6
Rapor: state/reviews/10c-1-r2.md. MAJOR yok; r1 MAJOR-1 `sse-sessiz-kopus` kapandı (tekrar yok).
- SIGKILL: Q1 (25 s kapalı) reconnecting kill'den ~6,9 s sonra, durum "Running" (bayat yok), lost +40 s, GET ile "Cancelled" 6,4 s; Q2 (hemen başlatma) reconnecting → streaming +16,6 s → done. Proxy+gzip: sınav akışı 2 s'de bir ayrı parça, 06a run POST olay olay; başlıklar no-transform + X-Accel-Buffering, enc=null.
- MINOR-1: `runs.py:113` birleşimi çağıranın `Cache-Control`'ünde no-transform'u sessizce düşürür, küçük harf anahtar çift başlık üretir (bugün çağıran yok). Öneri A: harf duyarsız birleşim + no-transform'suz Cache-Control'ü reddet + iki test; merge'ü bekletmez, FOLLOWUP da olabilir.
- NOTE: facade akışları no-transform'suz ve degisiklikler.md "every event stream" fazla geniş (FOLLOWUP adayı); lost sonrası yeniden deneme yok (K-10C1-0007 ile uyumlu); exam_stack başlık iddiası RUN_EVAL_STACK'le atlanıyor (test_09_api kapsıyor); işçi test-int logunda komut yok.
- Kapılar: lint/typecheck/check:api 0, Vitest 195/195, backend make lint 0, make test 1801 airgap + 1801 llmaas, test-int 30+8 atlandı ve ortak fixture tüketicileri 138/138, e2e 10c1 26/26, tam 163/163. İmaj HEAD ile eşleşti (172 py fark 0).
Kanıt: state/evidence/10c-1-r2-rv-*.log (+ probe spec kopyası; q1-run1-invalid probe hatası, açıklaması raporda). Kod değişikliği ve commit yok.

### R-10C1-0008 · 2026-11-16 14:38 · → koordinator · YIGIN-KAPA
Paket: 10c-1 · Cevap: R-10C1-0006 · Yigin: review10c1
`down -v --remove-orphans` exit 0; `review10c1_e2e_node_modules` silindi; konteyner 0, volume 0 (`state/evidence/10c-1-r2-rv-down.log`). Açık FF yığını yok (`docker compose ls`: yalnız airflow_project_dev). `ffcore-10a-nm` yalnız okundu; `ffcore/*:0.0.0-10c1` imajlarına dokunulmadı. e2e'nin yazdığı `docs/images` geri alındı, worktree `.worktrees/review-10c1-r2` kaldırıldı (HEAD b28cdc1 değişmedi).
