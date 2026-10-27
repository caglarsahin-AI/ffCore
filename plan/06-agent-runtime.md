# 06. Agent runtime: tanım -> LangGraph, çalıştırma API'si, streaming [FFCore Agents]

**Bağımlılık:** 03a, 03b, 01, 02, 04a, 05a, 08 (hook adları). **Süre:** 10 gün, iki alt paket ve iki PR (06a 7, 06b 3; inceleme v4-v6). **Dalga:** 06a dalga 4, 06b PoC sonrası. **PoC:** 06a.

**06a, çekirdek (≈6,5 gün, kritik yol, M3 öncesi zorunlu; PoC'de iki agent, PLAN 2d):** veri modeli (tam, facade alanları dahil), iz ve oturum alanları (02'den taşındı, B1), agent tanımı şeması, bağlam bütçesi, iş önceliği ve kuyruk (`LLM_SLOTS`, C8), graf üretimi, run API ve SSE, `resume`, tracing, `mode: tool` için `search_documents` aracı (C11), platform kuralları, guardrail kancalarının bağlanması (B3), guardrail engeli hata gövdesi, `run_events.fallback` ve `tool_call/tool_result` yazımı (B2, B3), iki aşamalı oluşturma API'si, yayın/geri alma. Kabul kriterleri: facade ve manifest dışındakiler.
**06b, dış yüz (≈3 gün, PoC sonrası; 03c ile birlikte):** OpenAI-uyumlu facade (`/v1/chat/completions`, `/v1/models`, kimlik eşleme yalnızca `impersonate` ile (B7), `x_platform` event'leri, `annotations[]`, onay akışı: istemci onay veremez, bekler (C4)), düz model proxy'si ve API anahtarı kota uygulaması (03c), dış agent (`kind: external`), manifest içe/dışa aktarma. Kabul kriterleri: facade ve manifest maddeleri.

## Amaç

Önyüzden doldurulan agent tanımını (JSON) çalışan bir LangGraph grafına çevirmek; agent'ı sürümleyip yayınlamak; sohbet ve API üzerinden çalıştırmak; her adımı kaydetmek. Onay bekleme noktaları burada hazırlanır, kuyruk 07'de.

## Kapsam

### Veri modeli

- `agents(id, project_id, key, name, description, status: draft|published|inactive, current_version_id, kind: native|external)`
- `agent_versions(id, agent_id, version, definition jsonb, created_by, created_at, published_at, eval_run_id)`
- (R5.1, tek doğru liste) `runs(id, project_id, agent_version_id, user_id nullable, api_key_id nullable, channel: chat|api|test|slack|teams|mattermost|widget, status: queued|running|waiting_approval|waiting_user|completed|failed|cancelled|abandoned, started_at, ended_at, input, output, tokens_in, tokens_out, cost_usd, langfuse_trace_id, trigger_type: chat|api|schedule|webhook, error_code (limit aşımında `limit_reached`, C13), reference_id, confidence, confidence_formulas jsonb, outcome_label (declined|below_threshold|answered; C24: sınav aşama etiketi ayrı, `eval_scores.outcome`), model_ms, tool_ms, retrieval_ms, unaccounted_ms, slowest_step, queue_wait_ms)`. `abandoned`: istemci SSE'yi kapattı ve run tamamlanmadı (02). `queued`: P7 kuyruğunda bekliyor.
- (R5.1) `run_events(id, run_id, seq, ts, type: queued|llm_call|tool_call|tool_result|approval_requested|approval_resolved|question|user_answer|guardrail_hook|budget|progress|memory_used|sources|answer|fallback|error, payload jsonb)`. `guardrail_hook` (08 aşaması ve kararı), `budget` (P8 planlanan/gerçekleşen), `progress` (D6 kullanıcıya ara bilgi), `memory_used` (14 hangi maddeler), `sources` (seçilen ve rerank tabanı altında elenen parçalar). `fallback` (01: kaynak model, hedef model, neden; yalnızca açık `chat-fallback` kaydıyla olur).
- `conversations(id, project_id, agent_id, user_id, title)` ve `messages(id, conversation_id, run_id, role, content, sources jsonb, feedback jsonb nullable (11: beğeni/şikâyet ve not, C23))`
- LangGraph checkpointer: `langgraph-checkpoint-postgres`, aynı Postgres, `checkpoints` şeması.

### İz ve oturum alanları (02'den taşındı, B1; tablo sahibi doldurur)

- `runs.status` listesi `abandoned` içerir (istemci akışı kapattı, run tamamlanmadı); "waiting on a person" 07'deki `waiting_approval`.
- Run özeti için türetilmiş alanlar `runs.model_ms, tool_ms, retrieval_ms, unaccounted_ms, slowest_step` ("zaman nereye gitti" kartı) ve araç/model bazında çağrı sayısı, toplam ve maksimum süre; 10'da aynı kart.
- `run_events.type` `guardrail_hook` içerir ve olaylar `iteration` alanıyla gruplanır (Grouped / Timeline / List görünümleri 10'da).
- Olay detayı: tür, model, istenen araç, süre, aktör (agent adı, rol, sürüm), finish reason, token in/out/total, istek ve yanıt byte, span kimlikleri (trace id, span id, parent id), bölümler (araç tanımları, system, user, araç çağrısı ve sonucu), metadata, ham JSON. `run_events.payload.request_messages` modele giden **nihai, maskelenmiş** mesaj listesini saklar; `content` retention sınıfına tabidir, `logData=false` ile kapatılabilir (03c ve 08 ile ortak kural; ham kullanıcı mesajı yalnızca `messages.content`'te).
- `system_prompt` üç parçadan birleştirilir ve izde ayrı gösterilir: `platform_rules`, `runtime_profile`, `user_instructions`.
- Agent sayfası Usage/Overview (10): son 7/30 gün run sayısı, başarı oranı, ortalama süre, token, "kullanılan araçlar" (son 30 günde her aracı çağıran run sayısı), günlük run grafiği; veri `runs`/`run_events`'ten, Langfuse'a `tracing.py` (02) ile gider.
- Guardrail kancası izde ayrı olay (`guardrail_hook`); gecikme `guardrail_events.latency_ms`'ten, `run_events` yalnızca referans tutar.

### Agent tanımı şeması (`definition` JSON, Pydantic ile doğrulanır)

```
{
  "model": "chat-default",
  "system_prompt": "...",             // ya da langfuse_prompt: {name, label}
  "variables": [{"key":"hospital_name","label":"Hastane adı","default":"..."}],
  "knowledge": [{"kb_key":"sozlesmeler","mode":"always|tool","top_k":8,"min_score":null,"filter":{"scope":["confluence:DWH","jira:PRSIM"]}}],   // filter additive (v9 P7): PayCore profilleri = filtreli agent; kaynak/alan kapsamı, 04 arama filtresine gider   // min_score yalnızca reranker kapalıyken (K2); top_k seed'e göre (R5.4)
  "tools": [{"tool_key":"mcp-sql","actions":["get_schema","run_sql"]}],
  "approval": {"actions":["mcp-sql.run_sql"],"assign_to":"developer"},   // tool_actions.needs_approval ile birleşir; assign_to 07'nin okuduğu alan (R5.2); `user` rolü hiçbir zaman onaylayamaz
  "ask_user": true,
  "guardrail_policy_key": "default",                // 08
  "structured_output": null | {json_schema},
  "limits": {"max_tool_calls":6,"max_turns":10,"run_timeout_s":null,"context_tokens":16000,"output_tokens":800},
  "context_policy": {                               // P8: bağlam bütçesi, birinci sınıf alan
    "history_turns": 6,                             // son N tur ham; öncesi özet
    "history_summarize": true,                      // eşik aşılınca tek model çağrısıyla özet (CPU'da arka plan, bir sonraki turda kullanılır)
    "history_max_tokens": 3000,
    "memory_max_tokens": 300,
    "rag_max_tokens": 4000,                         // R5.4: cpu seed top_k 8 / 4000; llmaas ve gpu seed top_k 12 / 8000; 13 ölçümleri bu değerlerle
    "tools_schema_max_tokens": 1500,
    "output_reserve_tokens": 800,
    "trim_order": ["history", "rag", "memory"]      // bütçe aşılınca önce geçmiş kırpılır, sonra RAG top_k düşürülür (düşen parçalar `sources.dropped_by_budget` olarak olaya yazılır, C13), en son hafıza
  },
  "answer_rules": {"cite_sources":true,"unknown_reply":"Bu bilgi belgelerde yok.","confidence_formula":"cited"   /* PayCore seed'inde `max` (ölçülmüş karar); rozet yine kapalı */,"confidence_threshold":null,"show_confidence":false,"verify":false,"max_answer_tokens":400},
  "reasoning": "none"                                // PayCore D6: Qwen'de thinking kapalı; model kaydı varsayılanı
}
```

### Bağlam bütçesi (P8)

`prepare` düğümü her turda bütçeyi hesaplar: `limits.context_tokens − (system + platform_rules + tools_schema + output_reserve)` kalanı `context_policy` paylarıyla hafıza, RAG ve geçmişe dağıtır; pay aşılırsa `trim_order` sırasıyla kırpar (geçmiş: en eski turlar düşer ya da özet devreye girer; RAG: top_k azalır, parçalar hiç kesilmez; hafıza: en düşük kullanımlı maddeler düşer). Token sayımı 04'teki `approx_tokens` ile (Türkçe payı dahil); gerçek usage dönünce `run_events`'e `budget` event'i yazılır (planlanan vs gerçekleşen). Bütçe `models.limits.context_window`'u aşamaz; `context_tokens > OLLAMA_CONTEXT_LENGTH` olan agent sürümü kaydedilemez (400 `context_configuration_invalid`); açılışta seed değeriyle tutarsızlık varsa `/readyz` 503 (C13; sessiz kırpma yok). RAG'den bütçe nedeniyle düşen parçalar `sources` olayında `dropped_by_budget` listesiyle görünür. CPU'da prompt işleme gecikmenin ana kalemi olduğu için varsayılanlar küçük tutulur; GPU profilinde seed farklıdır.

### İş önceliği ve kuyruk (P7 kararı)

CPU'da Ollama tek şerittir (`OLLAMA_NUM_PARALLEL=1`). **Uygulama (C8, iki katman):** (1) **Run düzeyi:** her run bir `arq` işidir; kullanıcı run'ları `llm-interactive` kuyruğuna, sınav/toplu/hafıza işleri `llm-background` kuyruğuna girer (C10 kuyruk adları). (2) **Model çağrısı düzeyi:** worker içindeki her tekil model çağrısı `litellm_client`'ta Redis tabanlı öncelikli eşzamanlılık yuvasından (`LLM_SLOTS`: cpu 1, gpu N, llmaas sağlayıcı eşzamanlılığı) geçer; yuva boşalınca önce etkileşimli bekleyen alınır. Böylece LangGraph graf döngüsü bölünmez (her LLM çağrısı ayrı iş değildir). Üç sınıf:

- **Etkileşimli** (sohbet, facade, kanallar, test paneli): her zaman önce; FIFO.
- **Etkileşimli-düşük** (R5.3): cevabın parçası olmayan ama gün içinde üretilmesi gereken işler: geçmiş özeti (P8), hafıza çıkarma (14). `llm-background` kuyruğunda koşar ama **pencere kuralına tabi değildir**; yuvada etkileşimli işten sonra, arka plan işinden önce. (`rewrite` varyant üretimi cevabın öncesinde olduğu için etkileşimli sınıftadır.)
- **Arka plan**: sınav koşuları (09), LLM judge, toplu yeniden indeksleme sonrası özetler. Yalnızca etkileşimli ve etkileşimli-düşük işler yuvada beklemiyorken ya da `BACKGROUND_WINDOW` içinde koşar. **(A8) `BACKGROUND_WINDOW` profil seed değeridir, kod dalı değil:** `airgap` cpu seed'inde `19:00-07:00` (hafta sonu tüm gün), `gpu` ve `llmaas` seed'lerinde boş (her zaman). Pencere dışında kuyrukta bekler, ekranda "mesai dışı bekliyor" görünür; `edit` modundaki admin "şimdi koştur" ile öne alabilir.
- `topic` guardrail kuralı (08) `input.pre`'de cevaptan önce koşar; arka plana atılamaz. `airgap` cpu seed'inde `topic` yalnızca anahtar kelime modunda; LLM modu `llmaas` ve `gpu`'da.
- Hedef (pilot, CPU): 10 eşzamanlı etkileşimli kullanıcı sıraya girer; kuyruk uzunluğu ve beklenen süre SSE `progress` event'i ve 10'daki sistem durumu ekranında gösterilir. GPU profilinde `OLLAMA_NUM_PARALLEL`/vLLM eşzamanlılığı artar, sınıflar aynı kalır.
- Uygulama: `backend/app/runtime/scheduler.py` (yuva ve sınıf kararı) + `arq` worker ayarları; worker etkileşimli işi arka plan işinin ortasında kesmez (bir çağrı atomik), ama bir sonraki arka plan çağrısını bekletir. `LLM_SLOTS` ve bekleyen sayısı `/readyz` ve sistem durumu ekranında (10). Süre: +1 gün.

### OpenAI-uyumlu facade (P2; bu paketin teslimatı)

LLMaaS müşterisi için ürünün kendisi: mevcut uygulamada yalnızca base URL değişir.

- (R1.2) **Tek halka açık giriş:** `POST /v1/chat/completions` backend'de. `model` `agent:<project_key>/<agent_key>` ise runtime'a gider; değilse (`<project_key>.chat-default` ya da proje bağlamında kısa ad) istek doğrulama, kota (03c kota motoru) ve guardrail (08 `input.pre`/`output.pre`) sonrası LiteLLM'e tek iç anahtarla (A4) ve `metadata` ile proxy'lenir. LiteLLM dışa açılmaz; istemci yalnızca base URL ve API anahtarını değiştirir. `/v1/models` çağıran anahtarın projesindeki modelleri ve yayınlanmış agent'ları listeler.
- İstek: OpenAI `messages[]` → konuşma: `user` alanı ya da `X-Conversation-Id` başlığı varsa kalıcı konuşma; yoksa `messages[]` olduğu gibi tek seferlik bağlam (geçmiş istemcide). `stream: true` SSE, OpenAI chunk şeması (`choices[0].delta.content`, `finish_reason`, son chunk'ta `usage`).
- Araç ve kaynak event'leri: varsayılan **metne gömülü değil, ayrı alanlarda**: her chunk'ta `x_platform: {event: tool_call|tool_result|sources|approval_required|progress, ...}`; OpenAI istemcileri bilinmeyen alanı yok sayar. `X-Agent-Events: none` başlığı ile tamamen kapatılır. Kaynaklar ayrıca son mesajın `annotations[]` alanında (OpenAI `url_citation` şeması). Onay bekleyen run'da akış `finish_reason: "approval_required"` ile kapanır, cevapta `x_platform.approval_id` ve `run_id`; **istemci onay veremez (C4):** onayı 10/11/15 ekranından oturum açmış yetkili kullanıcı verir; istemci `approval_id` ve `run_id` alır, onay verildikten sonra `X-Resume-Run-Id` ile akışı devam ettirir (bekleyen run'ı yoklamak için `GET /runs/{id}`).
- Kimlik eşleme (R1.2, R2.5, B7): `Authorization: Bearer <api key>` backend'de `key_hash` ile doğrulanır → `api_keys` → proje, kapsamlar, CIDR. Son kullanıcı eşlemesi **yalnızca `impersonate` kapsamlı anahtarla**: `user` alanı (e-posta) ya da `X-On-Behalf-Of` JWT'si platform kullanıcısına eşlenir; KB ACL, hafıza ve audit aktörü bu kullanıcıdır. `impersonate` kapsamı yoksa `user` alanı yalnızca LiteLLM/Langfuse log etiketi olarak gider, aktör olmaz ve audit'e `impersonation_denied` yazılır. Eşleme yoksa aktör API anahtarının kendisidir: KB ACL `api_keys.acl_role`'e göre (03c), hafıza kapalı, audit'te `actor_type=api_key`. LiteLLM'e her çağrı tek iç anahtarla ve `user`/`metadata` alanlarıyla gider (01 A4); kota backend'de uygulanır.
- Hata gövdesi OpenAI hata şemasında (`error.type`, `error.code`; 03b). Yayınlanmamış agent 404, kota 429 (backend kota motoru, 03c), guardrail engeli 400 `guardrail_blocked`.
- Kabul: `openai` Python istemcisi yalnızca `base_url` ve `api_key` değiştirilerek `agent:hastane/sozlesme-asistani`'ya streaming soru sorar, kaynaklı cevap alır; aynı istemci `model: hastane.chat-default` ile düz modele gider ve guardrail `input.pre` çalışır; `impersonate` kapsamlı anahtarla `user` verilen istekte ACL o kullanıcıya göre uygulanır, kapsamsız anahtarla aynı istek anahtarın `acl_role`'üyle çalışır ve `impersonation_denied` audit'e düşer; yayınlanmamış agent 404; LiteLLM portu dışarıdan erişilemez (compose'da yalnızca iç ağ).
- Süre: +1 gün (başlıkta güncellendi).

### Graf üretimi (`backend/app/runtime/builder.py`)

- Düğümler: `prepare` (değişken doldurma, Langfuse prompt çekme, bağlam bütçesi), `retrieve` (yalnızca `mode: always` KB'ler için 04 arama API'si), `guard_in` (08 `input.pre` kancası; `llmaas`'ta ayrıca `egress`), `model` (LiteLLM üzerinden, araçlar bağlı), `tools` (MCP çağrıları, 05 istemcisi; öncesinde 08 `tool.pre`, sonrasında `tool.post`; `needs_approval` olanlarda `interrupt`), `guard_out` (08 `output.pre` kancası), `finalize` (structured output doğrulama, kaynak listesi, güven skoru). (R5.5) Düğüm adları `guard_in/guard_out` kalır; kanca adları 08'in enum'uyla aynıdır: `input.pre, output.pre, tool.pre, tool.post, egress`.
- `mode: tool` KB'ler `search_documents` aracı olarak eklenir.
- `ask_user: true` ise `ask_user_question` aracı eklenir; çağrılınca `interrupt`, run `waiting_user` durumuna geçer (`waiting_approval`'dan ayrı durumdur: biri onay, diğeri kullanıcı cevabı bekler; N18).
- Limitler: araç çağrısı sayısı, tur sayısı, süre (`run_timeout_s`; seed'den: llmaas 120, cpu 900, gpu 300 s, C2). Aşımda zorla finalize **yoktur** (v6 M3): run `failed`, `error_code=limit_reached`, SSE `error` olayı ve `run_events` neden taşır; o ana kadar üretilen kısmi çıktı `runs.output`'ta `partial=true` ile saklanır, kullanıcıya "sınır aşıldı" mesajı Türkçe döner.
- Qwen için prompt şablonu: sistem mesajında araç kullanım kuralları açıkça; her araç sonucu `<tool_result name=...>` biçiminde.
- (PayCore düzeltmesi D6) **Prompt sırası KV önbelleği için:** sabit kısım (system + KAYNAKLAR bloğu) önde, değişen talimat ve kullanıcı sorusu en sonda. Aynı kaynaklarla ikinci çağrı (doğrulama, yeniden deneme, structured output finalize) kaynakları yeniden okumaz; PayCore'da 22 sn tasarruf. İki çağrı arasında farklı olan her şey kaynaklardan **sonra** gelir.
- (PayCore düzeltmesi D5) **Güncellik ve çelişki kuralı:** 04'ten gelen parçalar modele en yeniden eskiye verilir, her parçada güncelleme günü yazılır. Prompt: cevabı en yeni kaynaktan kur; çelişkide yeni tarihliyi esas al, eskinin farklı dediğini tarihiyle belirt. Skora tarih puanı eklenmez (seçimi reranker yapar). Kanıt: aynı kılavuzun 2022 `.doc` ve 2024 `.docx` sürümleri aynı anda indeksliydi.
- (PayCore CLAUDE.md; PayCore kontrolü K3) **Güven skoru, hesaplanır ve kaydedilir, varsayılan olarak gösterilmez:** her cevapla `confidence` (0-1) `runs` ve `run_events`'e yazılır, 09 her formülü kaydeder. Formül `answer_rules.confidence_formula`: CPU'da varsayılan `cited` (atıf yapılan parçaların rerank ortalaması, ek maliyet yok); `sentence_max` ve `max` cevap başına CPU'da 3-14 sn ekler, yalnızca GPU'da ya da açık seçimle. **Eşik ve rozet varsayılan kapalı** (`answer_rules.show_confidence: false`, `confidence_threshold: null`): PayCore'un 40 soruluk eval'inde 0,7 eşiği hiçbir yanlış cevabı yakalamadı, 6 doğru cevabı "düşük güvenli" saydı; ayarlanmamış rozet doğru cevaplara güvensizlik işareti koyar. Eşik, o bilgi tabanının kendi sınav setiyle (09, `formula_comparison`) kalibre edildikten sonra agent ayarından açılır; açılınca 11 ve 15'te rozet/uyarı görünür ve onaylı aksiyonlarda eşik altı cevap uyarı taşır. Modelin kendi "bulamadım" cevabı bundan bağımsızdır: metniyle gösterilir, `declined` etiketlenir, "cevaplandı" sayılmaz; tespit yalnızca olumsuz biçimlerle (`bulamadım|bulunamadı|bulunamamıştır|bulunmamaktadır`), "yeterli bilgi bulunmaktadır" eşleşmez.
- (PayCore CLAUDE.md) **Doğrulama adımı (ikinci model çağrısıyla iddia kontrolü) var ama varsayılan KAPALI** (`answer_rules.verify: false`): PayCore'da 20 soruluk eval'de doğru kaynaktan gelen cevapların yarısını reddetti. GPU'da (D8) 09'daki sınavla ölçülerek açılır; CPU'da açılmaz. Açıkken aynı prompt önekini kullanır (KV önbelleği).
- Türkçe %30-40 fazla token üretir; `ANSWER_MAX_TOKENS` (başlangıç 400) ve bağlam bütçesi buna göre (PayCore CLAUDE.md).

### API

- Agents: CRUD, `POST /agents/{id}/versions` (yeni taslak sürüm), `POST /agents/{id}/publish` (09 bitince eval eşiği kontrolü; şimdilik bayrak), `POST /agents/{id}/rollback`.
- Runs: `POST /agents/{key}/runs` (input, variables, conversation_id?) -> SSE akışı: `token`, `tool_call`, `tool_result`, `approval_required`, `question`, `sources`, `progress`, `fallback`, `done`, `error` (C9 ile aynı liste). `GET /runs/{id}`, `GET /runs/{id}/events`, `POST /runs/{id}/cancel`.
- `POST /runs/{id}/resume` (07 ve ask_user için; onay ya da kullanıcı cevabı ile checkpoint'ten devam).
- Test çalıştırma: `channel=test` ile aynı endpoint; önyüzdeki "dene" paneli için.
- Dış agent (`kind: external`): OpenAI-uyumlu URL kaydı; run isteği proxy'lenir, event'ler sınırlı. (Minimum düzeyde; Cognipeer'in "Connect Agent" karşılığı.)

### Tracing

Her run bir Langfuse trace (02 `tracing.py`); `runs.langfuse_trace_id` dolu; önyüz "Langfuse'ta aç" linki verir.

### Agent yaşam döngüsü ve ekran akışı gereksinimleri (konsol incelemesinden, bağlayıcı)

- Oluşturma iki aşamalı: `POST /agents` yalnızca ad, açıklama, model; kalan alanlar `PUT /agents/{id}/versions/{v}` ile. 10'da sekmeli sayfa: Genel, Oturumlar, Yapı, Yayın, Geri bildirim, Kullanım.
- `definition` ek alanları: `limits.context_tokens`, `limits.output_tokens`, `limits.run_timeout_s`, `prompt_ref` (Langfuse prompt adı; "yönetilen prompt'a terfi" düğmesi 02'deki prompt API'sine yazar), `runtime_profile` (rezerve; ilk sürümde tek profil). **Çıkarılanlar (C21, ARCH-07/10):** `webhook_url`, `budget_usd`, `raw_output_tools[]` (tanımsız bir özetleme adımı varsayıyordu; araç çıktısı özetlenmez, yalnızca görünür kırpma vardır). İstek gelirse additive eklenir.
- Manifest: `GET /agents/{id}/manifest` (definition + metadata, YAML/JSON) ve `POST /agents/import` (`dry_run` bayrağı ile doğrulama); 10'da kod görünümü, dışa/içe aktarma.
- Yayın durumu: `status: published` olmayan agent için `agent:` isteği 404 (facade kuralı).
- **PoC agent kapsamı (PLAN 2d, PayCore CPU ölçümü):** `mode: always` doküman asistanı ve `max_tool_calls: 1` ile tek araç çağrılı onaylı SQL asistanı; `mode: tool` ve karma asistan kodda var ama PoC kabulünde değil, GPU ya da `llmaas` ile ölçülür.
- Bilgi tabanı `mode: tool` seçildiğinde **tek araç** `search_documents(query, kb_key, top_k)` üretilir (C7 donmuş sözleşme, C11; belge okuma araçları yok, CPU bütçesini aşar). `mode: always` tek LLM çağrısı. Varsayılan: sözleşme asistanı `always`, belge + SQL karışık agent'lar `tool`.
- Platform sistem kuralları (`backend/prompts/platform_rules.md`, Türkçe, Qwen için kısa) kullanıcı talimatının üstüne otomatik eklenir; `system_prompt` izde `platform_rules`, `runtime_profile`, `user_instructions` olarak ayrı görünür (02).
- `runs.channel: test` playground oturumlarını ayırır; API ve chat oturumları aynı listede.
- Guardrail engeli: run `failed`, `error_code=guardrail_block`, `reference_id` (uuid); kullanıcıya Türkçe metin 08'deki `guardrail_policies.block_message_tr`'den, altında "düzenle ve tekrar dene" (11). Hata gövdesi OpenAI hata şemasında.


## Teslimatlar

- Migration, modeller, `runtime/` (builder, nodes, state), router'lar, SSE.
- Testler: tanım doğrulama; `always` ve `tool` modlu KB ile graf; araç çağrısı limiti; `needs_approval` aracında interrupt ve resume; structured output doğrulama. Testlerde LLM için kaydedilmiş sahte cevaplar (VCR benzeri) kullanılır.
- `docs/agent-tanimi.md`: şema ve örnekler.

## Kabul kriterleri

- Örnek "Sözleşme Asistanı" tanımı ile "fesih süresi nedir" sorusu kaynaklı cevap döner, `sources` event'i belge adı ve sayfa içerir.
- Belgede olmayan soruda `unknown_reply` döner, uydurma yok (sahte LLM fixture'ıyla deterministik test; gerçek kalite 09 ve 13b'de ölçülür, N5).
- `run_sql` `needs_approval=true` yapıldığında run `waiting_approval`'da durur; `resume(approved)` ile tamamlanır; `resume(rejected)` ile model reddi görüp cevap üretir.
- Backend yeniden başlatıldığında bekleyen run checkpoint'ten devam eder.
- Tüm event'ler `run_events`'te sıralı; Langfuse trace'i aynı adımları gösterir. (B2) `litellm_client` `FallbackObserved` döndüğünde `run_events.fallback` ve SSE `fallback` olayı yazılır. (B3) Her MCP çağrısı `tool_call`/`tool_result` satırı olur; `truncated=true` taşınır. (C12) Arama API'sine `X-Run-Id` iletilir, `kb_queries.run_id` dolar.
- (C13) `context_tokens` `OLLAMA_CONTEXT_LENGTH`'i aşan sürüm kaydı 400; `max_turns` aşımında run `failed/limit_reached`, kısmi çıktı `partial=true`.
- (B1, 02'den) `runs.model_ms/tool_ms/retrieval_ms/unaccounted_ms/slowest_step` her tamamlanan run'da dolu ve toplamı `ended_at−started_at`'e eşit (±1 s).

## Teknik notlar

- LangGraph 0.4+, `interrupt()` API'si; checkpointer Postgres.
- Runtime ayrı worker sürecinde çalışır (CPU model yavaş; API süreci bloklanmasın). API -> Redis kuyruk -> worker; SSE için worker event'leri Redis pub/sub ile API'ye.
- (PayCore düzeltmesi D6) Worker içinde de CPU yoğun yerel çağrı (reranker) iş parçacığında; SSE keepalive her 10 sn'de gider; uzun turlarda istemciye `progress` event'i ("kaynaklar okunuyor", "araç çalışıyor").
- (PayCore düzeltmesi D6, D8; C2) Süre beklentisi CPU'da: RAG cevabı 1,5-2 dk, `mode: tool` turu ~3 dk. İki ayrı zaman aşımı: tekil LLM çağrısı (01 seed: llmaas 60 / cpu 600 / gpu 120 s) ve run (`run_timeout_s`, seed: llmaas 120 / cpu 900 / gpu 300 s; PLAN 2b). Kabul kriterlerindeki süreler 13'te `cpu` ve `gpu` sütunlarıyla.
- Referans: PayCore `rag/answer.py` (`by_recency`, `format_context`, ortak prompt öneki, `ANSWER_TASK`), `rag/pipeline.py` (`declined`, güven skoru), `llm.py`.
- Zamanlanmış ve webhook tetikleyiciler kapsam dışı ama `runs.trigger_type` hazır.

## Kapsam dışı

Alt agent devri, görsel Flow, sandbox, ses. Onay kuyruğu UI ve bildirim (07). Guardrail içerikleri (08).
