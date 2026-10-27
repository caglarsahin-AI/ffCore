# Brief inceleme v2 (26 Ekim 2026, akşam sürümü)

PLAN.md ve plan/00-16 brief'lerinin 26 Ekim 18:23 halinin incelemesi. Bu dosya brief'leri güncelleyecek ajan içindir; brief'lere burada dokunulmamıştır.

Karar durumu: P1 (tek config kaynağı), P2 (facade sahipliği), P3 (LiteLLM guardrail kancası), P4 (`user` rolü rezerve, paket 17), P5 (tek embedding), P6 (sağlayıcı anahtarları DB'de), P7 (öncelikli kuyruk, 10 kullanıcı), P8 (bağlam bütçesi), P9 (referans bağlayıcılığı) brief'lere işlenmiş. Aşağıdaki liste bu kararların bıraktığı artıkları, kararların kendi aralarında ürettiği yeni çelişkileri ve hâlâ açık olan eski maddeleri içerir.

Öncelik: **A** başlamayı engeller ya da kabul kriterini ölçülemez yapar; **B** uygulamada yanlış seçime yol açar; **C** tutarlılık.

---

## 0. Ürün hedefi değişti: LLMaaS birincil, yerel LLM ikincil (A)

PLAN.md hâlâ "ilk müşteri Türkiye Hastanesi, ikinci hedef LLMaaS" diyor ve her varsayılan airgap'e göre. Hedef tersine döndüğüne göre aşağıdakiler değişmeli. Pilot müşteri airgap kalıyorsa bu açıkça yazılır: "ürün varsayılanı llmaas, pilot kurulum airgap".

| Yer | Şu an | Olması gereken |
|---|---|---|
| PLAN başlık ve bölüm 1 | "Hastane LLM Platformu", hastane birinci | Ürün adı nötr; bölüm 1: birincil pazar LLMaaS kullanan kurumlar, ikincil kapalı ağ / yerel model; pilot müşteri ayrı cümle |
| PLAN 2 kısıtlar tablosu, 1. satır | "Üretim sunucusunda internet yok" genel kısıt | Yalnızca `airgap` profilinin kısıtı; genel kısıt "dış ağ yalnızca izin listesiyle" |
| PLAN 2 "Hasta verisi platformda yok" | hastaneye özgü | Genel: "özel nitelikli kişisel veri RAG'e girmez; yapısal veri yalnızca salt-okunur sunum DB'si"; hastane örneği parantezde |
| PLAN 2b sıra ve `DEPLOY_PROFILE` varsayılanı | airgap önce; varsayılan belirtilmemiş | `llmaas` önce ve `.env.example` varsayılanı `llmaas`; 00 ve 13 bunu kullanır |
| PLAN 3 mimari şeması | "Anthropic (sadece geliştirme)" | "Sağlayıcılar (llmaas üretim) / Ollama-vLLM (airgap)" |
| PLAN 8 kilometre taşları | M5 "kapalı ağda kurulum" | M5: `llmaas` kurulum + egress + `veri-isleme.md`; airgap kurulumu aynı M5'in ikinci kabul satırı (ya da pilot için ayrı M5b) |
| 12 | `docs/kurulum-kapali-ag.md` ana rehber, `kurulum-llmaas.md` ek | Ters: llmaas ana rehber; airgap rehberi imaj taşıma ve model kopyalama ekler. Sağlayıcı anahtarı rotasyonu ve egress ana rehberde |
| 13 | `make e2e` eşikleri önce airgap | Tablo üç sütun: `llmaas`, `gpu`, `cpu`; CI'da varsayılan `llmaas` (sahte sağlayıcı ile) |
| 15, 16 | Slack/Teams, Atlassian Cloud, SharePoint "yalnızca llmaas" diye ikincil ton | Ton değişmez ama M7 içinde sıra: önce Slack + Teams + SharePoint + Confluence Cloud, sonra Mattermost ve ağ klasörü |
| 01 Kapsam 1 | `chat-dev` "sadece `ANTHROPIC_API_KEY` varsa" | P6 sonrası anahtar DB'de; koşul "sağlayıcı kaydı aktifse". `.env` değişkeni yalnızca seed için |

---

## 1. Gateway ve facade (01, 03a, 06)

**1.1 (A) Sanal model ve agent adları çakışır.** 03a `models.project_id` ile model kaydı proje düzeyinde, `key` ise LiteLLM `model_name` (`chat-default`). LiteLLM `model_name` globaldir: iki proje `chat-default` tanımlayınca çakışır. Aynı sorun `agent:<key>` için: `agents.key` proje başına benzersiz, LiteLLM adı global. Karar gerekli, önerim: LiteLLM adı `<project_key>.<model_key>` ve `agent:<project_key>/<agent_key>`; backend facade proje bağlamından kısa adı çözer. Yazılacak yer: 03a veri modeli, 01 Kapsam 0, 06 facade.

**1.2 (A) `agent:` yönlendirmesini LiteLLM'den kaldırın; facade tek giriş kapısı olsun.** Mevcut tasarım istemci → LiteLLM → backend → LiteLLM döngüsü kuruyor ve `X-LiteLLM-Key-Id` başlığına dayanıyor; LiteLLM üst servise anahtar kimliğini kendiliğinden iletmez, model başına statik `extra_headers` dışında yol yok. 06 zaten `POST /v1/chat/completions`'ı backend'de tanımlıyor ve `agent:` olmayan modeli LiteLLM'e proxy'liyor. Öneri: tek halka açık base URL backend facade; kimlik `api_keys` ile backend'de doğrulanır; LiteLLM iç ağda kalır (12 zaten böyle). 01'deki `agent:` render satırı ve "yalnızca yönlendirme" cümleleri silinir; 01'in ek kabul kriteri 06'ya taşınır. Reddedilirse: 01'e LiteLLM'in başlık iletim mekanizması ve test eklenmeli.

**1.3 (A) Agent çağrılarında LiteLLM anahtarı ve kota.** Runtime LiteLLM'i hangi anahtarla çağırır? Backend ham API anahtarını tutmaz (`key_hash`), LiteLLM key'i de yok. Tanımlanacak: runtime proje team anahtarıyla çağırır; her çağrıda `user=<platform user id | api_key id>` ve `metadata={project_id, agent_key, run_id, channel}`; API anahtarı başına bütçe LiteLLM `end_user` bütçesiyle ya da backend `usage_daily` ile uygulanır (biri seçilir). Yazılacak yer: 01 Kapsam 2, 03b kota bölümü, 06 facade.

**1.4 (B) `render-litellm` + `/config/reload`.** Config dosyasını her model değişikliğinde yeniden yükletmek LiteLLM'de güvenilir değil; yeniden başlatma akan stream'leri keser. Öneri: config dosyası yalnızca açılış için; değişiklikler LiteLLM'in DB'li model yönetim API'siyle (`/model/new`, `/model/update`, `/model/delete`, `store_model_in_db`) uygulanır; 08'in model başına `guardrails:` kaydı da aynı yoldan. 01 Kapsam 0 ve 08 P3 paragrafı buna göre.

**1.5 (A) Zaman aşımı sayıları birbirini tutmuyor.** 01: LiteLLM timeout 120 s. 06: `limits.timeout_s` CPU'da 600. 13: tek RAG cevabı CPU'da ≤ 2,5 dk. 01'in kendi ölçümü: prefill ~112 tok/s, 16k bağlam = ~143 s yalnızca prefill. LiteLLM 120 s'de keser, 13'ün kriteri hiç ölçülemez. Yapılacak: seed'de `cpu` için LiteLLM per-call timeout ≥ 600 s, `llmaas` için 60 s (30 s araç çağrılı turda dar); PLAN 2b tablosundaki "120 s / 30 s" satırı "LLM çağrısı / run" diye ikiye ayrılır; `OLLAMA_CONTEXT_LENGTH` 32768 iken `context_tokens` varsayılanı CPU seed'inde 8000.

**1.6 (C) `OFFLINE` ve reranker konumu.** 00 "reranker için `OLLAMA_MAX_LOADED_MODELS` ≥ 3" diyor; 04 ve 12 reranker'ı sentence-transformers/TEI ile süreç içinde koşturuyor. Biri seçilsin; 00 düzeltilsin.

---

## 2. Backend çekirdek (03a, 03b)

**2.1 (A) `quotas` iki şema.** Kapsam: `kind: rpm|tpm|daily_tokens|monthly_usd, limit, action`. Referans ("Bizde", bağlayıcı): `scope_type, scope_id, priority, windows jsonb, tokens jsonb, budget jsonb, is_active`. PLAN 5 kuralı "çelişkide Kapsam kazanır" diyor, PLAN 6 ise genişletilmiş olanı listeliyor. Kapsam'a genişletilmiş şema yazılsın; `kind` alanı kaldırılsın.

**2.2 (A) Retention sınıf listesi üç yerde üç farklı.** Kapsam: 7 sınıf. Referans: +`metrics, alerts`. 14: `memory` ("03'te"). Kapsam'da tek liste: `content, telemetry, traces, jobs, metrics, alerts, audit, usage, results, memory`; `memory` varsayılanı 365 (30-1095) burada tanımlanır, 14 yalnızca referans verir.

**2.3 (B) Rate limit sahipliği P7 ile çelişiyor.** 03 teknik not: "rpm/tpm LiteLLM'de uygulanır, bizde yalnızca tanım". LiteLLM yalnızca key/team düzeyinde sınırlar; `scope_type=user` ve `concurrent` pencereleri (P7 kuyruğu) backend'de uygulanır. Not şöyle olmalı: key/team → LiteLLM; user/concurrent → backend (Redis, 06 scheduler ile ortak).

**2.4 (B) Rol sırası ve fixture'lar `user`'ı içermiyor.** `require_role` sırası `user < analyst < developer < admin`; fixture matrisine `user_edit, user_read` eklensin (17 geldiğinde yetki testleri hazır olsun). 10'daki rol görünürlük listesine `user: yalnızca /chat ve Hafızam` satırı.

**2.5 (A) `X-On-Behalf-Of` üç pakette kullanılıyor, hiçbirinde tanımlı değil.** 05 (mcp-search, imzalı JWT), 06 facade (`impersonate` scope), 04 arama ACL'si (başlığı hiç anmıyor). 03b'de tek tanım: başlık adı, imzalı kısa ömürlü JWT formatı, hangi scope ile kabul edilir, backend'in iç servis çağrılarında nasıl üretir. 04 arama API'si bu başlığı kabul ettiğini Kapsam'da yazar.

**2.6 (B) Alembic çoklu head.** 03a, 03b ve 08 aynı dalgada ayrı migration yazar. Kural: her paket kendi `alembic` branch label'ı ile (`03a`, `03b`, `08`) yazar; dalga sonunda tek `alembic merge` PR'ı; CI `alembic heads` tek head bekler.

**2.7 (C) 03a ve 01 arasında `embed_dim` ölçümü.** 03a "kayıt anında test çağrısıyla ölçülür", 04 "globalle uyuşmazsa uyarı". Uyarı yerine 400 olmalı (P5: farklı seçim kabul edilmez); ikisi aynı cümleyi kullansın.

---

## 3. Bilgi tabanı (04)

**3.1 (A) PayCore referans kodu erişimi.** 04, 09, 12, 16 `src/paycore_llm/...` yollarına gönderiyor ama deponun yeri yok ve 09 "gerçek kurum verisi içerir" diyor. PLAN 10'a: PayCore deposunun konumu, hangi dizinlerin okunabileceği, `eval/scenario1` ve benzeri veri dizinlerinin okunmayacağı. Aksi halde 04'ü alan ajan 3 günlük düzeltme setini kaynaksız yazar.

**3.2 (B) `rewrite` (çok biçimli sorgu) "varsayılan açık" ama "M3 sonrası karar".** Her soruda ek bir etkileşimli model çağrısı; CPU'da 30+ s. Seed: `cpu` kapalı, `llmaas` ve `gpu` açık; "M3'te 09 ile ölçülüp karar verilir" cümlesi kalır.

**3.3 (B) `documents.status` enum'u eksik.** Metin `timeout` durumundan söz ediyor, enum'da yok. `pending|converting|gated|chunking|embedding|indexed|skipped|failed|timeout`.

**3.4 (C) `chunk_max_tokens` tanımsız.** Parça boyutu kuralı bu ayara dayanıyor; `knowledge_bases.chunk_size` ile ilişkisi yazılsın (hedef 400, üst sınır 512 gibi).

**3.5 (C) pgvector/Qdrant "ilk 5 aynı küme" kriteri.** İkisi de HNSW yaklaşık; test exact arama ile (`hnsw.ef_search` yüksek / Qdrant `exact=true`) ya da 4/5 örtüşme.

---

## 4. Araç katmanı (05, değişmedi)

**4.1 (B)** Bağımlılığa 08 eklenmeli; `guardrail_mode=enforce` kabul kriteri 08'siz koşmaz.
**4.2 (C)** "`tool_invocations` ya da 06'daki `run_events`" belirsizliği: `run_events` + `mcp_server_calls`; ayrı `tool_invocations` yok.
**4.3 (C)** `mcp_servers`, `mcp_server_calls`, `schema_descriptions`, `few_shots` PLAN 6 tablo listesine eklenmeli.

---

## 5. Agent runtime (06)

**5.1 (A) Enum'lar metinle uyuşmuyor.** `runs.status` listesinde `waiting_user` yok ama metin kullanıyor; 02 referansı `abandoned` ekliyor. `run_events.type` listesinde `guardrail_hook` (02), `budget` (P8), `progress` (D6), `memory_used` (14) yok. `runs`'a `error_code, reference_id, confidence, model_ms, tool_ms, unaccounted_ms, slowest_step` (02, D6, K3) ekleniyor ama veri modeli bölümünde yok. Veri modeli bölümü tek doğru liste olsun.

**5.2 (A) `approval.assign_to` tanım şemasında yok.** 07 bunu okuyor. `definition.approval = {actions: [], assign_to: "developer"}`.

**5.3 (B) Arka plan sınıfı yanlış işler içeriyor.** `topic` guardrail kuralı `input.pre`'de cevaptan önce koşar, arka plana atılamaz; CPU seed'inde `topic` yalnızca anahtar kelime modunda, LLM modu `llmaas`/`gpu`. Geçmiş özeti de "pencerede" beklerse gün içinde hiç üretilmez; sınıf "etkileşimli-düşük" (kuyruk boşken hemen) olmalı, pencereye bağlı değil.

**5.4 (B) 13 ile parça sayısı uyuşmuyor.** 13 "12 parçalı RAG cevabı" ölçüyor; 06 `top_k 5`, `rag_max_tokens 4000` (≈5×400+breadcrumb). 13'ün ölçümü hangi ayarla? Her ikisinde aynı değer (öneri: top_k 8, rag_max_tokens 4000 cpu; top_k 12, 8000 gpu/llmaas).

**5.5 (C) Kanca adları.** Düğüm adları `guard_in/guard_out` kalabilir ama kanca adları 08'in `input.pre, output.pre, tool.pre, tool.post`; bir cümleyle yazılsın.

---

## 6. Onay kuyruğu (07, değişmedi)

**6.1 (C)** `assigned_role` için `user` rolü hiçbir zaman onay veremez; 17 için şimdiden not.
**6.2 (B)** Uyarı/bildirim altyapısı yok (bkz. 9.1); 07'nin SMTP'si tek e-posta kanalı. 07 "SMTP ayarı 03b'de ortak `notifications` ayarından okunur" desin.

---

## 7. Guardrail (08)

**7.1 (A) `stage` enum'u Kapsam'da üç değer, referansta altı + `egress`.** PLAN 5 kuralıyla Kapsam kazanır, bu yanlış sonucu kilitler. Kapsam: `stage: prompt.pre|input.pre|output.pre|output.stream.delta|tool.pre|tool.post|egress`. `pii_policies` tablosu da Kapsam veri modeline yazılır (PLAN 6 sahipliği 08'de).

**7.2 (A) Ad-soyad recall eşiği hâlâ tutturulamaz.** spaCy'nin Türkçe modeli yok; "regex + isim listesi" ile 0,85 (llmaas 0,90) olmaz. llmaas artık birincil pazar ve 0,90 altı yayın admin onayına bağlı: her yayın admin onayı isteyecek. Karar: (a) gerçek Türkçe NER modeli (HF'deki Türkçe BERT NER'lerden biri; 12'de aynaya) ve test seti ekip dışı 100 cümle; (b) ya da ad-soyad "ölçülür ve raporlanır", yayın kapısı yalnızca TC/telefon/IBAN/e-posta için. Önerim (a); CPU'da gecikme bütçesi ayrı ölçülür.

**7.3 (A) P95 < 150 ms kriteri koşulsuz.** DeBERTa tabanlı injection modeli CPU'da tek başına 100-300 ms; aynı CPU Qwen üretirken daha kötü; P3 yolunda bir HTTP atlama daha var. Kriter: "boşta makinede yerel kurallar + injection P95 < 300 ms; yük altında ayrı ölçülür ve yazılır; LiteLLM kancası yolu +50 ms".

**7.4 (B) `egress` varsayılan kategori seti.** Sözleşme parçalarında tarih, karşı taraf adı, VKN, IBAN var; `pii` `tokenize` hepsini yer tutucuya çevirirse model karşılaştırma yapamaz. Aşama bazlı varsayılan kategori listesi yazılsın: `egress`'te doğum tarihi kapalı, TC/telefon/e-posta/kart açık, ad-soyad `tokenize`, IBAN/VKN politikaya göre.

**7.5 (C)** 02 ile "Langfuse'a giden içerik `guard_in` sonrası" → `input.pre` sonrası; llmaas'ta `egress` sonrası.

---

## 8. Evaluation (09) ve demo (13)

**8.1 (A) 13'ün soru seti sayıları toplanmıyor.** Kapsam 4: 20 belge + 5 yok + 5 SQL = 30. Kabul (D7): 14 doğrudan + 8 dolaylı + 5 alan içi cevapsız + 3 alan dışı = 30, SQL yok. Kabul kriterleri ise "20 belge sorusunda 16", "5 cevapsızda 5", "SQL 4/5" diyor. Tek dağılım: 35 item = 12 doğrudan + 8 dolaylı (20 belge) + 5 alan içi cevapsız + 3 alan dışı (8 cevapsız) + 5 SQL ya da 30'a sığdırılırsa her kriter yeniden yazılır. 09'daki "30 soruluk set" cümleleri de aynı sayıya.

**8.2 (B) 09'da eski süre notu kaldı.** "CPU'da 30 soru × 2 çağrı ≈ 10-20 dk" ile D8 notu "1-1,5 saat" aynı brief'te. Eski satır silinir.

**8.3 (A) "Ölçüm temizliği: model sunucusu sıfırlanır" P7 ile çelişir.** Ollama'yı her sınav öncesi yeniden başlatmak etkileşimli istekleri keser ve 85 s ısınma getirir; 09 aynı zamanda "koşu sırasında sohbet bekletilmez" diyor. Kural: sıfırlama yalnızca `BACKGROUND_WINDOW` içinde ya da `EVAL_RESET_MODEL=true` ile; varsayılan kapalı; kapalıyken `summary.warm_cache=true` işaretlenir.

**8.4 (C)** 13 `make seed` kullanıcı listesi: `user_edit/user_read` eklensin (rezerve rolün yetki testi için).

---

## 9. Hâlâ eksik olan zorunlu özellik

**9.1 (A) Uyarılar (alerts).** `quotas.action: warn` var ama uyarının gittiği yer yok; readiness "alarm kuralları kurulu mu" diye soruyor ama kural yok; 16 `prune_refused`, 04 `timeout`, 00 ısınma hatası, 12 disk/bellek, bütçe %80 hiçbir yere bildirilmiyor. En küçük kapsam, 03b'ye: `alert_rules(kind, threshold, channel: email|webhook, recipients)`, `alerts(rule_id, fired_at, payload, acked_by)`; olay türleri: bütçe eşiği, servis down (`/readyz` 5 dk), ingest/senkron hatası, bekleyen onay süresi, guardrail block oranı. 10'da "Uyarılar" ekranı (İşletme grubu). Retention sınıfı `alerts` zaten var, kullanan yoktu.

---

## 10. Hafıza (14), kanallar (15), veri kaynakları (16), önyüz (10)

**10.1 (B, 14)** `@audited` before/after hafıza metnini audit'e yazar; 14 "audit'te metin yok" diyor. 03b'ye: `@audited(..., redact_fields=[...])` ya da `audit_payload=False`; 14 bunu kullanır. Kabul kriteri "hiçbir API ile" → "API üzerinden" (DB ve yedek erişimi ayrı konu).
**10.2 (C, 14)** `memory-extract` sanal modeli 01 seed dosyalarına (cpu: Qwen, llmaas: küçük sağlayıcı modeli).
**10.3 (B, 16)** "SharePoint `delta` ile silinen dosya indeksten kalkar" ile "delta koşu hiçbir koşulda silmez" çelişiyor. Karar: kaynağın tombstone verdiği bağlayıcılarda (Graph delta) delta silme yapabilir ama D4 oran kuralı (`PRUNE_MAX_RATIO`) yine uygulanır; ya da kriter "bir sonraki `full` koşuda kalkar" olur.
**10.4 (C, 15)** `runs.channel` enum'una `slack|teams|mattermost|widget` 06'da eklenir; widget kimliği (intranet oturumu → imzalı token) 17'ye bağlıdır, 15'in bağımlılığına "widget kimliği için 17" notu.
**10.5 (B, 10)** Agent sihirbazında P8 `context_policy`, 14 "Hafıza" ve 15 "Kanallar" sekmeleri yok; "5. Güvenlik" altına "Bağlam ve limitler" (history_turns, rag_max_tokens, timeout) eklenir. Sistem Durumu ekranına P7 kuyruk uzunluğu ve beklenen süre. Rol matrisi yeni ekranlar için eksik: Sağlayıcılar/Modeller/Sistem Durumu (admin), Veri Kaynakları (developer), Uyarılar (admin).
**10.6 (C, 02)** Fiyat tek kaynak: `models.pricing` → LiteLLM `input_cost_per_token`; Langfuse fiyat tablosu ve `LOCAL_MODEL_PRICE_PER_1K` kaldırılır, maliyet LiteLLM callback'inden gelir. "5 s içinde Langfuse UI" → 30 s ya da API ile doğrulama.
**10.7 (C, 12)** `docling` ayrı imaj değil, worker içinde kütüphane; Docling'in layout modelleri imaja gömülür (HF indirmesi offline'da kırılır). Langfuse airgap küçük kurulumda `profiles: [observability]` ile isteğe bağlı; llmaas'ta açık.
**10.8 (C, 04/06)** Kuyruk kütüphanesi tek: `arq` (async); 04 worker, 06 scheduler ve 16 senkron aynı kuyruk altyapısı, ayrı kuyruk adları (`ingest`, `llm-interactive`, `llm-background`, `sync`).

---

## 11. PLAN.md tutarlılık

- Bölüm 7 tablosu: 05 bağımlılığına 08; toplam süre yazılsın (00-17 toplamı ≈ 69,5 agent-günü, tek ajan serisi).
- Bölüm 6: `attachments, ingest_gate_stats, mcp_servers, mcp_server_calls, schema_descriptions, few_shots, channels, channel_bindings, channel_identities, channel_threads, data_sources, source_items, sync_runs, sync_state, acl_mappings, alert_rules, alerts, conversations, messages` eksik.
- Bölüm 5 P9 kuralı: "çelişkide Kapsam kazanır" iyi ama 2.1, 2.2 ve 7.1'deki gibi referansın doğru olduğu yerler Kapsam'a taşınmadan kural yanlış sonucu kilitler. Bu dosyadaki A maddeleri işlendikten sonra kural güvenle uygulanır.
- Bölüm 2 kapasite satırı "CPU'da tek şerit" → `llmaas`'ta sağlayıcı eşzamanlılığı ve 429 geri çekilmesi (01 retry) ayrı cümle.

---

## Karar isteyen maddeler (kısa)

1. 0: Ürün varsayılanı `llmaas`, pilot `airgap` cümlesi. Önerim: evet.
2. 1.2: `agent:` yönlendirmesi LiteLLM'den kalksın, facade tek kapı. Önerim: evet.
3. 1.1: Ad uzayı `<project>.<model>` / `agent:<project>/<key>`. Önerim: evet.
4. 1.4: LiteLLM model yönetimi DB API ile, config yalnızca açılış. Önerim: evet.
5. 7.2: Türkçe NER gerçek model (a) ya da yumuşak kapı (b). Önerim: (a).
6. 8.1: Soru seti 35 item mı, 30'a sığdırılıp kriterler mi yeniden yazılır. Önerim: 35.
7. 9.1: Uyarılar 03b'ye. Önerim: evet.
8. 10.3: Delta silme kuralı. Önerim: tombstone veren bağlayıcıda delta silebilir, oran kuralı korunur.
