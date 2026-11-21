# Arşiv: isci-c · 11

Salt okunur; mesajlar ve ID'ler değişmeden taşındı (MULTI_AGENT_PROTOCOL 'Bağlam bütçesi ve arşiv'). Taşıma: 2026-11-21, koordinatör.

### C-11-0001 · 2026-11-20 19:45 · → koordinator · ACK
Paket: 11 · Cevap: K-11-0001, K-GEN-0033
Yeni isci-c oturumu (lease `ffcore-isci-c-11`) GOREV'i aldı. Zorunlu okuma tamam (FELSEFE, FELSEFE_UYGULAMA, MULTI_AGENT_PROTOCOL, SECURITY, KARARLAR indeks + Dalga 8/DECISION-193/10c-1 r1/sse-bekci/06a/02/10c-2/04b-2, plan/11, WORK_QUEUE 11, BLOCKERS 112/121/135). Worktree `.worktrees/feat/11-chat` açıldı (dal `feat/11-chat`, baz main 1c0abcd = 029934a + yalnız state commit'i). Sıradaki: kod keşfi ve PLANNED; PLAN-ONAY gelmeden kod yok.

### C-11-0002 · 2026-11-20 20:20 · → koordinator · DURUM
Paket: 11 · Cevap: K-11-0001 · Durum: PLANNED
Ayrıntılı plan: `state/pr/11.md` "Plan" (semboller, rota/bileşen ağacı, backend B1-B8, kabul→test, göç `11_0001`, felsefe). Bulgu: konuşma/mesaj tabloları 06a'da hazır ama **okuma/silme ucu yok**; `GET /agents` analyst ister (`user` rolü liste alamaz); kaynak olayında parça metni yok (FOLLOWUP-116); feedback ucu var (MemberWriter, score adı `expert_feedback`); başlık `input[:80]`. Bölme: **11-1** B1-B5+B7, D1-D3 + test paneli ortak bileşenleri; **11-2** B6+B8, D4-D6 + docs. Sorular (hepsinde önerim A):
- **S1** konuşma uçları (liste/mesajlar/sil): **A** yeni `api/conversations.py` + `api/__init__.py` modül listesine bir satır (touch-zone eki); B `runs.py` içine (800 satır büyür); C agents.py altına (yanlış kaynak).
- **S2** başlık 60: **A** `services/runs_start.py` `input[:80]`→60 (brief; touch-zone eki, 80'i doğrulayan test varsa bilerek değişir); B 80 kalır, brief/docs düzeltilir.
- **S3** kaynak parça metni: **A** `GET /runs/{r}/sources/{chunk_id}` runs.py'de, yalnız koşunun sources olayındaki chunk, silinmiş belge 404 `source_deleted`, belge ACL'i çağırana yeniden uygulanır; B 04a `knowledge.py`'ye chunk ucu (başka touch-zone, Reader=analyst, `user` alamaz); C metin yok, yalnız ad/sayfa (kabul 2 karşılanmaz).
- **S4** geri bildirim: **A** mevcut uç; score adı kanala göre (`chat`→`user_feedback`, diğerleri `expert_feedback` aynen); read kullanıcıda düğme pasif (MemberWriter değişmez); aynı mesajda uzman oyu son oyu ezer (audit ikisini tutar); B ad hep `expert_feedback` (ARCH-13: son kullanıcı oyu "uzman" görünür); C ayrı chat feedback ucu + read'e açık (ikinci yol, kalıcı karmaşıklık).
- **S5** `user` rolü agent listesi: **A** yeni `GET /chat/agents` (her üye; yalnız key/ad/açıklama/portal_config/show_confidence, tanım yok); B `GET /agents`'ı `user`'a açmak (tanım/prompt sızar).
- **S6** `/chat`'te proje: **A** konsolla aynı çerez + sohbet başlığında proje seçici, seçim yoksa açık "proje seçin" (ARCH-10, otomatik ilk proje yok); B kullanıcının tüm projelerindeki agent'lar tek listede (çok projeli sorgu, yeni uç).
Varsayım (soru değil): onay düğmesi `rol ≥ assign_to && edit` (backend `resume`/07 ile aynı); bekleme sırasında GET yoklama, durum değişince `/stream` ile devam; `app/page.tsx` `user` rolünü `/chat`'e yönlendirir. PLAN-ONAY bekliyorum.

### C-11-0003 · 2026-11-20 20:35 · → koordinator · ACK
Paket: 11 · Cevap: K-11-0002, K-GEN-0035
PLAN-ONAY alındı (S1-S6 A; touch-zone ekleri conversations.py + __init__ satırı, runs_start.py yalnız başlık, runs.py sources ucu). Notlar uygulanacak: `source_not_visible` ayrı kod, docs/evaluation.md score adı cümlesi, `/chat/agents` tanım taşımaz testi, 'proje seçin' iki tema + mobil. Her test koşusu tee ile `state/evidence/11-1-*.log`. 11-1 başladı: önce kırmızı backend testleri.

### C-11-0004 · 2026-11-20 21:05 · → koordinator · YIGIN-AC
Paket: 11 · Cevap: K-11-0002 · Yigin: ffcore-11
18770/13770, `--env-file .env.test`, `--pull never`, imaj `0.0.0-main` → `0.0.0-11` etiketi (build yok; testler kaynaktan, worktree bağlı). Önce yalnız postgres + redis (+ migrate): hedefli test-int `tests/integration/test_11_chat.py` kırmızı → yeşil (tam test-int değil, ENV-209 sırası istenmedi). e2e aşamasında aynı yığına `up --build --pull never` ile backend/frontend eklenecek; o zaman ayrıca DURUM.

### C-11-0005 · 2026-11-20 22:10 · → koordinator · DURUM
Paket: 11 · Cevap: C-11-0004 · Durum: IMPLEMENTED
11-1 kod commit'li (dal feat/11-chat, 7 commit: test/kod ayrı). Hedefli test-int `test_11_chat.py` 18/18 (`11-1-b-green-int*.log`), unit+contract 104 (`11-1-b-green-unit.log`), önyüz lint/typecheck/check:api 0 + Vitest 296 (`11-1-f-gate-2.log`). Şimdi aynı yığın `ffcore-11` tam açılıyor: `--profile test up -d --wait --build --pull never` (imaj `0.0.0-11` dal kodundan), seed-prompts + superadmin, `FAKE_EMBED=1`; e2e: 11 spec'leri, sonra test paneli/giriş etkilenen spec'ler ve tam koşu (`--grep-invert @model-missing --workers=1`). Bitince `down -v` + YIGIN-KAPA.

### C-11-0006 · 2026-11-20 23:05 · → koordinator · YIGIN-KAPA
Paket: 11 · Cevap: C-11-0004 · Yigin: ffcore-11
`down -v` (profiller test, e2e, tools) + elle açılan `ffcore-11_e2e_node_modules` silindi; konteyner 0, volume 0 (`state/evidence/11-1-down.log`). `ffcore/{backend,tools,frontend}:0.0.0-11` etiketleri duruyor.

### C-11-0007 · 2026-11-20 23:06 · → koordinator · PR-HAZIR
Paket: 11 · Cevap: K-11-0002 · SHA: d31574b385e1a590ab8727983ac7a5542be55820
**11-1** (sohbet çekirdeği) hazır: dal `feat/11-chat`, delta `main...d31574b` (merge-base 1c0abcd) 11 commit, 52 dosya (40 + 12 görüntü), state/ yok. PR notu `state/pr/11.md` "PR 11-1" bölümü (kabul→test, komutlar, bilerek değişen testler, varsayımlar).
Kapı: backend `make lint && make test` 2120×2 (llmaas/airgap); hedefli test-int `test_11_chat.py` 18/18; önyüz lint/typecheck/check:api 0 + Vitest 296; e2e 11 spec'leri 8/8; tam e2e 186 passed + düşen 11'in tekrarı: 10c3 9/9 (sahte upstream'le), `test_11_1` ve `test_10ab_2` geçti; kalan tek `test_10bp1_10` stand-in ready = `/readyz` `ollama_runtime_context` (yığında Ollama yok, ENV-204, dokunulmayan kod). Loglar `state/evidence/11-1-*.log`.
Bilerek değişen testler: `test_06a_openapi` EXPECTED (+5 yol), `test_03a_write_flag` (`delete_conversation` muaf). Not: GOREV'deki "bir satır" `api/__init__.py`'de import + liste = iki satır; 404 `source_reindexed` ek kod (belge duruyor, parça yeniden indekslenmiş). Tam test-int koşulmadı (ENV-209; istenirse sıra rica ederim). 11-2'ye REVIEW sonrası ya da onayınla geçerim.

### C-11-0008 · 2026-11-20 23:40 · → koordinator · DURUM
Paket: 11 · Cevap: K-11-0004 · Durum: PLANNED
**11-2 planı** `state/pr/11.md` "PR 11-2 · Plan" (semboller, D4-D6 dosyaları, backend B6/B8, kabul→test, felsefe). Kod yok; dal 11-1 merge'ünden sonra `feat/11-2-chat`. Sorular (önerim A):
- **S1 geri bildirim (S4'ü yeniden açıyorum, gerekçeli):** `GET /runs?feedback=pending` (F9 uzman kuyruğu) `messages.feedback IS NOT NULL` ile süzer; son kullanıcının oyu aynı alana yazılırsa koşu uzman kuyruğundan düşer, sonraki uzman oyu da kullanıcınınkini ezer. **A** göç `11_0001`'e ikinci additive kolon `messages.user_feedback jsonb`; `FeedbackRequest.source` (`review` varsayılan, eski davranış aynen | `chat`), `chat` → yeni kolon + score `user_feedback`, yalnız koşunun kullanıcısı; F9 dokunulmaz. B onaylı S4 aynen (tek alan, ad kanala göre): kuyruk hatası kalır, belgelenir. C ayrı chat uç (`/runs/{id}/rating`): A ile aynı veri, ikinci yol.
- **S2 Portal ayarı yeri:** **A** ajan sihirbazında ayrı "Portal" sekmesi, sürüm fieldset'i dışında, kendi Kaydet'i (PATCH, analyst+edit; yayınlanmış ajanda da düzenlenir); B ayrı sayfa `/agents/{id}/portal`.
- **S3 kontrast tutmayan vurgu:** **A** sunucu yalnız hex doğrular; önyüz açık/koyu ton türetir (≥ 4.5:1 metin), konsol önizlemesi iki temada gösterir; türetilen tonun kullanıcının rengi olmadığı önizlemede yazılı. B kontrast tutmayan renk 422 (kullanıcı başka renk seçer; tek temada uygun renk diğerinde reddedilebilir).
- **S4 onay bekleyen kullanıcıya "bildirim":** **A** yeni bildirim yok; chat "{rol} onayı bekleniyor" der ve yoklamayla sürer; onaylayıcı 07 kuyruğu/sayaçla görür. B 03c bildirimleri onaylayıcı rollere (kapsam büyür, ayrı FOLLOWUP).

### C-11-0009 · 2026-11-20 23:50 · → koordinator · ACK
Paket: 11 · Cevap: K-11-0005
11-2 PLAN-ONAY alındı (S1-S4 A). Notlar uygulanacak: chat oyu sonrası koşu `feedback=pending` kalır + uzman oyu ezmez + iki score adı testli; Portal sekmesi read'de salt görünüm; ton türetimi deterministik ve kontrastı testli, önizleme iki tema; 'onay bekleniyor' rol adı messages json'dan, yoklama `RUNS_POLL_MS`/10b bekçisi. Kod yok; 11-1 MERGED duyurusunu bekliyorum, sonra `feat/11-2-chat` main'den, kapı `11-2-*.log`.

### C-11-0010 · 2026-11-21 00:05 · → koordinator · ACK
Paket: 11 · Cevap: K-11-0006
DUZELT 11-1 r2 alındı: (1) MINOR-1 `axe-gecis-kararsiz` test_11_4 mobilde sheet opacity geçişi duruma bağlı beklenir, e2e ×4; (2) NOTE-3 + NOTE-2 docs/chat.md; (3) NOTE-1 kopuş Vitest'i 11-2 plan notuna. Test/docs ayrı commit, aynı dal `feat/11-chat`; yığın `ffcore-11` (YIGIN-AC ayrıca).

### C-11-0011 · 2026-11-21 00:20 · → koordinator · YIGIN-AC
Paket: 11 · Cevap: K-11-0006 · Yigin: ffcore-11
18770/13770, `--env-file .env.test`, `--profile test up -d --wait --no-build --pull never` (imaj `0.0.0-11` mevcut; r2 yalnız test+docs), `FAKE_EMBED=1`; seed-prompts + superadmin; e2e `test_11_4` ×4 ardışık (`11-1-r2-e2e-x4.log`). Tam test-int yok. Bitince `down -v` + YIGIN-KAPA.

### C-11-0012 · 2026-11-21 00:55 · → koordinator · YIGIN-KAPA
Paket: 11 · Cevap: C-11-0011 · Yigin: ffcore-11
`down -v` (test, e2e, tools): konteyner 0, volume 0 (`11-1-r2-down.log`).

### C-11-0013 · 2026-11-21 00:56 · → koordinator · PR-HAZIR
Paket: 11 · Cevap: K-11-0006 · SHA: f9d213fdded017f843b5e7120e0ad6526a4e8d40
**11-1 r2** hazır: delta `d31574b..f9d213f` 2 commit (test 82c4a85, docs f9d213f), 2 dosya +15/-4; backend ve ürün kodu değişmedi. MINOR-1: `test_11_4` mobilde sheet/backdrop `data-starting-style` kalkması + `opacity: 1` + koşan animasyon yok beklenir (sabit bekleme yok); e2e ×4 ardışık 16/16 (`11-1-r2-e2e-x4.log`). NOTE-3 + NOTE-2 docs/chat.md; NOTE-1 11-2 plan tablosunda. Önyüz lint 0 / typecheck 0 (`11-1-r2-frontend-gate.log`). PR notu `state/pr/11.md` "PR 11-1 r2". Bilerek değişen test: `test_11_4` (yalnız bekleme).

### C-11-0014 · 2026-11-21 01:10 · → koordinator · ACK
Paket: 11 · Cevap: K-11-0012 · SHA: 97342eb
DUZELT-MAIN alındı. Dal `fix/11-1-parity` (worktree `.worktrees/fix/11-1-parity`, main 97342eb). Düzeltme yalnız test: 03a `PARITY_EXEMPT_PREFIXES`'e `conversations/{conversation_id}`, 06a döngüsünde `runs/{run_id}/sources/{chunk_id}` atlanır (gerekçe yorumlu); `test_11_chat.py`'ye `test_11_4_read_mode_get_parity` (aynı üye edit→read, 4 GET aynı durum+gövde). Ürün kodu değişmez. Tam test-int ffmain YIGIN-KAPA'nı bekler.

### C-11-0015 · 2026-11-21 01:10 · → koordinator · YIGIN-AC
Paket: 11 · Cevap: K-11-0012 · Yigin: ffcore-11
18770/13770, `--env-file .env.test`, `FFCORE_VERSION=0.0.0-11p`, `--profile test up -d --wait --build --pull never` (dal kaynağından); önce main'de kırmızı kanıt (`11-1-parity-red.log`), sonra dalda 03a/06a/11 hedefli (`11-1-parity-green.log`). Bitince `down -v` + YIGIN-KAPA.

### C-11-0016 · 2026-11-21 01:35 · → koordinator · DURUM
Paket: 11 · Cevap: K-11-0012, K-11-0014 · SHA: 43f5ed86021b41f2d54b192afed3181677e7be0f
**Parity düzeltmesi:** `fix/11-1-parity` 43f5ed8 (tek test commit'i, 3 dosya +37; ürün kodu değişmedi). Kırmızı main 97342eb'de: 03a/06a/11 dosyaları 2 failed, 24 passed (`11-1-parity-red.log`; aynı iki KeyError). Dalda: ruff 0, aynı üç dosya **27 passed** (`11-1-parity-green.log`); `make lint && make test` llmaas **2159 passed** (`11-1-parity-make-test.log`). Yöntem notu: yığın C-11-0015'te yazdığım `--build 0.0.0-11p` yerine `--no-build` `0.0.0-11` ile açıldı (tools kaynağı `.:/work` bağlı; `uv.lock`/`pyproject`/Dockerfile f9d213f..main arasında aynı).
**@model-missing (madde 4):** ffcore-11'i main'den `--build` (`0.0.0-11m`), `FAKE_EMBED=0` ile açtım; spec **koşmadı**: makinede **disk doldu**: seed-prompts'ta Langfuse 500, create-superadmin `psycopg DiskFull: No space left on device`, e2e'de redis unhealthy (`11-1-parity-model-missing.log`). Disk dolmadan önce alınan `/readyz` spec'in beklediği gibi: `not_ready`, warmup `failed` `model_missing` (bge-m3 yok), `ollama_runtime_context` ve `ollama_context` **skipped** (failed değil). Bu temiz yığında ENV-204 belirtisi yok ve 11-1 readiness'e dokunmuyor. ffmain'deki düşüşün olası nedeni aynı disk dolması ya da K-11-0014'teki karışık FAKE_EMBED; trace sende. Spec'i senin tekrar koşunla sınıflandırmanı öneririm. **Disk uyarısı:** `docker system df` Images 81.9 GB (70.9 GB geri alınabilir), Volumes 24.7 GB; ffmain e2e tekrarı da etkilenebilir. Başkasının imajını silmedim; temizlik kararı sende.
**Bekleyen:** ENV-209 tam test-int (senin YIGIN-KAPA'n ve disk açılınca), sonra PR-HAZIR.

### C-11-0017 · 2026-11-21 01:35 · → koordinator · YIGIN-KAPA
Paket: 11 · Cevap: C-11-0015 · Yigin: ffcore-11
`down -v` (test, e2e, tools): konteyner 0, volume 0 (`11-1-parity-down.log`).

### C-11-0018 · 2026-11-21 01:50 · → koordinator · PR-HAZIR
Paket: 11 · Cevap: K-11-0012, K-GEN-0036 · SHA: 43f5ed86021b41f2d54b192afed3181677e7be0f
**11-1 parity** hazır: dal `fix/11-1-parity`, delta `main..43f5ed8`: 1 commit (test), 3 dosya +37, ürün kodu değişmedi. Main'de kırmızı (2 failed, `11-1-parity-red.log`); dalda 03a/06a/11 27 passed (`-green.log`); `make lint && make test` 2159 passed (`-make-test.log`). Tam test-int K-GEN-0036 gereği koşulmadı (ENV-217 disk), kapıda. Bilerek değişen testler: 03a/06a muafiyetleri (gerekçeli) + yeni `test_11_4_read_mode_get_parity`. PR notu `state/pr/11.md` "PR 11-1 parity".

### C-11-0019 · 2026-11-21 06:40 · → koordinator · ACK
Paket: 11 · Cevap: K-11-0018, K-11-0019 · SHA: 2f9a25e
11-2 başladı: dal `feat/11-2-chat` yerel main 2f9a25e'den (worktree `.worktrees/feat/11-2-chat`, origin'e dokunulmadı). Bağlayıcı: K-11-0005 S1-S4 A, KARARLAR '11-2 plan kararları'. Sıra: backend kırmızı (göç `11_0001`, `user_feedback`, `portal_config`) → kod → önyüz kırmızı (onay/ask_user/oy/portal, NOTE-1 kopuş Vitest'i) → kod → e2e → docs; test/kod/docs ayrı commit, changelog'da 11-2 üstte. FOLLOWUP-135 kapanış notu PR'da. OpenAPI ve ortak modül dokunulacağı için PR-HAZIR öncesi tam test-int slotu isteyeceğim. Yığın açarken YIGIN-AC.

### C-11-0020 · 2026-11-21 06:55 · → koordinator · YIGIN-AC
Paket: 11 · Cevap: K-11-0019 · Yigin: ffcore-11
11-2 backend: postgres+redis, `--env-file .env.test`, `--no-build --pull never` (`0.0.0-11`; tools kaynağı `.:/work` bağlı, bağımlılık değişmedi); hedefli test-int kırmızı/yeşil (`11-2-b-*.log`). Önyüz e2e için sonra `--build` ile tam test profili. Bitince `down -v` + YIGIN-KAPA.

### C-11-0021 · 2026-11-21 08:10 · → koordinator · DURUM
Paket: 11 · Cevap: K-11-0019 · Yigin: ffcore-11
11-2 ilerleme: backend (göç `11_0001`, `source: chat` → `user_feedback`, `portal_config`) hedefli 149 passed (`11-2-b-green-int-2.log`; kırmızı `11-2-b-red-int.log` 10 failed); önyüz lint/typecheck/check:api 0, Vitest 323/323 (`11-2-f-gate-2.log`; kırmızı `11-2-f-red-vitest.log`). ffcore-11 (C-11-0020) şimdi tam test profiliyle genişliyor: `--build --pull never` `0.0.0-11b`, `FAKE_EMBED=1`, e2e 11 spec'leri + Langfuse public API'den `user_feedback` score sorgusu (tools konteyneri; anahtarlar yazılmaz) (`11-2-e2e-run1.log`).

### C-11-0022 · 2026-11-21 09:05 · → koordinator · ISTEK
Paket: 11 · Cevap: K-11-0019 · SHA: b957c66 · Yigin: ffcore-11
**Tam test-int slotu istiyorum** (FOLLOWUP-216: 06a OpenAPI, `agents_schemas`, `runs.py` feedback, `models/*`, göç `11_0001` değişti). Dal `feat/11-2-chat` b957c66 (test/kod/docs ayrı, 8 commit). e2e 11 spec'leri 14/14 (`11-2-e2e-run2.log`), 10bp2 panel regresyonu 29/29 (`11-2-e2e-panel.log`); Langfuse public API'de `user_feedback` score 1 (value `wrong`, not dâhil; `11-2-e2e-run1.log`). ffcore-11 açık (test profili); slot verilince aynı yığında `make test-int` koşarım, sonra `down -v` + YIGIN-KAPA + PR-HAZIR. Bu arada `make lint && make test` iki profil.

### C-11-0023 · 2026-11-21 10:05 · → koordinator · YIGIN-KAPA
Paket: 11 · Cevap: C-11-0020, C-11-0022 · Yigin: ffcore-11
`down -v` (test, e2e, tools, qdrant): konteyner 0, volume 0 (`11-2-down.log`). Tam test-int slotu geri veriliyor.

### C-11-0024 · 2026-11-21 10:05 · → koordinator · PR-HAZIR
Paket: 11 · Cevap: K-11-0019, K-11-0021 · SHA: b957c6691da0d7c7547a43eea9c952bdb1a752f7
**11-2** hazır: dal `feat/11-2-chat`, delta `main..b957c66` (baz 2f9a25e): 8 commit (test → kod → test → kod → test → docs), 42 dosya +1892/−119. Göç `11_0001` (`messages.user_feedback`, `agents.portal_config`; heads tek, up/down/up). Kapı: tam test-int **1188 passed / 42 skipped** (`11-2-test-int-2.log`; ilk deneme qdrant'sız koşmadı, `-test-int.log`); `make lint && make test` llmaas + airgap 2159 + 2159; önyüz lint/typecheck/check:api 0, Vitest 323/323; e2e 11 14/14, 10bp2 panel 29/29; Langfuse public API'de `user_feedback` score 1. Bilerek değişen testler: `test_11_1_chat_agents_carry_no_definition` (+`portal_config`), `test_11_1_chat_view` fikstürü (+`user_feedback`), kendi `test_11_3_portal_tab` hatam. **FOLLOWUP-135 kapanabilir** (sohbette `QuestionBox`, e2e `test_11_7_ask_user`). Sapmalar PR notunda: Langfuse score'u e2e konteynerinden değil tools'tan sorgulandı (e2e'de anahtar yok, `deploy/` touch-zone dışı); vurgu zemin değerleri gerekçeli eslint-disable + tokens.css testi. PR notu `state/pr/11.md` "PR 11-2".

### C-11-0025 · 2026-11-21 10:40 · → koordinator · YIGIN-AC
Paket: 11 · Cevap: K-11-0024 · Yigin: ffcore-11
11-2 r2: postgres+redis, `--env-file .env.test`, `--no-build --pull never` (`0.0.0-11b`, tools kaynağı bağlı); hedefli test-int kırmızı/yeşil (`test_11_2_chat`, `test_06a_feedback`, `test_06a_run_access`, `test_11_chat`; `11-2-r2-*.log`) + `make test` llmaas. Bitince `down -v` + YIGIN-KAPA.

### C-11-0026 · 2026-11-21 11:00 · → koordinator · YIGIN-KAPA
Paket: 11 · Cevap: C-11-0025 · Yigin: ffcore-11
`down -v`: konteyner 0, volume 0 (`11-2-r2-down.log`).

### C-11-0027 · 2026-11-21 11:00 · → koordinator · PR-HAZIR
Paket: 11 · Cevap: K-11-0024 · SHA: 2085aa47e8cbcac531708bd49a4c0d90407cd117
**11-2 r2** hazır: delta `b957c66..2085aa4`: 3 commit (test c912697, kod d470bd9, docs 2085aa4),  8 files changed, 71 insertions(+), 15 deletions(-). MINOR-1 A: `user` + `review` (varsayılan dâhil) → 403 `not_reviewer`, F9 kuyruğu etkilenmez; MINOR-2 tablo düzeldi; NOTE-1 cümlesi. Kırmızı 3 failed, yeşil hedefli 154 passed; `make test` 2159; Vitest 323. Bilerek değişen test: `test_06a_r1_feedback_user_own_run_with_edit` (kullanıcı oyu `source: chat`). PR notu `state/pr/11.md` "PR 11-2 r2".

### C-11-0028 · 2026-11-21 13:30 · → koordinator · HANDOFF
Paket: 11 · Cevap: K-11-0030, K-11-0031 · SHA: 6590719
**Bitenler (11 DONE):**
- 11-1 (merge 15f1da9): `/chat` çekirdeği; konuşma uçları, kaynak parça ucu (çağıranın ACL'i), başlık 60 karakter, iki tema + telefon.
- 11-1 parity düzeltmesi (fix/11-1-parity 43f5ed8, merge d3f96ed): 03a/06a muafiyetleri + `test_11_4_read_mode_get_parity`.
- 11-2 (merge 6590719):
  - inline onay; yetkisiz kullanıcıda "{rol} onayı bekleniyor", yoklama ile sürer
  - ask_user cevabı (FOLLOWUP-135 kapandı)
  - kullanıcı oyu: `messages.user_feedback`, score `user_feedback`; `user` + review → 403 `not_reviewer`
  - Portal sekmesi ve `portal_config`, vurgu tonu türetme
  - göç `11_0001`
- test-int 1143 → 1190.

**Açık kalanlar (bende değil, kayıtlı):**
- FOLLOWUP-219: readiness `_context_needs` `limits.context_tokens` okuyor, seed `context_window` yazıyor; Ollama bağlam denetimi yalnız yayımlanmış agent varken çalışıyor. 04b-2/01 kapsamı, 11 kodu dokunmadı.
- FOLLOWUP-220: e2e `npm ci` registry soket kopması (ortam). 11-2 e2e'lerim proje yığınının node_modules volume'üyle `npm ci` sonrası geçti.
- `not_reviewer` için önyüzde ayrı mesaj yok (sohbet hep `source: chat`); gerekirse küçük bir errors.ts eki.
- e2e konteynerinde Langfuse anahtarı yok. `user_feedback` score'u tools'tan sorgulandı. İstenirse `deploy/` touch-zone'unda e2e servisine anahtar eklemek ayrı iş.

**Temizlik (kullanıcı/koordinatör kararı):**
- Worktree'ler silinmeye hazır, hepsi merge edildi, kirli dosya yok:
  - `.worktrees/feat/11-chat` (f9d213f)
  - `.worktrees/fix/11-1-parity` (43f5ed8)
  - `.worktrees/feat/11-2-chat` (2085aa4)
- İmajlar kullanıcı temizliğine (≈31 GB):
  - `ffcore/{backend,tools,frontend}:0.0.0-11`
  - `ffcore/{backend,tools,frontend}:0.0.0-11b`
- ffcore-11 yığını kapalı: konteyner 0, volume 0.
- Scratchpad betikleri oturuma özel; repoda iz yok.

Yeni kod/konteyner işi yok; RETIRED'ı bekliyorum.
