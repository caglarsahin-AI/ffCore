# Blocker ve Takip Kayıtları

Önekler: `BREAKING-C<n>` donmuş sözleşme kırma talebi · `FOLLOWUP-` kapsam dışı görülen iş · `DRIFT-` doküman-kod sapması · `DEBT-` bilinçli bırakılan borç · `ENV-` ortam engeli (`PENDING_ENV`) · `DECISION-` kullanıcı kararı bekleyen konu.

| No | Tür | Açıldı | Paket | Açıklama | Durum | Kapanış |
|---|---|---|---|---|---|---|
| 1 | DECISION | 2026-10-27 | 00 | ffcore alan adı ve marka araması (ffcore.com dolu; adaylar ffcore.com.tr, ffcore.ai/io) | açık | |
| 2 | DECISION | 2026-10-27 | 13 | M3'te `rewrite` ve judge modeli kararı (KARARLAR açık konular) | açık | |
| 3 | DECISION | 2026-10-27 | 08 | M4'te ad-soyad NER eşiği | açık | |
| 4 | DECISION | 2026-10-27 | 09 | ARCH-09: sınav tabloları Langfuse v3 datasets/experiments üzerine kurulsun mu? | kapandı | 2026-10-27, kullanıcı onayı (A5): Langfuse datasets/experiments; 09 işçisi yalnızca judge evaluator'ın OSS'de olup olmadığını doğrular |
| 5 | DRIFT | 2026-10-27 | 01 | U2/U3: LiteLLM'in `/model/new` gövdesindeki anahtarı şifreli sakladığı ve fallback sonrası cevap veren deployment'ı hangi alanda bildirdiği pinli sürümde doğrulanacak; doğrulanamazsa 01 durur | açık | |
| 6 | DRIFT | 2026-10-27 | 05a | U5: resmi `mcp` SDK streamable HTTP istemcisinin çağrı başına başlık alıp almadığı; almıyorsa `forward_user` için oturum çağrı başına açılır | açık | |
| 7 | DRIFT | 2026-10-27 | 02 | Langfuse v3 `LANGFUSE_INIT_*` değişkenleri ve datasets/experiments/scores API'sinin OSS'de olduğu pinli sürümde doğrulanacak (09 için judge evaluator ayrıca) | açık | |
| 8 | DRIFT | 2026-10-27 | 08 | Türkçe NER modeli lisansı ve imaja gömme hakkı; injection sınıflandırıcısının CPU gecikmesi ölçülecek | açık | |
| 9 | DRIFT | 2026-10-27 | 15 | Teams etkinliğinde kullanıcı e-postasının her kiracıda gelip gelmediği (`TeamsInfo.getMember` gerekebilir) | açık | |
| 10 | DEBT | 2026-10-27 | 04a | DuckDB belge deposu PoC'de `KnowledgeStore` bağdaştırıcısıyla sarılır; Postgres göçü 04b'de. Bilinçli borç (ARCH-09, ölçülmüş kod korunur) | açık | |
| 11 | DRIFT | 2026-10-27 | 04a | U14: Ollama embedding API'si bge-m3 için sparse (`lexical_weights`) üretmez; doğrulanırsa C10 tersine kararı kesinleşir (zaten süreç içi) | açık | |
| 12 | DRIFT | 2026-10-27 | 00i | U1: Open WebUI son kullanıcı kimliğini imzalı iletir mi; iletmezse audit aktörü `openwebui_service` | açık | |
| 13 | DRIFT | 2026-10-27 | 02 | U16: LiteLLM Langfuse callback'inin v3 ile uyumu; PayCore v2 → v3 değişimi (veri yok) | açık | |
| 14 | DECISION | 2026-10-27 | 08 | PRSIM ingest'ine kişi verisi guard'ı: karar 5 ile 08 tam gelene kadar ertelendi; o zaman yeniden açılır | ertelendi | |
| 15 | DECISION | 2026-10-27 | 00i | Bellek artırımı: kullanıcı onayladı; 00i bellek tablosu gereken miktarı verir | kapandı | 2026-10-27 |
