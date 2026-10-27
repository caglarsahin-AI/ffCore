# 01. LiteLLM gateway [FFCore Gateway]

**Bağımlılık:** 00, 03a (providers/models tabloları). **Süre:** 2,5 gün (uzlaştırıcı ve fallback tespiti dahil; inceleme v4-v6). **Dalga:** 3. **PoC:** evet.

## Amaç

Tüm model çağrılarının geçtiği tek kapı. Sanal model adları, yalnızca açık yapılandırılmış sağlayıcı fallback'i (`chat-fallback` kaydı varsa; örtük fallback yok, FELSEFE ARCH-06/ARCH-10), Langfuse'a kayıt. Proje bazlı LiteLLM team ve sanal anahtar **yoktur** (karar A4, inceleme v4-v6): backend LiteLLM'i tek iç anahtarla çağırır, proje ve kullanıcı bilgisi `metadata` ile gider, kota backend'de.

## Kapsam

0. **(P1, R1.4, C1 uzlaştırıcı) Tek kaynak, tek mekanizma:** LiteLLM'in model listesi her zaman `providers` ve `models` tablolarından türetilir ve **yalnızca LiteLLM DB'sinde** yaşar (`store_model_in_db=true`). `deploy/litellm/config.yaml` yalnızca `general_settings` ve `litellm_settings` içerir, `model_list` içermez; böylece dosya ve DB diye iki kaynak oluşmaz. `make render-litellm` bir **uzlaştırıcıdır** (`backend/app/services/litellm_reconcile.py`): açılışta ve her sağlayıcı/model mutasyonunda tabloları LiteLLM `/model/info` ile karşılaştırır, farkı `POST /model/new`, `/model/update`, `/model/delete` ile uygular; yeniden başlatma ve `/config/reload` yok, akan stream'ler kesilmez. Tutarlılık testi: tablo ile `/model/info` eşit. Sağlayıcı anahtarı `litellm_params.api_key` olarak istek gövdesiyle gider; **01 işçisinin ilk işi** pinli LiteLLM sürümünde bu anahtarın DB'de `LITELLM_SALT_KEY` ile şifreli saklandığını doğrulamaktır (doğrulanmamış iddia U2); doğrulanamazsa durur ve `DECISION-` kaydı açar. Profil farkı seed farkıdır: `deploy/seed/models.llmaas.yaml` (varsayılan) ve `deploy/seed/models.airgap.yaml` ilk kurulumda tabloları doldurur (`make seed-models`), sonrası UI'dan. Tablolar 03a'da.
0b. **(R1.1) Ad uzayı:** LiteLLM `model_name` globaldir, model kaydı proje düzeyindedir; çakışmayı önlemek için LiteLLM adı `<project_key>.<model_key>` (`hastane.chat-default`), agent adı `agent:<project_key>/<agent_key>`. Backend proje bağlamında kısa adı (`chat-default`) tam ada çevirir; dış istemci tam adı kullanır; `project_key` global benzersiz (03a).
1. Uzlaştırıcının LiteLLM DB'sine yazdığı model kayıtları (`llmaas` seed'i ile beklenen içerik):
   - Modeller: `<proje>.chat-default` -> aktif sağlayıcı kaydından (örn. `anthropic/claude-sonnet-5-5`, `azure/<deployment>`, `bedrock/...`); `<proje>.chat-fallback` -> ikinci sağlayıcı (yalnızca seed'de varsa); `<proje>.memory-extract` -> küçük model (14 için; `llmaas`'ta sağlayıcının küçük modeli, `airgap`'ta Qwen). **Embedding LiteLLM'den geçmez** (C10 tersine, PLAN 2d): süreç içi bge-m3 dense + sparse, 04a. `airgap` seed'inde `chat-default` -> `ollama/qwen3.5:35b` (PayCore'da Ollama host'ta: `http://host.docker.internal:11434`) ya da `hosted_vllm/...`. Her modelin kaydı yalnızca sağlayıcı kaydı aktifse yazılır; `.env` değişkeni yalnızca seed anında okunur.
   - `router_settings`: `chat-default` için fallback listesi yalnızca projede `chat-fallback` kaydı **varsa** `[chat-fallback]`; yoksa fallback listesi boş ve sağlayıcı hatası çağırana 503 `model_unavailable` olarak döner (sessiz düşüş yok). **Fallback tespiti bu paketin işidir (B2):** `litellm_client.py`, cevaptaki model/deployment bilgisini istenen modelle karşılaştırır (hangi alan ya da başlığın güvenilir olduğu pinli sürümde doğrulanır, U3) ve tipli `FallbackObserved(source_model, target_model, reason)` sonucu döner; unit test ile kanıtlanır. Bu sonucun `run_events.fallback` olarak yazılması ve Langfuse tag'i 06a'nın kabul kriteridir; 10'da sistem durumu ekranında sayılır. `OFFLINE=true` iken dış sağlayıcı kayıtları yazılmaz ve `chat-fallback` dış sağlayıcıya işaret edemez (seed doğrulaması reddeder). **(R1.5) Zaman aşımı per-call:** `llmaas` 60 s, `airgap` cpu 600 s, gpu 120 s (PLAN 2b; run süresi ayrı: 06 `run_timeout_s`). Retry 2, 429'da üstel geri çekilme, `stream_options.include_usage` açık (Ollama'nın son chunk'ta `usage` döndürdüğü pinli sürümde doğrulanır).
   - `general_settings`: master key `.env`'den, Postgres (LiteLLM'in kendi tabloları için aynı Postgres sunucusunda ayrı DB `litellm`), `litellm_settings.callbacks: ["langfuse"]` (anahtarlar 02'de doldurulur). LiteLLM içinde guardrail kancası **yoktur** (karar B3): guardrail yalnızca backend'de (06a graf düğümleri, 06b facade) çalışır.
2. **(A4) Kimlik ve bütçe modeli:** LiteLLM team, sanal anahtar ve `end_user` bütçesi **kullanılmaz**. Backend (06 runtime ve facade) LiteLLM'i tek iç anahtarla (`LITELLM_INTERNAL_KEY`, master değil; `.env`) çağırır; her çağrıda `user=<platform user id | api_key:<id>>` ve `metadata={project_id, agent_key, run_id, channel, api_key_id}` gönderilir, maliyet proje bazında Langfuse ve `usage_daily`'den (03c) okunur. Kota ve bütçe tek yerde, backend'de (03c kota motoru, Redis sayaçları). `litellm_client.py`: `chat`, `embed`, `model_new/update/delete`, `model_info`, `FallbackObserved`. LiteLLM dışa açılmaz; dış istemciler facade üzerinden (06b).
3. `deploy/litellm/README.md`: sanal model ekleme, uzlaştırıcı, fallback davranışı.
4. Test: `tests/test_gateway.py`, LiteLLM'e `chat-default` ile streaming istek atar, usage alanı dolu gelir. PayCore'da `llm.py` LiteLLM'i gösterir; `reasoning_effort: none` ve boş cevap hatası (`empty_completion`) korunur.

### Sağlayıcı ve model kaydı gereksinimleri (konsol incelemesinden, bağlayıcı)

Tablolar 03a'da; bu paket onlardan LiteLLM yapılandırması üretir ve aşağıdaki davranışları teslim eder.

- Sağlayıcı (tenant düzeyi: anahtar, base URL, alanlar `domains[]`: Model, Embedding, Vector, File; hangi projeler) ile model (proje düzeyi, `models.provider_id`) ayrı kavramlardır; `provider_projects` boş bırakılamaz.
- `POST /providers/{id}/test` kaydetmeden canlı test yapar; başarısız test kaydı engellemez; sürücü başına `supports_test` bayrağı (yerel disk, pgvector gibi sürücülerde "bağlantı testi yok" mesajı).
- Model kaydı alanları ve LiteLLM'e yansıması: `category` (llm, embedding, stt, tts, ocr, moderation), sağlayıcıdaki `model_id`, `capabilities` (tool calls, reasoning, structured outputs; model id'den otomatik tespit, elle değiştirilebilir), `input_types[]`, `pricing` (input/output/cached per 1M, "katalogdan doldur" `model_catalog`'dan), `limits` (context window, max output, temperature, max tokens), `reasoning_default` ve "reasoning metnini çağırana döndür", `upstream_api` (chat/completions ya da Responses; otomatik seçilmez), `request_policy` (sağlayıcının reddettiği parametreleri düşür, ek reddedilecekler, her isteğe eklenecek JSON gövde, bilinmeyen parametreleri ilet). `render-litellm` bunların tamamını `litellm_params`'a çevirir; `reasoning_effort: none` (D6) `request_policy.extra_body` ile gelir.
- `model_catalog(provider_driver, model_id, input_per_1m, output_per_1m, cached_per_1m, context_window, capabilities)` repo'daki YAML'dan yüklenir; `airgap` profilinde sanal fiyat elle girilir.
- Kategori sonradan değiştirilebilir; UI'da kategori seçimi model id girilmeden önce zorunlu adım (yanlış kategorili model diğer modüllerde listelenmez). Embedding modelinde `embed_dim` kayıt anında test çağrısıyla ölçülür; globalle uyuşmazsa 400 (P5, R2.7).
- Model Hub kullanım özeti (10'daki model listesinde): toplam çağrı, hata oranı, token in/out, ortalama gecikme, cache isabeti, maliyet, en çok çağrılan modeller, 14 günlük trend; veri 02'den.
- Yayınlanmış agent `model: "agent:<project_key>/<agent_key>"` ile backend facade'ından çağrılır; bu paket `agent:` için hiçbir şey üretmez (R1.2), tamamı 06'da.


## Profil farkları (PLAN.md 2b)

- (P1, R1.5) İki **seed** dosyası: `deploy/seed/models.llmaas.yaml` (varsayılan: Anthropic birincil, Azure OpenAI ya da OpenAI `chat-fallback`, per-call timeout 60 s, `run_timeout_s` 120, gerçek fiyatlar `models.pricing`, `rewrite` açık, `context_tokens` 16000) ve `deploy/seed/models.airgap.yaml` (Ollama/vLLM, fallback yok, per-call timeout cpu 600 s / gpu 120 s, `run_timeout_s` cpu 900 / gpu 300, sanal fiyat, `rewrite` cpu'da kapalı, `context_tokens` cpu'da 8000 çünkü `OLLAMA_CONTEXT_LENGTH` 32768 iken 16k prefill tek başına ~143 s; `BACKGROUND_WINDOW` cpu'da `19:00-07:00`, gpu ve llmaas'ta boş, karar A8). `make seed-models` `DEPLOY_PROFILE`'a göre doğru seed'i tablolara yükler; uzlaştırıcı her iki profilde aynıdır.
- (P6, düzeltildi C1) **Sağlayıcı anahtarları veritabanında, şifreli** (`providers.config_encrypted`, 03 Fernet); kaynak burasıdır ve UI'dan sağlayıcı ekleme/"Test connection" buna yazar. `.env` yalnızca ilk kurulum için (`SEED_ANTHROPIC_API_KEY` gibi; `make seed-models` bunları tabloya taşır ve `.env`'den silinmesini önerir). Uzlaştırıcı anahtarı çözüp LiteLLM model API'sine istek gövdesiyle verir (ortam değişkeni **değil**; çalışan konteynere env verilemez, KARARLAR "tersine karar"); LiteLLM bunu kendi DB'sinde şifreli saklar (U2 doğrulaması). LiteLLM UI kapalı. Bölge parametreleri (`AZURE_API_BASE` EU uç noktası, `AWS_REGION_NAME=eu-central-1`) sağlayıcı formunda zorunlu alan.
- `llmaas` için ek test: birincil sağlayıcı kapatıldığında `chat-fallback` varsa `FallbackObserved` döner, yoksa 503.

## Teslimatlar

- Çalışan LiteLLM proxy (iç ağ); `curl -H "Authorization: Bearer $LITELLM_INTERNAL_KEY" litellm:4000/v1/chat/completions` ile `<proje>.chat-default` cevap verir (`llmaas` CI'da sahte sağlayıcı, `airgap`'ta Qwen).
- `litellm_client.py`, `litellm_reconcile.py` ve testleri.
- `deploy/litellm/README.md`.

## Kabul kriterleri

- `OFFLINE=true` iken hiçbir istek Anthropic'e gitmez (uzlaştırıcı dış sağlayıcı kaydı yazmaz; `/model/info` ve egress logu ile doğrulanır).
- `airgap` seed'iyle Ollama kapatıldığında `chat-default` isteği 503 `model_unavailable` döner, hiçbir dış sağlayıcıya gitmez (egress testi 0 bağlantı). `llmaas` seed'iyle birincil sağlayıcı kapatıldığında yalnızca `chat-fallback` kaydı varsa oraya geçer ve `litellm_client` `FallbackObserved` döner (unit test); kayıt yoksa 503. (`run_events.fallback` yazımı 06a kriteri.)
- Uzlaştırıcı: tabloda pasif yapılan model `/model/info`'dan düşer; `config.yaml`'da `model_list` anahtarı yoktur (test dosyayı parse eder).
- Streaming cevabın son chunk'ında token sayıları vardır.

- (R1.1, R1.4) `models` tablosunda `hastane` projesine `chat-default` eklenince LiteLLM `/model/info` listesinde `hastane.chat-default` görünür, yeniden başlatma olmadan; aynı anda akan bir stream kesilmez (test: uzun stream sırasında model ekle). İki projede aynı kısa ad çakışmaz.


## Teknik notlar

- Qwen'in tool-calling formatı Ollama üzerinden OpenAI şemasına çevrilir; LiteLLM bunu destekler ama `parallel_tool_calls` kapalı tutulur.
- (PayCore düzeltmesi D6) **Qwen3.5 thinking kapalı:** `chat-default` model kaydında "her isteğe eklenecek JSON gövde" alanı `{"reasoning_effort": "none"}` olur. Ollama'nın OpenAI ucu `think` alanını yok sayar, yalnızca `reasoning_effort`'u okur. Açık kalırsa bütçe akıl yürütmeye gider ve cevap boş döner ya da süre 29-47 sn'den 155-330 sn'ye çıkar; PayCore ölçümünde doğruluk kazancı yok. Model kaydındaki `reasoning` varsayılanı yalnızca açıkça isteyen agent'lar için (`definition.reasoning`) değiştirilebilir. Boş cevap dönerse LiteLLM istemcisi bunu hata olarak loglar (`empty_completion`), sessizce boş string geçirmez.
- (PayCore düzeltmesi D8) **`INFERENCE_BACKEND=ollama|vllm`** (profil dalı değil, yapılandırma değeri): `vllm` seçilince `chat-default` -> `hosted_vllm/<model>` (OpenAI uyumlu uç; `reasoning_effort` ve `num_ctx` vLLM'de sunucu parametresi), embedding ve reranker GPU'da ayrı servis ya da aynı sunucu. Uygulama tarafı değişmez; her çağrı LiteLLM'den. Compose `profiles: [vllm]` ile vLLM servisi; `make render-litellm` backend'i de seçer.
- (PayCore düzeltmesi D6) Gerçekçi süre referansı (35B-A3B Q4_K_M, 32 vCPU Haswell, PayCore ölçümü): prefill ~112 tok/s, üretim ~11 tok/s; 12 parçalı RAG cevabı 84-114 sn; `mode: tool` agent'ında 20K token'lık bir tur ~3 dk. Timeout ve kabul kriterleri (06, 13) bu sayılarla; 4,8 sn gibi bulut ölçümleri CPU için geçersiz.
- Embedding boyutu (`EMBED_DIM`) `.env`'de tek yerde; 04 bu değeri pgvector kolon boyutunda kullanır. Model değişirse yeniden indeksleme gerekir, README'ye yazılır.
- LiteLLM imajı iç registry'den; sürüm sabitlenir.

## Kapsam dışı

Proje ve kullanıcı yönetimi (03), Langfuse kurulumu (02), LiteLLM team/sanal anahtar/`end_user` bütçesi (karar A4: kullanılmaz; kota backend'de), LiteLLM içi guardrail kancası (B3).
