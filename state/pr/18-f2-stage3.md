# PR 18-f2-stage3: F2 aşama 3 + gerçek seed koşusu

**Paket:** 18 senaryolar (F2 aşama 3; 18 r3 ONAY şartı "gerçek seed kanıtı") · **Sınıf:** [A] (yalnız `tests/e2e/scenarios/**`) · **Branch:** feat/18-f2-stage3 @ 7e5bf8ca35a4dd8a56a7405a9b92dca61df04d39 (main 6deb0c1 üstünde, 2 commit) · `FFCORE_VERSION=0.0.0-18e2e`, `BACKEND_PORT=18020 FRONTEND_PORT=13020`
GOREV K-SEN-0036/0044/0047; karar K-SEN-0048 A. Durum: PR-HAZIR.

## Değişiklik

- `tests/e2e/scenarios/test_18_f2_approvals.py` (yeni): `e2e-bilet`'in `send_reply`'ı 07 kuyruğunda bekler; konsol oturumuyla onay/ret 07 uçlarından (`/approvals/{id}/approve|reject`).
- `seed.py`: hedef projenin `default` politikası enforce, secrets kuralı `log`. Gerekçe artık zehirli/kodlu içerik (P5 base64); belge adı yanlış pozitifi 08 düzeltmesiyle gitti. Karar K-SEN-0048 A; bütün cevabı bloklama FOLLOWUP-107.

## Koşular (temiz yığın, `docker compose -p ffcore-18e2e --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test`)

| Koşu | Baz | Seed | pytest | Not |
|---|---|---|---|---|
| 1 | a257192 (08 öncesi) | 0, tekrar 0 (idempotent) | 31 passed / 3 failed / 24 skipped | F2 aşama 3 üçü geçti; kırmızılar f10_4, f10_7, f4_1c (08 öncesi beklenen) |
| 2 | 6deb0c1, secrets dahil tam enforce | 0 | 30 / 4 / 24 | **f4_1c yeşil**; F1/F2/F3 KB koşuları belge adlarıyla bloklanmadı; f11_5[P3,P5] `guardrail_block` (P5 base64 → API_TOKEN 5.2 bit; P3 aynı KB'den P5 parçasını getiriyor) → karar gerekti |
| 3 (son) | 6deb0c1 + 7e5bf8c (secrets=log, karar A) | 0 | **32 passed / 2 failed / 24 skipped** | kırmızılar yalnız bilinen ürün bulguları f10_4, f10_7 |

Gerçek seed koşusu (18 r3 ONAY şartı): üç temiz yığında seed çıkış 0; koşu 1'de art arda iki kez (idempotent). Superadmin girişi önce, yalnız 401 `invalid_credentials` → `create-superadmin` yolu gerçek yığında çalıştı.

## Kabul → test (F2 aşama 3)

| Kriter | Test | Ölçülen | Durum |
|---|---|---|---|
| yanıt 07 kuyruğunda bekler; doğru eylem/argüman; `can_decide`; sayaç; masa boş | `test_18_f2_8` | `ticket-desk__send_reply`, `ticket_id=tkt-001`, analyst can_decide, count ≥ 1, `/_sent` boş | geçti |
| `read` erişimli admin karar veremez | `test_18_f2_8` | GET `can_decide=false`, approve 403, `/_sent` boş | geçti |
| konsol onayı yanıtı bir kez gönderir; ikinci karar 409 | `test_18_f2_9` | `approved` + `resolved_by`, `stream_after` ile akış `done`, run completed, `/_sent` = [tkt-001], ikinci approve 409 | geçti |
| ret: gönderim yok, model bilgilendirilir | `test_18_f2_10` | `rejected`, run completed, `/_sent` boş, modele giden istekte "The approver rejected this action. Comment: e2e ret", `approval_resolved` = rejected | geçti |
| ret sonrası koşu `declined` | `test_18_f2_10b` | — | NOT_RUN: gerçek model (fake "hello …" DECLINE_PATTERN'e uymaz) |

## Ürün bulguları (kırmızı kalan)

| Test | Bulgu | Sahip |
|---|---|---|
| `test_18_f10_4_direct_ids_are_404` | üye olmayana 12 uçta 403 `insufficient_role` (404 beklenir) | FOLLOWUP-103 (isci-a) |
| `test_18_f10_7_deleted_source_keeps_reference_without_content` | **tek satır tarif:** `sources` olayının `breadcrumb`'ı belgenin başlık satırlarını metin olarak taşıyor, belge silinince içerik parçası koşu kaydında kalıyor; olay yalnız başlık kimliği/sayfa taşımalı ya da silmede breadcrumb maskelenmeli. | **sahip:** 04a (breadcrumb üretimi, chunking) + 06a (`Source.public()` olaya yazıyor); koordinatör notu 10b-poc-2/10a ise yalnız gösterim tarafı |
| (yeni, karar A ile kırmızı değil) | secrets enforce'ta getirilen tek kodlu parça (P5 base64) bütün cevabı blokluyor, aynı KB'deki masum soru (P3) dahil | FOLLOWUP-107 (08 tam: kaynak başına maskeleme/eleme) |

## Kapılar

- Yığınsız: `pytest tests/e2e/scenarios` → 8 passed (örtü + seed birim), diğerleri NOT_RUN.
- Yığın: yukarıdaki üç koşu; YIGIN-AÇ T-18-0043, son `down -v` sonrası `ffcore-18e2e` konteyneri 0.
- `make lint` `tests/e2e`'yi kapsamaz; değişiklik yalnız test dosyaları.
