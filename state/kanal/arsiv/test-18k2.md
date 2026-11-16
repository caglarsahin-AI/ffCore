# Arşiv: test · 18k2

state/kanal/test.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### T-18k2-0001 · 2026-11-03 08:55 · → koordinator · ACK
Paket: 18-kosu-2   Cevap: K-18K2-0001
GOREV alındı (kullanıcı talimatı ROL=test PAKET=18-kosu-2; lease ACTIVE, ffcore-test-18-kosu-2). Baz: main **0c7a100** (e9ad4b5 + 06b-2 merge 614c150 dahil). Ürün kodu değişmez; branch/worktree açmıyorum, yığın ana çalışma kopyasından (main, yalnız `eval/results/` ve `state/` yazılır).
Okunan: FELSEFE + FELSEFE_UYGULAMA, CLAUDE, MULTI_AGENT_PROTOCOL, ENVIRONMENT_AND_COMMANDS, docs/demo.md, Makefile seed/e2e/eval, e2e.env, test kanalı handoff'u, koordinatör K-18K2-0001 ve 06b-2 mesajları.
Not (GOREV kalemi 5): 06b-2 merge edildiği için `kind: external` → 501 artık beklenen davranış değil (K-06b2-0008: yapılandırılmamış/anahtarı sıfırlanmış dış agent → 501, yapılandırılmış → upstream). Dumanda güncel davranışı ölçüp öyle raporlayacağım; 501'i yapılandırılmamış dış agent ile sınarım.
Sıra: YIGIN-AÇ → seed ×2 → e2e → eval → TTL negatif → facade dumanı → Kapı 2 kuru koşu → down -v → DURUM.

### T-18k2-0002 · 2026-11-03 08:55 · → koordinator · YIGIN-AÇ 18k2
Paket: 18-kosu-2   Cevap: K-18K2-0001
Proje ffcore-18k2, FFCORE_VERSION=0.0.0-main, BACKEND_PORT=18260 FRONTEND_PORT=13260, --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test --profile qdrant; main 0c7a100. Açık FF yığını yok (yalnız airflow_* dev konteynerleri, FF değil); C: 104 GB boş.

### T-18k2-0003 · 2026-11-03 09:20 · → koordinator · YIGIN-KAPA 18k2
Paket: 18-kosu-2   Cevap: K-18K2-0003
`down -v` exit 0 (state/evidence/18k2-down.log); ffcore-18k2 konteyner 0, volume 0. Geçici örtüler (ext-agent takma adı, üçüncü env-file) yalnız scratchpad'deydi, yığınla gitti.

### T-18k2-0004 · 2026-11-03 09:20 · → koordinator · DURUM
Paket: 18-kosu-2   Cevap: K-18K2-0001 / K-18K2-0002 / K-18K2-0003
DURUM: VERIFIED. Rapor: **state/pr/18-kosu-2.md** (tablolar, süreler, bulgular). Baz main 0c7a100; ürün kodu değişmedi; kanıt tam tee state/evidence/18k2-*.log.
- (1) seed 36/15 → **0/0**. (2) make e2e **64 passed / 0 failed / 22 NOT_RUN** (taban 64/0/22 ile aynı); F1-F4, F9-F13, Negative 14/14, Setup 22/22 passed; F tablosu eval/results/e2e-20261103-0558.md.
- (3) make eval fake-llm: 33/33 completed, kalem başı cites_source 19/20; judge NOT_RUN. (4) TTL negatif 2/2 passed.
- (5) facade taban **26/26** (kapsamlar, düz/agent akışlı+akışsız, unsupported_field, invalid_parameter, scope_missing, model_not_found, api_key_required, egress e-posta ham değer yok ×2, reserved host 422 ×2, allowlist dışı 422). Dış agent uçtan uca **15/15** (geçici iç host `ext-agent` = fake-llm takma adı; 201, api_key `***`, yayın öncesi **404 agent_not_published** (501 değil), publish → listede, akışlı+akışsız, egress, system 400, origin değişince anahtar null → 501, audit satırları).
- (6) Kapı 2: gate2:code_heavy 0, gate2:no_prose 0, **n=1** (yalnız .txt ulaşabildi; .md'ler Docling ağırlığı yok, model_missing). FOLLOWUP-145 verisi bu yığından çıkmaz; M3 aşama 0 raporu gerekir.
plan/18 Durum önerisi raporda.

### T-18k2-0005 · 2026-11-03 09:20 · → koordinator · KAYIT-TALEBI
Paket: 18-kosu-2   Cevap: -
Ayrıntı ve kanıt state/pr/18-kosu-2.md "Bulgular".
- **B1 (MAJOR adayı, sahibi 19):** `ingest-raw` backend imajında HttpEmbedClient → `backend` çağrısı EgressDenied: backend servisinin ALLOWED_INTERNAL_HOSTS'unda `backend` yok (yalnız worker/agent-worker ekliyor). `backend` eklenince aynı dosya indexed. test_19_ingest_raw LocalEmbedClient enjekte ettiği için yol testte koşmamış. Sunucuda da olur mu: doğrulanmadı (PayCore compose app-env'i kopyalıyorsa olur). M3 ingest'inden önce.
- **B2 (MAJOR adayı, 19/04a):** raw_ingest.py:252 sha aynıysa statüye bakmadan `unchanged`; failed/gated belge yeniden denenmez; ikinci koşu konsolda `created 0, status: -` (temiz görünür), gerçek durum yalnız manifestte. İstisnada satır `gated`'da kalıyor, failed'a çekilmiyor. Fail-loud açığı; `make models` sonrası yeniden koşu hiçbir şeyi düzeltmez.
- **B3 (MINOR, 13b/19 eval_report.py):** "right source"/"Source accuracy" = contains VE cites_source (fake'te 0/20, cites_source 19/20). S1 kaynak isabeti karşılaştırmasını yanıltır (ARCH-13); kullanıcının S1 koşusundan önce ayrılmalı.

### T-18k2-0006 · 2026-11-03 09:22 · → koordinator · HANDOFF
Paket: 18-kosu-2   Cevap: K-18K2-0004
### 18-kosu-2 · ffcore-test-18-kosu-2 · 2026-11-03 09:22
- Durum: VERIFIED kabul edildi; bulgular FOLLOWUP-154/155/156 (fix/19-dis-inceleme ekine). Lease RETIRED; bu oturum kapanıyor.
- Tam sonraki adım: yok (test rolünde açık iş yok). Not: K-08T1-0002 S6 (F11 seed `secrets` geri alma doğrulaması) bir sonraki test koşusuna.
- Değişen dosyalar: state/pr/18-kosu-2.md (rapor), state/evidence/18k2-*.log (9 log), eval/results/ (git-ignored: e2e-20261103-0558.md, eval-20261103-0600.md, 18k2-ingest-manifest-{1,2}.json). Ürün kodu yok.
- Koşan testler: seed ×2 (36/15 → 0/0), make e2e 64/0/22, make eval fake-llm 33/33 completed, TTL negatif 2/2, facade 26/26, dış agent 15/15, ingest-raw ×5 (Kapı 2 n=1).
- Kalan: gerçek model / judge, Kapı 2 Docling yolu (ağırlık), konsol Playwright, airgap; hepsi GOREV dışı ya da kullanıcıda.
- Blocker: yok. Commit edilmemiş durum: yalnız state/ (koordinatör commit eder). Yığın ffcore-18k2 kapalı (konteyner 0, volume 0); imaj eklenmedi. Scratchpad'deki parola dosyası ve duman betikleri depo dışı, oturumla atılır.
- Branch: yok (main 0c7a100 üstünde koşu).
