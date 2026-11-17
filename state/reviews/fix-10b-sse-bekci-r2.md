# Review fix/10b-sse-bekci r2 · teyit turu (r1 MAJOR-1, NOTE-2, NOTE-4)
SHA: 8c01f046c9e6087076b495de53661ef63f60e646 · Sonuc: ONAY · Bulgu: B0 M0 m0 N2

- **İncelenen tam SHA:** `8c01f046c9e6087076b495de53661ef63f60e646`. Worktree salt okunur incelendi.
- **Delta** `5894610..8c01f04`: 3 commit, 9 dosya, +124/−6. Commit'ler:
  - kırmızı test 0e8fdfd
  - kod 058dbe8
  - docs 8c01f04

  Test, kod ve docs ayrı commit'lerde; r1 N1 karşılandı.
- **İstek:** K-SSE-0007 (karar K-SSE-0006). r1 raporu `fix-10b-sse-bekci-r1.md`.
- **Yöntem:**
  - Delta okundu.
  - Kapı node konteynerinde koşuldu: `ffcore-rv-sse`, `--network none`.
  - r1'in 10 probe vakası aynen yeniden koşuldu ve üstüne 5 yeni vaka eklendi (r2 P1, P11-P14). Toplam **15/15 geçti**.
- **Karar: ONAY**
- **Sayılar:** BLOCKER 0 · MAJOR 0 · MINOR 0 · NOTE 2
- **MAJOR sınıfları:** yok. r1'deki `yoklama-hatada-sessiz-durma` kapandı ve tekrarlamadı.

## Kontrol listesi (K-SSE-0007)

| # | Madde | Sonuç | Kanıt (`-r2-rv-probe.log`) |
|---|---|---|---|
| 1 | **P1 tekrarı (r1 MAJOR-1)** | **Kapandı.** <br>• Backend düşükken akış `lost` oluyor. Hata satırı görünüyor: `test-server-error`, `role="alert"`, metinde `network_error`. <br>• GET'ler her 3 s'de sürüyor: 40, 43, 46, 49 ve 52 s. Backend döndükten sonraki ilk GET başarılı. <br>• Hata satırı kalkıyor ve yerine "Status read from the server: Running" geliyor. <br>• Okuma başladıktan sonra en büyük GET boşluğu 3000 ms, yani `RUNS_POLL_MS`. <br>• r1 probe'unun P1'i de artık backend dönünce durumu gösteriyor. | r2 P1, r1 P1 |
| 2 | Hata satırı | Sözleşme kodu (`unavailable`, `run_not_found`) ya da `network_error` gösteriliyor. Metin `Errors` anahtarları üzerinden `errorMessageKey` ile geliyor. tr yerelinde: "Koşu sunucudan okunamadı: İstek başarısız oldu. (kod: unavailable). Yeniden deneniyor…" (P12). <br>Önceden veri varken sonradan düşen GET'te hata satırı durum satırının yerini alıyor ve yoklama sürüyor (P12). | P11, P12 |
| 3 | Yoklama ne zaman duruyor | Koşu bitince duruyor: veri geldiyse `isLiveRun` kararı geçerli (işçi testi "stops reading once the run has ended"; P14 varsayılan yolda 3 GET'te durdu). Akış `streaming`'e dönünce `enabled` false oluyor ve yoklama duruyor (r1 P3 dizisi değişmedi: 30, 61, 92 … s). | P3, P14; `test_10bsse_2_panel_poll` |
| 4 | `useRun` varsayılanı değişmedi | Doğru. `pollWhileUnknown` isteğe bağlı ve yalnız panel veriyor. Seçeneksiz `useRun`'da ilk GET düşünce tekrar yok (P13: 1 GET). Canlı koşu yoklanıyor, biten koşu duruyor (P14). `runs/[runId]` sayfasının davranışı aynı (FOLLOWUP-192). | P13, P14 |
| 5 | NOTE-2 cancel | `if (attempt.signal.aborted) stop();` dinleyici kaydından hemen sonra geliyor. İşçi testi "cancels the body it will not read and ends as aborted" (cancel = 1). r1 P7 ve P9 değişmeden geçiyor: zamanlayıcı 0. | P7, P9 |
| 6 | i18n ve docs | `TestPanel.serverUnavailable` en (kaynak) ve tr'de var; kodda sabit metin yok. `text-destructive` iki temada tanımlı token (`styles/tokens.css` açık #B91C1C, koyu #F87171). <br>`docs/agentlar.md` ve `docs/degisiklikler.md` hata satırını ve tekrar denemeyi doğru anlatıyor. "Server answers or the run has ended" ifadesi probe ile uyumlu. Asılı ilk istek de yazılmış (r1 NOTE-4). | diff |

## Kapı
Konteyner ve bağlama düzeni r1 ile aynı. Sonuç işçininkiyle aynı:
- `npm run lint`: 0
- `npm run typecheck`: 0
- `npm run check:api`: 0
- `npx vitest run`: **40 dosya, 211/211**, exit 0

Log `state/evidence/fix-10b-sse-bekci-r2-rv-gate.log`, `HEAD=` satırlı.

## NOTE

1. **Kalıcı hatada süresiz yoklama (P11).** GET hep `404 run_not_found` dönerse panel açık kaldıkça her 3 s'de bir istek atıyor; 10 dakikada 201 GET. Metin de çelişkili: "It no longer exists. Refresh the page … Trying again…". Zararsız; yük düşük ve yalnız `reconnecting`/`lost` iken oluyor. İstenirse 4xx kodlarında (`*_not_found`, `forbidden`) yoklama durdurulabilir. Karar koordinatörün; birleştirmeyi beklemez.
2. **Probe notu:** sahte saatte başarılı GET'ten sonra durum satırının çizilmesi birkaç zamanlayıcı turu sürüyor (TanStack notify ve React). İlk r2 P1 denemem bu yüzden erken ölçtü ve düştü. Bu bir ürün hatası değil, ölçüm düzeltildi. İşçinin panel testlerindeki `advance(0)` notuyla aynı olgu.

## Kanıt
- `state/evidence/fix-10b-sse-bekci-r2-rv-gate.log`: lint, typecheck, check:api ve Vitest 211/211.
- `state/evidence/fix-10b-sse-bekci-r2-rv-probe.log`: r1'in 10 vakası ve r2'nin 5 vakası, 15/15. `[RV]`/`[RV2]` satırları ölçümleri taşıyor.
- `state/evidence/fix-10b-sse-bekci-r2-rv-probe.test.tsx.txt`: r2 probe dosyası. r1'inki `-r1-rv-probe.test.tsx.txt`.
