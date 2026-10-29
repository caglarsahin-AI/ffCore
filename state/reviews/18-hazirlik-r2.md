# 18-hazirlik r2 bağımsız inceleme

**İncelenen tam SHA:** `e02eaa40191a282a35f8f402f752bb5ddbc5639b`  
**Baz:** `881fe3c`  
**R1 delta tabanı:** `df1e09f8fa617c60942537b322bbb59ad1b3bacf`  
**Karar:** **ONAY**  
**Bulgular:** BLOCKER 0 · MAJOR 0 · MINOR 0

Baz diff'inde `state/**` değişikliği yoktur. İnceleme yalnız exact SHA'nın detached `.worktrees/review-18-hazirlik-r2` ağacında yapıldı.

## R1 MAJOR-1 kapanışı

R1'deki salt katalog okuyan UNION kaydı ayrı `catalog` vakası olarak korunmuş; yeni yazma-etkili vakalar `hidden_write` sınıfına eklenmiştir:

- CTE içindeki `UPDATE` sonucunu UNION'a bağlayan vaka;
- UNION dalında `lo_create()` ile yan etki deneyen fonksiyon vakası;
- satır yorumundan sonra ikinci ifadede `INSERT` vakası;
- önceki CTE, blok yorumlu ikinci ifade ve `SELECT INTO` vakaları.

Her kayıt `patterns` metadata'sı taşır. Birim testi bildirilen kalıbın SQL metninde gerçekten bulunmasını, her `hidden_write` kaydının yazma etkili bir öğe taşımasını ve UNION/CTE/yorum/fonksiyon/ikinci ifade/SELECT INTO kalıplarının eksiksiz kapsanmasını zorunlu tutuyor.

Gerçek Postgres testi bütün `write` ve `hidden_write` kayıtlarını `agent_readonly` rolü ve `default_transaction_read_only=on` ile çalıştırdı. Tümü reddedildi; altı tablonun satır sayıları, tablo listesi, sekans durumu ve large-object sayısı koşu öncesi/sonrası aynı kaldı. R1 MAJOR-1 kapanmıştır.

## Komutlar ve sonuçlar

| Komut / kontrol | Sonuç |
|---|---|
| `git diff --name-status 881fe3c..e02eaa4 -- state` | boş |
| Docker `make test-samples` (`--network none`, kaynak salt-okunur) | exit 0; 50 test geçti, 5 opt-in Postgres testi atlandı |
| `RUN_PG_TESTS=1 ... test_18_pg -v` | exit 0; 2 test geçti, 75.316 s |
| exact-SHA durum/HEAD kontrolü | HEAD eşleşti, çalışma ağacı temiz |
| geçici Postgres konteyner filtresi | boş |

## NOT_RUN

- 05a gerçek SQL doğrulayıcısına karşı `expected_code` matrisi, koordinatörün K-SEN-0008 sınırında belirtildiği üzere 05a merge sonrasına kadar NOT_RUN.
- Backend, iki profil `make test`, e2e ve model testleri bu yalnız beş dosyalık r2 veri/test deltasında yeniden koşulmadı; r1'in bağımsız sonuçları yeni SHA'ya mal edilmedi.
