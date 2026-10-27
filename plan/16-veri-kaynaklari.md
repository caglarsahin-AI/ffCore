# 16. Veri kaynağı bağlayıcıları: Confluence, Jira, SharePoint, ağ klasörü [FFCore Knowledge]

**Bağımlılık:** 03, 04a, 05a, 03b (`core/egress.py`). **Süre:** 8 gün (PayCore'un Confluence/Jira Data Center bağlayıcıları `ingest/sync.py`, `atlassian_client.py` Server/DC yarısını karşılar ve `ffcore.sources` uzantısından FFCore'a terfi eder, C14; 3 günü PayCore düzeltmeleri D1-D4). **Dalga:** PoC sonrası (M7). **Sıra:** önce Confluence/Jira DC terfisi (PayCore'da zaten canlı), sonra SharePoint Online ve Atlassian Cloud (`llmaas`), sonra ağ klasörü. **Profil:** ağ klasörü her ikisi; Confluence ve Jira Server/Data Center `airgap`'te de; Atlassian Cloud ve SharePoint Online yalnızca `llmaas`. **PoC:** hayır (PayCore korpusu PoC'de PayCore'un mevcut senkronuyla beslenir). Tablo adı: FFCore `source_sync_state` (PayCore `sync_state` ile çakışmaz, N48).

## Amaç

Bilgi tabanının elle dosya yüklemeyle değil, kurumun yaşayan kaynaklarından düzenli ve artımlı olarak beslenmesi; silinen ve güncellenen içeriğin indekste de güncellenmesi; kaynak sistemdeki erişim yetkilerinin indekse taşınması. PayCore LLM'deki Confluence ve Jira bağlantılarının yönetilebilir, ekrandan kurulan hali.

Jira iki yönlü ele alınır: (a) veri kaynağı olarak issue'lar bilgi tabanına indekslenir (geçmiş kararlar, çözümler); (b) araç olarak canlı sorgu ve issue açma 05'teki OpenAPI→MCP yayınlama ile yapılır. Bu paket (a)'yı kapsar, (b) için yalnızca hazır Jira OpenAPI örneği eklenir.

## Kapsam

### Ortak bağlayıcı çekirdeği (`backend/app/sources/`; TERMINOLOGY: "connector" adı kullanılmaz, N28)

- `data_sources(id, project_id, kb_id, kind: confluence|jira|sharepoint|fs, name, config (şifreli: URL, kimlik, alan/proje/site/klasör filtreleri), schedule (cron), sync_mode: full|incremental, status, last_sync_at, last_error, created_by)`
- `source_items(id, data_source_id, external_id, external_url, title, external_updated_at, content_hash, raw_path, document_id, acl_source jsonb, state: active|deleted, gate0_status, gate0_reason)`; ekler 04'teki `attachments` tablosunda (`source_item_id` ile).
- `sync_runs(id, data_source_id, layer: raw|silver|gold, mode: full|delta, started_at, ended_at, status, listed, added, updated, deleted, skipped, reused, errors jsonb, count_before, count_after, prune_decision)` (PayCore düzeltmesi D3, D4)
- `sync_state(data_source_id, layer, cursor, completed_at)`: her katmanın kendi ilerleme işareti; önceki bitmeden sonraki koşmaz. (PayCore düzeltmesi D3)
- Bağlayıcı arayüzü (PayCore düzeltmesi D3): `count() -> int` (kaynak sunucusunun kayıt sayımı), `list_changes(since) -> iterator[Item]`, `fetch_raw(item) -> bytes + headers` (API cevabı birebir), `list_attachments(item) -> iterator[Attachment]`, `fetch_attachment(att) -> bytes`, `acl(item) -> roles/users`, `test_connection()`. Bağlayıcı Markdown üretmez; dönüşüm 04'ün hattında raw'dan yapılır. Her kaynak türü bir sınıf.
- **Üç katmanlı senkron** (PayCore düzeltmesi D3): `raw` (API cevabı birebir + ek dosyaları, `data/storage/raw/{project}/{kb}/{kind}/{space|proje}/{id}/`) → `silver` (04'teki dönüşüm ve kapılar, kaynağa gitmeden raw'dan) → `gold` (parça ve vektör, silver'dan). Komutlar: `make sync SOURCE=<key> LAYER=raw|silver|gold MODE=full|delta`. Parçalama değişince yalnızca gold; dönüştürücü/kapı değişince silver; kaynağa yalnızca raw koşusu gider. Metni değişmeyen parçaların vektörü taşınır (`reused`). Kanıt: PayCore ölçeğinde (~30 bin sayfa, ~30 GB ek) kaynaktan yeniden çekim saatler ve hız sınırı; değişmemiş eklerin yeniden embed'i ~46 dk.
- **Kapı 0, ek kabulü indirmeden önce** (PayCore düzeltmesi D1): kaynak listelemesindeki ek metadata'sıyla (ad, boyut, tarih, MIME) karar verilir; metni olmayan ikili, kapsam dışı biçim (arşiv, Excel/CSV, `.sql`, görsel), `ATTACHMENT_MIN_DATE` öncesi, boyut sınırı aşan ve mükerrer (aynı ad + boyut başka kayıtta dönüşmüşse `shared_from`) ekler indirilmez; karar `attachments.gate0_*`'a yazılır. Biçim kümeleri 04'teki `scope.py`'den.
- **Ek dönüşümü** (PayCore düzeltmesi D2): indirilen ekler 04'teki hattan geçer (ilk bayt yönlendirme, kodlama, PDF kuralı, eski Office, e-posta, diyagram, isteğe bağlı video, süreç havuzu ve süre sınırı); ek metni belgenin silver'ına üst kayıt breadcrumb'ı + `Ek: <dosya adı>` ile girer. Kurumsal Confluence/Jira'da bilginin önemli kısmı eklerdedir; "ekler isteğe bağlı" değil, varsayılan açıktır.
- Senkron motoru (04'teki worker üzerinde): zamanlayıcı (`arq` cron, C9) ya da elle tetik; `delta` modunda `external_updated_at` ve `content_hash` ile yalnızca değişenler; hata olan öğe atlanır ve `sync_runs.errors`'a yazılır, tüm senkron durmaz. **(R10.3 kararı) Delta koşu, kaynağın silme bilgisi (tombstone) verdiği bağlayıcılarda silebilir** (SharePoint/OneDrive Graph `delta` `@removed`); tombstone vermeyen bağlayıcılarda (Confluence, Jira, ağ klasörü) delta hiçbir şey silmez. Tombstone silmesinde de D4'ün oran kuralı (`PRUNE_MAX_RATIO`) ve sıra (önce vektör, sonra DB ve dosya) aynen uygulanır; sayım kontrolü delta'da tombstone sayısına uygulanır; **oran kaynaktaki toplam belge sayısına bölünür, delta paketindeki öğe sayısına değil** (C20).
- **Güvenli silme uzlaştırması** (PayCore düzeltmesi D4), yalnızca `full` koşuda ve şu koşulların hepsi tutarsa: (1) listeleme istisnasız bitti; (2) kaynak sunucusunun kayıt sayımı listelemeden **önce ve sonra** alındı ve görülen tekil kayıt sayısına eşit (`count_mismatch` ise hiçbir şey silinmez, zorlama bayrağı bunu geçmez); (3) silinecek oran kaynağın `PRUNE_MAX_RATIO` değerini (varsayılan 0,2) aşmıyor, aşarsa `prune_refused` loglanır ve yalnızca açık `--force-prune` ile geçilir; (4) sıra: önce vektör deposu, o silinemezse hiçbir şey silinmez, sonra DB ve dosyalar; (5) başka bir belgenin ödünç aldığı (`shared_from`) ek dosyası silinmez, dönüşümüyle o belgeye taşınır. `prune_decision` ve sayımlar `sync_runs`'a yazılır; `prune_refused` 10'daki ekranda uyarı olur. Kanıt: servis hesabı yetki kaybedince ya da listeleme yarıda kesilince kapısız tam tarama bütün bilgi tabanını "kaynakta silinmiş" sayardı.
- ACL eşleme: kaynak sistemdeki grup/kullanıcı yetkileri `documents.acl_*` alanlarına eşlenir; eşleme tablosu `acl_mappings(data_source_id, external_group, role|user_id)` ekrandan düzenlenir; eşlenmeyen gruplar varsayılan olarak "yalnızca admin" (güvenli taraf). **(C15)** Senkron motoru kaynak gruplarını senkron anında platform kullanıcılarına genişletir ve `documents.acl_users` olarak yazar (platformda grup varlığı yoktur); üyelik değişince bir sonraki senkronda güncellenir.
- Belgeye kaynak bağlantısı: cevaplardaki kaynak kartı Confluence sayfasına ya da Jira issue'ya doğrudan link verir (`external_url`).
- Hız sınırı ve nezaket: kaynak başına eşzamanlı istek sınırı, Atlassian/SharePoint rate limit cevaplarında üstel bekleme.

### Confluence

- Cloud (REST v2, API token) ve Server/Data Center (REST v1, PAT) ikisi de; `config.space_keys[]`, isteğe bağlı etiket ve üst sayfa filtresi.
- Sayfa içeriği raw'a storage format olarak birebir; silver'da Markdown'a dönüşüm (makro temizleme: `toc`, `jira`, `include` özel işlenir; tablolar korunur). Ekler Kapı 0'dan geçenler indirilir ve dönüştürülür (varsayılan açık). (PayCore düzeltmesi D1-D3)
- Sayfa hiyerarşisi breadcrumb olarak embed edilen metnin başına (`Space › üst sayfalar › Sayfa › Başlık`) ve `section_path` olarak parçalara yazılır (04). (PayCore düzeltmesi D5)
- Dil kuralı `ALLOWED_LANGUAGES` (varsayılan `tr,en`); yalnızca Türkçe kabul etmek PayCore'da teknik space'lerin %25'ini elemişti. (PayCore düzeltmesi D1)
- Artımlı: CQL `lastModified >= since`.
- ACL: space izinleri ve sayfa kısıtlamaları → `acl_mappings`.

### Jira (veri kaynağı)

- Cloud ve Server; `config.jql` (örn. `project in (OPS, HELP) AND updated >= -30d`), alan seçimi (özet, açıklama, yorumlar, çözüm, durum, etiketler).
- Her issue bir belge: başlık + açıklama + yorumlar Markdown; metadata: proje, tür, durum, öncelik, atanan, tarih; parçalama yorum sınırlarında.
- Artımlı: `updated >= since` JQL (delta, silmez); silinen/arşivlenen issue'lar yalnızca `full` koşuda güvenli silme uzlaştırmasıyla (D4) kaldırılır. Yorum ve açıklamadaki log/stack trace/JSON yığınları Kapı 2 veri dökümü tespitiyle elenir; PayCore PRSIM'de 8.594 düzyazısız ve 3.784 çok kısa parça bu kapılarla ayıklandı. (PayCore düzeltmesi D1, D4)
- ACL: proje izin şeması → `acl_mappings`.
- Araç tarafı için: `data/samples/openapi/jira.yaml` (issue ara, issue getir, issue oluştur [onaylı], yorum ekle [onaylı]) 05'teki MCP yayınlama ile kullanılır; bu paket yalnızca dosyayı ve bir uçtan uca testi sağlar.

### SharePoint / OneDrive (`llmaas`)

- Microsoft Graph, uygulama kimliği (client credentials) ile; `config.site_ids[]`, kütüphane ve klasör filtresi, dosya türü filtresi.
- Artımlı: Graph `delta` sorgusu (eklenen, değişen, silinen tek çağrıda).
- Dosyalar 04'teki Docling hattına verilir; ACL: Graph `permissions` → eşleme.
- SharePoint Server (on-prem) kapsam dışı; gerekirse ağ klasörü bağlayıcısıyla kütüphane kök dizini üzerinden.

### Ağ klasörü (her iki profil)

- Sunucuya bağlı dizin (SMB/NFS mount, Compose volume); `config.root` **sabit `FS_SOURCES_BASE` kökünün altında göreli yoldur** (C5): mutlak yol, `..` ve symlink ile kök dışına çıkış kayıt anında 400, runtime'da da doğrulanır (`.env` ve uygulama dizini indekslenemez); `include_globs, exclude_globs`.
- Artımlı: dosya `mtime` ve `content_hash`; silinenler taranarak bulunur.
- ACL: klasör bazlı eşleme (`/sozlesmeler/yonetim/` → admin) ekrandan.

### Yönetim ve izleme (10'a ekran)

- Veri Kaynakları ekranı: kaynak ekle (tür, bağlantı bilgileri, bağlantı testi, filtreler, zamanlama, ACL eşleme), elle "Şimdi senkronla", senkron geçmişi (eklenen/güncellenen/silinen/hata), öğe listesi (durum, son güncelleme, belgeye git), hata ayrıntıları.
- Bilgi tabanı ekranında belgenin kaynağı ve kaynak bağlantısı görünür; kaynaktan gelen belge elle silinemez (kaynaktan silinmeli ya da kaynak filtresi değişmeli), uyarı ile.

## Teslimatlar

- Bağlayıcı çekirdeği, dört bağlayıcı, senkron motoru, ACL eşleme, 10'a ekranlar, `jira.yaml` araç örneği, testler (sahte Confluence/Jira/Graph sunucuları ile; ağ klasörü gerçek dizinle), `docs/veri-kaynaklari.md` (her kaynak için gerekli izinler ve adımlar).

## Kabul kriterleri

- Confluence'ta bir sayfa güncellendiğinde bir sonraki delta senkronda yalnızca o sayfa yeniden indekslenir; kaynakta gerçekten silinen 3 sayfa (oran eşik altında) bir sonraki `full` koşuda bütün katmanlardan kalkar.
- (PayCore düzeltmesi D4) Servis hesabının yetkisi bir space'ten kaldırılınca `full` senkron `prune_refused` verir, hiçbir belge silinmez, ekranda uyarı görünür. Listeleme ortasında ağ hatası olunca silme yapılmaz (`count_mismatch`). Tombstone vermeyen kaynaklarda delta koşu hiçbir koşulda silmez; SharePoint delta'da tombstone oranı `PRUNE_MAX_RATIO`'yu aşarsa `prune_refused`.
- (PayCore düzeltmesi D3) Parçalama ayarı değişip `make sync LAYER=gold MODE=full` koşulduğunda kaynak sisteme hiç istek gitmez (sahte sunucu istek sayacı 0); metni değişmeyen parçalar yeniden embed edilmez (`reused=N`). Dönüştürücü değişince `LAYER=silver` raw'dan üretir, kaynağa gitmez.
- (PayCore düzeltmesi D1, D2) 10.000 satırlık log eki `data_dump:log` olur; sayfa indekslenir, ek indekslenmez. 500 MB üstü ek ve görsel ekler indirilmez (`gate0_status=skipped`). Aynı ad ve boyuttaki ek iki sayfada varsa bir kez indirilir ve dönüştürülür (`shared_from`). `.doc` uzantılı MHTML eki okunur Türkçe metin üretir.
- Jira'da `jql` ile seçilen issue'lar belge olarak indekslenir; "X hatasını daha önce nasıl çözmüştük" sorusuna ilgili issue kaynak gösterilir ve karta tıklayınca Jira açılır.
- Confluence'ta yalnızca "Yönetim" grubunun görebildiği sayfa, `acl_mappings` ile admin'e eşlenir ve analyst aramasında dönmez; eşlenmemiş grup varsayılan olarak yalnızca admin'e açılır.
- SharePoint `delta` ile silinen dosya (tombstone) aynı delta koşusunda indeksten kalkar; 100 dosyalık kütüphanede 30 dosya aynı anda silinirse (oran > 0,2) `prune_refused` ve uyarı (03c uyarı sistemi).
- (C5) `config.root=/` ya da `../..` ile kaynak kaydı 400 `path_outside_base`; `FS_SOURCES_BASE` altındaki symlink dışarıyı gösteriyorsa öğe atlanır ve hata listesine yazılır.
- Ağ klasöründe 1.000 dosyalık ilk tam senkron ve ardından tek dosya değişikliğiyle artımlı senkron, ikincisi 1 dakikanın altında.
- Senkron sırasında bir öğe hata verirse diğerleri devam eder; hata ekranda öğe bazında görünür.
- Kaynak kimlik bilgileri API cevaplarında ve loglarda maskelidir.

## Teknik notlar

- Atlassian için `atlassian-python-api`; Graph için `msgraph-sdk` ya da düz httpx; Confluence storage format dönüşümü için kendi dönüştürücü (04'teki to-markdown hattına ek).
- PayCore LLM'deki Confluence dönüşüm ve parçalama tecrübesi buraya taşınır; makro temizleme kuralları oradan alınır. (PayCore düzeltmesi D1-D4) Referans kod: `src/paycore_llm/ingest/sync.py` (bronze/silver/gold, `_bronze_attachments` = Kapı 0 sırası, `count_mismatch`, `prune_refused`, `_reuse_vectors`, `_backfill_embedding_model`), `ingest/prune.py` (`reconcile_source`, `_remove`, `release_file`, `drop_rejected`), `ingest/layout.py` (yol kuralları), `ingest/store.py` (`content_hash_owner`, `text_hash_owner`); PayCore CLAUDE.md "Bilgi deposu yapısı", "Senkronizasyon kuralları", "Bronze `--full`".
- Prod sonrası artımlı senkron mesai dışında zamanlanır; CPU'da ingest sohbeti yavaşlatır (PayCore tecrübesi). İlk tam senkron kullanıcıya açılmadan önce kesintisiz koşar.
- Disk bütçesi: raw ve silver katmanı PayCore ölçeğinde ~30 GB; `docs/donanim.md` (12).
- Büyük alanlarda ilk tam senkron saatler sürebilir; ilerleme `sync_runs`'ta ve ekranda, iptal edilebilir.
- Profil: `airgap`'te Atlassian Cloud ve Graph adresleri kapalıdır; Server/DC ve ağ klasörü çalışır. `llmaas`'ta çıkış izin listesine Atlassian ve Microsoft adresleri eklenir (12).

## Kapsam dışı

Google Drive, Notion, e-posta kutuları, veritabanı tablolarını belge olarak indeksleme (bunlar text-to-SQL ile sorgulanır), SharePoint Server on-prem API'si, gerçek zamanlı webhook tabanlı senkron (zamanlı artımlı yeterli; webhook ileride).
