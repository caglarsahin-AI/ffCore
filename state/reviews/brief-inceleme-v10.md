# FFCore brief incelemesi v10 — PayCoreLLM içinde PoC

## 0. Özet

1. **Mevcut brief’lerle kodlamaya başlanamaz; aşağıdaki daraltılmış entegrasyon brief’i yazıldıktan sonra başlanabilir.** Uygulama dizini artık boş FFCore monoreposu değil, çalışan `paycoreLLM` deposudur.
2. En önemli bulgu B1’dir: 00’ın yeni monorepo/compose kurma talebi, PayCoreLLM’in çalışan FastAPI, Qdrant, Postgres, Langfuse, Open WebUI, ingest ve worker yapısını ikinci kez kurar.
3. B2’ye göre LangGraph + MCP/text-to-SQL + onay akışı PoC’den çıkarılmalıdır; PayCoreLLM anayasası Faz 1 bitmeden bunların kodlanmasını açıkça yasaklıyor.
4. B3’e göre PoC’nin gerçek kritik açığı platform özelliği değil güvenli erişimdir: mevcut `/ask` ve `/v1` uçlarında kimlik doğrulama yoktur; compose’da zayıf secret varsayılanları ve gereksiz yayınlanan altyapı portları vardır.
5. **PoC kritik yol:** mevcut dikey dilimi dondur → API erişimini ve veri sınırını güvene al → Faz 1 eksiklerini/izlemeyi tamamla → mevcut eval kapılarını geçir → offline kurulum ve Open WebUI üzerinden demo et.

### V10 PoC kritik listesi

| Sıra | Kritik iş | Mevcut yapıdan yeniden kullanılacak | PoC’den çıkarılan karşılığı |
|---|---|---|---|
| P1 | Entegrasyon tabanı ve regresyon kapısı | `src/paycore_llm`, mevcut compose, mevcut migration ve testler | 00’ın yeni monorepo/servis iskeleti |
| P2 | API kimlik doğrulama, tek-tenant veri sınırı ve aktörlü audit | Open WebUI oturumu + mevcut FastAPI; kimlik aktarımı doğrulanmalı | 03’ün provider/model kataloğu, kota, retention, alert ve çok-proje yönetişimi |
| P3 | Compose güvenlik sıkılaştırması | mevcut server override ve iç ağ | Yeni Redis/LiteLLM/ClickHouse/MinIO yığını |
| P4 | Mevcut RAG eşzamanlılık düzeltmesi ve readiness | `rag/*`, `warmup.py`, Qdrant, DuckDB | 04a’nın pgvector’a yeniden yazımı ve 04b vektör göçü |
| P5 | Eksik Langfuse gönderimi | mevcut Langfuse v2 servisi ve `rag/trace.py` | Langfuse v3’e yükseltme, prompt yönetim ürünü, dataset UI |
| P6 | PRSIM Faz 1 eksiklerini kapatma | mevcut router, Postgres kuyruğu, Jira suggestion gate | MCP, text-to-SQL, serbest agent ve genel onay kuyruğu |
| P7 | S1/S2 eval ve fail-loud kalite kapısı | `src/paycore_llm/eval/run.py`; gerçek veri deposu bu incelemede açılmadı | Yeni 35 soruluk hastane/SQL demosu ve ayrı eval platformu |
| P8 | Offline paket, secret/port kontrolü ve duman testi | mevcut Nexus imajları, compose, DevOps teslim akışı | 12’nin tüm yeni servisleri paketleyen genel ürün kurulumu |
| P9 | Open WebUI üzerinden uçtan uca demo | mevcut OpenAI-uyumlu `/v1` ve Open WebUI | 10 ve 11’deki özel Next.js yönetim/chat uygulaması |

## 1. BLOCKER bulgular

### B1 — Başlangıç brief’i yanlış uygulama kökü ve ikinci altyapı yığını varsayıyor

**Brief alıntısı:** `plan/00-depo-iskeleti.md:7`: “Monorepo iskeletini, geliştirme ortamını ve altyapı servislerini (Postgres+pgvector, Redis, Ollama, LiteLLM, Langfuse) tek `docker compose up` ile ayağa kaldırmak.”

**Mevcut uygulama kanıtı:** `paycoreLLM/compose.yml:77-106` zaten `api`, `worker` ve ayrı `ingest` işini; `compose.yml:110-138` Qdrant ve Postgres’i; `compose.yml:189-235` Langfuse ve Open WebUI’ı tanımlar. `paycoreLLM/CLAUDE.md:179-181` ayrıca “Postgres tablosu + Python worker”, Langfuse ve Docker Compose seçimlerini dondurur.

Bu brief tek başına işçiye verilirse işçi istenen uygulama dizininin dışında yeni klasör ağacı kurar veya çalışan depoda ikinci backend/frontend/queue yaratır. Sonuç PR’a çevrilebilir görünür ama yanlış ürünü üretir.

**Düzeltme:** 00 yerine `00p-paycore-entegrasyon-tabani` yazılmalı. Touch-zone `paycoreLLM` olmalı; mevcut servis adları, portlar, veri volume’ları ve CLI girişleri envanterlenip regresyon testine bağlanmalı. Yeni servis eklemek bu paketin kapsamı dışında olmalı. Bu seçim mevcut yatırımı korur ve ARCH-09’a uyar.

### B2 — PoC paketleri PayCoreLLM’in Faz 1 yasağını aşıyor

**Brief alıntıları:**

- `plan/05-arac-katmani-mcp.md:5`: “05a ... `mcp-sql`: `get_schema`, `run_sql` ... **PoC:** 05a.”
- `plan/06-agent-runtime.md:10`: “agent tanımını (JSON) çalışan bir LangGraph grafına çevirmek”.
- `plan/07-onay-kuyrugu.md:18-20`: araç çağrısında interrupt, approval kaydı ve grafı resume etme akışı.
- `plan/13-ornek-veri-demo.md:21`: SQL, onaylı araç akışı ve PII’yi aynı PoC e2e’sinde zorunlu kılar.

**Çelişen PayCoreLLM cümleleri:** `paycoreLLM/CLAUDE.md:31-35`: “FAZ 1 KAPSAMI: yalnızca Senaryo 1 ve 2. Senaryo 3 için kod yazma, bağımlılık ekleme, altyapı kurma.” `CLAUDE.md:43-52`: ilk iş akış çatısı kararıdır ve “Faz 2 ve 3 için kod, bu bölümdeki karar adımları onaylanmadan yazılmaz.”

İşçi aynı anda hem FFCore PoC kabulünü hem uygulama deposunun üst kararını yerine getiremez. Bu yalnız kapsam tartışması değildir; izin verilmemiş mimari karar gerektirir.

**Düzeltme:** 05, 06, 07 ve 13’ün SQL/agent/onay maddeleri PayCore PoC’den çıkarılmalı. PoC, mevcut sabit RAG/PRSIM workflow’u ve Jira’nın kapalı-by-default öneri kapısını kanıtlamalı. Faz 2’ye ancak S1 ≥ %80, S2 ≥ %85 ve ayrı framework kararı sonrası geçilmeli. Genel agent runtime’ı “ince bir PoC için” gizlice eklemeyi reddediyorum.

### B3 — Mevcut API dış sınırı kimlik doğrulamıyor

**İlgili brief alıntısı:** `plan/03-backend-cekirdek.md:43`: “Auth: `POST /auth/login` ... `GET /auth/me`.” `plan/06-agent-runtime.md:84` bearer API key doğrulamasını tarif eder; fakat 06b PoC sonrasına bırakılmıştır (`plan/06-agent-runtime.md:6`).

**Mevcut kod kanıtı:** `paycoreLLM/src/paycore_llm/api.py:389-436` `/health`, `/ask`, `/v1/models` ve `/v1/chat/completions` uçlarını herhangi bir dependency/header doğrulaması olmadan yayınlar. `paycoreLLM/compose.yml:82-83` API’yi hostta `8010` portuna açar; Open WebUI ise sabit `OPENAI_API_KEY: local` kullanır (`compose.yml:212-215`).

Bu haliyle ağ erişimi olan herkes iç Jira/Confluence bilgisini sorgulayabilir. FFCore kimlik/proje/audit aktörü bu açık kapı çözülmeden anlamlı değildir.

**Düzeltme:** PoC için genel kullanıcı/rol ürününü değil, tek bir net sınırı uygulayın: dış kullanıcı girişi Open WebUI’da kalmalı; Open WebUI→API çağrısı güçlü, kuruluma özel servis anahtarıyla doğrulanmalı; doğrudan `/ask` ve `/v1` aynı anahtar olmadan 401 vermeli. Son kullanıcı kimliğinin güvenilir biçimde forward edilmesi doğrulanırsa audit’e bağlanmalı; doğrulanamazsa PoC audit aktörü `openwebui_service` olarak açıkça yazılmalı, kişiymiş gibi gösterilmemeli. Ham anahtar loglanmamalı ve `local` varsayılanı yasaklanmalı.

### B4 — Secret ve ağ varsayılanları fail-open

**İlgili brief alıntısı:** `plan/12-kapali-ag-paketleme.md:21`: “Compose’da yalnızca frontend ve backend portları dışa açık; Postgres, Redis, LiteLLM, Langfuse iç ağda.”

**Mevcut uygulama kanıtları:**

- `paycoreLLM/compose.yml:35` ve `:127`: Postgres şifresi `${POSTGRES_PASSWORD:-CHANGE_ME}`.
- `paycoreLLM/compose.yml:194-197`: Langfuse DB, NextAuth ve salt için `CHANGE_ME` varsayılanları.
- `paycoreLLM/compose.yml:114-115` Qdrant’ı, `:199-200` Langfuse’u, `:144-145` Ollama’yı hosta yayınlar.

Bu PoC kritik bir güvenlik kusurudur; 12’yi bütünüyle “PoC sonrası” saymak doğru değildir.

**Düzeltme:** Tam 12 paketi değil, `12p-paycore-hardening` PoC’ye alınmalı: zorunlu secret’lar `${VAR:?message}` ile fail-loud; altyapı portları kaldırılmalı veya yalnız `127.0.0.1`/iç ağda bind edilmeli; dışarı yalnız Open WebUI ve gerekiyorsa kimlik doğrulamalı backend açılmalı. Mevcut offline imaj/bundle yolu korunmalı.

## 2. MAJOR bulgular

### M1 — pgvector ve Redis/arq, çalışan Qdrant/DuckDB/Postgres kuyruğunu gereksiz çoğaltıyor

**Brief alıntıları:** `plan/04-bilgi-tabani.md:5`: “`PgVectorStore` ... Redis kuyruğu”; `plan/04-bilgi-tabani.md:35`: “Pipeline (Redis kuyruğu + worker süreci, yalnızca `arq`)”.

**Çelişen PayCoreLLM cümleleri:** `paycoreLLM/CLAUDE.md:173-179`: “Vektör DB | Qdrant”, “Doküman deposu | DuckDB + Parquet” ve “İş kuyruğu | Postgres tablosu + Python worker | Redis/Celery yok”. `paycoreLLM/src/paycore_llm/jira/queue.py:37-50` mevcut kuyruğun `FOR UPDATE SKIP LOCKED` ile atomik claim yaptığını gösterir.

Yeni depolar ürün değerini artırmadan veri uzlaştırma, RAM ve işletim yükü getirir. 64 GB bütçe zaten Qwen, embedding/reranker ve ingest ile doludur (`paycoreLLM/CLAUDE.md:552-566`).

**Düzeltme:** PoC’de Qdrant + DuckDB + mevcut Postgres kuyruğu tek yol olmalı. FFCore’un `VectorStore`/queue soyutlaması gerekiyorsa mevcut uygulamanın etrafında ince adaptör olarak eklenmeli; pgvector, Redis ve arq servisi eklenmemeli. Genel ürün sürücüsü kararı PoC ölçümünden sonra alınmalı.

### M2 — LiteLLM bu PoC’de çözülmüş bir soruna yeni servis ekliyor

**Brief alıntısı:** `plan/01-litellm-gateway.md` model gateway’ini PoC kritik zincirine koyar; `plan/00-depo-iskeleti.md:14` ayrı `litellm` servisi ister.

**Mevcut kod kanıtı:** `paycoreLLM/src/paycore_llm/llm.py:1-14` uygulamanın zaten yalnız OpenAI-uyumlu protokol konuştuğunu ve base URL değişimiyle Ollama/vLLM ayrımını çözdüğünü gösterir. PayCore hedefi tamamen lokaldir (`paycoreLLM/CLAUDE.md:12-14`).

Tek yerel model sağlayıcısı, 1-2 PoC kullanıcısı ve dış sağlayıcı olmayan bu kurulumda LiteLLM’in fallback/katalog/bütçe özellikleri kullanılmayacaktır. Yeni proxy ek gecikme, secret ve arıza yüzeyi yaratır.

**Düzeltme:** PoC’de `llm.py` korunmalı. Model adı/base URL/timeout ayarları açık yapılandırma olarak test edilmeli. LiteLLM yalnız ikinci sağlayıcı, gerçek fallback veya dış FFCore facade gereksinimi geldiğinde yeniden değerlendirilmelidir.

### M3 — Langfuse brief’i mevcut sürümü yükseltmeyi ve gereksiz ürün yüzeyini zorunlu kılıyor

**Brief alıntıları:** `plan/02-langfuse-izleme.md:33`: “Langfuse v3; ClickHouse ister”; `:15`: prompt API’si, cache ve seed akışı.

**Mevcut uygulama kanıtı:** `paycoreLLM/compose.yml:189-204` Langfuse v2’yi mevcut Postgres ile 2 GB sınırında çalıştırır. `paycoreLLM/CLAUDE.md:39-42` gerçek açık eksiği “Langfuse entegrasyonu (config var, gönderen kod yok)” diye tanımlar.

PoC ihtiyacı v3 migration’ı veya prompt yönetim ürünü değil, mevcut trace’in gönderilmesidir. v3 ayrıca ClickHouse/MinIO/worker ile bellek ve offline paket yükünü büyütür.

**Düzeltme:** `02p` yalnız `rag/trace.py` verisini mevcut Langfuse v2’ye secret/PII taşımadan göndermeli, Langfuse kapalıyken açık `trace_delivery_failed` kaydı üretmeli ve cevap akışını durdurmamalı. V3 yükseltmesi ayrı, ölçülmüş migration işi olmalı.

### M4 — Yeni Next.js yönetim ve chat yüzeyi PoC için mevcut Open WebUI’ı yeniden inşa ediyor

**Brief alıntıları:** `plan/10-yonetim-onyuzu.md:3` PoC için toplam 9 günlük 10a+10b ister; `plan/11-chat-arayuzu.md:7` aynı Next.js içinde ayrı `/chat` ister.

**Mevcut uygulama kanıtı:** `paycoreLLM/CLAUDE.md:177-180` Jira’yı birincil, Open WebUI v0.11.3’ü test/manuel ikincil arayüz olarak seçmiştir. `paycoreLLM/compose.yml:207-235` Open WebUI’ı doğrudan mevcut `/v1` API’sine bağlar.

PoC’de ikinci web uygulaması yaklaşık 12 agent-gününü ürünün kanıtlanmayan kısmına harcar. Ayrıca auth sınırını iki yerde çözmeye zorlar.

**Düzeltme:** 10 ve 11 PoC’den çıkarılmalı. Demo Open WebUI ile yapılmalı; kaynaklar ve aşama izleri mevcut OpenAI-uyumlu cevapta korunmalı. Yalnız Open WebUI’ın gösteremediği kritik bir kabul kriteri kanıtlanırsa küçük bir yönetim endpoint’i eklenebilir; yeni tasarım sistemi kurulmaz.

### M5 — 08’in tam PII/NER sistemi yerel PayCore Faz 1’in kritik yolunda değil

**Brief alıntısı:** `plan/08-guardrail-pii.md:21` Presidio ve gerçek Türkçe NER modelini; `:32` Redis’te token eşlemesini; `:63` 100 cümlelik recall kapısını ister.

PayCoreLLM’de belge ve model kurum içinde kalır (`paycoreLLM/CLAUDE.md:12-14`); PoC dış sağlayıcıya egress yapmayacaktır. Buna rağmen secret sızıntısı ve trace içeriği korunmalıdır.

**Düzeltme:** Tam 08 PoC’den çıkarılmalı. PoC’ye yalnız secret redaction, log/trace gövdesi politikası ve girdide açıkça yasak veri sınıflarını reddeden deterministik kontrol alınmalı. Presidio, Türkçe NER, reversible tokenization ve Redis eşlemesi gerçek LLMaaS egress profiline geçerken eklenmeli.

### M6 — Mevcut Faz 1 eksikleri yeni platform özelliklerinden önce kapanmalı

**İlgili brief alıntısı:** `plan/13-ornek-veri-demo.md:3` yeni 35 soruluk ve üç profilli kabul setini PoC kapısı yapar.

**Mevcut uygulama kanıtları:** `paycoreLLM/CLAUDE.md:37-42` açık işleri eşzamanlılık donması, Langfuse gönderimi, kalan kaynaklar ve S1/S2 eval olarak listeler. `paycoreLLM/src/paycore_llm/prsim/pipeline.py:76-83` benzer kayıt araması ve kriter belgesini hâlâ `TODO`/boş döndürür. Mevcut eval koşucusu hata alan soruyu durdurmadan kayıt altına alır (`src/paycore_llm/eval/run.py:120-176`).

Yeni sentetik SQL demosu, ana ürün akışının tamamlanmadığını gizler.

**Düzeltme:** PoC kapısı mevcut S1/S2 seti ve PayCore senaryoları olmalı: S1 kaynak doğruluğu ≥ %80, S2 sınıflandırma ≥ %85, her hata görünür, Jira yazma bayrağı kapalı. PRSIM’in `similar_requests` ve `criteria_document` eksikleri bu kapıdan önce tamamlanmalı. Gerçek eval verisi bu incelemede açılmadı.

## 3. MINOR bulgular

### N1 — Profil dili entegrasyon brief’inde açıkça `airgap` olarak sabitlenmeli

`PLAN.md:59` `.env.example` varsayılanını `llmaas` yapar; `paycoreLLM/CLAUDE.md:12-14` ise tamamen local ve dış API’siz sistemi tanımlar. Bu entegrasyon PoC’sinde `DEPLOY_PROFILE=airgap` açık kabul olmalı. Genel FFCore ürün varsayılanının değiştirilmesi gerekmez.

### N2 — Sağlık ve readiness kavramları mevcut uçlarla eşlenmeli

`plan/00-depo-iskeleti.md:16` `/healthz`, `plan/04-bilgi-tabani.md:5` `/readyz` ister; mevcut uygulama yalnız `/health` sunar (`paycoreLLM/src/paycore_llm/api.py:389-391`). PoC brief’i yeni isim üretmeden önce geriye uyumlu alias mı, tek standart mı kullanılacağını söylemeli. **Öneri:** `/health` liveness olarak kalsın, bağımlılık/model kontrolleri için additive `/readyz` eklenip deploy smoke buna bağlansın.

Küçük yazım/biçim notları PoC kritik listesine alınmadı.

## 4. Brief’ler arası çelişkiler

| No | Brief A | Brief B / mevcut sözleşme | Alıntı | Öneri |
|---|---|---|---|---|
| C1 | 00 | PayCoreLLM compose | 00:7 yeni Postgres+pgvector/Redis/Ollama/LiteLLM/Langfuse; `compose.yml:77-235` çalışan API/worker/Qdrant/Postgres/Ollama/Langfuse/Open WebUI | 00’ı entegrasyon tabanı olarak yeniden yaz; ikinci yığın kurma. |
| C2 | 04 | PayCoreLLM teknoloji kararı | 04:35 “Redis ... arq”; `CLAUDE.md:179` “Postgres tablosu + Python worker; Redis/Celery yok” | PoC’de mevcut kuyruk; genel arq göçü ertelensin. |
| C3 | 04 | PayCoreLLM teknoloji kararı | 04:5 `PgVectorStore`; `CLAUDE.md:173-174` Qdrant + DuckDB/Parquet | Qdrant/DuckDB tek kaynak; pgvector göçü yok. |
| C4 | 05/06/07/13 | PayCoreLLM Faz 1 | 05:5 mcp-sql, 06:10 LangGraph, 07:18 interrupt/resume, 13:21 SQL/onay; `CLAUDE.md:31-35` Senaryo 3 için kod/altyapı yasağı | Bu dört akışı PoC’den çıkar. |
| C5 | 10/11 | PayCoreLLM arayüz kararı | 11:7 yeni Next.js `/chat`; `CLAUDE.md:177-178` Jira + Open WebUI | Open WebUI’ı kullan; yeni UI ertelensin. |
| C6 | 12 | 12’nin kendi kapsam etiketi | 12:3 “PoC: hayır”; 12:21 yalnız frontend/backend portları dışa açık | Tam 12 ertelensin, fakat secret/port/offline smoke alt dilimi PoC’ye alınsın. |

## 5. Felsefe ihlalleri

| No | İlke | Brief | Alıntı / sorun | Öneri |
|---|---|---|---|---|
| F1 | ARCH-09 | 00, 04 | 00:7 ikinci altyapı yığını; 04:35 Redis/arq; mevcut Qdrant/DuckDB/Postgres kuyruğu aynı işi yapıyor | Mevcut bileşenleri sar, yeniden inşa etme. |
| F2 | ARCH-09 | 10, 11 | 10:3 ve 11:7 özel Next.js yüzeyleri; mevcut Open WebUI `/v1`e bağlı | PoC demosunu Open WebUI ile yap. |
| F3 | ARCH-07 | 05, 06, 07 | Genel MCP + LangGraph + approval motoru, tek sabit RAG/PRSIM akışı için çekirdeği büyütüyor | Faz 2 kararı ve gerçek ikinci araç gelene kadar çıkar. |
| F4 | ARCH-10 | 00 / PLAN profili | `plan/00:18` sessiz varsayılan `llmaas`; PayCore hedefi airgap | Entegrasyon brief’inde `airgap` açık, doğrulanan profil olsun. |
| F5 | ARCH-06 | compose güvenliği | `compose.yml:35,127,194-197` `CHANGE_ME` ile ayağa kalkabiliyor | Eksik secret’ta startup açık hata versin. |
| F6 | ARCH-06 | PayCore profil yükleme | `src/paycore_llm/router/profiles.py:88-100` bozuk/eksik profili loglayıp genel aramaya devam ediyor | PoC’de seçili profil istenmişse fail-loud; yalnız otomatik genel kullanımda açık uyarıyla devam. |

## 6. Süre ve dalga değerlendirmesi

### S1 — Revize PoC süresi

| İş | Tahmin (agent-günü) | Gerekçe |
|---|---:|---|
| P1 entegrasyon tabanı/regresyon | 1-2 | Mevcut servis ve veri sözleşmesini dondurma, smoke tabanı. |
| P2 API auth + minimal audit/veri sınırı | 3-5 | Open WebUI kimlik aktarımı belirsiz; en az servis anahtarı ve negatif güvenlik testleri. |
| P3 compose hardening | 1-2 | Secret fail-loud, portlar, iç ağ ve konfigürasyon testleri. |
| P4 RAG eşzamanlılık/readiness | 2-4 | CPU-bound embedding/reranker donması ve bağımlılık sağlık kontrolleri. |
| P5 Langfuse v2 trace gönderimi | 1-2 | Yeni yığın yok; mevcut trace’in güvenli aktarımı. |
| P6 PRSIM TODO’ları ve Jira gate testi | 2-3 | Benzer kayıt/kriter entegrasyonu ve gerçek yazmayı engelleyen test. |
| P7 mevcut S1/S2 eval + rapor | 2-4 | Koşu süresi uzun; dataset bu incelemede doğrulanmadı. |
| P8 offline kurulum/smoke | 1-2 | Mevcut Nexus ve teslim belgeleri büyük ölçüde hazır. |
| P9 Open WebUI e2e demo | 1 | Yeni UI yok; mevcut `/v1` akışı. |

Toplam **14-25 agent-günü**; tek işçiyle yaklaşık **3-5 hafta**, iki işçiyle bağımlılık ve review payı dahil **2-3 hafta**. Bu, mevcut planın yaklaşık 51 agent-günlük PoC’sinden küçüktür; azalma özelliklerin “kolay sayılmasından” değil LiteLLM, pgvector, Redis/arq, LangGraph, MCP/SQL, Next.js ve tam PII platformunun çıkarılmasından gelir.

### S2 — Revize dalga ve kritik yol

1. **Dalga P0:** P1; mevcut regresyon ve veri yedeği/geri dönüş noktası.
2. **Dalga P1:** P2 ve P3 paralel; güvenlik sınırı kapanmadan demo verisi açılmaz.
3. **Dalga P2:** P4, P5 ve P6 paralel; hepsi mevcut mimari üzerinde.
4. **Dalga P3:** P7; S1/S2 kapıları. Başarısızsa yeni özellik eklenmez, mevcut zincir düzeltilir.
5. **Dalga P4:** P8 ve P9; offline temiz kurulumdan Open WebUI demosu.

Kritik yol **P1 → P2/P3 → P4/P6 → P7 → P8/P9**’dur. 01, tam 02, tam 03, pgvector 04, 05, 06, 07, tam 08, 09, 10, 11, tam 12 ve 13’ün SQL/agent bölümü bu PoC’nin kritik yolunda değildir. 14-17 zaten PoC dışıdır.

## 7. Katılmadığım kararlar (KARARLAR’daki) ve gerekçem

### K1 — Bu entegrasyon PoC’sinde `llmaas` varsayılanına katılmıyorum

`KARARLAR.md:7`: “Ürün varsayılanı `llmaas` ... `airgap` ikincil profil”. Genel ürün kararı olarak itiraz etmiyorum; fakat PayCoreLLM uygulama hedefi internet çıkışı olmayan, tamamen yerel sistemdir. Bu PoC’yi `llmaas` ile koşturmak yanlış sistemi test eder. **Kararım:** genel varsayılan korunur, PayCore entegrasyonunun test/deploy profili açıkça `airgap` olur.

### K2 — Bu uygulama için pgvector varsayılanını uygulamaya katılmıyorum

`KARARLAR.md:38`: “pgvector varsayılan, Qdrant ikinci sürücü”. PayCoreLLM’de çalışan indeks, hybrid dense+sparse davranışı ve mevcut veri Qdrant’tadır. PoC’de varsayılanı değiştirmek ürün doğrulaması değil veri platformu göçüdür. **Kararım:** PayCore entegrasyonunda Qdrant birincil kalır; genel FFCore kararı değiştirilmez.

### K3 — “Monorepo, bu klasör” kararı yeni uygulama dizini kararıyla geçersiz kaldı

`KARARLAR.md:46`: “Monorepo, bu klasör.” Kullanıcının bu incelemeye esas yeni kararı uygulama dizinini kardeş `paycoreLLM` olarak belirledi. İki kökü aynı anda kaynak kabul etmek işçi touch-zone’unu belirsizleştirir. **Kararım:** ffcore plan/karar deposu olabilir; çalıştırılabilir kod ve deployment değişikliklerinin tek sahibi `paycoreLLM` olmalıdır. Bu tersine karar KARARLAR’a yazılmadan işçi brief’i dağıtılmamalıdır.

Reddedilen kararlar yeniden önerilmedi. `state/BLOCKERS.md` içindeki LiteLLM/Langfuse v3 doğrulama maddeleri yeni bulgu yapılmadı; ilgili bileşenler bu PoC kesiminden çıkarıldığı için kritik yolu bloke etmiyor.

## 8. Doğrulanmamış iddialar listesi

### U1 — Open WebUI son kullanıcı kimliği aktarımı

Open WebUI v0.11.3’ün backend’e güvenilir, imzalı kullanıcı kimliği veya kullanıcıya özel token iletip iletmediği izin verilen kaynaklarda **doğrulanmadı**. P2’nin kesin audit aktörü bu doğrulama olmadan kişi olarak tasarlanmamalı.

### U2 — Langfuse v2 trace API/SDK uyumu

Mevcut imajın tam alt sürümü, Python SDK sürümü ve desteklediği ingest API’si izin verilen dosyalarda **doğrulanmadı**. P5 başlamadan çalışan konteyner/sürüm lock’u üzerinden doğrulanmalı; v3 varsayılmamalı.

### U3 — Mevcut gerçek S1/S2 sonuçları

Top-level `eval/` kullanıcı talimatıyla açılmadı. Dataset büyüklüğü, son skorlar ve çalışma süresi **doğrulanmadı**; yalnız `src/paycore_llm/eval/run.py` koşucu kodu incelendi.

### U4 — Server override’daki nihai port ve bind davranışı

İzin verilen referanslar `compose.server.yml` kullanımını anlatıyor, ancak kullanıcı PayCoreLLM için yalnız `compose.yml` okunmasına izin verdi. Override’ın host portlarını kapatıp kapatmadığı **doğrulanmadı**. B4, base compose’un tek başına güvenli olmadığı bulgusudur.

### U5 — Çalışan sistemin regresyon durumu

Bu çalışma belge/kod incelemesidir; konteynerler başlatılmadı, test ve eval koşulmadı. Mevcut API, Qdrant, Ollama, Jira ve Langfuse’un şu anda sağlıklı olduğu **doğrulanmadı**.

### U6 — Kimlik ve veri sınırı gereksiniminin nihai kapsamı

PoC’nin yalnız tek ekip/tek bilgi alanı mı, yoksa FFCore’daki çok proje/rol izolasyonunu mu göstereceği yeni kullanıcı kararında belirtilmedi. V10, süreyi korumak için **tek tenant + güçlü servis sınırı** kabulünü seçmiştir; çok-proje izolasyonu **doğrulanmış gereksinim değildir** ve PoC sonrasına bırakılmıştır.
