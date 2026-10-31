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

## Değişen dosyalar
(doldurulacak)

## Kabul kriterleri → testler
(doldurulacak)

## Çalıştırılan komutlar
(doldurulacak)

## Varsayımlar ve brief'teki çelişkiler
- `.env.test` değiştirilmez; bayraklı koşu `FFCORE_TEST_HOOKS=1` ortamıyla `tools` konteynerine verilir.

## Kalan riskler
(doldurulacak)
