# PR fix/08-default-egress-enforce

**Paket:** 08 düzeltme (plan/18 F4 bulguları) · **Sınıf:** [B] · **Branch:** fix/08-default-egress-enforce · **Baz:** main 01639c5 · **SHA:** 7dcaa9823c178daf7a8e85c186f38b0274969654 (r1 delta; ilk a749023)
GOREV K-SEN-0030; kararlar K-SEN-0029 A (FOLLOWUP-102), K-SEN-0032 (egress A, entropi kapsamı). Durum: PR-HAZIR.

## Değişiklik

1. **Kural düzeyinde mod (C4 additive)**: `Rule.mode: "monitor" | "enforce" | null` (null = politikanın modu). Engine her kuralı kendi etkin moduyla değerlendirir; yalnız enforce kurallar metni değiştirir ya da bloklar, monitor kural kayıt düşer. `on_error=block` da yalnız enforce kuralda bloklar (eski monitor davranışı aynen). `mode: off` politika her şeyi kapatmaya devam eder. `backend/openapi/08.yaml` yeniden üretildi (8 satır, yalnız ekleme).
2. **Yerleşik `default` sürüm 2**: politika `monitor` kalır; egress PII `tokenize` kuralı `mode="enforce"`. Proje politika tanımlamasa da llmaas'ta kimlikler dış sağlayıcıya yer tutucuyla gider. input/output redact ve secrets monitor kalır (davranış değişikliği yalnız egress).
3. **secrets entropi**: `is_plain_identifier`: `-`/`_` parçalarının her biri rakam, ≤ 3 karakterlik etiket, ≤ 6 harflik büyük harf kodu ya da sözcük gibi (tek tür harf, ≥ %25 sesli, 4 ünsüzlük dizi yok; r1) ise (`SZL-2025-003_temizlik-hizmet`, `p4-…`, `PRSIM-1234-…`) token sayılmaz. Parça içinde harf+rakam karışık uzun parçalar ve ayraçlı rastgele harfler yakalanmaya devam eder. Ek kalıp: 32+ karakter hex (harf+rakam), entropi tabanının altında kaldığı için önceden kaçıyordu.
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

## Review r1 düzeltmesi (K-SEN-0040)

MAJOR-1: `is_plain_identifier` ayraçlı rastgele tek-tür harfli sırları muaf tutuyordu (`kemubcrdlsbq-gbcnnchcrnbs-dhuusbssmbhb`). Düzeltme: uzun harf segmenti ancak sözcük gibiyse düz sayılır: tek tür harf, ≥ %25 sesli, 4 ünsüzlük dizi yok. Büyük harf kodları ≤ 6 harf (`PRSIM`, `SZL`) ve ≤ 3 karakter etiketler (`p4`, `v2`) düz kalır. Tek bir rastgele segment, değerin tamamını entropi kontrolünde tutar.

Seçenek A'dan sapma (gerekçeli): inceleyici segment başına entropi önerdi. Ölçüm, bu uzunlukta entropinin sözcükle rastgeleyi ayırmadığını gösterdi:

| segment | entropi (bit/karakter) | sesli payı |
|---|---|---|
| kemubcrdlsbq (rastgele) | 3.42 | 0.17 |
| gbcnnchcrnbs (rastgele) | 2.63 | 0.00 |
| dhuusbssmbhb (rastgele) | 2.46 | 0.17 |
| sterilizasyon | 3.39 | 0.46 |
| temizlik | 2.75 | 0.38 |
| danismanlik | 2.91 | 0.36 |
| hijyeni | 2.52 | 0.57 |

Bu yüzden "sözlük kontrolü" kolu, sesli payı + ünsüz dizisiyle uygulandı (dış sözlük yok, ağsız).

Testler: `test_08e_6`'ya 4 yeni vaka (ayraçlı rastgele küçük harf, `_` ayraçlı, büyük harf rastgele, sözcükler arasında tek rastgele segment): önce 4 kırmızı, sonra yeşil. `test_08e_5` (belge adları, PRSIM-1234) yeşil kaldı. `data/samples` altındaki tüm dosya adları tarandı: hiçbiri bulgu vermiyor.

Kapılar: lint 0; llmaas 667 passed; airgap ilk koşu FOLLOWUP-97'nin iki 04a testi, tekrar 667 passed.
