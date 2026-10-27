# Brief İncelemesi v4 (kodlama öncesi)

**İnceleyen:** Bağımsız Gözden Geçirici Oturumu  
**Tarih:** 27 Ekim 2026  
**Kapsam:** `PLAN.md` 2.2, `KARARLAR.md`, `handbook/` (12 dosya), `plan/00-16` (17 brief), `state/BLOCKERS.md`, `BASLATMA.md`.  
**Referans:** PayCore deposu açılmadı; hiçbir bulgu ona dayanmıyor.  
**Derecelendirme:**  
- **BLOCKER:** Bu haliyle kodlanamaz; bağımlılık, veri modeli veya güvenlik temeli eksik/kırık.  
- **MAJOR:** Kodlanır ama yanlış ürün çıkar, güvenlik açığı yaratır veya gizli degrade olur.  
- **MINOR:** Netleştirme, tek satırlık uyum/yazım düzeltmesi.  
*(Satır numaraları `cat -n` ve brief dosyalarının güncel hallerindendir).*

---

## 0. Özet

1. **Kodlamaya başlanabilir mi? Hayır; yalnızca Dalga 1 (00) başlayabilir.** Dalga 2 ve sonrası, B1–B7 düzeltilmeden açılmamalıdır: 03, 02, 01 ve 04a'nın kabul kriterleri daha sonraki dalgalarda doğan tablolara, istemcilere, şifreli anahtarlara ve örnek verilere bağlıdır. Bu haliyle paketler VERIFIED olamaz.
2. **En önemli güvenlik bulgusu (B5, güvenlik):** Facade'da `user` alanı (e-posta) `impersonate` kapsamı istenmeden son kullanıcıya eşlenmektedir (06:74, 06:76). `agents` kapsamlı herhangi bir API anahtarı `user: "admin@..."` göndererek admin ACL'siyle arama yapabilir ve admin hafızasını okuyabilir. Ayrıca 06:74 "ACL anahtarın proje rolüne göre" derken `api_keys` tablosunda `role` kolonu yoktur (03:30).
3. **En önemli mimari bulgu (B1 + B6, gateway & guardrail):** 03a dalga 2'de LiteLLM team'i açmak zorundadır ama istemci 01'de (dalga 3). Ayrıca `projects` tablosunda `litellm_team_key` saklama kolonu yoktur; backend facade LiteLLM'i team anahtarıyla yetkilendiremez. LiteLLM dışa kapatılmışken 08'deki `litellm_hook.py` (P3 kancası) gereksiz bir HTTP döngüsü ve dağıtım sorunu yaratmaktadır.
4. **En önemli planlama ve veri bulgusu (B4 + B7, kuyruk & örnek veri):** 04a, 05a, 09 ve 10'un kabul kriterleri 13'ün örnek verisine bağlıdır, ancak 13 dalga 6'dadır (13'ü 13a ve 13b olarak ikiye bölmek şarttır). 04:35'te ise reddedilen `rq` kütüphanesi geri getirilmiştir.
5. **Takvim ve Dalga:** Brief sayılarıyla bile kritik yol 20 değil ~23-28 gündür. Dalga kapıları ve gerçekçi süreler eklenince M3'e ~35 iş günü, projenin tamamı ~100 agent-günüdür (bölüm 6).

---

## 1. BLOCKER Bulgular

### B1. 03 ile 01 Döngüsel Bağımlı ve `projects.litellm_team_key` Kolonu Eksik (A, F, G)
- **Konum:** `plan/03-backend-cekirdek.md` satır 23, 28, 43, 44, 90 vs `plan/01-litellm-gateway.md` satır 17 vs `plan/06-agent-runtime.md` satır 74.
- **Alıntı (`03-backend-cekirdek.md:L28`):**  
  > `projects(id, key, name, description, litellm_team_id, created_by, ...)`
- **Alıntı (`03-backend-cekirdek.md:L43-44, L90`):**  
  > `Projects: CRUD; oluşturulunca LiteLLM team açılır. API keys: … LiteLLM key ile eşlenik.` / `Kota monthly_usd=0, block verilen projede LiteLLM key'i 429 döner.`
- **Alıntı (`01-litellm-gateway.md:L17` & `06-agent-runtime.md:L74`):**  
  > `06 runtime ve facade LiteLLM'i projenin team anahtarıyla çağırır (API anahtarının ham değeri backend'de yoktur)...`
- **Gerekçe:** 
  1. `litellm_client.py (create_team, create_key, set_budget …)` 01 paketinin teslimatıdır (01:17); 01 dalga 3'te, 03 dalga 2'dedir. 03 bu satırları kodlayamaz, 03:90'ı test edemez.
  2. 01:17 ve 06:74, backend facade ve runtime'ın LiteLLM'i çağırırken projenin team anahtarını kullanacağını emreder. LiteLLM API'si team anahtarını yalnızca oluşturma anında bir kez döner. `projects` tablosunda `litellm_team_id` vardır ama üretilen anahtarın saklanacağı `litellm_team_key_encrypted` kolonu tanımlanmamıştır. Bu kolon olmadan facade LiteLLM'e istek atamaz.
- **Önerilen Düzeltme:** 
  1. `plan/03-backend-cekirdek.md` satır 28'e `litellm_team_key_encrypted` (Fernet şifreli) kolonu eklenir; `litellm_team_id` nullable bırakılır.
  2. 03a dalga 2'de LiteLLM team'i açmaz. Team ve team anahtarı oluşturma, kota eşleme ve 03:90 testi 01 paketine taşınır (01 bunu proje açılış kancası olarak bağlar). 03:44'teki "LiteLLM key ile eşlenik" ifadesi silinir.
- **Kural:** ARCH-11, CONTRACTS C2/C3.

---

### B2. 02'nin Kapsam 7'si Dalga 3'te Var Olmayan Tablolara Yazıyor (A, F)
- **Konum:** `plan/02-langfuse-izleme.md` satır 18–25 vs `plan/06-agent-runtime.md` satır 18–19.
- **Alıntı (`02-langfuse-izleme.md:L18`):**  
  > `alanlar 06'nın runs/run_events listesinde tanımlıdır, bu paket doldurur ve Langfuse'a yansıtır.`
- **Alıntı (`02-langfuse-izleme.md:L19-25`):**  
  > `runs.status listesi abandoned içerir... runs.model_ms, tool_ms, retrieval_ms, unaccounted_ms, slowest_step... run_events.type guardrail_hook içerir... Agent sayfası Usage/Overview (10)...`
- **Gerekçe:** 02 paketi Dalga 3'te (0,5 gün), `runs` ve `run_events` tabloları ise Dalga 4'te 06a paketinde doğmaktadır. Olmayan tablonun alanlarını doldurmak, migration'ı yazılmamış modelin event türlerini tanımlamak touch-zone kuralına (MULTI_AGENT:30) ve dalga sırasına aykırıdır. 02 bu haliyle VERIFIED olamaz.
- **Önerilen Düzeltme:** 02:18–27 maddeleri 02 brief'inden çıkarılıp doğrudan `plan/06-agent-runtime.md` Kapsam'ına ("İzleme ve Oturum Alanları") taşınmalıdır. 02 yalnızca Langfuse compose init, `@observe` kütüphanesi (`core/tracing.py`) ve prompt client'ı teslim etmeli; süresi 0,5 gün kalmalıdır. 06a'ya +1 gün eklenmelidir.
- **Kural:** EXECUTION_HANDBOOK:23 (DoR), MULTI_AGENT:15.

---

### B3. 01'in Fallback Kabul Kriteri Ölçülemez ve Mekanizması Yok (A, C)
- **Konum:** `plan/01-litellm-gateway.md` satır 15 ve 49.
- **Alıntı (`01-litellm-gateway.md:L49`):**  
  > `llmaas seed'iyle birincil sağlayıcı kapatıldığında yalnızca chat-fallback kaydı varsa oraya geçer ve run_events'te fallback olayı görünür; kayıt yoksa 503.`
- **Gerekçe:** 
  1. `run_events` tablosu Dalga 3'te (01 sırasında) mevcut değildir.
  2. Fallback LiteLLM proxy'sinin içinde gerçekleşir. LiteLLM'in bir fallback yaptığını çağıran backend servisine nasıl ileteceği (HTTP response header mı, gövdedeki model alanı mı?) brief'te tanımlanmamıştır.
- **Önerilen Düzeltme:** 01 paketinde `litellm_client.py`, dönen yanıttaki `model` alanını (veya `x-litellm-model-id` başlığını) kontrol ederek `FallbackResult(used_fallback=True, target_model=...)` nesnesi döner ve bu unit test ile kanıtlanır. `run_events.fallback` veritabanı yazımı ve 01:49 kriterinin veritabanı doğrulaması Dalga 4'teki 06a paketine devredilir.
- **Kural:** TEST_STRATEGY:28, CLAUDE.md:19.

---

### B4. Örnek Veri Sahipliği Çıkmazı: Erken Dalgalar 13'e Bağımlı, 13 Dalga 6'da (A, F, G)
- **Konum:** `plan/04-bilgi-tabani.md` satır 96, 102 vs `plan/05-arac-katmani-mcp.md` satır 38, 46 vs `plan/09-evaluation.md` satır 72 vs `plan/13-ornek-veri-demo.md` satır 3, 11 vs `handbook/SECURITY_AND_PERMISSIONS.md` satır 16.
- **Alıntı (`04-bilgi-tabani.md:L96, L102`):**  
  > `data/samples/contracts/ içindeki örnek sözleşmelerle tests/test_ingest.py` / `"fesih bildirim süresi" sorgusu ilgili maddeyi ilk 3'te getirir (örnek belgeyle test).`
- **Alıntı (`05-arac-katmani-mcp.md:L46`):**  
  > `Hedef DB: data/samples/schema/ ile kurulan demo "agent sunum DB'si" (13'te doldurulur; bu pakette minimal seed).`
- **Alıntı (`13-ornek-veri-demo.md:L3, L11`):**  
  > `Dalga: 6.` / `Sözleşmeler: kullanıcının sağladığı örnek sözleşmeler data/samples/contracts/ altına (gizlilik kontrolü: ... içeriyorsa 08'deki maskeleme ile temizlenmiş kopya).`
- **Gerekçe:** `data/samples/` dizini 13'ün touch-zone'udur (MULTI_AGENT:36) ve 13 Dalga 6'dadır. Ancak Dalga 3'teki 04a ve Dalga 4'teki 05a bu dosyalar olmadan testlerini koşamaz ve kabul kriterlerini karşılayamaz. Ayrıca 13:11'deki "kullanıcının sağladığı sözleşmeler maskelenerek depoya girer" ifadesi, SECURITY:16'daki *"Örnek sözleşmeler ve şema sentetiktir; gerçek kurum belgesi oraya konmaz"* kuralını doğrudan çiğnemektedir.
- **Önerilen Düzeltme:** Paket 13 ikiye bölünmelidir:
  - **13a "Örnek Sentetik Veri":** Dalga 1'de test agent'ı tarafından hazırlanır (1 gün). 5 sentetik sözleşme (PDF+DOCX), demo hastane sunum şeması (`data/samples/schema/`), `superset.yaml` ve 100 cümlelik PII test seti üretilip commit edilir.
  - **13b "E2E ve Ölçüm":** Dalga 6'da (veya Dalga 5 sonunda) kalır; `make seed` ve `make e2e` komutlarını ve performans ölçümlerini tamamlar.
  - 13:11'deki gerçek belge ibaresi silinir; belgelerin %100 sentetik üretileceği yazılır.
- **Kural:** SECURITY_AND_PERMISSIONS:16, EXECUTION_HANDBOOK:23.

---

### B5. Facade Kimlik Eşlemesi ACL ve Hafızayı Delip Geçiyor (G, B, A)
- **Konum:** `plan/06-agent-runtime.md` satır 74 vs `plan/03-backend-cekirdek.md` satır 30 vs `handbook/SECURITY_AND_PERMISSIONS.md` satır 38.
- **Alıntı (`06-agent-runtime.md:L74`):**  
  > `Son kullanıcı: user alanı (e-posta) ya da X-On-Behalf-Of JWT'si (03b tanımı; yalnızca impersonate kapsamlı anahtarla) platform kullanıcısına eşlenir; KB ACL, hafıza ve audit aktörü bu kullanıcıdır. Eşleme yoksa aktör API anahtarının kendisidir: ACL anahtarın proje rolüne göre, hafıza kapalı, audit'te actor_type=api_key.`
- **Alıntı (`SECURITY_AND_PERMISSIONS.md:L38`):**  
  > `X-On-Behalf-Of yalnızca impersonate kapsamlı anahtar ya da SERVICE_TOKEN ile; aksi yok sayılır ve impersonation_denied audit'e düşer.`
- **Gerekçe:** 
  1. Güvenlik açığı: Cümle yapısı `impersonate` şartını yalnızca JWT'ye bağlamış gibi görünmektedir. Eğer dış istemci standart bir API anahtarıyla JSON gövdesinde `user: "ceo@hastane.com"` gönderdiğinde backend bunu doğrudan platform kullanıcısına eşlerse; `agents` kapsamlı herhangi bir istemci CEO'nun ACL'siyle kurumsal belgeleri aratabilir ve CEO'nun özel hafızasını (`memories`) okuyup sızdırabilir!
  2. Tanımsız alan: "Eşleme yoksa ACL anahtarın proje rolüne göre" denmektedir; ancak 03:30'da `api_keys` tablosunda hiçbir `role` kolonu tanımlanmamıştır. Bu kural kodlanamaz.
- **Önerilen Düzeltme:** 
  1. `user` alanının platform kullanıcısına eşlenmesi de **kesinlikle `impersonate` kapsamı** şartına bağlanmalıdır. Bu kapsam yoksa `user` alanı yalnızca LiteLLM'e giden bir log/audit etiketi olarak kalmalı, aktör olarak kabul edilmemeli ve audit'e `impersonation_denied` yazılmalıdır.
  2. `plan/03-backend-cekirdek.md` satır 30'daki `api_keys` tablosuna `acl_role: admin|developer|analyst` (varsayılan `analyst`) kolonu eklenmelidir.
- **Kural:** SECURITY_AND_PERMISSIONS:38, CONTRACTS C2, FELSEFE ARCH-06.

---

### B6. 08 Dalga 2'de LiteLLM Kancasını Kodlayamaz; Kancanın Gerekçesi Geçersizdir (F, D: ARCH-09/07)
- **Konum:** `plan/08-guardrail-pii.md` satır 3, 37, 38 vs `KARARLAR.md` satır 59 vs `PLAN.md` satır 163, 221.
- **Alıntı (`08-guardrail-pii.md:L3, L38`):**  
  > `Dalga: 2` / `(P3) Doğrudan model yolu da kapsanır: kurumun kendi uygulaması API anahtarıyla chat-default'a LiteLLM üzerinden gittiğinde de engine çalışır. Teslimat: backend/app/guardrails/litellm_hook.py, LiteLLM'in custom guardrail arayüzünü (CustomGuardrail, pre_call ve post_call) uygular, engine'i HTTP ile çağırır (POST /internal/guardrails/evaluate, yalnızca iç ağ); render-litellm (01) her modele proje politikasını guardrails: olarak yazar.`
- **Alıntı (`KARARLAR.md:L59` & `PLAN.md:L163`):**  
  > `Reddedilenler: Dış istemcilere LiteLLM sanal anahtarı vermek. Tek giriş kapısı facade'dır; kota, guardrail ve audit backend'de tek yerde (R1.2). LiteLLM team anahtarı yalnızca backend'de` / `Tek giriş kapısı (R1.2): dışa açılan tek adres backend facade (/v1/chat/completions, 06); LiteLLM iç ağda kalır.`
- **Gerekçe:** 
  1. Dalga uyuşmazlığı: 08 Dalga 2'dedir; 01 ve LiteLLM servisi Dalga 3'tedir. 08 işçisi henüz var olmayan LiteLLM konteynerine kanca yazamaz ve test edemez.
  2. Mimari çelişki: Kancanın varoluş sebebi "kurum uygulaması LiteLLM'e doğrudan gittiğinde koruma sağlamak" olarak yazılmıştır. Oysa KARARLAR:59 ve PLAN:163 dış istemcilerin LiteLLM'e erişimini yasaklamış, tek kapıyı backend facade yapmıştır. Facade (06:71) zaten doğrudan model çağrılarında da `input.pre` ve `output.pre` kancalarını çalıştırmaktadır. LiteLLM içine kanca koymak gereksiz bir çift HTTP döngüsü (facade -> LiteLLM -> backend hook -> LiteLLM -> model) yaratır (ARCH-09, ARCH-07).
- **Önerilen Düzeltme:** `litellm_hook.py`, LiteLLM `CustomGuardrail` entegrasyonu ve `POST /internal/guardrails/evaluate` uç noktası brief'ten tamamen çıkarılmalıdır (-0,5 gün). 08 Dalga 2'de saf kütüphane/motor olarak kalmalı (`engine.py`, PII tanıyıcıları, test paneli); graf kancaları 06a'da, doğrudan model kancaları 06b facade'da çağrılmalıdır.
- **Kural:** ARCH-07, ARCH-09, KARARLAR:59.

---

### B7. Kuyruk Altyapısında Kararla Çelişen `rq` Seçeneği (A, B)
- **Konum:** `plan/04-bilgi-tabani.md` satır 35 vs `KARARLAR.md` satır 53 vs `PLAN.md` satır 166.
- **Alıntı (`04-bilgi-tabani.md:L35`):**  
  > `Pipeline (Redis kuyruğu + worker süreci, arq ya da rq)`
- **Alıntı (`KARARLAR.md:L53` & `PLAN.md:L166`):**  
  > `Reddedilenler: İkinci kuyruk kütüphanesi (rq) | Tek kütüphane arq; iki kuyruk sistemi tutarsızlık riski (R10.8)` / `Kuyruk altyapısı (R10.8): tek kütüphane arq; 04 worker, 06 scheduler ve 16 senkron aynı Redis'te ayrı kuyruk adlarıyla (ingest, llm-interactive, llm-background, sync).`
- **Gerekçe:** 04 brief'i KARARLAR.md'de açıkça reddedilen `rq` kütüphanesini alternatif olarak sunmaktadır. İşçi `rq` seçerse, senkron/bloklayıcı bir worker kurulacak; 06 runtime scheduler'ı ve 16 senkron motoruyla kuyruk altyapısı paylaşılamayacak ve iki ayrı worker süreci gerekecektir.
- **Önerilen Düzeltme:** `plan/04-bilgi-tabani.md` satır 35'teki "`arq ya da rq`" ifadesi silinmeli, kesin olarak "`arq (kuyruk: ingest)`" yazılmalıdır.
- **Kural:** ARCH-09, FELSEFE META-01, KARARLAR:53.

---

## 2. MAJOR Bulgular

### M1. LiteLLM: İki Model Kaynağı ve Çalışırken Verilemeyen Sağlayıcı Anahtarı (B, C, D: ARCH-09)
- **Konum:** `plan/01-litellm-gateway.md` satır 11, 37 vs `plan/03-backend-cekirdek.md` satır 23 vs `plan/10-yonetim-onyuzu.md` satır 25.
- **Alıntı (`01-litellm-gateway.md:L11, L37`):**  
  > `Açılışta make render-litellm statik deploy/litellm/config.yaml üretir … Çalışırken … DB'li model yönetim API'siyle...` / `render-litellm anahtarları çözüp LiteLLM'e ortam değişkeni olarak verir (config dosyasına düz yazmaz)`
- **Alıntı (`03-backend-cekirdek.md:L23` & `10-yonetim-onyuzu.md:L25`):**  
  > `her değişiklik 01'deki render-litellm'i tetikler.` / `kayıt sonrası render-litellm tetiklenir`
- **Gerekçe:** 
  1. Çelişki: 03 ve 10 her model kaydında `render-litellm` tetikler derken, 01 ve PLAN 5 bunu yasaklamaktadır.
  2. Uygulanamaz kural: UI üzerinden çalışma zamanında eklenen yeni bir sağlayıcının API anahtarı, çalışan LiteLLM konteynerine ortam değişkeni olarak verilemez (çalışan sürecin env'i dinamik güncellenemez).
  3. Çift kaynak: Açılışta dosya, çalışırken DB kullanılırsa konteyner restart olduğunda modeller mükerrerleşir.
- **Önerilen Düzeltme:** `config.yaml` dosyasında `model_list` hiç yer almamalıdır (yalnızca genel LiteLLM ayarları kalmalıdır). `render-litellm` scripti, açılışta ve her sağlayıcı/model mutasyonunda çalışan bir **DB uzlaştırıcıya** (reconciler) dönüştürülmelidir. Anahtar LiteLLM DB API'sine (`POST /model/new`) doğrudan gövdede gönderilmeli; LiteLLM'in bunu kendi DB'sinde `LITELLM_SALT_KEY` ile şifrelemesi sağlanmalıdır. 03:23 ve 10:25 "uzlaştırıcıyı tetikler" olarak düzeltilmelidir.
- **Kural:** ARCH-09, ARCH-10, PLAN 5:161.

---

### M2. Zaman Aşımı Değerleri Üç Yerde Üç Farklı (B)
- **Konum:** `PLAN.md` satır 72 vs `plan/06-agent-runtime.md` satır 36, 135.
- **Alıntı (`PLAN.md:L72`):**  
  > `Zaman aşımı (LLM çağrısı / run) | llmaas: LLM çağrısı 60 s / run 120 s | CPU: LLM çağrısı 600 s / run 900 s; GPU: 120 s / 300 s`
- **Alıntı (`06-agent-runtime.md:L135` & `L36`):**  
  > `limits.timeout_s varsayılanı CPU'da 600, GPU'da 120.` / `"limits": {"timeout_s":300}`
- **Gerekçe:** 06 brief'i PLAN'daki "tekil çağrı" sürelerini (600 s) "tüm run" süresi (`timeout_s`) sanmıştır. CPU'da bir araçlı agent turu ~3 dakika sürerken 600 saniye run limiti 2 tur sonra run'ı zaman aşımıyla keser ve sistemi çalışmaz hale getirir.
- **Önerilen Düzeltme:** CHANGE_CONTROL:25 uyarınca PLAN.md kazanır. 06:135 şu şekilde düzeltilmelidir: `limits.timeout_s` varsayılanları: `llmaas` 120 s, `cpu` 900 s, `gpu` 300 s. 06:36 şemasındaki örnek değer `null` (profile göre otomatik) yapılmalıdır.
- **Kural:** CHANGE_CONTROL:25, PLAN:72.

---

### M3. MCP `forward_user`: Havuzlanan Oturum, Süresi Dolan JWT ve Sızıntı Riski (G)
- **Konum:** `plan/05-arac-katmani-mcp.md` satır 19, 24 vs `plan/03-backend-cekirdek.md` satır 37.
- **Alıntı (`05-arac-katmani-mcp.md:L19, L24`):**  
  > `MCP istemcisi … streamable HTTP taşıma; bağlantı havuzu` / `forward_user (çağıran kullanıcının kimliği X-On-Behalf-Of ve imzalı kısa ömürlü JWT ile iletilir)`
- **Alıntı (`03-backend-cekirdek.md:L37`):**  
  > `exp ≤ 5 dk, aud=internal`
- **Gerekçe:** 
  1. Bağlantı havuzu (connection pool) kullanılırsa, A kullanıcısı için açılan HTTP oturumu B kullanıcısının isteğinde tekrar kullanılabilir ve B kullanıcısı A'nın kimliğiyle mcp-search yapabilir.
  2. CPU'da run süresi 900 saniyedir; 5 dakikalık JWT run'ın ikinci turunda expire olur ve araç çağrısı 401 alır.
  3. `aud=internal` token'ı dış bir üçüncü taraf sisteme (Jira, SAP) `forward_user` ile iletilirse, o sistem bizim backend'imize o kullanıcı adına sızabilir.
- **Önerilen Düzeltme:** 
  1. `forward_user` yalnızca `ALLOWED_INTERNAL_HOSTS` içindeki FFCore servislerine (mcp-search) izinli olmalıdır.
  2. JWT oturum açılışında değil, **her araç çağrısında anlık** imzalanmalı ve `aud=<tool_key>` taşımalıdır.
  3. `forward_user` araçlarında bağlantı havuzu devre dışı bırakılmalıdır.
- **Kural:** SECURITY_AND_PERMISSIONS:38, CONTRACTS C2.

---

### M4. Facade Üzerinden Onay API Anahtarıyla Verilebiliyor (G, C)
- **Konum:** `plan/06-agent-runtime.md` satır 73 vs `plan/07-onay-kuyrugu.md` satır 14, 22.
- **Alıntı (`06-agent-runtime.md:L73`):**  
  > `istemci 07 API'si ile onaylayıp X-Resume-Run-Id ile devam eder.`
- **Alıntı (`07-onay-kuyrugu.md:L22`):**  
  > `onay yalnızca giriş yapmış kullanıcıyla verilir (e-posta linkinden doğrudan onay yok).`
- **Gerekçe:** Facade istemcisi bir dış sistem veya API anahtarıdır. API anahtarının kendi çağırdığı araca onay vermesi İnsan Onayı (HITL) ilkesini boşa çıkarır.
- **Önerilen Düzeltme:** `/approvals/{id}/approve` uç noktası yalnızca oturum açmış kullanıcı (cookie) ya da `impersonate` kapsamlı JWT taşıyan yetkili kullanıcı tarafından çağrılabilir. Facade istemcisi onay veremez; `approval_id` alır, insan onayı 10/11/15 ekranlarından verildikten sonra facade istemcisi yalnızca `X-Resume-Run-Id` ile akışı devam ettirir.
- **Kural:** TERMINOLOGY:52, ARCH-06.

---

### M5. SSRF ve Güvensiz Dosya Yolu Açığı (G)
- **Konum:** `plan/05-arac-katmani-mcp.md` satır 16, 30 vs `plan/16-veri-kaynaklari.md` satır 55 vs `handbook/SECURITY_AND_PERMISSIONS.md` satır 40–41.
- **Alıntı (`16-veri-kaynaklari.md:L55`):**  
  > `config.root, include_globs, exclude_globs`
- **Gerekçe:** 
  1. 05a'da `tools.endpoint_url` ve 05b'de `mcp_servers.upstream_base_url` kullanıcı girdisidir. SSRF filtresi ve test kriteri brief'te yoktur.
  2. 16'da ağ klasörü bağlayıcısı ekrandan serbest `config.root` almaktadır. Kötü niyetli bir kullanıcı `/app` veya `/` girerek `.env` dosyasını ve Fernet anahtarlarını bilgi tabanına indeksletebilir.
- **Önerilen Düzeltme:** 
  1. 03b'ye merkezi `core/egress.py` modülü eklenmeli; 05, 15 ve 16 tüm dış HTTP çağrılarını buradan yapmalıdır (özel IP'ler varsayılan bloklu, DNS rebinding korumalı).
  2. 16'da `config.root`, sunucudaki sabit bir `FS_SOURCES_BASE` kök dizinine göre göreli yol olmalı; `..` ile yukarı çıkışlar 400 ile engellenmelidir.
- **Kural:** SECURITY_AND_PERMISSIONS:40, 41.

---

### M6. Cookie Tabanlı Oturumda CSRF ve CORS Tanımsız (G)
- **Konum:** `plan/03-backend-cekirdek.md` satır 41 vs `plan/10-yonetim-onyuzu.md` satır 79 vs `handbook/SECURITY_AND_PERMISSIONS.md` satır 44.
- **Alıntı (`03-backend-cekirdek.md:L41`):**  
  > `POST /auth/login (JWT, httpOnly cookie), POST /auth/logout, GET /auth/me.`
- **Gerekçe:** Frontend ve backend compose'da ayrı portlarda yayınlanmaktadır (ayrı origin). `httpOnly` cookie kullanıldığında CORS `allow_credentials=True` gerekir ve tarayıcı istekleri CSRF saldırılarına açık hale gelir. Brief'lerde SameSite politikası ve CSRF koruması belirtilmemiştir.
- **Önerilen Düzeltme:** Frontend, backend API'sine Next.js `/api` rewrite (reverse proxy) üzerinden erişerek tek bir origin gibi davranmalıdır. Cookie `SameSite=Strict; Secure; HttpOnly` olarak ayarlanmalı; mutasyon uçlarında `X-CSRF-Token` başlığı zorunlu kılınmalı ve 03a kabul kriterlerine CSRF testi eklenmelidir.
- **Kural:** SECURITY_AND_PERMISSIONS:35.

---

### M7. `embed_dim` Uyuşmazlığında 400 Hata vs Uyarı Çelişkisi (B, ARCH-06)
- **Konum:** `plan/04-bilgi-tabani.md` satır 16 vs `plan/03-backend-cekirdek.md` satır 59.
- **Alıntı (`04-bilgi-tabani.md:L16`):**  
  > `03a'daki models.embed_dim ölçümü globalle uyuşmazsa model kaydı uyarı verir.`
- **Alıntı (`03-backend-cekirdek.md:L59`):**  
  > `(R2.7) models.embed_dim ölçümü globalle (EMBED_DIM) uyuşmazsa model kaydı 400 döner (uyarı değil; P5 kuralı). 04 ile aynı cümle.`
- **Gerekçe:** 03a 400 hatası üretirken 04 "uyarı verir" demektedir. Uyarı verilirse farklı boyutta model kaydedilir; pgvector kolonu (`vector(EMBED_DIM)`) boyutu uymayan vektör yazılırken veritabanı seviyesinde çöker (ARCH-06 Fail-loud ihlali).
- **Önerilen Düzeltme:** 04 satır 16'daki "uyarı verir" ifadesi "model kaydı 400 döner ve reddedilir" olarak düzeltilmelidir.
- **Kural:** ARCH-06, PLAN:16.

---

### M8. Kuyruk Tasarımı Belirsizliği: Öncelik ve Eşzamanlılık Yuvası (A, D: ARCH-09)
- **Konum:** `plan/06-agent-runtime.md` satır 58–65 vs `handbook/CONTRACTS.md` C10.
- **Alıntı (`06-agent-runtime.md:L58, L65`):**  
  > `tüm model çağrıları tek Redis kuyruğundan geçer ve iki sınıfa ayrılır: Etkileşimli... Etkileşimli-düşük... Arka plan...` / `worker etkileşimli işi arka plan işinin ortasında kesmez... bir sonraki arka plan çağrısını bekletir.`
- **Gerekçe:** C10'da iki LLM kuyruğu vardır (`llm-interactive`, `llm-background`). "Etkileşimli-düşük" işlerin hangi kuyrukta koşacağı belirsizdir. Ayrıca bir agent run'ının graf düğümleri çalışırken her LLM çağrısının ayrı bir arq işi olarak kuyruğa atılması LangGraph checkpoint döngüsünü bozar.
- **Önerilen Düzeltme:** 
  1. **Run Seviyesi:** Kullanıcı run'ları `llm-interactive` kuyruğuna, sınav ve hafıza işleri `llm-background` kuyruğuna girer. Etkileşimli-düşük işler `llm-background` kuyruğunda mesai penceresi kısıtı olmadan çalışan işlerdir.
  2. **Model Çağrısı Seviyesi:** Çalışan worker içindeki tekil model çağrıları, `litellm_client` seviyesinde Redis tabanlı bir **öncelikli semafor / eşzamanlılık yuvası** (`LLM_SLOTS`: cpu 1, gpu N) üzerinden geçer.
- **Kural:** ARCH-09, CONTRACTS C10.

---

### M9. APScheduler: İkinci Bir Zamanlayıcı Kütüphanesinin İnşası (D: ARCH-09)
- **Konum:** `plan/03-backend-cekirdek.md` satır 35, 50 vs `plan/07-onay-kuyrugu.md` satır 20 vs `plan/16-veri-kaynaklari.md` satır 23 vs `PLAN.md` satır 166.
- **Alıntı (`03-backend-cekirdek.md:L35`):**  
  > `Değerlendirme APScheduler ile (dakikalık); service_down /readyz 5 dk başarısızlıkta...`
- **Gerekçe:** PLAN 5 satır 166 "tek altyapı arq" demektedir. `arq` zaten yerleşik `cron_jobs` desteğine sahiptir. Backend sürecine ayrıca APScheduler eklemek C sınıfı bağımlılık getirir ve çoklu worker süreçlerinde işlerin mükerrer çalışmasına yol açar.
- **Önerilen Düzeltme:** APScheduler bağımlılığı tamamen kaldırılmalıdır. Uyarı değerlendirmesi, veri saklama temizliği, onay TTL aşımı ve kaynak senkronizasyonu `arq`'ın `WorkerSettings.cron_jobs` yeteneğiyle worker sürecinde çalıştırılmalıdır.
- **Kural:** ARCH-09, PLAN:166.

---

### M10. Embedding Nerede Çalışıyor: Çelişkili Açıklamalar (B, D: ARCH-10)
- **Konum:** `PLAN.md` satır 66 vs `plan/01-litellm-gateway.md` satır 14 vs `plan/04-bilgi-tabani.md` satır 44, 122.
- **Alıntı (`PLAN.md:L66`):**  
  > `Yerel varsayılan (Ollama ya da süreç içi)`
- **Alıntı (`01-litellm-gateway.md:L14`):**  
  > `<proje>.embed-default -> yerel embedding (ollama/bge-m3 ya da süreç içi TEI; profil ve EMBED_MODEL'e göre)`
- **Alıntı (`04-bilgi-tabani.md:L122`):**  
  > `Yerel reranker ve embedding model nesneleri süreç başına bir kez yüklenir; asyncio.to_thread + model başına threading.Lock.`
- **Gerekçe:** 04:122 embedding modelinin süreç içine yükleneceğini söylerken 04:44 LiteLLM `embed-default` üzerinden çağrılacağını söyler. TEI süreç içi bir kütüphane değil bağımsız bir servistir.
- **Önerilen Düzeltme:** Mimari netleştirilmelidir: Embedding her iki profilde de **Ollama `bge-m3` -> LiteLLM `embed-default`** üzerinden çağrılır. Süreç içi çalışan tek model `bge-reranker`'dır. 04:122'den "ve embedding" ifadesi çıkarılmalıdır.
- **Kural:** ARCH-10, FELSEFE META-01.

---

### M11. `mode: tool` Araç Adları Donmuş Sözleşme C7 ile Çelişiyor (B, C)
- **Konum:** `plan/06-agent-runtime.md` satır 110 vs `handbook/CONTRACTS.md` C7.
- **Alıntı (`06-agent-runtime.md:L110`):**  
  > `Bilgi tabanı mode: tool seçildiğinde üç araç üretilir: knowledge_search, knowledge_read_document, knowledge_read_document_lines...`
- **Alıntı (`CONTRACTS.md:L13`):**  
  > `C7: MCP... yerleşik araç imzaları search_documents(query, kb_key, top_k), get_schema(question?), run_sql(sql, reason)`
- **Gerekçe:** Donmuş sözleşme C7 yalnızca `search_documents` aracını tanımlar. 06:110'daki belge okuma araçları bağlam bütçesini aşırı tüketir ve C7 sözleşmesinde yer almaz.
- **Önerilen Düzeltme:** CONTRACTS C7 kazanır. 06:110'daki ek araç tanımları silinmeli; bilgi tabanı aracı yalnızca `search_documents` olarak bağlanmalıdır.
- **Kural:** ARCH-11, CONTRACTS C7.

---

### M12. 09 Aşama Teşhisi İçin Gereken Aday Verisi Kaydedilmiyor (A, C)
- **Konum:** `plan/09-evaluation.md` satır 21–27 vs `plan/06-agent-runtime.md` satır 19 vs `plan/04-bilgi-tabani.md` satır 87.
- **Alıntı (`09-evaluation.md:L25`):**  
  > `not_retrieved: expected_docs hibrit adaylarda (top-30) yok... not_reranked: adayda var, reranker sonrası seçilenlerde yok.`
- **Gerekçe:** 09'un bu teşhisi koyabilmesi için arama anındaki top-30 adayın kaydedilmiş olması gerekir. Ancak 06:19 `sources` olayı yalnızca nihai seçilenleri tutar. `kb_queries` tablosunda ise `run_id` kolonu yoktur.
- **Önerilen Düzeltme:** 04a'da `kb_queries` tablosuna `run_id nullable` ve `candidates jsonb` (ilk 30 aday ID'si ve skorları) kolonları eklenmelidir. Arama API'si `X-Run-Id` başlığını kabul etmeli; 09 teşhisi bu tablodan okumalıdır.
- **Kural:** ARCH-06, FELSEFE DOC-15.

---

### M13. Fail-Loud İhlalleri: Sessiz Uyarı, Kırpma ve Fallback (D: ARCH-06)
- **Konum:** `plan/06-agent-runtime.md` satır 45, 54 vs `plan/05-arac-katmani-mcp.md` satır 19 vs `plan/02-langfuse-izleme.md` satır 15.
- **Gerekçe ve Düzeltmeler:**
  1. **06:54:** "`OLLAMA_CONTEXT_LENGTH` ile tutarsızsa açılışta uyarı" ifadesi sessiz kırpmaya yol açar. **Düzeltme:** `context_tokens > OLLAMA_CONTEXT_LENGTH` olan agent kaydı 400 ile engellenmeli; açılışta tutarsızlık varsa `/readyz` 503 dönmelidir.
  2. **06:45:** Bütçe aşılınca RAG `top_k`'nın sessizce düşürülmesi. **Düzeltme:** Düşen parçalar `sources.dropped_by_budget` olarak event'e yazılmalı ve UI'da gösterilmelidir.
  3. **05:19:** Araç sonucunun sessizce kırpılması. **Düzeltme:** Modele görünen metne `[kırpıldı: N/M karakter]` eklenmeli ve `tool_result` event'inde `truncated=true` olmalıdır.
  4. **02:15:** Langfuse kesilince yerel dosya yedeğine sessiz düşüş. **Düzeltme:** Yerel dosya yalnızca ilk seed olmalı; çalışma anında Langfuse yoksa önbellek kullanılmalı ve `service_down` uyarısı üretilmelidir.
- **Kural:** ARCH-06 (Fail-loud).

---

### M14. `/mcp/{key}/` Uç Noktasının İkinci Dış Kapı Açması (B, C)
- **Konum:** `plan/05-arac-katmani-mcp.md` satır 33 vs `PLAN.md` satır 163.
- **Alıntı (`05-arac-katmani-mcp.md:L33`):**  
  > `Erişim: access=token ise çağıran 03'teki API anahtarıyla gelir ve proje yetkisi kontrol edilir...`
- **Gerekçe:** PLAN 5 satır 163 "dışa açılan tek adres backend facade'dır" derken, 05b `/mcp/{key}/` üzerinden dış istemcilere ikinci bir giriş kapısı açmaktadır.
- **Önerilen Düzeltme:** PLAN R1.2 güncellenmelidir: "Backend dışa açılan tek süreçtir; iki onaylı yüzeyi vardır: Facade (`/v1/*`) ve yayınlanan MCP sunucuları (`/mcp/{key}/`). İkisi de `resolve_actor`, kota, guardrail ve audit'ten geçer." `access=token` için `api_keys.scopes` içinde `tools_invoke` zorunlu tutulmalıdır.
- **Kural:** ARCH-11, CONTRACTS C11.

---

### M15. ACL Anlamı Tanımsızlığı ve Kaynak Yetkisi İzolasyonu (A, G)
- **Konum:** `plan/04-bilgi-tabani.md` satır 73 vs `plan/16-veri-kaynaklari.md` satır 25.
- **Alıntı (`04-bilgi-tabani.md:L73`):**  
  > `çağıran kullanıcı/anahtarın rolü ve kimliği documents.acl_* ile sorguda filtrelenir`
- **Gerekçe:** `documents.acl_roles` ve `acl_users` boş olduğunda belgenin herkese mi açık olduğu yoksa kimseye mi açık olmadığı tanımsızdır. Ayrıca 16'da Confluence grupları platformda grup varlığı olmadığı için eşlenememektedir.
- **Önerilen Düzeltme:** 04a'ya şu kural yazılmalıdır: "İki ACL dizisi de boşsa belge proje üyelerinin tamamına açıktır; elle yüklemede arayüz ACL seçimini zorunlu kılar (varsayılan `analyst`)." 16 senkron motoru ise kaynak gruplarını senkron anında platform kullanıcılarına genişleterek (`acl_users`) indekslemelidir.
- **Kural:** ARCH-13, SECURITY_AND_PERMISSIONS:13.

---

### M16. Egress İzin Listesi Uygulama Aracı Yetersizliği ve Teams Port Talebi (G)
- **Konum:** `plan/12-kapali-ag-paketleme.md` satır 27 vs `plan/15-kanallar.md` satır 37.
- **Alıntı (`12-kapali-ag-paketleme.md:L27`):**  
  > `Docker ağı için nftables/iptables scripti ve kurumsal güvenlik duvarı için liste.`
- **Gerekçe:** `nftables/iptables` L3/L4 seviyesindedir; joker alan adı (`*.openai.azure.com`) filtreleyemez. Ayrıca 15'te Teams Bot Framework dışarıdan içeriye HTTPS bağlantısı talep ederek kurum ağını açmayı gerektirmektedir.
- **Önerilen Düzeltme:** `llmaas` profilinde çıkış için Compose'a hafif bir forward proxy (`EGRESS_PROXY`, örn. Squid) eklenmeli; alan adı ACL'si burada uygulanmalıdır. Teams için dışarıdan erişim yalnızca ters proxy'de `/channels/teams/messages` yoluyla sınırlandırılmalıdır.
- **Kural:** SECURITY_AND_PERMISSIONS:40, 44.

---

### M17. Akışta Tokenize Edilmiş Yer Tutucunun Chunk Sınırında Bölünmesi (A)
- **Konum:** `plan/08-guardrail-pii.md` satır 14, 32.
- **Alıntı (`08-guardrail-pii.md:L32`):**  
  > `<<PII_1>> yer tutucu; eşleme Redis'te run süresince... çıkışta geri çevrilir.`
- **Gerekçe:** Model streaming yanıt üretirken `<<PII_` bir SSE chunk'ında, `1>>` sonraki chunk'ta gelebilir. Tamponlama yapılmazsa istemciye ham `<<PII_1>>` sızar.
- **Önerilen Düzeltme:** `output.stream.delta` aşamasında, `<<` görüldüğünde `>>` gelene kadar (en fazla 16 karakter) metni tutan kayan bir tamponlayıcı (detokenizer buffer) tanımlanmalı ve kabul kriterlerine chunk bölme testi eklenmelidir.
- **Kural:** CONTRACTS C4, TEST_STRATEGY:14.

---

### M18. Test Setlerinin Ölçülen İşçi Tarafından Yazılması (A, TEST)
- **Konum:** `plan/08-guardrail-pii.md` satır 63, 70 vs `plan/14-kullanici-hafizasi.md` satır 56.
- **Alıntı (`08-guardrail-pii.md:L70`):**  
  > `Teslimatlar: data/samples/pii/ Türkçe test seti: 100 cümle, etiketli (sentetik).`
- **Gerekçe:** Kendi yazdığı teste karşı ölçülen recall bağımsız kanıt oluşturmaz.
- **Önerilen Düzeltme:** PII test seti ve hafıza test seti B4'te önerilen 13a paketine devredilmeli; test agent'ı tarafından 08 ve 14 kodlanmadan önce bağımsız olarak hazırlanmalıdır.
- **Kural:** TEST_STRATEGY:32, EXECUTION_HANDBOOK:7.

---

### M19. "Bunu Hatırla" Komutunun PII Engelini Atlaması (G)
- **Konum:** `plan/14-kullanici-hafizasi.md` satır 24, 27.
- **Alıntı (`14-kullanici-hafizasi.md:L27`):**  
  > `kullanıcı "bunu hatırla: ..." yazarsa çıkarma modeli atlanır, doğrudan kind=preference, confidence=1.`
- **Gerekçe:** Çıkarma modelinin atlanması 08 `pii block` kuralının da atlanması riskini doğurur. Kullanıcı "bunu hatırla: Hasta Ahmet Y., TC 123..." derse hasta verisi hafızaya sızar.
- **Önerilen Düzeltme:** Açık komut yolu da kesinlikle 08 `input.pre` PII filtresinden geçirilmeli; PII tespit edilirse işlem 400 ile engellenmeli ve audit'e yazılmalıdır.
- **Kural:** CONTRACTS:39, SECURITY_AND_PERMISSIONS:13.

---

### M20. Uygulayıcısı Olmayan Kota Kapsamları ve Senkron Gecikmesi (A)
- **Konum:** `plan/03-backend-cekirdek.md` satır 31, 32, 88.
- **Alıntı (`03-backend-cekirdek.md:L31`):**  
  > `quotas(..., scope_type: project|group|user|api_key|model|provider...)`
- **Gerekçe:** `group`, `model` ve `provider` kapsamlarının backend'de veya LiteLLM'de uygulayıcısı yoktur. Ayrıca API anahtarı bütçesinin `usage_daily`'den saatlik senkronla uygulanması bütçe aşımlarında 1 saate varan gecikmeye yol açar.
- **Önerilen Düzeltme:** Bu sürümde `scope_type` yalnızca `project|api_key|user` olarak sınırlandırılmalıdır. API anahtarı bütçesi Redis sayaçlarıyla anlık takip edilmeli; `usage_daily` yalnızca raporlama için kullanılmalıdır.
- **Kural:** ARCH-13, FELSEFE META-06.

---

### M21. Çekirdek Yüzeyinin Cognipeer Kopyasıyla Gereksiz Genişlemesi (D: ARCH-07, ARCH-10)
- **Konum:** `plan/04-bilgi-tabani.md` satır 85 vs `plan/06-agent-runtime.md` satır 107.
- **Alıntı (`04-bilgi-tabani.md:L85`):**  
  > `chunk_strategy (recursive|token|markdown|sentence|semantic), separators[], parent_window, contextual_headers, oversample...`
- **Alıntı (`06-agent-runtime.md:L107`):**  
  > `webhook_url, budget_usd, raw_output_tools[] (çıktısı özetlenmeyecek araçlar)...`
- **Gerekçe:** PayCore'da ölçülmüş tek strateji başlık duyarlı parçalamadır. 5 ayrı strateji gereksiz bakım yüküdür. 06:107'deki `raw_output_tools` ise hiçbir yerde tanımlanmamış gizli bir araç çıktısı özetleme adımını varsaymaktadır (ARCH-10 ihlali).
- **Önerilen Düzeltme:** 04:85'ten karmaşık parçalama stratejileri çıkarılmalı, `heading` stratejisi sabitlenmelidir. 06:107'den tanımsız `raw_output_tools`, `budget_usd` ve `webhook_url` çıkarılmalıdır.
- **Kural:** ARCH-07, ARCH-10, FELSEFE META-06.

---

### M22. GPU Sütununun Olmayan Donanımı Kabul Kriteri Yapması (A)
- **Konum:** `plan/12-kapali-ag-paketleme.md` satır 46 vs `plan/13-ornek-veri-demo.md` satır 35–43 vs `KARARLAR.md` satır 67.
- **Alıntı (`12-kapali-ag-paketleme.md:L46`):**  
  > `rehberdeki GPU yapılandırmasında 10 eşzamanlı RAG sorusunun P50/P95'i docs/donanim.md'de yazılıdır.`
- **Gerekçe:** GPU donanımı geliştirme ve test ortamında henüz yoktur (`KARARLAR:67` açık konu). Bu ölçüm zorunlu tutulursa 12 ve 13 paketleri VERIFIED olamaz.
- **Önerilen Düzeltme:** GPU sütunu kabul kriterlerinde "Donanım mevcutsa ölçülür, aksi takdirde `NOT_RUN (PENDING_ENV)` bırakılır" olarak işaretlenmelidir. M5 kilometre taşının kapanışı `llmaas` ve `cpu` ölçümlerine bağlanmalıdır.
- **Kural:** EXECUTION_HANDBOOK:69, TEST_STRATEGY:56.

---

### M23. `guardrail_policies` ve `guardrail_events` Eksik Kolonları (A)
- **Konum:** `plan/08-guardrail-pii.md` satır 13–15 vs satır 45, 50, 53, 54.
- **Gerekçe:** Satır 13'teki tablo şemasında metin içinde zorunlu kılınan `on_error`, `short_circuit` ve `block_message_tr` alanları yer almamaktadır. Satır 54'te ise `guardrail_events` için ek kolonlar (`status, input_preview, findings, severity, source`) metin olarak bırakılmıştır.
- **Önerilen Düzeltme:** 08 Veri Modeli altındaki tablo tanımları bu kolonları içerecek şekilde birleştirilmelidir.
- **Kural:** CONTRACTS C4, FELSEFE DOC-15.

---

### M24. `documents` Tablosunda Kapı 0 Kolonlarının ve `messages.feedback` Eksikliği (A, C)
- **Konum:** `plan/04-bilgi-tabani.md` satır 17 vs `plan/11-chat-arayuzu.md` satır 15 vs `plan/06-agent-runtime.md` satır 20.
- **Gerekçe:** 
  1. `documents` tablosunda `gate1` ve `gate2` durumları varken ana belgenin Kapı 0 elemesini kaydedecek `gate0_status` ve `gate0_reason` yoktur.
  2. 11:15'te kullanıcının geri bildirimini yazacağı belirtilen `messages.feedback` kolonu 06:20'deki `messages` tablosunda tanımlanmamıştır.
- **Önerilen Düzeltme:** 04 `documents` tablosuna `gate0_status` ve `gate0_reason`; 06 `messages` tablosuna `feedback jsonb nullable` eklenmelidir.
- **Kural:** ARCH-06, CONTRACTS C3.

---

## 3. MINOR Bulgular (Tek Satır)

- **N1 (`03-backend-cekirdek.md:L90`):** "LiteLLM key'i 429 döner" ifadesi TERMINOLOGY:24 yasaklı terim kuralını çiğnemektedir; "facade üzerinden gelen istek 429 döner" yapılmalıdır.
- **N2 (`00-depo-iskeleti.md:L37`):** "boş config.yaml" LiteLLM konteynerini çökertir; `model_list: []` başlangıç şablonu verilmelidir.
- **N3 (`06-agent-runtime.md:L95`):** SSE olay listesinde `progress` ve `fallback` eksiktir; CONTRACTS C9'a göre eklenmelidir.
- **N4 (`01-litellm-gateway.md:L14`):** "süreç içi TEI" teknik çelişkidir; "süreç içi sentence-transformers ya da harici TEI" yazılmalıdır.
- **N5 (`06-agent-runtime.md:L125`):** "burada manuel" kabul kriteri otomatik test standardına aykırıdır; mock LLM fixture'ı ile otomatikleştirilmelidir.
- **N6 (`09-evaluation.md:L88`):** CPU'da 35 soru süresi "1-1,5 saat" denirken 13'te 4 dk tolerans vardır; süre "1,5–2 saat" olarak güncellenmelidir.
- **N7 (`05-arac-katmani-mcp.md:L38`):** `make sync-superset-metrics` genel araç brief'i yerine `data/samples/` scripti düzeyinde tutulmalıdır.
- **N8 (`PLAN.md:L185` vs `06-agent-runtime.md:L18`):** PLAN 6, 15 paketinin `runs.channel` enum değerlerini ekleyeceğini söylerken 06 bunu baştan tanımlamıştır; PLAN düzeltilmelidir.
- **N9 (`01-litellm-gateway.md:L3`):** "Bağımlılık: 00, 03" yazmaktadır; PLAN:192'ye uygun olarak "00, 03a" yazılmalıdır.
- **N10 (`00-depo-iskeleti.md:L13`):** "'Platform' başlığı" TERMINOLOGY:9'a aykırıdır; "FFCore" kullanılmalıdır.
- **N11 (`00-depo-iskeleti.md:L40`):** `warmup` ve `/readyz` 00'da tanımlanmış ama 00 uygulama kodu içermez; ısınma 01 veya 04a'ya devredilmelidir.
- **N12 (`00-depo-iskeleti.md:L15`):** `llmaas` varsayılanında da Qwen 35B çekilmektedir; `models.txt` profile göre seçilmeli, llmaas'ta yalnızca `bge-m3` olmalıdır.
- **N13 (`02-langfuse-izleme.md:L11`):** "Anahtarlar `.env`'e yazılır" SECURITY:6 ile çelişir; Langfuse headless init env girdileri kullanılmalıdır.
- **N14 (`03-backend-cekirdek.md:L3`):** "6 gün (03a 2,5 + 03b 3,5; +1 …)" toplamı 7 gün etmektedir; başlık düzeltilmelidir.
- **N15 (`04-bilgi-tabani.md:L19` & `05-arac-katmani-mcp.md:L48`):** `chunks` ve `few_shots` tablolarında `project_id, created_by` kolonları CONTRACTS C3 gereği eklenmelidir.
- **N16 (`05-arac-katmani-mcp.md:L6`):** Satır 6'da hâlâ "Postman" adı geçmektedir; satır 35'te reddedildiği için başlıktan silinmelidir.
- **N17 (`05-arac-katmani-mcp.md:L48`):** "pgvector ya da basit benzerlik" ARCH-10'a aykırıdır; `embed-default` + pgvector sabitlenmelidir.
- **N18 (`06-agent-runtime.md:L83`):** "`waiting_approval` benzeri `waiting_user`" ifadesi iki ayrı durum olduğunu netleştirmelidir.
- **N19 (`07-onay-kuyrugu.md:L23`):** Tekrar eden onayda "ikinci kez sorulmaz" ifadesi `approval_reused` olayı olarak loglanmalıdır.
- **N20 (`08-guardrail-pii.md:L21`):** "spaCy Türkçe modeli kullanılmaz" denirken satır 82'de ayna listesine eklenmiştir; gerekli paket tam adıyla belirtilmelidir.
- **N21 (`08-guardrail-pii.md:L65`):** "`airgap`'te egress çalışmaz" kuralı `if profile` ile değil, seed bayrağı (`GUARDRAIL_EGRESS_ENABLED`) ile yönetilmelidir.
- **N22 (`09-evaluation.md:L50`):** `EVAL_RESET_MODEL` backend'e Docker soket yetkisi gerektirir; güvenlik riski nedeniyle kaldırılmalı, `warm_cache=true` loglanmalıdır.
- **N23 (`10-yonetim-onyuzu.md:L41-42`):** Kanallar ve Kaynaklar ekranları 15 ve 16 tarafından yazılacaksa touch-zone açıkça paylaştırılmalıdır.
- **N24 (`12-kapali-ag-paketleme.md:L7`):** Amaç bölümü hâlâ "İnternetsiz üretim sunucusuna kurulum" demektedir; `llmaas` birincil hedefine göre güncellenmelidir.
- **N25 (`12-kapali-ag-paketleme.md:L11`):** Langfuse airgap'te isteğe bağlı bırakılmamalı; mimari karara uygun olarak her iki profilde zorunlu olmalıdır.
- **N26 (`14-kullanici-hafizasi.md:L15`):** `memories` tablosuna PLAN:237 gereği `scope: user|team|project` kolonu şimdiden eklenmelidir.
- **N27 (`15-kanallar.md:L7`):** Kanal "giriş kapısı" değil, "kullanıcı yüzeyi" olarak adlandırılmalıdır (TERMINOLOGY:15).
- **N28 (`16-veri-kaynaklari.md:L13`):** Dizin adı `connectors/` değil, TERMINOLOGY:42'ye uygun olarak `sources/` olmalıdır.

---

## 4. Brief'ler Arası Çelişkiler

| # | Brief A (Alıntı) | Brief B (Alıntı) | Önerilen Düzeltme |
|---|---|---|---|
| **C1** | `04-bilgi-tabani:L16` "`models.embed_dim` uyuşmazsa uyarı verir" | `03-backend-cekirdek:L59` "400 döner (uyarı değil)" | 04 düzeltilir: 400 hatası üretir. |
| **C2** | `03-backend-cekirdek:L23` "her değişiklik `render-litellm`'i tetikler" | `01-litellm-gateway:L11` "çalışırken DB API... reload kullanılmaz" | 03a düzeltilir: LiteLLM DB API reconciler tetiklenir. |
| **C3** | `04-bilgi-tabani:L35` "Redis kuyruğu... `arq` ya da `rq`" | `PLAN.md:L166` & `KARARLAR:L53` "tek kütüphane `arq`" | 04 düzeltilir: `arq` tek seçenektir. |
| **C4** | `08-guardrail-pii:L38` "`litellm_hook.py`, LiteLLM'in custom guardrail arayüzünü uygular" | `KARARLAR:L59` & `PLAN.md:L163` "Dışa kapalı LiteLLM, tek kapı facade" | 08 düzeltilir: `litellm_hook.py` silinir, facade tek denetim noktasıdır. |
| **C5** | `07-onay-kuyrugu:L40` "basit `ON_APPROVAL_WEBHOOK_URL` env değişkeni yeterli" | `03-backend-cekirdek:L36` & `07:L22` "`notification_settings.default_webhook_url`, ayrı env yok" | 07 düzeltilir: 03b DB ayarı tek kaynaktır. |
| **C6** | `02-langfuse-izleme:L47` "09 Langfuse datasets kullanmaz" | `KARARLAR:L69` & `BLOCKERS:L10` "DECISION-4 açık konu" | 02 düzeltilir: DECISION-4 kararına bağlanır. |
| **C7** | `06-agent-runtime:L74` "ACL anahtarın proje rolüne göre" | `03-backend-cekirdek:L30` `api_keys` tablosunda `role` kolonu yok | 03b düzeltilir: `api_keys.acl_role` eklenir. |
| **C8** | `03-backend-cekirdek:L28` `projects` tablosunda team_key kolonu yok | `01-litellm-gateway:L17` "facade LiteLLM'i team anahtarıyla çağırır" | 03a düzeltilir: `projects.litellm_team_key_encrypted` eklenir. |
| **C9** | `06-agent-runtime:L18` `outcome_label (declined\|below_threshold\|answered)` | `09-evaluation:L17` & `TERMINOLOGY:L69` `outcome: not_retrieved\|not_reranked...` | 06a düzeltilir: `outcome_label` arama ve rerank aşama etiketlerini içerir. |
| **C10** | `13-ornek-veri-demo:L42` Tablo satırı: "Cevapsız sorularda tutma: cpu 7/8" | `13-ornek-veri-demo:L48` Metin maddesi: "Cevapsız 8 sorunun 8'inde uydurma yoktur" | 13 düzeltilir: Metin maddesi CPU için 7/8 yapılır. |
| **C11** | `06-agent-runtime:L82` "`mode: tool` KB'ler `search_documents` aracı olarak eklenir" | `06-agent-runtime:L110` "üç araç üretilir: `knowledge_search`, `read_document`..." | CONTRACTS C7 kazanır: Yalnızca `search_documents` kalır. |
| **C12** | `06-agent-runtime:L61` "Etkileşimli-düşük... hafıza çıkarma... pencereye bağlı değildir" | `14-kullanici-hafizasi:L69` "Hafıza çıkarma arka plan sınıfındadır... pencerede koşar" | 06a kazanır: Etkileşimli-düşük pencereye bağlı değildir. |
| **C13** | `06-agent-runtime:L73` "istemci 07 API'si ile onaylayıp devam eder" | `07-onay-kuyrugu:L22` "onay yalnızca giriş yapmış kullanıcıyla verilir" | 07 kazanır: Dış istemci onaylayamaz, insan onayını bekler. |
| **C14** | `15-kanallar:L19` "düğmeli onay mesajı... 07 kurallarıyla kontrol edilir" | `07-onay-kuyrugu:L22` "yalnızca giriş yapmış kullanıcıyla" | 07'ye doğrulanmış kanal kimliği istisnası eklenir. |
| **C15** | `PLAN.md:L185` "15 `runs.channel` enum değerlerini ekler" | `06-agent-runtime:L18` `channel: chat\|api\|test\|slack\|teams...` | 06a baştan tanımlar; PLAN 6 güncellenir. |
| **C16** | `MULTI_AGENT:L39` "16 \| `backend/app/sources/`" | `16-veri-kaynaklari:L13` "`backend/app/knowledge/connectors/`" | `sources/` dizin adı sabitlenir. |
| **C17** | `PLAN.md:L72` "run 120 s / CPU run 900 s / GPU 300 s" | `06-agent-runtime:L135` `limits.timeout_s varsayılanı CPU 600, GPU 120` | PLAN 2b kazanır: 06'daki değerler düzeltilir. |
| **C18** | `PLAN.md:L163` "dışa açılan tek adres backend facade" | `05-arac-katmani-mcp:L33` "`access=token` ise çağıran API anahtarıyla gelir" | PLAN R1.2 güncellenir: Facade ve `/mcp/{key}/` iki dış yüzeydir. |
| **C19** | `00-depo-iskeleti:L39` "`make smoke` context length'i doğrular" | `06-agent-runtime:L54` "tutarsızsa açılışta uyarı" | 06 düzeltilir: Tutarsızlıkta `/readyz` 503 verir (Fail-loud). |
| **C20** | `16-veri-kaynaklari:L23` "sayım kontrolü delta'da tombstone sayısına uygulanır" | `16-veri-kaynaklari:L76` "100 dosyalık kütüphanede 30 dosya silinirse... prune_refused" | 16:23 netleştirilir: Oran delta paketine değil, toplam belgeye bölünür. |

---

## 5. Felsefe İhlalleri

| İlke | Brief | Alıntı | İhlal Nedeni | Önerilen Düzeltme |
|---|---|---|---|---|
| **ARCH-06** (Fail-loud) | `04-bilgi-tabani:L16` | `models.embed_dim ölçümü globalle uyuşmazsa model kaydı uyarı verir.` | Uyuşmazlıkta sessizce uyarı verip kaydetmek pgvector'ü çalışma anında çökertecektir. | Hata fail-loud olmalı, 400 ile işlem hemen kesilmelidir. |
| **ARCH-06** (Fail-loud) | `06-agent-runtime:L54` | `OLLAMA_CONTEXT_LENGTH ile tutarsızsa açılışta uyarı` | Model sessizce prompt kırpacak ve kaynakların %70'i kaybolacaktır. | Açılışta `/readyz` 503, agent kaydında 400 dönmelidir. |
| **ARCH-06** (Fail-loud) | `06-agent-runtime:L45` | `bütçe aşılınca önce geçmiş kırpılır, sonra RAG top_k düşürülür` | Parçalar kullanıcıya veya loglara bildirilmeden sessizce atılmaktadır. | Düşen parçalar `sources.dropped_by_budget` olarak loglanmalıdır. |
| **ARCH-06** (Fail-loud) | `05-arac-katmani-mcp:L19` | `çağrı sonucu boyutu TOOL_RESULT_MAX_CHARS ile kırpılır` | Model kırpıldığını bilmezse bozuk JSON/SQL ile halüsinasyon üretir. | Kırpılan metne `[kırpıldı]` işareti ve `truncated=true` eklenmelidir. |
| **ARCH-06** (Fail-loud) | `02-langfuse-izleme:L15` | `Langfuse erişilemezse yerel backend/prompts/*.md yedeğine düşer` | İki prompt deposu birbirinden sapar ve sessizce eski prompt çalışır. | Yerel dosya yalnızca seed olmalı; kesintide önbellek + uyarı üretilmelidir. |
| **ARCH-07** (Dar senaryo için çekirdeği ağırlaştırma) | `08-guardrail-pii:L38` | `backend/app/guardrails/litellm_hook.py, LiteLLM custom guardrail arayüzünü uygular...` | Dışa kapalı LiteLLM için konteyner içine Python kodu gömmek gereksiz bakım yüküdür. | Kanca mimariden çıkarılmalı, guardrail sadece facade'da çalışmalıdır. |
| **ARCH-07** (Dar senaryo için çekirdeği ağırlaştırma) | `04-bilgi-tabani:L85` | `chunk_strategy (recursive\|token\|markdown\|sentence\|semantic)...` | 5 ayrı parçalama stratejisi kalıcı bir test ve yeniden indeksleme matrisi yaratır. | Yalnızca test edilmiş `heading` parçalama stratejisi bırakılmalıdır. |
| **ARCH-09** (Var olanı yeniden inşa etme) | `07-onay-kuyrugu:L40` | `webhook çıkışı için notifications tablosu yerine basit ON_APPROVAL_WEBHOOK_URL env değişkeni yeterli.` | 03b'deki `notification_settings` altyapısı varken paralel bağımsız env tanımlamak. | 03b'nin veritabanı ayarı kullanılmalıdır. |
| **ARCH-09** (Var olanı yeniden inşa etme) | `03-backend-cekirdek:L35` | `Değerlendirme APScheduler ile (dakikalık)` | `arq` zaten cron desteği sunarken ikinci bir zamanlayıcı kütüphanesi getirmek. | `arq`'ın `cron_jobs` yeteneği kullanılmalıdır. |
| **ARCH-09** (Var olanı yeniden inşa etme) | `09-evaluation:L13–18` | `datasets, dataset_items, eval_suites, eval_runs, eval_scores tabloları` | Langfuse v3 OSS zaten Dataset ve Experiment motoruna sahipken sıfırdan 5 tablo kurmak. | `DECISION-4` ile Langfuse Datasets API'si kullanılmalıdır. |
| **ARCH-10** (Açık kontrol, sihir yok) | `04-bilgi-tabani:L35` | `arq ya da rq` | İşçiye ve sisteme örtük kütüphane seçimi bırakmak. | `arq` açıkça ve tek seçenek olarak sabitlenmelidir. |
| **ARCH-10** (Açık kontrol, sihir yok) | `06-agent-runtime:L107` | `raw_output_tools[] (çıktısı özetlenmeyecek araçlar)` | Tanımlanmamış ve gizli bir araç çıktısı özetleme adımı varsayımı. | Alan ve gizli özetleme adımı brief'ten çıkarılmalıdır. |
| **ARCH-13** (Belirsiz terim) | `03-backend-cekirdek:L90` | `LiteLLM key'i 429 döner.` | `TERMINOLOGY.md` satır 24 "LiteLLM key" terimini yasaklamıştır. | "Facade üzerinden gelen istek 429 döner" olarak düzeltilmelidir. |
| **ARCH-13** (Belirsiz terim) | `15-kanallar:L7` | `Kanal ... giriş kapısıdır` | "Tek giriş kapısı" facade'ın adıdır; kanal "kullanıcı yüzeyi"dir. | "kullanıcı yüzeyi" terimi kullanılmalıdır. |
| **ARCH-13** (Belirsiz terim) | `16-veri-kaynaklari:L13` | `knowledge/connectors/` | `TERMINOLOGY.md` satır 42 "connector" adını yasaklamıştır. | `sources/` terimi ve dizin adı kullanılmalıdır. |

---

## 6. Süre ve Dalga Değerlendirmesi

### 6.1 Paket Tahminleri ve Sapma Analizi

| Paket | Brief Süresi | Gerçekçi Tahmin | Sapma | Gerekçe |
|---|---|---|---|---|
| **00** | 1,0 gün | 1,5 gün | +0,5 | Langfuse v3 bağımlılıkları (ClickHouse, MinIO) + Ollama bağlam doğrulama testleri |
| **01** | 1,5 gün | 3,0 gün | +1,5 | Model uzlaştırıcı reconciler (M1), B1 team key yönetimi ve gerçek LiteLLM entegrasyonu |
| **02** | 0,5 gün | 1,0 gün | +0,5 | Kapsam 7 06a'ya aktarılsa bile SDK ve headless init testleri 1 gün ister |
| **03a** | 2,5 gün | 3,0 gün | +0,5 | Rol × mod erişim matrisi, parametrik OpenAPI testleri, CSRF koruması |
| **03b** | 3,5 (+1) gün | 5,0 gün | +0,5 | Kotalar, uyarı motoru, e-posta/webhook bildirimi, audit partition, OBO |
| **04a** | 5,0 gün | 7,0 gün | +2,0 | Docling süreç havuzu, MHTML/cp1254/PDF kuralları, üç kapı, hibrit + reranker + ACL |
| **04b** | 2,5 gün | 3,5 gün | +1,0 | Qdrant tam eşdeğerlik testi, `migrate-vectors`, normalizer K1 testi |
| **05a** | 3,0 gün | 4,0 gün | +1,0 | MCP istemci + mcp-sql + mcp-search + SSRF filtreleri + `forward_user` |
| **05b** | 2,0 gün | 3,0 gün | +1,0 | OpenAPI -> MCP sunucu tarafı dönüşümü, şema doğrulama, Superset testi |
| **06a** | 4,5 gün | 7,0 gün | +2,5 | LangGraph builder, bütçe motoru, P7 kuyruk yuvaları, SSE pub/sub, interrupt/resume ve 02'den gelen Kapsam 7 |
| **06b** | 2,0 gün | 3,0 gün | +1,0 | OpenAI chunk şeması, `x_platform`, `annotations`, B5 kimlik doğrulaması |
| **07** | 1,5 gün | 1,5 gün | 0,0 | Kapsam dar ve net; gerçekçi |
| **08** | 5,0 gün | 5,5 gün | +0,5 | Kanca çıkarılıyor (-0,5); ancak akış tamponlama (M17) ve Türkçe NER entegrasyonu ekleniyor (+1,0) |
| **09** | 3,5 gün | 4,5 gün | +1,0 | 8 scorer, M12 aday teşhisi, sürüm karşılaştırma ve yayın kapısı |
| **10** | 8,5 gün | 14,0 gün | +5,5 | ~25 ekran × iki tema × iki erişim modu, Playwright görsel regresyon, sihirbaz formları |
| **11** | 2,5 gün | 3,0 gün | +0,5 | 10 ile paylaşılan bileşenler hazırsa 3 gün |
| **12** | 2,5 gün | 4,0 gün | +1,5 | İki kurulum rehberi, egress forward proxy (M16), yedekleme/geri yükleme provası |
| **13** | 2,0 gün | 4,0 gün | +2,0 | 13a (1 gün) + 13b (3 gün): üç ortamda ölçüm, CPU'da tek e2e sınav koşusu ~3 saat |
| **14** | 2,5 gün | 3,5 gün | +1,0 | Çıkarma motoru + geri çağırma + kullanıcı kontrol ekranı + PII bloklama testleri |
| **15** | 4,0 gün | 7,0 gün | +3,0 | Dört adaptör + widget paketi + Adaptive Card / Block Kit formatlayıcılar |
| **16** | 8,0 gün | 11,0 gün | +3,0 | 4 ayrı kaynak API'si, delta/tombstone senkronu, D4 güvenli silme uzlaştırması |
| **Toplam** | **68,0 gün** | **100,0 gün** | **+32,0** | **Net sapma: +%47 artış (100 agent-günü)** |

---

### 6.2 Kritik Yol ve Dalga Dağılımı Optimizasyonu

- **PLAN:210 İddiası:** Kritik yol "~20 gün".  
  Gerçek brief toplamı: 00 (1) -> 03a (2,5) -> 01 (1,5) -> 04a (5) -> 05a (3) -> 06a (4,5) -> 09 (3,5) -> 13 (2) = **23 gün**.  
  Gerçekçi süre tahminlerimizle: 1,5 + 3 + 3 + 7 + 4 + 7 + 4,5 + 4 = **34 iş günü**.
- **Dalga Tıkanıklıkları ve Çözüm:**
  1. **Dalga 2 Tıkanıklığı:** `BASLATMA:62`, İşçi B'ye sırayla 03b (3,5g) ve 08 (5g) vererek Dalga 2'yi 8,5 güne uzatmaktadır. Oysa İşçi A 03a'yı 2,5 günde bitirip boşta kalmaktadır.  
     *Çözüm:* Dalga 2'de İşçi A 03a, İşçi B 08 yapmalıdır (08 bağımsızdır). 03b Dalga 3'e kaydırılmalıdır.
  2. **Dalga 4 Tıkanıklığı:** `BASLATMA:64`, İşçi A'ya sıralı olarak 05a (3g) ve 06a (4,5g) vererek 7,5 gün yüklemekte, İşçi B ise yalnızca 04b (2,5g) yaparak 5 gün beklemektedir.  
     *Çözüm:* 04a biter bitmez Dalga 4 başında 05a İşçi B'ye verilmeli; İşçi B 05a'yı tamamlayınca İşçi A doğrudan 06a'ya başlamalıdır.
  3. **Dalga Kapısı İlkesi:** Dalga kapıları tüm paralel paketlerin bitmesini bekleyen kaba bir blokaj olmamalı; paketler **yalnızca kendi doğrudan bağımlılıkları MERGED olduğunda** READY olmalıdır (EXECUTION_HANDBOOK:9). Dalga kapanışları yalnızca Alembic merge ve iç tutarlılık denetimi için kullanılmalıdır. Bu optimizasyon kritik yoldan 4-5 gün kazandırır.

---

## 7. Katılmadığım Kararlar (`KARARLAR.md`) ve Gerekçen

### İtiraz 1: Mesai Dışı Pencere Kısıtının Tüm Profillerde Zorunlu Tutulması
- **Mevcut Karar (`KARARLAR.md:L30`):** *"arka plan mesai dışı pencerede (BACKGROUND_WINDOW 19:00-07:00)"*.
- **İtiraz Gerekçesi:** Bu kural `airgap` CPU'daki tek şeritli (concurrency=1) dar boğaz için hayati derecede doğrudur. Ancak ürünün birincil varsayılanı olan `llmaas` profilinde model sağlayıcıdan çağrılmaktadır; arka plan sınav veya değerlendirme işleri etkileşimli sohbeti CPU'da olduğu gibi dondurmaz. Analistin gündüz saatinde yaptığı bir agent değişikliğini sınava sokup yayınlayabilmek için akşam 19:00'u beklemesi ürün geliştirme çevikliğini yok eder.
- **Önerilen Pozisyon:** `BACKGROUND_WINDOW` bir kod dalı değil, profil seed değeri olmalıdır: `airgap cpu` için `19:00-07:00`, `llmaas` ve `gpu` için ise boş (her zaman aktif) bırakılmalıdır. Arka plan işleri etkileşimli işlerden sonra ama mesai saatinde de çalışabilmelidir.

### İtiraz 2: Sağlayıcı Anahtarlarının LiteLLM'e Ortam Değişkeniyle Verilmesi
- **Mevcut Karar (`KARARLAR.md:L60`):** *"Anahtar DB'de Fernet ile şifreli, ... LiteLLM'e ortam değişkeniyle (P6)"*.
- **İtiraz Gerekçesi:** Bu karar, PLAN 5:161'deki *"çalışırken değişiklikler LiteLLM'in DB'li model yönetim API'siyle uygulanır, yeniden başlatma ve /config/reload yok"* kararıyla teknik olarak bağdaşamaz. Çalışan bir Docker konteynerine işletim sistemi seviyesinde yeni ortam değişkeni enjekte etmek konteyneri yeniden başlatmadan mümkün değildir.
- **Önerilen Pozisyon:** Kararın ilk yarısı (DB'de Fernet ile saklama) korunmalı; ikinci yarısı düzeltilmelidir: Anahtar çalışma zamanında LiteLLM DB API'sine (`POST /model/new`) doğrudan request body içinde gönderilmeli ve LiteLLM'in kendi şifreli veritabanında `LITELLM_SALT_KEY` ile saklanmalıdır.

### İtiraz 3: M7 Kanallarının Paket 17'den (AD/LDAP & Son Kullanıcı) Önceye Alınması
- **Mevcut Karar (`KARARLAR.md:L25, L66`):** Son kullanıcı açılışı ve AD/LDAP (Paket 17) M6 sonrasına ertelenmiştir; ancak Paket 15 (Slack ve Teams kanalları) M7 kilometre taşı olarak Paket 17'nin önündedir.
- **İtiraz Gerekçesi:** 15:15 kuralı uyarınca kanal kullanıcıları platform kullanıcısına e-posta ile eşlenir; eşleşmeyenlere "platformda hesabınız yok" hatası verilir. Kurumsal kimlik dizini (AD/LDAP) entegre edilmeden Slack ve Teams açılırsa, kurumdaki yüzlerce çalışan bota yazdığında yetkisiz kalacaktır. Bütün kanal yalnızca geliştirme sırasındaki 8 demo kullanıcıyla test edilebilir.
- **Önerilen Pozisyon:** Paket 17, Paket 15'in önüne çekilmeli; kurumsal kanallar kurum kimlik dizini bağlandıktan sonra yayına alınmalıdır.

### İtiraz 4: Evaluation (09) İçin Langfuse Datasets Yerine Sıfırdan 5 Tablo Kurulması
- **Mevcut Durum (`KARARLAR.md:L69`, `BLOCKERS:L10` DECISION-4):** Sınav tablolarının Langfuse v3 datasets API'sine mi yoksa özel tablolara mı kurulacağı açık bırakılmıştır.
- **İtiraz Gerekçesi:** Brief 09 incelendiğinde; `datasets`, `dataset_items`, `eval_suites`, `eval_runs`, `eval_scores` olmak üzere 5 ayrı tablo, bunların CRUD API'leri, CSV import/export motoru ve karşılaştırma arayüzleri talep edilmektedir. Oysa Langfuse v3 OSS sürümü; CSV ile dataset yükleme, versiyonlama, experiment koşturma, run'ları dataset item'larıyla eşleştirme, web UI üzerinden diff ve skor dağılımı gösterme yeteneklerini eksiksiz sunmaktadır. Sıfırdan 5 tablo ve önyüz inşa etmek FELSEFE ARCH-09 ilkesinin ("Zaten var olanı yeniden inşa etme") doğrudan ihlalidir.
- **Önerilen Pozisyon:** `DECISION-4` Langfuse lehine kapatılmalıdır: 09 paketi Langfuse Datasets & Experiments API'si üzerine kurulmalı; yerel veritabanında yalnızca hafif bir suite-experiment eşleme tablosu tutulmalıdır. Bu tercih projeye en az 1,5–2 gün kazandırır.

---

## 8. Doğrulanmamış İddialar Listesi

Aşağıdaki teknik iddialar brief'lerde veya analizlerde olgu gibi yazılmış olup gerçek sürümde henüz test edilip kanıtlanmamıştır. İlgili paket işçisi planının 1. maddesinde ("Bulunan semboller") bunları doğrulamalıdır:

1. **`08-guardrail-pii.md:L23`:** *"LLM Guard'ın PromptInjection modeli yerel; CPU'da ms düzeyi"*  
   $\rightarrow$ **[Doğrulanmadı]**: DeBERTa tabanlı injection sınıflandırıcıları 32 vCPU Haswell mimarisinde PyTorch overhead'i ve tokenizasyon ile birlikte boşta 150–250 ms, eşzamanlı Qwen yükü altında 500+ ms gecikme üretebilir. CPU'da "ms düzeyi" iddiası doğrulanmamıştır.
2. **`04-bilgi-tabani.md:L118`:** *"bge-m3 ve multilingual-e5-large örnek sorgu setiyle karşılaştırılır (10 soru), kazanan varsayılan olur"*  
   $\rightarrow$ **[Doğrulanmadı]**: 10 soruluk sentetik bir set, Türkçe morfolojisi, teknik terimler ve uzun bağlam performansı için istatistiksel geçerliliğe sahip değildir; tek başına embedding modeli seçimi için güvenilir kabul edilemez.
3. **`01-litellm-gateway.md:L15, L51`:** *"stream_options.include_usage açık; streaming cevabın son chunk'ında token sayıları vardır"*  
   $\rightarrow$ **[Doğrulanmadı]**: Ollama'nın OpenAI uyumlu `/v1/chat/completions` uç noktasının tüm sürümlerinde streaming esnasında son chunk'ta `usage` alanını eksiksiz döndürdüğü doğrulanmamıştır; eski Ollama sürümlerinde bu alan boş dönebilmektedir.
4. **`06-agent-runtime.md:L86`:** *"Sabit kısım önde... aynı kaynaklarla ikinci çağrı kaynakları yeniden okumaz; PayCore'da 22 sn tasarruf"*  
   $\rightarrow$ **[Doğrulanmadı]**: Qwen 3.5'in Ollama CPU sunucusu üzerinde KV önbelleklemesinin (prompt caching) oturumlar arası veya istekler arası ne ölçüde korunduğu ve thread kilitlemesi durumunda cache eviction davranışının 22 saniye kazandırıp kazandırmadığı doğrulanmamıştır.
5. **(M1 İddiası):** *"LiteLLM proxy, config.yaml'daki model_list ile store_model_in_db modellerini birleştirir; aynı ad iki kaynakta olunca çift kayıt oluşur"*  
   $\rightarrow$ **[Doğrulanmadı]**: LiteLLM'in güncel versiyonunun dosya ve DB modellerini nasıl birleştirdiği ve çakışma durumunda DB'nin mi dosyanın mı kazandığı test edilmemiştir.
6. **(M3 İddiası):** *"Resmi mcp Python SDK'sının streamable HTTP istemcisi başlıkları oturum açılışında alır, çağrı başına dinamik almaz"*  
   $\rightarrow$ **[Doğrulanmadı]**: MCP SDK'nın güncel sürümünde istek başına özel header enjeksiyonu desteği bulunup bulunmadığı kod seviyesinde doğrulanmamıştır.
7. **`15-kanallar.md:L37`:** *"kullanıcı e-postası … Teams etkinliğinden alınır"*  
   $\rightarrow$ **[Doğrulanmadı]**: Bot Framework Teams turnContext activity nesnesi her kiracı yapılandırmasında e-posta taşımayabilir; `TeamsInfo.getMember` çağrısı gerektirebilir.
8. **(M9 İddiası):** *"arq WorkerSettings.cron_jobs dakikalık dinamik cron desteğini eksiksiz sunar"*  
   $\rightarrow$ **[Doğrulanmadı]**: `arq` cron desteği standarttır ancak runtime'da dinamik eklenen yeni cronjob'ları worker restart olmadan alıp almadığı doğrulanmalıdır.
