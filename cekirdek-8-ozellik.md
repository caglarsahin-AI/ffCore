# Kurumsal LLM Platformunun 8 Çekirdek Özelliği: Tam Detay

Bu doküman, cognipeer-analiz.md'deki 80/20 listesinin A grubunu (çekirdek %20) açar. Her özellik için: ne olduğu, neden kritik olduğu, alt yetenekler, Cognipeer Console'daki karşılığı, kendi yapınızda nasıl kurulacağı, ölçüm kriterleri ve tuzaklar.

Öncelik sırası, yapım sırasıdır. 1 ve 2 olmadan 3 anlamsız; 3 olmadan 7 ölçülemez.

---

## 1. OpenAI-uyumlu tek gateway, çoklu provider, fallback

**Ne:** Tüm uygulamaların LLM çağrısını tek bir HTTP endpoint'e (`/v1/chat/completions`, `/v1/embeddings`) yaptığı, gateway'in isteği doğru sağlayıcıya yönlendirdiği katman.

**Neden kritik:** Uygulama kodu sağlayıcıya bağımlı olmaz. Model değiştirmek, A/B test etmek, kesintide yedeğe geçmek kod değişikliği gerektirmez. OpenAI şeması fiili standart olduğu için mevcut tüm SDK'lar (openai-python, LangChain, Vercel AI SDK) sıfır değişiklikle bağlanır.

**Alt yetenekler**
- Chat completions, embeddings, streaming (SSE), tool/function calling, structured output (JSON schema), vision (görsel girdi), batch endpoint.
- Sanal model adı → gerçek model eşleme. Uygulama `hastane-asistan-v2` çağırır, gateway bunu `claude-sonnet-5-5` ya da `gpt-5`'e çevirir.
- Fallback zinciri: birincil model 429/5xx/timeout dönerse ikinciye, sonra üçüncüye geç. Zincir model bazlı tanımlanır.
- Health-aware routing: hata oranı eşiği aşan sağlayıcı geçici olarak devre dışı kalır (circuit breaker).
- Retry politikası: üstel geri çekilme, idempotency, maksimum deneme.
- Load balancing: aynı modelin birden çok API anahtarı ya da bölgesi arasında ağırlıklı dağıtım.
- İstek/yanıt normalizasyonu: Anthropic Messages, Bedrock Converse, Vertex, Azure, vLLM/Ollama gibi farklı şemaları OpenAI şemasına çevirme; usage alanını (input/output/cache token) standartlaştırma.
- Prompt caching desteği: Anthropic ve Bedrock için cache_control başlıklarını geçirme.
- Timeout ve max_tokens üst sınırı: proje bazlı.
- Semantic / exact cache: aynı prompt tekrarlarında LLM'e gitmeden yanıt dönme (isteğe bağlı, ikinci dalga).

**Cognipeer'de karşılığı:** Providers (tenant düzeyi) + Model Hub (proje düzeyi endpoint). Provider sürücüleri: OpenAI, Anthropic, Azure OpenAI, Bedrock, Vertex, Together, OpenAI-Compatible (vLLM/Ollama). "Dynamic LLM" ile sanal model; fallback chain ve health-aware routing dokümante. Prompt caching Agent SDK'da var.

**Nasıl yapılır**
- Hazır: LiteLLM proxy (Python, 100+ provider, fallback, bütçe) ya da Portkey Gateway (TS). Çoğu kurum için LiteLLM'i Postgres ile ayağa kaldırmak 1 gün.
- Sıfırdan: Node/Go reverse proxy + provider adapter katmanı + Redis tabanlı circuit breaker. Streaming'i doğru yapmak (SSE chunk'ları yeniden yazmak, tool call delta'larını birleştirmek) en zahmetli kısımdır; 2-3 hafta.
- Konfigürasyon: `models.yaml` benzeri deklaratif tanım + UI.

**Ölçüm:** P50/P95 gateway overhead < 20 ms; fallback tetiklenme oranı; sağlayıcı başına hata oranı; streaming ilk token süresi (TTFT).

**Tuzaklar**
- Fallback'te farklı modeller farklı tool-call formatı üretir; uygulama kodu buna hazır olmalı.
- Embedding fallback'i yapılmaz: farklı embedding modeli farklı vektör uzayı demek, indeks bozulur.
- Streaming'de usage bilgisi son chunk'ta gelir; maliyet hesabı için `stream_options.include_usage` zorunlu.
- Azure deployment adı ile model adı farklıdır; eşleme tablosu şart.

---

## 2. Proje/tenant izolasyonu, scoped API key, kota ve bütçe

**Ne:** Her ekibin/uygulamanın kendi projesi, kendi anahtarları, kendi limitleri ve kendi faturası olduğu yönetim katmanı.

**Neden kritik:** Tek bir OpenAI anahtarını herkese dağıtan kurum, üç ay sonra kimin ne harcadığını bilmez ve anahtar sızdığında her şeyi döndürmek zorunda kalır. Kota olmadan tek bir hatalı döngü aylık bütçeyi bir gecede bitirir.

**Alt yetenekler**
- Hiyerarşi: Tenant (kurum) → Proje (ekip/uygulama) → Kullanıcı / API token.
- Scoped API key: hangi projeye, hangi modellere, hangi servislere (chat, embedding, RAG, tool) erişebileceği; okuma/yazma ayrımı; son kullanma tarihi; IP kısıtı.
- Kota boyutları: istek/dakika (RPM), token/dakika (TPM), günlük/aylık token, aylık USD bütçe, eşzamanlı istek sayısı. Her boyut proje, token ve model seviyesinde tanımlanabilmeli.
- Kota aşımı davranışı: reddet (429), yavaşlat, ucuz modele düşür, uyar ama geçir.
- Bütçe uyarıları: %50/%80/%100 eşiklerinde e-posta/Slack.
- Fiyat tablosu: model başına input/output/cache token fiyatı; kendi barındırdığınız modeller için sanal fiyat (GPU saat maliyetinden türetilmiş).
- Kullanıcı bazlı atıf: token üzerinden değil, isteği yapan son kullanıcı (`user` alanı ya da JWT) üzerinden harcama görme.
- RBAC: Owner, Admin, Developer, Viewer; IAM entegrasyonu (SSO/LDAP ikinci dalga).
- Secret yönetimi: sağlayıcı anahtarları şifreli saklanır, UI'da maskeli görünür, loglara yazılmaz.

**Cognipeer'de karşılığı:** Proje seçici, tenant düzeyi Providers, proje düzeyi API Tokens, IAM merkezi, "Users & Tokens" dashboard'u, per-project quotas (Mayıs sürümü), Config Management (secret). Cedar policy motoru ile yetkilendirme.

**Nasıl yapılır**
- Veri modeli: `tenants`, `projects`, `api_keys` (hash'lenmiş, prefix görünür), `quotas`, `usage_daily` (rollup).
- Rate limit: Redis token bucket / sliding window; proje+model anahtarıyla.
- Bütçe: her isteğin maliyeti usage × fiyat ile hesaplanıp `usage_daily`'ye eklenir; eşik kontrolü asenkron.
- Policy: basit rol tablosu yeter; Cedar/OPA ancak çok kiracılı SaaS'ta gerekir.
- LiteLLM bunların çoğunu (virtual keys, teams, budgets, RPM/TPM) hazır verir.

**Ölçüm:** Her isteğin bir projeye ve kullanıcıya atfedilme oranı %100; kota ihlali sayısı; bütçe sapması (tahmin vs gerçek).

**Tuzaklar**
- Anahtar hash'lenmeli, düz saklanmamalı; sızıntıda sadece o proje döndürülür.
- Streaming isteklerde maliyet istek bitmeden bilinmez; kota kontrolü tahmini token ile yapılır, gerçek usage sonradan düşülür.
- "Ucuz modele düşür" davranışı kalite düşüşünü sessizce getirir; mutlaka loglanmalı.

---

## 3. Tracing ve token-maliyet izleme (OpenTelemetry)

**Ne:** Her LLM çağrısının, her agent oturumunun ve her tool çağrısının süre, token, maliyet, hata ve içerik bilgisiyle kaydedilip sorgulanabilir olması.

**Neden kritik:** "Dün gece asistan neden yanlış cevap verdi?", "Bu ay neden 3 kat harcadık?", "Hangi adım 8 saniye sürüyor?" sorularının tek cevabı. Tracing olmadan prompt değişikliği kör uçuştur.

**Alt yetenekler**
- Span hiyerarşisi: session → run/turn → LLM call → tool call → retrieval. OpenTelemetry GenAI semantic conventions (`gen_ai.*` attribute'ları) ile standart.
- Her span'de: model, provider, input/output token, cache token, maliyet, latency, TTFT, finish_reason, hata kodu, prompt versiyonu, kullanıcı/proje.
- İçerik yakalama: prompt ve yanıt metni (PII maskeli ya da kapatılabilir), tool argümanları ve sonuçları.
- Ingest yolları: gateway otomatik (sıfır kod), SDK ile açık instrumentasyon, OTLP/HTTP (dış agent framework'leri: LangChain, OpenAI Agents, Claude Agent SDK).
- Arama/filtre: kullanıcı, proje, model, hata, süre aralığı, metin arama, etiket.
- Session replay: bir konuşmanın tüm adımlarını zaman çizelgesinde görme.
- Dashboard'lar: model ops (trafik, latency yüzdelikleri, hata), cost & spend (model/endpoint/kullanıcı), agent sessions (süre, başarısızlık oranı), tool health.
- Alert: eşik (hata > %5), baseline sapması, absence (trafik kesildi), SLO.
- Export: CSV, OTLP'ye yeniden gönderme (Grafana/Datadog), veri gölüne.
- Retention: içerik kısa (30 gün), telemetri uzun (90+), rollup çok uzun (2 yıl).

**Cognipeer'de karşılığı:** Agent Observability, 21 analitik dashboard, Health paneli, Alerts & Incidents (threshold/baseline/absence/SLO), OTLP ingest + OTel exporter, cognipeer-observability kütüphanesi (LangChain/OpenAI Agents/Claude Agent SDK), Data Retention sınıfları.

**Nasıl yapılır**
- Hazır: Langfuse (açık kaynak, Postgres+ClickHouse, OTel ingest, maliyet hesabı, prompt yönetimi) ya da Arize Phoenix. Langfuse self-host 1 gün.
- Sıfırdan: OTel Collector → ClickHouse; UI için Grafana. Span'leri gateway'de üret, agent'larda SDK ile zenginleştir.
- Maliyet: fiyat tablosu × usage; gateway'de hesaplanıp span'e yazılır.

**Ölçüm:** Trace kapsama oranı (her isteğin trace'i var mı); trace sorgu gecikmesi; alert'ten fark edilmeye kadar geçen süre.

**Tuzaklar**
- İçerik yakalama varsayılan açıksa hasta verisi loglara gider; varsayılan kapalı ya da maskeli olmalı.
- Yüksek hacimde Postgres yetmez; ClickHouse/time-series gerekir.
- Dış framework'lerin span adlandırması farklıdır; normalizasyon katmanı şart.

---

## 4. RAG: dosya ingest, vektör arama, kaynak gösterme

**Ne:** Kurumsal dokümanların parçalanıp vektörlenerek aranabilir hale gelmesi ve LLM yanıtının bu parçalara dayanıp kaynağını göstermesi.

**Neden kritik:** Kurumsal LLM senaryolarının büyük çoğunluğu bilgi erişimidir: prosedür, mevzuat, ürün, politika. Model ne kadar iyi olursa olsun kurum belgesini bilmez. Kaynak göstermeyen cevaba kurum güvenmez.

**Alt yetenekler**
- Ingest: 20+ format (PDF, DOCX, PPTX, XLSX, HTML, e-posta, Markdown) → Markdown dönüşümü; taranmış PDF için OCR; tablo ve görsel çıkarımı.
- Kaynaklar: dosya yükleme, S3/Blob bucket, SharePoint/Drive, web crawler (sitemap, derinlik, robots), API/veritabanı senkronu, zamanlanmış yeniden indeksleme.
- Chunking: başlık-duyarlı, sabit boyut + overlap, semantik; metadata (başlık, bölüm, sayfa, tarih, erişim etiketi).
- Embedding: model seçimi, batch, yeniden indeksleme (model değişince).
- Vektör mağazası soyutlaması: pgvector, Qdrant, Milvus, Chroma, Elasticsearch, Azure AI Search, SQLite (yerel).
- Arama: vektör + BM25 hibrit, metadata filtresi, erişim kontrolü filtresi (kullanıcı hangi belgeyi görebilir), top-k, eşik.
- Reranker: Cohere/Jina/Voyage ya da LLM ile yeniden sıralama.
- Query rewriting: soruyu genişletme, çoklu sorgu, HyDE.
- Kaynak gösterme: her yanıt parçasında belge adı, sayfa/bölüm, bağlantı; "bulunamadı" diyebilme.
- Knowledge base yönetimi: modül/koleksiyon bazlı, belge durumu (indexed/failed), chunk önizleme, test sorgusu arayüzü.
- Ölçüm: retrieval hit rate, MRR, yanıt gerekçelendirme oranı (groundedness).

**Cognipeer'de karşılığı:** Knowledge Engine (RAG modülü, belge/chunk sayacı), Knowledge Index (vektör), Document Store, Reranker, Crawlers, OCR Jobs, to-markdown kütüphanesi (20+ format), 15 vektör sürücüsü (pgvector, Qdrant, Milvus, Chroma, ES, Azure AI Search, Mongo Atlas, SQLite, S3 Vectors). Knowledge Base Health ve RAG dashboard'ları.

**Nasıl yapılır**
- Ingest: Docling ya da unstructured (Python) → Markdown; OCR için Tesseract/PaddleOCR ya da Azure Document Intelligence.
- Chunking + embedding: LlamaIndex ya da kendi 300 satırlık pipeline'ınız.
- Vektör: pgvector ile başlayın (tek veritabanı, yedekleme kolay); 10M+ chunk'ta Qdrant.
- Hibrit arama: Postgres full-text + pgvector, RRF ile birleştirme.
- Reranker: Cohere rerank-3 ya da bge-reranker self-host.
- Erişim kontrolü: chunk metadata'sına `acl` yazıp sorguda filtrele; asla sonradan filtreleme.

**Ölçüm:** Retrieval recall@5 > 0.85 (etiketli test seti); groundedness > 0.9; indeks güncelleme gecikmesi.

**Tuzaklar**
- Chunking kalitesi, embedding modelinden daha belirleyici; tablo ve başlık yapısı korunmalı.
- Erişim kontrolü atlanırsa İK belgesi herkese görünür; en sık güvenlik hatası.
- Belge güncellenince eski chunk'lar silinmeli; versiyon yönetimi unutulur.
- "Bilmiyorum" diyemeyen RAG uydurur; eşik ve prompt talimatı şart.

---

## 5. Tool calling ve insan onay kapısı (HITL)

**Ne:** LLM'in dış sistemleri (API, veritabanı, e-posta, ticket) çağırabilmesi ve belirli aksiyonlardan önce insan onayı beklemesi.

**Neden kritik:** "Cevap veren" asistan ile "iş yapan" agent arasındaki fark budur. Ama onay kapısı olmadan hiçbir kurum agent'ın SGK'ya itiraz göndermesine ya da hasta kaydını güncellemesine izin vermez.

**Alt yetenekler**
- Tool tanımı: JSON Schema ile isim, açıklama, parametreler; Zod/Pydantic'ten üretim.
- Tool kaynakları: kod içi fonksiyon, HTTP/OpenAPI spec'inden otomatik tool, MCP server (stdio/remote), veritabanı sorgusu, client-side tool (tarayıcıda çalışan).
- MCP hub: MCP sunucularını merkezi kayıt, tool bazlı izin, versiyon, sağlık.
- Tool-call döngüsü: model tool ister → çalıştır → sonucu modele ver → tekrar; paralel tool çağrısı; maksimum tur sınırı.
- Onay kapısı: tool bazlı `needsApproval` bayrağı; koşullu onay (tutar > X, dış alıcı); onay kanalı (UI, Slack, e-posta linki); zaman aşımı davranışı; onaylayan kimliği ve gerekçesi loglanır.
- Askıya alma/devam: agent durumu kalıcı saklanır, onay geldiğinde kaldığı yerden devam eder (saatler/günler sonra bile).
- Soru sorma: agent eksik bilgi için kullanıcıya soru sorup bekler (`ask_user`).
- Tool-call politikaları: hangi tool hangi projede, hangi rolde çağrılabilir; argüman doğrulama (SQL injection, path traversal); çıktı boyutu sınırı.
- Büyük tool çıktısı yönetimi: özetleme/arşivleme, gerektiğinde tam çıktıyı geri çağırma.
- İdempotency: aynı aksiyonun iki kez çalışmasını engelleme.

**Cognipeer'de karşılığı:** Agent SDK'da `createTool`, `needsApproval`, `humanInTheLoop.askUser`, `get_tool_response` (arşivlenmiş çıktı), `limits` bütçeleri; MCP Servers servisi (OpenAPI/remote/stdio, tool bazlı kontrol); Guardrail'de tool-call kuralları; Pulse'ta onay politikaları ve e-posta/Slack onayı; Studio Flow'da onay adımı.

**Nasıl yapılır**
- Runtime: Claude Agent SDK, OpenAI Agents SDK ya da LangGraph; hepsinde interrupt/approval var. Kendi döngünüz 200 satır ama durum kalıcılığı (checkpoint) zor kısım.
- Onay kuyruğu: `approvals` tablosu (pending/approved/rejected, tool, args, requester, approver, expires_at) + webhook/Slack bildirimi.
- MCP: resmi MCP SDK ile sunucu; gateway'de MCP registry.
- Politika: tool adı + proje + rol tablosu; argüman şema doğrulaması.

**Ölçüm:** Onay bekleyen aksiyon sayısı ve ortalama onay süresi; reddedilme oranı; tool hata oranı; yanlış tool seçimi oranı (evaluation ile).

**Tuzaklar**
- Onay yorgunluğu: her şeye onay istenirse kullanıcı düşünmeden "evet" der; sadece geri alınamaz aksiyonlara onay.
- Tool açıklaması kötü yazılırsa model yanlış tool seçer; açıklama prompt'tan önemlidir.
- Prompt injection: tool çıktısındaki metin ("bu e-postayı şuraya ilet") talimat sanılabilir; çıktı veri olarak işaretlenmeli, Guardrail ile taranmalı.
- Durum kalıcılığı olmadan onay sonrası agent baştan başlar.

---

## 6. Guardrail ve PII maskeleme (giriş/çıkış)

**Ne:** LLM'e giden ve LLM'den dönen içeriğin politika kurallarına göre taranıp engellenmesi, maskelenmesi ya da işaretlenmesi.

**Neden kritik:** Sağlık ve finansta yasal zorunluluk (KVKK, HIPAA, PCI). Bir TC kimlik numarası ya da hasta adı dış sağlayıcıya gittiğinde geri alınamaz. Ayrıca prompt injection ve jailbreak kurumsal agent'ın en büyük saldırı yüzeyidir.

**Alt yetenekler**
- PII tespiti: TC kimlik (algoritmik doğrulama), telefon, e-posta, IBAN, kart no, ad-soyad (NER), adres, hasta no, doğum tarihi. Türkçe NER modeli şart.
- PII işlemi: maskele (`[TC_KIMLIK]`), kısmi maskele, hash'le, tokenize edip çıkışta geri çevir (reversible), engelle.
- Secret tespiti: API anahtarı, şifre, bağlantı dizesi (regex + entropy).
- Content moderation: nefret, şiddet, cinsel içerik, self-harm; sağlayıcı moderasyon API'si ya da yerel model.
- Prompt injection / jailbreak: "ignore previous instructions" kalıpları, rol değiştirme, encoded payload; sınıflandırıcı model (Prompt Guard, Lakera) + heuristik.
- Konu dışı (off-topic) ve yetkisiz konu kontrolü: asistan sadece İK konusunda konuşsun.
- Çıkış kontrolü: halüsinasyon/groundedness (RAG bağlamına uyuyor mu), yasaklı kelime, format doğrulama (JSON schema), yarışmacı/marka adı, tıbbi tavsiye uyarısı.
- Tool-call kuralları: belirli argüman kalıplarını (DROP TABLE, dış domain) engelleme.
- Özel LLM-judge kuralı: "bu yanıt hasta mahremiyetini ihlal ediyor mu?" gibi serbest politika.
- Uygulama noktası: gateway'de (tüm trafik, kod değişikliği yok), SDK'da, agent runtime'da; giriş/çıkış ayrı ayrı; sync (engelle) ya da async (logla).
- Politika yönetimi: proje bazlı politika seti, önem derecesi, aksiyon (block/redact/warn/log), istisna listesi.
- Gözlemlenebilirlik: tetiklenme sayısı, false positive inceleme kuyruğu, latency.

**Cognipeer'de karşılığı:** Guardrail servisi (PII, secrets, moderation, prompt injection, tool-call rules), ayrı PII Service (detect/redact/mask), Red Team (OWASP LLM Top 10 probları), Analysis (konuşma kalite yargılama), `@cognipeer/guardrail` ve `pii` kütüphaneleri, Guardrails & Safety dashboard'u.

**Nasıl yapılır**
- PII: Microsoft Presidio (açık kaynak, özel tanıyıcı eklenir) + Türkçe spaCy/BERT NER + TC kimlik algoritması.
- Injection: Meta Prompt Guard ya da Lakera Guard API; ek olarak kural tabanlı.
- Moderation: OpenAI moderation endpoint (ücretsiz) ya da Llama Guard self-host.
- Mimari: gateway middleware; politika motoru (YAML kurallar); her guardrail bir "evaluator" arayüzü; paralel çalıştır, en sert aksiyon kazanır.
- Reversible masking: PII→token eşlemesi Redis'te kısa ömürlü; çıkışta geri çevir.

**Ölçüm:** PII kaçak oranı (red team test setinde) < %1; false positive oranı; guardrail latency P95 < 150 ms; injection yakalama oranı.

**Tuzaklar**
- Türkçe için hazır NER zayıf; kendi modelinizi eğitmeniz ya da regex ağırlıklı gitmeniz gerekir.
- Aşırı agresif maskeleme RAG kalitesini düşürür (hasta adı maskelenince "Ahmet Bey'in randevusu" bulunamaz); tokenizasyon tercih edilir.
- Guardrail'in kendisi LLM ise latency ve maliyet ikiye katlanır; önce ucuz kurallar, sonra model.
- Sadece girişi kontrol etmek yetmez; model çıkışta PII üretebilir (RAG bağlamından).

---

## 7. Evaluation: dataset, LLM-as-judge, regresyon

**Ne:** Prompt, model ya da RAG konfigürasyonu değiştiğinde kalitenin düşüp düşmediğini otomatik ölçen test altyapısı.

**Neden kritik:** Prompt değişikliği kod değişikliğidir ama unit test'i yoktur. Evaluation olmadan "yeni model daha iyi mi" sorusu birkaç kişinin 5 örnek denemesiyle cevaplanır ve üretimde patlar. Model sağlayıcıları sürümleri sessizce değiştirir; regresyon testi tek koruma.

**Alt yetenekler**
- Dataset yönetimi: girdi + beklenen çıktı (+ bağlam, metadata); CSV/JSON import; üretim trace'lerinden örnekleme ile dataset oluşturma; versiyonlama.
- Scorer türleri: exact match, regex, JSON schema, semantik benzerlik (embedding cosine), LLM-as-judge (rubric ile 1-5 puan, pairwise karşılaştırma), kod tabanlı özel scorer, insan puanlama.
- RAG metrikleri: context precision/recall, faithfulness/groundedness, answer relevance (RAGAS seti).
- Agent metrikleri: görev tamamlama, doğru tool seçimi, adım sayısı, maliyet, süre.
- Deney yönetimi: aynı dataset üzerinde iki konfigürasyonu (prompt v1 vs v2, model A vs B) yan yana; istatistiksel fark; maliyet/latency karşılaştırması.
- Regresyon: CI'da çalışan eval; eşik altına düşerse prompt yayını engellenir.
- Online evaluation: üretim trafiğinin örneklemi üzerinde judge çalıştırıp kalite trendini izleme; kullanıcı geri bildirimi (thumbs up/down) ile birleştirme.
- Prompt versiyonlama ile entegrasyon: her prompt sürümünün eval skoru kayıtlı.
- Red team eval: injection/jailbreak dataset'i ile güvenlik regresyonu.
- Raporlama: skor dağılımı, en kötü örnekler, hata kategorileri.

**Cognipeer'de karşılığı:** Evaluations servisi (dataset + scorer, offline), Studio Evaluation (semantic, LLM-judge, exact match; accuracy/relevance/consistency), Analysis (konuşma kalite yargılama, alan çıkarma), Prompt Studio (versiyon + test case), Prompt Optimizer (varyant üret-test et-terfi ettir), Red Team. Developer hub roadmap'inde "evals harness" devam ediyor.

**Nasıl yapılır**
- Hazır: Langfuse datasets + experiments, Promptfoo (CI dostu, YAML), RAGAS (RAG metrikleri), DeepEval, Braintrust.
- Sıfırdan: `datasets`, `dataset_items`, `runs`, `scores` tabloları; judge prompt kütüphanesi; worker ile paralel çalıştırma.
- CI: GitHub Actions'ta Promptfoo; eşik altında PR kırmızı.
- Judge modeli: değerlendirilen modelden farklı ve güçlü olmalı (örneğin Claude Opus ile Sonnet'i puanla).

**Ölçüm:** Dataset boyutu (minimum 50-100 örnek/senaryo); judge-insan uyumu (Cohen's kappa > 0.7); eval çalışma süresi; yakalanan regresyon sayısı.

**Tuzaklar**
- LLM-judge kendi tarzını tercih eder; rubric açık ve örnekli olmalı, insan kalibrasyonu şart.
- Dataset üretim dağılımını yansıtmazsa eval yeşil, üretim kırmızı olur; trace'lerden örnekleme.
- Tek sayıya (accuracy %87) indirgenen eval yanıltır; hata kategorileri ve en kötü örnekler gösterilmeli.
- Non-determinizm: aynı girdi farklı çıktı; 3-5 tekrar ile ortalama.

---

## 8. Audit log

**Ne:** Kim, ne zaman, neyi değiştirdi ya da erişti sorusunun değişmez (append-only) kaydı.

**Neden kritik:** Denetim (KVKK, ISO 27001, iç denetim) ilk bunu ister. Maliyeti en düşük, eksikliği en pahalı özellik. Bir sızıntı sonrası "hangi anahtar hangi belgeye erişti" sorusu cevaplanamazsa sorumluluk tanımlanamaz.

**Alt yetenekler**
- Olay türleri: kimlik (login, SSO, token oluşturma/silme), yapılandırma (provider, model, prompt, guardrail politikası, kota değişikliği), erişim (hangi kullanıcı hangi knowledge base'i sorguladı, hangi belgeyi gördü), aksiyon (tool çağrısı, onay verildi/reddedildi), veri (belge yüklendi/silindi, retention sweep), yönetim (rol değişikliği, proje oluşturma).
- Olay şeması: zaman (UTC), aktör (kullanıcı/token/sistem), aktör IP ve user-agent, tenant/proje, kaynak türü ve id, aksiyon, sonuç (success/denied/error), önce/sonra değer (diff, secret maskeli), istek id (trace ile ilişki).
- Değişmezlik: append-only tablo, silme yetkisi yok; isteğe bağlı hash zinciri ya da WORM depolama.
- Retention: en uzun sınıf (1-10 yıl); Cognipeer'de 365-3650 gün aralığı.
- Sorgulama: aktör, kaynak, aksiyon, zaman aralığı filtreleri; export (CSV/JSON); SIEM'e akış (Splunk, Sentinel, syslog).
- Alert: kritik olaylarda (politika kapatıldı, admin eklendi, toplu silme) anında bildirim.
- Tenant izolasyonu: her tenant sadece kendi audit kaydını görür.
- Veri imha kaydı: retention sweep'in ne sildiğinin kendisi audit olayıdır (Cognipeer "Destruction records").
- Prompt/model değişiklik geçmişi: audit ile prompt versiyonlama birleşir; "bu yanıt hangi prompt sürümüyle üretildi" izlenebilir.

**Cognipeer'de karşılığı:** Audit & Security dashboard'u, tenant-scoped audit logs, config ve MCP değişiklik logları (retention sınıfı "Audit", 365 gün varsayılan), Destruction records, Alerts.

**Nasıl yapılır**
- Tablo: `audit_events(id, ts, tenant_id, project_id, actor_type, actor_id, ip, action, resource_type, resource_id, outcome, before, after, request_id)`; Postgres'te partition by month; sadece INSERT yetkisi.
- Üretim: servis katmanında middleware/decorator; her mutasyon otomatik olay yazar.
- SIEM: Kafka ya da doğrudan syslog/HTTP forwarder.
- UI: filtreli tablo + export; 1 hafta iş.

**Ölçüm:** Mutasyon kapsama oranı (her yazma işleminin audit kaydı var mı) %100; audit sorgu gecikmesi; SIEM teslim gecikmesi.

**Tuzaklar**
- Secret ve PII audit'e düz yazılırsa audit'in kendisi sızıntı kaynağı olur; before/after alanları maskelenmeli.
- Uygulama logu ile audit logu karıştırılır; audit iş olayıdır, debug logu değil.
- Silinebilir audit, audit değildir; DB rolü ayrılmalı.
- Saat dilimi tutarsızlığı denetimde sorun çıkarır; her şey UTC.

---

## Yapım sırası ve süre (3-4 kişilik ekip, hazır bileşenlerle)

| Hafta | İş | Çıktı |
|---|---|---|
| 1-2 | Gateway (LiteLLM) + proje/key/kota + Postgres/Redis | Tüm uygulamalar tek endpoint'e bağlı, harcama görünür |
| 3-4 | Tracing (Langfuse) + audit tablosu + temel dashboard | Her istek izlenebilir, her değişiklik kayıtlı |
| 5-7 | RAG pipeline (Docling + pgvector + hibrit + reranker) + erişim filtresi | İlk knowledge base canlı, kaynaklı yanıt |
| 8-9 | Guardrail middleware (Presidio + TC kimlik + injection sınıflandırıcı) | PII dış sağlayıcıya gitmiyor |
| 10-11 | Tool runtime + onay kuyruğu + MCP registry | İlk aksiyon alan agent, onaylı |
| 12-14 | Evaluation (Promptfoo/Langfuse datasets) + CI entegrasyonu | Prompt değişikliği testsiz yayınlanamıyor |

Toplam yaklaşık 14 hafta. Cognipeer Console'u fork etmek bu sürenin yarısını kaldırır ama AGPL ve Next.js/TS yığınına bağımlılık getirir.
