# 10b-poc-1 — bilgi tabanı ve sistem durumu — r1

İstek **K-10bp-0004**, ACK **R-10bp1-0001**. İncelenen tam SHA **0ba0ac2e2b546d65990f4bd5ff63c6a259ac2f7d**, baz **fe0d434**; ayrı detached `.worktrees/review-10bp1-r1`. İnceleyici ffcore-inceleyici-20261028-0203. Ana checkout/switch yok; yalnız bu SHA.

**Karar: ONAY; BLOCKER 0, MAJOR 0, MINOR 2.** İki aşağıdaki UI bulgusu açık; kapatılmış veya testleri geçmiş sayılmıyor. Indexleme/arama ve API yetki korumasını engellemedikleri için MINOR değerlendirildi; takip/merge kararı koordinatörde.

## MINOR-1 — Worker tamamlandığında KB özetinin parça sayısı yenilenmiyor

Kaynak: `frontend/lib/api/knowledge-queries.ts:70-87`, `frontend/app/(console)/knowledge-bases/[kbId]/page.tsx:104-119`. Belge listesi işlenen belge varken poll ediyor. Yükleme mutation'ı 202 geldiğinde belge/KB query'lerini invalid ediyor; worker daha sonra indekslemeyi bitirince belge listesi güncelleniyor ama KB özet query'si yeniden invalid olmuyor. Liste query'sinin de belge mutation invalidasyonunda ayrı yenilemesi yok.

Bağımsız gerçek tarayıcı repro: yeni KB aç, konsoldan 13a bakım PDF'ini yükle, belge satırının indexed olmasını bekle, 2,5 saniye daha bekle. Gerçek backend KB GET **chunk_count=15**, ekrandaki KB özetinde **0** kaldı: `REVIEW_COUNTS {api:15,ui:0}`. Belge satırının terminal durumu ve gerçek parçalar mevcut. Bu, veri kaybı veya ACL açığı değildir; aynı ekranda tamamlanmış indexlemenin özet sayısı yanlış kalıyor.

Beklenen: worker terminal geçişi sonrasında KB özet/listedeki ilgili sayılar güncellensin; sonsuz ek poll yerine mevcut belge yaşam döngüsüyle tutarlı invalidasyon yeterli. Negatif kabul: sayfa yenilemeden indexed belge satırı, özet ve gerçek KB GET parça sayıları aynı. Bağımsız probe bu iddiada kırmızı; ürün testleri bunu kontrol etmiyor.

## MINOR-2 — Salt-okunur sayfada yükleme/yeniden üretme alanları hâlâ enabled

Kaynak: `frontend/components/document-upload.tsx:91-130`, `frontend/components/reindex-form.tsx:39-56`; brief `plan/10-yonetim-onyuzu.md:20` formlar görüntüleme modunda, alanlar okunur/düzenlenemez diyor. WriteGate yalnız Upload/Rebuild düğmelerini sarıyor. Dosya input'u, rol/açık ACL seçimleri ve reindex katman/full kontrolleri salt-okunur kullanıcıda disabled/readOnly olmuyor.

Bağımsız admin+read tarayıcısında yalnız upload/reindex alanları seçildi: **6 enabled kontrol**. `REVIEW_READ_ONLY_ENABLED_FIELDS 6`; beklenen0 assert'i kırmızı. Düğmeler pasif, mevcut ürün e2e'sinde doğrudan DELETE403/read_only_access kontrolü var; yetkisiz sunucu mutasyonu saptanmadı. Bu yüzden güvenlik bypass'ı olarak sunulmadı. Eksik, brief'in okunur form etkileşimi kuralıdır.

Beklenen: aynı bileşenler proje kimliğiyle useAccess/ortak read-only kalıbını kullanarak bu form alanlarını da pasif/okunur sunsun; ayrı viewer ekranı gerekmez. Arama bir okuma işlemidir, kullanılabilir kalmalı. Negatif kabul: admin+read tüm upload/reindex alanları düzenlenemez; admin+edit alanları kullanılabilir, mutasyonlar WriteGate ve backend403 sınırını korur.

Her iki kanıt `.worktrees/review-10bp1-r1-evidence/review-probes.spec.ts` içinde. Kaynak worktree'ye test eklenmedi; yalnız git archive'dan oluşturulan kendi Docker test kopyasında çalıştı.

## Kapsam ve sözleşme

53 dosyalık diff okundu; frontend dışında yalnız onaylı Compose FAKE_EMBED varsayılan0 satırı ve belgeler. Baz state diff boş; diffcheck temiz. Backend uygulama/şema/lock değişmedi; kullanılan backend imajındaki **87 Python dosyası** LF-normalize hash ile exact SHA'ya eşit. Önyüz kaynakları git archive ile bu SHA'dan kendi çalışma volume'una alındı; build/PNG çıktıları asıl worktree'yi değiştirmedi.

K-10bp-0002 D1-D3 kararları ve FOLLOWUP-86 uygulandı. Uçsuz ACL sonradan düzenleme, ingest raporu, elenen parçaların listesi/rerank_truncated, preset ve ek sistem ölçümleri yeniden açılmadı; istemcide sahte veri/yer tutucu eklenmemiş. Rerank tabanı altında elenenlerin **sayısı** gösteriliyor; liste/truncated desteği iddia edilmiyor. Tipler doğrudan backend/openapi/04a.yaml'dan; check:api iki spec için geçti, ikinci spec kopyası yok.

KB liste/ayrıntısı proje key'iyle remount oluyor; sorgu key'leri proje+KB içeriyor. Mutasyon Save/Upload/Rebuild/Delete kontrolleri WriteGate projectId kullanıyor. ListState/QueryError ve 401 goToLogin/safeNext kalıpları korunmuş. EN/TR mesajları ve ICU parse kontrolleri geçti. Sabit renk/metin denetimi geçti; iki tema örnekleri görsel incelendi.

## Bağımsız testler

| Kapı | Sonuç |
|---|---|
| Önyüz lint / typecheck / check:api | hepsi exit0;iki şema güncel |
| Vitest | **113 passed /23 dosya**,8,26sn |
| E2E aşama1: ağırlıksız/fake0 | **1 passed**,43,1sn;model_missing kodu/açıklama/çözüm |
| E2E aşama2: fake1,tek worker | **95/95 ürün testi passed**;4 bağımsız probun2'si passed/2'si açıkMINOR kırmızısı. Toplam **97 passed/2 failed**,exit1,5,0dk |
| Bağımsız sayaç / read-only alan negatifleri | iki kırmızı; yukarıdaki açık MINOR1/2 |
| Bağımsız kimliksiz/analyst readiness RSC | passed;FAKE_EMBED/model yolu sızıntısı0 |
| Bağımsız proje A→B geçişi | passed;A KB başlığı yok,404 QueryError |
| Compose varsayılan fake | llmaas/airgap backend+worker+tools **0** |
| Backend kaynak / modelcache |87 dosya eşit;başlangıç0dosya/gerçek ağırlık yok;sonda4küçük ONNX Runtime metadata dosyası |

Ürün e2e'leri binary Kapı0 reddi, DOCX model_missing, Türkçe sorgu/dosya adı, iki skor/eşik/elenen sayısı, duplicate link, DELETE/reindex, read-only API403, analyst ACL görünmezliği, 404/503 hata ekranı, tema/axe ve önceki10a/10ab/10af akışlarını kapsıyor. 10bp1'in dört ekranı iki temada8axe testinde sıfır ihlal verdi;95ürün testinin19'u10bp1,76'sı önceki akışlar. Kendi iki negatifin başarısızlığı ürün testlerinin geçtiği iddiasına karıştırılmadı; birleşik99test koşusu exit1 verdi,99green denmedi.

## Güvenlik turu

- **Kimlik:** sistem durumu sayfası sunucuda kendi getSession+canOpen kontrolünü backend readiness fetch'inden önce yapıyor; yalnız layout/client RouteGuard'a güvenmiyor. /readyz için frontend rewrite/route eklenmemiş. Kimliksiz ve analyst RSC gövdeleri bağımsız tarandı, FAKE_EMBED/model yolu yok. Konsol /readyz HTML not-found gövdesi dönüyor, backend checks JSON'u açılmıyor; mevcut streamed200 davranışı ürün açığı sayılmadı.
- **ACL:** proje key'li query ve remount sınırı korunmuş; bağımsız proje değişimi eski KB'yi göstermedi. Analyst'in admin-only belgesini görememe/GET404 ve sayımlar backend04a sınırına dayanıyor; frontend alternatif filtre üretmiyor. Başka projenin KB'si 404 QueryError oluyor.
- **Secret:** gerçek .env okunmadı/kopyalanmadı/yazılmadı. Kendi .env.test yığını, sabit sentetik e2e hesabı; gizli değerler mesajlara basılmadı. Npm bağımlılıklarında korunan cache salt-okunur, pw seed kullanılmadı. Dinamik session içerebilen Playwright failure trace'leri evidence'a taşınmayacak; own geçici volume ile temizlenecek.
- **SQL:** uygulama/migration SQL değişmedi. E2E yalnız kendi geçici PostgreSQL/LiteLLM veritabanına sentetik kullanıcı/proje/KB/model yazdı; diğer yığınlara erişmedi.
- **Egress:** her model runtime env HF_HUB_OFFLINE1/TRANSFORMERS_OFFLINE1 ve aşamaya uygun FAKE0/1 render ile servis öncesi doğrulandı; kendi ağ internal. Run image pull_policy never, up --pull never; düz Docker run --pull=never. Dış npm/model indirme yok. Readiness adresi sabit backendUrl, kullanıcı girdisinden türetilmiyor.
- **PII:** 13a sentetik sözleşmeler/hesaplar; gerçek korpus/PayCore verisi yok. Türkçe dosya adı/sorgu gerçek tarayıcı üzerinden geçti. Backend error ayrıntısı rol kontrollü ekranda gösteriliyor; raw belge içeriği izleme servisine gönderilmedi.
- **Log sızıntısı:** kendi backend/worker/LiteLLM161527bayt logunda10sentetik envsecret değeri için0eşleşme. Değerler basılmadı.02 merkezi logging bulgusu bu PR ile kapatılmadı.

## Ortam / komutlar / NOT_RUN

Kendi Compose `review-10bp1-r1`, FFCORE_VERSION=0.0.0-review-10bp1, backend18056. Modelcache kendi boş volume'u; işçi04a cache'ine dokunulmadı. Yerel backend96be37c21258/tools25da00c2e5a6 ve pinli Playwright digest47b510dd…/image d8e19ba36e14. Node20.19.5-alpine. Başka yığın durdurulmadı.

Güncel **ffcore-10a-nm** salt-okunur seed'den kendi review-10bp1-r1-nm volume'una kopyalandı; bayat pw seed kopyalanmadı. 31 doğrudan bağımlılık package.json ve package-lock sürümleriyle eşit doğrulandı; Node kapıları ve glibc Playwright build çalıştı. Ağdan npm ci yerine mevcut doğrulanmış dependency tree kullanıldı. Tüm build/test/screenshot çıktıları kendi review-work Docker volume'unda, kaynak exact-SHA arşivinden; asıl worktree temiz kaldı.

Node kapıları `docker run --pull=never --rm --network none ... node:20.19.5-alpine sh -c 'npm run lint && npm run typecheck && npm run check:api && npm test'`. E2E aynı Compose dosyaları + kendi runtime override ile `up -d --wait --pull never backend`, sentetik create-superadmin, `run --rm --no-deps e2e ... playwright test --grep @model-missing --workers=1`; ikinci aşama FAKE_EMBED1 backend/worker up ve `--grep-invert @model-missing --workers=1`.

İlk ro-parent mount'unda eksik node_modules alt dizini oluşturulamadı; kendi archive volume'u ile çözüldü. İlk Compose run --pull komutu Compose2.23 desteklemediği için başlamadan reddedildi; bu sürümde pull_policy:never override render doğrulandı. İlk elle yazılmış Playwright digest uzunluğu yanlıştı; inspect reddetti, doğru digest doğrudan commit dosyasından alındı. Hiçbiri geçti sayılmadı, bu tur registry indirme denemesi yok.

**NOT_RUN:** gerçek embed/rerank/Docling/Paddle kalite ve süreleri; başarılı DOCX/Markdown dönüşümü; tam backend test/test-int (ürün backend kodu değişmedi); iki profil tam e2e (önyüz bağımsız, Compose varsayılanı iki profil kontrol edildi); gerçek warming→ready model ısınması (ağırlık yok; predicate birim testi var); 516MB gerçek tarayıcı413 (XHR birim testi var); Lighthouse FOLLOWUP-37; Langfuse açılmadığından tam make smoke (backend/readiness e2e'de gerçek); PayCore/sunucu/dış sistem. Bu kriterler geçti sayılmadı.

## Temizlik

2026-10-29 14:19: yalnız review-10bp1-r1 yığını down-v ile kaldırıldı (exit0). Kendi external review-10bp1-r1-nm ve review-10bp1-r1-work volume'ları ayrıca kaldırıldı; son own container/volume filtreleri boş. Work volume'undaki olası session içeren failure trace'ler de böylece temizlendi, evidence'a kopyalanmadı. Başlangıç modelcache0dosyaydı; son kontrol4 ONNX Runtime yerel metadata dosyası (deviceid ve SQLite/db-shm/db-wal;toplam82252bayt), model ağırlığı yok; içerikleri okunmadı, owncache ile kaldırıldı. ffcore-10a-nm, ffcore-10a-nm-pw ve04a-knowledge-core_model_cache varlıkları doğrulandı/korundu; yalnız normalnm seed başlangıçta ro okundu.

HEAD tam0ba0ac2e2b546d65990f4bd5ff63c6a259ac2f7d/ağaç temiz doğrulandı; worktree git worktree remove ile kaldırıldı (exit0), hedef artık yok; force kullanılmadı. Kendi güvenli probe/sonuç ve10PNG evidence'ı paket kapanışına kadar kaldı; reviewbackend/tools etiketleri temizlenebilir. Ana checkout/switch/ürün kodu değişikliği/commit/push yok.

Kapanış eki — 2026-10-29 15:22 (K-02-0024): onaylı 02 SHA0940628e04c7e2af26ec35f311c50e7211df9f7a ve10b SHA c0926f9cee3928706847011ec02065b2d0ed8052 main atası olarak salt okunur doğrulandı. Koordinatörün kapanış izniyle yalnız review-02-r1/r2/r3/r4-evidence ve review-10bp1-r1/r2-evidence dizinleri, mutlak .worktrees sınırı ve reparse point kontrollerinden sonra kaldırıldı (5+3+3+1+16+13 dosya). Yoklukları doğrulandı. Kalıcı review raporları/kanallar korundu; korunan cache ve başka oturum kaynaklarına dokunulmadı. Önceki evidence bağlantıları artık tarihsel referanstır.
