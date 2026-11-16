# Review fix/ajan-hooklari r3 · teyit turu (r2 MINOR-2 GUARD-DERINLIK, MINOR-1 belge satırı)
SHA: 7a1195afc17648062a0a6afdae45d2aa54d88bd9 · Sonuc: ONAY · Bulgu: B0 M0 m0 N3

- **İncelenen tam SHA:** `7a1195afc17648062a0a6afdae45d2aa54d88bd9` (`fix/ajan-hooklari`, worktree salt okunur). Delta `49b4343..7a1195a`: 3 commit (test 8dba118, fix c05fee1, docs 7a1195a). 5 dosya, +55/−4. state, backend ve frontend değişikliği yok.
- **İstek:** K-HOOK-0012 REVIEW-ISTEK (teyit turu). Kapsam kararı K-HOOK-0011: MINOR-2 bu turda kapanır; MINOR-1 kodu ve MINOR-3 FOLLOWUP-189'a gider, bu turda yalnız belge satırı yazılır.
- **Yöntem:** yığın açılmadı, ağ kullanılmadı.
  - Delta diff'i okundu.
  - Host `py -3.12` ile `pytest tests/hooks` koşuldu.
  - r2 probe'u (104 çağrı) aynen tekrarlandı, üstüne 8 derinlik vakası (D01-D08) eklendi: toplam 112 doğrudan çağrı.
  - Çağrılar `.claude/settings.json`'daki komut biçimiyle, `FFCORE_MAIN_ROOT` geçici kökteyken yapıldı.
- **Karar: ONAY**
- **Sayılar:** BLOCKER 0 · MAJOR 0 · MINOR 0 · NOTE 3
- **MAJOR sınıfları:** yok (r1'in iki sınıfı r2'de kapandı, tekrar yok).

## Kontrol listesi (K-HOOK-0012)

| # | Madde | Sonuç | Kanıt (`-r3-rv-probe.log`) |
|---|---|---|---|
| 1 | R13: 4 düzey `sh -c` push, işçi rolünde `GUARD-DERINLIK` engeli ve kayıt | **Kapandı.** R13 ve D01 çıkış 2, stderr `[GUARD-DERINLIK] iç içe komut 3 düzeyi aşıyor; denetlenemedi`, kayıtta `block isci-a Bash GUARD-DERINLIK` satırı var. warn kipinde çıkış 0, `systemMessage` ve `warn` kaydı (D08). | R13, D01, D08 ve kayıt dökümü |
| 2 | 3 düzey hâlâ denetleniyor | **Evet.** 3 düzey push `PUSH` ile engellenir (D02), 3 düzey `echo` serbest (D03). compose run > `sh -c` > `bash -c 'make test'` `KAPI` ile engellenir (D06). e2e tarifi (`compose run e2e sh -c "npx playwright test" … \| tee`) serbest (D07). | D02, D03, D06, D07 |
| 3 | Düz 4 düzey `echo` yanlış pozitif mi | **Evet, engelleniyor** (D04). compose run > `sh -c` > `bash -c` > `sh -c echo` de engelleniyor (D05; compose run bir düzey sayılıyor). Bilinçli ve kabul edilebilir bir yanlış pozitif; değerlendirmesi N1'de. | D04, D05 |
| 4 | "Bilinen sınırlar" satırı | **Doğru ve davranışla tutarlı.** docs 9.2, ENVIRONMENT ve SECURITY `git push` satırı şunları sayıyor ve FOLLOWUP-189'a bağlıyor: `env [K=V]…`, `command`, `exec`, `time`, `nice`, `nohup`, `bash -o <seçenek> -c`, `$(…)`, ters tırnak, `{ …; }`. "`( … )` alt kabuğu denetlenir" cümlesi r2 R21 ile tutarlı. docs 9.2 tablosuna `GUARD-DERINLIK` satırı, "İç içe komutlar" paragrafına engel cümlesi eklendi. | diff; r2 R15-R21 (r3'te aynı sonuçlar) |
| 5 | MINOR-3'e dokunulmadı | Doğru. Maske davranışı r2 ile aynı (M01-M12 sonuçları değişmedi). Belge durumu N2'de. | M01-M12 |

Kapı: `py -3.12 -m pytest tests/hooks -q` **142 passed**, exit 0, 88 s → `state/evidence/fix-ajan-hooklari-r3-rv-tests.log` (HEAD satırlı). İşçinin ve koordinatörün sonucuyla aynı.
Regresyon: r2'nin 104 vakasından yalnız R13 değişti (0 → 2, beklenen). Kalan 103 vakanın çıkış kodu birebir aynı.

## NOTE

1. **Yanlış pozitif kabul edilebilir:** düz 4 düzey `sh -c` zincirinde iç komut zararsız olsa da engelleniyor (D04, D05). Fail-loud ilkesine uygun: denetlenemeyen komut geçmiyor, mesaj çözümü söylüyor ("zinciri kısalt"). Projenin gerçek tariflerinde en derin zincir 2 düzey (compose run e2e > `sh -c`) ve geçiyor. warn günü bu kuralın sayısını göstermeli.
2. **MINOR-3 belge durumu:** K-HOOK-0011'e göre MINOR-3 FOLLOWUP-189'da. docs 9.2'deki "boşlukla ayrılmış değer (`--token abc`) maskelenmez" cümlesi `curl -u user:pass` durumunu kapsıyor. JSON gövdesindeki `"token":"…"` maskesiz kalıyor ve belgede yazmıyor. FOLLOWUP-189 kaydında bu iki biçimin adıyla geçmesi yeterli.
3. **Warn günü kontrolleri hâlâ açık** (r1 N2, r2 N4): kullanıcı arayüzünde `systemMessage`; `Read` deny reddi (`//c/` biçimi); `Edit` kuralının Write'ı da kapsaması, PayCore `.env` için `Edit` satırı dahil. Merge'i engellemez.

## Kanıt
- `state/evidence/fix-ajan-hooklari-r3-rv-tests.log`: `pytest tests/hooks` 142 passed.
- `state/evidence/fix-ajan-hooklari-r3-rv-probe.log`: 112 doğrudan çağrı ve geçici kökteki maskeli kayıt dökümü.
- `state/evidence/fix-ajan-hooklari-r3-rv-probe.py.txt`: probe betiği (r1, r2 ve r3 vakaları).
