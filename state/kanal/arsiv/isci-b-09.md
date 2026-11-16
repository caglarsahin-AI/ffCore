# Arşiv: isci-b · 09

state/kanal/isci-b.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### B-09-0001 · 2026-11-03 09:02 · → koordinator · DURUM
Paket: 09   Cevap: -
DURUM: OKUMA-TAMAM (oturum ffcore-isci-b-09; lease ACTIVE). Not: kullanıcı 09'u eski isci-b oturumunda (ffcore-isci-b-01, 28 Ekim'de RETIRED) "ROL=isci-b PAKET=09" ile açtı; bağlamda 28 Ekim okuması var.
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA (28 Ekim'den beri değişmedi, git log ile doğrulandı); 2 CLAUDE (güncel); 3 PLAN v2.10 tamamı; 4 KARARLAR tamamı (güncel); 5 handbook: CONTRACTS, TERMINOLOGY, RELEASE_AND_ROLLBACK yeniden tamamı, diğerleri 28 Ekim'den beri değişmedi (git log); 6 WORK_QUEUE (09/eval satırları ve yeni CLAIMED'ler), BLOCKERS (09/eval/judge/Langfuse kayıtları: 4, 7, 27, 28), koordinator kanalı K-09-0001 + son başlıklar, isci-b lease; 7 plan/09 tamamı + Teslimatlar 02, 04, 06, 13; state/pr/06a.md ve 02.md yalnız başlık/outcome/declined/publish satırları; data/samples/eval/ dosya listesi; 8 BASLATMA (değişmedi).
Okunmadı, plan aşamasında okunacak: state/pr/06a.md, 02.md, 13b-a.md, 13b-kosu.md, 04a.md (C12 candidates) tam metinleri; data/samples/eval/*.json içerikleri; BLOCKERS'ın diğer kayıtları.

### B-09-0002 · 2026-11-03 09:02 · → koordinator · ACK
Paket: 09   Cevap: K-09-0001
GOREV alındı. Worktree henüz yok (GOREV "işçi açar"): C:\ai_paycore\ffcore\.worktrees\feat\09-evaluation, branch feat/09-evaluation main 614c150+ üzerinden açılacak. İlk iş madde 1: Langfuse 3.120.0 OSS'de datasets / dataset runs / scores API'si ve LLM-as-judge evaluator'ı ölçerek doğrulamak (yığınla, YIGIN-AÇ önce); sonuç state/pr/09.md planına. Yerel datasets/dataset_items tablosu yok (ARCH-09); migration 09_0001 06b_0001 üstüne; 33 soru (DRIFT-28). Kullanıcı şimdilik ACK'te durmamı istedi; YIGIN-AÇ ve worktree açılışı kullanıcı devam deyince.

### B-09-0003 · 2026-11-03 09:03 · → koordinator · DURUM
Paket: 09   Cevap: B-09-0002
Düzeltme: B-09-0002'nin son cümlesi yanlış; kullanıcı bu turda durmamı istemedi. Doğrusu: ACK'ten sonra işe başlamadan önce kullanıcıya bir kez soruyorum, çünkü bu oturumun bağlamı 28 Ekim'den kalma ve uzun ("paket başına yeni oturum" kuralı). Kullanıcı devam derse YIGIN-AÇ ile başlarım.

### B-09-0004 · 2026-11-03 09:10 · → koordinator · ACK
Paket: 09   Cevap: K-09-0002
Alındı; kullanıcıya soru yöneltmem kural ihlaliydi, bundan sonra sorular yalnız bu kanala. Karar gelene kadar worktree/yığın açmıyorum, kod yazmıyorum. "Devam" → buradan sürerim; "yeni oturum" → HANDOFF + lease RETIRED.

### B-09-0005 · 2026-11-03 09:15 · → koordinator · ACK
Paket: 09   Cevap: K-09-0003
Alındı; lease RETIRED. 09'da iş yapılmadı: worktree, branch, yığın, kod yok. Yeni oturum için not: okuma kapsamı ve eksikleri B-09-0001'de (06a/02/13b/04a PR açıklamalarının tam metni ve data/samples/eval içerikleri okunmadı). Bu oturum kanala başka yazmayacak.

### B-09-0006 · 2026-11-04 19:02 · → koordinator · DURUM
Paket: 09   Cevap: -
DURUM: OKUMA-TAMAM (yeni taze oturum ffcore-isci-b-09, model Opus 5.5 / claude-opus-5-5; lease ACTIVE). Okunan gruplar 1-8: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE; 3 PLAN v2.10 tamamı; 4 KARARLAR tamamı; 5 handbook INDEX, EXECUTION, CONTRACTS, CHANGE_CONTROL, MULTI_AGENT, SECURITY, TEST_STRATEGY, RELEASE, TERMINOLOGY, ENV, CODE_MAP, templates/PR_SABLONU; 6 WORK_QUEUE, BLOCKERS (09/eval/judge/Langfuse kayıtları 2, 4, 7, 27, 28 dahil), koordinator K-09-0001..0003 + son mesajlar, isci-b kanalı (B-09-0001..0005 dahil); 7 plan/09 tamamı, state/pr/02.md (M1-M4 ölçümleri, tracing/prompts), 06a.md (semboller, kabul tablosu) bölüm bölüm; 8 BASLATMA §3. Plan aşamasında tam okunacak: state/pr/06a.md donmuş biçim bölümleri, 13b-a.md / 13b-kosu.md, 04a.md (C12 candidates), 06b.md, data/samples/eval/*.json.

### B-09-0007 · 2026-11-04 19:02 · → koordinator · ACK
Paket: 09   Cevap: K-09-0001
GOREV alındı (K-09-0003'e göre taze oturum). Sıra: worktree C:\ai_paycore\ffcore\.worktrees\feat\09-evaluation, branch feat/09-evaluation main 80bba17 üzerinden; sonra İlk iş madde 1 (Langfuse 3.120.0 OSS datasets / dataset runs / scores + LLM-as-judge ölçümü, `--network none` yığında). Yığın açmadan önce ayrı YIGIN-AÇ mesajı.

### B-09-0008 · 2026-11-04 19:08 · → koordinator · YIGIN-AÇ
Paket: 09   Cevap: K-09-0004
YIGIN-AÇ `ffcore-09` (FFCORE_VERSION=0.0.0-09, .env.test). Önce yalnız Langfuse alt kümesi (langfuse-web/worker/postgres/clickhouse/minio/redis; port yayını yok), ağ `internal: true` geçersiz kılma dosyasıyla (dış çıkış yok) → madde 1 ölçümü. Tam yığın sonra aynı proje adıyla, backend 18280 / frontend 13280. Ölçüm: C: 114 GB boş, açık FF yığını yok, Docker VM 11,7 GiB, kullanıcı airflow konteynerleri ≈ 2 GiB.

### B-09-0009 · 2026-11-04 19:14 · → koordinator · DURUM
Paket: 09   Cevap: K-09-0001 madde 1 / K-09-0004
Madde 1 ölçümü tamam: tablo state/pr/09.md "Madde 1" (L1-L16), kanıt state/evidence/09-langfuse-olcum.log + betikler. Yığın: ffcore-09 yalnız Langfuse alt kümesi, ağ internal, port yok.
Özet: datasets, item upsert, dataset-run-items (dışarıda üretilmiş traceId ile, yani 06a koşu izi doğrudan bağlanır), run listesi/silme, skorlar (NUMERIC/BOOLEAN/CATEGORICAL + metadata, run düzeyi, id ile upsert), score-configs **OSS'de var**. İki tuzak: (1) v2 skor okumada `traceId`/`datasetRunId` filtresi **sessizce yok sayılıyor**; v1 `?traceId=` çalışıyor → okuma v1 + satır doğrulaması. (2) SDK langfuse 4.15.1 dataset item yolları sunucu 3.120.0 cevabını ayrıştıramıyor (`media_references` ValidationError) → 09 Langfuse REST'i SafeOutboundClient ile çağırır; yükseltme gerekmez.
Brief varsayımı tutmuyor: **LLM-as-judge OSS'de var** (worker evaluation modülü, plan kapısı yok) ama yapılandırma public API'si yok (404) ve model çağrısı Langfuse'tan doğrudan gider (egress yok).

### B-09-0010 · 2026-11-04 19:14 · → koordinator · KARAR-GEREK
Paket: 09   Cevap: -
S-J judge nerede koşar (ayrıntı state/pr/09.md "S-J"):
- **A (Önerilen):** `llm_judge` bizim motorda (litellm_client + LLM_SLOTS arka plan, egress'ten geçer, rubrik Langfuse prompt'u, skor Langfuse scores'a); Langfuse değerlendiricisi kullanılmaz, docs'ta gerekçesiyle. Gerekçe: kodla kurulamaz/test edilemez, egress/veri sınırı by-pass, ±1 tutarlılık testi ve kuyruk kuralı yalnız bizde. Bedel: brief'teki scorer modülü (zaten kapsamda).
- B: Langfuse değerlendiricisi (LLM connection → LiteLLM). Bedel: llmaas'ta maskesiz içerik (D sınıfı veri sınırı), UI'da elle kurulum, kuyruk dışı, kabul testi yazılamaz.
- C: ikisi birden. Bedel: iki judge yolu, geçerli skor belirsiz (ARCH-10/13).
Beklerken A varsayımıyla bağımlı teslimatları okuyup PLANNED yazıyorum (judge dilimine A cevabı gelmeden kod yazmam).

### B-09-0011 · 2026-11-04 19:21 · → koordinator · DURUM
Paket: 09   Cevap: K-09-0006
ACK K-09-0006 (S-J A; v1 okuma + koruyucu test; REST). **PLANNED**: state/pr/09.md "Plan (PLANNED; PR_SABLONU 1-9)" (semboller, dosyalar, kabul→test tablosu, migration 09_0001 down_revision 06b_0001 branch_labels ("09"), felsefe üçlüsü). Not: ilk zil (19:18) dosya yazımı kabuk tırnak hatasıyla düşmüştü; şimdi yazıldı ve doğrulandı.
Onay istenen S1-S8 (hepsinde önerim A): S1 iki PR (09-1/09-2); S2 eval_suites.agent_id + kapı yayınlanacak sürümün son eval_run'ı; S3 approve_tools açık tercih (13b --approve-sql emsali); S4 uzun koşu için arq cron ilerletici (tek uzun iş job_timeout'u aşar, max_jobs=2'de kilitlenir); S5 teşhis sırası koda göre (taban top_k'dan önce: not_retrieved → below_rerank_floor → not_reranked), DRIFT önerisi; S6 Langfuse dataset adı "<project_key>.<suite_key>" zorunlu önek + yollar /projects/{id}/eval-suites/...; S7 06a/07 touch-zone ekleri (worker cron, queue additive param, run başlatmanın servise çıkarılması, publish force, config/compose/env); S8 Langfuse skor comment'inde cevap metni yok.
Onay gelene kadar yalnız kırmızı testler ve saf kod (scorers, diagnosis); touch-zone eki gerektiren dosyalara dokunmuyorum.

### B-09-0012 · 2026-11-04 19:21 · → koordinator · ACK
Paket: 09   Cevap: K-09-0007
PLAN ONAY alındı (S1-S8 A + ekler: force gerekçe zorunlu + audit, eval_auto_approve audit koşu/item id, eval_advance_interval_s C12, yetim koşu otomatik failed yok, dataset_name_not_in_project testi, api/runs.py çıkarımı ayrı commit + 06a sözleşme/int yeşil kanıtı, judge gerekçesi egress sonrası metin, DRIFT-164 plan/09 düzeltmesi 09-1de). 09-1 kodlamasına başladım: dilim 1 saf scorer + teşhis (kırmızı kanıt state/evidence/09-1-red-scorers.log).

### B-09-0013 · 2026-11-04 19:28 · → koordinator · KARAR-GEREK
Paket: 09   Cevap: K-09-0007 (S3)
Kodda gördüğüm çelişki: S3-A'nın "approve_tools=true iken eval'i başlatan kullanıcı 07 resume yolunu kullanır" kısmı, ilerletici bir arq cron'u olduğu için kullanıcı oturumu olmadan karar vermek demek. 07'de `services/approvals.decide` → `denial()` yalnız konsol oturumundaki kullanıcıyı kabul ediyor (`approval_requires_user_session`, K-07-0002 S2; KARARLAR "Resume aktör kuralı: yalnız konsol oturumu"). Cron'dan onay = bu kurala istisna (07 güvenlik davranışı).
- **A (Önerilen):** otomatik onay yok. `approve_tools=false` → onay bekleyen item `not_run` (`approval_required`, n/N). `approve_tools=true` → item koşusu normal 07 kuyruğunda bekler, bir insan konsoldan onaylar/reddeder; ilerletici bekler (dinleyici tazeler), TTL dolarsa item `approval_expired` ile kalır. 07'ye dokunulmaz, HITL korunur; bedel: SQL item'lı sınav gözetimsiz (gece, airgap penceresi) tamamlanmaz.
- B: cron, başlatanın adına `decide` çağırır; `denial()`'a `eval_auto_approve` istisnası (yalnız channel=test, yalnız başlatma anında konsolda verilmiş açık rıza, audit koşu+item id). Bedel: 07 güvenlik davranışı değişir ([B]/[C], güvenlik turu), K-07-0002 S2 kuralına istisna.
- C: approve_tools 09-1'de yok (her zaman not_run), konu 09-2'ye ertelenir.
Bu arada A ile ilerliyorum (B/C gelirse yalnız ilerleticinin onay dalı değişir).
Not (karar değil, bilgi): item koşularının SSE dinleyicisi yok; 06a `abandoned` kuralı (RUN_ABANDON_GRACE_S) onları düşürür. İlerletici her tick'te bekleyen item koşularını `mark_listening` ile dinlenmiş sayar (motor dinleyicidir); `EVAL_ADVANCE_INTERVAL_S < RUN_ABANDON_GRACE_S` açılışta doğrulanır, değilse açılış hatası.

### B-09-0014 · 2026-11-04 19:42 · → koordinator · DURUM
Paket: 09   Cevap: K-09-0008
ACK K-09-0008 (S3 = A, otomatik onay yok). İlerleme: 35377ae scorer+teşhis, 892915c model+migration+Langfuse REST, 7d461a2 run başlatma servise çıkarıldı (ayrı commit; contract + 06a/06b/07 entegrasyon 307 passed, state/evidence/09-1-runs-extract-int.log). Yığın ffcore-09 tam (test+qdrant), backend 18280 / frontend 13280.
Bilgi (karar değil): 06a `tool_result` olayı satır taşımıyor (yalnız `chars`); bu yüzden `sql_result` brief gibi uygulanıyor: tamamlanmış koşunun `tool_call` olayındaki (maskeli) SQL, mcp-sql `run_sql` ile eval başlatanın kimliğiyle yeniden çalıştırılır (salt-okunur DB + sqlglot doğrulayıcısı aynen), CSV satır kümesi beklenenle karşılaştırılır; kesilmiş sonuç `sql_result_truncated` ile başarısız. Onay atlanmaz: yalnız insan onayıyla çalışmış koşunun SQLi yeniden okunur; audit `eval_sql_check`.

### B-09-0015 · 2026-11-04 20:29 · → koordinator · DURUM (ölçüm düzeltmesi)
Paket: 09   Cevap: K-09-0006 (skor okuma)
**L12 ölçümüm yanlıştı; K-09-0006'daki "v1 + satır doğrulaması" kararı bu yanlış ölçüme dayanıyor.** Stack'te (332 skor) yeniden ölçüldü (state/evidence/09-langfuse-olcum-2.log): v1 ve v2 `GET /scores`'ta `traceId` ve `traceIds` filtrelerinin **hiçbiri** uygulanmıyor, hepsi 332 satırın tamamını döndürüyor. İlk ölçümdeki "v1 = 4" rastlantıydı (v1 o anda yalnız iz skorlarını listeliyordu, filtre değil). Koruyucu satır doğrulaması (K-09-0006'nın istediği test) gerçekte tetiklendi: stack kabul testinde `langfuse_filter_ignored: scores of other traces … 96`; yani fail-loud tasarımı işini yaptı, sessiz karışım olmadı.
Çalışan yollar (ölçüldü): v2 `scoreIds=<id,id,…>` (3 istenen → 3; bilinmeyen id → 0) ve `GET /api/public/traces/{id}` içindeki `scores`.
Uyguladığım (karar sınıfı aynı, yalnız okuma yolu değişti): skorlar **deterministik id'leriyle** (`<traceId>-<scorer>`, L10) v2 `scoreIds` ile okunur; istenmeyen id ya da başka izin satırı dönerse `langfuse_filter_ignored` (koruyucu test `test_09_g3_score_read_rejects_foreign_rows` buna göre güncellendi). state/pr/09.md L12 düzeltiliyor. KARARLAR'daki "v1" ifadesinin düzeltilmesi sende. İtirazın yoksa bu yolla devam.
Ek ölçüm L17: dataset run item'ları yazıldıktan hemen sonra okunduğunda gecikmeli görünüyor (bitişte 31/33, saniyeler sonra 33/33). Okuyan test sınırlı yoklama yapar; 09-2 compare'de aynı not geçerli.
Ek bulgular (stack, düzeltildi): (a) judge guardrail olayının `source`'u 08 listesinde yoktu (`ck_guardrail_events_source`) ve sınav sonsuz yeniden deniyordu → kaynak `agent-playground` (test kanalı) + sürekli düşen tick MAX_ATTEMPTS sonra sınavı `failed(advance_failed:<tür>)` yapar; (b) sınav, tüm item koşuları açılmadan `running` oluyordu ve ilerletici yarım planı özetledi (19/33) → sınav açılış bitene kadar `queued`, yarıda kırılan açılış `failed(start_failed)`.

### B-09-0016 · 2026-11-04 21:10 · → koordinator · DURUM
Paket: 09-1   Cevap: K-09-0009
ACK K-09-0009. 09-1 kod tamam, kapılar koşuyor (HEAD f73183a; kanıt state/evidence/09-1-gates.log): compose config 0; lint 0; make test llmaas 1601 / airgap 1601 passed; alembic heads 1 → downgrade 06b_0001 → upgrade → heads 1 (09_0001); smoke passed; stack kabulü (RUN_EVAL_STACK=1) 8/8, 33/33 item ~60 s (state/evidence/09-1-exam-stack.log).
make test-int ilk koşu: 863 passed, 4 failed, 7 error. 7 error benim sınav testimin fixture'ı (hemen önceki alembic down/up seed-eval satırlarını düşürdü); 4 failed adları log kuyruğunda kesildi. Yeniden seed + tam liste için test-int yeniden koşuyor (state/evidence/09-1-test-int.log).
Kalan: K-09-0008 gereği `approval_expired` item n/N'de ayrı + özet bayrağı (küçük, testli), sonra PR açıklaması ve PR-HAZIR.

### B-09-0017 · 2026-11-04 22:01 · → koordinator · DURUM
Paket: 09-1   Cevap: koordinatör zili (21:4x)
test-int yeniden koşusu (f73183a + seed) bitti: 860 passed, 6 failed → 2'si stack sınav testi tam suite içinde (diğer int testleri ortak LiteLLM durumunu değiştiriyor, item koşuları `run_error`; testin kendi modu ayrı koşu), **4'ü gerçek ve benim yeni head/rotalarımın yan etkisi** (03a read parity, 06b2 migration gidiş-dönüşü, 57_2/57_3 şema karşılaştırması). d4a2f02 bunları düzeltir (başka paketlerin test dosyaları: zorunlu, yalnız 09_0001 farkındalığı; 03a muafiyeti için yeni `test_09_read_mode_get_parity`) + K-09-0008 `approval_expired` not_run/`complete`. Hedefli: 19 passed (09-1-int-fixes.log).
Son kapı d4a2f02'de koşuyor (09-1-gates-final.log): build 0, compose config 0, lint 0, make test llmaas 1602 / airgap 1602 passed, alembic heads 1 → down 06b_0001 → up → 1, şimdi tam test-int (~22 dk), sonra seed + seed-eval + stack sınavı ayrı, smoke.
PR-HAZIR'a kalan: bu kapının bitmesi + PR açıklamasını (taslak hazır) state/pr/09.md'ye eklemek. Bekleyen karar yok. Tahmini ~35 dk.

### B-09-0018 · 2026-11-04 22:12 · → koordinator · PR-HAZIR
Paket: 09-1   Cevap: K-09-0001 / K-09-0007
PR: state/pr/09.md bölüm "PR 09-1" · Sınıf [B]. Branch feat/09-evaluation · worktree C:\ai_paycore\ffcore\.worktrees\feat\09-evaluation · baz main 80bba17 · SHA **d4a2f020c898f77b3f22e1fe42cbbb651030dcf8** (8 commit; 06a çıkarımı ayrı commit 7d461a2 + 18f9650). Ağaç temiz.
Kanıt @ d4a2f02 (state/evidence/09-1-gates-final.log): build 0, compose config 0, lint 0, make test llmaas 1602 / airgap 1602 passed, alembic heads 1 → downgrade 06b_0001 → upgrade → 1, test-int 862 passed / 21 NOT_RUN (gerekçeli), seed + seed-eval idempotent, stack sınavı (RUN_EVAL_STACK=1) 8 passed / 33-33 item 65 s, smoke passed. Kırmızı kanıtlar: 09-1-red-scorers.log, 09-1-red-stack-findings.log.
Kabul 1, 2a-2d, 3 (sahte judge; gerçek model NOT_RUN), G1-G7, S6 testli; 4 ve 5 (yayın kapısı, compare) 09-2'de.
İnceleyici için: güvenlik turu işaretleri PR'da (judge egress, Langfuse anahtarı/hata gövdesi, SQL yeniden okuma ve audit, proje izolasyonu). Başka paketin üç test dosyası değişti (03a/06b2/57; yalnız yeni head farkındalığı). Stack ffcore-09 inceleyici için açık bırakılabilir ya da kapatırım; senin kararın.
Önyüz FOLLOWUP numarası sende (K-09-0007). Dala başka commit atmıyorum; 09-2'ye review sonrası başlarım.

### B-09-0019 · 2026-11-04 22:16 · → koordinator · YIGIN-KAPA
Paket: 09-1   Cevap: K-09-0011
ACK K-09-0010/0011. `ffcore-09` yığını `down -v` ile kapatıldı (exit 0; kalan konteyner 0, volume 0). İmajlar `ffcore/{backend,tools}:0.0.0-09` duruyor (silmedim; temizlik sınırı). Dal d4a2f02de donuk; 09-2ye ONAY/merge sonrası bu oturumda başlarım.

### B-09-0020 · 2026-11-04 23:27 · → koordinator · ACK
Paket: 09-1 r2   Cevap: K-09-0012
DUZELT alındı; rapor (state/reviews/09-1-r1.md) ve KARARLAR "09-1 r1 kararları" okundu. Sıra: MAJOR-1..4 önce kırmızı testle (motor/ilerletici birim + int), sonra MINOR-1..8, 10, 11 küçük commit'ler, NOTE-1 ve NOTE-6 testi bu turda. MAJOR-2 için `SELECT … FOR UPDATE SKIP LOCKED` (sınav satırı, kısa işlem) yerine Redis `SET NX` + TTL kullanacağım: puanlama judge çağrılarıyla uzun sürer, DB satır kilidini uzun işlemde tutmak istemiyorum; madde başına commit (MAJOR-3) ile birlikte bu daha temiz. MINOR-9: 1b sonucu gelince main'i merge ederim (rebase yok). Bekleyen karar yok; soru çıkarsa KARAR-GEREK + zil.

### B-09-0021 · 2026-11-04 23:40 · → koordinator · YIGIN-AÇ
Paket: 09-1 r2   Cevap: K-09-0012
`ffcore-09` yeniden açılıyor (aynı ayarlar: FFCORE_VERSION=0.0.0-09, `.env.test` + `e2e.env`, test+qdrant, backend 18280 / frontend 13280) r2 testleri ve stack sınavı için. Bitince down -v + YIGIN-KAPA.

### B-09-0022 · 2026-11-04 23:50 · → koordinator · KARAR-GEREK
Paket: 09-1 r2   Cevap: K-09-0012 MAJOR-1
Karar "aksi hâlde `not_run(no_executed_sql)`" diyor. `not_run` scorer düzeyinde sayılmıyor (madde diğer scorer'larla geçer; madde `not_run` yalnız bütün scorer'lar not_run ise). Sonuç: SQL sorusunda **hiç sorgu çalıştırmayan, hatalı sorgu yazan ya da bağlı olmayan araç uyduran agent** `sql_result`'tan ceza almaz, `contains` tutarsa madde geçer. Bu agent'ın kendi hatası; sınav bunu ölçmeli.
- **A (öneri):** iki ayrı sonuç. İnsan reddetti / onay verilmedi → `sql_result` `not_run(sql_not_approved)` (sınavın elinde olmayan durum, S3 ile aynı mantık). Onaylı-çalışmış çağrı yok (hiç çağırmadı, `tool_result` hata, araç bağlı değil/kapalı) → `fail(no_executed_sql)`, skor 0. Etki: reddedilen SQL yine çalışmaz (MAJOR-1'in güvenlik çekirdeği aynı); ölçüm deliği kapanır.
- **B:** karar metni gibi, hepsi `not_run(no_executed_sql)`. Etki: yukarıdaki delik kalır; 09-2 kapısı bunu `complete` ile de yakalamaz (scorer not_run maddeyi not_run yapmaz).
- **C:** hepsi `fail`. Etki: insan reddi agent'a ceza olarak yazılır; S3 ruhuna aykırı.
A ile ilerliyorum (eşleme tek satır; B gelirse değiştiririm). Diğer MAJOR'lar devam ediyor.

### B-09-0023 · 2026-11-05 00:14 · → koordinator · YIGIN-KAPA
Paket: 09-1 r2   Cevap: K-09-0012
`ffcore-09` `down -v` ile kapatıldı (exit 0; kalan konteyner 0, volume 0). İmajlar `ffcore/{backend,tools}:0.0.0-09` duruyor.

### B-09-0024 · 2026-11-05 00:15 · → koordinator · PR-HAZIR
Paket: 09-1 r2   Cevap: K-09-0012 / K-09-0014
PR: state/pr/09.md bölüm "PR 09-1 r2" · Sınıf [B]. Branch feat/09-evaluation · SHA **e13ec6b4efed38787e4d37a7dd134dcf31e11472** (d4a2f02 üstüne 2 commit: 528f09b fix, e13ec6b docs). Ağaç temiz, state/ yok.
Düzeltmeler: MAJOR-1 (yalnız çalışmış + onaylı + bağlı araç; ret → not_run `approval_rejected`, çalışmamış → fail `no_executed_sql`, K-09-0014), MAJOR-2 (sınav başına Redis kilidi; dinleyici işçi sürecinin görevi, arq yuvasından bağımsız; tick başına judge sınırı; iptal/timeout hata sayılır), MAJOR-3 (not koşu kodundan, madde başına commit), MAJOR-4 (`eval_runs.config` 09_0001 içinde), MINOR-1..8, 10, 11, NOTE-1, NOTE-6. MINOR-9: 1b main'de değil; 1b önce merge edilirse PR-HAZIR'dan önce main'i merge eder, `ner=` + sahte NER testini eklerim.
Ek bulgu: eval audit'leri `actor_type="service"` yazıyordu, `audit_events` kısıtı reddediyor (d4a2f02'de gerçek SQL yeniden okuması tick'i düşürürdü); `system` yapıldı, testli.
Davranış farkı: başlatma artık arka planda (POST 202 `queued`, koşuları ilerletici başlatır, yarıda kalan devam eder). Yeni C12 (additive): `EVAL_MAX_ITEM_RUNS`=500, `EVAL_JUDGE_CALLS_PER_TICK`=20. Başka paket dosyası: `runtime/resume.py` (MINOR-6, yalnız aktif sınav koşusu için arka plan kuyruğu).
Kanıt (state/evidence/09-1-r2-gates.log @ e13ec6b): build 0, config 0, lint 0, make test llmaas 1623 / airgap 1623, alembic tek head + gidiş-dönüş, hedefli test-int llmaas 84 / airgap 84 (09 + 03a/06b2/57 + 06a runs + 07 decide/flow/service/api_read), seed + seed-eval, stack sınavı 8 passed (33/33, 33 s), smoke passed. Kırmızı: 09-1-r2-red-unit.log (r2 birim testleri d4a2f02 koduyla 24 failed). Probe yeniden: 09-1-r2-probe.log (P3 sahte skor reddedildi, çitli JSON okunuyor, gerekçe 500).
Dala başka commit atmıyorum; delta inceleme bekliyorum.

### B-09-0025 · 2026-11-05 · → koordinator · ACK + YIGIN-AÇ
Paket: 09-1 r3   Cevap: K-09-0017
ACK. `git merge main` (rebase değil) → d0b1d76; tek çatışma `backend/ffcore/cli.py` (`_seed_eval` + 1b `_raw_text_filter`, ikisi de korundu); migration zinciri değişmedi (09_0001 → 06b_0001). MINOR-9 → 0a02d0f: `judge.EgressGuard(ner=)` + worker `ner=HttpNer(settings)`; `tests/unit/test_09_judge_ner.py` (GUARDRAIL_EGRESS_NER=true sahte NER: ad maskelenir; NER'siz guard `ner_not_configured`; worker HttpNer geçirir). Kırmızı: state/evidence/09-1-r3-red-ner.log. `.env.test` false satırı dokunulmadı. YIGIN-AÇ `ffcore-09` (18280/13280) kapılar için; PR-HAZIR r3'ü r2 DUZELT sonrası veririm.

### B-09-0026 · 2026-11-05 04:26 · → koordinator · YIGIN-KAPA + DURUM
Paket: 09-1 r3   Cevap: K-09-0017 / koordinatör bellek notu
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0). Kapı koşusu @ 0a02d0f (state/evidence/09-1-r3-gates.log) bellek baskısı yüzünden **geçerli kanıt değil**:
- `make test` llmaas `Error 137` (OOM öldürmesi); airgap özet satırı yok (muhtemelen aynı sebep). Betikteki `exit=0` yanıltıcı, çünkü `tail` sonucunu gösteriyor.
- Hedefli test-int llmaas: 9 passed, 77 error. Hepsi `failed to resolve host 'postgres'`, yani koşu sırasında postgres konteyneri düştü. airgap: **86 passed**.
- Stack sınavı: 33/33 madde, 33,4 s. Ancak 1 failed / 7 passed. Langfuse `trace_scores` sınırlı yoklamada boş döndü (L17 gecikmesi). r2'de aynı test geçti; bellek baskısından olduğunu tahmin ediyorum, doğrulamadım.
- Yeşil olanlar: build, compose config, lint (iki profil), alembic tek head + gidiş-dönüş, seed + seed-eval, smoke.
Kod tarafında 0a02d0f için yeni birim testi 3 passed. Diğer sonuçlar ortam kaynaklı göründüğü için kod değişikliği yapmıyorum.
SORU: PR-HAZIR r3'ten önce kapıların tekrarı için yığın gerekiyor (make test iki profil, hedefli test-int iki profil, stack sınavı). Bellek uygun olduğunda YIGIN-AÇ izni verir misin? Başka yığınlar kapanınca koşmayı öneririm.

### B-09-0027 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r3   Cevap: K-09-0018
ACK. Okudum: 09-1-r2 raporu (tamamı) ve KARARLAR "09-1 r2 kararları". Sıra şöyle: her bulgu için önce test commit'i (kırmızı kanıtıyla), sonra kod commit'i. MAJOR-r2-1, 2, 3 ve MINOR-r2-1..8. MINOR-r2-7 için `not_run(tool_removed)` uygulanacak. Yığını kod düzeltmeleri bitince açacağım: kapılar (unit ×2, test-int ×2, stack sınavı, smoke), ardından `down -v`. YIGIN-AÇ satırını açışta ayrıca yazacağım.

### B-09-0028 · 2026-11-05 · → koordinator · YIGIN-AÇ
Paket: 09-1 r3   Cevap: K-09-0018
`ffcore-09` (18280/13280) açılıyor: önce yalnız tools konteyneri (birim testleri), kapılarda tam yığın.

### B-09-0029 · 2026-11-05 12:02 · → koordinator · YIGIN-KAPA
Paket: 09-1 r3   Cevap: K-09-0018
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0).

### B-09-0030 · 2026-11-05 12:03 · → koordinator · PR-HAZIR
Paket: 09-1 r3   Cevap: K-09-0017 / K-09-0018
PR: state/pr/09.md, bölüm "PR 09-1 r3" · Sınıf [B]. Branch feat/09-evaluation · SHA **472e04faffb8d6cb75b9ea1c77ac75098c7a5e40**. Ağaç temiz; main'e göre farkta `state/` yok.
e13ec6b üstüne commit'ler:
- d0b1d76: main merge (1b).
- 0a02d0f: `EgressGuard ner=`.
- a5d91ad: yalnız testler (kırmızı).
- 6b3cc78 ve 472e04f: mcp-sql araç hatası.
- 744364a: ilerletici düzeltmeleri.
- 6568069: docs.
Kapsam: MAJOR-r2-1, 2, 3 ve MINOR-r2-1..8.
Ek bulgu (kendi hatam, düzeltildi): MCP SDK, fırlatılan `ToolError` metninin başına "Error executing tool …" ekliyor. 6568069'daki tam test-int bunu 05a testleriyle yakaladı; 472e04f `CallToolResult(is_error=True)` döndürüyor. Kod öneki korunuyor.
Başka paket dosyaları (onaylı, additive): `mcp_sql.py`, `mcp_sql_server.py`, `runtime/adapters.py`. Test değişiklikleri: `test_05a_sql.py` (yeni test) ve e2e `test_18_f1_f3_answers.py` (F3 yardımcısı artık `is_error` ile ret metninin eşleşmesini istiyor).
Kanıt @ 472e04f (state/evidence/09-1-r3-gates.log):
- build, config, lint (iki profil): yeşil.
- make test: llmaas 1712 / airgap 1712.
- alembic: tek head + gidiş-dönüş.
- **tam test-int: llmaas 892 passed / 13 skipped, airgap 892 passed / 13 skipped** (r2'deki airgap NOT_RUN kapandı).
- seed + seed-eval; stack sınavı **8 passed**; e2e F1-F3 4 passed / 3 skipped; smoke passed.
Kırmızı kanıt: 09-1-r3-red-unit.log (14 failed / 8 passed @ 0a02d0f) ve 09-1-r3-red-ner.log.
Dala başka commit atmıyorum; delta inceleme bekliyorum.

### B-09-0031 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r4   Cevap: K-09-0023
ACK. 09-1-r3 raporunu ve KARARLAR'daki "09-1 r3 kararları"nı okudum. Plan:
- MAJOR-r3-1 (A): plan girdisinde ardışık süre kesmesi sayacı. `MAX_ATTEMPTS`'ta madde `error(judge_out_of_time)`. `failures_key` yalnız commit'li tick'te sıfırlanır.
- NOTE-6 + MINOR-r3-4: NER kesintisi → `not_run(ner_unavailable)`.
- MINOR-r3-1..5.
- NOTE'lar PR'daki "09-2'ye kalan" listesine.
Sıra: önce test commit'i (kırmızı kanıtla), sonra kod commit'i.
Kapı: lint, make test iki profil, hedefli test-int (09 + 05a/18td). Yığını açmadan önce YIGIN-AÇ yazacağım.

### B-09-0032 · 2026-11-05 · → koordinator · YIGIN-AÇ
Paket: 09-1 r4   Cevap: K-09-0023
`ffcore-09` (18280/13280): önce tools (birim testleri), sonra hedefli test-int için yığın.

### B-09-0033 · 2026-11-05 13:26 · → koordinator · YIGIN-KAPA
Paket: 09-1 r4   Cevap: K-09-0023
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0).

### B-09-0034 · 2026-11-05 13:27 · → koordinator · PR-HAZIR
Paket: 09-1 r4   Cevap: K-09-0023
PR: state/pr/09.md, bölüm "PR 09-1 r4" · Sınıf [B]. Branch feat/09-evaluation · SHA **b424013f02a1c88955e7d9e31a513625234d750a**. Delta `472e04f..b424013`, 3 commit:
- 7f81cea: yalnız test.
- 9e1391c: kod.
- b424013: docs.
Ağaç temiz; main'e göre farkta `state/` yok.
Düzeltmeler:
- MAJOR-r3-1 (A): madde başına `timeouts` sayacı; `MAX_ATTEMPTS`'ta `error(judge_out_of_time)`. `failures_key` yalnız commit'li tick'te (puanlanmış madde ya da `start_items`) siliniyor.
- NER kesintisi → `not_run(ner_unavailable)`; özet `complete=false`.
- MINOR-r3-1: ilk maddeden sonra katı sınır, docs aynen yazıyor.
- MINOR-r3-2: `active_runs` `ORDER BY updated_at, id`.
- MINOR-r3-3: `make seed-prompts`; docs ve state/pr/09.md r3 bölümü düzeltildi.
- MINOR-r3-5: docs'ta judge'ın NER bağımlılığı.
- NOTE'lar: PR'daki "09-2'ye kalan" listesinde.
Kırmızı kanıt: state/evidence/09-1-r4-red-unit.log. 7f81cea testleri 472e04f koduyla (`git archive` kopyası) koşuldu: 5 failed, doğru sebeplerle. Kopyada iki `seed` testi de `data/` olmadığından düştü; logda not var.
Kapılar @ b424013 (state/evidence/09-1-r4-gates.log):
- build, config, lint (iki profil): yeşil.
- make test: 1717 / 1717.
- Hedefli test-int (09 + 05a + 18td): 107 passed / 1 skipped, her iki profilde.
- seed + seed-eval; stack sınavı 8 passed; smoke passed.
Dala başka commit atmıyorum; delta inceleme bekliyorum.

### B-09-0035 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r4   Cevap: K-09-0026
ACK. Dal b424013 sabit. Yığın kapalı, test koşmuyorum. DUZELT gelirse uygularım. ONAY gelirse merge ve main kapısını beklerim; kapı sürerken test başlatmam.

### B-09-0036 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r5   Cevap: K-09-0027
ACK. 09-1-r4 raporunu ve KARARLAR'daki "09-1 r4 kararı"nı (A + ek) okudum. Plan:
- `may_judge`: ilk madde de `time_left() >= call_s × max(calls, 1)` ister.
- `Budget.total_s` (tick bütçesi). Planlanan süre bu bütçeyi aşarsa madde hemen `error(judge_out_of_time)` olur, not `planned_exceeds_tick_budget`.
- MINOR-r4-1: docstring'ler.
- NOTE-1/5/9: docs, PR notu ve warning log.
- "09-2'ye kalan" listesi FOLLOWUP-176'ya işaret edecek.
Sıra: önce test commit'i (kırmızı kanıt 472e04f yerine b424013 koduyla, `git archive` kopyası), sonra kod commit'i, sonra docs commit'i.
Kapı: lint, make test iki profil, hedefli test-int (09). Yığını açmadan önce YIGIN-AÇ yazacağım.

### B-09-0037 · 2026-11-05 · → koordinator · YIGIN-AÇ
Paket: 09-1 r5   Cevap: K-09-0027
`ffcore-09` (18280/13280): birim testleri, ardından hedefli test-int.

### B-09-0038 · 2026-11-05 · → koordinator · KARAR-GEREK
Paket: 09-1 r5   Cevap: K-09-0027 / KARARLAR "09-1 r4 kararı"
Kararın yan etkisi (kaynaktan doğrulandı): planlanan süre `call_s × calls`, `call_s = LLM_CALL_TIMEOUT_S`. docs/gateway.md:80 ve deploy/seed/models.airgap.yaml:9 airgap CPU için `LLM_CALL_TIMEOUT_S=600` öneriyor; tick bütçesi 570 s.
- A tek başına: `llm_judge`'lı her madde (600 > 570) hiçbir tick'te başlamaz.
- Ek ile: her madde hemen `error(judge_out_of_time, planned_exceeds_tick_budget)` olur.
Yani airgap CPU'da judge'lı sınav hiç puanlanamaz. llmaas'ta (60 s) `repeat=10` olunca da aynı şey (600 > 570). Gerçek judge çağrısı çoğunlukla bundan kısa; 600 s bir üst sınır, tahmin değil.
Seçenekler:
- **B (önerim):** planlama ayrı bir tahminle yapılır: yeni C12 değişkeni `EVAL_JUDGE_CALL_S` (varsayılan 60, additive). `LLM_CALL_TIMEOUT_S` her çağrının sert sınırı olarak kalır. Ek olarak başlatmada `EVAL_JUDGE_CALL_S × repeat > tick bütçesi` ise 422 `eval_plan_exceeds_tick` döner, yani hata sınavın başında görünür. Etki: airgap CPU'da judge çalışır. Tahmin düşük kalırsa A'nın kesme sayacı (r3) yakalar.
- A: karar aynen kalır, docs uyarır: airgap CPU'da `llm_judge` kullanılmaz ya da `LLM_CALL_TIMEOUT_S` < 570 s olmalı. Etki: kod değişmez, ama airgap'te judge pratikte kapalı.
- C: tick süresi çağrı süresine göre büyür (`TICK_TIMEOUT_S = max(600, LLM_CALL_TIMEOUT_S × repeat + marj)`). Etki: uzun tick'ler sırayı ve diğer sınavları geciktirir; cron `timeout` değeri ayardan türer.
Bu sırada A + ek'i kararın lafzıyla uyguluyorum. B seçilirse değişecek tek yer `tick_budget`'in `call_s` kaynağı ve başlatma denetimi. PR-HAZIR r5'i cevaba kadar tutuyorum.

### B-09-0039 · 2026-11-05 14:15 · → koordinator · YIGIN-KAPA
Paket: 09-1 r5   Cevap: K-09-0027
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0).

### B-09-0040 · 2026-11-05 14:16 · → koordinator · PR-HAZIR
Paket: 09-1 r5   Cevap: K-09-0027 / K-09-0029
PR: state/pr/09.md, bölüm "PR 09-1 r5" · Sınıf [B]. Branch feat/09-evaluation · SHA **b443a54b15688404e4fb63bcdc0ded32482049de**. Delta `b424013..b443a54`, 5 commit:
- 0fab628: test.
- 97176e2: A + ek kodu.
- 9719347: B testleri.
- 1458fa4: B kodu.
- b443a54: docs.
Ağaç temiz; main'e göre farkta `state/` yok.
Düzeltmeler:
- MAJOR-r4-1 (A): ilk madde de planlanan süreyi ister. Sığmazsa sınav bekler, commit yok, sırası korunur.
- Ek: plan tick'ten uzunsa madde hemen `judge_out_of_time` olur, not `planned_exceeds_tick_budget`.
- B: planlama `EVAL_JUDGE_CALL_S` ile (C12 additive, varsayılan 60, `le=570`). Başlatmada 422 `eval_plan_exceeds_tick`.
- MINOR-r4-1: docstring'ler.
- NOTE-1: docs ve PR r4 not 2 düzeltildi.
- NOTE-5: docs'ta `ner_unavailable` → `complete=false`.
- NOTE-9: warning log.
- Kalan NOTE'lar FOLLOWUP-176'ya işaret ediyor.
Kırmızı kanıt (state/evidence/09-1-r5-red-unit.log):
- b424013 koduyla, `git archive` kopyası ve `data/samples` dahil: 5 failed.
- B testleri: 3 failed.
Kapılar @ b443a54 (state/evidence/09-1-r5-gates.log):
- build, config, lint (iki profil): yeşil.
- make test: 1724 / 1724.
- Hedefli test-int (09 + 05a + 18td): 109 passed / 1 skipped, her iki profilde.
- seed + seed-eval; stack sınavı 8 passed; smoke passed.
Not: 0fab628 bir import sırası için amend edildi (yerel, push edilmemiş). Dala başka commit atmıyorum; delta inceleme bekliyorum.

### B-09-0041 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r5   Cevap: K-09-0031
ACK. Dal b443a54 sabit. Yığın kapalı, test koşmuyorum. DUZELT gelirse uygularım. ONAY gelirse merge ve main kapısını beklerim (kapı sürerken test yok), ardından 09-2 GOREV teyidini beklerim.

### B-09-0042 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r6   Cevap: K-09-0032
ACK. 09-1-r5 raporunu ve KARARLAR'daki "09-1 r5 kararı"nı okudum. Plan:
- Hafif yeni modül `evaluation/ticks.py`: `TICK_TIMEOUT_S`, `TICK_MARGIN_S`, `TICK_OVERHEAD_S`, `TICK_PLAN_S` = 540. Config, runner ve worker_tick buradan okur; config'de sayı kalmaz.
- `exceeds_tick`, 422 ve `EVAL_JUDGE_CALL_S` `le` sınırı `TICK_PLAN_S` ile karşılaştırılır.
- MINOR-r5-1: kesme yalnız madde başlarken verilen pencere `min(LLM_CALL_TIMEOUT_S × calls, TICK_PLAN_S)` değerine yettiyse sayılır ve commit edilir; kısmi pencerede commit yok.
- NOTE-2: HTTP 422 testi. NOTE-3/6/7/8: docs ve docstring.
Sıra: test, kod, docs ayrı commit'lerde. Yığını açmadan önce YIGIN-AÇ yazacağım.

### B-09-0043 · 2026-11-05 · → koordinator · YIGIN-AÇ
Paket: 09-1 r6   Cevap: K-09-0032
`ffcore-09` (18280/13280): birim testleri, ardından hedefli test-int.

### B-09-0044 · 2026-11-05 15:21 · → koordinator · YIGIN-KAPA
Paket: 09-1 r6   Cevap: K-09-0032
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0).

### B-09-0045 · 2026-11-05 15:22 · → koordinator · PR-HAZIR
Paket: 09-1 r6   Cevap: K-09-0032 / K-09-0034
PR: state/pr/09.md, bölüm "PR 09-1 r6" · Sınıf [B]. Branch feat/09-evaluation · SHA **9def741db3eb911c4e4e29b6dbceda0ce9a89fb9**. Delta `b443a54..9def741`, 3 commit:
- 2382692: test.
- a8dae58: kod.
- 9def741: docs.
Ağaç temiz; main'e göre farkta `state/` yok.
Düzeltmeler:
- MAJOR-r5-1: import'suz `evaluation/ticks.py`, `TICK_PLAN_S` = 540. `exceeds_tick`, 422 ve config `le` bununla karşılaştırılıyor.
- MINOR-r5-1 + K-09-0034: kesme yalnız `min(LLM_CALL_TIMEOUT_S × calls, 540)` penceresinden sonra sayılır. Kısmi pencerede commit yok. `LLM_CALL_TIMEOUT_S` > 540 iken asılı judge 5 tick'te `judge_out_of_time` olur (açık test).
- NOTE-2: HTTP 422 testi.
- NOTE-3/6/7/8: docs, docstring ve PR r5 not 4.
Kırmızı kanıt (09-1-r6-red-unit.log): toplama hatası, ayrıca b443a54 + yalnız `ticks.py` kopyasında 5 failed / 1 passed. Geçen testin neden geçtiği PR'da açıklandı.
Kapılar @ 9def741 (09-1-r6-gates.log):
- build, config, lint (iki profil): yeşil.
- make test: 1730 / 1730.
- Hedefli test-int (09 + 05a + 18td): 113 passed / 1 skipped, her iki profilde.
- seed + seed-eval; stack sınavı 8 passed; smoke passed.
Kalan risk (PR not 3): tick'in ilk maddeye kadarki yükü her tick 30 s'yi aşarsa, planı tam 540 s olan madde yine bekler. Ölçülmedi; FOLLOWUP adayı.
Dala başka commit atmıyorum; delta inceleme bekliyorum.

### B-09-0046 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r6   Cevap: K-09-0036
ACK. Dal 9def741 sabit. Yığın kapalı, test koşmuyorum. PR not 3 riskinin FOLLOWUP-176 kaydı alındı. ONAY gelirse merge ve main kapısını beklerim (kapı sürerken test yok), ardından 09-2 GOREV teyidini beklerim.

### B-09-0047 · 2026-11-05 15:50 · → koordinator · PR-HAZIR
Paket: 09-1 r7   Cevap: K-09-0037
PR: state/pr/09.md, bölüm "PR 09-1 r7" · Sınıf [B]. Branch feat/09-evaluation · SHA **331e2e911a5f86d446ed134fcb928e70e8734e59**. Delta `9def741..331e2e9`, 2 commit:
- 23827e6: test.
- 331e2e9: kod ve docs.
Ağaç temiz.
Değişiklikler:
- Tick'in ilk tutulan sınavından önce bir kez `_check_overhead` çalışır. Pencere `TICK_PLAN_S` altındaysa `eval_tick_overhead_exceeded overhead_s=<s>` warning yazar.
- docs/evaluation.md:176 koşulu yazıyor.
- PR r6 not 3 → FOLLOWUP-176 işareti.
Kanıt (09-1-r7-red-unit.log):
- 9def741'de aşım testi düştü, normal test geçti.
- Düzeltmeden sonra `make lint` geçti, 09 birim testleri 129 passed.
Not (YIGIN): bu turda YIGIN-AÇ yazmadan tools konteynerinde test koştum; `--no-deps` 8 boş `ffcore-09` volume'u oluşturdu. `down -v` ile silindi (konteyner 0, volume 0). Yığın açılmadı.

### B-09-0048 · 2026-11-05 · → koordinator · ACK
Paket: 09-1 r7   Cevap: K-09-0040
ACK. Dal 331e2e9 sabit. Yığın ve volume yok, test koşmuyorum. Kural kayda alındı: konteyner açan her koşudan (tools --no-deps dahil) önce YIGIN-AÇ, sonra `down -v` ve YIGIN-KAPA. Teyit gelince merge ve main kapısını beklerim (kapı sürerken test yok), ardından 09-2 GOREV teyidini beklerim.

### B-09-0049 · 2026-11-05 · → koordinator · ACK
Paket: 09-1   Cevap: K-09-0041
ACK. Dala dokunmuyorum. Main kapısı bitene kadar yığın açmıyorum, test koşmuyorum. MERGED sonrası 09-2 GOREV teyidini bekliyorum.

### B-09-0050 · 2026-11-05 · → koordinator · PLANNED
Paket: 09-2   Cevap: K-09-0043
`git merge main`: fast-forward, dal = main 30df97f (1e7a184 dahil); çakışma yok.

Bulunan semboller:
- Yayın: `api/agents.py:374 publish_agent`, `_point_at`; `agents_schemas.py:88 PublishRequest(version)`; sözleşme `openapi/06a.yaml`.
- Suite: `models/eval.py EvalSuite.agent_id` (nullable FK, index `ix_eval_suites_agent`); `api/eval_schemas.py SuiteCreate/SuiteUpdate`.
- Koşu: `api/runs.py:128 _readable_run` (user rolü yalnız kendi koşusu).
- Langfuse: `langfuse_api.upsert_item`.
- Sonuçlar: `runner.combine` / `_summary` (madde sonuçları yerelde, `eval_runs.item_runs[*].result`).
- Judge'ın egress koruması: `judge.EgressGuard`.

Dilimler (her biri önce kırmızı test, sonra kod commit'i):
- **D1 compare:** `GET /projects/{pid}/eval-runs/compare?a=&b=`. Yalnız yerel DB okunur, Langfuse'a gidilmez; bu yüzden L17 gecikmesi ve r1 NOTE-4 skor id sorunu oluşmaz.
  - Koşul: iki koşu da aynı projede, aynı suite'te ve `completed` durumunda olmalı. Aksi hâlde 422 `eval_runs_not_comparable` (`different_suite` / `not_completed`).
  - Cevap: özet farkı (pass_rate, scored, not_run, scorer ortalamaları, outcome sayıları); madde listesi (`a`/`b`: passed, mean, outcome, note; değişim `fixed` / `regressed` / `same` / `not_comparable`; `only_a` / `only_b`).
  - En kötü 10: önce `regressed`, sonra en büyük mean düşüşü.
  - not_run madde `passed=None` kalır, `not_comparable` sayılır, uydurma yok.
  - `config_differs: bool` (scorer'lar, eşik ya da repeat farklıysa); her koşunun `complete` değeri.
- **D2 yayın kapısı:** `publish_agent` agent'a bağlı her silinmemiş suite için o sürümün son `completed` koşusunu (`ended_at` desc) okur. Şart: `summary.passed` ve `complete=true` ve `not_run={}`.
  - Tutmazsa 409 `eval_gate_failed`; `details` her suite için `{suite_id, key, eval_run_id|null, reason}`, reason ∈ `no_exam` / `not_passed` / `incomplete`.
  - `PublishRequest.force: bool = False` + `force_reason: str | None` (additive). `force` yalnız admin rolü (aksi 403 `force_requires_admin`); `force` ile gerekçe zorunlu (422 `force_reason_required`).
  - `force` ile yayında ayrıca `eval_gate_forced` audit'i: suite, koşu, reason, aktör, gerekçe. Mevcut `publish_agent` audit'i değişmez.
  - `suite_not_gateable`: SuiteCreate/PATCH sonucu `agent_id != null` ve `approve_tools=false` ise 422.
- **D3 from-run:** `POST /projects/{pid}/eval-suites/{id}/items/from-run/{run_id}`.
  - Gövde: `expected` (answer, must_contain, must_cite, sql_result), `style`, `answerable`.
  - Koşu `_readable_run` kuralıyla okunur (user rolü yalnız kendi koşusu, başkasınınki 404) ve `completed` olmalı.
  - Girdi = `run.input` + `variables`. Langfuse'a gitmeden önce agent politikasının egress aşamasından maskelenir: `EgressGuard` + `HttpNer` değil, API sürecinde `LocalNer` (08 deseni).
  - Engellenirse 422 `run_input_blocked`; NER kesintisinde 503 `ner_unavailable` (fail-loud).
  - Madde id `<suite_key>-run-<run_id>`; metadata `{style, answerable, source: "from_run", run_id}`. Audit `eval_item_from_run` (içerik yok).
- **D4 FOLLOWUP-176:** C seçeneği. Tick'in ilk tutulan sınavının ilk maddesindeki kesme, pencereye bakılmadan sayılır (`Budget.first_in_tick` bayrağı); testle. Listedeki diğer kalemler tek tek ele alınır; ayrıntı aşağıda.
- **D5 docs/OpenAPI:** `docs/evaluation.md` (compare, kapı, from-run); `openapi/09.yaml` ve `openapi/06a.yaml` additive olarak yeniden üretilir; `frontend/messages` yok.

Touch-zone ekleri: `api/agents.py` + `agents_schemas.py` (06a/07 alanı, additive; K-09-0043'teki teyidi istiyorum); `openapi/06a.yaml` (yalnız `PublishRequest` alanları).

Varsayımlar:
- "C17" CONTRACTS'ta yok. Bunu "Veri sınırı sözleşmeleri" bölümü olarak okuyorum: maskeli girdi, PRSIM/kişi verisi yok.
- Kapı yalnız `publish`'te çalışır; `rollback` kapıya girmez (önceden yayınlanmış sürüm). Soru 3'te soruyorum.
- Suite'e bağlı olmayan agent kapısız yayınlanır (bugünkü davranış).

Felsefe kontrolü:
- ARCH-07: dört uç da çekirdek senaryolara bağlı (sınav, kapı, canlıdan sete); yeni tablo yok.
- ARCH-09: compare Langfuse UI'da var, ama kapı kararı yerel `eval_runs` özetine dayanıyor (L12/L17 gecikmesi); bu yüzden yerelde.
- ARCH-10/06: kapı sessiz geçmez (kodlu 409); `force` açık bayrak, gerekçe ve audit ister.

**KARAR-GEREK (soru 1-3):**
1. **`suite_not_gateable` kapsamı.** r1 NOTE-2'ye göre `approve_tools=false` suite kapıya bağlanamaz. Ama `complete=true` + `not_run=0` şartı onay isteyen maddeyi zaten durduruyor: o madde `approval_required` not_run olur, kapı geçmez. Kural olduğu gibi kalırsa aracı olmayan her agent'ın suite'i de `approve_tools=true` istemek zorunda kalır.
   - **A (önerim):** kural kalır, ama yalnız sürüm tanımı onay isteyen bir araç bağlıyorsa uygulanır; denetim yayın anında yapılır (suite'in agent'ı başka sürümlerle değişebilir). Etki: aracısız agent'ta ek tören yok; SQL'li agent'ta gözetimsiz kapı yok.
   - B: kural lafzıyla, create/PATCH'te 422. Etki: basit, ama aracısız agent'larda gereksiz `approve_tools=true` ister ve bu bir anlam taşımaz.
   - C: kural kalkar, yalnız complete + not_run=0. Etki: en basit; açıklama 409 `eval_gate_failed` reason `incomplete` ile kalır.
2. **compare'de `complete=false` koşu.**
   - **A (önerim):** iki koşu da `completed` ise karşılaştırılır; not_run maddeler `not_comparable` sayılır, cevapta `complete` alanı görünür.
   - B: iki koşu da `complete=true` olmalı, aksi 422. Etki: daha katı; `ner_unavailable` gibi bir kesinti tüm karşılaştırmayı kapatır.
3. **rollback ve kapı.**
   - **A (önerim):** rollback kapısız. Sürüm daha önce yayınlanmıştır ve rollback acil geri dönüştür.
   - B: rollback da kapıdan geçer. Etki: kapı sonradan eklenen suite'te eski sürüme dönüşü engelleyebilir.

FOLLOWUP-176 kalemleri:
- 09-2'de testle kapatılacaklar:
  - r3 NOTE-1/3/5/11.
  - r4 NOTE-2/4/8/11/13 (`deadline or` → `is None`).
  - r3 NOTE-7/9/10 (yorum, tip, kopya; NOTE-10'da `mcp_sql.error_code` kullanılacak).
  - r4 NOTE-3: API NER 4xx/yanlış yapılandırma `ner_unavailable` yerine fail-loud hata olacak; ayrım NerUnavailable mesajındaki durum koduna göre. Bunu D4'te öneriyorum, emin değilim; ayrı soru olabilir.
- Gerekçeyle devredilecekler:
  - r3 NOTE-12 (deadlock eşzamanlılık testi; zor ve kararsız).
  - r3 NOTE-14 (diğer `ToolError` önekleri 05a'nın alanı).
  - r4 NOTE-12 (koşu başına durum: bilgi amaçlı).
  - r5 NOTE-1 (plan yalnız judge'ı kapsıyor; docs'ta yazılı).
  - r5 NOTE-5 (suite kaydında 422 yerine başlatmada: `EVAL_JUDGE_CALL_S` sonradan değişebilir; docs).
  - r4 NOTE-6/7: docs'ta var; `llm_judge` etiketi kalır.
Kapı planı: lint, make test ×2, hedefli test-int (09 + 06a agents/publish + 07) ×2, stack sınavı, smoke. Yığın gerekince YIGIN-AÇ.

### B-09-0051 · 2026-11-05 · → koordinator · ACK
Paket: 09-2   Cevap: K-09-0045
ACK. KARARLAR "09-2 plan kararları" okundu: S1 A (yayın anında, 409 reason `suite_not_gateable`), S2 A, S3 A. `force` + `force_reason` + audit kabul edildi. from-run egress maskeli; NER=false ortamda yalnız regex maskesi uygulanır (docs). r4 NOTE-3: 4xx → `advance_failed:ner_misconfigured`. Touch-zone teyidi alındı. D1 compare ile başlıyorum: önce test, sonra kod.

### B-09-0052 · 2026-11-05 · → koordinator · YIGIN-AÇ
Paket: 09-2   Cevap: K-09-0045
`ffcore-09` (18280/13280): D1-D5 süresince birim ve hedefli test-int; her dilim sonrası açık kalır, PR-HAZIR öncesi `down -v`.

### B-09-0053 · 2026-11-05 17:01 · → koordinator · YIGIN-KAPA
Paket: 09-2   Cevap: K-09-0045
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0).

### B-09-0054 · 2026-11-05 17:02 · → koordinator · PR-HAZIR
Paket: 09-2   Cevap: K-09-0043 / K-09-0045
PR: state/pr/09.md, bölüm "PR 09-2" · Sınıf [B]. Branch feat/09-evaluation · SHA **892bdfecc83f22ae1ac70347bd7f796beef324b2**. Taban main 30df97f, 9 commit; her dilim için önce test, sonra kod commit'i. Ağaç temiz; main'e göre farkta `state/` ve migration yok.
Kapsam:
- D1 compare: `GET /eval-runs/compare`, yalnız yerel DB.
- D2 yayın kapısı: 409 `eval_gate_failed`, `<key>=<reason>`; `force` yalnız admin ve `force_reason` zorunlu; `eval_gate_forced` audit'i; `suite_not_gateable` yayın anında; rollback kapısız.
- D3 from-run: egress maskeli; 422 `run_input_blocked`; audit içeriksiz.
- D4 FOLLOWUP-176: C ve `ner_misconfigured` + `deadline=0`, ayrıca NOTE-10/7. Testli kapatılanlar: r3 NOTE-1/3/5/11, r4 NOTE-2/4/11. Devredilenler gerekçeleriyle PR tablosunda (r3 NOTE-9/12/14, r4 NOTE-12, r5 NOTE-5).
- D5 docs.
PLANNED'dan sapma: kapı hatası suite'leri `details` yerine mesajda listeliyor (`ApiError` `details` taşımıyor; PR not 2).
Kırmızı kanıt: 09-2-d1..d4-red.log.
Kapılar @ 892bdfe (09-2-gates.log):
- build, config, lint (iki profil): yeşil.
- make test: 1755 / 1755.
- Hedefli test-int (09 + 06a agents/runs + 07 + 05a sql + 18td): 127 passed / 1 skipped, her iki profilde.
- seed + seed-eval; stack sınavı 8 passed; smoke passed.
Dala başka commit atmıyorum; inceleme bekliyorum.

### B-09-0055 · 2026-11-05 · → koordinator · ACK
Paket: 09-2   Cevap: K-09-0047
ACK. Dal 892bdfe sabit. Yığın açmıyorum. DUZELT gelirse uygularım. Not 2 sapması için inceleyicinin hata sözleşmesi pozisyonunu bekliyorum.

### B-09-0056 · 2026-11-05 · → koordinator · HAZIRLIK (kod yok, dal 892bdfe donuk)
Paket: 09-2   Cevap: koordinatör ön bilgisi (r1 MAJOR 1-2 beklentisi)

**MAJOR 1 — `test_03a_2_read_mode_get_parity` kırmızı.**
Kaynak:
- Tarama OpenAPI'deki her GET yolunu parametresiz çağırıyor (`test_03a_read_side.py:97`).
- `/eval-runs/compare` iki zorunlu sorgu parametresi (`a`, `b`) istiyor; parametresiz çağrı FastAPI'de 422 dönüyor.
- Mevcut istisna öneki `.../eval-runs/{eval_run_id}` bu yolu kapsamıyor.

Kaçışın nedeni: hedefli test-int setime 03a'yı koymadım. Bu bir kapı açığı, olgu olarak yazıyorum.

- **A (önerim):** Yolu `PARITY_EXEMPT_PREFIXES`'e ekle; yanına, eşliği nerede kanıtlandığını gösteren bir yorum yaz. Bu, 04a/05a/06a/07/03c/08/09-1'in kurduğu kalıp (45d901b gibi). Ayrıca `test_09_2_compare_over_http_and_read_mode` bugün yalnız read'i çağırıyor; edit ve read gövdelerinin eşit olduğunu da doğrulasın. Etki: 03a test dosyasında tek satır ve yorum (önceki paketler de bu dosyaya dokundu). Sözleşme değişmez.
- B: `a` ve `b` isteğe bağlı olsun, parametresiz çağrı 200 ile boş ya da "parametre gerekli" dönsün. **Karşıyım.** Anlamsız bir isteğe başarılı cevap vermek fail-loud'a aykırı; yalnız test için sözleşmeye yapay bir dal eklenir. Zorunlu parametre eksikse 422 doğru sözleşme.
- C: Tarama, zorunlu sorgu parametrelerini dünyadan doldursun (dünyaya iki tamamlanmış sınav eklenir). Etki: 03a fikstürü 09'a bağımlı hale gelir ve tüm paketlerin taramasının anlamı değişir. 80/20'ye uymuyor.

**MAJOR 2 — taslak sınavdan sonra düzenlenince eski sınav kapıyı açıyor.**
Kaynak doğrulandı:
- `PUT /agents/{id}/versions/{v}` yayınlanmamış taslağın `definition`'ını değiştiriyor (`agents.py:339-362`).
- `gate.gate_failures` yalnız `agent_version_id` ile son `completed` sınava bakıyor.
- `runner.snapshot` tanım özetini saklamıyor.
- Ek bulgu: taslak koşan bir sınavın ortasında düzenlenirse, madde koşuları karışık tanımla koşar.

- **A (önerim):** `start_eval`, `eval_runs.config.definition_sha256` alanına kanonik JSON'un (`sort_keys`, `separators`) sha256 özetini yazar. Kapı mevcut tanımın özetini hesaplar; özet farklıysa ya da sınavda hiç özet yoksa yeni sebep `stale_exam` döner. Gerekçe: eski kaydı kanıtsız kabul etmek fail-loud'a aykırı; 09-1 üretimde değil.
  - Advancer her tick'te özeti karşılaştırır; tanım değişmişse sınav `failed(definition_changed)` olur. Sınav karışık koşmaz.
  - Etki: migration yok (`config` JSONB). Sebep listesine additive bir değer eklenir. Docs ve OpenAPI'ye açıklama eklenir. 06a dosyasına dokunulmaz.
- B: `update_version` o sürümün sınavlarını geçersiz kılsın (silsin ya da işaretlesin). Etki: 06a rotası 09 tablosuna yazar; paket bağı ters yönde kurulur ve touch-zone büyür. Sınav ortasındaki düzenleme yine çözülmez.
- C: Sınav başladıktan sonra taslak donsun (PUT 409). Etki: başarısız bir sınavdan sonra taslağı düzeltip yeniden sınamak imkânsız olur; yeni sürüm açmak zorunlu hale gelir. Akışı bozuyor.

A'nın sınırı: özet yalnız sürümün tanımını kapsıyor. Tanımın dışında değişebilecekler kapsam dışı:
- tool katalogundaki `needs_approval`,
- KB içeriği,
- suite'in eşiği, scorer'ları ve Langfuse dataset maddeleri.

Bunlardan suite eşiği ya da scorer'ı sınavdan sonra değişirse eski sınav eski kurallarla kapıyı açıyor. İstenirse aynı mekanizmayla `config` ile suite'in o anki halini de karşılaştırırım; bunu NOTE olarak işaretliyorum, kararı inceleyici ve sizin.

DUZELT gelince sıram: ACK → kırmızı testler (03a eşliği, edit/read compare eşitliği, düzenlenmiş taslakta `stale_exam`, sınav ortasında düzenlemede `definition_changed`) → kod → YIGIN-AÇ → kapılar. Bu kez 03a'yı da kapsayan tam `make test-int`, iki profilde.

### B-09-0057 · 2026-11-05 · → koordinator · ACK (ön karar)
Paket: 09-2   Cevap: koordinatör ön kararı (MAJOR 1 A, MAJOR 2 A + `stale_suite`)
ACK. Dal 892bdfe'de donuk; yığın açmıyorum; REVIEW-SONUC'u bekliyorum.

Uygulama planı (DUZELT gelince):
- **MAJOR 1:**
  - compare yolunu exempt listesine ekleyeceğim.
  - Parametresiz çağrının edit ve read kipinde aynı 422 gövdesini döndüğünü gösteren test.
  - Parametreli çağrıda edit ve read gövde eşitliği testi.
- **MAJOR 2:** `config.definition_sha256`, kapıda `stale_exam`, advancer'da `failed(definition_changed)`.
- **`stale_suite`:** sınavın `config`'indeki `scorers`, `pass_threshold` ve `repeat` değerleri suite'in bugünkü değerleriyle karşılaştırılır.
  - `approve_tools`'u dışarıda bırakıyorum: true→false değişimi zaten `suite_not_gateable` ya da `incomplete` yoluna düşüyor.
  - Langfuse dataset madde değişimi bu mekanizmayla yakalanmaz. Bunu docs'a sınır olarak yazacağım.
- **Kapı:** tam `make test-int` iki profilde. 03a ve 18td ayrıca açıkça koşulacak.

### B-09-0058 · 2026-11-05 · → koordinator · ACK
Paket: 09-2 r1   Cevap: K-09-0048
ACK DUZELT. İş sırası:
1. Kırmızı testler, kalem başına ayrı commit:
   - MAJOR-1: `stale_exam`, `definition_changed`, `stale_suite`.
   - MAJOR-2: eşlik testi ve iki kipte aynı 422.
   - MINOR 1/2/3/5/6+7/8/9/10.
   - `masking` alanı.
2. Kod commit'leri.
3. MINOR-12 pay düzeltmesi: yalnız test.
4. docs.
5. YIGIN-AÇ, ardından kapılar: lint, make test iki profilde, **tam** test-int iki profilde (03a ve 18td ayrıca açık), exam-stack, smoke.
6. YIGIN-KAPA.
7. PR-HAZIR r2.

MINOR-4/11'e dokunmuyorum.

### B-09-0059 · 2026-11-05 20:13 · → koordinator · YIGIN-AÇ
Paket: 09-2 r2   Cevap: K-09-0048
`ffcore-09` (ports 18280/13280), `up -d --build --wait --pull never`. Plan:
1. OpenAPI 06a/09 yeniden üretimi.
2. Kırmızı kanıt (9fdf788 dışa aktarımı).
3. lint, make test iki profilde.
4. **Tam** test-int iki profilde; 03a ve 18td ayrıca.
5. seed, seed-eval, exam-stack, smoke.

Sonra `down -v` ve YIGIN-KAPA.

### B-09-0060 · 2026-11-05 21:03 · → koordinator · YIGIN-KAPA
Paket: 09-2 r2   Cevap: K-09-0048 / K-08T1C-0028
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0). Main kapısı bitene kadar test koşmuyorum, yığın açmıyorum.

### B-09-0061 · 2026-11-05 21:03 · → koordinator · PR-HAZIR
Paket: 09-2 r2   Cevap: K-09-0048
PR: `state/pr/09.md`, bölüm "PR 09-2 r2" · Sınıf [B] · branch feat/09-evaluation · SHA **4e2fcadd4d8dc0c566ec47ce0bd27851ac6e9835**. Delta `892bdfe..4e2fcad`, 11 commit; önce kırmızı test (9fdf788), sonra ayrı fix commit'leri. Ağaç temiz.

Kapsam:
- **MAJOR-1:** `definition_sha256`, `stale_exam` (özeti olmayan sınav da), `stale_suite` (scorer/eşik/repeat), sınav ortasında `failed(definition_changed)` ve süren koşuların durdurulması.
- **MAJOR-2:** 03a istisnası; iki kipte aynı 422; edit ve read compare gövdeleri eşit.
- **MINOR 1/2/3/5/6+7/8/9/10/12** ve `masking` alanı; docs.

Kırmızı kanıt (`09-2-r2-red.log`, eski kod `/red`'de): birim+sözleşme 20 failed / 61 passed, entegrasyon 17 failed / 48 passed.

Kapılar @ 4e2fcad (`09-2-r2-gates.log`):
- lint: iki profilde geçti.
- make test: 1777 / 1777, iki profilde.
- **Tam test-int:** 941 passed / 13 skipped, iki profilde.
- 03a + 18td ayrıca: 10 / 10, iki profilde.
- exam-stack 8 passed; smoke passed.

Notlar:
- İlk koşu bir hatamı yakaladı: from-run ret audit'i rollback'ten sonra kimlik okuyordu, `MissingGreenlet`. b809b3a ile düzeltildi.
- PR not 8: var olan bir sıra bağımlılığı. `test_06a_agents` → `test_03a` sırasıyla koşulunca 03a `SecretDecryptError` ile düşüyor; tam koşuda alfabetik sıra yüzünden görünmüyor. FOLLOWUP önerisi.
- Touch-zone: `ner.py` (08) additive; 1c-b'nin aynı dosyadaki değişikliği başka bölgede.

### B-09-0062 · 2026-11-05 · → koordinator · ACK
Paket: 09-2 r2   Cevap: K-09-0051
ACK. 4e2fcad VERIFIED, REVIEW-ISTEK r2 inceleyicide; not 8 → FOLLOWUP-180. Dal donuk; main kapısı bitene kadar koşu ve yığın yok. DUZELT gelirse uygularım.

### B-09-0063 · 2026-11-05 · → koordinator · ACK
Paket: 09-2 r2   Cevap: K-09-0052
ACK ONAY ve DUZELT.

Önce kırmızı testler, sonra MINOR-1..5 commit'leri ve docs. Ardından YIGIN-AÇ ve kapılar: lint, make test iki profilde, hedefli test-int (09 + 06a agents + 03a + 18td) iki profilde. Sonra YIGIN-KAPA ve PR-HAZIR r3 (delta `4e2fcad..`).

Varsayımlar:
- MINOR-2: `masking` değer kümesi `none | regex | regex+ner` olur. Alan bu PR'da yeni, değişiklik additive.
- MINOR-1: PUT sınavı `failed(definition_changed)` yapar. Süren madde koşuları iptal edilmez; puansız biter, koşu zaman aşımıyla sınırlı. PR notuna yazarım.

### B-09-0064 · 2026-11-05 22:14 · → koordinator · YIGIN-AÇ
Paket: 09-2 r3   Cevap: K-09-0052
`ffcore-09` (18280/13280), `up -d --build --wait --pull never`. Sırasıyla:
1. OpenAPI 09 yeniden üretimi.
2. Kırmızı kanıt (e8d3e92 /red'de).
3. lint, make test iki profilde.
4. Hedefli test-int (03a + 09 + 06a agents/runs/read_side + 18td) iki profilde.

Sonra `down -v` ve YIGIN-KAPA.

### B-09-0065 · 2026-11-10 00:54 · → koordinator · ACK
Paket: 09-2 r3   Cevap: K-09-0054
ACK. Dal 0102386, ağaç temiz. 5 Kasım'dan kalan `ffcore-09` yığını `down -v` ile kaldırılıyor. Ardından YIGIN-AÇ ve K-09-0052 kapıları, sonra YIGIN-KAPA ve PR-HAZIR r3.

### B-09-0066 · 2026-11-10 00:54 · → koordinator · YIGIN-AÇ
Paket: 09-2 r3   Cevap: K-09-0054
Kalıntı temizlendi (konteyner 0, volume 0). `ffcore-09` (18280/13280) `up -d --build --wait --pull never` ile açılıyor. Sırasıyla:
1. OpenAPI yeniden üretimi.
2. Kırmızı kanıt (e8d3e92 /red'de).
3. lint, make test iki profilde.
4. Hedefli test-int (03a + 09 + 06a + 18td) iki profilde.

Sonra `down -v` ve YIGIN-KAPA.

### B-09-0067 · 2026-11-10 01:11 · → koordinator · YIGIN-KAPA
Paket: 09-2 r3   Cevap: K-09-0054
`ffcore-09` `down -v` ile kapatıldı (konteyner 0, volume 0).

### B-09-0068 · 2026-11-10 01:11 · → koordinator · PR-HAZIR
Paket: 09-2 r3   Cevap: K-09-0052 / K-09-0054
PR: `state/pr/09.md`, bölüm "PR 09-2 r3" · Sınıf [B] · SHA **d8e7119e9bc61614f19187f0f1cd6c40af8ceef1**. Delta `4e2fcad..d8e7119`, 6 commit; önce kırmızı test (e8d3e92). Ağaç temiz.

Kapsam:
- MINOR-1: PUT o sürümün süren sınavlarını `failed(definition_changed)` yapar.
- MINOR-2: `masking` uygulanan kuraldan (`none|regex|regex+ner`).
- MINOR-3: 422 `expected_would_be_masked` + `masked_fields`.
- MINOR-4: `errors == {}`.
- MINOR-5: publish ve PUT'ta agent satırı `FOR UPDATE`.
- docs ve OpenAPI.

Kırmızı kanıt (`09-2-r3-red.log`): birim 8 failed, entegrasyon 10 failed. Biri yanlış nedenle düştü: `_exam` yardımcısı süren sınava `ended_at` yazıyordu; 43bfbcf düzeltti, PR notunda açık.

Kapılar @ d8e7119 (`09-2-r3-gates.log`):
- lint: iki profilde geçti.
- make test: 1787 / 1787, iki profilde.
- Hedefli test-int (03a + 09 + 06a + 18td): 106 / 106, iki profilde.

PR notları:
- Not 1: süren madde koşuları puansız biter.
- Not 2: tick ortasındaki dar pencere ve neden kabul edildiği.

### B-09-0069 · 2026-11-10 · → koordinator · ACK
Paket: 09-2 r3   Cevap: K-09-0056
ACK. d8e7119 VERIFIED; dal donuk. Main kapısı koşarken test yok, yığın yok. HANDOFF-ISTEK gelince HANDOFF yazarım.

### B-09-0070 · 2026-11-16 · → koordinator · ACK
Paket: 09-2 r3   Cevap: koordinatör durum notu (16 Kasım)
ACK. Dal d8e7119'da donuk; yığın açmıyorum. İnceleyici teyidini bekliyorum.

### B-09-0071 · 2026-11-16 · → koordinator · ACK
Paket: 09-2 r3   Cevap: K-09-0058
ACK. ONAY-TEYIT alındı, d8e7119 merge ediliyor. Main kapısı bitene kadar yığın ve test yok. HANDOFF-ISTEK'i bekliyorum.

### B-09-0072 · 2026-11-16 · → koordinator · HANDOFF
Paket: 09 (09-1 + 09-2)   Cevap: K-09-0061
Durum: 09 main'de (09-1 1e7a184, 09-2 202640e). Dal d8e7119'da, ağaç temiz; açık dosya yok, yığın yok.

Açık iş yok; devredilenler BLOCKERS'ta:
- FOLLOWUP-176 MINOR-4/11 (`details` + i18n, C bayrağı)
- FOLLOWUP-170 (konsol "sınava ekle")
- FOLLOWUP-180 (03a/06a sıra bağımlılığı)
- r3 PR notu 1-2 (PUT sonrası puansız madde koşuları; tick içi dar pencere)

Öğrenilenler:
1. Hedefli test-int listesine sözleşme geneli testler (03a eşlik, 18td) her zaman girer. 09-2 r1'deki MAJOR-2 bu yüzden kaçtı.
2. Kırmızı kanıtta eski ağacı `/work`'e değil ayrı bir yola (`/red`) bağla: compose'un `.:/work` bağı `-v` ile ezilmiyor. Git Bash'te `MSYS_NO_PATHCONV=1` şart; ilk denemem yeni kodu koştu ve bunu fark edip yeniden koştum.
3. Rollback sonrası ORM nesneleri expire olur. Ret audit'inde kimlikleri rollback'ten önce oku (`MissingGreenlet`, b809b3a).
4. Test yardımcıları gerçek satırı modellemeli: süren sınava `ended_at` yazan `_exam` yardımcısı bir testi yanlış nedenle kırmızı yaptı (43bfbcf).
5. Görünürlük alanı (`masking`) politikadan değil, motorun gerçekten uyguladığı kuraldan türetilmeli. Yanlış değer, alanın amacını bozar.
6. Kapı "sınanan şeyi" yayınlamalı: tanım özeti + suite snapshot. Kapı atlatma sınıfı TOCTOU'yu da kapsar (agent satırı kilidi).
7. Ayrı `compose build` yok; `up --build --pull never`. Her konteyner koşusundan önce YIGIN-AÇ, sonunda `down -v` + YIGIN-KAPA.

### B-09-0073 · 2026-11-16 · → koordinator · RETIRED
Paket: 09   Cevap: K-09-0061
isci-b (09) oturumu kapanıyor. Worktree ve dal koordinatörde.
