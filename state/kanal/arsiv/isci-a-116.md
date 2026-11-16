# Arşiv: isci-a · 116

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-116-0001 · 2026-10-31 10:40 · → koordinator · ACK
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0001
GOREV alındı; lease ACTIVE (ffcore-isci-a-116). Worktree .worktrees/fix/06a-checkpoint-sources e5074ab, temiz. Touch-zone: runtime/graph.py (+ runner/state gerekirse), tests, docs/agentlar.md; sınıf [A]; C8/C9'a dokunursam dururum.
İlk bulgu (koddan, plan bunu ele alacak): parça metni checkpoint'te iki yerde: (1) `state.sources[*].text` (graph.py:64), (2) `state.messages`: guard_in'in kullanıcı mesajı (`user_message(..., sources)`, graph.py:137) ve search_documents araç sonucu (graph.py:423, 471) metni içeriyor. Yalnız (1)'i kaldırmak hedefi karşılamaz. Ayrıca bitmiş koşunun checkpoint'i hiç silinmiyor (runner.py; `delete_thread` yok). Plan state/pr/06a-checkpoint-sources.md'ye, seçenekler KARAR-GEREK ile; yığın gerekirse önce YIGIN-AÇ.


### A-116-0002 · 2026-10-31 11:05 · → koordinator · DURUM
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0001
DURUM: PLANNED talebi (koşullu). Plan: state/pr/06a-checkpoint-sources.md (bulunan semboller, 7 kabul testi, felsefe üçlüsü). Kod yok; A-116-0003 kararına bağlı.

### A-116-0003 · 2026-10-31 11:05 · → koordinator · KARAR-GEREK
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0001
Sorun: GOREV hedefi "checkpoint'te yalnız chunk_id" ama metin üç yerde: `state.sources.text`, `state.messages` (guard_in kullanıcı mesajı + search_documents araç sonucu) ve LangGraph'ın her adım için ayrı tuttuğu checkpoint sürümleri. Son durumu temizlemek geçmiş sürümleri silmez. Bitmiş koşunun thread'i hiç silinmiyor; waiting_user'ın süresi yok.
- **A (Önerilen):** sources metinsiz + koşu bitince `adelete_thread` (runner bitişlerinde hemen; iptal/onay süresi gibi runner dışı bitişler ve başarısız silmeler dakikalık arq cron süpürgesiyle) + bekleyen koşunun belgesi silinmişse resume'da ya da süpürgede `failed`/`source_deleted` (model silinmiş metni görmez). Etki: metin yalnız koşu canlıyken checkpoint'te, silinen belgeyle devam yok; C8/C9 değişmez (yeni durum/olay yok, yalnız hata kodu). Bedel: touch-zone'a `runtime/worker.py` (cron) + yeni `runtime/checkpoints.py`; api/runs.py ve services/approvals.py'ye dokunmaz.
- B: GOREV'in harfi: state ve mesajlarda yalnız ref, metin her model çağrısında DB'den yeniden kurulur, egress maskesi her çağrıda yeniden. Etki: tam ref modeli; bedel: guardrail egress olayları çağrı başına çoğalır ya da yeni önbellek kuralı gerekir, graph'ın yarısı değişir; `run_events.llm_call.request_messages` metni yine taşıdığı için vaadi tek başına sağlamaz.
- C: Yalnız `sources.text` kaldırılır. Etki: küçük; bedel: metin messages'da ve eski sürümlerde kalır, FOLLOWUP-116 kapanmış görünür ama kapanmaz (ARCH-13). Önermiyorum.

### A-116-0004 · 2026-10-31 11:05 · → koordinator · KAYIT-TALEBI
Paket: fix/06a-checkpoint-sources   Cevap: -
Tür: FOLLOWUP- (bu dalın dışında, dokunmuyorum). `run_events` `llm_call.request_messages` (graph.py:197) ve `answer.text` modele giden maskeli mesajları, dolayısıyla kaynak parça metnini append-only saklar; belge silinince kalır. FOLLOWUP-108 vaadinin üçüncü yeri. Öneri: 03c retention `content` sınıfı (`clear_content`) bu alanları kapsasın; belge silinince ilgili `llm_call` payload'ında `request_messages` temizlensin ya da yalnız ref saklansın. 03c PLANNED'da açıkça istenmeli.

### A-116-0005 · 2026-10-31 11:20 · → koordinator · ACK
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0002
Alındı; PLANNED onaylı, sınıf [B]. Uygulanacak: (1) `runs.checkpoint_deleted_at` additive kolon (Alembic 06a etiketi, downgrade'li); bitişte silme + idempotent süpürge (terminal AND kolon NULL), hata → kolon boş, süpürge yeniden; 24 saat sonra uyarı log'u. (2) Belge silme ucu (api/knowledge.py) o belgeyi kaynak göstermiş waiting_* koşuları işaretler: ikinci additive kolon `runs.source_deleted_at` (varsayım; işaretin yeri kolon, ayrı tablo değil); süpürge/resume bunları failed/source_deleted kapatır + thread siler. (3) `source_deleted` docs/agentlar.md hata kodları tablosuna. (4) Kanıtlar listendeki gibi (3 tablo 0 satır, events.py sources/tool_result gövdesi kontrolü, 07 TTL süpürge deseni, `?now=` kancası). (5) FOLLOWUP-119 NOT_RUN gerekçeli. (6) 10b-poc-2 koşu ekranının kaynak metni okuma yeri PR'a. Plan dosyası bu şartlarla güncelleniyor.

### A-116-0006 · 2026-10-31 11:20 · → koordinator · YIGIN-AÇ 116
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0002
Proje ffcore-116, FFCORE_VERSION=0.0.0-116, BACKEND_PORT=18070 FRONTEND_PORT=13070, --env-file .env.test --profile test --profile qdrant; worktree .worktrees/fix/06a-checkpoint-sources. Amaç: kırmızı integration testleri + make test-int. Şu an açık: review13bk (inceleyici, 19 konteyner) ve kullanıcının ayrı projesi airflow_project_dev (5 konteyner, ffcore değil). Benimkiyle iki ffcore yığını olur; sıra verene kadar açmıyorum, kod ve unit testlerle ilerliyorum.

### A-116-0007 · 2026-10-31 10:59 · → koordinator · YIGIN-KAPA 116
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0003
`down -v` exit 0; ffcore-116 konteyner 0, volume 0. İmajlar `ffcore/{tools,backend,frontend}:0.0.0-116` = `0.0.0-main` etiketi kaldı (silme listende).

### A-116-0008 · 2026-10-31 10:59 · → koordinator · DURUM
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0002
DURUM: VERIFIED. HEAD 94f3e07843d3089221f94bd1401482af7c3cae2a (e5074ab üstüne 1 commit, 12 dosya, touch-zone + K-116-0002 genişletmesi içinde; state/ yok).
Kapılar (tee, state/pr/06a-checkpoint-sources-kapilar/): make lint 0; make test llmaas 727/727, airgap 727/727; make test-int 541 passed + 4 opt-in atlandı (425 s). Kırmızı önce: red-1 (modül yok), red-2 (iskelet: 8 davranış hatası, thread satırları 26/40/47, sources'ta text).
K-116-0002 şartları: (1) `runs.checkpoint_deleted_at` + idempotent süpürge (terminal AND NULL), başarısız silme NULL bırakır, 24 saatte `checkpoint_purge_overdue` log'u (test_116_5, _7); (2) belge ve KB silme canlı koşuları `runs.source_deleted_at` ile işaretler; boundary, resume ve süpürge `failed`/`source_deleted` + thread silme (test_116_3, _4, _10, _11); (3) `source_deleted` docs hata kodları tablosunda, C9 durum/olay değişmedi; (4) üç tabloda 0 satır, events.py sources/tool_result gövdesinde metin yok (DB + Redis), `GET /events` sources `[deleted]` (test_116_2, _3); `?now=` kancası gerekmedi, süpürge testte doğrudan `now` ile; (5) FOLLOWUP-119 NOT_RUN gerekçeli; (6) önyüz bulgusu aşağıda.
Not: test_07_worker.py'de 07 cron testi tek cron varsayıyordu; adıyla seçecek şekilde değişti (davranış aynı).

### A-116-0009 · 2026-10-31 10:59 · → koordinator · PR-HAZIR
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0002
PR: state/pr/06a-checkpoint-sources.md · Branch: fix/06a-checkpoint-sources · SHA: 94f3e07843d3089221f94bd1401482af7c3cae2a · Baz: e5074ab · Sınıf: [B] · push yok. Migration 06a_0002 (06a etiketi, downgrade'li; round-trip gerçek Postgres'te test_06a_schema). Upgrade sonrası eski bitmiş koşuların thread'lerini ilk süpürgeler siler (bilinçli). Branch'e başka commit atmıyorum.

### A-116-0010 · 2026-10-31 10:59 · → koordinator · KAYIT-TALEBI
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0002
Üç FOLLOWUP- önerisi, hepsi bu dalın dışında, dokunmadım:
(1) isci-c (K-116-0002 madde 6): koşu ekranı `frontend/components/run-timeline.tsx:31-33` `GET /runs/{id}/events` gövdelerini ham JSON gösteriyor; `llm_call.request_messages` parça metnini taşıdığından silinen belgenin metni ekranda görünür (FOLLOWUP-119'un ekran yüzü; 03c temizleyene kadar ekran `request_messages`'ı göstermemeli ya da kaynak bloklarını maskelemeli). Test paneli (`agent-test-panel.tsx`, `lib/run-view.ts:90`) SSE `sources`'tan okur: metin yok.
(2) 07 (isci-b): `source_deleted` ile kapanan bekleyen koşunun onay kaydı `pending` kalır, onay kuyruğunda TTL dolana kadar görünür; sonra 07 süpürgesi `approval_expired_run_not_waiting` loglar. Öneri: kuyruk bitmiş koşunun pending onayını göstermesin ya da kapanışta `expired`/`cancelled` yapılsın (07 kararı).
(3) 03c: `checkpoint_purge_overdue` yalnız log; 03c uyarı kuralı (`kind` listesine ya da mevcut `service_down` benzeri) ile görünür olsun.

### A-116-0011 · 2026-10-31 13:59 · → koordinator · ACK
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0005
DUZELT alındı, r1 okundu. Uygulanacak: (1) sweep'te `_close_waiting` koşu başına try/except Exception + rollback + `source_deleted_close_failed` log'u, continue; (2) bekleyen sorgusu `order_by(Run.source_deleted_at)`; (3) önce kırmızı test: iki bekleyen koşu, ilkinde writer hatası → ikincisi kapanır, ilki bekler, sonraki tur kapatır; (4) docs: "en çok bir süpürge aralığı (60 s)"; aralık ayar değil (arq cron `second=30`), PR notuna yazılır. Yeni SHA ile PR-HAZIR.

### A-116-0012 · 2026-10-31 13:59 · → koordinator · YIGIN-AÇ 116
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0005
Proje ffcore-116, FFCORE_VERSION=0.0.0-116, 18070/13070 (K-116-0005 onayı), --env-file .env.test --profile test --profile qdrant. Amaç: kırmızı/yeşil hedefli test + make test-int.

### A-116-0013 · 2026-10-31 14:22 · → koordinator · YIGIN-KAPA 116
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0005
`down -v` exit 0; ffcore-116 konteyner 0, volume 0.

### A-116-0014 · 2026-10-31 14:22 · → koordinator · PR-HAZIR
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0005
r1 DUZELT uygulandı. Branch fix/06a-checkpoint-sources @ ceaa7045d66fac8745cdd98b7a25d5857a73779e (94f3e07 üstüne 1 commit, 3 dosya: runtime/checkpoints.py, tests/integration/test_116_checkpoint_sources.py, docs/agentlar.md). Sınıf [B], push yok. PR: state/pr/06a-checkpoint-sources.md "Review r1 bulgu → düzeltme → kanıt".
(1) sweep: koşu başına try/except + rollback + `source_deleted_close_failed`, continue; (2) `order_by(Run.source_deleted_at)`; (3) `test_116_12`: önce kırmızı (r1-red.txt, ConnectionError döngüden fırladı), sonra yeşil; (4) docs: en çok bir süpürge aralığı (60 s); aralık ayar değil (arq cron `second=30`).
Kapılar ceaa704: make lint 0; make test llmaas 727/727, airgap 727/727; make test-int 542 passed + 4 opt-in (529 s).

### A-116-0015 · 2026-10-31 14:55 · → koordinator · HANDOFF
Paket: fix/06a-checkpoint-sources   Cevap: K-116-0007
- Durum: MERGED (main 1e12c4b; r1 ONAY 94f3e07, r2 delta ONAY ceaa704). Lease ffcore-isci-a-116 RETIRED; oturum kapanıyor.
- Tam sonraki adım: bu dalda iş yok. Kalan: FOLLOWUP-119 (03c, K-03c-0001 madde 4'te zorunlu: `run_events` llm_call.request_messages/answer.text temizliği; `mark_document_runs` ile aynı jsonb eşleşmesi `runtime/checkpoints.py` `_shows_document` yeniden kullanılabilir), FOLLOWUP-123 (`checkpoint_purge_overdue` uyarı kuralı, 03c). A-116-0010'daki önyüz (run-timeline ham `request_messages`) ve 07 (source_deleted ile kapanan koşunun pending onayı) önerileri koordinatörde.
- Değişen dosyalar: backend/alembic/versions/06a_0002_checkpoint_lifetime.py, backend/ffcore/{models/runs.py, runtime/checkpoints.py, runtime/runner.py, runtime/graph.py, runtime/worker.py, api/knowledge.py}, backend/tests/{integration/test_116_checkpoint_sources.py, integration/test_06a_schema.py, unit/test_116_source_state.py, unit/test_07_worker.py}, docs/agentlar.md. Ayrıntı state/pr/06a-checkpoint-sources.md.
- Testler: ceaa704'te make lint 0; make test 727/727 iki profil; make test-int 542 + 4 opt-in. NOT_RUN: eski sürüm uygulaması downgrade sonrası açılış (kabul), gerçek model/airgap.
- Kararlar: K-116-0002 (A şartlı, [B]), K-116-0005 (sweep izolasyonu); varsayımlar PR "Varsayımlar" 1-6 (işaret kolonu `runs.source_deleted_at`, işaret running + waiting_*, retrieve→guard_in sürümü metni taşır ama thread sonunda silinir).
- Blocker: yok.
- Commit edilmemiş durum: yok (yalnız state/ kanal ve PR dosyası, koordinatör commit eder). Yığın kapalı; yerelde `ffcore/{tools,backend,frontend}:0.0.0-116` etiketleri silinebilir.
