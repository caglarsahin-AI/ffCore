# PR fix/08-default-egress-enforce

**Paket:** 08 düzeltme (plan/18 F4 bulguları) · **Sınıf:** [B] · **Branch:** fix/08-default-egress-enforce · **Baz:** main 01639c5 · **SHA:** a74902389b4e583af69292aff010351d622350d9
GOREV K-SEN-0030; kararlar K-SEN-0029 A (FOLLOWUP-102), K-SEN-0032 (egress A, entropi kapsamı). Durum: PR-HAZIR.

## Değişiklik

1. **Kural düzeyinde mod (C4 additive)**: `Rule.mode: "monitor" | "enforce" | null` (null = politikanın modu). Engine her kuralı kendi etkin moduyla değerlendirir; yalnız enforce kurallar metni değiştirir ya da bloklar, monitor kural kayıt düşer. `on_error=block` da yalnız enforce kuralda bloklar (eski monitor davranışı aynen). `mode: off` politika her şeyi kapatmaya devam eder. `backend/openapi/08.yaml` yeniden üretildi (8 satır, yalnız ekleme).
2. **Yerleşik `default` sürüm 2**: politika `monitor` kalır; egress PII `tokenize` kuralı `mode="enforce"`. Proje politika tanımlamasa da llmaas'ta kimlikler dış sağlayıcıya yer tutucuyla gider. input/output redact ve secrets monitor kalır (davranış değişikliği yalnız egress).
3. **secrets entropi**: `is_plain_identifier`: `-`/`_` parçalarının her biri rakam, tek harf türü (küçük ya da büyük) ya da ≤ 3 karakterlik etiket ise (`SZL-2025-003_temizlik-hizmet`, `p4-…`, `PRSIM-1234-…`) token sayılmaz. Parça içinde harf+rakam karışık uzun parçalar yakalanmaya devam eder. Ek kalıp: 32+ karakter hex (harf+rakam), entropi tabanının altında kaldığı için önceden kaçıyordu.
4. `docs/guardrail.md`: kural modu, yerleşik politika tablosu (Mode sütunu, sürüm 2, gerekçe), entropi istisnası ve hex kalıbı.

## Kabul → test (`backend/tests/unit/test_08_egress_enforce.py`)

| Kriter | Test | Durum |
|---|---|---|
| yerleşik politikayla egress'te ham PII yok, olay enforce/redacted | `test_08e_1` | kırmızı → geçti |
| yerleşikte diğer kurallar monitor (input.pre metni aynen) | `test_08e_2` | geçti (değişmedi) |
| yerleşikte secrets egress'te bloklamaz | `test_08e_3` | geçti (değişmedi) |
| kural modu politika modunu ezer (iki yön) | `test_08e_4` | kırmızı → geçti |
| belge adları ve tanımlayıcılar (SZL-…, hastane-a-admin-edit-…, b-el-hijyeni-…, p4-…, PRSIM-1234-…) secret değil | `test_08e_5[*]` | 5 kırmızı → geçti |
| gerçek secret biçimleri yakalanır (tok_…, 32 hex, karışık token, base64, API_KEY=…, sk-…, ghp_…) | `test_08e_6[*]` | 32 hex kırmızı → geçti; diğerleri geçti |
| mevcut 08 testleri (engine, recognizers, cost, API, OpenAPI) | `make test` | geçti |

## Kapılar (tools 0.0.0-08e, `--no-deps`, servis yok)

| Komut | Sonuç |
|---|---|
| `python -m ffcore.api.openapi_export 08 > openapi/08.yaml` | +8 satır (`Rule.mode`) |
| `make lint` | 0; 291 dosya biçimli |
| `make test` `DEPLOY_PROFILE=llmaas` | 663 passed |
| `make test` `DEPLOY_PROFILE=airgap` | ilk koşu 2 failed (FOLLOWUP-97'nin iki 04a havuz testi, bu dalın dışında); tekrar 663 passed |

## Notlar

- C4 additive: `Rule.mode` yeni opsiyonel alan; aşama adları, `action_taken` enum'u ve `Decision` aynı. CONTRACTS.md metni koordinatörde (gerekirse "C4: Rule.mode additive" notu).
- 18 e2e (feat/18-scenarios-e2e) `test_18_f4_1c` bu dal merge olunca yeşile dönmeli; seed'deki hedef proje politikasında secrets'i `log` yapan geçici ayar bu düzeltmeden sonra kaldırılabilir (ayrı küçük iş, e2e dalında).
- Yığın koşusu yok (görev yığınsız). Uçtan uca doğrulama 18 e2e yeniden koşusunda.
