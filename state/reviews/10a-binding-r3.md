# 10a-bağlama · r3 · Bağımsız delta incelemesi

- İstek `K-10ab-0014`; ACK `R-10ab-0005`.
- İncelenen tam SHA: `e9fe396678f84fe2b074a1babdefa8b2cf4de240`.
- R2 `628d4164ba6c7b593e3e0f58167a92b0f68a2482`; baz `591aac3`.
- **ONAY / merge-ready, yalnız bu SHA. BLOCKER0, MAJOR0, MINOR0.** R2 açık yönlendirme bulgusu kapandı.
- İnceleyici `ffcore-inceleyici-20261028-0203`, 28 Ekim2026.

## Kapanış

`safeNext` ham/kodlu C0, DEL ve ters bölüyü reddediyor. Ardından URL ayrıştırması, referansla origin eşitliği ve normalleşen pathname'in `//` ile başlamaması denetleniyor; ham giriş yerine yalnız pathname+search+hash dönüyor. Nokta segmentiyle `/..//x` üretme yolu da kapalı.

Sunucuda da kullanılan sabit `http://console.invalid` referansı K-10ab-0014 kabulüyle uyumlu. Referans adresine ağ isteği yok; yalnız URL ayrıştırma tabanı. Normal göreli yol/query/hash korunuyor. Testte mutlak adres taramasına eklenen istisna bu ayrılmış referans için; gerçek backend adresi istemciye eklenmedi.

Bağımsız Node probe: tüm33 C0/DEL için raw ve yüzde kodlu66 örnek +4 nokta/backslash normalizasyonu, toplam **70 ret**; üç normal yol/query/hash same-origin pozitif. R2'nin tam TAB girdisi artık **`/`** dönüyor.

Gerçek Chromium'da R2'nin `/login?next=%2F%09%2Fbackend%3A8000%2Fhealthz` adresi ve gerçek sahte-hesap girişi tekrarlandı; son origin **konsolda kaldı**. Mevcut test bu URL'yi aynen kullanıyor ve giriş sonrasında origin denetliyor. Geçerli next ile401 sonrası tekrar giriş, users/projects503 hata görünürlüğü ve logout sonrası eski token reddi de aynı hedefli koşuda geçti.

## Bağımsız doğrulama

Exact SHA readonly kaynağı kendi Docker volume'una kopyalandı; kaynak worktree'ye build/test çıktısı yazılmadı. Kullanıcı node_modules önbellekleri readonly, değiştirilmedi. Backend r2 ile aynı kaynak/imaj; yeni backend farkı yok. Kendi proje `review-10ab-r3`, `FFCORE_VERSION=0.0.0-review-10ab`, host backend18023; sahte `.env.test`, pinli Playwright1.64.1 digest. Yeni build/indirme yok.

| Kontrol | Sonuç |
|---|---|
| Node20.19.5 lint + tsc noEmit/incremental false | **passed** |
| Vitest tüm unit/sözleşme | **76 passed /13dosya**, 10,03sn |
| check:api | **passed** |
| Bağımsız safeNext invariant probe | **70 ret +3 normal same-origin pozitif** |
| Gerçek backend hedefli Playwright: login, session_boundary, query_failures | **9 passed**, 50,9sn; gerçek build/start dahil |
| R2 tam saldırı URL'si | **passed**, konsol origin'i korundu |
| Baz `state/` diff /delta diff --check | **boş /passed** |

R1/r2 temiz alanlar yeniden açılmadı. İşçinin full52 E2E koşusu PR'da; r3'te bağımsız tekrar **NOT_RUN**, yerine değişen login/session yolu için9 hedefli test çalıştı. Backend tam kapıları, iki profil, Lighthouse ve kurum/satıcı bağlantıları **NOT_RUN** (delta dışı). R2'nin full51 koşusu bu raporda full52 gibi sunulmadı.

## Güvenlik turu

- **Kimlik:** next artık URL normalizasyonu sonrası güvenli göreli hedef;401 tekrar giriş ve revocation geçti. Yeni çerez/credential yolu yok.
- **ACL:** mevcut backend yetkileri değişmedi; r2 temiz alan. Query/session testleri tekrarlandı.
- **Secret:** URL/probe/test çıktısına token yazılmadı, yalnız dummy hesap; gerçek `.env` okunmadı.
- **SQL:** backend/ORM delta yok; yalnız kendi geçici e2e fixture'ları.
- **Egress:** açık yönlendirme kapandı; referans origin sadece parse için, ağ yok. C6 rewrite değişmedi.
- **PII/log:** example.org fixture'ları; yeni loglama/ham içerik yolu eklenmedi.

## Temizlik

Kendi stack down-v ile temizlendi; iki geçici volume kaldırıldı. Exact HEADe9fe396678f84fe2b074a1babdefa8b2cf4de240 ve boş git status doğrulandı; worktree remove exit0, --force yok. Kullanıcı önbellekleri ve diğer stack'ler korundu. Main checkout/switch, kaynak edit/commit/push ve dış sistem bağlantısı yok. ffcore/backend:0.0.0-review-10ab etiketi tekrar koordinatörce temizlenebilir.
