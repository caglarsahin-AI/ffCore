# Örnek veri üreticileri (paket 13a, 18-hazirlik)

`data/samples/` altındaki her dosya bu betiklerin çıktısıdır; elle düzenlenmez. Tamamen sentetiktir: gerçek kurum belgesi, gerçek kişi ya da hasta verisi yoktur.

## Çalıştırma

Yalnızca Python 3.12 standart kütüphanesi gerekir (`requirements.txt` bilerek boş).

```bash
py -3.12 data/samples/scripts/generate.py                 # hepsi, seed 13
py -3.12 data/samples/scripts/generate.py --only eval,pii # seçili modüller
py -3.12 -m unittest discover -s data/samples/scripts/tests -v
docker compose run --rm tools make test-samples           # aynı testler tools konteynerinde
```

Aynı seed aynı baytları üretir (`test_13a_8_deterministic` depodaki dosyaları yeni üretimle karşılaştırır). Seed değişirse tüm modüller yeniden üretilir; her modülün kendi rastgele akışı vardır (`"<seed>:<modül>"`), biri değişince diğeri değişmez. Not: PDF ve DOCX sıkıştırması zlib kullanır; farklı bir zlib derlemesi bayt farkı üretebilir, içerik aynı kalır.

Postgres yükleme testi isteğe bağlıdır ve Docker ister (00'ın pinlediği `pgvector/pgvector:0.8.1-pg16`, port yayınlamayan geçici `ffcore-13a-pg` konteyneri):

```bash
RUN_PG_TESTS=1 py -3.12 -m unittest data.samples.scripts.tests.test_13a_pg -v
RUN_PG_TESTS=1 py -3.12 -m unittest data.samples.scripts.tests.test_18_pg -v   # sql-20 ve yazma denemeleri
```

## Modüller ve tüketiciler

| Dizin | İçerik | Tüketen paket |
|---|---|---|
| `contracts/` | 5 sözleşme (2 PDF, 3 DOCX) ve `manifest.json` (ACL: analyst, admin, boş) | 04a ingest/arama/ACL, 06a, 13b |
| `schema/` | demo sunum DB'si: şema, 10.000 satır seed, salt-okunur rol şablonu, `schema_descriptions`, 20 few-shot | 05a mcp-sql, 13b |
| `agents/` | `sozlesme-asistani`, `veri-soru-cevap` (PLAN 2d: tek, onaylı `run_sql`; şema açıklaması ve few-shot'lar sistem prompt'unda, `get_schema` ve `ask_user` yok), `karma-asistan` | 06a, 10b, 13b |
| `eval/` | `sozlesme-33.json` (12 doğrudan, 8 dolaylı, 5+3 cevapsız, 5 SQL) ve `suite.json` | 09, 13b |
| `eval/` (18) | `sql-20.json` + `suite-sql-20.json` (F3 sınavı: 13a'nın 5 SQL sorusu + 15 yeni), `sql-write-attempts.json` (F3 olumsuz testi: mcp-sql'in reddetmesi gereken 12 ifade ve beklenen 05a ret kodu) | 09, 13b, plan/18 F3 |
| `poison/` (18) | 5 talimat gömülü prosedür belgesi (`docs/*.txt`), 3 talimat gömülü bilet (`tickets-poison.jsonl`) ve `expected.json` (cevapta olması ve olmaması gerekenler, yasak araç çağrıları) | plan/18 F11 |
| `projects/` (18) | iki proje, her birinde admin/edit, admin/read, analyst/edit üyesi (şifresiz), kaynaklar ve izolasyon beklentisi; B projesinin tek belgesi | 13b seed, plan/18 F10 |
| `versions/` (18) | 13a'nın iki DOCX sözleşmesinin tarihli v2'si ve `expected.json` (değişen madde, v1/v2 değeri, soru) | plan/18 F13, 04b |
| `tickets/` (18) | `tickets-20.jsonl` (20 sentetik destek bileti; 5'inde PII span'i) ve ayrı `labels.json` (beklenen sınıf + gerekçe) | plan/18 F2, sahte `ticket-desk` aracı |
| `pii/` | 100 etiketli Türkçe PII cümlesi (19 kategori, 10 negatif) ve kategori kodları | 08 |
| `memory/` | 40 beklenen çıktılı hafıza konuşması | 14 |
| `openapi/` | Superset alt kümesi (6 işlem) | 05b |

`openapi/superset.yaml` içinde onay bilgisi yoktur; onay `tool_actions.needs_approval` ayarıdır. 05b testi `createChart` ve `addChartToDashboard` aksiyonlarını onaylı işaretler.

## Kişi adları (DECISION-24)

Kişi adı yalnızca `pii/` (20 cümle, `PERSON` span'i) ve `memory/` (4 konuşma, `contains_person_name: true`) içinde geçer. Adlar `gen/pii.py` içindeki sabit havuzdandır: yaygın adlar ile uydurma soyadlarının birleşimi; gerçek bir kişiyle çakışmaması amaçlanır ama bu, dış kaynağa bakılmadan kanıtlanamaz. `test_13a_9_no_person_names_outside_pii_memory` havuzdaki hiçbir adın sözleşme, şema, sınav, agent ve OpenAPI dosyalarında geçmediğini kanıtlar.

## Açık noktalar

- Agent şablonlarının 06a Pydantic şemasıyla gerçek uyumu 06a/13b'de doğrulanır.
- PDF metin katmanının Docling ile okunması 04a ingest testinde doğrulanır; burada standart kütüphaneyle yapısal geri okuma yapılır.

## Kullanım senaryoları verisi (paket 18-hazirlik, plan/18)

- `sql-20.json`: beklenen sonuçlar elle yazılmaz; `gen/scenarios_sql.py` her soruyu `schema.build()` satırlarından hesaplar (seed.sql'in kaynağı aynı) ve `test_18_f3_4` her `metadata.reference_sql`'i gerçek Postgres'te `agent_readonly` ile koşup karşılaştırır. İlk beş soru `sozlesme-33.json`'dan alınır (`metadata.origin`), ids `sql-01`…`sql-20`. `sql_result` hücreleri: sayımlar tam sayı, ondalık ve tutarlar metin (`"442.9"`), tarihler `YYYY-AA-GG`. Boş, NULL ya da tek `0` sonuçlu soru üretilmez (bulamayan model şansla geçerdi). Hiçbir soru bir few-shot'ı tekrarlamaz. `metadata.tags`: `sql` + `join`, `group`, `date`, `null`, `multi_row`.
- `sql-write-attempts.json`: `class` = `write` (düz yazma), `hidden_write` (CTE, ikinci ifade, `SELECT INTO`), `catalog` (sistem kataloğu/fonksiyonu). `expected_code` 05a'nın doğrulayıcı kodlarıdır; 05a merge'ünden sonra gerçek doğrulayıcıya karşı denenir. `test_18_f3_7` yazma sınıflarının veritabanı katmanında da (`agent_readonly`) reddedildiğini ve satır sayısının değişmediğini kanıtlar.
- `tickets/`: sınıflar kapalı liste `access, billing, bug, how_to, other` (5/4/5/4/2); her sınıfta ihtiyacı dolaylı anlatan en az bir bilet. Etiketler ayrı dosyada; sahte bilet aracı yalnız `tickets-20.jsonl`'ı sunar. PII yalnız 5 bilette ve yalnız 08-lite regex kategorilerinde (TC kimlik, telefon, e-posta, IBAN); `test_18_f2_2/3` 08-lite'ın kendi tanıyıcısıyla (`backend/ffcore/guardrails/recognizers/regex.py`) etiketli span'lerin tam bulunduğunu ve diğer biletlerde bulgu olmadığını kanıtlar. Kişi adı yok; biletler birim adıyla imzalıdır.
- `poison/`: her belgede tek bir enjeksiyon satırı vardır (numarasız satır; `expected.json` `injection`), geri kalanı sorulabilir bir olgu taşıyan prosedürdür. Kanarya dizgeleri (`KANARYA-…`, `SIZINTI-…`) yalnız enjeksiyon satırında geçer; P5'inki base64 içindedir. Cevapta kanarya görünmesi "talimat uygulandı" demektir. Bilet B2, tkt-002'nin sentetik TC kimlik numarasını sızdırmaya çalışır; `must_not_contain` bu değeri taşır. Belgeler `.txt` (04a `plaintext` yolu, model ağırlığı istemez).
- `projects/`: e-postalar `<proje>-<rol>-<erişim>@example.test`; şifre bu dosyada yok, 13b seed'i verir. `isolation`: B üyeleri A'nın kaynaklarını listede, GET'te, aramada, araç çağrısında ve koşu detayında göremez, beklenen 404.
- `versions/`: v1 `contracts/` altındaki 13a dosyasıdır (kopyalanmaz); v2 13a'nın rastgele akışı yeniden oynatılarak aynı bloklardan üretilir (`contracts.render_all`), tek fark değişen madde ve başa eklenen "Sürüm 2" notudur (`test_18_f13_1/2`). Değişen maddeler F1 sınavında sorulmaz (`test_18_f13_3`); v2'ler e2e'de ayrı bir KB'ye yüklenir.
