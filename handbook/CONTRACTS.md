# Donmuş ve Additive Sözleşmeler

FFCore sıfırdan yazılıyor; sözleşmeler kilometre taşında **donar**. Donmadan önce brief'in sahibi değiştirebilir (PR notuyla). Donduktan sonra değişiklik yalnızca additive'dir; kırıcı değişiklik aşağıdaki prosedürle ve kullanıcı onayıyla olur. Sözleşme kaynağı ilgili brief'tir; burada yalnızca neyin dondurulduğu ve ne zaman yazılır.

| ID | Sözleşme | Donma noktası | Donan davranış |
|---|---|---|---|
| C1 | Ad uzayı: `<project_key>.<model_key>`, `agent:<project_key>/<agent_key>`; `project_key` global benzersiz (PLAN 5) | M1 | Biçim ve çözümleme kuralı. Yeni önek (`agent:` gibi) additive |
| C2 | Kimlik: `X-On-Behalf-Of` JWT alanları (`sub, project_id, exp ≤ 5 dk, aud=internal`), `resolve_actor()` tek doğrulama noktası, `api_keys.scopes` enum'u (03) | M2 | Alan adları ve anlamı; yeni scope additive, var olan scope'un anlamı değişmez |
| C3 | Ortak tablo kolonları `id, project_id, created_at, updated_at, created_by, deleted_at` **yalnızca proje sahipli kök tablolar için** (B5) ve audit decorator'ı (PLAN 5, 03b). Adlandırılmış istisnalar: global `users`; çocuk tablolar `chunks, attachments, tool_actions, agent_versions, messages, few_shots, channel_*` (projeyi FK zinciriyle alır: `kb_id`, `tool_id`, `agent_id`, `conversation_id`); append-only olay tabloları `run_events, audit_events, guardrail_events, usage_daily, kb_queries, mcp_server_calls, alerts, checkpoints` (`id, ts/created_at` + sahibi gösteren FK). Yeni istisna eklemek B sınıfıdır, bu listeye yazılır | M2 | Kök tablolar bunlara uyar; `deleted_at` yerine fiziksel silme yalnızca audit ve retention işinde |
| C4 | Guardrail aşamaları `prompt.pre, input.pre, output.pre, output.stream.delta, tool.pre, tool.post, egress`; `Decision` yapısı; `POST /internal/guardrails/evaluate` (08) | 08 merge | Aşama adları ve sırası, `action_taken` enum'u. Yeni kural türü additive |
| C5 | `VectorStore` arayüzü: `ensure_collection, upsert, search(kb_id, query: {dense, sparse?}, filters, top_k), delete_by_document, drop_collection` ve filtre anahtarları; sparse sorgu isteğe bağlı, pgvector sürücüsü yok sayıp Postgres BM25 ile hibrit yapar, Qdrant sürücüsü bge-m3 sparse ile (04a) | M3 | İmzalar; yeni isteğe bağlı metot "unsupported" varsayılanıyla additive |
| C6 | `ingest_from_raw(raw_path, metadata, acl)` giriş noktası ve raw/silver/gold dizin düzeni (04a) | M3 | 16 bu imzayı kullanır; metadata'ya yeni anahtar additive |
| C7 | MCP: streamable HTTP taşıma, `tools/list` keşfi, yerleşik araç imzaları `search_documents(query, kb_key, top_k)`, `get_schema(question?)`, `run_sql(sql, reason)` (05a) | M3 | Araç adı ve zorunlu parametreler; yeni isteğe bağlı parametre additive |
| C8 | Agent tanımı `definition` JSON'u ve `schema_version` (06a) | M3 | Var olan alan silinmez, anlamı değişmez; yeni alan varsayılanla gelir; manifest içe aktarma eski `schema_version`'ı okur |
| C9 | `runs.status` ve `run_events.type` enum'ları; SSE event adları `token, tool_call, tool_result, approval_required, question, sources, done, error, progress, fallback` (06a) | M3 | Var olan değerler korunur; tüketiciler bilmedikleri event'i yok sayar (10, 11, 15 bu kuralı test eder) |
| C10 | Kuyruk adları `ingest, llm-interactive, llm-background, sync`; iş sınıfları etkileşimli / etkileşimli-düşük / arka plan; run = tek arq işi, model çağrıları `LLM_SLOTS` yuvasından (C8); `BACKGROUND_WINDOW` profil seed değeri (PLAN 5, 06a) | M3 | Ad ve sınıf anlamı; yeni kuyruk additive |
| C11 | OpenAI-uyumlu facade: `POST /v1/chat/completions`, `GET /v1/models`, chunk şeması, `x_platform` ve `annotations[]` ek alanları; `user` alanı yalnızca `impersonate` kapsamıyla aktör (B7); `/mcp/{key}/` ikinci yüzey aynı kimlik/kota/guardrail/audit'ten (C14) (06b, 05b) | M4 | OpenAI alanlarının anlamı OpenAI ile aynı kalır; FFCore'a özgü her şey `x_platform` altında ve additive |
| C12 | Ortam değişkeni adları `.env.example`'da; `DEPLOY_PROFILE`, `VECTOR_BACKEND`, `INFERENCE_BACKEND`, `OLLAMA_CONTEXT_LENGTH`, `REGISTRY_PREFIX`, `OFFLINE` (00, 12) | M1 | Ad değişimi yalnızca deprecation ile (CHANGE_CONTROL) |
| C14 | **Uzantı noktaları** (entry point grupları): `ffcore.sources` (veri kaynağı sürücüsü), `ffcore.tools` (yerleşik araç), `ffcore.guardrail_rules` (kural türü), `ffcore.seeds` (profil seed'i). Tüketici paket (paycoreLLM) yalnızca bunlara kayıt olur; FFCore tüketiciyi import etmez (CI import testi) | M2 | Grup adları ve kayıt imzaları; yeni grup additive |
| C13 | Tema token'ları `frontend/styles/tokens.css` ve `messages/tr.json` anahtar düzeni (00, 10) | M2 | Token silinmez; yeni token additive. Çeviri anahtarı yeniden adlandırılırsa eski anahtar bir sürüm kalır |

## Additive kalıpları

- İsteğe bağlı metot, varsayılanı "desteklenmiyor" hatası.
- Enum'a yeni değer; tüketiciler bilinmeyen değeri yok sayar ya da açık hata verir, sessizce başka değere eşlemez.
- Yeni yapılandırma veya JSON alanı, eski varsayılanla.
- Yeni gerçekleştirme fabrika ya da `settings.features` bayrağı arkasında.
- Yeniden adlandırmada eski ad + uyarı + en az iki küçük sürüm.

## Kırıcı değişiklik prosedürü

1. Additive seçenekler denenmiş ve neden yetmediği PR'da yazılmış olmalı.
2. `state/BLOCKERS.md`'ye `BREAKING-C<n>` kaydı açılır: hangi sözleşme, kim etkilenir, geçiş planı.
3. Kod ve migration üretimi durur; koordinatör kullanıcıya sorar.
4. Kullanıcı onayı KARARLAR.md'ye tarihle yazılır; ancak ondan sonra devam edilir.
5. Değişiklik ilgili brief'e ve buradaki tabloya işlenir.

## Veri sınırı sözleşmeleri (her zaman D sınıfı, bkz. CHANGE_CONTROL)

- Hasta verisi ve kişi düzeyi kurum verisi platformda tutulmaz; text-to-SQL yalnızca salt-okunur agent sunum DB'sine.
- Belge indekslenirken dışarı çıkmaz (embedding yerel); `llmaas`'ta dışarı yalnızca model çağrısı ve izin listesindeki adresler.
- Bu iki kural için additive yol yoktur; değiştirmek ürün kararıdır.
