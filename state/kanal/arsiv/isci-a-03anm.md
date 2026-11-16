# Arşiv: isci-a · 03anm

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-03anm-0001 · 2026-10-30 17:48 · → koordinator · ACK
Paket: fix/03a-nonmember-404 (FOLLOWUP-103)   Cevap: K-04aWR-0007 / K-04aWR-0008
GOREV alındı, yeni oturum ffcore-isci-a-03anm, lease ACTIVE. Worktree .worktrees/fix/03a-nonmember-404 (HEAD f1f78fc = main, temiz). Plan A-04awr-0008 + karar A (K-04aWR-0005) esas: `_grant` üye değil / proje yok → 404 `project_not_found` aynı gövde, rol yetmez 403 aynen, audit'te gerçek neden ayrı alan; 06a runs 404 uyum testi; 12 uç parametrik; R-04AWR-0001 MINOR-1 (`test_04awr_5` açık Settings). PR dosyası state/pr/03a-nonmember-404.md. Sıra: önce kırmızı test → düzeltme → lint + make test iki profil; test-int için "YIGIN-AÇ 03anm" (18030/13030) ile sıra isteyeceğim.

### A-03anm-0002 · 2026-10-30 17:58 · → koordinator · DURUM
Paket: fix/03a-nonmember-404 (FOLLOWUP-103)   Cevap: K-03ANM-0001
K-03ANM-0001 alındı (A-03anm-0001 ACK ile aynı iş; OKUMA-TAMAM bu oturumda A-INIT-0001, kanallar 17:47 itibarıyla yeniden tarandı). DURUM: PLANNED. Plan state/pr/03a-nonmember-404.md (kabul 1-7, felsefe üç sorusu). Kırmızı test yazıldı: tests/integration/test_03a_nonmember_404.py (OpenAPI'deki tüm `{project_id}` uçları parametrik + F10 12 uç kapsama + düşük rol 403 + silinmiş proje + audit `reason` + 06a run uyumu). Varsayım: uuid olmayan project_id de 404, audit `no_project`. Onaylı plan üstünde ilerliyorum; DB testi için "YIGIN-AÇ 03anm" sırası isteyeceğim.

### A-03anm-0003 · 2026-10-30 18:00 · → koordinator · DURUM
Paket: fix/03a-nonmember-404   Cevap: K-03ANM-0001
YIGIN-AÇ 03anm talebi (sıra bekliyorum): `FFCORE_VERSION=0.0.0-03anm`, `BACKEND_PORT=18030 FRONTEND_PORT=13030`, `--profile test --profile qdrant`. Amaç: yeni testin kırmızı kanıtı (main kodu), düzeltme sonrası yeşil + etkilenen entegrasyon testleri + make test-int. Bu arada kod düzeltmesi ve birim/lint yığınsız.

YIGIN-AÇ 03anm · 2026-10-30 17:52 · isci-a · 18030/13030 · FFCORE_VERSION=0.0.0-03anm (K-03ANM-0002)
YIGIN-KAPA 03anm · 2026-10-30 18:30 · down -v exit 0, konteyner 0, volume 0

### A-03anm-0004 · 2026-10-30 18:30 · → koordinator · DURUM
Paket: fix/03a-nonmember-404 (FOLLOWUP-103)   Cevap: K-03ANM-0002
DURUM: VERIFIED. HEAD 8d3cb3bfde871165f49e088e8d6a7e07b29d329f (main f1f78fc üstüne 2 commit: b80c8c9 kırmızı test, 8d3cb3b düzeltme). Kırmızı (b80c8c9): 72 failed / 2 passed, parametrik 69/69 hepsi 403 insufficient_role. Kapılar: make lint 0; make test llmaas 696/696, airgap 696/696; make test-int 8d3cb3b 516 passed / 4 skipped (opt-in), exit 0. Çıktılar state/pr/03a-nonmember-404-kapilar/ (tee).
Not 1: ilk test-int'te 4 düşüş: 03a OBO üye olmayan süper admin ve 07 outsider (beklenti 403 → 404, karar A); 08_19/08_6 paylaşımlı DB'de audit satırını yalnız eylem adıyla sayıyordu, yeni test artık audit'lenen 404 retleri ürettiği için sayım kayıyordu → conftest `audit_rows(..., project=None)` additive filtre, 08 testleri kendi projesine daraltıldı. Gevşetme yok.
Not 2: tenant ucu DELETE /projects/{id} süper admin olmayana var/yok proje için birebir aynı 403 veriyor (sızıntı yok); testte açık istisna. OpenAPI değişmedi (404 zaten ERROR_RESPONSES'ta), yaml'lar bayt aynı.
Not 3: A-03anm-0002/0003 saat damgaları 17:58/18:00 yazılmış, gerçek 17:49/17:50; içerik doğru.

### A-03anm-0005 · 2026-10-30 18:30 · → koordinator · KAYIT-TALEBI
Paket: fix/03a-nonmember-404   Cevap: -
Tür: FOLLOWUP-. Önyüz `frontend/lib/api/errors.ts`'te `project_not_found` için mesaj anahtarı yok; bu kodu alan ekran genel hata + kod gösterir. Önceden yalnız süper admin/olmayan projede görülürdü, artık her üye olmayan çağıranda. Öneri: bir sonraki önyüz dalında `project_not_found` eşlemesi (en/tr) ve proje bağlamında "proje yok ya da erişiminiz yok" durumu. Touch-zone'um dışı, dokunmadım.

### A-03anm-0006 · 2026-10-30 18:30 · → koordinator · PR-HAZIR
Paket: fix/03a-nonmember-404 (FOLLOWUP-103)   Cevap: K-03ANM-0002
PR: C:\ai_paycore\ffcore\state\pr\03a-nonmember-404.md · Branch fix/03a-nonmember-404 · Worktree .worktrees/fix/03a-nonmember-404 · Baz main f1f78fc · SHA 8d3cb3bfde871165f49e088e8d6a7e07b29d329f · Sınıf [A] · push yok. 12 dosya (1 kod, 10 test, docs/api.md). Yığın kapalı; review yığın isterse komutlar PR dosyasında. Branch'e başka commit atmıyorum.

### A-03anm-0007 · 2026-10-30 19:10 · → koordinator · HANDOFF
Paket: fix/03a-nonmember-404 (FOLLOWUP-103)   Cevap: K-03ANM-0007
- Durum: MERGED (main 298cbb4; r1 ONAY 8d3cb3b, 0 bulgu). Lease ffcore-isci-a-03anm RETIRED; oturum kapanıyor.
- Tam sonraki adım: bu dalda iş yok. Sıradaki isci-a işleri yeni oturumlarda (kullanıcı paketleme kararı): FOLLOWUP-105 fix/06a-definition-error-codes, FOLLOWUP-108 fix/04a-breadcrumb, FOLLOWUP-101 fix/04a-updated-at-source, 13b A tarafı. Not: 18 `test_18_f10_4_direct_ids_are_404` ve 13b üye-olmayan negatif testi artık yeşil olmalı (bu dalda koşulmadı, doğrulanmadı).
- Değişen dosyalar: backend/ffcore/core/auth.py; tests/integration/{test_03a_nonmember_404 (yeni), conftest (audit_rows project filtresi), test_03a_access, test_03a_obo_scope, test_04a_api, test_04a_review_r1_acl, test_05a_sql, test_07_api_read, test_08_api}; tests/unit/test_04a_convert.py; docs/api.md. Ayrıntı state/pr/03a-nonmember-404.md.
- Testler: lint 0, make test 696/696 iki profil, test-int 516 (+4 opt-in skip) 8d3cb3b'de; main kapısı koordinatörde 698/698 + test-int 520.
- Kararlar: karar A (K-04aWR-0005) `project_not_found`; audit `after.reason` not_member|no_project; tenant DELETE /projects/{id} aynı 403 (sızıntı yok); uuid olmayan id 404.
- Blocker: yok. Açık takip: FOLLOWUP-112 (önyüz `project_not_found` eşlemesi, isci-c).
- Commit edilmemiş durum: yok. Yerelde: imaj etiketleri ffcore/{backend,frontend,tools}:0.0.0-03anm (0.0.0-main kopyası) silinebilir; worktree .worktrees/fix/03a-nonmember-404'e dokunmadım. Yığın ffcore-03anm kapalı (down -v).
