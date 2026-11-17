# [B] fix(frontend): run stream stall watchdog; test panel reads the run with GET

**Paket:** fix/10b-sse-bekci (FOLLOWUP-188) · **Sınıf:** [B] · **Branch:** fix/10b-sse-bekci · **Baz commit:** 106d9a3 (main; a46f147 + yalnız `oturumlar.json` state commit'i) · **HEAD (r2):** 8c01f046c9e6087076b495de53661ef63f60e646 (r1: 5894610dd1f844d625756e6c10c2517aebe154cd)

GOREV K-SSE-0001, PLANNED C-SSE-0002, PLAN-ONAY K-SSE-0002 (Soru 1 A, Soru 2 A, D2 uygun).

## r2 (DUZELT K-SSE-0005, r1 DEGISIKLIK B0 M1 m0 N5) · delta 5894610..8c01f04
3 commit (test / kod / docs ayrı, NOTE-1): `0e8fdfd` kırmızı test, `058dbe8` kod, `8c01f04` docs; 9 dosya +124/−6.
- **MAJOR-1 `yoklama-hatada-sessiz-durma` (A):** `useRun(projectId, runId, { enabled, pollWhileUnknown })`: `pollWhileUnknown` ile veri yokken (ilk GET düştü) `refetchInterval` `RUNS_POLL_MS` döner; veri gelince eski kural (`isLiveRun` false → durur). Panel bunu `reading` iken kullanır; `server.error` → `data-testid="test-server-error"` satırı, `TestPanel.serverUnavailable` (en + tr) `Errors` mesajı + kod: `ApiError` ise sözleşme kodu, `api()`'den gelen ApiError olmayan red fetch'in kendisi (ağ) → `network_error`. Son GET başarılıysa hata satırı kalkar, durum satırı gelir. `runs/[runId]` değişmedi (FOLLOWUP-192).
- **NOTE-2:** `drain` dinleyiciyi ekledikten hemen sonra deneme zaten bittiyse `stop()` (`reader.cancel`) çağırır.
- **NOTE-4:** `docs/agentlar.md` 'Runs' ve `docs/degisiklikler.md`: başarısız GET gösterilir ve sunucu cevap verene ya da koşu bitene kadar tekrarlanır; 30 s asılı kalan ilk istek `runId`'siz `lost` biter, koşu oluşmuş olabilir: Runs'tan açın. **NOTE-3** kabul, değişiklik yok.

| # | Kriter (K-SSE-0005) | Test | Durum |
|---|---|---|---|
| M1 | Probe P1: ilk GET ve yeniden bağlanmalar `TypeError`; yoklama sürer, hata satırı (`network_error`) görünür; backend dönünce `RUNS_POLL_MS` içinde durum satırı, hata satırı kalkar | `test_10bsse_2_panel_poll` "keeps reading after a failed GET, shows the failure, then the status once the backend is back" (`lost` iken GET ≥ 2) | geçti |
| M1 | Reddedilen GET sözleşme koduyla görünür; koşu bitince (`completed`) yoklama durur | "shows the contract code when the GET is refused, and stops reading once the run has ended" (5 × `RUNS_POLL_MS` boyunca GET sayısı sabit) | geçti |
| M1 | Mevcut panel testleri yeşil | `test_10bsse_2_panel_poll` ilk 3 test (değişmedi) | geçti |
| N2 | Okunmadan biten denemenin gövdesi iptal edilir | `test_10bsse_1_stall` "cancels the body it will not read and ends as aborted" (`cancel` = 1) | geçti |

Kırmızı kanıt (0e8fdfd, kod yok): `state/evidence/sse-bekci-r2-red.log` (3 düştü, 13 geçti). Kapı HEAD 8c01f04: lint 0 uyarı, typecheck 0, check:api 0, Vitest **40 dosya, 211/211** → `state/evidence/sse-bekci-gate-r2.log`.

## Plan
1. **Bulunan semboller:** `frontend/lib/sse.ts` `followRunStream`/`drain` (zaman aşımsız `reader.read()`, okuma reddi dışarı fırlıyordu); `lib/eval-stream.ts` `startAttempt`/`openWithin`/`sleep` (10c-1 bekçisi); `components/agent-test-panel.tsx` (tek tüketici; `onState`, `lost` metni, Runs bağlantısı; GET'e geçmiyordu); `lib/api/runs-queries.ts` `useRun` (`RUNS_POLL_MS` 3 s, `isLiveRun`); `app/(console)/runs/[runId]/page.tsx` akış kullanmıyor, `useRun` ile yokluyor; `backend/ffcore/core/config.py:156` `sse_keepalive_s = 10`.
2. **Kapsam:** D1 bekçi, D2 panel GET okuması, D3 belge. **Kapsam dışı:** backend keepalive, 06a akışının Playwright e2e'si, `runs/[runId]` (zaten yokluyor: not yeter).
3. **Dosyalar:** bkz. "Değişen dosyalar".
4. **Sözleşme/yapılandırma/profil:** C9 değişmez (olay adları, `Last-Event-ID`); OpenAPI değişmez (`check:api` 0). `FollowOptions.open/reconnect` deneme sinyalini ek argüman alır, `stallMs` isteğe bağlı: additive, eski sıfır argümanlı çağıranlar derlenir. `useRun`'a isteğe bağlı `{enabled}`. Profil etkisi yok.
5. **Kabul → test:** tablo aşağıda.
6. **Migration:** yok.
7. **Geri alma:** `git revert 5894610 4d32587 6f0a78e` (yalnız önyüz + docs).
8. **Durma koşulları:** backend değişikliği gerekirse; C9 kırılırsa. Gerçekleşmedi.
9. **Felsefe:** ARCH-07 tek tüketici, yarı açık bağlantı her test koşusunu etkiler; kalıcı karmaşıklık küçük, bekçi tek yerde (eval-stream ile paylaşılır). ARCH-09 yoklama TanStack Query `refetchInterval` (`useRun`), yeni altyapı yok; bekçi yardımcıları kopyalanmadı, taşındı. ARCH-06/10 sessiz akış `reconnecting`/`lost` olarak görünür; hiçbir yerde `done` uydurulmaz; bozuk JSON eskisi gibi fırlar; panel GET durumunu "sunucudan okunan" diye etiketler.

## Değişen dosyalar
- `frontend/lib/sse.ts`: `SSE_KEEPALIVE_MS = 10_000` (yorum: `core/config.py sse_keepalive_s`, `runtime/events.py`), `STALL_MS = 3 × SSE_KEEPALIVE_MS`; `Attempt`, `startAttempt`, `openWithin`, `sleep` export (eval-stream'den taşındı; `sleep` abort dinleyicisine `{ once: true }`); `drain` deneme sinyaliyle `reader.cancel()`, her ham parçada `alive()`, okuma reddi → `null` (drop); `followRunStream` deneme başına bekçi, ilk istek reddi eskisi gibi fırlar (panel `startFailed`), bekçinin kestiği ya da yeniden bağlanmada düşen istek drop.
- `frontend/lib/eval-stream.ts`: yalnız import (yerel `Attempt`/`startAttempt`/`openWithin`/`sleep` silindi). Davranış değişmedi: 10c-1 testleri değişmeden yeşil.
- `frontend/lib/api/runs-queries.ts`: `useRun(projectId, runId, { enabled })`.
- `frontend/components/agent-test-panel.tsx`: deneme sinyali `startRun`/`reconnectRun`'a gider; `reading = runId && (reconnecting || lost)` iken `useRun` ve `data-testid="test-server-status"` satırı (`Runs.statuses` etiketleri).
- `frontend/messages/{en,tr}.json`: `TestPanel.serverStatus`.
- `frontend/tests/unit/test_10bsse_1_stall.test.ts` (10 test), `test_10bsse_2_panel_poll.test.tsx` (3 test).
- `docs/agentlar.md` 'Runs' (keepalive, 30 s, panel GET), `docs/degisiklikler.md` 2026-11-17 girdisi.

## Kabul kriterleri → testler
| # | Kriter (K-SSE-0001) | Test | Durum |
|---|---|---|---|
| 1 | Parça verip susan akış → `STALL_MS` sonra deneme iptal, `reconnect` `Last-Event-ID` ile, `onState('reconnecting')` | `test_10bsse_1_stall` "(1) ends a stream that spoke then went silent…" (STALL−1'de yok, STALL'da var; deneme sinyali aborted; `reconnect("r1","1-0",AbortSignal)`) | geçti |
| 2 | Yalnız `: keepalive` gelen akış bekçiyi tetiklemez | "(2) keeps a stream alive on `: keepalive` comments alone" (3×STALL boyunca) | geçti |
| 3 | Her yeniden bağlanma da susarsa `maxReconnects` sonunda `lost`, üst sınır adlı | "(3) reports lost after maxReconnects…" `LOST_UPPER_BOUND_MS = STALL + MAX_RECONNECTS × (RETRY_DELAY_MS + STALL)` = 185 s; sınır−1'de bitmemiş, sınırda `lost`; "(3b)" asılı reconnect isteği de bekçide | geçti |
| 4 | Susan akış yeniden açılınca `done` → `done` | "(4) reports done when the stream reopened after a stall…" | geçti |
| 5 | Dış `signal` iptali `aborted`, zamanlayıcı temizlenir | "(5) ends as aborted on the outside signal…" (`vi.getTimerCount() === 0`, reconnect yok) | geçti |
| 6 | Mevcut 4 following testi değişmeden yeşil | `test_10bp2_6_sse` (8/8; dosya değişmedi) | geçti |
| 7 | lint, typecheck, check:api, Vitest yeşil | `state/evidence/sse-bekci-gate-head.log` | geçti |
| S2 | Okuma reddi drop (Soru 2 A); bozuk JSON fırlar | `test_10bsse_1_stall` "a failed read is a drop" (2 test) | geçti |
| — | `stallMs` ayarlanabilir; `STALL_MS = 3 × SSE_KEEPALIVE_MS` | "uses FollowOptions.stallMs", "derives STALL_MS…" | geçti |
| D2 | Panel `reconnecting`/`lost` iken GET ile okur, durum gösterir; akış dönünce yoklama durur | `test_10bsse_2_panel_poll` (3 test: STALL−1'de GET yok / STALL'da GET + "Running" + `RUNS_POLL_MS` sonra tekrar; `lost` sonrası sürer; akış konuşunca durur) | geçti |
| S1 | 10c-1 eval-stream testleri değişmeden yeşil (Soru 1 A kanıtı) | `test_10c1_3_eval_stream` 16/16 (dosya değişmedi) | geçti |

Kırmızı kanıt (test commit'i 6f0a78e, kod yok): `state/evidence/sse-bekci-red-1.log` (stall: 8 düştü, 2 geçti: yalnız-keepalive ve bozuk-JSON testleri eski kodda da doğru), `sse-bekci-red-2.log` (panel: 3/3 düştü).

## Çalıştırılan komutlar
| Komut | Ortam | Exit | Sonuç / kanıt |
|---|---|---|---|
| `npx vitest run tests/unit/test_10bsse_1_stall.test.ts` (kırmızı) | `node:20.19.5-alpine`, `--network none`, `ffcore-10a-nm` | 1 | `sse-bekci-red-1.log` |
| `npx vitest run tests/unit/test_10bsse_2_panel_poll.test.tsx` (kırmızı) | aynı | 1 | `sse-bekci-red-2.log` |
| hedefli Vitest (sse, stall, panel, eval-stream) | aynı | 1 → düzeltme | `sse-bekci-green-targeted.log`: panel 'lost' testi render boşaltması eksikti (test düzeltmesi 4d32587, kod değil) |
| `npm run lint`, `typecheck`, `check:api`, `npx vitest run` (HEAD 5894610) | aynı | 0 / 0 / 0 / 0 | lint 0 uyarı; Vitest **40 dosya, 208/208**; `state/evidence/sse-bekci-gate-head.log` (önceki koşu `sse-bekci-gate-1.log`: 2 lint uyarısı test dosyasında, giderildi) |
| backend `make test`/`test-int`, e2e | — | NOT_RUN | diff'te backend yok (K-SSE-0001 kabul 7) |

## Çıktı özeti ve post-state
Konteyner `ffcore-sse-gate` her koşuda `--rm`; açık konteyner yok. Compose yığını açılmadı. Secret, kurum verisi yok.

## Kontrol listesi
- [x] Felsefe ile çelişen nokta yok
- [x] Donmuş sözleşme kırılmadı (C9 aynı; tip değişiklikleri additive)
- [ ] İki profil testi koştu: önyüzde profil farkı yok, backend testi gerekmez (kabul 7)
- [x] Mutasyon ucu eklenmedi
- [x] Secret-free
- [x] Metin `en`/`tr`'de; yeni satır mevcut `text-muted-foreground` sınıfıyla (iki temada token rengi; tema e2e koşmadı)
- [x] Docs güncel; `.env.example` gerekmez
- [x] OpenAPI değişmedi; `check:api` yeşil
- [ ] WORK_QUEUE: koordinatörde

## Varsayımlar ve brief'teki çelişkiler
- Baz main a46f147 değil 106d9a3 (aradaki tek commit `state/oturumlar.json`).
- Bekçinin kestiği **ilk** istek (open asılı kalırsa) drop sayılır; `run_id` henüz bilinmediği için sonuç `lost` (yeniden bağlanacak koşu yok). Sunucunun **reddettiği** ilk istek eskisi gibi `ApiError` fırlatır (panel `startFailed`).
- `sleep`'e `{ once: true }` eklendi (taşınırken; davranış aynı, dinleyici sızıntısı yok). eval-stream'in davranışı değişmedi.
- Panel testinde React zamanlayıcıları sahte saatte koştuğu için `lost` sonrası bir `advance(0)` gerekir (test düzeltmesi, 4d32587).

## Kalan riskler
- Yarı açık bağlantının gerçek tarayıcıda (backend SIGKILL) Playwright kanıtı yok; kapsam dışı (gerekirse FOLLOWUP).
- `SSE_KEEPALIVE_S` ≥ 30 s yapılırsa sessiz koşular gereksiz yeniden bağlanır (docs/degisiklikler.md'de yazılı); önyüz sabiti backend değerini okumaz, yorumla bağlı.
