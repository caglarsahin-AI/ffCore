# [A] fix(05a): analysts read tools and actions (FOLLOWUP-100)

**Paket:** fix/05a-tools-read-analyst · **Sınıf:** [A] · **Branch:** fix/05a-tools-read-analyst · **Baz commit:** f1f78fc · **HEAD:** a795d9d (2 commit) · Oturum ffcore-isci-b-05atr · GOREV K-05ATR-0001

## Plan (onaylı: B-07-0018, K-10bp2-0003 karar A)
1. Bulunan semboller: `backend/ffcore/api/tools.py:46` `Reader = require_role("developer")`, yalnız `list_tools` ve `get_tool` kullanıyor; yazma uçları `Admin = require_role("admin", write=True)`; `sql_context` `AnyMember` (değişmez). `core/auth.py:284` `ROLE_ORDER` user < analyst < developer < admin. Ayrı bir aksiyon liste ucu yok: aksiyonlar `ToolOut.actions` içinde, yani "aksiyon listesi" = iki GET.
2. Kapsam: iki GET `analyst`; yazma (`POST`, `PATCH`, `DELETE`, `discover`, aksiyon `PATCH` içinde `needs_approval`, `invoke`) admin + edit kalır. Kapsam dışı: önyüz (`docs/onyuz.md:20-21`, `:191` hâlâ "developer"; isci-c alanı), üye olmayana 404 (FOLLOWUP-103, isci-a `fix/03a-nonmember-404`).
3. Değişen dosyalar: `api/tools.py` (Reader + docstring'ler), `openapi/05a.yaml` (yeniden üretim), `docs/araclar.md` (rol cümlesi), testler.
4. Sözleşme ve profil: C7 araç imzaları değişmedi; yetki genişlemesi, imza aynı → additive. OpenAPI'de iki GET'e `description` eklendi (additive). Profil farkı yok.
5. Kabul → test: aşağıdaki tablo.
6. Migration: yok.
7. Geri alma: `Reader` satırını `developer`'a geri almak (tek satır); veri değişikliği yok.
8. Durma koşulları: yazma uçlarından biri `Reader` kullanıyor çıkarsa (çıkmadı, birim tarama kanıtlar).
9. Felsefe: ARCH-07 analist agent sihirbazında araç seçebilsin diye tek satır, kalıcı karmaşıklık yok; ARCH-09 03a `require_role` aynen kullanıldı, yeni yetki mekanizması yok; ARCH-10/06 gizli davranış yok, gizli alanlar her okuyucuya `***` (testle), red kodlu (`insufficient_role`).

## Değişen dosyalar
- backend/ffcore/api/tools.py
- backend/openapi/05a.yaml
- backend/tests/unit/test_05a_tool_read_roles.py (yeni)
- backend/tests/integration/test_05a_tools_api.py
- docs/araclar.md

## Kabul kriterleri → testler
| # | Kriter (GOREV K-05ATR-0001) | Test | Durum |
|---|---|---|---|
| 1 | Araç ve aksiyon okuma (iki GET) `analyst`, yazma admin + edit | `tests/unit/test_05a_tool_read_roles.py::test_05a_tool_reads_need_analyst`, `::test_05a_tool_changes_stay_admin_with_edit` | geçti (kırmızı b8e2f15: `('developer', False) == ('analyst', False)`) |
| 2 | `user` rolü 403 | `test_05a_tools_api.py::test_05a_tool_read_user_role_refused` | NOT_RUN (test-int, yığın sırası) |
| 3 | `analyst` 200, gizli alan `***`, ham değer yok | `::test_05a_tool_read_analyst_sees_masked_secret`, `::test_05a_tool_roles` (analyst 403 → 200) | NOT_RUN (test-int) |
| 4 | `analyst` POST/PATCH/DELETE/discover/aksiyon PATCH/invoke 403 | `::test_05a_tool_analyst_cannot_change` | NOT_RUN (test-int) |
| 5 | `access=edit` kuralı aynen: analyst+read okumada eşit | `::test_05a_tool_read_analyst_read_parity` | NOT_RUN (test-int) |
| 6 | OpenAPI taslağı = uygulama | `tests/contract/test_05a_openapi.py` | geçti |

## Çalıştırılan komutlar
Hepsi `FFCORE_VERSION=0.0.0-05atr docker compose -p 05atr --env-file .env.test --profile tools run --rm --no-deps -T tools ...` (yığınsız, imaj kendi etiketiyle derlendi).
| Komut | Ortam | Exit | Süre |
|---|---|---|---|
| `pytest tests/unit/test_05a_tool_read_roles.py` @ b8e2f15 (kırmızı) | - | 1 (1 failed, 1 passed) | 6 s |
| `python -m ffcore.api.openapi_export 05a > openapi/05a.yaml` | - | 0 | - |
| `make lint` | - | 0 (306 dosya) | - |
| `make test` | `DEPLOY_PROFILE=llmaas` | 0 (698 passed) | 178 s |
| `make test` | `DEPLOY_PROFILE=airgap` | 0 (698 passed) | 131 s |
| `pytest tests/unit/test_05a_tool_read_roles.py tests/contract/test_05a_openapi.py` @ a795d9d | - | 0 (6 passed) | 7 s |
| `make test-int` | - | NOT_RUN | yığın: "YIGIN-AÇ 05atr" sırası bekleniyor |

Not: `make test` 698'i docstring kısaltmasından (yalnız satır uzunluğu) önce koştu; sonrası lint + hedefli 6 test.

## Kontrol listesi
- [x] Felsefe ile çelişen nokta yok
- [x] Donmuş sözleşme kırılmadı (C7 imzaları aynı; yetki genişlemesi additive, K-10bp2-0003)
- [x] İki profil testi koştu (birim)
- [x] Mutasyon uçları değişmedi (audit ve `write=True` aynen; 03a taraması yeşil)
- [x] Gizli alanlar her okuyucuya `***` (test 3, test-int'te)
- [ ] Docs: `docs/araclar.md` güncel; `docs/onyuz.md` önyüz tarafında (isci-c)

## Varsayımlar ve brief'teki çelişkiler
- "Aksiyon listesi GET'i" ayrı uç değil; aksiyonlar araç GET'lerinin içinde (`ToolOut.actions`).
- Analist artık `endpoint_url` ve başlık adlarını görür (gizli değerler değil); K-10bp2-0003 A bunu kabul ediyor.
- `test_05a_tool_roles`'taki analyst 403 beklentisi 200'e çevrildi (karar A'nın doğrudan sonucu).

## Kalan riskler
- `fix/03a-nonmember-404` merge sırasına göre üye olmayanın kodu 404 olur; bu dalın testleri yalnız üye-ama-rolü-yetmeyen (403) durumunu sınar, kesişme beklenmez ama rebase'te test-int yeniden koşmalı.
- `docs/onyuz.md` ve 10b-poc-2 analist açıklaması ("geliştirici rolü gerekir") bu merge sonrası güncellenmeli (isci-c).
