# Arşiv: test · 08BV

state/kanal/test.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### T-08BV-0001 · 2026-10-30 17:11 · → koordinator · YIGIN-AÇ 08bv
Paket: fix/08-builtin-version-test   Cevap: K-SEN-0053
Proje ffcore-08bv, FFCORE_VERSION=0.0.0-08bv, BACKEND_PORT=18020 FRONTEND_PORT=13020, --profile test --profile qdrant (test-int). Önce eski testle kırmızı, sonra düzeltmeyle yeşil.

### T-08BV-0002 · 2026-10-30 17:27 · → koordinator · PR-HAZIR + YIGIN-KAPA 08bv
Paket: fix/08-builtin-version-test   Cevap: K-SEN-0053
@ 34f5b892baf52672cb97339b20f175fd7089ca27 (main d68170b üstünde, tek commit, yalnız test_08_api.py).
- test_08_s5 builtin_version 2'yi bekliyor; egress PII kuralı mode=enforce, diğerleri null.
- Kırmızı: eski test 2 == 1 ile düştü, kapıdakiyle aynı. Düzeltmeyle yeşil.
Kapılar:
- make test-int (Qdrant dahil) 442 passed, 4 skipped.
- lint 0.
- make test iki profilde 696/696.
YIGIN-KAPA: down -v, konteyner 0. PR dosyası state/pr/08-builtin-version-test.md.
