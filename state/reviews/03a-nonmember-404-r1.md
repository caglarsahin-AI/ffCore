# 03a non-member 404 · review r1

**Tam SHA:** 8d3cb3bfde871165f49e088e8d6a7e07b29d329f (b80c8c9 + 8d3cb3b; state/ değişikliği yok) · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 0.

## Statik okuma (`core/auth.py`)

- `HIDDEN_PROJECT = (no_project, not_member)`: üye olmayan ve olmayan proje aynı `404 project_not_found` gövdesini alıyor.
- Üye ama rolü yetmeyen çağrı 403 `insufficient_role` olarak kalıyor.
- Gerçek sebep (`not_member`, `no_project`) yalnız denetim kaydında (`after.reason`), yanıtta yok.
- Süper admin ve OBO yolu: süper admin dalı ve `via_service` kısıtı değişmedi; yalnız eksik-proje kodu birleşti.

## Koşular (yığın review03anm, SHA 8d3cb3b, `down -v` ile kapatıldı)

| Koşu | Sonuç |
|---|---|
| `tests/integration/test_03a_nonmember_404.py`, `test_03a_access.py`, `test_03a_obo_scope.py` | 102 passed (çıkış 0; log: `state/evidence/03anm-r1-int.log`) |
| Negatif probe (`state/reviews/03anm-negative-probe.py`, 12 test) | 12 passed |

Probe iki şeyi ekliyor: (1) bozuk proje kimliğinde üye ve üye olmayan aynı durum/gövde; (2) yabancı ve olmayan proje GET yanıtları bayt-bayt eşit ve `NOT_FOUND`.

## Gözlem

Tenant düzeyi rotalar (proje kimliği taşımayan) üye olmayana 403 `insufficient_role` veriyor; proje varlığı sızdırmıyor. Kabul edildi.

## Worktree

`.worktrees/review-03anm-r1`: koşudan sonra değişiklik yoktu; `git worktree remove` "Permission denied" verdi, git kaydı kaldırıldı, dizin kalmış olabilir. Zorla silinmedi.
