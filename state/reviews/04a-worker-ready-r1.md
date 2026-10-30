# 04a worker-ready · review r1

**Paket:** fix/04a-worker-ready (FOLLOWUP-97) · **Baz:** main 28d7a5f · **Tam SHA:** 3cecab486a37e9c68b1827f159f8bec95f05109d (1 commit, 8 dosya)
**Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 1.

## İstenen beş kontrol

1. **ready protokolü, kilitlenme ve kill yolu.** `wait_ready` `poll(timeout)` ile sınırlı; sessiz işçi `_start_timeout` ile öldürülüp `convert_worker_start_timeout` döner; ölen işçi `EOFError` ile `worker_died` olur. `kill` metodu değişmedi. Kilitlenme yok.
2. **PersistentPool yeniden doğan işçi.** Hata yolunda `_worker` `None` oluyor; sonraki çağrıda yeni `_Worker` (`ready=False`) ve `wait_ready` çalışıyor. Test 2 bunu doğruluyor (kill, `_worker is None`, sonra yeniden dönüşüm başarılı).
3. **Kırmızı kanıtı ve duvar saati.** `state/pr/04a-worker-ready-kapilar/red.log`: yeni testler eski kodda 5 failed, 2 passed. Testlerde süre üst sınırı yok; gecikme yalnız `FFCORE_TEST_START_DELAY` ile hedef işçinin içinde.
4. **.env.example / compose.** `CONVERT_WORKER_START_TIMEOUT_SECONDS=60` düz sayı, secret değil; `.env.test` bu commit'te değişmedi.
5. **Yük altında 10/10.** `load-10c.log`: 10 koşu, her biri 7 passed (14 CPU yakıcı altında).

## Komutlar

| Komut | Ortam | Sonuç |
|---|---|---|
| `pytest tests/unit/test_04a_convert.py` | `ffcore/tools:0.0.0-review-06a`, read-only worktree, `--env-file .env.test` | 29 passed |
| aynı, `.env.test` olmadan | aynı | 1 failed (test_04awr_5), 28 passed |

## Bulgular

**MINOR-1, test_04awr_5 ortama bağlı.** Test `Settings(...)`'i ortam değişkeni olmadan kuruyor; `offline`, `service_token`, `obo_jwt_secret`, `secret_key` gibi zorunlu alanlar yoksa pydantic hatası veriyor. Compose'un tools servisi `.env.test` yüklediği için kurumsal koşuda geçiyor, ama test kendi başına izole değil. Öneri: testte gerekli alanları `monkeypatch.setenv` ile vermek ya da `Settings`'e açık değerler geçmek. (Tools servisinin `env_file` ile `.env.test` yüklediği bu incelemede ayrıca doğrulanmadı.)

## Kalan riskler

- Model yüklemesi ilk belgenin dosya süresinde kalıyor (PR'da açık, K-04aWR-0002 A); ilk belge yavaşsa yine zaman aşımına girebilir.
