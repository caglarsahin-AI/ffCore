# Brief İncelemesi v9: PoC kritik listesi, paycoreLLM entegrasyonuyla

İnceleyen: bağımsız gözden geçirici oturumu · Tarih: 2026-10-27

Derece: **BLOCKER** bu haliyle kodlanamaz · **MAJOR** kodlanır ama yanlış ürün çıkar · **MINOR** netleştirme.

## Sürüm notu

| Sürüm | Değişiklik |
|---|---|
| v3 | Tam inceleme (6 BLOCKER, 22 MAJOR, 46 MINOR) |
| v5.1 | PoC (M3) kapsamına daraltıldı |
| **v9** | **Kullanıcı kararı (2026-10-27):** FFCore paycoreLLM ile entegre olacak ve uygulama dizini `C:\ai_paycore\paycoreLLM` olacak. Liste bu karara ve paycoreLLM'in gerçek koduna göre yeniden kuruldu. v3 ve v5'ten kalan bulgular eski numaralarını koruyor (B, M, N). Entegrasyondan doğan bulgular **P** önekli. Bölüm 10, v5'e göre neyin değiştiğini listeliyor. |

## Kaynaklar ve okuma sınırı

- **FFCore tarafı:** v3/v5'te okunan belgeler. İçerikleri değişmedi (v5 sürüm notu).
- **paycoreLLM'de okunanlar** (yalnızca kod ve belge; veri yok):
  - `CLAUDE.md` (tamamı)
  - `compose.yml`, `compose.server.yml`, `compose.dev.yml`, `pyproject.toml`, `Makefile`, `.gitignore`, `docker/postgres/init.sql`
  - `src/paycore_llm/`: `api.py`, `llm.py`, `rag/embed.py`, `rag/retrieve.py`, `rag/pipeline.py` tam; diğer modüllerde sembol ve grep taraması
  - `docs/agentic/referans/README.md` ve `deployment_plan.md`; `devops_handover.md` §1, §7, §8
  - `docs/agentic/02_agentic_development.md` §1-3, §5-7
  - `docs/handover/hastane-platformu-duzeltmeler.md` (taslak, agent notları, kontrol 3 cevabı)
- **Okuma sınırını aştığım yer:** FFCore CLAUDE.md ve PLAN:164 yalnızca `src/`, `CLAUDE.md`, `docs/agentic/referans/` ve `compose.yml` okumasına izin veriyor. Kök yapılandırma dosyalarını ve `docs/agentic`, `docs/handover` belgelerini de okudum, çünkü entegrasyon incelemesi bunlar olmadan yapılamıyor. Hiçbiri kurum verisi içermiyor.
- **Açılmayanlar:** `.env` (gerçek değerler içeriyor), `eval/`, `data/`, `experts/`, `tests/` içerikleri, `docs/agentic/tarihce.md`, `01_fonksiyonel_dokuman.md`, `waves/`, `scripts/`. Bu dizinlerin yalnızca adlarını ve git'te izlenen dosya sayılarını gördüm.

## PoC tanımı (varsayımım)

**PoC = M3 "ilk agent"** (PLAN:229). Değişen şey yeri:
- **Depo:** paycoreLLM.
- **Sunucu:** PayCore'un test sunucusu (VMware, 32 vCPU, 64 GB, GPU yok, internet yok).
- **Profil:** `airgap`, Qwen3.5-35B-A3B, Ollama CPU.
- **Korpus:** PayCore'un mevcut Confluence/Jira korpusu (8 space + PRSIM).
- **Kabul:** PayCore'un S1 seti. SQL demosu için sentetik bir sunum DB'si.

Bir bulguyu şu üç durumdan en az birinde listede tutuyorum:
1. Bir PoC paketini kodlanamaz ya da doğrulanamaz bırakıyorsa.
2. PoC'de yanlış ya da güvensiz sonuç üretiyorsa.
3. M3'e kadar donan bir sözleşmeyi etkiliyorsa.

**PoC hedefi Türkiye Hastanesi (`llmaas`) ise** bu liste geçersiz. O durumda v5.1 geçerlidir, artı P1, P2, P4 ve P8.

---

## 0. Özet

1. **Kodlamaya başlanabilir mi? Hayır, 00 dahil hiçbir paket.** Entegrasyon kararı 00'ın ne olduğunu değiştiriyor: boş bir monorepo değil, 10 bin satırlık çalışan bir depo var. Kodlamadan önce dört kararın verilmesi gerekiyor:
   - hangi anayasa geçerli (P1),
   - dizin yerleşimi (P2),
   - bileşen başına "PayCore'unki mi, FFCore'unki mi" (P3),
   - bellek bütçesi (P4).
   Dördü de belge işi, toplam 1-2 günlük bir "00i entegrasyon kararları" paketi.
2. **En önemli bulgu (P1): iki anayasa birbiriyle çelişiyor.** paycoreLLM'in kuralları FFCore'un PoC'sini yasaklıyor:
   - "Dal açılmaz; commit doğrudan `master`'a",
   - "Faz 2 (text-to-SQL) için kod yazılmaz",
   - "Hiçbir veri dış servise gönderilmez",
   - "Teknoloji seçimleri sorulmadan değişmez",
   - "Bellek bütçesini aşan bileşen eklenmez".
   Kodu yazan işçi iki kural setini aynı anda sağlayamaz.
3. **İkinci bulgu (P4): bellek.** PayCore sunucusunun konteyner sınırları bugün bile 64 GB'ı aşıyor: 58 GB konteyner + ~8 GB işletim sistemi. FFCore buna LiteLLM, Redis, Next.js, mcp-sql, mcp-search, Presidio + Türkçe NER ekliyor; Langfuse v3 (ClickHouse + MinIO) yalnız başına +4-6 GB. PoC bu haliyle sunucuya sığmaz.
4. **Üçüncü bulgu (P3): FFCore'un bilgi tabanı tasarımı, PayCore'un ölçülmüş yığınıyla çelişiyor.**
   - **Hibrit arama:** PayCore'da Qdrant'ta bge-m3 sparse ağırlıklarıyla yapılıyor. FFCore'da Postgres'te BM25 ile.
   - **Embedding:** PayCore'da süreç içinde dense + sparse üretiliyor. FFCore'da LiteLLM'den geçiyor.
   - **Doküman deposu:** PayCore'da DuckDB, FFCore'da Postgres.
   - **Kuyruk:** PayCore'da Postgres tablosu, FFCore'da arq + Redis.
   - **Langfuse:** PayCore'da v2, FFCore'da v3.

   Bu yüzden v5'teki M10 önerimi ("embedding Ollama üzerinden") geri alıyorum: Ollama sparse ağırlık üretmez (U14) ve PayCore'un hibrit araması bozulur.
5. **İyi haber: süre kısalıyor.** 04a'nın ingest, kapılar, dönüşüm, breadcrumb, rerank tabanı ve güncellik kısmı ile 09'un teşhis mantığı paycoreLLM'de çalışır durumda. PoC ~60 agent-gününden **~50'ye**, kritik yol ~35 iş gününden **~30'a** iner. İki iş ise kritik yolda yeniden kazandırılmış süreyi geri alır: 00i ve sunucuda kullanıcı eliyle yapılacak doğrulama (P5).

**Önceki tavsiyemi geri alıyorum.** Bir önceki mesajda "`airgap` tam desteği ve CPU ayarlaması ilk kapalı ağ müşterisine ertelensin" demiş ve "PayCore kapalı ağ müşterisiyse bu öneri geçersiz" diye eklemiştim. PayCore öyle bir müşteri: paycoreLLM/CLAUDE.md:13 "Dış API'ye veri çıkmaz", devops_handover §1 "İnternet çıkışı yok". PoC için `airgap` birincil profil.

---

## 1. BLOCKER bulgular

### P1. İki anayasa: paycoreLLM kuralları FFCore PoC'sini yasaklıyor (yeni)
- **paycoreLLM:**
  - `docs/agentic/02_agentic_development.md` §5: "Dal açılmaz; commit doğrudan `master`'a." · "Faz 2 (text-to-SQL) için kod yazılmaz, bağımlılık eklenmez (W17 kilitli)." · "Hiçbir veri dış servise gönderilmez; dış API çağıran bağımlılık eklenmez." · "Teknoloji seçimleri sorulmadan değişmez (NFR-TEC-01). Bellek bütçesini aşan bileşen eklenmez." · "Sunucuya ajan bağlanmaz; komutları kullanıcı çalıştırır."
  - paycoreLLM/CLAUDE.md:52 "Faz 2 ve 3 için kod, bu bölümdeki karar adımları onaylanmadan yazılmaz." · CLAUDE.md:43-47 "İlk iş akış çatısı kararıdır: … LangGraph / PydanticAI / düz kod kıyaslanır."
- **FFCore:** MULTI_AGENT:45 "Branch: `feat/<paket>-<kısa-slug>`" · 05a mcp-sql (text-to-SQL) · 06a "LangGraph 0.4+" (06:132) · SECURITY:17 "Geliştirmede Anthropic API'ye yalnızca sentetik veri gider" · LiteLLM, Redis ve Langfuse v3 ekleniyor.
- **Öneri:**
  1. Depo kökünde tek bir CLAUDE.md olur: FFCore'unki. paycoreLLM'in CLAUDE.md'si `docs/paycore/` altına PayCore eklentisinin (Jira, PRSIM, router) kuralları olarak taşınır.
  2. PayCore'un **daha sıkı** kuralları FFCore'a aynen geçer: Jira çıktı kapısı (`JIRA_SUGGESTIONS_ENABLED=false`), `.env`'e dokunmama, sunucuya ajan bağlanmaması, dış servise veri göndermeme. Sonuncusu PoC profili `airgap` olduğu için kendiliğinden sağlanıyor.
  3. Gevşetilecek dört kural `DECISION-` kaydıyla sizden onay alır: dal ve PR akışı, W17 kilidinin FFCore'un sentetik SQL demosu için açılması, akış çatısının LangGraph olması (PayCore'un açık çatı kararı FFCore'un kararıyla kapanır), teknoloji tablosunun P3'e göre güncellenmesi.
- **Gerekçe:** CHANGE_CONTROL:25'e göre "brief ile PLAN çelişirse PLAN kazanır", ama iki ayrı deponun anayasası için böyle bir kural yok. Bunu karar vermeden işçiye bırakmak, ilk PR'da durması demek.

### P2. Depo yerleşimi: brief'lerin hiçbir yolu paycoreLLM'de yok (yeni)
- **FFCore:** PLAN 4 (satır 122-154) `backend/app/{api,core,models,services,runtime,guardrails,knowledge,evaluation}`, `frontend/`, `services/mcp-*`, `deploy/docker-compose.yml`, `data/samples/`. Bütün touch-zone'lar (MULTI_AGENT:22-39) ve CODE_MAP bu yollara bağlı.
- **paycoreLLM:** `src/paycore_llm/{ingest,rag,router,jira,prsim,eval}`, kökte `compose*.yml`, `docker/postgres/init.sql`, `data/` (gerçek veri, git'te izlenen 11 dosya; `.gitignore` `data/knowledge/` gibi alt dizinleri dışlıyor), `eval/`, `experts/`.
- **Çakışmalar:**
  - FFCore `data/samples/` paycoreLLM'in gerçek veri dizininin içine düşer.
  - 16'nın `knowledge/` touch-zone'u PayCore'un `ingest/` koduyla aynı işi yapıyor.
  - İki compose dosyası olur.
- **Öneri:**
  - Python paketi `src/ffcore/` (FFCore backend; mevcut `paycore_llm`'i kütüphane olarak içe aktarır). `frontend/` ve `services/mcp-*` kökte.
  - Tek `compose.yml` (PayCore'unki genişletilir; `profiles` korunur).
  - FFCore'un örnek verisi `samples/` altında; `data/` altında asla değil.
  - PayCore'a özgü modüller (`jira/`, `prsim/`, `router/`) "PayCore eklentisi" olarak `src/paycore_llm/` altında kalır. Handover:13-14 de bunu söylüyor: "PayCore'un Senaryo 2'si … bu ürüne taşınmaz; PayCore'un kendi eklentisi olarak kalır."
  - Bütün brief'lerdeki yollar, MULTI_AGENT touch-zone tablosu ve CODE_MAP aynı PR'da güncellenir.
- **Gerekçe:** Touch-zone'u olmayan bir claim yazılamaz (EXECUTION_HANDBOOK:10).

### P3. Bileşen kararları: PayCore'un ölçülmüş yığını ile FFCore'un planı (yeni)

| Konu | paycoreLLM (kod/karar) | FFCore brief | Önerim (PoC) | Gerekçe |
|---|---|---|---|---|
| Vektör deposu ve hibrit arama | Qdrant v1.11.3; dense + **bge-m3 sparse** (`lexical_weights`), RRF Qdrant'ta (`rag/retrieve.py` `_fused`; CLAUDE.md:173 "BM25 değil") | pgvector varsayılan; BM25 Postgres tsvector'den, RRF uygulamada (04:64, KARARLAR:30) | **Qdrant birincil sürücü.** C5 `search()` imzası sparse sorguyu taşıyacak biçimde M3'ten önce genişletilir. pgvector ve BM25 PoC'den sonraya | Canlı korpus (~30 bin sayfa) ve iki aylık ölçüm bu yığında. C5 M3'te donuyor |
| Embedding | Süreç içi `BGEM3FlagModel`, dense + sparse (`rag/embed.py:47-52`) | LiteLLM `embed-default` (04:44, 01:14) | **Süreç içi**, LiteLLM dışında. Embedding izi Langfuse'a `tracing.py` ile gider | Ollama sparse vermez (U14). v5 M10 geri alındı |
| Doküman deposu | DuckDB (`ingest/store.py`, tek yazıcı) + silver dosyaları | Postgres `documents`, `chunks`, `attachments` (04:16-21) | **PoC'de DuckDB + Qdrant kalır.** FFCore `knowledge_bases` ve ACL/proje meta verisi Postgres'te. 04a, PayCore deposunu saran bir `KnowledgeStore` bağdaştırıcısı yazar. Postgres'e taşıma PoC sonrası ayrı paket | `store.py` (950 satır) + `sync.py` (1.619 satır) yeniden yazımı PoC'ye ~5 gün ekler ve ölçülmüş davranışı riske atar (ARCH-09) |
| Kuyruk | Postgres tablosu + worker; "Redis/Celery yok" (CLAUDE.md:179) | `arq` + Redis (PLAN:166) | **arq + Redis.** PayCore'un Jira kuyruğu (`jira/queue.py`, 93 satır) aynı PR'da arq'a taşınır | Redis SSE pub/sub, PII token eşlemesi ve hız sınırı için zaten gerekiyor. İki kuyruk sistemi KARARLAR:53 ile reddedildi |
| Langfuse | v2 (`langfuse:2`, yalnızca Postgres, 2 GB); gönderen kod yok (CLAUDE.md:40) | v3 + ClickHouse + MinIO (00:36, 02:41) | **v2 kalır.** v3 geçişi GPU veya ek bellekle | Bellek (P4). DECISION-4 (v3 datasets) bu yüzden PoC'de konu dışı |
| LLM istemcisi | `llm.py` OpenAI istemcisi → host'taki Ollama | Her çağrı LiteLLM'den (PLAN:117) | **LiteLLM eklenir.** `llm.py` LiteLLM'i gösterir; `reasoning_effort: none` ve boş cevap hatası (`llm.py:62-71`) korunur | Tek kapı ve maliyet izi FFCore'un çekirdeği |
| OCR | PaddleOCR `tr` (CLAUDE.md:384, karar 2026-09-21) | Tesseract `tur+eng` (04:40) | **PaddleOCR.** 04:40 düzeltilir | Kullanıcı kararı ve korpus bununla dönüştürülmüş |
| Akış çatısı | Karar açık: LangGraph / PydanticAI / düz kod kıyası (CLAUDE.md:43-47) | LangGraph (06:132) | LangGraph; P1'deki `DECISION-` ile | `interrupt()` onay kuyruğunu bedavaya veriyor (FELSEFE_UYGULAMA:23) |
| Güven formülü varsayılanı | `max` (CLAUDE.md:136, 40 soruluk eval) | `cited` (06:88) | **PayCore seed'inde `max`** | Ölçülmüş kullanıcı kararı. Seed farkıdır, kod dalı değil |

- **Gerekçe:** C5, C6, C8 ve C10 M3'te donuyor. Tablodaki satırlar karara bağlanmadan 04a ve 06a kodlanamaz.

### P4. Bellek bütçesi: PoC sunucuya sığmıyor (yeni)
- **Bugün:** `compose.yml` sınırları: ollama 40 + api 8 + worker 3 + qdrant 2 + postgres 1 + langfuse 2 + open-webui 2 = **58 GB**, artı işletim sistemi ~8 GB (CLAUDE.md:561) = **66 GB > 64 GB**. `ingest` (40 GB) yalnızca modeller boşaltılınca çalışıyor (devops_handover §7).
- **FFCore'un ekledikleri:** LiteLLM ~1, Redis ~0,5, Next.js ~1, mcp-sql + mcp-search ~0,6, Presidio + Türkçe NER ~1-1,5. Runtime worker bge-m3 ve reranker'ı ayrıca yüklerse +3. Langfuse v3 +4-6. Toplam **+7-13 GB**. Bu rakamlar tahminimdir, ölçülmedi (U15).
- **Öneri:** 00i'nin teslimatı ölçülmüş bir bütçe tablosu olur ve aşağıdaki beş kural uygulanır:
  1. Langfuse v2 kalır (P3).
  2. bge-m3 ve reranker'ı **yalnızca API süreci** yükler. FFCore runtime worker'ı ve PayCore Jira worker'ı aramayı 04'ün arama API'si üzerinden yapar (06:81 zaten "retrieve … 04 arama API'si" diyor). Worker 3 GB'tan ~0,5 GB'a iner.
  3. 11 (chat) birleşince Open WebUI kaldırılır (−2 GB).
  4. Türkçe NER PoC'de yüklenmez. `airgap`'te `egress` aşaması yok (08:65); NER M4'te.
  5. 4B router modeli (Ollama'da ~4 GB + KV) yalnızca otomatik profil seçimi için var. PoC'de profiller agent'a eşlendiği için (P7) router kapatılabilir; Ollama sınırı ölçülerek düşürülür. Bu kararı vermeden önce PayCore'un "otomatik model" kullanımını sizin teyit etmeniz gerekiyor.
- **Gerekçe:** paycoreLLM/CLAUDE.md:577 "Bellek bütçesini aşan bileşen ekleme." PayCore'da Ollama 36 GB sınırında swap'a düştü (`compose.yml` notu, 2026-10-05).

### B1. 03 ile 01 döngüsel bağımlı (v3'ten, değişmedi)
- 03:43 "oluşturulunca LiteLLM team açılır" · 03:90 "LiteLLM key'i 429 döner". İstemci 01'de (01:17), 01 dalga 3'te.
- **Öneri:** Team ve anahtar işi ile 03:90 01'e taşınır; `projects.litellm_team_id` nullable olur.

### B2. 02'nin Kapsam 7'si dalga 3'te var olmayan tablolara yazıyor (v3'ten; P3'le genişledi)
- 02:18-25 `runs`/`run_events` alanları 06a'da doğuyor. Ayrıca 02:41 "Langfuse v3; ClickHouse ister" P3 ile çelişiyor.
- **Öneri:** 02:18-25 06a'ya taşınır. 02, Langfuse **v2**'ye gönderen kodu yazar. Bu, PayCore'un Faz 1 açığını da kapatır (CLAUDE.md:40 "config var, gönderen kod yok").

### B4. PoC kabul verisi: sentetik sözleşmeler yerine PayCore'un S1 seti (v3'ten, yeniden yazıldı)
- 04:102 "'fesih bildirim süresi' … ilk 3'te", 13:11 sözleşmeler, 09:72 `sozlesme-35.json`, 10:66 "13'teki örnek belgelerle". PoC'nin korpusu bunların hiçbiri değil.
- **Öneri:**
  - **Kalite kabulü:** PayCore'un S1 seti (50 soru, kaynak doğruluğu ≥ %80; CLAUDE.md:534).
  - **Akış kabulü:** 13a'nın küçük sentetik KB'si (3-5 belge, ACL testleri için) ve sentetik SQL şeması.
  - S1 sunucuda **kullanıcı tarafından** koşulur; ajan `eval/`'ı okumaz.
- **Ayrı bir çelişki:** `.gitignore` "S1 soru seti iç dokümantasyon sorularıdır, müşteri verisi değil; repoda durur (kullanıcı kararı 2026-10-02)" diyor. 09:87 ise "`eval/scenario1/questions.jsonl` … gerçek kurum verisi içerir" diyor. Hangisi doğru, ancak siz söyleyebilirsiniz. FFCore'un okuma yasağı bu cevaba göre dosya düzeyinde yeniden yazılmalı (P8).

### B6. 08: LiteLLM kancası kaldırılır; PoC'de 08 küçülür (v3'ten; P4'le genişledi)
- 08:38 kancası gereksiz (facade tek kapı; KARARLAR:59).
- **Öneri:** PoC'de 08 şunları teslim eder: engine, `regex` PII, `secrets`, `tool_args` kuralları ve `POST /internal/guardrails/evaluate`. Türkçe NER ve `injection` sınıflandırıcısı M4'e kalır.
- **Gerekçe:** `airgap` profilinde `egress` aşaması yok (08:65) ve bellek yok (P4). 06a yalnızca aşama adlarına bağlı (PLAN:221).

---

## 2. MAJOR bulgular

### P5. Doğrulama ortamı: zincir lokalde koşmuyor, ajan sunucuya bağlanamıyor, CI yok (yeni)
- deployment_plan.md: "embedding/reranker in-process olduğu için **RAG zinciri lokalde uçtan uca koşmaz**" · "CI yok". 02_agentic_development §5: "Sunucuya ajan bağlanmaz; komutları kullanıcı çalıştırır."
- FFCore ise şunları istiyor: EXECUTION_HANDBOOK:63 "Entegrasyon: compose ayakta, gerçek Postgres/Redis", :69 "Entegrasyon koşulamıyorsa paket VERIFIED olamaz", RELEASE:6 "CI'da `upgrade → downgrade → upgrade`".
- **Öneri:**
  1. Geliştirme makinesinde `ml` paketleri kurulur; bge-m3 ve reranker laptopta **doğruluk testi** için çalışır (deployment_plan "laptopta çalışır ama … ölçüm değeri yoktur"). Entegrasyon testleri lokal compose'da (Qdrant + Postgres + Redis + `FAKE_LLM`) koşar.
  2. **Ölçüm** (süre, S1) yalnızca sunucuda ve kullanıcı eliyle yapılır. Paket "VERIFIED (ölçüm bekliyor)" diye işaretlenir.
  3. Jenkinsfile'a `make lint test test-int` aşaması eklenir.
- **Gerekçe:** Sunucu doğrulaması kritik yolda insan beklemesine dönüşüyor. PoC'ye kaç gün ekleyeceği sizin günlük ritminize bağlı.

### P6. CPU'da araçlı agent: PayCore'un ölçülmüş "serbest ajan değil" kararı M3 demosuyla çelişiyor (yeni)
- paycoreLLM/CLAUDE.md:492-495: "CPU'da her ajan adımı büyüyen bağlamı yeniden işler (~20K token ≈ 20 sn); 5-6 adımlık döngü 2-4 dk sürer … 3B aktif parametreli modelin araç seçimi hatası adımlar boyunca birikir." CLAUDE.md:155-157: tek soru ~165-320 sn.
- FFCore: 13:16 `karma-asistan` "KB mod `tool`", 06:36 `"max_tool_calls":6`, PLAN:229 M3 "SQL aracı onay bekler".
- **Öneri:** PoC agent'ları iki tane:
  - `mode: always` doküman asistanı (PayCore'un bugünkü zinciri),
  - `max_tool_calls: 1`, onaylı tek araçlı SQL asistanı.

  `karma-asistan` ve `mode: tool` PoC dışına çıkar; GPU ya da `llmaas` ile ölçülür. M3 kabulündeki "araçlı agent taşıyor mu" sorusu bu iki agent'la cevaplanır.
- **Gerekçe:** PayCore'un CPU ölçümü bu kararın tek kanıtı. FFCore'da buna karşı bir ölçüm yok.

### P7. PayCore profilleri FFCore agent'larına eşlenmeli; C8'e kapsam filtresi gerekiyor (yeni)
- paycoreLLM `/v1/models` profil başına bir model döner (`paycore-ocean`, …; `api.py:406-418`); profil seçimi "duvar" (`PICKED_PROFILE_SHARE = 1.0`). Bu, Open WebUI kullanıcılarının bugün kullandığı bir özellik.
- FFCore 04:127 "kaynak ağırlıklı arama ve uzman profilleri (PayCore'a özgü)" diyerek bunu kapsam dışı bırakıyor. 06:30 `knowledge: [{kb_key, mode, top_k, min_score}]` yapısında kaynak filtresi yok.
- **Öneri:** Her PayCore profili bir FFCore agent'ı olur. `definition.knowledge[]` öğesine M3'te donmadan önce additive bir `filter: {scope: [...]}` eklenir (C8). Otomatik router ve "ağırlık" (`PROFILE_CANDIDATE_SHARE`) PayCore eklentisinde kalır.
- **Gerekçe:** Bu eklenmezse entegrasyon, PayCore'un kullanılan bir özelliğini kaldırır. Eklemenin maliyeti tek bir alan.

### P8. Gerçek kimlik bilgileri ve veri, işçilerin çalışma alanında (yeni, G)
- paycoreLLM kökünde gerçek değerli bir `.env` var (Atlassian servis hesabı; CLAUDE.md:187-189). MULTI_AGENT:47 "`.env` kopyalanır, commit edilmez": her worktree'ye gerçek parola kopyalanır.
- `data/` ve `eval/` gerçek içerik barındırıyor. `compose.yml` `./eval:/app/eval` bağlıyor. FFCore'un okuma yasağı (FFCore CLAUDE.md:24, PLAN:164) dizin düzeyinde ve `experts/`'i de kapsıyor. Oysa paycoreLLM'de `experts/` bir şablon dizini (CLAUDE.md:459 "Repo'daki `experts/` şablondur"), ve P7'deki iş bu şablonlara dokunuyor.
- **Öneri:**
  1. Worktree'lere `.env` kopyalanmaz. İşçiler `.env.test` (sahte değerler, `FAKE_LLM=1`, Atlassian kapalı) ile çalışır.
  2. Okuma yasağı dosya düzeyinde yeniden yazılır: `.env`, `data/**`, `eval/scenario*/*.jsonl` (B4'teki cevaba göre), `eval/results/**` yasak; `experts/*.yaml` şablonları serbest.
  3. Bu, SECURITY_AND_PERMISSIONS'a C sınıfı bir değişiklik olarak girer.
- **Gerekçe:** Yasak dizin işçinin çalışma dizininin içindeyse kuralı tek koruyan ajanın dikkati olur.

### P9. PayCore'un açık "API donması" hatası, FFCore 04'ün D6 kabul kriteriyle aynı şey (yeni)
- paycoreLLM/CLAUDE.md:39 "API'nin embedding/reranker sırasında donması (eşzamanlı kullanıcı)". Kodda `rag/retrieve.py` `search()` `embed()`'i, `rag/pipeline.py` `answer_question()` de `rerank()`'i async fonksiyon içinden **senkron** çağırıyor. Sorgu yolunda `to_thread` yok; yalnızca `warmup.py` ve `jira/worker.py` kullanıyor.
- FFCore 04:114 kabul kriteri: "10 eşzamanlı arama isteğinde … sağlık endpoint'i ve SSE keepalive 1 saniyenin altında".
- **Öneri:** Bu düzeltme 04a'nın **ilk PR'ı** olur: `asyncio.to_thread` + model başına `threading.Lock` (04:122). PayCore'un Faz 1 açığını da kapatır.
- **Gerekçe:** P4'e göre modelleri yalnızca API süreci yükleyecek. API'nin donması bütün agent'ları ve Jira worker'ını aynı anda kilitler.

### M1. LiteLLM: iki model kaynağı ve çalışırken verilemeyen anahtar (v3'ten)
- 01:11, 01:37, 03:23, 10:25. **Öneri değişmedi:** tablolardan LiteLLM DB API'sine yazan tek uzlaştırıcı. Ek olarak: Ollama host'ta çalışıyor (`OLLAMA_URL=http://host.docker.internal:11434`, `compose.yml` `extra_hosts`). LiteLLM'in Ollama kaydı bu adresi kullanır.

### M2. Zaman aşımı değerleri üç yerde üç farklı (v3'ten; CPU PoC'de daha da kritik)
- PLAN:72 run 900 s CPU, 06:135 600 s. PayCore'da tek soru ~165-320 sn ölçüldü (CLAUDE.md:155-157). **Öneri:** PLAN değeri (run 900 s, çağrı 600 s) seed'de.

### M3. mcp-search kimliği: havuzlanan oturum ve 5 dakikada düşen JWT (v3'ten)
- 05:19 bağlantı havuzu, 03:37 `exp ≤ 5 dk`; CPU run'ı 900 s. **Öneri:** JWT araç çağrısı başına imzalanır; `forward_user` araçları için havuz yoktur.

### M8. Kuyruk tasarımı (v3'ten; P3 ile birleşti)
- 04:35 "`arq` ya da `rq`"; 06:58-62'de üç sınıf, iki kuyruk. **Öneri:** `arq`. Run'lar arq işi; model çağrısı Redis tabanlı öncelikli yuvadan geçer (`LLM_SLOTS=1`, Ollama `OLLAMA_NUM_PARALLEL` ile uyumlu). PayCore Jira kuyruğu `llm-background` sınıfına taşınır.

### M10. Embedding süreç içinde kalır (v5'teki önerinin tersi)
- v5'te "Ollama → LiteLLM `embed-default`" önermiştim. paycoreLLM `rag/embed.py:47-52` dense + sparse üretiyor ve hibrit arama sparse'a dayanıyor. **Öneri:** 01:14'teki `embed-default` LiteLLM kaydı PoC'de yazılmaz. 04:44 "süreç içi `BGEM3FlagModel`, dense + sparse" olarak düzeltilir. 14 ve 09'un `semantic` scorer'ı da aynı fonksiyonu kullanır. P9'daki thread kuralı burada da geçerli.

### M11. `mode: tool` araç adları donmuş C7 ile çelişiyor (v3'ten)
- 06:110'daki üç araç C7'ye (CONTRACTS:13) aykırı. P6'ya göre PoC'de `mode: tool` olmasa da C7 M3'te donuyor. **Öneri:** 06:110 silinir.

### M12. Aşama teşhisinin verisi: PayCore'da bellekte, FFCore'da kalıcı olmalı (v3'ten, yeniden yazıldı)
- paycoreLLM `eval/run.py:179-214` `not_retrieved`/`not_reranked`'ı `trace.candidates`'tan, yani süreç içi iz nesnesinden türetiyor. FFCore'da arama ayrı API'de ve runtime ayrı worker'da olduğu için bu nesne yok.
- **Öneri:** 04a'da `kb_queries`'e `run_id` ve `candidates jsonb` (top-30) eklenir. 09, PayCore'un `eval/run.py` mantığını bu kayıttan okuyacak biçimde uyarlar (kopya değil).

### M13. Fail-loud ihlalleri (v3'ten)
- 06:54 `OLLAMA_CONTEXT_LENGTH` tutarsızlığı yalnızca uyarı veriyor (PayCore compose'u 32768'i sabitliyor; FFCore'un 8000/16000 bağlam seed'i bununla doğrulanmalı). 06:45 RAG top_k sessizce düşüyor. 05:19 araç sonucu sessizce kırpılıyor. 02:15 prompt yedeği.
- **Öneri:** v5 ile aynı. Ek olarak PayCore'un `embed.py:18-38` `embedding_truncated` uyarısı, FFCore'un fail-loud kuralına göre `chunks.chunk_status=flagged` + gerekçeye çevrilir.

### M15. ACL: paycoreLLM'de hiç yok (v3'ten, yeniden yazıldı)
- paycoreLLM'de ACL, izin ya da kısıt alanı yok (`ingest/`, `rag/` grep'i boş döndü). Herkes her parçayı görüyor. FFCore 04:73, 04:103 ve 05:67 ACL kabul kriterleri koyuyor.
- **Öneri:** PoC'de mevcut korpus "proje üyelerine açık" kabul edilir: bu PayCore'un bugünkü davranışı. `acl_roles` ve `acl_users` Qdrant payload'ına eklenir, filtre sorgu anında uygulanır. Kabul testleri 13a'nın sentetik KB'siyle yapılır. Confluence ve Jira izinlerinin aktarımı (16) PoC sonrasıdır; ama bu açıkça yazılmalı, çünkü PRSIM kayıtlarını görebilen herkes bütün korpusu görür.

### M20. Kota kapsamları (v3'ten)
- 03:31 `group|model|provider` uygulayıcısız; 03:88 facade'a bağlı. **Öneri:** `project|api_key|user`; 03:88 06b'ye.

### M21. Çekirdek yüzeyi genişliyor (v3'ten; C8)
- 04:85 KB ayarları, 06:107 `webhook_url`, `budget_usd`, `raw_output_tools`. **Öneri:** v5 ile aynı. Ek olarak paycoreLLM'in parçalama kuralı (Confluence H2/H3, 400-600 token; CLAUDE.md:402, 416) FFCore'un tek `heading` stratejisi olur. FFCore 04:43'teki "hedef 400, üst sınır 512" bununla uzlaştırılmalı.

### M22. Kabul tablosu: PoC'de yalnızca `cpu` sütunu geçerli (v3'ten, yeniden yazıldı)
- 13:35-43. **Öneri:** PoC kabulünde `cpu` sütunu geçerli, `llmaas` ve `gpu` sütunları `NOT_RUN`. `cpu` eşikleri PayCore'un ölçümleriyle (S1 ≥ %80, tek soru ~165 sn) yeniden yazılır. 13'teki "≤ 4 dk" ile PayCore'un "bütçe 60-90 sn" hedefi (CLAUDE.md:73) farklı şeyler ölçüyor; hangisinin kabul olduğu yazılmalı.

---

## 3. MINOR bulgular (tek satır)

- **N11** 04:19 `chunks`, 05:48 `few_shots`: `project_id, created_by` eksik (C3, M2'de donuyor).
- **N16** 06:95 SSE listesinde `progress`, `fallback` yok (C9).
- **N23** 08:14 `action_taken` ile 08:15 `default_action` uyuşmuyor (C4).
- **N47** `outcome_label` iki listeyi adlandırıyor (06:18, 09:17, TERMINOLOGY:69).
- **N48 (yeni)** Tablo adı çakışması: paycoreLLM `docker/postgres/init.sql:25` `sync_state(source, last_sync)` ile FFCore 16:18 `sync_state(data_source_id, layer, cursor, completed_at)` aynı Postgres veritabanında (`llm`). FFCore tablosu `source_sync_state` olarak adlandırılmalı ya da PayCore'unki göç ettirilmeli.
- **N49 (yeni)** paycoreLLM Alembic ve SQLAlchemy kullanmıyor (`init.sql` + ham `psycopg`). FFCore'un Alembic zinciri (PLAN:165) mevcut üç tabloyu bir "taban" migration'ıyla sahiplenmeli; yoksa `alembic heads` ve `init.sql` iki şema kaynağı olur.
- **N50 (yeni)** Terim: paycoreLLM kodu ve komutları `bronze` diyor (`sync_state` `<kaynak>:bronze`, `--bronze`, CLAUDE.md:409). TERMINOLOGY:36 bilgi tabanı için `bronze`'u yasaklıyor (ARCH-13). Ekranda ve FFCore API'sinde `raw` kullanılır; PayCore'un CLI adları eklentide kalır ya da `DeprecationWarning` ile değiştirilir.
- **N51 (yeni)** İmaj adı ve sürümü: `nexus.paycore.com/paycore-llm/paycore-llm:3.12.${PAYCORE_LLM_VERSION}-test` (Jenkins) ile FFCore'un `FFCORE_VERSION` ve `REGISTRY_PREFIX` kuralları (RELEASE:15, C12) uzlaştırılmalı.

---

## 4. Çelişkiler (brief ↔ brief ve FFCore ↔ paycoreLLM)

| # | A (alıntı) | B (alıntı) | Öneri |
|---|---|---|---|
| 1 | FFCore MULTI_AGENT:45 "Branch: `feat/<paket>-<kısa-slug>`" | paycoreLLM 02_agentic §5 "Dal açılmaz; commit doğrudan `master`'a." | FFCore akışı; `DECISION-` (P1) |
| 2 | FFCore 05a mcp-sql | paycoreLLM 02_agentic §5 "Faz 2 (text-to-SQL) için kod yazılmaz … (W17 kilitli)" | W17 FFCore'un sentetik demosu için açılır; `DECISION-` (P1) |
| 3 | FFCore 06:132 "LangGraph 0.4+" | paycoreLLM CLAUDE.md:43-47 "İlk iş akış çatısı kararıdır" | LangGraph; `DECISION-` (P1, P3) |
| 4 | FFCore 04:64 "BM25 Postgres'ten, vektör seçilen sürücüden, RRF" | paycoreLLM CLAUDE.md:173 "Sparse = bge-m3 `lexical_weights` … BM25 değil" | Qdrant + sparse; C5 genişler (P3) |
| 5 | FFCore 04:44 "LiteLLM `embed-default` üzerinden" | paycoreLLM `rag/embed.py:47` dense + sparse süreç içi | Süreç içi (M10) |
| 6 | FFCore PLAN:166 "tek kütüphane `arq`" | paycoreLLM CLAUDE.md:179 "Postgres tablosu + Python worker · Redis/Celery yok" | arq; Jira kuyruğu taşınır (P3, M8) |
| 7 | FFCore 00:36 "Langfuse v3 compose'u ClickHouse, MinIO ve Redis ister" | paycoreLLM `compose.yml` `langfuse:2`, `mem_limit: 2g` | v2 (P3, P4) |
| 8 | FFCore 04:40 "Tesseract'a (`tur+eng`)" | paycoreLLM CLAUDE.md:384 "OCR motoru PaddleOCR `tr`" | PaddleOCR (P3) |
| 9 | FFCore 06:88 "CPU'da varsayılan `cited`" | paycoreLLM CLAUDE.md:136 "`max` (… **varsayılan**, kullanıcı kararı 2026-10-05)" | PayCore seed'inde `max` (P3) |
| 10 | FFCore 13:16 `karma-asistan` "KB mod `tool`" | paycoreLLM CLAUDE.md:492 "Neden serbest ajan değil: CPU'da her ajan adımı …" | PoC'de yok (P6) |
| 11 | FFCore 09:87 "`questions.jsonl` … gerçek kurum verisi içerir" | paycoreLLM `.gitignore` "S1 soru seti iç dokümantasyon sorularıdır, müşteri verisi değil (kullanıcı kararı 2026-10-02)" | Sizin cevabınız (B4) |
| 12 | FFCore 16:18 `sync_state(data_source_id, …)` | paycoreLLM `init.sql:25` `sync_state(source, last_sync)` | Yeniden adlandırma (N48) |
| 13 | FFCore 01:11 / 03:23 / 10:25 `render-litellm` çelişkisi | (brief'ler arası, v3) | Tek uzlaştırıcı (M1) |
| 14 | FFCore 06:82 `search_documents` · C7 | 06:110 üç `knowledge_*` aracı | C7 (M11) |
| 15 | FFCore PLAN:72 run 900 s | 06:135 600 s · 06:36 300 s | PLAN (M2) |
| 16 | FFCore 08:14 `action_taken` | 08:15 `default_action` | Tek liste (N23) |

---

## 5. Felsefe ihlalleri

| İlke | Yer | Alıntı | Öneri |
|---|---|---|---|
| ARCH-09 | FFCore 04a tamamı | "veri modeli (tam), üç katmanlı depo, pipeline adımları 1-9 …" (04:5) | paycoreLLM'de çalışan ingest ve RAG kodu yeniden yazılmaz, sarılır (P3) |
| ARCH-09 | FFCore 09 teşhis | `not_retrieved`, `not_reranked` … (09:21-31) | paycoreLLM `eval/run.py` mantığı uyarlanır (M12) |
| ARCH-09 | FFCore 08:38 | "`litellm_hook.py` … `CustomGuardrail`" | Kaldırılır (B6) |
| ARCH-09 | FFCore 01:11 | açılışta statik config + çalışırken DB API | Tek uzlaştırıcı (M1) |
| ARCH-06 | paycoreLLM `rag/pipeline.py` / `retrieve.py` | sorgu yolunda senkron `embed()` ve `rerank()` | `to_thread` + kilit (P9) |
| ARCH-06 | FFCore 06:54 · 06:45 · 05:19 · 02:15 | uyarı / sessiz top_k düşüşü / kırpma / prompt yedeği | M13 |
| ARCH-06 | paycoreLLM `rag/embed.py:18-38` | "`embedding_truncated`" yalnızca log uyarısı | `chunk_status=flagged` + gerekçe (M13) |
| ARCH-07 | FFCore 04:85 · 06:107 | KB ayarları, `webhook_url`, `budget_usd`, `raw_output_tools` | Çıkarılır (M21) |
| ARCH-07 | FFCore 13:16 · 06:36 | CPU'da çok adımlı araç döngüsü | PoC'de tek araç çağrısı (P6) |
| ARCH-10 | FFCore 04:35 | "`arq` ya da `rq`" | `arq` (M8) |
| ARCH-10 | FFCore 01:14 | "`ollama/bge-m3` ya da süreç içi TEI" | Süreç içi FlagEmbedding (M10) |
| ARCH-13 | paycoreLLM ↔ TERMINOLOGY:36 | `bronze` ↔ "bronze/silver/gold … yasak" | `raw` (N50) |
| ARCH-13 | paycoreLLM "uzman profili" ↔ FFCore "agent" | CLAUDE.md:488 "uzman profili" · TERMINOLOGY:53 `agents` | Profil = filtreli agent (P7); ekranda tek terim "agent" |
| ARCH-13 | paycoreLLM "Faz / Wave" ↔ FFCore "kilometre taşı / dalga" | CLAUDE.md:31 "FAZ 1" · 02_agentic §3 "Wave" · TERMINOLOGY:77-78 | FFCore terimleri; PayCore'un Faz 1 kapanışı bir kilometre taşı satırı olur |
| ARCH-13 | FFCore TERMINOLOGY:69 · 06:18 · 09:17 | `outcome_label` iki liste | İki terim (N47) |

---

## 6. Süre ve dalga değerlendirmesi (PoC, entegrasyonla)

### 6.1 Paket tahminleri

| Paket | v5 tahminim | v9 tahminim | Değişimin nedeni |
|---|---|---|---|
| **00i** (00'ın yerine: entegrasyon kararları + yerleşim + compose birleştirme + bellek tablosu + lokal `ml` ortamı) | 1,5 | 2 | Boş iskelet yerine çalışan depo; P1-P5 |
| 01 | 3 | 3 | Host'taki Ollama; `llm.py` LiteLLM'e yönlenir |
| 02 | 1 | 1 | Langfuse v2'ye gönderen kod |
| 03a | 3 | 3 | Değişmedi (yeni kod) |
| 03b | 5 | 4,5 | Jira kuyruğunun arq'a taşınması eklendi (+0,5); `group/model/provider` kapsamları çıktı (−1) |
| 04a | 7 | **4** | Ingest, kapılar, dönüşüm, chunk, breadcrumb, rerank tabanı ve güncellik mevcut. Kalan iş: `KnowledgeStore` bağdaştırıcısı, elle yükleme yolu, ACL payload, yönetim/arama API'si, P9 |
| 05a | 4 | 4 | Sentetik SQL DB'si 13a'dan |
| 06a | 7 | 6,5 | `mode: tool` PoC'de yok (P6); P7 filtresi eklendi |
| 07 | 1,5 | 1,5 | |
| 08 | 5,5 | **3** | PoC'de NER ve injection sınıflandırıcısı yok (B6) |
| 09 | 4,5 | **3** | `eval/run.py` mantığı uyarlanır |
| 10 (M3 ekranları) | 10 | 10 | Değişmedi |
| 11 | 3 | 3 | Open WebUI'nin yerine geçer |
| 13 | 4 | **2** | Sentetik sözleşme yok; S1 seti var. Sentetik KB ve SQL şeması kalıyor |
| **Toplam** | **~60** | **~50,5** | −%16 |

### 6.2 Kritik yol (M3'e)

- **Brief zinciri, v9 sayılarıyla:** 00i (2) → 03a (3) → 01 (3) → 04a (4) → 05a (4) → 06a (6,5) → 09 (3) → 13 (2) = **27,5 gün**.
- **Dalga kapılarıyla:** ~30 gün.
- **Hesaba katılmayan:** sunucuda kullanıcı eliyle yapılacak ölçüm (P5). Her kritik paket için yarım gün beklemeyle 4 gün daha. **~30-34 iş günü.**
- **Paralel çalıştırılmalı:** PayCore'un Faz 1 açıkları (S1/S2 eval'leri, kalan space'lerin yüklenmesi) FFCore PoC'sine paralel olarak sunucuda yürür. Ama `ingest` (40 GB) ile Ollama birlikte çalışamıyor (devops_handover §7). Bu yüzden toplu yükleme günleri sunucudaki ölçümlerle aynı güne konmamalı. Bu, sunucu takvimini koordinatörün işi haline getirir.

### 6.3 Sıra

1. **00i** (2 gün, kodsuz): P1-P4 kararları, P2 yerleşimi, `DECISION-` kayıtları, bellek tablosu.
2. **P9** (04a'nın ilk PR'ı, 0,5 gün): PayCore'un donma hatası; FFCore'un ilk görünür faydası.
3. **02** (Langfuse v2 gönderimi), 03a/03b ve 08 paralel.
4. 01 → 04a → 05a → 06a → 07/09/11 → 13.
5. Open WebUI, 11 birleşip S1 ile doğrulanınca kaldırılır.

---

## 7. Katılmadığım kararlar

- **"Geliştirme paycoreLLM içinde yapılacak" (2026-10-27): kısmen katılıyorum.** Teknik olarak doğru: çalışan ingest/RAG kodu, iki aylık ölçüm, gerçek korpus ve gerçek sunucu PoC'yi ~10 gün kısaltıyor ve PoC'yi gerçek bir kapalı ağ müşterisinde koşturuyor. Ama karar, iki yazılı kararla çelişiyor ve bunlar kayda geçmeden uygulanmamalı:
  1. **KARARLAR:11** "PayCore bir müşteridir; … ürün adı ve alan adı PayCore'a bağlanmaz" ve PLAN:164 "Kod birebir kopyalanmaz". Ürün kodunun müşterinin deposunda (git: PayCore DWH) yazılması, bu kararın tersine dönmesi demek. Ya KARARLAR'a "tersine karar" olarak yazılmalı ya da deponun sahipliği, FFCore kodunun ileride ayrı bir depoya nasıl çıkacağıyla birlikte netleşmeli. Sahiplik konusunu ben değerlendiremem; yalnızca belgelerin şu an birbiriyle çeliştiğini söylüyorum.
  2. **paycoreLLM'in kendi yol haritası** (CLAUDE.md:37-52, kullanıcı kararı 2026-10-26): "Faz 1'i kapat → Faz 2 çatı kararı → Faz 3". FFCore PoC'si fiilen Faz 2 ve 3'ün işi. P1'deki `DECISION-` kayıtları olmadan bir gün önceki kararınızla çelişiyor.
- **FFCore'un M3 tanımı ("araçlı agent", karma asistan), PayCore'un CPU ölçümüyle çelişiyor (P6).** PayCore'un kararı ölçüme dayalı, FFCore'unki değil. CPU'da PayCore'un kararını doğru buluyorum.
- **KARARLAR:30 "pgvector varsayılan, Qdrant ikinci sürücü".** PoC için katılmıyorum: canlı korpus ve ölçümler Qdrant + sparse üzerinde (P3). Bu durum, v5'teki "Qdrant ertelensin" önerimi de tersine çeviriyor.
- **KARARLAR:60 "LiteLLM'e ortam değişkeniyle".** v5'teki itirazım sürüyor (M1). `airgap` PoC'de sağlayıcı anahtarı yok, ama Ollama/vLLM kaydı da aynı uzlaştırıcıdan geçmeli.
- **v5'teki `BACKGROUND_WINDOW` itirazımı geri çekiyorum.** PoC `airgap` CPU'da; pencere tam bu durum için doğru.

---

## 8. Doğrulanmamış iddialar

- **U1-U2** (M1) LiteLLM'in config ve DB model kayıtlarını birleştirmesi; `/model/new`'daki anahtarın şifrelenmesi.
- **U4** (M8) LiteLLM OSS'te istek önceliklendirme özelliği olup olmadığı.
- **U5** (M3) `mcp` SDK'sının streamable HTTP istemcisinde başlıkların oturum açılışında alınması.
- **U12** Süre tahminleri yargıdır.
- **U14 (yeni)** Ollama'nın embedding API'si bge-m3 için yalnızca dense vektör döner, `lexical_weights` (sparse) vermez. Bu doğruysa M10'daki geri dönüş zorunlu.
- **U15 (yeni)** P4'teki ek bileşen bellek rakamları (LiteLLM, Redis, Next.js, MCP servisleri, NER, Langfuse v3) tahmindir; 00i'de `docker stats` ile ölçülmeli.
- **U16 (yeni)** LiteLLM'in Langfuse callback'inin Langfuse **v2** sunucusuyla çalıştığı (SDK sürüm uyumu) doğrulanmadı.
- **U17 (yeni)** 4B router'ın Ollama'da ~4 GB + KV tuttuğu, paycoreLLM CLAUDE.md:556'daki bütçe satırından (`~4 GB`) alındı; ben ölçmedim.
- **U18 (yeni)** paycoreLLM Jira PRSIM kayıtlarının kişisel veri (müşteri personeli adı, e-posta) içerip içermediğini bilmiyorum. İçeriyorsa FFCore'un CONTRACTS:39 veri sınırı kuralı ("kişi düzeyi kurum verisi platformda tutulmaz") mevcut korpusla zaten ihlal ediliyor olabilir. Veriye bakmadan karar veremem; sizin değerlendirmeniz gerekiyor.

---

## 9. PoC dışında kalanlar (ilgili paket başlamadan önce ele alınmalı)

- **06b (facade) öncesi:** B5 (`user` alanıyla ACL atlatma), M4 (API anahtarıyla onay), C11 yol çakışması. paycoreLLM zaten kimlik doğrulamasız `/v1/chat/completions` ve `/v1/models` sunuyor (`api.py:406-436`); FFCore facade aynı yolu `agent:<proje>/<agent>` adlarıyla istiyor. Göç planı gerekiyor: PayCore modelleri → agent'lar (P7), Open WebUI'ye API anahtarı.
- **`llmaas` öncesi:** B3 (fallback), M5 (SSRF), M6 (CSRF), M16 (egress, Teams), M17 (akışta geri çevirme), Türkçe NER (B6), v5'in sentetik sözleşme maddesi (M7).
- **M4 öncesi:** M18 (kendi yazdığı test setleri).
- **05b, 14, 15, 16 öncesi:** M14, M19, M15'in 16 kısmı. 16 için önemli not: paycoreLLM'deki Confluence ve Jira **Data Center** bağlayıcıları (`ingest/sync.py`, `atlassian_client.py`) 16'nın Server/DC yarısını zaten karşılıyor. 16'nın süresi 8 günden belirgin biçimde düşer.
- **Kritik değil:** M9 (APScheduler), N1-N46'nın kalanı (v3).

---

## 10. v5'ten v9'a değişenler

| Bulgu | v5 | v9 | Neden |
|---|---|---|---|
| P1-P9 | — | yeni | paycoreLLM incelemesi |
| B3 | BLOCKER | PoC dışı | `airgap` seed'inde fallback yok (01:36) |
| B4 | sentetik sözleşmeler | S1 seti + küçük sentetik KB/SQL | PoC korpusu PayCore'unki |
| B6 | kanca kalkar | + NER ve injection PoC dışı | P4, `airgap` |
| M7 | MAJOR | PoC dışı | Gerçek sözleşme konusu PayCore PoC'sinde yok; veri kuralı P8'e taşındı |
| M10 | Ollama → LiteLLM | **süreç içi FlagEmbedding** | Sparse (U14) |
| M12 | `kb_queries` alanları | + PayCore `eval/run.py` uyarlaması | ARCH-09 |
| M15 | boş ACL anlamı | paycoreLLM'de ACL yok; PoC kabulü sentetik KB'yle | Kod taraması |
| M22 | `gpu` NOT_RUN | yalnızca `cpu` geçerli; eşikler PayCore ölçümüyle | PoC donanımı |
| N4 | MINOR | kaldırıldı | paycoreLLM'de `/health` ve `warmup.py` var; 00 → 00i |
| Önceki sohbet önerisi "airgap ertelensin" | öneri | **geri alındı** | PayCore kapalı ağ müşterisi |
| v5 "Qdrant ertelensin" | öneri | **geri alındı** | Canlı korpus Qdrant'ta |
| v5 `BACKGROUND_WINDOW` itirazı | itiraz | **geri çekildi** | PoC CPU |
