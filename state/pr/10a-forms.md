# PR: 10a-formlar (sağlayıcı ve model formları)

Sınıf [A] · Branch `feat/10a-forms` (main 070d8b0) · Oturum ffcore-isci-c-10af · GOREV K-10af-0001 (taslak K-10af-0000)

## Plan (kodlamadan önce)

### 1. Bulunan semboller ve dosyalar (worktree 070d8b0'da okundu)

- Sözleşme: `backend/openapi/03a.yaml` = `frontend/mocks/openapi-03a.yaml` (cmp aynı). Uçlar: `GET /provider-drivers` (`DriverSpec{driver, domains, supports_test, fields[DriverField{name, required, secret, description}]}`), `GET|POST /providers`, `POST /providers/test` (`ProviderTestRequest{driver, config}` → `ProviderTestResult{supported, ok, code, message, latency_ms}`), `GET|PATCH|DELETE /providers/{id}`, `PUT /providers/{id}/projects` (`project_ids` minItems 1), `POST /providers/{id}/test`, `GET /model-catalog?driver=&model_id=`, `GET|POST /projects/{pid}/models`, `GET|PATCH|DELETE /projects/{pid}/models/{id}`.
- Backend davranışı (kaynaktan, `backend/ffcore/services/providers.py`, `api/providers.py`, `api/models.py`):
  - Sağlayıcı uçlarının hepsi `require_superadmin` (okuma dahil). Model yazma `require_role("admin", write=True)`; katalog her oturumlu kullanıcıya açık.
  - Sürücü alanları: `base_url`, `api_key`, `api_base`, `api_version`, `aws_access_key_id`, `aws_secret_access_key`, `region`, `url`, `path` (açıklamalar backend'de İngilizce sabit).
  - `merge_config` gönderilen config'i **tamamen** alır (gönderilmeyen anahtar silinir); gizli alan `"***"` gönderilirse kayıtlı değer korunur. `validate_config` `"***"` ile kaydetmeyi/test etmeyi reddeder (`invalid_config_field`). Yani "boş = değişmez" UI'da: düzenlemede boş bırakılan gizli alan, kayıtlı değer varsa `"***"` olarak gönderilir; tam config her zaman gönderilir.
  - Test sonuç kodları: `ok`, `connection_test_unsupported`, `auth_failed`, `connection_failed`, `egress_timeout`, `http_<status>`, egress red kodları (`egress_offline`, `egress_not_allowlisted`, `egress_private_address`, `egress_invalid_url`, `egress_too_many_redirects`, ...). Test hiçbir zaman hata fırlatmaz, kaydı engellemez.
  - Hata kodları: 409 `provider_key_taken`, `provider_in_use` (DELETE, PATCH is_active=false, PUT projects); 422 `domain_not_supported`, `unknown_config_field`, `missing_config_field`, `invalid_config_field`, `unknown_project`; model 400 `provider_not_assigned`, `provider_domain_mismatch`, `embed_dim_mismatch`; 409 `model_key_taken`, `embedding_probe_unavailable` (main'de hiçbir sürücünün probe'u yok, 04a `local_flagembedding` için kaydedecek).
  - Model: `ModelUpdate`'te `key` ve `provider_id` yok (düzenlemede salt okunur). DELETE soft delete, 409 yok. `embed_dim` yalnız ölçümle.
  - Katalog (`deploy/seed/model_catalog.yaml`, migrate her profilde yükler): `ollama qwen3.5:35b`, `local_flagembedding BAAI/bge-m3`.
- Önyüz (main, 10a-bağlama): `app/(console)/{providers,models}/page.tsx` salt-okuma liste; form kalıbı `components/project-form.tsx` (FormData + zod, alan altı hata, `useReportError`); `components/screen.tsx` `ListState`/`QueryError`; `lib/api/errors.ts` `KEYS`; `lib/api/queries.ts` `useProviders`, `useModels`, `useProjects`; `components/write-gate.tsx` `WriteGate projectId`; shadcn `select`, `checkbox`, `sheet`, `tabs`, `input`, `label` mevcut (textarea yok).
- e2e ortamı: `.env.test` `ALLOWED_INTERNAL_HOSTS=litellm`, `OFFLINE=false`, `EMBED_DIM=1024`; compose `e2e` servisinde LiteLLM adresi/anahtarı yok.

### 2. Kapsam / kapsam dışı

Kapsam:
1. **Sağlayıcılar (süper yönetici):** Ekle / Düzenle (yan panel `Sheet`), Bağlantı testi, Pasifleştir / Etkinleştir, Proje ataması.
   - Sürücü seçimi `/provider-drivers`'tan; domain kutuları yalnız sürücünün domain'leri; config alanları `fields`'tan dinamik (zorunlu işareti, gizli alan `type=password`, `autocomplete=off`).
   - Alan etiketi ve ipucu `messages` `ProviderFields.<alan>` (EN kaynak, TR çeviri); backend'in İngilizce `description`'ı gösterilmez.
   - Gizli alan: düzenlemede boş, ipucu "Stored. Leave empty to keep it."; boş + kayıtlı → `"***"`; tam config gönderilir.
   - Test: ekleme formunda `POST /providers/test` (kaydetmeden, formdaki değerlerle); düzenleme formunda ve satırda `POST /providers/{id}/test` ("Test saved configuration", kayıtlı config). `supports_test=false` sürücüde düğme yerine "This driver has no connection test" açıklaması. Sonuç kodu → mesaj; bilinmeyen kod genel mesaj + kod. Başarısız test kaydı engellemez.
   - Projeler: `useProjects` listesinden çoklu seçim, en az 1 (zod, istemci; sunucu da 422). Eklemede `project_ids` gövdede, düzenlemede `PUT /providers/{id}/projects` (değiştiyse).
   - Pasifleştir: `DELETE` (onay); 409 `provider_in_use` açık mesaj. Etkinleştir: `PATCH {is_active: true}`.
2. **Modeller (seçili proje):** Ekle / Düzenle / Sil.
   - Önce kategori (zorunlu; seçilmeden diğer alanlar pasif). Sağlayıcı seçimi: projeye atanmış, aktif ve kategorinin domain'ini (`embedding` → embedding, diğerleri → model) taşıyan sağlayıcılar.
   - "Fill from catalog": `GET /model-catalog?driver=<sağlayıcı sürücüsü>&model_id=<girilen>`; bulunursa capabilities, input_types, limits.context_window/max_output, pricing doldurulur ve `source` + `as_of` gösterilir; boşsa "Not in the catalog; enter the values yourself", alanlara dokunulmaz.
   - Alanlar: key, display_name, model_id, capabilities (3 kutu), input_types, pricing (3), limits (4), reasoning_default (seçim, "Not set" = null), return_reasoning, upstream_api (açık seçim, varsayılan `chat`), request_policy (drop_unsupported_params, reject_params, extra_body JSON; geçersiz JSON alan altı hata), is_active. `forward_unknown_params` gösterilmez, gönderilmez (varsayılan false; DRIFT-72, 01 `forward_unknown_params_unsupported`).
   - Embedding: 409 `embedding_probe_unavailable`, 400 `embed_dim_mismatch` alan üstünde açık mesaj; listede `embed_dim` ve `litellm_name` sütunu.
   - Sil: onay, soft delete.
3. `lib/api/errors.ts` + `messages/{en,tr}.json` `Errors`: yukarıdaki yeni kodlar. Test sonuç kodları ayrı `ProviderTest` ad alanı.
4. docs/onyuz.md: ekran haritası (Providers/Models "forms"), form davranışı (gizli alan, test, katalog), e2e komutu (D2/D3'e göre), ekran görüntüleri.

Kapsam dışı: FOLLOWUP-67 (üye ekleme yolu), backend değişikliği (D1-B seçilirse ayrı), gizli alanı silme (aşağıda risk), Lighthouse (FOLLOWUP-37), iki profil e2e (önyüz profil bağımsız; 10a-bağlama ile aynı gerekçe).

### 3. Değişecek dosyalar ve neden

| Dosya | Neden |
|---|---|
| `frontend/app/(console)/providers/page.tsx` | Ekle düğmesi, satır eylemleri (düzenle, test, pasifleştir/etkinleştir) |
| `frontend/app/(console)/models/page.tsx` | Ekle, düzenle, sil; `litellm_name`, `embed_dim` sütunları |
| `frontend/components/provider-form.tsx` (yeni) | Sağlayıcı formu, dinamik alanlar, test, projeler |
| `frontend/components/model-form.tsx` (yeni) | Model formu, kategori önce, katalogdan doldur |
| `frontend/components/provider-test-result.tsx` (yeni) | Test sonucu gösterimi (iki formda ve satırda ortak) |
| `frontend/lib/provider-config.ts` (yeni) | `buildConfig(fields, values, stored)`: gizli alan `"***"` kuralı, saf fonksiyon (birim testli) |
| `frontend/lib/api/queries.ts` | `useDrivers`, `useCreateProvider`, `useUpdateProvider`, `useSetProviderProjects`, `useDeactivateProvider`, `useTestProviderConfig`, `useTestProvider`, `useCatalog`, `useCreateModel`, `useUpdateModel`, `useDeleteModel` |
| `frontend/lib/api/errors.ts` | Yeni hata kodları |
| `frontend/messages/{en,tr}.json` | `Providers`, `Models`, `ProviderFields`, `ProviderTest`, `Errors` |
| `frontend/components/ui/textarea.tsx` (yeni, shadcn) | extra_body JSON alanı |
| `frontend/tests/unit/*` | `buildConfig`, hata ve test kodu eşlemesi |
| `frontend/tests/e2e/test_10af_*.spec.ts`, `support.ts`, `global-setup.ts` | Kabul testleri |
| `docs/onyuz.md`, `docs/images/10a-provider-form-*.png`, `10a-model-form-*.png` | Belgeler, iki tema |
| (D2-A seçilirse) `deploy/docker-compose.yml` `e2e.environment` | 2 satır, touch-zone genişlemesi |

### 4. Sözleşme, yapılandırma, profil etkisi

Sözleşme değişmez (03a okunur; `npm run check:api` yeşil kalır). Yapılandırma: yalnız D2-A seçilirse e2e servisine iki ortam değişkeni. Profil farkı yok (önyüz profil bağımsız); e2e stack `.env.test` (llmaas).

### 5. Kabul kriteri → test adı

| Kabul | Test |
|---|---|
| Sürücü seçimi alanları değiştirir; canlı `/provider-drivers`'taki her alan adının EN ve TR etiketi var (sapma kırmızı) | `test_10af_1_provider_driver_fields` (e2e) |
| Sağlayıcı eklenir, projeye atanır, listede görünür; gizli değer hiçbir yanıtta ve DOM'da yok | `test_10af_2_provider_create` |
| Kaydetmeden test sonuç mesajı; başarısız test kaydı engellemez; `supports_test=false` açıklaması; kayıtlı config testi | `test_10af_3_provider_test` |
| Düzenlemede boş gizli alan kayıtlı değeri korur (istek gövdesinde `"***"`, kayıtlı test aynı sonucu verir) | `test_10af_4_provider_edit_keeps_secret` + birim `buildConfig` |
| Proje seçimi boş bırakılamaz (istek gitmez); PUT ataması değişir | `test_10af_5_provider_projects` |
| Kullanımdaki sağlayıcı pasifleştirilince `provider_in_use` mesajı, satır aktif kalır | `test_10af_6_provider_in_use` |
| Form ile model kaydı → 01 uzlaştırıcısı → LiteLLM `/model/info`'da `<proje>.<anahtar>` (API ile, anahtar başlıkta) | `test_10af_7_model_create_reconciled` |
| Katalogdan doldur: bulunan kayıt alanları doldurur + kaynak/tarih; bulunmayan kayıt mesajı, alanlar değişmez | `test_10af_8_model_catalog_fill` |
| Embedding kaydı probe yokken `embedding_probe_unavailable` açık mesajı | `test_10af_9_model_embedding_probe` |
| Model düzenle ve sil; silinen LiteLLM'den de kalkar | `test_10af_10_model_edit_delete` |
| `read` erişimde form düğmeleri pasif, açıklamalı | `test_10af_11_forms_read_only` |
| Formlar iki temada PNG + axe (WCAG 2 AA) | `test_10af_12_forms_both_themes` |
| Hata ve test kodu eşlemesi; bilinmeyen kod genel mesaj | birim `test_10af_errors`, `test_10af_provider_config` |

Önce kırmızı: her dilimde test önce yazılır, kırmızı çıktısı PR'a.

### 6. Migration

Yok.

### 7. Geri alma

Yalnız önyüz + belge (+ D2-A'da compose e2e'ye iki satır); revert yeterli, veri etkisi yok.

### 8. Durma koşulları

- Backend sözleşmesiyle çelişen davranış (ör. `"***"` kuralının çalışmaması) → KARAR-GEREK, backend'e dokunmam.
- LiteLLM `/model/info` model kaydını 60 s içinde göstermezse 01 sorunu olarak kayıt, testi gevşetmem.
- Touch-zone dışı gereksinim (D1-B, D2-A) koordinatör onayı olmadan yapılmaz.

### 9. Felsefe kontrolü

- **ARCH-07 (tek kod yolu):** formlar üretilmiş tiplerle gerçek backend'e gider; msw ya da sahte yanıt yok; test sonucu, katalog ve hata kodları backend'in kendi kodlarıyla.
- **ARCH-09 (yeniden inşa yok):** form kütüphanesi eklenmez (mevcut FormData + zod kalıbı); config birleştirmeyi backend yapar (`"***"`), önyüz yalnız kuralı uygular; LiteLLM'e önyüzden yazılmaz, uzlaştırıcı yapar.
- **ARCH-10/06 (açık tercih, fail-loud):** `upstream_api` açık seçim (algılama yok), kategori önce; katalogda olmayan model "bulunamadı" der, tahmin etmez; bilinmeyen sürücü alanı/test kodu ham adıyla görünür ve e2e drift testi kırmızı olur; `embed_dim` elle girilmez.

## Koordinatör kararı gereken noktalar (KARAR-GEREK, öneri önce)

- **D1 Proje admin'i sağlayıcı listesini okuyamıyor** (`GET /providers` yalnız süper yönetici). Model formu sağlayıcı seçimi için listeye muhtaç.
  - **A (öneri):** bu PR'da model *ekleme* yalnız süper yöneticiye (WriteGate nedeni: "Adding a model needs a superadmin until providers are listed per project"); düzenleme ve silme proje admin'ine açık (sağlayıcı alanı gerekmez, sağlayıcı adı yerine kısaltılmış kimlik). FOLLOWUP: 03'e additive `GET /projects/{id}/providers` (salt-okuma, config'siz), sonra kısıt kalkar. Etki: PoC'ta süper yönetici zaten var; touch-zone korunur.
  - B: aynı PR'da backend'e additive uç (isci-a alanı, sözleşme additive). Etki: touch-zone genişler, review backend'i de kapsar, süre uzar.
  - C: sağlayıcı kimliğini elle yazdırmak. Etki: kullanılamaz; önermem.
- **D2 e2e'de LiteLLM doğrulaması:** e2e servisinde LiteLLM adresi/anahtarı yok.
  - **A (öneri):** `deploy/docker-compose.yml` `e2e.environment`'a `LITELLM_URL: http://litellm:4000` ve `LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:?...}` (yalnız `.env.test` test değeri; `Authorization` başlığında, URL'de değil). Etki: compose'a 2 satır, touch-zone genişlemesi; kabul Playwright içinde kanıtlanır.
  - B: Playwright sonrası ayrı adım `docker compose run --rm tools make render-litellm CHECK=1`, çıktı PR'a. Etki: compose değişmez ama kabul testin dışında kalır.
  - C: LiteLLM doğrulaması yok, yalnız `litellm_name`. Etki: GOREV'in uçtan uca şartı karşılanmaz.
- **D3 e2e sağlayıcı adresi:** uzlaştırıcı egress kuralını uygular, `.env.test` yalnız `litellm`'e izin veriyor.
  - **A (öneri):** `ollama` sağlayıcısı `http://fake-llm:11434`, stack komut satırında `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm` (dosya değişmez); fake-llm başlatılmaz (`/model/new` upstream'e gitmez). Bağlantı testi `connection_failed` döner, "başarısız test kaydı engellemez" kabulü de bununla kanıtlanır; katalog `ollama qwen3.5:35b` ile eşleşir.
  - B: `http://litellm:4000` adresi (izinli, dosya değişmez). Etki: kendine dönen yapılandırma, ekran görüntüsünde yanıltıcı.
  - C: `.env.test`'e `fake-llm` eklemek. Etki: touch-zone dışı dosya.
- **D4 `upstream_api=responses`:** 01 uzlaştırıcısı `upstream_api_unsupported` ile yazmıyor.
  - **A (öneri):** seçenek görünür ama pasif, açıklama "Not wired in the gateway yet"; varsayılan `chat` açıkça seçili. Etki: kayıtlı `responses` modeli (seed/API) düzenlemede değer olarak görünür, kaydedilebilir.
  - B: seçilebilir + uyarı. Etki: LiteLLM'e yazılmayan model kaydı oluşturur.
  - C: hiç gösterme. Etki: sözleşme alanı gizlenir, mevcut değer görünmez.

## Varsayımlar ve brief'teki çelişkiler (plan aşaması)

- Taslaktaki "düzenlemede boş = değişmez" sözleşmede `"***"` ile ifade ediliyor; UI boşu `"***"`'a çevirir (çelişki değil, uygulama ayrıntısı).
- Gizli alanı **silmek** (ör. opsiyonel `api_key`'i kaldırmak) bu sözleşmeyle UI'dan mümkün değil (boş = koru). Kalan risk olarak yazılır, gerekirse FOLLOWUP.
- Backend sürücü alanı açıklamaları İngilizce sabit; UI metin kuralı gereği gösterilmez, `ProviderFields` mesajları kullanılır.

## Plan onayı ve sapmalar

- K-10af-0002 (2026-10-28 22:46): plan onaylı, D1-D4 hepsi A. Koşullar: D1 ekle düğmesi proje admin'inde pasif ve nedenli, düzenlemede sağlayıcı salt okunur, liste çağrısı yok (FOLLOWUP-79). D2 compose satırları yalnız `${LITELLM_MASTER_KEY}` interpolasyonu, anahtar başlıkta; Playwright rapor/trace dizininde sahte anahtar araması 0; compose değişikliği paylaşılan değişiklik olarak işaretli. D3 tam komut docs/onyuz.md'de. D4 pasif seçenek açıklaması uzlaştırıcının `upstream_api_unsupported` reddine dayanır; kayıtlı `responses` modeli listede "LiteLLM'de değil" işaretli. Gizli alanı silme FOLLOWUP-80.
- K-10af-0003 (2026-10-28 23:26): C-10af-0004 bulgusu için karar B; `backend/ffcore/core/egress.py` + backend testleri touch-zone'a eklendi, ayrı `fix(03b)` commit'i, önce kırmızı test.

### Sapmalar (plan → uygulama)

1. **Test sırası:** birim testler önce yazıldı ve kırmızıydı (3 dosya: modül yok / `provider_key_taken` → `unexpected`). e2e testleri bileşenlerden **sonra** yazıldı; kırmızı kanıtı ayrı commit'le alındı: yalnız testleri içeren 86c04d8 (form yok) üzerinde `test_10af_*` → **22/22 kırmızı**, sebep eksik UI (17 tıklama zaman aşımı, eksik mesaj anahtarları, `element(s) not found`) + bir backend 500 (aşağıda).
2. Sağlayıcı listesinde satır düzeyinde "Test" düğmesi eklenmedi; kayıtlı yapılandırma testi düzenleme formunda ("Test saved configuration"). Gerekçe: aynı işlev, sonucu gösterecek ikinci bir yer gerekmez.
3. Birim test adları `test_10af_13..15` (plandaki `test_10af_errors`, `test_10af_provider_config` yerine, numaralı kalıp).
4. Model ekleme düğmesi proje admin'inde `DisabledWithReason` ile pasif (WriteGate kalıbı, `data-needs-superadmin`); düzenlemede sağlayıcı alanı kimlik olarak salt okunur, `/providers` çağrısı yok (test_10af_11 ağ isteğiyle doğrular).
5. `ProviderCreate.is_active` ve `RequestPolicy.forward_unknown_params` üretilen tipte zorunlu: `is_active: true` ve `forward_unknown_params: false` açıkça gönderiliyor (D4/DRIFT-72 ile uyumlu).
6. Ortam: 04a stack'i host 8000'i tutuyordu; `BACKEND_PORT=18010` (docs/onyuz.md'ye not eklendi). e2e `npm ci` bir kez ağ hatası verdi, tekrarında geçti.
7. Docker içinde çözülemeyen ad 4-8 s'de düşüyor (ölçüldü: 3,78 / 8,02 / 4,01 s); test_10af_3/12 sonucu backend'in 15 s test bütçesine kadar bekler (82219e6).
8. Tam sayfa ekran görüntüsünde sabit kenar çubuğu kaydırılmış konumda formun üstüne çiziliyordu; test_10af_12 çekimden önce başa kaydırır (851de1d).

## Touch-zone dışı backend düzeltmesi (K-10af-0003 B)

- Hata: `SafeOutboundClient` → `_PinnedBackend.connect_tcp` → `system_resolver` → `anyio.getaddrinfo` → `socket.gaierror`. gaierror `httpx2.HTTPError` değil; `_follow` yakalamıyor, `test_connection` yalnız `EgressError` yakalıyor → ASGI 500 (`POST /providers/test` ve `/providers/{id}/test`).
- Düzeltme (b1d07f6, `backend/ffcore/core/egress.py`): resolver çağrısı `try/except OSError` → `EgressRequestFailed("egress_dns_failed", "<host>:<port>", "name does not resolve") from None`. Sistem metni taşınmaz; politika kontrolleri (`check_host`, sonra her adres için `check_address`) aynı sırada, lookup'tan önce. `test_connection` bunu mevcut `except EgressError` dalında `connection_failed` sonucuna çevirir; API 200.
- Testler: `test_03b_2_unresolvable_host_is_request_failed` (gerçek resolver, `no-such-provider.invalid`, RFC 6761) ve `test_03b_2_resolver_os_error_is_request_failed` önce **kırmızı**, sonra yeşil; `test_03b_2_unresolvable_host_still_needs_the_policy` (izinsiz host lookup'a gitmeden `egress_not_allowlisted`) baştan yeşil. API: `test_03a_9_unresolvable_host_is_a_failed_test` (unsaved + stored → 200 + `connection_failed`). Uzlaştırıcı aynı `SafeOutboundClient`'ı kullanır, ek kod yok; ayrı uzlaştırıcı regresyon testi yazılmadı (risk).

## Değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `frontend/app/(console)/providers/page.tsx` | Ekle, satırda Düzenle / Pasifleştir / Etkinleştir (WriteGate), form aç-kapa |
| `frontend/app/(console)/models/page.tsx` | Ekle (süper yönetici; diğerlerinde nedenli pasif), Düzenle, Sil; `embed_dim` sütunu, kategori adı mesajdan, "Not in the gateway" rozeti |
| `frontend/components/provider-form.tsx` (yeni) | Sürücü alanları `/provider-drivers`'tan, gizli alan kuralı, iki tür test, projeler, istemci doğrulaması |
| `frontend/components/model-form.tsx` (yeni) | Kategori önce, uygun sağlayıcılar, katalogdan doldur, sayı alanları, upstream_api, request_policy, form içi hata kodları |
| `frontend/components/provider-test-result.tsx` (yeni) | Test sonucu, kod Details altında |
| `frontend/components/form-parts.tsx` (yeni) | `FieldShell`, `TextField`, `CheckGroup`, `CheckField` (aria-describedby kalıbı) |
| `frontend/components/ui/textarea.tsx` (yeni) | shadcn textarea, input ile aynı token sınıfları |
| `frontend/lib/provider-config.ts` (yeni) | `buildConfig`, `missingFields`, `testResultKey` |
| `frontend/lib/model-form.ts` (yeni) | `eligibleProviders`, `applyCatalog`, `parseExtraBody`, `parseList`, `parseNumber`, `notInGateway` |
| `frontend/lib/api/queries.ts` | Sürücü, sağlayıcı yazma/test, katalog, model yazma kancaları; `useProviders(enabled)` |
| `frontend/lib/api/errors.ts` | 12 yeni kod |
| `frontend/messages/{en,tr}.json` | `Providers`, `Models`, `ProviderFields`, `ProviderTest`, `Errors` |
| `frontend/tests/unit/test_10af_13..15` | Birim |
| `frontend/tests/e2e/api.ts`, `test_10af_1..12` | Kabul (gerçek backend + LiteLLM) |
| `deploy/docker-compose.yml` | **Paylaşılan değişiklik** (D2): `e2e.environment`'a `LITELLM_URL`, `LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:?...}`; 04a da compose'a dokunuyor, sonra merge olan rebase eder |
| `backend/ffcore/core/egress.py`, `backend/tests/unit/test_03b_egress.py`, `backend/tests/integration/test_03a_providers.py` | Touch-zone eki (yukarıda) |
| `docs/onyuz.md`, `docs/images/10a-*` | Ekran haritası, form davranışı, e2e komutu (`ALLOWED_INTERNAL_HOSTS`, `BACKEND_PORT`), 4 yeni + yenilenmiş PNG |

## Kabul kriterleri → testler

| Kabul | Test | Sonuç (son kod) |
|---|---|---|
| Sürücü alanları dinamik; canlı her alanın EN/TR etiketi | `test_10af_1_provider_driver_fields` (2) | geçti |
| Sağlayıcı ekleme + proje; gizli değer yanıt ve DOM'da yok, API `***` | `test_10af_2_provider_create` (2) | geçti |
| Kaydetmeden test, başarısız test kaydı engellemez, `supports_test=false` açıklaması, kayıtlı test | `test_10af_3_provider_test` (3) | geçti (`connection_failed`) |
| Boş gizli alan korunur (PATCH gövdesinde `***`, kayıtlı test aynı) | `test_10af_4_provider_edit_keeps_secret` + birim `buildConfig` | geçti |
| Proje boş bırakılamaz (yazma isteği yok), PUT ataması değişir | `test_10af_5_provider_projects` | geçti |
| Kullanımdaki sağlayıcı 409 `provider_in_use` mesajı; kullanılmayan pasif/etkin | `test_10af_6_provider_in_use` (2) | geçti |
| Form → uzlaştırıcı → LiteLLM `/model/info`'da `<proje>.<anahtar>` (anahtar başlıkta) | `test_10af_7_model_create_reconciled` | geçti |
| Katalogdan doldur (bulunan: değerler + kaynak/tarih, sıcaklık korunur; bulunmayan: mesaj) | `test_10af_8_model_catalog_fill` | geçti |
| Embedding probe yok → `embedding_probe_unavailable` form mesajı; yalnız embedding sağlayıcıları | `test_10af_9_model_embedding_probe` | geçti |
| Model düzenle/sil, LiteLLM'den kalkar; `responses` modeli işaretli, düzenlenebilir, yenide pasif | `test_10af_10_model_edit_delete` (2) | geçti |
| Salt-okuma süper yönetici; proje admin'i düzenler ama ekleyemez, `/providers` çağrısı yok | `test_10af_11_forms_read_only` (2) | geçti |
| Formlar iki tema PNG + axe WCAG 2 AA | `test_10af_12_forms_both_themes` (4) | geçti |
| Hata ve test kodu eşlemesi, bilinmeyen kod genel mesaj, sayı/JSON/liste ayrıştırma | birim `test_10af_13/14/15` | geçti |
| Çözülemeyen host 500 değil | `test_03b_2_*` (3), `test_03a_9_unresolvable_host_is_a_failed_test` | geçti |

## Çalıştırılan komutlar

Ortam: Windows, Docker Desktop (VM 11,7 GB; aynı anda 02 ve 04a stack'leri + tools koşuları açık). Önyüz birim/lint `node:20.19.5-alpine` + `ffcore-10a-nm`; backend `tools` konteyneri; e2e compose `e2e` servisi. Stack: `export ALLOWED_INTERNAL_HOSTS=litellm,fake-llm FFCORE_VERSION=0.0.0-10af BACKEND_PORT=18010; docker compose -p 10af --env-file .env.test ...`.

| Komut | SHA | Exit | Sonuç |
|---|---|---|---|
| `npx vitest run tests/unit/test_10af_` (kod yokken) | çalışma ağacı | 1 | **kırmızı**: 3 dosya |
| `pytest tests/unit/test_03b_egress.py -k 'unresolvable or resolver_os_error'` (düzeltme yokken) | çalışma ağacı | 1 | **kırmızı**: 2 failed, 1 passed |
| `npx playwright test tests/e2e/test_10af` (yalnız testler) | 86c04d8 | 1 | **kırmızı**: 22/22 |
| `npx tsc --noEmit`, `npx eslint .`, `npx vitest run`, `npm run check:api` | 82219e6 | 0 | 16 dosya / 89 test; sözleşme güncel |
| `make lint`, `make test` (`DEPLOY_PROFILE=llmaas` / `airgap`) | 82219e6 | 0 / 0 | 292 / 292 geçti |
| `make test-int` (llmaas / airgap, `--profile test` fake-llm) | 82219e6 | 0 / 0 | 134 / 134 geçti |
| `docker compose ... config -q` (varsayılan, `--profile e2e`) | c66408c | 0 | |
| e2e tam takım, yeniden derlenmiş backend | b1d07f6 | 1 | 72/74; 2 hata DNS beklemesi (5 s < 4-8 s) → 82219e6 |
| e2e tam takım, aynı stack 4. koşu (68 birikmiş sağlayıcı) | 82219e6 | 1 | 65/74; zaman aşımları (axe, giriş) |
| e2e tam takım, **temiz stack**, varsayılan worker | 82219e6 | 1 | 60/74; 10,9 dk; giriş/yükleme 5 s zaman aşımları, eski testler dahil (makine yükü) |
| e2e tam takım, temiz stack, `--workers=2` | 82219e6 | 1 | **71/74** (6,4 dk); 3 hata değişmemiş testlerde: `test_10a_4_axe_contrast: providers light` (giriş yönlendirmesi 5 s), `test_10ab_3_members` (2, 5 s) |
| aynı iki test dosyası tek worker | 82219e6 | 0 | **16/16** |
| `test_10af_12_forms_both_themes` (scrollTo sonrası) | 851de1d | 0 | 4/4 |
| LiteLLM master key araması: `frontend/test-results` + 6 e2e logu | | | 0 isabet (sınır: test-results yalnız son koşunun çıktısını tutuyor; başarısız koşuların trace'leri sonraki koşuda silindi) |
| `docker compose -p 10af ... down -v` | | 0 | konteyner 0, volume 0 |

NOT_RUN: Lighthouse (FOLLOWUP-37); iki profil e2e (önyüz profil bağımsız, 10a-bağlama ile aynı gerekçe); **tek seferde 74/74 temiz tam koşu** (paylaşılan makinede yük; yukarıdaki parçalı kanıt).

## Çıktı özeti ve post-state

Branch `feat/10a-forms` @ 851de1d (070d8b0 üstüne 6 commit), ağaç temiz. Stack kapalı. İmajlar `ffcore/backend:0.0.0-10af`, `ffcore/tools:0.0.0-10af` duruyor (kapanışta koordinatör siler).

## Kontrol listesi

- [x] Felsefe ile çelişen nokta işaretlendi (sapma 1: e2e test sırası; kırmızı ayrı commit'le kanıtlı)
- [x] Donmuş sözleşme kırılmadı (03a OpenAPI değişmedi; `check:api` 0)
- [x] İki profil: backend `make test` + `make test-int` iki profilde; e2e profil bağımsız (NOT_RUN gerekçeli)
- [x] Salt-okuma: form düğmeleri pasif (`test_10af_11`), API 403 mevcut (`test_10ab_4`)
- [x] Secret: gizli alan hiç doldurulmaz, yanıt/DOM'da yok (`test_10af_2`); master key yalnız başlıkta, çıktı aramasında 0
- [x] Metinler `en.json` kaynak + `tr.json`; iki tema PNG + axe
- [x] Docs güncel (`docs/onyuz.md`)
- [x] Durum kanal mesajıyla bildirildi

## Kalan riskler

- Paylaşılan makinede e2e zamanlaması: varsayılan 5 s beklemeler yük altında düşüyor (eski testler dahil); tam takım tek seferde yeşil kanıtlanamadı. Öneri: inceleyici daha az yüklü anda tam koşu ya da `--workers=2`.
- Gizli alan UI'dan silinemiyor (FOLLOWUP-80).
- Proje admin'i model ekleyemiyor (FOLLOWUP-79).
- Uzlaştırıcı yolu için ayrı DNS regresyon testi yok (aynı `SafeOutboundClient`; birim testi resolver noktasında).
- `docs/images/10a-providers-*.png` ve form görüntüleri e2e verisiyle çekildiği için çok satırlı ve büyük (~240-530 KB).

## Review r1 bulgu → düzeltme → kanıt (DUZELT K-10af-0007)

r1: ONAY, MINOR-1 merge öncesi kapanır (state/reviews/10a-forms-r1.md). Delta 851de1d → 275d06d (3 commit): c13cb2b test, f08b5b6 fix, 275d06d PNG.

| Bulgu | Düzeltme | Kanıt |
|---|---|---|
| MINOR-1: alpha'da açık model formu, beta'ya (read) geçişte açık kalıyor, Kaydet etkin, `PATCH beta/alpha-model` gidiyor | (1) `ModelList key={projectId}`: proje değişince liste ve form yeniden kurulur, state sıfırlanır. (2) Model formunda Kaydet `<WriteGate projectId>` içinde; (3) sağlayıcı formunda Kaydet `<WriteGate>` içinde (aynı desen) | `test_10af_16_project_switch` (2: alpha edit → beta read; süper yönetici alpha → beta edit): form yok, `model-save` yok, `/models` yazma isteği 0. c13cb2b'de (düzeltme yok) **2/2 kırmızı** (`toHaveCount(0)`), f08b5b6'da yeşil. Birim `test_10af_17_form_save_gate` (read'de iki formun Kaydet'i pasif, edit'te etkin): düzeltme öncesi **2/2 kırmızı**, sonra yeşil |
| Ek bulgu (birim testte görüldü): `Models.extraBodyHint` içindeki `{"reasoning_effort": "none"}` ICU argümanı sanılıyor (`INVALID_MESSAGE: MALFORMED_ARGUMENT`), next-intl yedek metne düşüyor | EN/TR'de JSON örneği ICU tırnağıyla (`'{...}'`) | `test_10af_18_messages_parse` (her EN/TR mesajı `createTranslator` ile, yalnız `INVALID_MESSAGE` hata): önce **2/2 kırmızı** (tek mesaj, iki dil), sonra yeşil; PNG'de ipucu tırnaksız görünüyor |

r2 kapıları:

| Komut | SHA | Exit | Sonuç |
|---|---|---|---|
| `npx tsc --noEmit`, `npx eslint .`, `npx vitest run` | f08b5b6 | 0 | 18 dosya / 93 test |
| `npx playwright test tests/e2e/test_10af_16 --workers=1` | c13cb2b (test, düzeltme yok) | 1 | **kırmızı** 2/2 |
| `npx playwright test --workers=1` (tam takım, temiz stack `-p 10af`) | f08b5b6 | 0 | **76/76** (4,8 dk) |
| LiteLLM master key araması: r2 e2e logları + `frontend/test-results` | | | 0 |
| `docker compose -p 10af ... down -v` | | 0 | konteyner 0, volume 0 |

Backend r2'de değişmedi (make test/test-int r1 sonuçları geçerli; NOT_RUN r2). Önceki "tek seferde 74/74 kanıtı yok" riski bu koşuyla kapandı: tek worker'da tam takım tek seferde yeşil.
