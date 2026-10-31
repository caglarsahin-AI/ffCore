# fix/06a-checkpoint-sources · review r2 (delta)

**Tam SHA:** ceaa7045d66fac8745cdd98b7a25d5857a73779e (r1 ONAY SHA'sı 94f3e07 üstüne 1 commit, 3 dosya; state/ değişikliği yok) · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 1.

## Statik okuma

- `runtime/checkpoints.py` `sweep`: her bekleyen koşu için `try/except`; hata olunca `session.rollback()` (başlatılmamış durum değişikliği geri alınır), `source_deleted_close_failed` uyarısı (run kimliği ve istisna türü, metin yok), `continue`. Diğer koşular kapanıyor.
- `order_by(Run.source_deleted_at)`: en eski işaret önce.
- Hata, `writer.start()` aşamasında (ilk olaydan önce) geri alınıyor. İlk olay yazıldıktan sonra yayın hatası olursa koşu zaten `failed` ve commit'li kalır; `continue` ile `purge` atlanır, ama dakikalık süpürgenin ikinci kısmı (biten ve damgasız koşular) thread'i siler. Yani kayıp yok.
- `docs/agentlar.md`: "en çok bir süpürge aralığı (60 s)" ve `source_deleted_close_failed` davranışı yazılı; r1 MINOR-2 kapandı.

## Koşular (yığın review116, `down -v`; log: `state/evidence/116-r2-int.log`)

| Koşu | Sonuç |
|---|---|
| `test_116_checkpoint_sources.py` (10 test, yeni `test_116_12` dahil) + `test_116_source_state.py` (2) + 3 probe'um | 15 passed |

`test_116_12`: iki bekleyen koşu, ilkinde `RunEventWriter.start` hatası → ikincisi kapanıyor ve thread 0 satır, ilki `waiting_approval` kalıyor, sonraki turda kapanıyor ve thread 0 satır. Eski kodda (izolasyonsuz) istisna `sweep`'ten çıkardı ve test kırmızı olurdu (okumayla).

## Bulgu

**MINOR-1, "aç bırakamaz" iddiası sınırlı.** Koddaki yorum, hata veren bir koşunun toplu işlemde diğerlerini aç bırakamayacağını söylüyor. En eski işaretten başlayan sıralama ve `SWEEP_BATCH = 200` ile bu yalnız 200'den az kalıcı hata varken doğru; 200 koşu kalıcı hata verirse daha yeni koşular işlenmez. Gerçekçi değil ama yorum "en fazla 200 hatalı koşuya kadar" diye daraltılabilir.

## Kalan (r1'den)

- MINOR-1 r1 (`llm_call` metni, FOLLOWUP-119) bu delta'yla değişmiyor; açık.
