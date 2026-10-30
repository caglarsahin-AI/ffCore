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

## Plan onayı ve kararlar (K-10bp2-0002..0004)

- PLANNED onaylı. D1 **A**: satır içi karar 07 `approve|reject` ucuna gider; önyüz 06a `/resume`'u yalnız `ask_user` cevabı için çağırır. D2 **A**: şablonla doldurma yok, FOLLOWUP (13b seed). D3 **A**: `needs_approval` ve `enabled` alanlarını admin + edit değiştirir, diğer roller salt okunur görür.
- FOLLOWUP-100 (K-10bp2-0003, karar A): 05a araç okumayı `analyst`'a açar (isci-b, 07 sonrası). O gelene kadar analist sihirbazda seçilmiş aksiyonları ve nedenini salt okunur görür. Analist-araç e2e'si NOT_RUN: FOLLOWUP-100.
- Kabul 2 (satır içi onay) ve onay kararları (K-10bp2-0004, karar A): fake-llm'e `tool-*` modunu test işçisi ekler (`fix/fake-llm-tool-mode`). O merge olana kadar `test_10bp2_5` ve `test_10bp2_9` karar testi `fixme`, yani NOT_RUN. Merge sonrası ticket-desk `send_reply` ile yazılır.

## Uygulama (HEAD cc52c77; baz fcbcfc4)

| Commit | Dilim |
|---|---|
| ff1586e | 05a/06a tipleri + `check:api`; `lib/sse.ts`; `lib/agent-definition.ts` |
| 012e901 | Araçlar ekranları; 05a/06a/07 hata kodları |
| 9be9d01 | Agent listesi ve sihirbaz |
| f7d3df5 | Test paneli, Koşular, F9 |
| 1fb0d20 | Onaylar ve kenar çubuğu rozeti |
| 47cd313 | e2e spec'leri; `support.ts` "coming-soon" örneği `/agents` → `/evaluations` (`/agents` artık gerçek ekran) |
| cc52c77 | docs/onyuz.md |

### Değişen dosyalar (57; backend, compose, deploy dokunulmadı)

- **Ekranlar:** `frontend/app/(console)/{tools,agents,runs,approvals}/**` (8 sayfa).
- **Bileşenler:**
  - Araçlar: `tool-form.tsx`, `tool-actions.tsx`.
  - Agent: `agent-create-form.tsx`, `agent-wizard/*` (8 dosya), `agent-test-panel.tsx`.
  - Koşular: `run-timeline.tsx`, `run-feedback.tsx`.
  - Kenar çubuğu: `app-sidebar.tsx` (onay rozeti).
- **Kitaplık:**
  - Saf yardımcılar: `lib/sse.ts`, `lib/run-view.ts`, `lib/agent-definition.ts`.
  - Sorgular: `lib/api/{tools,agents,runs,approvals}-queries.ts`.
  - Diğer: `lib/api/errors.ts` (35 kod), `lib/navigation.ts` (4 kalem `ready: true`).
- **Tipler:** `lib/api/schema-{05a,06a}.d.ts` (üretilmiş); `package.json` `gen:api`, `scripts/check-api.mjs` `SPECS`.
- **Metin:** `messages/{en,tr}.json`: Tools, Agents (+wizard), TestPanel, Runs, Approvals, Errors ekleri.
- **Testler:** `tests/unit/test_10bp2_{6,14,16,17,18,19}_*` (Vitest), `tests/e2e/test_10bp2_{1..5,7..13}_*`, `tests/e2e/agents.ts`, `tests/e2e/support.ts` (tek satır).
- **Belge:** `docs/onyuz.md`.

### Kabul kriteri → test (durum 2026-10-30, yığın açılmadan)

| # | Test | Durum |
|---|---|---|
| 1 | `test_10bp2_1_tool_crud_and_errors` | yazıldı, NOT_RUN (yığın sırası) |
| 2 | `test_10bp2_2_discover_actions_invoke` | yazıldı, NOT_RUN (yığın sırası) |
| 3 | `test_10bp2_3_agent_wizard_lifecycle` | yazıldı, NOT_RUN (yığın sırası) |
| 4 | `test_10bp2_4_contract_assistant_cited` | yazıldı, NOT_RUN (yığın sırası; aşama 2, `FAKE_EMBED=1`) |
| 5 | `test_10bp2_5_inline_approval` | `fixme`, NOT_RUN: fix/fake-llm-tool-mode |
| 6 | `test_10bp2_6_sse` (Vitest, 8) | **geçti**. e2e kopma testi yok: Playwright akışı yarıda kesemiyor; birim testi kopma ve yeniden bağlanmayı sahte gövdeyle kanıtlıyor (plandan sapma) |
| 7 | `test_10bp2_7_runs_list_detail` | yazıldı, NOT_RUN (yığın sırası) |
| 8 | `test_10bp2_8_run_feedback` | yazıldı, NOT_RUN (yığın sırası) |
| 9 | `test_10bp2_9_approvals_queue` | boş kuyruk testi yazıldı, NOT_RUN (07 merge + yığın); karar testi `fixme` (fake-llm) |
| 10 | `test_10bp2_10_read_only` | yazıldı, NOT_RUN (yığın sırası) |
| 11 | `test_10bp2_11_roles` | yazıldı, NOT_RUN (yığın sırası). Developer görünümü NOT_RUN: fixture'da developer yok (A3) |
| 12 | `test_10bp2_12_screens_themes_axe` (7 ekran × 2 tema) | yazıldı, NOT_RUN (yığın sırası). Onay ayrıntısı görüntüsü fake-llm sonrası |
| 13 | `test_10bp2_13_query_failures` | yazıldı, NOT_RUN (yığın sırası) |
| 14 | `test_10bp2_14_agent_definition` (8), `test_10bp2_17_agent_versions` (2) | **geçti** |
| 15 | `check:api` + `test_10bp2_16_error_codes`, `test_10bp2_18_run_view` (7), `test_10bp2_19_run_contract` (2), i18n eşlik testleri | **geçti** |

Sıra: birim testleri önce kırmızı (modül yok ya da eşleme yok), sonra yeşil. Ekran bileşenlerinde ve e2e spec'lerinde sıra tersine döndü: ekranlar önce yazıldı, çünkü e2e yığın sırası bekliyor. Bu sapma açıkça yazılı.

### Çalıştırılan komutlar (ağsız `node:20.19.5-alpine` + `ffcore-10a-nm`, `--network none`)

| Komut | Exit | Sonuç |
|---|---|---|
| `npm run check:api` | 0 | 03a/04a/05a/06a güncel (önce kırmızı: 05a/06a tipleri eksik) |
| `npx vitest run` | 0 | 142/142 |
| `npx tsc --noEmit -p .` | 0 | |
| `npx eslint .` | 0 | |
| `next build` (`FFCORE_BACKEND_URL=http://backend:8000`) | 0 | 23 rota, yeni 8 rota dahil |
| `npx playwright test --list` | 0 | 27 test_10bp2 girdisi |
| e2e (iki aşama) | NOT_RUN | yığın sırası (isci-b → test → isci-c, K-10bp2-0004) |

### Varsayımlar

1. **07 tipleri:** `lib/api/approvals-queries.ts` 07 dalının `api/approvals_schemas.py` dosyasını alan alan yansıtıyor ve elle yazılmış. Bu, "elle tip yazılmaz" kuralından bilinçli ve geçici bir sapma (K-10bp2-0002 "şimdilik approvals_schemas.py kabul"). `backend/openapi/07.yaml` gelince `schema-07.d.ts` üretilecek, `SPECS`'e eklenecek ve elle yazılan tip silinecek. PR-HAZIR bundan önce yok.
2. **`approval_id`:** 07 dalında `approval_required` olayına `approval_id` ekleniyor (`graph.py` L310-325). SSE verisine ulaştığı **doğrulanmadı**; doğrulama 07 merge sonrası koşuda yapılacak. Olay kimlik taşımazsa panel kararı vermez; "Onaylar'ı aç" bağlantısıyla açık hata gösterir.
3. **Langfuse bağlantısı:** önyüzde Langfuse adresi yapılandırması yok, bu yüzden iz kimliği metin olarak gösteriliyor, bağlantı yok (plan varsayım 4). Bağlantı gerekiyorsa FOLLOWUP.
4. **Test paneli kaydedilmiş sürümü çalıştırır:** kaydedilmemiş değişiklik varsa panel bunu yazar. Taslağı önce kaydetmeyen gizli bir otomatik kayıt yok (ARCH-10).
5. **e2e yığını:** `ALLOWED_INTERNAL_HOSTS` listesine `ticket-desk` eklenmeli ve `--profile test` ile `fake-llm` ile `ticket-desk` ayakta olmalı. Kesin komutlar yığın koşusundan sonra docs/onyuz.md "Acceptance tests" bölümüne yazılacak.

### Kalan riskler

- Next.js rewrite'ın SSE'yi tamponlayıp tamponlamadığı yığında henüz görülmedi (durma koşulu 1). Tamponlarsa önerilen yol K-10bp2-0002'deki seçenek: doğrudan backend portu.
- 07 incelemesinde onay sözleşmesi değişirse onay ekranı rebase edilir.
- e2e'lerin hiçbiri henüz koşmadı. Spec'ler tip ve lint temiz, ama gerçek yığında düzeltme gerekebilir.

## Son durum: PR-HAZIR (2026-10-30)

**HEAD:** `2459133138523b039e687ac3be535aebca175613` · **Baz:** main `d4aebfc` (07 dahil; rebase çakışmasız) · 10 commit, 102 dosya. Dosyaların 41'i `docs/images/*.png`; bunların 16'sı yeni 10bp2 görüntüsü, 25'i eski görüntülerin yeniden üretimi (kenar çubuğunda bu paketin 4 ekranı açıldı). Push yok. Sınıf **[A]**. Backend, compose ve deploy dokunulmadı.

Bu bölüm yukarıdaki "Uygulama (HEAD cc52c77)" durum tablosunun yerine geçer.

### Kararlar (K-10bp2-0002..0006)

- D1, D2, D3 **A**.
- FOLLOWUP-100 (analist araç okuması, isci-b).
- `fix/fake-llm-tool-mode` main'de; kabul 2 artık koşuyor.
- FOLLOWUP-105 (06a tanım kodu 422'de kayboluyor, isci-a): `test_10bp2_3` bilerek kırmızı.
- K-INIT-0020: her yığın kendi portunu verir.

### Kabul kriteri → test (HEAD c836320'de tam koşu; 2459133 yalnız docs/görüntü ekler)

| # | Test | Durum |
|---|---|---|
| 1 | `test_10bp2_1_tool_crud_and_errors` | geçti |
| 2 | `test_10bp2_2_discover_actions_invoke` | geçti |
| 3 | `test_10bp2_3_agent_wizard_lifecycle` | **açık kırmızı, ürün bulgusu FOLLOWUP-105**: kaydetme `variable_undefined` yerine `validation_error` dönüyor. Kod kontrolü `expect.soft`; oluşturma, eksik model, yer tutucu ipucu, kaydet, yayınla, salt okunur yayın, yeni taslak, geri alma adımları aynı koşuda geçti (tek hata o kontrol) |
| 4 | `test_10bp2_4_contract_assistant_cited` (brief kabul 1) | geçti: analist, 13a PDF'i, test paneli, kaynak kartı |
| 5 | `test_10bp2_5_inline_approval` (brief kabul 2) | geçti: onayla, ticket-desk `send_reply` 1 kayıt; reddet, koşu biter, kayıt artmaz. `approval_required` olayının `approval_id` taşıdığı bununla **doğrulandı** |
| 6 | `test_10bp2_6_sse` (Vitest 8) | geçti. e2e kopma testi yok (plandan sapma, yukarıda) |
| 7 | `test_10bp2_7_runs_list_detail` | geçti |
| 8 | `test_10bp2_8_run_feedback` (F9) | geçti |
| 9 | `test_10bp2_9_approvals_queue` (2 test) | geçti: boş kuyruk; liste, rozet, read `can_decide` false, onay, ikinci karar 409 `approval_not_pending` |
| 10 | `test_10bp2_10_read_only` (brief kabul 4) | geçti |
| 11 | `test_10bp2_11_roles` (2 test, brief kabul 5) | geçti. Developer görünümü NOT_RUN: fixture'da developer yok (A3). Analist araç seçimi NOT_RUN: FOLLOWUP-100 |
| 12 | `test_10bp2_12_screens_themes_axe` (8 ekran × 2 tema) | geçti, axe 0 ihlal. Görüntüler `docs/images/10bp2-*` (16) |
| 13 | `test_10bp2_13_query_failures` | geçti |
| 14 | `test_10bp2_14`, `test_10bp2_17` (Vitest) | geçti |
| 15 | `check:api` (03a/04a/05a/06a/07) + `test_10bp2_16/18/19` + i18n | geçti |
| — | Brief kabul 3 (iki modlu ekran görüntüsü karşılaştırması) | kapsam dışı, 10c (A3). Lighthouse FOLLOWUP-37 |

### Çalıştırılan komutlar

Tam çıktılar oturum scratchpad'inde tee ile alındı, depoya girmedi.

| Komut | Ortam | Exit | Sonuç |
|---|---|---|---|
| `npm run check:api`, `eslint .`, `tsc --noEmit`, `vitest run` | `node:20.19.5-alpine`, `--network none`, c836320 | 0 / 0 / 0 / 0 | 142/142 |
| `next build` | aynı, 1fb0d20 | 0 | 23 rota |
| `compose -p 10bp2 --profile test build` + `up -d --wait` | `FFCORE_VERSION=0.0.0-10bp2` | 0 / 0 | 18 servis healthy |
| `tools make seed-prompts`, `create-superadmin` | | 0 / 0 | `platform_rules` oluştu |
| e2e aşama 1 `--grep @model-missing` | `FAKE_EMBED=0` | 1, sonra 0 | 1. koşu `test_10bp1_10` `page.goto` 30 s zaman aşımı (kenar çubuğu logosu `_next/image` cevapsız; nedeni **doğrulanmadı**, iki yığın aynı anda açıktı); tekrar koşu 1/1, 4,4 s |
| e2e aşama 2, ilk tam koşu | `FAKE_EMBED=1`, 1eb9fe4 | 1 | 126 geçti / 11 düştü (hepsi test_10bp2; nedenler aşağıda) |
| e2e aşama 2, son tam koşu | `FAKE_EMBED=1`, c836320 | 1 | **136 geçti / 1 düştü** (`test_10bp2_3`, FOLLOWUP-105) |
| `compose ... down -v` | | 0 | konteyner 0, volume 0 |

İlk tam koşuda düşen 11 testin nedenleri, hepsi c836320'de düzeltildi:

1. Testlerin sağlayıcısı fake-llm'i 11434'te arıyordu, fake-llm sohbeti 9999'da veriyor. 9 run `model_unavailable` ile düştü. Bu 4, 5, 7, 8, 9, 10 ve 12'deki onay ayrıntısını düşürdü.
2. Aksiyon anahtarı sunucu durumunu izliyor; `check()` beklemiyordu, test tıklayıp bekliyor.
3. Filtresiz `/runs` istek kalıbı tutmuyordu.
4. Sözleşme sorusu İngilizceydi; FAKE_EMBED'in sahte reranker'ı kelime örtüşmesi sayıyor, `no_sources` oldu.
5. Onay satırı seçicisi fazla genişti.
6. **Ürün düzeltmesi:** kaydırılabilir `<pre>` blokları klavyeyle odaklanamıyordu (axe `scrollable-region-focusable`); altısına `tabIndex={0}` eklendi.

### Varsayımlar (yukarıdakileri günceller)

1. 07 tipleri artık `openapi/07.yaml`'dan üretiliyor. Elle yazılmış tip kalmadı.
2. `approval_id` SSE verisinde var; `test_10bp2_5` ile doğrulandı.
3. Langfuse iz kimliği metin olarak gösteriliyor, bağlantı yok (önyüzde Langfuse adresi yapılandırması yok).
4. e2e.env örtüsü main'de yok (18e2e dalında). Belgelenen `export` deseni kullanıldı. `ALLOWED_INTERNAL_HOSTS` = `.env.test` listesi + `fake-llm`. `fake-llm`'i backend doğrudan yalnız sağlayıcı bağlantı testlerinde (10af) çağırıyor; agent koşuları LiteLLM üzerinden gidiyor.
5. Yığın 8000/3000 ile açıldı, port kuralı (K-INIT-0020) koşu başladıktan sonra geldi. docs/onyuz.md komutları yeni kurala göre `BACKEND_PORT=18010 FRONTEND_PORT=13010` diyor; port dışında koşulanla aynı.
6. Eski paketlerin 25 görüntüsü yeniden üretildi: kenar çubuğu bu paketle değişti. İçerik değişikliği istenmedi, yalnız menü.

### Kalan riskler

- FOLLOWUP-105 kapanana kadar sihirbaz tanım hatalarını kodla gösteremiyor. Tanımsız yer tutucu için istemci ipucu var, diğer tanım kodları için yok.
- Next rewrite üzerinden SSE akışı uçtan uca çalışıyor (4 ve 5 geçti, onay sonrası `stream_after` ile devam). Olayların tamponlanmadan parça parça gelip gelmediği **ölçülmedi**: fake-llm cevabı kısa olduğu için tamponlama bu testlerde görünmez. Gerçek modelle uzun akışta kontrol edilmeli (13b ya da sunucu).
- Aşama 1'in ilk koşusundaki zaman aşımının nedeni doğrulanmadı; tek seferlik, tekrar etmedi.

### Takip notları (K-10bp2-0008)

**FOLLOWUP-105 gelince (06a tanım hataları kendi koduyla 422):**

1. Önyüzde kod değişikliği gerekmez. `agent-wizard.tsx` `onSave` hatayı `errorMessageKey(error.code)` ile eşliyor. Mesaj ve kod `wizard-save-error` satırında görünür: "…placeholder… (code: variable_undefined)". `lib/api/errors.ts`'te 11 tanım kodunun eşlemesi ve iki dilde mesajı hazır: `variable_undefined`, `variable_unknown`, `variable_duplicate`, `knowledge_duplicate`, `tool_duplicate`, `approval_action_unknown`, `structured_output_invalid`, `output_reserve_too_small`, `verify_not_supported`, `confidence_formula_not_supported`, `knowledge_filter_not_supported`. Bunlar `test_10bp2_16` ile kanıtlı.
2. `test_10bp2_3` değişmeden yeşillenir. `expect.soft(...).toContainText("variable_undefined")` geçer; testte başka hata yok.
3. Yeşillendikten sonra `expect.soft` tekrar `expect`'e çevrilir (tek satır) ve FOLLOWUP-105 yorumu silinir. Bu, FOLLOWUP-105 PR'ının ya da ayrı küçük önyüz PR'ının işi.
4. Yeni bir 06a kodu gelirse (ör. `prompt_source`): `errors.ts` + `messages/{en,tr}.json` + `test_10bp2_16` listesi. Eşlenmemiş kod genel mesajla ve ham koduyla görünür, sessiz değil.
5. İsteğe bağlı: 06a kodla birlikte alan yolu da dönerse (ör. `definition.system_prompt`), sihirbaz hatayı ilgili sekmeye bağlayabilir. Bu PR'da yok, ihtiyaç görülürse FOLLOWUP.

**FOLLOWUP-100 gelince (araç/aksiyon okuma `analyst`'a açılır):**

1. `components/agent-wizard/tools-tab.tsx` `canList = hasRole(role, "developer")` satırı `analyst` olur. Ya da daha iyisi, satır kaldırılır ve liste her role sorgulanır; 403 gelirse açık hata görünür. Böylece analist araç ve aksiyon seçer ve onay listesini düzenler. Salt okunur dal (`tools-need-developer` açıklaması) ve `toolsNeedDeveloper` mesajı silinir.
2. `lib/navigation.ts` Araçlar menüsü `minRole: "developer"` kalır. Araç kaydı ve değiştirme admin işidir, menü erişimi ayrı bir karar. Analist araç ayrıntısını da görecekse `analyst` olur. Bu karar koordinatörde; önerim menünün `developer` kalması, analistin araçları yalnız sihirbazda görmesi.
3. Testler: `test_10bp2_11_roles` analist için `nav-tools` beklentisi menü kararına göre kalır ya da değişir. Yeni e2e: analist sihirbazda ticket-desk `list_tickets`'i seçer, `send_reply`'ı onaylı işaretler, kaydeder; tanımda `tools` ve `approval.actions` doğru yazılır. Şu an NOT_RUN: FOLLOWUP-100.
4. Docs: docs/onyuz.md "Analysts and tools" maddesi silinir; rol matrisinde Tools satırı karar neyse ona göre güncellenir.
- **Menü kararı (K-10bp2-0009):** Araçlar menüsü developer ve admin'de kalır (`navigation.ts` değişmez, `test_10bp2_11` analist için `nav-tools` 0 beklemeye devam eder). FOLLOWUP-100 sonrası analist araçları yalnız sihirbazda görür. Araç kaydını ve aksiyon anahtarlarını değiştiremez, ama kendi agent'ı için aksiyon seçer ve onay listesini düzenler; FOLLOWUP-100'ün amacı bu.
