# Arşiv: test · 13bk

state/kanal/test.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### T-13bk-0001 · 2026-10-31 09:05 · → koordinator · DURUM
Paket: 13b-kosu   Cevap: K-HANDOFF-20261031-EK
DURUM: OKUMA-TAMAM. Kullanıcı talimatı: ROL=test PAKET=13b-kosu; lease ACTIVE (ffcore-test-13b-kosu).
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE (31 Ekim sürümü); 3 PLAN v2.7 (2.6/2.7 satırları dahil); 4 KARARLAR (28-30 Ekim eklemeleri: 08-lite, iki yığın kuralı, egress enforce, proje dışı 404, review yığını, C4/C7/C8/C9/C10 dondu, model ağırlıkları yalnız kullanıcı); 5 handbook tümü (CONTRACTS C8/C9 ve TERMINOLOGY güncel satırları); 6 WORK_QUEUE 13b satırı, BLOCKERS 101-117, test kanalı (T-13b-0001…0006 HANDOFF), koordinatör K-13b-0007…0010, K-HANDOFF-20261031 ve -EK, K-INIT-0029/0030; 7 plan/13 ve plan/18 tamamı; 8 BASLATMA.
Okunmayan (doğrulanmadı): diğer brief'ler, diğer kanalların test'e adresli olmayan mesajları, docs/demo.md (GOREV gelince komutlar için okunacak).
Durum: 13b-kosu için bana adresli GOREV henüz yok. Handoff'tan anladığım kapsam (doğrulanmadı, GOREV bağlar): (1) main'de yığın açıp `make seed` + `make e2e` ile F tablosunun koşusu (eval/results/), (2) onay TTL negatif testi `FFCORE_TEST_HOOKS=1` ile (`/api/v1/internal/approvals/sweep?now=`, FOLLOWUP-111 kancası; known_findings.json şimdi `{}`), (3) sonuçlar plan/18 Durum'a koordinatörce. Gözlem: FOLLOWUP-114 (test_07f_3 bayrağa bağımlı) bayrak açıkken koşuda düşer; GOREV'de nasıl ele alınacağını belirt.
Yığın açmadan YIGIN-AÇ ile sıra isteyeceğim. GOREV bekliyorum; kod ve yığın yok.

### T-13bk-0002 · 2026-10-31 09:20 · → koordinator · ACK
Paket: 13b-kosu   Cevap: K-13BK-0001
GOREV alındı. TTL negatif testi kod ister (tests/e2e/negative/test_13b_negative.py'deki `test_13b_neg_approval_1` şu an FOLLOWUP-111 skip'i); GOREV branch vermediği için touch-zone içinde dal açtım: `feat/13bk-ttl-negative` (main 3fa8a60), worktree `.worktrees/feat/13bk-ttl-negative`; yığın bu worktree'den, `FFCORE_VERSION=0.0.0-13bk`. Dokunulacak yalnız tests/e2e/negative/**; state/ commit edilmez. Dal adı uymazsa söyle, değiştiririm.
Sıra: (1) önce main koduyla yığında seed ×2 + make e2e (taban F tablosu), (2) TTL testi önce kırmızı (hook çağrısı yokken süre dolmaz) sonra yeşil, (3) test_07f_3 bayrak açık ortamda (FOLLOWUP-114) koşulur, sonuç raporlanır; isci-b dosyasına dokunmam.

### T-13bk-0003 · 2026-10-31 09:25 · → koordinator · YIGIN-AÇ 13bk
Paket: 13b-kosu   Cevap: K-13BK-0001
Proje ffcore-13bk, FFCORE_VERSION=0.0.0-13bk, BACKEND_PORT=18050 FRONTEND_PORT=13050, --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test --profile qdrant; worktree .worktrees/feat/13bk-ttl-negative.

### T-13bk-0004 · 2026-10-31 09:50 · → koordinator · YIGIN-KAPA 13bk
Paket: 13b-kosu   Cevap: K-13BK-0001
`down -v` exit 0; ffcore-13bk konteyner 0, volume 0. İmajlar `ffcore/*:0.0.0-13bk` kaldı (silme senin listende).

### T-13bk-0005 · 2026-10-31 09:50 · → koordinator · DURUM + PR-HAZIR
Paket: 13b-kosu   Cevap: K-13BK-0001
DURUM: VERIFIED. PR: state/pr/13b-kosu.md · Branch feat/13bk-ttl-negative · SHA 8fd02bd49b6e394a148cc4f8302c941c6ebde53a (main 3fa8a60 üstünde tek commit, yalnız tests/e2e/negative/test_13b_negative.py) · Sınıf [A] · push yok.
- F tablosu (HEAD'de, fake-llm hat kanıtı): `make seed` 36/15 → 0/0; `make e2e` **64 passed / 0 failed / 22 NOT_RUN** gerekçeli; F1-F4, F9-F13, Negative 14/14, Setup 22/22 hepsi passed. Tablo PR dosyasında.
- TTL negatif: iki gerçek test (FOLLOWUP-111 NOT_RUN kalktı): expires_at−1 s pending kalır, +1 s expired + run failed `approval_expired`, geç onay 409 `approval_not_pending`, ticket-desk'e yanıt 0, süpürme idempotent; kanca kimliksiz 401, üye 403 `service_account_required`. Mutantla kırmızı kanıtı.
- FOLLOWUP-114 doğrulandı: `FFCORE_TEST_HOOKS=1` ile `test_07f_3` düşüyor (07f_2/4/5 geçti); isci-b dosyası, dokunmadım.
- Olay (kendi hatam): 07f entegrasyon testini e2e yığınında koştum, LiteLLM'deki model kayıtları kayboldu (400 no healthy deployments); `make render-litellm` ile onarıldı, seed 0/0, e2e yeniden yeşil. Ayrıntı ve kök neden notu (doğrulanmadı) PR'da. Öneri: integration testleri e2e yığınında koşmasın (FOLLOWUP adayı: fikstür LiteLLM'e uzlaştırma yapıyorsa ayrı yığın şartı ya da açık hata).
NOT_RUN: `make test` (üretim kodu değişmedi), airgap profili (sunucu koşusu kullanıcıda), `make eval` (GOREV dışı).

### T-13bk-0006 · 2026-10-31 10:40 · → koordinator · HANDOFF
Paket: 13b-kosu   Cevap: K-13BK-0004
### 13b-kosu · ffcore-test-13b-kosu · 2026-10-31 10:40
- Durum: MERGED (main ad3d95c, 8fd02bd). Lease RETIRED; bu oturum kapanıyor.
- Tam sonraki adım: yok (test rolünde açık iş yok). Yeni test işi yeni oturumla.
- Değişen dosyalar: tests/e2e/negative/test_13b_negative.py (TTL negatif 2 test; FOLLOWUP-111 NOT_RUN kalktı); state/pr/13b-kosu.md.
- Koşan testler: make seed ×3 (36/15 → 0/0 → 0/0), make e2e 64 passed / 0 failed / 22 NOT_RUN (HEAD 8fd02bd), negatif 14/14, mutant kırmızı kanıtı, ruff + make lint 0. Kalan: make test (üretim kodu yok), airgap/gerçek model (kullanıcı sunucusu), make eval (GOREV dışı).
- Kararlar ve bulgular: FOLLOWUP-114 doğrulandı (isci-b dalında); olay FOLLOWUP-118 (entegrasyon testi e2e yığınında koşmaz; LiteLLM `make render-litellm` ile onarıldı, kök neden doğrulanmadı); küçük not: `render-litellm --check` "litellm_reconciled created=N" log satırı yazıyor (yazmadan), 01 sahibine.
- Blocker: yok.
- Commit edilmemiş durum: yok (worktree ve branch koordinatörce kaldırıldı). Yığın ffcore-13bk kapalı (konteyner 0, volume 0); `ffcore/*:0.0.0-13bk` imajları temizlik listesinde. Scratchpad'deki test parolası dosyası depo dışı, oturumla atılır.
- Branch ve son commit: feat/13bk-ttl-negative (kaldırıldı) @ 8fd02bd49b6e394a148cc4f8302c941c6ebde53a → main ad3d95c.
