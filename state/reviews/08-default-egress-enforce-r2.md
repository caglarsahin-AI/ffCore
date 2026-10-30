# 08 · fix/08-default-egress-enforce · review r2 (delta)

**Tam SHA:** 7dcaa9823c178daf7a8e85c186f38b0274969654 (r1 a749023 üstüne 1 commit) · **Karar:** DUZELT. BLOCKER 0 · MAJOR 1 · MINOR 1.

## Ölçüm (tools imajı, `is_plain_identifier` ve `find_secrets`, tohum 11, 4000 örnek)

| Biçim | Muaf (exempt) | Secrets tarafından yakalanan |
|---|---|---|
| rastgele küçük harf, 2 segment × 12 | 2,2 % | 97,1 % |
| rastgele küçük harf, 3 segment × 12 | 0,4 % | 99,7 % |
| **rastgele BÜYÜK harf, 2 segment × 6** | **100 %** | **0 %** |
| **rastgele BÜYÜK harf, 3 segment × 6** | **100 %** | **0 %** |
| rastgele karışık (harf+rakam), 3 segment × 12 | 0 % | 100 % |

Belge adları (örnekler): `SZL-2025-003_temizlik-hizmet`, `SZL-2024-011_cihaz-bakim`, `SZL-2025-007_laboratuvar-kiti`, `SZL-2025-012_yonetim-danismanlik`, `SZL-2023-019_yazilim-lisans`, `PRSIM-1234_kullanici-talebi`, `HBYS-2024_hasta-kayit-prosedur`, `yonetim-danismanlik-sozlesmesi`, `temizlik-hizmet-raporu-2025`: hepsi muaf, hiçbiri yakalanmıyor. Yanlış pozitif: `strengths-report-final-v2` yakalanıyor ("ngths" dört ünsüz kümesi); kelime ölçütünün İngilizce kelimeye kısmen uyumsuzluğu.

## Bulgular

**MAJOR-1, büyük harf tokenları tamamen muaf.** `_is_plain_segment` büyük harfli ≤6 harf segmentini sözcük ya da kod sayıyor ve ünlü/ünsüz ölçütünü uygulamıyor. Rastgele büyük harf segmentlerinden oluşan bir sır (örnek: `KQZXWP-LMRTYB-QWERTY`) hiç yakalanmıyor. Sınıf [B] yerleşik politikada yalnız monitor olduğu için varsayılan kurulumda blok yok; ama `secrets` kuralı enforce edilmiş bir politikada bu bir sızıntı. Öneri: büyük harf segmenti için de sözcük ölçütü (kod biçimi için ayrı, sıkı bir sınır: örneğin tek segment ≤4 harf ve en fazla iki segment; belge adı kalıbı `[A-Z]{2,6}-\d{4}` gibi açık bir desen) ya da büyük harf tamamen rastgele kabul edilip entropi kontrolüne bırakılsın. Test: büyük harf ayraçlı rastgele tokenlar `test_08e_6` içinde yakalanmalı.

**MINOR-1, küçük harf artığı.** Ölçümde 2 segmentli rastgele küçük harfli tokenların yaklaşık %2'si hâlâ muaf (3 segmentte %0,4). Sözcük ölçütü ünsüz kümesini dört ünsüzle sınırlıyor; üç ünsüz kümesine ya da segment başına en az iki ünlü kuralına çekmek bu oranı düşürür. Kabul edilebilir ama takip edilmeli.

## Doğrulananlar

- Ünlü payı ve ünsüz kümesi ölçütü belge adlarını (9 örnek) ve sayı/kısa etiket segmentlerini muaf tutuyor.
- Karışık harf-rakam rastgele tokenlar %100 yakalanıyor.
- `Rule.mode` ve yerleşik egress kuralı r1'de doğrulandı; bu r2 onları değiştirmiyor (3 dosya, yalnız `rules.py` ve test/doc).
