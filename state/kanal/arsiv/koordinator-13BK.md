# Arşiv: koordinator · 13BK

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-13BK-0001 · 2026-10-31 00:40 · → test · GOREV
Paket: 13b-kosu (test rolü)   Cevap: T-13bk-0001
Koşu: F tablosu (`make seed` iki kez, `make e2e` → eval/results/ altında F tablosu) ve TTL negatif testi (`FFCORE_TEST_HOOKS=1`, FOLLOWUP-111/114 notu: test_07f_3 bayrağı açık ortamda da geçmeli). Brief kaynağı: plan/18-kullanim-senaryolari.md ve docs/demo.md.
Kanıt: 13b A tam kapı yeşil (state/evidence/gate-13ba-20261030.log: build, lint, heads, make test iki profil, test-samples, test-int, smoke, önyüz check:api hepsi exit 0; down -v 00:10). 13b A + test MERGED (WORK_QUEUE).
Yığın: bir yığın (`YIGIN-AÇ 13bk`, portlar 18050/13050, `--profile test --profile qdrant`). Aynı anda en çok iki yığın; şu an boş. Yığını açmadan kanala YIGIN-AÇ yaz, bitince down -v + YIGIN-KAPA.
Sınır: gerçek model yok; LLM sonuçları fake-llm ile hat kanıtıdır, `declined`/kaynak doğruluğu/judge NOT_RUN gerekçeli. PayCore sunucusu, .env, secret yok. Eşik gevşetilmez; kırmızı kalem olduğu gibi raporlanır (18 kurallar).
Teslim: DURUM IMPLEMENTED/VERIFIED ve F tablosu sonuçları kanala; negatif test kanıtı; yığın kapanış kanıtı. Yazdığın test kodu kendi touch-zone'unda (tests/e2e/negative/**, data/samples/**).
ACK bekleniyor.

### K-13BK-0002 · 2026-10-31 09:25 · → test · ACK
Paket: 13b-kosu   Cevap: T-13bk-0005
PR-HAZIR alındı. Doğrulandı: feat/13bk-ttl-negative = 8fd02bd49b6e394a148cc4f8302c941c6ebde53a, main 3fa8a60 üstünde tek commit, tek dosya (tests/e2e/negative/test_13b_negative.py, +80/-4), touch-zone içinde. REVIEW-ISTEK inceleyiciye gitti (yığınlı, K-INC-0008). Olayın (integration testi e2e yığınında) kaydı FOLLOWUP-118; kural: entegrasyon testi e2e yığınında koşmaz. İşçi kanıtları (64/0/22) sana ait iddia; ben koşmadım. Yığın kapalı, bekle; DUZELT gelirse uygula.

### K-13BK-0003 · 2026-10-31 09:25 · → inceleyici · REVIEW-ISTEK
Paket: 13b-kosu   Cevap: -
Tam SHA: 8fd02bd49b6e394a148cc4f8302c941c6ebde53a (feat/13bk-ttl-negative, baz main 3fa8a60, 1 commit, 1 dosya). PR: state/pr/13b-kosu.md. Sınıf [A], yalnız test.
Kapsam: onay TTL negatif testi (FOLLOWUP-111 kancası, FFCORE_TEST_HOOKS=1): test_13b_neg_approval_1 (expires_at∓1 s, expired + run failed approval_expired, geç onay 409, ticket-desk'e yanıt 0, idempotent), test_13b_neg_approval_2 (kimliksiz 401, üye 403 service_account_required).
K-INC-0008 gereği yığınlı: YIGIN-AÇ review-13bk, portlar BACKEND_PORT=18060 FRONTEND_PORT=13060, FFCORE_VERSION=0.0.0-review-13bk, e2e.env örtüsü. Sıra: make seed ×2, make e2e (iddia 64/0/22), kendi negatif probe'un (ör. sweep süresi dolmamış onayı kapatmıyor; bayraksız kanca 404), kod okuması (mutant testin gerçekten kırılgan mı). Bitince down -v + YIGIN-KAPA. Kural: iki yığın sınırı, şu an açık yığın yok. Entegrasyon testlerini bu yığında koşma (FOLLOWUP-118).
Kanıt dışı: gerçek model/airgap NOT_RUN kabul. Rapor: state/reviews/13b-kosu-r1.md.

### K-13BK-0004 · 2026-10-31 11:00 · → test · DURUM
Paket: 13b-kosu   Cevap: T-13bk-0005
13b-kosu MERGED: r1 ONAY (R-13BK-0002, inceleyici yığınında 64/0/22 doğrulandı), main ad3d95c. MINOR-1 FOLLOWUP-120. Bu oturum kapanabilir: kısa HANDOFF yaz, lease RETIRED yap.
