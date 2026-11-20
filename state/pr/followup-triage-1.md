# PR: fix/followup-triage-1

**Paket:** triage-1 (FOLLOWUP 202, 203, 194, 201, 207, DRIFT-198) · **Sınıf:** [B] · **Branch:** fix/followup-triage-1 · **Baz commit:** a60228d · **İşçi:** isci-b (lease ffcore-isci-b-triage1)

Durum: **PR-HAZIR** · HEAD `292f2907d56486b1476644d194211b6ebfdde1d0` · delta `a60228d..292f290` (13 commit, 26 dosya, +598/−82; merge-base a60228d, main o zamandan beri yalnız state/KARARLAR) · PLAN-ONAY K-TRJ-0002; kararlar KARARLAR 'triage-1 plan kararları'.

## Plan (B-TRJ-0002, onaylı)
1. **Bulunan semboller ve dosyalar:** `.claude/hooks/ffcore_guard.py` `check_compose`; `tests/hooks/test_guard.py` 139-162, `tests/hooks/test_wrappers.py:131`; `backend/tests/integration/test_06b_direct.py::test_06b_6_quota_exceeded_429_openai_shape`, `ffcore.services.quota` (`time.time()`); `backend/ffcore/api/knowledge.py` `_check_reupload`, `_document`, `get_document`, `update_document`, `delete_document`, `acl_for`; `backend/ffcore/core/auth.py` `authorize`, `_audit_denied`; `backend/ffcore/core/audit.py` `audited`; `backend/ffcore/api/agents.py` `_admin_if_external`; `backend/ffcore/api/runs.py` 461/730/769 (`@audited` dışında); `backend/ffcore/services/mcp_client.py` `is_platform_target`; `services/providers.py`, `services/litellm_reconcile.py`, `services/notify.py` `post_webhook`, `api/alerts.py`, `api/notifications.py`; plan/04 satır 6; PLAN.md 209 ve 233.
2. **Kapsam:** altı dilim (aşağıda). **Kapsam dışı:** FOLLOWUP-205/206, video dönüştürücü, yeni özellik; belge listesi/arama/ingest-report C15 süzgeçli kalır (S-1).
3. **Dilimler (sıra):**
   1. **207** hook: `up --build` + `--pull never` kabul (yığın sayımı sürer); `--pull never`'sız `up` PROSES-175; standalone `build` her biçimde PROSES-175 (`--pull=false` muafiyeti kalkar); `warn` kipi değişmez.
   2. **201** kota testi: `monkeypatch` ile `ffcore.services.quota.time` sabit saat (dakika başı + 5 sn); üretim kodu değişmez; 20 koşu.
   3. **202** tek kural `_manages_acl(request)` (`grant.role == "admin"`; süperadmin grant'i de admin): `_check_reupload` ve tekil GET/PATCH/DELETE; analyst 404 aynen; iki sürücü.
   4. **203 (A)** `@audited` içindeki `authorize()` satır yazmaz, red ayrıntısını (`code`, `min_role`, `write`) istisnaya ekler; wrapper tek `denied` satırına `after` olarak birleştirir. Dependency düzeyindeki redler bugünkü gibi `route` satırı.
   5. **194** `is_platform_target` `core/egress.py`'ye; sağlayıcı `base_url` kayıt/güncelleme 400 `endpoint_is_platform`, `test_connection` sonucu, `litellm_reconcile`, alert `params.webhook_url` ve bildirim `default_webhook_url` kaydı 400, `post_webhook` çağrı anı red. Üç URL biçimi + `ALLOWED_INTERNAL_HOSTS=backend` varyantı. `alerts.readyz_probe` bilinçli dışarıda.
   6. **DRIFT-198** plan/04 satır 6, PLAN.md 209 ve 233 cümlesi; PLAN 89 ve 273 (geçmiş) dokunulmaz. S-3: `handbook/ENVIRONMENT_AND_COMMANDS.md:49` ve `docs/takim/ajanlarla-gelistirme.md:422-423` 207 kural metni (touch-zone eki, yalnız o cümleler).
4. **Sözleşme, yapılandırma, profil etkisi:** sözleşme değişmez; yeni hata kodu `endpoint_is_platform` 05b'de zaten var; `core/config.py` değişmez.
5. **Kabul → test:** tablo aşağıda (uygulamada doldurulur).
6. **Migration:** yok.
7. **Geri alma:** commit'ler bağımsız geri alınabilir.
8. **Durma koşulları:** sözleşme kırma gereği, touch-zone dışı dosya.
9. **Felsefe:** ARCH-07 yeni özellik yok, mevcut kurallar tek yere toplanır; ARCH-09 platform karşılığı yok; ARCH-06/10 194 kodlu red, 203 kayıt kaybı yok.

## Dilim / commit tablosu
| Dilim | Test commit | Kod commit | Docs commit |
|---|---|---|---|
| 207 | 2f197be | 9aebcd6 | 185023f (ENVIRONMENT_AND_COMMANDS:49, docs/takim:423) |
| 201 | 52a2852 | — (yalnız test) | — |
| 202 | 27639a3 | f66a744 | 185023f (docs/bilgi-tabani.md) |
| 203 | 8b4ab8f | 7075a7d | 185023f (degisiklikler) |
| 194 | 5a01181, b90f20e, 49461a1 | 218faa7, 292f290 (format) | 185023f (degisiklikler) |
| 198 | — | — | 185023f (plan/04 satır 6, PLAN.md 209 + 233) |

`b90f20e`/`49461a1`: kırmızı koşuda görülen test hataları (fixture `ALLOWED_INTERNAL_HOSTS`'u değiştirip Langfuse'u dışarıda bırakıyordu; `project_ids: []` geçersiz; `/providers/test` gövdesi yalnız `driver`+`config`; mesaj denetimi "backend" kelimesi yerine `://`). Davranış beklentisi değişmedi.

## Değişen dosyalar
- `.claude/hooks/ffcore_guard.py` (`check_compose`)
- `backend/ffcore/api/knowledge.py` (`_manages_acl`, `_managed_document`, `_document(filters=None)`)
- `backend/ffcore/core/auth.py` (`_audit_denied(..., error)`: `@audited` içindeyse `error.audit_detail`), `backend/ffcore/core/audit.py` (`request.state.audited_endpoint`, `after=audit_detail`, `denied`)
- `backend/ffcore/core/egress.py` (`BACKEND_CONTAINER_PORT`, `is_platform_target`, `refuse_platform_target`), `services/mcp_client.py` (aynı adla içe aktarır), `services/providers.py` (`URL_FIELDS`, `refuse_platform_urls`, `test_connection`), `api/providers.py` (create, update, test config), `services/litellm_reconcile.py` (`desired_model`), `api/alerts.py` (`_validate(..., settings)`; dört uç `SettingsDep` alır), `api/notifications.py` (`_put`), `services/notify.py` (`post_webhook`)
- testler: `tests/hooks/test_guard.py`; `backend/tests/integration/test_06b_direct.py`, `test_04b_r3_upload_acl.py`, `test_06b2_external_agent.py`; yeni `test_trj_202_admin_manages_acl.py`, `test_trj_203_single_denied_row.py`, `test_trj_194_platform_registration.py`; yeni `backend/tests/unit/test_trj_194_platform_targets.py`
- docs: `PLAN.md`, `plan/04-bilgi-tabani.md`, `docs/bilgi-tabani.md`, `docs/degisiklikler.md`, `handbook/ENVIRONMENT_AND_COMMANDS.md`, `docs/takim/ajanlarla-gelistirme.md`

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 207 | `up --build --pull never` kabul, `--pull never`'sız `up --build` ve her standalone `build` PROSES-175, yığın sayımı sürer, mesaj güncel | `test_compose_up_build_pull_never_allowed`, `test_compose_up_build_without_pull_never_blocked`, `test_compose_build_pull_false_blocked`, `test_compose_build_message_names_up_build`, `test_compose_up_build_counts_stacks` | geçti (358, `trj-207-hook-tests.log`) |
| 201 | kota testi dakika sınırına bağlı değil; saat motora ulaşıyor | `test_06b_6_quota_exceeded_429_openai_shape`, `test_06b_6_quota_clock_reaches_the_engine` | geçti; 20/20 (`trj-201-x20.log`) |
| 202 | admin/süperadmin kullanıcıya özel belgede GET/PATCH/DELETE; analyst 404; liste C15 süzgeçli; iki sürücü | `test_trj_202_*` (6 × pgvector/qdrant), `test_04b_r3_admin_reuploads_a_user_only_document` | geçti |
| 203 | tek `denied` satırı (agents, knowledge PATCH, upload), kaynak türü/id ve neden; dependency reddi `route` satırı | `test_trj_203_acl_patch_refusal_is_one_row`, `test_trj_203_route_refusal_keeps_route_row`, `test_06b2_r1_rename_and_delete_external_need_admin`, `test_04b_r3_u1_…` | geçti |
| 194 | üç URL biçimi × sağlayıcı create/update/test-config/azure `api_base`, alert kuralı (proje+kurulum, create+patch), varsayılan webhook: 400 `endpoint_is_platform`; bağlantı testi, reconcile, webhook gönderimi bağlantısız red; `ALLOWED_INTERNAL_HOSTS` backend'i içerse de | `test_trj_194_*` (28 entegrasyon + birim) | geçti |
| 198 | plan/04 ve PLAN 7 cümlesi | docs | — |

## Bilerek değişen testler
- `tests/hooks/test_guard.py`: `test_compose_build_pull_false_allowed` → `…_blocked` (`--pull=false` muafiyeti kalktı); `test_compose_up_build_blocked` → `test_compose_up_build_pull_never_allowed` + `…_without_pull_never_blocked`. (`test_wrappers.py:131` `{ docker compose up --build; }` `--pull never`'sız olduğu için PROSES-175 almaya devam ediyor; değişmedi.)
- `test_04b_r3_admin_reuploads_a_user_only_document`: admin GET artık 200 (202); peer 404 eklendi.
- `test_04b_r3_u1_…` ve `test_06b2_r1_rename_and_delete_external_need_admin`: `denied` satırı tam 1 ve `after.code/min_role` (203).
- `test_06b_6_quota_exceeded_429_openai_shape`: kota saati enjekte (201).

## Notlar / varsayımlar
- 203: `audit_payload=False` olan uçlarda (14 hafıza) `after` yazılmadığı için redde neden de yazılmaz; satır tek ve `denied` kalır. Şu an bu uçlarda endpoint içi `authorize()` yok.
- 194: `alerts.readyz_probe` (backend'in kendi `/readyz`'i) ve 05b self endpoint bilinçli dışarıda. `services/external_config.py` 06b-2'nin ayrı (daha geniş) `RESERVED_HOSTS` kuralını ve kendi `BACKEND_CONTAINER_PORT` kopyasını tutuyor; dokunulmadı.
- `docs/api.md` (355 bildirim ayarları, 583 civarı sağlayıcı) 194 kuralını anmıyor; touch-zone dışında, değişiklik `docs/degisiklikler.md`'de. İstenirse ek commit.
- `docs/takim/ajanlarla-gelistirme.md:507` "Ders" paragrafı eski `build --pull=false` kuralını tarihçe olarak anlatıyor; S-3 yalnız 422-423'ü kapsadığı için dokunulmadı.
- Hook değişikliği bu oturumu etkilemez (worktree guard'ı; ENVIRONMENT_AND_COMMANDS "Yükleme"); main'e merge sonrası geçerli.

## Çalıştırılan komutlar
| Komut | Ortam | Exit | Log |
|---|---|---|---|
| `py -3.12 -m pytest tests/hooks tests/scripts -q` | host | 0 (358) | `state/evidence/trj-207-hook-tests.log` (kırmızı: `trj-207-red.log`) |
| hedefli pytest (kırmızı, kod öncesi) | ffcore-trj tools | 1 (45 failed + 28 fixture error) | `trj-red.log`, `trj-194-red.log` |
| hedefli pytest (yeşil) | ffcore-trj tools | 0 (135 + 28) | `trj-green-targeted.log`, `trj-194-green.log` |
| 201 × 20 | ffcore-trj tools | 0 (20/20) | `trj-201-x20.log` |
| `make lint` | tools `--no-deps` | 0 | `trj-lint.log` |
| `make test` | `DEPLOY_PROFILE=llmaas FAKE_LLM=1` | 0 (1989) | `trj-test-llmaas.log` |
| `make test` | `DEPLOY_PROFILE=airgap FAKE_LLM=1` | 0 (1989) | `trj-test-airgap.log` |
| `alembic heads` | tools `--no-deps` | 0 (tek head `04b_0001`) | `trj-alembic-heads.log` |
| `make test-int` (tam) | ffcore-trj | 2 (1029 passed, 12 skipped, 10 failed, 82 error) | `trj-test-int-full.log` (compose istemcisinin koptuğu kısa log: `trj-test-int.log`) |
| etkilenen 18 dosya yeniden | ffcore-trj | 213 passed, 77 error (hepsi `clean_litellm` setup) | `trj-test-int-rerun.log` |
| `docker restart` litellm + kalan 11 dosya | ffcore-trj | 0 (79 passed) | `trj-test-int-rerun2.log` |
| `down -v` | ffcore-trj | 0 (konteyner 0, volume 0) | `trj-down.log` |

**test-int notu (dürüst kayıt):** tam koşu tek geçişte yeşil değil. ~11:05'te Docker ağında DNS kesintisi oldu (`failed to resolve host 'postgres'` 30 satır, reconcile `egress_dns_failed`; compose istemcisi aynı anda `error waiting for container` ile koptu, konteyner koşmaya devam etti). Bütün FAILED/ERROR satırları bu kesinti ya da ardından LiteLLM'de kalan DB'siz model kaydından (`/model/delete` 400 "not found in db"). Kesintiden etkilenen 18 dosya yeniden koşuldu: 213 + 79 geçti, kod kaynaklı kırmızı yok. Etkilenmeyen 1029 test ilk geçişte geçti. Tek temiz geçiş isteniyorsa main kapısı tam koşuyu yapar.
