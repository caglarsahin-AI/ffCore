# FFCore brief incelemesi v6 — PoC odaklı

## 0. Özet

1. **Paket 00 ile kodlamaya başlanabilir; PoC bütününe henüz başlanamaz.** B1-B4 çözülmeden sonraki kritik zincir güvenilir PR'lara ayrılamıyor.
2. En ağır sorun B1: ortak tablo kolon sözleşmesi ile PoC brief şemaları bağdaşmıyor; 03 migration'ı tek anlamlı biçimde yazılamaz.
3. B3 nedeniyle 01 ve 05, kendilerinden sonra gelen 06'nın tablosunu kendi kabul kapısı yapıyor.
4. Güvenlikte yalnız PoC'yi doğrudan etkileyen konu tutuldu: kullanıcı tanımlı outbound adreslerde SSRF, egress ve timeout sözleşmesi eksik.
5. Hafıza, kanallar, üretim bağlayıcıları, tam airgap paketleme, ince UI ve terminoloji bulguları PoC kritik listesinden çıkarıldı.

### PoC kapsamı ve brief kararı

PoC, **M1–M3** olarak alınmıştır: 00, 03a/03b, 01, 02, 04a, 05a, 06a, 07, gerekli 10 ekranları, 11 ve daraltılmış 13a demo. 08, 06'nın zorunlu güvenlik bağımlılığı olduğu için kalır. Tam 09, 12 ve 14–16 PoC sonrasıdır.

| Brief | PoC kararı | Gerekçe |
|---|---|---|
| 00 | Başlanabilir | PoC başlangıcı; kritik belirsizlik yok. |
| 01 | Bloke | B3: 03a bağımlılığı ve 06 run_events kabulü düzelmeli. |
| 02 | Bloke | B4: .env yazma güvenlik sözleşmesine aykırı. |
| 03 | Bloke | B1 ve M2: şema ve güvenli outbound istemcisi net değil. |
| 04a | Bloke | M1: embedding boyutu davranışı çelişkili. |
| 04b | PoC sonrası | Qdrant, video, rewrite ve gelişmiş raporlama zorunlu değil. |
| 05a | Bloke | B3 ve M2: 06 tablosuna ters bağımlılık ve outbound güvenliği. |
| 05b | PoC sonrası | OpenAPI→MCP yayınlama ve Superset ertelenebilir. |
| 06a | Bloke | M3: context ve limit ihlali fail-loud değil. |
| 06b | PoC sonrası | Facade ve manifest ilk iç demo için zorunlu değil. |
| 07 | Bağımlılıklar sonrası | SQL onay akışı için gerekli. |
| 08 | Bloke | B2: 03'e bağımlıyken aynı dalgada bağımsız gösteriliyor. |
| 09 | PoC sonrası | Tam eval ürünü M4 işidir; DECISION-4 yeniden sorulmadı. |
| 10 | Daraltılarak | M4: yalnız PoC ekranları iki PR'a ayrılmalı. |
| 11 | Bağımlılıklar sonrası | M3 chat demosu için gerekli. |
| 12 | PoC sonrası | Üretim ve offline paketleme. |
| 13 | Daraltılarak | M5: yalnız 13a M3 smoke/demo. |
| 14 | PoC sonrası | Hafıza M6. |
| 15 | PoC sonrası | Kanallar M7. |
| 16 | PoC sonrası | Kaynaklar M7; PoC elle yüklemeyle kanıtlanabilir. |

## 1. BLOCKER bulgular

### B1 — Ortak tablo kolonları sözleşmesi uygulanabilir değil

**Brief alıntıları:**

- plan/03-backend-cekirdek.md:25: “users(id, email, password_hash, full_name, is_active, created_at)”
- plan/04-bilgi-tabani.md:17: “documents(id, kb_id, filename, ... updated_at_source, ... convert_seconds)”

**Çelişen cümle:** handbook/CONTRACTS.md:9 “Her yeni tablo bunlara uyar” der ve kolonları “id, project_id, created_at, updated_at, created_by, deleted_at” olarak dondurur. PLAN.md:171 de “Her tablo” der.

Global users, child documents/chunks ve append-only event tablolarına aynı kolon setini uygulamak iki proje kapsamı kaynağı veya gereksiz tekrar üretir. Şema listelerinin tam mı özet mi olduğu da belli değildir.

**Düzeltme:** C3 koddan önce değişmeli: altı kolon proje-sahipli aggregate root tablolarında zorunlu olmalı; global, saf join, child ve append-only tablolar adlandırılmış istisna listesine girmeli ve proje kapsamını hangi FK zincirinden aldığı yazılmalı. Sonra PoC tabloları tam kolon listeleriyle güncellenmeli. Her tabloya körlemesine project_id eklemeyi reddediyorum.

### B2 — 08 aynı anda 03'e bağımlı ve Dalga 2'de bağımsız olamaz

**Brief alıntısı:** plan/08-guardrail-pii.md:3: “Bağımlılık: 03. ... Dalga: 2 (bağımsız geliştirilir...)”.

**Çelişen cümleler:** PLAN.md:215 “03a, 03b, 08 (birbirinden bağımsız...)”; handbook/EXECUTION_HANDBOOK.md:23 “bağımlı paketler MERGED”.

08 proje kimliği ve audit davranışı kullanır. 03 aynı dalgada birleşmemişken READY değildir.

**Düzeltme:** 08, 03a+03b sonrasında Dalga 3'e taşınmalı ve 06a'dan önce bitmelidir. 04a ile paralel yürüyebilir. Güvenlik katmanını varsayımsal auth/audit mock'larıyla geliştirmeyi önermiyorum.

### B3 — 01 ve 05 sonraki paket 06'nın tablosunu kabul kapısı yapıyor

**Brief alıntıları:**

- plan/01-litellm-gateway.md:3: “Bağımlılık: 00, 03”.
- plan/01-litellm-gateway.md:49: “run_events'te fallback olayı görünür”.
- plan/05-arac-katmani-mcp.md:68: “Her araç çağrısı 06'daki run_events ... görünür”.

PLAN.md:192 01'i 00+03a sonrasına, PLAN.md:196-197 05a'yı 06a'dan önce koyar. PR kapısında run_events yoktur.

**Düzeltme:** 01 bağımlılığı 03a olmalı. 01 fallback kararını typed olayla, 05a MCP çağrısını kendi servis kaydıyla test etmeli. Bunların 06 run_events'e yansıması 06a kabul kriterine taşınmalı. 06 tablosunu erkenden yaratmayı reddediyorum.

### B4 — 02 .env yazmayı zorunlu kılıyor

**Brief alıntısı:** plan/02-langfuse-izleme.md:11: “Anahtarlar .env'e yazılır.”

**Çelişen cümleler:** handbook/SECURITY_AND_PERMISSIONS.md:6 “.env'i kullanıcı doldurur; agent .env yazmaz”; satır 33 “.env yazma, secret üretme yasak”.

PoC olması secret politikasını gevşetmez.

**Düzeltme:** init.sh .env değiştirmemeli. Bootstrap'i kullanıcı çalıştırmalı, değer yalnız bir kez kullanıcıya gösterilmeli ve .env kullanıcı tarafından doldurulmalıdır.

## 2. MAJOR bulgular

### M1 — 04a embedding boyutu uyuşmazlığına hem uyarı hem hata diyor

**Brief alıntıları:**

- plan/04-bilgi-tabani.md:16: “models.embed_dim ... uyuşmazsa model kaydı uyarı verir.”
- plan/04-bilgi-tabani.md:105: “Embedding boyutu ... eşleşmezse yükleme net hata verir.”

plan/03-backend-cekirdek.md:59 aynı durumu 400 olarak tanımlar. Uyarıyla devam pgvector kolonunu ilk ingest'te kırar.

**Düzeltme:** Tek davranış model kayıt anında HTTP 400 embedding_dimension_mismatch olmalıdır. Model aktive edilmemeli ve ingest'e ulaşmamalıdır.

### M2 — PoC outbound çağrılarında SSRF ve egress sözleşmesi eksik

**Brief alıntıları:**

- plan/03-backend-cekirdek.md:35-36: webhook gönderici ve default_webhook_url.
- plan/05-arac-katmani-mcp.md:20,30: httpx çağrısı ve kullanıcı tanımlı upstream_base_url.

handbook/SECURITY_AND_PERMISSIONS.md:40 timeout, llmaas allow-list ve özel IP engelini zorunlu kılar. Redirect sonrası kontrol, DNS rebinding ve özel IP testleri yoktur.

**Düzeltme:** 03 ortak SafeOutboundClient teslim etmeli: URL parse, DNS çözümleme, her redirect'te IP kontrolü, profil allow-list, connect/read/total timeout ve secret-free hata. 05a yalnız bunu kullanmalı. Kabul testleri loopback, RFC1918, link-local, DNS rebinding ve izin-listesi dışı alan adını reddetmelidir.

### M3 — 06a bağlam ve limit ihlalinde fail-loud değil

**Brief alıntıları:**

- plan/06-agent-runtime.md:54: “OLLAMA_CONTEXT_LENGTH ile tutarsızsa açılışta uyarı.”
- plan/06-agent-runtime.md:84: “aşımda finalize zorlanır.”

plan/00-depo-iskeleti.md:39 bağlam uzunluğunu zorunlu doğrular. PoC CPU ölçümünde context uyumsuzluğu yanlış kalite sonucu; zorla finalize kısmi cevabı başarı gibi üretir.

**Düzeltme:** Eksik veya yetersiz context ayarında /readyz 503 context_configuration_invalid vermeli. Araç, tur veya süre aşımında run açık limit_reached terminal durumuyla kapanmalı; SSE error ve run_events neden taşımalıdır.

### M4 — 10 tek PoC PR'ı olarak iki dalgaya yayılamaz

**Brief alıntıları:** plan/10-yonetim-onyuzu.md:3 “Dalga: 3 (iskelet), 5 (kalan)”; satır 61 tek teslimatta giriş, proje, belge, agent ve onay Playwright akışlarını ister.

KARARLAR.md:40 her pakete tek PR der. Dalga 3'ten 5'e açık PR review ve rollback sınırını bozar.

**Düzeltme:** İki PR: 10a giriş, proje, tema ve 03 ekranları; 10b-poc belge yükleme/arama, araç keşfi, agent formu, run/onay görünümü. Analitik dashboard'lar, MCP yayınlama, kaynak, kanal ve hafıza ekranları PoC sonrasına çıkmalıdır.

### M5 — 13'ün PoC ile tam ürün kabulü ayrılmamış

**Brief alıntısı:** plan/13-ornek-veri-demo.md:3: “Bağımlılık: tüm paketler. ... Dalga: 6.”

BASLATMA.md:65 13'ü M3 için Dalga 5'e koyar. Tüm paketler birleşmiş olmalıysa M3'te READY olamaz. 35 soruluk eval ve üç profil matrisi PoC smoke ile aynı iş değildir.

**Düzeltme:** 13a-poc yalnız gerekli 00-11 alt paketlerine bağlı olmalı ve şu akışı kanıtlamalı: seed, belge ingest, kaynaklı RAG cevabı, salt-okunur SQL, onay interrupt/resume, PII maskesi ve audit. 35 soruluk tam set ve üç profil kalite kapısı 13b olarak M4/M5'e kalmalıdır.

## 3. MINOR bulgular

PoC başlangıcını veya güvenli demosunu etkilemeyen MINOR bulgu tutulmadı. Terminoloji, ekran adı, tema ayrıntısı ve doküman biçimi notları PoC sonrası review'a bırakıldı; çözülmüş sayılmadı.

## 4. Brief'ler arası çelişkiler

| No | Brief A | Brief B | Alıntı | PoC önerisi |
|---|---|---|---|---|
| C1 | 01 | 06 | 01:49 run_events.fallback; 06:18-19 tablonun sahibi 06. | B3: 01 olay üretir, 06 projekte eder. |
| C2 | 04 | 03 | 04:16 “uyarı”; 03:59 “400 döner”. | M1: yalnız 400. |
| C3 | 05 | 06 | 05:68 05 kabulünde 06 tablosu; 06:19 tablo 06'ya ait. | B3: entegrasyon testi 06a'ya. |
| C4 | 13 | BASLATMA | 13:3 tüm paketler/Dalga 6; BASLATMA:65 M3/Dalga 5. | M5: 13a-poc ve 13b. |

## 5. Felsefe ihlalleri

| No | İlke | Brief | Alıntı | PoC önerisi |
|---|---|---|---|---|
| F1 | ARCH-06 | 06 | satır 54 context uyumsuzluğu yalnız uyarı | M3: readiness 503. |
| F2 | ARCH-06 | 06 | satır 84 limitte zorla finalize | M3: açık terminal hata. |
| F3 | ARCH-09 | 04 | satır 35 “arq ya da rq” | PoC yalnız PLAN standardı arq kullanmalı; brief temizlenmeli. |
| F4 | ARCH-10/06 | 01 | fallback açık kayda bağlı, fakat kabul 06 tablosuna bağlı | Açıklık korunmalı, kayıt sahipliği B3'e göre ayrılmalı. |

## 6. Süre ve dalga değerlendirmesi

### S1 — PoC süre tahmini

| PoC işi | PLAN | Tahmin | Gerekçe |
|---|---:|---:|---|
| 00 | 1 | 1,5-2 | Compose, Langfuse servisleri ve smoke. |
| 03a+03b | 6 | 8-10 | Auth, iki migration, audit, temel kota, outbound güvenliği. |
| 01 | 1,5 | 2,5-3,5 | DB model API, seed, fallback ve stream testi. |
| 02 | 0,5 | 1-1,5 | Init, callback, trace ve maliyet. |
| 04a | 5 | 7-9 | Dönüşüm, pgvector/BM25, reranker ve ACL. |
| 08 PoC çekirdeği | 5 | 5-7 | Deterministik PII, hook ve fail-closed; tam NER M4. |
| 05a | 3 | 4-5 | MCP, iki servis, SQL güvenliği ve SSRF. |
| 06a | 4,5 | 6-8 | LangGraph, checkpoint, SSE, queue ve bütçe. |
| 07 | 1,5 | 2-3 | Resume, TTL ve RBAC. |
| 10a+10b-poc | 10'un alt kümesi | 7-9 | Yalnız demo ekranları. |
| 11 | 2,5 | 3-4 | Chat, SSE recovery ve kartlar. |
| 13a-poc | 13'ün alt kümesi | 2-3 | Seed ve tek e2e demo akışı. |

PoC orta tahmini **55-60 agent-günü**; üç işçi ve review/merge kapılarıyla **25-30 iş günü**dür. PLAN'ın yaklaşık 20 günlük kritik yolu kendi rakamlarıyla bile en az 23 gündür.

### S2 — PoC dalga sırası

1. Dalga 1: 00.
2. Dalga 2: 03a ve 03b; 10a yalnız birleşmiş 03 yüzeylerine göre.
3. Dalga 3: 01; ardından 02 ve 04a; 08 tam 03 sonrası 04a ile paralel.
4. Dalga 4: 05a, sonra 06a. 06a ayrıca 02 ve 08'i bekler.
5. Dalga 5: 07 ve 11; ardından 10b-poc.
6. PoC kapısı: 13a-poc; temiz checkout, iki profil sahte model testi ve seçilmiş gerçek PoC profiliyle demo.

04b, 05b, 06b, tam 09, 12 ve 14-16 kritik yol dışındadır.

## 7. Katılmadığın kararlar (KARARLAR'daki) ve gerekçen

### K1 — Katılmadığım çözülmüş karar yok

PoC için de ikinci kuyruk, örtük fallback, Postman içe aktarma ve ayrı tool_invocations tablosunun reddine katılıyorum. Açık DECISION-1/2/3/4 yeniden sorulmadı. Tam 09 PoC dışında olduğu için DECISION-4 PoC başlangıcını bloke etmez.

## 8. Doğrulanmamış iddialar listesi

### U1 — LiteLLM çalışma zamanı API'si

plan/01-litellm-gateway.md:11 içindeki model API yolları, store_model_in_db ve akan stream'in kesilmemesi pinli sürümde **doğrulanmadı**.

### U2 — Langfuse init ve API

plan/02-langfuse-izleme.md:11,35 içindeki LANGFUSE_INIT değişkenleri ve trace API yolu pinli Langfuse v3'te **doğrulanmadı**. B4 bundan bağımsızdır.

### U3 — PoC model performansı

CPU RAG süresi, araçlı tur ve context bellek etkisi hedef PoC makinesinde yeniden ölçülmedi; **doğrulanmadı**. 13a kalite iddiası değil akış ve ölçüm kanıtı üretmelidir.

### U4 — Türkçe NER modeli

Model lisansı, imaja gömme hakkı ve recall/gecikme hedefleri **doğrulanmadı**. PoC'ta deterministik temel PII ve fail-closed hook zorunlu; ad-soyad kalibrasyonu M4'e bırakılabilir.

