# Review fix/10b-sse-bekci r1 · tam tur
SHA: 5894610dd1f844d625756e6c10c2517aebe154cd · Sonuc: DEGISIKLIK · Bulgu: B0 M1 m0 N5

- **İncelenen tam SHA:** `5894610dd1f844d625756e6c10c2517aebe154cd`. Worktree salt okunur incelendi.
- **Dal:** main 106d9a3 üstüne 3 commit, 10 dosya, +464/−73. Commit'ler:
  - kırmızı test 6f0a78e
  - test düzeltmesi 4d32587
  - kod ve docs 5894610
- **İstek:** K-SSE-0003. PR notu `state/pr/fix-10b-sse-bekci.md`.
- **Yöntem:**
  - Diff satır satır okundu. Backend `runtime/events.py` `follow` ve `api/runs.py` `_stream` ile karşılaştırıldı: keepalive her `sse_keepalive_s`'de `xread` boş dönünce yazılıyor.
  - Kapı tek kullanımlık node konteynerinde koşuldu: `ffcore-rv-sse`, `--network none`, worktree salt okunur, içeride `/work` kopyası.
  - İnceleyici probe'u yazıldı: 10 Vitest vakası, sahte saatte, dalın kodu değiştirilmeden.
- **Karar: DEGISIKLIK**
- **Sayılar:** BLOCKER 0 · MAJOR 1 · MINOR 0 · NOTE 5
- **MAJOR sınıfları:** `yoklama-hatada-sessiz-durma` (yeni sınıf).

## MAJOR

### MAJOR-1 · `yoklama-hatada-sessiz-durma`: panelin GET okuması ilk istek düşerse kalıcı olarak duruyor ve hata görünmüyor

**Nerede:**
- `frontend/lib/api/runs-queries.ts` `useRun`: `refetchInterval: (q) => (q.state.data && isLiveRun(...) ? RUNS_POLL_MS : false)`. QueryProvider'da `retry: false`.
- `frontend/components/agent-test-panel.tsx`: `server.error` hiç işlenmiyor. Durum satırı yalnız `server.data` varken çiziliyor.

**Ne oluyor:**
1. Akış durunca `reconnecting` başlıyor ve `useRun` ilk GET'i atıyor.
2. Backend tam o sırada ayakta değilse bu GET düşüyor. Bu, D2'nin hedeflediği senaryo: backend yeniden başlıyor, proxy 502 veriyor ya da ağ hatası var.
3. `retry: false` olduğu için yeniden denenmiyor. `q.state.data` boş kaldığı için `refetchInterval` `false` dönüyor ve yoklama bir daha başlamıyor.
4. Yeniden bağlanma denemeleri de hızlı düşüyor (fetch reddi, 1 s gecikme). Akış `streaming`'e hiç dönmediği için `enabled` de değişmiyor. Bu yüzden `lost`'tan sonra da tek bir GET bile yok.
5. Hata ekrana yansımıyor; kayıt da tutulmuyor. Bu, fail-loud kuralına ters.

**Kanıt (probe P1):**
- İlk GET ve yeniden bağlanmalar `TypeError("Failed to fetch")` alıyor; sonra backend ayağa kalkıyor.
- Sonuç: akış `lost`, toplam **1 GET** (40 s'de). Backend döndükten sonra 10 × `RUNS_POLL_MS` boyunca **yeni GET yok**.
- `test-server-status` hiç çizilmiyor. Sayfada hata metni yok.

**Bayatlık ölçütü:**
- Sağlıklı backend'de ölçüt tutuyor (P3): GET'ler 30, 61, 92, 123, 154, 185 s'de ve `lost`'tan sonra her 3 s'de bir geliyor. En büyük boşluk 31 s, sınır `STALL + RUNS_POLL_MS` = 33 s.
- İlk GET düşerse ölçüt tutmuyor: panel sunucu durumunu süresiz okumuyor.
- Panel "lost: Runs'tan açın" yazdığı için koşuyu canlı gibi göstermiyor; yani BLOCKER değil. Ama D2'nin vaadi ve docs cümlesi bu yolda doğru değil.

**Beklenen düzeltme (yön; uygulama işçinin):**
- Panel okurken GET hatası yoklamayı durdurmamalı: veri yokken ya da hata varken de `RUNS_POLL_MS` ile denemeye devam etmeli.
  - Örneğin `useRun`'a isteğe bağlı bir `pollUntilLoaded` (ya da `refetchInterval`) seçeneği eklenebilir; `enabled` gibi additive.
  - `runs/[runId]` sayfasının davranışı değişmemeli. O sayfanın aynı açığı paketin kapsamı dışında (N5).
- Hata panelde görünmeli: mevcut `Errors` anahtarlarıyla (`errorMessageKey`) bir durum satırı, ya da en azından `report`. Yeni metin gerekirse yalnız `messages/{en,tr}.json`.
- Kabul testi: ilk GET düşüyor, sonrakiler başarılı. Durum satırı en geç `RUNS_POLL_MS` içinde görünüyor ve hata metni o ana kadar görünür kalıyor. Ayrıca `lost` sonrası ilk GET düşen vaka.

## Kontrol listesi (K-SSE-0003)

| # | Madde | Sonuç | Kanıt |
|---|---|---|---|
| 1 | Bekçi: parça verip susan akış, ham parça, sıfırlama, asılı `open` | **Doğru.** <br>• `drain` her `read()` dönüşünde `attempt.alive()` çağırıyor; `done` dahil. `openWithin` çözülünce de bir kez çağrılıyor. <br>• Yorumlar da sayılıyor; ikiye bölünmüş `: kee` + `palive\n\n` bile bekçiyi sıfırlıyor (P6). <br>• Her `STALL−1`'de bir parça gelen 6 × STALL'lık canlı akışta yanlış kopuş yok ve sonuç `done` (P5). <br>• Sinyali yok sayan ve hiç dönmeyen `open()` STALL'da bitiyor. `runId` bilinmediği için sonuç `lost`, deneme sinyali aborted, zamanlayıcı yok (P8). <br>• İşçi testleri (1) ve (3b) yeniden bağlanma yolunu kapsıyor. | P5, P6, P8; `test_10bsse_1_stall` |
| 2 | Dış `signal` iptali | **Doğru.** Okuma sırasında, yeniden deneme uykusunda ve asılı reconnect sırasında iptal: üç durumda da `ended: aborted`, `vi.getTimerCount() === 0`. `reader.cancel` gövdeye ulaşıyor (cancel = 1). <br>Panelde koşu sürerken söküm (unmount) sonrası kalan 2 zamanlayıcı TanStack'in `gcTime` zamanlayıcısı: söküm öncesinde de 2'ydi, 5 dk sonra 0. | P7, P4 |
| 3 | Okuma reddi drop; bozuk JSON fırlar | **Doğru.** <br>• Akış ortasında `c.error()` drop sayılıyor ve `reconnect("r1", "1-0", AbortSignal)` çağrılıyor; durumlar `streaming,reconnecting,streaming`. <br>• `done` hiçbir yerde uydurulmuyor. <br>• Bozuk `data:` fırlatıyor. <br>• Reddedilen ilk istek fırlatıyor (panelde `startFailed` yolu). | P9 |
| 4 | `lost` üst sınırı ve panel GET yoklaması | **Sınır doğru:** ölçülen 185 000 ms = `STALL + 5 × (RETRY + STALL)` (P10). <br>Yoklama `reconnecting` anında başlıyor. Etiketler `Runs.statuses`'tan, sekiz durumun hepsi en ve tr'de var. Akış yeniden `streaming` olunca yoklama duruyor; koşu bitince `useRun` kendi duruyor (işçi testleri ve P3). <br>**İlk GET düşerse yoklama kalıcı duruyor: MAJOR-1.** Durum satırının yalnız `reconnecting` penceresinde görünmesi: N3. | P1, P3, P10 |
| 5 | `eval-stream.ts` birebir mi | **Evet.** Kaldırılan `Attempt`, `startAttempt`, `openWithin` ve `sleep` ile `sse.ts`'teki karşılıkları gövdede aynı. Farklar şunlar: <br>• `spoke` parametresi varsayılanlı oldu; eval-stream onu açıkça veriyor. <br>• `sleep` abort dinleyicisine `{ once: true }` eklendi; davranış aynı. <br>• `openWithin` tipi `EvalFollowOptions["open"]` yerine `(signal) => Promise<Response>` oldu; ikisi aynı imza. <br>`test_10c1_3_eval_stream` değişmedi ve yeşil. | diff; kapı |
| 6 | `open`/`reconnect` sinyali; `enabled` additive | **Doğru.** Panel deneme sinyalini `startRun` ve `reconnectRun` üzerinden `fetch`'e veriyor; dış `controller.signal` `options.signal` olarak zincirleniyor. Sıfır argümanlı eski `open` hâlâ derleniyor. `useRun(projectId, runId)` çağıranları değişmeden çalışıyor (`enabled ?? true`). | diff; typecheck |
| 7 | i18n, tema, docs | `TestPanel.serverStatus` en (kaynak) ve tr'de var; kodda sabit metin yok. Satır mevcut `text-muted-foreground` token'ını kullanıyor; tema etkisi yok. `docs/agentlar.md` cümlesi (30 s, panel GET) ve `docs/degisiklikler.md` girdisi davranışla uyumlu; yalnız GET hata yolu MAJOR-1 ile birlikte düzelmeli. | diff |
| 8 | Commit düzeni | Kırmızı test önce (6f0a78e), test düzeltmesi ayrı. Kod ve docs tek commit'te (5894610): N1. | `git log` |

**Kapı:** bkz. aşağıdaki "Kapı" bölümü.

## NOTE

1. **Kod ve docs tek commit'te (5894610).** Koordinatör K-SSE-0004'te zaten not etti; bir sonraki sefer docs ayrı commit'te.
2. **`drain` başında deneme zaten iptal edilmişse `reader.cancel` çağrılmıyor.** Bu, `openWithin` çözüldükten hemen sonra bekçi ya da dış iptal geldiğinde olur. `abort` olayı geçmişte kaldığı için `stop` dinleyicisi tetiklenmiyor; döngü `null` dönüyor. Panelde `fetch` aynı sinyali taşıdığı için bağlantı yine kapanıyor. Gövdeyi sinyalsiz açan bir `open` için gövde açık kalabilir. `if (attempt.signal.aborted) stop()` tek satırla kapanır; düşük öncelik.
3. **Sunucu durum satırı her yeniden bağlanma döngüsünde yalnız kısa bir an görünüyor (P3).** Örnek: yeniden bağlanma hemen 200 dönüyor ama sessiz kalıyor. Satır `reconnecting` penceresinde (yaklaşık `RETRY_DELAY_MS` kadar) görünüyor, sonra akış `streaming` olunca 30 s gizleniyor. Tasarım gereği (`reading` tanımı) ve bayatlık sınırını bozmuyor. Ama kullanıcı satırı neredeyse göremez. Gerekirse satır son okunan değerle `lost` ya da `streaming` olana kadar tutulabilir; karar koordinatörün.
4. **İlk istek bekçide kesilirse (asılı POST) sonuç `lost` ve `runId` yok.** Koşu sunucuda oluşmuş olabilir. Panel "Runs'tan açın" diyor; PR notunda varsayım olarak yazılı. Backend `POST …/runs` yanıtını `_queued_event` ile hemen açtığı için 30 s yeterli görünüyor. Ölçümü yok, gerçek tarayıcı kanıtı da kapsam dışı (PR notundaki "Kalan riskler").
5. **`runs/[runId]` sayfası aynı `useRun` mantığını kullanıyor:** ilk GET düşerse orada da yoklama durur. Bu dalın kapsamı dışında. MAJOR-1 düzeltmesi sayfanın davranışını değiştirmemeli; ayrı bir FOLLOWUP önerilir.

## Kapı

Konteyner `ffcore-rv-sse`: `node:20.19.5-alpine`, `--network none`, worktree `/repo` olarak salt okunur, `ffcore-10a-nm` node_modules. Sonuç işçininkiyle aynı:
- `npm run lint`: 0
- `npm run typecheck`: 0
- `npm run check:api`: 0
- `npx vitest run`: **40 dosya, 208/208**, exit 0

Log `state/evidence/fix-10b-sse-bekci-r1-rv-gate.log`, `HEAD=` satırlı.

İlk denemede yalnız `frontend/` kopyalanmıştı. `check:api` ve 6 sözleşme testi `../backend` okuduğu için düştü; bu benim kurulum hatamdı. Tüm worktree bağlanınca yukarıdaki sonuç alındı. Probe ayrı koşuldu: 10/10 geçti.

## Kanıt
- `state/evidence/fix-10b-sse-bekci-r1-rv-gate.log`: lint, typecheck, check:api ve tüm Vitest (probe dosyası olmadan).
- `state/evidence/fix-10b-sse-bekci-r1-rv-probe.log`: 10 probe vakası, `[RV]` satırları ölçümleri taşıyor.
- `state/evidence/fix-10b-sse-bekci-r1-rv-probe.test.tsx.txt`: probe dosyası. Dala ait değil; konteyner içinde `/work` kopyasına konup koşuldu.
