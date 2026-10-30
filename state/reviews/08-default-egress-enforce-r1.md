# 08 · fix/08-default-egress-enforce · review r1

**Sınıf:** [B] · **Tam SHA:** a74902389b4e583af69292aff010351d622350d9 · **Baz:** main 28d7a5f
**Karar:** DUZELT. BLOCKER 0 · MAJOR 1 · MINOR 0.

## Doğrulananlar

- `Rule.mode` additive (varsayılan None; mevcut politikalar kendi modunu izler). Yerleşik sürüm 1 → 2.
- Yerleşik politikada yalnız egress PII tokenize kuralı enforce; diğerleri monitor. Monitor kuralları metni değiştirmiyor ve bloklamıyor (engine: değişiklik ve blok yalnız `mode == "enforce"` dalında).
- Testler (tools imajı, `--env-file .env.test`): lint temiz; `pytest tests/unit tests/contract` airgap 663 passed; llmaas 662 passed, 1 failed. Tek başarısız test `test_02_r1_m3_child_process_exits_by_itself` (02 kapsamı, zamanlamaya bağlı); tek başına çalıştırınca geçti. 08 egress testleri (`test_08_egress_enforce.py`, 5 test ve entropi parametreleri) geçti.

## Bulgu

**MAJOR-1, sır tespitinde atlatma.** `is_plain_identifier` tüm `-`/`_` ayraçlı parçaların rastgele harflerden oluşan küçük harf (ya da büyük harf) segmentleri olmasını yeterli sayıyor. Sonuç: ayraçlı rastgele küçük harfli bir sır artık sır olarak yakalanmıyor. Ölçüm (tools imajı, aynı girdi):

| Girdi | 28d7a5f (önceki) | a749023 (bu değişiklik) |
|---|---|---|
| `kemubcrdlsbq-gbcnnchcrnbs-dhuusbssmbhb` (rastgele küçük harf, ayraçlı) | API_TOKEN | **bulgu yok** |
| `J2isAjIhKtJ0-RlgLKOmxgJTe-KdNnFRIBXuDL` (karışık, ayraçlı) | API_TOKEN | API_TOKEN |
| `SZL-2025-003_temizlik-hizmet` (belge adı) | API_TOKEN (yanlış pozitif) | bulgu yok (düzeltme amacı) |

Yani değişiklik belge adındaki yanlış pozitifi çözerken, rastgele küçük harfli sırları da kaçırıyor. Yerleşik politika monitor olduğu için varsayılan kurulumda blok yok; ama `secrets` kuralı enforce edilmiş herhangi bir politikada sızıntı olur. Kapsam gerekçesi (K-SEN-0032) bu durumu kapsamıyor.

Öneri (seçenekler, önerilen **A**):
- **A (önerilen):** ayırıcılı değerde her harf segmenti için ayrı entropi kontrolü; segment entropisi eşik üstünde ise yakala. Belge adları (kısa ya da düşük entropili kelime segmentleri) yine geçer.
- **B:** muafiyeti yalnızca bilinen belge adı biçimine (büyük harf etiketi + rakam kümesi) sınırla. Daha dar, ama yeni belge adı biçimleri yanlış pozitif üretebilir.
- **C:** muafiyeti kaldır, yanlış pozitifleri politika düzeyinde (yerleşik kural için allowlist) çöz. Kod karmaşıklığı az, ama belge adları yine yanlış pozitif olur.

Test eklenmesi gereken durum: ayraçlı rastgele küçük harfli ve büyük harfli sır biçimleri `test_08e_6` içinde yakalanmalı.

## Kalan riskler

- llmaas koşusundaki `test_02_r1_m3` zamanlama testi yük altında kırılgan (02 kapsamı, ayrı takip önerisi).
