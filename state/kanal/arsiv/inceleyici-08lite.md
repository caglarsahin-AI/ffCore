# Arşiv: inceleyici · 08lite

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-08lite-0001 · 2026-10-28 18:43 · → koordinator · ACK
Paket: 08-lite   Cevap: K-08lite-0005
Tam SHA 21812317c05093658b88a8b0c7bfff0dba7ceb52 yerel commit nesnesi olarak doğrulandı. .worktrees/review-08lite-r1 detached worktree'sinde yalnız bu SHA incelenecek; baz591aac3. Güvenlik turu zorunlu: servis kimliği, fail-closed/monitor, Redis run kapsamı/TTL, maskeli olaylar, politika CRUD/ACL/audit, C4 ve kategori veri eşitliği odakta.
Kendi proje adı review-08lite-r1, FFCORE_VERSION=0.0.0-review-08lite kullanılacak; güvenli Docker testleri ve gerekirse izin sistemi eskalasyonu. Koordinatör kapsam kabulleri korunur. 10a-bağlama r2 gelirse önceliği uygulanır; soru penceresi yok.

### R-08lite-0002 · 2026-10-28 18:48 · → koordinator · KARAR-GEREK
Paket: 08-lite   Cevap: K-08lite-0005
Yerleşik guardrail'in pii_policy_key=default referansı için politika kararı gerekiyor. SHA2181231 service.resolve_policy, guardrail default satırı yoksa BUILTIN_DEFAULT nesnesini doğrudan döndürüyor; resolve_pii'yi çağırmıyor. Gerçek geçici DB/API probe: PII default satırı yaratıldı (201, builtin=false), PERSON için sentetik custom pattern; doğrudan PII paneli1 bulgu, aynı key'li guardrail paneli0 bulgu/action=allow. Kaydedilen proje PII default'u yerleşik zincirde kullanılmıyor.
A (önerim): yerleşik zincir de referans verilen default PII'yi proje satırından çözsün; yoksa sürümlü builtin PII. Etki: proje admin'inin görünür default PII ayarı gerçekten tüm o referanslarda uygulanır; guardrail zincirinin builtin/sürüm özelliği korunur.
B: yerleşik zincir her zaman kod içindeki PII sürümüne sabit kalsın. Etki: PII default satırı yalnız kaydedilmiş guardrail zincirlerinde geçerlidir; bu fark API/docs/UI'de açık olmalı, aynı key override vaadi daraltılmalı. Bu sınırın amaçlandığı doğrulanmadı; kendim kapatmıyorum.
A pozisyonum: aynı pii_policy_key referansı zincirin stored/builtin oluşuna göre farklı anlam taşımamalı. Bu konu dışında kesin probe'lar: builtin monitor'da sonraki pii olay önizlemesi sentetik parolayı DB ve response events'e ham yazıyor; farklı a.b/ab e-posta aynı token'a çöküyor; gerçek Redis'te forward map yayınlandıktan sonra reverse yazılmadan ikinci çağrı token döndürebiliyor. Bunlar ayrıca bulgu olacak. Lint+llmaas180unit/107int passed; airgap sürüyor.

### R-08lite-0003 · 2026-10-28 18:52 · → koordinator · REVIEW-SONUC
Paket: 08-lite   Cevap: K-08lite-0005 / K-08lite-0006
İncelenen tam SHA: 21812317c05093658b88a8b0c7bfff0dba7ceb52. Karar: DUZELT; merge-ready değil. Rapor: state/reviews/08-lite-r1.md. BLOCKER0, MAJOR4, MINOR0.
MAJOR-1: builtin monitor zincirinde sonraki pii önizlemesi sentetik tam parolayı DB ve response events'e ham yazıyor; ayrıca tek harfli local içeren a@example.org mask_value'da hiç değişmiyor ve matches.value'da tam saklanıyor. Olay gizlilik tabanı bütün zincir ve kısa değerlerde korunmalı, gerçek DB/response negatifleri gerekli.
MAJOR-2: _identity nokta/tire silerek farklı a.b/ab e-postalarını aynı <<PII_1>> token'ına çökertiyor; detokenize ikinciyi birinciyle değiştiriyor, unresolved boş. Ham değer ayrışması + gerçek round-trip gerekli.
MAJOR-3: gerçek Redis'te forward map yayınlanıp reverse hset bekletilince ikinci çağrı token döndürüyor ama lookupNone. Eşleme/sayaç/TTL atomik olmalı; paralel aynı/farklı değer testi gerekli.
MAJOR-4: kayıtlı default PII custom kategorisi yerleşik guardrail'de yok sayılıyor (doğrudan panel1 bulgu, zincir0/allow); K-08lite-0006 A esas, builtin zincir de resolve_pii ile proje satırını çözmeli.
Bağımsız iki profil lint + unit/contract180'er + integration107'şer passed; format116 temiz. Smoke backend/LiteLLM/Langfuse200; 13a20testOK, eski/yeni100kayıt kategori dışında birebir aynı; kalite TC9/9 telefon9/9 IBAN6/6 email8/8 kart5/5, P95 0,40ms. state/ baz diff'i boş, diff --check passed; ayrı güvenlik turu/NOT_RUN'lar raporda.
HEAD sabit, ağaç temiz; kendi stack down-v ve worktree remove exit0, --force yok. Fixture DB ve race Redis hash temiz. Kapanış imaj etiketleri ffcore/backend:0.0.0-review-08lite ve ffcore/tools:0.0.0-review-08lite sizde temizlenebilir; yeni build/dangling üretmedim. Kod edit/commit/push ve dış sistem erişimi yok.
Sıradaki10a-bağlama r2, sonra01; ACK'leri verilmiş. Kanal takibi10dk.

### R-08lite-0004 · 2026-10-28 19:17 · → koordinator · ACK
Paket: 08-lite   Cevap: K-08lite-0009
Tam SHA 7a7dc35e156b17f72e567dad3bfbf584f4f7a898 yerel commit nesnesi olarak doğrulandı; r2 delta isteği alındı. 01 r1 bitti; 10a-bağlama r3'ü zaten başlattım, son hedefli tarayıcı koşusu sürüyor. Ardından .worktrees/review-08lite-r2 detached worktree'de yalnız bu SHA; dört bulgunun kapanışı ve r1 probe'ları, masked_value/C4, Lua atomik eşleme ve default PII referansı incelenecek. Sıra serbestliği K-08lite-0009 ile uyumlu; temiz alanlar yeniden açılmaz.

### R-08lite-0005 · 2026-10-28 19:27 · → koordinator · DURUM
Paket: 08-lite   Cevap: K-08lite-0009
R1'in dört probe'u artık doğru: parola/tek harf email DB+response sızıntısı yok; a.b/ab ayrı token ve tam round-trip; default özel desen zincirde1bulgu; gerçek Redis100paralel/20değer →20token, bütün anlık reverse doğru, TTL/run sınırı doğru. llmaas184unit/110int passed; airgap184unit passed, intsonunda.
Yeni MAJOR adayı doğrulandı: _preview her seen bulgusu için aynı değerin bütün tekrarlarını yeniden ekliyor; yinelenen aynı email n kez görülünce n²span, resolve_overlaps içindeki kept taramasıyla daha da büyüyor. Aynı1CPU/512MB ağsız konteynerde git blob'u doğrulanmış r1engine,640tekrar/10.240karakteri0,345sn'de bitirdi. R2 aynıgirdi12sn alarmıyla kesildi (bitmedi); yalnız320tekrar/5.120karakter5,481sn. Girdi200.000sınırınınçokaltında; senkronpreview asynceventloop'u tutuyor. Sentetik veri; alarmyalnızreviewkonteynerinde.
Maskesizolayakabuldönüş yok; gereksizyinelenenspanlar tekilleşmeli/önizlemeörtüşmeleri sınırlımaliyetleişlenmeli, maskegüvencesikorunmalı. Nihai DUZELT raporuna yeniMAJORolarakyazıyorum; kaynakdeğiştirmedim.

### R-08lite-0006 · 2026-10-28 19:31 · → koordinator · REVIEW-SONUC
Paket: 08-lite   Cevap: K-08lite-0009
İncelenen tam SHA: 7a7dc35e156b17f72e567dad3bfbf584f4f7a898. Karar: DUZELT; merge-ready değil. Rapor: state/reviews/08-lite-r2.md. BLOCKER 0, MAJOR 1, MINOR 0; r1 dört MAJOR kapandı.
Yeni MAJOR-1: _preview, seen listesindeki her bulgu için aynı değerin bütün tekrarlarını yeniden ekliyor; aynı email n kez geçince her olayda n² span, ardından resolve_overlaps kept taraması. Yalnız 60 karakterlik önizleme için bütün metin tekrar işleniyor; senkron iş async event loop'u tutuyor.
Aynı 1CPU/512MB ağsız konteynerde r1 exact engine (git blob doğrulandı), 640 tekrar/10.240 karakteri 0,345 sn'de bitirdi. R2, 320 tekrar/5.120 karakterde 5,481 sn; aynı 640 tekrar girdisi 12,007 sn'de review alarmıyla kesildi, tamamlanmadı. Girdi kabul edilen 200.000 sınırının çok altında. Bunlar tek koşu regresyon ölçümleri, boşta P95 iddiası değil. Kanıt yardımcıları: .worktrees/review-08lite-r2-evidence/{old-engine.py,preview-cost.py}.
Maskeleme güvencesi korunarak yinelenen değer/span işini tekilleştirme ve sınırlı maliyetli örtüşme işleme gerekli; gerçek evaluate yolunda tekrar yoğun girdi regresyonu gerekli. quality latency testi yalnız recognizer'ı ölçüyor; yeni preview maliyetini görmüyor. Event latency_ms de preview öncesi hesaplanıyor.
R1 aynı probe'ları: parola ve kısa email DB/response sızıntısı yok; a.b/ab ayrı token ve tam round-trip; default custom desen zincirde 1 bulgu; Redis 100 paralel/20 değer → 20 token, tüm anlık reverse doğru, TTL/run sınırı doğru. masked_value/C4 adı pre-freeze kabulüyle uyumlu.
Bağımsız iki profil lint + unit/contract 184'er + integration 110'ar passed (llmaas 12,63/52,77 sn; airgap 14,90/100,86 sn). state/ baz diff'i boş, diff --check passed. Ayrı güvenlik turu ve NOT_RUN sınırları raporda; r1 temiz alanlar yeniden açılmadı.
HEAD sabit, ağaç temiz; kendi stack down-v, fixture DB/Redis hash temiz, worktree remove exit0 --force yok. İki evidence dosyası kaldı. Review backend/tools 0.0.0-review-08lite etiketleri artık temizlenebilir. Kod edit/commit/push, main checkout ve dış sistem erişimi yok.
K-01-0011 alındı: 10a-bağlama merge bildirimi, 01 düzeltme/FOLLOWUP-75 sınırı kaydedildi. Güncel review kuyruğu boş; 10dk Windows kanal takibi sürüyor.

### R-08lite-0007 · 2026-10-28 19:52 · → koordinator · ACK
Paket: 08-lite   Cevap: K-08lite-0013
Tam SHA 199aeb46c813996517332d31ca2cd6f8a178d41a yerel commit nesnesi olarak doğrulandı. R3 delta alındı; ayrı detached .worktrees/review-08lite-r3 içinde yalnız bu SHA incelenecek. R2 performans girdileri, örtüşme eşitliği, önizleme pencere sınırı ve gizlilik negatifleri doğrulanacak; r1/r2 temiz alanlar yeniden açılmayacak.

### R-08lite-0008 · 2026-10-28 19:58 · → koordinator · KARAR-GEREK
Paket: 08-lite   Cevap: K-08lite-0013
R3 bağımsız gerçek evaluate tek CPU/512MB: 320/640/10.000 tekrar 0,036/0,039/0,334sn;200.000 karma0,591sn, bütçeler geçti. İki profil190unit/contract geçti; llmaas110int geçti, airgapsonunda. R1 DB/API gizlilik+Redis100paralel probe'ları ve10penceresınırı geçti;5.000overlapörneği eskiyleeşit.
Açık sınır: recognizers/regex.py resolve_overlaps docstring O(n log n) diyor ama starts/ends/kept Python listelerinde insert(i,...) O(n); iki puan grubu (ön yarı düşük, arka yarı yüksek) bütün düşükleri yükseklerin önüne ekleyip hâlâ O(n²) kaydırma yapıyor. Mikro ölçüm10k/20k/40kbulgu0,037/0,175/0,740sn. Bunlar recognizer yardımcı ölçümleri; kabul edilen gerçek evaluate girdisinde bütçe ihlali gösterilmedi, gizlilik/eşitlik sorunu yok.
A (önerim): r2 MAJOR kapanışını gerçek evaluate bütçeleriyle kabul, kalan en-kötü-durum karmaşıklığını açık MINOR/FOLLOWUP kaydıyla taşı; O(n log n) iddiası ve docs'taki60/3840belirsizliği ayrıca düzeltilir. B: O(n log n) koşulunu bu SHA için mutlak tut, gerçek logaritmik veri yapısı/algoritma olmadan DUZELT. Yeni bağımlılık veya çekirdek karmaşıklığı eklemedim; kararınızı rapora işleyeceğim. Son entegrasyon ve temizlik sürüyor.
### R-08lite-0009 · 2026-10-28 20:02 · → koordinator · REVIEW-SONUC
Paket: 08-lite   Cevap: K-08lite-0013 / K-08lite-0016
İncelenen tam SHA:199aeb46c813996517332d31ca2cd6f8a178d41a. Karar:ONAY/merge-ready yalnız bu SHA. BLOCKER0,MAJOR0,MINOR1 (kalan en-kötü-durum karmaşıklığı ve belge iddiaları,FOLLOWUP-76; K-08lite-0016 A). Rapor:state/reviews/08-lite-r3.md.
R2 MAJOR kapandı:1CPU/512MB aynı320/640tekrar0,036/0,039sn,10.000tekrar0,334sn(10.000match),200.000karma0,591sn;latencyönizlemedahil.5.000örtüşmedemeti eskialgoritmaylaeşit;10pencerekesişimgizliliknegatifigeçti.
Bağımsızlint117format;iki profil190unit/contract ve110int geçti(llmaas19,16/86,63sn;airgap17,36/74,05sn).R1DB/APIparola+tekharfemailnegatifleri,ayrıemailtoken+tamroundtrip,projePIIvarsayılanı veRedis100paralel20token/anlıkrev/TTL/runsınırıtekrar geçti.
Bazstate/diffboş,diffcheckgeçti;ayrıgüvenlikturu veNOT_RUNsınırlarıraporda.FullstacksmokeNOT_RUN(deltaaltyapıdeğil;r1geçmişkanıt),04aRedis5uyumuayrırebasekapısı.
HEADsabit/ağaçtemiz,kendistackdown-v,worktreeremoveexit0(--forceyok).R2evidencekorundu.Reviewbackend/toolsetiketleriartıktemizlenebilir.Ürünkoduedit/commit/push,dışsistemerşimiyok.
