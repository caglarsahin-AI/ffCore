# Dalga raporu · 16 Kasım 2026 (dalga: PoC sonrası 1)

Yazan: koordinatör (lease ffcore-koordinator-20261102). Şablon: docs/takim/ajanlarla-gelistirme.md 9.3. Onay: kullanıcı; onay satırı `state/WORK_QUEUE.md` "Kapılar".

## 1. Dalga, paketler, main, kapı logları

| Paket | Merge | Main kapısı | Log |
|---|---|---|---|
| 09-1 Evaluation çekirdeği (7 tur) | 1e7a184 (5 Kasım) | yeşil: 1739×2, test-int 903 | state/evidence/gate-09-1-20261105.log |
| 08 tam 1c-a (NER kilit/süre/reindex/pii_regex) | c5b234c (5 Kasım) | yeşil: 1608×2, test-int 870 | gate-08t1c-a-20261105.log |
| 08 tam 1c-b (NER ölçüm ve seçim: akdeniz27, `first`, int8) | 6066276 (5 Kasım) | yeşil: 1751×2, test-int 903 | gate-08t1c-b-20261105.log |
| 09-2 (compare, yayın kapısı, from-run, FOLLOWUP-176) | 202640e (16 Kasım) | yeşil: 1799×2, test-int 951; önyüz şema regen gerekti (PROSES-184) | gate-09-2-20261116.log |
| 10c-1 (09 Evaluation önyüzü + SSE no-transform) | 6157752 (16 Kasım) | yeşil: 1801×2, test-int 952; lint kırmızısı koordinatör betiğiydi (düzeltme 9cb763e) | gate-10c-1-20261116.log |

Ayrıca merge'siz süreç işleri: FOLLOWUP-181 Ollama compose adresi (ffcore 67f89f5, paycoreLLM 0add48f); handbook/şablon düzeltmeleri (DRIFT-182, PROSES-184); bağlam bütçesi adım 1 (56e29ce) ve adım 2 (bu rapor ile).

## 2. Bu dalgada alınan kararlar (KARARLAR; tek cümle)

16 Kasım maddeleri (indeksten):
- 16 Kasım 2026 · 10c-1 plan kararları · [Ertelenenler ve açık konular]
- 16 Kasım 2026 · Ajan kuralları hook ile zorlanır; dalga kapısında insan raporu; push yalnız kullanıcı t… · [Ertelenenler ve açık konular]
- 16 Kasım 2026 · fix/ajan-hooklari plan kararları · [Ertelenenler ve açık konular]
- 16 Kasım 2026 · Bağlam bütçesi: açılış okuması ≤ 60 KB · [Ertelenenler ve açık konular]
- 16 Kasım 2026 · İnceleme tur kuralı · [Geliştirme düzeni]
- 16 Kasım 2026 · Koordinatör araç betiği istisnası · [Geliştirme düzeni]
- 16 Kasım 2026 · Bağlam bütçesi: açılış okuması ≤ 60 KB · [Geliştirme düzeni]
- 16 Kasım 2026 · fix/ajan-hooklari plan kararları · [Geliştirme düzeni]
- 16 Kasım 2026 · Ajan kuralları hook ile zorlanır; dalga kapısında insan raporu; push yalnız kullanıcı talimatıyla · [Geliştirme düzeni]
- 16 Kasım 2026 · 10c-1 r1 kararları (sse-sessiz-kopus bekçisi) · [Geliştirme düzeni]
- 16 Kasım 2026 · Kanal mesaj biçimi kapalı listelerle · [Geliştirme düzeni]
- 16 Kasım 2026 · SSE yanıtları no-transform taşır (Next proxy gzip tamponu) · [Geliştirme düzeni]

5 Kasım maddeleri: 09-1 r2/r3/r4/r5/r6 zamanlama kararları (tek sabit `TICK_PLAN_S`, kesme sayma kuralı, `EVAL_JUDGE_CALL_S`), 09-2 plan ve r1/r2 kararları (stale_exam/stale_suite, eşlik istisnası, from-run maskeleme), 08 tam 1c-b kararları (`first`, int8, bütçe hedef donanımda, sabit commit + safetensors, offline paket listelenenler), üç yığın bellek kuralı, M3 OCR NER'siz sunucu.

## 3. Tersine dönen kararlar
- Karar 2, anayasa · [PayCore entegrasyonu] · tersine
- META-01 tersine karar — yapılandırılmış sorular · [Geliştirme düzeni] · tersine
- Ürün dili: İngilizce varsayılan, Türkçe yerel · [Geliştirme düzeni] · tersine
- paycoreLLM merge'ü de koordinatörde · [Geliştirme düzeni] · tersine
- Yığın sınırı üçe çıkarıldı · [Ertelenenler ve açık konular] · tersine
- 10c-1 GOREV D2 "suite'te madde listesi" koordinatör brief hatasıydı; 09 brief akış 5 geçerli (10c-1 plan kararları S2).
- Hook kararı: "push yalnız sekreter" (belge oturumundan ilk iletim) → "karar kullanıcıda, işlem koordinatörde, bayrakla" (kullanıcı düzeltmesi).

## 4. Tutarlılık denetimi (DOC-19) bulguları ve DRIFT'ler

Açık DRIFT kayıtları (35):
- 7 (02): Langfuse v3 LANGFUSE_INIT_* değişkenleri ve datasets/experiments/scores API'sinin OSS'de olduğu pinli sürümde …
- 8 (08): Türkçe NER modeli lisansı ve imaja gömme hakkı; injection sınıflandırıcısının CPU gecikmesi ölçülecek
- 9 (15): Teams etkinliğinde kullanıcı e-postasının her kiracıda gelip gelmediği (TeamsInfo.getMember gerekebilir)
- 11 (04a): U14: Ollama embedding API'si bge-m3 için sparse (lexical_weights) üretmez; doğrulanırsa C10 tersine kararı kes…
- 12 (00i): U1: Open WebUI son kullanıcı kimliğini imzalı iletir mi; iletmezse audit aktörü openwebui_service
- 16 (handbook): ENVIRONMENT_AND_COMMANDS "PayCore referans deposu" bölümü eval/, data/, experts/ tamamen okunmaz diyor; CLAUDE…
- 17 (handbook): FELSEFE_UYGULAMA ARCH-09 satırı DECISION-4'ü açık gösteriyor; KARARLAR (A5) ve BLOCKERS 4 kapalı. Dalga 1 kapa…
- 18 (handbook): FELSEFE_UYGULAMA ARCH-11 "13 sözleşme" diyor; CONTRACTS.md C1-C14, 14 satır. Dalga 1 kapanışında düzeltilecek
- 21 (KARARLAR): (isci-b B-00i-0002) KARARLAR "Geliştirme düzeni" PoC satırı v2.3 değerlerinde: 11 PoC'de ve ≈51 gün yazıyor, 0…
- 22 (00): (isci-a plan varsayım 1 ve 3) Brief 00 süre 1 gün, PLAN 7 1,5 gün. Brief 00 madde 5 llmaas'ta Ollama'ya yalnız…
- 25 (13a): Brief 13 madde 3 veri-soru-cevap "run_sql onaylı değil"; PLAN 2d karar 5 PoC SQL asistanı "max_tool_calls 1, r…
- 28 (13a/09): Sınav seti "35 soru" etiketi aritmetik hata: zorunlu dağılım 12+8+5+3+5 = 33 (test T-13a-0007; koordinatör doğ…
- 30 (PLAN/00): PLAN 2 kısıt tablosu "Embedding de yerel: Ollama üzerinden bge-m3" satırı eski; PLAN 2b/2d ve KARARLAR C10 ter…
- 32 (13): plan/13-ornek-veri-demo.md madde 1 ve teknik not 56 "kişi adı üretilmez" der; DECISION-24 (A) ile pii/ ve memo…
- 34 (00): Backend paket yolu: review 00-r1 MAJOR-1 (tüketici import ffcore için kurulabilir paket yok). Koordinatör kara…
- 36 (tumu): Ürün dili tersine kararı (KARARLAR 28 Ekim): PLAN 1b/7 satırlarındaki "Türkçe yönetim önyüzü", brief 10 ("tr t…
- 41 (10): Brief 10 R10.5 rol listelerinde "Kullanım" ekranı hiçbir role atanmamış; 10a en dar varsayımla admin'e verdi (…
- 51 (tumu): BASLATMA §3 işçi şablonu ve §2 inceleyici talimatı soru aracını yasaklamıyor; işçi oturumu iki kez kullanıcıya…
- 53 (03): CONTRACTS C3 "ortak kolonlar yalnızca proje sahipli kök tablolar için" istisna listesini yazmıyor; 03a kararı:…
- 54 (03): Brief 03 sağlayıcı sürücü listesinde local_flagembedding yok ama models maddesi bu sürücüyü kullanıyor (C10 te…
- 55 (03): Brief 03 hem POST /providers/{id}/test hem POST /providers/test der; brief 01 "kaydetmeden canlı test" ister. …
- 58 (04): Brief 04 bağımlılık satırı "00i, 03a, 01, 13a"; 04a 01'e gerçekte bağımlı değil (LLM çağrısı yok, rewrite 04b'…
- 59 (04): Brief 04a başlığı "KnowledgeStore DuckDB + silver dosyalarını sarar" ffcore içinde bir bağdaştırıcı ima eder; …
- 60 (04): Brief 04 pipeline adım 4 hem "PaddleOCR tr (Tesseract değil)" hem "taranmış PDF Tesseract (tur+eng)" der. PLAN…
- 61 (10): Brief 10 / handbook make e2e der; tools konteynerinde Node ve tarayıcı yok, Docker soketi yok. e2e compose e2e…
- 62 (10): Brief 10 rol matrisi "admin: sağlayıcılar, modeller, proje, kullanıcılar" der; 03a'da providers/users require_…
- 63 (04): Brief 04 parçalama "hedef 400, overlap 60, üst sınır 512 (×1,28)", embed batch 32; PayCore ölçülmüş kodu min 4…
- 64 (04): Brief 04 ve 03 kabulleri embedding_dimension_mismatch kodunu yazar; 03a kodu embed_dim_mismatch (main). Kod ka…
- 65 (04): Brief 04 "hibrit arama iki sürücüde de aynı çalışır (BM25 Postgres'ten)" der; C5 Qdrant sürücüsünün sözcüksel …
- 68 (01): Brief 01 madde 1 fallback'i router_settings'te ister; DB modunda tek yol /config/update ve bu uç master key + …
- 71 (08): Brief 08 on_error için iki değer kümesi (block\
- 72 (03/01): 03a models.request_policy.forward_unknown_params alanını kabul ediyor; LiteLLM v1.80.0'da karşılığı yok (B-01-…
- 124 (03c): B-03c-0010 ölçümü (state/evidence/03c-u1-u2-probe-20261031.md): LiteLLM v1.80 spend log'u api_key_id/metadata …
- 151 (08): A-08T1-0003: plan/08 "NER modeli imaja gömülür ve 12'de aynaya eklenir" cümlesi KARARLAR 04a "model ağırlıklar…
- 187 (state/WORK_QUEUE "Kapılar"): Dalga kapıları tablosunun kanıt sütunu boş; dalga kapanışları fiilen main kapısı loglarıyla yapıldı, tablo gün…

Bu dalgada kapanan: 182 (handbook kanıt cümlesi), 183 (geçersiz), 186 (push sahipliği kararı). DOC-19'un dalga başına koşulması bu raporla başlar.

## 5. İnsana kalan açık konular

DECISION (4):
- 1 (00): ffcore alan adı ve marka araması (ffcore.com dolu; adaylar ffcore.com.tr, ffcore.ai/io)
- 2 (13): M3'te rewrite ve judge modeli kararı (KARARLAR açık konular)
- 3 (08): M4'te ad-soyad NER eşiği
- 14 (08): PRSIM ingest'ine kişi verisi guard'ı: karar 5 ile 08 tam gelene kadar ertelendi; o zaman yeniden açılır

ENV (6):
- 45 (00i): PENDING_ENV: sunucu ölçümleri, ajan bağlanmaz, kullanıcı koşar (B-00i-0011, ayrıntı state/kanal/isci-b.md): (1…
- 52 (00i): PENDING_ENV: Docker Desktop paylaşım izni yol bazında verilmiş: C:\ai_paycore\paycoreLLM-00i ve paycoreLLM\doc…
- 117 (04a/00): Koordinatör kapı yığınlarında (ffmain, ayrıca 07-approvals) worker-1 (04a bilgi işçisi) ModelMissing: BAAI/bge…
- 138 (paycoreLLM): B-19-0013: paycoreLLM test venv'inde bs4 yok; test_data_dump, test_mhtml, test_reconvert HTML testleri düşüyor…
- 173 (ortam): R-09-0009: Docker yeniden başlatması sonrası review09 compose ağında aralıklı DNS çözümleme düşmesi (airgap te…
- 177 (08 tam 1c-b): NER gecikme kabulü (R7.3: boşta P95 < 300 ms, 1.000 karakter, yerel kurallar + NER) **hedef donanımda** kullan…

Ayrıca: sunucu `.env` `GUARDRAIL_EGRESS_NER=false` (63ffb16+ dağıtımı öncesi); eski oturumların arşivi (auto mode hook engeli); push (ffcore main 9d38bc4 sonrası, paycoreLLM güncel); hook paketi için worktree kanıt oturumu kararı.

## 6. Açık FOLLOWUP sayısı ve en riskli üçü

Açık FOLLOWUP: 71. En riskli üçü (koordinatör görüşü):
1. FOLLOWUP-188: 06a koşu akışı `lib/sse.ts` zaman aşımsız okuma; yarı açık bağlantıda koşu ekranı bayat kalır (10c-1'de aynı sınıf kapatıldı).
2. FOLLOWUP-185: `GET /eval-runs/{id}/items` ve `EvalSummary` şeması yok; konsolda tam madde tablosu yok, özet tipsiz (zod okuyucu ile).
3. FOLLOWUP-190: `EventStreamResponse` başlık birleşimi sessizce `no-transform` düşürebilir (bugün çağıran yok).

## 7. Hook kayıtları

Yok: `fix/ajan-hooklari` henüz merge edilmedi (IMPLEMENTED 1986c2b, 101 test; gerçek çağrı kanıtı bekleniyor). İlk kayıtlar bir sonraki dalga raporunda.

## 8. Bağlam bütçesi ölçümü (adım 2 sonrası)

```
dosya                                                                      boyut    hedef  durum
zorunlu küme (CLAUDE.md, FELSEFE.md, handbook/FELSEFE_UYGULAMA.md, han    43.8K     60K  ok
KARARLAR indeksi                                                          10.7K     15K  ok
state/BLOCKERS.md (açık)                                                  46.4K     30K  AŞIM
state/WORK_QUEUE.md                                                        9.6K     15K  ok
state/kanal/inceleyici.md                                                  0.6K     50K  ok
state/kanal/isci-a.md                                                      7.1K     50K  ok
state/kanal/isci-b.md                                                      0.5K     50K  ok
state/kanal/isci-c.md                                                      0.6K     50K  ok
state/kanal/isci-d.md                                                      0.7K     50K  ok
state/kanal/koordinator.md                                                10.9K     50K  ok
state/kanal/test.md                                                        0.5K     50K  ok
aşım: 1
```

Adım 2 taşıması: 7 kanalda 2.076 mesaj → 13 aktif kaldı, 2.063 mesaj `state/kanal/arsiv/<rol>-<paket>.md` dosyalarına taşındı (sayımlar eşit); WORK_QUEUE 51 satır durum tablosuna indi (100 KB → 9,6 KB), tam satırlar `state/arsiv/work-queue-dalga1.md`. Kalan aşım: BLOCKERS açık kayıtlar 46 KB (hedef 30): açık kayıtların 3 satıra kısaltılması ayrı bir temizlik turu.

## Onay

Kullanıcı bu raporu okuyup onaylar ya da bir maddeyi geri çevirir; koordinatör onayı WORK_QUEUE "Kapılar" tablosuna tarih ve rapor yoluyla yazar.

**Onay: 2026-11-16, kullanıcı (koordinatör oturumunda "Onaylıyorum"); geri çevrilen madde yok.** Sonraki dalga READY.
