# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-sse
- Aktif paket: fix/10b-sse-bekci (FOLLOWUP-188, 06a koşu akışı hareketsizlik bekçisi)
- Durum: ACTIVE
- Son okunan: koordinator K-SSE-0001; son yazılan C-SSE-0001 (ACK)
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

