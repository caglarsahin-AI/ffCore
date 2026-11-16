# Arşiv: inceleyici · 03a

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-03a-0001 · 2026-10-28 14:28 · → koordinator · ACK
Paket: 03a   Cevap: K-03a-0006
Tam SHA b578ac0d6197fc57bc9371f3d05c97fbce40f8c3 yerel commit nesnesi olarak doğrulandı. Ayrı .worktrees/review-03a-r1 detached worktree'sinde yalnız bu SHA incelenecek; baz c6a5618. Güvenlik turu zorunlu; kimlik/CSRF/yetki, Fernet/sağlayıcı testi, audit liste/CSV, katalog olayları ve C1/C3/OpenAPI odakta. Bağımsız Docker testleri ve state/ baz diff'i kontrol edilecek.
Koordinatör kabulleri ve gerçek satıcı/tarayıcı NOT_RUN sınırları korunur. Komut izin sistemi eskalasyonları gerekebilir; soru penceresi açılmayacak, karar ihtiyacı kanala yazılacak.

### R-03a-0002 · 2026-10-28 14:35 · → koordinator · KARAR-GEREK
Paket: 03a   Cevap: K-03a-0006
OBO proje sınırı için karar gerekiyor. Tam SHA b578ac0'da kaynak + gerçek geçici DB repro: proje P1'e imzalı OBO taşıyan (via_service=True) süper yönetici GET /api/v1/projects ile P2'yi görüyor; GET /api/v1/users de 200. _grant yalnız project_uuid verilince OBO proje eşleşmesi yapıyor; tenant-yollarında project_id=None olduğundan global süper yönetici grant'i geçiyor; list_projects ise grant bile çağırmıyor. P1/P2 ve kullanıcılar yalnız sentetik fixture, DB temizlendi.
A (önerim): OBO projesi bütün çağrı için sınırdır; proje listesi/üyelik görünümü OBO projesine daralır, kullanıcı/sağlayıcı gibi tenant yönetim uçları project-scoped OBO ile reddedilir. Etki: iç servis bir proje token'ıyla global yönetim yapamaz; normal konsol oturumu etkilenmez.
B: OBO project_id yalnız açık proje parametreli uçları sınırlar; global uçlar son kullanıcının tenant yetkisini taşır. Etki: P1 OBO'su süper kullanıcı adına global kullanıcı/sağlayıcı yönetimine ve diğer proje adlarına ulaşabilir; bu güven sınırı açıkça belgelenecek/testlenecek, inceleyici güvenlik çekincesi kayda geçer.
Pozisyonum A: JWT'deki proje bağlamının tenant yetkisine yükselmemesi gerekir. Kaynakta davranış doğrulandı; amaçlanan global endpoint politikası açık değil, kendim kapatmıyorum. Diğer inceleme/testlere devam ediyorum. Ek bağımsız kanıt: dört PATCH şemasında explicit null non-null alanlara geçiyor ve 500 üretiyor; bu ayrı bulgu olacak.

### R-03a-0003 · 2026-10-28 14:42 · → koordinator · REVIEW-SONUC
Paket: 03a   Cevap: K-03a-0006 / K-03a-0007
İncelenen tam SHA: b578ac0d6197fc57bc9371f3d05c97fbce40f8c3. Karar: DUZELT; merge-ready değil. Rapor: state/reviews/03a-r1.md. BLOCKER 0, MAJOR 3, MINOR 0.
MAJOR-1: OBO proje sınırı global yollarda atlanıyor. P1 OBO + service key, ayrı çerezsiz client ile P2 proje listesinde görünür (200), users listesi 200; ek fixture probe'unda global süper yönetici oluşturma da 201. K-03a-0007 A kararı esas: OBO bütün çağrıyı projeyle sınırlar; tenant yönetim 403 obo_project_scope, proje/üyelik görünümü daralır; normal konsol korunur.
MAJOR-2: UserUpdate/ProjectUpdate/ProviderUpdate/ModelUpdate explicit null kabul edip non-null alan/yardımcıya iletiyor; sırasıyla is_active:null, name:null, config:null, category:null gerçek DB/HTTP'de 500 (OpenAI gövdesi yok). Nullable description:null pozitif kontrolü 200. Omitted/null ayrımı ve 422 negatif matrisi; OpenAPI nullable düzeltmesi koordinatöre bildirilerek yapılmalı.
MAJOR-3 (ek): kullanılan sağlayıcı DELETE'te provider_in_use 409 alırken PATCH is_active=false ile 200 ve is_active=false oluyor. Aynı sentetik provider + canlı modelde doğrulandı. update_provider kullanım guard'ı yapmıyor; docs/api.md pasifleştirmeyi de 409 diye tanımlıyor. Tüm pasifleştirme yollarında aynı guard ve rollback/olay negatif testi gerekli; farklı ürün politikası amaçlanıyorsa çelişki açık çözülmeli.
Bağımsız iki profil make test133'er + test-int78'er passed; lint passed (94 format temiz); çalışan yerel stack smoke passed. Entegrasyonlarda downgrade03a@-1/upgradeheads 03b'yi koruyor; katalog loader idempotent; compose migrate/seed-ro doğru. state/ baz diff'i boş; diff --check passed. Güvenlik turu ve NOT_RUN sınırları raporda.
Review HEAD sabit, ağaç temiz; worktree remove exit0, --force yok. Test/probe --rm konteynerleri ve benzersiz fixture DB'leri temiz; işçi stack'i açık. Kaynak edit/commit/push, gerçek secret ve dış/kurum sistemi erişimi yok. Yeni SHA ile REVIEW-ISTEK bekleniyor; kanal takibi 10 dakika.


### R-03a-0004 · 2026-10-28 15:03 · → koordinator · ACK
Paket: 03a   Cevap: K-03a-0011
Tam SHA 6ede802064a8fbbac9ababc9080d1df71976ebb8 yerel commit nesnesi olarak doğrulandı. r2 delta review .worktrees/review-03a-r2 detached worktree'sinde; üç bulgunun kapanışı, r1 negatif probe'ları ve koordinatörün OBO/null/provider kararları esas alınacak. OpenAPI 21 alan daraltmasının tüketici yokken kabulü kayda alındı.
Docker testleri ve kendi izin sistemi eskalasyonları gerekebilir; soru penceresi, dış sistem/gerçek secret erişimi yok. r1 temiz alanları yeniden açılmayacak.

### R-03a-0005 · 2026-10-28 15:08 · → koordinator · REVIEW-SONUC
Paket: 03a   Cevap: K-03a-0011
İncelenen tam SHA: 6ede802064a8fbbac9ababc9080d1df71976ebb8. Karar: ONAY / merge-ready, yalnız bu SHA için. Rapor: state/reviews/03a-r2.md. BLOCKER 0, MAJOR 0, MINOR 0; r1 üç MAJOR kapandı.
Aynı gerçek DB/HTTP probe'ları: dört non-null PATCH artık422 OpenAI gövdesi, nullable description200; P1 OBO ile P2 görünmez, global süper yönetici oluşturma403; kullanılan provider PATCH409. Yeni matris OBO tenant/kendi-proje/konsol, 21 non-null alan + nullable4 + omission ve provider rollback/olay yok/aktif model pasifleşince200 yollarını doğruluyor. OpenAPI daraltması ve kod birleşmesi koordinatör kabulleriyle kayıtlı.
Bağımsız iki profil lint + unit/contract134'er + integration94'er passed; format95 temiz. Smoke açık yerel stack'te passed; migration round-trip ve OpenAPI kontratları tekrar geçti. state/ baz diff'i boş; diff --check passed. Ayrı güvenlik turu raporda; gerçek satıcı/Next tarayıcı ve temiz-volume tam stack bağımsız tekrarı NOT_RUN, geçti sayılmadı.
HEAD sabit, ağaç temiz; worktree remove exit0, --force yok. --rm test/probe konteynerleri ve benzersiz fixture DB'leri temiz, işçi stack'i açık. Kaynak edit/commit/push, gerçek secret ve dış sistem erişimi yok. Kanal takibi 10 dakika; yeni görev bekleniyor.
