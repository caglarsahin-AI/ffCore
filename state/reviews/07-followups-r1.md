# fix/07-followups · review r1

**Tam SHA:** d9d66fbabf74b3bb22c19a106c6b5489fed26739 (4 commit, 15 dosya; state/ değişikliği yok) · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 1.

## Statik okuma

- `runtime/events.py` `follow`: Redis yayını başarısız olsa bile satır önce Postgres'e commit ediliyor; yeniden bağlanan istemci, bitmiş run için kayıtlı satırları alıp akışı kapatıyor (FOLLOWUP-104). Keepalive turunda iki tur bekleme var; normal bitişte token'lar iki kez gitmiyor.
- `api/approvals_internal.py`: kanca `FFCORE_TEST_HOOKS` kapalıyken route bağımlılığında 404 veriyor; servis jetonu ondan sonra kontrol ediliyor. `sweep` artık süresi dolan onayları döndürüyor; tekrarlı çağrı koşullu güncellemeler yüzünden değişiklik üretmiyor.
- `config.py` varsayılanı `False`; `deploy/docker-compose.yml` `${FFCORE_TEST_HOOKS:-0}`; `.env.example` 0. Paylaşılan `app-env` bloğuna eklendi; işçi servisler bu değişkeni okumuyor.

## Koşular (yığın review07f, SHA d9d66fbabf74b3bb22c19a106c6b5489fed26739, `down -v` ile kapatıldı)

| Koşu | Dosyalar | Sonuç |
|---|---|---|
| `FFCORE_TEST_HOOKS=1` | `test_07f_followups.py`, `test_07f_sql_context_roles.py`, `test_07f_compose.py`, `test_07f_follow.py` | 9 passed, 1 failed (`test_07f_3`, aşağıda) |
| bayraksız (varsayılan) | aynı dört dosya | 10 passed (log: `state/evidence/07f-r1-hooks-off.log`) |
| Negatif probe (`state/reviews/07f-negative-probe.py`) | anonim çağrı, bayraksız | 1 passed: anonim sweep yanıtı bilinmeyen yolla bayt-eşit 404 |

Redis yayın hatası testi (`test_07f_2`) ve sql-context pozitif testi (`test_07f_6`) bayraksız koşuda geçti; bayraklı koşuda da geçti.

## Bulgular

**MINOR-1, `test_07f_3` ortama bağlı.** Test `settings.ffcore_test_hooks is False` diye varsayılan değeri doğruluyor; bayrak açıkken koşunca kırmızı. Ürün davranışı doğru (bayrak açıkken 404 olmaması beklenen), ama test bayrağı açıkça kapatmalı (`hooks` fixture'ının tersi, `monkeypatch` ile False). Bu bir test hijyeni sorunu.

## Kalan riskler

- Sweep kancası yalnızca test stack'inde açılmalı; compose varsayılanı 0, ama test stack'i açıkken `now` parametresi süresi dolmamış onayları da kapatabilir. Bu tasarımın gereği.
