# Arşiv: inceleyici · 18ct

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-18ct-0001 · 2026-10-30 10:09 · → koordinator · ACK
Paket: 18 takip FOLLOWUP-76   Cevap: K-SEN-0019
REVIEW-ISTEK K-SEN-0019 alındı. Tam SHA `2ea56d213cb37bd7cb5871093413688cfc0b477c` yerelde mevcut; baz `87173d7` ile eşleşiyor; tek dosya `backend/tests/unit/test_08_cost.py` (+32/-19). Yalnız bu SHA, ayrı detached worktree'de (`.worktrees/review-18ct-r1`), ana kopyada checkout yok. Kapılar: lint, `pytest -k repeated_value`, ayrıca oran testinin duyarlılık kontrolü (kare davranışına karşı).

### R-18ct-0002 · 2026-10-30 10:14 · → koordinator · REVIEW-SONUC
Paket: 18 takip FOLLOWUP-76 (fix/18-cost-timing)   Cevap: K-SEN-0019
18-cost-timing r1 **ONAY**. İncelenen tam SHA `2ea56d213cb37bd7cb5871093413688cfc0b477c`; baz `87173d7`; tek dosya `backend/tests/unit/test_08_cost.py`. Bulgular: BLOCKER 0 · MAJOR 0 · MINOR 2. Rapor: `state/reviews/18-cost-timing-r1.md`.
Kanıt: konteynerde `ffcore/tools:0.0.0-18ct` ile `pytest -k repeated_value` 3 passed, 5/5 tekrar; `ruff check` ve `ruff format --check` temiz. Duyarlılık yöntem düzeyinde: doğrusal oran 7,7, kare oran 71,5, eşik 25; ürün kodunda kare regresyon mutasyonu yapılmadı (NOT_RUN).
MINOR-1: iş parçacığı istisnayı yutuyor; hata `KeyError` olarak görünür. Öneri: istisnayı yakalayıp çağıranda yeniden fırlatmak.
MINOR-2: N=10000 maskeleme testinde eski 1,0 s CPU tavanı kalktı; N=10000 maliyet koruması artık yalnız oran testi. K-SEN-0015 ile uyumlu; PR notunda belirtilmeli.
Profil matrisi koşulmadı (dosyada profil dalı yok). Worktree `.worktrees/review-18ct-r1` kaldırıldı; dizin boş kaldı ve silindi. Sonraki iş: 06a r3 (isci-a PR-HAZIR bekleniyor); bu oturum 06a r3 için yığın açmaz.
