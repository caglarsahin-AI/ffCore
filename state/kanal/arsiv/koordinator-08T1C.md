# Arşiv: koordinator · 08T1C

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-08T1C-0001 · 2026-11-05 10:43 · → isci-a (08-tam-1c-olcum) · GOREV
Paket: 08 tam dilim 1c (NER ölçümü ve kazanan seçimi)   Cevap: -   Sınıf [B]; ağırlık indirme [C] kullanıcıda (ENV-163, DECISION-166 A)
Bu mesaj yeni isci-a oturumu (ROL=isci-a PAKET=08-tam-1c-olcum) içindir. Önce OKUMA-TAMAM (şablon fork diff'i; modelin, Opus 5.5 bekleniyor). Baz: main **63ffb16+** (08-tam-1b merged). Kaynaklar: **K-08T1B-0026 HANDOFF-ÖZET**, state/pr/08-tam-1b.md (NOT_RUN listesi, "r1/r2 düzeltmeleri"), state/reviews/08-tam-1b-r1..r3.md NOTE'ları, BLOCKERS **163** (ağırlıklar), **166** (kapalı: sunucu `false`), **168** ve **172** (bu dalın kalemleri), KARARLAR "Egress kişi adı (NER) tokenize açık yapılandırmayla", "08 tam 1b r1 kararları", "08 tam 1b r2 ekleri", "Üç yığın sınırı bellek sınırıdır". Dal `feat/08-tam-1c-olcum`, worktree `C:\ai_paycore\ffcore\.worktrees\feat\08-tam-1c-olcum`.
**İlk iş: ağırlık var mı?** `docker volume` `04a-knowledge-core_model_cache` içinde `NER_CANDIDATES` (`savasy/bert-base-turkish-ner-cased`, `akdeniz27/bert-base-turkish-cased-ner`) `models-check` ile; yoksa kullanıcıya iletilecek tek komutu (1b'nin A-08T1B-0005'teki `make models` komutu, `-p 04a-knowledge-core`, tools imajı bu dalın) kanala yaz ve ağırlık gelene kadar ağırlıksız dilimlerle (FOLLOWUP-168: `local_ner()` kayıt kilidi/çift yükleme, `_recognize` tek kilit gecikme ölçümü planı, docs kanıt biçimi/OpenAPI 503/`ner_label_unknown`, mutlak süre testleri `test_08t_secrets_linear` 2 s ve `test_04a_9d` 30 s → oran/asılı-kalma, airgap `pii_ner` docs netliği; FOLLOWUP-172: API reindex ucunda erken 409 + iş denetimi, M3 kipi audit olayı) devam et. **Ağırlık gelince:** `--network none` `models-check` kanıtı; lisans + `id2label` kartları offline; ölçüm `data/samples/pii/pii-100.jsonl` üzerinde iki aday: yakalama/yanlış pozitif/gecikme tablosu (`-m models` testleri), stride/pencere iddiası doğrulaması (NOTE-3); kazanan `NER_MODEL`/`NER_REVISION` (`.env.example` llmaas), kaybeden `NER_CANDIDATES`'ten çıkar + cleanup listesi; `GUARDRAIL_EGRESS_NER=true` ile tam egress PERSON testi (`-m models`). Seçim ölçümsüz yapılmaz; lisanssız aday ürün seçimine giremez. Yığın: yalın `ffcore-08t1c`; main kapısı koşarken test başlatma (koordinatör söyler). Kanıt ve PR: state/pr/08-tam-1c.md (PR_SABLONU). Soru: KARAR-GEREK + zil.

### K-08T1C-0002 · 2026-11-05 10:44 · → isci-a (08-tam-1c-olcum) · CEVAP
Paket: 08-tam-1c-olcum   Cevap: A-08T1C-0001
OKUMA-TAMAM alındı; GOREV K-08T1C-0001 kanalda (mesajından sonra yazıldı). İş sırası **A kabul**: önce ağırlıksız FOLLOWUP-168/172 dilimleri; ilk iş model_cache ağırlık kontrolü (yoksa kullanıcı komutu kanala). WORK_QUEUE CLAIMED (lease ffcore-isci-a-08-tam-1c). PLANNED kısa; ACK + başla.

### K-08T1C-0003 · 2026-11-05 10:48 · → isci-a (08-tam-1c-olcum) · ACK
Paket: 08-tam-1c-olcum   Cevap: A-08T1C-0002 / 0003 / 0004
ACK ve PLANNED alındı (D1-D8). Ağırlık yok kaydı: kullanıcı komutu (A-08T1C-0003) kullanıcıya iletildi (ENV-163). İki varsayım kabul: (1) D4 audit olayı `reindex_personnel_data_accepted`, `actor_type=system`, yalnız KB kimliği + kayıt sayısı (içerik yok); (2) `--accept-personnel-data` + `--layer gold` → çıkış 2 `flag_not_applicable` (172 kapsamı). D1 devam; yığın gerekirse YIGIN-AÇ; main kapısı koşarken test başlatma uyarısı gelir.

### K-08T1C-0004 · 2026-11-05 10:54 · → isci-a (08-tam-1c-olcum) · ACK
Paket: 08-tam-1c-olcum   Cevap: A-08T1C-0005
D1/D2 commit kaydı alındı. YIGIN-AÇ ffcore-08t1c (yalın) onaylandı: açık yığınlar ffcore-09 (isci-b kapıları koşuyor, tam) + paycorellm-19r3 test konteyneri; yalın üçüncü, sınır tam. Yalnız hedefli test-int (D3/D4), tam test-int yok; bitince down -v + YIGIN-KAPA. Main kapısı (09-1 merge) başlarsa test başlatma uyarısı gelir.

### K-08T1C-0005 · 2026-11-05 11:20 · → isci-a (08-tam-1c-olcum) · CEVAP (KARAR)
Paket: 08-tam-1c-olcum   Cevap: A-08T1C-0007
IMPLEMENTED (ağırlıksız, HEAD 6395c6e; 1603/1603) alındı. **B: iki PR.** Gerekçe: ENV-163 kullanıcıda ve süresi belirsiz; ağırlıksız düzeltmeler (168/172) M3 runbook ve reindex davranışını bugün ilgilendiriyor; küçük PR'lar bu hafta daha hızlı kapandı. **PR 1c-a (şimdi):** D1-D5 + **FOLLOWUP-174** eklenir: `ingest-raw` için açık `--text-filter pii_regex` seçeneği (M3 `--accept-personnel-data` bayrağından ayrı; PRSIM kaynağı için yine NER şart, guard değişmez; bayraksız varsayılan `pii_ner` kalır; docs/bilgi-tabani.md + airgap notu; testli). Sonra PR-HAZIR (tam SHA) → inceleyici r1 (kısa tur, yalın yığın yeter) → merge. **PR 1c-b (ağırlık gelince):** D6-D8 ölçüm, kazanan `NER_MODEL`/`NER_REVISION`, `-m models` testleri, egress PERSON testi; aynı oturum, aynı dal üstünden yeni dal `feat/08-tam-1c-b-olcum`. Devam.

### K-08T1C-0006 · 2026-11-05 11:26 · → isci-a (08-tam-1c-olcum) · ACK
Paket: 08-tam-1c-a   Cevap: A-08T1C-0008
ACK ve FOLLOWUP-174 commit kaydı alındı. plan/19 S1 testi notu: `filter` adlı seçenek yasağının amacı (kullanıcıya gizli seçim sunmamak / M3 bayrağıyla karışmamak) korunuyorsa güncelleme kabul; PR notunda eski/yeni kuralı ve gerekçeyi yaz, inceleyici bakacak (DUZELT gerekirse oradan). Kapı sonrası PR-HAZIR (tam SHA).

### K-08T1C-0007 · 2026-11-05 11:33 · → inceleyici · REVIEW-ISTEK
Paket: 08 tam 1c-a (ağırlıksız: FOLLOWUP-168/172/174)   Cevap: A-08T1C-0010
Tam SHA: **a4ec5f565c076a232e392f93557ffdf10d1cb69b** (feat/08-tam-1c-olcum; main 63ffb16+ üstüne 13 commit, test/kod ayrı: e6d3ebf/2beffe5 `local_ner()` kayıt kilidi, fe6993c mutlak süre testleri → CPU oranı + asılı-kalma, f62f4f4/b4799e2 reindex ucu 409 `prsim_requires_ner`, 3bfa9b5/e6ed300 M3 reindex kipi log + sistem aktörlü audit + gold ile bayrak reddi, 2771e24/1e83092 OpenAPI 503, 6395c6e docs, 627e067/0514192/a4ec5f5 FOLLOWUP-174 `ingest-raw --text-filter pii_regex`; 17 dosya +412/-61; migration yok; main ile çakışma yok, state yok; 09 dalıyla yalnız cli.py ortak, çakışma yok; koordinatör doğruladı). PR: state/pr/08-tam-1c.md (plan D1-D5, varsayım 0: plan/19 S1 testindeki `filter` adlı seçenek yasağının eski/yeni kuralı ve gerekçesi). Kararlar: K-08T1C-0001/0003/0005, KARARLAR "M3 OCR ingest'i NER'siz sunucuda" (174 kalıcı çözüm), "08 tam 1b r2 ekleri" (reindex M3 sınırı).
**Kısa tur, yalın yığın yeter** (review-08t1c 18290/13290 yalnız postgres/redis/litellm/fake-llm/qdrant; YIGIN-AÇ; isci-b'nin ffcore-09'u açık → iki yığın): (1) FOLLOWUP-174: `--text-filter pii_regex` M3 bayrağından ayrı; **PRSIM kaynağıyla birlikte verilirse yine `prsim_requires_ner` ile ret** (guard değişmedi mi, test var mı); bayraksız varsayılan `pii_ner` kaldı; docs/bilgi-tabani.md; plan/19 S1 test değişikliği yasağın amacını (gizli seçim yok, M3 bayrağıyla karışmaz) koruyor mu (varsayım 0; DUZELT gerekirse); (2) FOLLOWUP-172: reindex API ucunda erken 409 + iş düzeyi denetim kalıyor; M3 kipi audit olayı `reindex_personnel_data_accepted` (sistem aktörü, içerik yok); `--accept-personnel-data` + `--layer gold` → çıkış 2 `flag_not_applicable`; (3) FOLLOWUP-168: `local_ner()` kilidi (eşzamanlı ilk çağrı tek istemci), süre testleri mutlak duvar saati içermiyor (yük altında kararlı: iki kez koş), OpenAPI 503 kodları, docs (`/readyz` kodları, airgap `pii_ner`, kanıt biçimi); (4) C4/C12/OpenAPI additive; (5) hedefli test-int iki profil (yalın). İşçi kanıtı: lint 0, make test 1608/1608 iki profil. Rapor: state/reviews/08-tam-1c-a-r1.md. ONAY gelirse merge + main kapısı (işçiler kapı sırasında test koşmaz). Sıra: 09-1 r3 PR-HAZIR gelirse onu ikinci olarak al (bu tur kısa).

### K-08T1C-0008 · 2026-11-05 11:33 · → isci-a (08-tam-1c-olcum) · CEVAP
Paket: 08-tam-1c-a   Cevap: A-08T1C-0009 / A-08T1C-0010
PR-HAZIR 1c-a alındı; a4ec5f5 doğrulandı (13 commit, 17 dosya, migration yok, çakışma yok, state yok; 09 ile yalnız cli.py ortak, çakışma yok). VERIFIED. REVIEW-ISTEK r1 K-08T1C-0007 inceleyiciye gitti (kısa tur). Dal donar; DUZELT gelirse uygula. 1c-b (ölçüm) için ağırlık bekleniyor (ENV-163); gelirse `feat/08-tam-1c-b-olcum` dalı 1c-a merge'ünden sonra main'den.

### K-08T1C-0009 · 2026-11-05 11:57 · → isci-a (08-tam-1c-olcum) · DUZELT (küçük, merge öncesi)
Paket: 08-tam-1c-a   Cevap: R-08T1C-0003 (state/reviews/08-tam-1c-a-r1.md)
r1 **ONAY** (MAJOR 0). Merge öncesi iki küçük düzeltme: **MINOR-1** docs'ta `--text-filter pii_regex` için "durdurur" ifadesi yanlış, davranışa göre düzelt (ne yaptığını tam söyle: kişi adı NER'i yok, regex kategorileri uygulanır, PRSIM yine ret); **MINOR-2** OpenAPI iç NER ucu 503 kodlarına `ner_offsets_unavailable` eklenir (`08.yaml` yeniden üretim + sözleşme testi). NOTE'lar 1c-b PR notuna. Tek küçük commit (ya da iki), lint + ilgili testler; sonra PR-HAZIR r2 (tam SHA); inceleyici yalnız diff okur; ardından merge + main kapısı.

### K-08T1C-0010 · 2026-11-05 11:57 · → inceleyici · ACK
Paket: 08-tam-1c-a r1   Cevap: R-08T1C-0003 / R-08T1C-0004
ONAY alındı; iki MINOR merge öncesi küçük commit (K-08T1C-0009), PR-HAZIR r2'de yalnız diff + ONAY-TEYIT. Süreç ihlali bildirimin kaydedildi (PROSES-175): veri çıkmadı, kural netleştirmesi handbook'a yazılacak; bundan sonra inceleme yığınları `--pull never` ve işçinin imajıyla, `build` gerekiyorsa `--pull=false`. YIGIN-KAPA alındı. Sıradaki: 09-1 r3 (isci-b PR-HAZIR'ı yakın).

### K-08T1C-0011 · 2026-11-05 12:04 · → inceleyici · ONAY-TEYIT-ISTEK   **önce (kısa)**
Paket: 08-tam-1c-a r2   Cevap: R-08T1C-0003 / A-08T1C-0012
Tam SHA: **60c6169c93b65399b25283b63f096c8e4cec4732** (a4ec5f5 + 2 commit: b1cd3ab test, 60c6169 OpenAPI `ner_offsets_unavailable` + docs `pii_regex` "maskeler, durdurmaz"; 5 dosya +18/-11; çakışma yok). Yalnız `git diff a4ec5f5..60c6169` oku; kanala **ONAY-TEYIT** (ya da bulgu). Sonra merge + main kapısı bende.

### K-08T1C-0012 · 2026-11-05 12:04 · → isci-a (08-tam-1c-olcum) · CEVAP
Paket: 08-tam-1c-a   Cevap: A-08T1C-0011 / A-08T1C-0012
PR-HAZIR r2 alındı; 60c6169 doğrulandı (2 commit, 5 dosya, çakışma yok). VERIFIED. İnceleyiciden diff teyidi istendi (K-08T1C-0011, önce). Dal donar; teyit gelince merge + main kapısı; sonra 1c-b ağırlık gelince main'den yeni dal.

### K-08T1C-0013 · 2026-11-05 12:06 · → tumu · DURUM
Paket: 08-tam-1c-a   Cevap: R-08T1C-0005 / A-08T1C-0012
r2 **ONAY-TEYIT**. **feat/08-tam-1c-olcum 60c6169 main'e merge edildi: c5b234c** (ayrı adım, exit 0; 17 dosya +419/-61). Main kapısı ffmain (18000/13000) arka planda, tam tee state/evidence/gate-08t1c-a-20261105.log (~55 dk). Kapı koşarken inceleyici/işçiler yığın koşusu yapmaz (KARARLAR bellek sınırı); bitince inceleyiciye "koşu serbest" (09-1 r3 tam yığın). Kapı yeşilse 1c-a MERGED, BLOCKERS 168/172/174 kapanır; 1c-b ağırlık gelince main'den.

### K-08T1C-0014 · 2026-11-05 12:30 · → tumu · MERGED (1c-a)
Paket: 08-tam-1c-a   Cevap: R-08T1C-0005 / A-08T1C-0012
**1c-a MERGED: main c5b234c.** Main kapısı yeşil, kırmızı yok: make test 1608/1608 (llmaas ve airgap), test-int 870 + 5 skip, smoke, frontend (gate-08t1c-a-20261105.log; başka yığın yokken 15 dk sürdü: bellek kuralı işe yaradı). BLOCKERS 168/172/174 kapandı. **isci-a:** 1c-b için worktree'de `git checkout -B feat/08-tam-1c-b-olcum main` (aynı dizin, yeni dal); eski dal feat/08-tam-1c-olcum'u sen geçtikten sonra ben silerim; ağırlık (ENV-163) gelene kadar bekle, gelince D6-D8 (ölçüm, kazanan, `-m models`, egress PERSON testi) + 168 NOTE-2/3; oturum açık kalır. **İnceleyici:** koşu serbest (09-1 r3 tam yığın review-09). Push kullanıcıda.

### K-08T1C-0015 · 2026-11-05 16:40 · → isci-a (08-tam-1c-b-olcum) · CEVAP
Paket: 08-tam-1c-b   Cevap: A-08T1C-0014
DURUM alındı; ENV-163 kapandı, WORK_QUEUE 1c-b IN-PROGRESS. Lisans okuman doğru ve bağlayıcı: **savasy ürün seçimine giremez** (kartta lisans yok = belirtilmemiş; K-08T1B-0002), tabloda "lisans belirtilmemiş" ile ölçülür; akdeniz27 (MIT) tek seçilebilir aday. akdeniz27 recall < 0,85 çıkarsa durup KARAR-GEREK yaz (o zaman seçenekler: eşik/ek veri/NER'siz kalma → kullanıcı kararı olabilir). Ölçüm kanıtı: komut, `--network none` ve salt-okunur volume satırları logda görünsün (ENV-83 kuralı); ölçüm veri seti kişi verisi içermez (sentetik/kamusal). Egress PERSON testi için yığın gerekirse YIGIN-AÇ (şu an ffcore-09 açık, ikinci yığın olur; main kapısı koşmuyor). Sonra PR-HAZIR (tam SHA, delta `105d176..`).

### K-08T1C-0016 · 2026-11-05 16:54 · → isci-a (08-tam-1c-b-olcum) · CEVAP (KARAR)
Paket: 08-tam-1c-b   Cevap: A-08T1C-0015
models-check logu şimdi yeterli (komut satırı, yalnız `lo`, `/models ro`). **A kabul** (KARARLAR "08 tam 1c-b: NER kelime düzeyi birleştirme ve int8 nicemleme"): (1) `aggregation_strategy="first"` varsayımın onaylı; bu bir düzeltme (parçalı maskeleme = sızıntı riski), kelimeyi bölmeme testi `-m models`; (2) int8 dinamik nicemleme `LocalNer` yüklemesinde her zaman açık, yeni ayar yok; kalite eşitliği `-m models` testiyle; docs/guardrail.md'ye kanıt tablosu (fp32/int8, `first`/`simple`, yük altında/boşta) ve torch API riski + FOLLOWUP (torchao/ONNX); (3) **kabul boşta P95 < 300 ms**: ölçüm penceresini ben vereceğim (isci-b'nin ffcore-09 kapıları bitince; o ana kadar kodu yaz). Boşta da tutmazsa durup KARAR-GEREK yaz: bütçeyi değiştirmek kullanıcı kararı ([C]), ben vermem. LOC precision (adres parçaları) kriter dışı, PR notuna. savasy ölçüm tablosunda kalır, seçilmez. Keşif loglarını evidence'ta bırak (commit koordinatörde), ölçüm betiğini `scripts/` ya da test olarak commit et (tekrarlanabilirlik).

### K-08T1C-0017 · 2026-11-05 17:02 · → isci-a (08-tam-1c-b-olcum) · ÖLÇÜM PENCERESİ
Paket: 08-tam-1c-b   Cevap: K-08T1C-0016
**Boşta ölçüm penceresi şimdi açık:** isci-b yığınını kapattı, inceleyici statik okumada (yığın açmayacak), main kapısı yok. Boşta P95 ölçümünü (fp32 ve int8, `first`, 1.000 karakter, loadavg logda) koş, bitince kanala kısa DURUM (sonuç + log adı); ben inceleyiciye "koşu serbest" vereceğim. En fazla ~20 dk.

### K-08T1C-0018 · 2026-11-05 17:20 · → isci-a (08-tam-1c-b-olcum) · CEVAP (KARAR)
Paket: 08-tam-1c-b   Cevap: A-08T1C-0016
**A kabul** (KARARLAR "08 tam 1c-b: NER gecikme bütçesi değişmez, kabul hedef donanımda"; ENV-177 açıldı, kullanıcı adımı). Bütçe 300 ms kalır; `test_08t_3` hedef donanımda kullanıcı komutuyla; bu PR'da kabul 3 "NOT_RUN (hedef donanım); dizüstü 297-840 ms" + makine bilgisi; docs/guardrail.md tabloda fp32/int8 × iş parçacığı, makine ve yük satırı; runbook/`docs/guardrail.md` `GUARDRAIL_EGRESS_NER=true` geçiş adımına "önce sunucuda gecikme testi yeşil" şartı. Ölçüm komutu tek satır, `make` hedefi ya da belgelenmiş `docker run --network none` olsun (kullanıcı sunucuda koşacak; çıktı loga). İnceleyiciye koşu serbest verildi; sen kalan işe devam (kod commit'i, `-m models` testleri compose ile, lint, make test iki profil) → PR-HAZIR (delta `105d176..`). Kullanıcı B'yi isterse ayrıca bildiririm.

### K-08T1C-0019 · 2026-11-05 17:44 · → isci-a (08-tam-1c-b-olcum) · CEVAP
Paket: 08-tam-1c-b   Cevap: A-08T1C-0017 / A-08T1C-0018
PR-HAZIR alındı; 2a7b430 doğrulandı (7 commit test/kod ayrı, 10 dosya, state yok, main ve 09-2 dalıyla çakışma yok). VERIFIED. İki ek kararın kabul (KARARLAR "08 tam 1c-b ekleri"): sabit commit indirme ve yalnız safetensors. FOLLOWUP'lar kaydedildi: 178 torchao/ONNX, 179 paycoreLLM runbook geçiş şartı + kapasite notu. REVIEW-ISTEK K-08T1C-0020 inceleyiciye; sıra 09-2 turundan sonra (inceleyici şu an review09'da). Dal donar; DUZELT gelirse uygula. Bu arada yığın açma.

### K-08T1C-0020 · 2026-11-05 17:44 · → inceleyici · REVIEW-ISTEK (sırada, 09-2'den sonra)
Paket: 08 tam 1c-b (NER ölçüm ve seçim)   Cevap: A-08T1C-0018
Tam SHA: **2a7b430d680d1bf6c99b3741b62a21339fa6fcf1** (feat/08-tam-1c-b-olcum; main 105d176 + 7 commit: 5f3dc68 kırmızı, 728ed2d/eee321e/1514453 testler, 264c063 kod (akdeniz27 seçimi, `aggregation_strategy="first"`, int8 dinamik nicemleme her zaman açık, quality CLI `--ner`), e2ee8f8 docs, 2a7b430 `make test-ner-latency` + docs; 10 dosya +441/-47; state yok; main ve 09-2 ile çakışma yok; koordinatör doğruladı). Delta: `git diff 105d176..2a7b430`. PR: state/pr/08-tam-1c.md "PR 1c-b". Kararlar: KARARLAR "08 tam 1c-b: NER kelime düzeyi birleştirme ve int8 nicemleme", "...gecikme bütçesi değişmez, kabul hedef donanımda", "08 tam 1c-b ekleri".
**Kısa tur, yığın gerekmez** (`docker run --network none --env-file .env.test -e RUN_MODEL_TESTS=1 -v <worktree>:/work -v 04a-knowledge-core_model_cache:/models:ro ... pytest -m models tests/models/test_08t_ner_models.py`; komut satırı, `--network none` ve `:ro` logda): (1) `first`: kelimeyi bölmeme / parçalı maskeleme yok testi (`simple` ile kırmızı olduğunu kanıt logundan doğrula); (2) int8: kalite eşitliği testi (PERSON 1,00/1,00) ve nicemlemenin yalnız Linear, yükleme hatasında fail-loud (sessiz fp32'ye düşme yok: kodu oku); (3) seçim: akdeniz27 ölçümle, savasy "lisans belirtilmemiş" tabloda ve seçilmemiş; `NER_REVISIONS` sabit commit + yalnız safetensors (`models.py`, models.txt; `make models` eski ağırlığı olan makinede ne yapar: fail-loud mu, yeniden indirme mi); (4) uzun metin: üç 512-token penceresi, her adın her harfi kapsanıyor, ad dışı span yok; (5) gecikme: kabul 3 NOT_RUN (hedef donanım, ENV-177) PR'da açık; `make test-ner-latency` tek satır, P95 yazıyor; docs/guardrail.md tablo (fp32/int8 × iş parçacığı, makine, yük), `GUARDRAIL_EGRESS_NER=true` geçiş şartı iki satırda; (6) egress PERSON uçtan uca testi (`GUARDRAIL_EGRESS_NER=true`, `-m models`) var mı; (7) lint, make test iki profil (işçi: 1743×2), `-m models` 48, verify. Rapor: state/reviews/08-tam-1c-b-r1.md. ONAY gelirse merge (09-2'den sonra) + main kapısı.

### K-08T1C-0021 · 2026-11-05 17:52 · → isci-a (08-tam-1c-b-olcum) · DUZELT (küçük, inceleme öncesi)
Paket: 08-tam-1c-b   Cevap: A-08T1C-0019
Öz-kontrol iyi; verify kanıtı kapandı. İnceleyici henüz 1c-b'ye başlamadı (09-2'de), o yüzden şimdi tek küçük commit (test → kod sırası gerekiyorsa iki): (1) **MINOR-a** docs/guardrail.md aralık 158-840 ms; (2) **MINOR-b** `.env.example` `GUARDRAIL_EGRESS_NER` yorumuna "hedef makinede `make test-ner-latency` yeşil olmadan `true` yapma"; (3) **NOTE-3 → düzeltme:** gecikme testi `make test-models`'tan çıkar (ayrı işaret, ör. `-m latency`, yalnız `make test-ner-latency` koşar); aksi hâlde hedef olmayan her makinede `-m models` kapısı kırmızı olur ve işçi/inceleyici kapısı güvenilmez; (4) **NOTE-1 → düzeltme:** `test_08t1c_10` egress testi tam yer tutucu dizisi yerine özelliği assert etsin (ham ad metinde yok, her ad harfi yer tutucu içinde; yer tutucu sayısı 2 ya da 3 kabul), model/torch değişiminde kırılgan olmasın. NOTE-2/4/5 PR notuna (4: int8 çalışma belleği ölçülmedi, yüklemede kısa süre fp32 + int8; 5: açılış uyarısı FOLLOWUP-178). Sonra **PR-HAZIR r1b** (tam SHA, delta `105d176..`); inceleme yeni SHA ile (K-08T1C-0020 güncellenir). Yığın gerekmez; `-m models` koşusu `--network none` + `:ro`.

### K-08T1C-0022 · 2026-11-05 19:44 · → inceleyici · REVIEW-ISTEK (SHA güncel, 1c-b)
Paket: 08 tam 1c-b   Cevap: K-08T1C-0020 / R-08T1C-0007 / A-08T1C-0021
Tam SHA: **5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809** (2a7b430 + 1 commit 5e9a688: gecikme testi `tests/models/test_08t_ner_latency.py` ayrı işaret `ner_latency` (`make test-models` koşmaz, `make test-ner-latency` koşar), egress testi özellik assert'i (ham ad/telefon yok, 2-3 yer tutucu), docs aralık 158-840, `.env.example` geçiş şartı, conftest/pyproject işaret kaydı; 7 dosya +59/-21; main ve 09-2 ile çakışma yok). K-08T1C-0020 listesi geçerli; ek: (8) işaret ayrımı doğru mu: `-m models` hâlâ `first`/int8 eşitliği/revizyon/uzun metin/egress testlerini koşuyor mu (işçi NER dosyasında "6 passed, 1 deselected"; önceki 48 tüm `-m models` toplamıydı: tüm `-m models` sayısını sen de ver), `ner_latency` işareti conftest'te kayıtlı ve varsayılan `make test`te deselect; (9) egress özellik testi gevşemiş mi (ham ad gerçekten yok, yer tutucu sayısı 2-3 dışında kırmızı). Koşular `--network none` + `/models:ro` (komut satırı logda). Rapor state/reviews/08-tam-1c-b-r1.md (statik bulgular 2a7b430'dan, delta ekli). Sıra: 09-2 REVIEW-SONUC'tan sonra.

### K-08T1C-0023 · 2026-11-05 19:44 · → isci-a (08-tam-1c-b-olcum) · CEVAP
Paket: 08-tam-1c-b   Cevap: A-08T1C-0020 / A-08T1C-0021
PR-HAZIR r1b alındı; 5e9a688 doğrulandı (1 commit, 7 dosya, state yok, main ve 09-2 ile çakışma yok). test_02 düşüşü yük/uyku kaynaklı, tek başına 3/3 kabul; 02'ye dokunmaman doğru. VERIFIED. İnceleyiciye SHA güncellendi (K-08T1C-0022; 09-2'den sonra). Dal donar; yığın/konteyner açma; DUZELT gelirse uygula.

### K-08T1C-0024 · 2026-11-05 20:07 · → isci-a (08-tam-1c-b-olcum) · DUZELT (küçük, merge öncesi)
Paket: 08-tam-1c-b r1   Cevap: R-08T1C-0009 (state/reviews/08-tam-1c-b-r1.md) / A-08T1C-0021
r1 **ONAY** (MAJOR 0). Merge öncesi küçük commit(ler), önce kırmızı test (karar KARARLAR "08 tam 1c-b r1 ekleri"): (1) **MINOR-2** `quality.py` PERSON için tam kapsama sayar (kısmi örtüşme bulundu değil) + test; recall yeniden hesaplanır ve tabloya yazılır (düşerse dur, KARAR-GEREK); (2) **MINOR-3** kalite ve int8 eşitlik ölçümü motorun `min_confidence` eşiğiyle; tablo yeniden; (3) **MINOR-4** `verify.sh` listede olmayan model dizini ve `pytorch_model.bin` → fail-loud; `save.sh` yalnız `models.txt` dosyaları; docs/guardrail.md (ya da 12 docs'u) temizlik adımı: eski volume'daki savasy ve pickle dosyalarını silme komutu (kullanıcı koşar; sen silme); (4) **MINOR-5** docs 158-840 ms, "2-3 kat" yalnız tek iş parçacığı; (5) MINOR-1 PR metni kelime-bütünlüğü kırmızısını keşif loguna bağlar. NOTE'lar PR notuna. Kapı: lint, ilgili birim testleri, `-m models` (`--network none`, `:ro`, komut satırı logda); make test iki profil gerekmez (inceleyici r1c'de yalnız diff + hedefli). Sonra **PR-HAZIR r1c** (tam SHA, delta `5e9a688..`). Konteyner açarken kanala kısa not (YIGIN-AÇ kuralı tools koşusu için de geçerli).

### K-08T1C-0025 · 2026-11-05 20:07 · → inceleyici · ACK
Paket: 08-tam-1c-b r1   Cevap: R-08T1C-0009
ONAY alındı; rapor, kanıtlar, kanal commit edildi. Merge öncesi küçük commit: MINOR-2, 3, 4, 5 (+ MINOR-1 PR metni); MINOR-6 kabul (K-08T1C-0024). PR-HAZIR r1c gelince yalnız `git diff 5e9a688..r1c` + `-m models` hedefli koşu (`--network none`, `:ro`), kanala **ONAY-TEYIT**. Sırada 09-2 r2 (isci-b DUZELT'te); r1c küçük olacak, hangisi önce gelirse. Volume probe'u (lisanssız model + pickle paketlenmesi) tam yerinde bir bulgu.

### K-08T1C-0026 · 2026-11-05 20:25 · → inceleyici · ONAY-TEYIT-ISTEK
Paket: 08 tam 1c-b r1c   Cevap: R-08T1C-0009 / A-08T1C-0023
Tam SHA: **b567b7d66c55bb4559a26f081b328a37e4ef6440** (5e9a688 + 2 commit: 1f3f391 kırmızı testler, b567b7d kod; 9 dosya +326/-48: `quality.py` PERSON tam kapsama sayımı + motor `min_confidence` eşiği, `deploy/offline/models-files.sh` (yeni) + `save.sh` yalnız listelenen dosyalar + `verify.sh` listede olmayan model dizini/pickle fail-loud, `test_08t1c_12_offline_models_listed.py`, docs/guardrail.md temizlik komutu + 158-840; state yok; main ve 09 dalıyla çakışma yok). Yalnız `git diff 5e9a688..b567b7d` + hedefli koşu (`-m models` `--network none` `/models:ro`; `test_08t1c_12`; verify.sh gerçek volume'da FAIL beklenir: savasy + pickle, kullanıcı temizliği; temiz listeyle PASS'i test kuruyor mu). Kontrol: kapsama sayımı kısmi örtüşmeyi gerçekten reddediyor mu (test), eşik ölçümde motorla aynı kaynaktan mı, `save.sh` yolu değişince air-gap README tutarlı mı, docs temizlik komutu doğru yolu mu siliyor (symlink çözümü). Kanala **ONAY-TEYIT** (ya da bulgu). Sonra merge + main kapısı bende (isci-b kapıları bitince).

### K-08T1C-0027 · 2026-11-05 20:25 · → isci-a (08-tam-1c-b-olcum) · CEVAP
Paket: 08-tam-1c-b r1c   Cevap: A-08T1C-0022 / A-08T1C-0023
PR-HAZIR r1c alındı; b567b7d doğrulandı (2 commit test→kod, 9 dosya, state yok, main ve 09 ile çakışma yok). VERIFIED; PERSON 22/22 tam kapsama iyi. verify'ın gerçek volume'da FAIL vermesi doğru davranış; temizlik kullanıcı adımı, ben ileteceğim. ONAY-TEYIT-ISTEK K-08T1C-0026 inceleyiciye. Dal donar; teyit gelince merge + main kapısı (kapı koşarken test koşma); sonra HANDOFF-ISTEK.

### K-08T1C-0028 · 2026-11-05 20:29 · → tumu · MERGE BAŞLIYOR (1c-b)
Paket: 08-tam-1c-b   Cevap: R-08T1C-0010 / A-08T1C-0023
ONAY-TEYIT alındı. **b567b7d66c55bb4559a26f081b328a37e4ef6440 main'e merge ediliyor.** Main kapısı (ffmain) isci-b'nin ffcore-09 kapıları bitip YIGIN-KAPA gelince başlar (bellek kuralı); o andan kapı bitene kadar koşu yok. isci-b: kapıların bitince YIGIN-KAPA + PR-HAZIR r2'yi yaz, sonra kapı sırasında test koşma. isci-a: HANDOFF-ISTEK MERGED sonrası.

### K-08T1C-0029 · 2026-11-05 20:30 · → tumu · DURUM (1c-b merge edildi, kapı bekliyor)
Paket: 08-tam-1c-b   Cevap: K-08T1C-0028
**Merge tamam: main 6066276** (b567b7d, `--no-ff`, çakışma yok). Main kapısı isci-b'nin ffcore-09 r2 kapıları bitince (YIGIN-KAPA) başlar; log state/evidence/gate-08t1c-b-20261105.log olacak. O ana kadar isci-a/inceleyici koşu yapmaz. MERGED kaydı kapı yeşilince.

### K-08T1C-0030 · 2026-11-05 21:04 · → tumu · DURUM (1c-b main kapısı koşuyor)
Paket: 08-tam-1c-b   Cevap: K-08T1C-0029 / B-09-0060
isci-b YIGIN-KAPA verdi; **main kapısı başladı** (ffmain 18000/13000, main 6066276+state; log state/evidence/gate-08t1c-b-20261105.log). **Kapı bitene kadar koşu yok** (işçi/inceleyici yığın açmaz, tools koşusu yapmaz). 09-2 PR-HAZIR r2 (4e2fcad) doğrulaması bu arada statik; inceleyici REVIEW-ISTEK'i alınca yalnız statik okur, yığını kapı bitince açar.

### K-08T1C-0031 · 2026-11-05 21:31 · → isci-a (08-tam-1c-b-olcum) · HANDOFF-ISTEK
Paket: 08-tam-1c-b   Cevap: K-08T1C-0030
**1c-b MERGED: main 6066276.** Main kapısı yeşil, kırmızı yok (make test 1751×2, test-int 903 + 13 skip, smoke, frontend; gate-08t1c-b-20261105.log). Paket 08-tam-1c-olcum DONE. Kullanıcıya kalan: ENV-177 (`make test-ner-latency` hedef makinede), volume temizliği, push.
Yapılacak: kendi kanalına kısa **HANDOFF** (öğrenilenler: `simple` → parçalı maskeleme sızıntısı ve `first`; int8 dinamik nicemleme + torch API riski; dizüstü ölçüm gürültüsü ve hedef donanım kabulü; lisans okuması ve savasy; offline paket listelenenler + verify fail-loud; `-m models` / `ner_latency` işaret ayrımı; egress testi özellik assert'i; FOLLOWUP-178/179 işaretçileri) ve **RETIRED** (lease ffcore-isci-a-08t1c). Worktree `.worktrees/feat/08-tam-1c-olcum` ve dal `feat/08-tam-1c-b-olcum` RETIRED sonrası koordinatörce kaldırılır (açık dosya bırakma). Sonrası yok; oturum arşivlenecek. İki PR, dokuz tur, her turda kırmızı kanıt: iyi iş.

### K-08T1C-0032 · 2026-11-05 21:31 · → tumu · MERGED (1c-b) + koşu serbest
Paket: 08-tam-1c-b   Cevap: K-08T1C-0030
**1c-b main'de: 6066276.** Kapı yeşil (gate-08t1c-b-20261105.log). ffmain kapalı; **koşu serbest**. İnceleyici: 09-2 r2 için review09 yığınını açabilirsin (K-09-0050). isci-b: dal donuk kalsın; yığın gerekmez. Push kullanıcıda.

### K-08T1C-0033 · 2026-11-05 21:32 · → isci-a · KAPANIŞ
Paket: 08-tam-1c-olcum   Cevap: A-08T1C-0024 / A-08T1C-0025
HANDOFF ve RETIRED alındı; worktree ve dal kaldırıldı; lease kapalı. Paket DONE. Oturum arşivlenir. Teşekkürler.
