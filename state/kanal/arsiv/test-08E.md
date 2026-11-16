# Arşiv: test · 08E

state/kanal/test.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### T-08E-0001 · 2026-10-30 12:53 · → koordinator · DURUM: PLANNED
Paket: fix/08-default-egress-enforce [B]   Cevap: K-SEN-0030
Dal main 01639c5 (worktree). Önce kırmızı, üç dilim:
1. **secrets entropi**: rules.find_secrets'te _TOKEN adayı, [-_.] ile bölünen her parçası "tek tür" ise (yalnız harf ya da yalnız rakam) tanımlayıcı sayılır, atlanır. Örnekler: SZL-2025-003_temizlik-hizmet, hastane-a-admin-edit. Rastgele token'lar parça içinde harf+rakam karışık (tok_8c0aa0…, test_08_11 vakası) → yakalanmaya devam eder. Vendor kalıpları ve parola anahtar sözcüğü değişmez.
   Testler: 13a sözleşme adları ve breadcrumb biçimi allow; karışık token'lar block (mevcut 08_11 aynen).
2. **yerleşik default egress PII enforce** (K-SEN-0029 A, FOLLOWUP-102). Mod politika düzeyinde; monitor politika metni hiç değiştirmiyor (engine.py son satırlar). Seçenekler:
   - **A (öneri)** Rule'a additive `mode: monitor|enforce|null` (null = politika modu). Yerleşik egress PII tokenize kuralı mode=enforce; politika monitor kalır. Etki: C4 additive alan + openapi/08.yaml güncellemesi; yalnız egress tokenize uygulanır; input/output redact ve secrets monitor kalır. Proje politikaları da kural düzeyinde kullanabilir.
   - **B** Yerleşik politika tamamen enforce. Etki: kullanıcı girdisi modelden önce redact olur, secrets her aşamada bloklar; airgap'te de input redact devreye girer. Daha geniş davranış değişikliği.
   - **C** Engine'de "egress tokenize her zaman uygulanır" özel durumu. Etki: gizli otomatik davranış (ARCH-10), önermiyorum.
   A ile ilerliyorum. Testler: yerleşik politikayla egress'te ham PII yok; input.pre yerleşikte monitor kalır; secrets egress'te bloklamaz (monitor).
3. docs/guardrail.md: yerleşik politika satırı, kural modu, entropi istisnası.
Kapılar: lint + make test iki profil, yığınsız.

### T-08E-0002 · 2026-10-30 13:11 · → koordinator · PR-HAZIR
Paket: fix/08-default-egress-enforce [B]   Cevap: K-SEN-0030 / K-SEN-0032
fix/08-default-egress-enforce @ a74902389b4e583af69292aff010351d622350d9 (main 01639c5 üstünde, tek commit).
- Rule.mode additive (C4; openapi/08 +8 satır).
- Yerleşik default sürüm 2: politika monitor, egress PII tokenize enforce.
- Entropi: düz tanımlayıcılar atlanıyor + 32+ hex kalıbı.
- docs/guardrail.md güncellendi.
Kırmızı → yeşil: 08e_1, 08e_4, 08e_5 ×5, 08e_6 32-hex. Ek olarak sk-, ghp_, base64, KEY=değer ve PRSIM-1234 vakaları.
Kapılar:
- lint 0.
- llmaas 663 passed.
- airgap: ilk koşu yalnız FOLLOWUP-97'nin iki 04a testi düştü; tekrar 663 passed.
PR dosyası: state/pr/08-default-egress-enforce.md.
Merge sonrası 18 e2e'de f4_1c yeşile dönmeli. Seed'deki secrets=log geçici ayarı o zaman kaldırılabilir.

### T-08E-0003 · 2026-10-30 13:47 · → koordinator · PR-HAZIR (r2 delta)
Paket: fix/08-default-egress-enforce [B]   Cevap: K-SEN-0040
fix/08-default-egress-enforce @ 7dcaa9823c178daf7a8e85c186f38b0274969654 (a749023 üstüne tek commit).
- MAJOR-1: uzun harf segmenti yalnız sözcük gibiyse düz sayılıyor: ≥%25 sesli, 4 ünsüzlük dizi yok; büyük harf kod ≤6 ve etiket ≤3 düz.
- Sapma: A'nın "segment başına entropi"si ölçümde ayırt etmiyor (rastgele 2.46-3.42, sözcük 2.52-3.39 bit/karakter). Sesli payı ayırıyor (0-0.17'ye karşı 0.36-0.57). Tablo PR dosyasında.
- test_08e_6'ya 4 vaka: önce kırmızı, şimdi yeşil. Belge adları ve PRSIM-1234 yeşil. data/samples dosya adlarının hiçbiri bulgu vermiyor.
Kapılar: lint 0; llmaas 667; airgap ilk koşuda FOLLOWUP-97, tekrar 667.

### T-08E-0004 · 2026-10-30 14:08 · → koordinator · PR-HAZIR (r3 delta) + KARAR-GEREK küçük
Paket: fix/08-default-egress-enforce [B]   Cevap: K-SEN-0043
@ e7d850abcb240b6f91379593b36a87e7ad001100 (7dcaa98 üstüne tek commit).
Kural: her segment rakam / normalize sözcük (≥%30 sesli, 3 ünsüzlük dizi yok) / kısa etiket / sayıdan önce büyük harf kod; ≥3 segmentte etiket+kod harfleri 15'i aşarsa muafiyet yok.
İnceleyicinin üreteciyle ölçüm (tablo PR dosyasında):
- ≥24 karakterlik tüm rastgele biçimler %99-100 yakalanıyor (BÜYÜK 4x6: %0 → %99,2).
- Belge adları %100 allow.
- data/samples dosya adlarının hiçbiri bulgu vermiyor.
Testler önce kırmızı (2), sonra yeşil.
Kapılar:
- lint 0.
- airgap 675.
- llmaas: iki koşuda yalnız FOLLOWUP-97'nin iki 04a testi düştü; dosya tek başına 24/24.

KARAR-GEREK: BÜYÜK 2x6/3x6 (13 ve 20 karakter) ENTROPY_MIN_CHARS 24'ün altında, tabanda da %0. Muafiyetle ilgisi yok.
- **A (öneri)** kapsam dışı, ayrı FOLLOWUP.
- **B** ayraçlı değerler için aday eşiği 12. Kısa kodlarda yanlış pozitif riski, ölçülmedi.
A ile bırakıyorum.

Şimdi K-SEN-0044: 18e2e yığını.

### T-08E-0005 · 2026-10-30 14:12 · → koordinator · ÖLÇÜM (taban, 5x3)
Paket: fix/08-default-egress-enforce   Cevap: koordinatör zili (5x3)
Tohum 11, 4000 örnek, host py3.12, dal dokunulmadı:
| biçim (uzunluk) | 28d7a5f muaf / yakalanan | e7d850a muaf / yakalanan |
|---|---|---|
| küçük 5x3 (19) | 0 / 0 % | 100 / 0 % |
| BÜYÜK 5x3 (19) | 0 / 0 % | 100 / 0 % |
Sonuç: 19 karakter ENTROPY_MIN_CHARS 24'ün altında, tabanda da yakalanmıyor. Muafiyetin %100 olması sonucu değiştirmiyor (uzunluk eşiği zaten taramıyor). FOLLOWUP-106 kapsamında. 08 dalına dokunmadım; 18e2e koşusu sürüyor.
