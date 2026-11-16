# Arşiv: inceleyici · 08T1

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-08T1-0001 · 2026-11-03 12:35 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0006
REVIEW-ISTEK alındı. SHA doğrulandı: fb7130d6fda59b2b62fbecf50e47b7ebd1a15bdf (merge-base ea0db36 üstüne 6 commit, 24 dosya +1523/-73, state/ 0). Sıra: statik inceleme ve güvenlik turu şimdi başlıyor (yığınsız); fix/19 r2 REVIEW-ISTEK gelirse önce o yapılır. Tam yığın review-08t1a (18290/13290) fix/19 r2'den sonra açılacak.

### R-08T1-0002 · 2026-11-03 14:10 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: K-08T1-0006
Rapor taslak (karar DEGISIKLIK büyük olasılıkla kalır; MAJOR 7 yığın probe'u ve iki doğrulayıcıyla). Kalan: airgap test-int (tam yığın, %8; ~15 dk), ardından 06b-2 SSRF probe'u (~5 dk). Biten: make test 1010/1010 llmaas + airgap; test-int llmaas tam yığın 809 passed 5 skipped. Yaklaşık 20-25 dk sonra REVIEW-SONUC + YIGIN-KAPA.
- 2026-11-03 14:25 YIGIN-KAPA review-08t1a: down -v; kalan konteyner 0, volume 0.

### R-08T1-0003 · 2026-11-03 14:25 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1a   Cevap: K-08T1-0006
**DEGISIKLIK** (fb7130d6fda59b2b62fbecf50e47b7ebd1a15bdf). BLOCKER 0, MAJOR 7, MINOR 14, NOTE 9. Rapor state/reviews/08-tam-1a-r1.md (ayrı Güvenlik turu bölümü).
- MAJOR-1 (C17): TTL dolunca sayaç 1'den başlıyor → eski <<PII_1>> başka kişinin değerine çözülür (yığında gerçek RedisTokenStore ile kanıtlandı).
- MAJOR-2 (C17): konuşma geçmişindeki önceki koşunun yer tutucusu yeni koşunun kapsamında başka değere çözülür (yığında modül düzeyinde kanıtlandı).
- MAJOR-3 (C17, KARAR): çıkışta geri çevirme URL/markdown içinde değeri açar → upstream/injection ile dışarı sızdırma (Open WebUI görsel yükler). A önerilen: URL/bağlantı bağlamında geri çevirme yok; B: dış agent + facade düz yolda kapalı; C: kısıt + FOLLOWUP.
- MAJOR-4 (106): _SHORT_TOKEN karesel ReDoS: token+20k boşluk 43 s, 180k karakter 59 s (mevcut _ASSIGNMENT da karesel, aynı düzeltme).
- MAJOR-5 (106): yanlış pozitif → block: getAccessToken(), "anahtar TeslimProjeleri", INC0012345678, loadSecretValue, BearerTokenRequired.
- MAJOR-6 (107): hepsi engellenince sources olayı yok; F11 e2e failed dalı ölü (ValueError).
- MAJOR-7 (107×108): blocked listesine silinmiş belge maskesi uygulanmıyor (_SOURCE_LISTS).
- Doğru: S8 yetki (yalnız sahip/çağıran), saklanan görünümler, kapsam seçimi, hizalayıcı (fuzz), enforce pii → geri çevirme yok, 147 eşdeğer, C8/C9/C11 additive, airgap aynı.
- Koşular: make test 1010/1010 ×2; tam yığın test-int llmaas 809 passed 5 skipped, airgap 807 passed 7 skipped (kırmızı yok; işçinin ortam kırmızıları tam yığında geçti); 06b-2 SSRF probe + 06b-2/147 testleri 138/138 ×2. NOT_RUN: F11 e2e, MAJOR-2/3 uçtan uca, MAJOR-6/7 yığında, Langfuse/DB değer taraması, lint.
- Dosyalar commit edilmedi (rapor, 08-tam-1a-r1-probe.py, evidence 08t1a-r1-*, kanal). Worktree dizini Permission denied ile diskte kaldı (git'ten çıktı).

### R-08T1-0004 · 2026-11-03 15:58 · → koordinator · ACK
Paket: 08-tam-1a r2 (delta)   Cevap: K-08T1-0012
REVIEW-ISTEK r2 alındı. SHA doğrulandı: 6d0d9ba0aa0efcf04eddf9409d36e42f16053f55 (fb7130d üstüne 9 commit, 26 dosya +1294/-101, state/ 0). Worktree .worktrees/review-08t1a-r2 (temiz). Delta statik inceleme + tam yığın r1 probe'larının yeniden koşusu başlıyor.
- 2026-11-03 15:58 YIGIN-AC review-08t1a (r2; 18290/13290, COMPOSE_PROJECT_NAME=review08t1a, FFCORE_VERSION=0.0.0-review-08t1a, kod 6d0d9ba worktree, `--profile test --profile qdrant`: langfuse + mcp + ticket-desk dahil). Açık başka FF yığını yok. Boş disk 93G.

### R-08T1-0005 · 2026-11-03 17:05 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1a r2 (delta)   Cevap: K-08T1-0012
**DEGISIKLIK** (6d0d9ba0aa0efcf04eddf9409d36e42f16053f55). BLOCKER 0, MAJOR 3, MINOR 7, NOTE 8. Rapor state/reviews/08-tam-1a-r2.md (güvenlik turu ayrı bölüm).
- Kapandı (yığında r1 probe'larıyla): MAJOR-1 (TTL sonrası yeni değer <<PII_2>>, eski cevap çözülmüyor; lookup TTL yeniliyor), MAJOR-4 (200 bin boşluk 0,055 s; 20.000 örnekte span farkı 0), MAJOR-5, MAJOR-6, MAJOR-7; MINOR 1/2/3/7/8/12.
- MAJOR-r2-1 (MAJOR-3 kısmi, CONFIRMED uçtan uca): URL kuralı atlatılıyor: `]( //host`, `[1]: //host` referans tanımı, `](<… boşluklu>)`, `<img src=//>`; akışta 8.192 karakter öncesi başlayan URL. Facade düz yolda istemciye ham e-posta döndü. Öneri: fail-closed bağlam; 8.192 sınırının fail-closed olması koordinatör kararı.
- MAJOR-r2-2 (MAJOR-2 kısmi, CONFIRMED): facade agent istemci geçmişinde istek anı egress denetimi reserve'den önce tokenize ediyor; bayat <<PII_1>> yeni isteğin e-postasına çözülüyor. Soru metni ve facade düz yol aynı mekanizma (kod).
- MAJOR-r2-3 (PLAUSIBLE, mekanizma yığında): _history ham değere çeviriyor, yeniden tokenize egress'in yeniden bulmasına bağlı; telefon bağlamla 0,85, bağlamsız 0,75 → min_confidence 0,8 projede sağlayıcıya ham gider (KARARLAR "yeni kapsamda yeniden tokenize" ile farklı). Öneri: eski yer tutucu → yeni yer tutucu doğrudan eşleme.
- MINOR: büyük numara reserve (9 hane akışta açılmıyor, >2^63 INCR hatası); detokenize_unavailable sonrası yeniden bağlanmada girdi kaybı/yineleme; facade düz akışta Redis hatası olaysız kesiyor; geçmiş okuması eski eşlemeleri canlı tutuyor; docs/agentlar.md kodla çelişiyor; PR notu bayat; test boşlukları.
- Koşular: make test 1046/1046 ×2; tam yığın test-int llmaas 824 passed 5 skipped, airgap 822 passed 7 skipped; 06b-2 SSRF probe + 147 138/138 ×2; lint NOT_RUN (işçi kanıtı).
- Dosyalar commit edilmedi: rapor, 08-tam-1a-r2-probe.py, 08-tam-1a-r2-int-probe.py, evidence 08t1a-r2-*, kanal. Worktree git'ten çıktı, dizin Permission denied ile diskte kaldı (--force kullanılmadı).
- 2026-11-03 17:05 YIGIN-KAPA review-08t1a (r2): down -v; kalan konteyner 0, volume 0.

### R-08T1-0006 · 2026-11-03 18:01 · → koordinator · ACK
Paket: 08-tam-1a r3 (delta)   Cevap: K-08T1-0016
REVIEW-ISTEK r3 alındı. SHA doğrulandı: 370912d914df97eb1b7682e40f4df061369a7a54 (6d0d9ba üstüne 4 commit, 19 dosya +1060/-136, state/ 0). Worktree .worktrees/review-08t1a-r3 (temiz). Delta statik inceleme + r2 probe'larının yeniden koşusu + min_confidence 0,8 uçtan uca başlıyor.
- 2026-11-03 18:01 YIGIN-AC review-08t1a (r3; 18290/13290, COMPOSE_PROJECT_NAME=review08t1a, FFCORE_VERSION=0.0.0-review-08t1a, kod 370912d worktree, `--profile test --profile qdrant`: langfuse + mcp + ticket-desk dahil). Açık başka FF yığını yok.

### R-08T1-0007 · 2026-11-03 19:43 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1a r3 (delta)   Cevap: K-08T1-0016
**DEGISIKLIK** (370912d914df97eb1b7682e40f4df061369a7a54). BLOCKER 0, MAJOR 2, MINOR 8, NOTE 5. Rapor state/reviews/08-tam-1a-r3.md (güvenlik turu ayrı bölüm).
- Kapandı: MAJOR-r2-1 (r2 tablosu + çok satırlı taşıma + 8.192 fail-closed, 30 yazım × 7 okuma biçimi; facade düz uçtan uca 4 yazım tutuldu), MAJOR-r2-2 (facade geçmiş bayat <<PII_1>> → None), MAJOR-r2-3 (gerçek adapters.context_factory + LiteLLM + fake sağlayıcı, min_confidence 0,8: sağlayıcıya <<PII_10>>, ham telefon yok; messages/run_events/guardrail_events/runs.output temiz; A TTL yenilenmedi). MINOR-r2-2/3/4, NOTE-1 kapandı.
- Varsayım 9 KABUL (hedef her zaman işaretten sonra; PR güvenlik notu düzeltilsin), varsayım 10 KABUL (zorunlu), 11 KABUL. MINOR-r2-1 "≤ 8 hane" yetmiyor: <<PII_99999999>> sayacı 9 haneye itiyor, bayat 9 haneli yer tutucu yeni değere çözülüyor (MINOR-r3-2, doğrulandı).
- MAJOR-r3-1 (karar gerekir): HTML yeniden yazımları işaret listesini atlatıyor: `src` + satır sonu + `=`, `style="…url(http:host…)"`, `<object data="http:…">` (// yok); değer açıldı. Öneri: satır sonunda öznitelik adı, style=/data=/url(/şema-iki nokta işaret; ya da HTML etiketli satırda açma yok.
- MAJOR-r3-2 (gerileme): UrlLines her parçada satırı baştan tarıyor; işaretsiz tek satır 64 bin karakter/4'lük parça 5 s, 100 bin 8-10 s eşzamanlı CPU, okuyucu başına olay döngüsü blokajı (normal düzyazı 122 bin 0,2 s). Öneri: artımlı tarama + _marked/_cut sonrası atla.
- MINOR: yeniden bağlanan okuyucu satır ortasında URL yer tutucusunu açıyor (fail-open); komşu facade yollarında 502 eşlemesi yok; fail-closed durumu cevap sonuna kadar sıfırlanmıyor (karar); docs (agentlar URL kuralı, facade agent yeniden bağlanma ifadesi); canlı yeniden bağlanma testi yok; araç/KB metnindeki düz <<PII_n>> ayrılmıyor (fb7130d'den beri); PR r1 satırı bayat.
- Koşular: make test llmaas 1210/1210; airgap 1205 + 5 zaman bütçesi kırmızısı (yük; dosya tek başına 7/7; NOTE); test-int llmaas 837 passed 1 failed (03a_9 .invalid DNS zaman aşımı, tek başına 16/16, ortam), airgap 836 passed; 06b-2 138/138 ×2; r2 entegrasyon probe'u yeşil.
- Dosyalar commit edilmedi: rapor, 08-tam-1a-r3-probe.py, 08-tam-1a-r3-e2e-probe.py, evidence 08t1a-r3-*, kanal. Worktree git'ten çıktı, dizin Permission denied ile kaldı (--force yok).
- 2026-11-03 19:43 YIGIN-KAPA review-08t1a (r3): down -v; kalan konteyner 0, volume 0.

### R-08T1-0008 · 2026-11-03 20:30 · → koordinator · ACK
Paket: 08-tam-1a r4 (delta)   Cevap: K-08T1-0022
REVIEW-ISTEK r4 alındı. SHA doğrulandı: 4aecdbc327a3a85e328045bf103b3d186c66ace9 (370912d üstüne 9 commit, 19 dosya +801/-98, state/ 0). KARARLAR "C17 URL bağlam kuralı, ek" (a)-(f) düzeltilmiş hâliyle okundu. Worktree .worktrees/review-08t1a-r4 (temiz). Delta statik inceleme + r2/r3 probe'larının yeniden koşusu + yeni yazımlar + performans başlıyor.
- 2026-11-03 20:30 YIGIN-AC review-08t1a (r4; 18290/13290, COMPOSE_PROJECT_NAME=review08t1a, FFCORE_VERSION=0.0.0-review-08t1a, kod 4aecdbc worktree, `--profile test --profile qdrant`). Açık başka FF yığını yok. Boş disk 92G.

### R-08T1-0009 · 2026-11-03 21:09 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1a r4 (delta)   Cevap: K-08T1-0022
**DEGISIKLIK** (4aecdbc327a3a85e328045bf103b3d186c66ace9). BLOCKER 0, MAJOR 1, MINOR 6, NOTE 7. Rapor state/reviews/08-tam-1a-r4.md (güvenlik turu ayrı bölüm).
- Kapandı: MAJOR-r3-2 (100 bin/1'lik parça 0,4-0,6 s; r3'te 23-28 s), MINOR-r3-1 (gerçek Redis + detokenizer(after): r3 senaryosu tutuldu, onay sonrası sahip değeri görüyor, iki satır önce açılan HTML değeri tutuldu, bilinmeyen after fail-closed), MINOR-r3-2 (99.999.998 sınırı, 9 hane açılmaz), MINOR-r3-3/4/6, NOTE-1. İstenen yazımların hepsi (r3 tablosu + `<a\nhref`, svg href, url( 'http:' ), IMG SRC, entity, 3 satırlı etiket, boş satır sonrası etiket değeri, srcdoc, css blok) dört okuma biçiminde tutuldu; facade düz uçtan uca 7 HTML yazımı temiz.
- Varsayım 12 KABUL (bütün girdileri taramak HTML taşımasını kurmak için gerekli; 20 bin girdi 0,36 s; COUNT sayfalama önerisi), varsayım 13 KABUL. 4aecdbc: fake `hello + [:50]` kesiyor; yalnız style yazımı boşuna geçiyor, diğer 9'da `<<PII_` iddiası gereksiz kaldırılmış (MINOR).
- MAJOR-r4-1 (karar gerekir): satır/taşıma modeli yine atlatılıyor, 7 yazım doğrulandı: etikette `alt=a"b src="…` tırnak uyuşmazlığı (gerileme), `[a]( <img src="…` açıcı önceliği, `<pre>` + `](` + boş satır (gerileme), `<PII_1 style` etiket adı istisnası, `<style>` içinde CSS kaçışları (`\75 rl`, `@import`), parçalara bölünmüş CRLF. Öneri A: cevap düzeyinde HTML fail-closed (ilk `<harf`'ten sonra cevabın geri kalanında açma yok; istisna yalnız tam `<<PII_n>>`; markdown satır kuralı kalır; CRLF bekletme). B: satır modelini yine yamala. C: HTML'i tehdit modelinden çıkar.
- MINOR: aralık taşması egress'te on_error yolundan geçiyor (block → guardrail_block, log → ham değer sağlayıcıya; çağıran tetikleyebilir) ve docs durum/kodu yanlış; konuşmadaki <<PII_99999999>> sonraki her koşuyu kalıcı düşürüyor (karar); hazırlık hatasında yalnız ilk satır tutuluyor (karar: _lost); 4aecdbc test zayıflığı; kullanılabilirlik (data:/file: düzyazı, x<y tag kipi); prime beklenmeyen hata akışı olaysız kesiyor.
- Koşular: make test 1382/1382 ×2; tam yığın test-int llmaas 848 passed 5 skipped, airgap 846 passed 7 skipped; 06b-2 138/138 ×2; r2+r3+r4 entegrasyon probe'ları 13/13; lint NOT_RUN (işçi kanıtı).
- Dosyalar commit edilmedi: rapor, 08-tam-1a-r4-probe.py, -int-probe.py, -adv-probe.py, evidence 08t1a-r4-*, kanal. Worktree temiz kaldırıldı.
- 2026-11-03 21:09 YIGIN-KAPA review-08t1a (r4): down -v; kalan konteyner 0, volume 0.

### R-08T1-0010 · 2026-11-03 21:45 · → koordinator · ACK
Paket: 08-tam-1a r5 (delta)   Cevap: K-08T1-0026
REVIEW-ISTEK r5 alındı. SHA doğrulandı: 60f2250caf8fa089abb0ee476b7a0325394d3c44 (4aecdbc üstüne 5 commit, 14 dosya +282/-188, state/ 0). KARARLAR "C17 geri çevirme: cevap düzeyinde HTML fail-closed" (+ d′, f′) okundu. Worktree .worktrees/review-08t1a-r5 (temiz). Delta + adversarial (markdown/CRLF) + probe yeniden koşusu başlıyor.
- 2026-11-03 21:45 YIGIN-AC review-08t1a (r5; 18290/13290, COMPOSE_PROJECT_NAME=review08t1a, FFCORE_VERSION=0.0.0-review-08t1a, kod 60f2250 worktree, `--profile test --profile qdrant`). Açık başka FF yığını yok. Boş disk 92G.

### R-08T1-0011 · 2026-11-03 22:27 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1a r5 (delta)   Cevap: K-08T1-0026
**DEGISIKLIK** (60f2250caf8fa089abb0ee476b7a0325394d3c44). BLOCKER 0, MAJOR 1, MINOR 4, NOTE 7. Rapor state/reviews/08-tam-1a-r5.md (güvenlik turu ayrı bölüm).
- Kapandı: karar A (r1-r4 bütün yazımlar + r4'ün 7 atlatması + bu turun markdown/CRLF listesi tutuldu; facade düz uçtan uca 11 yazım temiz; adversarial okumada sıfır tık yol yok), MINOR-r4-1 (on_error=allow + aralık → 400, sağlayıcı çağrılmadı), f′ (99.999.999 konuşmada sorun değil), d′/MINOR-r4-6 (hazırlık hatası cevap sonuna kadar), MINOR-r4-4. Varsayım 14/15 KABUL. Performans gerilemesi yok (100 bin/1'lik 0,34-0,42 s).
- MAJOR-r5-1 (gerileme, c22894a): _HTML_TAG istisnası `(?<=<<)` önceki karaktere bakıyor; 32 karakterlik kuyruk bir yer tutucunun iki `<`'i arasından kesilince `<PII_1>>` etiket sayılıyor, cevabın kalanı tutuluyor. Canlı akışta sahip değerleri göremiyor: rastgele 1-6 karakterlik girdilerde 97/200 cevap değer kaybetti. Düzeltme tek satır: `<(?!PII_\d{1,8}>>)[a-z]`.
- MINOR: taşınan <<PII_99999998>> kapsamı tüketiyor (konuşma yine kalıcı düşüyor; Unicode rakam da 99999999 istisnasını atlatıyor) — eşik önerisi, karar; HTML kuralının bedeli konsola da düşüyor (`<br>`, `List<String>`, `<your-email>`) ve kapsam okuyucunun akışı, docs yanlış — (a) docs önerim, (b) konsol muafiyeti, karar; bayat test/PR metni; küçük docs sapmaları (C4 evaluate 400).
- Koşular: make test airgap 1505/1505, llmaas 1503 + 2 zaman bütçesi kırmızısı (yük; dosya tek başına 3×6/6); tam yığın test-int llmaas 849 passed, airgap 847 passed; 06b-2 138/138 ×2; entegrasyon probe'ları 15/15; lint NOT_RUN (işçi kanıtı).
- Dosyalar commit edilmedi: rapor, 08-tam-1a-r5-probe.py, -tail-probe.py, -int-probe.py, evidence 08t1a-r5-*, kanal. Worktree temiz kaldırıldı.
- 2026-11-03 22:27 YIGIN-KAPA review-08t1a (r5): down -v; kalan konteyner 0, volume 0.

### R-08T1-0012 · 2026-11-03 22:58 · → koordinator · ACK
Paket: 08-tam-1a r6 (kısa delta)   Cevap: K-08T1-0030
REVIEW-ISTEK r6 alındı. SHA doğrulandı: 33a0268f66bacde2cd57204e942b62b0ea2385cb (60f2250 üstüne 6 commit, 17 dosya +225/-81, state/ 0). KARARLAR (g)-(i) okundu. Worktree .worktrees/review-08t1a-r6 (temiz). Yığın kararı: tam yığın review-08t1a (probe'lar Redis ve yeni kodlu backend konteyneri istiyor); koşular make test iki profil + hedefli test-int iki profil + kuyruk/sınır probe'ları.
- 2026-11-03 22:58 YIGIN-AC review-08t1a (r6; 18290/13290, COMPOSE_PROJECT_NAME=review08t1a, FFCORE_VERSION=0.0.0-review-08t1a, kod 33a0268 worktree, `--profile test --profile qdrant`). Açık başka FF yığını yok. Boş disk 93G.

### R-08T1-0013 · 2026-11-03 23:12 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1a r6 (kısa delta)   Cevap: K-08T1-0030
**ONAY** (33a0268f66bacde2cd57204e942b62b0ea2385cb). BLOCKER 0, MAJOR 0, MINOR 1, NOTE 3. Rapor state/reviews/08-tam-1a-r6.md (güvenlik turu ayrı bölüm).
- MAJOR-r5-1 kapandı: kuyruk probe'u iki yolda 1-11'lik parçalarda 3/3, rastgele 0/200 kayıp (r5'te 97/200); `<PII_1 style` tutuluyor; r4'ün 7 adversarial yazımı 0 açılma. (h): taşınan 8 haneli/Unicode numara → konuşma çalışıyor (gerçek Redis). (i) docs doğru. MINOR-r5-3/4, NOTE-1/2/7 kapandı.
- 1-7 hane uygulaması: C17 ile tutarlı, sayaç 9.999.999'da fail-loud, sızıntı/yanlış atıf yönü yok (8 haneli eşleme oluşamaz).
- MINOR-r6-1 (karar): yok sayma eşiği verme sınırıyla aynı yerde; taşınan `<<PII_9999999>>` ilk değeri düşürüyor, konuşma yine kalıcı bozuluyor (doğrulandı). Öneri: taşınan > 1.000.000 yok sayılsın, verme sınırı 9.999.999 kalsın (iki satır, merge öncesi önerilir).
- NOTE: docs "up to 8 digits" → 7; MAX_CHARS yorumu; tek `<`'li yer tutucu benzeri metin akışta fail-closed.
- Koşular: make test 1525/1525 ×2; hedefli test-int (08t*, 08_api, 06b2 + SSRF probe) 116/116 ×2; tam test-int NOT_RUN (kısa tur, tam kapı ffmain'de); lint NOT_RUN (işçi kanıtı).
- Dosyalar commit edilmedi: rapor, 08-tam-1a-r6-probe.py, evidence 08t1a-r6-*, kanal. Worktree temiz kaldırıldı.
- 2026-11-03 23:12 YIGIN-KAPA review-08t1a (r6): down -v; kalan konteyner 0, volume 0.

### R-08T1-0014 · 2026-11-03 23:23 · → koordinator · ONAY-TEYIT
Paket: 08-tam-1a r7   Cevap: K-08T1-0034
**ONAY-TEYIT** (c9258241a411ef27393f79e10ea1cde383506b20; yalnız `git diff 33a0268..c925824` okuması, yığın yok, test koşulmadı; state/ 0). Rapor state/reviews/08-tam-1a-r7.md.
- Kod KARARLAR (h′) ile birebir: `reserve_carried` yalnız ≤ 1.000.000 taşınan numarayı ayırıyor, verme sınırı 9.999.999 ve 1-7 hane deseni değişmedi. Test sınırın iki yanını kapsıyor (9999999/1000001 → <<PII_1>>, 1000000 → <<PII_1000001>>, 999999 → <<PII_1000000>>); gerçek Redis testi yankıdaki 9999999/1000001 ile ilk değeri <<PII_2>> buluyor.
- MINOR-r7-1 (yalnız docs, merge'ü engellemez): docs/api.md:540 ve docs/guardrail.md:128 hâlâ "taşınan <<PII_9999999>> + yeni değer fail-loud olur" diyor; (h′) ile bu yok sayılıyor. Örnek "9.999.999 değer vermiş bir kapsam" olarak düzeltilmeli. Merge öncesi tek satır ya da main'de; senin kararın.
- Dosyalar commit edilmedi: rapor 08-tam-1a-r7.md, kanal.
