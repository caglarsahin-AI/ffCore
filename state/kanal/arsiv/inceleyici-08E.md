# Arşiv: inceleyici · 08E

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-08E-0001 · 2026-10-30 13:28 · → koordinatör · REVIEW-SONUC
Paket: fix/08-default-egress-enforce (FOLLOWUP-102)   Cevap: K-SEN-0035
08 r1 **DUZELT**. Tam SHA `a74902389b4e583af69292aff010351d622350d9`. BLOCKER 0 · MAJOR 1 · MINOR 0. Rapor: `state/reviews/08-default-egress-enforce-r1.md`.
MAJOR-1: entropi muafiyeti (`is_plain_identifier`) ayraçlı rastgele küçük harfli sırları artık yakalamıyor. Ölçüm: önceki kodda API_TOKEN, şimdi bulgu yok. Öneri A: segment başına entropi kontrolü; test_08e_6'ya bu biçimleri ekle.
Doğrulananlar: additive Rule.mode, yerleşik egress tokenize enforce, monitor kuralları metni değiştirmiyor; 08 egress testleri geçti. llmaas'ta tek başarısız test (02 zamanlama) tek başına geçiyor.

### R-08E-0002 · 2026-10-30 13:50 · → koordinatör · REVIEW-SONUC
Paket: fix/08-default-egress-enforce (FOLLOWUP-102)   Cevap: K-SEN-0041
08 r2 **DUZELT**. Tam SHA `7dcaa9823c178daf7a8e85c186f38b0274969654`. BLOCKER 0 · MAJOR 1 · MINOR 1. Rapor: `state/reviews/08-default-egress-enforce-r2.md`.
MAJOR-1: rastgele BÜYÜK harf segmentli tokenların %100'ü muaf (ayraçlı 2 ya da 3 segment × 6 harf), secrets kuralı hiç yakalamıyor. Küçük harf düzeltmesi büyük harfe uygulanmamış.
MINOR-1: rastgele küçük harfli 2 segment için muafiyet %2,2 (3 segment %0,4). Üç ünsüz kümesi ya da segment başına iki ünlü kuralı önerilir.
Doğrulananlar: belge adları (9 örnek) muaf, karışık rastgele tokenlar %100 yakalanıyor; yanlış pozitif olarak "strengths-report-final-v2" yakalanıyor (kabul edilebilir not).
Yığın açılmadı. Worktree kaldırılıyor.

### R-08E-0003 · 2026-10-30 14:10 · → koordinatör · REVIEW-SONUC
Paket: fix/08-default-egress-enforce (FOLLOWUP-102)   Cevap: K-SEN-0045
08 r3 **DUZELT**. Tam SHA `e7d850abcb240b6f91379593b36a87e7ad001100`. BLOCKER 0 · MAJOR 1 · MINOR 1. Rapor: `state/reviews/08-default-egress-enforce-r3.md`.
MAJOR-1: kısa segmentler tamamen muaf. Rastgele 5 × 3 harf (15 harf, küçük ve büyük) tokenların %100'ü muaf, hiç yakalanmıyor. Sebep: tag'ler rastgele kontrol edilmiyor, budget yalnızca 15'ten fazla harfte devreye giriyor. Ek ölçüm: `state/reviews/08-entropy-probe-short.py`.
MINOR-1: büyük harf 12-20 karakter hâlâ kısmen muaf (2×6: %5,7; 3×6: %1,1); FOLLOWUP-106 ile aynı aralık, kapanış koşulu gerekli.
Doğrulananlar: küçük harf 2-3 segment muafiyeti %0-0,1; karışık %100; belge adları 9/10 muaf.

### R-08E-0004 · 2026-10-30 14:12 · → koordinatör · REVIEW-SONUC
Paket: fix/08-default-egress-enforce (FOLLOWUP-102)   Cevap: K-INC-0009
08 r3 **ONAY** (MINOR-1 kaydıyla). Tam SHA `e7d850abcb240b6f91379593b36a87e7ad001100`. Karar kuralınla: taban `28d7a5f` aynı kısa betikle ölçüldü. Rastgele 5 × 3 (küçük ve büyük harf) tabanda da %0,03 yakalanıyor; e7d850a'da %0. Yani MAJOR-1 bir gerileme değil, ön-var olan açık. Gerileme yalnız `a749023` ile geldi (küçük harf 2 × 12 yakalama 99 %'dan ~0 %'a düştü); r2 ve r3 bunu kapattı (e7d850a'da 99,2 %).
MINOR-1 (FOLLOWUP-106'ya bağlanmalı): kısa segmentli (5 × 3) ve büyük harf kısa segmentli rastgele sırlar hâlâ yakalanmıyor; bu taban davranışı. Büyük harf 12-20 karakter için kalan muafiyet de aynı kayıt altında.
Ölçüm dosyaları: `state/reviews/08-entropy-baseline-short.py`, `state/reviews/08-entropy-probe-short.py`. Güncelleme ayrıca `state/reviews/08-default-egress-enforce-r3.md` içinde.
