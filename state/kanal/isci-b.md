# Kanal: isci-b

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-b-04b (önceki lease ffcore-isci-b-05b RETIRED, B-05B-0018)
- Aktif paket: 04b
- Durum: ACTIVE
- Son okunan: koordinator K-04B-0001

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-b-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 309 mesaj); ID ile atıf orada bulunur.

### B-04B-0001 · 2026-11-19 13:54 · → koordinator · ACK
Paket: 04b · Cevap: K-04B-0001
GOREV alındı. Lease ffcore-isci-b-04b ACTIVE. Worktree `.worktrees/feat/04b-knowledge-ext`, dal `feat/04b-knowledge-ext` (baz main bd240ca; GOREV'deki ec89bb1'den sonra yalnız state commit'leri). Okuma ve kod keşfi sürüyor; PLANNED ardından gelecek, PLAN-ONAY'a kadar kod yok.

### B-04B-0002 · 2026-11-19 14:40 · → koordinator · DURUM
Paket: 04b · Cevap: K-04B-0001 · Durum: PLANNED
Plan ayrıntısı `state/pr/04b.md` "Plan" (bulunan semboller, dosya listesi, göç tasarımı, testler, felsefe kontrolü, S1-S7).
**Ana bulgu (DOC-17):** FFCore'da DuckDB yok; belge/parça/sürüm/kapı meta'sı 04a'dan beri Postgres (`PgKnowledgeStore`, `ingest_gate_stats` görünümü), PayCore korpusu 19 `ingest-raw` ile raw'dan giriyor. D1'in gerçek işi `migrate-vectors` + eşdeğerlik; DEBT-10 (brief "DEBT-1") kanıtla kapanır.
**Göç:** Alembic `04b_0001` (down `05b_0001`, label 04b) `chunks.sparse jsonb NULL`; ingest sparse'ı da yazar (Qdrant'taki gereksiz yeniden embed kalkar). `migrate-vectors --from --to [--kb] [--dry-run] [--drop-target]`: kaynak Postgres satırları, embedding yeniden hesaplanmaz, KB başına sayı eşitliği yoksa çıkış 1; geri dönüş `VECTOR_BACKEND` eski değer (kullanıcı), kaynak hiç değişmez.
**PR bölme:** 04b-1 = D1 + D2 (rapor, ACL düzenleme, elenen parça listesi/`rerank_truncated`, preset) + 157 + 133. 04b-2 = D3 + D4 + D5 + D6 + 87 + 145 + 31; 04b-1 merge'ünden sonra main'den.
**Touch-zone eki isteği (S5):** `backend/ffcore/runtime/definition.py` (422 kalkar) ve `runtime/adapters.py` (scope aramaya gider); 04b-2'de, iki satır düzeyinde.
**Sorular (hepsinde önerim A):** S1 D1 kapsamı (A: DuckDB içe aktarıcı yok, DEBT-10 kapanır) · S2 sparse (A: `chunks.sparse` + eski satırda yalnız sparse hesaplanır, sayılır) · S3 TR normalizer (A: ayar + config id + 409 + yalnız PayCore katman A) · S4 video (A: bayrak + preset + açılışta hata; faster-whisper ayrı C PR) · S5 scope (A: `metadata.source` IN, C5 additive liste değeri) · S6 86 sistem durumu (A: yalnız kuyruk derinliği) · S7 num_ctx (A: Ollama `/api/ps` context_length). Ayrıntı ve bedeller PR notunda.
PLAN-ONAY bekliyorum; kod yok.

### B-04B-0003 · 2026-11-19 14:18 · → koordinator · YIGIN-AC
Paket: 04b · Cevap: K-04B-0002 · Yigin: ffcore-04b
04b-1 kırmızı kanıtı ve hedefli test-int için: postgres + redis + qdrant (`--profile qdrant`), `FFCORE_VERSION=0.0.0-04b` (backend/tools `0.0.0-main` imajlarından etiket; bağımlılık değişmiyor), `--env-file .env.test`, `--pull never`, 18440/13440. Log'lar `state/evidence/04b-*.log`. Not: B-04B-0002 başlığındaki saat 14:40 yanlış yazıldı (gerçek ~14:00; K-04B-0002'den önce); mesaj değiştirilmedi.

### B-04B-0004 · 2026-11-19 14:52 · → koordinator · KARAR-GEREK
Paket: 04b · Cevap: K-04B-0002
04b-1 `backend/openapi/04a.yaml`'a additive alanlar ekliyor (`GET .../ingest-report`, `DocumentUpdate.acl_*`, `ReindexRequest.preset`, `SearchResponse.filtered`/`rerank_truncated`). PROSES-184 ve `frontend/scripts/check-api.mjs` SPECS satırı gereği `frontend/lib/api/schema-04a.d.ts` aynı commit'te `npm run gen:api` ile yeniden üretilmeli; GOREV "frontend dokunulmaz" diyor. Test commit'i atıldı (53720c9), kod sürüyor; karar kod commit'inden önce gerekli.
**A (önerilen):** yalnız üretilmiş `frontend/lib/api/schema-04a.d.ts` touch-zone'a eklenir; `npm run gen:api` + `check:api` frontend konteynerinde, aynı kod commit'inde; başka frontend dosyası yok. 10c-3 bu dosyaya dokunmuyorsa kesişim yok. Bedel: diff'te tek üretilmiş dosya.
**B:** 04a.yaml güncellenir, d.ts güncellenmez; main'de `check:api` kırmızı kalır, 10c'nin sonraki dilimi üretir. Bedel: PROSES-184 ihlali, kırmızı kapı.
**C:** yeni uçlar ayrı `openapi/04b.yaml`'a (SPECS'te yok, check:api etkilenmez). Bedel: GOREV "04a.yaml additive" kararından sapma; aynı router iki taslağa bölünür.
