# Arşiv: isci-a · 04awr

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-04awr-0001 · 2026-10-30 12:18 · → koordinator · ACK
Paket: fix/04a-worker-ready   Cevap: K-06a-0029 / K-06a-0035
Yeni oturum ffcore-isci-a-04awr, lease ACTIVE. Görev: FOLLOWUP-97 karar A (işçi `ready` gönderir, dosya saati ondan sonra; açılışa ayrı kodlu sınır, aşımı kendi hata koduyla). Worktree .worktrees/fix/04a-worker-ready (be500c1) mevcut. Sınıf [A]; touch-zone: backend/ffcore/knowledge/convert/workers.py + ilgili config alanı + 04a havuz testleri + docs/bilgi-tabani.md ilgili paragraf. Sıra: kaynak oku → state/pr/04a-worker-ready.md planı → DURUM: PLANNED; kod onaydan sonra, önce kırmızı. Yığın gerekmez (yalnız birim testleri, yığınsız `tools make test` iki profil).

### A-04awr-0002 · 2026-10-30 12:24 · → koordinator · DURUM
Paket: fix/04a-worker-ready   Cevap: K-04aWR-0001 (zil)
Zil alındı; ancak K-04aWR-0001 GOREV metni state/kanal/koordinator.md'de yok (çalışma kopyası ve main f1b534c; son mesaj K-SEN-0027). Bağlayıcı kaynak olarak K-06a-0029 (karar A) + zil içeriğini esas alıyorum: WORKER_START_TIMEOUT kodlu açılış sınırı, ready olayı sonrası dosya deadlineı,
iki
flaky
test
olaya
dayalı,
docs
tek
paragraf,
kapılar
lint
+
make
test
iki
profil
+
yük
altında
10
tekrar.
Lütfen
GOREVi kanala yaz (kayıt için).
Worktree be500c1 idi (28d7a5f içermiyordu); kod commit'i yokken main f1b534c'ye fast-forward edildi. Plan state/pr/04a-worker-ready.md hazırlanıyor.

### A-04awr-0003 · 2026-10-30 12:23 · → koordinator · ACK
Paket: fix/04a-worker-ready   Cevap: K-04aWR-0001
GOREV alındı (A-04awr-0002'deki "kanalda yok" notu geçersiz: GOREV 12:25'te yazılmış, ben 12:24'te bakmıştım). Worktree e9583df (main). Lease ffcore-isci-a-04awr ACTIVE.

### A-04awr-0004 · 2026-10-30 12:23 · → koordinator · DURUM
Paket: fix/04a-worker-ready   Cevap: K-04aWR-0001
DURUM: PLANNED. Plan: state/pr/04a-worker-ready.md (semboller, 6 kabul → test, felsefe üç sorusu). Onay istenenler:
(1) Touch-zone eki: core/config.py (convert_worker_start_timeout_seconds, varsayılan 60) zorunlu; .env.example + deploy/docker-compose.yml birer satır (CONVERT_WORKER_START_TIMEOUT_SECONDS) öneriyorum, yoksa ayar compose'da değiştirilemez.
(2) Varsayım: aşım status=error + error_code=convert_worker_start_timeout (convert_cpu_limit kalıbı), belge failed; yeni status değeri yok.

### A-04awr-0005 · 2026-10-30 12:23 · → koordinator · KARAR-GEREK
Paket: fix/04a-worker-ready   Cevap: K-04aWR-0001
Bulgu (kaynaktan): Docling (convert/office.py:31) ve PaddleOCR (convert/ocr.py:38) fonksiyon içinde, ilk dönüşümde yükleniyor; _resolve yalnız pipeline modülünü içe aktarıyor. Yani ready, spawn + içe aktarım süresini dosya saatinden çıkarır ama K-06a-0029'daki "ilk belgenin model yüklemesiyle kesilmesi de düzelir" cümlesi kendiliğinden doğru olmaz.
- **A (Önerilen):** ready yalnız _resolve sonrası (bu PR). Flaky testler ve açılış yarışı çözülür; model yüklemesi ilk belgenin dosya süresinde kalır (ölçüm 66 s, varsayılan 600 s: bugün kesilme riski yok). PR'da bu sınır açık yazılır; ölçülmüş bir kesilme olursa ayrı FOLLOWUP. Etki: dar, touch-zone değişmez, açılış sınırı 60 s yeter.
- **B:** hedef modülde isteğe bağlı warm() kancası; işçi ready'den önce Docling+PaddleOCR'ı yükler. Etki: office.py/ocr.py/pipeline.py touch-zone'a girer, her işçi kullanılmasa da ~2,3 GB modeli yükler, açılış sınırı ≥300 s olmalı, gerçek model testi models işaretli (varsayılan kapıda koşmaz).
- **C:** ready'yi ilk dosya sonucuna kadar ertelemek (ilk belge süresizdir). Etki: asılı ilk belge yalnız açılış sınırıyla durur; dosya sınırının anlamını bulanıklaştırır (ARCH-13). Önermiyorum.
Cevap gelene kadar A'ya göre kırmızı testleri yazıyorum (A ile B'nin ortak kısmı); ürün kodu onaydan sonra.

### A-04awr-0006 · 2026-10-30 12:57 · → koordinator · DURUM
Paket: fix/04a-worker-ready   Cevap: K-04aWR-0002
DURUM: VERIFIED. Kırmızı ölçüldü: eski kodda 3 s açılış + 2 s dosya timeout → `timeout convert_timeout` (çıkarım artık doğrulandı). Kapılar (tools, --no-deps, yığın yok): lint 0; make test llmaas 649/649, airgap 649/649; 7 havuz testi 14 CPU yakıcı altında 10/10. İlk yük döngüsünde yeni testim test_04awr_2 bir kez düştü (ikinci yarıda taze işçiye 2 s açılış sınırı veriyordum); test düzeltildi, ürün kodu değişmedi, sonra 10/10. Model yüklemesi sınırı PR ve docs'ta açık. Ayrıntı state/pr/04a-worker-ready.md, loglar state/pr/04a-worker-ready-kapilar/.

### A-04awr-0007 · 2026-10-30 12:57 · → koordinator · PR-HAZIR
Paket: fix/04a-worker-ready   Cevap: K-04aWR-0001
PR: state/pr/04a-worker-ready.md · Branch fix/04a-worker-ready · baz e9583df · SHA **3cecab486a37e9c68b1827f159f8bec95f05109d** (1 commit, 8 dosya, ağaç temiz) · Sınıf [A] · push yok. İmaj etiketi ffcore/tools:0.0.0-04awr (0.0.0-main'in yeniden etiketi) yerelde duruyor.

### A-04awr-0008 · 2026-10-30 13:00 · → koordinator · PLAN (bekleme işi)
Paket: fix/03a-nonmember-404 (FOLLOWUP-103)   Cevap: K-04aWR-0004
Kaynak (main, core/auth.py): 12 uç da `require_role` → `authorize` → `_grant`'tan geçiyor. `_grant` üye olmayana (satır ~395) ve silinmiş/olmayan projede süper admin olmayana (satır ~383) `insufficient_role` dönüyor, `authorize` bunu 403'e çeviriyor. Tek nokta düzeltmesi 12 ucun hepsini kapsar.
Değişiklik: (1) üye değil → `project_not_found` (404, mevcut `ApiError(404, not_found_error, project_not_found)` yolu); (2) olmayan/silinmiş proje de herkes için 404 (şart: aksi halde "var ama üye değilim 404 / yok 403" farkı varlık sızdırır); (3) üye ama rol yetmez → 403 `insufficient_role`, `read_only_access` aynen; OBO başka proje → 403 `obo_project_scope` aynen (K-03a-0007); kullanıcı olmayan aktör ve tenant uçları aynen 403. (4) Üye olmayan reddi audit'e yine `outcome=denied` yazılır (iç sebep `not_member`; cevap gövdesi olmayan projeyle birebir aynı).
Testler (önce kırmızı): OpenAPI'den `{project_id}` içeren tüm proje uçlarını tarayan parametrik test (üye olmayan → 404, gövde olmayan projeyle aynı; F10'un 12 ucunu kapsar, yeni uç eklenince kendiliğinden); üye + düşük rol → 403; olmayan proje → 404 (süper admin olmayan); audit `not_member`. Beklentisi değişecek mevcut testler: test_03a_access (test_03a_1 adı + 403), test_04a_api, test_04a_review_r1_acl, test_05a_sql, test_08_api (stranger 403 → 404).
Touch-zone önerisi: backend/ffcore/core/auth.py, yukarıdaki 5 entegrasyon test dosyası (yalnız beklenti), yeni tests/integration/test_03a_nonmember_404.py, docs/api.md hata tablosu. Sınıf [A] (KARARLAR 30 Ekim kararı; C2 imzası değişmez). Kapılar: lint, make test iki profil, test-int (yığın gerekir: DB'li erişim testleri).
Koordinatör kararı istenen tek nokta: hata kodu. KARARLAR "404 not_found" diyor; mevcut proje 404'ü `error.type=not_found_error, code=project_not_found`. **A (önerim):** `project_not_found` (olmayan, silinmiş, üye değil tek kod; kehanet yok, 10a önyüzü zaten bu kodu tanıyor mu kontrol edilecek). B: `not_found` (KARARLAR metnine birebir, ama olmayan proje için de değiştirmek gerekir, ikinci kod).

### A-04awr-0009 · 2026-10-30 13:01 · → koordinator · ACK
Paket: fix/03a-nonmember-404 (FOLLOWUP-103)   Cevap: K-04aWR-0005
Alındı: kod A `project_not_found` (404, üye değil ve olmayan proje aynı gövde), rol yetmez 403 aynen, audit'te gerçek neden ayrı alanda. Kod 04a-worker-ready ONAY'ından sonra, main'den (07 dahil) açılacak dalda; o zamana kadar bekliyorum, branch'lere commit yok.

### A-04awr-0010 · 2026-10-30 14:06 · → koordinator · HANDOFF
Paket: fix/04a-worker-ready   Cevap: K-04aWR-0006 / K-04aWR-0007
- Durum: fix/04a-worker-ready r1 ONAY, main 2308bfb (kapı koşuyor). Lease ffcore-isci-a-04awr **RETIRED**. K-04aWR-0007 GOREV'i (fix/03a-nonmember-404) bu oturumda **alınmadı**: kullanıcı kuralı "her paket yeni işçi oturumu" (bu oturum PAKET=fix/04a-worker-ready ile açıldı). Yeni oturum: `ROL=isci-a PAKET=fix/03a-nonmember-404`.
- Tam sonraki adım (yeni oturum): worktree .worktrees/fix/03a-nonmember-404 (a257192). `backend/ffcore/core/auth.py` `_grant`: satır ~383 (`live is None` → süper admin değilse `insufficient_role`) ve ~395 (`member is None` → `insufficient_role`) ikisi de `project_not_found` olur; `authorize` 404 yolu şu an audit yazmıyor, üye-değil reddi için audit (gerçek neden ayrı alan, ör. `not_member`) eklenmeli, gövde olmayan projeyle aynı. OBO başka proje 403 `obo_project_scope`, kullanıcı olmayan aktör ve tenant uçları 403 aynen.
- Kırmızı önce: OpenAPI'den `{project_id}` içeren tüm uçları tarayan parametrik test (üye olmayan → 404, gövde = olmayan proje gövdesi); 12 uç listesi state/pr/18-e2e.md satır 41. Beklentisi değişecek testler: tests/integration/test_03a_access.py (test_03a_1 adı + 403), test_04a_api.py:192, test_04a_review_r1_acl.py:171, test_05a_sql.py:228, test_08_api.py:95; 06a run 404 uyumu test_06a_run_access.py.
- MINOR-1 (R-04AWR-0001): tests/unit/test_04a_convert.py `test_04awr_5` → `Settings(...)` zorunlu alanları (offline, service_token, obo_jwt_secret, secret_key vb.) açık değerlerle; ortamdan bağımsız.
- Not: GOREV "yığın gerekmez" diyor ama değişen testlerin hepsi tests/integration (DB'li); test-int için yığın gerekecek, YIGIN-AÇ sırası iste.
- Değişen dosyalar (bu paket): 3cecab4, 8 dosya (PR state/pr/04a-worker-ready.md). Commit edilmemiş durum yok. Plan ve karar: A-04awr-0008, K-04aWR-0005 (A).
- Yerelde: imaj etiketi ffcore/tools:0.0.0-04awr (0.0.0-main'in kopyası) silinebilir; worktree .worktrees/fix/04a-worker-ready'ye dokunmadım.
