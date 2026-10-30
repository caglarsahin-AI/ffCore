# PR: fix/04a-06a-followups (FOLLOWUP-105, 108, 101)

**Paket:** fix/04a-06a-followups · **Sınıf:** [A] · **Branch:** fix/04a-06a-followups · **Baz commit:** c8650cb · **Oturum:** ffcore-isci-a-af · **GOREV:** K-AF-0001

## Plan (kodlamadan önce)

1. **Bulunan semboller ve dosyalar** (worktree c8650cb, rg ile):
   - 105: `backend/ffcore/runtime/definition.py` `_fail(code, message)` → `ValueError(f"{code}: {message}")`; `AgentDefinition._consistent` (`model_validator(mode="after")`) → `check_definition`. Tanım istek gövdesinde (`api/agents_schemas.py:67,79` `definition: AgentDefinition`) doğrulandığı için hata `RequestValidationError` olur; `core/errors.py` `_validation_error` yalnız alan yollarını yazar → `422 validation_error`, kod kaybolur. `docs/agentlar.md:14,28` "refused at save (`variable_undefined`)" vaadi; önyüz `frontend/lib/api/errors.ts:48` `variable_undefined` eşlemesi hazır; `frontend/tests/e2e/test_10bp2_3_agent_wizard_lifecycle.spec.ts:45` soft-expect.
   - 108: `backend/ffcore/knowledge/chunking.py` `_ARTICLE` + `_article_sections`: düz metinde "Madde N - …" satırının **tamamı** (alt madde numarası yoksa satır sonuna kadar, `[:80]`) başlık olur → `crumb = "<KB> › <dosya> › <satır>"` → `TextChunk.breadcrumb` ve `section_path` → `chunks.breadcrumb` → arama → `runtime/prompting.py` `Source.public()` → `sources` olayı (`run_events.payload.selected[].breadcrumb`). Belge silme `api/knowledge.py` `delete_document`: `deleted_at` + chunk silme; koşu olayı değişmez. Olay okuma: `api/runs.py` `list_run_events` ve `_replay_rows` (Postgres'ten SSE tekrar oynatma).
   - 101: `models/knowledge.py:141` `Document.updated_at_source` kolonu var; `knowledge/search.py` `by_recency` sıralaması kullanıyor; **hiçbir yazma yolu set etmiyor**: `upload_documents` (`api/knowledge.py:342`) alan almıyor, `ingest_from_raw` (C6) `metadata["updated_at_source"]`'u kolona değil `document.meta`'ya yazıyor (aynı kusurun ikinci yolu). Belge için PATCH ucu yok (yalnız KB PATCH). `tests/e2e/scenarios/test_18_f11_f13_content.py:65` `test_18_f13_3` FOLLOWUP-101 skip'i; `seed.py` `seed_kb` alanı göndermiyor; `data/samples/versions/expected.json` `v2_effective_date: 2025-09-01` (v1 tarihi yok).

2. **Kapsam / kapsam dışı:** Kapsam: üç FOLLOWUP, ilgili docs ve OpenAPI (04a.yaml, 06a.yaml gerekiyorsa) dışa aktarımları, F13 seed alanı + skip kaldırma. Kapsam dışı: LangGraph checkpoint'inde kaynak metni (`graph.py` `_source_payload` `text` taşır; silme sonrası checkpoint'te kalır; ayrı retention konusu, KAYIT-TALEBI ile FOLLOWUP önereceğim), Redis Stream'in TTL içindeki canlı tekrar oynatması (maskelenmez; yeni breadcrumb zaten yapısal), eski indekslenmiş belgelerin breadcrumb'ı (yeniden indekslemeyle güncellenir, migration yok).

3. **Değişecek dosyalar ve neden** (üç dilim, ayrı commit, her biri önce kırmızı test):
   - **Dilim 1 (105):** `runtime/definition.py`: `DefinitionError(ValueError)` (`code`, `message`); `_fail` bunu atar (önek metni korunur, additive). `core/errors.py` `_validation_error`: hataların `ctx["error"]`'ı `DefinitionError` ise `422 invalid_request_error` + o `code`, mesaj `"<alan yolu>: <message>"`; diğer doğrulama hataları aynen `validation_error`. Önek ayrıştırma yok (tipli istisna, ARCH-10). `docs/agentlar.md` hata kodu satırı; `docs/api.md` 422 notu.
   - **Dilim 2 (108):** `knowledge/chunking.py`: başlık kuralı tek fonksiyonda (`structural_heading`): madde başlığı `Madde N` + (varsa) `- Başlık`; başlık `:` öncesinde kesilir ("Madde 2 - Süre: metin…" → "Madde 2 - Süre"); sonuç > 60 karakterse yalnız `Madde N`. Markdown başlığı ≤ 60 karakterse aynen, uzunsa baştaki bölüm numarası (`3.2`) varsa o, yoksa başlık breadcrumb'a girmez (gövdede kalır; sessiz kırpma değil, yazılı kural). `api/runs.py`: `sources` olaylarını dönerken (`list_run_events`, `_replay_rows`) payload'daki `document_id`'lerden canlı olmayanların (`deleted_at` dolu ya da satır yok) `breadcrumb`'ı `"[deleted]"` olur (bkz. S2); DB'deki olay değişmez (append-only). `docs/bilgi-tabani.md` "Chunking", `docs/agentlar.md` sources notu.
   - **Dilim 3 (101):** `api/knowledge.py` `upload_documents`: isteğe bağlı `updated_at_source: datetime | None` form alanı (istekteki tüm dosyalara); `ingest.register_upload`'a geçer. Yeni `PATCH /projects/{p}/knowledge-bases/{kb}/documents/{doc}` (`Editor`, `@audited("update_document", …)`, gövde `{updated_at_source: datetime | null}`, ACL'siz/ silinmiş belge 404). `knowledge/ingest.py` `ingest_from_raw`: `metadata["updated_at_source"]` kolona da yazılır (C6 metadata anahtarı zaten belgeli, davranış düzeltmesi). `openapi/04a.yaml` yeniden üretilir. `tests/e2e/scenarios/seed.py` versions KB'sinde v2'ye `v2_effective_date`; `test_18_f13_3` skip kaldırılır. `docs/bilgi-tabani.md`, `docs/api.md`.

4. **Sözleşme, yapılandırma, profil etkisi:** C8 additive (yeni hata kodları yanıta çıkar; tanım alanları değişmez). C9 değişmez (olay tipi yok; `sources` payload alanı aynı, değer maskesi). C5/C6 imzası değişmez (C6 metadata anahtarı zaten vardı). Yeni ortam değişkeni yok; profil farkı yok, testler iki profille.

5. **Kabul kriteri → test adı:**
   | # | Kriter | Test |
   |---|---|---|
   | 1 | Tanım hatası 422 `invalid_request_error` + kendi kodu (`variable_undefined`, `knowledge_duplicate`, `approval_action_unknown`, `verify_not_supported`, …), alan yolu mesajda | `tests/unit/test_af_1_definition_error_codes.py` (her `_fail` kodu parametrik, gerçek app + TestClient) |
   | 1b | Tanım dışı doğrulama hataları `validation_error` kalır (gerileme yok) | aynı dosya `test_af_1b_other_validation_unchanged` |
   | 2 | Düz metin madde satırı breadcrumb'a girmez; `Madde N - Kısa başlık` ≤ 60; uzun markdown başlığı kuralı | `tests/unit/test_af_2_structural_breadcrumb.py` (F10_7'nin `_procedure` metniyle) |
   | 2b | Silinen belgenin `sources` referansı kalır, `breadcrumb == "[deleted]"`, `document_name` kalır | `tests/integration/test_af_2b_deleted_source_breadcrumb.py` (+ e2e `test_18_f10_7` yığında) |
   | 3 | Yükleme `updated_at_source` form alanını belgeye yazar; yoksa NULL | `tests/integration/test_af_3_upload_updated_at_source.py` |
   | 3b | PATCH ile değişir, audit olayı düşer, `access=read` 403, ACL dışı 404 | aynı dosya |
   | 3c | `ingest_from_raw` metadata tarihini kolona yazar | `tests/integration/test_af_3c_ingest_from_raw_date.py` |
   | 3d | F13: v2 v1'den önce listelenir | `test_18_f13_3_newest_version_listed_first` (yığında, skip kalkar) |
   | 4 | OpenAPI dışa aktarımı commit'lenmiş dosyayla eşit | mevcut `test_04a_openapi`, `test_06a_openapi` |

6. **Migration:** yok (kolon var).
7. **Geri alma:** commit başına revert; veri değişikliği yok (PATCH yalnız kolon). Eski indeks breadcrumb'ları yeniden indekslemeye kadar eski kalır.
8. **Durma koşulları:** `RequestValidationError.errors()` `ctx["error"]` istisna örneğini taşımıyorsa (pydantic sürümü) → koda dayalı alternatif için koordinatöre; chunking değişikliği 13a/04a kalite testlerinde (parça sayısı/ölçüm) gerileme yaparsa; `test_10bp2_3` yeşillenmezse önyüz tarafı (touch-zone dışı) için KAYIT-TALEBI.
9. **Felsefe kontrolü:** ARCH-07: üç dar düzeltme, kalıcı karmaşıklık: bir istisna sınıfı, bir başlık fonksiyonu, bir PATCH ucu; değer: C8 vaadi, silme/saklama vaadi, F13 sıralaması. ARCH-09: Pydantic'in istisna bağlamı kullanılır, ayrı doğrulama katmanı yok; Postgres zaten `updated_at_source` sıralıyor. ARCH-10/06: tarih yoksa **gizli varsayılan yok** (S1); başlık kısaltma kuralı yazılı ve testli; maskeleme açık işaretli değer, sessiz silme değil.

## Koordinatör görüşü isteyen iki nokta (META-01)

**S1. "Yoksa dosya mtime'ı" (FOLLOWUP-101 kararı).** HTTP multipart yüklemede istemci dosyanın mtime'ını göndermez; sunucudaki tek "mtime" yükleme anıdır. Bunu `updated_at_source` diye yazmak, belge sürümü tarihini sessizce yükleme tarihiyle değiştirir (ARCH-10/06).
- **A (önerilen):** form alanı isteğe bağlı; yoksa NULL (prompt "unknown date" yazıyor, `by_recency` NULL'ları sona koyuyor). Tarih PATCH ile sonradan verilir; `ingest_from_raw` (16) kaynağın tarihini metadata'dan zaten verir. Bedel: elle yüklenen belge tarih girilmezse sıralamada sona düşer, ekranda "tarih yok" görünür.
- **B:** yoksa yükleme anı, belge `meta.updated_at_source_origin = "upload"` işaretli. Bedel: iki anlamlı tarih tek kolonda; sürüm sıralaması yükleme sırasına bağlanır.
- **C:** alan zorunlu. Bedel: her yükleme formu ve seed değişir; tarihi bilinmeyen belgeye uydurma tarih yazdırır.

**S2. `[silindi]` işaretinin dili.** Karar metni `[silindi]` diyor; işaret API yanıtındaki veri değeri ve ürün dili kararı API metinlerini İngilizce yapıyor (KARARLAR 28 Ekim).
- **A (önerilen):** `"[deleted]"` sabiti (önyüz isterse çevirir). Bedel: karar metniyle harfiyen aynı değil.
- **B:** `"[silindi]"` aynen. Bedel: İngilizce API'de tek Türkçe değer.
- **C:** breadcrumb `null` + `document_deleted: true` alanı (additive). Bedel: şema değişikliği, önyüz eşlemesi gerekir.

**Plan onayı (K-AF-0002):** S1 **A** (tarih yoksa NULL; yükleme anı asla yerine yazılmaz; PATCH ile verilir). S2 **A** (`"[deleted]"`; önyüz çevirisi FOLLOWUP-112 ile).

## Durum
HEAD **06de43294432a8f7a666f1ededb5fb036190eb20** (c8650cb üstüne 4 commit, push yok):
- 7a982c8 `fix(06a): answer definition refusals with their own code` (dilim 1, FOLLOWUP-105)
- 027230e `fix(04a): keep run sources to structure, mask deleted documents` (dilim 2, FOLLOWUP-108)
- 62818ff `fix(04a): take the source date from the upload or a PATCH` (dilim 3, FOLLOWUP-101)
- 06de432 `test(04a): classify the source date and contract the document PATCH` (dilim 3'ün iki sınıflandırma kapısı)

## Değişen dosyalar
- **Kod:** `backend/ffcore/runtime/definition.py` (`DefinitionError`), `backend/ffcore/core/errors.py` (`_coded`: kodlu ret → 422 `invalid_request_error` + kod), `backend/ffcore/knowledge/chunking.py` (`structural_heading`, `MAX_HEADING_CHARS = 60`), `backend/ffcore/api/runs.py` (`_mask_deleted_sources`, `DELETED_BREADCRUMB`; `list_run_events` ve `_replay_rows`), `backend/ffcore/api/knowledge.py` (yükleme `updated_at_source` form alanı; `PATCH …/documents/{document_id}` `update_document`; `DocumentOut.updated_at_source`), `backend/ffcore/api/knowledge_schemas.py` (`DocumentUpdate`, alan), `backend/ffcore/knowledge/ingest.py` (`ingest_from_raw` tarihi kolona yazar, `_source_date`).
- **Sözleşme dışa aktarımı:** `backend/openapi/04a.yaml` (yeniden üretildi; additive: alan + PATCH); `frontend/lib/api/schema-04a.d.ts` (openapi-typescript çıktısı, elle düzenleme yok; önyüz `check:api` için). `06a.yaml` bayt aynı.
- **Yeni testler:** `tests/unit/test_af_1_definition_error_codes.py`, `tests/unit/test_af_2_structural_breadcrumb.py`, `tests/integration/test_af_2b_deleted_source_breadcrumb.py`, `tests/integration/test_af_3_updated_at_source.py`.
- **Uyarlanan testler (gevşetme yok):** `tests/integration/test_04a_review_r1_ingest.py` `test_04a_r1_4` (uzun başlık artık breadcrumb'a girmediği için `chunk_breadcrumb_too_long` koruması uzun KB adıyla tetikleniyor); `tests/integration/test_04a_api.py` üç audit sayımına `project=` filtresi (paylaşımlı DB'de yeni testlerin satırları da sayılıyordu; 03anm'deki aynı düzeltme); `tests/unit/test_04a_review_r1_audit_fields.py` (`updated_at_source` güvenli alan: tarih, içerik yok); `tests/contract/test_04a_openapi.py` (belge yoluna `patch`).
- **e2e:** `tests/e2e/scenarios/seed.py` (`seed_kb` isteğe bağlı kaynak tarihi; v2'ye `v2_effective_date`, v1 tarihsiz), `tests/e2e/scenarios/test_18_f11_f13_content.py` (`test_18_f13_3` FOLLOWUP-101 skip'i kaldırıldı).
- **Belgeler:** `docs/agentlar.md` (tanım hata kodları; `sources` olayı ve `[deleted]`), `docs/api.md` (422 kodlu ret; yükleme alanı; belge PATCH), `docs/bilgi-tabani.md` (breadcrumb yapısal kuralı; kaynak tarihi ve `by_recency`).

## Kabul kriterleri → testler
| # | Kriter | Test | Kırmızı (önce) | Durum |
|---|---|---|---|---|
| 1 | Tanım hatası 422 `invalid_request_error` + kendi kodu, mesajda alan yolu (11 kod) | `test_af_1_definition_error_codes[*]` | 11 failed (`validation_error`), `af1-kirmizi.log` | geçti |
| 1b | Tür ya da bilinmeyen alan hatası `validation_error` kalır | `test_af_1b_other_validation_unchanged` | kırmızıda da geçti (gerileme koruması) | geçti |
| 2 | Düz metin madde satırı breadcrumb/section_path'e girmez; kural tablosu | `test_af_2_*` (9) | 9 failed, `af2-kirmizi.log` (kelime breadcrumb'da) | geçti |
| 2b | Silinen belge: referans kalır, breadcrumb `[deleted]`; olay listesi ve DB'den tekrar oynatma | `test_af_2b_deleted_source_breadcrumb` | 1 failed, `af2b-kirmizi.log` (runs.py HEAD sürümüyle) | geçti |
| 2c | e2e F10_7: silinen kaynağın metni koşu kaydında yok | `test_18_f10_7_deleted_source_keeps_reference_without_content` | bilinen kırmızı (T-18-0045) | geçti (yığında) |
| 3 | Yükleme form alanı kolona yazılır; yoksa NULL; geçersiz tarih 422 | `test_af_3_upload_sets_updated_at_source` | failed (`KeyError`), `af3-kirmizi.log` | geçti |
| 3b | PATCH değiştirir ve temizler; audit `update_document` güvenli alanlarla; `access=read` 403; proje dışı 404; bilinmeyen alan 422 | `test_af_3b_patch_updated_at_source` | failed (405) | geçti |
| 3c | `ingest_from_raw` metadata tarihini kolona yazar | `test_af_3c_ingest_from_raw_writes_the_date` | failed (NULL) | geçti |
| 3d | e2e F13: v2 v1'den önce | `test_18_f13_3_newest_version_listed_first[SZL-2025-003, SZL-2025-007]` | skip'liydi (FOLLOWUP-101) | geçti (yığında) |
| 4 | OpenAPI dışa aktarımı commit'lenmiş dosyayla eşit | `test_04a_openapi`, `test_06a_openapi` | — | geçti |
| — | Önyüz sihirbaz kaydında `variable_undefined` görünür | `test_10bp2_3_agent_wizard_lifecycle` (Playwright) | — | **NOT_RUN**: yığının e2e servisi boş `e2e_node_modules` volume'una `npm ci` ile ağdan indirir; yapmadım. Backend sözleşmesi (`error.code`) birim testiyle kanıtlı, önyüz eşlemesi `frontend/lib/api/errors.ts:48`'de hazır. İnceleyici yığınında ya da koordinatör kapısında koşulmalı |

## Çalıştırılan komutlar
Hepsi `tools` konteynerinde, `MSYS_NO_PATHCONV=1 FFCORE_VERSION=0.0.0-af`; yığın `ffcore-af` (`--env-file .env.test`, `--profile test --profile qdrant`, 18030/13030, `up -d --wait --pull never` 94 s). İmajlar: `ffcore/{tools,frontend}:0.0.0-af` = `0.0.0-main` etiketi; e2e için `ffcore/backend:0.0.0-af` = `0.0.0-main` + `COPY backend/ffcore /app/ffcore` (`docker build --network none`; bağımlılık ve migration değişmedi). Çıktılar `state/pr/04a-06a-followups-kapilar/` (tee).

| Komut | HEAD | Exit | Sonuç | Dosya |
|---|---|---|---|---|
| `make lint` | 06de432 | 0 | ruff check + format temiz (15 s) | `lint.txt` |
| `make test` llmaas | 06de432 | 0 | 719 passed (142 s) | `test-llmaas.txt` |
| `make test` airgap | 06de432 | 0 | 719 passed (137 s) | `test-airgap.txt` |
| `make test` ilk | 62818ff | 2 | 717 passed, 2 failed: iki sınıflandırma kapısı (yeni alan, yeni PATCH) → 06de432 | özet burada (dosya üzerine yazıldı) |
| `make test-int` | 06de432 | 0 | 525 passed, 4 skipped (opt-in), 482 s | `test-int.txt` |
| seed (`python -m tests.e2e.scenarios.seed`, `e2e.env` örtüsü; parolalar kabukta üretildi, dosyaya yazılmadı) | 06de432 | 0 | 2 proje, 4 model, agent'lar | `e2e-seed.txt` |
| `pytest tests/e2e/scenarios -v -rs` (`RUN_E2E_SCENARIOS=1`) | 06de432 | 0 | 36 passed, 22 skipped (NOT_RUN gerekçeli); F10 4/4, F13 2 geçti + 2 gerçek model | `e2e-scenarios.txt` |
| `npx openapi-typescript ../backend/openapi/04a.yaml` + `npm run check:api` (`node:20.19.5-alpine`, `ffcore-10a-nm`, `--network none`) | 62818ff | 1 | 04a temiz; **05a sapması main'de** (kalan riskler) | — |
| `down -v` | — | 0 | konteyner 0, volume 0 | kanal YIGIN-KAPA |

## Çıktı özeti ve post-state
Migration yok; yeni tablo ya da kolon yok. `backend/openapi/04a.yaml` +109 satır (alan + PATCH). Yığın kapalı. Yerelde `ffcore/{backend,tools,frontend}:0.0.0-af` etiketleri kaldı (silinebilir; backend olan yalnız küçük bir kod katmanı).

## Kontrol listesi
- [x] Felsefe ile çelişen nokta işaretlendi (S1 mtime, S2 dil; K-AF-0002 ile kapandı)
- [x] Donmuş sözleşme kırılmadı: C8 additive (kodlar yanıta çıktı, alanlar aynı), C9 aynı (yeni olay tipi ya da alan yok), C5/C6 imzası aynı
- [x] İki profil testi koştu
- [x] Yeni mutasyon ucu audit üretiyor (`update_document`, güvenli alanlar); salt-okunur 403
- [x] Log, API, audit, hata gövdesi secret-free; parolalar dosyaya yazılmadı
- [ ] Önyüz: yalnız üretilmiş tip dosyası değişti; Playwright NOT_RUN (yukarıda)
- [x] Docs güncel; `.env.example` değişmedi (yeni değişken yok)
- [x] WORK_QUEUE durumu kanal üzerinden

## Varsayımlar ve brief'teki çelişkiler
- FOLLOWUP-101 "yoksa dosya mtime" HTTP yüklemesinde karşılıksız; K-AF-0002 S1 A: NULL.
- FOLLOWUP-108 `[silindi]` → `[deleted]` (K-AF-0002 S2 A).
- `ingest_from_raw` tarihi kolona yazmıyordu (aynı kusurun C6 yolu); düzeltildi, metadata kopyası da kalır. Geçersiz tarih `ValueError` ile durur, belge tahmini tarihle kaydedilmez.
- Yükleme alanı istekteki tüm dosyalara uygulanır (dosya başına farklı tarih için ayrı istek ya da PATCH).
- Aynı bayt (`unchanged`) yeniden yüklemede tarih verilirse belgeye yazılır (tarih düzeltmenin ikinci yolu).
- Breadcrumb kuralı: madde başlığı ilk `:`'ya kadar; 60 karakteri aşarsa yalnız numara; numarasız uzun Markdown başlığı breadcrumb'a girmez (gövdede kalır). Birleşen en çok 3 başlığın her biri ayrı ayrı ≤ 60.
- `[deleted]` maskesi yalnız okuma yollarında (olay listesi, DB'den tekrar oynatma); DB'deki append-only olay değişmez. Belge satırı hiç yoksa da silinmiş sayılır.
- Kırmızı testler düzeltmeyle aynı commit'te; kırmızı kanıtlar `*-kirmizi.log` dosyalarında.

## Kalan riskler
- **main'de önyüz `check:api` kırmızı (bu daldan önce):** `frontend/lib/api/schema-05a.d.ts`, `backend/openapi/05a.yaml`'ın openapi-typescript çıktısı değil; 05a.yaml a795d9d'de (fix/05a-tools-read-analyst) değişmiş, tipler yeniden üretilmemiş. Bu dalda dokunulmadı (KAYIT-TALEBI A-af-0007).
- **isci-b fix/07-followups da `api/runs.py`'yi değiştiriyor** (K-07F-0005): ikinci merge edilen dal metin çakışması alabilir. Bu dalın değişikliği: yeni `_mask_deleted_sources` yardımcısı, `_replay_rows` döngüsü ve `list_run_events` gövdesi.
- LangGraph checkpoint'i kaynak parça metnini taşıyor (`runtime/graph.py` `_source_payload` `text`); belge silinince checkpoint'te kalır (KAYIT-TALEBI A-af-0007).
- Redis Stream'in TTL içindeki canlı tekrar oynatması maskelenmez (yeni breadcrumb yapısal olduğu için içerik taşımaz).
- Eski indekslenmiş belgelerin breadcrumb'ları yeniden indekslemeye kadar eski kuralla kalır; yeniden indekslemede gömülen metin değişir, vektörler yeniden hesaplanır.
- `test_10bp2_3` önyüz kanıtı NOT_RUN.
