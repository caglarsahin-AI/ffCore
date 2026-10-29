# 18-hazirlik r1 bağımsız inceleme

**İncelenen tam SHA:** `df1e09f8fa617c60942537b322bbb59ad1b3bacf`  
**Baz:** `881fe3c`  
**Karar:** **DUZELT**  
**Bulgular:** BLOCKER 0 · MAJOR 1 · MINOR 0

Baz diff'inde `state/**` değişikliği yoktur. İnceleme yalnız exact SHA'nın detached `.worktrees/review-18-hazirlik-r1` ağacında yapıldı.

## MAJOR-1 — UNION örneği yazma denemesi değil ve testler bu boşluğu örter

K-SEN-0004 ve plan/18 F3, CTE/UNION/yorum ile gizlenmiş yazma denemelerini ister. Exact SHA'daki `data/samples/eval/sql-write-attempts.json:64` ise UNION örneği olarak `SELECT code ... UNION SELECT usename FROM pg_user` kullanıyor. Bu sorgu yazma yapmaz; yalnız sistem kataloğu okur ve `class=catalog` olarak işaretlenmiştir. Üretici de aynı sorguyu `data/samples/scripts/gen/scenarios_sql.py:236` içinde kuruyor.

Boşluk testlerle yakalanmıyor: `test_18_f3_6_write_attempts_cover_classes` anahtar sözcük listesinde `union` aramıyor (`test_18.py:159-169`), gerçek Postgres yazma testi ise yalnız `write` ve `hidden_write` sınıflarını seçerek `catalog` kaydını dışlıyor (`test_18_pg.py:69`). Böylece 49 örnek-veri testi ve iki Postgres testi yeşil olsa da UNION ile gizlenmiş gerçek bir yazmanın reddi/satır değişmezliği kanıtlanmıyor.

Beklenen: UNION içeren ve gerçekten yazma etkisi deneyen bir negatif vaka eklenmeli; test açıkça UNION kapsamını ve bu vakanın `hidden_write`/eşdeğer yazma sınıfında olduğunu doğrulamalı, gerçek DB/validator kapısı da onu çalıştırmalıdır. Salt katalog UNION vakası ayrı savunma testi olarak kalabilir.

## Doğrulananlar

- Yeni veride kişi adı bulunmadı; PII yalnız işaretli beş bilette 08-lite kategorileriyle üretildi. Poison setindeki sızıntı hedefi de işaretli sentetik bilet değerine bağlıdır; gerçek kişi/kurum izi saptanmadı.
- Üreticiler iki bağımsız üretimde ve depodaki çıktılara karşı bayt eşitliğini geçti. 13a çıktı ağacı da yeniden üretimle eşleşti; mevcut 13a üretilmiş dosyalarında baz farkı yok.
- `sql-20` sonuçları `schema.build()` seed satırlarından türetiliyor; 20 referans SQL gerçek Postgres'te `agent_readonly` ile beklenen sonuçlara eşleşti.
- CTE, ikinci ifade+yorum ve `SELECT INTO` yazma denemeleri gerçek Postgres'te reddedildi; satır sayıları ve tablo listesi değişmedi.
- Beş poison belgesi ve üç poison bileti ile `expected.json` olgu/kanarya/yasak araç eşleşmeleri tutarlı.
- `test-samples` hedefi additive ve belgeli. Backend diff'i sıfır; mevcut `make test` tarifi değişmemiştir.

## Komutlar ve sonuçlar

| Komut / kontrol | Sonuç |
|---|---|
| `git diff --name-status 881fe3c..df1e09f -- state` | boş |
| `make test-samples` | hostta `make` yok: NOT_RUN; aynı hedef yerel `ffcore/tools:0.0.0-18` imajında `--network none`, kaynak salt-okunur koşuldu |
| Docker `make test-samples` | exit 0; 49 test geçti, 5 opt-in Postgres testi atlandı |
| `RUN_PG_TESTS=1 ... test_18_pg -v` | exit 0; 2 test geçti, 67.739 s; geçici portsuz Postgres kendi konteynerini kaldırdı |
| `git diff --quiet ... -- backend` | `BACKEND_DIFF=0` |
| exact-SHA statik veri/üretici/test incelemesi | MAJOR-1 yeniden üretildi |

## NOT_RUN

- `make test` iki profil bağımsız yeniden koşulmadı. İşçinin `441 passed` sonuçları bu review'da bağımsız geçiş sayılmadı. Backend ağacının bazla aynı olduğu ve mevcut `test` tarifinin değişmediği doğrulandı.
- 05a gerçek SQL doğrulayıcısına karşı `expected_code` matrisi, 05a merge edilmediği için NOT_RUN; bu PR'ın kendi beyanındaki sınır korunuyor.
- E2E senaryo, model ve dış sistem testleri bağımlı paketler henüz birleşmediği için NOT_RUN; dış ağ/model kullanılmadı.
