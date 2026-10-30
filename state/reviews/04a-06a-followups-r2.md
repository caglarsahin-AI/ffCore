# fix/04a-06a-followups · review r2 (delta)

**Tam SHA:** be3449fe30749c25d165e7cbc6fb17408735f453 (r1 06de432 üstüne 1 commit, 5 dosya) · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 0.

## Statik okuma

- Tek maske fonksiyonu `masked_sources` (`api/runs.py`): `selected` (DB) ve `sources` (canlı SSE) anahtarlarını aynı kuralla maskeliyor.
- Üç yol aynı fonksiyonu kullanıyor: olay listesi (`_stored_payloads`), DB'den yeniden oynatma (`_replay_rows`) ve Redis canlı akışı (`transform=_mask_live_event`). `events.follow` `transform`'u her canlı girişe uyguluyor (`events.py` 188-189).
- Belge canlılığı her okumada sorgulanıyor; silinmiş belge ya da geçersiz kimlik maskeleniyor.

## Koşular (yığın reviewaf, SHA be3449fe30749c25d165e7cbc6fb17408735f453, `down -v` ile kapatıldı)

| Koşu | Sonuç |
|---|---|
| unit (`test_af_1`, `test_af_2`, `test_af_2c_source_mask_paths`, `test_04a_review_r1_audit_fields`), contract (`test_04a_openapi`), integration (`test_af_2b`, `test_af_3`, `test_04a_api`, `test_04a_review_r1_ingest`) + kendi probe'um | 56 passed (log: `state/evidence/af-r2-tests.log`) |
| Kendi probe'um (`state/reviews/af-negative-probe.py`): akış anahtarı varken silinmiş belgenin canlı akışı | r1'de başarısızdı (`['KB › M']`), r2'de geçti (`[deleted]`) |

## Notlar

- `test_af_2b` artık akış anahtarını silmiyor; hem DB hem canlı yol aynı testte sınanıyor.
- Önyüz tip eşleşmesi (`check:api`) bu incelemede koşulmadı (NOT_RUN); koordinatör main kapısında koşacak.
- Not (kayıt): bu dosya ve R-AF-0005 satırı, koordinatörün birleştirme iptalinde (K-INIT-0026) silinmişti; 2026-10-30 21:58'de aynı içerikle yeniden yazıldı. Özgün zaman damgası kurtarılamadı.
