# Main test kapıları / DRIFT-85 — r1

İstek: K-04a-0032; ACK: R-gates-0001; DNS kapsam kararı: K-04a-0034 (B). İnceleyici: ffcore-inceleyici-20261028-0203. İncelenen tam SHA: **7605022c46b3ad2d9fe6b82631b50592811e906b**; baz **fe0d434**. Ayrı detached `.worktrees/review-gates-r1`, yalnız bu SHA.

**Karar: DUZELT. BLOCKER 0, MAJOR 1, MINOR 0.** Ağırlıksız test kapıları ve servis teşhisi doğrulandı; varsayılan entegrasyon kapısının denetimsiz gerçek DNS sorgusu MAJOR olarak açık.

## MAJOR-1 — Varsayılan entegrasyon kapısı host/kurum DNS'ine sorgu gönderebilir

Kaynak: `backend/tests/integration/test_03b_egress_dns.py:20-38`, `docs/gelistirme-ortami.md:33`. Yeni test bayraksız toplanıp çalışıyor, `.invalid` adı `egress.system_resolver` üzerinden gerçek sistem resolver'ına gönderiliyor. 30 saniye arama bütçesi ve zaman aşımında NOT_RUN var; fakat bunlar sorgunun dış resolver'a iletilmesini önlemiyor. Testin kendi açıklaması ve PR bu iletim ihtimalini açıkça kabul ediyor. `.invalid` adının ayrılmış olması, DNS paketinin host/kurum resolver'ına gitmeyeceği anlamına gelmez. Belgelenen Compose komutunda bu sorguyu yerel sınırda tutan DNS yapılandırması yok.

K-04a-0034 ile koordinatörün **B** kararı: gerçek-resolver testi açık bir bayrakla (ör. RUN_DNS_TESTS=1) çalışmalı; bayrak yokken sorgu başlamadan gerekçeli NOT_RUN olmalı. Belge bayrağın dış DNS'e sorgu gönderebildiğini söylemeli. Varsayılan make test-int dış DNS sorgusu üretmemeli. Yerel NXDOMAIN sunucusu ekleme seçeneği koordinatör tarafından 80/20 gerekçesiyle seçilmedi; bu rapor onu yeniden önermiyor.

Bağımsız kanıt/sınır: source'ta işaret/bayrak koruması yok. Kendi review tools konteynerinde yalnız loopback DNS (`HostConfig.Dns=[127.0.0.1]`) ve `internal=true` Compose ağı doğrulanarak gerçek system_resolver testi llmaas geniş koşuda geçti. Bu, testi dışarı sorgu göndermeden çalıştırabildiğimizi gösterir; PR'ın varsayılan ortamının güvenli olduğunu kanıtlamaz. Varsayılan host resolver'a sorgu gönderme **NOT_RUN**; dış bağlantı yasağı nedeniyle çalıştırılmadı. İşçinin gerçek dış DNS sorgusunun fiilen hangi sunucuya ulaştığı bağımsız doğrulanmadı.

Beklenen negatif test: bayrak yokken system_resolver çağrı sayısı sıfır ve açık NOT_RUN nedeni; bayrak açıkken gerçek resolver hata yolu `egress_dns_failed` iddiasını korur. Timeout başarı sayılmamalı. `make test-int` varsayılanda tüm kalan testleri çalıştırmalı; DNS için ilave NOT_RUN görünmeli. İncelenen SHA değiştirilmedi; bu düzeltme sonraki tam SHA turuna aittir.

## Delta ve test iddiaları

11 dosya, yalnız testler ve geliştirme belgesi; `backend/ffcore`, pyproject/lock, Makefile, deploy değişmedi. Bazına göre state diff boş; `git diff --check` temiz. Mevcut backend imajındaki **87 Python kaynak dosyası**, LF-normalize SHA256 ile incelenen SHA'ya eşit. Testler `/work:ro` kaynaktan çalıştı.

- DNS unit testi artık `socket.gaierror(EAI_NONAME)` atan resolver kullanıyor. Önceki `egress_dns_failed`, host var/yol yok, `__cause__ is None` iddiaları aynı; gerçek DNS gecikmesi birim kapısından çıkarılmış. İstisna dönüştürme davranışı gevşetilmedi.
- `tests/converters.py`, yalnız Markdown için text-as-is dönüşüm seam'i sağlıyor. Diğer ağırlıksız biçimler gerçek convert_inline'a gider; ağırlık isteyen bilinmeyen/Office biçimi açık AssertionError ile düşer. Bağımsız ağsız probe Markdown metninin aynen korunmasını, test-markdown-as-is method'unu ve DOCX için fail-loud davranışını doğruladı. Bu seam gerçek Docling testi olarak sunulamaz.
- API/ingest/ACL/publication testlerinde dönüştürme sonrası DB, gate, chunk/vector, ACL daraltma, audit ve hata iddiaları korunmuş; yalnız converter bağımlılığı değişiyor. Markdown gerçek Docling varyantı aynı testte `models` parametresiyle korunmuş. DOCX gerçek bounded converter testi models işaretli, silinmemiş.
- Worker testi gerçek arq job, Redis ve bounded converter süreç yolunu koruyor; giriş dosyası stdlib EML. Sonraki-dosya unit testi redden sonra ağırlıksız TXT kullanıyor. Bunlar Docling kalite/başlatma kapsamı iddiası taşımıyor.
- Entegrasyon ön kontrolü yalnız gereken fixture/işaret için Qdrant/fake-llm TCP erişimini denetliyor. Ayrı ağsız gerçek pytest collection negatiflerinde eksik Qdrant ve eksik fake-llm, testler başlamadan tek açıklayıcı mesaj ve exit1 verdi. Testler sessiz atlanmadı.

## Bağımsız kapılar

| Kapı | Sonuç |
|---|---|
| Lint | passed; 197 dosya |
| Airgap make test | **385 passed**, 90,87 sn |
| Llmaas make test, tekrar | **385 passed**, 89,34 sn |
| İlk llmaas make test | **384 passed / 1 failed**, 94,53 sn; aşağıda açık |
| Llmaas make test-int | **207 passed / 2 skipped**, 189,74 sn |
| Airgap make test-int | **207 passed / 2 skipped**, 185,33 sn |
| Eksik servis negatifleri | Qdrant ve fake-llm ayrı exit1; tek neden/başlatma komutu |
| Kaynak/cache/DNS guard | 87 dosya eşit; model_cache 0 dosya; internal ağ + loopback DNS |
| Smoke | backend, LiteLLM, Langfuse health200; Ollama inaktif; passed |
| Kendi 5 servis log taraması | 281465 bayt; 17 sentetik envsecret değeri; 0 eşleşme |

İlk llmaas koşusunda değişmeyen `test_08_9_repeated_value_bounded_and_masked[10000-1.0]` 1 saniyeyi aştı. Tam yığın başlatımıyla çakıştı; kök sebebin kaynak yükü olduğu **doğrulanmadı**. Sonraki tam llmaas ve airgap koşuları aynı test dahil geçti. İlk kırmızı silinmedi; süre eşiği/ürün/test değiştirilmedi. Mevcut FOLLOWUP-76 kapatılmadı; yeni DRIFT-85 ürün bulgusu sayılmadı.

İki model skip'i açık **NOT_RUN: needs RUN_MODEL_TESTS=1**: gerçek Markdown Docling ve 13a DOCX. Bu SHA'da DNS testi kısıtlı yerel ağda çalıştı; varsayılan B düzeltmesi sonrası beklenen ilave DNS NOT_RUN henüz yok.

## Güvenlik turu

- **Kimlik:** uygulama auth/session/OBO kodu değişmedi; geniş entegrasyon auth ve provider testleri çalıştı. Test DB'leri kendi Compose Postgres'inde geçici UUID adlarıyla açılıp kapandı.
- **ACL:** pgvector/Qdrant role/user narrowing, metadata ve audit testlerinin converter dışındaki iddiaları korunmuş ve llmaas'ta geçti. Sahtenin ACL filtresini veya storage katmanını ikame ettiği görülmedi.
- **Secret:** gerçek .env okunmadı/yazılmadı; yalnız sentetik .env.test. Kendi servis loglarında 17 değer için sıfır ham eşleşme. Yeni ön kontrol URL metni operatör girdisi; inceleme URL'lerinde credential yoktu.
- **SQL:** ürün SQL/migration değişmedi. Entegrasyon test DB host koruması postgres/localhost/127.0.0.1 olarak korunmuş. Yalnız kendi yığınında migration/fixture işlemleri yürütüldü.
- **Egress:** MAJOR-1. İnceleme ağı internal, tools DNS loopback; model loader env offline1 doğrulandı. Host/kurum resolver ve dış sistem sorgusu yapılmadı.
- **PII:** sentetik dosyalar/örnekler kullanıldı; gerçek müşteri korpusu yok. Audit PIIsiz test iddiaları duruyor. Yeni belge/yardımcı herhangi bir gerçek veri taşımıyor.
- **Log sızıntısı:** yeni ürün log kodu yok; servis kapısının hata mesajı servis adı/URL/komut içeriyor. Kontrol edilen own servis loglarında sentetik secret eşleşmesi yok. 02 structured-extra bulgusu bu paketin dışında, yeniden kapatılmadı.

## Ortam, komutlar ve NOT_RUN

Kendi proje `review-gates-r1`, FFCORE_VERSION=0.0.0-review-gates, backend18054/frontend18055; yerel fixgates backend/tools/frontend imajları ayrı review etiketiyle kullanıldı, indirme/build yok. Backend imaj kaynak eşitliği yukarıda. Compose kaynağı exact SHA; ek inceleme dosyası `.worktrees/review-gates-r1-evidence/compose.review.yaml` yalnız runtime offline/fake, kaynak ro/cache ayarları ve DNS/ağ sınırı getiriyor. Kaynak testlere patch yok.

Unit/lint: `docker run --rm --network none ... -v <worktree>:/work:ro -w /work ffcore/tools:0.0.0-review-gates make lint test`; profil env ile iki değer. ruff cache /tmp, pytest cache/bytecode kapalı. İlk lint ro-cache ayarı eksikliği test başlamadan düzeltildi.

Int: `docker compose -p review-gates-r1 --env-file .env.test -f compose.yaml -f <review-override> --profile test --profile qdrant up -d --wait --pull never`, ardından `run --rm --no-deps -e DEPLOY_PROFILE=<profil> tools make test-int`. İlk harness up çağrısında yanlış tools profili de açıldı ve tools exit0 nedeniyle up exit1 verdi; tools profili çıkarılarak belgelenen servis profilleriyle up --wait geçti. Bu iki harness hatası ürün bulgusu sayılmadı. Model cache yeni/kendi volume, başka oturum cache'i bağlanmadı. Ortam probe'un ilk Settings/shell quoting hataları dış çağrı/test başlatmadan düzeltildi.

**NOT_RUN:** gerçek model Docling/DOCX/Paddle/embed kalite ölçümleri; yetkisiz host/kurum DNS; PayCore/sunucu/dış sistem; ürün değişmediğinden yeni UI/e2e/benchmark. Baz fe0d434'ün eski tüm kırmızı takımı bu tur tekrar çalıştırılmadı (PR işçi kanıtı bağımsız passed sayılmadı); baz kaynak diff'i okundu. Kendi iki profil kapılarının güvenli runtime override ile geçtiği, PR'ın sınırsız varsayılan DNS ortamının geçtiği anlamına gelmez.

## Temizlik

2026-10-29 13:13: testler sonrası kendi model_cache hâlâ **0 dosya**. Kendi Compose projesi down-v ile kapatıldı. İlk yanlış tools profiliyle oluşmuş kapalı tools konteyneri cache'i tutuyordu; proje etiketi ve stopped durumu doğrulanıp yalnız bu konteyner, ardından kendi boş cache volume'u kaldırıldı. Son own container/volume filtreleri boş. Başka oturumun `04a-knowledge-core_model_cache` volume'u korundu, bu incelemeye bağlanmadı. HEAD tam SHA/ağaç temiz doğrulandı; detached worktree `git worktree remove` ile kaldırıldı (exit0), yol artık yok; force kullanılmadı. Evidence paket kapanışına kadar kaldı; review etiketli imajlar temizlenebilir. Ana checkout/switch, ürün kodu değişikliği, commit/push yok.
