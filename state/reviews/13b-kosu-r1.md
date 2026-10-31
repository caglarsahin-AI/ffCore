# 13b koşu · TTL negatif testleri · review r1

**Tam SHA:** 8fd02bd49b6e394a148cc4f8302c941c6ebde53a (feat/13bk-ttl-negative, baz 3fa8a60, 1 commit, 1 dosya; state/ değişikliği yok) · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 1.

## Koşular (yığın review13bk, e2e.env örtüsü, `down -v` ile kapatıldı)

| Komut | Sonuç | İddia |
|---|---|---|
| `make seed` (ilk) | created 36, uploaded 15 | — |
| `make seed` (ikinci) | created 0, uploaded 0 (idempotent) | — |
| `make e2e` (F tablosu dahil) | **64 passed, 0 failed, 22 skipped** | 64 / 0 / 22 |
| Kendi probe'um (`state/reviews/13bk-negative-probe.py`) | 3 passed | — |

Önceki durum 62 passed / 23 skipped idi; fark tam olarak eski TTL skip'inin geçmesi ve yeni `approval_2` testi (62 + 2 = 64, 23 − 1 = 22). `13b_negative` içinde skip yok. Entegrasyon testleri bu yığında koşturulmadı (FOLLOWUP-118). Loglar: `state/evidence/13bk-seed1.log`, `13bk-seed2.log`, `13bk-e2e.log`.

Probe: (1) `now` 2000 yılında: sweep boş döner (hiçbir şey kapatmaz); (2) saat dilimsiz `now`: 422 `now_without_timezone`; (3) çözümlenemeyen `now`: 422 `validation_error`.

## Kod okuması (mutant kırılganlığı)

- `test_13b_neg_approval_1`: son kullanma saatinden 1 s önce sweep onayı `pending`, run `waiting_approval` bırakıyor; 1 s sonra `expired`, run `failed` / `approval_expired`, olay `approval_expired` ve son olay `error`; geç onay 409 `approval_not_pending`; ticket-desk `/_sent` boş; ikinci sweep aynı onayı yeniden listelemiyor.
- Okuma ile iki mutant: kanca `now`'u yok sayarsa "due" aşaması kırmızı olur (gerçek saat son kullanmadan önce); sweep süresi dolmadan kapatırsa "henüz dolmadı" aşaması kırmızı olur. Mutasyon fiilen uygulanmadı, yalnız okumayla.
- `test_13b_neg_approval_2`: kimliksiz 401 `unauthenticated`, üye oturumu 403 `service_account_required`.

## Bulgu

**MINOR-1, sweep tüm yığına etki ediyor.** Kanca `now` ile çağrılınca, o ana kadar son kullanma tarihi geçen tüm bekleyen onayları kapatıyor, yalnız testin kendi onayını değil. Test yalnız kendi `approval["id"]`'sini kontrol ediyor, bu yüzden geçiyor; ama aynı yığındaki başka bir testin bekleyen onayı sessizce kapanabilir (F2 fixture'ı bekleyen onay bırakıyor). `negative/` `scenarios/`'dan önce koşuyor, bu yüzden bugün çakışma yok. Öneri: testin docstring'ine bu yığın-geneli etkiyi yazmak ya da kanca ileride `approval_id` filtresi alsın.

## NOT_RUN

- Gerçek model / airgap: kabul edilmiş (istek metni).
- Entegrasyon testleri (FOLLOWUP-118).
