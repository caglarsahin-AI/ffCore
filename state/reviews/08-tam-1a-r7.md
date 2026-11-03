# 08-tam-1a r7 ONAY-TEYIT (yalnız diff + test okuması)

- **SHA:** c9258241a411ef27393f79e10ea1cde383506b20 (33a0268 + 1 commit c925824; 6 dosya +45/-18; `state/` 0)
- **İstek:** K-08T1-0034 · Cevap: R-08T1-0013 (r6 ONAY), KARARLAR (h′)
- **Yöntem:** `git diff 33a0268..c925824` okuması; yığın yok, test koşulmadı (koordinatör talimatı). Worktree açılmadı.
- **Karar: ONAY-TEYIT** — MINOR 1 (yalnız docs), NOTE 0

## Okuma

- **Kod** (`masking.py`): `CARRIED_MAX_NUMBER = 1_000_000`. `reserve_carried` yalnız ≤ 1.000.000 olan taşınan numaraları ayırıyor (`n <= CARRIED_MAX_NUMBER`). Verme sınırı `PLACEHOLDER_MAX_NUMBER = 9_999_999` ve yer tutucu deseni `[0-9]{1,7}` değişmedi. KARARLAR (h′) ile birebir: taşınan 7 haneli numara kapsamı artık tüketemez; yok sayılan numarayla çakışma için bir kapsamın 1 milyondan fazla değer vermesi gerekir.
- **Testler:**
  - `test_08t_r6_carried_numbers_above_one_million_are_ignored`: `9999999` → `<<PII_1>>`, `1000001` → `<<PII_1>>`, `1000000` → `<<PII_1000001>>`, `999999` → `<<PII_1000000>>`. Sınırın iki yanı kapsanıyor; r6 MINOR-r6-1 senaryosu (`<<PII_9999999>>`) artık konuşmayı düşürmüyor.
  - Verme sınırı testleri artık sınırı `store.reserve(…, 9_999_999)` ile kuruyor, çünkü taşınan metin onu dolduramıyor.
  - `test_08t_m2_history`: gerçek Redis'te `<<PII_9999999>>` ve `<<PII_1000001>>` yankısı geçmişte duruyor; ilk değer `<<PII_2>>`.
- **Yorum:** `PLACEHOLDER_MAX_CHARS` yorumu 7 haneye göre güncellenmiş (r6 NOTE-2 kapandı). agentlar.md "up to 8 digits" ifadesi düzeltilmiş (r6 NOTE-1'in yarısı kapandı).

## MINOR-r7-1 · İki docs cümlesi artık kodla çelişiyor

- `docs/api.md:540`: "…past 9,999,999, e.g. the request carries `<<PII_9999999>>` and a new value…"
- `docs/guardrail.md:128` (`tokenize` satırı): "A scope that would issue past 9,999,999 (a carried `<<PII_9999999>>` and a new value) fails loudly…"

(h′) ile taşınan `<<PII_9999999>>` yok sayılıyor; yeni test de bunu iddia ediyor (`<<PII_1>>`). Örnek, örneğin "a scope that has issued 9,999,999 values" biçiminde düzeltilmeli. Merge'ü engellemez. Merge öncesi tek satırlık docs commit'i ya da main'de küçük bir düzeltme; koordinatörün kararı.

## Sonuç

ONAY-TEYIT. Merge + main kapısı koordinatörde.
