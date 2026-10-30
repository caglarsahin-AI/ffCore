# PR 18-cost-timing (FOLLOWUP-76)

**Paket:** 18 takip · **Sınıf:** [A] (yalnız test) · **Branch:** fix/18-cost-timing · **Baz:** main 87173d7 · **SHA:** 2ea56d213cb37bd7cb5871093413688cfc0b477c
Karar K-SEN-0015 A; PR-HAZIR K-SEN-0018. Tek dosya: `backend/tests/unit/test_08_cost.py` (+32/-19).

## Değişiklik

- `test_08_9_cost_scales_linearly` (yeni): N=1000 ve N=10000 tekrarlı e-posta için `process_time` (her biri `REPEATS=3` koşunun en iyisi); `large / small < MAX_RATIO=25`. Doğrusal ≈10, karesel ≈100.
- `run_evaluate`: karar + CPU + duvar saati döner; tek sınır `HANG_S=10` duvar saati asılı kalma koruması (assertion mesajı "hang guard"). Mutlak bütçe dosyada kalmadı (KARARLAR kalıcı kuralı).
- `test_08_9_repeated_value_bounded_and_masked[320|640|10000]`, `largest_allowed_mixed_text`, `latency_includes_the_preview`, `08_20`: maske, önizleme ≤ 60, bulgu sayısı (`len(pii.matches) == repeats`) assertion'ları aynen; yalnız bütçe parametresi kalktı.

## Kanıt

Ortam: `FFCORE_VERSION=0.0.0-18ct`, `docker compose -p ffcore-18ct run --rm --no-deps tools`, 7 CPU. "Eski" = main 87173d7'deki dosya (134f868, process_time bütçesi), kanıt için geçici kopya `test_08_cost_old.py` (commit'te yok).

| Koşul | Eski (87173d7) | Yeni (2ea56d2) |
|---|---|---|
| Yüksüz | 6 passed | 7 passed |
| 28 CPU yakıcı süreç (başka süreç yükü), 5 koşu | 5/5 geçti (bu yükle kırmızı çıkmadı) | 5/5 geçti (6-14 s) |
| Süreç içi yük: pytest sürecinde 2 meşgul iş parçacığı (geçici `-p busy_threads_plugin`, commit'te yok), 5 koşu | 1/5 düştü: CPU ataması, `cpu 1.0786 s > 1.0` (`[10000-1.0]`) | 5/5 geçti |

Bulgu: `process_time` aynı süreçteki diğer iş parçacıklarının CPU'sunu da sayar; eski mutlak bütçe bu yüzden süreç içi yükte aşılabilir. Kapıdaki (main) düşüşün nedeni doğrulanmadı.

Oran dağılımı, 28 yakıcı altında 10 örnek (small = N=1000, large = N=10000, saniye CPU):

| # | small | large | oran |
|---|---|---|---|
| 1 | 0.0468 | 0.3007 | 6.43 |
| 2 | 0.0388 | 0.3268 | 8.43 |
| 3 | 0.0428 | 0.3429 | 8.01 |
| 4 | 0.0434 | 0.3086 | 7.12 |
| 5 | 0.0427 | 0.3312 | 7.76 |
| 6 | 0.0459 | 0.3105 | 6.76 |
| 7 | 0.0457 | 0.3176 | 6.95 |
| 8 | 0.0567 | 0.4153 | 7.33 |
| 9 | 0.0669 | 0.4630 | 6.92 |
| 10 | 0.0501 | 0.4107 | 8.20 |

min 6.43, maks 8.43 (eşik 25).

Diş kanıtı (host py3.12, yüksüz, `--noconftest`): `evaluate` önüne yapay karesel ek maliyet (n²/4 döngü) → oran 67 / 26 / 66, 3/3 yakalandı. Not: Windows `process_time` 15.6 ms adımlı, küçük ölçüm gürültülü (26 bu yüzden); CI Linux konteynerinde çözünürlük ince (yukarıdaki tablo).

## Kapılar

| Komut | Sonuç |
|---|---|
| `make lint` | 0; 250 dosya biçimli |
| `make test` `DEPLOY_PROFILE=airgap` | 584 passed (2:35) |
| `make test` `DEPLOY_PROFILE=llmaas` | iki koşuda 1 failed / 583 passed; **bu dalın dışında** (aşağıda) |

llmaas düşüşleri, her koşuda farklı 04a testi, ikisi de süreç havuzu `timeout=2` s duvar saati:
1. `test_04a_persistent_pool_reuses_its_process_and_replaces_it_after_timeout` (`'' == 'fast1'`); tek başına 3/3 geçti.
2. `test_04a_9d_timeout_kills_worker_and_continues`.
Bu dal `test_08_cost.py` dışında dosyaya dokunmaz. FOLLOWUP-97 (isci-a).

Yığın: YIGIN-AÇ T-18-0025, down -v + YIGIN-KAPA T-18-0027. Loglar: scratchpad `costfix/` (load.log, red2.log, red3.log, lint.log, test-*.log, 04a-rerun.log).

## Kalan riskler

- `process_time` süreç içi iş parçacıklarını saymaya devam eder; oran iki ölçümü birlikte etkilendiği için dayanıklı, ama küçük ölçüm sırasında ani bir süreç içi yük oranı geçici düşürür (gevşeme yönü, yanlış alarm değil).
- Karesel gerilemenin küçük katsayılısı (N=10000'de ek maliyet < ~2× doğrusal) eşiğin altında kalabilir; bu tasarım gereği (eşik 25).
