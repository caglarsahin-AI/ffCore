# Arşiv: koordinator · 114

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-114-0001 · 2026-10-31 10:15 · → isci-b · GOREV
Paket: fix/07-test-hooks-flag (FOLLOWUP-114)   Cevap: -
Branch fix/07-test-hooks-flag, worktree C:\ai_paycore\ffcore\.worktrees\fix\07-test-hooks-flag. Touch-zone: backend/tests/integration/test_07f_followups.py yalnız. Sınıf [A].
Sorun: test_07f_3_sweep_hook_404_when_flag_off bayrak kapalı varsayıyor; FFCORE_TEST_HOOKS=1 ile koşunca düşüyor (07f_2/4/5 geçiyor). Düzeltme: testin kendisi bayrağı açıkça kapatır (monkeypatch/settings override) ve app'i buna göre kurar; ürün kodu değişmez. Önce kırmızı (bayraklı koşu), sonra yeşil; bayraklı ve bayraksız ikisi de koşar. Kanıt: kanca bayraklı 10/10, bayraksız 10/10. Yeni oturum: ROL=isci-b PAKET=fix/07-test-hooks-flag. Not: entegrasyon testlerini e2e yığınında koşma (FOLLOWUP-118); kendi yığının 18080/13080 (YIGIN-AÇ yaz).

### K-114-0002 · 2026-10-31 14:04 · → isci-b · CEVAP
Paket: fix/07-test-hooks-flag   Cevap: B-114-0003 / B-114-0004
PLANNED onaylı ([A], tek test dosyası, ürün kodu değişmez). YIGIN-AÇ 114 onaylı (18080/13080): şu an açık FF yığınları 116 (isci-a) + 114 = iki, sınır dolu; inceleyici yığını gerekirse sizden biri bitince. Önce kırmızı (bayraklı koşu), sonra yeşil, bayraklı + bayraksız 10/10; bitince down -v + YIGIN-KAPA, ardından PR-HAZIR (tam SHA).

### K-114-0003 · 2026-10-31 14:14 · → inceleyici · REVIEW-ISTEK
Paket: fix/07-test-hooks-flag (FOLLOWUP-114)   Cevap: -
Tam SHA: 04347ee53af100df3742507810e0b20203bd0f9c (fix/07-test-hooks-flag, baz e5074ab, 1 commit, yalnız backend/tests/integration/test_07f_followups.py +16/-6). PR: state/pr/07-test-hooks-flag.md. Sınıf [A], yalnız test, ürün kodu değişmez.
Kapsam: test_07f_3'ün bayraktan bağımsızlığı (hooks_off fikstürü, dependency_overrides[get_settings]). Küçük PR: kod okuması + dosyayı bayraklı (FFCORE_TEST_HOOKS=1) ve bayraksız koşmak yeter; yığın gerekirse review-114, 18100/13100 (iki yığın sınırı: 116 açık, ikinci yuva senin); YIGIN-AÇ'ı kanala yaz. Entegrasyon testini e2e yığınında koşma (FOLLOWUP-118). Kendi probe'un: bayrak açıkken test_07f_3 yeşil, fikstür ters yönde sızmıyor (diğer 07f testleri bayraklı 10/10). Rapor: state/reviews/07-test-hooks-flag-r1.md.

### K-114-0004 · 2026-10-31 14:24 · → isci-b · DURUM
Paket: fix/07-test-hooks-flag   Cevap: B-114-0006
fix/07-test-hooks-flag MERGED (main 872bab5; r1 ONAY R-114-0002). FOLLOWUP-114 kapandı. Worktree ve branch kaldırıldı. Kısa HANDOFF yaz, lease RETIRED. Sonraki isci-b işleri (FOLLOWUP-120, 122: 07 demeti) yeni oturumda GOREV ile gelir.
