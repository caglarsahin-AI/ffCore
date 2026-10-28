# 08-lite r3 — bağımsız delta incelemesi

İncelenen tam SHA: **199aeb46c813996517332d31ca2cd6f8a178d41a**.
Baz: 591aac3; önceki incelenen SHA: 7a7dc35e156b17f72e567dad3bfbf584f4f7a898.
İstek: K-08lite-0013; ACK: R-08lite-0007. İnceleyici: ffcore-inceleyici-20261028-0203.

**Karar: ONAY / merge-ready, yalnız incelenen SHA. BLOCKER0, MAJOR0, MINOR1 (FOLLOWUP-76 ile kabul).** R2 MAJOR performans regresyonu gerçek evaluate girdilerinde kapandı. Koordinatör K-08lite-0016 ile A seçti; kalan en-kötü-durum karmaşıklığı ve belge ifadeleri FOLLOWUP-76 kapsamında, bu SHA için engel değil.

## Kapsam ve kapanış

Dört dosyalık r2→r3 deltası tamamen okundu: engine, regex recognizer, yeni maliyet testleri, guardrail dokümanı. Ana çalışma kopyasında checkout/switch yapılmadı. Detached review worktree yalnız belirtilen SHA'daydı.

Önizleme değerleri tekilleşiyor, baş pencere taraması ve aralık birleşimi kullanılıyor. Çıktı hâlâ en çok60 karakter; 4096 tarama/3840 kaynak konumu sınırı olay çıktısı boyutu değildir. Kural tarama ve önizleme asyncio.to_thread üzerinden çalışıyor; latency_ms kendi önizlemesinin süresini içeriyor. Bulgular bütün girdiden toplanıyor:10.000 tekrarın tamamı matches içinde doğrulandı. Önizleme kendi örtüşmelerinde birleşim kullanıyor; bu, gizlilik için daraltma yapmıyor.

## Açık bulgu ve karar noktası

**MINOR-1 — resolve_overlaps için O(n log n) iddiası doğru değil.** backend/ffcore/guardrails/recognizers/regex.py:133 ve devamı: bisect araması logaritmik, ancak starts.insert(i,...), ends.insert(i,...) ve kept.insert(i,...) Python listesinin kalan kısmını kaydırır. Ön yarıda düşük, arka yarıda yüksek puanlı ayrık bulgular olduğunda yüksekler önce alınır; ardından düşüklerin her biri yükseklerin önüne eklenir. En kötü durumda O(n²) kaydırma sürer. Bu kaynak kanıtı; yalnız ölçümden karmaşıklık çıkarımı yapılmadı.

Aynı1CPU/512MB ağsız konteynerde iki puan gruplu yardımcı ölçüm:10.000 bulgu0,0374sn;20.000 bulgu0,1754sn;40.000 bulgu0,7395sn. Bunlar doğrudan resolve_overlaps mikro ölçümleri; kabul edilen gerçek evaluate girdisinde bütçe ihlali veya yanlış sonuç gösterilmedi.5.000 rastgele, pozitif uzunluklu örtüşme demetinde eski algoritmayla sonuç birebir aynıydı.

R-08lite-0008 seçenekleri: **A önerilen:** r2 MAJOR kapanışını gerçek evaluate bütçeleriyle kabul, kalan en-kötü-durum sınırını açık MINOR/FOLLOWUP taşı, yanlış karmaşıklık iddiasını düzelt. **B:** O(n log n) koşulunu mutlak tut, gerçek algoritmik garanti olmadan DUZELT. Koordinatör K-08lite-0016 ile A seçti; FOLLOWUP-76 kaydıyla bu SHA için kabul etti. İnceleyici bu gereksinimi kendiliğinden gevşetmedi. PR'da zaten belirtilen docs60/3840 belirsizliği de kapanış doküman düzeltmesine dahil edilmeli.

## Bağımsız doğrulama

Kaynak salt okunur /work bağlandı; importlar exact r3 /work/backend'den. Tools yalnız bağımlılık imajıdır: sha256:4c179b8636ca79e522e0792b3b1a177d3dd956719fd65bd010f516b2d2ad52c0. Ürün imajından kaynak kullanıldığı iddia edilmedi. Test ortamı sahte .env.test, yalnız kendi PostgreSQL/Redis yığını review-08lite-r3; FFCORE_VERSION=0.0.0-review-08lite. Yeni imaj indirilmedi/derlenmedi.

| Kontrol | Sonuç |
|---|---|
| make lint | passed;117 dosya format kontrolü |
| llmaas make test |190 passed;19,16sn;1CPU/512MB,ağsız |
| airgap make test |190 passed;17,36sn;1CPU/512MB,ağsız |
| llmaas make test-int |110 passed;86,63sn |
| airgap make test-int |110 passed;74,05sn |
| R2 aynı 320/640 tekrar girdileri |0,0358/0,0394sn; bütün bulgular ve maskeli≤60 önizleme |
|10.000 tekrar/160.000 karakter |0,3342sn;10.000 PII match;latency toplam332,426ms |
|200.000 karakter karma metin |0,5913sn; üst sınır1sn altında |
|4096 pencere sınırı gizliliği |10 konum:0,1,40,59,60,3839,3840,4090,4095,4096;6.000karakter sentetik sırın parçaları hiçbir önizlemede yok |
|Örtüşme sonuç eşitliği |5.000 rastgele demette eski pairwise algoritmayla aynı |
|R1 DB/API gizlilik probe'ları |sentetik parola iki olayda/response events'te yok;tek harf email DB matches'te ham değil |
|Default PII proje satırı |panel1/zincir1 özel bulgu,redact |
|Token round-trip |a.b/ab ayrı token,geri dönüş tam,unresolved boş |
|Gerçek Redis |100paralel/20değer→20token;tüm anlık reverse doğru,TTL pozitif,başka run çözmüyor |
|Baz state/ diff / diff --check |boş / passed |

Maliyetler tek koşu üst sınır kanıtıdır; P95 veya bütün olası girdiler için garanti değildir. İlk DB probe çağrısı yanlış /work çalışma dizini nedeniyle tests importunda durdu; /work/backend ile tekrarlandı ve geçti. Bu deneme ürün hatası veya passed sayılmadı.

## Güvenlik turu

- **Kimlik:** servis-only, kullanıcı oturumu ve OBO negatifleri iki profil entegrasyon matrisinde geçti; delta kimlik kodunu değiştirmiyor.
- **ACL:** proje sınırı,analyst/read-modu,audit kontrolleri geçti; mevcut yetki modeli daraltılmadı/genişletilmedi.
- **Secret:** yalnız sentetik test değerleri; r1 parola DB/API olay sızıntısı tekrar negatif.4096pencere kesişimi ve6.000karakterlik sır maskeli; gerçek .env okunmadı/kopyalanmadı.
- **SQL:** yalnız fixtures'ın oluşturduğu UUID test DB'leri; migration/audit testleri geçti, delta SQL/migration eklemiyor.
- **Egress:** birim/probe Docker çalışmaları ağsız; entegrasyon yalnız yerel PG/Redis.Dış sağlayıcı/kurum sunucusuna bağlantı yok; kapalı egress kontrolü iki profil matrisinde.
- **PII:** kısa email masked_value,ayrı token ve tam geri dönüş,proje PII varsayılanı tekrar doğrulandı.Ham değer önizleme/response events'te yok.
- **Log sızıntısı:** exception log biçiminde delta yok; probe çıktıları booleans/süre/sayılar,credential içermez.Performans girdileri sentetik.Ürün loglarında yeni ham metin yazımı kaynakta yok.

## NOT_RUN ve sınırlar

R3 full-stack LiteLLM/Langfuse/backend smoke bağımsız NOT_RUN: altyapı/compose delta yok,r1 smoke geçmiş kanıt; işçinin r3 smoke beyanı bağımsız passed sayılmadı. Dış satıcı,NER,injection,C17,kurum bağlantısı,Redis crash testi ve04a Redis5.3.1 rebase matrisi NOT_RUN. Mevcut bağımlılık imajı Redis8 içindir; gelecekteki rebase kapısı ayrı. Rastgele örtüşme eşitliği sıfır uzunluklu regex bulgularını kapsamıyor.

## Temizlik

Exact HEAD199aeb46c813996517332d31ca2cd6f8a178d41a ve boş git status --porcelain --untracked-files=normal doğrulandı. Kendi stack down-v exit0,network ve bütün kendi volume'ları kaldırıldı. Detached worktree git worktree remove ile kaldırıldı,exit0;--force yok. R2 evidence dizini değişmedi/korundu,koordinatör merge sonrası temizleyecek. Ürün kaynak edit/commit/push yok; ana checkout değişmedi,diğer oturumların yığın/volume'ları korunuyor.Review tools/backend etiketleri kapanışta koordinatörce temizlenebilir.