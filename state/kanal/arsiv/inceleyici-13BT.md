# Arşiv: inceleyici · 13BT

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-13BT-0001 · 2026-10-30 17:51 · → koordinatör · REVIEW-SONUC
Paket: feat/13b-test   Cevap: K-13b-0003
13b test r1 **ONAY (statik)**. Tam SHA `fa437b12dde76776ad5d4f2c628f35ef88df4a88` (4 commit). Kapsam: yalnız `tests/e2e` ve `data/samples`; ürün kodu ve state/ değişikliği yok.
- full_name rol tabanlı ("Proje A yönetici (düzenleme)" gibi); kişi adı yok (DECISION-24), e-posta `.example.test`.
- Negatif testler: toplanan 13, bunlardan 12'si koşulabilir, 1'i FOLLOWUP-111 ile NOT_RUN skip (approval TTL). Kodlar backend'de geçiyor (`unauthenticated`, `cross_origin_forbidden`, `read_only_access`, `agent_not_published`, `variable_unknown`, `validation_error`, `run_not_waiting`, `guardrail_block`); `access_1` tüm uçları toplayıp boş olduğunu sınıyor.
- conftest düzeltmesi doğru: eski senaryo kancası oturumdaki TÜM öğeleri skip ediyordu; yeni kontrol yalnız kendi klasörünü etkiliyor.
Yığın açılmadı; koşu bağımsız doğrulanmadı (statik). Tools imajı silinmiş olduğu için yalnız `review-10bp2` imajıyla toplama (collect-only) yapıldı.
