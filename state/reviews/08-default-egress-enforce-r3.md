# 08 · fix/08-default-egress-enforce · review r3 (delta)

**Tam SHA:** e7d850abcb240b6f91379593b36a87e7ad001100 (r2 7dcaa98 üstüne 1 commit) · **Karar:** DUZELT. BLOCKER 0 · MAJOR 1 · MINOR 1.

## Ölçüm (aynı üreteç, tohum 11, 4000 örnek)

`state/reviews/08-entropy-probe.py` (r2 tablosu, yeni SHA):

| Biçim | Muaf | Yakalanan |
|---|---|---|
| rastgele küçük harf 2 × 12 | 0,1 % | 99,2 % |
| rastgele küçük harf 3 × 12 | 0,0 % | 100 % |
| rastgele BÜYÜK harf 2 × 6 | **5,7 %** | 0 % |
| rastgele BÜYÜK harf 3 × 6 | **1,1 %** | 0 % |
| karışık harf+rakam 3 × 12 | 0 % | 100 % |

Belge adları (10 örnek): 9'u muaf, `strengths-report-final-v2` yakalanıyor (önceki not). Belge adı davranışı değişmedi.

Ek ölçüm: `state/reviews/08-entropy-probe-short.py` (tohum 11, 4000):

| Biçim | Muaf | Yakalanan |
|---|---|---|
| **rastgele küçük harf 5 × 3 (15 harf)** | **100 %** | 0 % |
| **rastgele BÜYÜK harf 5 × 3 (15 harf)** | **100 %** | 0 % |
| rastgele BÜYÜK harf 4 × 4 | 0,4 % | 0 % |

## Bulgular

**MAJOR-1, kısa segmentler tamamen muaf.** `_TAG` 1-3 harfli her küçük ya da büyük harf segmentini tag sayıyor ve yalnızca 3 ya da daha fazla segmentte, ve yalnızca 15 harften fazlasında (`> MAX_UNVERIFIED_LETTERS`) muafiyeti kapatıyor. Sonuç: 15 harfe kadar tamamen rastgele bir sır (yaklaşık 70 bit) hiç yakalanmıyor; 15 harf tam sınırda kaldığı için bile geçiyor. Tag'lerin rastgele olup olmadığına bakılmıyor. Öneri: tag harfleri toplamını düşük bir üst sınırla sınırlamak (örneğin en çok 6 harf), ya da tag için bilinen liste (`kdv`, `v2`, `q3` gibi) ve segment sayısı sınırı kullanmak; ayrıca en az iki kısa segment olan tokenlarda entropi kontrolünü sürdürmek. Test: 5 × 3 küçük ve büyük harf tokenları `test_08e_6` içinde yakalanmalı.

**MINOR-1, büyük harf 12-20 karakter (bilinen açık).** 2 × 6 büyük harf tokenların %5,7'si, 3 × 6 olanların %1,1'i hâlâ muaf. Bu, işçinin belirttiği FOLLOWUP-106 ile aynı aralık; takip kaydı olduğu için bloke etmiyor, ama MAJOR-1 düzeltmesi bu aralığı da kapatmalı ya da FOLLOWUP-106'da kapanış koşulu yazılı olmalı.

## Doğrulananlar

- Küçük harf 2 ve 3 segment: muafiyet %0,1 ve %0, yakalama %99-100.
- Karışık harf-rakam: %100 yakalanıyor.
- Belge adları: 9/10 muaf.

## Güncelleme (K-INC-0009): taban ölçümü ve karar

Taban (`28d7a5f`, exemption öncesi) aynı kısa betikle: `state/reviews/08-entropy-baseline-short.py` (tohum 11, 4000):

| Biçim | Taban yakalanan | e7d850a yakalanan | Değişim |
|---|---|---|---|
| küçük harf 5 × 3 | 0,03 % | 0 % | yok (taban da yakalamıyor) |
| BÜYÜK harf 5 × 3 | 0,03 % | 0 % | yok (taban da yakalamıyor) |
| küçük harf 2 × 12 | 99,1 % | 99,2 % | yok (regresyon yok) |
| BÜYÜK harf 2 × 6 | 0 % | 0 % | yok (taban da yakalamıyor) |

Sonuç: MAJOR-1 (kısa segmentler) bir **gerileme değil**; taban da bu biçimleri yakalamıyordu. Gerileme yalnız `a749023` ile geldi (küçük harf 2 × 12 yakalama 99 %'dan ~0 %'a düştü); r2 ve r3 bunu kapattı (e7d850a'da 99,2 %). Bu nedenle karar: **ONAY, MINOR-1 kaydıyla** (FOLLOWUP-106 kapsamı). Kısa segmentli ve büyük harf kısa segmentli rastgele sırlar tabanda da yakalanmıyor; bu bir ön-var olan açık, değişikliğin sebep olduğu bir bozulma değil.
