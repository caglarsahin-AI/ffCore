# 10a-bağlama · r2 · Bağımsız delta incelemesi

- İstek `K-10ab-0010`; ACK `R-10ab-0003`.
- İncelenen tam SHA: `628d4164ba6c7b593e3e0f58167a92b0f68a2482`.
- R1 `7229da702f843c44d320bea519def2f356f46572`; PR bazı `591aac3`.
- İnceleyici `ffcore-inceleyici-20261028-0203`; 28 Ekim 2026.
- **DUZELT / merge-ready değil. BLOCKER0, MAJOR1, MINOR0.** R1'in iki bulgusu kapandı; yeni yönlendirme kodunda güvenlik bulgusu var.

## MAJOR-1 — safeNext kontrol karakterleriyle açık yönlendirmeye izin veriyor

`frontend/lib/login-redirect.ts:9-11` yalnız `/` başlangıcı, `//` ve ters bölüyü denetliyor. URL ayrıştırıcısı TAB/LF/CR karakterlerini kaldırdığından `/` + TAB + `/host/path` bu kontrolden geçip `//host/path` gibi başka origin'e dönüşüyor. Yeni `LoginPage`/`LoginForm` bu değeri yönlendirmede kullanıyor.

Exact SHA'daki gerçek `safeNext` TypeScript'i Node'da transpile edilerek sınandı: `"/\t/backend:8000/healthz"`, LF ve CR karşılıkları aynen kabul edildi; `new URL(accepted, 'http://localhost:3000').origin` **aynı origin değil**.

Gerçek Chromium + gerçek backend kanıtı: oturumsuz kullanıcı `/login?next=%2F%09%2Fbackend%3A8000%2Fhealthz` adresine gider, sahte e2e hesabıyla giriş yapar; giriş sonrası origin **`http://backend:8000`**, yol **`/healthz`** oldu. Konsol origin'i `http://localhost:3000` idi. Probe tarayıcısında localhost/backend dışındaki istekler engellendi; dış sisteme gidilmedi. Aynı adres yapısında host saldırganın adresi olabilir; bunun için gerçek dış bağlantı denenmedi. Credential sızıntısı kanıtlanmadı; doğrulanan kusur güvenilen giriş ekranından origin dışına yönlendirme.

İstenen düzeltme: ham kontrol karakterlerini reddetmek ve gerçek URL ayrıştırması sonrası origin/path koşulunu doğrulamak. TAB/LF/CR, backslash, absolute/protocol-relative ve yüzde kodlama varyantları için negatif testler; aynı-origin normal yol/query pozitifleri. En az bir gerçek login tarayıcı testi kontrol karakterli `next`'in origin dışına çıkmadığını kanıtlamalı. Mevcut altı güvensiz değer testi bu varyantları içermiyor.

## R1 bulgularının kapanışı

**R1 MAJOR-1 kapandı.** Ortak `QueryError` ana listeler ve yardımcı sorgularda kullanılıyor. User/project pending, hata ve gerçek boş durumları ayrılmış; members yüklenmeden aday formu açılmıyor. Normal üyelerde gereksiz projects sorgusu devre dışı. R1 ile aynı 503 kodları ve gerçek oturumla tekrar: `review_users_unavailable` ve `review_projects_unavailable` Details'ta görünür; ilgili seçici sayısı her ikisinde **0**. Yeni unit negatif/pozitifleri ve iki gerçek-backend E2E enjeksiyon testi geçti.

**R1 MINOR-1 kapandı.** QueryCache/MutationCache ve mutasyon hata gösterimi ortak 401 yolunu kullanıyor; yanlış parola `invalid_credentials` istisnası korunuyor. Gerçek backend'de token başka istemciden iptal edilip açık sekmede refetch yapıldığında `/login?next=%2Fprojects`, yeniden giriş ardından `/projects` testi bağımsız geçti. Ancak dönüş hedefinin güvenlik kontrolü yukarıdaki yeni MAJOR'dır; eski query401 sorunu yeniden açık sayılmadı.

## Bağımsız doğrulama

Yalnız r1 → r2 deltası incelendi; r1 temiz tasarım alanları yeniden açılmadı. Kaynak exact SHA'dan salt okunur bağlanıp frontend/backend/docs kendi Docker volume'larına kopyalandı; build/PNG/test çıktısı bu kopyada kaldı. Kullanıcının iki bağımlılık önbelleği salt okunur kullanıldı, değiştirilmedi/silinmedi.

Backend imajı `sha256:c96aa420d9ee73b1576a29ec7c93e162b9a184613f89cca3ef90a3c7d4e09c66`: 40 Python dosyası exact kaynakla aynı. `ffcore/backend:0.0.0-review-10ab` etiketi, kendi compose projesi `review-10ab-r2`, host backend18020, sahte `.env.test`/e2e hesabı; dış indirme yok. Playwright imajı digest `47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea` (1.64.1).

| Kontrol | Sonuç |
|---|---|
| Node20.19.5 lint + tsc noEmit/incremental false | **passed** |
| Vitest | **55 passed /13 dosya**, 8,48 sn |
| check:api | **passed** |
| Temiz backend stack + migrate/seed + sahte yönetici CLI | **passed** |
| Gerçek backend Playwright | **51 passed**, 1,2 dk; iki tema, axe ve gerçek 401 tekrar giriş dahil |
| R1 users/projects503 probe'ları | **passed**, hata kodları görünür/seçiciler yok |
| Kontrol karakterli safeNext ve gerçek login probe | **FAILED**, origin dışına yönlendirme doğrulandı |
| `git diff --check 7229da7 HEAD` / baz `state/` diff'i | **passed /boş** |

İşçinin 401 e2e ilk-kırmızı testindeki yanlış document olayı ve yardımcı giriş fonksiyonu düzeltmeleri PR'da açık; bağımsız final gerçek401 senaryosu geçti. Geçersiz ilk kırmızı ürün kanıtı sayılmadı.

## Güvenlik turu

- **Kimlik:** gerçek oturum iptali/yeniden giriş ve yanlış parola ayrımı geçti; next hedefi **MAJOR-1**. R1 server session/çerez sınırında delta yok.
- **ACL:** kullanıcı/project seçicileri hata durumunda veri göstermiyor; backend guard'larında delta yok. Read-only ve rol E2E tekrar geçti.
- **Secret:** credential/token loglama eklenmedi; probe gerçek token yazdırmadı, yalnız sahte hesap kullanıldı. Açık yönlendirmede credential sızdığı iddia edilmedi.
- **SQL:** backend/DB kodu değişmedi; gerçek test fixture'ları kendi review DB'sinde.
- **Egress:** C6 rewrite değişmedi; yeni navigasyon hedefi doğrulaması bozuk. Probe yalnız localhost ve kendi backend host'una izin verdi, dış bağlantı yok.
- **PII/log:** sadece example.org fixture'ları ve sentetik hata kodları; yeni QueryError kod/metni gösteriyor, gizli alan eklenmedi. Genel backend log güvenliği yeniden varsayılmadı.

**NOT_RUN:** backend tam testleri (delta yok, koordinatör sınırı), iki profil E2E, Lighthouse, gerçek kurum/satıcılar, arg'sız Docker build tekrarı. R1 FOLLOWUP-66/67 ve onaylı kapsam sınırları korundu.

## Temizlik

Kendi probe konteyneri durdurulup kaldırıldı; stack down-v, iki geçici kaynak/deps volume'u silindi. Exact HEAD628d4164ba6c7b593e3e0f58167a92b0f68a2482 ve boş git status doğrulandı; worktree remove exit0, --force yok. Kullanıcı node_modules volume'ları korundu. Kaynak edit/commit/push ve main checkout/switch yok. Review backend etiketi ffcore/backend:0.0.0-review-10ab kapanışta koordinatöre bildiriliyor.
