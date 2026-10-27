# 10. Yönetim önyüzü (Türkçe) [FFCore Console]

**Bağımlılık:** 03a ile iskelet; 04-09 ile ekranlar. **Süre:** 14 gün (inceleme v4-v6; ~25 ekran × iki tema). **Üç PR (A6, M4):** **10a** giriş, proje, üyeler, tema, sağlayıcı ve model ekranları (dalga 2, 03a merge sonrası, 3 gün; PoC); **10b-poc** bilgi tabanı, araçlar, agent sihirbazı, test paneli, run ve onay görünümü, sistem durumu (dalga 5, 6 gün; PoC); **10c** PoC sonrası (5 gün): dashboard'lar, MCP sunucu ve izleme, API anahtarları, limitler, uyarılar, retention, kullanım, kaynak/kanal/hafıza menüleri, salt-okunur modun ekran tarafı ve iki modda ekran görüntüleri.

## Amaç

Bilgi işlem ve iş analistinin, kod yazmadan: proje ve kullanıcı yönetmesi, belge yüklemesi, araç kaydetmesi, agent kurup test edip yayınlaması, onay vermesi, sınav koşturması, kullanım ve audit görmesi. Hedef kullanıcı Python bilmeyen analist; her ekranda kısa Türkçe açıklama.

## Kapsam

### Dalga 3: iskelet (03 ile)

- Next.js App Router, next-intl (`tr` tek dil, anahtarlar İngilizce), shadcn/ui, TanStack Query, zod form doğrulama, SSE istemcisi yardımcıları.
- **Tema altyapısı (açık ve koyu):** `next-themes` ile `class` stratejisi; `frontend/styles/tokens.css` içinde iki tema için CSS değişkenleri (arka plan, yüzey, metin, vurgu, sınır, durum renkleri: başarı/uyarı/hata, grafik paleti 8 renk); shadcn/ui bileşenleri bu token'lara bağlı; üst çubukta tema anahtarı (sistem / açık / koyu), seçim `localStorage`'da; ilk yüklemede yanıp sönmeyi önleyen inline script. Kod ve markdown blokları, SSE araç kartları, grafikler (Recharts) ve Langfuse bağlantıları iki temada okunabilir kontrastta (WCAG AA, 4.5:1). Storybook ya da basit bir `/dev/theme` sayfası ile tüm bileşenler iki temada yan yana görülür.
- Düzen (P9 ile güncellendi): sol menü gruplu: **Genel Bakış**; **Yapı**: Sağlayıcılar, Modeller, Bilgi Tabanları, Veri Kaynakları, Araçlar, MCP Sunucuları, Agent'lar; **İşletme**: Koşular, Onaylar, Sınavlar, Guardrail, Kanallar, Kullanım, Sistem Durumu; **Yönetim**: Projeler, Kullanıcılar, API Anahtarları, Kotalar, Audit, Veri Saklama, Ayarlar; kullanıcı menüsünde Hafızam ve tema. Üstte proje seçici. Rol dışı gruplar görünmez.
- Ekranlar: Giriş; Projeler (liste, oluştur, üyeler ve roller); API Anahtarları (oluştur, bir kez göster, iptal); Kotalar; Kullanım (günlük token ve maliyet grafiği, proje bazlı); Audit (filtre, CSV); Ayarlar > Veri Saklama (sınıf, süre, dry-run sonucu).
- Giriş ekranı (e-posta/şifre), oturum süresi ve çıkış; kullanıcı menüsünde rol ve erişim modu görünür.
- Rol bazlı görünürlük (hangi ekranlar; R10.5): `user` (17'de aktif) yalnızca `/chat` ve Hafızam; analyst agent, bilgi tabanı, sınav, onay, koşular; developer ek olarak araç, MCP sunucu, veri kaynakları, kanallar, kota, guardrail; admin ek olarak sağlayıcılar, modeller, proje, kullanıcı, API anahtarı, uyarılar, sistem durumu, audit, veri saklama, ayarlar.
- Erişim modu (salt-okunur): `access=read` kullanıcı rolünün tüm ekranlarını aynen görür; veri, filtre, grafik, detay sayfaları birebir aynı. Fark yalnızca şu: tüm oluştur/kaydet/sil/yayınla/onayla/çalıştır düğmeleri pasif ve üzerine gelince "Salt-okunur erişim" açıklaması; formlar görüntüleme modunda (alanlar okunur, düzenlenemez); üst çubukta "Salt-okunur" rozeti. Ayrı bir "viewer" ekran seti yoktur; aynı bileşenler `readOnly` özelliğiyle çalışır. Tek bir `useAccess()` kancası ve `<WriteGate>` sarmalayıcısı; her mutasyon düğmesi bu sarmalayıcıdan geçer, elle `if` yazılmaz.
- İstisnalar (salt-okunur modda da yapılabilir): şifre ve tema tercihi, kendi hafızasını yönetme, sohbet.

### Dalga 5: ürün ekranları

- **Sağlayıcılar (03a):** tam CRUD; sürücü seçimi, alanlar (Model/Embedding/Vector/File), kimlik bilgileri (şifreli, maskeli), "Test connection", proje atama (zorunlu adım). (P1/P6/P9)
- **Modeller (03a, 01):** tam CRUD; kategori, sağlayıcıdaki model id, yetenekler, fiyat ("Fill from catalog"), limitler, reasoning varsayılanı, upstream API, istek politikası; kayıt sonrası 01'deki uzlaştırıcı tetiklenir (LiteLLM DB model API'si, C1); sağlık durumu, son 24 saat çağrı ve hata. Config dosya tabanlı değildir. (P1/P9)
- **Bilgi Tabanları (04):** liste, oluştur (ad, parçalama ayarı), belge yükle (sürükle-bırak, ilerleme), belge listesi ve durum (katman: raw/silver/gold; kapı durumları ve gerekçeleri belge satırında; `duplicate_of` bağlantısı; dönüştürücü ve süre), ACL düzenleme, "Aramayı dene" paneli (sorgu yaz, parçaları embedding ve rerank skoruyla gör, rerank tabanı altında elenenler ayrı). **Ingest Raporu** sekmesi (PayCore düzeltmesi D1): kaynak × kapı × gerekçe sayımı, elenen belge ve parça listesi gerekçesiyle, toplamlar belge sayısına eşit; "yeniden dönüştür" (preset seçimiyle, D2) ve "katmanı yeniden üret" (silver/gold, D3) düğmeleri `edit` modunda.
- **Araçlar (05):** MCP/OpenAPI kaydı, kimlik türü seçimi (yok, bearer, özel başlık, basic, kullanıcıyı ilet), bağlantı testi ve ön kontrol listesi, "Keşfet" ile aksiyonlar, aksiyon bazlı `onay gerekli` ve `açık` anahtarları, "Dene" formu.
- **MCP Sunucuları (05 A3):** OpenAPI spec'ini yapıştır/yükle/URL'den al, açılacak operation'ları seç, araç adı ve açıklamasını düzenle, upstream kimlik, erişim modu, guardrail modu (kapalı/izle/zorla); "Araç olarak ekle" düğmesi. **MCP İzleme** sekmesi: sunucu başına sağlık, 24 saat istek/hata/gecikme, son çağrılar, audit izi.
- **Agent'lar (06):** liste (durum, sürüm, model). **Agent sihirbazı**, sekmeli form:
  1. Kimlik: ad, açıklama, model.
  2. Talimat: sistem prompt'u (Langfuse prompt seçimi ya da serbest metin), değişkenler tablosu.
  3. Bilgi: KB seç, mod (her zaman ara / araç olarak), top_k, eşik, "bilmiyorum" cevabı.
  4. Araçlar: kayıtlı araçlardan aksiyon seç, onay gerektirenleri işaretle.
  5. Güvenlik, bağlam ve limitler: guardrail politikası seç (08), soru sorabilir anahtarı, limitler (süre, tur, araç çağrısı), bağlam politikası (R10.5, P8: geçmiş tur sayısı ve özet, RAG token payı, hafıza payı, çıktı rezervi; seed varsayılanları profile göre).
  5b. Hafıza (14): açık/kapalı, izin verilen türler, madde sınırı, süre, çıkarma modeli.
  5c. Kanallar (15): widget gömme kodu, Slack/Teams/Mattermost bağlama, oda eşlemesi.
  6. Çıktı: serbest metin / JSON şeması.
  7. Test: sağ panelde sohbet; token akışı, araç kartları, kaynak kartları, onay istemi; "Sınava ekle" düğmesi (09).
  8. Yayın: sürüm notu, son sınav sonucu, Yayınla / Geri al.
  Şablonlar: 13'teki hazır tanımlar ("Sözleşme Asistanı", "Veri Soru-Cevap") sihirbazı önceden doldurur.
- **Kanallar (15):** kanal ekle (tür, kimlik bilgileri, bağlantı testi), agent eşleme, kimlik eşleme listesi, son 24 saat mesaj/hata; agent sihirbazında "Kanallar" sekmesi. (Ekranlar 15 paketinde yazılır; touch-zone `frontend/app/(console)/channels/` 15'indir, 10 yalnızca menü ve rota yerini ayırır; N23.)
- **Veri Kaynakları (16; ekranlar 16 paketinde, touch-zone `frontend/app/(console)/sources/` 16'nındır, N23):** kaynak ekle (tür, bağlantı, filtre, zamanlama, ACL eşleme), "Şimdi senkronla" (katman ve mod seçimiyle: raw/silver/gold, full/delta), senkron geçmişi (listelenen/eklenen/güncellenen/silinen/yeniden kullanılan, sayım öncesi/sonrası, `prune_refused` uyarısı; PayCore düzeltmesi D3, D4), öğe listesi ve hata ayrıntıları, Kapı 0 ile elenen ekler; bilgi tabanı ekranında belgenin kaynağı ve dış bağlantısı. (Ekranlar 16 paketinde yazılır.)
- **Sınavlar (09) ek:** koşu özetinde `outcome` ve `style` dağılımı (aşama bazlı teşhis), ısınma süresi, güven skoru formül karşılaştırması (PayCore düzeltmesi D7).
- **Sistem durumu (00, 12):** ısınma durumu (`warming/ready`), yüklü modeller ve bağlam uzunluğu, bellek kullanımı vs `mem_limit`; `OLLAMA_CONTEXT_LENGTH` set değilse kırmızı uyarı (PayCore düzeltmesi D6); (R10.5) P7 kuyrukları: etkileşimli / etkileşimli-düşük / arka plan uzunlukları ve beklenen süre, mesai dışı penceresi durumu; `llmaas`'ta sağlayıcı sağlığı ve son 429 oranı.
- **Uyarılar (03c, R9.1; 10c):** kural listesi (tür, eşik, kanal, alıcı), aktif uyarılar (önem, zaman, ack), geçmiş; rozet sayacı üst çubukta; `admin` düzenler, `developer` görür.
- **Onaylar (07):** bekleyen liste, rozet sayacı, detay (agent, kullanıcı, araç, argümanlar vurgulu), Onayla / Reddet + not.
- **Sınavlar (09):** dataset'ler (liste, içe aktar, item düzenle), suite'ler (scorer seçimi, eşik), koşular (ilerleme, özet, item tablosu, iki koşuyu karşılaştır).
- **Koşular (06):** run listesi ve detay (event zaman çizelgesi, "Langfuse'ta aç" linki).
- **Guardrail (08):** politika düzenleyici (kural listesi, aksiyon), "Dene" paneli, olay listesi.

### Ortak

- Boş durum ekranları analisti yönlendirir ("Önce bir bilgi tabanı oluşturun").
- Hata mesajları Türkçe, teknik ayrıntı "ayrıntı" altında.
- Erişilebilirlik: klavye ile gezilebilir formlar.
- Her yeni ekran iki temada da geliştirilir ve PR'da iki temanın ekran görüntüsü eklenir; bileşenlerde sabit renk (`#fff`, `bg-white`, `text-gray-900` gibi) kullanılmaz, yalnızca token sınıfları (`bg-background`, `text-foreground`, `bg-muted`...).

## Teslimatlar

- Çalışan Next.js uygulaması, Dockerfile, `messages/tr.json`.
- Playwright uçtan uca testler (10a: giriş ve proje; 10b-poc: belge yükleme, agent sihirbazı, test, onay): giriş, proje oluşturma, belge yükleme, agent sihirbazı ile oluşturma ve test, onay verme.
- `docs/onyuz.md`: ekran haritası ve rol matrisi.

## Kabul kriterleri

- Analyst rolündeki kullanıcı, kod yazmadan, 13a'daki sentetik örnek belgelerle "Sözleşme Asistanı"nı sihirbazdan kurup test panelinde kaynaklı cevap alır (Playwright ile kanıtlanır).
- Test panelinde onay gerektiren araç çağrısı inline onay istemi gösterir, onay sonrası akış devam eder.
- `admin + read` kullanıcı admin'in tüm ekranlarına girer, aynı listeleri ve detayları görür; hiçbir oluştur/kaydet/sil/yayınla/onayla düğmesi aktif değildir; Playwright ile her ana ekranda `edit` ve `read` modunun ekran görüntüsü karşılaştırılır (fark yalnızca düğme durumları ve rozet).
- Salt-okunur kullanıcı API'yi doğrudan çağırsa bile (tarayıcı konsolundan) mutasyon 403 döner; önyüz bu hatayı "Salt-okunur erişim" mesajıyla gösterir.
- Rolü dışındaki ekranlar menüde görünmez ve URL ile girilince "yetkiniz yok" sayfası döner.
- Lighthouse erişilebilirlik skoru ≥ 90.
- Tema anahtarı açık, koyu ve sistem arasında geçiş yapar; seçim sayfa yenilenince korunur; ilk yüklemede tema yanıp sönmesi yoktur.
- Playwright ile her ana ekranın açık ve koyu ekran görüntüsü alınır; kaynakta sabit renk sınıfı arayan lint kuralı (`eslint` özel kural ya da `grep` tabanlı CI adımı) temiz geçer.
- Metin/arka plan kontrastı iki temada da WCAG AA (axe ile otomatik kontrol).

## Teknik notlar

- Backend OpenAPI şemasından `openapi-typescript` ile tipler üretilir; elle tip yazılmaz.
- SSE için `EventSource` yerine `fetch` + `ReadableStream` (cookie ve header kontrolü için).
- Grafikler için Recharts; dataviz kurallarına uygun sade palet.

## Kapsam dışı

Son kullanıcı sohbet uygulaması (11), görsel akış tasarımcısı, çoklu dil.
