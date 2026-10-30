# PR: 10b-poc-2 araçlar, agent sihirbazı ve test paneli, koşular, onaylar

**Paket:** 10b-poc-2 · **Sınıf:** [A] · **Branch:** feat/10b-poc-2 · **Baz commit:** fcbcfc4 (main; 06a c8c8868 dahil) · **HEAD:** — (kod yok) · **Oturum:** ffcore-isci-c-10bp2 · **GOREV:** K-10bp2-0001 · `FFCORE_VERSION=0.0.0-10bp2`

## Plan (kodlamadan önce)

### 1. Bulunan semboller ve dosyalar (gerçek kod, fcbcfc4 + feat/07-approvals 4d39f7f)

- **05a** `backend/openapi/05a.yaml`:
  - Uçlar: `GET/POST /api/v1/projects/{p}/tools`, `GET/PATCH/DELETE .../tools/{tool_id}`, `POST .../{tool_id}/discover`, `PATCH .../{tool_id}/actions/{action_name}`, `POST .../actions/{action_name}/invoke`. `sql-context` ve `internal/obo/verify` iç uçlar, ekran yok.
  - Rol (`api/tools.py`): okuma `require_role("developer")`; kayıt, düzenleme, silme, keşif, aksiyon PATCH ve invoke `admin + write`.
  - Şemalar: `ToolCreate {key, name, kind: mcp|openapi, endpoint_url, auth}`. `auth` beş tür, `type` ile ayrılıyor: `AuthNone`, `AuthBearer`, `AuthHeader`, `AuthBasic`, `AuthForwardUser`; gizli alanlar `***` döner. `ToolOut` alanları: `status`, `discovered_at`, `last_error_code`, `actions[]`. `ToolActionOut` alanları: `name`, `description`, `input_schema`, `needs_approval`, `enabled`, `max_calls_per_run`, `timeout_s`, `status`. `InvokeResult` alanları: `text`, `truncated`, `total_chars`, `is_error`, `latency_ms`.
  - Hata kodları (KARARLAR 05a r1): `endpoint_url_not_allowed`, `header_name_not_allowed`. Keşfedilen aksiyonlar `enabled=false` ve `needs_approval=true` ile gelir.
- **06a** `backend/openapi/06a.yaml`:
  - Agent uçları: `GET/POST /agents`, `GET/PATCH/DELETE /agents/{id}`, `GET/POST /agents/{id}/versions`, `GET/PUT .../versions/{v}`, `POST .../publish`, `POST .../rollback`.
  - Run uçları:
    - `POST /agents/{agent_key}/runs`: SSE döner; ilk olay `progress {run_id}`.
    - `GET /runs` filtreleri: `agent_id`, `channel`, `status`, `feedback=pending|given`.
    - Diğerleri: `GET /runs/{id}`, `GET /runs/{id}/events`, `GET /runs/{id}/stream` (`Last-Event-ID`), `POST .../resume`, `POST .../cancel`, `POST .../feedback {vote: correct|partial|wrong, note?}`.
  - Rol: agent okuma `analyst`, agent yazma `analyst + write` (`api/agents.py`); run uçları `user` üyesi (`api/runs.py`); resume `definition.approval.assign_to`.
  - C8 (`runtime/definition.py`): `model`, `system_prompt` | `langfuse_prompt {name, label}`, `variables[{key, label, default}]` ve `{{key}}`, `knowledge[{kb_key, mode: always|tool, top_k, min_score}]`, `tools[{tool_key, actions}]`, `approval {actions, assign_to=analyst}`, `ask_user`, `guardrail_policy_key`, `structured_output`, `limits`, `context_policy`, `answer_rules`, `reasoning`, `runtime_profile=default`. Bilinmeyen alan 422. Desteklenmeyen seçenekler kodla reddedilir: `verify_not_supported`, `confidence_formula_not_supported`, `knowledge_filter_not_supported`.
  - C9 (`CONTRACTS.md`): 8 status, 18 `run_events.type`, 10 SSE adı. Tüketici bilmediği olayı yok sayar.
  - `docs/agentlar.md`: akış `done`, `error`, `approval_required` ya da `question` ile biter. Süresi dolan canlı akış `progress {"replay": "run_events"}` ile tekrar oynatılır.
- **07** (feat/07-approvals @ 4d39f7f; `backend/openapi/07.yaml` **henüz dalda yok**, `api/approvals_schemas.py` kaynak):
  - Uçlar: `GET /projects/{p}/approvals` (`status` filtresi), `GET .../approvals/count`, `GET .../approvals/{id}`, `POST .../{id}/approve|reject {note?}`.
  - Rol: okuma `analyst`, karar `analyst + write` ve `assigned_role` kontrolü.
  - Şema: `ApprovalOut` alanları: `action`, `tool_key`, `arguments` (maskeli), `reason_from_model`, `status` (pending|approved|rejected|expired), `assigned_role`, `expires_at`, `can_decide`. `ApprovalDecided.stream_after` alanı, akışı `Last-Event-ID` ile sürdürmeye yarar.
- **Önyüz (main):**
  - `lib/navigation.ts`: `tools` developer, `agents`, `runs`, `approvals` analyst; hepsi `ready: false`.
  - `lib/api/client.ts` `api()` yalnız JSON çağrı yapıyor; SSE yardımcısı yok.
  - `scripts/check-api.mjs` `SPECS` yalnız 03a ve 04a; `package.json` `gen:api` de öyle.
  - Kalıplar (C-10bp1-0011): `Screen`, `ListState`, `QueryError`, `WriteGate projectId`, `DisabledWithReason`, `<fieldset disabled={!canWrite}>`, geçişte invalidation, görünür yenileme göstergesi, bilinmeyen kodun ham gösterilmesi.
  - `next.config.ts` rewrite: `/api/v1/:path*` → backend (C6).

### 2. Kapsam ve kapsam dışı

**Kapsam:**
1. **Araçlar:**
   - liste (ad, anahtar, tür, durum, son hata kodu, aksiyon sayısı) ve kayıt/düzenleme formu: tür, endpoint, beş kimlik türü, gizli alan maskeli ve boş bırakılırsa korunur;
   - silme onaylı;
   - "Keşfet" ve aksiyon tablosu: açık, onay gerekli, çağrı sınırı, zaman aşımı;
   - "Dene" formu: `input_schema`'dan JSON argüman alanı; sonuç metni, `truncated`/`total_chars`, `is_error`, gecikme;
   - endpoint ve başlık doğrulama hataları kodlu mesajla gösterilir.
2. **Agent'lar:**
   - liste: durum, yayınlanan sürüm, model;
   - oluşturma: anahtar, ad, açıklama, model; taslak sürüm 1 açılır;
   - sekmeli sihirbaz:
     - Kimlik;
     - Talimat: serbest metin ya da Langfuse prompt adı + etiketi; değişken tablosu; `{{key}}` uyarısı istemcide, kesin red sunucunun `variable_undefined` kodu;
     - Bilgi: KB seç, `always|tool`, top_k, min_score; rerank açık KB'de min_score pasif ve açıklamalı;
     - Araçlar: keşfedilmiş ve açık aksiyonlardan seçim; onay listesi; `assign_to` varsayılanı analyst, `user` seçeneği yok;
     - Güvenlik ve limitler: guardrail politika anahtarı, `ask_user`, limitler, bağlam politikası;
     - Çıktı: serbest ya da JSON şeması;
     - Test;
     - Yayın: sürüm listesi, yeni taslak, yayınla, geri al.
   - Yayınlanmış sürüm düzenlenmez: 409 `version_published` mesajı ve "yeni taslak aç" yolu.
3. **Test paneli (sihirbazın sağ paneli):**
   - `channel=test` run, `fetch` + `ReadableStream` SSE (brief teknik notu);
   - akışta görünenler: token akışı, araç çağrısı ve sonuç kartları (argüman maskeli, olduğu gibi), kaynak kartları;
   - `approval_required` → satır içi onay istemi (karar yolu D1), `question` → cevap alanı;
   - koparsa `Last-Event-ID` ile yeniden bağlanma;
   - bilinmeyen olay yok sayılır (C9 kuralı, birim testi);
   - `error` kodlu mesaj, iptal düğmesi.
4. **Koşular:**
   - liste: filtreler agent, kanal, durum, geri bildirim (`pending|given`);
   - ayrıntı: durum, olay zaman çizelgesi (18 tip; bilinmeyen tip ham etiketle gösterilir), maskeli argümanlar olduğu gibi (ham değer yok), sonuç;
   - iptal düğmesi;
   - F9: tamamlanmış run'da oy (`correct|partial|wrong`) + not, `edit` ister; "bekleyenler" = `feedback=pending` filtresi;
   - "Langfuse'ta aç" bağlantısı yalnız şema iz kimliği ve yapılandırılmış URL taşıyorsa (varsayım 4).
5. **Onaylar:**
   - bekleyen liste (durum filtresi), kenar çubuğunda sayaç rozeti (`/approvals/count`);
   - ayrıntı: agent/run bağlantısı, aksiyon, maskeli argümanlar vurgulu, model gerekçesi, kalan süre;
   - Onayla / Reddet + not; düğme `can_decide` ve `WriteGate` ile açılır;
   - 403 kodları (`approval_requires_user_session`, rol yetersiz) ve 409 (`run_not_waiting`, zaten karar verilmiş) kodlu mesaj.
6. **Ortak:**
   - dört ekran menüde `ready: true`;
   - EN kaynak + TR çeviri;
   - iki tema, axe AA;
   - read modu: alanlar ve düğmeler pasif, API 403 → "Salt-okunur erişim";
   - rol dışı URL → "yetkiniz yok";
   - tipler `openapi-typescript` ile 05a, 06a, 07'den üretilir, kopya yok; `check:api` listesine eklenir.

**Kapsam dışı (uç yok ya da başka paketin; 10bp1 D3 deseni, ekran ve yer tutucu yok):**
- Sihirbaz 5b Hafıza (14), 5c Kanallar (15), test panelinde "Sınava ekle" ve yayın sekmesinde "son sınav sonucu" (09).
- MCP Sunucuları ekranı (05b).
- Agent şablonlarıyla önceden doldurma: D2.
- `edit/read` iki modlu ekran görüntüsü karşılaştırması 10c'de (A3). Lighthouse FOLLOWUP-37.

### 3. Değişecek dosyalar ve neden

- `frontend/app/(console)/{tools,agents,runs,approvals}/**`: dört ekran; liste ve ayrıntı sayfaları.
- `frontend/components/`: yeni bileşenler.
  - Araç ekranı: `tool-form.tsx`, `tool-actions.tsx`, `tool-invoke.tsx`.
  - Agent ekranı: `agent-form.tsx`, `agent-wizard/*` (sekme başına bir dosya), `agent-test-panel.tsx`.
  - Koşu ve onay ekranları: `run-timeline.tsx`, `run-feedback.tsx`, `approval-detail.tsx`.
  - `app-sidebar.tsx`: onay rozeti.
- `frontend/lib/api/{tools,agents,runs,approvals}-queries.ts`: TanStack sorguları; 10bp1 kalıbıyla.
- `frontend/lib/api/schema-{05a,06a,07}.d.ts`: üretilmiş tipler.
- `frontend/lib/sse.ts`: `fetch` + `ReadableStream` SSE ayrıştırıcı. `Last-Event-ID` ile yeniden bağlanır, C9 dışı adları yok sayar. Saf fonksiyon, birim testli.
- `frontend/lib/agent-definition.ts`: form ↔ C8 `definition` dönüşümü ve `{{key}}` taraması.
- `frontend/lib/navigation.ts`: `ready: true` (dört kalem).
- `frontend/lib/api/errors.ts`: yeni hata kodu → mesaj eşlemeleri.
- `frontend/messages/{en,tr}.json`: tüm metinler.
- `frontend/package.json` (`gen:api`), `frontend/scripts/check-api.mjs` (`SPECS`): üç spec.
- `frontend/tests/unit/*`, `frontend/tests/e2e/test_10bp2_*.spec.ts`, `tests/e2e/agents.ts`: fixture'lar, sahte MCP aracı ve fake-llm ile.
- `docs/onyuz.md`: ekran haritası, rol matrisi, e2e komutları.
- Backend, compose, deploy: **dokunulmaz**. Gerekirse durma koşulu 2.

### 4. Sözleşme, yapılandırma, profil etkisi

- Yalnız tüketici. C7, C8, C9 donmuş biçimde okunur, hiçbiri değişmez. C13: yalnız yeni çeviri anahtarı ve token yok.
- Profil farkı yok; ekranlar yapılandırmadan bağımsız. e2e varsayılan `llmaas` + fake-llm; airgap için ayrı ekran davranışı yok (backend testleri iki profili koşar).

### 5. Kabul kriteri → test

Brief 10 kabulleri (1, 2, 4, 5, 7-9) ve GOREV maddeleri bu pakete düşen kadarıyla. Brief kabul 3 (`edit/read` görüntü karşılaştırması) 10c'de, kabul 6 (Lighthouse) FOLLOWUP-37.

| # | Kriter | Test |
|---|---|---|
| 1 | Araç kaydı, düzenleme, silme (admin); developer listeyi ve ayrıntıyı görür, düğmeler nedenli pasif; `endpoint_url_not_allowed` / `header_name_not_allowed` kodlu mesaj | `test_10bp2_1_tool_crud_and_errors.spec.ts` |
| 2 | Keşfet → aksiyon tablosu; açık/onay anahtarı kaydedilir; "Dene" sonucu (`truncated`, `is_error`) görünür | `test_10bp2_2_discover_actions_invoke.spec.ts` |
| 3 | Agent oluştur → taslak; sihirbaz sekmeleri `definition`'ı kaydeder; tanımsız `{{x}}` → `variable_undefined` mesajı; yayınla, yeni taslak, geri al | `test_10bp2_3_agent_wizard_lifecycle.spec.ts` |
| 4 | Brief kabul 1: analyst, 13a sözleşmeleriyle KB + "Sözleşme Asistanı"nı kod yazmadan kurar, test panelinde kaynaklı cevap alır (fake-llm) | `test_10bp2_4_contract_assistant_cited.spec.ts` |
| 5 | Brief kabul 2: onay gerektiren araç çağrısı satır içi onay istemi gösterir, onay sonrası akış devam eder; ret sonrası model "reddedildi" ile devam eder | `test_10bp2_5_inline_approval.spec.ts` |
| 6 | SSE ayrıştırıcı: olay/id/çok satırlı data; bilinmeyen ad yok sayılır; kopmada `Last-Event-ID` ile devam | `lib/sse.test.ts` (Vitest) + `test_10bp2_6_stream_reconnect.spec.ts` |
| 7 | Koşular: filtreler, zaman çizelgesi, maskeli argüman olduğu gibi (ham değer DOM'da yok), iptal | `test_10bp2_7_runs_list_detail.spec.ts` |
| 8 | F9: tamamlanmış run'a oy + not; `feedback=pending` listesi; read modunda pasif | `test_10bp2_8_run_feedback.spec.ts` |
| 9 | Onaylar: liste, rozet sayısı, ayrıntı, onayla/reddet + not; `can_decide=false` düğme nedenli pasif; 409 kodlu mesaj | `test_10bp2_9_approvals_queue.spec.ts` |
| 10 | Brief kabul 4: read modunda dört ekranda alan ve düğme pasif; tarayıcıdan doğrudan mutasyon 403 → "Salt-okunur erişim" | `test_10bp2_10_read_only.spec.ts` |
| 11 | Brief kabul 5: analyst menüde Araçlar'ı görmez, URL ile "yetkiniz yok"; developer araçları görür, kaydedemez | `test_10bp2_11_roles.spec.ts` |
| 12 | Brief kabul 7-9: dört ekran açık/koyu PNG, axe AA 0 ihlal | `test_10bp2_12_screens_themes_axe.spec.ts` |
| 13 | Sorgu hataları `QueryError` ile; boş durumlar yönlendirir | `test_10bp2_13_query_failures.spec.ts` |
| 14 | Form ↔ C8 dönüşümü; bilinmeyen alan üretilmez; `{{key}}` taraması | `lib/agent-definition.test.ts` (Vitest) |
| 15 | `check:api` 05a/06a/07 tiplerinin güncel olduğunu doğrular; çeviri anahtarları iki dilde | `npm run check:api` + mevcut i18n eşlik testi |

Her kriter için önce kırmızı test, sonra kod.

### 6. Migration

Yok (önyüz).

### 7. Geri alma

`navigation.ts`'de dört kalem `ready: false`'a dönerse ekranlar "coming soon" olur. Backend ve veri etkisi yok.

### 8. Durma koşulları (koordinatöre dönerim)

1. Next.js rewrite SSE'yi tamponlarsa (token akışı parça parça gelmezse) test panelinin taşıması değişir. Ayrı rota ya da compose değişikliği gerekir; kendim seçmem.
2. Bir ekran için backend'de alan ya da uç eksikse (ör. onay kaydını run'dan bulma, Langfuse URL'si): backend'e dokunmam, FOLLOWUP isterim.
3. `openapi/07.yaml` 07 review'unda değişirse onay ekranı rebase edilir. 07 MERGED olmadan PR-HAZIR yok.
4. e2e için sahte MCP aracı ya da fake-llm'in araç çağrısı üretmesi yığında yoksa 13b ve test işçisiyle çakışmamak için sorarım.

### 9. Felsefe kontrolü

- **ARCH-07:** Dört ekran PoC kapısının (M3, 13b) doğrudan ön koşulu; analistin agent kurup test etmesi çekirdek özellik 4-5'in yüzü. Uç olmayan özellik için ekran yazılmaz (hafıza, kanal, sınav). Kalıcı karmaşıklık: tek SSE yardımcısı; ikinci istemci yolu yok.
- **ARCH-09:** Tipler `openapi-typescript`'ten; durum TanStack Query'de; SSE `fetch` akışı, yeni kütüphane yok. Run durumu, onay ve yeniden oynatma backend'in (Redis Stream, `run_events`); önyüz kendi durum makinesini kurmaz.
- **ARCH-10 / ARCH-06:** Otomatik seçim yok: sihirbaz alan varsayılanlarını backend'in C8 varsayılanlarından gösterir, gizli değer üretmez. Proje seçimi açık. Bilinmeyen olay ve hata kodu ham ve görünür; sessiz düşme yok. Yeniden bağlanma görünür gösterge taşır. Akış kesilip run sürüyorsa "yeniden bağlanılıyor" yazar, sessizce bitirmez.

## Koordinatör görüşü isteyen noktalar

- **D1, test panelindeki satır içi onay hangi uca gider?**
  - **A (önerim):** 07 karar ucu (`POST /approvals/{id}/approve|reject`). Onay kaydı, audit ve TTL tek yerde; Onaylar ekranıyla aynı yol. Bedel: panel onay kimliğini bilmeli. Main'de `approval_required` verisi yalnız `action`, `arguments`, `assign_to` taşıyor (`runtime/graph.py` L307-321). 07 dalı (4d39f7f, `graph.py` L310-325) olaya `approval_id` ve `expires_at` ekliyor. SSE verisine ulaştığını kodda gördüm ama koşuyla **doğrulamadım**. 07 liste ucunda `run_id` filtresi yok, yalnız `status` var.
  - **B:** 06a `POST /runs/{id}/resume`. Bedel: aynı karar iki uçtan; 07 kaydının bu yolla kapanıp kapanmadığı doğrulanmadı.
- **D2, şablonla önceden doldurma (brief: 13a "Sözleşme Asistanı", "Veri Soru-Cevap"):**
  - **A (önerim):** bu PR'da yok; FOLLOWUP. 13b seed'i agent'ları zaten kuruyor; önyüze 13a JSON'unu gömmek ikinci kaynak olur.
  - **B:** `data/samples/agents/*.json` derlemede önyüze kopyalanır. Bedel: örnek veri ürün koduna girer.
- **D3, araç aksiyonundaki `needs_approval` anahtarı:** GOREV "salt okunur göster" diyor. Backend aksiyon PATCH'i `admin + write` ile `enabled` ve `needs_approval` alanlarını kabul ediyor, brief "aksiyon bazlı onay gerekli ve açık anahtarları" diyor.
  - **A (önerim):** admin + edit değiştirir; diğerleri salt okunur görür.
  - **B:** herkese salt okunur; değişiklik yalnız API'den. GOREV cümlesini B diye okumak da mümkün; senin niyetin hangisi?
- **Varsayım 4:** "Langfuse'ta aç" yalnız `RunOut` iz kimliği ve önyüzde yapılandırılmış Langfuse adresi varsa. İkisi de yoksa bağlantı yok ve FOLLOWUP; uydurma URL yok.
