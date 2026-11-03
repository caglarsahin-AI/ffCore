# 08-tam-1a r6 inceleme (kısa delta, r5 DEGISIKLIK kapanışı)

- **SHA:** 33a0268f66bacde2cd57204e942b62b0ea2385cb (feat/08-tam-1-ner; 60f2250 üstüne 6 commit, 17 dosya +225/-81, `state/` 0)
- **İstek:** K-08T1-0030 · Cevap: R-08T1-0011 (r5), K-08T1-0028 (DUZELT)
- **Kararlar:** KARARLAR "C17 HTML kuralı, düzeltmeler" (g)-(i)
- **İnceleyici worktree:** `.worktrees/review-08t1a-r6` (temiz; 06b-2 probe'u tek dosya mount ile koşuldu, mount noktası silindi)
- **Yığın:** tam yığın review08t1a, 18290/13290, `--pull never`, hepsi healthy. Yığın kararı benim: probe'lar Redis'e ve yeni kodlu backend konteynerine ihtiyaç duyuyordu.
- **Karar: ONAY** — BLOCKER 0, MAJOR 0, MINOR 1, NOTE 3

r5'in MAJOR'ı kapandı: kuyruk probe'unun bütün tablosu iki yolda 3/3; rastgele parçalamada 0/200 değer kaybı (r5'te 97/200). (h) taşınan 8 haneli ve Unicode rakamlı numaralarda konuşmayı koruyor; (i) docs doğru. Kalan tek MINOR kararın kendisinde: yok sayma eşiği verme üst sınırıyla aynı yerde olduğu için 7 haneli `<<PII_9999999>>` aralığı yine tüketiyor. Önerim merge öncesi küçük bir commit (karar gerekir); MAJOR değil, ONAY'ı engellemiyor.

## r5 bulgularının kapanışı

| r5 | Durum | Kanıt |
|---|---|---|
| MAJOR-r5-1 kuyruk penceresi | **KAPANDI** | r5 kuyruk probe'u bu SHA'da (`08t1a-r6-tail-probe.log`): 1-11 karakterlik parçalarda tek parça, facade düz akış ve konsol canlı, hepsi 3/3; rastgele 1-6 karakterlik girdilerde **0/200** cevap değer kaybetti. `<PII_1 style…` (r4-3) tek parça ve akışta tutuldu; r4'ün yedi adversarial yazımı hâlâ tutuluyor (`08t1a-r6-rerun-r4-adv-probe.log`: 0 açılma). İşçinin `test_08t_r5_tail.py` testi probe'un tablosunu birebir koşuyor. |
| MINOR-r5-1 (h) | **KAPANDI** (8+ hane, Unicode) / kenar: MINOR-r6-1 | Gerçek Redis (`08t1a-r6-probe.log`): taşınan `<<PII_99999998>>`, `<<PII_٩٩٩٩٩٩٩٩>>` ve `<<PII_10000000>>` → değerler `<<PII_1>>`, `<<PII_2>>`, `<<PII_3>>` (konuşma çalışıyor). |
| MINOR-r5-2 (i) docs | **KAPANDI** | guardrail.md, agentlar.md ve api.md: kapsam "okuyucunun akışının geri kalanı", turlar arası sıfırlanmaz, onay sonrası `prime`; bedel konsol sahibine de; tetikleyici listesi (`<br>`, `List<String>`, `#include <stdio.h>`, `Bearer <token>`, `<your-email>`, `x<y`); konsola muafiyet yok ve gerekçesi. |
| MINOR-r5-3 bayat metin | **KAPANDI** | Test docstring'leri ve adları cevap/akış düzeyi kurala göre; PR r1-r4 satırlarında tarihçe notları. |
| MINOR-r5-4 | **KAPANDI** | `/internal/guardrails/evaluate` 400 `placeholder_out_of_range`: kod docstring'i, `openapi/08.yaml` yeniden üretildi, `test_08_api.py` (+34). api.md:540 tamponlu/canlı akışta hata olayı + `[DONE]`. guardrail.md "işaretli ya da açık satır kesilirse". |
| NOTE-1 `exc_info` | **KAPANDI** | `runs.py:302` |
| NOTE-2 replay `after` | **KAPANDI** | guardrail.md'de yazılı ("When the live stream has expired…") |
| NOTE-7 bütçe | **KAPANDI** | CPU süresiyle ölçülüyor (07c17ee); `make test` iki profilde yeşil. |

## İşçinin 1-7 hane uygulaması (K-08T1-0030 madde 2)

`PLACEHOLDER = <<PII_[0-9]{1,7}>>`, verme üst sınırı 9.999.999. Değerlendirme:

- **C17 biçimiyle tutarlı mı: EVET.** Hiçbir kapsam 8 haneli numara vermez; 8+ haneli ya da ASCII olmayan rakamlı `<<PII_n>>` hiçbir yerde yer tutucu değil. Bu da karar (h)'nin "10.000.000'dan büyük numara ayrılmaz ve açılmaz" hükmünü en basit yoldan sağlıyor. Hizalayıcı (`_OPEN_PLACEHOLDER` 8 hane) ve HTML istisnası (`{1,8}`) 8 haneyi tutmaya devam ediyor. Bu yalnız fazla bekletme ya da zararsız istisna demek: `<PII_12345678>>` özniteliksiz bir öğe.
- **Sayaç 9.999.999'da fail-loud mu: EVET.** Taşınan `<<PII_9999990>>` → 9.999.991, 92, 93; taşınan `<<PII_9999999>>` → ilk değer `PlaceholderOutOfRange: placeholder_out_of_range`.
- **Sızıntı ya da yanlış atıf yönü: YOK.** Bir kapsamın 8 haneli eşlemesi oluşamaz, bu yüzden metindeki 8 haneli `<<PII_n>>` hiçbir değere çözülemez. Önde sıfırlı 7 haneli (`<<PII_0000001>>`) numara 1 olarak ayrılıyor; verilen yer tutucu `<<PII_1>>` olduğu için ona çözülmüyor. Fazla ayırma, zararsız.
- **Kalan kenar:** MINOR-r6-1.

## Yeni bulgular

### MINOR-r6-1 · Yok sayma eşiği verme üst sınırıyla aynı yerde; taşınan 7 haneli numara aralığı yine tüketiyor (karar (h)'nin kendisinde) — CONFIRMED (gerçek Redis)

Karar (h): eşiğin (10.000.000) altındaki taşınan numara ayrılır, sayaç eşiğe ulaşırsa fail-loud. İkisi aynı sınırda olduğu için taşınan `<<PII_9999999>>` sayacı sona itiyor ve ilk yeni değer düşüyor. `<<PII_9999990>>` yalnız 9 değere izin veriyor. Bu, r4 MINOR-r4-2 ve r5 MINOR-r5-1'in bir hane aşağı kaymış hâli: kullanıcının yazdığı ya da belgeden yankılanan 7 haneli bir numara konuşmayı kalıcı düşürüyor.

**Öneri (koordinatör kararı, iki satır):** yok sayma eşiği verme sınırının çok altına alınsın: **1.000.000'dan büyük taşınan numara yok sayılsın, verme üst sınırı 9.999.999 kalsın.**
- Tükenme ancak bir koşunun 9 milyon değer vermesiyle olur.
- Yok sayılan numarayla çakışma ancak 1 milyon değerle olur.

İkisi de gerçekte olamaz. Taşınan aralık nereye kadar giderse gitsin, ayırma ile sınır arasında her zaman büyük bir boşluk kalır. Test: `<<PII_9999999>>` ve `<<PII_1000000>>` taşınınca değerler `<<PII_1>>`'den başlar; `<<PII_999999>>` taşınınca `<<PII_1000000>>`.

Merge öncesi küçük bir commit önerilir. MAJOR değil, çünkü sızıntı ya da yanlış atıf yok; etki erişilebilirlik ve kasıtlı tetikleme gerektiriyor.

## NOTE

1. guardrail.md (`tokenize` satırı) ve agentlar.md:93 hâlâ "every placeholder number (up to 8 digits)" diyor; artık 7. guardrail.md "from 10,000,000 (any 8 or more digits)" ifadesi önde sıfırlı numarada tam doğru değil (`<<PII_01234567>>` 8 hane, değeri 1.234.567; yer tutucu sayılmıyor, zararsız).
2. `PLACEHOLDER_MAX_CHARS = 16` yorumu "up to 8 digits" diyor; hizalayıcı 8 haneyi tutuyor, yer tutucu en çok 7. Tutarlı ama yorum güncellenebilir.
3. Akışta `<PII_12345678>>` ve `x<PII_1>>` (tek `<`) parçalı gelirse, `>>` henüz pencerede olmadığından etiket sayılıp akışın kalanı tutulabiliyor (probe: tek parça açıldı, 3'lük akış tuttu). Gerçek yer tutucular `<<…>>` olduğu ve hizalayıcı onları bütün verdiği için etkilenmiyor. Fail-closed, zararsız.

## Güvenlik turu

- **Sıfır tık:** r1-r5 yazımlarından açılan yok (r4 adversarial bu SHA'da 0 açılma); (g) istisnası etiket kaçırmıyor (`<PII_1 style` tutuldu).
- **Kişi verisinin karışması:** 8+ haneli ve Unicode rakamlı numaralar hiçbir kapsamda çözülmüyor.
- **Erişilebilirlik:** MINOR-r6-1.
- **06b-2 SSRF ve 147:** 06b-2 probe'u ve `test_06b2_external_agent.py` hedefli test-int içinde iki profilde yeşil.
- **S8:** değişmedi.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | 1525 passed (2:37) | `state/evidence/08t1a-r6-unit-llmaas.log` |
| `make test` airgap | 1525 passed (2:20) | `08t1a-r6-unit-airgap.log` |
| Hedefli test-int llmaas (`test_08t_*`, `test_08_api`, `test_06b2_external_agent`, 06b-2 SSRF probe) | 116 passed | `08t1a-r6-int-targeted-llmaas.log` |
| Aynısı airgap | 116 passed | `08t1a-r6-int-targeted-airgap.log` |
| Kuyruk probe'u (r5) bu SHA'da | 3/3 her biçim, 0/200 kayıp | `08t1a-r6-tail-probe.log` |
| r6 sınır + HTML istisnası probe'u (gerçek Redis) | yukarıda | `08t1a-r6-probe.log`, `state/reviews/08-tam-1a-r6-probe.py` |
| r4 adversarial probe'u bu SHA'da | 0 açılma | `08t1a-r6-rerun-r4-adv-probe.log` |
| Tam `make test-int` | NOT_RUN: kısa delta turu, koordinatör hedefli test-int'i yeterli saydı; tam kapı merge sonrası ffmain'de koordinatörde | — |
| lint | NOT_RUN: işçi kanıtı "lint 0" | — |

## Sonuç

ONAY. MINOR-r6-1 için koordinatör kararı: merge öncesi iki satırlık eşik düzeltmesi (önerilen) ya da FOLLOWUP-162. NOTE 1-2 docs ve yorum düzeltmeleri aynı commit'e eklenebilir.
