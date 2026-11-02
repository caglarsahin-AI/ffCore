# 19. M3 sunucu paketi: PayCore sunucusunda PoC koşusunun hazırlığı [FFCore Platform]

**Bağımlılık:** 00i, 04a, 06a, 07, 13b (MERGED); 03c (anahtar/kota; MERGED). **Süre:** ~4 gün. **PoC:** evet (M3 kapısının kalan yarısı). **Karar kaynağı:** kullanıcı, 1 Kasım 2026 ("M3 başlatılsın, 2-3 korpus kullanılabiliyor"; korpus yolu A: raw katmandan ingest, KARARLAR).


**Durum (2 Kasım 2026):** MERGED: ffcore f25268e (990abdb, r2 ONAY R-19-0004), paycoreLLM master ca1b287 (6f03007). Kalan: kullanıcının sunucu koşusu (runbook `docs/paycore/m3-sunucu.md`), kabul 3 bellek bütçesi `free -g` ile (PENDING_ENV), FOLLOWUP-137 (Kapı 2 başlık satırı) M3 ingest'inden önce.

## Amaç

PLAN 8 M3 kapısı PayCore sunucusunda (`airgap`, Qwen 3.5 35B CPU, internetsiz) gerçek modelle `make eval` (S1 ≥ %80, `docs/paycore/s1-taban.md` ile karşılaştırma) ve cpu süre ölçümü ister. Kod hazır ama sunucuya kurulum hazır değil. Bu paket, **kullanıcının sunucuda yalnız belgeli komutları koşturarak** FFCore'u kurup PayCore korpusuyla ölçüm alabilmesini sağlar. Ajan sunucuya bağlanmaz, `.env`'e dokunmaz, `data/**` ve `eval/results/**` okumaz (CLAUDE.md, PLAN 5 R3.1).

## Kapsam

1. **Sunucu kurulumu (paycoreLLM tüketici deposu, `compose.ffcore.yml`):** bugün yalnız Langfuse servislerini içerir (00i). Tüm FFCore servisleri eklenir: `migrate`, `backend`, `agent-worker`, `agent-worker-bg`, `worker` (bilgi), `mcp-search`, `mcp-sql`, LiteLLM, Redis, Qdrant (PayCore'da mevcutsa yeniden kullanım, değilse profil), frontend (konsol); Ollama host'ta kalır (`host.docker.internal:11434`). `mem_limit` değerleri 00i bellek tablosuna (`docs/paycore/bellek.md`) işlenir; toplam fiziksel bellek − OS payını aşmaz.
2. **Çevrimdışı paketleme (12'nin PoC alt kümesi):** `deploy/offline/images.txt` (sürüm/digest pinli), `docker save` ile imaj arşivi + SHA-256 manifesti; `make models` ağırlıklarının (bge-m3, reranker, Docling, PaddleOCR) `model_cache` volume'una taşınması; dış ağ gerektiren her adım **kullanıcının internetli hazırlık makinesinde** (ajan çalıştırmaz). Sunucuda `docker load` + manifest doğrulama.
3. **Korpus girişi (karar A, raw katmandan ingest):** FFCore'a additive CLI `python -m ffcore.cli ingest-raw --project --kb --raw-dir <salt okunur bağlama> --acl <rol> [--limit N] [--sources ...]` (C6 `ingest_from_raw` giriş noktasını çağırır; idempotent: sha256, sürüm). PayCore tarafı uzantı betiği (paycoreLLM `scripts/`, C14: gerekirse `ffcore.sources` kaydı) PayCore raw düzenini FFCore `raw_path`/metadata biçimine eşler (breadcrumb, kaynak URL, güncellik tarihi). **Önce küçük dilim** (`--limit`), süre ölçülür, sonra tam korpus (kullanıcı 2-3 korpusu seçer; kişi verisi içeren kayıt (PRSIM personel adı/e-posta) için KARARLAR karar 5: guard 08 tam gelene kadar o kaynak ingest dışı ya da maskeli). Kapılar (Kapı 0-2) ve ingest raporu çalışır; elenen belge gerekçeli.
4. **Seed ve hesaplar:** `make seed` sentetik değil PayCore profili: tek proje, `admin` kullanıcı (şifre kullanıcı elinde, `create-superadmin` CLI), PayCore doküman asistanı (`mode: always`) ve onaylı SQL asistanı (sentetik DB); PayCore S1 profilleri = filtreli agent (`knowledge[].filter`). Open WebUI → facade yolu 06b'ye bağlı olduğundan PoC'de konsol test paneli kullanılır.
5. **Ölçüm koşusu:** `make eval MODEL="qwen3.5:35b cpu" DATASET=<S1 yolu> PROJECT=<proje> APPROVE_SQL=1` (kullanıcı koşturur; S1 deponun dışında kalır); `rewrite=false` koşu 1 kabul koşusu; rapor `eval/results/` altında, kullanıcı özet sayıları `docs/demo.md` "Real-model results" ve `docs/paycore/s1-taban.md` karşılaştırma tablosuna aktarır (ajan o dizini okumaz).
6. **Runbook `docs/paycore/m3-sunucu.md` (İngilizce arayüz kuralı hariç proje belgesi Türkçe):** hazırlık makinesi, taşıma, kurulum, sağlık kontrolü (`/readyz`, `make smoke`), küçük dilim ingest, tam ingest, S1 koşusu, ölçüm toplama, geri alma (`down`, volume), sorun giderme (bellek, `model_missing`, Ollama bağlam). Her komut kopyalanabilir blok, beklenen çıktı satırıyla.

## Teslimatlar

- paycoreLLM: `compose.ffcore.yml` (tam), `scripts/` korpus eşleme betiği, `docs/paycore/m3-sunucu.md`, bellek tablosu güncel; merge koordinatörde (KARARLAR "paycoreLLM merge'ü koordinatörde").
- FFCore: `deploy/offline/` (images.txt, save/load betikleri, manifest), `backend/ffcore/cli.py` `ingest-raw` (additive), testler, `docs/paycore-entegrasyon.md` güncel.

## Kabul kriterleri

- **Yerel kuru koşu (sunucu olmadan, `--network none`):** sentetik küçük bir "PayCore benzeri" raw ağacı (depoda, `data/samples/paycore-like/`; gerçek PayCore verisi yok) `ingest-raw` ile içeri alınır; ikinci koşu `created 0`; bir soru kaynaklı cevap verir (`FAKE_LLM`/`fake-llm`).
- Runbook'taki her komut, yerel `--network none` ortamda (ağ gerektirenler hariç, NOT_RUN gerekçeli) en az kuru çalıştırılır ya da `--help`/dry-run ile doğrulanır; doğrulanamayan adım runbook'ta "kullanıcı ortamında doğrulanır" diye işaretlenir.
- `docker compose -f compose.yml -f compose.ffcore.yml config` hatasız; toplam `mem_limit` ≤ fiziksel bellek − OS payı (değerler `bellek.md`'de).
- Manifest: imaj arşivi SHA-256'ları `images.txt` ile birebir; `load` sonrası doğrulama betiği.
- Güvenlik: `.env` yazılmaz, secret yok, Jira yazma kapısı kapalı (test), korpus mount'u salt okunur, ingest log/rapor kişi verisi/ham içerik yazmaz.
- Brief'teki hiçbir adım ajanın sunucuya bağlanmasını gerektirmez.

## Kapsam dışı

Open WebUI entegrasyonu (06b sonrası), gerçek model ölçümünün kendisi (kullanıcı), 04b (rewrite, DuckDB→Postgres göçü), kişi verisi guard'ı 08 tam, kapalı ağ paketlemenin tamamı (12), GPU yolu.

## Güvenlik şartları (danışman görüşü, 1 Kasım 2026; bağlayıcı)

1. **PRSIM reddi:** `ingest-raw --sources` PRSIM içeren kaynak verirse CLI reddeder (`prsim_requires_ner`, KARARLAR karar 5); 08 tam gelince açılır. Confluence/Jira için de kişi verisi olası: PayCore eşleme betiği yazar/atanan/yorum yazarı/sayfa sahibi alanlarını metne **katmaz** (yalnız başlık, gövde, etiket). Ingest'te 08-lite regex PII `ingest` kipinde **maskeleme zorunlu** (e-posta, telefon, TC, IBAN, kart); ad-soyad NER'siz yakalanamaz → runbook'ta "bilinen sınır". Rapor yalnız sayı (tür başına maskelenen adet).
2. **Yol sınırı:** `--raw-dir` altında `realpath` ile çözülen her dosya taban içinde (symlink ve `..` reddi, `path_outside_base`), dosya boyutu üst sınırı (04a kapıları referans), mount `:ro`, konteyner kullanıcısı root değil, CLI raw dizinine hiçbir şey yazmaz (test). Hata loglarında dosya yolu evet, içerik hayır.
3. **Çapa depoda:** `deploy/offline/images.txt` imaj registry digest'lerini (BLOCKERS 109) ve model ağırlıkları için HF revision commit + dosya SHA-256'larını FFCore git deposunda tutar; sunucuda `load` sonrası `docker image inspect --format '{{.RepoDigests}}'` ve dosya hash'leri **depodaki** listeyle karşılaştırılır (arşivle gelen manifest değil: bütünlük sağlar, kaynak doğrulamaz). İmza (cosign/GPG) 12'de; runbook "taşıma medyası kullanıcı elinde" varsayımını yazar.
4. **`GUARDRAIL_EGRESS_ENABLED=false` YAPILMAZ** (30 Ekim kullanıcı onaylı "yerleşik default egress PII kuralı her profilde enforce", 6deb0c1). Gecikme sorun olursa kullanıcıya A/B ile gelinir, sessizce kapatılmaz (ARCH-13). Runbook sağlık kontrol listesi: `OFFLINE=true`, `EGRESS_ALLOWLIST` boş, `FFCORE_TEST_HOOKS=0`, `RETENTION_DRY_RUN=true`, `RETENTION_AUDIT_DROP_ENABLED=false`, Jira yazma kapısı kapalı (test); `SERVICE_TOKEN`, OBO/JWT anahtarları ve ilk süperadmin parolası **sunucuda kullanıcı tarafından üretilir**, pakette secret yok; SQL asistanı yalnız sentetik demo DB'ye ve salt okunur rolle bağlı (PayCore'un gerçek DB'sine değil); ingest öncesi Postgres volume yedek komutu; Langfuse ve audit yerelde.
5. **S1 raporu depoya girmez:** `make eval`, `DATASET` depo dışındaysa çıktıyı varsayılan olarak depo dışına yazar (`EVAL_OUT`, ör. `/var/lib/ffcore/eval`; depo içi yol verilirse `eval/results/` zorunlu); kapıya tek kontrol: `git ls-files eval/results | wc -l` = 0 ve S1 dosya adı deseni `git grep` boş; sunucudaki FFCore checkout'unda push yetkisi yok (runbook). Özet (yüzde, süre, aşama teşhis sayıları) kullanıcı **elle** PLAN/plan-13 tablosuna taşır; soru metni taşınmaz.

## Korpus kapsamı ve ölçüm düzeni (kullanıcı kararı C + danışman görüşü, 1 Kasım 2026; bağlayıcı)

Ayrıntı KARARLAR "M3 korpus kapsamı". Pakete etkisi: (1) `ingest-raw` **manifest** üretir (kaynak adı, belge sayısı, parça sayısı, ingest tarihi, raw manifest SHA-256) ve `m3_preflight`/rapor başına yazar; (2) `--limit` aşama 0 dilimi içindir (rapor "pipeline kanıtı" etiketli, kabul değil); (3) S1'in PRSIM'e dayanan soruları `make eval`'da `--exclude-sources prsim` (ya da eşdeğer) ile **dışarıda** bırakılır, rapor "S1-PRSIM'siz n/50" yazar ve `m3-gate-check` kabulü manifest tam + `failed/timeout = 0` şartına bağlar; (4) runbook ölçüm düzenini yazar: ingest/ölçüm ayrı pencere, PayCore yükü yok, aynı Ollama ayarları, ısınma ayrı, `uptime`/RAM kaydı, taban önce manifestle alınır (iki kez gerekirse tam + PRSIM'siz).

## PRSIM kararı (kullanıcı kararı A, D sınıfı, 1 Kasım 2026; önceki "PRSIM hariç" bölümlerin yerine geçer)

Korpus manifesti: **`ocr` + `prsim`**; kapsam yalnız M3 ölçümü, PayCore sunucusu, `airgap`. `ingest-raw` PRSIM'i yalnız açık bayrakla alır (`--accept-personnel-data`, bayrak yokken `prsim_requires_ner` reddi kalır) ve KARARLAR "PRSIM M3 ölçümüne girer" korumalarını (a-g) uygular: yapısal kişi alanları ve `[~kullanıcı]`/`@ad`/imza izleri eşleme betiğinde temizlenir, regex PII maskesi zorunlu, gövdedeki personel adı maskelenmez (bilinen sınır, runbook), ölçüm sonrası temizlik komut listesi runbook'ta, eval raporu depo dışında. **Müşteri/kart sahibi verisi görülürse** (maskelenen kart/IBAN/TC sayısı beklenmedik yüksek ya da örnek bulunursa) ingest durur ve işçi KAYIT-TALEBI + koordinatöre bildirir. S1 kabulü 50/50; `--exclude-sources` PRSIM dışlaması bu paketin kabul koşusunda kullanılmaz (yalnız yardımcı seçenek olarak kalır).
