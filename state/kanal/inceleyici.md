# Kanal: inceleyici

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-inceleyici-d9 (önceki: ffcore-inceleyici-04b; Fable 5.2, dalga 9'dan itibaren)
Aktif paket: 14-2 r2 teyidi (bd37a16)
- Durum: ACTIVE
Son okunan: koordinator K-14-0029

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/inceleyici-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 335 mesaj); ID ile atıf orada bulunur.

### R-GEN-0001 · 2026-11-16 22:00 · → koordinator · DURUM
Paket: - · Cevap: K-GEN-0016 · Durum: VERIFIED
Warn günü bilgisi alındı. Bu oturum hook merge edilmeden önce açıldı. Claude Code proje ayarını oturum açılışında okuduğu için bu oturumda hook yüklü değil (docs 9.2 "Hangi oturum hangi ayarı yükler"). Bu yüzden warn günü verisi üretmez; 'rol bulunamadı' ya da yanlış pozitif gözleyemem. Warn günü kontrolleri (`systemMessage`, Read deny, Edit kuralının Write'ı kapsaması) merge sonrası açılan yeni bir oturumda yapılmalı. Bekliyorum.

### R-GEN-0002 · 2026-11-17 17:36 · → koordinator · DURUM
Paket: - · Cevap: - · Durum: BLOCKED
**10c-2 r1 kapısı** (`git archive` kopyası, HEAD 5c27543):
- Backend lint ve `make test`: 1813 passed (llmaas), 1813 passed (airgap).
- Önyüz: lint, typecheck ve check:api 0; Vitest 250/250.
- **e2e: 180/180 ✓.** Bütün 10c-2 testleri geçti: anahtar bir kez gösteriliyor ve iptal ediliyor; kota, uyarı, ack ve rozet; retention; read modu ile 6 ekran × 2 tema axe.
- Loglar `state/evidence/10c-2-r1-rv-*.log`.
- test-int ilk denemede qdrant profili açık olmadığı için başlamadı (benim kurulum hatam); qdrant ile yeniden koşulacak.

**Takılan nokta (Docker):**
- Playwright testler bittikten sonra worker kapanışında asıldı ("worker-0 did not exit within 300000ms, force-killed").
- `ffcore-rv10c2-e2e-run-70c285051d24` konteyneri 16:19'dan beri Up. `docker stop` "tried to kill container, but did not receive an exit event" hatası veriyor.
- Aynı anda açılan 05b r2 hafif yığınında postgres ve migrate 16:32'den beri `Created`; `docker start` zaman aşımına düşüyor.
- Docker daemon yeni konteyner başlatamıyor. 05b r2 teyiti bu yüzden başlamadı; 10c-2 test-int ve probe'ları da bekliyor.

KARAR-GEREK koordinatörün kanalında; seçenekler SendMessage ile gönderildi.

### R-GEN-0003 · 2026-11-18 12:45 · → koordinator · DURUM
Paket: - · Cevap: K-GEN-0022 · Durum: BLOCKED
K-GEN-0022 alındı. Ama Docker motoru şu an çalışmıyor:
- `docker info` "open //./pipe/docker_engine: The system cannot find the file specified" hatası veriyor.
- Süreç listesinde yalnız `com.docker.service` var; Docker Desktop uygulaması açık değil.

Docker Desktop'ı açmak kullanıcının işi; ben açmıyorum. Motor gelince sıra şöyle:
1. 05b r2: rv05b hafif yığını, YIGIN-AC, probe'lar (P1-P9) ve hedefli testler, rapor, YIGIN-KAPA.
2. 10c-2: rv10c2, test-int (qdrant) ve probe'lar.

### R-GEN-0004 · 2026-11-22 12:10 · → koordinator · HANDOFF
Paket: - · Cevap: K-GEN-0042 · Durum: HANDOFF
Oturum `ffcore-inceleyici-04b` kapanıyor. Açık iş yok, ayakta yığın yok (`ffcore-rv` kapalı, YIGIN-KAPA yazıldı). Son rapor `state/reviews/11-2-r2.md` (ONAY).
Yeni inceleyici (`ffcore-inceleyici-d9`) için notlar:
- Örnek raporlar `state/reviews/11-2-r1.md` (yığınlı tur: imaj /app hash denetimi, hedefli test-int, probe, e2e, Langfuse) ve `11-1-r1.md`.
- Probe deseni: `git archive <sha> | tar -x` kopyasına dalın parçası olmayan `tests/integration/test_rv_*_probe.py` yaz; dal testlerini toplamamak için fikstürleri açık adla import et, star import kullanma.
- Kopuk koşu: `run -d tools sh -c '… | tee /tmp/x.log'`, sonra `docker wait`, sonra `docker logs > evidence`. Hook tee'siz pytest/playwright'ı ve `docker logs >` tek başına yazımı engeller.
- e2e kurulumu: `ffcore-10a-nm-pw` volume'ünden `node_modules` kopyası, webServer'sız playwright config ve forward.js. triage-2 ile (220) `e2e_node_modules` imajdan doluyor; bu desen eskiyebilir.
- psql tools imajında yok; `compose exec -T postgres psql` kullan. Kanal başlığının 6. ve 8. satırları `- ` öneksiz.
Bundan sonra bu kanala yazmıyorum.

### R-14-0001 · 2026-11-22 14:20 · → tumu · YIGIN-AC
Paket: 14 · Cevap: K-14-0008 · Yigin: ffcore-rv
14-1 r1 (SHA `bb5ad0d1de032b37077548ffd4d77def28d3ca99`) için hafif inceleme yığını: `ffcore-rv` (18540/13540), `git archive bb5ad0d` kopyasından, `--env-file .env.test`, `--pull never`, `tools` imajı `0.0.0-14` (işçinin; kaynak kopyadan bağlı, yeniden kurulum yok). Servisler: `postgres`, `redis` + `tools` koşuları (14 hedefli test-int, 06a/03c/57 regresyon, birim/sözleşme ve dalda olmayan probe testi). Tam test-int yok. Açık yığınlar: `ffcore` (kullanıcı) + `ffcore-rv`. Bitince `down -v` + YIGIN-KAPA. Diff okuması bitti; güvenlik turu probe'ları bu yığında.

### R-14-0002 · 2026-11-22 14:41 · → koordinator · REVIEW-SONUC
Paket: 14 · Cevap: K-14-0008 · SHA: bb5ad0d1de032b37077548ffd4d77def28d3ca99 · Sonuc: DEGISIKLIK · Bulgu: B0 M2 m2 N5
Rapor `state/reviews/14-1-r1.md` (güvenlik turu ayrı bölüm); kanıt `state/evidence/14-1-r1-rv-*.log`. MAJOR sınıfları: `sinir-yeni-maddeyi-arsivler`, `maske-isaretci-kacagi`.
- **Koşular:** 14 birim/sözleşme/test-int + 03c retention + 57 merge 100 ×2 profil; 06a graph/runs + 134 egress 39; göç turu (tek head `14_0001`, upgrade/downgrade/upgrade 0); dalda olmayan 12 probe. Tam test-int, `make test`, lint, `check:api` ve gerçek HTTP worker→API yolu koşulmadı (işçi logları okundu).
- **MAJOR-1 `sinir-yeni-maddeyi-arsivler`:** `max_items_per_user` dolu ve eski maddelerin hepsi en az bir kez kullanılmışken yeni madde yazıldığı anda arşivleniyor (probe: sınır 2, üçüncü `POST /memories` 201 ama `status: archived`). Sınırdaki kullanıcıda hafıza öğrenmeyi bırakır; "bunu hatırla" başarı döner, uygulanmaz. Düzeltme: bu yazımın kimlikleri tahliye adayı olmasın + test.
- **MAJOR-2 `maske-isaretci-kacagi` (güvenlik, S4):** madde metninde `[/USER MEMORY]` geçerse `recall.mask` ilk işaretçide duruyor; kalan hafıza metni `llm_call.request_messages` kaydında açık kalıyor ve modelde veri bloğu erken kapanıyor. Böyle metin yazılabiliyor (`POST /memories` 201). Düzeltme: yazımda işaretçili metni reddet + maske son işaretçiye kadar; iki test.
- **MINOR-1 `ner-yok-500`:** hafıza açıkken NER yapılandırması kalkarsa `POST /memories` kodsuz 500 (`NerConfigError`); yazım yok. **MINOR-2 `recall-her-kosuda` (karar gerek):** hafıza kapalıyken de her kullanıcı koşusu iç recall çağrısına bağlı, 200 dışı cevap koşuyu düşürür; recall `question` 20.000 sınırı facade + kullanıcı yolunda aşılabilir (kod okuması, uçtan uca denenmedi). Önerim A: kapalılık denetimi worker'da yerel.
- **Sağlam çıkanlar:** sahip dışı herkes (süperadmin dâhil) 403 `memory_not_owner`, `?ids=`/`?source_run_id=` sızdırmıyor; iç uçlar yalnız servis hesabı ve sahiplik koşudan; audit satırlarında metin yok; guardrail önizlemesinde hafıza bloğu yok (gerçek motorla denendi); opt-out yarışı 409; `done` enqueue'dan önce; göç ve `SET NULL`.
- NOTE'lar: reddedilen "bunu hatırla" metninin 60 karakteri `guardrail_events`'te; `dropped` maddeler de kullanılmış sayılıyor; çıkarma işinde `EgressError` koşu olayına düşmüyor; kalıcı enjeksiyon riski; triage-2 ile `docs/degisiklikler.md` merge çakışması.

### R-14-0003 · 2026-11-22 14:41 · → tumu · YIGIN-KAPA
Paket: 14 · Cevap: R-14-0001 · Yigin: ffcore-rv
`ffcore-rv` `down -v` temiz: konteyner 0, volume 0, ağ 0 (`state/evidence/14-1-r1-rv-down.log`). Açık FF yığını yalnız `ffcore` (kullanıcı). İmaj kurmadım; işçinin `0.0.0-14` etiketleri duruyor, `ffcore/e2e:0.0.0-rv` (triage-2 turundan) hâlâ duruyor. Sıradaki: triage-2 r2 teyidi ve 14-1 r2 istekleri geldiğinde.

### R-14-0004 · 2026-11-22 16:20 · → koordinator · ACK
Paket: 14 · Cevap: K-14-0015, K-14-0010, K-GEN-0044
14-1 r2 teyidi başladı: SHA `90aa8c121a1d2560d5278760d5e814fb1ae405ac` (main `d88c682` üstüne rebase'li; r2 delta `4e3150d..90aa8c1`). Önce delta okuması ve rebase doğruluğu (yığınsız), sonra `ffcore-rv` için YIGIN-AC ve altı teyit maddesinin probe'ları. Rapor `state/reviews/14-1-r2.md`.

### R-14-0005 · 2026-11-22 16:32 · → tumu · YIGIN-AC
Paket: 14 · Cevap: K-14-0015 · Yigin: ffcore-rv
14-1 r2 teyidi (SHA `90aa8c121a1d2560d5278760d5e814fb1ae405ac`) için hafif inceleme yığını: `ffcore-rv` (18540/13540), `git archive 90aa8c1` kopyasından, `--env-file .env.test`, `--pull never`, `tools` imajı `0.0.0-14` (kaynak kopyadan bağlı, kurulum yok). Servisler: `postgres`, `redis` + `tools` koşuları (14 hedefli test-int, 06a/facade regresyon, dalda olmayan probe). Tam test-int yok. Açık yığınlar: `ffcore` (kullanıcı) + `ffcore-rv`. Rebase doğruluğu yığınsız doğrulandı (range-diff: r1 commit'leri aynı). Bitince `down -v` + YIGIN-KAPA.

### R-14-0006 · 2026-11-22 16:52 · → koordinator · REVIEW-SONUC
Paket: 14 · Cevap: K-14-0015 · SHA: 90aa8c121a1d2560d5278760d5e814fb1ae405ac · Sonuc: ONAY · Bulgu: B0 M0 m0 N2
r2 teyidi tamam; rapor `state/reviews/14-1-r2.md`, kanıt `state/evidence/14-1-r2-rv-*.log`. Altı maddenin hepsi kendi probe'umla yeniden denendi (11 probe yeşil).
- **(1) MAJOR-1 kapandı:** sınır 2, iki eski madde kullanılmış → yeni madde `active`, en az kullanılan eski `archived`; çıkarma yolunda üç aday için `written` ve `archived` kesişmiyor, aktif sayı 2.
- **(2) MAJOR-2 kapandı:** işaretçili metin (büyük/küçük harf dâhil) POST ve PATCH 400 `memory_text_invalid`, aday yolunda `invalid` 1; tabloya doğrudan konmuş üç işaretçili maddeyle kayıt kopyasında metin yok.
- **(3) MINOR-1 kapandı:** NER'siz POST, PATCH ve `/candidates` 422 `memory_requires_ner`, yazım yok.
- **(4) MINOR-2 A kapandı:** `memory_port` açıkken `HttpMemory`, opt-out ve kapalıyken çağrısız `OffMemory`, kullanıcısız koşuda port yok; `RUN_INPUT_MAX` tek sabit; facade uzun mesaj testi yeşil.
- **(5) NOTE'lar:** önizleme boş; `dropped` madde `use_count` almıyor; `allowed_kinds` recall ve related'da süzüyor; katalog dışı model 400 `model_not_found`; taşıma hatası üç çağrıda da `memory_unavailable` (detail `egress_not_allowlisted`); `deleted_by_user` tabloda reddediliyor; istatistik bütün maddelerini silen kullanıcıyı listeliyor.
- **(6) Rebase:** range-diff'te r1 commit'leri birebir aynı; triage-2 dosyalarına dokunuş yok; `degisiklikler.md` iki madde, 14-1 üstte; `config.py:113` düzeltilmiş.
- **Koşular:** hedefli 128 ×2 profil, 06a/egress/readyz 44, ruff 0. Tam test-int, `make test`, `check:api` ve gerçek HTTP worker→API yolu koşulmadı (işçi logları okundu).
- NOTE-1: uzun facade sorusunda recall sorgusu 20.000 karakterde kayıtsız kesiliyor (koşu düşmüyor; bir olay işareti önerilir, 14-2 ya da FOLLOWUP). NOTE-2: `enabled=false` iken katalog dışı model kabul ediliyor (zararsız).

### R-14-0007 · 2026-11-22 16:53 · → tumu · YIGIN-KAPA
Paket: 14 · Cevap: R-14-0005 · Yigin: ffcore-rv
`ffcore-rv` `down -v` temiz: konteyner 0, volume 0, ağ 0 (`state/evidence/14-1-r2-rv-down.log`). Açık FF yığını yalnız `ffcore` (kullanıcı). İmaj kurulmadı. Açık inceleme isteği yok; sıradaki 14-2 PR-HAZIR'ı.

### R-14-0008 · 2026-11-22 19:49 · → koordinator · ACK
Paket: 14 · Cevap: K-14-0025
14-2 r1 isteği alındı (SHA `8f07072ce80f18c7104ddc0058541416102db5d5`, yedi odak). Önce yığınsız okuma (delta 47 dosya, mesaj dosyaları, e2e ve Vitest), ardından `ffcore-rv` için YIGIN-AC (e2e profili, NER ağsız kopya). Tam test-int yok. Rapor `state/reviews/14-2-r1.md`.

### R-14-0009 · 2026-11-22 19:55 · → tumu · YIGIN-AC
Paket: 14 · Cevap: K-14-0025 · Yigin: ffcore-rv
14-2 r1 (SHA `8f07072ce80f18c7104ddc0058541416102db5d5`) için inceleme yığını: `ffcore-rv` (18540/13540), `git archive 8f07072` kopyasından, `--env-file .env.test`, `--pull never`, imaj etiketi `0.0.0-rv` (`up --build --pull never`, çıplak build yok). Profil `test` + `e2e` (tam yığın: e2e backend'e bağlı), `FAKE_EMBED=1`, NER ağırlığı `ffcore_model_cache`'ten ağsız kopya. Koşular: Vitest (dal + probe, `--no-deps`), e2e `test_14_*` + dalda olmayan probe spec, backend hedefli 14 testleri. Tam test-int yok; `E2E_SCREENSHOT_DIR` boş. Açık yığınlar: `ffcore` (kullanıcı), `ffcore-16`, `ffcore-rv` (üçüncü; K-14-0025 izni). Bitince `down -v` + YIGIN-KAPA.

### R-14-0010 · 2026-11-22 20:13 · → koordinator · DURUM
Paket: 14 · Cevap: K-GEN-0048 · Yigin: ffcore-rv (durduruldu, volume duruyor)
K-GEN-0048 alındı: `ffcore-rv` servislerinin hepsi adıyla durduruldu (çalışan konteyner 0; `down -v` değil, NER kopyası ve e2e kurulumu volume'de). Koşan e2e (test_14_*) yarıda kesildi, sonucu sayılmaz. Biten: Vitest 64 dosya / 349 (dal 344 + 5 probe). Bekleyen (16 zilinden sonra): e2e test_14_*, probe spec, backend hedefli 14 testleri. O zamana kadar yığınsız rapor taslağı. İlk bulgu adayları: 'dikkate aldım' kartında `?ids=` hatası ve başarısız 'Bunu unut' ekranda sessiz (probe P2/P3).

### R-14-0011 · 2026-11-22 20:47 · → koordinator · REVIEW-SONUC
Paket: 14 · Cevap: K-14-0025 · SHA: 8f07072ce80f18c7104ddc0058541416102db5d5 · Sonuc: ONAY · Bulgu: B0 M0 m2 N5
14-2 r1 tamam; rapor `state/reviews/14-2-r1.md`, kanıt `state/evidence/14-2-r1-rv-*.log`.
- **Koşular:** Vitest 64 dosya / 349 (dal 344 + 5 probe), e2e `test_14_*` 8/8 (NER ağsız kopya, atlanan yok), e2e probe 4/4, backend hedefli 58 + ruff 0. Tam test-int, `make test`, typecheck/eslint ve airgap hedefli koşulmadı (işçi logları okundu).
- **(1) Veri sınırı tutuyor:** admin `/settings`, sihirbaz sekmesi, `/memory`, `/runs`: 20 API cevabında ve DOM'da üyenin metni yok; istatistik yalnız sayı; başka üye görmüyor. **Düzeltme:** `GET /memories?ids=<başkasının>` 403 değil **200 boş liste** (sahibine süzüyor); 403 `memory_not_owner` tekil PATCH/DELETE'te. Bulgu değil (NOTE-1).
- **(2) Akışlar:** sil/Unut sonrası kart yok; opt-out'ta tek okuma, kart yok; yoklama 5,04 sn aralık, sonuç gelince ve sohbetten çıkınca duruyor; pii ve işaretçi redleri kodlu ve anlaşılır metinle, yazım yok.
- **(3) Konsol:** analyst'e neden, istek 0; silinmiş modelli satırda açıkken `model_not_found` ekranda, kapatma kaydediliyor. **(4)** `question_truncated` yalnız uzun soruda. **(5)** en/tr 1792/1792, sabit metin yok, 12 yeni görüntü. **(6)** hata tablosu API ile aynı. **(7)** `user` rolü Vitest render'ı var; başlık/menü bağlantısı testi yok (NOTE-3).
- **MINOR-1 `not-karti-hatasi-sessiz`:** cevap altı kartta `?ids=` sorgusu 403/500 ve başarısız "Bunu unut" ekrana çıkmıyor; unutulan maddeden sonra sayı eski kalıyor (`memory-notes.tsx`).
- **MINOR-2 `docs-baglanti-kosulu`:** `docs/chat.md` bağlantıyı "hafıza açıkken" diye anlatıyor, kodda koşulsuz.
- NOTE-2: mesaj başına tam olay okuması (FOLLOWUP önerisi). NOTE-4: çıkarma hatası üyeye görünmüyor. NOTE-5: kapalı projede "Use memory" açık görünüyor.

### R-14-0012 · 2026-11-22 20:47 · → tumu · YIGIN-KAPA
Paket: 14 · Cevap: R-14-0009 · Yigin: ffcore-rv
`ffcore-rv` `down -v` temiz: konteyner 0, volume 0, ağ 0 (`state/evidence/14-2-r1-rv-down.log`). Açık FF yığını yalnız `ffcore` (kullanıcı). Kalan imaj etiketleri `ffcore/{backend,frontend,tools,e2e}:0.0.0-rv` (16-1 turunda yeniden kurulacak). Sıradaki: K-16-0008 (16-1 r1 + güvenlik turu); yeni YIGIN-AC ile.

### R-16-0001 · 2026-11-22 20:47 · → koordinator · ACK
Paket: 16 · Cevap: K-16-0008, K-16-0010
16-1 r1 + güvenlik turu isteği alındı (SHA `044c148ee278494a6140a3e7e36ab916a0131c0e`, yedi odak; K-16-0010: `document_from_source` 16-3'ün işi, bulgu sayılmayacak). Önce yığınsız okuma (51 dosya; `sources/**`, `api/sources.py`, göç, `knowledge/removal.py`), ardından `ffcore-rv` için YIGIN-AC (16-1 imajı, hedefli + güvenlik probe'ları; tam test-int yok). Rapor `state/reviews/16-1-r1.md`, güvenlik turu ayrı bölüm.

### R-16-0002 · 2026-11-22 20:52 · → tumu · YIGIN-AC
Paket: 16 · Cevap: K-16-0008 · Yigin: ffcore-rv
16-1 r1 + güvenlik turu (SHA `044c148ee278494a6140a3e7e36ab916a0131c0e`) için hafif inceleme yığını: `ffcore-rv` (18540/13540), `git archive 044c148` kopyasından, `--env-file .env.test`, `--pull never`, imaj `0.0.0-rv` 16-1 koduyla yeniden (`up --build --pull never`). Servisler: `postgres`, `redis`, `migrate`, `sync-worker` (başlangıç ve bağlama kontrolü) + `tools` koşuları (16-1 hedefli iki profil, dalda olmayan güvenlik probe'u). Tam yığın, e2e ve tam test-int yok. Açık yığınlar: `ffcore` (kullanıcı) + `ffcore-rv`. Bitince `down -v` + YIGIN-KAPA.

### R-16-0003 · 2026-11-22 21:11 · → koordinator · REVIEW-SONUC
Paket: 16 · Cevap: K-16-0008 · SHA: 044c148ee278494a6140a3e7e36ab916a0131c0e · Sonuc: DEGISIKLIK · Bulgu: B0 M1 m2 N8
16-1 r1 + güvenlik turu tamam; rapor `state/reviews/16-1-r1.md`, kanıt `state/evidence/16-1-r1-rv-*.log`.
- **Koşular:** hedefli 110 ×2 profil, ruff 0, güvenlik probe'u 6/6 (gerçek dizin, symlink, hard link), `sync-worker` 16-1 imajıyla ayakta (tik çalışıyor, `/data/sources` salt-okunur, port yok). Tam test-int, `make test`, ölçek testi, 04b silme grubu, `check:api`, smoke ve Qdrant koşulmadı (işçi logları okundu).
- **MAJOR-1 `fs-kok-proje-siniri-yok` (KARAR-GEREK):** `FS_SOURCES_BASE` kurulum genelinde tek ve kaydı her projenin developer'ı yapabiliyor. Probe S3: B projesinin developer'ı kök `"."` ile kaydedip senkronluyor (201/202), öğe listesinde A'nın `paylasim/ik/maas.md` yolunu görüyor; B'nin admin'i A'nın dosya metnini aramada buluyor. Seçenekler: **A (önerim)** ağ klasörü kaydı ve kök değişikliği superadmin'e (en küçük değişiklik; sağlayıcı ataması deseni); **B** proje başına taban `FS_SOURCES_BASE/<proje>` (dizin düzenini platform dayatır); **C** olduğu gibi + docs uyarısı (sınır operatöre kalır).
- **Güvenlik turunun kalanı temiz:** 23 kök denemesi (mutlak, `..`, `~`, ters bölü, NUL, dışarı ve içeri symlink, URL-kodlu) kaçamadı; runtime'da dışarı symlink'ler `path_outside_base` ile atlandı, dışarıdaki metin ne parçada ne depoda; kök sonradan symlink'e çevrilince koşu `failed`. Kimlik `secret_encrypted` + `***` + audit maskesi (`config` düz JSONB, kimlik taşımıyor: NOTE-1). ACL: eşlemesiz yalnız admin; iç içe klasör eşlemesi dosya değişmeden bir sonraki koşuda yeniden çözülüyor.
- **D4:** boşalmış paylaşım `prune_refused` (0 silme), kök yokken `failed`, vektör deposu düşünce `prune_failed` (0 silme, sonraki koşu tamamlıyor).
- **MINOR-1 `kb-silinince-kaynak-surer`:** beslenen bilgi tabanı silinince (204) kaynak `active` kalıp silinmiş bilgi tabanına belge yazmayı sürdürüyor, hata yok.
- **MINOR-2 `sync-worker-bellek-siniri-yok`:** `mem_limit` yok; `fetch_raw` dosyayı (≤ 500 MB) belleğe okuyor, `max_jobs=2`.
- NOTE'lar: hard link ayırt edilemez; eşleme daraltması sonraki koşuya kadar etkisiz; `prune_refused` uyarısı kural ister; eski `mtime` ile kopyalanan dosyayı delta görmez; kayıp `queued` koşu kaynağı kilitler; Qdrant'ta kısmi vektör silme.
- İnceleme notu: ilk `up`'ta `sync-worker` eski imajla döndü (serviste `build` yok); `backend` yeniden kurulunca düzeldi. Ürün hatası değil; kapı betiklerinde `backend` kurulumunun `sync-worker`'dan önce geldiği teyit edilmeli.

### R-16-0004 · 2026-11-22 21:11 · → tumu · YIGIN-KAPA
Paket: 16 · Cevap: R-16-0002 · Yigin: ffcore-rv
`ffcore-rv` `down -v` temiz: konteyner 0, volume 0, ağ 0 (`state/evidence/16-1-r1-rv-down.log`). Açık FF yığını yalnız `ffcore` (kullanıcı). Kalan imaj etiketleri `ffcore/{backend,frontend,tools,e2e}:0.0.0-rv`. Sıradaki: K-14-0029 (14-2 r2 teyidi, yığınsız).

### R-14-0013 · 2026-11-22 21:12 · → tumu · YIGIN-AC
Paket: 14 · Cevap: K-14-0029 · Yigin: ffcore-rv
14-2 r2 teyidi alındı (ACK; SHA `bd37a169ecdb0b2f23c5a4581bc8379e2cbe726c`). Servis açılmıyor; yalnız tek konteyner koşusu: `ffcore-rv` `e2e` servisi `--no-deps` ile Vitest (dal + probe), `git archive bd37a16` kopyasından, imaj `ffcore/e2e:0.0.0-rv` (kurulum yok). Koşu `e2e_node_modules` volume'unu açtığı için YIGIN-AC; bitince `down -v` + YIGIN-KAPA. Açık yığın: `ffcore` (kullanıcı).
