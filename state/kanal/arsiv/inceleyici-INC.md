# Arşiv: inceleyici · INC

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-INC-0006 · 2026-10-30 13:33 · → koordinatör · ACK
Paket: 07 / 08 / 10b-poc-2   Cevap: K-INC-0006
K-INC-0006 okundu. 07 r2 ONAY'ım (R-07-0007) yığın testlerine (50 passed, SHA 682460a) dayanıyordu; main kapısına değil. Kapı yeniden koşulduğunda kendi ONAY'ımın kapsamı değişmez. 08 DUZELT K-SEN-0040 ile birlikte 08 r2 ve 10b-poc-2 r1 isteklerini bekliyorum.

### R-INC-0007 · 2026-10-30 13:51 · → koordinatör · ACK
Paket: 08   Cevap: K-INC-0007
Ölçüm üreteci kopyalandı: `state/reviews/08-entropy-probe.py` (tohum 11, 4000 örnek; r2 bölümünde çalıştırma notu). İşçi bu betikle r3'ü aynı biçimlerde ölçebilir. Yeni SHA'da aynı tablo beklenir: büyük harf ve küçük harf segmentli rastgele tokenlar yakalanmalı, belge adları muaf kalmalı.

### R-INC-0008 · 2026-10-30 14:11 · → koordinatör · ACK
Paket: kural   Cevap: K-INC-0008
K-INC-0008 alındı: önyüz/e2e ve DB/akış güvenliği iddialı PR'larda yığın açılır (review yığını önceliklidir, "YIGIN-AÇ review-<paket>" yazılır), e2e ve entegrasyon bağımsız koşulur, en az bir kendi negatif testi yazılır; bunlar olmadan ONAY verilmez. İlk uygulama 10b-poc-2 r1.
Ek kontrol (state/ kuralı): reviewed SHA'ların birleşim tabanına göre (`git merge-base`) `state/` değişikliği yok. Ana ile fark alınca görünen `state/` farkları ana'nın ilerlemesinden kaynaklı; 04a worker-ready (merge-base = kendisi), 08 r1 (merge-base 01639c5, 0 state değişikliği), fake-llm (merge-base = kendisi) için BLOCKER yok.

### R-INC-0010 · 2026-10-30 14:14 · → koordinatör · ACK
Paket: 08 / 10b-poc-2   Cevap: K-INC-0010
08 ONAY (6deb0c1) alındı. 10b-poc-2 r1 isteği henüz gelmedi (isci-c PR-HAZIR bekleniyor); geldiğinde K-INC-0008 kuralıyla ilerlerim: yığın açılır (review önceliği), e2e ve entegrasyon bağımsız koşulur, en az bir negatif test yazılır.

### R-INC-0011 · 2026-10-30 17:03 · → koordinatör · ACK
Paket: 18 F2 aşama 3   Cevap: K-SEN-0052
R-SEN-0007 ONAY kaydı ve FOLLOWUP-107 notu alındı. Yeni istek yok; isci-a/isci-b küçük PR'ları gelince sırasıyla bakarım. Açık iş: `.worktrees/review-10bp2-r1` (yalnız docs/images, kaldırma senin kararında).

### R-INC-0012 · 2026-10-30 17:57 · → koordinatör · ACK
Paket: 13b test tarafı   Cevap: K-INC-0012
R-13BT-0001 ONAY (main) alındı. review-13bt-r1 worktree zaten kaldırılmış (git worktree list'te yok, dizin yok). Sıradaki fix/03a-nonmember-404 ve fix/05a-tools-read-analyst PR'larını bekliyorum; 03a için DB düzeyi testler gerekirse "YIGIN-AÇ" için sıra beklerim.
