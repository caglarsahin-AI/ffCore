# 18-cost-timing · review r1

**Paket:** 18 takip, FOLLOWUP-76 (fix/18-cost-timing) · **Sınıf:** [A] (yalnız test) · **Baz:** main 87173d7
**İncelenen tam SHA:** 2ea56d213cb37bd7cb5871093413688cfc0b477c (tek commit, tek dosya `backend/tests/unit/test_08_cost.py`, +32/-19)
**İnceleyen:** inceleyici oturumu (bu incelemede yalnız detached worktree `.worktrees/review-18ct-r1`, kaldırıldı)

## Karar

**ONAY.** BLOCKER 0 · MAJOR 0 · MINOR 2.

## Komutlar ve çıkış kodları

| Komut | Ortam | Sonuç |
|---|---|---|
| `python -m pytest tests/unit/test_08_cost.py -k repeated_value -q -p no:cacheprovider` | `ffcore/tools:0.0.0-18ct`, worktree `/work`, `PYTHONPATH=/work/backend` | 3 passed, 4 deselected, çıkış 0 |
| aynı komut, 5 tekrar | aynı | 5/5 koşuda 3 passed |
| `ruff check tests/unit/test_08_cost.py` | aynı imaj | All checks passed |
| `ruff format --check tests/unit/test_08_cost.py` | aynı imaj | already formatted |

Profil matrisi çalıştırılmadı: dosyada `DEPLOY_PROFILE` ya da profil dalı yok (grep 0). Tam `make test` ve `make test-int` bu incelemede koşulmadı; kapsam test dosyası ve `-k repeated_value` seçimiyle sınırlı (K-SEN-0019 kararı). Yığın açılmadı.

## Duyarlılık (ölçüm yöntemi, ürün kodu değil)

Oran eşiğinin kare regresyonunu ayırıp ayırmadığını ölçmek için repo dışında bir yardımcı betik, aynı yöntemi (en iyi-of-3 `time.process_time`, N=1000 ve N=10000, eşik 25) Linux konteynerinde çalıştırdı:

- doğrusal fonksiyon: oran 7,7
- kare fonksiyon (önek her adımda yeniden taranıyor): oran 71,5

Ürün `evaluate` yoluna kare regresyon enjekte edilmedi. Bu yüzden "ürün kodundaki kare regresyon testte kırmızı olur" iddiası yalnız yöntem düzeyinde kanıtlandı; ürün mutasyonu NOT_RUN.

## Bulgular

**MINOR-1, istisna gizleniyor.** `run_evaluate` içindeki iş parçacığı istisnayı yakalamıyor. `evaluate` hata verirse `result` boş kalır ve test asıl hatayı değil `KeyError` gösterir. Öneri: `target` içinde `try/except` ile hatayı `result["error"]`'a yazıp çağıranda yeniden fırlatmak. Kalıp önceki sürümden devralındı.

**MINOR-2, N=10000 için mutlak tavan kalktı.** Eski sürüm N=10000 maskeleme testinde 1,0 s CPU tavanı koyuyordu; yeni sürümde bu test yalnız 10 s duvar saati asılı kalma korumasını taşıyor. N=10000 maliyet koruması artık yalnız `test_08_9_cost_scales_linearly` oranına dayanıyor. K-SEN-0015 kararıyla uyumlu ve docstring'de yazılı; PR notunda bu sınır açıkça belirtilmeli.

## Kalan riskler

- Oran eşiği iki ölçüm arasında yaklaşık üç kat marj bırakıyor (doğrusal ölçümler 6,4–8,4; kare beklenen ~70–100). Yük altında yeniden koşulursa marj daralabilir; bu worker'ın yük testiyle tutarlı.
- Ürün yolunda kare regresyon mutasyon kanıtı yok (yukarıda NOT_RUN).
