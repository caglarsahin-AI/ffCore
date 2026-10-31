# fix/07-test-hooks-flag (FOLLOWUP-114) · review r1

**Tam SHA:** 04347ee53af100df3742507810e0b20203bd0f9c (baz e5074ab, 1 commit, 1 dosya; baz diff'inde state/ yok) · **Sınıf:** [A], yalnız test · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 1.

## Kod okuması

- `hooks` ve yeni `hooks_off` fikstürleri ortak `_with_hooks(app, settings, enabled)` ile `ffcore_test_hooks` değerini `dependency_overrides[get_settings]` ile sabitliyor. Sweep rotası `Depends(get_settings)` kullandığı için sabitleme etkili.
- `test_07f_3` artık `hooks_off` istiyor; yığının `FFCORE_TEST_HOOKS` değerinden bağımsız. Gerçek denetim 404 eşitliği: kanca bayrağı yok sayıp açık olsaydı, servis jetonlu `SWEEP` çağrısı 200 verirdi ve test kırılırdı.
- Ürün kodu değişmedi.

## Koşular (yığın review114, `down -v` ile kapatıldı; log: `state/evidence/114-run.log`)

| Koşu | Sonuç |
|---|---|
| `test_07f_followups.py`, bayrak tanımsız (varsayılan) | 4 passed |
| aynı dosya, `FFCORE_TEST_HOOKS=1` | 4 passed (önceden `test_07f_3` bu durumda kırmızıydı, R-07F-0002 MINOR-1) |
| ters sıra: `test_07f_4`, `test_07f_5` (bayraklı fikstür) sonra `test_07f_3` (`hooks_off`), bayrak 1 | 3 passed |

Ters sıra: bayraklı testlerden sonra `hooks_off` testi hâlâ kanca kapalı 404 görüyor, bayraklı fikstür sızmıyor. Normal sırada `hooks_off` testi bayraklılardan önce, ve onlar yine yeşil: kapalı fikstür ters yönde de sızmıyor.

## Bulgu

**MINOR-1, testin ilk assert'i totoloji.** `assert hooks_off.ffcore_test_hooks is False` fikstürün az önce yazdığı değeri okuyor; bir şey kanıtlamıyor. Gerçek denetim 404 karşılaştırması. Silinebilir ya da yorum satırına çevrilebilir. Küçük, bloklamaz.

## NOT_RUN

- Entegrasyon testi e2e yığınında koşturulmadı (FOLLOWUP-118): kasıtlı.
