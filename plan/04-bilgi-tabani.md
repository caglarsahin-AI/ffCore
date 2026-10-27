# 04. Bilgi tabanı: ingest, chunk, yerel embedding, pgvector arama, erişim kontrolü [FFCore Knowledge]

**Bağımlılık:** 00i, 03a, 01; örnek veri 13a'dan. **Süre:** 9,5 gün, iki alt paket ve iki PR (04a 5,5, 04b 4; inceleme v9). **Dalga:** 04a dalga 3, 04b PoC sonrası. **PoC:** 04a, PayCore'un çalışan ingest/RAG kodunu **sararak** (ARCH-09; PLAN 2d).

**04a, çekirdek (≈5,5 gün, kritik yol, M3 öncesi zorunlu):** **PayCore entegrasyonu (v9 P3):** PayCore'un `ingest/` (kapılar, dönüşüm, chunk, breadcrumb, hash sahipliği, güncellik) ve `rag/` (dense+sparse embedding, Qdrant hibrit, reranker) kodu **yeniden yazılmaz**; `backend/app/knowledge/store.py` `KnowledgeStore` bağdaştırıcısı DuckDB + silver dosyalarını sarar, FFCore'un `knowledge_bases`, ACL ve proje meta verisi Postgres'tedir; `chunks`/`documents` Postgres tabloları PoC'de yalnızca ACL/metadata için (tam göç 04b). Bu listeden PayCore'da zaten olanlar bağdaştırıcıdan geçer, olmayanlar (elle yükleme yolu, ACL payload, yönetim/arama API'si, `kb_queries`, warmup, `to_thread` kilidi 00i'den) yazılır. Orijinal kapsam: veri modeli (tam), üç katmanlı depo, pipeline adımları 1-9 (video hariç), kalite kapıları 1-2 ve veri dökümü tespiti, Kapı 0'ın elle yükleme kısmı, breadcrumb, karakter tabanlı parça sınırı, embedding ve vektör yeniden kullanımı, `PgVectorStore`, hibrit arama, normalizer biçim temizliği, reranker ve rerank tabanı, tek eşik kuralı, ACL ve on-behalf-of, yönetim API'si, `ingest_from_raw` giriş noktası, `kb_queries` tablosu (`run_id` ve `candidates` ile, C12; ekransız), `warmup` görevi ve `/readyz` (00'dan taşındı), boş ACL kuralı (C15). Kabul kriterleri: Qdrant ve `migrate-vectors` dışındakiler.
**04b, genişletme (≈4 gün, PoC sonrası):** DuckDB → Postgres belge deposu göçü (`DEBT-1`), `PgVectorStore` tam eşdeğerlik ve `migrate-vectors`, hedefli yeniden dönüştürme presetleri (pipeline adım 10), video dönüşümü (`VIDEO_TRANSCRIPT_ENABLED`), `TEXT_NORMALIZE_TR` katmanı (varsayılan kapalı), çok biçimli sorgu (`rewrite`), embedding modeline göre eşik tablosu ve öneri, Türkçe embedding karşılaştırması, ingest raporu görünümü (`ingest_gate_stats`) ve 10'daki ekran verileri. Kabul kriterleri: Qdrant, `migrate-vectors`, K1 normalizer, video_disabled raporu.

## Amaç

Sözleşme ve prosedür belgelerinin yüklenip aranabilir hale gelmesi; belge hiç dışarı çıkmadan (yerel embedding). Arama API'si 05'teki mcp-search ve 06'daki runtime tarafından kullanılır.

## Kapsam

### Veri modeli

- `knowledge_bases(id, project_id, key, name, description, embed_model, embed_dim, chunk_size, chunk_overlap, status)`. (P5 kararı) **Kurulum başına tek embedding modeli:** `EMBED_DIM` ve `EMBED_MODEL` global; `knowledge_bases.embed_model/embed_dim` yalnızca kayıt amaçlıdır ve globalle eşleşmek zorundadır (farklı seçim 400). pgvector'de tek `chunks.embedding vector(EMBED_DIM)` kolonu; Qdrant sürücüsünde de aynı kural (koleksiyon başına farklı boyut bu sürümde kullanılmaz). Embedding modeli değişimi = tüm KB'lerin gold katmanı yeniden üretimi (`make reindex LAYER=gold --full`, D3 ile silver'dan, kaynağa gitmeden). 03a'daki `models.embed_dim` ölçümü globalle uyuşmazsa model kaydı 400 `embedding_dimension_mismatch` döner ve model aktive edilmez (C7). 14 (hafıza) aynı modeli ve boyutu kullanır.
- `documents(id, kb_id, filename, mime_sniffed, size, sha256, raw_path, silver_path, status: pending|converting|gated|chunking|embedding|indexed|skipped|failed|timeout, error, page_count, acl_roles[], acl_users[], metadata jsonb, version, source_item_id nullable, breadcrumb, updated_at_source, language, text_hash, duplicate_of nullable, gate0_status, gate0_reason, gate1_status, gate1_reason, gate2_status, gate2_reason, convert_engine, convert_seconds)` (PayCore düzeltmesi D1, D2, D3)
- `attachments(id, document_id, filename, mime_sniffed, size, raw_path, silver_path, gate0_status, gate0_reason, gate2_status, gate2_reason, convert_engine, convert_seconds, shared_from nullable)`: belgenin ekleri (16'daki Confluence/Jira ekleri ve elle yüklenen zip dışı çoklu dosyalar); ek metni belgenin silver'ına `Ek: <dosya adı>` breadcrumb'ıyla girer. (PayCore düzeltmesi D1, D2)
- `chunks(id, document_id, kb_id, ordinal, text, token_count, char_count, page, section_path, breadcrumb, embedding vector(EMBED_DIM), embedding_model, tsv tsvector, chunk_status: ok|flagged|skipped, chunk_reason, text_hash)`; HNSW indeks (cosine) ve GIN indeks (tsv, Türkçe yapılandırma). Arama yalnızca `ok` ve `flagged` parçaları görür. (PayCore düzeltmesi D1, D3, D5)
- `ingest_gate_stats` görünümü: kaynak × kapı × gerekçe sayımı (rapor ekranı için). (PayCore düzeltmesi D1)

### Üç katmanlı bilgi deposu (PayCore düzeltmesi D3)

Data lake'teki bronze/silver/gold ile aynı disiplin; her katmanın kendi ilerleme işareti vardır, biri bitmeden sonraki koşmaz.

| Katman | Yol | İçerik | Yeniden üretim |
|---|---|---|---|
| **raw** | `data/storage/raw/{project}/{kb}/{source}/{id}/` | Kaynaktan gelen ham veri birebir: yüklenen dosya, 16'da API cevabı JSON'u ve ek dosyası | Yalnızca kaynak değişince; kaynağa tek gidiş burası |
| **silver** | `data/storage/silver/.../{id}.md` + frontmatter | Dönüştürülmüş ve kapılardan geçmiş Markdown; frontmatter: breadcrumb, tarih, ACL, kapı kararları, dönüştürücü, dil; yanında `text_raw` (normalize edilmemiş dönüşüm çıktısı) | Dönüştürücü, normalizer ya da kapı kuralı değişince raw'dan; OCR/Whisper `text_raw` varsa yeniden koşmaz |
| **gold** | Postgres `chunks` + vektör deposu | Parçalar, vektörler, BM25 | Parçalama ya da embedding modeli değişince silver'dan |

- Komutlar: `make reindex KB=<key> LAYER=silver|gold [--full]`. `LAYER=gold --full` kaynağa hiç gitmez. Metni (breadcrumb dahil) birebir aynı kalan parçanın vektörü yeni kimliğine taşınır (`text_hash` + `embedding_model` eşleşirse); model farklıysa yeniden hesaplanır. Log `reused=N embedded=M`.
- Bilerek reddedilen: raw'ı atlayıp yalnızca Markdown saklamak; dönüştürücü hatası bulununca düzeltme ancak yeniden çekimle mümkün olurdu.

### Pipeline (Redis kuyruğu + worker süreci, yalnızca `arq`, kuyruk `ingest`; B4)

1. **Dosya alma:** `POST /kb/{id}/documents` (multipart, çoklu dosya); dosya raw'a; sha256 ile tekrar yükleme tespiti. Elle yüklemede Kapı 0 yalnızca boyut ve biçim kapsamı uygular (bkz. kalite kapıları).
2. **Biçim yönlendirme ilk baytlarla, uzantıyla değil** (PayCore düzeltmesi D2): `sniff()` MIME'ı içerikten belirler (`documents.mime_sniffed`). MHTML (`MIME-Version` + `multipart/related`, çoğu zaman `.doc` uzantılı Word "Tek Dosya Web Sayfası") tanınır, yalnızca HTML parçası (BOM'lu UTF-16 olabilir) çözülüp Docling'e verilir; ham MIME asla metin sayılmaz.
3. **Kodlama tespiti** (PayCore düzeltmesi D2): düz metin, e-posta gövdesi ve diyagram önce UTF-8, olmazsa cp1254 ile okunur; `errors="replace"` kullanılmaz (Türkçe harfleri kalıcı siler).
4. **Metne çevirme** (PayCore düzeltmesi D2): Docling (PDF, DOCX, PPTX, HTML, Markdown) -> Markdown; OCR motoru **PaddleOCR `tr`** (PayCore kararı 21 Eylül; Tesseract değil); başlık hiyerarşisi ve tablolar korunur. Kapsam ekleri: eski Office (`.doc .ppt .vsd`) LibreOffice ile; e-posta (`.msg` extract-msg, `.eml` stdlib; HTML gövde görünür metne); draw.io/`.vsdx` stdlib XML; video (`.mp4`, `.m4a`) ffmpeg + faster-whisper (dil `tr`, VAD açık) **`VIDEO_TRANSCRIPT_ENABLED` ile, varsayılan kapalı, M3 sonrası**; kapalıyken video ekleri sessizce düşmez, Kapı 0'da `skipped/video_disabled` gerekçesiyle kaydedilir ve raporda sayılır (açılınca hedefli yeniden dönüştürme ile işlenir). **PDF:** metin katmanı olan PDF asla OCR'a girmez (Docling -> `pymupdf4llm` -> düz metin sırası); yalnızca taranmış PDF Tesseract'a (`tur+eng`) gider, `OCR_PDF_MAX_PAGES` sınırıyla; log'da `convert_engine` görünür.
5. **Her dosya ayrı süreçte, süre sınırıyla** (PayCore düzeltmesi D2): kalıcı işçi süreç havuzu (her süreç kendi Docling kopyasını yükler; bellek bütçesine yazılır); `CONVERT_TIMEOUT_SECONDS` (600, video 3600) dolunca süreç öldürülür, kayıt `timeout` alır, diğer dosyalar devam eder, düz koşuda tekrar denenmez. Eski `.doc`'ta Docling bitmezse LibreOffice düz metni yedek.
6. **Kalite kapıları** (aşağıda) ve silver yazımı; sorgu ile aynı normalizer.
7. **Parçalama:** başlık-duyarlı, hedef 400 token, overlap 60; madde numaraları (`Madde 7`, `7.1`) parça başında tekrar edilir; tablo parçalanmaz. **Breadcrumb embed edilen metnin başında** (PayCore düzeltmesi D5): `Bilgi tabanı › klasör/üst sayfalar › Belge › Bölüm` (16'da `Space › üst sayfalar › Sayfa › Başlık`; Jira'da issue başlığı; ekte üst kayıt + `Ek: <dosya adı>`); `section_path` ayrıca saklanır. Varsayılan açık; contextual headers (parça başına model çağrısı) seçenek olarak kalır, varsayılan kapalı. **Parça boyutu karakterle de sınırlanır** (PayCore düzeltmesi D2): token tahmini `max(kelime × 1,6, karakter / 6)`; boşluksuz uzun dizi uzunluğuna göre kesilir; hiçbir parça `chunk_max_tokens × 6` karakteri aşmaz (R3.4: `chunk_max_tokens = knowledge_bases.chunk_size × 1,28`, hedef 400 → üst sınır 512; `chunk_size` hedef, `chunk_max_tokens` türetilmiş üst sınırdır). Türkçe %30-40 fazla token üretir; sınırlar buna göre (PayCore CLAUDE.md).
8. **Embedding:** **süreç içi** `BGEM3FlagModel` (`FlagEmbedding`), dense + sparse (`lexical_weights`), 32'lik batch; `chunks.embedding_model` yazılır; vektör yeniden kullanımı (D3). İlerleme `documents.status` ve Redis'te yüzde olarak. (C10 tersine, PLAN 2d: Ollama sparse üretmez; PayCore `rag/embed.py` yeniden kullanılır.) Model nesnesini **yalnızca API süreci** yükler; ingest worker'ı embedding'i API'nin iç ucundan (`POST /internal/embed`, `SERVICE_TOKEN`) alır. `embedding_truncated` durumu sessiz uyarı değil `chunk_status=flagged` + gerekçe. **CPU yoğun işler (embedding, reranker) async API'nin olay döngüsünde çalıştırılmaz** (PayCore düzeltmesi D6): iş parçacığı havuzunda, model başına kilitle; aksi halde bir isteğin rerank'i diğer tüm istekleri dondurur.
9. **Yazma:** chunks tablosu; belge sürümü artarsa eski parçalar silinir (vektör taşıma kuralıyla).
10. **Hedefli yeniden dönüştürme** (PayCore düzeltmesi D2, M3 sonrası): `make reconvert KB=<key> PRESET=encoding|timeout|mhtml|engine:<ad>`; yalnızca ilgili sorunun vurduğu dosyalar seçilip raw'dan yeniden dönüştürülür.

### Kalite kapıları (PayCore düzeltmesi D1)

Üç kapı, her biri kendi kolonunda; biri diğerinin kararını geri almaz. Hiçbir şey sessizce atılmaz: her eleme `gate*_status` (`ok|flagged|skipped`) ve `gate*_reason` ile kaydedilir; `documents.status` kapı kararlarından türetilir.

- **Kapı 0, ek kabulü (indirmeden/dönüştürmeden önce; 16'da indirmeden önce):** metni olmayan ikili (`apk exe dll ...`); kapsam dışı biçim: arşiv, Excel/CSV (tablo soruları text-to-SQL'in işi), `.sql`, **görsel ekler** (PayCore: 1.434 PNG'nin OCR'ı 46 kullanılabilir parça üretti); tarih sınırı (`ATTACHMENT_MIN_DATE`); boyut sınırı (düz metin 5 MB, diğerleri 500 MB); mükerrer (aynı ad + boyut başka kayıtta dönüşmüşse `shared_from` ile paylaş, tekrar indirme/dönüştürme). Biçim kümeleri tek yerde tanımlı (`knowledge/scope.py`).
- **Kapı 1, belge kabulü (dönüşümden önce):** taslak/arşiv, şablon, dil kuralı (`ALLOWED_LANGUAGES`, varsayılan `tr,en`; yalnızca Türkçe kabul etmek PayCore'da teknik dokümanların %25'ini elemişti; bge-m3 çok dilli, cevap yine Türkçe), belgeler arası mükerrer (normalize edilmiş metnin hash'i başka belgede varsa `duplicate_of:<id>`, sahiplik sabit), boş/çok kısa gövde (gövde kısaysa belgenin **kendi** eklerine bakılır; metni olan ya da dönüşmeyi bekleyen eki varsa geçer), eski belge `flagged` (silinmez, işaretlenir). Elenen belgenin ekleri dönüştürülmez.
- **Kapı 2, metin kalitesi (dönüşümden sonra, belge ve parça düzeyinde):** boş/yalnızca başlık, boilerplate (satırların %60'ı bağlantı/menü), kod/log yığını, düzyazısız (yalnızca tablo/kod iskeleti), çok kısa, parçalar arası mükerrer.
- **Veri dökümü tespiti (ek düzeyinde):** tamamı log, stack trace, JSON/XML, ayraçlı kayıt listesi ya da base64/hex olan ek `data_dump:<tür>` ile elenir; belgenin metnine ve parçalarına girmez. Kod (SQL betiği) ve Markdown tablo veri sayılmaz.
- **Rapor:** `ingest_gate_stats` görünümü ve 10'da "Ingest Raporu" ekranı: kaynak × kapı × gerekçe sayımı, elenen belge/parça listesi gerekçesiyle; toplamlar belge sayısına eşit.
- Kanıt (PayCore, Confluence OCR space'i): 3.071 `ok` parçaya karşı 7.911 boilerplate ve 2.919 düzyazısız elendi; Jira PRSIM'de 19.058 `ok`'a karşı ~17.500 elenen. Kapısız indeksin ~%70'i gürültü olurdu.

### Vektör deposu soyutlaması

- `backend/app/knowledge/vectorstore/base.py`: `VectorStore` arayüzü (C5): `ensure_collection(kb_id, dim)`, `upsert(chunks)` (dense + isteğe bağlı sparse), `search(kb_id, query: {dense, sparse?}, filters, top_k)`, `delete_by_document(document_id)`, `drop_collection(kb_id)`. Filtreler: `document_ids`, `acl_roles`, `acl_users`, `metadata` eşitlikleri.
- İki gerçekleştirme, **ikisi de 04a'da**: `QdrantStore` (PayCore PoC'de birincil: dense + bge-m3 sparse, RRF Qdrant'ta; koleksiyon başına KB, payload'da `document_id, acl_roles, acl_users, page, section_path`; filtreler payload filter ile sorgu anında; PayCore'un mevcut koleksiyonu ACL payload'ı eklenerek devralınır) ve `PgVectorStore` (ürün varsayılanı; `chunks.embedding` dense, HNSW; sparse yok sayılır, hibrit Postgres BM25 ile). Tam eşdeğerlik testi ve `migrate-vectors` 04b.
- Seçim `.env`: `VECTOR_BACKEND=pgvector|qdrant`, `QDRANT_URL`, `QDRANT_API_KEY`. Compose'da `qdrant` servisi `profiles: [qdrant]` ile isteğe bağlı; mevcut bir Qdrant varsa yalnızca URL verilir.
- Parça metni ve tsvector her durumda Postgres `chunks` tablosunda kalır; Qdrant yalnızca vektör ve filtre payload'ı tutar. Böylece hibrit arama (BM25 Postgres'ten, vektör seçilen sürücüden, RRF ile birleşim) iki sürücüde de aynı çalışır.
- `make migrate-vectors FROM=pgvector TO=qdrant` (ve tersi): embedding yeniden hesaplanmaz, koleksiyonlar kopyalanır; ilerleme ve doğrulama (parça sayısı eşitliği) raporlanır.
- Testler iki sürücü için de koşar (`pytest -m vectorstore`, Qdrant için test konteyneri).
- 05 (few-shot örnekleri) ve 14 (hafıza) aynı arayüzü kullanır; küçük koleksiyonlar oldukları için `MEMORY_VECTOR_BACKEND` ile ayrı seçilebilir, varsayılan pgvector.

### Arama API'si

- `POST /kb/{id}/search`: `{query, top_k, filters, hybrid: true, rewrite: bool}`. Akış: sorgu **silver ile aynı normalizer yapılandırmasından** geçer (aşağıda) → (isteğe bağlı) çok biçimli sorgu → vektör (cosine) + BM25 (tsvector), RRF → reranker → rerank tabanı → sonuç. Döner: parça metni, belge adı, sayfa, breadcrumb, güncelleme tarihi, embedding skoru, rerank skoru, kaynak bağlantısı.
- **Normalizer iki katman** (PayCore düzeltmesi D5; K1 ile düzeltildi): (a) **biçim temizliği, zorunlu**: HTML ve entity çözme, boşluk ve satır sonu sadeleştirme, Unicode NFC, görünmez karakterler; belge ve sorguya aynen uygulanır. (b) **Türkçe düzeltme katmanı** (`TEXT_NORMALIZE_TR`, sözlük ve kural tabanlı yazım/ek düzeltmesi): **ayrı ayar, varsayılan kapalı**; PayCore'da 300 örnekte hata kapısını geçemediği için hiç açılmadı, hatalı bir düzeltme belgeyi de sorguyu da kalıcı bozar. Açılırsa belge (silver) ve sorgu birebir aynı fonksiyon ve aynı sözlük sürümünden geçer; `knowledge_bases.normalizer_config_id` silver'a ve her sorgu kaydına (`kb_queries`) yazılır. Genel yazım hataları belgede düzeltilmez; sorgu tarafında çok biçimli sorgu ve isteğe bağlı rapidfuzz varyantı ile ele alınır.
- Erişim: çağıran kullanıcı/anahtarın rolü ve kimliği `documents.acl_*` ile sorguda filtrelenir (sonradan eleme yok). **Boş ACL kuralı (C15):** `acl_roles` ve `acl_users` ikisi de boşsa belge projenin tüm üyelerine açıktır; elle yüklemede arayüz ACL seçimini zorunlu adım olarak sorar (varsayılan `analyst`), API'de alan verilmezse varsayılan `analyst` yazılır ve cevapta görünür. (R2.5) Arama API'si `X-On-Behalf-Of` JWT'sini (03b tanımı) kabul eder; iç servisler (05 mcp-search, 06 runtime) son kullanıcı adına bu başlıkla çağırır, ACL o kullanıcıya göre uygulanır.
- **Tek eşik kuralı** (PayCore kontrolü K2): reranker açıkken `min_score` (embedding skoru) **uygulanmaz**; hibrit adaylar (top-30) olduğu gibi reranker'a gider, eleme yalnızca rerank tabanında yapılır. Reranker kapalıysa `min_score` tek eşik olarak kalır. Gerekçe: embedding eşiği, reranker'ın düzeltebileceği adayları reranker'a ulaşmadan keser; Cognipeer incelemesinde varsayılan 0,50 ile 6 sorgunun 6'sı bu yüzden elenmişti. Boş sonuç runtime'da "belgede yok" davranışına yol açar.
- **Reranker ve rerank tabanı** (PayCore düzeltmesi D5): `bge-reranker-v2-m3` yerel (sentence-transformers, iş parçacığında); hibrit top-30 → reranker → top-k. Reranker puanı `RERANK_MIN_SCORE` (bge-reranker-v2-m3 için 0,1) altındaki parçalar döndürülmez; hiçbiri kalmazsa boş sonuç. Elenenler `kb_queries` ve run kaydında "rerank tabanı altında" olarak görünür. Kanıt: PayCore'da modele verilen 240 parçanın üçte biri taban altındaydı, hiçbiri beklenen sayfa değildi; CPU'da bağlamı okumak cevap süresinin ~%75'i. `min_score` embedding skorudur, bu ayrı.
- **Güncellik** (PayCore düzeltmesi D5): hangi parçaların seçileceğine reranker karar verir, tarih değil; skora tarih puanı eklenmez. Sonuç listesi `updated_at_source` ile en yeniden eskiye sıralanıp her parçada gün yazılarak döner; çelişki kuralı 06'daki prompt'ta.
- **Çok biçimli sorgu** (PayCore düzeltmesi D5, M3 sonrası karar): `rewrite=true` ise soru LiteLLM üzerinden 2-3 varyantla yeniden yazılır, hepsi aranır, RRF ile birleşir. Kısa/yarım cümleli sorular için; PayCore'da dolaylı sorularda yetersiz kaldı (doküman terimini üretmiyor). (R3.2) Seed'e göre: `airgap` cpu kapalı (her soruda 30+ s ek etkileşimli çağrı), `llmaas` ve `gpu` açık; her durumda 09'daki sınavla ölçülüp M3'te karar verilir.

### Yönetim API'si

KB CRUD, belge listesi ve durum, belge silme (parçalar dahil), yeniden indeksleme, test sorgusu endpoint'i (önyüzde "arama dene" için).

### Bilgi tabanı ayarları ve sorgu günlüğü (konsol incelemesinden, bağlayıcı)

- `knowledge_bases` ek alanlar (C21, ARCH-07 ile daraltıldı): `chunk_strategy` tek değer `heading` (başlık duyarlı parçalama; PayCore'da ölçülmüş tek yol, alan ileride additive genişler), `hybrid bool`, `rerank_model`, `default_top_k`, `default_min_score` (yalnızca reranker kapalıyken, K2), `default_filter jsonb`, `normalizer_config_id`. Çıkarılanlar (KARARLAR Reddedilenler): `separators[]`, `parent_window`, `contextual_headers`, `oversample`, `response_detail`, `filterable_fields[]`.
- Paylaşılan vektör indeksinde modül izolasyonu: her parça `kb_id` payload'ı taşır ve sorgu her zaman KB ile filtrelenir (sızıntı önleme).
- `kb_queries(id, kb_id, query, normalizer_config_id, run_id nullable (C12; arama API'si `X-Run-Id` başlığını kabul eder), candidates jsonb (hibrit top-30 `chunk_id`, `document_id`, embed ve rerank skorları; 09 aşama teşhisi buradan okur), best_embed_score, best_rerank_score, returned, filtered_by_rerank_floor, filtered_by_min_score, latency_ms, user_id, ts)`; 10'daki modül Overview'unda: belge ve parça sayısı, toplam sorgu, ortalama gecikme, **sıfır sonuçlu sorgu sayısı ve oranı**, **tabanla elenen sorgu sayısı**, **skor dağılımı grafiği** (her sorgunun en iyi skoru, eşiğe göre), "hiçbir şey bulamayan sorgular" tablosu (sorgu, neden, en iyi skor, zaman). Kabul kriteri olarak ölçülür.
- Embedding modeline göre varsayılan eşik tablosu (`bge-m3` ve `e5` için ölçülüp `docs/bilgi-tabani.md`'ye yazılır); UI skor dağılımına bakarak eşik önerir ("sorguların %X'i eşiğin altında" uyarısı). Gerekçe: Cognipeer'de varsayılan 0,50, 6 sorgunun 6'sını elemişti.
- Test sorgusu (Playground) endpoint'i yalnızca arama yapar, parça metni ve skorları döner; "bu parçalarla modelden cevap al" seçeneği 06'ya bağlanır. Belge yüklendikten sonra parça sayısı ve durum KB kartında görünür.
- Vektör sürücüsü ilk sürümde iki tane (pgvector, Qdrant); `VectorStore` arayüzü başka sürücü eklenebilecek şekilde kalır.


## Teslimatlar

- Migration, modeller, worker, router'lar.
- 13a'nın sentetik örnek sözleşmeleriyle (`data/samples/contracts/`, dalga 1'de hazır) `tests/test_ingest.py` ve `tests/test_search.py`.
- `docs/bilgi-tabani.md`: parçalama ayarları, embedding değişikliğinde yeniden indeksleme, ACL.

## Kabul kriterleri

- 10 sayfalık örnek sözleşme yüklendiğinde 2 dakika içinde `indexed` olur (CPU embedding ile; süre README'de ölçülüp yazılır).
- "fesih bildirim süresi" sorgusu ilgili maddeyi ilk 3'te getirir (örnek belgeyle test).
- `acl_roles=['admin']` belgesinin parçaları analyst kullanıcının aramasında dönmez.
- Aynı dosya ikinci kez yüklenince yeni kayıt açılmaz, sürüm artar.
- Embedding boyutu `EMBED_DIM` ile eşleşmeyen model kaydı 400 `embedding_dimension_mismatch` döner ve aktive edilmez (03a ile aynı kural, C7); yükleme bu duruma hiç ulaşmaz.
- (R3.5) Aynı belge seti ve aynı sorgu için pgvector ve Qdrant sürücüleri exact arama modunda (`hnsw.ef_search` yüksek / Qdrant `exact=true`) ilk 5'te aynı parçaları döner; yaklaşık modda en az 4/5 örtüşme.
- `migrate-vectors` sonrası iki tarafta parça sayısı eşittir ve ACL filtresi Qdrant'ta da sorgu anında uygulanır.
- (PayCore düzeltmesi D1) Yalnızca alt sayfa bağlantılarından oluşan navigasyon sayfası `skipped/boilerplate` olur, aramada çıkmaz. 10.000 satırlık log eki `data_dump:log` olur; ait olduğu belge indekslenir, ek indekslenmez. Aynı içerikli iki belgeden biri `duplicate_of:<diğeri>` olur ve sahiplik sonraki koşularda yer değiştirmez. Rapor ekranı her elenen belge ve parçayı gerekçesiyle sayar; toplamlar belge sayısına eşittir.
- (PayCore düzeltmesi D2) `.doc` uzantılı MHTML dosyası okunur Türkçe metin üretir, base64 içermez. cp1254 kodlu Türkçe `.txt` eki `ş ı ğ` harflerini korur. Metin katmanlı 50 sayfalık PDF OCR'a girmez (`convert_engine` OCR değildir). Takılan bir dönüşüm süre sınırında öldürülür, diğer dosyalar devam eder, kayıt `timeout` görünür. Hiçbir parça `chunk_max_tokens × 6` karakteri aşmaz.
- (PayCore düzeltmesi D3) Parçalama ayarı değişip `make reindex LAYER=gold --full` koşulduğunda kaynak sisteme ve raw'a dokunulmadan silver'dan üretilir; metni değişmeyen parçalar yeniden embed edilmez (log `reused=N`). Embedding modeli değişince eski vektörler taşınmaz, yeniden hesaplanır.
- (PayCore düzeltmesi D5) Embed edilen her parça metni breadcrumb ile başlar; arama sonucu yolu gösterir. Rerank tabanı altındaki parçalar sonuçta dönmez ve `kb_queries`'te "elendi" olarak sayılır.
- (PayCore kontrolü K1) `TEXT_NORMALIZE_TR` kapalıyken silver metni yalnızca biçim temizliğinden geçer (`clean_markdown`: HTML etiketi, entity, literal `\n`, çift boşluk; kod blokları dokunulmaz) ve bu varsayılandır. Belgenin silver'ında ve sorgu kaydında aynı `normalizer_config_id` yazılıdır; `TEXT_NORMALIZE_TR` silver yeniden üretilmeden sorguda açılamaz (uyumsuzlukta arama 409 döner).
- (PayCore kontrolü K2) Reranker açıkken, embedding skoru 0,3'ün altında olup reranker'da taban üstüne çıkan bir aday sonuçta döner (eşik üst üste binmez); reranker kapatılınca `min_score` devreye girer.
- (PayCore düzeltmesi D6) 10 eşzamanlı arama isteğinde reranker çalışırken sağlık endpoint'i ve SSE keepalive 1 saniyenin altında cevap vermeye devam eder (olay döngüsü kilitlenmez).
- (C12) Her aramada `kb_queries.candidates` hibrit top-30 adayı skorlarıyla kaydeder; `X-Run-Id` verilen aramada `run_id` dolu gelir.
- (C15) ACL'si boş belge aynı projedeki analyst ve admin'e döner, başka projeye dönmez; elle yüklemede ACL alanı verilmeyen belge `analyst` ile kaydedilir ve cevapta görünür.
- (00'dan) Açılışta `warmup` reranker'ı yükler; ısınma bitmeden `/readyz` 503 `warming`, bitince 200; `OLLAMA_CONTEXT_LENGTH` yoksa ya da seed `context_tokens` değerinden küçükse `/readyz` 503 `context_configuration_invalid` (C13).

## Teknik notlar

- (04b) Türkçe embedding kalitesi: `bge-m3` ve `multilingual-e5-large` 13a'daki soru setiyle (35 soru; 10 soru istatistiksel olarak yetersiz, inceleme v4 U2) karşılaştırılır, sonuç `docs/bilgi-tabani.md`'ye; kazanan varsayılan olur.
- Docling imajı büyük; iç registry'ye alınmalı (12'de listeye eklenir).
- Postgres tsvector için `turkish` yapılandırması vardır; ek stopword listesi gerekmez.
- (PayCore düzeltmesi D1-D3) Referans kod PayCore deposunda (`src/paycore_llm/ingest/`): `gates.py`, `scope.py`, `store.py` (hash sahipliği), `convert/router.py` (`sniff`), `convert/mhtml.py`, `convert/encoding.py`, `convert/pdf.py`, `convert/ocr.py`, `convert/libreoffice.py`, `convert/email_msg.py`, `convert/diagram.py`, `convert/video.py`, `convert/workers.py`, `convert/pipeline.py`, `reconvert.py`, `chunking.py` (`approx_tokens`, breadcrumb), `normalize.py`, `layout.py`, `sync.py` (`_reuse_vectors`). Birebir kopya değil; bu paketin Postgres veri modeline uyarlanır. PayCore'daki `docs/agentic/referans/attachment_conversion_plan.md` biçim tablosu ve araç gerekçeleri için okunmalı.
- (PayCore düzeltmesi D6) Yerel reranker model nesnesi süreç başına bir kez yüklenir (`warmup`); `asyncio.to_thread` + `threading.Lock`. Embedding süreç içinde yüklenmez (C10).
- Disk: raw ve silver katmanı ek yer tutar; Confluence bağlayıcısında (16) PayCore ölçeğinde ~30 GB. `docs/donanim.md` (12) bellek ve disk bütçesine yazılır.

## Kapsam dışı

Web crawler, S3 depolama (yerel disk yeterli), OCR kalite ayarı, MCP sarmalayıcı (05), görsel eklerin OCR'ı (Kapı 0 eler), kaynak ağırlıklı arama ve uzman profilleri (PayCore'a özgü; ileride agent tanımında "bilgi tabanı ağırlığı" olarak değerlendirilebilir). Confluence, Jira, SharePoint ve ağ klasörü bağlayıcıları 16'da; bu paket `documents.source_item_id`, `attachments` tablosunu ve worker'da "raw'a düşmüş kaynak içeriğini dönüştür ve indeksle" giriş noktasını (`ingest_from_raw(raw_path, metadata, acl)`) hazır bırakır ki 16 ingest hattını yeniden yazmasın.
