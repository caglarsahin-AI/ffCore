# Dalga raporu · 17 Kasım 2026 (dalga 6: PoC sonrası, kapanış)

Yazan: koordinatör (lease ffcore-koordinator-20261102). Şablon: docs/takim/ajanlarla-gelistirme.md 9.3. Önceki rapor: state/dalga/dalga-16kasim-rapor.md (onaylı 16 Kasım). Onay: kullanıcı; onay satırı `state/WORK_QUEUE.md` "Kapılar".

## 1. Dalga, paketler, main, kapı logları

PLAN 7 "PoC sonrası dalga 6": 03c, 06b, 11, 04b, 05b, 08 tam, 09, 10c. Bu rapor dalganın **biten yarısını** kapatır; kalan yarısı (04b, 05b, 10c-2/10c-3, 11, 08 tam kalanı) bölüm 9'daki planla "dalga 6b" olarak sürer.

| Paket | Merge | Main kapısı | Log |
|---|---|---|---|
| 03c API key, kota, usage, retention, uyarılar (03c-1 + 03c-2) | önceki rapordan önce main'de | yeşil | gate-03c-* |
| 06b facade + 06b-2 dış agent | main'de (614c150) | yeşil | gate-06b* |
| 09-1 / 09-2 Evaluation | 1e7a184 (5 Kas), 202640e (16 Kas) | yeşil 1799×2, test-int 951 | gate-09-2-20261116.log |
| 08 tam 1a / 1b / 1c-a / 1c-b (Türkçe NER seçimi, akdeniz27 int8) | c5b234c, 6066276 (5 Kas) | yeşil 1751×2 | gate-08t1c-b-20261105.log |
| 10c-1 (09 Evaluation önyüzü, SSE no-transform) | 6157752 (16 Kas) | yeşil 1801×2, test-int 952 | gate-10c-1-20261116.log |
| fix/ajan-hooklari (PreToolUse hook, warn kipi) | 2d44b0c (16 Kas 21:54) | hook testleri 142, ruff; yığınsız | gate-hook-20261116.log |
| fix/ajan-hooklari-2 (kanal biçim kuralı, sarmalayıcılar, maske, kanal_ozet) | 4d09310 (17 Kas 00:45) | 355 test, ruff; yığınsız | gate-hook2-20261117.log |
| fix/10b-sse-bekci (06a koşu akışı bekçisi, FOLLOWUP-188) | 4216718 (17 Kas 08:45) | önyüz kapısı: lint/typecheck/check:api 0, Vitest 211 | gate-sse-20261117.log |

Sürüm: ilk adlı sürüm **0.1.0-m3** (etiket 18031ec; `.env.example`, degisiklikler.md). İç ayna: `https://git.paycore.com/scm/dwh/ffcore.git` (K1 evet; main + etiket 17 Kasım). GitHub `origin/main` df996a9'da; sonraki state commit'leri ve üç merge push bekliyor (kullanıcı talimatı).

## 2. Bu dalgada alınan kararlar (KARARLAR; tek cümle)

- 16 Kasım 2026 · 10c-1 plan kararları · [Ertelenenler ve açık konular]
- 16 Kasım 2026 · fix/ajan-hooklari plan kararları · [Ertelenenler ve açık konular]
- 16 Kasım 2026 · fix/ajan-hooklari plan kararları · [Geliştirme düzeni]
- 16 Kasım 2026 · 10c-1 r1 kararları (sse-sessiz-kopus bekçisi) · [Geliştirme düzeni]
- 17 Kasım 2026 · FFCore iç aynası Bitbucket scm/dwh/ffcore.git (K1 evet; tek yönlü, kullanıcı talimatıyla push) · [Sürüm]
- 17 Kasım 2026 · fix/10b-sse-bekci kapısı önyüz-yalnız; konteynere depo kökü bağlanır; FOLLOWUP-188 kapandı · [Geliştirme düzeni]
- 17 Kasım 2026 · fix/10b-sse-bekci r1 kararları (yoklama hatada sürer, hata görünür; sayfa FOLLOWUP-192) · [Geliştirme düzeni]
- 17 Kasım 2026 · fix/10b-sse-bekci plan kararları (bekçi yardımcıları sse.ts'ten paylaşılır; okuma reddi drop) · [Geliştirme düzeni]
- 17 Kasım 2026 · Sıradaki paket fix/10b-sse-bekci (FOLLOWUP-188, kullanıcı A) · [Geliştirme düzeni]
- 17 Kasım 2026 · fix/ajan-hooklari-2 kapısı yığınsız; ilk kanal_ozet koşusu; FOLLOWUP-189 kapandı · [Geliştirme düzeni]
- 16 Kasım 2026 · fix/ajan-hooklari-2 r1 kararları (r2 kısa dilim: bileşik gövde fail-loud, ENV gerilemesi FN yönü, kanal_ozet cevaplanmış) · [Geliştirme düzeni]
- 16 Kasım 2026 · fix/ajan-hooklari-2 plan kararları (Q1-Q4 A; DUYURU; warn günü: hook eski oturumlarda da çalışır, ENV metin yanlış pozitifi → 189 e) · [Geliştirme düzeni]
- 16 Kasım 2026 · FFCore sürümü 0.1.0-m3 (etiket, FFCORE_VERSION, paycoreLLM K3) · [Sürüm]
- 16 Kasım 2026 · Hook paketi kapısı (yığınsız) ve warn günü 16-17 Kasım · [Geliştirme düzeni]
- 16 Kasım 2026 · fix/ajan-hooklari r2 kararları (derinlik fail-loud r3; önek/maske FOLLOWUP-189) · [Geliştirme düzeni]
- 16 Kasım 2026 · fix/ajan-hooklari r1 kararları (kapı tee kapsamı, kayıt maskesi) · [Geliştirme düzeni]

## 3. Tersine dönen kararlar

- docs/takim 9.2 "Claude Code ayarı oturum açılışında okunur, sonradan yüklenmez" tespiti kanıtla çürüdü (hook-guard.log 16 Kas 22:26, merge öncesi açılmış koordinatör oturumu): hook bütün açık oturumlarda devreye girdi; belge gözleme göre yazıldı (K-HOOK2-0003).
- ENV kuralı: "metin içinde `.env` sözcüğü de tetikler" (fix/ajan-hooklari) → "yalnız yol konumu" (hooklari-2, 189 e) → r1 incelemesi bunu yorumlayıcıya giden kod için gerileme buldu; yön FN'den yana düzeltildi (sh/bash heredoc gövdesi ve `py -c` argümanı komut sayılır).
- "MINOR merge'i bekletmez" uygulaması: fail-loud ya da veri sınırı sınıfındaki MINOR'lar (hooklari-2 r1) merge öncesi kısa dilimle kapatıldı; tur kuralı değişmedi, uygulaması netleşti.

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

Bu dalgada açılan belge notları FOLLOWUP-191'de (docs 9.2 maske cümlesi, `case` kolu, ENVIRONMENT "Yükleme/Testler/Kip" satırları, konteynere depo kökü bağlama). DOC-19 bu dalgada ayrıca koşulmadı; DRIFT listesi değişmedi.

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

Ayrıca: GitHub push (origin df996a9 → main); eski oturumların arşivi ve üç worktree silme; sunucu `.env` `FFCORE_VERSION=0.1.0-m3`; paycoreLLM K1 adresinin runbook'a işlenmesi (paycoreLLM ajanı); hook `block` geçişi (17 Kasım 22:05 sonrası karar); M3 sunucu ölçümü (PoC kapısı) henüz koşmadı.

## 6. Açık FOLLOWUP sayısı ve en riskli üçü

Açık FOLLOWUP: 71. En riskli üçü (koordinatör görüşü):
1. FOLLOWUP-192: koşu detay sayfası `useRun` ilk GET düşerse yoklama sessiz durur, hata görünmez (panelde kapatıldı, sayfada açık).
2. FOLLOWUP-185: `GET /eval-runs/{id}/items` ve `EvalSummary` şeması yok; konsolda tam madde tablosu yok.
3. FOLLOWUP-190: `EventStreamResponse` başlık birleşimi `no-transform`'u sessizce düşürebilir.

## 7. Hook kayıtları (state/evidence/hook-guard.log, 16 Kas 19:09 - 17 Kas 08:57; 36 satır, hepsi warn)

- isci-b · KAPI: 12
- koordinator · ENV: 10
- isci-b · ENV: 5
- inceleyici · ENV: 4
- inceleyici · KAPI: 2
- - · ENV: 1
- inceleyici · PAYCORE: 1
- koordinator · KAPI: 1

Sınıflama: isci-b KAPI 12 → gerçek (tee'siz pytest, işçi düzeltti); ENV satırlarının tamamı metin yanlış pozitifi (hooklari-2 ile kapandı; 4d09310 sonrası sıfır); koordinatör 17 Kas 08:56-08:57 2 satır probe. **Merge 4d09310 sonrası 8 saatte üç oturumda gerçek ya da yanlış uyarı yok.** Block geçişi önerisi: evet (22:05 sonrası, kullanıcı kararı).

## 8. Bağlam bütçesi ölçümü

```
dosya                                                                      boyut    hedef  durum
zorunlu küme (CLAUDE.md, FELSEFE.md, handbook/FELSEFE_UYGULAMA.md, han    48.7K     60K  ok
KARARLAR indeksi                                                          12.3K     15K  ok
state/BLOCKERS.md (açık)                                                  46.7K     30K  AŞIM
state/WORK_QUEUE.md                                                       10.8K     15K  ok
state/kanal/inceleyici.md                                                  6.4K     50K  ok
state/kanal/isci-a.md                                                     11.3K     50K  ok
state/kanal/isci-b.md                                                      0.6K     50K  ok
state/kanal/isci-c.md                                                      0.7K     50K  ok
state/kanal/isci-d.md                                                      0.7K     50K  ok
state/kanal/koordinator.md                                                26.3K     50K  ok
state/kanal/test.md                                                        0.5K     50K  ok
aşım: 1
```

Kalan aşım: BLOCKERS açık kayıtlar 46,7 KB (hedef 30). Öneri: brief metni düzeltmesi olan DRIFT'lerin toplu kapatma turu; ayrı küçük koordinatör işi.

## 9. Dalga 6b planı (onay bekliyor)

Şeritler (üç yığın sınırı: aynı anda en çok iki işçi yığını + inceleyici):
- **isci-c (önyüz): 10c-2** dashboard'lar (kullanım, maliyet), API anahtarları, limitler/kotalar, uyarılar, retention, salt-okunur mod ekran tarafı ve iki modda ekran görüntüleri (03c ve 09 hazır). FOLLOWUP-185 ve 192 içinde. **10c-3** (MCP sunucu ve izleme, kaynak/kanal/hafıza menüleri) 05b merge'ünden sonra.
- **isci-a (backend): 05b** OpenAPI→MCP yayınlama (`mcp_servers`, `/mcp/{key}/`, guardrail modu, `remote_mcp`), Superset örneği; sonra 08 tam kalanı (injection sınıflandırıcı, akış tamponu).
- **isci-b (backend/veri): 04b** bir sonraki slotta (migrate-vectors, reconvert, TR normalizer, DuckDB→Postgres göçü; 04a/04b FOLLOWUP'ları).
- **inceleyici:** tek oturum, paket başına kanal başlığı.
- Karar gereken: **DECISION-193** (11 son kullanıcı sohbet arayüzü: kendi `/chat` ekranı mı, Open WebUI kalıcı mı; 14/15/17 buna bağlı). **Brief 12** `llmaas` kurulum rehberi ve egress proxy'ye daralır (airgap tarafı plan/19 ve `deploy/offline` ile büyük ölçüde yapıldı); plan/12'ye ek bölüm yazıldı.

## Onay

Kullanıcı bu raporu okuyup onaylar ya da bir maddeyi geri çevirir; koordinatör onayı WORK_QUEUE "Kapılar" tablosuna tarih ve rapor yoluyla yazar. Onayla birlikte dalga 6b READY: 10c-2 ve 05b GOREV'leri yazılır.

**Onay: 2026-11-17, kullanıcı ("Onaylıyorum, DECISION-193 A, oturumları sen aç"); geri çevrilen madde yok. Dalga 6b READY; 05b isci-a yerine isci-b şeridinde (isci-a HANDOFF'u henüz gelmedi, oturum çevrimdışı).**
