# 08-lite · r1 · Bağımsız inceleme

- İstek `K-08lite-0005`; ACK `R-08lite-0001`.
- İncelenen tam SHA: `21812317c05093658b88a8b0c7bfff0dba7ceb52`.
- Baz `591aac3`; detached worktree `.worktrees/review-08lite-r1`.
- İnceleyici `ffcore-inceleyici-20261028-0203`; 28 Ekim 2026.
- **DUZELT / merge-ready değil. BLOCKER 0, MAJOR 4, MINOR 0.** `R-08lite-0002` politika sorusu `K-08lite-0006` A kararıyla çözüldü; aşağıda MAJOR-4 olarak uygulandı.

## Bulgular

### MAJOR-1 — Olay önizlemesi ve maskeli eşleşme ham değer saklayabiliyor

`backend/ffcore/guardrails/engine.py` `_preview` yalnız genel regex PII tanıyıcıları + o anki kuralın bulgularını sansürlüyor. Diğer kuralların secret/custom bulguları kapsanmıyor. Monitor metni değiştirmediğinden yerleşik zincirin `secrets#0` olayı güvenliyken sonraki `pii#1` önizlemesi aynı parolayı ham saklıyor. Daha sonraki `service.record_events` bu önizlemeyi aynen DB'ye yazıyor; `EventOut` da döndürüyor. Kural sırası değiştirilmiş enforce zincirinde erken olaylar da aynı soruna açık.

Gerçek geçici PG + uygulama API probe'u: yalnız sentetik `dummy-not-secret-` tabanlı parola, `POST /api/v1/internal/guardrails/evaluate`, yerleşik monitor, `input.pre`. HTTP **200**; `secrets#0` önizlemesinde tam dummy değer **yok**, `pii#1` önizlemesinde **var**; hem DB `guardrail_events.input_preview` hem yanıtın `events` listesinde ham tam değer bulundu. Çıktıya credential yazılmadı, yalnız boolean basıldı. Monitor'un `text_out` ham metni döndürmesi bulgu değildir; ihlal kalıcı olay/önizlemededir.

İkinci sızıntı yolu `masking.py:mask_value`: e-postanın ilk harfi + domain korunuyor, local kısmı tek karakterse hiçbir şey maskelenmiyor. Gerçek API'de `a@example.org` için HTTP **200**, DB `guardrail_events.matches[].value` içinde **aynı tam e-posta** bulundu. Kısa custom bulguların genel son-dört maskesi de bu tabana karşı kontrol edilmeli.

İstenen düzeltme: olay verisi üretimi politika modu ve kural sırasından bağımsız bir gizlilik tabanı sağlamalı; bilinen secret ve etkin custom bulgular başka kuralın önizlemesine sızmamalı. Maskeli değer tam ham değere eşit kalmamalı. Bileşik zincir/monitor/enforce ve kısa e-posta/custom bulgu negatifleri gerçek DB ve response events üzerinde kanıtlanmalı. Genel log temizliği geçti diye bu alanlar güvenli sayılmamalı.

### MAJOR-2 — Token kimliği farklı e-postaları birleştirip yanlış değeri geri koyuyor

`backend/ffcore/guardrails/masking.py:_identity` bütün kategorilerde boşluk, nokta ve tireyi silerek casefold yapıyor. Bu, e-postanın anlamlı karakterlerini de kaldırıyor. `a.b@example.org` ve `ab@example.org` farklı adresler olmasına rağmen aynı kimliğe dönüşüyor.

Bağımsız gerçek `recognize` → `apply_action(tokenize)` → `detokenize` probe'u: iki e-posta **`<<PII_1>> <<PII_1>>`** oldu; geri çevirme ikinci adresi birinci adresle değiştirdi. `exact_roundtrip=false`, `second_restored_as_first=true`, `unresolved=[]`; hata fark edilmeden yanlış kimlik geri dönüyor. Ortak `_identity` her iki store'a da anahtar verdiğinden yalnız MemoryTokenStore test yardımcısına özgü değil.

İstenen düzeltme: kategoriye uygun ve çakışmasız kimlik; e-postalarda anlamlı nokta/tire korunmalı. Ayrı adreslerin ayrı token alması, yinelenen aynı değerin aynı token alması ve tam round-trip ayrı pozitif/negatiflerle kanıtlanmalı. Format normalizasyonunun ham metin geri dönüşü üzerindeki bilinçli sınırı varsa açık yazılmalı.

### MAJOR-3 — Redis forward/reverse eşlemesi atomik yayınlanmıyor

`RedisTokenStore.token_for` sayaç, `k:<identity>` forward eşlemesi, `t:<token>` reverse eşlemesi ve TTL'yi ayrı komutlarla yazıyor. Başka çağrı forward alanı görür görmez token'ı döndürebiliyor; reverse alanı henüz bulunmayabiliyor. `hsetnx` yalnız forward yarışı için koruma; bütün eşlemenin hazır olmasını sağlamıyor.

Gerçek kendi compose Redis'inde kontrollü eşzamanlı probe: ilk çağrı forward alanını yazdıktan sonra yalnız reverse `hset` gönderimi bir asyncio bariyeriyle bekletildi; ikinci ayrı store aynı run/değer için **`<<PII_1>>`** döndürdü; hemen `lookup` **None** oldu. İlk çağrı serbest bırakılınca lookup başarıyla çözüldü. Redis komutları taklit edilmedi; gerçek ağ komutları arasındaki geçerli bir yürütme sırası kontrol edildi. Run'a özel probe hash'i temizlendi.

İstenen düzeltme: sayaç/iki yönlü eşleme/TTL tek atomik işlemle kurulmalı; token dönen hiçbir çağrı yarım eşleme görmemeli. Aynı ve farklı değerlerin paralel çağrıları, doğru reverse ve TTL kanıtlanmalı. Komutlar arasında süreç kesilmesinin TTL'siz hash bırakma riski de mevcut koddan çıkarımdır; crash senaryosu bağımsız çalıştırılmadı.

### MAJOR-4 — Yerleşik zincir projenin default PII override'ını kullanmıyor

`service.resolve_policy` guardrail default satırı yoksa `BUILTIN_DEFAULT` nesnesini doğrudan döndürüyor; proje PII default satırını çözmüyor. Gerçek DB/API: PII default satırı **201 / builtin=false**, sentetik PERSON custom pattern için doğrudan PII panelinde **1 bulgu**; aynı key'li guardrail panelinde **0 bulgu / allow**. Proje kaydı görünür ama yerleşik zincir sabit `DEFAULT_PII` kullanıyor.

`R-08lite-0002` A/B sorusuna koordinatör `K-08lite-0006` ile **A** kararı verdi: `pii_policy_key` zincirin builtin/stored oluşundan bağımsız aynı referanstır; `resolve_pii` proje satırını, yoksa sürümlü builtin'i çözmeli. Bu kararla mevcut davranış MAJOR'dır. İstenen düzeltme: builtin zincirin PII bağımlılıklarını da çözmek; custom kategoriyle hem panel hem internal çağrıda aynı bulgu/karar, başka projeye taşmama ve satır yokken builtin pozitifleri.

## Bağımsız doğrulama

37 dosyalık baz diff'i ve kaynak/test/sözleşme akışları incelendi. İmajlar yerel önbellekten review'e özel etiketlendi:

- tools `sha256:4c179b8636ca79e522e0792b3b1a177d3dd956719fd65bd010f516b2d2ad52c0` → `ffcore/tools:0.0.0-review-08lite`.
- backend `sha256:111b54801fb65021fa19678d1fc511000b42bc4d26e3fc6f37263e0afaac5e5e` → `ffcore/backend:0.0.0-review-08lite`.
- İmajdaki `ffcore`/`alembic` 56 Python dosyası exact SHA ile bayt karşılaştırıldı: **0 fark**.
- Kaynak root `/work:ro`, Python bytecode/pytest cache kapalı, ruff no-cache. Sadece kendi compose ağı ve sentetik fixture DB'leri kullanıldı.
- Her compose çağrısı `FFCORE_VERSION=0.0.0-review-08lite`; proje `review-08lite-r1`, backend host portu18018; gerçek `.env` okunmadı/değişmedi, `.env.test` sahte değerleri kullanıldı. Derleme/dış indirme yok.

| Kontrol | Sonuç |
|---|---|
| llmaas `make lint && make test && make test-int` | **passed**; 116 format temiz, 180 birim/sözleşme (10,15 sn), 107 entegrasyon (55,54 sn) |
| airgap aynı kapılar | **passed**; 180 birim/sözleşme (8,56 sn), 107 entegrasyon (41,06 sn), 116 format temiz |
| Temiz volume'lardan backend/LiteLLM/Langfuse stack | **passed**; migrate 03a/03b/08 + katalog |
| `make smoke` kendi stack'te | **passed**; backend/LiteLLM/Langfuse200; Ollama inactive açık skip |
| Entegrasyonda migration downgrade08@-1/upgradeheads | **passed**, 03a/03b korunuyor |
| 13a `python -m unittest tests.test_13a`, konteyner | **20 OK** (1,615 sn) |
| Eski set kategori eşlemesi ardından yeni JSON ile karşılaştırma | **100 kayıt birebir eşit**, metin/span ve diğer alanlar aynı |
| PII kalite bağımsız ölçüm | TC9/9, telefon9/9, IBAN6/6, email8/8, kart5/5; her birinde precision/recall1,00 |
| Regex 1.000 karakter P95 | **0,40 ms**; docs0,61 ms ayrı işçi ölçümü, çelişki değil |
| Olay/token/default/Redis negatif probe | Yukarıdaki hatalar yeniden üretildi; fixture DB ve race hash temizlendi |
| OpenAPI08 üretim eşitliği /03a bayt eşitliği | **passed**, test kapıları içinde |
| Baz `state/` diff'i / `git diff --check` | **boş / passed** |

Set ve tanıyıcıların aynı ekipten olması ve küçük destek sayısı docs'ta dürüst belirtilmiş; ölçüm alan recall'u sayılmadı. Kategori değişimi dışında 13a metninin değiştirilmediği bağımsız karşılaştırıldı. Tam unit testlerinde standalone C4 dosyası yerine `test_08_openapi` içindeki C4 kontrolleri çalışıyor; eksik Makefile hedefi yok.

## Güvenlik turu

- **Kimlik:** internal evaluate servis-aktör guard'ı; anonim401, kullanıcı/OBO403; bağımsız entegrasyon matrisinde geçti. SERVICE_TOKEN ham değeri rapora/loga yazılmadı. Internal yol `/api/v1/internal` koordinatör kabulü.
- **ACL:** read/write require_role, proje sınırı/OBO/read403, GET read-parity, test-paneli read hakkı ve audit before/after bağımsız geçti. Proje filtreleri kaynakta incelendi. Kendi test/probe DB'si dışında SQL yazılmadı.
- **Secret:** **MAJOR-1 açık**; gerçek secret değil sentetik parola ile DB ve response events sızıntısı kanıtlandı. Secrets kuralının tek başına testi bileşik monitor zincirini kapsamıyor.
- **SQL/audit:** politika sorguları parametreli ORM; create/update/delete audited, enforce geçişi before/after, PII referans silme409. Kısmi tekil indeksler ve migration FK bağımlılığı incelendi; gerçek PG testleri geçti. Yarışan duplicate create 500 davranışı ayrıca yük altında sınanmadı.
- **Egress:** zorunlu bool yapılandırma, kapalı egress409; iki profil tekrarlandı. Engine dış sağlayıcı çağrısı yapmıyor. ReDoS admin-defined regex riski PR'da kabul edilmiş; yeni sınıflandırıcı/NER çağrısı var sayılmadı.
- **PII:** **MAJOR-1/2/3 açık**. TTL/normal run scope pozitifleri mevcut ama atomic publish ve kimlik ayrışması eksik. Redis mapping ham değeri TTL'li tutmak için tasarlanmış; bu beklenen geçici eşleme kalıcı olay sızıntısıyla karıştırılmadı.
- **Log sızıntısı:** exception mesajı yerine sınıf adı kullanımı kaynakta doğrulandı, probe çıktıları sadece boolean/sentetik adres/token. Olay önizleme açığı merkezi logger temizliğiyle kapanmış sayılmadı; gerçek müşteri verisi kullanılmadı.

## Kapsam ve sınırlar

Presidio/NER/injection/stream buffer/CVV-PIN yerleşik tanıyıcıları 08 tam'a, 06a hook bağlama başka pakete. Bunlar yeni bulgu değil. C4 bu merge ile donacak taslak olarak incelendi; stage/action enumları ve Decision alanları testle kilitli. Rule-exception on_error, monitor/off/short_circuit ve 200.000 karakter422 pozitif/negatifleri geçti.

**NOT_RUN:** gerçek satıcı, kurum sunucusu, NER/injection gecikmesi, SSE C17, yük altı regex/Redis crash deneyi. Bunlar geçti sayılmadı. Default PII sorusu K-08lite-0006 A kararıyla kapandı; kod düzeltmesi henüz yok.

## Temizlik

Kendi stack'i `down -v` ile kapandı; exact HEAD21812317c05093658b88a8b0c7bfff0dba7ceb52 ve boş git status doğrulandı. Worktree remove exit0, --force yok. Kullanıcı/işçi stack veya volume'ları silinmedi; main checkout/switch, kaynak edit/commit/push ve dış sistem erişimi yok. Review'e özel iki imaj etiketi koordinatörün kapanış temizliği için bildiriliyor; başka imajlara prune uygulanmadı.
