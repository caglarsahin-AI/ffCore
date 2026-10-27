# 00i. PayCore LLM entegrasyon tabanı ve sıkılaştırma [FFCore Platform]

**Bağımlılık:** 00 (FFCore deposu iskeleti, path bağımlılığı için). **Süre:** 4 gün (entegrasyon tabanı 1, API kimlik sınırı 1,5, compose sıkılaştırma 1, eşzamanlılık düzeltmesi 0,5). **Dalga:** 1, 00 ile birlikte; **03a, 01 ve 04a bu paket MERGED olmadan başlamaz** (karar 3: Faz 1 açıkları önce). **PoC:** evet. **Touch-zone: `C:\ai_paycore\paycoreLLM` deposu** (FFCore deposuna yalnızca `docs/paycore-entegrasyon.md` yazar).

## Amaç

FFCore'un canlı test yeri PayCore LLM'dir (internetsiz sunucu, Qwen 3.5 35B Ollama CPU, Qdrant, Confluence/Jira korpusu). Bu paket, FFCore katmanları gelmeden önce PayCore'u (1) FFCore'u tüketebilecek hale getirir, (2) inceleme v9/v10'un bulduğu açık güvenlik kusurlarını kapatır, (3) PayCore Faz 1'in açık işlerinden FFCore'un önkoşulu olanları bitirir. Kaynak: `state/reviews/brief-inceleme-v9.md` (P1-P5, P8, P9) ve `brief-inceleme-v10.md` (B1, B3, B4, P4, P5).

## Kapsam

### A. Entegrasyon tabanı (karar 1, 2)

- **Depo modeli:** FFCore ayrı depoda kalır; paycoreLLM tüketicidir. Geliştirmede `pip install -e ../ffcore` (path bağımlılığı, `pyproject.toml` `[tool.uv.sources]` ya da `-e` satırı), sunucuda iç registry'den (`nexus.paycore.com`) wheel ve imaj. Tek yön: `paycore_llm → ffcore`; `ffcore` hiçbir yerde `paycore_llm` import etmez (CI'da import testi, FFEngine Community/Enterprise kuralıyla aynı).
- **Anayasa:** paycoreLLM kökündeki `CLAUDE.md` FFCore'un CLAUDE.md'sine işaret eden kısa bir giriş olur; PayCore'un mevcut CLAUDE.md'si `docs/paycore/KURALLAR.md`'ye taşınır ve **sıkı kuralları aynen geçerli kalır:** dış servise veri gönderilmez, `.env`'e dokunulmaz, sunucuya ajan bağlanmaz (komutları kullanıcı çalıştırır), Jira yazma kapısı (`JIRA_SUGGESTIONS_ENABLED=false`) kapalı, bellek bütçesi aşılmaz. Değişen tek kural: "dal açılmaz, doğrudan master" yerine FFCore'un branch + PR akışı (KARARLAR tersine karar).
- **Faz kilidi (karar 3):** PayCore'un "Faz 2 kodu yazılmaz (W17)" kuralı, bu paketin kabul kriterleri MERGED olduktan sonra **yalnızca sentetik sunum DB'si** için açılır; gerçek PayCore verisine text-to-SQL PoC'de yok.
- **Yerleşim:** PayCore'a özgü `jira/`, `prsim/`, `router/` modülleri `src/paycore_llm/` altında **uzantı** olarak kalır ve FFCore'un uzantı noktalarına (CONTRACTS C14: `ffcore.sources`, `ffcore.tools`, `ffcore.guardrail_rules`, `ffcore.seeds`) kayıt olur; FFCore kodu paycoreLLM'e kopyalanmaz. FFCore örnek verisi paycoreLLM `data/` altına **girmez**.
- **Compose:** PayCore'un `compose.yml` / `compose.server.yml` korunur; FFCore servisleri (backend, worker, frontend konsol, litellm, redis, mcp-sql, mcp-search) `compose.ffcore.yml` override'ı olarak eklenir. Ollama host'ta kalır (`host.docker.internal:11434`). **Langfuse v3** (00'daki yığın; mevcut v2'de gönderilmiş iz yok, veri göçü gerekmez; bellek artırımı onaylandı). Open WebUI kalır (karar 7: PoC chat'i), 4B router modeli kapatılır (karar 6).
- **Bellek tablosu:** `docker stats` ile ölçülmüş bütçe (`docs/paycore/bellek.md`): her konteynerin `mem_limit`'i ve gerçek kullanımı; modeller (bge-m3 dense+sparse, reranker) **yalnızca API süreci** tarafından yüklenir, worker ve Jira işçisi aramayı 04a arama API'sinden yapar. Bellek artırımı talebi için gereken sayı bu tablodan çıkar.
- **Terim:** PayCore CLI'daki `bronze` adı uzantıda kalır, FFCore API ve ekranda `raw` (TERMINOLOGY); `sync_state` tablo adı çakışması: FFCore'unki `source_sync_state` (16). PayCore'un `init.sql` tabloları FFCore Alembic zincirinde bir "taban" migration'ı ile sahiplenilir (tek şema kaynağı).

### B. API kimlik sınırı (v10 B3)

- `/ask`, `/v1/models`, `/v1/chat/completions` ve `/health` dışındaki her uç kimliksiz istekte **401** döner. PoC sınırı tek: Open WebUI → API çağrısı kuruluma özel güçlü servis anahtarıyla (`PAYCORE_API_KEY`, `.env`'de, `${VAR:?}` ile zorunlu); `local` gibi varsayılan değer yasak.
- Audit aktörü: Open WebUI'nin son kullanıcı kimliğini imzalı biçimde ilettiği doğrulanırsa (U1) kullanıcı; doğrulanamazsa aktör açıkça `openwebui_service` yazılır, kişiymiş gibi gösterilmez. 03b geldiğinde bu sınır FFCore `resolve_actor()`'a bağlanır.
- Ham anahtar loglanmaz; `Authorization` başlığı merkezi sanitizer'da maskeli.

### C. Compose sıkılaştırma (v10 B4)

- Zorunlu secret'lar `${VAR:?mesaj}` ile fail-loud; `CHANGE_ME` varsayılanları silinir.
- Qdrant, Langfuse, Postgres, Ollama ve Redis portları host'a yayınlanmaz ya da yalnızca `127.0.0.1`'e bind edilir; dışarı yalnızca Open WebUI ve kimlik doğrulamalı API.
- Worktree'lere gerçek `.env` kopyalanmaz; işçiler `.env.test` (sahte değerler, `FAKE_LLM=1`, Atlassian kapalı) ile çalışır (v9 P8). Okuma yasağı dosya düzeyinde: `.env`, `data/**`, `eval/results/**` yasak; `eval/scenario*/questions.jsonl` (S1, iç dokümantasyon sorusu, karar 4) ve `experts/*.yaml` şablonları okunabilir, FFCore deposuna kopyalanmaz.

### D. Eşzamanlılık düzeltmesi (v9 P9, PayCore Faz 1 açığı)

- `rag/retrieve.py` `search()` ve `rag/pipeline.py` `answer_question()` içindeki senkron `embed()`/`rerank()` çağrıları `asyncio.to_thread` + model başına `threading.Lock` ile iş parçacığına alınır. Bu, FFCore 04a'nın D6 kabul kriteriyle aynı iştir ve FFCore'un PayCore'daki ilk görünür faydasıdır.
- `embed.py` `embedding_truncated` uyarısı sessiz kalmaz: parça `flagged` + gerekçe (fail-loud).

### E. Faz 1 önkoşulları (v10 P5, P7'nin FFCore'a giren kısmı)

- Langfuse gönderimi: `rag/trace.py` verisi Langfuse'a gider (02 bu paketin üstüne gelir; burada yalnızca SDK bağlantısı ve `trace_delivery_failed` kaydı).
- S1 koşusu: mevcut `eval/run.py` ile S1 seti sunucuda **kullanıcı tarafından** koşturulur, sonuç `docs/paycore/s1-taban.md`'ye yazılır (FFCore öncesi taban ölçümü; 13b aynı setle karşılaştırır).
- PRSIM `similar_requests` ve `criteria_document` eksikleri FFCore'un önkoşulu değildir; PayCore uzantı kuyruğunda kalır (karar 5: PRSIM ingest'ine kişi verisi guard'ı 08 geldiğinde eklenir, o zamana kadar ertelendi).

## Teslimatlar

- paycoreLLM: `pyproject.toml` path bağımlılığı, kök `CLAUDE.md` girişi, `docs/paycore/KURALLAR.md`, `compose.ffcore.yml`, sıkılaştırılmış `compose.yml`, `.env.test`, kimlik middleware'i, `to_thread` düzeltmesi, `docs/paycore/bellek.md`, `docs/paycore/s1-taban.md`.
- FFCore: `docs/paycore-entegrasyon.md` (model, uzantı noktaları, sürüm eşlemesi `FFCORE_VERSION` ↔ `PAYCORE_LLM_VERSION`).

## Kabul kriterleri

- `pip install -e ../ffcore` sonrası paycoreLLM `import ffcore` eder; `ffcore` paketinde `paycore_llm` import'u yoktur (CI testi).
- Servis anahtarsız `curl /v1/chat/completions` 401; anahtarla 200; ham anahtar hiçbir logda görünmez.
- `.env`'de zorunlu bir secret eksikken `docker compose up` açık hata ile durur; `docker compose config` çıktısında Qdrant/Langfuse/Postgres/Ollama/Redis için host portu yoktur.
- 10 eşzamanlı `/ask` isteğinde `/health` 1 saniyenin altında cevap verir (donma yok).
- Bellek tablosu ölçülmüş değerlerle dolu; toplam `mem_limit` fiziksel bellek − işletim sistemi payının altında (artırım sonrası değer ile).
- S1 taban ölçümü belgede; FFCore'a dokunulmadan koşulmuş.
- Jira yazma kapısı kapalı: `JIRA_SUGGESTIONS_ENABLED=true` olmadan hiçbir yazma çağrısı yapılmadığını test kanıtlar.

## Teknik notlar

- Sunucuya ajan bağlanmaz; sunucu komutlarını kullanıcı çalıştırır, çıktıyı PR'a yapıştırır; paket "VERIFIED (ölçüm bekliyor)" olarak işaretlenebilir (EXECUTION_HANDBOOK istisnası, yalnızca bu depo için).
- Open WebUI → API kimlik aktarımı (U1), Langfuse SDK uyumu (U16) pinli sürümde doğrulanır; doğrulanamayanlar `DRIFT-` kaydı.

## Kapsam dışı

FFCore servislerinin kendisi (01-13), PRSIM eksikleri, DuckDB → Postgres göçü, Langfuse v2 verisi (yok), yeni özellik.
