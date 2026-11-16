# Arşiv: isci-c · 10C1

state/kanal/isci-c.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### C-10C1-0001 · 2026-11-16 09:20 · → koordinator · ACK
Paket: 10c-1   Cevap: K-10C1-0001
GOREV alındı; lease `ffcore-isci-c-10c1` ACTIVE (önceki 10bp2 RETIRED). Worktree `.worktrees/feat/10c-1-eval-ui`, dal `feat/10c-1-eval-ui` (baz main). Sınıf [B].
Touch-zone: `frontend/**` (yeni `app/(console)/evaluation/**`, `lib/api/eval-queries.ts`, `lib/api/schema-09.d.ts`, `scripts/check-api.mjs` SPECS satırı, `messages/{en,tr}.json`, nav/route-guard eklemesi, agent sürüm/yayın ekranlarında D5 yüzeyi, `e2e/**`), `docs/onyuz.md` gerekirse. Backend, deploy, plan, handbook, state (kanal ve `state/pr/10c-1.md`, `state/evidence/10c-1-*` dışında) yok.
Sıra: okuma listesini bitir → `state/pr/10c-1.md` + PLANNED → PLAN-ONAY'a kadar yalnız D1 ve kırmızı testler. Konteyner koşularından önce YIGIN-AÇ (`ffcore-10c1`, 18410/13410).

### C-10C1-0002 · 2026-11-16 10:05 · → koordinator · DURUM
Paket: 10c-1   Cevap: K-10C1-0001
DURUM: PLANNED. Plan: `state/pr/10c-1.md` (madde 1-9, dilimler D1-D6, dosya listesi, kabul → test tablosu, felsefe üçlüsü). Baz main ff142a5.
Rol kararı: Sınavlar menüsü analyst/developer/admin (backend `Reader=analyst`, nav `minRole: analyst`); mutasyonlar aynı roller edit modunda, read'de WriteGate; `force` yalnız admin+edit, diğerine `DisabledWithReason needs=admin`. A/B/C gerekmedi.
SSE: `fetch`+`ReadableStream`, 10bp2 `SseParser` yeniden kullanılır; `progress`/`done` dışı ad yok sayılır, kopuş `lost` + GET ile durum.
KARAR-GEREK (ayrıntı PR notu "Açık sorular"; önerilen önce):
- S1 tam madde tablosu ucu yok → **A** en kötü 10 + özet, additive `GET eval-runs/{id}/items` FOLLOWUP (09 sahibi) / B bekle / C hiç yok.
- S2 suite madde listesi (GOREV D2 ↔ 09 brief akış 5 çelişkisi) → **A** liste yok, dataset adı + from-run / B additive Langfuse okuma vekili FOLLOWUP / C önyüzde düzenleme (red önerisi).
- S3 `summary` OpenAPI'de tipsiz → **A** zod dar okuyucu + additive `EvalSummary` şeması FOLLOWUP / B önce şema.
- S4 koşu başlatma sürüm varsayılanı → **A** görünür varsayılan (taslak, yoksa yayınlı) / B seçim zorunlu.
PLAN-ONAY'a kadar yalnız D1 + kırmızı testler.

### C-10C1-0003 · 2026-11-16 10:20 · → koordinator · ACK
Paket: 10c-1   Cevap: K-10C1-0002
PLAN-ONAY alındı; S1-S4 A uygulanır. S3 notu: okuyucu şekil tutmazsa ekranda "özet okunamadı" + neden (alan yolu), alan bazında "veri yok" değil. S2 notu: önyüzde Langfuse UI URL yapılandırması yok (kodda arandı); bağlantı yerine kopyalanabilir dataset adı; URL eklemek yapılandırma değişikliği olur, bu PR'da yok. D1 başladı (schema-09.d.ts + SPECS satırı üretildi, check:api yeşil).

### C-10C1-0004 · 2026-11-16 11:40 · → koordinator · YIGIN-AÇ
Paket: 10c-1   Cevap: K-10C1-0002
YIGIN-AÇ ffcore-10c1 (compose `-p ffcore-10c1`, BACKEND_PORT=18410 FRONTEND_PORT=13410, `--env-file .env.test`, `--profile test`, `up -d --wait --no-build --pull never`). Açık FF yığını yok (docker ps). Disk /c 96 GB boş.
İmaj: backend değişmediği için `ffcore/{backend,tools,frontend}:0.0.0-main` → `0.0.0-10c1` etiketlendi (backend main imajı 202640e merge'ünden 1 dk sonra derlendi; 202640e..main arası backend/deploy değişikliği yok). Derleme yok.
e2e: compose `e2e` servisi `npm ci` ağ ister; yerine `ffcore-10a-nm-pw` (glibc, @playwright/test 1.64.1, next 15.5.28) içeriği yığının `e2e_node_modules` volume'una ağsız kopyalanır, komut `npx playwright test` (npm ci yok). Sonunda `down -v` + YIGIN-KAPA.
D1-D6 kodu dalda (HEAD 71c0bbb); lint/typecheck/check:api/Vitest 180 yeşil.

### C-10C1-0005 · 2026-11-16 12:45 · → koordinator · YIGIN-KAPA
Paket: 10c-1   Cevap: C-10C1-0004
YIGIN-KAPA ffcore-10c1: `down -v` exit 0, e2e node_modules volume'u silindi; konteyner 0, volume 0. `ffcore/*:0.0.0-10c1` etiketleri (main imajlarının takma adı) duruyor, silinmesi sende.

### C-10C1-0006 · 2026-11-16 12:46 · → koordinator · PR-HAZIR
Paket: 10c-1   Cevap: K-10C1-0002
PR-HAZIR: `feat/10c-1-eval-ui` @ `2ac405197efc01463beb75500ecf184fa53095ab`, delta `ff142a5..2ac4051` (6 commit, 71 dosya, 26'sı görüntü). Backend/deploy/state diff 0. PR notu `state/pr/10c-1.md`. Sınıf [B].
Kapı: lint/typecheck/check:api 0; Vitest 180/180; e2e 10c1 22/22 (ilk koşudaki tek test hatası düzeltildi); tam e2e 159/159, gerileme yok. Kanıt `state/evidence/10c-1-*.log`. İki tema + edit/read görüntüleri `docs/images/10c1-*.png`.
Dikkat: (1) `10c-1-e2e-run1.log` geçersiz ilk denemedir (eski `ffcore-10a-nm-pw` volume'u, build düştü); e2e'de `npm ci` yerine `ffcore-10a-nm` kopyası kullanıldı. (2) Langfuse UI bağlantısı yok (adres yapılandırması yok), dataset adı metin. (3) Kabul 1 e2e'si 13a seed yerine fake-llm agent + from-run ile.
Dal donuk; inceleme bekliyorum.

### C-10C1-0007 · 2026-11-16 · → koordinator (10c-1) · ACK
Paket: 10c-1 r2   Cevap: K-10C1-0005
DUZELT alındı. Sıra: MAJOR-1 A (deneme başına AbortController + `STALL_MS = 3 × PROGRESS_INTERVAL_MS`, open() asılmasını da kapsar; Vitest sahte zamanlayıcı), MINOR-1 "Getirilmedi", MINOR-2 compare çevirisi, MINOR-3 analyst+read turu + kapı paneli axe. `lib/sse.ts`'e dokunulmaz (FOLLOWUP-188). Her biri önce kırmızı test, ayrı commit. Sonra YIGIN-AÇ, kapı + SIGKILL probe tekrarı, `state/evidence/10c-1-r2-*.log`, PR-HAZIR r2 (delta `2ac4051..`).

### C-10C1-0008 · 2026-11-16 12:20 · → koordinator · YIGIN-AC
Paket: 10c-1 · Cevap: K-10C1-0005 · Yigin: ffcore-10c1
r2 kapısı için: compose `-p ffcore-10c1`, BACKEND_PORT=18410 FRONTEND_PORT=13410, `.env.test`, `--profile test`, `up -d --wait --no-build --pull never` (backend imajı değişmedi; e2e kaynaktan derler). Sıra: e2e 10c1, SIGKILL probe, tam e2e. Açık başka FF yığını yok (docker ps). Disk /c 93 GB boş.

### C-10C1-0009 · 2026-11-16 12:27 · → koordinator · DURUM
Paket: 10c-1 · Cevap: K-10C1-0005 · Durum: IMPLEMENTED
SIGKILL probe 3. koşu GEÇTİ: `state/evidence/10c-1-r2-probe-sigkill.log` (+`-host.log`). Kill 12:23:47 → `lost` 12:24:15 (kill'den 28 s) → backend healthy 12:24:25 → GET "Running" → iptal 4,5 s'de "Cancelled". Koşu 1 düştü: probe hatası (healthz bağlantı reddi 0'ı "<500" saydı, iptal backend dinlemeden gitti; `-run1*.log`). Koşu 2 geçti (`-run2*.log`), ardından rozet düzeltmesi geldi, koşu 3 onu doğruladı.
Bekçi çalışıyor; şüpheli olan probe değil, süre. `lost` = STALL 6 s + 5 yeniden açma × (2 s bekleme + en çok 6 s) → üst sınır ~46 s (e2e 10c1_7: hiç cevap vermeyen akışta 46,7 s). Kill sonrası 28 s, DUZELT'teki "lost ≤ ~10 s"in üstünde. O arada sayfa `streaming` ve son durumu gösteriyor.
KARAR-GEREK (ölçüt için):
- **A (önerilen):** ilk deneme done'sız bittiğinde sayfa hemen GET yoklamasına geçer, yeniden açma arkada sürer (`data-state=reconnecting`). Bayatlık ≤ ~6 s + yoklama aralığı. Bedel: sayfa durumu + Vitest + e2e 10c1_7 güncellemesi, ~1 saat.
- B: `MAX_REOPENS` 5→1. `lost` ≤ ~14 s, tek satır. Bedel: geçici kopuşta GET'e erken düşer, akış bir daha açılmaz.
- C: olduğu gibi kalsın, PR notunda ~46 s üst sınır yazılsın. Bedel: ölçüt karşılanmaz.
Ek (kapsamda, ayrı commit'ler): rozet akış sürerken akıştaki durumu, bitince GET'inkini gösteriyor (`shownStatus`, inceleyicinin "Queued/Running" gözlemi). Compare'de kodu olmayan taraf için boş not-run tablosu kaldırıldı.
Kapı durumu: e2e 10c1 25/25 (`10c-1-r2-e2e-10c1.log`; rozet ve compare-boş düzeltmelerinden önce koştu). Tam e2e henüz koşmadı; karar gelince koşacağım. Yığın açık.

### C-10C1-0010 · 2026-11-16 12:58 · → koordinator · KARAR-GEREK
Paket: 10c-1 · Cevap: K-10C1-0007
K-10C1-0007 A uygulandı (`reconnecting` + GET, Vitest 195/195; e2e 10c1_7 stall: `reconnecting` 6,9 s, lost 46,9 s ✓). Ancak "akış geri gelince yoklama durur" e2e'si düştü ve kök neden PR dışı çıktı.
**Bulgu (kanıt `state/evidence/10c-1-r2-diag-stream.log`):** canlı sınav akışı Next proxy'sinden (`next.config` rewrites) gzip ile geçince hiç parça gelmiyor (12 s'de 0). `accept-encoding: identity` ile ve backend'den doğrudan okununca her 2 s'de 70 B geliyor. Next'in `compression` katmanı SSE'yi tamponluyor; tarayıcı her zaman gzip istiyor. Sonuç: konsolda sınav ilerlemesi akıştan hiç gelmiyor, olaylar yalnız akış kapanınca toplu geliyor (r1'de de böyleydi; test_10c1_1 `streaming|done` kabul ettiği için görünmedi). Bekçiyle sayfa artık her 6 s'de `reconnecting` + GET'e düşüp ~46 s'de `lost` oluyor: işlev doğru, akış ölü. 06a koşu akışı da aynı başlıklarla (`runs.py` `no-cache` + `X-Accel-Buffering: no`, `no-transform` yok) muhtemelen aynı durumda; doğrulamadım.
Next'in `compression`'ı `Cache-Control: no-transform`'a uyuyor (`node_modules/next/dist/compiled/compression` regex).
- **A (önerilen):** backend `eval.py:548` (ve `runs.py:411`) `Cache-Control: no-cache, no-transform`. Kaynağında doğru anlam, iki satır + backend testi. Bedel: touch-zone dışı (backend); ya bu PR'a ek izin ya da ayrı küçük paket.
- B: `frontend/next.config.ts` `compress: false`. Touch-zone içi, tek satır. Bedel: konsolun tüm yanıtları sıkıştırmasız (airgap'te önde sıkıştıran proxy yoksa paketler büyür).
- C: akış yolları için frontend route handler ile ayrı proxy. Önermiyorum: platformun proxy'sini yeniden kurmak (80/20).
Bekleyenler: A seçilirse resume e2e'si onunla yeşile döner. Tam e2e ve SIGKILL probe 4. koşu bu karardan sonra koşacak. Yığın açık. Commit edilmemiş: docs/onyuz.md + görüntüler; izlenmeyen probe/diag spec'leri (kopyaları evidence'ta, PR'a girmez).

### C-10C1-0011 · 2026-11-16 13:24 · → koordinator · DURUM
Paket: 10c-1 · Cevap: K-10C1-0008 · Durum: IMPLEMENTED
K-10C1-0008 uygulandı: `EventStreamResponse` varsayılanı `Cache-Control: no-cache, no-transform` + `X-Accel-Buffering: no` (06a ve 09 aynı sınıf). Önce kırmızı birim testi; make test ×2 1801/1801; hedefli test-int 30 geçti, 8 NOT_RUN (`test_09_exam_stack` `RUN_EVAL_STACK=1` ister; 09 akış başlığı yeni `test_09_api` testiyle gerçek DB'de kanıtlı). İmaj `up --build --pull never backend worker`. Teşhis sonrası: proxy+gzip artık her 2 s parça (`10c-1-r2-diag-stream-after.log`). e2e 10c1_7 iki test yeşil (resume dahil).
SIGKILL probe 4 GEÇTİ (`-run4*.log`): kill 13:19:21 → `reconnecting` + ilk GET 5,5 s sonra; backend kapalıyken GET 500 sayfada hata; dönünce GET 200 "Running"; iptal 6,4 s. Kusur: `reconnecting` sırasında rozet, akışın bildirdiği "Running" yerine sayfa açılışındaki GET'in "Queued"una döndü. Düzeltme ayrı commit (önce kırmızı Vitest): akış olayı ile GET'ten hangisi en son geldiyse o gösteriliyor (`newestState`). Doğrulamak için probe 5'i şimdi koşuyorum, sonra tam e2e.

### C-10C1-0012 · 2026-11-16 13:55 · → koordinator · YIGIN-KAPA
Paket: 10c-1 · Cevap: C-10C1-0008 · Yigin: ffcore-10c1
`down -v` (+ `e2e`/`tools` profilleri) ve kalan `ffcore-10c1_e2e_node_modules` adıyla silindi: konteyner 0, volume 0 (`state/evidence/10c-1-r2-down.log`). İmaj etiketleri `ffcore/*:0.0.0-10c1` duruyor (backend r2'de yeniden derlendi).

### C-10C1-0013 · 2026-11-16 13:56 · → koordinator · PR-HAZIR
Paket: 10c-1 · Cevap: K-10C1-0005 · SHA: b28cdc1c19b7cee4582c0d5740b0fba14b02e736
r2: `feat/10c-1-eval-ui`, delta `2ac4051..b28cdc1` (21 commit, 29 dosya, +725/−103). PR notu `state/pr/10c-1.md` "r2" bölümü. Sınıf [B].
MAJOR-1: bekçi (`STALL_MS` 6 s) + `reconnecting` (GET hemen, akış arkada; K-10C1-0007) + `newestState` (akış/GET'ten en son gelen). MINOR-1/2/3 yapıldı (+compare'de boş not-run tablosu kaldırıldı). Backend (K-10C1-0008): `EventStreamResponse` varsayılanı `no-cache, no-transform` + `X-Accel-Buffering: no`; Next proxy gzip tamponu kök nedendi (`10c-1-r2-diag-stream{,-after}.log`); `docs/degisiklikler.md` yeni.
Kapı: Vitest 195/195, lint/typecheck/check:api 0; backend lint 0, make test ×2 1801/1801, hedefli test-int 30 + 8 NOT_RUN (`RUN_EVAL_STACK`); tam e2e 163/163 (10c1 26/26). SIGKILL probe 5 geçti: `reconnecting` + ilk GET kill'den 4,7 s, kopuklukta rozet "Running", iptal 6,4 s (`10c-1-r2-probe-sigkill.log`); 1-4. koşular PR notunda.
Dikkat: (1) `test_09_exam_stack` başlık iddiası NOT_RUN (senaryo yığını gerekir); 09 başlığı `test_09_api` ile gerçek DB'de kanıtlı. (2) 06a istemci bekçisi FOLLOWUP-188'de; backend başlığı 06a'yı da kapsıyor. Dal donuk.

### C-10C1-0014 · 2026-11-16 15:20 · → koordinator · HANDOFF
Paket: 10c-1 · Cevap: K-10C1-0013
10c-1 MERGED (main 6157752); açık iş yok. Kalan: FOLLOWUP-185 (items ucu), 188 (`lib/sse.ts` bekçi), 190 (başlık birleşimi). Öğrenilenler:
1. **SSE bekçisi:** deneme başına `AbortController` + parça (ve istek) başına sıfırlanan zamanlayıcı (`STALL_MS = 3 × backend progress aralığı`); `open()` sinyali yok sayarsa `openWithin` yarışıyla asılmaz. Sahte zamanlayıcıda `advanceTimersByTimeAsync`.
2. **reconnecting/GET deseni:** ilk başarısız denemede GET hemen + yoklama, akış arkada; ekranda akış olayı/GET'ten en son gelen (`dataUpdatedAt` karşılaştırması); başarısız yeniden okuma ekranı silmez, hata üstte. 06a için FOLLOWUP-188'e aynı desen.
3. **Next proxy gzip tamponu:** rewrites arkasında `text/event-stream` gzip'le akış bitene dek tamponlanır; tarayıcıdan bakınca "streaming" görünür ama ara olay gelmez. Teşhis: node fetch ile `accept-encoding: identity` ↔ gzip ↔ backend doğrudan parça zamanları. Çözüm `Cache-Control: no-transform` (Next `compression` buna uyar).
4. **SIGKILL probe deseni:** izlenmeyen spec `/work/<işaret>` yazar, host betiği işareti görünce `docker kill` → 25 s → `docker start` → healthy; sağlık yoklamasında bağlantı reddi 0 döner, "<500" değil "==200" bekle. Onay bekleyen sınav (`approve_tools: true`) canlı kalır.
5. **e2e tuzakları:** eski `ffcore-10a-nm-pw` volume'u bayat (react-query yok) → `ffcore-10a-nm`'i e2e volume'üne kopyala; `down -v` `e2e_node_modules`'ü silmeyebilir, adıyla sil; `route.continue()` gzip tamponuyla akışı geçirmiyor gibi görünür (asıl neden 3); `page.unroute` bekleyen isteği de serbest bırakır.
6. **Compare kod çevirisi:** `components/eval/codes.tsx` ortak (bilinen kod çeviri + mono ham kod, bilinmeyen ham); kodsuz tarafa boş tablo yok.
7. **Read modu testleri:** fixture'da proje üyesi `analystReader` (analyst+read) var; superadmin read ↔ üye read ayrı yollar, ikisi de test edilmeli. jsdom'da disabled `<fieldset>` girdileri `.disabled` yapmıyor → her kontrole açık `disabled`.
8. ICU mesajında `<...>` ayrıştırmayı kırar; Bash aracında ters bölü çiftleri teke iner (betik Write ile).
Worktree temiz (izlenmeyen dosya yok; probe/diag spec'leri silindi, kopyaları evidence'ta). Yığın kapalı. İmaj etiketleri `ffcore/*:0.0.0-10c1` duruyor.

### C-10C1-0015 · 2026-11-16 15:21 · → koordinator · RETIRED
Paket: 10c-1 · Cevap: K-10C1-0013
Lease `ffcore-isci-c-10c1` bırakıldı. Worktree `.worktrees/feat/10c-1-eval-ui` ve dal `feat/10c-1-eval-ui` kaldırılmaya hazır (açık dosya yok).
