# Terimler (bağlayıcı)

Ekranda Türkçe, kodda İngilizce. Soldaki ad ekran ve belgede, kod adı kolonundaki ad kodda, tabloda ve API'de kullanılır. "Yasak" kolonu karıştırılan ya da yanlış vaat eden adlardır.

## Ürün ve profil

| Doğru | Kod adı | Anlam | Yasak |
|---|---|---|---|
| FFCore | `ffcore` | ürünün adı; modüller Gateway, Trace, Knowledge, Tools, Agents, Guard, Eval, Console, Channels, Platform (PLAN 1b) | "PayCore ürünü", "platform" tek başına marka gibi |
| LLM as a Service (LLMaaS) müşterisi | profil `llmaas` | modeli sağlayıcıdan alan, veri ve orta katmanı kendinde tutan kurum; ürün varsayılanı | "LLM servis", "bulut LLM müşterisi" |
| kapalı ağ müşterisi | profil `airgap` | modeli kendi sunucusunda çalıştıran, dışa çıkışı olmayan kurum | "lokal LLM" tek başına (GPU/CPU ayrımını gizler) |
| çıkarım arka ucu | `INFERENCE_BACKEND=ollama\|vllm` | airgap'te modelin çalıştığı motor | "Ollama profili" (profil değil, arka uç) |
| sağlayıcı | `providers` | model satan ya da sunan taraf (Anthropic, Azure, Ollama) | "vendor", "connector" |
| model (sanal model) | `models`, ad `<project_key>.<model_key>` | LiteLLM'de projeye verilen model adı; sağlayıcı modelini gizler | sağlayıcının ham model adını ekranda kullanmak |
| tek giriş kapısı (facade) | `/v1/chat/completions` | dışa açılan tek adres; LiteLLM iç ağda | "LiteLLM endpoint'i" (dışa açıkmış gibi) |

## Kimlik ve yönetişim

| Doğru | Kod adı | Anlam | Yasak |
|---|---|---|---|
| proje | `projects`, `project_key` | kota, anahtar ve agent'ların sahibi; global benzersiz anahtar | "tenant" (çok kiracılı değil), "workspace" |
| rol / erişim modu | `role: admin\|developer\|analyst\|user`, `access: edit\|read` | rol neyi gördüğünü, mod değiştirip değiştiremediğini belirler | "read-only kullanıcı rolü" (mod, rol değil) |
| salt-okunur mod | `access=read` | aynı ekranlar, hiçbir değişiklik; API 403 | "görüntüleyici rolü" |
| API anahtarı | `api_keys`, `scopes` | dış istemcinin facade'a geldiği anahtar; LiteLLM anahtarı değil | "LiteLLM key", "token" |
| adına çağrı (on-behalf-of) | `X-On-Behalf-Of` JWT | iç servisin son kullanıcı kimliğiyle çağrı yapması | "impersonation" ekranda |
| kota | `quotas`, `usage_daily` | proje ve anahtar bazlı token/maliyet sınırı | "rate limit" (o Redis'teki saniye sınırıdır) |
| audit | `audit_events` | her mutasyonun kaydı | "log" |
| saklama sınıfı | `retention_policies` | veri türüne göre silme süresi | "arşiv" |
| uyarı | `alert_rules`, `alerts` | eşik aşımında bildirim | "alarm" |

## Bilgi tabanı (Knowledge)

| Doğru | Kod adı | Anlam | Yasak |
|---|---|---|---|
| bilgi tabanı | `knowledge_bases`, kısaltma KB | belgelerin indekslendiği küme; RAG burada | "index" tek başına, "veri gölü" |
| üç katman | raw / silver / gold | ham kaynak → dönüşmüş metin → parça+vektör | bronze/silver/gold (o lakehouse'un katmanları) |
| kalite kapısı | Kapı 0 / 1 / 2 | 0 kapsam ve biçim, 1 dönüşüm sonrası metin, 2 parça kalitesi; her red gerekçeli | "filtre" (gerekçesiz çağrışımı) |
| parça | `chunks` | arama birimi; breadcrumb taşır | "segment", "passage" |
| yeniden sıralayıcı | reranker, `RERANK_MIN_SCORE` rerank tabanı | hibrit aramadan sonra ikinci sıralama ve taban | "ikinci eşik" (tek eşik kuralı: reranker açıkken `min_score` kapalı) |
| Türkçe normalizer | iki katman: biçim temizliği (açık), TR düzeltme (varsayılan kapalı) | sorgu ve silver aynı yapılandırmadan geçer | normalizer'ı "zorunlu" diye anlatmak |
| güven skoru | `confidence`, formül `cited` | hesaplanır ve kaydedilir; rozet varsayılan kapalı | "doğruluk skoru" |
| veri kaynağı | `sources` (16) | Confluence, Jira, SharePoint, ağ klasörü; raw'a besler | "connector" (kanal ile karışır) |
| lakehouse / agent sunum DB'si | platform dışı | hasta ve kurum verisi burada; FFEngine CDC ile besler; text-to-SQL yalnızca sunum DB'sine | "RAG'deki hasta verisi" |

## Araçlar ve agent'lar

| Doğru | Kod adı | Anlam | Yasak |
|---|---|---|---|
| araç | `tools` (kind `mcp\|openapi`) | backend'in **tükettiği** MCP ya da OpenAPI sunucusu | "plugin", "skill" |
| aksiyon | `tool_actions` | aracın tek bir çağrılabilir işlevi; onay ve açık/kapalı aksiyon bazında | "fonksiyon" ekranda |
| MCP sunucusu | `mcp_servers` (05b) | backend'in **yayınladığı** MCP ucu (OpenAPI → MCP) | tüketilen araçla aynı adı kullanmak |
| onay | `approvals` (07), run durumu `waiting_approval` | aksiyon çalışmadan önce insan onayı (HITL) | "moderasyon" |
| agent | `agents`, `agent_versions`, ad `agent:<project_key>/<agent_key>` | tanımı veri olan (JSON), LangGraph grafı üretilen yürütücü | "bot", "asistan" (asistan yalnızca kanal ekranında kullanıcıya görünen ad) |
| agent sürümü / yayın | `agent_versions`, `published` | her değişiklik sürüm; yayınlanan sürüm facade'dan görünür | "deploy" |
| koşu | `runs`, `run_events` | bir agent çağrısının tamamı; event'ler sıralı | "session", "trace" (trace Langfuse'daki izdir) |
| bağlam bütçesi | `limits.context_tokens`, `context_policy` | her turda hafıza, RAG ve geçmişe pay dağıtımı | "context window" (o modelin sınırıdır) |
| kuyruk sınıfı | etkileşimli / etkileşimli-düşük / arka plan; kuyruklar `llm-interactive`, `llm-background` | CPU'da sohbet önce, sınav ve hafıza mesai dışı | "öncelik seviyesi 1-5" |
| hafıza | `memories` (14) | kullanıcıya özel, kurum içinde, kullanıcı kontrolünde kalıcı bilgi | "profil", "geçmiş" (geçmiş konuşmadır) |
| kanal | `channels` (15) | web widget, Slack, Teams, Mattermost; agent'ın kullanıcıya ulaştığı yüzey | "connector", "entegrasyon" |

## Koruma ve ölçüm

| Doğru | Kod adı | Anlam | Yasak |
|---|---|---|---|
| guardrail | `guardrail_policies`, `rules` | metin ve araç çağrısı kuralları; modlar off / monitor / enforce | "filtre", "sansür" |
| aşama | `stage: prompt.pre … egress` | kuralın uygulandığı nokta (7 aşama, C4) | "hook" ekranda |
| PII | `pii_policies`, aksiyon `redact\|tokenize\|block` | kişisel veri tespiti; Türkçe NER modeli gerçek model | "anonimleştirme" (tokenize geri çevrilebilir) |
| sınav (evaluation) | `eval_datasets`, `eval_suites`, `eval_runs`, scorer | soru seti ile agent'ın ölçülmesi | "test" (test yazılım testidir) |
| sonuç etiketi | `outcome_label` | `answered`, `declined`, `below_threshold`, `not_retrieved`, `not_reranked`, `below_rerank_floor`, `unanswerable_*` | "başarılı/başarısız" ikilisi |
| izleme | Langfuse trace, `langfuse_trace_id` | her LLM ve araç çağrısının izi ve maliyeti | "log" |

## Yürütme terimleri

| Terim | Anlam |
|---|---|
| paket | `plan/NN-*.md` ile tanımlı iş birimi; a/b alt paketler ayrı PR |
| dalga | aynı anda çalışabilen paket kümesi (PLAN 7); kapı dalga değil doğrudan bağımlılık bazlıdır |
| PoC | M1-M3 kapsamı (PLAN 7 "PoC" kolonu); 13b ile kapanır, Qwen/CPU ve model kararı burada |
| uzlaştırıcı (reconciler) | 01'deki `render-litellm`: tabloları LiteLLM DB'siyle karşılaştırıp model API'siyle farkı uygular; config dosyası üretmez |
| `LLM_SLOTS` | tekil model çağrılarının geçtiği Redis tabanlı öncelikli eşzamanlılık yuvası (cpu 1); run'lar arq işidir |
| iç servis hesabı | `SERVICE_TOKEN` ile çağıran iç servis (mcp-search, worker); dış API anahtarından (03c) ayrıdır |
| tüketici (paycoreLLM) | FFCore'u path bağımlılığı / wheel + imaj olarak kullanan kurulum deposu; uzantıları `ffcore.*` entry point'lerine kayıt olur (C14); FFCore tüketiciyi import etmez |
| uzantı | tüketiciye özgü modül (PayCore `jira/`, `prsim/`, `router/`); ikinci müşteride de işe yararsa FFCore'a **terfi** eder |
| 00i | PayCore entegrasyon tabanı ve sıkılaştırma paketi; 03a/01/04a onu bekler |
| S1 seti | PayCore'un 50 soruluk iç dokümantasyon sınavı; PoC kalite kabulü (≥ %80), sunucuda kullanıcı eliyle koşar |
| kilometre taşı | M1-M7, PLAN 8; kullanıcıya demo noktası |
| koordinatör / işçi | BASLATMA.md rolleri |
| claim | paketin `state/WORK_QUEUE.md`'de tek işçiye bağlanması |
| touch-zone | claim'in dokunabileceği dosya alanı |
| kanıt | PR açıklamasındaki kabul kriteri → test → komut → çıktı zinciri |
| donmuş sözleşme | CONTRACTS.md'deki ID; kilometre taşından sonra yalnızca additive |
| profil farkı | kodda dal değil yapılandırma değeri (PLAN 5) |
| fail-loud | sessiz fallback, kırpma ve atlama yok; her red kayıtlı ve gerekçeli |
