# Cognipeer Ürün Analizi (23 Ekim 2026)

Kaynaklar: cognipeer.com, developer.cognipeer.com, docs.cognipeer.com, github.com/cognipeer ve console.cognipeer.com (Enterprise plan, boş proje ile gezildi).

## 1. Ürün nedir?

Cognipeer kendini "AI Operating Suite" olarak konumlandıran, üç katmanlı bir kurumsal LLM platformu:

| Katman | Ürün | Ne yapar | Lisans |
|---|---|---|---|
| Build | **Studio** | No-code agent ("Peer") builder, Flow (görsel workflow), Agent Ops (uzun süreli sandbox işleri), veri kaynakları, araçlar, evaluation, kanal yayınlama (Slack, WhatsApp, Chatwoot, webchat, API) | Kapalı / SaaS + on-prem |
| Control | **Console** | OpenAI-uyumlu LLM gateway, çoklu provider routing + fallback, proje/tenant izolasyonu, kota, scoped API key, RAG (vektör DB + dosya ingest), guardrail/PII, tracing (OTLP), MCP hub, prompt yönetimi, Cedar yetkilendirme | AGPL-3.0 (açık kaynak), EE kapalı |
| Work | **Pulse** | Kullanıcı başına kalıcı timeline, arka plan görevleri, zamanlanmış işler, onay akışları, memory, entegrasyonlar (Slack, GitHub, Jira, Notion, Drive, CRM), dosya/artefakt üretimi, meeting agent, code agent, voice | Kapalı |

Developer tarafı: Agent SDK (MIT, TS, LangChain'siz runtime; runtime profilleri, HITL, structured output, handoff, subagent, OTel tracing), Agent Server (REST+SSE), Chat UI (React), Console SDK, Client SDK, to-markdown (20+ format), graph-builder, observability lib.

Console EE (kapalı): GPU fleet/MIG, izole sandbox, LDAP/AD SSO, realtime voice, prompt optimizer, cluster admin, red-teaming (OWASP LLM Top 10).

## 1b. Konsol incelemesi (console.cognipeer.com)

Hesap: Enterprise plan, sıfır model / agent / veri; yani ürün boş halde gezildi, gerçek trafik davranışı görülmedi.

**Yapı.** Tek bir "proje" seçicisi, tenant düzeyinde Providers, proje düzeyinde API Token; IAM merkezi ayrı. Hesap menüsü: My account, Settings, License, Help & Support. Sol rayda 6 sabitlenmiş servis, "Pin more" ile 31 servisin tamamı.

**31 servis, kategoriye göre**

| Kategori | Servisler |
|---|---|
| Build (6) | Model Hub (provider + fiyat), Prompt Studio (versiyonlu şablon + test case), Agents, Portals (seçili agent'lar için hazır chat sayfası), Prompt Optimizer, Config Management (secret/config) |
| Data (8) | Knowledge Index (vektör), Knowledge Engine (RAG modülü), Agent Memory (semantik kalıcı hafıza), Document Store (bucket), Reranker, Crawlers, Web Search (Bing/Brave/Serper/Tavily/SearxNG/DDG), OCR Jobs |
| Operate (14) | Agent Observability, Model Monitoring (vLLM), Guardrail (PII, secret, moderation, prompt injection, tool-call kuralları), PII Service, Evaluations (dataset + scorer), Red Team, Analysis (konuşma alanı çıkarma, kalite yargılama), MCP Servers (API'yi MCP'ye çevirme), Browsers (headless profil), Realtime (WebSocket voice + telefon köprüsü), Alerts & Incidents (threshold/baseline/absence/SLO), Cost & Optimization (model değiştirme önerisi, parite testi), Automations, Sandbox |
| Admin (3) | Cluster, GPU Fleet (host onboarding, model marketplace, pool, bulk deploy), AI App Gateway (Claude Code / Codex / Copilot kullanımını kim, ne gönderiyor, ne yapabilir diye kontrol) |

**Analitik.** 21 hazır dashboard: Model Ops, Cost & Spend, Users & Tokens (kullanıcı ve token bazlı harcama), Agent Sessions/Health, Guardrails, Model/KB/MCP/Tool Health, RAG, Web Search, Browser, Crawler, Batch, Audit, Sandbox, Realtime Voice. Ayrıca "Health" paneli (critical/warning/degraded/healthy/idle) ve aktif incident listesi.

**Data Retention.** Veri sınıfı bazlı saklama süreleri ve izin verilen aralıklar görünür: içerik 30 gün (1–90), telemetri 90, trace 30, audit 365 (365–3650), usage rollup 760 gün. Dry-run ve "clean now" var, proje bazlı istisna ve imha kaydı tutuluyor. KVKK için ciddi bir artı.

**Gözlemler**
- Yüzey, pazarlama sayfasından bile geniş: 31 servis, 21 dashboard. "NEW" etiketli servis sayısı 14; ürün hızlı genişliyor ama bu kadar modül küçük ekipte olgunluk farkı yaratır.
- Birkaç küçük pürüz: `/agents/new` doğrudan açılınca "Agent not found", Model Hub içindeki "Providers" linki "We could not find this model" diyor. Kırık kenarlar var ama çekirdek akış (provider → model → prompt → agent) net.
- AI App Gateway dikkat çekici: Claude Code, Codex, Copilot gibi kodlama agent'larının kurumsal kontrolü. 2026'da yeni bir ihtiyaç ve çok az rakip var.
- Guardrail'de tool-call kuralları ve prompt injection koruması, Analysis'te konuşma kalite yargılama; bunlar olgun gözlemlenebilirlik ürünlerinde (Langfuse, Arize) yeni yeni görülen özellikler.
- Fiyat yine görünmüyor; Enterprise plan etiketi var ama kota/limit bilgisi yok.

## 2. Değerlendirme

**Güçlü yönler**
- Console'un tasarımı doğru yerde: gateway + tenant/proje + kota + tracing + guardrail aynı yerde. Bu, kurumsal LLM benimsemesinin en çok sorun çıkaran kısmı.
- Açık kaynak çekirdek (AGPL) ve self-host (SQLite ile sıfır bağımlılık, Docker/Helm) düşük giriş bariyeri sağlıyor.
- Tek bir tedarikçiden "agent builder + gateway + günlük asistan" üçlüsü; rakipler genelde tek katmana odaklanıyor (LiteLLM/Portkey gateway, Dify/Flowise builder, Glean/Copilot asistan).
- Türkiye merkezli ekip; yerel referanslar, KVKK/veri yerleşimi için on-prem seçeneği.

**Zayıf / riskli yönler**
- Çekinme çekirdeği: GitHub yıldız sayıları düşük (console 26, diğerleri 0-11). Topluluk ve üçüncü parti doğrulaması zayıf.
- Fiyatlandırma sayfası yok; SOC2/ISO/HIPAA gibi sertifika beyanı yok. Kurumsal satın alma için eksik.
- Çok geniş yüzey alanı (GPU fleet, voice, meeting bot, mobil uygulama, red-team...) küçük bir ekip için derinlik riskini artırıyor. Her modülün olgunluğu farklı olabilir.
- AGPL lisansı, Console'u kendi kapalı ürününüze gömmek isterseniz ticari lisans gerektirir.
- Konsol, pazarlamanın vaat ettiğinden fazlasını içeriyor; sorun vaat değil, 31 modülün her birinin derinliği. Boş projede küçük kırık linkler görüldü; gerçek yükte davranış test edilmedi.

## 3. Bu ürünü hangi amaçlarla kullanabilirsiniz?

Hastane / sağlık bağlamı (Türkiye Hastaneleri projesi) için:

1. **Merkezi LLM gateway** olarak: tüm iç uygulamalar tek OpenAI-uyumlu endpoint'e bağlanır; model değiştirmek, maliyet izlemek, departman başına kota koymak tek yerden yapılır.
2. **Veri yerleşimi gereken RAG**: hasta bilgisi içermeyen ama kurumsal (prosedür, mevzuat, SUT, ilaç prospektüsü) dokümanlar için on-prem bilgi asistanı.
3. **PII/guardrail katmanı**: Tüm LLM trafiğinde TC kimlik, hasta adı gibi verileri maskeleme ve politika uygulama.
4. **İç operasyon agent'ları**: İK/İdari sorular, randevu-çağrı merkezi destek, fatura/SGK itiraz süreçleri için Peer + Flow.
5. **Agent gözlemlenebilirliği**: Kendi yazdığınız agent'ları (Claude Agent SDK, LangChain vb.) Console tracing'e bağlayıp denetim izi oluşturmak.
6. **Hızlı PoC**: Studio ile kod yazmadan bir Peer kurup WhatsApp/webchat'e çıkmak.

Dikkat: Hasta verisiyle çalışacaksanız self-host zorunlu; SaaS kullanımında KVKK ve veri işleme sözleşmesini sorgulayın.

## 4. Benzerini yapmak için neler gerekir?

Minimum ekip: 3-5 kişi (1 backend/platform, 1 frontend, 1 AI/RAG, 1 DevOps-yarı zamanlı, 1 ürün). 80/20 çekirdeği için 3-4 ay, tam süit için 12-18 ay.

| Bileşen | Yapı taşı / alternatif | Zorluk |
|---|---|---|
| OpenAI-uyumlu gateway + routing + fallback | LiteLLM (açık kaynak) üzerine ince katman, ya da sıfırdan Node/Go proxy | Orta |
| Tenant/proje, API key, kota, rate limit | Postgres + Redis; Cedar/OPA ile policy | Orta |
| Tracing | OpenTelemetry GenAI semantic conventions; Langfuse/Phoenix gömülebilir | Düşük-orta |
| RAG | to-markdown benzeri ingest (unstructured/docling), chunking, pgvector/Qdrant, reranker | Orta |
| Guardrail / PII | Presidio, LLM-judge, regex; politika motoru | Orta |
| Agent runtime | Mevcut SDK'lar (Claude Agent SDK, OpenAI Agents, LangGraph) üzerine HITL + structured output | Düşük-orta |
| No-code Peer builder + Flow canvas | React Flow tabanlı editör; en pahalı UI işi | Yüksek |
| Kanal entegrasyonları | Slack/WhatsApp Business API/webchat widget | Orta |
| Evaluation | Dataset + LLM-as-judge + semantic score | Düşük-orta |
| Sandbox / code agent | Docker/Firecracker/E2B | Yüksek |
| Pulse benzeri asistan (timeline, görev, memory, meeting bot, mobil) | Çok büyük yüzey; ayrı ürün | Çok yüksek |
| GPU fleet, voice, LDAP SSO | Yalnızca kurumsal gereksinimde | Yüksek |

Pratik öneri: Sıfırdan yazmak yerine Console'u (AGPL) fork edip sağlık alanına özel guardrail ve veri kaynaklarıyla genişletmek ya da LiteLLM + Langfuse + bir RAG servisi + Claude Agent SDK kombinasyonu ile %80'i 1-2 ayda kurmak.

## 5. LLM sektöründe kıymetli özellikler: 80/20 derecelendirmesi

Puan: 1-5 (5 = en değerli). Etki = kullanıcının gördüğü değer, Çaba = yapım maliyeti. 80/20: yüksek etki / düşük-orta çaba olanlar.

### A. Çekirdek %20 (değerin %80'ini üretir)

| # | Özellik | Etki | Çaba | Neden |
|---|---|---|---|---|
| 1 | OpenAI-uyumlu tek gateway, çoklu provider, fallback | 5 | 2 | Her uygulamanın tek bağlantı noktası; vendor lock-in'i kırar, kesinti riskini azaltır |
| 2 | Proje/tenant izolasyonu + scoped API key + kota/bütçe | 5 | 2 | Maliyet kontrolü ve güvenlik olmadan kurumsal yayılım olmaz |
| 3 | Tracing / token-maliyet izleme (OTel) | 5 | 2 | "Ne oldu, neye mal oldu" sorusu her kurumda ilk sorulan |
| 4 | RAG: dosya ingest + vektör arama + kaynak gösterme | 5 | 3 | Kurumsal LLM kullanım senaryolarının çoğu bilgi erişimi |
| 5 | Guardrail + PII maskeleme (giriş/çıkış) | 4 | 2 | Sağlık/finans için yasal zorunluluk; nispeten ucuz |
| 6 | Tool calling + HITL onay kapısı | 5 | 2 | "Cevap veren" değil "iş yapan" agent'ın ayrım noktası; onay olmadan kimse aksiyon açmaz |
| 7 | Evaluation (dataset + LLM-judge + regresyon) | 4 | 2 | Prompt/model değişimini güvenle yapmanın tek yolu |
| 8 | Audit log | 4 | 1 | Düşük maliyet, denetim ve uyum için şart |

### B. Değerli ama ikinci dalga

| # | Özellik | Etki | Çaba | Not |
|---|---|---|---|---|
| 9 | No-code Peer/agent builder | 4 | 4 | İş birimlerini kazandırır ama UI maliyeti yüksek |
| 10 | Kanal yayınlama (webchat, Slack, WhatsApp) | 4 | 3 | Dağıtım olmadan benimseme olmaz |
| 11 | MCP hub / tool registry | 4 | 3 | 2026'da standart; yetki kontrollü MCP kıymetli |
| 12 | Prompt versiyonlama (dev/staging/prod) | 3 | 2 | Ucuz, disiplinli ekipler için değerli |
| 13 | Semantik memory (kullanıcı/proje bazlı) | 4 | 3 | Asistan deneyimini değiştirir; curasyon zor |
| 14 | Görsel Flow / workflow canvas | 3 | 4 | Çoğu ekip için kodla yazmak daha hızlı |
| 15 | Zamanlanmış/arka plan görevler + webhook tetikleyici | 4 | 3 | Pulse'un en somut değeri |
| 15b | Veri saklama politikası (sınıf bazlı retention, imha kaydı) | 4 | 2 | KVKK/GDPR için ucuz ve ayırt edici; konsolda iyi çözülmüş |
| 15c | Kullanıcı/token bazlı harcama raporu + alert/SLO | 4 | 2 | Kota ile birlikte "kim ne harcıyor" sorusunu kapatır |
| 15d | Kodlama agent'ları için gateway (Claude Code/Codex/Copilot kontrolü) | 4 | 3 | Yeni ihtiyaç, az rakip; yazılım ekibi olan kurumlar için |

### C. Niş / pahalı (yalnızca gerektiğinde)

| # | Özellik | Etki | Çaba | Not |
|---|---|---|---|---|
| 16 | İzole code sandbox / code agent | 3 | 5 | Yazılım ekipleri dışında talep düşük |
| 17 | Realtime voice / telefon | 3 | 5 | Çağrı merkezi varsa yüksek, yoksa gereksiz |
| 18 | Meeting bot (Zoom/Teams) | 2 | 4 | Doygun pazar (Otter, Fireflies, Copilot) |
| 19 | GPU fleet / MIG yönetimi | 2 | 5 | Yalnızca kendi modelini barındıranlar |
| 20 | Red-teaming otomasyonu | 3 | 3 | Güvenlik ekibi varsa değerli |
| 21 | Prompt optimizer | 2 | 4 | Henüz olgunlaşmamış alan |
| 22 | Mobil/masaüstü istemci | 2 | 5 | Web + Slack çoğu kurum için yeter |
| 23 | Graph-builder (reasoning graph) | 2 | 4 | Deneysel |

### Sonuç

İlk 8 madde (A grubu) toplam çabanın yaklaşık %20'si ile kurumsal değerin %80'ini verir. Cognipeer'in Console ürünü tam da bu 8 maddeyi hedefliyor; Studio ve Pulse ise B ve C gruplarına yayılıyor. Kendi ürününüzü yapacaksanız A grubunu bitirmeden B'ye geçmeyin.
