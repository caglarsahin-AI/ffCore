# fix/04a-06a-followups · review r3 (çakışma çözümü)

**Tam SHA:** a38d45842ea3e9a0aa70a841f75e5829e2254029 (baz a3a5553) · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 0.

## Statik okuma

- `runtime/events.py` `follow`: saklanan terminal olay (07f, Redis yayın hatasında) `replay_rows` üzerinden gidiyor; `transform` yalnız canlı girişlere uygulanıyor. İki mekanizma birbirini bozmuyor.
- Maske yalnız `sources` olaylarını değiştiriyor; `error` ve diğer olaylar değişmeden geçiyor.
- `_stored_payloads` ve `_mask_live_event` aynı `mask_deleted_sources` fonksiyonunu kullanıyor.

## Koşular (yığın reviewaf, SHA a38d45842ea3e9a0aa70a841f75e5829e2254029, hooks kapalı, `down -v`)

| Koşu | Sonuç |
|---|---|
| unit (af_1, af_2, af_2c, 07f_compose, 07f_follow, 04a audit fields), contract (04a openapi), integration (07f_followups incl. Redis publish hatası reconnect, 07f_sql_context_roles, af_2b, af_3, 04a_api, 04a_review_r1_ingest) + kendi [deleted] probe'um | 66 passed (log: `state/evidence/af-r3-tests.log`) |

Reconnect'te saklanan error'ın maskeden geçmediği `test_07f_2` ile kanıtlandı (yayın hatası, reconnect, error olayı gelir); probe akış yolunda maskenin çalıştığını gösteriyor.

## Notlar

- Önyüz `check:api` bu incelemede koşulmadı (NOT_RUN, koordinatörün main kapısında).
