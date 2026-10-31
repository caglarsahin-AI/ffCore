**Paket:** fix/07-test-hooks-flag (FOLLOWUP-114) · **Sınıf:** [A] · **Branch:** fix/07-test-hooks-flag · **Baz commit:** e5074ab

## Plan (kodlamadan önce)
1. Bulunan semboller ve dosyalar: `backend/tests/integration/test_07f_followups.py` — `hooks` fixture'ı (satır 89-94: `settings.model_copy(update={"ffcore_test_hooks": True})` + `app.dependency_overrides[get_settings]`), `test_07f_3_sweep_hook_404_when_flag_off` (satır 106-112: `assert settings.ffcore_test_hooks is False`, override yok, uygulama ortamdan gelen ayarla koşar). Ürün tarafı: `backend/ffcore/api/approvals_internal.py:30` `test_hooks_on` bağımlılığı `Depends(get_settings)` ile okur; `core/config.py:132` `ffcore_test_hooks: bool = False`; `tests/integration/conftest.py:126` `app` fixture'ı `get_settings`'i `app_settings` ile override eder (ortamdan, `FFCORE_TEST_HOOKS=1` ise True). Kırmızı kanıtı zaten var: state/evidence/07f-r1-hooks-on.log (bayraklı 9/10, satır 107 `assert True is False`).
2. Kapsam: yalnız test_07f_3 bayraktan bağımsız olur. Kapsam dışı: ürün kodu, compose, diğer 07f testleri, FOLLOWUP-118 (e2e yığını izolasyonu).
3. Değişecek dosya: yalnız `backend/tests/integration/test_07f_followups.py`. `hooks` fixture'ı bayrak değerini parametre alan küçük bir yardımcıya dönüşür; yeni `hooks_off` fixture'ı aynı yoldan `ffcore_test_hooks=False` override eder; test_07f_3 ortam ayarına değil `hooks_off`'a bağlanır ve onu doğrular.
4. Sözleşme, yapılandırma, profil etkisi: yok (test dosyası). İki profilde aynı.
5. Kabul kriteri → test: (a) bayraklı (`FFCORE_TEST_HOOKS=1`) koşuda 07f 10/10 → `test_07f_*`; (b) bayraksız koşuda 10/10 → `test_07f_*`; (c) önce kırmızı: düzeltmeden önce bayraklı koşuda `test_07f_3` düşer (bu oturumda yeniden üretilir); (d) `make lint` 0; (e) `make test` iki profil (birim; dosya entegrasyon olduğu için etkilenmez, kapı olarak koşar).
6. Migration: yok.
7. Geri alma: tek commit revert.
8. Durma koşulları: ürün kodunda değişiklik gerekirse (ör. kanca ayarı `get_settings` dışından okursa) dur, koordinatöre yaz.
9. Felsefe kontrolü: ARCH-07 tek test, kalıcı karmaşıklık yok; ARCH-09 FastAPI `dependency_overrides` kullanılır, yeni mekanizma yok; ARCH-10/06 test artık ortam değişkenine örtük bağlı değil, varsayımı açık override eder; sessiz atlama yok.

Yığın: `-p 114`, 18080/13080 (BACKEND_PORT/FRONTEND_PORT komut satırında), `FFCORE_VERSION=0.0.0-114`, `--profile test --profile qdrant`, temiz volume; e2e yığınında koşulmaz (FOLLOWUP-118). Bitince `down -v` + YIGIN-KAPA.

**HEAD:** 04347ee53af100df3742507810e0b20203bd0f9c (e5074ab üstüne 1 commit)

## Değişen dosyalar
- backend/tests/integration/test_07f_followups.py (+16 −6): `_with_hooks(app, settings, enabled)` yardımcısı; `hooks` onu True ile çağırır (davranış aynı), yeni `hooks_off` False ile; `test_07f_3` `settings` yerine `hooks_off` alır ve onu doğrular.

## Kabul kriterleri → testler
| # | Kriter (K-114-0001) | Test | Durum |
|---|---|---|---|
| 1 | Önce kırmızı: düzeltmeden önce bayraklı koşuda test_07f_3 düşer | `test_07f_3_sweep_hook_404_when_flag_off` @ e5074ab, `FFCORE_TEST_HOOKS=1` | kırmızı (1 failed, 3 passed; satır 107 `assert True is False`) |
| 2 | Bayraklı koşu 10/10 | 07f dört dosya (r1'deki küme: integration/test_07f_followups.py, integration/test_07f_sql_context_roles.py, unit/test_07f_compose.py, unit/test_07f_follow.py), `FFCORE_TEST_HOOKS=1` | 10 passed |
| 3 | Bayraksız koşu 10/10 | aynı dört dosya, `FFCORE_TEST_HOOKS=0` | 10 passed |
| 4 | Ürün kodu değişmez | `git diff --stat e5074ab..HEAD` yalnız test dosyası | geçti |

## Çalıştırılan komutlar
Hepsi `FFCORE_VERSION=0.0.0-114 BACKEND_PORT=18080 FRONTEND_PORT=13080 docker compose -p 114 --env-file .env.test --profile tools run --rm -T [-e ...] tools ...`; yığın `--profile test --profile qdrant --profile tools`, temiz volume (yeni proje 114). Loglar `state/evidence/`.

| Komut | Ortam | Exit | Süre | Log |
|---|---|---|---|---|
| `pytest -q tests/integration/test_07f_followups.py` @ e5074ab | `FFCORE_TEST_HOOKS=1` | 1 (beklenen kırmızı) | 61 s | fix-114-red-hooks-on-20261031.log |
| `pytest -q` 07f dört dosya | `FFCORE_TEST_HOOKS=1` | 0 (10 passed) | 45 s | fix-114-hooks-1-20261031.log |
| `pytest -q` 07f dört dosya | `FFCORE_TEST_HOOKS=0` | 0 (10 passed) | 42 s | fix-114-hooks-0-20261031.log |
| `make lint` | | 0 | | fix-114-lint-20261031.log |
| `make test` | `DEPLOY_PROFILE=llmaas` | 0 (725 passed) | 152 s | fix-114-test-llmaas-20261031.log |
| `make test` | `DEPLOY_PROFILE=airgap` | 0 (725 passed) | 136 s | fix-114-test-airgap-20261031.log |
| `make test-int` (tam) | | NOT_RUN | | gerekçe: değişen tek dosya entegrasyon testidir ve tam olarak iki bayrakla koşuldu; diğer dosyalar bu fikstürleri import etmiyor (`hooks`/`hooks_off` yalnız bu dosyada). Main kapısı test-int koşar |
| `down -v` | | 0 (konteyner 0, volume 0) | | |

Migration yok. Commit'ten sonra yeniden koşu yok; commit'lenen içerik koşulan çalışma ağacıyla aynı (tek dosya, `git status` temiz).

## Kontrol listesi
- [x] Felsefe ile çelişen nokta yok
- [x] Donmuş sözleşme kırılmadı (yalnız test)
- [x] İki profil testi koştu
- [x] Mutasyon ucu / audit: değişiklik yok
- [x] Log, PR metni secret-free
- [ ] Önyüz yok
- [x] Docs değişmez (davranış aynı)

## Varsayımlar ve brief'teki çelişkiler
- `.env.test` değiştirilmez; bayraklı koşu `FFCORE_TEST_HOOKS=1` ortamıyla `tools` konteynerine verilir.

- Varsayılanın `False` olduğu artık test_07f_3'ün değil `core/config.py:132` ve `tests/unit/test_07f_compose.py`'nin kanıtıdır (compose varsayılanı 0); test_07f_3 yalnız "bayrak kapalıyken 404" davranışını sınar.

## Kalan riskler
- Yok bilinen. FOLLOWUP-118 (entegrasyon testlerinin e2e yığınında LiteLLM modellerini kaybettirmesi) bu PR'ın kapsamı dışında, açık.
