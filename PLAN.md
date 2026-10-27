# FFCore: Kurumsal LLM Platformu Geliştirme Planı

Sürüm 2.4, 27 Ekim 2026 (geçmiş bölüm 11). **PoC kapsamı** (M1-M3) bölüm 7'de işaretlidir ve **PayCore LLM'de `airgap` profiliyle canlı koşar** (bölüm 2d); PoC sonrası paketler brief'leriyle birlikte bağlayıcı kalır. Bu dosya mimariyi, kısıtları, depo düzenini ve iş paketlerinin sırasını tanımlar. Her iş paketi `plan/` klasöründe ayrı bir brief olarak durur ve tek başına bir geliştirici agent'a verilebilir. Bir agent'a brief verirken bu dosyayı da ekleyin; ortak kurallar burada.

## 1. Amaç

Model dışındaki her şeyin kurum içinde kaldığı bir LLM platformu. **Birincil pazar ve ürün varsayılanı:** modeli LLM as a Service (LLMaaS) olarak bir sağlayıcıdan alan, verisini ve orta katmanı kendinde tutan kurumlar (`llmaas` profili). **İkincil:** modeli kendi sunucusunda çalıştıran kapalı ağ kurumları (`airgap` profili). **Pilot müşteri:** Türkiye Hastanesi, `llmaas` profiliyle (veri kurum içinde kalır, model sağlayıcıdan; bkz. bölüm 2b). Kapalı ağ profili geliştirme ve ikinci müşteri tipi için korunur.

- Açık kaynak bileşenlerle (LiteLLM, Langfuse, LangGraph, pgvector, Presidio) kurulan çekirdek.
- Bu bileşenleri tek yerden yöneten Türkçe bir web önyüzü.
- Kod bilmeyen bir iş analistinin önyüzden agent kurup yayınlayabilmesi.
- Çekirdek 8 özellik: tek kapı, proje/kota, izleme, bilgi tabanı (RAG), araç + onay, guardrail/PII, sınav (evaluation), audit.
- Katma değer: kurumun kalıcı kullanıcıları için kullanıcıya özel, kurum içinde saklanan, kullanıcının kontrolündeki kalıcı hafıza (14).

Cognipeer Console'un yaptığı işin, bizim kısıtlarımıza göre sadeleştirilmiş ve sahiplenilmiş hali. Ayrıntılı gerekçe için `cognipeer-analiz.md` ve `cekirdek-8-ozellik.md`.

## 1b. Ürün adı ve modüller

Ürün adı **FFCore**; FF ürün ailesinin (FFEngine, FFGov) parçasıdır. Ad tek bir özelliği değil, modelin dışındaki katmanın tamamını (kapı, bilgi, araç, agent, koruma, izleme) adlandırır. Modül adları pazarlama ve ekran başlıkları içindir; kod, tablo ve dizin adları İngilizce ve paket brief'lerindeki gibi kalır. Her brief'in başlığında köşeli parantez içinde ait olduğu modül yazar.

| Modül | Ne yapar | Paketler |
|---|---|---|
| FFCore Gateway | Tek kapı: sağlayıcı/model kataloğu, sanal model adları, proje, API anahtarı, kota, audit, retention, uyarılar | 01, 03 |
| FFCore Trace | İzleme: her LLM ve araç çağrısının izi, maliyet, gecikme (Langfuse) | 02 |
| FFCore Knowledge | Bilgi tabanı: üç katmanlı ingest, kalite kapıları, yerel embedding, arama, ACL; kaynak bağlayıcıları | 04, 16 |
| FFCore Tools | Araç katmanı: MCP kaydı, text-to-SQL, belge arama, OpenAPI'yi MCP olarak yayınlama | 05 |
| FFCore Agents | Agent tanımı ve çalıştırma, onay kuyruğu, kullanıcı hafızası | 06, 07, 14 |
| FFCore Guard | Guardrail ve PII (Türkçe NER), Monitor/Enforce | 08 |
| FFCore Eval | Sınav: dataset, suite, run, scorer, aşama bazlı teşhis | 09 |
| FFCore Console | Türkçe yönetim önyüzü ve chat arayüzü | 10, 11 |
| FFCore Channels | Web widget, Slack, Teams, Mattermost | 15 |
| FFCore Platform | Depo iskeleti, compose, kurulum ve paketleme, örnek veri ve duman testi | 00, 12, 13 |

Paket 17 (son kullanıcı açılışı, AD/LDAP) FFCore Gateway'e girer. Alan adı ve marka tescili ürün sahibinin işidir (KARARLAR.md).

## 2. Kısıtlar (her paket için geçerli)

| Kısıt | Sonuç |
|---|---|
| Dış ağ yalnızca izin listesiyle | `llmaas`: yalnızca sağlayıcı ve etkin kanal/kaynak adreslerine çıkış (egress allow-list); `airgap`: hiç çıkış yok, imajlar ve paketler iç registry/PyPI aynasından (12). Her iki profilde de iç registry kullanılabilir |
| Model (`llmaas`, varsayılan): sağlayıcıdan; (`airgap`): Qwen 3.5 35B Ollama CPU (PoC) ya da vLLM + GPU (üretim) | `llmaas`'ta sağlayıcı eşzamanlılığı ve 429 geri çekilmesi (01 retry) belirleyici. CPU yavaş ve sınırlı: RAG cevabı 1,5-2 dk, araçlı agent turu ~3 dk, eşzamanlı kullanıcılar sıraya girer (PayCore ölçümü); prompt'lar kısa, tool şemaları az ve net, paralel çağrı yok, streaming şart, thinking kapalı, `OLLAMA_CONTEXT_LENGTH` zorunlu. `INFERENCE_BACKEND=ollama\|vllm` yapılandırma değeri; GPU rehberi 12'de (PayCore düzeltmesi D6, D8). Her iki profilde LiteLLM aynı sanal model adı |
| Bilgi tabanı üç katmanlı | raw (ham kaynak) → silver (dönüşmüş, kapılardan geçmiş metin) → gold (parça + vektör). Kalite kapıları her katmanda gerekçeli; hiçbir şey sessizce atılmaz. Kaynağa yalnızca raw koşusu gider (PayCore düzeltmesi D1, D3) |
| Embedding de yerel | Ollama üzerinden küçük bir embedding modeli (örn. bge-m3 ya da nomic-embed-text; Türkçe desteği olan seçilir). Belge hiç dışarı çıkmaz |
| Vektör deposu müşteriye göre değişir | Tek `VectorStore` arayüzü (C5, sparse sorgu taşır); pgvector ürün varsayılanı (ek servis yok; dense + Postgres BM25), Qdrant ikinci sürücü (dense + bge-m3 sparse; **PayCore PoC'de birincil**, canlı korpus orada). Metin ve BM25 her durumda Postgres'te; sürücüler arası geçiş embedding'siz kopyalama |
| Dağıtım: Docker Compose, tek Linux sunucu | Kubernetes yok. Tek `docker-compose.yml`, ortam farkları `.env` ile |
| Kapasite (P7) | Pilot hedefi 10 eşzamanlı etkileşimli kullanıcı. `llmaas`'ta sınır sağlayıcı eşzamanlılığıdır; 429'da üstel geri çekilme ve yalnızca açık yapılandırılmış fallback (01). `airgap` CPU'da tek şerit, sıraya girer. Arka plan model işleri (sınav, hafıza, judge) öncelikli kuyrukta ve mesai dışı pencerede; `docs/donanim.md` (12) sunucu spec ve bellek bütçesini verir |
| Son kullanıcı (P4) | Pilotta (M3-M5) son kullanıcı yok; sohbet analist ve bilgi işlemle test edilir. `user` rolü veri modelinde rezerve; son kullanıcı açılışı ve AD/LDAP girişi M6 sonrası paket 17 |
| Kimlik: yerel kullanıcı + rol + erişim modu | E-posta/şifre ile giriş. Dört rol: admin, developer, analyst, user (rezerve, pilotta atanmaz); her rolün iki erişim modu: `edit` ve `read`. Salt-okunur kullanıcı rolünün gördüğü ekranların aynısını görür, hiçbir değişiklik yapamaz (önyüzde düğmeler pasif, API'de 403). AD/LDAP ileride |
| Özel nitelikli kişisel veri RAG'e girmez | RAG'de sözleşme, prosedür, kurumsal doküman; yapısal veri için text-to-SQL yalnızca ayrı, salt-okunur bir agent sunum DB'sine (kişi düzeyi veri yükleme anında maskelenmiş). Hastane örneği: hasta verisi platformda yok, lakehouse'ta kalır |
| Dil | Arayüz Türkçe; kod, API, veritabanı adları, commit mesajları İngilizce |

## 2b. Dağıtım profilleri

Aynı kod iki müşteri tipine kurulur:

- **LLM as a Service (LLMaaS) kullanan müşteriler** (`llmaas`, **ürün varsayılanı**): modeli Anthropic, OpenAI, Azure OpenAI ya da AWS Bedrock gibi bir sağlayıcıdan servis olarak satın alan, ancak indeks, agent tanımları, araçlar, onay, audit ve sınav gibi orta katmanın tamamını kendi içinde tutan kurumlar. Pilot müşteri Türkiye Hastanesi bu profildedir.
- **Kapalı ağ müşterileri** (`airgap`): modeli kendi sunucusunda çalıştıran, dış ağı olmayan kurumlar. İkincil profil; geliştirme ortamı ve ikinci müşteri tipi için tam desteklenir.

Profil `.env` içindeki `DEPLOY_PROFILE` ile seçilir (`.env.example` varsayılanı `llmaas`; 00 ve 13 bunu kullanır); paketler bu değişkene göre davranış ayırır. **PoC profili `airgap`'tir** (PayCore LLM; bölüm 2d): ürün varsayılanı değişmez, PoC'nin test ve deploy profili açıkça `airgap` olur; `llmaas` Türkiye Hastanesi için paralel geliştirilir, canlı kullanımı sonra.

| Konu | `llmaas` (varsayılan) | `airgap` (kapalı ağ, yerel model) |
|---|---|---|
| Dış ağ | Yalnızca sağlayıcı ve etkin kanal/kaynak adreslerine izin listesi (egress allow-list); diğer her şey kapalı | Yok; `OFFLINE=true` |
| Model | Anthropic, OpenAI, Azure OpenAI, Bedrock; birden fazla sağlayıcı arası fallback | Ollama Qwen (CPU) ya da vLLM (GPU) |
| Bölge ve saklama | Sağlayıcıda EU bölgesi ve sıfır saklama (zero data retention) sözleşmesi zorunlu; `docs/veri-isleme.md` doldurulur | Konu dışı |
| Embedding | Her profilde **süreç içi** bge-m3 (`FlagEmbedding`, dense + sparse; C10 tersine döndü, bkz. 2d: Ollama sparse ağırlık üretmez); yalnızca API süreci yükler, worker'lar arama API'sini çağırır; belge indeksleme sırasında dışarı çıkmaz. Sağlayıcı embedding'i yalnızca açık kararla | Aynı |
| İndeks ve veri | İçeride; dışarı sadece soru anındaki parçalar | İçeride |
| PII/guardrail | Kritik: modele giden her metin maskeli; dışarı giden içerik ayrı loglanır (`guardrail_events.stage=egress`) | Önemli |
| Fiyat ve kota | Gerçek fiyat tablosu; aylık USD bütçe ve uyarılar aktif | Sanal fiyat |
| Sunum (inference) | Sağlayıcı; eşzamanlılık ve 429 geri çekilmesi (01) | `INFERENCE_BACKEND=ollama` (CPU, PoC ve küçük kurulum) ya da `vllm` (GPU, üretim); `docs/donanim.md` (PayCore düzeltmesi D8) |
| Kalite eşikleri | Yüksek; judge modeli gerçek; araç sayısı artabilir | Düşük (Qwen CPU); kabul kriterleri `cpu` ve `gpu` sütunlarıyla (13) |
| Zaman aşımı (LLM çağrısı / run) | LLM çağrısı 60 s / run 120 s | CPU: LLM çağrısı 600 s / run 900 s; GPU: 120 s / 300 s |
| Kurulum | 12: ana rehber `docs/kurulum.md`; çıkış kuralları ve sağlayıcı anahtarı yönetimi | 12: ek rehber `docs/kurulum-kapali-ag.md`; imaj, wheel ve model taşıma |
| Uyum belgesi | `docs/veri-isleme.md`: sağlayıcıya ne gider, ne kadar kalır, hangi bölge, kim sorumlu | Yok |

Her iki profilde de orta katman (indeks, agent tanımı, araçlar, onay, audit, sınav) müşteride kalır. Fark yalnızca modelin nerede olduğu ve dışarı çıkan metnin nasıl korunduğudur. LLMaaS müşterisi için ürünün değer önerisi şudur: sağlayıcıdan yalnızca modeli kiralar, geri kalan her şeyi (verisi, bilgi tabanı, agent'ları, kuralları, kayıtları) kendinde tutar ve sağlayıcıyı istediğinde değiştirir.

Profil farkı olan paketler: 01 (sağlayıcı listesi, fallback, timeout, fiyat), 08 (egress aşaması, eşikler), 09 (judge modeli, eşikler), 12 (çıkış kuralları, uyum belgesi), 13 (kabul eşikleri), 14 (çıkarma modeli ve egress). Diğer paketler profilden bağımsızdır.

Kullanıcıya özel kalıcı hafıza (14) her iki profilin de özelliğidir: kurumların kalıcı kullanıcıları (yöneticiler, bölüm sorumluları, uzmanlar) her iki tipte de vardır; hafıza her durumda kurum içinde saklanır ve kullanıcının kontrolündedir.

## 2d. PayCore LLM entegrasyonu (canlı test yeri; 27 Ekim kararları)

FFCore'un canlı test ve ilk kullanım yeri PayCore LLM'dir (`C:\ai_paycore\paycoreLLM`; internetsiz sunucu, 32 vCPU, Qwen 3.5 35B Ollama CPU, Qdrant, Confluence/Jira korpusu). Türkiye Hastanesi `llmaas` profiliyle ikinci kurulumdur. Kararlar (KARARLAR "PayCore entegrasyonu"):

1. **Depo modeli:** FFCore ayrı depoda ürün olarak kalır; paycoreLLM tüketicidir (geliştirmede path bağımlılığı, sunucuda iç registry'den wheel ve imaj). Tek yön `paycore_llm → ffcore`. PayCore'a özgü `jira/`, `prsim/`, `router/` paycoreLLM'de **uzantı** olarak kalır ve FFCore uzantı noktalarına (CONTRACTS C14) kayıt olur. Terfi kuralı: ikinci müşteride de işe yarayan ekleme FFCore'a taşınır.
2. **Anayasa:** paycoreLLM kökünde FFCore CLAUDE.md geçerli; PayCore'un sıkı kuralları (dış servise veri yok, `.env`'e dokunma, sunucuya ajan bağlanmaz, Jira yazma kapısı) aynen; "dal açılmaz" kuralı FFCore branch + PR akışıyla değişir.
3. **Sıra:** PayCore Faz 1 açıkları (kimlik sınırı, compose sıkılaştırma, eşzamanlılık donması, Langfuse gönderimi, S1 taban ölçümü) 00i paketinde önce kapanır; W17 kilidi (text-to-SQL) ancak sonra ve yalnızca sentetik sunum DB'si için açılır.
4. **Yığın (PayCore seed'i):** Qdrant + bge-m3 sparse birincil, embedding süreç içi, DuckDB belge deposu PoC'de `KnowledgeStore` bağdaştırıcısıyla sarılır (Postgres göçü PoC sonrası, `DEBT-` kaydı), LiteLLM ve arq + Redis eklenir (Jira kuyruğu arq'a taşınır), Langfuse v3, PaddleOCR, güven formülü seed'de `max`, 4B router kapalı, Open WebUI PoC chat'i (11 ertelendi).
5. **Agent kapsamı (CPU ölçümü):** PoC'de iki agent: `mode: always` doküman asistanı ve tek araç çağrılı onaylı SQL asistanı; `mode: tool` ve karma asistan GPU ya da `llmaas` ile ölçülür.
6. **Kabul:** kalite PayCore S1 seti (50 soru, kaynak doğruluğu ≥ %80; iç dokümantasyon sorusu, müşteri verisi değil), akış 13a'nın küçük sentetik KB'si ve SQL şeması; S1 sunucuda kullanıcı eliyle koşar.
7. **Veri sınırı:** PRSIM kayıtlarındaki personel adı/e-postası PayCore uzantı verisidir; ingest'e kişi verisi guard'ı 08 geldiğinde eklenir (ertelendi, koşullu). Hasta ve müşteri kişi verisi kuralı değişmez.
8. **Bellek:** sunucu belleği artırılır (kullanıcı kararı); yine de modeller yalnızca API sürecinde yüklenir ve bütçe tablosu ölçülerek tutulur.

## 2c. Dış sistem bağlantı türleri

Üç ayrı mekanizma vardır; karıştırılmaz:

| Tür | Yön | Mekanizma | Paket |
|---|---|---|---|
| Araç (tool) | Agent → sistem (Superset'te chart çek, Jira'da issue aç) | MCP ya da OpenAPI→MCP yayınlama | 05 |
| Kanal (channel) | Kullanıcı → agent (Teams'te yazıp cevap almak) | Kanal adaptörü | 15 |
| Veri kaynağı (data source) | Sistem → bilgi tabanı (Confluence'ı düzenli indekslemek) | Zamanlı artımlı senkron bağlayıcısı | 16 |

Jira gibi bazı sistemler hem araç (canlı sorgu, issue açma) hem veri kaynağı (geçmiş issue'ları indeksleme) olabilir; ikisi ayrı kaydedilir.

## 3. Mimari

```
[Kullanıcı: analist / bilgi işlem / son kullanıcı]
        |  (tarayıcı)
[frontend: React/Next.js, Türkçe]
        |  REST + SSE
[backend: FastAPI]  --- kimlik, proje, kota, agent tanımı, bilgi tabanı, araç kaydı,
        |               onay kuyruğu, guardrail, evaluation, audit
        |-- LangGraph runtime (backend içinde, ayrı worker süreci)
        |-- Postgres + pgvector (uygulama verisi, vektörler, checkpoint, audit)
        |-- Qdrant (isteğe bağlı vektör deposu; VECTOR_BACKEND ile seçilir, mevcut kurulum kullanılabilir)
        |-- Redis (kuyruk, rate limit, kısa ömürlü PII token eşlemesi)
        |
        |-- LiteLLM proxy (iç ağ) --> sağlayıcılar: Anthropic/OpenAI/Azure/Bedrock (llmaas) | Ollama/vLLM (airgap)
        |   (tek halka açık giriş: backend facade /v1/chat/completions; LiteLLM dışa açılmaz)
        |-- Langfuse       <-- LiteLLM callback + LangGraph trace
        |-- MCP servisleri: services/mcp-sql (text-to-SQL), services/mcp-search (belge arama)
```

İlkeler:

- Model pasiftir; indekse ve araçlara yalnızca runtime ulaşır.
- Her LLM çağrısı LiteLLM'den geçer; backend doğrudan sağlayıcıya gitmez.
- Her değişiklik audit tablosuna yazılır; her LLM ve araç çağrısı Langfuse'a düşer.
- Agent tanımı veridir (JSON); LangGraph grafı bu veriden üretilir. Analist JSON görmez, form görür.
- Araçlar standart MCP; backend MCP istemcisidir. Dış araç eklemek kod değil kayıt işidir.

## 4. Depo düzeni (monorepo)

```
/
  PLAN.md
  plan/                      iş paketi briefleri
  backend/                   FastAPI uygulaması + LangGraph runtime
    app/
      api/                   router'lar
      core/                  config, auth, db, audit
      models/                SQLAlchemy
      services/              iş mantığı
      runtime/               agent tanımı -> LangGraph grafı
      guardrails/
      knowledge/             ingest, chunk, embed, search
      evaluation/
    alembic/
    tests/
  frontend/                  Next.js (App Router), Tailwind, Türkçe
  services/
    mcp-sql/                 text-to-SQL MCP sunucusu
    mcp-search/              belge arama MCP sunucusu (backend knowledge API'sini sarar)
  deploy/
    docker-compose.yml
    litellm/config.yaml
    langfuse/
    ollama/                  model listesi, pull scripti
    offline/                 imaj ve wheel paketleme scriptleri
  data/
    samples/contracts/       örnek sözleşmeler
    samples/schema/          örnek Postgres şeması ve seed
  docs/
```

## 5. Ortak kurallar

Bu bölüm kısa kuralları verir; geliştirme felsefesi `FELSEFE.md` ve FFCore'daki karşılığı `handbook/FELSEFE_UYGULAMA.md` her kuralın üstündedir; yürütme, sözleşme, güvenlik, test ve terim kuralları `handbook/` altındadır ve aynı ağırlıkta bağlayıcıdır (giriş `CLAUDE.md`, dizin `handbook/INDEX.md`). Donmuş sözleşmeler `handbook/CONTRACTS.md`, değişiklik sınıfları `handbook/CHANGE_CONTROL.md`.

- **Tek parça brief (P9):** brief'lerde ayrı "referans" bölümü yoktur; konsol incelemesinden türetilen gereksinimler ilgili brief'in Kapsam'ında "(konsol incelemesinden, bağlayıcı)" başlıklı alt bölümlerdedir ve Kapsam'ın geri kalanıyla aynı ağırlıktadır. Bir agent iki cümle arasında çelişki görürse PR'da işaretler, sessizce seçmez.
- **Tek yapılandırma kaynağı (P1):** LiteLLM config'i yalnızca `providers`/`models` tablolarından üretilir; elle yazılan statik config yoktur. Profil farkı seed farkıdır. (R1.4) Üretilen config yalnızca açılış içindir; çalışırken değişiklikler LiteLLM'in DB'li model yönetim API'siyle (`/model/new|update|delete`, `store_model_in_db=true`) uygulanır, yeniden başlatma ve `/config/reload` yok.
- **Ad uzayı (R1.1):** LiteLLM sanal model adı `<project_key>.<model_key>` (örn. `hastane.chat-default`), agent adı `agent:<project_key>/<agent_key>`. Backend facade proje bağlamından kısa adı (`chat-default`) çözer; dış istemci tam adı kullanır. `project_key` global benzersizdir.
- **Tek giriş süreci (R1.2, C14):** dışa açılan tek süreç backend'dir; iki onaylı yüzeyi vardır: facade (`/v1/*`, 06b) ve yayınlanan MCP sunucuları (`/mcp/{key}/`, 05b). İkisi de aynı `resolve_actor`, kota, guardrail ve audit'ten geçer. LiteLLM ve Langfuse iç ağda kalır; LiteLLM içinde guardrail kancası ya da proje başına team/anahtar yoktur (A4, B3): backend LiteLLM'i tek iç anahtarla çağırır. `agent:` yönlendirmesi facade'dadır.
- **PayCore LLM deposu (R3.1, 2d):** `C:\ai_paycore\paycoreLLM` (git: PayCore DWH) artık yalnızca referans değil, canlı test yeri ve FFCore'un tüketicisidir. Agent'lar kodu ve belgeleri okur; okuma yasağı dosya düzeyindedir: `.env`, `data/**`, `eval/results/**` okunmaz ve kopyalanmaz; `eval/scenario*/questions.jsonl` (S1) ve `experts/*.yaml` okunabilir ama FFCore deposuna kopyalanmaz. PayCore kodu FFCore'a birebir kopyalanmaz: ya uzantıda kalır ya `ffcore.*` entry point'inden FFCore'a terfi eder (C14). Sunucuya ajan bağlanmaz.
- **Migration (R2.6):** aynı dalgada çalışan paketler kendi Alembic branch label'ı ile (`03a`, `03b`, `08`) yazar; dalga sonunda tek `alembic merge` PR'ı; CI `alembic heads` tek head bekler.
- **Kuyruk altyapısı (R10.8, C8):** tek kütüphane `arq` (zamanlı işler de `arq cron_jobs`; APScheduler yok); 04 worker, 06 scheduler ve 16 senkron aynı Redis'te ayrı kuyruk adlarıyla (`ingest`, `llm-interactive`, `llm-background`, `sync`). Run = arq işi; tekil model çağrıları `LLM_SLOTS` öncelikli eşzamanlılık yuvasından geçer (06). `BACKGROUND_WINDOW` profil seed değeridir: yalnızca `airgap` cpu'da dolu (A8).

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest. Ruff ile lint ve format.
- Node 20, Next.js 15, TypeScript, Tailwind, shadcn/ui. Türkçe metinler `frontend/messages/tr.json` içinde; kodda sabit Türkçe metin yok.
- Tüm web ekranları açık (light) ve koyu (dark) temada geliştirilir. Renkler yalnızca CSS değişkenleri (design token) üzerinden; bileşenlerde sabit renk yok. Varsayılan sistem tercihi (`prefers-color-scheme`), kullanıcı üstten değiştirir, seçim kalıcıdır. Her ekran ve grafik iki temada da test edilir (Playwright ekran görüntüsü karşılaştırması).
- Proje sahipli kök tablolar: `id` (uuid), `project_id`, `created_at`, `updated_at`, `created_by`, `deleted_at` (silme yerine). İstisnalar adlandırılmış listededir (handbook/CONTRACTS.md C3): global (`users`), çocuk (`chunks`, `attachments`, `tool_actions`, `agent_versions`, `messages`, `few_shots`: projeyi FK zinciriyle alır) ve append-only olay tabloları (`run_events`, `audit_events`, `guardrail_events`, `usage_daily`, `kb_queries`, `mcp_server_calls`, `checkpoints`). Her tabloya körlemesine `project_id` eklenmez (B5).
- Her mutasyon endpoint'i audit olayı üretir (`core/audit.py` decorator'ı).
- Secret'lar yalnızca `.env` ve Postgres'te şifreli (Fernet, anahtar `.env`'de). Loga, API cevabına, audit'e yazılmaz.
- Her paket kendi testiyle gelir; `docker compose up` sonrası `make smoke` yeşil olmalı.
- Commit: Conventional Commits, İngilizce. PR açıklamasında hangi iş paketi olduğu yazılır.
- Dış ağ gerektiren her şey `OFFLINE=true` iken devre dışı ya da iç aynaya yönlenmiş olmalı; `llmaas`'ta yalnızca izin listesindeki adreslere çıkış.
- Profil farkı olan davranışlar `DEPLOY_PROFILE` ile seçilir; kodda `if profile == ...` dalları yerine yapılandırma değerleri (timeout, fiyat, eşik, sağlayıcı listesi) kullanılır. İki profil için de testler koşar.

## 6. Veri modeli (özet)

Ana tablolar; alan ayrıntıları ilgili pakette:

03a: `users, roles, projects, project_members, providers, provider_projects, model_catalog, models`. 03b: `audit_events` (+ on-behalf-of, `SERVICE_TOKEN`, `core/egress.py`). 03c (PoC sonrası): `api_keys (allowed_cidrs, scopes, acl_role), quotas (kapsam, pencere, bütçe), usage_daily, audit_events, retention_policies, alert_rules, alerts, notification_settings`. 04: `knowledge_bases, documents, attachments, chunks, kb_queries, ingest_gate_stats (görünüm)`. 05: `tools, tool_actions, mcp_servers, mcp_server_calls, schema_descriptions, few_shots`. 06: `agents, agent_versions, runs, run_events, conversations, messages`. 07: `approvals`. 08: `pii_policies, guardrail_policies, guardrail_events`. 09: `datasets, dataset_items, eval_suites, eval_runs, eval_scores`. 14: `memories, memory_settings`. 15: `channels, channel_bindings, channel_identities, channel_threads`. 16: `data_sources, source_items, sync_runs, sync_state, acl_mappings`.

Tablo sahipliği yukarıdaki listedir; bir paket başka paketin tablosuna kolon eklerse kendi migration'ında yapar ve brief'inde yazar (örn. 11 `agents.portal_config`; `runs.channel` enum'u baştan 06a'da tanımlıdır, 15 eklemez, N8; eski örnek: 15 `runs.channel` enum değerleri). Alan ayrıntıları her brief'in Veri modeli ve Kapsam bölümlerindedir.

## 7. İş paketleri ve bağımlılıklar

| # | Paket | Bağımlı olduğu | Tahmini süre (1 agent) | PoC |
|---|---|---|---|---|
| 00 | FFCore depo iskeleti ve altyapı compose (bağımsız kurulum ve TH için) | — | 1,5 gün | evet |
| 00i | PayCore entegrasyon tabanı ve sıkılaştırma: path bağımlılığı, anayasa, compose birleştirme, kimlik sınırı, secret/port, eşzamanlılık düzeltmesi, bellek tablosu, S1 taban ölçümü | 00 | 4 gün | evet; 03a/01/04a bunu bekler |
| 01 | LiteLLM gateway (uzlaştırıcı: modeller yalnızca LiteLLM DB'sinde, config'de `model_list` yok; sanal model ad uzayı; tipli fallback tespiti; team/sanal anahtar yok) | 00, 03a | 2,5 gün | evet |
| 02 | Langfuse izleme (init, tracing, prompt istemcisi; iz alanları 06a'da) | 00, 01 | 1 gün | evet |
| 03 | Backend çekirdek: **03a** kimlik + sağlayıcı/model kataloğu (3); **03b** audit, on-behalf-of, iç servis token'ı, `core/egress.py` (2); **03c** API key, kota, usage, retention, uyarılar, bildirim ayarı (3,5, PoC sonrası) | 00 | 8,5 gün | 03a, 03b |
| 04 | Bilgi tabanı. **04a** çekirdek: PayCore ingest/RAG'i saran `KnowledgeStore` bağdaştırıcısı, elle yükleme yolu, süreç içi dense+sparse embedding, `VectorStore` (Qdrant sparse birincil, pgvector), hibrit arama, reranker, ACL payload, `kb_queries.candidates`, warmup, yönetim/arama API'si (5,5). **04b**: `migrate-vectors`, reconvert, video, TR normalizer, rewrite, eşik tablosu, ingest raporu, DuckDB → Postgres göçü (4) | 04a: 00i, 03a, 01, 13a; 04b: 04a | 9,5 gün | 04a |
| 05 | Araç katmanı. **05a** çekirdek: araç kaydı, upstream kimlik, mcp-sql, mcp-search (4). **05b**: OpenAPI→MCP yayınlama, Superset (3) | 05a: 03a, 03b, 04a, 08; 05b: 05a | 7 gün | 05a |
| 06 | Agent runtime. **06a** çekirdek: tanım -> LangGraph, run API, SSE, bağlam bütçesi, kuyruk ve `LLM_SLOTS`, iz alanları, guardrail bağlama, `knowledge[].filter` (PayCore profilleri = agent) (6,5). **06b**: OpenAI-uyumlu facade, dış agent, manifest (3) | 06a: 03a, 03b, 01, 02, 04a, 05a, 08; 06b: 06a, 03c | 9,5 gün | 06a (iki agent: `always` + tek çağrılı SQL) |
| 07 | Onay kuyruğu | 06a, 03b | 1,5 gün | evet |
| 08 | Guardrail ve PII (Türkçe). **08-lite (PoC, 3):** engine, 7 aşama, regex PII, `secrets`, `tool_args`, Monitor/Enforce, test paneli, `/internal/guardrails/evaluate`. **08 tam (M4, 2,5):** Türkçe NER, injection sınıflandırıcısı, akış tamponlayıcı, `egress` kalibrasyonu, PRSIM ingest guard'ı | 03a (merge sonrası), 03b | 5,5 gün | 08-lite |
| 09 | Evaluation: Langfuse datasets/experiments üstünde suite, run, scorer, aşama bazlı teşhis | 06a, 02, 04a, 13a | 3,5 gün | hayır |
| 10 | Yönetim önyüzü (Türkçe): **10a** giriş, proje, tema, sağlayıcı/model (3); **10b-poc** KB, araç, agent sihirbazı, run/onay, sistem durumu (6); **10c** dashboard'lar, MCP, anahtar/limit/uyarı/retention, salt-okunur ekran tarafı (5) | 10a: 03a; 10b: 04a-07; 10c: 03c, 05b, 09 | 14 gün | 10a, 10b |
| 11 | Son kullanıcı chat arayüzü (PoC'de Open WebUI kullanılır, karar 7) | 06a, 07 | 3 gün | hayır |
| 12 | Kurulum rehberi (llmaas ana, airgap ek), paketleme, egress proxy, donanım rehberi, vLLM yolu | hepsi | 4 gün | hayır |
| 13 | **13a** küçük sentetik KB (ACL testleri), demo SQL şeması, iki agent şablonu, PII/hafıza test setleri (1, dalga 1); **13b** `make seed/e2e`, PayCore S1 seti ile `make eval` ve M3 ölçümleri, yalnızca `cpu` sütunu (2) | 13a: —; 13b: PoC paketleri, 00i S1 tabanı | 3 gün | evet |
| 14 | Kullanıcıya özel kalıcı hafıza (her iki profil) | 03, 04a, 06a, 08, 11, 13a | 3,5 gün | hayır |
| 15 | Kanallar: web widget, Mattermost; Slack ve Teams 17'den sonra | 06a, 07, 11, 03b; Slack/Teams: 17 | 7 gün | hayır |
| 16 | Veri kaynağı bağlayıcıları: Confluence, Jira, SharePoint, ağ klasörü; üç katmanlı senkron, güvenli silme. PayCore'un Confluence/Jira Data Center bağlayıcıları Server/DC yarısını zaten karşılar (uzantıdan FFCore'a terfi), süre düşer | 03, 04a, 05a | 8 gün | hayır |
| 17 | Son kullanıcı açılışı ve AD/LDAP girişi (`user` rolü aktivasyonu, toplu kullanıcı, LDAP/Keycloak, kanal ve widget kimlik eşlemesi) | 03, 11 | 3 gün (brief M6 sonrası yazılır) | hayır |

Toplam: yaklaşık 101 agent-günü (tek agent serisi). **PoC (M1-M3, PayCore'da) toplamı ≈ 49 agent-günü:** 00 (1,5), 00i (4), 01 (2,5), 02 (1), 03a (3), 03b (2), 04a (5,5), 05a (4), 06a (6,5), 07 (1,5), 08-lite (3), 10a (3), 10b-poc (6), 13a (1), 13b (2); 11 PoC dışı (Open WebUI). PoC kritik yolu 00 → 00i → 03a → 01 → 04a → 05a → 06a → 07 → 13b ≈ 31 iş günü; sunucuda kullanıcı eliyle yapılan ölçümler hariç, üç işçi ve kapılarla ~32-36 iş günü.

Paralel çalışabilecek gruplar (kapı kuralı E: bir paket **kendi doğrudan bağımlılıkları MERGED olunca** READY olur; dalga yalnızca Alembic merge ve tutarlılık denetimi noktasıdır, tüm dalganın bitmesi beklenmez):

- Dalga 1: 00; 00i (PayCore sıkılaştırma, 00'dan hemen sonra); 13a (test agent'ı, paralel)
- Dalga 2: 00i MERGED sonrası 03a, 03b (paralel); 03a merge olunca 08-lite ve 10a başlar (her biri kendi Alembic branch'inde; 08 `pii_policies` ve `guardrail_*` tablolarına dokunur)
- Dalga 3: 01, 02, 04a (01 03a'yı bekler; 02 01'in hemen ardından). Dalga sonunda Alembic merge PR'ı.
- Dalga 4: 05a, sonra 06a (kritik yol; 06a 02 ve 08'i de bekler)
- Dalga 5: 07, 10b-poc; 13b = **M3 / PoC kapısı** (Open WebUI ile demo)
- PoC sonrası dalga 6: 03c, 06b, 11, 04b (DuckDB → Postgres göçü dahil), 05b, 08 tam, 09, 10c
- Dalga 7: 12, 14, 17
- Dalga 8: 16; 15 (widget ve Mattermost; Slack/Teams 17 sonrası)

Aynı dosyalara dokunan paketler aynı anda çalışmamalı: 03, 08 ve 06a `backend/app/models` üzerinde (03 ve 08 ayrı dosyalara yazar; 08 migration FK için 03a merge'ünü bekler; 06a ikisi bitmeden başlamaz); 06a bitmeden 07 ve 09 başlamaz; 04b 04a ile, 05b 05a ile, 06b 06a ile aynı dosyalara dokunur, bu yüzden her b parçası kendi a parçası birleştikten sonra başlar. 06'daki guardrail kancaları 08'in hook adlarını (`input.pre, output.pre, tool.pre, tool.post`) kullanır; 08 önce biter.

Dalga değişikliğinin M1'e etkisi: altyapı kilometre taşı 00 + 03a + 01 + 02 ile tamamlanır; 03b M2'de.

## 8. Kilometre taşları

1. **M1, altyapı ayakta** (00, 03a, 01, 02): `docker compose up` ile Postgres, Redis, LiteLLM, Langfuse (ve airgap'te Ollama) çalışır; `models` tablosundan üretilen config ile `curl` ile sanal model (`<proje>.chat-default`) cevap verir ve Langfuse'ta görünür. `llmaas` profilinde sahte sağlayıcı (mock) ile CI'da, gerçek sağlayıcıyla elle.
2. **M2, bilgi tabanı** (03a, 03b, 04a, 08, 10a): önyüzden giriş, proje, belge yükleme, arama sonucu görme.
3. **M3, ilk agent = PoC kapısı (PayCore sunucusunda, `airgap`)** (05a, 06a, 07, 10b-poc, 13b): konsoldan PayCore doküman asistanı (`mode: always`, PayCore korpusu) ve tek araç çağrılı SQL asistanı (sentetik DB) kurulur, Open WebUI'den kaynaklı cevap alınır, SQL aracı onay bekler; `make e2e` (sentetik KB) ve `make eval` (PayCore S1, ≥ %80, 00i tabanıyla karşılaştırma) koşar, yalnızca `cpu` sütunu. Qwen/CPU ve model kararı burada verilir. 03c, 04b, 05b, 06b, 09, 10c M3'ten sonra (facade ve API anahtarı M4'te).
4. **M4, güvenli ve ölçülebilir** (03c, 06b, 09, 10c; 08 PII tam kalibrasyon): PII maskeleme açık (Türkçe NER dahil), 35 soruluk sınav koşuyor, Draft/Published sınav eşiğine bağlı.
5. **M5, sunucuda** (12, 13): `llmaas` kurulumu: egress izin listesi, sağlayıcı anahtarı DB'de, `docs/veri-isleme.md` dolu, demo veriyle uçtan uca test. **M5b (pilot ve airgap müşterisi):** aynı paketlerle kapalı ağ kurulumu ve `cpu`/`gpu` ölçümleri; M5'in ikinci kabul satırı.
6. **M6, kişiselleşen asistan** (14): kalıcı kullanıcılar (yöneticiler, bölüm sorumluları) için hafıza açık; kullanıcı "Hafızam" sayfasından yönetir; hasta verisi hafızaya girmediği test setiyle kanıtlanmış.
7. **M7, bağlı kurum** (16, 15, 17): sıra: SharePoint ve Confluence Cloud (16), web widget ve Mattermost (15); **17 (AD/LDAP) sonra**; Slack ve Teams ancak 17'den sonra (A9: kurum kullanıcıları dizin olmadan eşlenemez). Sonra Confluence/Jira Server ve ağ klasörü. Asistan kanallardan kullanılıyor; veri kaynakları bilgi tabanını zamanlı ve artımlı besliyor; kaynak yetkileri indekse taşınmış.

## 9. Kapsam dışı (ilk sürüm)

Görsel akış tasarımcısı (Flow canvas), alt agent (sub-agent) devri, zamanlanmış görevler, webhook tetikleyici, sandbox'ta kod çalıştırma, ses, AD/LDAP ve son kullanıcı açılışı (17, M6 sonrası), çok kiracılı (tenant) yapı, Kubernetes, ekip ve kurum düzeyi hafıza (14'te yalnızca kullanıcı hafızası), WhatsApp/Telegram/e-posta kanalları (15'te widget, Slack, Teams, Mattermost), Google Drive/Notion/e-posta kutusu bağlayıcıları (16'da Confluence, Jira, SharePoint, ağ klasörü). Veri modeli bunları engellemeyecek şekilde kurulur (örn. `agents.kind`, `runs.trigger_type`, `memories.scope` alanları).

## 10. Agent'a brief verirken

Şu üçünü birlikte verin: `PLAN.md`, ilgili `plan/NN-*.md`, bağımlı olduğu paketlerin "Teslimatlar" bölümü. PayCore düzeltmesi içeren paketlerde (04, 09, 12, 16) bölüm 5'teki referans deposu kuralı geçerlidir. Agent'tan beklenen: brief'teki kabul kriterlerini test ile kanıtlamak, dokunduğu dosyaları PR açıklamasında listelemek, kapsam dışına çıkmamak, belirsizlikte varsayımını PR'da yazmak.

## 11. Sürüm geçmişi

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1 | 24 Ekim 2026 | İlk plan: 14 paket, airgap (Ollama CPU) varsayılan, Cognipeer benzeri 8 çekirdek özellik |
| 1.x | 24-26 Ekim | Dağıtım profilleri (2b), hafıza (14), kanallar (15), veri kaynakları (16), PayCore düzeltmeleri D1-D8, K1-K3, P1-P9 işlendi |
| 2 | 26 Ekim 2026 | **Tersine karar:** ürün varsayılanı `llmaas`, Türkiye Hastanesi pilotu `llmaas`; `airgap` ikincil. Reviewer R maddeleri; 03 → 03a/03b; "Agent runtime referansı" bölümleri Kapsam'a eritildi; 04/05/06 → a/b; toplam 71 agent-günü, kritik yol ~20 gün |
| 2.1 | 27 Ekim 2026 | Ürün adı FFCore ve modüller (1b); handbook/ ve state/ eklendi; PayCore'un müşteri olduğu netleşti |
| 2.4 | 27 Ekim 2026 | İnceleme v9/v10 ve yedi kullanıcı kararı (`state/reviews/cevap-v9-v10.md`): canlı test yeri PayCore LLM (`airgap`), bölüm 2d; 00i paketi; FFCore ayrı depo + paycoreLLM tüketici, uzantı noktaları C14; Qdrant sparse PayCore'da birincil, embedding süreç içi (C10 tersine); DuckDB sarılır; Langfuse v3 kalır; 08-lite; 11 PoC dışı (Open WebUI); iki agent; S1 kabul; PoC ≈ 49 agent-günü |
| 2.3 | 27 Ekim 2026 | İnceleme v4-v6 uygulandı (`state/reviews/cevap-v4-v6.md`): PoC kapsamı A1-A9 (03c ayrıldı, roller daraltıldı, LiteLLM team kaldırıldı, 09 Langfuse datasets, 10 ve 13 bölündü, `BACKGROUND_WINDOW` profil değeri, 17 Slack/Teams'ten önce); 7 blocker, 24 major, minörler; süreler ~101 agent-günü, PoC ≈51, kritik yol ~31 gün; kapı kuralı bağımlılık bazlı |
| 2.2 | 27 Ekim 2026 | `FELSEFE.md` bağlandı: örtük Ollama→Anthropic fallback kaldırıldı (01), `run_events.fallback` olayı (06, C9), Postman içe aktarma reddedildi (05), KARARLAR üç durumlu ve "Reddedilenler" bölümü, dalga kapanışında tutarlılık denetimi |
