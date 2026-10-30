# PR fix/08-builtin-version-test

**Paket:** 08 takip (10b-poc-2 kapısında düşen test) · **Sınıf:** [A] (yalnız test) · **Branch:** fix/08-builtin-version-test @ 34f5b892baf52672cb97339b20f175fd7089ca27 (main d68170b üstünde, tek commit) · GOREV K-SEN-0053 · Durum: PR-HAZIR

## Değişiklik

`backend/tests/integration/test_08_api.py::test_08_s5_builtin_default_listed_until_overridden`: `builtin_version == 2` (08 egress düzeltmesi sürümü artırdı) ve yerleşik politikanın kuralları: egress PII kuralı `mode="enforce"`, diğerleri `mode=null` (politikanın modu, monitor). Ürün kodu değişmedi.

## Kanıt (yığın ffcore-08bv, 18020/13020, `--profile test --profile qdrant`)

| Adım | Sonuç |
|---|---|
| eski test (HEAD kopyası) `-k s5` | kırmızı: `assert (None is None and 2 == 1)` (kapıdaki düşüşle aynı) |
| düzeltilmiş test `-k s5` | geçti |
| `make test-int` (Qdrant dahil) | 442 passed, 4 skipped |
| `make lint` | 0 |
| `make test` llmaas / airgap | 696 / 696 passed |

YIGIN-AÇ T-08BV-0001; `down -v` sonrası konteyner 0.
