# 05. Araç katmanı: MCP kaydı, mcp-sql (text-to-SQL), mcp-search [FFCore Tools]

**Bağımlılık:** 03a, 03b (`SERVICE_TOKEN`, `core/egress.py`), 04a, 08 (`guardrail_mode=enforce` kabul kriteri 08'siz koşmaz; R4.1). **Süre:** 7 gün, iki alt paket ve iki PR (05a 4, 05b 3; inceleme v4-v6). **Dalga:** 05a dalga 4, 05b PoC sonrası. **PoC:** 05a.

**05a, çekirdek (≈3 gün, kritik yol, M3 öncesi zorunlu):** A (araç kaydı, MCP istemcisi, keşif, aksiyon bazlı onay/açık, doğrudan test çağrısı), A2 (upstream kimlik türleri dahil `forward_user`), B (`mcp-sql`: `get_schema`, `run_sql`, doğrulayıcı, `schema_descriptions`, `few_shots`), C (`mcp-search`). Kabul kriterleri: A3 dışındakiler.
**05b, yayınlama (≈2 gün, kritik yol dışı):** A3 (OpenAPI'yi MCP sunucusu olarak yayınlama, `mcp_servers`, `mcp_server_calls`, guardrail modu, `remote_mcp`), Superset örneği ve metrik senkronu, OpenAPI türü araç (httpx). Kabul kriterleri: A3 ve Superset maddeleri.

## Amaç

Agent'ların "elleri". Araçlar backend'e MCP sunucusu olarak kaydedilir; backend MCP istemcisidir, araç listesini keşfeder, çağrıları loglar. İki yerleşik MCP servisi: text-to-SQL ve belge arama.

## Kapsam

### A. Araç kaydı (backend)

- `tools(id, project_id, key, name, kind: mcp|openapi, endpoint_url, auth_config (şifreli), status, discovered_at)`
- `tool_actions(id, tool_id, name, description, input_schema jsonb, needs_approval bool, enabled bool, max_calls_per_run, timeout_s)`
- API: tool CRUD; `POST /tools/{id}/discover` (MCP `tools/list` ile aksiyonları çeker, `tool_actions`'a yazar); aksiyon bazlı `needs_approval` ve `enabled` düzenleme; `POST /tools/{id}/actions/{name}/invoke` (doğrudan test çağrısı, audit'li).
- MCP istemcisi: `backend/app/services/mcp_client.py`, resmi `mcp` Python SDK, streamable HTTP taşıma; HTTP çıkışı `core/egress.py` SafeOutboundClient ile (C5). Bağlantı havuzu yalnızca `none/bearer/header/basic` kimlikli araçlarda; `forward_user` araçlarında havuz **yok**, oturum çağrı başına açılır (C3; SDK'nın başlıkları oturum açılışında alıp almadığı pinli sürümde doğrulanır, U5). Çağrı sonucu `TOOL_RESULT_MAX_CHARS` ile kırpılırsa modele giden metne `[kırpıldı: N/M karakter]` işareti eklenir ve olaya `truncated=true` yazılır (C13); tamamı `run_events`'e yazılır (06a).
- OpenAPI türü (05b): spec yüklenir, her operation bir aksiyon olur; çağrı `core/egress.py` üzerinden. (MCP önce, OpenAPI basit düzeyde.)

### A2. Upstream kimlik seçenekleri (tüketme tarafı)

`tools.auth_config` şu türleri destekler (tamamı şifreli saklanır, API cevabında maskeli): `none`, `bearer` (sabit token), `header` (özel başlık adı ve değeri), `basic` (kullanıcı adı ve şifre), `forward_user` (çağıran kullanıcının kimliği `X-On-Behalf-Of` JWT'si ile; **her çağrıda yeni imza, `aud=<tool_key>`**, yalnızca `ALLOWED_INTERNAL_HOSTS` içindeki FFCore servislerine izinli, üçüncü taraf upstream'e `forward_user` seçilemez, C3; mcp-search bunu kullanır). `discover` ve `invoke` aynı kimlikle çalışır; bağlantı testi sonucu ekranda görünür. `endpoint_url` ve `upstream_base_url` kullanıcı girdisidir, SSRF koruması `core/egress.py`'den gelir (C5).

### A3. OpenAPI'yi MCP sunucusu olarak yayınlama (outbound proxy)

Kurumsal sistemleri (Superset, HBYS, SAP, Jira) kod yazmadan agent aracına çevirmek için:

- `mcp_servers(id, project_id, key, name, source_kind: openapi|remote_mcp, spec (yaml/json, şifreli), upstream_base_url, upstream_auth (A2 türleri), exposed_operations[], protocols: [streamable_http], access: token|internal, guardrail_mode: off|monitor|enforce, status)`
- Backend, her sunucu için `/mcp/{key}/` yolunda bir MCP uç noktası sunar (resmi `mcp` SDK sunucu tarafı): OpenAPI operation'ları MCP araçlarına çevrilir (operationId -> araç adı, parametreler -> input_schema, açıklama -> description); yalnızca `exposed_operations` listesindekiler açılır; ad ve açıklama ekrandan düzenlenebilir (model için kısaltma).
- Çağrı akışı: agent -> backend MCP uç noktası -> guardrail `tool.pre` (argümanlar, 08) -> upstream HTTP çağrısı -> guardrail `tool.post` (sonuç) -> cevap. `guardrail_mode=monitor` yalnızca loglar, `enforce` engeller.
- Erişim (C14): `access=token` ise çağıran 03c'teki API anahtarıyla gelir, anahtarda `tools_invoke` kapsamı zorunlu ve proje yetkisi kontrol edilir; `internal` ise yalnızca runtime (06) çağırabilir. Herkese açık mod yok (kurumsal ürün). `/mcp/{key}/` backend'in ikinci onaylı dış yüzeyidir (PLAN 5 R1.2): facade ile aynı `resolve_actor`, kota, guardrail ve audit'ten geçer.
- Kaydedilen sunucu, aynı ekrandan tek tıkla A'daki `tools` tablosuna da eklenir (kendi kendini tüketme), böylece agent'a bağlanır.
- Postman koleksiyonu içe aktarma **reddedildi** (FELSEFE ARCH-07, META-06): Postman OpenAPI dışa aktarabiliyor; ayrı dönüştürücü %1 senaryo için kalıcı bakım yükü. Kullanıcı OpenAPI dosyasını yükler. KARARLAR.md "Reddedilenler".
- `remote_mcp` kaynağı: dış bir MCP sunucusunu bizim uç noktamız arkasından yayınlar (kimlik ekleme, guardrail ve log için); composite ve npx/uvx kapsam dışı.
- İzleme: `mcp_server_calls(server_id, operation, status, latency_ms, ts, run_id?)` tablosu; 10'da "MCP İzleme" ekranı (sunucu başına 24 saat istek, hata, gecikme, son çağrılar, audit).
- Örnek: `data/samples/openapi/superset.yaml` (Superset'in `/api/v1/_openapi` çıktısından 6 operation: dashboard ara, chart listele, chart verisi, dataset metrikleri, chart oluştur [onaylı], dashboard'a ekle [onaylı]) ile uçtan uca test. Superset metrik tanımlarını `schema_descriptions`'a senkronlayan script `data/samples/scripts/sync_superset_metrics.py` düzeyinde kalır, genel araç değildir (N7).

### B. `services/mcp-sql` (text-to-SQL, ayrı konteyner)

- Resmi MCP SDK ile sunucu, iki araç:
  - `get_schema(question?)`: `schema_descriptions` tablosundan iş dili açıklamalarını döner (tablo, kolon, örnek değer, metrik formülü); soru verilirse ilgili tablolara daraltır (basit anahtar kelime eşleşmesi).
  - `run_sql(sql, reason)`: doğrulayıp çalıştırır, en çok `SQL_MAX_ROWS` (varsayılan 500) satır ve `SQL_TIMEOUT_S` (20) saniye; sonuç CSV benzeri kompakt metin + satır sayısı.
- Doğrulayıcı (`sqlglot`): tek `SELECT`, bilinen şemadaki tablolar, `INSERT/UPDATE/DELETE/DROP/ALTER/COPY` yok, `pg_*` ve `information_schema` yok, alt sorgu derinliği ≤ 3, `LIMIT` yoksa eklenir.
- Bağlantı: salt-okunur Postgres kullanıcısı, `statement_timeout` DB tarafında da ayarlı. Hedef DB: `data/samples/schema/` ile kurulan demo "agent sunum DB'si" (13a dalga 1'de hazır; bu paket onu kullanır).
- `schema_descriptions(table_name, column_name, description_tr, sample_values, is_metric, formula)` tablosu ve yükleme scripti.
- `few_shots(id, kb_or_project scope: project_id, question, sql, embedding vector(EMBED_DIM), approved_by, created_at)`: örnek soru-SQL çiftleri; `get_schema` cevabına en yakın 5 örnek eklenir, benzerlik süreç içi bge-m3 dense + seçili vektör sürücüsü ile (tek yol, N17; C10 tersine).
- Her çağrı loglanır: soru, SQL, süre, satır, hata.

### C. `services/mcp-search` (belge arama)

- Tek araç `search_documents(query, kb_key, top_k=5)`: backend `POST /kb/{id}/search`'ü çağırır (iç servis hesabı `SERVICE_TOKEN` ile, 03b; çağıran kullanıcının kimliği `X-On-Behalf-Of` başlığıyla taşınır ki ACL doğru uygulansın; `X-Run-Id` iletilir, C12).
- Sonuç formatı: numaralı parçalar, her birinde belge adı ve sayfa; runtime bunları kaynak gösterimi için kullanır.

## Teslimatlar

- Backend: migration, modeller, router'lar, `mcp_client.py`, testler.
- `services/mcp-sql/` ve `services/mcp-search/`: Dockerfile, README, testler; compose'a eklenmiş.
- `docs/araclar.md`: yeni MCP sunucusu nasıl eklenir, `needs_approval` nasıl işler.

## Kabul kriterleri

- mcp-sql kaydedilip `discover` edilince iki aksiyon listelenir.
- `run_sql("DELETE FROM ...")` doğrulayıcıdan 400 ile döner, DB'ye gitmez.
- `run_sql` 500 satırdan fazla dönecek sorguda kırpar ve bunu sonuçta belirtir.
- `search_documents` çağrısı ACL'yi uygular (analyst, admin belgesini göremez).
- (R4.2, B3) Her araç çağrısı bu pakette `mcp_client` çağrı kaydıyla (yapısal log: tool, action, latency, status, truncated) test edilir; 06a entegrasyonunda aynı çağrı `run_events` (`tool_call`/`tool_result`) satırı olur ve bu 06a'nın kabul kriteridir. Yayınlanan sunucular için `mcp_server_calls` (05b). Ayrı `tool_invocations` tablosu yoktur. (R4.3) Bu paketin tabloları: `tools, tool_actions, mcp_servers, mcp_server_calls, schema_descriptions, few_shots` (PLAN.md 6).
- `superset.yaml` ile yayınlanan MCP sunucusu `discover` edilince 6 araç listelenir; `chart oluştur` çağrısı onay bekler; `guardrail_mode=enforce` iken yasak argüman kalıbı 08 tarafından engellenir ve `mcp_server_calls`'a düşer.
- `basic` kimlikli bir upstream'e yapılan çağrıda kullanıcı adı ve şifre loglarda ve API cevaplarında görünmez.
- `forward_user` ile çağrılan mcp-search, çağıran kullanıcının ACL'sini uygular; **iki kullanıcının eşzamanlı run'ında** (analyst ve admin) ACL karışmaz (C3 kabul kriteri). Süresi dolmuş JWT ile çağrı 401 döner ve runtime yeni JWT imzalar.
- (C5) `endpoint_url` olarak `http://127.0.0.1`, `http://10.0.0.5`, `http://169.254.169.254` ve izin listesi dışı alan adı kayıt anında ya da çağrıda reddedilir; `ALLOWED_INTERNAL_HOSTS`'taki `mcp-search` kabul edilir.
- (C13) `TOOL_RESULT_MAX_CHARS` aşan sonuçta modele giden metin `[kırpıldı: N/M karakter]` ile biter ve olayda `truncated=true`.

## Teknik notlar

- MCP taşıma: streamable HTTP; stdio konteynerler arası uygun değil.
- Qwen'in tool-calling'i zayıf olabileceği için araç adları ve açıklamaları kısa, parametreler az; `get_schema` ve `run_sql` ayrı tutulması bu yüzden.
- `needs_approval` varsayılanı: `run_sql` için `false` (salt-okunur), ileride yazma yapan araçlar için `true`. **PoC'de (PLAN 2d):** SQL asistanı `max_tool_calls: 1` ve `run_sql` onaylı; hedef yalnızca 13a'nın sentetik sunum DB'si (W17 kilidi karar 3 ile bu kapsamda açıldı), PayCore verisine SQL yok.

## Kapsam dışı

HBYS'ye yazan araçlar, web search, tarayıcı otomasyonu, composite MCP sunucusu (birkaç sunucuyu tek uçta birleştirme), npx/uvx paketlerini stdio'dan HTTP'ye köprüleme, MCP Hub (katalog ve keşif API'si), herkese açık MCP uç noktası. Veri modeli composite için `mcp_servers.source_kind` değerine `composite` eklenmesine izin verir. Postman koleksiyonu içe aktarma (reddedildi, KARARLAR). Üçüncü taraf upstream'e `forward_user` (C3).
