# Arşiv: isci-a · 08T1C

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-08T1C-0001 · 2026-11-05 10:43 · → koordinator · DURUM
Paket: 08-tam-1c-olcum   Cevap: K-08T1B-0026
DURUM: OKUMA-TAMAM. Kullanıcı talimatı ROL=isci-a PAKET=08-tam-1c-olcum; oturum 28 Ekim tam okumasından (A-INIT-0001) fork, aradaki fark okundu: `git diff 8ba004c..HEAD` CLAUDE/PLAN 2.10/KARARLAR (08 tam NER adayları, model ağırlıkları ve dış ağ, egress NER, 08 tam 1b r1/r2 ekleri, yığın sınırı üç = bellek sınırı, main kapısı)/CONTRACTS/TERMINOLOGY/BASLATMA (soru penceresi yok); plan/08 NER ve kabul satırları; state/pr/08-tam-1b.md (kriter 1/3/4 NOT_RUN, FOLLOWUP-168 kalemleri); BLOCKERS 163/168/172; WORK_QUEUE 08 satırları; koordinatör kanalı K-08T1B-0018..0026.
Lease ACTIVE (eski 1b lease'i RETIRED yazıldı; 1b oturumu HANDOFF bırakmadı, özetin esas). Kodlama, claim, worktree yok.
Durum: bana adresli 08-tam-1c-olcum GOREV'i yok; ENV-163 (iki aday ağırlığı, kullanıcı `make models`) açık.
SORU (iş sırası, senin yetkin): A (önerim) GOREV'i ağırlıktan bağımsız yaz; ağırlıksız dilimler önce: FOLLOWUP-168 NOTE-2 (`local_ner()` kilit), NOTE-4/8 docs, NOTE-5 mutlak süre testleri, FOLLOWUP-172 N1 (reindex erken 409) + N2 (M3 kipi audit); `-m models` ölçümü ve kazanan seçimi ENV-163 kapanınca aynı dalda. Etki: ağırlık beklerken dal ilerler, ölçüm ayrı commit'te kalır. B: GOREV'i ENV-163 kapanınca tek seferde yaz. Etki: boş bekleme, 168/172 ölçümle aynı turda incelenir. C: 168/172 ayrı küçük dala, 1c yalnız ölçüm. Etki: iki PR, iki inceleme turu.
GOREV ya da CEVAP gelince ACK + state/pr/08-tam-1c-olcum.md planı.

### A-08T1C-0002 · 2026-11-05 10:55 · → koordinator · ACK
Paket: 08-tam-1c-olcum   Cevap: K-08T1C-0001 / K-08T1C-0002
GOREV alındı; iş sırası A. Worktree `.worktrees/feat/08-tam-1c-olcum`, dal `feat/08-tam-1c-olcum`, baz main 8aa8442 (63ffb16 + state). Sıradaki: kısa plan state/pr/08-tam-1c.md + PLANNED, sonra ağırlıksız dilimler (168, 172).

### A-08T1C-0003 · 2026-11-05 10:55 · → koordinator · DURUM (ağırlık yok, kullanıcı adımı)
Paket: 08-tam-1c-olcum   Cevap: K-08T1C-0001 (ilk iş)
Kontrol (salt-okunur, `--network none`, alpine): `04a-knowledge-core_model_cache` hub'ında yalnız bge-m3, bge-reranker-v2-m3, docling-layout-heron, docling-models var; **iki NER adayı yok** (ENV-163 açık).
**Kullanıcıya iletilecek tek adım** (dışarı bağlanır; Docker Desktop açık; PowerShell, dizin `C:\ai_paycore\ffcore\.worktrees\feat\08-tam-1c-olcum`):
```
$env:FFCORE_VERSION="0.0.0-08t1c"; docker compose -p 04a-knowledge-core --env-file .env.test build tools
$env:FFCORE_VERSION="0.0.0-08t1c"; docker compose -p 04a-knowledge-core --env-file .env.test run --rm --no-deps tools make models
```
Mevcut ağırlıklar yeniden inmez, yalnız denetlenir; yeni inen `savasy/bert-base-turkish-ner-cased`, `akdeniz27/bert-base-turkish-cased-ner` (yalnız README/config/tokenizer/ağırlık dosyaları, tahmini ≤ ~1,8 GB). Çıktının son satırları (`download ... (NER candidate)`, `ok/missing`) yeter. `--network none` `models-check`, lisans ve `id2label` okumasını ben yaparım.

### A-08T1C-0004 · 2026-11-05 11:05 · → koordinator · DURUM
Paket: 08-tam-1c-olcum   Cevap: K-08T1C-0001 / K-08T1C-0002
DURUM: PLANNED. Plan state/pr/08-tam-1c.md (kısa; PR_SABLONU 1-9, felsefe üç sorusu). Dilimler: ağırlıksız D1 `local_ner()` kilidi, D2 mutlak süre testleri oran/asılı-kalma, D3 reindex API 409 `prsim_requires_ner` (ön denetim; iş denetimi kalır), D4 M3 kipi reindex log + sistem aktörlü audit olayı + `--layer gold` ile bayrak açık hata, D5 docs/OpenAPI (503, 409, `ner_label_unknown`, airgap `pii_ner`); ağırlıkla D6-D8 (models-check, lisans/id2label, ölçüm, kazanan, egress PERSON testi).
Görüş isteyen iki varsayım (itiraz yoksa böyle): (1) D4 audit olayı `reindex_personnel_data_accepted`, `actor_type=system`, yalnız KB kimliği ve kayıt sayısı; (2) `--accept-personnel-data` + `--layer gold` çıkış 2 `flag_not_applicable` (r3 NOTE-2'nin ikinci yarısı, 172 kapsamında sayıyorum).
D1'den başlıyorum; yığın gerekmedikçe birim testler tools konteynerinde `--no-deps`.

### A-08T1C-0005 · 2026-11-05 11:40 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1c-olcum   Cevap: K-08T1C-0003
Talep: yalın `ffcore-08t1c` (FFCORE_VERSION=0.0.0-main, `--env-file .env.test`, tools ile `make test-int` hedefli: test_08t_30, ardından D4 testleri). Ölçüm: açık yığınlar ffcore-09 (20 konteyner, ≈5,4 GB) + paycorellm-19r3 (1); `df -h /c` 106 GB boş. İzin gelene kadar yığın açmıyorum; o arada D5 docs.
İlerleme (dal, push yok): e6d3ebf kırmızı → 2beffe5 D1 `local_ner()` kilidi (4 eşzamanlı çağrıda 4 yükleme → 1; NER testleri 22/22); fe6993c D2 `test_08t_secrets_linear` CPU oranı (4x girdi, sınır 8, en iyi 3, 5 çağrı) + 120 s asılı kalma koruması, `test_04a_9d` 600 s uyku altında geniş koruma (300 s); eski kare desen aynı ölçümle oran 20,7 (yakalıyor), yeni testler 8/8. D3 testleri yazıldı (409 + kuyruk boş + audit `error`; gold ve kişi verisiz silver 202), commit'lenmedi, kırmızı koşusu yığın bekliyor.

### A-08T1C-0006 · 2026-11-05 11:16 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1c-olcum   Cevap: K-08T1C-0004
`ffcore-08t1c` (postgres, redis, litellm, fake-llm, qdrant) `down -v` ile kapatıldı; kalan konteyner 0, volume 0. Yalnız hedefli test-int koştu.
D3 (FOLLOWUP-172 N1): f62f4f4 kırmızı (202 ≠ 409) → b4799e2 reindex ucu silver'da `check_reindex_silver` → 409 `conflict_error` `prsim_requires_ner`, kuyruk boş, audit `error`; gold ve kişi verisiz silver 202.
D4 (172 N2): 3bfa9b5 kırmızı (log yok; gold+bayrak çıkış 0) → e6ed300 bayrakla kişi verisi kaydı sayısı `log.warning` (`records=N`), CLI sistem aktörlü audit `reindex_personnel_data_accepted` (`{layer, full, personnel_records}`, ad/yol yok), `--accept-personnel-data --layer gold` çıkış 2 `flag_not_applicable`.
Hedefli test-int: test_08t_30 + test_04a_api + test_19_ingest_raw 40 passed / 1 skipped; ruff temiz. Kanıt state/evidence/08t1c-d3-{red,green}.log, 08t1c-d4-{red,green}.log.
Sıradaki: D5 docs/OpenAPI, sonra tam `make lint` + `make test` iki profil (yığınsız); ağırlık gelince D6-D8.

### A-08T1C-0007 · 2026-11-05 11:45 · → koordinator · DURUM
Paket: 08-tam-1c-olcum   Cevap: K-08T1C-0004
DURUM: IMPLEMENTED (ağırlıksız kısım). HEAD 6395c6e (10 commit, 14 dosya, state yok, push yok). D5: 2771e24 kırmızı → 1e83092 iç NER ucunun 503'ü OpenAPI'de (08.yaml yeniden üretildi, additive); 6395c6e docs (reindex 409 + M3 audit, `/readyz` NER kodları, airgap'te ingest `pii_ner` NER ister, kanıt biçimi 7 karakter, DECISION-166 A satırı).
Kapı (yığınsız): `make lint` 0; `make test` llmaas 1603/1603, airgap 1603/1603 (state/evidence/08t1c-{lint,test-*}.log). PR açıklaması state/pr/08-tam-1c.md güncel.
Bekleyen: ENV-163 (kullanıcı `make models`); gelince D6-D8, sonra VERIFIED + PR-HAZIR. SORU (senin yetkin): A (önerim) dal ağırlıkla tek PR olarak kalsın, inceleme ölçümle birlikte; B ağırlıksız kısım şimdi ayrı review turuna girsin, ölçüm ikinci tur. Etki: A tek tur ama 168/172 ağırlığa kadar main dışı; B 168/172 erken main'e, iki tur.

### A-08T1C-0008 · 2026-11-05 12:05 · → koordinator · ACK
Paket: 08-tam-1c-olcum (1c-a)   Cevap: K-08T1C-0005
B alındı: 1c-a = D1-D5 + FOLLOWUP-174, aynı dal `feat/08-tam-1c-olcum`; 1c-b ağırlıkla `feat/08-tam-1c-b-olcum`.
174 yapıldı: 627e067 kırmızı (3 düştü) → 0514192 (önce kırmızı test commit'i): `ingest-raw --text-filter {pii_ner,pii_regex}`, varsayılan `pii_ner`; `pii_regex` NER çağırmaz, PRSIM (kaynak ya da yol) yine `prsim_requires_ner`; `--accept-personnel-data` + açık `pii_ner` → `text_filter_conflict` çıkış 2; `none` gibi kapatma seçimi yok (argparse 2). a4ec5f5 docs (bilgi-tabani, guardrail airgap notu, paycore-entegrasyon).
**İşaret (kararına aykırıysa DUZELT):** plan/19 S1 testi `test_19_s1_masking_cannot_be_disabled` adında `filter` geçen her seçeneği yasaklıyordu; senin 174 kararınla çelişti. Testi amacına göre değiştirdim: adında mask/filter geçen tek seçenek `--text-filter`, seçimleri tam `{pii_ner, pii_regex}` (ikisi de maskeler). PR varsayımına yazılacak.
Not: paycoreLLM runbook'undaki geçici `--accept-personnel-data` yolu (FOLLOWUP-174 metni) paycoreLLM'de; touch-zone'um dışında, 1c-a merge sonrası runbook'un `--text-filter pii_regex`'e çevrilmesi ayrı iş.
Kapı (lint + make test iki profil) koşuyor; yeşilse PR-HAZIR.

### A-08T1C-0009 · 2026-11-05 12:25 · → koordinator · DURUM
Paket: 08-tam-1c-olcum (1c-a)   Cevap: K-08T1C-0006
DURUM: VERIFIED. HEAD a4ec5f565c076a232e392f93557ffdf10d1cb69b: `make lint` 0 (447 dosya); `make test` llmaas 1608/1608, airgap 1608/1608 (state/evidence/08t1c-a-*.log). 13 commit, 17 dosya +412/-61, state yok, main ile çakışma yok (`merge-tree`). PR notunda S1 eski/yeni kural + gerekçe (varsayım 0).

### A-08T1C-0010 · 2026-11-05 12:25 · → koordinator · PR-HAZIR
Paket: 08-tam-1c-olcum (1c-a)   Cevap: K-08T1C-0005
Branch `feat/08-tam-1c-olcum` · SHA **a4ec5f565c076a232e392f93557ffdf10d1cb69b** · baz 8aa8442 · Sınıf [B] · push yok · PR açıklaması state/pr/08-tam-1c.md.
İnceleyici için: hedefli test-int `tests/integration/test_08t_30_reindex_prsim.py` (yalın yığın: postgres, redis, litellm, fake-llm, qdrant); birim `test_08t1c_*`, `test_08t_secrets_linear`, `test_04a_9d`, `test_19_raw_staging`, contract `test_08_openapi`. Her kalemde önce test commit'i. Dal donar; DUZELT gelirse yeni SHA ile PR-HAZIR.

### A-08T1C-0011 · 2026-11-05 12:45 · → koordinator · ACK
Paket: 08-tam-1c-olcum (1c-a)   Cevap: K-08T1C-0009
DUZELT alındı ve uygulandı: b1cd3ab test (düştü: `ner_offsets_unavailable` eksik) → 60c6169 OpenAPI/docstring/api.md dört 503 kodu + 08.yaml yeniden üretim; docs/bilgi-tabani.md `pii_regex`: NER yok, regex kategorileri maskelenir, koşu durmaz, PRSIM ret. contract 85/85, `make lint` 0. NOTE'lar 1c-b PR notuna.

### A-08T1C-0012 · 2026-11-05 12:45 · → koordinator · PR-HAZIR r2
Paket: 08-tam-1c-olcum (1c-a)   Cevap: K-08T1C-0009
Branch `feat/08-tam-1c-olcum` · SHA **60c6169c93b65399b25283b63f096c8e4cec4732** (r1 a4ec5f5 + 2 commit: b1cd3ab, 60c6169; 4 dosya +14/-8 ve test) · [B] · push yok · PR state/pr/08-tam-1c.md ("Review r1 bulgu → düzeltme → kanıt"). Dal donar.

### A-08T1C-0013 · 2026-11-05 13:10 · → koordinator · DURUM
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0014
Worktree `.worktrees/feat/08-tam-1c-olcum` artık `feat/08-tam-1c-b-olcum` dalında (`checkout -B ... main`, baz bf4ec66; 60c6169 main'de doğrulandı); eski dal `feat/08-tam-1c-olcum` silinmeyi bekliyor (sende). Ağaç temiz, commit yok.
Ağırlık yeniden denetlendi (`--network none`, salt-okunur): `04a-knowledge-core_model_cache` hub'ında hâlâ yalnız bge-m3, bge-reranker-v2-m3, docling-layout-heron, docling-models; **NER adayları yok** (ENV-163 açık; kullanıcı komutu A-08T1C-0003, dizin aynı worktree).
Bekliyorum; ağırlık gelince D6-D8 + FOLLOWUP-168 NOTE-2b/3, 1c-a r1 NOTE'ları PR notuna.

### A-08T1C-0014 · 2026-11-05 13:45 · → koordinator · DURUM
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0014, K-09-0044
**Ağırlık geldi (ENV-163 kapatılabilir).** Kullanıcı `make models` koştu; dal main'e ileri sarıldı (105d176). `--network none` + salt-okunur volume ile `make models-check`: `ok all model weights are in the cache`, exit 0 (state/evidence/08t1c-b-models-check.log). İki aday tam (`.incomplete` 0): `savasy/bert-base-turkish-ner-cased@7678083d645af39967e0ebe8213a6049deb6e2cc`, `akdeniz27/bert-base-turkish-cased-ner@99995f7d2be4b3a28c74f0d36ee97f8c04ee0571`, her biri ~0,44 GB.
D6 kart okuması (offline): **akdeniz27 `license: mit`**; **savasy kartında lisans alanı yok** (README yalnız `language: tr`) → K-08T1B-0002 gereği ürün seçimine giremez, yine ölçülür ve tabloda "lisans belirtilmemiş" yazar. `id2label` ikisinde de `O, B/I-PER, B/I-ORG, B/I-LOC` → `ner_label_unknown` yok. Durma koşulu yok (bir lisanslı aday var); akdeniz27 recall < 0,85 çıkarsa KARAR-GEREK.
Yığın gerekmiyor: ölçüm yalnız tools konteyneri (`docker run --network none`, 04a model volume salt-okunur). Egress PERSON testi (`GUARDRAIL_EGRESS_NER=true`, `-m models`) için yığın gerekirse YIGIN-AÇ yazarım. Sıra: kırmızı testler → ölçüm betiği → D8.

### A-08T1C-0015 · 2026-11-05 14:20 · → koordinator · KARAR-GEREK
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0015
models-check logu komut satırı, ağ arayüzleri (yalnız `lo`) ve `/models ... ro` bağlama satırıyla yeniden yazıldı (state/evidence/08t1c-b-models-check.log). Keşif ölçümleri (commit edilmemiş betik, ağsız, salt-okunur): state/evidence/08t1c-b-explore{,2,3,4}.log. Ölçüm verisi sentetik 13a seti, kişi verisi yok.
**Kalite (pii-100, PERSON 22 / ORG 4 / LOC 4):** iki aday da kişi adı recall 1,00. Ama kodun bugünkü `aggregation_strategy="simple"` ayarı akdeniz27'de kelimeyi alt parçalara bölüyor (`I`,`h`,`lam`; `ga çınaroba`) → PERSON precision 0,56 ve **adın parçalı maskelenmesi** (sızıntı riski). Kartın önerdiği `first` ile akdeniz27 PERSON recall 1,00 / precision 1,00, ORG 1,00 / 0,67; LOC precision 0,17 (yanlış pozitiflerin hepsi altın setin `TR_ADDRESS` dediği adres parçaları: mahalle, ilçe, il). savasy `first` ile PERSON precision 0,88. **Varsayım (aykırıysa DUZELT):** `ner.py` `aggregation_strategy` → `"first"` (kelime düzeyi etiket; kanıt tablosu PR'da, kelimeyi bölmeme testi `-m models`).
**Gecikme: P95 < 300 ms tutmuyor (durma koşulu).** 1.000 karakter = 293 token; süre neredeyse tamamen modelin ileri geçişi (tokenizer ~1 ms). fp32 akdeniz27 `first`, 4 iş parçacığı: medyan 370 ms, en iyi 318 ms, P95 484 ms. Ölçüm yük altında (ffcore-09 testleri, loadavg 3,4-4,7 / 7 CPU); boşta P95 düşer ama en iyi tek koşu bile 300'ün üstünde, yani fp32 bu CPU'da bütçeye girmez. int8 dinamik nicemleme (`torch.quantization.quantize_dynamic`, yalnız Linear): kalite aynı (PERSON 1,00/1,00, ORG aynı, LOC 23 tahmin), medyan 212 ms, en iyi 159 ms, P95 431 ms (yük altında).
Seçenekler:
- **A (önerilen):** akdeniz27 + `first` + int8 dinamik nicemleme `LocalNer` yüklemesinde her zaman açık (yeni ayar yok; kanıt evidence'ta `int8`). Boşta P95 ölçümünü yığın açık değilken tekrar koşarım; < 300 ms tutarsa kabul 3 yeşil. Risk: torch bu API'yi kullanımdan kaldırma yolunda (uyarı: torchao'ya geçiş); bugün çalışıyor, torch yükseltmesinde kırılırsa yükleme fail-loud olur. FOLLOWUP: torchao/ONNX geçişi. Kalite eşitliği testle sabitlenir (`-m models`).
- **B:** fp32 kalır, gecikme bütçesi ölçülen değere çekilir (P95 ~500 ms; M4 eşiği kullanıcı kararı, [C]). Kod basit, egress çağrısı başına ~0,4 s.
- **C:** ONNX Runtime ihracı (yeni bağımlılık ve imaj değişikliği, ayrı dilim); bu PR gecikme kriterini NOT_RUN/kırmızı bırakır.
A, 80/20'ye uyuyor: platformun (torch) sunduğu tek çağrı, kalite kaybı ölçülmedi. Bu arada birim testleri, ölçüm modülü ve `first` dilimine devam ediyorum; nicemleme kodunu karar gelene kadar yazmıyorum. Boşta ölçüm için ffcore-09'un test koşmadığı bir pencere lazım; söylersen o an koşarım.

### A-08T1C-0016 · 2026-11-05 14:40 · → koordinator · KARAR-GEREK
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0016, K-08T1C-0017
**Boşta P95 < 300 ms tutmadı (durma koşulu, K-08T1C-0016).** Pencere bitti, koşum yok; inceleyiciye koşu serbest verilebilir. Log: state/evidence/08t1c-b-idle-p95.log (komut satırı, `--network none`, `/models ro`, loadavg, host bilgisi). Betikler state/evidence/08t1c-b-scripts/. Ölçüm `quality.ner_latency_sample`: yerel kurallar + NER, 1.000 karakter (293 token), 200 koşu; akdeniz27, `first`.
| Kip | 4 torch iş parçacığı (VM 7 CPU) | `--cpus=1`, 1 iş parçacığı |
|---|---|---|
| fp32 | P95 1.259 / 1.462 ms | P95 1.300 / 936 ms |
| int8 | P95 825 / 840 ms | P95 458 / 442 ms |
Aynı kodla 13:59'da (ffcore-09 yeni bitmişti) int8 P95 **297 ms** ölçmüştüm (08t1c-b-measure-candidates.log); 20 dk sonra boş VM'de 825 ms. Fark bizim yükümüzden değil: makine **i7-1165G7 dizüstü (4 çekirdek / 8 iş parçacığı, Balanced güç planı, turbo)**, Windows tarafında Docker, Cursor, Teams ve claude oturumları %12-46 CPU kullanıyor. Isı/turbo ve host gürültüsü sonucu 3 kat oynatıyor; tek iş parçacığı 4 iş parçacığından hızlı çıktı (hiper-iş parçacığı çakışması). Bu makine bütçeyi sınamak için temsilî değil; yine de tek doğrulanmış sayı: int8 P95 297-840 ms, fp32 936-1.462 ms. int8 her koşulda fp32'den 2-3 kat hızlı, kalite aynı.
Seçenekler (bütçe değişikliği kullanıcı kararı):
- **A (önerilen):** Kod int8 + `first` ile merge edilir; `test_08t_3` eşiği 300 ms kalır ve **hedef donanımda** (PayCore sunucusu ya da llmaas kurulum makinesi) kullanıcı komutuyla koşulur; bu PR'da kabul 3 "NOT_RUN (hedef donanım), geliştirme dizüstünde 297-840 ms" olarak yazılır. Bugün üretim etkisi yok: PayCore sunucusu `GUARDRAIL_EGRESS_NER=false` (DECISION-166 A); `true`'ya geçiş adımına "önce sunucuda `make test-models` P95" şartı eklenir. Risk: sunucuda da tutmazsa geçiş bekler (o zaman B ya da C).
- **B:** Bütçe ölçülen değere çekilir (ör. NER dahil P95 < 1.000 ms; egress çağrısı başına ~0,3-0,8 s ek gecikme), test bu eşikle yeşil. Kullanıcı kararı [C]; LLM yanıt süresinin yanında küçük ama ilk token gecikmesine eklenir.
- **C:** Ek hızlandırma dilimi: ONNX Runtime int8 ve/veya torch iş parçacığı sayısı ayarı (ölçümde 1 iş parçacığı daha hızlı). Yeni bağımlılık ya da yeni ayar; bu PR bekler.
A'yı öneriyorum: bütçe, ölçemediğimiz bir makine yüzünden değiştirilmemeli; gerçek sayı sunucuda bir komutla alınır ve geçiş adımı zaten ayrı.
Bu arada kalan iş (karardan bağımsız): kod commit'i (`first` + int8, quality CLI `--ner`, NER_REVISIONS sabitlemesi, safetensors yalnız, `.env.example`, models.txt, docs), birim ve `-m models` testleri (gecikme hariç yeşil), lint ve `make test` iki profil. Son ölçüm logunda 2 birim testi yalnız çıplak `docker run`'da `.env.test` olmadığı için düştü; compose ile koşacağım.

### A-08T1C-0017 · 2026-11-05 14:55 · → koordinator · DURUM
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0018
DURUM: VERIFIED. HEAD 2a7b430d680d1bf6c99b3741b62a21339fa6fcf1: `make lint` 0 (476 dosya); `make test` llmaas 1743/1743, airgap 1743/1743 (`--env-file .env.test`, `--network none`; state/evidence/08t1c-b-test-*.log). `-m models` (`--network none`, `/models:ro`): 48 passed (gecikme hariç); `make test-ner-latency` bu koşuda P95 158 ms (yeşil, ama dizüstü temsilî değil: aynı kod 158-840 ms); `verify.sh --models` OK 73 dosya. main 0676a67 ile `merge-tree` temiz.
K-08T1C-0018 uygulandı: `make test-ner-latency` (tek satır, P95 yazar); docs/guardrail.md: dizüstü aralığı + makine bilgisi, `true` geçiş adımında "önce sunucuda gecikme testi yeşil" (PayCore satırı ve llmaas üretim satırı); PR'da kabul 3 NOT_RUN (hedef donanım, ENV-177).
NOTE-3 ölçüldü: 1.862 token, 60 ad; her adın her harfi kapsanıyor, ad dışı span yok. İlk testim her adı tek span sanıyordu, model soyadı bazen ayrı `B-PER` veriyor (kısa metinde de); test kapsama özelliğine çevrildi, docs yazıyor. NOTE-2b ölçüldü: verim kilitli ve kilitsiz ~4-5 çağrı/s (CPU'ya bağlı); kilit yalnız kuyruk ucunu etkiliyor; kilit kalır (state/evidence/08t1c-b-lock-latency.log).
İki ek karar, PR varsayımlarında (aykırıysa DUZELT): (1) `make models` NER'i artık `main` değil ölçülen commit'ten indiriyor (`NER_REVISIONS`); (2) yalnız safetensors, `pytorch_model.bin` (pickle) indirilmiyor ve models.txt'de yok.
FOLLOWUP önerileri (kayıt sende): torchao/ONNX geçişi (torch nicemleme API'si kaldırılma yolunda); paycoreLLM runbook'u `true` geçiş adımına `make test-ner-latency` şartı ve yeni sabit commit; egress NER kapasitesi ~4-5 çağrı/s/API süreci (yoğun eşzamanlılıkta kuyruk).

### A-08T1C-0018 · 2026-11-05 14:55 · → koordinator · PR-HAZIR
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0014
Branch `feat/08-tam-1c-b-olcum` · SHA **2a7b430d680d1bf6c99b3741b62a21339fa6fcf1** · baz 105d176 · delta `105d176..2a7b430` (7 commit, 10 dosya +441/-47) · Sınıf [B] · push yok · PR açıklaması state/pr/08-tam-1c.md "PR 1c-b" bölümü (1c-a r1 NOTE'ları içinde).
İnceleyici için: yığın gerekmez. `-m models` testleri `04a-knowledge-core_model_cache` volume'unu salt-okunur bağlayarak: `docker run --rm --network none --env-file .env.test -e RUN_MODEL_TESTS=1 -v <worktree>:/work -v 04a-knowledge-core_model_cache:/models:ro -w /work/backend ffcore/tools:0.0.0-08t1c pytest -m models tests/models/test_08t_ner_models.py`; ölçüm CLI'sı docs/guardrail.md "NER quality report". Gecikme testi makineye bağlı (kabul 3 NOT_RUN). Her kalemde önce test commit'i. Dal donar; DUZELT gelirse yeni SHA ile PR-HAZIR.

### A-08T1C-0019 · 2026-11-05 15:00 · → koordinator · DURUM
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0019
Kullanıcı isteğiyle öz-kontrol (dal 2a7b430'da donuk, değişiklik yok, yığın yok). Doğrulananlar: HEAD 2a7b430, 7 commit, main b6981f0 ile `merge-tree` temiz; test/lint logları 2a7b430 SHA'sını taşıyor ve PR'daki sayılarla aynı (1743×2, lint 0). `08t1c-b-green-models.log` başlığı "e2ee8f8 + çalışma ağacı": e2ee8f8..2a7b430 farkı yalnız o koşunun içerdiği 3 dosya (Makefile, test_08t_ner_models.py, docs), commit'ler koşudan sonra ve arada düzenleme yok.
**Kanıt boşluğu kapandı:** PR'daki "verify OK 73 dosya" hiçbir log'da yazmıyordu (yalnız `verify_exit=0`); offline yeniden koşuldu: state/evidence/08t1c-b-verify-models.log (`OK models (73 files)`, exit 0, HEAD 2a7b430).
Kendi bulgularım (DUZELT kararı sende; küçük, tek commit):
- **MINOR-a:** docs/guardrail.md aday tablosu seçilen satırda "P95 297-840 ms" diyor, PR "158-840 ms"; ölçülen tam aralık 158-840 ms (08t1c-b-green-models.log 158 ms). Docs düzelmeli.
- **MINOR-b:** `.env.example` `GUARDRAIL_EGRESS_NER=true` yorumu "`make test-ner-latency` hedef makinede yeşil olmadan true yok" şartını söylemiyor (docs iki yerde söylüyor). Kurulum yapan önce `.env.example`'ı okur.
NOTE'lar (kod değişikliği önermiyorum, inceleyici bilsin):
1. `test_08t1c_10` (egress) `"<<PII_1>> <<PII_2>> arar."` bekliyor; model bazen soyadını ayrı `B-PER` veriyor (hata ayıklamada kısa metnin başındaki "Ayşe Demir" ikiye bölündü). Bu cümlede bölünmüyor ve deterministik, ama model/torch değişirse üç yer tutucuya dönebilir (maskeleme yine tam).
2. Revizyon iki yerde: `.env.example` `NER_REVISION` ve `models.py` `NER_REVISIONS` (test 7d eşitliği tutuyor). Başka revizyon seçen kurulum `make models` ile onu indiremez; bilinçli (ölçülen commit), docs yazıyor.
3. `make test-models` artık gecikme testini de içeriyor; hedef olmayan makinede kırmızı olabilir (dizüstü 158-840 ms). Hedefli komut `make test-ner-latency`.
4. Bellek: int8'in çalışma belleği ölçülmedi; `quantize_dynamic` kopya üretir, yüklemede kısa süre fp32 + int8 birlikte bellekte. Docs'taki 0,44 GB disk boyutu.
5. Her API açılışında torch nicemleme kullanım dışı uyarısı loga düşer (FOLLOWUP-178 ile gider).

### A-08T1C-0020 · 2026-11-05 16:05 · → koordinator · DURUM
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0021
r1b commit 5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809 (2a7b430 + 1; MINOR-a/b, NOTE-1/3; lint 0; `-m models` 6 passed + gecikme ayrı işarette deselected; `make test-ner-latency` koşuyor: 08t1c-b-r1b-models.log). Kapı yavaş: review09 yığını ~%180 CPU'da test koşuyor; `make test` llmaas 28:53 sürdü (normalde 3:52) ve **1742/1743**: düşen `test_02_r1_m3_child_process_exits_by_itself` (mutlak duvar saati: `elapsed < SHUTDOWN_TIMEOUT_S + 3`, alt süreç); r1b tracing'e dokunmuyor, aynı test 2a7b430'da yeşildi. airgap `make test` şu an koşuyor. Bitince o testi tek başına 3 kez koşup sonuçla PR-HAZIR r1b yazacağım. Takılma yok; yük kaynaklı yavaşlık.

### A-08T1C-0021 · 2026-11-05 16:50 · → koordinator · PR-HAZIR r1b
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0021
Branch `feat/08-tam-1c-b-olcum` · SHA **5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809** · baz 105d176 · delta `105d176..5e9a688` (8 commit, 13 dosya +484/-52); r1b delta `2a7b430..5e9a688` (1 commit, 7 dosya +59/-21) · [B] · push yok · main c6c9d83 ile `merge-tree` temiz · PR state/pr/08-tam-1c.md "r1b" bölümü.
r1b: MINOR-a (docs P95 158-840 ms), MINOR-b (`.env.example` `true` öncesi `make test-ner-latency` şartı), NOTE-3 (gecikme testi `tests/models/test_08t_ner_latency.py`, işaret `ner_latency`, `make test-models` koşmaz: `6 passed, 1 deselected`), NOTE-1 (egress testi özellik: ham ad/telefon yok, 2-3 yer tutucu). NOTE-2/4/5 PR notunda.
Kapı: `make lint` 0; `make test` airgap 1743/1743; llmaas 1742/1743: `test_02_r1_m3_child_process_exits_by_itself` yük altında 1 kez düştü (mutlak duvar saati; review09 ~%180 CPU, makine uykusu), **tek başına 3/3 yeşil** (08t1c-b-r1b-tracing-rerun.log); 02'ye dokunulmadı. `-m models` 6 passed; `make test-ner-latency` koşuyor (dizüstü 266/367 ms, ENV-177). Dal donar.

### A-08T1C-0022 · 2026-11-05 17:40 · → koordinator · ACK
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0024
r1c başladı: MINOR-1..5 (state/reviews/08-tam-1c-b-r1.md). Kırmızı testler yazıldı. Konteyner notu: yalnız tools `docker run --rm --network none` (+ `04a-knowledge-core_model_cache:/models:ro` -m models için); yığın yok.

### A-08T1C-0023 · 2026-11-05 17:35 · → koordinator · PR-HAZIR r1c
Paket: 08-tam-1c-b-olcum   Cevap: K-08T1C-0024
Branch `feat/08-tam-1c-b-olcum` · SHA **b567b7d66c55bb4559a26f081b328a37e4ef6440** · baz 105d176 · delta `105d176..b567b7d` (10 commit, 18 dosya +775/-65); r1c delta `5e9a688..b567b7d` (2 commit: 1f3f391 kırmızı test → b567b7d; 9 dosya +326/-48) · [B] · push yok · PR state/pr/08-tam-1c.md "r1c" bölümü.
MINOR-2: `Covered` sütunu; **PERSON covered 22/22 = 1,00**, recall düşmedi. MINOR-3: ölçüm motorun eşiğiyle (0,5); akdeniz27 ORG 6 → 5 tahmin (precision 0,80), PERSON/LOC aynı. MINOR-4: `models-files.sh`; `save.sh` yalnız listelenenler (`tar --dereference`); `verify.sh` listede olmayan model dizini/snapshot dosyasını FAIL ile adlandırır, silmez; paketlenen ağaç ağsız yüklendi. MINOR-5: docs 158-840 ms, hız farkı 4 iş parçacığında 1,5-1,7, tek iş parçacığında 2,1-2,8 kat. MINOR-1: PR/docs metni (keşif kanıtı). MINOR-6 değişiklik yok.
Kapı: `make lint` 0; `make test` llmaas 1751/1751, airgap 1751/1751; birim 52 passed; `-m models` 7 passed + 1 deselected (state/evidence/08t1c-b-r1c-*.log). Konteynerler yalnız `docker run --rm --network none` (model volume `:ro`); yığın yok, hepsi kapandı.
**Kullanıcı adımı (merge sonrası, tek seferlik):** gerçek volume'da `verify.sh --models` artık FAIL (savasy dizini + akdeniz27 `pytorch_model.bin`; 08t1c-b-r1c-checks.log); temizlik komutu docs/guardrail.md "Old volumes". Ben silmedim. Dal donar.

### A-08T1C-0024 · 2026-11-05 18:30 · → koordinator · HANDOFF
Paket: 08-tam-1c-olcum (1c-a + 1c-b)   Cevap: K-08T1C-0031
**Bitti:** 1c-a main c5b234c (FOLLOWUP-168/172/174); 1c-b main 6066276 (NER ölçümü ve seçimi: akdeniz27@99995f7, MIT, `first` + int8, sabit commit indirme, yalnız safetensors, `make test-ner-latency`, kapsama sayımı, listelenen-modeller-yalnız offline paket). Açık dosya yok; worktree temiz; çalışan konteyner yok.
**Açık kalanlar (sahipleri kayıtlı):** ENV-177 sunucuda `make test-ner-latency` (kullanıcı; `GUARDRAIL_EGRESS_NER=true` öncesi şart); eski volume temizliği (kullanıcı, komut docs/guardrail.md "Old volumes"; yapılana kadar `verify.sh --models` FAIL); FOLLOWUP-178 torchao/ONNX; FOLLOWUP-179 paycoreLLM runbook; 1c-a r1 NOTE 1-5 ve 1c-b r1 NOTE 1-7 PR notunda.
**Öğrenilenler:**
1. Windows'ta Python `open(p, 'w')` CRLF yazar; `.gitattributes eol=lf` commit'te düzeltir ama kanal/state dosyası kirlenir. `newline=''` ile yaz.
2. Bash aracı heredoc'ta `\n`'yi gerçek satır sonuna çevirebiliyor (f-string kırıldı); ters bölülü kod Write/Edit ile.
3. `conftest` `item.keywords` dizin adlarını da içerir: `tests/models/` altındaki her test `models` anahtarını taşır; ayrı işaretli test yine `RUN_MODEL_TESTS` ister.
4. `pytest --collect-only -m X -q` seçimi kanıtlamaz (hepsini listeler); `-m X` ile koşup "N deselected" satırı kanıttır.
5. Dizüstünde gecikme ölçümü temsilî değil: aynı kod 20 dk arayla 3 kat oynadı; tek iş parçacığı 4'ten hızlı çıkabiliyor. Bütçe kararı hedef donanımda.
6. HF pipeline `aggregation_strategy` modele göre seçilmeli (kart önerisi); `simple` alt kelime parçalarıyla kısmi maskeleme yaptı.
7. Kanıt iddiası (ör. "verify OK 73") mutlaka log dosyasında olmalı; terminal çıktısı kanıt değil.
8. Çıplak `docker run` `.env.test` olmadan `get_settings()` testlerini düşürür; `--env-file .env.test` ver.

### A-08T1C-0025 · 2026-11-05 18:30 · → koordinator · RETIRED
Paket: 08-tam-1c-olcum   Cevap: K-08T1C-0031
Lease `ffcore-isci-a-08-tam-1c-olcum` bırakıldı. Worktree/dal kaldırma koordinatörde.
