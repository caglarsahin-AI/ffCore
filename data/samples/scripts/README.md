# Örnek veri üreticileri (paket 13a)

`data/samples/` altındaki her dosya bu betiklerin çıktısıdır; elle düzenlenmez. Tamamen sentetiktir: gerçek kurum belgesi, gerçek kişi ya da hasta verisi yoktur.

## Çalıştırma

Yalnızca Python 3.12 standart kütüphanesi gerekir (`requirements.txt` bilerek boş).

```bash
py -3.12 data/samples/scripts/generate.py                 # hepsi, seed 13
py -3.12 data/samples/scripts/generate.py --only eval,pii # seçili modüller
py -3.12 -m unittest discover -s data/samples/scripts/tests -v
```

Aynı seed aynı baytları üretir (`test_13a_8_deterministic` depodaki dosyaları yeni üretimle karşılaştırır). Seed değişirse tüm modüller yeniden üretilir; her modülün kendi rastgele akışı vardır (`"<seed>:<modül>"`), biri değişince diğeri değişmez. Not: PDF ve DOCX sıkıştırması zlib kullanır; farklı bir zlib derlemesi bayt farkı üretebilir, içerik aynı kalır.

Postgres yükleme testi isteğe bağlıdır ve Docker ister (00'ın pinlediği `pgvector/pgvector:0.8.1-pg16`, port yayınlamayan geçici `ffcore-13a-pg` konteyneri):

```bash
RUN_PG_TESTS=1 py -3.12 -m unittest data.samples.scripts.tests.test_13a_pg -v
```

## Modüller ve tüketiciler

| Dizin | İçerik | Tüketen paket |
|---|---|---|
| `contracts/` | 5 sözleşme (2 PDF, 3 DOCX) ve `manifest.json` (ACL: analyst, admin, boş) | 04a ingest/arama/ACL, 06a, 13b |
| `schema/` | demo sunum DB'si: şema, 10.000 satır seed, salt-okunur rol şablonu, `schema_descriptions`, 20 few-shot | 05a mcp-sql, 13b |
| `agents/` | `sozlesme-asistani`, `veri-soru-cevap` (PLAN 2d: tek, onaylı `run_sql`), `karma-asistan` | 06a, 10b, 13b |
| `eval/` | `sozlesme-33.json` (12 doğrudan, 8 dolaylı, 5+3 cevapsız, 5 SQL) ve `suite.json` | 09, 13b |
| `pii/` | etiketli Türkçe PII cümleleri ve kategori kodları | 08 |
| `memory/` | beklenen çıktılı hafıza konuşmaları | 14 |
| `openapi/` | Superset alt kümesi (6 işlem) | 05b |

`openapi/superset.yaml` içinde onay bilgisi yoktur; onay `tool_actions.needs_approval` ayarıdır. 05b testi `createChart` ve `addChartToDashboard` aksiyonlarını onaylı işaretler.

## Açık noktalar

- Kişi adı içeren PII cümleleri (20) ve hafıza konuşmaları (4) DECISION-24 kararını bekler; o zamana kadar `pii-100.jsonl` 80, `memory-40.jsonl` 36 kayıt içerir ve toplam testleri NOT_RUN döner.
- Agent şablonlarının 06a Pydantic şemasıyla gerçek uyumu 06a/13b'de doğrulanır.
- PDF metin katmanının Docling ile okunması 04a ingest testinde doğrulanır; burada standart kütüphaneyle yapısal geri okuma yapılır.
