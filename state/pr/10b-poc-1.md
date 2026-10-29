# PR: 10b-poc-1 bilgi tabanı ve sistem durumu ekranları

**Paket:** 10b-poc-1 · **Sınıf:** [A] (compose `&app-env`'e tek satır `FAKE_EMBED: ${FAKE_EMBED:-0}`, paylaşılan değişiklik, K-10bp-0002 D2) · **Branch:** feat/10b-poc-1 · **Baz commit:** fe0d434 · **HEAD:** db5c8fa38b53350f051094bc7efc106508f0d9f1 (7 commit, 53 dosya) · **Oturum:** ffcore-isci-c-10bp1 · **GOREV:** K-10bp-0001 (+ taslak K-10bp-0000, kararlar K-10bp-0002)

## Plan (kodlamadan önce)

### 1. Bulunan semboller ve dosyalar (gerçek kod, fe0d434)

- **04a sözleşmesi** `backend/openapi/04a.yaml` (14 uç):
  - KB: `GET/POST /api/v1/projects/{p}/knowledge-bases`, `GET/PATCH/DELETE .../{kb_id}`.
  - Belge: `GET/POST .../{kb_id}/documents` (multipart: `files[]`, `acl_roles[]`, `acl_users[]`, `acl_open`), `GET/DELETE .../documents/{id}`.
  - `POST .../reindex` (`layer: silver|gold`, `full`), `POST .../search`, `POST .../test-query` (playground, `source=playground` kaydı).
  - `GET /readyz` (kimliksiz; 200/503 aynı gövde).
- **Rol (backend `api/knowledge.py`):**
  - okuma `require_role("analyst")`;
  - yükleme, belge silme, reindex `analyst + write`;
  - KB oluştur/düzenle/sil `admin + write`.
- **Şemalar:**
  - `DocumentOut`: `status` 9 değer, `gate0/1/2 {status: ok|flagged|skipped, reason}`, `duplicate_of`, `convert_engine`, `convert_seconds`, `chunk_count`, `acl_roles/users`, `version`.
  - `UploadOutcome`: `created|new_version|unchanged`.
  - `SearchResponse`: `hits[]` (`embed_score`, `rerank_score`, `chunk_status`, `breadcrumb`, `page`), `threshold_mode` (`rerank_floor|min_score`), `filtered_by_rerank_floor`, `filtered_by_min_score`, `latency_ms`.
  - `ReadyzOut`: `status` (`ready|warming|not_ready`), `checks[]` (`name`, `status`, `code`, `detail`).
  - Kontroller: `warmup` (`warming`, `warmup_failed`, `model_missing`), `models`, `embed_dim` (`embed_dim_mismatch`), `ollama_context` (`context_configuration_invalid`), `vector_store`.
- **Yükleme sınırı:** `api/upload_limit.py` 413 `request_too_large` (`UPLOAD_MAX_REQUEST_BYTES`). Boyut ve tür retleri istek hatası değil, belge satırında Kapı 0 gerekçesidir (`knowledge/scope.py`: `too_large`, `binary`, `out_of_scope`, `video_disabled`, `libreoffice_unavailable` …). Ek hata kodları: `acl_conflict` (422), `knowledge_base_key_taken` (409), vektör deposu 503 kodları.
- **Önyüz (main):**
  - `lib/navigation.ts`: `knowledgeBases` `/knowledge-bases` analyst, `systemStatus` `/system-status` admin; ikisi `ready: false` (`[section]/page.tsx` "coming soon").
  - `lib/api/client.ts` `api()` yalnız JSON; `lib/api/queries.ts` (TanStack).
  - `components/screen.tsx` (`Screen`, `EmptyState`, `QueryError`, `ListState`), `components/write-gate.tsx` (`WriteGate projectId`), `components/form-parts.tsx`.
  - `lib/api/errors.ts`; `next.config.ts` rewrite yalnız `/api/v1/:path*`.
  - `package.json` `gen:api` ve `scripts/check-api.mjs` yalnız 03a.
- **Ortam:**
  - compose `&app-env`'de `FAKE_EMBED` **yok** (`core/config.py` `fake_embed=False`); `HF_HUB_OFFLINE` varsayılanı 1.
  - Ağırlıksız stack'te `/readyz` `model_missing` verir, KB araması ve indeksleme çalışmaz.
  - 13a örnekleri `data/samples/contracts/` (2 PDF, 3 DOCX).

### 2. Kapsam ve kapsam dışı

**Kapsam (04a'nın sunduğu kadarıyla):**
- **KB listesi:** ad, anahtar, durum (`active`/`reindexing`), belge ve parça sayısı; boş durum yönlendirir.
- **KB oluştur ve düzenle (admin):**
  - alanlar: anahtar (desen), ad, açıklama, `chunk_size`, `chunk_overlap`, `hybrid`, `rerank`, `default_top_k`, `default_min_score`;
  - tek eşik kuralı ekranda yazılı: rerank açıkken `min_score` pasif ve açıklamalı;
  - silme onaylı.
- **KB ayrıntısı, Belgeler sekmesi:**
  - Yükleme: sürükle-bırak + dosya seç, istek başına ilerleme çubuğu (XHR `upload.onprogress`). ACL seçimi: roller / "tüm proje üyelerine açık" (`acl_open`, çakışma istemcide engellenir; sunucu `acl_conflict` mesajı da eşlenir). Her dosyanın `outcome`'u (yeni / yeni sürüm / değişmedi) görünür.
  - Liste: dosya, durum, katman (raw → silver → gold, durumdan türetilir: `converting` raw, `gated`/`chunking` silver, `indexed` gold), Kapı 0/1/2 durumu ve gerekçesi (kod → mesaj; bilinmeyen kod ham gösterilir, sessiz değil), `duplicate_of` bağlantısı, dönüştürücü ve süre, parça sayısı, sürüm, ACL.
  - İşlenen belge varken liste 2 s'de bir yenilenir, hepsi terminal olunca durur (`indexed|skipped|failed|timeout`); yenileme göstergesi görünür.
  - Belge sil (onaylı).
- **"Katmanı yeniden üret":** silver/gold seçimi + "tümü" (`full`) seçeneği; 202 sonrası KB durumu `reindexing`. Brief'teki "yeniden dönüştür (preset)" düğmesi 04a'da preset parametresi olmadığı için yok (aşağıda FOLLOWUP).
- **"Aramayı dene" sekmesi** (`test-query`):
  - sorgu, `top_k`, `hybrid`;
  - sonuç kartları: belge, sayfa, breadcrumb, metin, `embed_score`, `rerank_score`, `chunk_status=flagged` işareti;
  - eşik modu ve eşik altında elenen sayısı ("rerank tabanı altında N parça elendi"), gecikme.
- **Sistem durumu (admin):**
  - `/readyz` genel durumu ve kontrol tablosu (ad, durum, kod → açık mesaj, ayrıntı);
  - `warming` iken 5 s'de bir yenilenir;
  - `model_missing` için açık mesaj ve çözüm satırı ("ağırlıkları `make models` getirir, yalnız kullanıcı koşturur");
  - FAKE_EMBED açıksa `models` ayrıntısı olduğu gibi görünür.
- Menü: iki ekran `ready: true`. EN kaynak + TR çeviri, iki tema, axe AA, read modu.

**Kapsam dışı (04a'da uç yok; GOREV: "olmayan uç için UI yazılmaz") → FOLLOWUP talepleri (aşağıda D3):**
- (a) belge ACL'ini **sonradan düzenleme** (PATCH belge ucu yok; ACL yalnız yüklemede);
- (b) **Ingest Raporu** sekmesi (kaynak × kapı × gerekçe sayımı, parça düzeyinde elenenler; uç yok);
- (c) rerank tabanı altında elenen **parçaların listesi** (yalnız sayı dönüyor) ve `rerank_truncated` işareti (şemada yok);
- (d) "yeniden dönüştür" preset seçimi;
- (e) sistem durumunda yüklü modeller/bağlam uzunluğu ayrı alanları, bellek vs `mem_limit`, kuyruk uzunlukları, mesai dışı penceresi, sağlayıcı 429 oranı (`/readyz` taşımıyor; `models`/`ollama_context` ayrıntı metni gösterilir);
- (f) `acl_users` seçimi (kullanıcı listesi `require_superadmin`, FOLLOWUP-67 ile aynı sorun; yüklemede yalnız roller + açık).

### 3. Değişecek dosyalar ve neden

- `frontend/app/(console)/knowledge-bases/page.tsx`, `knowledge-bases/[kbId]/page.tsx`: ekranlar (nav href'i `/knowledge-bases`; WORK_QUEUE'daki `{knowledge,status}` yazımı bu yollara karşılık gelir, varsayım A1).
- `frontend/app/(console)/system-status/page.tsx`.
- `frontend/components/`: `kb-form.tsx`, `document-upload.tsx`, `document-table.tsx`, `search-panel.tsx`, `readiness-table.tsx` (form-parts kullanır).
- `frontend/lib/api/`:
  - `client.ts`: additive `upload()` (XHR, ilerleme, aynı ApiError/401 yolu);
  - `queries.ts`: KB ve belge kancaları, proje kimliğiyle key'li;
  - `errors.ts`: yeni kodlar;
  - `schema-04a.d.ts`: üretilmiş.
- `frontend/lib/knowledge.ts`: durum → katman, terminal küme, gerekçe kodu → mesaj anahtarı (saf işlevler, birim testli).
- `frontend/lib/navigation.ts`: iki öğe `ready: true`.
- `frontend/mocks/openapi-04a.yaml` (sözleşme kopyası), `frontend/package.json` (`gen:api` iki spec; bağımlılık eklenmez), `frontend/scripts/check-api.mjs` (iki spec).
- `frontend/next.config.ts`: `/readyz` rewrite (D1).
- `frontend/messages/{en,tr}.json`: `KnowledgeBases`, `Documents`, `Search`, `SystemStatus`, `Errors` ekleri.
- `frontend/tests/unit/test_10bp1_*`, `frontend/tests/e2e/test_10bp1_*`, `frontend/tests/e2e/global-setup.ts` (KB testi için analyst kullanıcı zaten var mı bakılır; yoksa additive).
- `docs/onyuz.md`: ekran haritası, rol matrisi, e2e komutları (iki aşama, D2), ekran görüntüleri `docs/images/10bp1-*.png`.
- (D2 A ise) `deploy/docker-compose.yml` `&app-env`: `FAKE_EMBED: ${FAKE_EMBED:-0}` tek satır (paylaşılan değişiklik).

Dokunulmayan: `backend/**`.

### 4. Sözleşme, yapılandırma, profil etkisi

- Sözleşme değişmez. Tipler 04a OpenAPI'sinden üretilir. C13 yalnız additive (yeni mesaj anahtarları, token yok).
- Önyüz profil bağımsız. `/readyz` `ollama_context` profile göre `skipped` olabilir; ekran bunu "atlandı" diye gösterir.
- `FAKE_EMBED` varsayılanı 0 kalır (D2); açıkken `/readyz` `models` ayrıntısında açıkça görünür.

### 5. Kabul kriteri → test

Brief 10 ve GOREV'den numaralandı. Testler önce yazılır ve kırmızı görülür.

| # | Kriter | Test |
|---|---|---|
| 1 | KB listesi, boş durum, oluşturma (anahtar deseni, `knowledge_base_key_taken` mesajı), düzenleme, tek eşik kuralı ekranda | e2e `test_10bp1_1_kb_create_edit` |
| 2 | 13a DOCX yükleme: ilerleme, `outcome`, durum `indexed`'e kadar canlı; katman, kapılar, dönüştürücü/süre, parça sayısı satırda | e2e `test_10bp1_2_upload_indexed` |
| 3 | Aynı dosyayı tekrar yükleme `unchanged`; `duplicate_of` olan satırda bağlantı | e2e `test_10bp1_3_reupload_duplicate` |
| 4 | Kapı 0 reddi (ikili ya da kapsam dışı dosya) `skipped` + gerekçe mesajı; 413 `request_too_large` açık mesaj | e2e `test_10bp1_4_gate_reject` + birim `test_10bp1_13_upload_client` |
| 5 | Aramayı dene: kartlarda embedding/rerank skoru, eşik modu, "taban altında N elendi", gecikme | e2e `test_10bp1_5_search_panel` |
| 6 | ACL: yalnız `admin` rolüne yüklenen belge analyst'e listede görünmez (404); `acl_open` ile rol çakışması istemcide engelli | e2e `test_10bp1_6_acl_upload` |
| 7 | Belge silme ve "katmanı yeniden üret" (silver/gold): 202, KB `reindexing` görünür | e2e `test_10bp1_7_delete_reindex` |
| 8 | admin+read: aynı listeler; tüm mutasyon düğmeleri pasif + açıklama; edit/read ekran görüntüsü karşılaştırması (fark yalnız düğmeler ve rozet) | e2e `test_10bp1_8_read_only` |
| 9 | analyst: KB oluştur/düzenle/sil nedenli pasif (admin); yükleme açık; sistem durumu menüde yok, URL ile "yetkiniz yok" | e2e `test_10bp1_9_roles` |
| 10 | Sistem durumu: ağırlıksız stack'te `model_missing` açık mesaj + çözüm; FAKE_EMBED stack'inde `ready` | e2e `test_10bp1_10_readiness` (iki aşama, D2) |
| 11 | Dört ekran iki temada PNG + axe AA 0 ihlal | e2e `test_10bp1_11_screens_themes_axe` |
| 12 | Sorgu hatası `QueryError` (boş liste gibi görünmez); 401 → login | e2e `test_10bp1_12_query_failures` |
| 13 | `upload()`: ilerleme olayları, 413/422/401 eşlemesi, çok dosya | birim `test_10bp1_13_upload_client` |
| 14 | Durum → katman ve terminal küme sözleşme enum'uyla birebir; bilinmeyen gerekçe kodu ham gösterilir | birim `test_10bp1_14_knowledge_status` |
| 15 | Tüm readiness ve kapı gerekçe kodlarının EN/TR mesajı var; ICU ayrıştırma | birim `test_10bp1_15_messages` (+ mevcut `test_10af_18`, `test_10a_8`) |
| 16 | Yenileme yalnız terminal olmayan belge varken çalışır, sonra durur | birim `test_10bp1_16_polling` |
| 17 | Sabit renk ve sabit metin yok | mevcut `test_10a_3`, `test_10ab_12` |
| 18 | `check:api` iki spec için temiz | `npm run check:api` |

### 6. Migration
Yok.

### 7. Geri alma
Önyüz commit'leri geri alınır; `navigation.ts`'te `ready: false` yeterli. D2 satırı varsayılan 0 olduğu için etkisizdir.

### 8. Durma koşulları
- 04a şeması main'de değişirse `gen:api` ile yeniden üretilir; uç kalkarsa koordinatöre yazılır.
- DOCX dönüşümü ağırlıksız (`HF_HUB_OFFLINE=1`) worker'da çalışmazsa (Docling DOCX yolu kural tabanlı sanılıyor, **doğrulanmadı**) e2e 2-7 için fixture kararı istenir (13a'da `.md`/`.txt` yok).
- `backend/**` değişikliği gerekirse durulur.

### 9. Felsefe kontrolü
- **ARCH-07:** Değer çekirdek özellik 4'e (bilgi tabanı) ve PoC kapısına (M2 tanımı "önyüzden belge yükleme, arama sonucu görme"). Uçsuz özellikler (rapor, ACL düzenleme, elenen liste) yazılmaz, istemcide türetilmez.
- **ARCH-09:** Sunucu durumu TanStack Query; ilerleme tarayıcı XHR. Yeni kütüphane yok, ayrı durum makinesi yok.
- **ARCH-10/06:**
  - yenileme açık ve görünür (gösterge); bilinmeyen kod ham gösterilir;
  - tek eşik kuralı ekranda yazılı;
  - FAKE_EMBED açıkken `/readyz` bunu söyler; sessiz varsayılan yok;
  - `acl_open` açık seçim (varsayılan sunucunun `analyst` rolü, ekranda yazılı).

### Koordinatör kararları (K-10bp-0002, 12:46)

- **D1 B:** `/readyz` rewrite yok. Gerekçe: ayrıntı model adı ve dosya yolu taşıyor. Sistem durumu, girişli konsol düzeninde bir sunucu bileşeni; `/readyz`'i backend iç adresinden (`backendUrl()`) okur. `warming` durumundayken istemci birkaç saniyede bir `router.refresh()` yapar.
- **D2 A:** compose `&app-env`'e `FAKE_EMBED: ${FAKE_EMBED:-0}` eklenir (paylaşılan satır). `FAKE_EMBED=1` iken `/readyz` ve ekran bunu açıkça gösterir (test). e2e iki aşamalı.
- **D3 A:** FOLLOWUP-86 açıldı (sahibi 04b). Bu maddeler için yer tutucu ya da "yakında" yazılmaz.
- `mocks/openapi-04a.yaml` yok: tipler doğrudan `backend/openapi/04a.yaml`'dan üretilir, `check:api` iki spec'i oradan okur. Bu nedenle "Değişecek dosyalar" listesindeki mocks maddesi ve D1 için `next.config.ts` maddesi düştü.
- Önce ölçüm: ağırlıksız `FAKE_EMBED=1` yığında hangi biçimler `indexed` oluyor. e2e fixture'ı o biçimlerden seçilir. DOCX dönüşümünün e2e'si ağırlık gerektirdiği için NOT_RUN.

### Kararlar (KARAR-GEREK, öneri önce; yukarıda cevaplandı)

- **D1 `/readyz` önyüze nasıl gelir?** (kimliksiz, `/api/v1` dışında; rewrite yok)
  - **A (Önerilen):** `next.config.ts`'e `/readyz` rewrite (1 satır, C6 aynı origin). Tarayıcı yenileyebilir, `warming` canlı izlenir.
  - B: sunucu bileşeni render anında backend'i çağırır. Rewrite yok ama canlı yenileme yok, ısınma elle sayfa yenilemeyle izlenir.
  - C: Next route handler `app/api/readyz/route.ts`. İkinci vekil kodu (ARCH-09 tersi).
- **D2 e2e'de gömme nasıl açılır?** (`FAKE_EMBED` compose'a geçmiyor; ağırlık yok; GOREV fake yol istiyor)
  - **A (Önerilen):** `deploy/docker-compose.yml` `&app-env`'e `FAKE_EMBED: ${FAKE_EMBED:-0}` (varsayılan kapalı, paylaşılan değişiklik). e2e iki aşama: önce varsayılan stack'te readiness `model_missing` testi, sonra `FAKE_EMBED=1 up -d backend worker` ve geri kalan testler. Komutlar docs/onyuz.md'de.
  - B: önyüz testlerine ayrı compose override dosyası (`-f`). deploy/ dokunulmaz ama ikinci yapılandırma kaynağı olur.
  - C: e2e yalnız yükleme ve `skipped` yolunu test eder; indeksleme ve arama e2e'siz kalır. Kabul (M2 "arama sonucu görme") kanıtsız kalır.
- **D3 Uçsuz brief maddeleri (Kapsam dışı a-f):**
  - **A (Önerilen):** UI yazılmaz; her biri için koordinatör FOLLOWUP açar (a, c, d, e: 04b/03c'ye additive uç; b: 04b `ingest_gate_stats` ucu; f: FOLLOWUP-67 ile).
  - B: Ingest Raporu belge listesinden istemcide türetilir. Parça düzeyi eksik kalır; brief "toplamlar belge sayısına eşit" kanıtı kısmi olur; hesap yanlış katmanda (ARCH-08).

### Varsayımlar
- A1: yollar nav href'leridir (`/knowledge-bases`, `/system-status`); touch-zone'daki `{knowledge,status}` bunlara karşılık gelir.
- A2: touch-zone'a additive dosyalar eklenir: `next.config.ts` (D1), `package.json` scripts + `scripts/check-api.mjs` + `mocks/openapi-04a.yaml` (iki spec tip üretimi, bağımlılık yok), `lib/navigation.ts`.
- A3: Sistem durumu proje kapsamlı değil; nav `admin` kuralı korunur, ek `superadmin` kısıtı yok (`/readyz` zaten kimliksiz).

## Değişen dosyalar

- **Paylaşılan:** `deploy/docker-compose.yml`. `&app-env`'e `FAKE_EMBED: ${FAKE_EMBED:-0}` eklendi (3 satır, yorum dahil). Backend, worker ve tools'ta varsayılan `"0"`; `compose config` 0. Compose'a dokunan başka paket önce merge olursa, sonra merge olan rebase eder.
- **Sözleşme ve tipler:**
  - `frontend/lib/api/schema-04a.d.ts` (üretilmiş, `backend/openapi/04a.yaml`'dan; kopya yok).
  - `frontend/package.json`: yalnız `gen:api` script'i değişti, bağımlılık eklenmedi.
  - `frontend/scripts/check-api.mjs` (iki spec).
- **API katmanı:**
  - `frontend/lib/api/client.ts`: additive `upload()` (XHR ilerleme; aynı ApiError, `network_error`).
  - `frontend/lib/api/knowledge-queries.ts`: KB/belge/arama kancaları; belge listesi yalnız işlenen belge varken 2 s yenilenir.
  - `frontend/lib/api/errors.ts`: 5 yeni kod.
- **Saf mantık:**
  - `frontend/lib/knowledge.ts`: enum kopyaları, katman, kapı gerekçesi, hata kodu, yenileme.
  - `frontend/lib/readiness.ts`: sunucu tarafı `/readyz` okuması; sözleşme dışı cevap hata olur.
- **Ekranlar:**
  - `frontend/app/(console)/knowledge-bases/page.tsx` ve `knowledge-bases/[kbId]/page.tsx`;
  - `frontend/app/(console)/system-status/page.tsx` (sunucu bileşeni; rol sunucuda denetlenir, sonra backend okunur).
- **Bileşenler:** `kb-form.tsx`, `document-upload.tsx`, `document-table.tsx`, `reindex-form.tsx`, `search-panel.tsx`, `readiness-view.tsx`, `disabled-with-reason.tsx`.
  - `disabled-with-reason.tsx`, `app/(console)/models/page.tsx` içinden taşındı; models sayfası yalnız import ve `needs="superadmin"` değişti, davranış aynı.
- **Diğer önyüz değişiklikleri:**
  - `frontend/components/ui/tabs.tsx`: pasif sekme metni `text-foreground/60` → `/80`; açık temada axe `color-contrast` ihlali vardı. Sekmeyi yalnız bu paket kullanıyor.
  - `frontend/lib/navigation.ts`: `knowledgeBases`, `systemStatus` `ready: true`.
  - `frontend/messages/{en,tr}.json`: `KnowledgeBases`, `Documents`, `Search`, `SystemStatus` namespace'leri ve 5 `Errors` anahtarı.
- **Testler:** `frontend/tests/unit/test_10bp1_{13,14,15,16,17}_*`, `frontend/tests/e2e/test_10bp1_{1..12}_*.spec.ts`, `frontend/tests/e2e/knowledge.ts`.
- **Belgeler:** `docs/onyuz.md` (ekran haritası, "Knowledge bases (04a)", "System status", iki aşamalı e2e komutları, ekran görüntüleri), `docs/images/10bp1-*.png` (10 dosya).

## Kabul kriterleri → testler (HEAD db5c8fa, temiz yığın)

| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | KB listesi, boş durum, oluşturma (anahtar deseni, `knowledge_base_key_taken`), düzenleme, tek eşik kuralı | `test_10bp1_1_kb_create_edit` | geçti |
| 2 | 13a PDF yükleme, outcome, `indexed`'e kadar canlı liste, katman/kapılar/dönüştürücü/parça | `test_10bp1_2_upload_indexed` | geçti |
| 3 | Aynı dosya `unchanged`; aynı metin başka adla Kapı 1 `duplicate_of` + asıl belgeye bağlantı | `test_10bp1_3_reupload_duplicate` | geçti |
| 4 | Kapı 0 `binary` reddi gerekçesiyle; DOCX `failed` + `model_missing` açıklaması ve ayrıntı | `test_10bp1_4_gate_reject` | geçti |
| 4b | 413 `request_too_large` açık mesaj | birim `test_10bp1_13_upload_client` | geçti (e2e NOT_RUN: sınır 516 MB) |
| 5 | Aramayı dene: iki skor, eşik modu `rerank_floor`, elenen sayısı, gecikme; Türkçe sorgu tarayıcıdan | `test_10bp1_5_search_panel` | geçti |
| 6 | ACL: yalnız admin'e açık belge analyst'e görünmez ve URL ile 404; rol seçmeden yükleme formda reddedilir; "tüm üyeler" rolleri kapatır | `test_10bp1_6_acl_upload` | geçti |
| 7 | Belge silme, gold yeniden üretme (202, "Rebuilding 1 document."), belge yeniden `indexed` | `test_10bp1_7_delete_reindex` | geçti |
| 8 | admin+read: aynı satırlar (işlem sütunu hariç), tüm mutasyon kontrolleri pasif, rozet, arama açık, API 403 `read_only_access`; edit/read PNG | `test_10bp1_8_read_only` | geçti |
| 9 | analyst: KB oluştur/düzenle/sil nedenli pasif, yükleme/yeniden üretme açık; sistem durumu menüde yok, URL'de "yetkiniz yok", tablo render edilmez | `test_10bp1_9_roles` | geçti |
| 10 | Sistem durumu: ağırlıksız `not_ready` + `model_missing` açıklaması (1. aşama); FAKE_EMBED ile `ready` ve "FAKE_EMBED=1" görünür; tarayıcı `/readyz` gövdesine ulaşamaz | `test_10bp1_10_readiness` (iki test) | geçti |
| 11 | 4 ekran × 2 tema PNG + axe WCAG 2 A/AA 0 ihlal | `test_10bp1_11_screens_themes_axe` (8 test) | geçti |
| 12 | Sorgu hatası `QueryError` (404 ve zorlanmış 503), boş durum gibi görünmez | `test_10bp1_12_query_failures` | geçti |
| 13 | `upload()`: ilerleme, 413/422/401/403, sözleşme dışı gövde, ağ hatası | `test_10bp1_13_upload_client` | geçti |
| 14 | Enum kopyaları 04a sözleşmesiyle birebir; katman; gerekçe ve hata kodu eşlemesi; bilinmeyen kod ham | `test_10bp1_14_knowledge_status` | geçti |
| 15 | Yeni hata kodları, tüm kapı gerekçeleri, durumlar ve readiness kodları EN/TR'de | `test_10bp1_15_messages` (+ `test_10a_8`, `test_10af_18`) | geçti |
| 16 | Yenileme yalnız işlenen belge varken ve yalnız `warming`'de | `test_10bp1_16_polling` | geçti |
| 17 | Sunucu tarafı `/readyz` okuması: 200/503 sonuç, sözleşme dışı ve ağ hatası açık hata | `test_10bp1_17_readiness_read` | geçti |
| 18 | Sabit renk ve sabit metin yok | `test_10a_3`, `test_10ab_12`, `npm run lint` | geçti |
| 19 | `check:api` iki spec | `npm run check:api` | geçti |
| 20 | Brief: Lighthouse ≥ 90 | — | NOT_RUN (FOLLOWUP-37, axe yerine) |

## Çalıştırılan komutlar

Tümü konteynerde. Önyüz `node:20.19.5-alpine` + `ffcore-10a-nm` volume; e2e compose `e2e` servisi (Playwright imajı digest pinli); backend `tools` imajı `0.0.0-10bp1`.

| Komut | Ortam | Exit | Süre / sonuç |
|---|---|---|---|
| `npm run lint` | node:20 | 0 | |
| `npm run typecheck` | node:20 | 0 | |
| `npx vitest run` | node:20 | 0 | 23 dosya, 113 test |
| `npm run check:api` | node:20 | 0 | iki spec güncel |
| `docker compose --env-file .env.test config -q` | `FFCORE_VERSION=0.0.0-10bp1` | 0 | |
| `docker compose ... run --rm tools sh -c "cd backend && python -m pytest tests/unit/test_00_repo_skeleton.py -q"` | tools 0.0.0-10bp1 | 0 | 11 passed (compose yapı testleri) |
| `down -v` → `up -d --wait --build backend` → `create-superadmin` | `-p 10bp1`, `FAKE_EMBED` yok, ağırlık yok, `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm`, `BACKEND_PORT=18110` | 0 | up 53 s |
| e2e 1. aşama `npx playwright test --grep @model-missing --workers=1` | aynı yığın | 0 | 1/1, 97 s |
| `FAKE_EMBED=1 up -d --wait backend worker` | | 0 | 25 s |
| e2e 2. aşama `npx playwright test --grep-invert @model-missing --workers=1` | `FAKE_EMBED=1` | 0 | 95/95 (19'u 10bp1; 10a/10ab/10af 76 test aynı yığında yeşil), 389 s |
| `down -v` | | 0 | konteyner 0 |

**NOT_RUN:**
- `make test` / `make test-int` backend'in tamamı: backend kodu değişmedi; compose satırı için yapı testleri koştu. DRIFT-85 bilinen main kırmızıları koordinatörde.
- İki profil e2e: önyüz profil bağımsız; yığın `.env.test` profiliyle koştu.
- DOCX ve Markdown başarılı dönüşüm: Docling ağırlığı gerekir, ağırlıkları yalnız kullanıcı getirir.
- Gerçek modelle skor dağılımı.
- Lighthouse.

## Çıktı özeti ve post-state

- Ölçüm (C-10bp1-0005): metin katmanlı PDF `indexed` (`pymupdf4llm`, 15 parça); uzun TXT `indexed`; kısa TXT Kapı 2 `no_prose`; MD ve DOCX `failed model_missing`; ikili dosya Kapı 0 `binary`.
- Yığın kanıttan sonra kaldırıldı (`down -v`). 10a ekran görüntüleri e2e'de yeniden üretildi ama commit'lenmedi (geri alındı).
- Kanıt koşusunun ürettiği 10bp1 PNG'leri commit'teki sürümle aynı ekranlar; içerik koşu verisine göre değişir. Commit'teki sürüm, düzeltilmiş sekme kontrastıyla üretildi.

## Kontrol listesi

- [x] Felsefe ile çelişen nokta işaretlendi: D1-D3 koordinatör kararıyla kapandı; uçsuz maddeler için ekran yazılmadı (FOLLOWUP-86).
- [x] Donmuş sözleşme kırılmadı. C13 yalnız additive (yeni mesaj anahtarları); token eklenmedi.
- [x] İki profil: önyüz profil bağımsız. Compose satırının varsayılanı iki profilde de 0.
- [x] Mutasyonlar backend'de audit'li (04a); salt-okunur modda önyüz kontrolleri pasif, API 403 (test 8).
- [x] Log, API, hata gövdesi secret-free. `/readyz` ayrıntısı tarayıcıya yalnız admin ekranında, sunucuda rol denetiminden sonra gider. e2e anahtarları yalnız `.env.test` test değeri.
- [x] Metinler `messages/{en,tr}.json`'da; iki tema PNG + axe.
- [x] Docs güncel (`docs/onyuz.md`). `.env.example` değişmedi: `FAKE_EMBED` yalnız test bayrağı, compose varsayılanı 0.
- [x] WORK_QUEUE: kanalda DURUM/PR-HAZIR.

## Varsayımlar ve brief'teki çelişkiler

- Yollar nav href'leri: `/knowledge-bases`, `/system-status` (WORK_QUEUE touch-zone `{knowledge,status}`).
- Brief "ACL düzenleme", "Ingest Raporu", "rerank tabanı altında elenenler ayrı", "yeniden dönüştür (preset)", sistem durumunda yüklü model/bellek/kuyruk: 04a'da uç yok. FOLLOWUP-86 açıldı (D3 A); bu maddeler için ekran ve yer tutucu yok. "Elenenler" yalnız sayı olarak gösterilir.
- Yükleme ACL'inde kullanıcı seçimi yok: kullanıcı listesi `require_superadmin` (FOLLOWUP-67 ile aynı kök).
- Analyst'e yükleme ön-seçili. Bu, backend'in rol vermeyince uyguladığı varsayılanın ekranda görünür hâli; gizli varsayılan bırakılmadı (ARCH-10).
- Rerank açıkken `default_min_score` gönderilmez; kayıtlı değer sessizce silinmez.
- Kapı gerekçe kodları backend kaynağından alındı: `knowledge/scope.py` (5) ve `knowledge/gates.py` (`duplicate_of:<id>`, `data_dump:<kind>` dahil). Sözleşmede gerekçe enum'u yok; yeni kod ham gösterilir (birim testli).
- Gözlem, bu PR'da değişmedi: konsolda bilinmeyen yollar (`/readyz` dahil) `[section]` sayfasının `notFound()`'u ile HTML not-found gövdesi döner ama HTTP durumu 200 (akışlı render). Güvenlik etkisi yok (gövde konsolun sayfası), test bunu gövdeyle doğrular. 10a'dan beri böyle; düzeltilecekse ayrı küçük iş.
- Curl'den Türkçe JSON gövdesinin 400 alması kabuk kodlamasıymış: tarayıcıdan Türkçe sorgu test 5'te geçti.

## Süreç sapmaları (açık)

- Test-önce sırası birim testlerinde uygulandı: 13, 14, 15, 16 kırmızı görüldü, sonra kod yazıldı. 17'de test ve kod aynı adımda yazıldı; kırmızı, kod geçici olarak kaldırılarak görüldü.
- e2e testleri ekranlardan sonra yazıldı. İlk tam koşu 4 gerçek hata yakaladı ve düzeltildi: sekme kontrastı (ürün), `/readyz` beklentisi, salt-okunur karşılaştırması ve bekleme (test).

## Kalan riskler

- Gerçek modelle (FAKE_EMBED değil) skor dağılımı ve süreler e2e'de görülmez; M3 ölçümü (FOLLOWUP-77).
- Belge listesi sayfalamasız (04a); büyük KB'de liste ve 2 s yenileme yük getirir. 04b'de sayfalama gelirse additive.
- Yükleme tek istek (sunucu sınırı 516 MB); çok büyük toplu yüklemede 413 mesajı görünür, parçalama yok.
