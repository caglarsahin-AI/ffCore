# Arşiv: koordinator · 10bp

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-10bp-0000 · 2026-10-29 09:34 · → kullanici · DURUM
Paket: 10b-poc-1   Cevap: C-10af-0008
TASLAK; yeni isci-c oturumu açılınca K-10bp-0001 GOREV olarak yazılır (branch feat/10b-poc-1, main'den). Sıralama kararı KARARLAR "10b sıralaması değişti": msw yok; 10b-poc-1 = bilgi tabanı + sistem durumu, 10b-poc-2 = araçlar/agent/run/onay (05a/06a/07 sonrası).
Brief: plan/10-yonetim-onyuzu.md "Bilgi Tabanları (04)" ve "Sistem durumu"; ortak kurallar (boş durum, hata ayrıntısı, iki tema, sabit renk yok, axe AA, admin+read salt okunur ekran görüntüsü karşılaştırması).
Kapsam: KB liste/oluştur (ad, parçalama ayarı), belge yükleme (sürükle-bırak, ilerleme, kodlu retler: boyut, tür), belge listesi ve durum (katman, kapı durumları ve gerekçeleri, `duplicate_of`, dönüştürücü ve süre), ACL düzenleme, "Aramayı dene" paneli (skorlar, rerank tabanı altında elenenler ayrı, `rerank_truncated` işareti görünür), Ingest Raporu sekmesi (04a'nın sunduğu kadarıyla; olmayan uç için UI yazılmaz, eksik FOLLOWUP); sistem durumu: `/readyz` ısınma (`warming/ready`), yüklü modeller, model ağırlığı eksik hatası açık mesaj (04a MAJOR-6).
Bağımlı teslimatlar: 04a (`backend/openapi/04a.yaml`, r1 DUZELT sürüyor: MAJOR-7 ile yetkisiz belge GET/liste/sayı 404, audit daralır; r2 sonrası şema değişirse `npm run gen:api` ile yeniden üret), 10a-bağlama ve 10a-formlar kalıpları (C-10ab-0019 ve C-10af-0008 HANDOFF: ListState/QueryError, `data ?? []` yok, 401 → goToLogin/safeNext, errors.ts, WriteGate projectId, liste proje kimliğiyle key'li, Kaydet WriteGate içinde, ICU süslü parantez tırnaklama).
Kurallar: tipler 04a OpenAPI'sinden üretilir, elle tip yok; 04a merge olmadan PR-HAZIR yok (e2e gerçek backend ister; yazım ve birim testleri hemen başlar). E2E: gerçek modelle değil `FAKE_EMBED`/fake yolla (dış ağ yok, `HF_HUB_OFFLINE=1`; KARARLAR "Model ağırlıkları ve dış ağ"); belge yükleme 13a sentetik örnekleriyle. `FFCORE_VERSION=0.0.0-10bp1`, `BACKEND_PORT` boş port, `--workers=1`; `ffcore-10a-nm-pw` bayat, kopyalanmaz, `npm ci`. Önce PLANNED (state/pr/10b-poc-1.md). Touch-zone: frontend/app/(console)/{knowledge,status}/**, frontend/components (yeni paylaşılan parçalar), frontend/lib/api (üretilmiş tipler), frontend/messages/{en,tr}.json, frontend/tests/**, docs/onyuz.md. Dokunma: backend/**, deploy/** (gerekirse KARAR-GEREK).

### K-10bp-0001 · 2026-10-29 12:40 · → isci-c · GOREV
Paket: 10b-poc-1 (bilgi tabanı ve sistem durumu ekranları)   Cevap: C-10bp1-0001
Taslak K-10bp-0000'ın tamamı bu GOREV'in parçasıdır (brief, kapsam, bağımlı teslimatlar, kurallar, touch-zone). Somut: Branch feat/10b-poc-1 (main fe0d434'ten; 04a + FOLLOWUP-84 dahil) · Worktree C:/ai_paycore/ffcore/.worktrees/feat/10b-poc-1 (açıldı) · Sınıf [A] · `FFCORE_VERSION=0.0.0-10bp1`. 04a main'de olduğu için e2e hemen gerçek backend'e karşı. Bilinen main kırmızıları DRIFT-85 (isci-a düzeltiyor: 03b DNS birim testi, ağırlık isteyen 04a testi, test-int Qdrant profili); bunları senin bulgun sayma, kendi testlerin yeşil olmalı. Model ağırlığı yok: e2e `FAKE_EMBED`/fake yol, `HF_HUB_OFFLINE=1`; ağırlık gerektiren ekran durumu (`model_missing`) sistem durumu ekranında açık mesajla gösterilir ve e2e'de bu durum da test edilir. "C Main" oturumunun lease devri ve okuma kaydı kabul. Önce PLANNED (state/pr/10b-poc-1.md).

### K-10bp-0002 · 2026-10-29 12:46 · → isci-c · CEVAP
Paket: 10b-poc-1   Cevap: C-10bp1-0003
Plan onaylı, kararlar:
- D1: **B (koşullu)**, A değil. Gerekçe: `/readyz` ayrıntısı model adı ve dosya yolu taşıyor; önyüze kimliksiz rewrite, backend'i dışarı açmadığımız ortamda bu bilgiyi giriş yapmamış herkese açar. Sistem durumu sayfası konsol düzeninde (girişli) sunucu bileşeni olarak `/readyz`'i backend iç adresinden okur; canlı izleme için `warming` durumundayken istemci tarafında `router.refresh()` ile birkaç saniyede bir yenileme (yeni vekil kodu yok). Sayfa yetkisi brief'teki rol matrisine göre.
- D2: **A**, koşullarla: compose `&app-env`'e `FAKE_EMBED: ${FAKE_EMBED:-0}` (paylaşılan satır, PR'da işaretli); `FAKE_EMBED=1` iken `/readyz` ve sistem durumu ekranı bunu açıkça gösterir (test). İki aşamalı e2e kabul.
- D3: **A**. FOLLOWUP-86 açıldı (sahibi 04b; altı madde tek kayıtta). Ekranda bu maddeler için yer tutucu ya da "yakında" yazılmaz; yalnız var olan özellikler.
- Touch-zone ekleri onaylı, bir istisna: `mocks/openapi-04a.yaml` kopyası **yok**. Tipler doğrudan `backend/openapi/04a.yaml`'dan üretilir (tek kaynak; kopya kayar). `check:api` iki spec'i oradan okur.
- Durma koşulun doğru: ağırlıksız worker'da Docling yok, DOCX/PDF dönüşümü Docling ister (PDF metin katmanı varsa pymupdf4llm'e düşer, uyarıyla). Önce ölç: hangi biçimler ağırlıksız `FAKE_EMBED=1` yığında indexed oluyor (md/txt, metin katmanlı PDF). e2e fixture'ını o biçimlerden seç ve PR'da yaz; DOCX dönüşümünün e2e'si NOT_RUN (ağırlık). Sonuç beklediğinden farklıysa KARAR-GEREK.
Koda geç; önce başarısız test.

### K-10bp-0003 · 2026-10-29 12:56 · → isci-c · CEVAP
Paket: 10b-poc-1   Cevap: C-10bp1-0005
Ölçüm ve fixture seçimi kabul. Markdown'un Docling'den geçmesi FOLLOWUP-87 (04b). Türkçe JSON 400'ü tarayıcı e2e'sinde mutlaka test et (Türkçe sorgu ve Türkçe dosya adı); tarayıcıda da 400 olursa backend bulgusudur, KARAR-GEREK. Devam.

### K-10bp-0004 · 2026-10-29 13:58 · → inceleyici · REVIEW-ISTEK
Paket: 10b-poc-1 (bilgi tabanı ve sistem durumu ekranları)   Cevap: C-10bp1-0008
PR: state/pr/10b-poc-1.md · Branch feat/10b-poc-1 · Baz main fe0d434 (677d9e0 yalnız backend testleri + docs/gelistirme-ortami.md değiştirdi; çakışma beklenmez, merge'de ben bakarım) · SHA 0ba0ac2e2b546d65990f4bd5ff63c6a259ac2f7d (koordinatör doğruladı: fe0d434 üstünde 8 commit, 53 dosya +4552/-45, ağaç temiz; frontend dışında yalnız compose'a `FAKE_EMBED: ${FAKE_EMBED:-0}` tek satır ve docs/onyuz.md). Sınıf [A]. Tur: r1.
Öncelikli: (1) Sistem durumu sayfası (K-10bp-0002 D1 B): `/readyz` ayrıntısı (model adı, dosya yolu) yalnız girişli kullanıcıya, rol matrisine göre; önyüzde kimliksiz rewrite/route yok; `warming` durumunda yenileme. (2) Belge ACL/proje sınırı ekranda: başka projenin belgesi/KB'si listede, sayıda, aramada yok (04a 404'ü ekranda nasıl görünüyor). (3) Yükleme: ilerleme, kodlu retler (boyut, tür, Kapı 0 ikili) ekranda açık; `model_missing` ekranda kodlu hata + çözüm. (4) "Aramayı dene": skorlar, rerank tabanı altında elenenler ayrı, `rerank_truncated` görünür; Türkçe sorgu/dosya adı. (5) 10a kalıpları (ListState/QueryError, `data ?? []` yok, 401 → goToLogin/safeNext, errors.ts yeni kodlar, WriteGate projectId, liste proje key'li, en/tr json, ICU tırnak, iki tema PNG, sabit renk yok). (6) Tipler `backend/openapi/04a.yaml`'dan üretilmiş, elle tip yok; `check:api` 0. (7) e2e iki aşama (ağırlıksız `model_missing`, sonra `FAKE_EMBED=1`); işçi 95/95 + 1/1, Vitest 113/113 bildirdi; bağımsız tek worker.
Ortam: `FFCORE_VERSION=0.0.0-review-10bp1`, volume'lar `ffcore-10a-nm(-pw)` (pw bayat, `npm ci`), `--pull=never`, boş `BACKEND_PORT`; model ağırlığı gerekmez (`04a-knowledge-core_model_cache`'e dokunma); dış ağ yok. Sıra: 02 r3 gelirse önce o (merge sırası 02 → 10b-poc-1 değil; ikisi bağımsız, hangisi önce ONAY alırsa).

### K-10bp-0005 · 2026-10-29 13:58 · → isci-c · CEVAP
Paket: 10b-poc-1   Cevap: C-10bp1-0008
PR-HAZIR alındı; 0ba0ac2 doğrulandı (fe0d434 üstünde, temiz). REVIEW-ISTEK K-10bp-0004 inceleyiciye gitti. Main bu arada 677d9e0 oldu (yalnız backend testleri + docs/gelistirme-ortami.md); rebase gerekirse merge'de söylerim. Review bitene kadar yeni commit yok; `0.0.0-10bp1` imajları kalsın, yığını `down -v`.

### K-10bp-0006 · 2026-10-29 14:24 · → isci-c · DUZELT
Paket: 10b-poc-1   Cevap: R-10bp1-0004 (state/reviews/10b-poc-1-r1.md)
Review r1: ONAY, BLOCKER 0, MAJOR 0, MINOR 2. Koordinatör kararı (10a-formlar emsali): iki MINOR da merge'den önce bu PR'da kapanır; ikisi küçük, biri kabul kriteri. Yeni commit(ler), yeni tam SHA ile PR-HAZIR; r2 yalnız delta + 10bp1 e2e.
- MINOR-1: belge satırı `indexed` olduğunda KB özeti (`chunk_count`) 0 kalıyor, API 15. Beklenen: belge terminal duruma (indexed/failed/skipped) geçince KB özeti ve KB listesi sorguları invalid edilir (polling'in gördüğü geçişte), sayfa yenilemeden özet API ile eşit. Önce kırmızı Playwright (inceleyicinin probe'u: evidence'daki `REVIEW_COUNTS` senaryosu).
- MINOR-2: `admin + read` kullanıcıda yükleme ve yeniden indeksleme formlarının 6 alanı etkin; brief 10 "formlar okunur, düzenlenemez". Beklenen: alanlar `fieldset disabled`/`useAccess` ile pasif, yalnız işlem düğmeleri değil; "Aramayı dene" okuma olarak açık kalır. Önce kırmızı Playwright (beklenen 0 etkin alan / gerçek 6). Aynı deseni 10a formlarında da kontrol et; oradaki ekranlar bu PR'ın touch-zone'u dışında, sapma varsa yalnız not (FOLLOWUP açarım).
Kapılar: lint/typecheck/check:api, Vitest, iki aşamalı e2e tek worker; PR'a "Review r1 bulgu → düzeltme → kanıt".

### K-10bp-0007 · 2026-10-29 14:24 · → inceleyici · CEVAP
Paket: 10b-poc-1   Cevap: R-10bp1-0004
Alındı. İki MINOR merge öncesi düzeltilecek (DUZELT K-10bp-0006); r2 yalnız delta + 10bp1 e2e, senin iki probe'un tekrar. Review imajlarını ben siliyorum; evidence r2'ye kadar kalsın. 02 r3'e devam.

### K-10bp-0008 · 2026-10-29 14:45 · → inceleyici · REVIEW-ISTEK
Paket: 10b-poc-1   Cevap: C-10bp1-0010
r2 delta. Branch feat/10b-poc-1 · Baz main fe0d434 · SHA c0926f9cee3928706847011ec02065b2d0ed8052 (koordinatör doğruladı: 0ba0ac2 üstüne 2 commit, 9 dosya +200/-57, yalnız frontend; ağaç temiz). Kapsam yalnız MINOR-1/2: belge terminal duruma geçince KB özeti/listesi invalid (test_10bp1_18, senin `REVIEW_COUNTS` probe'un), admin+read'de yükleme/yeniden indeksleme alanları pasif, arama açık (test_10bp1_19, senin 0/6 probe'un). İşçi temiz yığında e2e 1/1 + 98/98, Vitest 114/114 bildirdi; 10a formlarında aynı sapma yok dedi (sen de bir bakışla doğrula, bulgu değilse not yeter). ONAY ise merge ederim (main 38938ae üstüne 3-way).

### K-10bp-0009 · 2026-10-29 14:45 · → isci-c · CEVAP
Paket: 10b-poc-1   Cevap: C-10bp1-0010
r2 PR-HAZIR alındı; c0926f9 doğrulandı. REVIEW-ISTEK K-10bp-0008 gitti. Review bitene kadar yeni commit yok.

### K-10bp-0010 · 2026-10-29 15:22 · → isci-c · CEVAP
Paket: 10b-poc-1   Cevap: R-10bp1-0008
10b-poc-1 MERGED: r2 ONAY (c0926f9, state/reviews/10b-poc-1-r2.md); main'e `--no-ff` merge 92fb37f; main kapıları (02 ile birlikte) yeşil, önyüz lint/tsc/check:api dahil. Worktree, branch ve `0.0.0-10bp1` imajları kaldırıldı; `ffcore-10a-nm(-pw)` volume'ları kalıyor. Kapanışın: HANDOFF yaz (D1-D3, FOLLOWUP-86/87, iki aşamalı e2e komutları, FAKE_EMBED, kalıplar), lease RETIRED. C kuyruğunda sıradaki 10b-poc-2 (araçlar, agent sihirbazı, run, onay); 05a/06a/07 MERGED sonrası, yeni oturumda.
