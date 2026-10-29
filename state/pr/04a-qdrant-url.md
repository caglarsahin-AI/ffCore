# PR: [A] fix(04a): make test-int Qdrant varsayılanı boş değerde de uygulanır

**Paket:** 04a takibi (FOLLOWUP-84, review 04a r2 MINOR-1) · **Sınıf:** [A] · **Branch:** fix/04a-qdrant-url · **Baz:** main ee30e03 · **SHA:** 076268c974177886d8090696b863b99ab72b4367 · 1 commit, push yok · **Cevap:** K-04a-0025

## Ne değişti

- `Makefile`: `QDRANT_URL ?= …` → `QDRANT_URL := $(or $(QDRANT_URL),http://qdrant:6333)`; aynısı `RUN_QDRANT_TESTS` için. Compose app-env `QDRANT_URL: ${QDRANT_URL:-}` değişkeni tools'a **boş değerle** veriyor; GNU make `?=` tanımlı-boş değişkeni doldurmaz, Qdrant testleri boş endpoint'le koşuyordu. `$(or)` unset ve boşu doldurur; ortamdan ya da komut satırından açık değer kazanır.
- `backend/tests/contract/test_04a_makefile_test_int.py` (yeni, 3 test): `make -n test-int` çıktısı unset ve boş ortamda `QDRANT_URL=http://qdrant:6333 RUN_QDRANT_TESTS=1`; açık değer (`http://other:6333`, `0`) korunur. `make` yalnız tools imajında; yoksa test açık gerekçeyle skip (host'ta make kurulmaz, K-00-0003).

Compose'a dokunulmadı (tools'a açık test URL'si vermek ürün env'ini testle karıştırırdı; tek yer Makefile).

## Kanıt

Hepsi `FFCORE_VERSION=0.0.0-04a docker compose -p 04a-knowledge-core --env-file .env.test run --rm tools …`, ayrı worktree `.worktrees/fix/04a-qdrant-url`, qdrant + fake-llm ayakta.

| Komut | SHA | Sonuç |
|---|---|---|
| tools içinde `echo $QDRANT_URL; make -n test-int` | ee30e03 | env `[]`; `QDRANT_URL= RUN_QDRANT_TESTS=1 pytest tests/integration` |
| `pytest tests/contract/test_04a_makefile_test_int.py` | ee30e03 + yeni test | **1 failed** (empty), 2 passed (unset, explicit; beklenen: `?=` unset'i zaten dolduruyordu) |
| `make test-int` (belgeli komut, ek bayrak yok) | ee30e03 | **7 failed, 200 passed, 4 errors** (review'daki sayıyla aynı) |
| `make -n test-int` | 076268c | `QDRANT_URL=http://qdrant:6333 RUN_QDRANT_TESTS=1 pytest tests/integration` |
| `make lint` | 076268c | 0, 195 dosya |
| `make test` | 076268c, llmaas / airgap | 385 / 385 passed |
| `make test-int` | 076268c, llmaas / airgap | 207 / 207 passed |

## Düzeltme (önceki PR metni)

04a PR'ında (state/pr/04a.md, 5402760 commit mesajı) rebase sonrası "Qdrant testleri 7 failed + 4 error" düşüşünü store → api import döngüsüne bağladım. Bu yanlıştı: o koşu `make test-int` ile, yani boş `QDRANT_URL` ile yapılmıştı; yeşil tekrar ise URL'yi açıkça veriyordu. Sayılar bu PR'ın kırmızısıyla aynı. Import döngüsü gerçek (tek başına `test_04a_qdrant.py` ImportError veriyordu, 5402760 onu kapattı) ama 7+4'ün nedeni değildi. r1 MAJOR kanıtları etkilenmez (onlar açık URL'li koşulardı).

## Felsefe

80/20: tek satırlık ortam varsayılanı, yeni hedef yok. Fail-loud: boş endpoint artık sessizce test'e gitmiyor. Belirgin varsayılan: Compose servis adı.
