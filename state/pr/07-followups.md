# PR: fix/07-followups

**Paket:** fix/07-followups (FOLLOWUP-104 + 111 + 113) · **Sınıf:** [A] · **Branch:** fix/07-followups · **Baz commit:** c8650cb · **HEAD:** d9d66fbabf74b3bb22c19a106c6b5489fed26739 (4 commit) · **GOREV:** K-07F-0001 · **Oturum:** ffcore-isci-b-07fu

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

## Kararlar (koordinatör)
- Plan onaylı; 113 = A (K-07F-0002): FOLLOWUP-113 dayanak hatalı diye kapandı, kod değişmez, sabitleme testi + docs.
- Compose geçişi: A (K-07F-0004), d9d66fb. Satır backend env bloğunda; worker'lar bloğu anchor ile paylaşır ama bayrağı okumaz.

## Değişen dosyalar
- Dilim 1, 104 (9efdb26):
  - `backend/ffcore/runtime/events.py`: `follow(..., finished)`. Ardışık ikinci boş keepalive turunda run bitmişse `replay_rows(<son seq>)` verilir ve akış biter.
  - `backend/ffcore/api/runs.py`: `_finished(run_id)`.
  - Testler: `tests/unit/test_07f_follow.py`, `tests/integration/test_07f_followups.py` (test 2).
- Dilim 2, 111 (3038435):
  - `backend/ffcore/api/approvals_internal.py` (yeni).
  - `api/__init__.py`: iki satır.
  - `core/config.py`: `ffcore_test_hooks`.
  - `services/approvals.py`: `sweep` expire edilenleri döner (additive).
  - `tests/unit/test_03a_write_flag.py`: `WRITE_EXEMPT`.
  - `.env.example`, `docs/onaylar.md`.
  - `tests/integration/test_07f_followups.py`: test 3-5.
- Dilim 3, 113 (fce0b50): `tests/integration/test_07f_sql_context_roles.py`, `docs/araclar.md`.
- Compose (d9d66fb): `deploy/docker-compose.yml` backend env (`FFCORE_TEST_HOOKS: ${FFCORE_TEST_HOOKS:-0}`), `docs/onaylar.md` notu, `tests/unit/test_07f_compose.py`.

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Canlı girdi kaybolsa da okuyucu saklı terminal olayı alır; canlı run'da bekler; geç yayınlanan canlı girdi tekrar oynatmaya tercih edilir | `test_07f_1_follow_ends_from_db_when_live_entry_lost`, `test_07f_1_follow_keeps_waiting_while_run_is_live`, `test_07f_1_follow_prefers_live_entry_published_after_commit` | geçti (önce kırmızı: `finished` yok) |
| 2 | TTL kapanışında `error` xadd'i düşer: run `failed`, `error` satırı DB'de, Last-Event-ID ile reconnect tek `error` alır ve biter | `test_07f_2_expired_close_redis_publish_fails_reconnect_gets_error` | geçti; baz kodla kırmızı (akış 20 s sınırında asılı) |
| 3 | Bayrak kapalı: 404, bilinmeyen yolla aynı gövde, kimlikten önce; compose bayrağı backend'e varsayılan 0 ile geçirir | `test_07f_3_sweep_hook_404_when_flag_off`, `test_07f_3_compose_passes_test_hook_flag_off_by_default`; canlı konteyner kontrolü (aşağıda) | geçti |
| 4 | Bayrak açık: süresi gelmeyen dokunulmaz, gelen `expired` + run `failed`; tekrar çağrı boş; `approval_expired` tek | `test_07f_4_sweep_hook_expires_and_is_idempotent` | geçti (önce kırmızı: 404) |
| 5 | Konsol oturumu 403 `service_account_required`; tz'siz `now` 422 `now_without_timezone` | `test_07f_5_sweep_hook_service_only_and_tz` | geçti (önce kırmızı) |
| 6 | sql-context: `user` ve `analyst` OBO ile 200, üye olmayan 404 `project_not_found` | `test_07f_6_sql_context_any_member_reads_on_behalf[user|analyst]` | geçti (sabitleme testi; kod değişmedi, kırmızı yok) |

## Çalıştırılan komutlar
Hepsi `FFCORE_VERSION=0.0.0-07f docker compose -p 07f --env-file .env.test --profile tools run --rm -T tools ...`; yığın `--profile test --profile qdrant`, 18060/13060, temiz volume.

| Komut | Ortam | Exit | Süre | Log |
|---|---|---|---|---|
| test_07f_2 baz koda karşı (events.py/runs.py geçici c8650cb) | yığın | 1 (beklenen kırmızı) | 48 s | state/evidence/fix-07f-red-104-20261030.log |
| 07f entegrasyon testleri, 111 bağlanmadan | yığın | 1 (4/5 kırmızı, 2/3/6 yeşil) | 52 s | state/evidence/fix-07f-red-111-113-20261030.log |
| `make lint` | --no-deps | 0 | 15 s | fix-07f-lint-20261030.log |
| `make test` | `DEPLOY_PROFILE=llmaas` | 0 (701 passed) | 163 s | fix-07f-test-llmaas-20261030.log |
| `make test` | `DEPLOY_PROFILE=airgap` | 0 (701 passed) | 160 s | fix-07f-test-airgap-20261030.log |
| `make test-int` | yığın (kod fce0b50; d9d66fb yalnız compose + birim test ekler) | 0 (526 passed, 4 skipped; main kapısıyla aynı atlama sayısı, nedenleri `-rs` ile alınmadı) | 608 s | fix-07f-test-int-20261030.log |
| `test_07f_compose.py` + `test_00_repo_skeleton.py`, `ruff check/format --check`, `compose config -q` | d9d66fb | 0 (12 passed) | | |
| canlı backend (imaj HEAD d9d66fb'den yeniden derlendi): bayrak 0 → servis ve anonim 404; bayrak 1 → servis 200 `{"expired":[]}`, anonim 401 | 18060 | beklenen | | fix-07f-live-hook-20261030.log |
| `down -v` | | 0 (konteyner 0, volume 0) | | |

Migration yok.

## Kontrol listesi
- [x] Felsefe ile çelişen nokta işaretlendi (113 dayanağı, B-07FU-0004)
- [x] Donmuş sözleşme kırılmadı: C9 tip ve SSE adları aynı; OpenAPI 07 değişmedi (kanca `include_in_schema=False`)
- [x] İki profil testi koştu
- [x] Mutasyon ucu: kanca servis hesabına özel, audit yazmaz (varsayım, aşağıda); salt-okunur kural uygulanmaz (`WRITE_EXEMPT`)
- [x] Log, API, hata gövdesi secret-free (kanca yalnız `now` loglar)
- [x] Docs ve `.env.example` güncel; loglarda servis jetonu yok (grep 0)
- [ ] Önyüz yok

## Varsayımlar ve brief'teki çelişkiler
- Kanca HTTP, CLI değil: 13b e2e Playwright konteynerinde koşar.
- Kanca audit yazmaz: tetiklediği dakikalık cron da yazmıyor. İz `approvals.resolved_by` (TTL çözücü) + `run_events` + `approvals_sweep_hook` log uyarısı.
- 104 tekrar oynatmasında, canlı `done` kaybolmuş tamamlanmış run'da istemci cevabı `answer` satırından tek `token` olarak tekrar alabilir; canlı tokenları zaten görmüşse metin iki kez görünür. Bu yalnız Redis yayın hatasında olur; normal bitişte ilk boş tur canlı girdiyi bekler (test 1c).
- 104'te keepalive başına bir `runs.status` sorgusu yapılır; yalnız boş turlarda (`SSE_KEEPALIVE_S`).
- `docs/onaylar.md`'deki "kapanış ve onay tek transaction" cümlesi, yayın hatasında satırların commit'li kaldığını söylemiyordu; yeni paragraf bunu yazar.

## Kalan riskler
- 13b'nin e2e env dosyasına `FFCORE_TEST_HOOKS=1` satırını 13b A tarafı ekler (K-07F-0004); eklenmezse kanca 404 döner (açık hata).
- `follow()` Redis tamamen düşerse (xread hatası) değişmedi; 06a altyapı davranışı.
