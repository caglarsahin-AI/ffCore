# Arşiv: isci-a · 13b

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-13b-0001 · 2026-10-30 21:45 · → koordinator · DURUM
Paket: 13b (A tarafı)   Cevap: K-AF-0008
PLANNED taslağı hazır: state/pr/13b-a.md (madde 0 FOLLOWUP-115 gen:api; seed = 18 seed.py + make hedefi; e2e = pytest tests/e2e + F tablosu; eval = scripts/eval_report.py, run API, eval/results/ gitignore; docs/demo.md). GOREV K-13b-0006 gelince kesinleştirip PLANNED gönderirim.
Taslaktaki dört soru (GOREV'le KARAR-GEREK olacak): S1 parolalar `run -e` ile (A); S2 PoC'de seed Langfuse dataset yazmaz, eval JSON'dan okur (A); **S3 S1 koşu 2 (`rewrite=true`) PoC'de koşamaz: rewrite 04b'de** (A: NOT_RUN gerekçeli, koşu 1 kabul); S4 set 33 (DRIFT-28).
Not: known_findings.json'daki f10_4 (103 kapandı) ve f10_7 (108, bu demet) satırları demet merge'ünden sonra kaldırılır.

### A-13b-0002 · 2026-10-30 21:48 · → koordinator · ACK
Paket: 13b A tarafı   Cevap: K-13b-0006
(Yeniden eklendi 22:0x, K-INIT-0026: merge abort'u commit edilmemiş satırları sildi; saat yaklaşık, içerik aynı.)
GOREV alındı; kararlar S1-S4 A planına işlendi (state/pr/13b-a.md). Branch feat/13b-e2e-eval, 0.0.0-13ba, 18030/13030; madde 0 FOLLOWUP-115 ayrı commit; e2e.env'e FFCORE_TEST_HOOKS=1. Kod demet MERGED yazılınca başlıyor; o zamana kadar yalnız okuma.

### A-13b-0003 · 2026-10-30 23:14 · → koordinator · DURUM
Paket: 13b A tarafı   Cevap: K-13b-0006
IMPLEMENTING (feat/13b-e2e-eval, 3f2bc31'e rebase edildi; lease ffcore-isci-a-13ba). Commit'ler: ee1b4c0 madde 0 FOLLOWUP-115 (check:api 1 → 0, yalnız schema-05a.d.ts); 244184d make seed (seed.py devralındı; aynı ad + bayt + tarihli canlı belge yeniden yüklenmez, çünkü yeniden yükleme sürüm artırıyor; seed sonunda "created N, uploaded M"; e2e.env FFCORE_TEST_HOOKS=1); 263e087 make e2e (pytest tests/e2e + F tablosu eval/results/, .gitignore; known_findings boş: 103/108 kapandı); d223423 make eval (scripts/eval_report.py; MODEL zorunlu, SQL onayı yalnız APPROVE_SQL=1, llm_judge NOT_RUN). Her dilim önce kırmızı (state/pr/13b-a-kapilar/).
YIGIN-AÇ 13ba açık: seed x2 + e2e + eval koşuyor. Sırada docs/demo.md (15 dk akış, sonuçlarla).

YIGIN-KAPA 13ba · 2026-10-30 23:31 · down -v exit 0, konteyner 0, volume 0

### A-13b-0004 · 2026-10-30 23:33 · → koordinator · DURUM
Paket: 13b A tarafı   Cevap: K-13b-0006
DURUM: VERIFIED. HEAD e5b957ba6695402df3383c9dccf768afe4153e29 (3f2bc31 üstüne 5 commit). Yığında: seed-1 created 36/uploaded 15 (60 s), seed-2 created 0/uploaded 0 (27 s); make e2e 62 passed / 0 failed / 23 NOT_RUN gerekçeli, F1-F13 + Negative + Setup satırları passed; make eval MODEL=fake-llm APPROVE_SQL=1 33 madde, rapor (hat kanıtı, ölçüm değil); lint 0; make test 725/725 iki profil; test-samples OK; check:api 0.
Test tarafına not: negative TTL testi hâlâ FOLLOWUP-111 gerekçesiyle skip'li; kanca artık açık (e2e.env FFCORE_TEST_HOOKS=1), testi açmak test rolünde.

### A-13b-0005 · 2026-10-30 23:33 · → koordinator · PR-HAZIR
Paket: 13b A tarafı   Cevap: K-13b-0006
PR: C:\ai_paycore\ffcore\state\pr\13b-a.md · Branch feat/13b-e2e-eval · Worktree .worktrees/feat/13b-e2e-eval · Baz main 3f2bc31 · SHA e5b957ba6695402df3383c9dccf768afe4153e29 · Sınıf [A] · push yok. Yığın kapalı. Review yığınlı (make e2e tam koşu; komutlar PR'da).

### A-13b-0006 · 2026-10-30 23:36 · → koordinator · ACK
Paket: 13b A tarafı   Cevap: K-13b-0008
REVIEW-ISTEK K-13b-0007 alındı; branch'e commit yok. REVIEW-SONUC ya da DUZELT bekliyorum; ONAY → MERGED sonrası HANDOFF + RETIRED.

### A-13b-0007 · 2026-10-30 23:58 · → koordinator · ACK
Paket: 13b A tarafı   Cevap: K-13b-0009
r1 ONAY alındı; merge ve kapı sende. MERGED yazılınca HANDOFF + lease RETIRED; o zamana kadar okuma.

### A-13b-0008 · 2026-10-31 00:12 · → koordinator · HANDOFF
Paket: 13b A tarafı   Cevap: K-13b-0010
- Durum: MERGED (main 3571030; r1 ONAY e5b957b). Lease ffcore-isci-a-13ba RETIRED; oturum kapanıyor.
- Tam sonraki adım: kod işi yok. M3 kapısı kullanıcıda: PayCore sunucusunda `make eval MODEL="qwen3.5:35b cpu" APPROVE_SQL=1` (sozlesme-33) ve `DATASET=<S1 yolu>` ile S1 koşu 1; sonuçlar docs/demo.md "Real-model results" tablolarına. S1 koşu 2 NOT_RUN (04b).
- Değişen dosyalar: frontend/lib/api/schema-05a.d.ts (üretilmiş), Makefile (seed/e2e/eval), scripts/eval_report.py, .gitignore, tests/e2e/{ftable.py, known_findings.json, test_13b_ftable.py, test_13b_eval_report.py}, tests/e2e/scenarios/{seed.py, e2e.env, conftest.py, README.md, test_13b_seed_unit.py, test_18_env_overlay.py}, docs/demo.md. Ayrıntı state/pr/13b-a.md.
- Testler: yığında seed x2 (ikincisi created 0/uploaded 0), make e2e 62 passed / 0 failed / 23 NOT_RUN, make eval (fake-llm, hat kanıtı); lint 0; make test 725/725 iki profil; check:api 0.
- Kararlar: K-13b-0006 S1-S4 A; seed aynı belgeyi yeniden yüklemez; known_findings boş; SQL onayı açık bayrak; llm_judge NOT_RUN.
- Blocker: yok. Açık: test rolünün negative TTL testi (kanca açık, test skip'li); FOLLOWUP-116 (checkpoint metni, 06b); FOLLOWUP-112 (önyüz eşlemeleri).
- Commit edilmemiş durum: yok. Yerelde imaj etiketleri ffcore/{backend,tools,frontend}:0.0.0-13ba ve 0.0.0-af silinebilir; worktree'lere dokunmadım. Yığınlar kapalı.
