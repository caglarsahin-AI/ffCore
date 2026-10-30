# PR: fix/03a-nonmember-404 (FOLLOWUP-103)

**Paket:** fix/03a-nonmember-404 · **Sınıf:** [A] · **Branch:** fix/03a-nonmember-404 · **Baz commit:** f1f78fc (main) · **Oturum:** ffcore-isci-a-03anm · **GOREV:** K-03ANM-0001 (= K-04aWR-0007 + karar A K-04aWR-0005)

Son durum: PR-HAZIR · HEAD 8d3cb3bfde871165f49e088e8d6a7e07b29d329f

## Plan

1. **Bulunan semboller:** `backend/ffcore/core/auth.py` `RoleRequirement.__call__` → `authorize()` → `_grant()`. `_grant` üye olmayana (`member is None`) ve silinmiş/olmayan projede süper admin olmayana `insufficient_role` dönüyor; `authorize` bunu 403'e çeviriyor ve `_audit_denied` yazıyor. `project_not_found` yolu bugün 404 ama audit yazmıyor. F10'un 12 ucu da `require_role` üzerinden geçiyor (state/pr/18-e2e.md "Ürün bulguları" 2); tek nokta düzeltmesi hepsini kapsar.
2. **Kapsam:** üye değil ya da proje yok/silinmiş → herkese `404 not_found_error project_not_found` (aynı gövde); üye ama rol yetmez → `403 insufficient_role` aynen; `read_only_access`, OBO başka proje `obo_project_scope`, kullanıcı olmayan aktör ve tenant uçları 403 aynen. Audit: 404 retleri de `outcome=denied`; `after.code=project_not_found`, gerçek neden `after.reason=not_member|no_project` (yanıtta yok). R-04AWR-0001 MINOR-1: `test_04awr_5` `Settings(...)` zorunlu alanları açık değerlerle. **Kapsam dışı:** kaynak düzeyi (KB, belge, run) 404 kuralları (04a/06a'da zaten var); zamanlama yan kanalı (üye-değil yolu bir sorgu fazla, aşağıda risk).
3. **Değişecek dosyalar:** `backend/ffcore/core/auth.py` (`_grant` iç neden kodları, `authorize` 404 + audit); `backend/tests/integration/test_03a_nonmember_404.py` (yeni); beklentisi 403 → 404 olan mevcut testler (test_03a_access, test_04a_api, test_04a_review_r1_acl, test_05a_sql, test_08_api ve koşuda çıkanlar; yalnız beklenti); `backend/tests/unit/test_04a_convert.py` (MINOR-1); `docs/api.md` hata tablosu.
4. **Sözleşme / profil:** C2 imzası (`resolve_actor`, JWT alanları) değişmez; hata gövdesi OpenAI şeması aynen, yalnız durum kodu 403 → 404 (KARARLAR 30 Ekim kararı, A). Profil etkisi yok. OpenAPI dosyalarında proje uçlarına 404 yanıtı belgeli mi bakılacak; değilse additive eklenir.
5. **Kabul → test:**
   | # | Kriter | Test |
   |---|---|---|
   | 1 | `{project_id}` içeren her uçta üye olmayan → 404, gövde olmayan projeyle birebir | `test_03a_nonmember_gets_404_like_missing_project[*]` (OpenAPI'den türetilir) |
   | 2 | F10'un 12 ucu taranan listede | `test_03a_nonmember_route_list_covers_followup_103` |
   | 3 | üye + düşük rol → 403 `insufficient_role` | `test_03a_member_with_low_role_still_403` |
   | 4 | silinmiş proje eski üyeye 404 | `test_03a_deleted_project_404_for_former_member` |
   | 5 | audit'te gerçek neden (`not_member`/`no_project`), yanıtta yok | `test_03a_nonmember_404_audits_real_reason` |
   | 6 | 06a runs kuralıyla uyum (başka kullanıcının run'ı `run_not_found`, başka proje `project_not_found`; ikisi de 404) | `test_03a_nonmember_404_agrees_with_06a_run_rule` |
   | 7 | MINOR-1 `test_04awr_5` ortamdan bağımsız | `test_04awr_5_ingest_pool_uses_start_timeout_setting` (`env -i` benzeri boş ortamda) |
6. **Migration:** yok.
7. **Geri alma:** tek commit revert; veri değişikliği yok.
8. **Durma koşulları:** bir `{project_id}` ucu `require_role` dışında kendi yetki kontrolünü yapıyorsa ve 404'e çekilmesi başka paketin davranışını değiştiriyorsa (ör. internal/servis uçları) koordinatöre dönerim; önyüzün 403'e bağlı bir akışı çıkarsa FOLLOWUP.
9. **Felsefe:** ARCH-07: tüm proje uçlarına değer, kalıcı karmaşıklık yok (tek fonksiyon). ARCH-09: platform karşılığı yok; mevcut `ApiError`/audit yolu kullanılır. ARCH-10/06: gizli davranış yok; ret sessiz değil, audit'e gerekçeyle düşer (bugün 404 yolu audit yazmıyordu, bu kapanır).

## Commit'ler (main f1f78fc üstüne 2)

- `b80c8c9` test(03a): kırmızı test (yalnız `tests/integration/test_03a_nonmember_404.py`)
- `8d3cb3b` fix(03a): düzeltme + beklenti güncellemeleri + MINOR-1 + docs

## Değişen dosyalar

- Kod: `backend/ffcore/core/auth.py`: `_grant` iç nedenler `no_project` / `not_member` (`HIDDEN_PROJECT`); `authorize` ikisini de 404 `project_not_found` (aynı gövde) yapar ve önce `_audit_denied(..., reason=...)` yazar; `_audit_denied`'e isteğe bağlı `reason` (yalnız `after.reason`). Süper admin olmayanın silinmiş projesi de artık 404 (önce 403'tü).
- Yeni test: `backend/tests/integration/test_03a_nonmember_404.py`.
- Beklenti 403 → 404 (yalnız üye-olmayan satırları): `test_03a_access.py` (`test_03a_1_non_member_gets_404_not_data` yeniden adlandırma + üyelikten çıkarılan kullanıcı), `test_03a_obo_scope.py` (OBO'da üye olmayan süper admin), `test_04a_api.py`, `test_04a_review_r1_acl.py`, `test_05a_sql.py`, `test_07_api_read.py`, `test_08_api.py`.
- Test altyapısı: `tests/integration/conftest.py` `audit_rows(..., project=None)` additive filtre; `test_08_api.py` audit sayımları kendi projesine daraltıldı. Neden: test DB'si paylaşımlı; yeni parametrik test artık audit'lenen 404 retleri ürettiği için yalnız eylem adına göre sayan iki 08 testi (`test_08_19`, `test_08_6`) başka testin satırlarını sayıyordu (ilk tam test-int koşusunda düştüler, `test-int-ilk.txt` yerine aşağıda anlatıldı).
- MINOR-1: `tests/unit/test_04a_convert.py` `test_04awr_5` unit `settings` fixture'ından `model_copy`; ortam okumaz.
- Docs: `docs/api.md` erişim bölümü (404 kuralı, audit `after.reason`, tenant uçları istisnası).
- OpenAPI: değişiklik yok; her router `ERROR_RESPONSES` ile 404'ü zaten belgeliyor, `backend/openapi/*.yaml` bayt aynı (kontrat testleri `make test` içinde yeşil).

## Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | `{project_id}` içeren her uçta (OpenAPI'den 69 işlem) üye olmayan → 404, gövde olmayan projeyle birebir | `test_03a_nonmember_gets_404_like_missing_project[*]` | geçti (kırmızıda 69/69 düştü, hepsi 403 `insufficient_role`) |
| 1b | Tenant ucu `DELETE /projects/{id}`: süper admin olmayana var/yok proje için birebir aynı 403 (sızıntı yok) | aynı test, `TENANT_ROUTES` dalı | geçti |
| 2 | F10'un 12 ucu taranan listede | `test_03a_nonmember_route_list_covers_followup_103` | geçti |
| 3 | üye + düşük rol → 403 `insufficient_role` | `test_03a_member_with_low_role_still_403` | geçti |
| 4 | silinmiş proje eski üyeye 404 | `test_03a_deleted_project_404_for_former_member` | geçti (kırmızıda 403) |
| 5 | audit `code=project_not_found`, `reason=not_member\|no_project`, `project_id` yazılı; yanıtta neden yok | `test_03a_nonmember_404_audits_real_reason` | geçti (kırmızıda audit satırı yoktu) |
| 6 | 06a uyumu: başka kullanıcının run'ı 404 `run_not_found`, başka projenin run'ı 404 `project_not_found` | `test_03a_nonmember_404_agrees_with_06a_run_rule` | geçti |
| 7 | MINOR-1 `test_04awr_5` ortamdan bağımsız | `test_04awr_5_ingest_pool_uses_start_timeout_setting` (`env -i`) | geçti; eski çağrı `env -i`'de `ValidationError` (kırmızı kanıt `minor1-red.txt`) |

## Çalıştırılan komutlar

Yığın `ffcore-03anm`, `FFCORE_VERSION=0.0.0-03anm` (imajlar `0.0.0-main`'in etiketi; bağımlılık değişmedi, kod `/work` bağlamasından), `BACKEND_PORT=18030 FRONTEND_PORT=13030`, `--profile test --profile qdrant up -d --wait --pull never` (83 s). Komutlar `docker compose -p ffcore-03anm --env-file .env.test run --rm -T --no-deps tools ...`. Tam çıktılar `state/pr/03a-nonmember-404-kapilar/`.

| Komut | HEAD | Exit | Sonuç | Dosya |
|---|---|---|---|---|
| yeni test, düzeltmesiz | b80c8c9 | 1 | 72 failed, 2 passed (hepsi 403) | `red.txt` |
| yeni test, düzeltmeli | çalışma ağacı | 1 → 0 | ilk 73/74 (tenant DELETE), istisna eklenince 74/74 | `green-new.txt` |
| MINOR-1 eski `Settings(...)` `env -i` | — | 1 | `ValidationError` (zorunlu alanlar) | `minor1-red.txt` |
| MINOR-1 yeni test `env -i` | — | 0 | 1 passed | `minor1-green.txt` |
| `make lint` | 8d3cb3b ağacı | 0 | 306 dosya | `lint.txt` |
| `make test` llmaas | 8d3cb3b ağacı (birim dosyaları aynı) | 0 | 696 passed (150 s) | `test-llmaas.txt` |
| `make test` airgap | aynı | 0 | 696 passed (194 s) | `test-airgap.txt` |
| `make test-int` ilk | commit öncesi | 2 | 512 passed, 4 failed (03a obo, 07 outsider: beklenen 404; 08_19/08_6: paylaşımlı DB'de audit sayımı) | (üzerine yazıldı; özet burada) |
| etkilenen 4 dosya | düzeltme sonrası | 0 | 118 passed | `fixed-four.txt` |
| `make test-int` | 8d3cb3b | 0 | 516 passed, 4 skipped (opt-in), 418 s | `test-int.txt` |
| `down -v` | — | 0 | konteyner 0, volume 0 | — |

## Çıktı özeti ve post-state
Migration yok, veri değişikliği yok. Yeni audit satırı türü: `outcome=denied`, `after.code=project_not_found`, `after.reason`.

## Varsayımlar ve brief'teki çelişkiler
- Geçersiz biçimli `project_id` (uuid değil) de 404 `project_not_found` (bugünkü davranış), audit nedeni `no_project`.
- Süper admin olmayan için silinmiş proje: 403 → 404 (planda yazılı; aksi "var ama üye değil 404 / yok 403" farkı varlık sızdırırdı).
- OBO'da üye olmayan süper admin (token projesi aynı): 403 → 404 (üye değil kuralı; `obo_project_scope` yalnız token projesi dışı için, aynen).
- `docs/degisiklikler.md` depoda yok; davranış değişikliği docs/api.md'de.

## Kalan riskler
- Zamanlama: üye-değil yolu "proje var" sorgusundan sonra bir üyelik sorgusu daha yapar; ölçülebilir fark teorik olarak varlık sızdırabilir. Yerel ağ + oturum gerektirir; kapsam dışı, not.
- Önyüz: `frontend/lib/api/errors.ts`'te `project_not_found` eşlemesi yok; bu kodu alan ekran genel hata mesajı + kodu gösterir (önce de süper admin/olmayan proje için aynıydı, artık üye olmayanlar için de). Touch-zone dışı; KAYIT-TALEBI ile FOLLOWUP önerildi.
- e2e: `test_18_f10_4_direct_ids_are_404` ve 13b negatif testi bu dalda koşulmadı (yığında seed yok); aynı `_grant` yolu, merge sonrası yeşile dönmesi beklenir, doğrulanmadı.
