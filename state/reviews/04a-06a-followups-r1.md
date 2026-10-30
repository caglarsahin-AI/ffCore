# fix/04a-06a-followups · review r1

**Tam SHA:** 06de43294432a8f7a666f1ededb5fb036190eb20 (4 commit, 22 dosya; state/ değişikliği yok) · **Karar:** DUZELT. BLOCKER 0 · MAJOR 1 · MINOR 0.

## Bulgu

**MAJOR-1, silinen belgenin breadcrumb'ı canlı akışta hâlâ dönüyor.** Commit `027230e` "mask deleted documents" diyor; maske `_mask_deleted_sources` ile yalnız DB'den okunan yollarda (`_replay_rows`, olay listesi) uygulanıyor. Canlı SSE yeniden bağlantısı Redis akışından okuyor (`events.follow`, `xread`) ve akış anahtarı `RUN_EVENT_STREAM_TTL_S` (varsayılan 86400 s) boyunca duruyor. Bu yolda ham breadcrumb dönüyor. Probe: belge silindi, akış anahtarı silinmedi, yeniden bağlanan istemci `['KB › M']` aldı; beklenen `['[deleted]']`. Test `test_af_2b` akış anahtarını bilerek silip yalnız DB yolunu sınıyor, bu yüzden bulgu yakalanmıyordu.

Öneri: maskeyi akış yoluna da uygulamak (Redis'ten okunan her `sources` olayında belge canlılığını kontrol edip breadcrumb'ı maskelemek) ya da akış anahtarını belge silinince kısaltmak/silmek. Test: akış anahtarı varken silinmiş belgenin breadcrumb'ı `[deleted]` olmalı (kendi probe'um: `state/reviews/af-negative-probe.py`).

## Koşular (yığın reviewaf, SHA 06de43294432a8f7a666f1ededb5fb036190eb20, `down -v`)

| Koşu | Dosyalar | Sonuç |
|---|---|---|
| unit + contract + integration | `test_af_1`, `test_af_2`, `test_04a_review_r1_audit_fields`, `test_04a_openapi`, `test_af_2b`, `test_af_3`, `test_04a_api`, `test_04a_review_r1_ingest` | 52 passed (log: `state/evidence/af-r1-tests.log`) |
| Negatif probe (kendi) | akış anahtarı varken silinmiş belge | **1 failed** (bulgu MAJOR-1) |

## Doğrulananlar

- 422 kodlu tanım hataları (`test_af_1`): `DefinitionError` kodu `validation_error` yerine yanıtta.
- Yapısal breadcrumb (`test_af_2`): başlık uzunluk sınırı, madde numarası ve ilk iki nokta korunuyor.
- Kaynak tarihi (`test_af_3`): NULL tarih sıralamada sona.

## Doğrulanmadı (NOT_RUN)

- `frontend/lib/api/schema-04a.d.ts` ile `backend/openapi/04a.yaml` eşleşmesi: önyüz tip üretimi (`check:api`) node konteynerinde koşulmadı; yalnız contract testi (`test_04a_openapi`) geçti.
