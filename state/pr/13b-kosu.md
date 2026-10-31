# 13b-kosu: F tablosu koşusu ve onay TTL negatif testi

**Paket:** 13b-kosu (test rolü, GOREV K-13BK-0001) · **Sınıf:** [A] · **Branch:** feat/13bk-ttl-negative · **Baz commit:** main 3fa8a60 · **HEAD:** 8fd02bd49b6e394a148cc4f8302c941c6ebde53a (tek commit) · push yok

## Plan (kısa; 1 günden kısa iş)
1. Bulunan semboller: `tests/e2e/negative/test_13b_negative.py::test_13b_neg_approval_1` (FOLLOWUP-111 NOT_RUN iskeleti); `backend/ffcore/api/approvals_internal.py` (`POST /api/v1/internal/approvals/sweep?now=`, `FFCORE_TEST_HOOKS=1`, `service_actor` 403 `service_account_required`); `services/approvals.py` (`EXPIRED_RUN_CODE="approval_expired"`, `expire_due`, `run_closer`, 409 `approval_not_pending`); `tests/e2e/scenarios/e2e.env` (bayrak açık); F2 ajanı `e2e-bilet` + `ticket-desk` `/_reset`, `/_sent`.
2. Kapsam: (a) main koduyla yığında `make seed` ×2 + `make e2e` (F tablosu); (b) TTL negatif testi; (c) FOLLOWUP-114'ün bayrak açık ortamda ölçümü. Kapsam dışı: `make eval` (GOREV istemedi), gerçek model, isci-b'nin `test_07f_3` dosyası.
3. Değişen dosya: yalnız `tests/e2e/negative/test_13b_negative.py` (touch-zone).
4. Sözleşme/profil: yok; test kancası yalnız test yığınında (bayraksız 404, 07'nin kendi testi).
5. Kriter → test: aşağıda.
6. Migration: yok. 7. Geri alma: commit revert. 8. Durma: yığın dışı etki, touch-zone dışı dosya.
9. Felsefe: ARCH-07 yeni üretim kodu yok, yalnız test; ARCH-09 07'nin kendi süpürmesi kanca ile çağrılıyor, ikinci süpürme yazılmadı; ARCH-06/10 sessiz atlama kalktı (NOT_RUN → gerçek test), kanca kapalıyken açık 404.

## Kabul → test
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Süresi dolmayan onay süpürmede `pending` kalır, koşu `waiting_approval` | `test_13b_neg_approval_1_expired_approval_closes_the_run` (expires_at − 1 s) | geçti |
| 2 | Süresi dolan onay `expired`, koşu `failed` + `approval_expired`, olaylarda `approval_expired` ve son `error` | aynı test (expires_at + 1 s) | geçti |
| 3 | Geç onay 409 `approval_not_pending`; sahte ticket-desk'e yanıt gitmez | aynı test | geçti |
| 4 | Süpürme idempotent | aynı test (ikinci çağrı) | geçti |
| 5 | Kanca kullanıcı kapısı değil: kimliksiz 401 `unauthenticated`, üye oturumu 403 `service_account_required` | `test_13b_neg_approval_2_sweep_hook_is_for_the_service_account_only` | geçti |

Kırmızı kanıtı: davranış (FOLLOWUP-111) zaten main'deydi, test yeni kapsama. Mutasyonla kanıtlandı: "dolan" süpürme `expires_at − 1 s`'e çekilen kopya düştü (`assert '<approval id>' in []`), asıl test geçti; kopya silindi.

## Çalıştırılan komutlar
Yığın: `docker compose -p ffcore-13bk --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test --profile qdrant`, `FFCORE_VERSION=0.0.0-13bk`, portlar 18050/13050, worktree `.worktrees/feat/13bk-ttl-negative`. Parolalar kabuktan (rastgele, depoda yok).

| Komut | Ortam | Exit | Süre / sonuç |
|---|---|---|---|
| `build` + `up -d --wait` | llmaas (.env.test), FAKE_EMBED=1, fake-llm | 0 | 83 s |
| `make seed` (1) | | 0 | 72 s, created 36, uploaded 15 |
| `make seed` (2) | | 0 | 20 s, created 0, uploaded 0 (idempotent) |
| `make e2e` (1, TTL testi dahil, commit öncesi) | | 0 | 70 s, 64 passed / 0 failed / 22 NOT_RUN |
| `pytest tests/e2e/negative -v -k approval` + mutant | | 1 (beklenen: yalnız mutant) | asıl 2/2 geçti, mutant 1 düştü |
| `pytest backend/tests/integration/test_07f_followups.py -v` | `FFCORE_TEST_HOOKS=1` | 1 | `test_07f_3` düştü (FOLLOWUP-114 doğrulandı), 07f_2/4/5 geçti |
| `ruff format tests/e2e/negative && ruff check tests/e2e && ruff format --check tests/e2e && make lint` | tools | 0 | |
| `make render-litellm` (onarım, aşağıya bkz.) | | 0 | created 8 |
| `make seed` (3) | | 0 | 20 s, created 0, uploaded 0 |
| `make e2e` (2, HEAD 8fd02bd) | | 0 | 69 s, **64 passed / 0 failed / 22 NOT_RUN** |
| `down -v` | | 0 | konteyner 0, volume 0 |
| `make test` | | NOT_RUN | backend/üretim kodu değişmedi; yalnız tests/e2e (make test kapsamı dışı) |
| `airgap` profili | | NOT_RUN | e2e yığını `.env.test` (llmaas); airgap gerçek koşu kullanıcı sunucusunda (M3) |

## F tablosu (HEAD 8fd02bd, eval/results/e2e-20261031-0616.md)

| Use case | Status | Passed | Failed | NOT_RUN | NOT_RUN gerekçesi (özet) |
|---|---|---|---|---|---|
| F1 | passed | 2 | 0 | 2 | gerçek model (declined, sozlesme-33 skoru) |
| F2 | passed | 5 | 0 | 3 | gerçek model (ret sonrası cevap, triyaj ≥ %80, PII'li bilet) |
| F3 | passed | 2 | 0 | 1 | gerçek model (sql-20 ≥ %80) |
| F4 | passed | 4 | 0 | 2 | kota 03c; gerçek model (araç argümanı) |
| F9 | passed | 2 | 0 | 1 | dataset otomasyonu 09 |
| F10 | passed | 4 | 0 | 0 | |
| F11 | passed | 5 | 0 | 7 | gerçek model; injection tanıyıcısı 08 tam |
| F12 | passed | 2 | 0 | 4 | servis durdurma compose düzeyi koşucu ister (Langfuse, Qdrant, LLM_SLOTS, airgap sağlayıcı) |
| F13 | passed | 2 | 0 | 2 | gerçek model (v2 değeri + tarih) |
| Negative | passed | 14 | 0 | 0 | (önceki 12 + yeni 2; TTL NOT_RUN kalktı) |
| Setup | passed | 22 | 0 | 0 | |

Önceki koşuyla fark (docs/demo.md, 30 Ekim): 62 passed / 23 NOT_RUN → 64 / 22 (TTL iskeleti 1 NOT_RUN → 2 gerçek test).

## Olay: entegrasyon testi e2e yığınını bozdu (kendi hatam)
FOLLOWUP-114'ü ölçmek için `backend/tests/integration/test_07f_followups.py`'yi **aynı e2e yığınında** koştum. Sonrasında LiteLLM'de `hastane-a.*`/`klinik-b.*` modelleri yoktu ("no healthy deployments", 400); ardından koşan negatif set 5 kurulum hatası verdi (`answered_run` → `run_error`). Tablolar sağlamdı (models 8, projeler 2). `make render-litellm` ile LiteLLM tablolardan yeniden kuruldu (created 8), seed 0/0, `make e2e` yeniden yeşil. Kök neden doğrulanmadı (integration fikstürlerinin LiteLLM'e uzlaştırma etkisi olduğunu düşünüyorum). Ders: entegrasyon testleri ayrı yığında koşar; nihai kanıt onarım sonrası temiz koşudur. Gözlem (küçük): `render-litellm --check` modu da `litellm_reconciled created=8` log satırı yazıyor (yazmadan, exit 1); log metni yanıltıcı, 01 sahibine not.

## Varsayımlar
- GOREV branch vermedi; touch-zone içinde `feat/13bk-ttl-negative` açıldı (T-13bk-0002).
- `make eval` GOREV kapsamında değil; koşulmadı.

## Kalan riskler
- FOLLOWUP-114 açık: bayrak açık ortamda `test_07f_3` düşer (isci-b).
- F12'nin dört servis-durdurma satırı compose düzeyi koşucu ister; NOT_RUN kalır.
