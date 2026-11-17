# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-sse
- Aktif paket: fix/10b-sse-bekci (FOLLOWUP-188, 06a koşu akışı hareketsizlik bekçisi)
- Durum: ACTIVE
- Son okunan: koordinator K-SSE-0005; son yazılan C-SSE-0009 (PR-HAZIR r2)
- Önceki lease: ffcore-isci-c-10c1 RETIRED (10c-1 MERGED; son C-10C1-0015 RETIRED); ondan önce ffcore-isci-c-10bp2 RETIRED (10b-poc-2 MERGED b43770d; son C-10bp2-0019 HANDOFF)

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-c-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 97 mesaj); ID ile atıf orada bulunur.

### C-SSE-0001 · 2026-11-17 07:30 · → koordinator · ACK
Paket: fix/10b-sse-bekci · Cevap: K-SSE-0001
GOREV alındı. Lease ffcore-isci-c-sse ACTIVE (önceki ffcore-isci-c-10c1 RETIRED, C-10C1-0015). Worktree `.worktrees/fix/10b-sse-bekci` (baz main) açılıyor; kod okuması sonrası PLANNED mesajı gelecek, PLAN-ONAY'a kadar kod yazılmaz.

### C-SSE-0002 · 2026-11-17 07:34 · → koordinator · DURUM
Paket: fix/10b-sse-bekci · Cevap: K-SSE-0001 · Durum: PLANNED
Worktree `.worktrees/fix/10b-sse-bekci` açıldı; baz main **106d9a3** (a46f147 sonrası yalnız `oturumlar.json` state commit'i). **Dosyalar (frontend/):** `lib/sse.ts`, `components/agent-test-panel.tsx`, `lib/api/runs-queries.ts` (`useRun`'a isteğe bağlı `enabled`, additive), `messages/{en,tr}.json` (1 anahtar), yeni `tests/unit/test_10bsse_1_stall.test.ts` + `test_10bsse_2_panel_poll.test.tsx`; `docs/agentlar.md` 'Runs' bir cümle, `docs/degisiklikler.md`; Soru 1=A ise `lib/eval-stream.ts` (yalnız import). Backend yok, OpenAPI yok.
**D1 zamanlayıcı:** `eval-stream` deseni: deneme başına `AbortController` (dış `signal`'e zincirli), `reader.read()` her döndüğünde (ham parça; `: keepalive` dahil) sıfırlanan `setTimeout`; dolunca `controller.abort()` + `reader.cancel()`; istek de bekçide (`openWithin`: asılı `open/reconnect` denemeyi kilitlemez). `SSE_KEEPALIVE_MS = 10000` (yorum: `backend/ffcore/core/config.py sse_keepalive_s`), `STALL_MS = 3 × SSE_KEEPALIVE_MS`, `FollowOptions.stallMs`. `open`/`reconnect` deneme sinyalini ek argüman alır (`open(signal)`, `reconnect(runId, last, signal)`; sıfır argümanlı eski çağıranlar tip uyumlu); panel bunu fetch'e verir, bağlantı gerçekten kapanır. Üst sınır adlı: `lost` ≤ `STALL + max × (RETRY + STALL)` = 30 + 5×31 = 185 s (test sabitlerle hesaplar). `done` hiçbir yerde uydurulmaz; dış iptal `aborted`, zamanlayıcı ve dinleyiciler `finally`'de temizlenir.
**D2 kararı:** panel bugün `lost`'ta yalnız metin + Runs bağlantısı gösteriyor, GET'e geçmiyor (`runs/[runId]` akış kullanmıyor, `useRun` zaten `RUNS_POLL_MS` ile yokluyor → not yeter). 10c-1 eki gibi: `reconnecting` ya da `lost` + `runId` varken panel `useRun(…, {enabled})` ile koşuyu okur ve sunucu durumunu mevcut `Runs.statuses` etiketleriyle tek satırda gösterir (yeni anahtar `TestPanel.serverStatus`); akış `streaming`'e dönünce yoklama durur; koşu bitmişse `useRun` kendi durur.
**Felsefe:** ARCH-07 tek tüketici, kalıcı karmaşıklık ~40 satır, yarı açık bağlantı bütün koşu ekranına değer; ARCH-09 Next/TanStack `refetchInterval` kullanılır, yeni yoklama altyapısı yok; ARCH-06/10 bekçi sessizliği `reconnecting`/`lost` olarak görünür kılar, sessiz `done` yok.
**Soru 1 (bekçi kodu):** **A (Önerilen)** `startAttempt`/`openWithin`/`sleep` `lib/sse.ts`'den export, `eval-stream.ts` import eder (10c-1 testleri değişmeden yeşil kanıt; tek kaynak, ARCH-09). B: `sse.ts`'te kopya (~40 satır çift kod, 10c-1'e sıfır dokunuş). C: ayrı `lib/stream-watchdog.ts` (A ile aynı, bir dosya fazla).
**Soru 2 (okuma hatası):** bugün `drain`'de `reader.read()` reddi `followRunStream`'den fırlar, panel yeniden bağlanmadan `lost` der. **A (Önerilen)** her okuma reddi (bekçi iptali ya da ağ hatası) 'drop' sayılır → yeniden bağlanma yolu (`reconnecting` görünür); bozuk JSON verisi drop değil, eskisi gibi fırlar. B: yalnız bekçi iptali drop, ağ hatası eskisi gibi fırlar (iki yol, tutarsız).
Cevap gelmezse A/A ile ilerlemem; PLAN-ONAY bekliyorum.

### C-SSE-0003 · 2026-11-17 07:40 · → koordinator · YIGIN-AC
Paket: fix/10b-sse-bekci · Cevap: K-SSE-0002 · Yigin: ffcore-sse-gate
PLAN-ONAY alındı (Soru 1 A, Soru 2 A, D2). Compose yığını yok: tek kullanımlık `docker run --rm --name ffcore-sse-gate --network none node:20.19.5-alpine`, worktree bağlı, `ffcore-10a-nm` → `frontend/node_modules`. Kırmızı test kanıtı ve sonra önyüz kapısı (lint, typecheck, check:api, vitest) bu adla koşar; çıktılar `state/evidence/sse-bekci-*.log`. Bitince YIGIN-KAPA.

### C-SSE-0004 · 2026-11-17 07:52 · → koordinator · YIGIN-KAPA
Paket: fix/10b-sse-bekci · Cevap: C-SSE-0003 · Yigin: ffcore-sse-gate
Tüm koşular `docker run --rm`; `ffcore-sse-gate` adlı konteyner kalmadı (`docker ps -a` boş). Compose yığını açılmadı, volume oluşturulmadı (`ffcore-10a-nm` yalnız okundu-bağlandı).

### C-SSE-0005 · 2026-11-17 07:53 · → koordinator · PR-HAZIR
Paket: fix/10b-sse-bekci · Cevap: K-SSE-0002 · SHA: 5894610dd1f844d625756e6c10c2517aebe154cd
Branch `fix/10b-sse-bekci` (baz main 106d9a3), 3 commit: 6f0a78e test (kırmızı), 4d32587 test düzeltmesi, 5894610 kod+docs; 10 dosya (frontend 8, docs 2), backend yok. PR notu `state/pr/fix-10b-sse-bekci.md`.
Kapı (HEAD, node konteyneri `--network none`): lint 0 uyarı, typecheck 0, check:api 0, Vitest 40 dosya **208/208** → `state/evidence/sse-bekci-gate-head.log`. Kırmızı kanıt `sse-bekci-red-{1,2}.log`.
Kabul 1-7 + Soru 2 (okuma reddi drop, bozuk JSON fırlar) + D2 (panel `reconnecting`/`lost` iken `useRun` ile sunucu durumu, akış konuşunca durur) testle; `test_10bp2_6_sse` ve `test_10c1_3_eval_stream` dosyaları değişmeden yeşil (Soru 1 A kanıtı). `lost` üst sınırı 185 s adlı sabitlerle testte. Hook kaydında isci-c uyarısı yok. Push yok; e2e/backend kapısı NOT_RUN (diff'te backend yok).

### C-SSE-0006 · 2026-11-17 08:10 · → koordinator · ACK
Paket: fix/10b-sse-bekci · Cevap: K-SSE-0005
DUZELT alındı (r1 DEGISIKLIK, rapor okundu). Uygulanacak: MAJOR-1 `useRun` additive `pollWhileUnknown` + panelde `TestPanel.serverUnavailable` hata satırı (ApiError kodu; `api()`'den gelen ApiError olmayan red = fetch ağ hatası → `network_error`); NOTE-2 `drain` başında iptalse `reader.cancel`; NOTE-4 docs + PR notu. Sıra: kırmızı test → kod → docs, üç ayrı commit; kapı konteynerde YIGIN-AC/KAPA, `sse-bekci-gate-r2.log`.

### C-SSE-0007 · 2026-11-17 08:10 · → koordinator · YIGIN-AC
Paket: fix/10b-sse-bekci · Cevap: K-SSE-0005 · Yigin: ffcore-sse-gate
r2 için aynı tek kullanımlık konteyner: `docker run --rm --name ffcore-sse-gate --network none node:20.19.5-alpine`, worktree bağlı, `ffcore-10a-nm`. Kırmızı kanıt ve kapı; bitince YIGIN-KAPA.

### C-SSE-0008 · 2026-11-17 08:15 · → koordinator · YIGIN-KAPA
Paket: fix/10b-sse-bekci · Cevap: C-SSE-0007 · Yigin: ffcore-sse-gate
Koşular `--rm`; `ffcore-sse-gate` konteyneri kalmadı (`docker ps -a` boş), yığın/volume açılmadı.

### C-SSE-0009 · 2026-11-17 08:15 · → koordinator · PR-HAZIR
Paket: fix/10b-sse-bekci · Cevap: K-SSE-0005 · SHA: 8c01f046c9e6087076b495de53661ef63f60e646
r2, delta `5894610..8c01f04` (9 dosya +124/−6), test/kod/docs ayrı: `0e8fdfd` kırmızı test, `058dbe8` kod, `8c01f04` docs. PR notu `state/pr/fix-10b-sse-bekci.md` "r2" bölümü.
MAJOR-1: `useRun` additive `pollWhileUnknown` (veri yokken `RUNS_POLL_MS`, koşu bitince durur); panel `test-server-error` satırı `TestPanel.serverUnavailable` (en+tr; ApiError kodu ya da fetch ağ reddi → `network_error`), GET başarılı olunca durum satırı. Probe P1 testte: `lost` iken GET ≥ 2, backend dönünce `RUNS_POLL_MS` içinde "Running", hata satırı kalkar; reddedilen GET kodu görünür, `completed` sonrası 5 aralık GET yok. NOTE-2 `drain` başında iptalse `reader.cancel` (test cancel=1). NOTE-4 docs. `runs/[runId]` değişmedi.
Kapı HEAD (konteyner `--network none`): lint 0 uyarı, typecheck 0, check:api 0, Vitest 40 dosya **211/211** → `state/evidence/sse-bekci-gate-r2.log`; kırmızı `sse-bekci-r2-red.log` (3 düştü). Push yok.

