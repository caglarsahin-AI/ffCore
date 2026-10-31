# PR: fix/06a-checkpoint-sources (FOLLOWUP-116)

**Paket:** fix/06a-checkpoint-sources · **Sınıf:** [A] · **Branch:** fix/06a-checkpoint-sources · **Baz commit:** e5074ab · **Durum:** PLAN (KARAR-GEREK A-116-0003 bekliyor; kod yok)

## Plan

### 1. Bulunan semboller ve dosyalar (kaynak okundu, e5074ab)
- `ffcore/runtime/graph.py:63-64` `_source_payload`: `Source.public() | {"text": ...}` → `state["sources"]` (retrieve :126, search tool :424/:465).
- **Metnin ikinci yeri, GOREV'de yok:** `state["messages"]`:
  - `guard_in` :137-146: `user_message(question, sources)` (prompting.py:181 `sources_block`) kullanıcı mesajına parça metnini gömer; egress maskeli hali `messages`'a yazılır.
  - `_search_tool` :423 + `tools` :466-472: `search_documents` sonucu `[n] doc (breadcrumb)\ntext` olarak `role: tool` mesajında.
- **Üçüncü yer:** LangGraph Postgres saver her adımın checkpoint'ini ayrı satır olarak tutar (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, thread_id = run id). Son durumdan metni çıkarmak geçmiş sürümlerdeki kopyayı silmez.
- `runtime/runner.py`: `_attempt_graph` :190-240 son durumu `aget_state` ile okur; `_complete` :268 `Message.sources`'a metni çıkararak yazar (doğru). **Hiçbir yol thread'i silmiyor**: bitmiş koşunun checkpoint'i süresiz kalır.
- Runner dışındaki son durum geçişleri: `api/runs.py:652` (kuyrukta/bekleyen koşu iptali), `services/approvals.py:383` `run_closer` (onay süresi doldu). `waiting_user`'ın süre sınırı yok (worker.py:85 yalnız `expire_approvals`).
- Silinen belge maskesi: `api/runs.py:164-200` `DELETED_BREADCRUMB`, `mask_deleted_sources` (okuma yolunda, FOLLOWUP-108).
- LangGraph 1.2.15 / checkpoint-postgres 3.1.3: `AsyncPostgresSaver.adelete_thread(thread_id)` var (imajda doğrulandı; üç tabloyu siler).
- Kapsam dışı ama aynı vaadi ilgilendiren: `run_events.llm_call.request_messages` (graph.py:197) modele giden maskeli mesajları, dolayısıyla parça metnini append-only saklar (`content` saklama sınıfı, 03c retention). Ayrı KAYIT-TALEBI (A-116-0004).

### 2. Kapsam / kapsam dışı (seçenek A'ya göre)
- Kapsam: (a) `state.sources` yalnız public alanlar (metin yok); metin yalnız o adımın mesajında. (b) Koşu bitince checkpoint thread'i silinir: runner'ın kendi bitişlerinde hemen, runner dışı bitişler (iptal, onay süresi) ve başarısız silmeler dakikalık arq cron süpürgesiyle. (c) Bekleyen koşu (onay/ask_user) devam ederken ya da worker yeniden başlayınca kaynak belgesi silinmişse koşu `failed` + `source_deleted` ile biter (model silinmiş metni görmez), sonra thread silinir. (d) Bekleyen koşunun belgesi silinirse aynı süpürge koşuyu `source_deleted` ile kapatır (waiting_user süresizdir; aksi halde metin süresiz kalır).
- Kapsam dışı: run_events içeriği (03c retention), `Message.sources` (zaten metinsiz), 04a belge silme API'si, C8/C9 alanları.

### 3. Değişecek dosyalar
- `backend/ffcore/runtime/graph.py`: `_source_payload` metinsiz; `guard_in` metni yalnız o anki `Source` nesnelerinden alır (retrieve aynı adımda tutar, bkz. varsayım 2); kaynak belge kontrolü `boundary` sonrası yeniden başlayan düğümlerde.
- `backend/ffcore/runtime/runner.py`: bitişte `adelete_thread`; devam/resume öncesi kaynak kontrolü.
- `backend/ffcore/runtime/checkpoints.py` (yeni): `purge_finished(session, saver)` ve `close_waiting_with_deleted_sources(...)`.
- `backend/ffcore/runtime/worker.py`: cron kaydı (touch-zone genişletmesi, gerekçe: süpürge arq cron, C9 kararı "zamanlı işler arq cron").
- `backend/tests/integration/test_116_*.py`, `backend/tests/unit/test_116_*.py`; `docs/agentlar.md` (checkpoint saklama bölümü).

### 4. Sözleşme, yapılandırma, profil
- C8 (definition), C9 (run durumları, `run_events.type`, SSE adları) değişmez: yeni durum ya da olay türü yok. Yeni hata kodu `source_deleted` `error` olayının `code` değeridir (kodlar kapalı listede değil; varsayım 3). Profil farkı yok.
- Yapılandırma: yok (süpürge her dakika, `expire_approvals` ile aynı).

### 5. Kabul kriteri → test (gerçek Postgres, `make test-int`)
| # | Kriter | Test |
|---|---|---|
| 1 | always KB ile biten koşu: checkpoint tablolarında thread yok; hiçbir checkpoint satırında parça metni yok (kırmızı önce) | `test_116_1_finished_run_leaves_no_checkpoint` |
| 2 | search_documents ile biten koşu: aynı | `test_116_2_tool_search_leaves_no_checkpoint` |
| 3 | Onayda bekleyen koşu: `state.sources` metin taşımıyor; belge silinir → resume `failed`/`source_deleted`, modele çağrı yok, thread silinmiş | `test_116_3_resume_after_document_delete_fails_loud` |
| 4 | waiting_user koşusunun belgesi silinir → süpürge koşuyu `source_deleted` ile kapatır, `error` olayı var, thread silinmiş | `test_116_4_sweep_closes_waiting_run_with_deleted_source` |
| 5 | Runner dışı bitiş (iptal, onay süresi) sonrası süpürge thread'i siler; ikinci koşu idempotent | `test_116_5_sweep_purges_threads_of_finished_runs` |
| 6 | Belgesi silinmemiş bekleyen koşu resume'da normal tamamlanır (regresyon), worker ölümü sonrası devam (06a_4) yeşil | `test_116_6_resume_with_live_sources_completes` + mevcut 06a takımı |
| 7 | `_source_payload` metin döndürmez; finalize alıntı/güven hesabı aynı (unit) | `test_116_7_source_state_has_no_text` |

### 6. Migration
Yok (LangGraph tabloları; şema değişmez).

### 7. Geri alma
Kod geri alınır; silinen checkpoint'ler bitmiş koşulara aittir (resume edilemez, okunmaz). Bekleyen koşular dokunulmadan kalır (yalnız silinmiş belgeli olanlar kapanır).

### 8. Durma koşulları
C8/C9'a dokunma ihtiyacı; `adelete_thread`'in bekleyen başka koşuyu etkilemesi; finalize'ın metne ihtiyacı çıkması; touch-zone dışı (api/runs.py, services/approvals.py) değişiklik gerekmesi.

### 9. Felsefe kontrolü
- ARCH-07: her koşu (tüm agent'lar) etkilenir; kalıcı ekleme bir modül + bir cron, yeni kolon/olay yok.
- ARCH-09: silme LangGraph'ın `adelete_thread`'i, zamanlama `arq cron`; kendi checkpoint temizleyicimiz ya da ikinci depo yok. Seçenek B (metni her model çağrısında DB'den yeniden kurmak) LangGraph'ın durumu taşıma işini yeniden yazardı.
- ARCH-06/10: silinmiş kaynakla devam yok (`source_deleted`, kodlu `error` olayı); silme hatası `checkpoint_purge_failed` log'u + süpürge yeniden dener; sessiz boş kaynak yok.

## Varsayımlar
1. Bitmiş koşunun checkpoint'ini okuyan yol yok (grep: yalnız runner ve bir unit test). Feedback (06a) ve okuma uçları `runs`/`run_events`'ten okur.
2. retrieve → guard_in arası metin: retrieve düğümünün döndürdüğü durum checkpoint'e yazılır; metinsiz olması için retrieve hit'leri `RunContext`'te (checkpoint'e girmeyen) tutar; worker bu iki düğüm arasında ölürse guard_in hit'leri bulamaz ve retrieve'i yeniden koşar (kodlu `progress`, sessiz değil). Uygulamada daha basit yol çıkarsa PR'da yazılır.
3. `source_deleted` yeni hata kodu; C9 kapalı listesi durum ve olay türüdür, kod değil (docs/agentlar.md'ye eklenir). Koordinatör aksini derse durur.

## Değişen dosyalar
(kod yok)
