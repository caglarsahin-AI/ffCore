# Review fix/11-1-parity r1 · kısa teyit (yığınsız, ENV-217)
SHA: 43f5ed86021b41f2d54b192afed3181677e7be0f · Sonuc: ONAY · Bulgu: B0 M0 m0 N0

- **İncelenen tam SHA:** `43f5ed86021b41f2d54b192afed3181677e7be0f` (dal `fix/11-1-parity`).
- **Delta** `main..43f5ed8`: 1 commit (test), 3 dosya, +37/−0. Ürün kodu yok.
- **İstek:** K-11-0015. Sebep: K-11-0013 (11-1 ffmain test-int'te 03a/06a read-mode parity yeni yolların yol parametresini fikstürde bulamıyor).
- **Yöntem:**
  - Delta satır satır okundu. 03a/06a parity döngüsü ve `cited` fikstürü dalın SHA'sından okundu (`git show`).
  - Erişim kipinin istek başına DB'den okunduğu kaynakta doğrulandı (aşağıda madde 3).
  - **Test koşmadım.** Docker sanal diski dolu (ENV-217, K-GEN-0036). Postgres+redis gereken üç dosya için yığın açmadım. İşçi loguna dayandım (aşağıda).
- **Karar: ONAY.** Muafiyetler dar ve gerekçeli. Kapsam kaybı yok: muaf yollar yeni testte aynı karşılaştırmayla sınanıyor.

## Kanıt (işçi logları, yeniden koşulmadı)

| Log | Sonuç |
|---|---|
| `11-1-parity-red.log` (HEAD 97342eb, main) | `test_03a_2_read_mode_get_parity` `KeyError: 'conversation_id'`; `test_06a_read_mode_get_parity` `KeyError: 'chunk_id'`. ffmain kırmızısıyla aynı. |
| `11-1-parity-green.log` | ruff temiz; **27 passed**. HEAD satırı `97342eb + worktree test changes`, yani commit öncesi çalışma ağacı. Logdaki diff stat (3 dosya +37) commit'le birebir aynı; içerik eşitliğini ayrıca doğrulamadım. |
| `11-1-parity-make-test.log` (HEAD 43f5ed8) | `make test` **2159 passed** (birim; bu üç dosyayı kapsamaz). |

## Kontrol listesi (K-11-0015)

| # | Madde | Sonuç |
|---|---|---|
| 1 | **Muafiyetler yalnız iki yol mu, gerekçeli mi** | Evet. <br>• 03a: `PARITY_EXEMPT_PREFIXES`'e `…/conversations/{conversation_id}` eklendi. Bu önek altında tek GET `…/messages`; aynı yoldaki DELETE zaten GET değil. Gerekçe yorumda yazılı: çağıranın kendi konuşması gerekiyor; parity `test_11_4`'te. <br>• 06a: döngüde `path.endswith("/sources/{chunk_id}")` atlanıyor. `runs/{run_id}` öneki altında bu sona sahip tek yol `get_run_source`. Gerekçe yazılı. `checked == 8` değişmedi: muafiyet öncesi sayılan sekiz yol aynen sayılıyor. |
| 2 | **`/chat/agents` ve konuşma listesi 03a'da kalıyor mu** | Evet. Önek `…/conversations/{conversation_id}` ile bitiyor; `startswith` ile `…/conversations` (liste) ve `…/chat/agents` eşleşmiyor. İkisi 03a'da edit 200 + read aynı gövde olarak sınanmaya devam ediyor. |
| 3 | **`test_11_4_read_mode_get_parity` read/edit aynı gövde** | Dört 11-1 GET'i: `/chat/agents`, `/conversations`, `/conversations/{id}/messages`, `/runs/{run_id}/sources/{chunk_id}`. Aynı üye (`user` rolü, süperadmin değil) önce `edit`, sonra `read` kipinde istiyor. Edit'te dördü de 200, read'de durum ve gövde (`response.content`) birebir aynı olmalı. <br>Kip değişikliği gerçekten etkili: `core/auth.py` 432-438 `ProjectMember`'ı her istekte DB'den okuyor, önbellek yok. Yani `UPDATE project_members` sonraki istekte geçerli. `UPDATE` projenin tüm üyelerine dokunuyor; `cited` fikstüründe projede tek üye var. |
| 4 | **Başka değişiklik** | Yok. Üç test dosyası, yukarıdaki satırlar. |

## e2e `@model-missing` (K-11-0013, ENV-204 şüphesi)
Bu dalın kapsamında değil. `11-1-parity-model-missing.log` (HEAD ac834fe) yığın kurulumunda düşmüş: `ffcore-11-redis-1 is unhealthy`. Test sonucuna ulaşmamış. Disk doluluğuyla (ENV-217) uyumlu, ama ben doğrulamadım.

## Bekleyen dosyalar (commit edilmedi)
- `state/reviews/11-1-parity-r1.md`
- `state/kanal/inceleyici.md`
