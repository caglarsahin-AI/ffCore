# 10b-poc-1 — r2 delta

İstek **K-10bp-0008**, ACK **R-10bp1-0006**. İncelenen tam SHA **c0926f9cee3928706847011ec02065b2d0ed8052**, PR baz **fe0d434**, delta baz **0ba0ac2e2b546d65990f4bd5ff63c6a259ac2f7d**. Ayrı detached review-10bp1-r2; inceleyici ffcore-inceleyici-20261028-0203.

**Karar: ONAY. BLOCKER 0, MAJOR 0, MINOR 0.** R1'in iki MINOR'u bağımsız eski problarla kapandı. Kapsam yalnız bu düzeltmeler ve ilgili10bp1 e2e; eski ürün/model alanları yeniden açılmadı.

## Kapanışlar

- **MINOR-1:** documentsFinished, ilk yükleme dışında aktif→terminal veya yeni terminal belge gelişini saptıyor. useDocuments mevcut poll sonucunda bu değişimi görünce KB ayrıntı/listesini exact key ile invalid ediyor; yeni timer yok. Exact kullanımı belge query'sini yeniden invalid edip döngü üretmiyor. Proje key'li remount/sorgular korunmuş. R1 review-probes.spec.ts değiştirilmeden tekrarlandı: **API15 / UI15**, sayfa yenilemeden. Yeni ürün test_10bp1_18 ayrıca KB listesi/özetini gerçek API ile karşılaştırıyor.
- **MINOR-2:** upload ve reindex alanları useAccess(projectId) ile disabled fieldset altında; drag/drop pick fonksiyonu read modda dosya kabul etmiyor. WriteGate düğmelerde korunmuş. Aynı bağımsız eski probe **6→0 enabled alan** verdi. Yeni ürün test_10bp1_19 read alanlarını kapalı, edit alanlarını etkin ve aramayı açık denetliyor.
- **10a kısa kontrol:** sağlayıcı/model form opener'ları normal read girişte kapalı. Mevcut test_10af_11'in iki gerçek tarayıcı testi de seçildi ve geçti; aynı erişim yolunda yeni alan sapması görülmedi. Açık bir formda yetkinin dışarıdan anlık geri alınması için yeni senaryo bu delta turunda koşulmadı; 10a yeniden tam review edilmedi.

## Kanıt

| Kapı | Sonuç |
|---|---|
| Lint / typecheck / check:api | exit0;iki spec güncel |
| Vitest | **114 passed /23 dosya**,5,77sn |
| Tek-worker Playwright | **28 passed**,2,1dk:22 ürün10bp1 +4 eski bağımsız probe +2 eski10a form testi |
| Eski sayaç probe | API15/UI15 |
| Eski read-only alan probe | enabled0 |
| Eski kimliksiz/analyst RSC ve proje A→B negatifleri | passed;model yolu/FAKE sızıntısı yok, eski KB404 |
| Backend kaynak |87 Python dosyası exact-SHA hash eşit |
| Dependency seed |31 doğrudan paket package/lock sürüm eşit |
| Baz state/diffcheck |boş/passed |

Dokuz dosyalık +200/-57 delta okundu: sayaç invalidasyonu/predicate, alan fieldset'leri, test ID'leri ve ilgili testler. Backend/Compose/şema/lock/dependency değişmedi. Kaynak git archive exact SHA'dan own Docker work volume'una açıldı; eski dört bağımsız probe yalnız bu kopyaya eklendi. Asıl worktree'ye ürün/test edit'i yapılmadı.

## Güvenlik turu

- **Kimlik:** readiness/auth kodunda delta yok; eski kimliksiz+analyst RSC negatifleri tekrar geçti, model/FAKE bilgisi açılmadı.
- **ACL:** projectId query key, remount ve WriteGate sınırları korunmuş; projeA→B eski KB404 probe geçti. Yeni disabled alanlar yalnız UI katmanı, backend kontrolü ikame edilmiyor.
- **Secret:** gerçek .env okunmadı/yazılmadı; yalnız own .env.test sentetik hesap/servis değerleri. Korunan normalnm seed yalnız ro; pw seed kullanılmadı.
- **SQL:** ürün SQL/migration değişmedi. E2E yalnız kendi geçici Postgres/LiteLLM yığınında sentetik fixture yazdı.
- **Egress:** own internal ağ; HF_HUB_OFFLINE1/TRANSFORMERS_OFFLINE1/FAKE1 render servis öncesi doğrulandı. up --pull never; run pull_policy never; düz Docker run --pull=never. Dış npm/model indirme yok.
- **PII:** gerçek müşteri verisi yok;13a sentetik PDF'leri/Türkçe dosya-sorgu kullanıldı. Yetkisiz başka proje verisi probe'da görünmedi.
- **Log:** kendi backend/worker/LiteLLM79892bayt logunda10sentetik envsecret değeri için0eşleşme; değerler basılmadı.02 log maskeleme bulgusu bu paketle kapatılmadı.

## Ortam ve sınırlar

Own proje review-10bp1-r2, FFCORE_VERSION=0.0.0-review-10bp1, backend18058. Backend96be37c21258/tools25da00c2e5a6; yerel pinli Playwright image d8e19ba36e14. Modelcache başlangıç boş; başka model cache'i bağlanmadı. Güncel normal node_modules salt-okunur seed'den yalnız own nm volume'una kopyalandı,31 paket sürümü doğrulandı. Ağdan npm ci yapılmadı; mevcut doğrulanmış bağımlılıklar kullanıldı.

Node kapıları Docker network none'da; tüm çıktı/cache kendi volume'unda. E2E komutu: `npx --offline playwright test test_10bp1 review-probes test_10af_11 --grep-invert @model-missing --workers=1`, own Compose e2e servisi/pull_policy never. Tek worker, gerçek backend/worker/DB, FAKE_EMBED1.

**NOT_RUN:** değişmeyen model_missing/fake0 aşaması bu delta turunda tekrarlanmadı (R1 kanıtı önceki SHA'ya ait); tüm98 eski+yeni ürün e2e takımı bağımsız tekrar edilmedi, seçilenler ayrı raporlandı; tam backend test/test-int/fullLangfuse smoke, gerçek model/başarılıDocling/Paddle/Lighthouse/ikinci profil tam e2e. Eski sınırlar ve FOLLOWUP'lar yeniden kapatılmadı. Worker'ın1+98 sonucu bağımsız tamkoşu sayılmadı.

## Temizlik

2026-10-29 14:59: yalnız own review-10bp1-r2 yığını down-v ile kapandı (exit0), own external work/nm volume'ları ayrıca kaldırıldı. Son own container/volume filtreleri boş; korunan npm/modelcache'ler değişmedi. Exact HEAD c0926f9cee3928706847011ec02065b2d0ed8052/ağaç temiz doğrulandı; git worktree remove exit0, hedef artık yok; force kullanılmadı. R1/r2 güvenli helper/sonuç/10PNG evidence paket kapanışına kadar korundu; review imajları temizlenebilir. Ana checkout/switch/ürün edit'i/commit/push yok.

Kapanış eki — 2026-10-29 15:22 (K-02-0024): onaylı 02 SHA0940628e04c7e2af26ec35f311c50e7211df9f7a ve10b SHA c0926f9cee3928706847011ec02065b2d0ed8052 main atası olarak salt okunur doğrulandı. Koordinatörün kapanış izniyle yalnız review-02-r1/r2/r3/r4-evidence ve review-10bp1-r1/r2-evidence dizinleri, mutlak .worktrees sınırı ve reparse point kontrollerinden sonra kaldırıldı (5+3+3+1+16+13 dosya). Yoklukları doğrulandı. Kalıcı review raporları/kanallar korundu; korunan cache ve başka oturum kaynaklarına dokunulmadı. Önceki evidence bağlantıları artık tarihsel referanstır.
