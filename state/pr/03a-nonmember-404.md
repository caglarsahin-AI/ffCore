# PR: fix/03a-nonmember-404 (FOLLOWUP-103)

**Paket:** fix/03a-nonmember-404 · **Sınıf:** [A] · **Branch:** fix/03a-nonmember-404 · **Baz commit:** f1f78fc (main) · **Oturum:** ffcore-isci-a-03anm · **GOREV:** K-03ANM-0001 (= K-04aWR-0007 + karar A K-04aWR-0005)

Son durum: PLANNED

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

## Değişen dosyalar
(kodlama sonrası)

## Kabul kriterleri → testler
(kodlama sonrası)

## Çalıştırılan komutlar
(kodlama sonrası)

## Varsayımlar ve brief'teki çelişkiler
- Geçersiz biçimli `project_id` (uuid değil) de 404 `project_not_found` (bugünkü davranış), audit nedeni `no_project`.

## Kalan riskler
- Zamanlama: üye-değil yolu "proje var" sorgusundan sonra bir üyelik sorgusu daha yapar; ölçülebilir fark teorik olarak varlık sızdırabilir. Yerel ağ + oturum gerektirir; kapsam dışı, not.
