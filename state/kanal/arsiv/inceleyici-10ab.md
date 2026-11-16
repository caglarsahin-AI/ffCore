# Arşiv: inceleyici · 10ab

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-10ab-0001 · 2026-10-28 16:52 · → koordinator · ACK
Paket: 10a-bağlama   Cevap: K-10ab-0007
Tam SHA 7229da702f843c44d320bea519def2f356f46572 yerel commit nesnesi olarak doğrulandı. .worktrees/review-10ab-r1 detached worktree'sinde yalnız bu SHA incelenecek; baz591aac3. Oturum/çerez, C6 rewrite, seçili proje yetkisi, hata eşlemesi, C13/FOLLOWUP-44, generated API ve gerçek stack Playwright odakta; güvenlik turu ayrı raporda.
Koordinatör kabulleri (msw yok, liste ekranları, FOLLOWUP-66/67, Lighthouse/profil/backend test sınırları) korunacak. Kendi proje adı ve geçici fixture kullanılır; eski kullanıcı node_modules volume'ları silinmez. Komut izin sistemi eskalasyonları gerekebilir; soru penceresi yok.

### R-10ab-0002 · 2026-10-28 17:39 · → koordinator · REVIEW-SONUC
Paket: 10a-bağlama   Cevap: K-10ab-0007
İncelenen tam SHA: 7229da702f843c44d320bea519def2f356f46572. Karar: DUZELT; merge-ready değil. Rapor: state/reviews/10a-binding-r1.md. BLOCKER 0, MAJOR 1, MINOR 1.
MAJOR-1: MemberForm users sorgusu ve ProjectSwitcher projects sorgusu hata/pending durumunu işlemiyor; data??[] başarısızlığı boş seçeneklere dönüştürüyor (ARCH-06). Gerçek oturumlu Chromium'da yalnız bu sorgulara 503 enjeksiyonu: users yalnız Choose a user, projects yalnız placeholder, hata kodu/ayrıntısı yok. Hata/gerçek boş liste ayrımı ve negatif test gerekli.
MINOR-1: ListState query 401 yanıtını mesaj yapıyor, /login'e yönlendirmiyor; mutasyon yolu yönlendiriyor. Probe providers401 sonrası /providers kaldı; auth/me tam sayfa 401 yolu doğru, yetki aşımı değil.
Bağımsız Node20 lint/tip/check:api passed; 11 dosya47unit passed (7,30sn); kendi temiz gerçek backend stack'inde Playwright48 passed (1,8dk), 14axe ve iki tema PNG dahil. Gerçek browser cookie HttpOnly/Secure/Strict; JS görmüyor. Bilinmeyen ana liste hatası Details'ta kod+metin gösteriyor. FOLLOWUP-44 tamam. state/ baz diff'i boş; diff --check passed.
Koordinatör kabulleri ve NOT_RUN'lar korunuyor; ayrı güvenlik turu raporda. Sapma8 önce-kırmızı kanıtı yok, geçmişe dönük geçti sayılmadı; sapma9 ara commit'lere onay yok, final SHA kapıları bağımsız geçti.
Tam HEAD sabit, ağaç temiz; worktree remove exit0, --force yok. Kendi stack down-v, probe ve geçici volume'lar temiz; kullanıcı ffcore-10a-nm/pw korunuyor. Kod edit/commit/push ve dış sistem erişimi yok. Yeni SHA ile REVIEW-ISTEK bekleniyor.
Kullanıcı kanal takibini Windows zamanlayıcısıyla kalıcılaştırmayı araştırmamı istedi; yetki denemesinde tetikleyicisiz geçici görev oluşturulup kaldırıldı. Asıl 10dk görevi henüz kurulmadı; kuruldu diye raporlanmıyor.

### R-10ab-0003 · 2026-10-28 18:50 · → koordinator · ACK
Paket: 10a-bağlama   Cevap: K-10ab-0010
Tam SHA 628d4164ba6c7b593e3e0f58167a92b0f68a2482 yerel commit nesnesi olarak doğrulandı; r2 delta isteği alındı. Şu an08-lite kapanışı; ardından .worktrees/review-10ab-r2 detached worktree'de yalnız bu SHA, r1 probe'ları + QueryError üç durum + 401/safeNext incelenecek. Sonra01. FFCORE_VERSION=0.0.0-review-10ab; r1 temiz alanlar yeniden açılmaz.

### R-10ab-0004 · 2026-10-28 18:58 · → koordinator · REVIEW-SONUC
Paket: 10a-bağlama   Cevap: K-10ab-0010
İncelenen tam SHA: 628d4164ba6c7b593e3e0f58167a92b0f68a2482. Karar: DUZELT; merge-ready değil. Rapor: state/reviews/10a-binding-r2.md. BLOCKER0, MAJOR1, MINOR0; r1 iki bulgu kapandı.
Yeni MAJOR-1: safeNext TAB/LF/CR'ı reddetmiyor. '/'+TAB+'/backend:8000/healthz' kabul ediliyor; URL ayrıştırıcı kontrol karakterini kaldırıp başka origin yapıyor. Gerçek Chromium'da /login?next=%2F%09%2Fbackend%3A8000%2Fhealthz + sahte hesapla giriş sonrası origin http://backend:8000, yol/healthz oldu (konsol localhost:3000). Yalnız kendi localbackend hedeflendi, dış istekler engellendi; credential sızıntısı iddia edilmedi.
Ham kontroller reddedilmeli ve parse sonrası origin kontrol edilmeli; TAB/LF/CR ve kodlama varyantları negatifleri + gerçek login testi gerekli. Mevcut altı unsafe değer testi atlıyor.
R1 aynı users/projects503 probe'ları artık kod görünür/seçici0; gerçek backend token iptali401 → /login?next= → yeniden girişte aynı sayfa passed. Bağımsız Node20 lint/tip/check:api, Vitest55 (13dosya,8,48sn), gerçek stack Playwright51 (1,2dk,axe/iki tema dahil) passed. state/ baz diff'i boş; diff --check passed. Ayrı güvenlik turu/NOT_RUN'lar raporda.
HEAD sabit, ağaç temiz; kendi stack down-v, probe/volume'lar temiz, worktree remove exit0 --force yok. Kullanıcı node_modules volume'ları korundu. ffcore/backend:0.0.0-review-10ab etiketi kapanış temizliği sizde; yeni build/dangling yok. Kod edit/commit/push ve dış sistem erişimi yok.
Şimdi01 r1 başlıyor (.worktrees/review-01-r1, önceden ACK R-01-0001).

### R-10ab-0005 · 2026-10-28 19:14 · → koordinator · ACK
Paket: 10a-bağlama   Cevap: K-10ab-0014
Tam SHA e9fe396678f84fe2b074a1babdefa8b2cf4de240 yerel commit nesnesi olarak doğrulandı. 01 r1 bitti (R-01-0003); şimdi .worktrees/review-10ab-r3 detached worktree'de yalnız bu SHA incelenecek. R2 açık yönlendirme probe'u tekrar, raw/kodlu kontrol karakterleri ve normalize yol sınırı; sabit referans origin kabulü korunacak. R1/r2 temiz alanları yeniden açılmayacak. FFCORE_VERSION=0.0.0-review-10ab, kendi geçici stack/fixture'lar.

### R-10ab-0006 · 2026-10-28 19:19 · → koordinator · REVIEW-SONUC
Paket: 10a-bağlama   Cevap: K-10ab-0014
İncelenen tam SHA: e9fe396678f84fe2b074a1babdefa8b2cf4de240. Karar: ONAY / merge-ready, yalnız bu SHA. Rapor: state/reviews/10a-binding-r3.md. BLOCKER0, MAJOR0, MINOR0; r2 açık yönlendirme kapandı.
Raw/kodlu C0/DEL/ters bölü reddi, parse sonrası origin, yalnız path/query/hash ve normalize//reddi kaynakta doğrulandı. Bağımsız70negatif+3normalpozitif passed; r2 TAB girdisi artık '/'. R2 tam saldırı URL'si gerçek girişte konsol origin'inde kaldı. Sabit referans kabulü korundu.
Bağımsız Node20 lint/tip/check:api passed; Vitest76/13dosya (10,03sn); hedefli gerçek backend Playwright9 passed (50,9sn): login/session/query503, token iptali401+next+tekrar giriş ve açık yönlendirme. R3 full52 bağımsız tekrar NOT_RUN; delta için9hedefli koşu, r2 full51 geçmiş kanıt. Ayrı güvenlik turu ve sınırlar raporda; state/ baz diff'i boş, diff --check passed.
HEAD sabit, ağaç temiz; kendi stack down-v, geçici volume'lar ve worktree temizlendi, remove exit0 --force yok. Kullanıcı önbellekleri korundu. ffcore/backend:0.0.0-review-10ab artık temizlenebilir. Kod edit/commit/push ve dış sistem erişimi yok.
Şimdi08-lite r2 (ACK R-08lite-0004) başlıyor; aynı mesaj ID'leri tekrar uygulanmadı.
