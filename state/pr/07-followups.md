# PR: fix/07-followups

**Paket:** fix/07-followups (FOLLOWUP-104 + 111 + 113) · **Sınıf:** [A] · **Branch:** fix/07-followups · **Baz commit:** c8650cb · **GOREV:** K-07F-0001 · **Oturum:** ffcore-isci-b-07fu

## Plan (kısa, kodlamadan önce)

1. **Bulunan semboller:**
   - `backend/ffcore/runtime/events.py`: `RunEventWriter.record` satırı commit eder, sonra `_publish` (xadd + expire) yapar. `follow()` akış anahtarı varsa yalnız Redis'i okur ve DB'ye hiç bakmaz; anahtar yoksa `replay_rows` kullanır.
   - `backend/ffcore/api/runs.py`: `_stream`, `_replay_rows(project_id, run_id)` (saklı satırları SSE'ye çevirir; tamamlanan run'a `done` ekler).
   - `backend/ffcore/services/approvals.py`: `run_closer` (run `failed` + `approval_expired` + `error` sse), `expire_due` (idempotent, onay başına transaction), `sweep(settings, now=)`.
   - `backend/ffcore/runtime/runner.py`: `_stop` (durum commit → `record(error, sse)`) ve `_complete` (commit → `live(done)`); `INFRASTRUCTURE_ERRORS`.
   - `backend/ffcore/runtime/worker.py` `expire_approvals` (arq cron).
   - `backend/ffcore/api/internal.py` `ServiceActor`; `api/tools_internal.py` (`/api/v1/internal/...` kalıbı).
   - `backend/ffcore/api/tools.py:313` `sql_context` (`AnyMember`).
   - `tests/unit/test_03a_write_flag.py` `WRITE_EXEMPT` (`sql_context` "POST olan okuma" diye listede).
   - `tests/integration/test_07_flow.py` (`_waiting`, `tick`, `events`, `run_row`).
2. **Kapsam / kapsam dışı:**
   - Kapsam: 104 (DB'ye yazılmış ama Redis'e ulaşmamış terminal olay okuyucuya gelir), 111 (bayraklı süpürme kancası), 113 (karar bekliyor, aşağıda).
   - Kapsam dışı: Redis'in tamamen düşmesi durumunda `follow()` (xread hata verir; o 06a altyapı davranışı), C9'a yeni tip.
3. **Değişecek dosyalar ve neden:**
   - **Dilim 1 (104):** `runtime/events.py` `follow()` yeni zorunlu parametre `finished` (async, run terminal mi). Keepalive turunda (yeni girdi yok) run bitmişse `replay_rows(<son görülen seq>)` ile kalan satırları verir ve biter. Böylece `run_closer`, `_stop` ve `_complete` yazıcılarının üçü de kapsanır. DB tarafı zaten doğru: satır ve `failed`/`completed` durumu, xadd'den önce commit edilir. Yazıcıya dokunulmaz. `api/runs.py` `_stream` `finished`'i verir (tek satır DB sorgusu, `FINISHED`). C9 değişmez.
   - **Dilim 2 (111):** `core/config.py` `test_hooks: bool = False` (env `FFCORE_TEST_HOOKS`). `api/approvals.py`'ye `POST /api/v1/internal/approvals/sweep?now=<ISO, tz zorunlu>` eklenir:
     - yalnız servis hesabı (`ServiceActor`);
     - bayrak kapalıysa 404 `not_found` (yol yokmuş gibi);
     - `include_in_schema=False` (üretim sözleşmesinde yok, docs'ta yazılı);
     - `services/approvals.sweep` çağrılır, `{expired: n}` döner;
     - idempotent (`expire_due` koşullu).

     `sweep` artık expire edilen listeyi döner (additive). `WRITE_EXEMPT`'e `sweep_approvals` (servis hesabı, rol yok). `docs/onaylar.md` bölümü.
   - **Dilim 3 (113):** KARAR-GEREK B-07FU-0004 sonucuna göre.
4. **Sözleşme, yapılandırma, profil etkisi:**
   - C9 aynı; yeni env `FFCORE_TEST_HOOKS` (varsayılan kapalı, compose app-env'e eklenmez; 13b kendi e2e env'inde açar).
   - `.env.example`'a tek satır açıklama: touch-zone eki talebi.
   - Profil farkı yok; testler iki profilde.
5. **Kabul kriteri → test:**

   | # | Kriter | Test |
   |---|---|---|
   | 1 | Canlı girdi kaybolsa da okuyucu DB'deki terminal olayı alır ve akış biter | `test_07f_1_follow_ends_from_db_when_live_entry_lost` (unit, sahte redis) |
   | 2 | TTL kapanışında `error` xadd'i düşerse: run `failed`, `error` satırı DB'de, Last-Event-ID ile reconnect `error` alır | `test_07f_2_expired_close_redis_publish_fails_reconnect_gets_error` (entegrasyon, xadd ilk olaydan sonra monkeypatch ile düşer) |
   | 3 | Bayrak kapalıyken kanca 404 | `test_07f_3_sweep_hook_404_when_flag_off` |
   | 4 | Bayrak açık, `now` ileri: süresi geçen onay `expired`, run `failed`; ikinci çağrı 0 | `test_07f_4_sweep_hook_expires_and_is_idempotent` |
   | 5 | Konsol oturumu (admin) 403 `service_account_required`; tz'siz `now` 422 | `test_07f_5_sweep_hook_service_only_and_tz` |
   | 6 | 113 | karara göre |

6. **Migration:** yok.
7. **Geri alma:** commit revert; bayrak varsayılan kapalı.
8. **Durma koşulları:**
   - `follow()` değişikliği 06a SSE sözleşme testlerini (C9, reconnect) kırarsa dururum.
   - 13b'nin e2e konteyneri servis jetonunu taşımıyorsa koordinatöre bildiririm (kanca HTTP olduğu için).
9. **Felsefe kontrolü:**
   - **ARCH-07:** üç küçük düzeltme. 104'te SSE okuyucusuna bir sorgu eklenir (keepalive başına bir sorgu, yalnız boş turlarda). Kalıcı karmaşıklık düşük.
   - **ARCH-09:** mevcut `replay_rows` ve `expire_due` yeniden kullanılır; ikinci kapanış yolu yok.
   - **ARCH-10/06:** kanca açık bayrakla, varsayılan kapalı. Kapalıyken 404. Sessiz asılı kalan SSE (bugünkü durum) kaldırılır.

## Varsayımlar
- Kanca HTTP, CLI değil: 13b e2e Playwright konteynerinde koşar ve backend konteynerinde komut çalıştıramaz. GOREV "ya da" diyor.
- Kanca audit yazmaz: tetiklediği cron işi de yazmıyor. İz `approvals` satırı (`resolved_by` TTL) ve `run_events`'tedir. Log `approvals_sweep_hook now=...` uyarısı.
