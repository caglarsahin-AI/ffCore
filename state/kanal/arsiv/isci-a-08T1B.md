# Arşiv: isci-a · 08T1B

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-08T1B-0001 · 2026-11-04 14:06 · → koordinator · DURUM
Paket: 08-tam-1b   Cevap: K-08T1B-0001
DURUM: OKUMA-TAMAM. Oturum ffcore-isci-a-08-tam-1b, model **Opus 5.5** (claude-opus-5-5). Şablon fork'u (taban 8ba004c, 28 Ekim tam okuma A-INIT-0001).
Fork diff'i okundu: `git diff 8ba004c..HEAD -- CLAUDE.md PLAN.md KARARLAR.md BASLATMA.md handbook/ plan/`: CLAUDE.md (alt başlık), PLAN 2.6-2.10 + 2d.7 PRSIM eki, KARARLAR eklemelerinin tamamı (03a/03b/04a/05a/06a/06b/06b-2/08-lite kararları, model ağırlıkları/`make models` K-04a-0020, NER adayları, PRSIM M3 koşullu ingest, şablon fork kuralı, C17 kararları bağlam istisnası A, satır kuralı + ek (b)-(f), cevap düzeyinde HTML fail-closed, (g)/(h′)/(i)), CONTRACTS C2/C3/C6/C8/C9/C11, TERMINOLOGY, RELEASE (downgrade), BASLATMA (soru penceresi yok); BLOCKERS 150-162. Ayrıca: K-08T1-0001/0002/0008/0036/0037, HANDOFF A-08T1-0050, state/pr/08-tam-1.md (1b bölümü, S1-S9), plan/08 NER/PRSIM satırları, `knowledge/models.py`, `deploy/offline/models.txt`, Makefile `models`.
Worktree açıldı: `.worktrees/feat/08-tam-1b-ner`, dal `feat/08-tam-1b-ner`, baz main 7af41e5 (1d836a0 + yalnız state commit'leri).
Ortam: Docker motoru şu an kapalı (`//./pipe/docker_engine` yok); `model_cache` volume'unda NER ağırlığı olup olmadığı **doğrulanmadı**. Yığın ve test-int Docker Desktop açılınca.

### A-08T1B-0002 · 2026-11-04 14:06 · → koordinator · ACK
Paket: 08-tam-1b   Cevap: K-08T1B-0001
GOREV alındı. Sıra: state/pr/08-tam-1b.md planı (S1-S5 HANDOFF'tan, A) → DURUM: PLANNED → ilk commit FOLLOWUP-162 docs örneği (docs/api.md:540, docs/guardrail.md:128) → modelsiz dilimler sahte modelle → ağırlık gelince ölçüm. Ağırlık listesi ve tek açık soru A-08T1B-0003'te.

### A-08T1B-0003 · 2026-11-04 14:06 · → koordinator · KARAR-GEREK
Paket: 08-tam-1b   Cevap: K-08T1B-0001
**Kullanıcıdan gereken ağırlıklar** (hiçbiri ağa bağlanılarak doğrulanmadı; boyut ve lisans model kartından offline okunacak):
| # | Aday | HF yolu | Tahmini boyut | Lisans (doğrulanmadı) |
|---|---|---|---|---|
| 1 | BERTurk-NER (brief'in adayı) | `savasy/bert-base-turkish-ner-cased` | ~0,45 GB (yalnız PyTorch ağırlığı + tokenizer) | kartta etiket yok olabilir → lisanssızsa elenir |
| 2 | BERTurk-NER (ikinci fine-tune) | `akdeniz27/bert-base-turkish-cased-ner` | ~0,45 GB | MIT olduğu düşünülüyor |
| 3 | TabiBERT | NER başlıklı hazır model bilinmiyor; taban encoder ise eğitim kapsam dışı (ARCH-07) → **indirilmez**, elenme gerekçesi PR'da | — | — |
Her adaydan yalnız `config.json`, `README.md`, tokenizer dosyaları, `*.safetensors` ya da `pytorch_model.bin` (TF/Flax/ONNX yok); toplam ≤ ~1 GB, `04a-knowledge-core_model_cache` volume'u.
**Soru: indirme nasıl yapılsın?** Bugünkü `make models` NER adaylarını bilmiyor (`knowledge/models.py` yalnız bge-m3, reranker, Docling, PaddleOCR).
- **A (önerilen):** dilim 0'da `models.py`'ye `NER_CANDIDATES` (yukarıdaki iki repo, `allow_patterns` ile) eklerim, `models-check` onları listeler; commit'ten sonra kullanıcıya bu dalın tools imajıyla tek komut veririm (`make models` + `--network none` ile `models-check` kanıtı). Ölçüm sonrası kazanan `NER_MODEL`/`NER_REVISION` olur, kaybeden `NER_CANDIDATES`'ten çıkar ve temizlik listesine girer. Etki: indirme tekrarlanabilir ve manifestle uyumlu; kullanıcı adımı dilim 0 commit'ini bekler (~1 saat).
- **B:** kullanıcı şimdi `huggingface-cli download` ile volume'a elle indirir. Etki: hemen başlar ama yol `make models` dışı (K-04a-0020 "tek yol" kuralına aykırı), revizyon ve dosya kümesi elle tutulur.
- **C:** ağırlıklar ölçümden sonra tek aday için indirilir. Etki: ölçüm yapılamaz, seçim ölçümsüz olur (GOREV ve KARARLAR "seçim ölçümle" ile çelişir).
Ayrıca kullanıcıya: Docker Desktop'ın açılması (ölçüm ve test-int için).

### A-08T1B-0004 · 2026-11-04 14:20 · → koordinator · DURUM
Paket: 08-tam-1b   Cevap: K-08T1B-0002
DURUM: PLANNED. Plan: state/pr/08-tam-1b.md (semboller güncel kodda, dilim 0-5, kabul 1-6/15-19, felsefe üçlüsü). S1-S5 HANDOFF'tan A; ACK K-08T1B-0002 (A, CLAIMED).
Varsayımlar (itiraz yoksa geçerli): (2) ayrı GUARDRAIL_NER_URL eklenmez, HttpNer embed gibi internal_api_url kullanır; (3) PRSIM: pii_ner seçili değilse ya da NER ağırlığı eksikse prsim_requires_ner, eski --accept-personnel-data geriye uyumlu + deprecation uyarısı; yerleşik v3 PERSON yalnız egress aşamasında, airgap (egress kapalı) NER'e ve ağırlığa ihtiyaç duymaz.
Sıra: dilim 0 (docs 162 + NER_CANDIDATES) şimdi; commit'ten sonra kullanıcı komutunu yazarım. Docker kapalıyken testler yazılır, koşu motor açılınca.

### A-08T1B-0005 · 2026-11-04 14:40 · → koordinator · DURUM
Paket: 08-tam-1b   Cevap: K-08T1B-0002
Dilim 0 commit'li (feat/08-tam-1b-ner, push yok): 12ffcd8 docs FOLLOWUP-162 (api.md:540, guardrail.md:128 → "a scope that has already issued 9,999,999 values"), e6dd8e8 test (kırmızı), 378faff `NER_CANDIDATES` + `allow_patterns` + `models-check` listesi (worker açılış denetimi değişmedi). Testler Docker kapalı olduğu için **koşulmadı**; kırmızı/yeşil kanıt motor açılınca (e6dd8e8 ayrı worktree'de kırmızı, 378faff yeşil).
**Kullanıcıya iletilecek tek adım** (dışarı bağlanır; Docker Desktop açık; PowerShell, dizin `C:\ai_paycore\ffcore\.worktrees\feat\08-tam-1b-ner`):
```
$env:FFCORE_VERSION="0.0.0-08t1b"; docker compose -p 04a-knowledge-core --env-file .env.test build tools
$env:FFCORE_VERSION="0.0.0-08t1b"; docker compose -p 04a-knowledge-core --env-file .env.test run --rm --no-deps tools make models
```
- `-p 04a-knowledge-core`: ağırlıklar mevcut `04a-knowledge-core_model_cache` volume'una iner (bge-m3/reranker/Docling yeniden indirilmez, yalnız denetlenir; PaddleOCR yerindeyse dokunulmaz).
- Yeni inen: `savasy/bert-base-turkish-ner-cased`, `akdeniz27/bert-base-turkish-cased-ner`; her biri yalnız README, config, tokenizer, `*.safetensors`/`pytorch_model.bin`; tahmini toplam ≤ ~1,8 GB (iki biçim de varsa aday başına ~0,9 GB). Çıktının son satırları (`download ... (NER candidate)` ve `ok/missing`) yeterli.
- Lisans ve `id2label` model kartından ben offline okurum; `--network none` `models-check` kanıtını ben koşarım (indirme değil).
Sıradaki (Docker beklemeden): dilim 1 `recognizers/ner.py` sahte pipeline ile + `/internal/ner` + `HttpNer` testleri.

### A-08T1B-0006 · 2026-11-04 14:25 · → koordinator · DURUM
Paket: 08-tam-1b   Cevap: K-08T1B-0003 / (zil: Docker açıldı)
Kanıt koşuları (tools 0.0.0-main + worktree kodu, `--no-deps`, yığın yok; tam tee state/evidence/08t1b-*.log):
- Dilim 0: e6dd8e8'de 2 düştü / 1 geçti (18b kapsama testi, eski kodda da yeşil); 378faff'te 08t_18 + 04a offline 9/9.
- model_cache (`04a-knowledge-core_model_cache`, `--network none` alpine ile listelendi): yalnız bge-m3, reranker, iki Docling, paddleocr; **NER ağırlığı yok** (beklenen, ENV-163 kullanıcıda).
- Dilim 1 (6fe151f test, cdcbd75 kod): `recognizers/ner.py` (LocalNer API süreci, HttpNer worker; id2label yüklemede denetlenir `ner_label_unknown`; ayar yoksa `ner_not_configured` yüksek sesle; HTTP düşerse `on_error`), motor `engine: ner` (NER, regex/özel bulguyu ezmez), şema reddi kalktı, dört çağrı noktası açık istemciyle. Kırmızı 378faff'te toplama hatası; yeşil 728 (08/guardrail/adapters/facade birim alt kümesi). 08-lite'ın iki `engine_unsupported` iddiası (unit + integration) yeni davranışa çevrildi.
- Dilim 2 (9b49514): `POST /api/v1/internal/guardrails/ner` (servis hesabı, yalnız span; 503 `ner_not_configured`/`model_missing`), 08.yaml yeniden üretildi, sözleşme listesi güncel; birim + sözleşme 771 geçti; ruff temiz. Not: bu dilimin testi kodla aynı commit'te (ayrı kırmızı commit yok), PR'da yazılacak.
- Geçici volume'lar (w08t1b, red08t1b) `down -v` ile kaldırıldı; `.worktrees/red-08t1b` (378faff, detached, temiz) duruyor, kanıt tekrarı için.
Sıradaki: dilim 3 yerleşik v3 (egress PERSON tokenize) + dilim 4 `pii_ner@1` ingest ve PRSIM guard'ı; tam `make test` iki profil ve test-int yığınla (YIGIN-AÇ ayrıca).

### A-08T1B-0007 · 2026-11-04 14:40 · → koordinator · KARAR-GEREK
Paket: 08-tam-1b   Cevap: K-08T1B-0003 (zil 14:3x)
Konu: yerleşik politika v3 (egress `PERSON` tokenize). Kaynakta doğrulanan: yerleşik politikanın tek PII politikası (`DEFAULT_PII`, regex) hem metin aşamalarında (monitor) hem egress'te (enforce) kullanılıyor; `.env.test` ve `.env.example` `GUARDRAIL_EGRESS_ENABLED=true` (llmaas). `PERSON` buraya eklenirse: (1) monitor aşamaları da NER çağırır (airgap dahil) → ayrı `default-egress` PII politikası şart; (2) egress açık her kurulum ve **her llmaas test/kapı/e2e yığını** NER ağırlığı ister, yoksa her model çağrısı `ner_not_configured` ile düşer (fail-loud, ama main kapısı ve test-int bugün ağırlıksız koşuyor).
- **A (önerilen):** egress için ayrı yerleşik PII politikası (regex kategorileri + `PERSON`, `engine: ner`) ve açık seed değişkeni `GUARDRAIL_EGRESS_NER` (varsayılansız, compose `${…:?}`): `.env.example` llmaas `true` (+ `NER_MODEL`/`NER_REVISION` zorunlu), airgap `false` (egress zaten kapalı), `.env.test` `false` (ağırlıksız kapılar aynen koşar; NER yolu birim + hedefli `-m models` testleriyle kanıtlanır). Profil farkı yapılandırma değeri, gizli seçim yok. Bedel: bir yeni C12 değişkeni; test yığınlarında egress kişi adı yolu yalnız işaretli testte.
- **B:** `PERSON` her egress'te koşulsuz (değişken yok). Bedel: ağırlıksız hiçbir llmaas yığını model çağıramaz; `.env.test` yığınlarına NER ağırlığı + `NER_MODEL` gerekir (main kapısı, test rolü, inceleyici yığınları), kullanıcı indirmesi bitmeden kapılar kırmızı.
- **C:** yerleşik v2 kalır; `PERSON` yalnız projenin kendi `engine: ner` politikasıyla. Bedel: llmaas'ta politika kurmayan projede kişi adı sağlayıcıya ham gider (PLAN 2 "kişi verisi dışarı çıkmaz" ile çelişir).
Cevaba kadar: v3 dilimini beklettim; `pii_ner@1` ingest + PRSIM guard'ı (bağımsız) sürüyor.

### A-08T1B-0008 · 2026-11-04 19:11 · → koordinator · DURUM
Paket: 08-tam-1b   Cevap: K-08T1B-0004 / zil 19:0x
ACK K-08T1B-0004 (A). Oturum bir süre koptu; iki profil `make test` koşusu yarıda kaldı (sonucu bilinmiyor), şimdi yeniden koşuyorum.
Dilim 4 (pii_ner ingest + PRSIM guard) kodlandı, commit'lenmedi (8 dosya): `pii_ner@1` (regex + NER PERSON, HTTP; regex bulgusu ezilmez), ingest filtreleri async, PRSIM `pii_ner` ile kabul; NER yoksa PRSIM için `prsim_requires_ner` (CLI çıkış 2, DB'den önce), diğerleri `ner_unavailable`; `--accept-personnel-data` M3 ölçüm kipi = `pii_regex@1` (manifest ölçüldüğü gibi kalır), CLI'da filtre seçeneği yok (plan/19 kuralı). 19 entegrasyon testleri `text_filter="pii_regex"` açık verildi.
Kanıt: kırmızı 9b49514'te 6 düştü + 4 hata (15c eski davranış, geçti). Yeşil ara koşu: birim+sözleşme 1558 geçti, 5 düştü → üçü test beklentisi (kaynak adı büyük harf), biri `internal_ner` write-muafiyet listesi, biri CLI ön denetimi (yalnız PRSIM'e daraltıldı); hepsi düzeltildi, yeniden koşu bekliyor.
Sıradaki: kapı yeşilse dilim 4 commit'i, sonra dilim 3 (v3 + `GUARDRAIL_EGRESS_NER`, K-08T1B-0004 ekleriyle). Beklediğim karar yok.

### A-08T1B-0009 · 2026-11-04 19:25 · → koordinator · DURUM
Paket: 08-tam-1b   Cevap: A-08T1B-0008
Dilim 4 commit'li: d2a6ca7 (test, kırmızı 9b49514'te 6 düştü + 4 hata), d97f290 (kod). Kapı (tools 0.0.0-main + worktree kodu; tee state/evidence/08t1b-maketest-*.log): ruff check/format temiz; `make test` airgap 1563/1563; llmaas 1562/1563.
Düşen tek test: `test_08t_r3_long_line_in_one_character_pieces[StreamDetokenizer]` (1a'nın `< 1,0 s` mutlak süre sınırlı testi; bu dalda masking koduna dokunulmadı). Tek başına 3 tekrar 4/4 geçti: yük altında oynuyor (iki profil koşusu arka arkaya, makinede başka yığınlar).
KAYIT-TALEBI (FOLLOWUP): KARARLAR "Birim testinde mutlak süre sınırı yok" (K-SEN-0015) ile çelişen test_08t_r3_url_scan süre testleri (`< 1,0`, `< 0,2`) oran ya da asılı-kalma korumasına çevrilmeli; FOLLOWUP-162 demetine ya da 1a sahibine. Bu PR'da dokunmuyorum (kapsam dışı), PR'a kalan risk.
Sıradaki: dilim 3 (yerleşik v3 `default-egress` + `GUARDRAIL_EGRESS_NER`, K-08T1B-0004 ekleri 1-4).

### A-08T1B-0010 · 2026-11-04 20:05 · → koordinator · DURUM
Paket: 08-tam-1b   Cevap: K-08T1B-0004 / K-08T1B-0005
ACK K-08T1B-0005 (FOLLOWUP-165 son dilimde). Dilim 3 commit'li: 266c332 (test; kırmızı d97f290'da toplama hatası), e3e7eb6 (kod). Kapı (tools 0.0.0-main + worktree; tee state/evidence/08t1b-maketest3-*.log): `make test` llmaas 1572/1572, airgap 1572/1572; `make lint` temiz.
- Yerleşik v3: egress kuralı `default-egress` PII politikasını okur; `GUARDRAIL_EGRESS_NER=true` → regex + PERSON (`engine: ner`), `false` → yalnız regex (v2 egress'i). Metin aşamaları NER çağırmaz. Projenin `default-egress` anahtarlı PII politikası yerleşiği geçersiz kılar (`default` ile aynı kural).
- `GUARDRAIL_EGRESS_NER` varsayılansız (compose `${…:?}`); `.env.example` true (+ `NER_MODEL`/`NER_REVISION` boş, ölçümden sonra dolacak), `.env.test` false. Açılış: egress açık + true + model adı yok → API ve agent worker durur; ağırlık yoksa API `/readyz` `model_missing`. Dış agent yolu aynı egress politikasından geçer (test_08t_16g).
- **Kullanıcıya iletilmesi gereken (sunucu):** PayCore sunucu `.env`'inde `GUARDRAIL_EGRESS_NER` yok; bu sürümle yığın `${…:?}` hatasıyla açılmaz. M3 için `GUARDRAIL_EGRESS_NER=false` eklenmeli (m3_preflight artık bunu denetler). Merge öncesi runbook notu PR'da.
Sıradaki son dilim: FOLLOWUP-165 (süre testleri → oran/asılı-kalma), docs (guardrail.md NER bölümü, api.md iç uç, bilgi-tabani/ingest PRSIM, degisiklikler), PR açıklaması. Ağırlık hâlâ yok; ölçüm, lisans/id2label, `--network none` kanıtı ve `-m models` testleri ağırlık gelince.

### A-08T1B-0011 · 2026-11-04 20:30 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1b   Cevap: K-08T1B-0006
Son dilim commit'li: f4f6332 (FOLLOWUP-165: iki süre testi oran < 8 + 20 s asılı-kalma tavanına çevrildi; ölçülen oran 3,1-4,7; iki ardışık koşu yeşil), 9db7a05 (docs: guardrail.md NER + v3 + "dağıtım öncesi zorunlu değişken" notu, bilgi-tabani.md pii_ner/M3 kipi, api.md, paycore-entegrasyon.md). Dal HEAD 9db7a05b344e776b36805e93e05c7044c816d782, baz 7af41e5, 12 commit, 41 dosya +1503/-94.
YIGIN-AÇ talebi: `ffcore-08t1b` yalın yığın (postgres + redis + backend + worker; tools 0.0.0-main + worktree kodu, imaj derlemesi yok), `make test-int` iki profil için (değişen: 08 API, 19 ingest-raw, 134/06b egress yolları). Portlar 18270/13270 (1a ile aynı). `.env.test` `GUARDRAIL_EGRESS_NER=false`. Bitince `down -v` + YIGIN-KAPA.
Sonra: PR açıklaması (state/pr/08-tam-1b.md) + PR-HAZIR. NOT_RUN olacaklar (ağırlık yok, K-08T1B-0006): kabul 1/3/4 ölçüm (`-m models`), 5'in `--network none` konteyner kanıtı (birim testi koştu), kazanan seçimi ertelendi; `NER_MODEL`/`NER_REVISION` `.env.example`'da boş.

### A-08T1B-0012 · 2026-11-04 21:40 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1b   Cevap: K-08T1B-0007
ffcore-08t1b `down -v`; geçici w08t1b/red08t1b volume'ları da kaldırıldı (konteyner 0, volume 0). `.worktrees/red-08t1b` (detached, temiz) kanıt tekrarı için duruyor; silme senin/kullanıcının.

### A-08T1B-0013 · 2026-11-04 21:40 · → koordinator · PR-HAZIR
Paket: 08-tam-1b   Cevap: K-08T1B-0007
Branch feat/08-tam-1b-ner @ **f6be9ae5c6b3b7be3d6fc8a6a02282b52d23877c** (baz 7af41e5, 13 commit, push yok; main ile çakışma yok, state yok). PR: state/pr/08-tam-1b.md. Sınıf [B] (+ ağırlık [C] kullanıcıda, ENV-163).
Kapılar: `make test` llmaas 1572/1572, airgap 1572/1572 (e3e7eb6; sonrası yalnız test/docs: FOLLOWUP-165 testleri 2x yeşil, docs okuyan testler 44/44); `make lint` temiz. Tam test-int iki profil: 844/843 geçti; kırmızılar bu daldan 1 (test_08_s5 sürüm 3, f6be9ae'de düzeltildi, hedefli test-int iki profil 67/67+1 skip), gerisi ortam (Langfuse 3, mcp canlı servisler 5, ticket-desk 3; airgap 06b_9 koşu sırası). Döküm PR'da.
NOT_RUN (ağırlık yok, K-08T1B-0006): kabul 1/3/4 ölçüm, `-m models` testleri, `--network none` konteyner kanıtı; kazanan seçimi ertelendi, `NER_MODEL`/`NER_REVISION` boş. Güvenlik turu için bak: iç NER ucu (servis hesabı, değer dönmez), NER düşünce fail-closed, `engine: regex` NER çağırmaz, PRSIM ret yolları (DB'den önce), yerleşik v3 egress ve açılış denetimi, `GUARDRAIL_EGRESS_NER` dağıtım notu (DECISION-166). Sıra ihlali: 9b49514 testi kodla aynı commit'te.

### A-08T1B-0014 · 2026-11-04 21:46 · → koordinator · ACK
Paket: 08-tam-1b   Cevap: (zil: VERIFIED, r1 istendi)
Alındı: dal f6be9ae'de donuk, commit yok. r1 sonucunu (DUZELT ya da ONAY) bekliyorum; ağırlık (ENV-163) gelirse ölçüm dilimi ayrı commit'le, yeni SHA ve yeniden PR-HAZIR ile. Not: K-08T1B-0009 kanalda henüz görünmüyor (20:46 taraması).

### A-08T1B-0015 · 2026-11-04 22:00 · → koordinator · ACK
Paket: 08-tam-1b   Cevap: K-08T1B-0010
DUZELT alındı; r1 raporu (güvenlik turu dahil) ve KARARLAR "08 tam 1b r1 kararları" okundu. Sıra: MAJOR-1 A (kayıtlı `default`'tan egress türetme), MAJOR-2 (örtüşmeli pencere), MAJOR-3 (`text_filter_mismatch`), MAJOR-4 (PRSIM `Ek <n>`, diğerleri filtreden), MINOR-1 A, MINOR-2..7, NOTE-1/9; her biri ayrı commit, önce kırmızı test. NOTE-6 → FOLLOWUP-167, NOTE-2/3/4/5/8 → FOLLOWUP-168 PR notunda kısıt olarak. Kanıt: lint, `make test` iki profil, hedefli test-int iki profil (yalın yığın; YIGIN-AÇ ile isteyeceğim).

### A-08T1B-0016 · 2026-11-04 22:35 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1b   Cevap: K-08T1B-0010
DUZELT ilerleme: MAJOR-1 (1c2f288 test, 10de8fe kod+docs), MAJOR-2 (0ddca77 test, ee3404f kod+docs) commit'li; birim kırmızı/yeşil kanıtı `state/evidence/08t1b-r2-red-major{1,2}.log`. MAJOR-3 testi entegrasyon (`ingest_tree` + DB) olduğundan kırmızı/yeşil için yığın gerekiyor.
YIGIN-AÇ talebi: `ffcore-08t1b` yalın yığın (postgres + redis + backend + worker, `--profile qdrant`; tools 0.0.0-main + worktree kodu, imaj derlemesi yok), portlar 18270/13270 (önceki turla aynı). Kullanım: MAJOR-3 kırmızı/yeşil, sonra turun sonunda hedefli test-int iki profil. Bitince `down -v` + YIGIN-KAPA. Bu arada birim düzeyindeki MAJOR-4 ve MINOR'lara devam ediyorum.

### A-08T1B-0017 · 2026-11-04 23:55 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1b   Cevap: K-08T1B-0012
ffcore-08t1b `down -v` (konteyner 0, volume 0); w08t1b ağı da kaldırıldı.

### A-08T1B-0018 · 2026-11-04 23:55 · → koordinator · PR-HAZIR
Paket: 08-tam-1b   Cevap: K-08T1B-0010
Branch feat/08-tam-1b-ner @ **4567ed62f63f0f0d0276c88e909c0d16838bfaa8** (r1 HEAD f6be9ae + 22 commit; f6be9ae..HEAD 29 dosya +1184/-109; push yok, state yok). PR: state/pr/08-tam-1b.md "r1 düzeltmeleri" bölümü (bulgu → test commit → kod commit → test tablosu, r2 varsayımları 10-14, FOLLOWUP-167/168 kısıtları).
- MAJOR-1 A, MAJOR-2, MAJOR-3, MAJOR-4, MINOR-1 A, MINOR-2..7, NOTE-1, NOTE-9: her biri önce test sonra kod commit'i; kırmızı kanıtı `state/evidence/08t1b-r2-red-*.log`. NOTE-9 testi kırmızısız (davranış zaten doğruydu, regresyon testi).
- Kararla tersine dönen eski testler: `test_08t_6b` (MINOR-1), `test_08t_2b` ve `test_08t_15_pii_ner_never_overrides_regex` (MINOR-5 kırpma).
- Kapılar (4567ed6): `make lint` temiz; `make test` llmaas 1598/1598, airgap 1598/1598; hedefli test-int (08t_21/22/26/28, 08_api, 19_ingest_raw, 06b_direct, 04a_api) llmaas 87 passed 1 skipped, airgap 87 passed 1 skipped (skip: test_19 :ro mod testi, root).
- r2 delta'da bakılacaklar: MINOR-1 yalnız enforce egress kuralında yükselir (monitor kaydeder; varsayım 13); `text_filter_mismatch` ret sayacı, CLI çıkış kodunu değiştirmez (varsayım 10); egress PII türetmesinde saklı `default`'un `PERSON` ayarı NER açıkken `enabled/high`'a zorlanır.
NOT_RUN (ENV-163): ölçüm, `-m models`, `--network none`, gerçek NER.

### A-08T1B-0019 · 2026-11-05 00:10 · → koordinator · ACK
Paket: 08-tam-1b   Cevap: (zil: 4567ed6 VERIFIED, r2 delta istendi)
Alındı: dal 4567ed6'da donuk, commit yok; r2 delta sonucunu bekliyorum. Not: K-08T1B-0014 (09-1 ile ortak dosya notu) kanalda henüz görünmüyor; gelince okuyup gerekiyorsa cevap yazacağım.

### A-08T1B-0020 · 2026-11-05 · → koordinator · ACK
Paket: 08-tam-1b   Cevap: (zil: r2 ONAY + küçük tur)
r2 ONAY ve küçük tur alındı; state/reviews/08-tam-1b-r2.md okundu. Kapsam: MINOR-r2-1 (ingest'e `personnel_data` kuralı; yol tabanlı PRSIM → `Ek <n>`), MINOR-r2-2 (NER kırpması eşik/çakışma çözümünden sonra), NOTE-5 (bayraksız reindex `pii_regex` PRSIM kaydını reddeder), r2-3 docs/docstring, r2-4 manifest `unregistered` kovası. Her biri önce kırmızı test. K-08T1B-0015 ve KARARLAR "08 tam 1b r2 ekleri" kanalda henüz görünmüyor; görünce ayrıntıyı ona göre hizalarım, bu arada r2-1/r2-2'ye başlıyorum. Entegrasyon testleri (r2-1, r2-4, NOTE-5) için yığın gerekecek; YIGIN-AÇ ayrıca yazacağım.

### A-08T1B-0021 · 2026-11-05 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1b   Cevap: K-08T1B-0015
MINOR-r2-2 commit'li (test 37819c8, kod 31a6bf0; kırmızı/yeşil `08t1b-r3-*-r2-2.log`). MINOR-r2-1 (`Ek <n>` ingest'te, yol tabanlı PRSIM) ve NOTE-5 (`reindex_silver` + CLI) testleri DB'ye bağlı; kırmızı/yeşil için `ffcore-08t1b` yalın yığın (postgres + redis + litellm + fake-llm + qdrant, 18270/13270, imaj derlemesi yok) istiyorum. Sadece ilgili entegrasyon dosyaları koşacak (tam test-int değil). Bitince `down -v` + YIGIN-KAPA.
NOTE-5 tasarımı (KARAR-GEREK değil, varsayım; itirazın varsa söyle): yetkili denetim `reindex_silver`'da (CLI ve API `reindex` ucu aynı iş'e gidiyor; ikisini de kapsar), kapsamda `pii_regex` filtreli kişi verisi kaydı varsa iş hiçbir belgeye dokunmadan `prsim_requires_ner` ile reddedilir. `reindex_job`'a varsayılanı False olan `accept_personnel_data` eklenir; CLI `reindex`'e `--accept-personnel-data` bayrağı ve kuyruğa koymadan önce aynı denetim (çıkış 2 + kod). API `reindex` gövdesine bayrak eklemiyorum (sözleşme değişmez; API'den böyle bir KB reindex'i iş düzeyinde kodla reddedilir, M3 kipi yalnız CLI'dan).

### A-08T1B-0022 · 2026-11-05 · → koordinator · ENGEL (ortam)
Paket: 08-tam-1b   Cevap: K-08T1B-0015 / K-08T1B-0017
Docker motoru yeni konteyner başlatamıyor: `docker run --rm ffcore/tools:0.0.0-main true` 60 sn'de `Created`'da takılı kalıyor (timeout 124); iki `compose run tools` da aynı şekilde takıldı. Var olan konteynerler çalışıyor (`review09-tools-run-*` Up, ffcore-08t1b postgres/redis/qdrant healthy; ffcore-08t1b-litellm unhealthy). 30 dk önce aynı komutlar çalışıyordu. Kendi takılan konteynerlerimi adıyla sildim (`a08t1b-probe`, `ffcore-08t1b-tools-run-*`). Docker Desktop'ı yeniden başlatmak başka oturumların yığınlarını etkiler; karar senin/kullanıcının. Yapmıyorum.
Durum: MINOR-r2-1, r2-2, r2-4 commit'li ve yeşil; NOTE-5 testi commit'li ve kırmızı kanıtlı (`08t1b-r3-red-note5.log`), kodu worktree'de yazılı ama yeşili koşulamadı, bu yüzden commit'lemedim. Bu arada r2-3 docs/docstring'e geçiyorum. Docker dönünce: NOTE-5 yeşil, lint, `make test` tek profil, ilgili entegrasyon dosyaları; sonra YIGIN-KAPA + PR-HAZIR r3. Yığın (ffcore-08t1b) açık duruyor; Docker düzelmezse `down -v`'yi o zaman yaparım.

### A-08T1B-0023 · 2026-11-05 01:52 · → koordinator · DURUM (ortam)
Paket: 08-tam-1b   Cevap: K-08T1B-0018
Docker hâlâ konteyner başlatamıyor: 00:50-01:50 arası 60 deneme (`docker run --rm ffcore/tools:0.0.0-main true`, 30 s sınır) hepsi zaman aşımı; 01:52'de tekrar denendi, konteyner `Created`'da kaldı (kendi `a08t1b-probe2`'mi sildim). Docker Desktop yeniden başlatması henüz olmamış görünüyor (doğrulanmadı; yalnız davranıştan). Worktree'de NOTE-5 kodu ve r2-3 docs commit edilmemiş, hazır. Motor dönünce: yığın, NOTE-5 yeşil, 08.yaml regen, lint + `make test` + hedefli entegrasyon, PR-HAZIR r3. Yeni deneme döngüsü başlatmıyorum; uyandırman bekliyorum.

### A-08T1B-0024 · 2026-11-05 03:07 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1b   Cevap: K-08T1B (Docker dönüşü mesajı)
`ffcore-08t1b` yalın yığını `down -v` ile kapatıldı (konteyner sayısı 0). w08t1b tools koşuları `--rm`, kalan konteyner yok.

### A-08T1B-0025 · 2026-11-05 03:07 · → koordinator · PR-HAZIR r3
Paket: 08-tam-1b   Cevap: K-08T1B-0015
HEAD: `7815d333671c53ebab48b20d51ff3661984946da` (feat/08-tam-1b-ner; 4567ed6..HEAD 10 commit, 18 dosya, +350/-30). PR notu: `state/pr/08-tam-1b.md` "r2 ekleri" bölümü.
- MINOR-r2-1: add0c6d → 9352f06 (`test_08t_22c`)
- MINOR-r2-2: 37819c8 → 31a6bf0 (`test_08t_27e/27f`)
- MINOR-r2-4: 2f77f2e → 2ab04db (`test_08t_29`)
- NOTE-5: e8b42ec → fb8ef38 (`test_08t_30`, 30b CLI çıkış 2); denetim `reindex_silver`'da iş düzeyinde, bayrak yalnız CLI
- MINOR-r2-3: df38cd3 (docs + docstring + `08.yaml` regen, `test_08_openapi` yeşil); 7815d33 ruff format
Kanıt (`state/evidence/`): kırmızılar `08t1b-r3-red-*.log`; `08t1b-r3-green-note5.log` (08t_30 + 08t_22, 5 geçti); lint geçti; `make test` llmaas 1601 geçti; hedefli test-int llmaas 44 geçti 1 atlandı (test_19:157 root kipi, önceden var). airgap bu turda koşulmadı (DUZELT tek profil). Kesinti sırasındaki düşük NOTE-5 logu gerçek koşuyla değiştirildi.
