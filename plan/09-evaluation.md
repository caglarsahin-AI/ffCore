# 09. Evaluation: Langfuse datasets/experiments üstünde suite, run, scorer [FFCore Eval]

**Bağımlılık:** 06a, 02, 04a (`kb_queries.candidates`), 13a (soru seti). **Süre:** 3,5 gün. **Dalga:** PoC sonrası (M4). M3 kararı için 13b'deki `make eval` scripti yeter. **PoC:** hayır.

## Amaç

Agent'ı yayınlamadan önce ve her değişiklikte otomatik sınava sokmak; sonuçları sürümler arasında karşılaştırmak; yayını eşiğe bağlamak.

## Kapsam

### Veri modeli (A5, DECISION-4 kapandı: Langfuse datasets/experiments yeniden inşa edilmez, ARCH-09)

- **Dataset ve item'lar Langfuse'ta** (`datasets`, `dataset_items`; Langfuse v3 OSS datasets API'si, CSV/JSON içe aktarma Langfuse'un kendi yoluyla). Item şeması Langfuse `input/expected_output/metadata` alanlarına eşlenir: `input` = {message, variables}; `expected_output` = {answer?, must_contain?, must_cite?, sql_result?, json?}; `metadata` = {tags[], answerable bool, style: dogrudan|dolayli|alan_ici_cevapsiz|alan_disi_cevapsiz, expected_docs[]} (PayCore düzeltmesi D7). Yerel `datasets`/`dataset_items` tablosu **yoktur**.
- 09 işçisinin ilk işi: pinli Langfuse sürümünde datasets, experiments (dataset run) ve scores API'sinin OSS'de olduğunu ve LLM-as-judge evaluator'ının OSS'de olup olmadığını doğrulamak; judge OSS'de değilse `llm_judge` scorer'ı bizim koşu motorumuzda çalışır ve skoru Langfuse `scores` API'siyle yazar (bu brief bunu varsayar).
- `eval_suites(id, project_id, key, name, langfuse_dataset_name, scorers jsonb, pass_threshold, repeat: 1)`: yerel, hafif eşleme tablosu.
- `eval_runs(id, suite_id, agent_version_id, langfuse_run_name, status, started_at, ended_at, summary jsonb (ortalama skorlar, geçti/kaldı, `outcome` ve `style` dağılımı, en kötü 10 item, warm_cache), cost_usd)`: yerel özet; item bazlı skorlar Langfuse dataset run'ındadır.
- Item bazlı skor ve teşhis **Langfuse `scores`** olarak yazılır: her item için scorer adı, `score`, `passed`, `comment`, ve `metadata` = {`outcome`: not_retrieved|not_reranked|below_rerank_floor|declined|below_threshold|answered|unanswerable_held|unanswerable_answered, confidence, confidence_formulas, run_id} (PayCore düzeltmesi D7; C24: bu `outcome` `runs.outcome_label`'dan ayrı bir terimdir). Karşılaştırma ekranı Langfuse'tan okur, yerelde kopya tutmaz.

### Aşama bazlı teşhis (PayCore düzeltmesi D7)

"Cevap yanlış" denince arama mı, sıralama mı, model mi başarısız olduğu görünmeli. Her item için `outcome`, `run_events` ve `kb_queries.candidates` (04a, C12; top-30 aday ve skorları) kaydından türetilir; ilk düşülen aşama kazanır:

| outcome | Anlamı |
|---|---|
| `not_retrieved` | `expected_docs` hibrit adaylarda (top-30) yok |
| `not_reranked` | adayda var, reranker sonrası seçilenlerde yok |
| `below_rerank_floor` | seçildi ama rerank tabanı altında elendi |
| `declined` | kaynak modele gitti, model "bulamadım" dedi (06'daki olumsuz biçim tespiti) |
| `below_threshold` | cevap verildi, güven skoru eşik altı (yalnızca agent'ta eşik ayarlıysa; eşik kalibrasyonu bu koşuların `formula_comparison` çıktısıyla yapılır; PayCore kontrolü K3) |
| `answered` | cevap verildi, eşik üstü |
| `unanswerable_held` / `unanswerable_answered` | `answerable=false` soruda doğru tutma / yanlış cevaplama |

Özet (`summary`) bu dağılımı ve `style` bazında kırılımını gösterir. Güven skoru her formülle (`cited`, `sentence_max`, `max`) ayrıca kaydedilir; sohbet yalnızca seçileni kullanır.

### Scorer türleri

| scorer | Ölçer | Nasıl |
|---|---|---|
| `contains` | beklenen ifadeler var mı | normalize edilmiş alt dize |
| `regex` | kalıp | re |
| `json_schema` | yapısal çıktı uygun mu | jsonschema |
| `cites_source` | kaynak gösterildi mi, doğru belge mi | `sources` event'i vs `expected.must_cite` |
| `semantic` | beklenen cevaba anlamca yakınlık | embedding cosine (süreç içi bge-m3 dense, 04a `/internal/embed`), eşik |
| `llm_judge` | rubrikle 1-5 puan: doğruluk, belgeye sadakat, uydurma yok | LiteLLM üzerinden judge modeli (`EVAL_JUDGE_MODEL`, geliştirmede Claude, sunucuda Qwen); rubrik şablonu Langfuse prompt'u |
| `sql_result` | üretilen SQL'in sonucu beklenen sonuçla eşleşiyor mu | mcp-sql ile çalıştırıp satır kümesi karşılaştırma |
| `latency_cost` | süre ve maliyet sınırı | runs tablosundan |

### Akış

1. `POST /eval-suites/{id}/run?agent_version_id=`: Langfuse dataset run'ı açılır, her item 06a run API'siyle koşar (`channel=test`, `X-Run-Id`), skorlar Langfuse'a yazılır, özet yerel `eval_runs`'a. (PayCore düzeltmesi D7, N22) Model sunucusu sıfırlama **yoktur** (`EVAL_RESET_MODEL` kaldırıldı: backend'e Docker soketi vermek güvenlik riski, ARCH-07); koşu özeti `warm_cache=true` ve ısınma süresini ayrı yazar, süre karşılaştırmaları buna göre yorumlanır.
2. Karşılaştırma: `GET /eval-runs/compare?a=&b=` iki koşunun item bazlı farkı; en kötü 10 item.
3. Yayın kapısı: 06'daki `publish`, agent'a bağlı suite varsa son `eval_run.summary.passed == true` ister; `force=true` yalnızca admin, audit'e düşer.
4. Trace'ten dataset'e: `POST /datasets/{id}/items/from-run/{run_id}` (canlıda görülen bir soruyu beklenen cevapla kaydetme; önyüzde "sınava ekle").
5. CSV/JSON içe aktarma Langfuse'un kendi dataset içe aktarımıyla; 10'da yalnızca Langfuse dataset'ine bağlantı ve `from-run` kısayolu.

## Profil farkları (PLAN.md 2b)

- `llmaas`: `EVAL_JUDGE_MODEL` güçlü bir sağlayıcı modeli; `llm_judge` birincil scorer olabilir; `pass_threshold` varsayılanı 0,85. Judge'a giden metin de 08'deki `egress` aşamasından geçer.
- `airgap`: judge Qwen; deterministik scorer'lar birincil; eşik 0,8.

### Soru seti kuralları (PayCore düzeltmesi D7)

- Alan dışı cevapsız sorular ("kripto ile ödeme limiti") hiçbir şey ölçmez; hiçbir parçayı yaklaştırmaz. Sette en fazla birkaç tane, yalnızca davranış kontrolü için.
- **Alan içi cevapsız** sorular şart: var olan bir belgenin/ekranın olmayan alanı; kaynakta 0 sonuç olduğu doğrulanmış. Uydurmayı asıl yakalayan bunlar.
- **Dolaylı** sorular şart: cevap belgede var ama sorunun kelimeleri belgede yok. Kanıt: PayCore'da doğrudan sorularda kaynak doğruluğu 20/20, dolaylılarda 5/10; set yalnızca doğrudan sorulardan oluşursa kalite abartılı görünür.
- (R8.1) Dağılım (35 soruluk set): 12 doğrudan + 8 dolaylı (20 belge sorusu), 5 alan içi cevapsız + 3 alan dışı cevapsız (8 cevapsız), 5 SQL. 13'teki `sozlesme-35.json` buna göre.
- Canlıda görülen her yanlış cevap `style` etiketiyle sete eklenir; set zamanla dolaylı ve cevapsız ağırlıklı büyür.

## Teslimatlar

- Migration, scorer'lar, koşu motoru, router'lar, testler (scorer birim testleri; küçük dataset ile uçtan uca koşu, sahte LLM ile).
- `data/samples/eval/sozlesme-35.json` 13a'da üretilir (dalga 1); bu paket onu Langfuse dataset'ine yükleyen `make seed-eval` hedefini verir.
- `docs/evaluation.md`: scorer seçimi, rubrik yazımı, eşik belirleme.

## Kabul kriterleri

- 35 soruluk set bir agent sürümünde koşar, özet skor ve geçti/kaldı üretir.
- (PayCore düzeltmesi D7) Özet, her item için `outcome` ve `style` bazında dağılım gösterir; `expected_docs` adaylarda olmayan bir item `not_retrieved` olarak işaretlenir ve bu, `llm_judge` puanından bağımsızdır. Model "bulamadım" dediğinde cevap metni korunur ama `declined` sayılır, `answered` sayılmaz. Koşu özeti ısınma süresini ayrı gösterir.
- `llm_judge` rubriği aynı cevaba iki koşuda ±1 puan içinde (tutarlılık testi, 5 tekrar).
- Eşik altındaki sürüm `publish` edilemez; admin `force` ile edebilir ve audit'te görünür.
- İki sürüm karşılaştırmasında item bazlı fark listesi döner.

## Teknik notlar

- Judge modeli sunucuda Qwen olacak; kalitesi sınırlı. Bu yüzden `contains`, `cites_source`, `sql_result` gibi deterministik scorer'lar önce; judge ikincil.
- Non-determinizm için `repeat` ve ortalama.
- (PayCore düzeltmesi D7) Referans: PayCore `eval/run.py` (`outcome`, `formula_comparison`, `summarize`, `report_md`), `rag/pipeline.py` (`declined`); `eval/scenario1/questions.jsonl` (S1) biçim örneğidir ve iç dokümantasyon sorusudur (karar 4), müşteri verisi değildir; yine de FFCore deposuna kopyalanmaz, PayCore'da kalır.
- (PayCore düzeltmesi D8, N6) Kabul eşikleri ve süreler `cpu` ve `gpu` sütunlarıyla; CPU'da 35 soruluk koşu 1,5-2 saat sürebilir (soru başına 1,5-3 dk; 13'teki tolerans buna göre), koşu arka planda, ilerleme SSE ile. (P7, A8) Sınav koşuları ve judge çağrıları arka plan sınıfındadır (06 kuyruk kuralı): `BACKGROUND_WINDOW` yalnızca `airgap` cpu seed'inde doludur; `llmaas` ve `gpu`'da sınav gün içinde, etkileşimli işlerden sonra koşar; admin "şimdi koştur" ile öne alabilir. Koşu sırasında sohbet bekletilmez.

## Kapsam dışı

Online evaluation (canlı trafik örneklemesi), Promptfoo entegrasyonu (CI için ileride; dataset formatı Promptfoo'ya dönüştürülebilir tutulur).
