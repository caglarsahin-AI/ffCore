# Brief İncelemesi v5 (kodlama öncesi, PoC kapsamı)

İnceleyen: bağımsız gözden geçirici oturumu · Tarih: 2026-10-27 · Kaynak: PLAN.md 2.2, KARARLAR.md, handbook/, plan/00-16, state/BLOCKERS.md, BASLATMA.md. PayCore deposu açılmadı; hiçbir bulgu ona dayanmıyor.

Derece: **BLOCKER** bu haliyle kodlanamaz · **MAJOR** kodlanır ama yanlış ürün çıkar · **MINOR** netleştirme. Satır numaraları `cat -n` çıktısındandır.

## Sürüm notu

| Sürüm | Değişiklik |
|---|---|
| v3 | Tam inceleme: 6 BLOCKER, 22 MAJOR, 46 MINOR (`brief-inceleme-v3.md`, değiştirilmedi) |
| v5 (15:40) | Kaynaklar yeniden karşılaştırıldı: içerik farkı yok; bulgular v3 ile aynı |
| v5.1 (bu sürüm) | **PoC kapsamına daraltıldı.** Bulgu numaraları v3'teki gibi korundu; aradaki boşluklar çıkarılan bulgulardır. Yeni madde yok, yalnızca N47 (v3 tablo 4, satır 5'ten maddeye çevrildi) |

## PoC kapsamı ve eleme ölçütü

**PoC = M3 "ilk agent"** (PLAN:229): önyüzden Sözleşme Asistanı kurulur, chat'te kaynaklı cevap verir, SQL aracı onay bekler, Qwen/CPU ve model kararı verilir. Bunun için gereken paketler: 00, 03a, 03b, 01, 02, 04a, 05a, 06a, 07, 08 (06a ona bağlı), 09 (M3 kararı sınav setiyle verilir, TEST_STRATEGY:36), 10 (iskelet ve M3 ekranları), 11, 13 (örnek veri ve M3 e2e). PoC dışında kalanlar: 04b, 05b, 06b (facade), 12, 14, 15, 16, 17.

Bir bulgu şu üç durumdan en az birinde listede kalıyor:
1. Bir PoC paketini kodlanamaz ya da doğrulanamaz bırakıyorsa.
2. PoC'de yanlış ya da güvensiz sonuç üretiyorsa.
3. M3'e kadar donan bir sözleşmeyi (C1-C10, C12, C13) etkiliyorsa; sonradan düzeltmek `BREAKING-` gerektirir.

Çıkarılanlar bölüm 9'da tek satırlık listede duruyor. Silinmediler; ilgili paket başlamadan önce yeniden ele alınmalılar (DOC-16).

---

## 0. Özet

1. **Kodlamaya başlanabilir mi? Yalnızca 00 için evet.** Dalga 2 ve 3, B1-B4 ve B6 düzeltilmeden açılmamalı. 03, 02, 01, 04a ve 08'in kabul kriterleri daha sonraki dalgalarda doğan tablolara, istemcilere ve verilere bağlı; bu haliyle VERIFIED olamazlar.
2. **Sıra (B1, B4):**
   - 03 (dalga 2), LiteLLM team'ini açmak zorunda, ama gereken istemci 01'de (dalga 3).
   - 04a, 05a, 09 ve 10'un kabul kriterleri 13'ün örnek verisine bağlı, 13 dalga 6'da.
   - Önerim: sentetik örnek veriyi dalga 1'e çekmek (13a).
3. **CPU PoC'yi kıracak iki değer (M2, M3):**
   - Run zaman aşımı 06'da 600 s, PLAN'da 900 s. CPU'da bir `mode: tool` turu ~3 dk sürdüğü için 600 s iki turdan sonra run'ı keser.
   - Kullanıcı kimliğini taşıyan JWT 5 dakikada düşüyor. Uzun CPU run'ında mcp-search ACL'yi run ortasında kaybeder.
4. **LiteLLM (M1):** açılışta config dosyası, çalışırken DB API: bu iki ayrı model kaynağı demek. Ayrıca çalışırken eklenen sağlayıcının anahtarı ortam değişkeniyle verilemez. 01, 03 ve 10 bu konuda birbiriyle çelişiyor.
5. **Takvim:** PoC paketleri brief'te 43 agent-günü; benim tahminim ~60. Kritik yol M3'e brief sayılarıyla ~28 gün, gerçekçi tahminle ~35 iş günü. PLAN'daki "~20 gün" tutmuyor (bölüm 6).

---

## 1. BLOCKER bulgular

### B1. 03 ile 01 döngüsel bağımlı (A, F)
- 03:43 "Projects: CRUD; oluşturulunca LiteLLM team açılır." · 03:44 "API keys: … LiteLLM key ile eşlenik." · 03:90 "Kota `monthly_usd=0, block` verilen projede LiteLLM key'i 429 döner." · 03:23 "her değişiklik 01'deki `render-litellm`'i tetikler."
- `litellm_client.py (create_team, create_key, set_budget …)` 01'in teslimatı (01:17); 01 dalga 3'te, 03 dalga 2'de. 03 bu satırları kodlayamaz, 03:90'ı test edemez.
- **Öneri:** 03a `projects.litellm_team_id`'yi nullable bırakır, team açmaz. Team ve anahtar oluşturma, kotanın LiteLLM'e yansıtılması ve 03:90 kabul kriteri 01'e taşınır; 01 bunları "proje oluşturma olayına abone" biçiminde ekler. 03:44'teki "LiteLLM key ile eşlenik" silinir (KARARLAR:59).
- **Gerekçe:** 01 03a'nın tablolarına bağlı, sırayı ters çeviremiyoruz. Döngüyü yalnızca sorumluluğu 01'e taşıyarak kırabiliyoruz.

### B2. 02'nin Kapsam 7'si dalga 3'te var olmayan tablolara yazıyor (A, F)
- 02:18 "alanlar 06'nın `runs`/`run_events` listesinde tanımlıdır, bu paket doldurur ve Langfuse'a yansıtır." 02:19-25 `runs.model_ms … slowest_step`, `guardrail_hook` olayı ve "Agent sayfası Usage/Overview (10)" ister. 02 dalga 3'te, 0,5 gün; `runs` ve `run_events` 06a'da (dalga 4) doğuyor.
- **Öneri:** 02:18-25 06a Kapsam'ına taşınır (+1,5 gün). 02 yalnızca 1-6. maddeleri ve ilk iki kabul kriterini taşır.
- **Gerekçe:** Tablonun sahibi 06 (PLAN 6). Alanı dolduran kodun da tablo sahibinin dosyasında olması touch-zone kuralının (MULTI_AGENT:30) gereği.

### B3. 01'in fallback kabul kriteri ölçülemez ve mekanizması yok (A)
- 01:49 "`chat-fallback` kaydı varsa oraya geçer ve `run_events`'te `fallback` olayı görünür". 01:15 "Her fallback geçişi 06'ya `run_events.fallback` … yazılır."
- İki sorun var. `run_events` dalga 3'te yok. Fallback LiteLLM router'ının içinde gerçekleşiyor ve brief, backend'in bunu nasıl öğreneceğini söylemiyor.
- **Öneri:** 01, `litellm_client` cevabında "istenen model ≠ cevap veren deployment" karşılaştırmasıyla bir `FallbackObserved(kaynak, hedef, neden)` sonucu döner ve bunu unit testle kanıtlar. `run_events.fallback` yazımı 06a kabul kriterine taşınır.
- **Gerekçe:** C9 (`fallback` SSE olayı) M3'te donuyor. Olayın kaynağı şimdi tanımlanmazsa donmuş bir sözleşmenin üreticisi olmaz.

### B4. Örnek veri sahipliği: erken dalgalar 13'ün verisine bağlı, 13 dalga 6'da (A, F)
- 04:96 "`data/samples/contracts/` içindeki örnek sözleşmelerle `tests/test_ingest.py`" ve 04:102 "'fesih bildirim süresi' sorgusu ilgili maddeyi ilk 3'te getirir" (04a, dalga 3).
- 05:46 "demo 'agent sunum DB'si' (13'te doldurulur; bu pakette minimal seed)". 09:72 `sozlesme-35.json` "(13 ile birlikte tamamlanır)". 10:66 "13'teki örnek belgelerle".
- `data/samples/` 13'ün touch-zone'u (MULTI_AGENT:36). 13, PLAN:204 ve 13:3'te dalga 6'da; BASLATMA:65'te ise dalga 5'te. 13:11 "kullanıcının sağladığı örnek sözleşmeler": bugün böyle bir dosya yok.
- **Öneri:** 13 ikiye bölünür.
  - **13a "örnek veri"**, dalga 1'de test agent'ı tarafından hazırlanır (1 gün): 5 sentetik sözleşme (PDF+DOCX), demo şema ve seed, 35 soruluk set iskeleti.
  - **13b "M3 e2e ve ölçüm"** dalga 5'te kalır.
- **Gerekçe:** Kabul kriteri verisi olmadan 04a VERIFIED olamaz (EXECUTION_HANDBOOK:69).

### B6. 08 dalga 2'de LiteLLM kancasını ve 06 bağlantısını kodlayamaz; kancanın gerekçesi de geçersiz (F, ARCH-09/07)
- 08:3 "Dalga: 2". 08:38 "`render-litellm` (01) her modele proje politikasını `guardrails:` olarak yazar". 01 ve LiteLLM servisi dalga 3'te. 08:37 "06 bu kancaları no-op bırakmıştı"; PLAN:221 ise "08 önce biter" diyor.
- Kancanın gerekçesi 08:38'de: "kurumun kendi uygulaması … LiteLLM üzerinden gittiğinde". Oysa PLAN:163 ve KARARLAR:59, dış istemcinin LiteLLM'e hiç ulaşmadığını söylüyor. Kanca kalırsa runtime'ın her model çağrısında guardrail iki kez koşar.
- **Öneri:** `litellm_hook.py` ve 08:38 kaldırılır (−0,5 gün). 08 dalga 2'de engine'i, kural türlerini ve `POST /internal/guardrails/evaluate`'i teslim eder; graf düğümlerine bağlantı 06a'nın işidir (06:81).
- **Gerekçe:** 06a 08'e bağlı olduğu için 08 PoC'nin kritik yolunda. Tek giriş kapısı ilkesi zaten tek denetim noktası sağlıyor (ARCH-09).

---

## 2. MAJOR bulgular

### M1. LiteLLM: iki model kaynağı ve çalışırken verilemeyen anahtar (B, C, ARCH-09)
- 01:11 "Açılışta `make render-litellm` statik `deploy/litellm/config.yaml` üretir … Çalışırken … DB'li model yönetim API'siyle". 01:37 "`render-litellm` anahtarları çözüp LiteLLM'e ortam değişkeni olarak verir". 03:23 ve 10:25 "kayıt sonrası `render-litellm` tetiklenir"; bu, PLAN:161 "yeniden başlatma ve `/config/reload` yok" ile çelişiyor.
- **Öneri:** `config.yaml`'da `model_list` olmaz. `render-litellm` tek bir **uzlaştırıcıya** dönüşür: açılışta da kayıtta da tablolardan `/model/new|update|delete`'e yazar. Anahtar `litellm_params.api_key` ile gider ve LiteLLM DB'sinde `LITELLM_SALT_KEY` ile şifrelenir; bu ikinci şifreli depo SECURITY'ye yazılır. 03:23 ve 10:25 "uzlaştırıcıyı tetikler" diye düzeltilir.
- **Gerekçe:** M1 kabulü ("`models` tablosundan üretilen config ile … cevap verir", PLAN:227) bu mekanizmaya dayanıyor.

### M2. Zaman aşımı değerleri üç yerde üç farklı (B)
- PLAN:72 "LLM çağrısı 60 s / run 120 s | CPU: LLM çağrısı 600 s / run 900 s; GPU: 120 s / 300 s". 06:135 "`limits.timeout_s` varsayılanı CPU'da 600, GPU'da 120" (bunlar çağrı değerleri, run değil). 06:36 örnek tanım `"timeout_s":300`.
- **Öneri:** PLAN kazanır (CHANGE_CONTROL:25). Run zaman aşımı seed'de `run_timeout_s` olarak durur: llmaas 120, cpu 900, gpu 300. 06:36 örneği `null` (seed varsayılanı) olur.
- **Gerekçe:** CPU'da `mode: tool` turu ~3 dk (06:135). 600 s sınırı karma asistanı M3 demosunda keser.

### M3. mcp-search kimliği: havuzlanan oturum ve run ortasında düşen JWT (G)
- 05:19 "MCP istemcisi … streamable HTTP taşıma; bağlantı havuzu". 05:53 mcp-search, kullanıcıyı `X-On-Behalf-Of` ile taşıyor. 03:37 "`exp ≤ 5 dk`".
- İki sorun var:
  1. Başlık oturum açılırken verildiği için havuzdaki bir oturum başka kullanıcının kimliğini taşıyabilir (doğrulanmadı, U5). Bu, 05:67 "analyst, admin belgesini göremez" kriterini eşzamanlı run'da bozar.
  2. CPU'da run 900 s; JWT 5 dakika sonra düşer.
- **Öneri:** JWT her araç çağrısında yeniden imzalanır. `forward_user` araçları için havuz yoktur, oturum çağrı başına açılır. Kabul kriteri: "iki kullanıcının eşzamanlı run'ında mcp-search ACL'si karışmaz".
- **Gerekçe:** C2'nin alanları değişmiyor, yalnızca imzalama anı değişiyor. C2 M2'de donmadan önce yazılmalı.

### M7. Gerçek sözleşmeler örnek veri olarak depoya giriyor (G, B)
- 13:11 "kullanıcının sağladığı örnek sözleşmeler `data/samples/contracts/` altına (… içeriyorsa 08'deki maskeleme ile temizlenmiş kopya)". SECURITY:16 "(`data/samples/`) sentetiktir; gerçek kurum belgesi oraya konmaz."
- **Öneri:** Yalnızca sentetik sözleşmeler (B4'teki 13a). Gerçek belgeyle deneme, kullanıcının makinesinde ve depo dışında yapılır. Geliştirmede Anthropic'e yalnızca sentetik veri gider (SECURITY:17).
- **Gerekçe:** Veri sınırı D sınıfı. Ad-soyad recall'u 0,85 olan bir maskeleme bu sınırı taşıyamaz.

### M8. Kuyruk tasarımı belirsiz; 04 reddedilmiş `rq`'yu geri getiriyor (A, B; C10)
- 04:35 "`arq` ya da `rq`"; PLAN:166 tek kütüphane `arq` diyor, KARARLAR:53 `rq`'yu reddetti. 06:58 "tüm model çağrıları tek Redis kuyruğundan geçer ve iki sınıfa ayrılır" diyor ama ardından üç sınıf sayıyor (06:60-62). C10'da iki LLM kuyruğu var; "etkileşimli-düşük" hangi kuyrukta, belli değil.
- **Öneri:**
  1. 04:35 "`arq`, kuyruk `ingest`" olur.
  2. Run'lar arq işidir (`llm-interactive`; sınav ve toplu işler `llm-background`). Model çağrıları `litellm_client` içinde Redis tabanlı, öncelikli bir eşzamanlılık yuvasından geçer (`LLM_SLOTS`: cpu 1). Etkileşimli-düşük, `llm-background` kuyruğunda pencere kuralı olmayan bir sınıftır.
- **Gerekçe:** C10 M3'te donuyor. arq'ın öncelik desteği yok; öncelik çağrı anında, yuvada çözülmeli.

### M10. Embedding nerede çalışıyor: üç belge, üç cevap (B, ARCH-10)
- PLAN:66 "Ollama ya da süreç içi". 01:14 "`ollama/bge-m3` ya da süreç içi TEI". 04:44 "LiteLLM `embed-default` üzerinden". 04:122 "Yerel reranker ve embedding model nesneleri süreç başına bir kez yüklenir".
- **Öneri:** Embedding her profilde Ollama `bge-m3` → LiteLLM `embed-default` yolundan gider. Reranker tek süreç içi model olarak kalır. "ya da"lar silinir.
- **Gerekçe:** 04a kritik yolda. İşçinin iki ayrı gerçekleştirme arasında seçim yapması gerekmemeli (ARCH-10).

### M11. `mode: tool` araç adları donmuş C7 ile çelişiyor (B, C)
- 06:82 "`mode: tool` KB'ler `search_documents` aracı olarak eklenir." 06:110 "üç araç üretilir: `knowledge_search`, `knowledge_read_document`, `knowledge_read_document_lines`". CONTRACTS:13 (C7) `search_documents(query, kb_key, top_k)`.
- **Öneri:** C7 kazanır. 06:110 silinir.
- **Gerekçe:** C7 M3'te donuyor. Karma asistan (13:16) `mode: tool` kullanıyor, yani PoC demosu doğrudan bu araçtan geçiyor. Tam belge okuma CPU bütçesini (06:54) de aşar.

### M12. 09'un aşama teşhisi için gereken veri kaydedilmiyor (A)
- 09:25 "`not_retrieved`: `expected_docs` hibrit adaylarda (top-30) yok". 09:21 "`outcome`, `run_events`'ten türetilir". Oysa 06:19 `sources` olayı yalnızca seçilen ve taban altında elenen parçaları taşıyor; `kb_queries`'te (04:87) `run_id` yok.
- **Öneri:** 04a'da `kb_queries`'e `run_id nullable` ve `candidates jsonb` (top-30 `document_id` + skorlar) eklenir; arama API'si `X-Run-Id` başlığını kabul eder.
- **Gerekçe:** M3'teki model kararı "arama mı, model mi başarısız?" sorusunun cevabına dayanıyor. Bu veri 04a'da kaydedilmezse 09'da geriye dönük üretilemez.

### M13. Fail-loud ihlalleri: sessiz uyarı, kırpma ve yedek (ARCH-06)
- **06:54 "`OLLAMA_CONTEXT_LENGTH` ile tutarsızsa açılışta uyarı."** PayCore'un ölçtüğü sessiz kırpma hatasının (00:39) aynısı. **Öneri:** Tutarsız agent sürümünü kaydetmek 400 alır; açılışta tutarsız seed varsa `/readyz` 503 döner.
- **06:45 "sonra RAG top_k düşürülür".** **Öneri:** Düşen parçalar `sources` olayında `dropped_by_budget` olarak listelenir.
- **05:19 "`TOOL_RESULT_MAX_CHARS` ile kırpılır".** **Öneri:** Modele de görünen `[kırpıldı: N/M karakter]` işareti eklenir ve olaya `truncated=true` yazılır; `run_sql` (05:66) zaten böyle çalışıyor.
- **02:15 "Langfuse erişilemezse yerel `backend/prompts/*.md` yedeğine düşer".** **Öneri:** Yerel dosya yalnızca seed'dir. Langfuse yoksa son önbellek kullanılır, `prompt_cache_stale` olayı yazılır ve uyarı düşer.
- **Gerekçe:** Dördü de CPU PoC'nin ölçümünü sessizce bozar; M3 kararı yanlış veriyle verilir.

### M15. Boş ACL'nin anlamı tanımsız (A, G)
- 04:73 "rolü ve kimliği `documents.acl_*` ile sorguda filtrelenir"; `acl_roles` ve `acl_users` boşsa belgeyi kimin göreceği yazmıyor.
- **Öneri:** 04a'da kural yazılır: "iki dizi de boşsa belge projenin tüm üyelerine açıktır; elle yüklemede ekran ACL seçimini zorunlu adım olarak sorar (varsayılan `analyst`)."
- **Gerekçe:** 04a ve 05a'nın ACL kabul kriterleri (04:103, 05:67) bu varsayılana dayanıyor.

### M20. Kota: üç kapsamın uygulayıcısı yok; bir kabul kriteri facade'a bağlı (A)
- 03:31 `scope_type: project|group|user|api_key|model|provider`. R2.3 yalnızca `project`, `api_key`, `user`, `concurrent` için uygulama yeri veriyor; `group`'un tablosu yok.
- 03:88 "facade 429 döner": facade 06b'de, PoC dışında. 03b bu kriteri test edemez.
- **Öneri:** `scope_type` bu sürümde `project|api_key|user`. 03:88 06b kabul kriterine taşınır; 03b, kota motorunun 429 kararını unit testle kanıtlar.
- **Gerekçe:** Uygulayıcısı olmayan enum değeri "ekranda var, çalışmıyor" demek (ARCH-13).

### M21. Çekirdek yüzeyi Cognipeer kopyasıyla genişliyor (ARCH-07, ARCH-10; C8)
- 04:85 `chunk_strategy (recursive|token|markdown|sentence|semantic), separators[], parent_window, contextual_headers, oversample, response_detail, filterable_fields[]`. 04a "veri modeli (tam)" olduğu için kritik yola iş ekliyor.
- 06:107 `webhook_url`, `budget_usd`, `raw_output_tools[]`. Sonuncusu, araç çıktılarının varsayılan olarak özetlendiğini ima ediyor; böyle bir adım hiçbir yerde tanımlı değil.
- **Öneri:** 04:85'ten yalnızca `hybrid, rerank_model, default_top_k, default_min_score, normalizer_config_id` kalır; `chunk_strategy` tek değerli (`heading`). 06:107'den bu üç alan çıkarılır.
- **Gerekçe:** `definition` şeması (C8) M3'te donuyor. Kullanılmayan alanlar donarsa ya hep taşınır ya da `BREAKING-` gerekir.

### M22. 13'ün GPU sütunu var olmayan donanımı ölçmeyi kabul kriteri yapıyor (A)
- 13:35-43 `gpu` sütununda ≤10 s, ≤20 s eşikleri var. KARARLAR:67 GPU alımını açık bırakıyor.
- **Öneri:** `gpu` sütunu "donanım varsa ölçülür, yoksa `NOT_RUN (PENDING_ENV)`" olarak işaretlenir. M3 için geçerli sütunlar `cpu` ve `llmaas`.
- **Gerekçe:** Aksi halde 13b, PoC'de VERIFIED olamaz (EXECUTION_HANDBOOK:69).

---

## 3. MINOR bulgular (tek satır)

- **N4** 00:40 ısınma ve `/readyz` 00'da tanımlanıyor, ama 00 "uygulama kodu" içermiyor (00:45); ENVIRONMENT:35 `make smoke`'un `/readyz`'ı denetlediğini söylüyor. 00 bu haliyle smoke'u geçemez. `warmup` 04a'ya, 00'a yalnızca `/healthz` kalmalı.
- **N11** 04:19 `chunks` ve 05:48 `few_shots` tablolarında `project_id, created_by` yok; C3 her tabloda istiyor ve M2'de donuyor.
- **N16** 06:95 SSE listesinde `progress` ve `fallback` yok; C9 (CONTRACTS:15) bunları sayıyor ve M3'te donuyor.
- **N23** 08:14 `action_taken: block|redact|tokenize|warn|log`, 08:15 `default_action: detect|redact|mask|tokenize|block`. C4 08 merge'ünde donmadan `mask` eklenmeli, `detect`→`log` eşlemesi yazılmalı.
- **N47** `outcome_label` iki listeyi adlandırıyor: 06:18 (3 değer), 09:17 (8 değer), TERMINOLOGY:69. İki terime ayrılmalı: `runs.outcome_label` ve `eval_scores.outcome` (ARCH-13). İkisi de M3'teki veri modelinde.

---

## 4. Brief'ler arası çelişkiler

| # | Brief A (alıntı) | Brief B (alıntı) | Öneri |
|---|---|---|---|
| 1 | 01:11 "Çalışırken … DB'li model yönetim API'siyle … yeniden başlatma ve `/config/reload` kullanılmaz" | 03:23 "her değişiklik 01'deki `render-litellm`'i tetikler" · 10:25 "kayıt sonrası `render-litellm` tetiklenir" | Tek uzlaştırıcı (M1) |
| 2 | 03:30 "LiteLLM anahtarı yoktur" | 03:44 "LiteLLM key ile eşlenik." | 03:44 düzeltilir (B1) |
| 3 | PLAN:166 "tek kütüphane `arq`" · KARARLAR:53 | 04:35 "`arq` ya da `rq`" | `arq` (M8) |
| 4 | 06:18 `outcome_label (declined\|below_threshold\|answered)` | 09:17 `outcome: not_retrieved\|…` · TERMINOLOGY:69 | İki terim (N47) |
| 5 | 06:82 "`search_documents` aracı olarak eklenir" · CONTRACTS:13 (C7) | 06:110 "üç araç üretilir: `knowledge_search` …" | C7 (M11) |
| 6 | PLAN:221 "08 önce biter." | 08:37 "06 bu kancaları no-op bırakmıştı" | 08 engine'i teslim eder, 06a bağlar (B6) |
| 7 | PLAN:204 · 13:3 "Dalga: 6" | BASLATMA:65 "07, 13 (M3 e2e)" · WORK_QUEUE:27 | 13a dalga 1, 13b dalga 5 (B4) |
| 8 | 08:14 `action_taken` | 08:15 `default_action` · TERMINOLOGY:67 | Tek liste (N23) |
| 9 | 00:39 `make smoke` doğrular · FELSEFE_UYGULAMA:20 "doğrulanmazsa `make smoke` kırmızı" | 06:54 "tutarsızsa açılışta uyarı" | 400 / `/readyz` 503 (M13) |
| 10 | PLAN:72 "run … CPU 900 s; GPU 300 s" | 06:135 "CPU'da 600, GPU'da 120" · 06:36 `"timeout_s":300` | PLAN (M2) |

---

## 5. Felsefe ihlalleri

| İlke | Brief | Alıntı | Öneri |
|---|---|---|---|
| ARCH-06 | 06:54 | "`OLLAMA_CONTEXT_LENGTH` ile tutarsızsa açılışta uyarı" | 400 / 503 (M13) |
| ARCH-06 | 06:45 | "sonra RAG top_k düşürülür" | `dropped_by_budget` (M13) |
| ARCH-06 | 05:19 | "`TOOL_RESULT_MAX_CHARS` ile kırpılır" | Görünür kırpma işareti (M13) |
| ARCH-06 | 02:15 | "yerel `backend/prompts/*.md` yedeğine düşer" | Seed + önbellek + olay (M13) |
| ARCH-07 | 04:85 | "`chunk_strategy (recursive\|token\|markdown\|sentence\|semantic)` …" | Ölçülmüş tek yol (M21) |
| ARCH-07 | 06:107 | "`webhook_url` …, `budget_usd`, … `raw_output_tools[]`" | Çıkarılır (M21) |
| ARCH-07 | 03:31 | `scope_type: …group…model\|provider` | `project\|api_key\|user` (M20) |
| ARCH-09 | 08:38 | "`litellm_hook.py` … `CustomGuardrail`" | Kaldırılır (B6) |
| ARCH-09 | 01:11 | açılışta statik config + çalışırken DB API | Tek uzlaştırıcı (M1) |
| ARCH-10 | 04:35 | "`arq` ya da `rq`" | `arq` (M8) |
| ARCH-10 | 01:14 · PLAN:66 | "`ollama/bge-m3` ya da süreç içi TEI" | Ollama → LiteLLM (M10) |
| ARCH-10 | 06:107 | "`raw_output_tools[]` (çıktısı özetlenmeyecek araçlar)" | Gizli özetleme; alan kaldırılır (M21) |
| ARCH-13 | TERMINOLOGY:69 · 06:18 · 09:17 | `outcome_label` iki listeyi adlandırıyor | İki terim (N47) |

---

## 6. Süre ve dalga değerlendirmesi (PoC paketleri)

### 6.1 Paket tahminleri

| Paket | Brief | Tahminim | Gerekçe |
|---|---|---|---|
| 00 | 1 | 1,5 | Langfuse v3 yığını, bağlam doğrulaması |
| 01 | 1,5 | 3 | Uzlaştırıcı (M1), `request_policy` eşlemesi, fallback tespiti, B1'den gelen team/anahtar işi |
| 02 | 0,5 | 1 | B2 sonrası kalan kısım |
| 03a | 2,5 | 3 | Rol × mod matrisi, OpenAPI tarayıcı test |
| 03b | 4,5 | 5 | Kota, uyarılar, audit partition, retention, OBO |
| 04a | 5 | 7 | Docling süreç havuzu, üç kapı, hibrit + reranker + ACL, D1-D6 kriterleri |
| 05a | 3 | 4 | MCP istemci + mcp-sql + mcp-search + kimlik (M3) |
| 06a | 4,5 | 7 | Graf, bütçe, yuva (M8), SSE, interrupt/resume, B2'den +1,5 |
| 07 | 1,5 | 1,5 | Gerçekçi |
| 08 | 5 | 5,5 | Kanca kalkar (−0,5), Türkçe NER entegrasyonu |
| 09 | 3,5 | 4,5 | 8 scorer, teşhis (M12), karşılaştırma |
| 10 (M3 ekranları) | ~6* | 10 | İki tema × iki mod ekran görüntüsü, axe, sihirbaz |
| 11 | 2,5 | 3 | Bileşenler 10'da hazırsa |
| 13 (13a + 13b) | 2 | 4 | 13a 1 + 13b 3 (CPU'da tek koşu ~3 saat) |
| **Toplam** | **~43** | **~60** | +%40 |

\* Brief 10'u ekran bazında bölmüyor; M3 ekranlarının 8,5 günlük toplamdan payını ben tahmin ettim.

### 6.2 Kritik yol (M3'e)

- **PLAN:210 "~20 gün".** Brief sayılarıyla toplam: 00 (1) → 03a (2,5) → 01 (1,5) → 04a (5) → 05a (3) → 06a (4,5) → 09 (3,5) → 13 (2) = **23 gün**.
- **Dalga kapılarıyla:** dalga 2 = 5 gün (08), ama BASLATMA:62 03b ile 08'i aynı işçiye sırayla verdiği için 8,5 gün. Dalga 3 = 7, dalga 4 = 7,5, dalga 5 = 5,5. Toplam **~28 gün**.
- **Benim tahminlerimle:** **~35 iş günü.**
- **Önerim:** kapı, dalga yerine paket bağımlılığı üzerinden çalışsın (EXECUTION_HANDBOOK:9 "bağımlı paketler MERGED"). Dalga yalnızca Alembic merge ve tutarlılık denetimi noktası olarak kalsın. Bu, 3-5 gün kazandırır.

### 6.3 Dalga sırası düzeltmeleri (PoC)

1. 13a dalga 1'de, test agent'ıyla, 00'a paralel (B4).
2. 02 kapsam 7 06a'ya (B2); 01'in team/anahtar işi 03'ten 01'e (B1).
3. 08'den kanca çıkar (B6); işçi B'nin 03b'den sonra başlaması 06a'yı beklettirmez.
4. 04b, 05b, 06b, 12 ve 14-16 M3'ten sonra başlar; PoC takvimine girmez.

---

## 7. Katılmadığım kararlar (KARARLAR.md)

- **KARARLAR:30 "arka plan mesai dışı pencerede" (her iki profil için).** Katılmıyorum. Kural CPU'daki tek şerit için doğru. `llmaas`'ta sınav ve judge koşularını geceye ertelemek, M3 kararı için gereken "değiştir, sına" döngüsünü günlere yayar ve karşılığında hiçbir şey korunmaz. **Önerim:** `BACKGROUND_WINDOW` profil seed değeri olsun: `airgap cpu` için `19:00-07:00`, `llmaas` ve `gpu` için boş. Kararı kullanıcı verir; `DECISION-` olarak açılmasını öneriyorum.
- **KARARLAR:60 "LiteLLM'e ortam değişkeniyle (P6)".** Anahtarın DB'de şifreli durmasına katılıyorum. "LiteLLM'e ortam değişkeniyle" yarısına katılmıyorum, çünkü çalışırken yeniden başlatmadan model ekleme kararıyla (PLAN:161) bir arada tutulamıyor (M1).

---

## 8. Doğrulanmamış iddialar

- **U1** (M1) LiteLLM, `config.yaml`'daki `model_list` ile DB'deki modelleri birleştirir; aynı ad iki kaynakta olunca çift kayıt oluşur.
- **U2** (M1) `/model/new` gövdesindeki `api_key`, LiteLLM DB'sinde `LITELLM_SALT_KEY` ile şifreli saklanır (sürüme bağlı).
- **U3** (B3) LiteLLM cevap gövdesindeki `model` alanı fallback sonrası cevap veren deployment'ı gösterir; yoksa başlıklara (`x-litellm-*`) bakmak gerekir.
- **U4** (M8) LiteLLM proxy'nin OSS sürümünde istek önceliklendirme özelliği olabilir; varsa M8'deki yuva onun üstüne kurulmalı (ARCH-09).
- **U5** (M3) Resmi `mcp` Python SDK'sının streamable HTTP istemcisi başlıkları oturum açılışında alır, çağrı başına almaz.
- **U12** (bölüm 6) Süre tahminlerim yargıdır; PayCore'daki gerçekleşen sürelere bakılmadı.

---

## 9. PoC dışına çıkarılanlar (ilgili paket başlamadan önce ele alınmalı)

- **06b (facade) öncesi:** B5 (`user` alanı ile ACL atlatma, `api_keys` rolü), M4 (API anahtarıyla onay).
- **05b öncesi:** M14 (`/mcp/{key}/` ikinci dış giriş).
- **Sunucu ve 12 öncesi:** M5 (SSRF, 16'nın fs kökü), M6 (CSRF/CORS), M16 (egress uygulaması, Teams içeriden erişim).
- **M4 (08 PII ve 09 yayın kapısı) öncesi:** M17 (akışta geri çevirme), M18 (kendi yazdığı test seti).
- **14 ve 16 öncesi:** M19 ("bunu hatırla" PII), M15'in 16 kısmı (grup genişletme).
- **Kritik değil, uygun ilk PR'da:** M9 (APScheduler → arq cron), M3'ün üçüncü taraf upstream kısmı; N1-N3, N5-N10, N12-N15, N17-N22, N24-N46. Metinleri `brief-inceleme-v3.md`'de.
