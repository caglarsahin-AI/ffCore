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

Cevap gelene kadar dilim 1 (105) bu iki noktaya bağlı değil; onay gelirse oradan başlarım.

## Değişen dosyalar
(kodlama sonrası)

## Kabul kriterleri → testler
(kodlama sonrası; tablo plan 5'te)

## Çalıştırılan komutlar
(kodlama sonrası)

## Varsayımlar ve brief'teki çelişkiler
- FOLLOWUP-101 "dosya mtime" ifadesi HTTP yüklemesinde karşılıksız (S1).
- FOLLOWUP-108 "`[silindi]`" ürün dili kararıyla çelişiyor (S2).
- `ingest_from_raw`'ın `updated_at_source`'u kolona yazmaması aynı kusurun ikinci yolu; düzeltmeyi bu PR'a aldım (aynı FOLLOWUP, aynı kolon).

## Kalan riskler
- LangGraph checkpoint'i kaynak parça metnini taşıyor (`graph.py` `_source_payload`); belge silinince orada kalır (FOLLOWUP önerisi).
- Yeni breadcrumb kuralı yeniden indekslenen belgelerde parça sınırlarını değiştirmez ama gömülen metni değiştirir (vektörler yeniden hesaplanır).
