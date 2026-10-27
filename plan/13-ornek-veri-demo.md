# 13. Örnek veri (13a) ve M3 uçtan uca duman testi (13b) [FFCore Platform]

**İki alt paket (A7, B4; PLAN 2d):** **13a "sentetik örnek veri"**: bağımlılık yok, dalga 1'de 00'a paralel, test agent'ı yazar, 1 gün; PoC. **13b "M3 e2e ve ölçüm"**: bağımlılık PoC paketleri ve 00i S1 tabanı, dalga 5, 2 gün; PoC kapısı. **Kalite kabulü PayCore S1 seti** (50 soru, kaynak doğruluğu ≥ %80; iç dokümantasyon sorusu, karar 4; sunucuda kullanıcı eliyle koşar, 00i tabanıyla karşılaştırılır), **akış kabulü** 13a'nın küçük sentetik KB'si (3-5 belge, ACL testleri) ve sentetik SQL şeması. 35 soruluk sentetik set TH (`llmaas`) kurulumu için kalır, PoC kapısı değildir.

## Amaç

Platformun boş değil, anlamlı ve **tamamen sentetik** veriyle teslim edilmesi: örnek sözleşmeler, hastane benzeri demo şema, üç hazır agent şablonu, 35 soruluk sınav, PII ve hafıza test setleri (13a); tek komutla koşan uçtan uca test ve M3 ölçümü (13b).

## Kapsam

1. **(13a) Sözleşmeler:** `data/samples/contracts/` altına **yalnızca sentetik** en az 5 belge (PDF ve DOCX karışık; Faker Türkçe, kurum adları uydurma, kişi adı üretilmez). Gerçek kurum belgesi depoya **girmez** (SECURITY, B4/M7); gerçek belgeyle deneme kullanıcının makinesinde ve depo dışında yapılır.
2. **(13a) Demo şema:** `data/samples/schema/` içinde "agent sunum DB'si": `departments, beds, admissions (daily aggregate), devices, device_faults, contracts_meta`. Kişi düzeyi veri yok; sayılar ve kodlar. Seed scripti 10.000 satır sentetik. `schema_descriptions` (05) ve 20 `few_shots` doldurulur.
3. **(13a) Agent şablonları** (`data/samples/agents/*.json`, 06 şemasında):
   - `sozlesme-asistani`: KB `sozlesmeler`, mod `always`, kaynak zorunlu, bilmiyorum cevabı, guardrail `default`.
   - `veri-soru-cevap`: araç `mcp-sql` (`get_schema`, `run_sql`), `run_sql` onaylı değil, ask_user açık; sonuçları tablo olarak yazma talimatı.
   - `karma-asistan`: ikisi birlikte; KB mod `tool`; onay `run_sql` için açık (demo amaçlı).
   Önyüz sihirbazı (10) bunları "Şablondan başla" olarak sunar.
4. **(13a) Sınav seti** (R8.1): `data/samples/eval/sozlesme-35.json`, 35 item: 20 belge sorusu (12 doğrudan + 8 dolaylı), 8 cevapsız (5 alan içi + 3 alan dışı), 5 SQL sorusu beklenen sonuçla. Suite tanımı: `contains`, `cites_source`, `sql_result`, `llm_judge`; eşik 0,8.
4b. **(13a) PII test seti** `data/samples/pii/` (100 etiketli sentetik Türkçe cümle, çeşitli yazım biçimleri; 08 bunu tüketir, kendi setini yazmaz, C18) ve **hafıza test seti** `data/samples/memory/` (40 konuşma, beklenen hafıza çıktısıyla; 14 için). `data/samples/openapi/superset.yaml` (05b için) de burada.
5. **(13b) `make seed`:** demo kullanıcılar (PoC'de `admin_edit, admin_read, analyst_edit`, A3; tam matris 10c ve 17 ile), demo proje, KB ve belge yükleme (ingest bekleme), demo DB, araç kaydı ve keşif, üç agent, dataset ve suite; idempotent.
6. **(13b) `make e2e`:** seed sonrası: sözleşme sorusu kaynaklı cevap; belgede olmayan soru "yok" cevabı; SQL sorusu doğru sayı; onaylı araç akışı (karma asistan) onay verilince tamamlanır; PII içeren girdi maskelenir; sınav koşar ve özet üretir; audit'te bu adımlar görünür. Çıktı: geçti/kaldı tablosu.
7. **(13b) `make eval`:** 35 soruluk seti 06a run API'siyle koşturan, `outcome` dağılımı ve kaynak doğruluğu özetini Markdown rapor olarak yazan script (M3 kararı için yeter; 09 tabloları beklenmez).
8. **(13b) Demo senaryosu dokümanı** `docs/demo.md`: 15 dakikalık sunum akışı, hangi ekranda ne gösterilir.

## Profil farkları (PLAN.md 2b)

`make e2e` her iki profilde koşar; CI'da varsayılan `llmaas` (sahte sağlayıcı ile, kalite kriterleri atlanır, akış kriterleri koşar); gerçek sağlayıcıyla ve `airgap`'ta elle. Kabul tablosu üç sütun: `llmaas`, `gpu`, `cpu` (aşağıda). Sonuçlar `docs/demo.md`'de yan yana raporlanır.

## Teslimatlar

- Örnek veri ve scriptler, üç agent şablonu, sınav seti, `make seed`, `make e2e`, `docs/demo.md`.

## Kabul kriterleri

- (PayCore düzeltmesi D8, v9 M22) **PoC'de yalnızca `cpu` sütunu geçerli**; `llmaas` ve `gpu` `NOT_RUN`. `cpu` eşikleri PayCore ölçümüyle: tek RAG cevabı ≤ 5 dk (PayCore ~165-320 sn), S1 ≥ %80; "bütçe 60-90 sn" PayCore'un hedefidir, kabul değildir. Tablo:

| Ölçüt | `llmaas` (sağlayıcı modeli) | `gpu` (vLLM, 96 GB sınıfı; **donanım varsa**, yoksa `NOT_RUN (PENDING_ENV)`, C22) | `cpu` (Ollama, 35B-A3B Q4, 32 vCPU) |
|---|---|---|---|
| `make seed && make e2e` toplam süre | ≤ 30 dk | ≤ 30 dk | ≤ 3 saat (ingest + 35 soruluk sınav dahil; ölçülüp yazılır) |
| Tek RAG cevabı (top_k 12 / 8000 token; cpu'da top_k 8 / 4000, R5.4) | ≤ 15 sn | ≤ 10 sn | ≤ 4 dk (LiteLLM per-call 600 s, R1.5) |
| `mode: tool` karma asistan turu | ≤ 30 sn | ≤ 30 sn | süre kriteri yok, yalnızca doğruluk |
| 10 eşzamanlı RAG sorusu P95 | ≤ 30 sn (sağlayıcı eşzamanlılığı) | ≤ 20 sn | ölçülür, kriter yok (sıraya girer) |
| Belge soruları kaynak doğruluğu (20) | ≥ 18/20 | ≥ 18/20 | ≥ 16/20 |
| Cevapsız sorularda tutma (8) | 8/8 | 8/8 | 7/8 |
| SQL soruları (5) | 5/5 | 5/5 | ≥ 4/5 |

- CPU'da `mode: tool` agent'lı demo doğruluk için koşar, süre kriterinden muaftır; CPU PoC ve küçük kurulum, GPU üretim (PLAN.md 2b). Her iki ölçüm `docs/demo.md`'ye ve `docs/donanim.md`'ye (12) yazılır. M3 (PoC kapısı) `llmaas` ve `cpu` ölçümleriyle kapanır; `gpu` sütunu donanım gelince doldurulur (C22).
- (PayCore düzeltmesi D7, R8.1) `sozlesme-35.json` dağılımı 09'daki kurala göre: 12 doğrudan, 8 dolaylı, 5 alan içi cevapsız, 3 alan dışı cevapsız, 5 SQL; her item `style`, `answerable`, `expected_docs` taşır.
- Sözleşme asistanı 20 belge sorusunun en az 16'sında doğru maddeyi kaynak gösterir.
- Cevapsız 8 soruda uydurma yoktur: `llmaas` ve `gpu` 8/8, `cpu` ≥ 7/8 (tabloyla aynı; v4 C10).
- SQL sorularının en az 4'ünde beklenen sonuç gelir.

## Teknik notlar

- Qwen CPU ile kalite sınırlı; kabul eşikleri buna göre. Geliştirmede Anthropic ile aynı set koşturulup fark `docs/demo.md`'ye yazılır; model yükseltme kararı için veri olur.
- Sentetik veri üretimi için Faker (Türkçe yerel ayar); kişi adı üretilmez.

## Kapsam dışı

Gerçek hastane verisi, HBYS bağlantısı, üretim kullanıcı listesi.
