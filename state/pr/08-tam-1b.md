# PR: 08 tam dilim 1b — Türkçe NER tanıyıcısı, `/internal/ner`, `pii_ner` ingest filtresi, PRSIM guard'ı

**Paket:** 08-tam-1b · **Sınıf:** [B]; NER ağırlıkları [C] (kullanıcı `make models`, K-08T1B-0002 A) · **Branch:** feat/08-tam-1b-ner · **Baz commit:** 7af41e5 (main; 1d836a0 + yalnız state commit'leri) · **Oturum:** ffcore-isci-a-08-tam-1b (Opus 5.5) · **Durum:** PR-HAZIR r2 (r1 DEGISIKLIK düzeltildi; ölçüm NOT_RUN, ağırlık bekliyor) · **HEAD:** 4567ed62f63f0f0d0276c88e909c0d16838bfaa8 (35 commit; r1 HEAD f6be9ae)

Kaynak: GOREV K-08T1B-0001, kararlar K-08T1-0002 (S1-S9 A; 1b'ye düşen S1-S5), K-08T1B-0002 (indirme yolu A), HANDOFF A-08T1-0050, state/pr/08-tam-1.md "08-tam-1b" bölümü (bu plan onu güncel koda göre ayrıntılandırır).

## Plan (kodlamadan önce)

### 1. Bulunan semboller ve dosyalar (worktree @ 7af41e5, rg ile)

| Sembol / dosya | Ne için |
|---|---|
| `guardrails/schemas.py:61` `PiiPolicySpec.engine: Literal["regex","ner"]`; `:180` `engine_unsupported` reddi | `ner` kabulü (additive; C4 biçimi değişmez) |
| `guardrails/findings.py:8` `Finding`; `recognizers/regex.py:132` `resolve_overlaps`, `:153` `recognize` | NER bulguları aynı tip, aynı çakışma çözümü |
| `guardrails/categories.py:53` `PERSON` (regex=False); `ORGANIZATION`, `LOCATION` | NER kategorileri var olan kodlar |
| `guardrails/builtin.py:13` `BUILTIN_VERSION = 2` | v3: egress `PERSON` tokenize (S6 aşağıda) |
| `runtime/adapters.py:334` `EngineGuard` (worker'da süreç içi motor) | worker'da model yok → `HttpNer` |
| `api/internal.py` `router` + `service_actor`, `POST /internal/embed` | `POST /internal/ner` aynı desen |
| `knowledge/ingest.py:62/73` `LocalEmbedClient` / `HttpEmbedClient` (SafeOutboundClient, `internal_api_url`, servis jetonu) | `LocalNer` / `HttpNer` aynı desen |
| `knowledge/ingest.py:358/383` `text_filter: Callable[[str], str]` (senkron); `:410` `_text_filter(document)` | `pii_ner` için async filtre yolu |
| `knowledge/ingest_mask.py:19` `TextFilterName = Literal["pii_regex"]`, `PiiRegexFilter`, `_FILTERS`, `resolve` | `pii_ner@1` |
| `knowledge/raw_ingest.py:49` `TEXT_FILTER = "pii_regex"`; `raw_staging.py:67/156` `prsim_requires_ner`; `cli.py:155/197/264` `--accept-personnel-data` | PRSIM guard'ı |
| `knowledge/models.py` `hf_path`, `required`, `missing`, `download`, `main`; Makefile `models`/`models-check`/`test-models`; `deploy/offline/models.txt` | `NER_CANDIDATES` (dilim 0) |
| `data/samples/pii/pii-100.jsonl` (PERSON 22, ORG 4, LOC 4) | ölçüm seti (değiştirilmez) |
| docs/api.md:540, docs/guardrail.md:128 | FOLLOWUP-162 MINOR-r7-1 (ilk commit) |

### 2. Kapsam / kapsam dışı

**Kapsam:** (0) FOLLOWUP-162 docs örneği; `NER_CANDIDATES` indirme/denetim; (1) `recognizers/ner.py` + ölçüm (aday tablosu: recall/precision/P95, lisans, boyut) + seçim; (2) `POST /api/v1/internal/ner` + `HttpNer` (worker, ingest); (3) `engine: ner` kabulü, yerleşik v3; (4) `pii_ner@1` filtresi, PRSIM guard'ı; (5) docs (guardrail kalite raporu, ingest/PRSIM, api).
**Kapsam dışı:** injection/topic (dilim 2), TabiBERT eğitimi (NER başlıklı hazır model yoksa elenir, ARCH-07), paycoreLLM staging (19r2, BLOCKERS 161), FOLLOWUP-162'nin 1b'ye dokunmayan kalemleri (PR notunda kısıt olarak; yalnız MINOR-r3-7 `reserve_carried` araç/KB yolu 1b'yi ilgilendirir, ayrıca değerlendirilir).

### 3. Değişecek dosyalar ve neden (dilim sırası; her dilim ayrı commit, önce kırmızı test)

0. `docs/api.md`, `docs/guardrail.md`: "a scope that has issued 9,999,999 values" (162). `knowledge/models.py`: `NER_CANDIDATES` (`allow_patterns`: config.json, README.md, tokenizer*/vocab*, special_tokens_map.json, `*.safetensors` ya da `pytorch_model.bin`), `required()` ve `download()` adayları kapsar, `models-check` listeler; `deploy/offline/models.txt` adaylar kullanıcının indirmesinden sonra kaydedilir.
1. `guardrails/recognizers/ner.py`: `NerRecognizer` (transformers `pipeline("token-classification", aggregation_strategy="simple")`, CPU, model yerel yoldan `hf_path(NER_MODEL, NER_REVISION)`; etiket eşleme `id2label` → `PERSON/ORGANIZATION/LOCATION`, eşleşmeyen etiket açık hata; kanıt `ner <repo>@<rev7> <score>`); `LocalNer` (API süreci, model kilidi + `to_thread`) / `HttpNer` (worker); `ffcore.guardrails.quality` ölçüm betiği (aday başına tablo).
2. `api/internal.py`: `POST /internal/ner` (servis hesabı; istek metinler + kategoriler; cevap span/kategori/skor, değer yok; metin sınırı 08-lite'ın 200.000'i).
3. `guardrails/schemas.py` (reddin kalkması), motorda `engine: ner` = regex + NER, `engine: regex` NER'i hiç çağırmaz; `guardrails/builtin.py` v3; `core/config.py` `ner_model`, `ner_revision` (zorunlu değil, kullanılınca fail-loud), `GUARDRAIL_NER_URL` yerine `internal_api_url` (embed ile aynı; ayrı değişken gerekmez → varsayım 2).
4. `knowledge/ingest_mask.py` `pii_ner@1` (regex + NER, async), `knowledge/ingest.py` filtre çağrısı async, `raw_ingest.py` `TEXT_FILTER` varsayılanı `pii_ner`, `raw_staging.py` PRSIM yalnız `pii_ner` ile ya da eski `accept_personnel_data` ile (deprecation uyarısı), `cli.py`.
5. `.env.example`, `deploy/docker-compose.yml` (`NER_MODEL`/`NER_REVISION` `${…:?}`, kazanan belli olunca), `docs/guardrail.md`, `docs/api.md`, ingest/PRSIM docs, `docs/degisiklikler.md`.

### 4. Sözleşme, yapılandırma, profil etkisi

- C4 donmuş: aşama/`action_taken`/`Decision` değişmez; `engine: ner` kabulü additive. C6: `text_filter` yeni ad `pii_ner` additive; eski `pii_regex@1` belgeleri değişmez. C11/C17: 1a biçimi aynen (NER kategorileri aynı `tokenize` yolundan). C12: yeni ortam değişkenleri `GUARDRAIL_EGRESS_NER` (varsayılansız, zorunlu), `NER_MODEL`, `NER_REVISION` (r1 MINOR-7).
- Profil: kodda dal yok. Yerleşik v3 `PERSON` yalnız egress aşamasında (airgap'te `GUARDRAIL_EGRESS_ENABLED=false` → NER çağrılmaz, ağırlık şartı doğmaz); `pii_ner` ingest her iki profilde aynı.
- Bellek: model yalnız API sürecinde (~0,45 GB); bellek tablosu notu.

### 5. Kabul kriteri → test adı

| # | Kriter | Test |
|---|---|---|
| 1 | Ad-soyad recall ≥ 0,85 (llmaas hedefi 0,90 raporda); kurum/konum ve precision raporda | `test_08t_1_ner_recall_person` (`-m models`), `test_08t_1b_quality_report_matches_docs` |
| 2 | TC/telefon/IBAN/e-posta ≥ 0,98, NER regex bulgusunu ezmez | `test_08t_2_regex_recall_unchanged_with_ner` |
| 3 | 1.000 karakter, yerel kurallar + NER, boşta P95 < 300 ms; tek CPU ayrıca | `test_08t_3_ner_latency_p95` (`-m models`) |
| 4 | Aday tablosu (recall/precision/P95/lisans/boyut) PR'da ve docs'ta; TabiBERT elenme gerekçesi | ölçüm betiği çıktısı |
| 5 | Ağırlık yoksa `model_missing` (ad + yol), indirme yok; `--network none` kanıtı | `test_08t_5_ner_missing_weights_fail_loud` |
| 6 | Worker'da model yüklenmez; worker ve ingest NER'i API'den alır; API kapalıysa açık hata, regex'e sessiz düşüş yok | `test_08t_6_worker_uses_http_ner`, `test_08t_6b_http_ner_down_fails_closed` |
| 15 | `pii_ner` ad-soyadı silver öncesi maskeler; PRSIM yalnız `pii_ner` ile kabul; `--accept-personnel-data` geriye uyumlu; manifest `pii_ner@1`; eski belgeler değişmez | `test_08t_15_pii_ner_filter`, `test_08t_15b_prsim_accepted_with_ner`, `test_08t_15c_old_manifest_untouched`, `test_08t_15d_prsim_refused_without_ner` |
| 16 | Yerleşik v3: egress `PERSON` tokenize | `test_08t_16_builtin_v3_person_tokenized` |
| 17 | `engine: ner` kabul, `engine: regex` NER'i çağırmaz | `test_08t_17_engine_ner_accepted`, `test_08t_17b_regex_engine_never_calls_ner` |
| 18 | `NER_CANDIDATES` `models-check`'te listelenir, `download` yalnız izinli dosyalar | `test_08t_18_ner_candidates_checked` |
| 19 | `make test` iki profil, `make test-int`, önyüz `check:api` (OpenAPI değişirse) | kapı |

### 6. Migration

Yok (`pii_policies.engine` zaten `regex|ner`; CHECK kısıtı varsa `ner`'i kabul ettiği testle doğrulanır).

### 7. Geri alma

`engine: regex` politikaları NER'i çağırmaz; yerleşik v3 → v2 sabit; `pii_ner` yalnız yeni ingest; ağırlık volume'da, imaj değişmez; `TEXT_FILTER` varsayılanı tek sabit.

### 8. Durma koşulları

Hiçbir aday ad-soyad ≥ 0,85 ya da P95 < 300 ms tutmazsa ölçüm tablosuyla KARAR-GEREK (M4 eşiği kullanıcıda). Lisanssız aday ürün seçimine giremez (K-08T1B-0002); hiç lisanslı aday kalmazsa KARAR-GEREK. C4/C6'da additive olmayan değişiklik gerekirse dur. M3 koşusu sürüyorsa ve ölçüm manifestine dokunulacaksa dur. Ağırlık yoksa NER testleri NOT_RUN; VERIFIED için `make models` şart.

### 9. Felsefe kontrolü

- **ARCH-07:** NER, llmaas'ta ad-soyadın sağlayıcıya ham gitmemesinin ve PRSIM gövdesindeki personel adının indekse girmemesinin tek yolu (TH pilotu, PRSIM bilinen sınırı). Kalıcı ek: bir tanıyıcı, bir iç uç, bir filtre; Presidio yok.
- **ARCH-09:** transformers zaten bağımlılık; ağırlık/offline `knowledge/models.py`; worker deseni `/internal/embed`; maskeleme 08-lite/1a yolları.
- **ARCH-10 / ARCH-06:** model ve revizyon açık değer; ağırlık yoksa `model_missing`; NER çağrısı düşerse regex'e sessiz düşüş yok (politika `on_error`, ingest'te belge `failed` + kod); yerleşik v3'ün NER şartı yalnız egress açıkken doğar (profil yapılandırma değeri).

## Varsayımlar ve brief'teki çelişkiler

1. Brief "model imaja gömülür" ↔ KARARLAR 04a (volume + `make models`): KARARLAR kazanır (DRIFT-151).
2. HANDOFF "`GUARDRAIL_NER_URL`" der; embed istemcisi ayrı URL değil `internal_api_url` kullanıyor. Aynı süreç aynı uçları sunduğu için ayrı değişken eklemiyorum (tek kaynak); itiraz gelirse additive eklenir.
3. GOREV (3) "NER hazır olmadan PRSIM reddedilir": `pii_ner` filtresi seçili değilse ya da ağırlık eksikse (`models.missing` NER satırı) PRSIM `prsim_requires_ner`; eski `--accept-personnel-data` yolu M3 kaydı için geriye uyumlu kalır, deprecation uyarısı loglanır.
4. TabiBERT: NER başlıklı hazır model bilinmiyor; kullanıcı HF'de gösterirse aday olarak eklenir (K-08T1B-0002).

## Kalan riskler

- n=22 PERSON: bir kaçırma ≈ 0,045; sentetik biçimler (BÜYÜK, küçük, SOYAD Ad) cased modellerde zayıf olabilir; ölçüm olduğu gibi yazılır.
- Ingest'te belge başına HTTP turu ve CPU süresi (yük altında) ayrıca ölçülür.
- Docker motoru kapalıyken birim testleri koşulamaz (araçlar Docker'da); koşu zamanı PR'da yazılır.


---

## Uygulama (kodlamadan sonra)

### Commit'ler (sırayla; her dilimde önce kırmızı test)

| Commit | Dilim | Kırmızı kanıtı |
|---|---|---|
| 12ffcd8 | FOLLOWUP-162 MINOR-r7-1 docs örneği (api.md:540, guardrail.md:128) | docs |
| e6dd8e8 → 378faff | 0: `NER_CANDIDATES` + `allow_patterns`, `models-check` listesi | e6dd8e8'de 2 düştü / 1 geçti (18b kapsama) |
| 6fe151f → cdcbd75 | 1: `recognizers/ner.py`, `engine: ner`, dört çağrı noktası | 378faff'te toplama hatası |
| 9b49514 | 2: `POST /api/v1/internal/guardrails/ner`, 08.yaml | **test kodla aynı commit'te** (sıra ihlali, açıkça) |
| d2a6ca7 → d97f290 | 4: `pii_ner@1`, PRSIM guard'ı, CLI | 9b49514'te 6 düştü + 4 hata (15c eski davranış, geçti) |
| 266c332 → e3e7eb6 | 3: yerleşik v3 `default-egress`, `GUARDRAIL_EGRESS_NER`, açılış denetimi | d97f290'da toplama hatası |
| f4f6332 | FOLLOWUP-165: iki süre testi oran + asılı-kalma tavanı | oran 3,1-4,7 (eşik 8) |
| 9db7a05 | docs | — |
| f6be9ae | test-int: `test_08_s5` yerleşik sürüm 3 | tam test-int'te kırmızı (2 bekliyordu) |

Kanıt dosyaları: `state/evidence/08t1b-*.log` (red/green dilim 0-4, maketest, maketest3).

### Değişen dosyalar (41, +1503/-94; `git diff 7af41e5..9db7a05 --stat`)

- **guardrails:** `recognizers/ner.py` (yeni), `engine.py` (NER bulguları, `EvalContext.ner`), `schemas.py` (`engine_unsupported` kalktı), `categories.py` (`NER_CATEGORIES`), `builtin.py` (v3), `service.py` (`default-egress` çözümü), `settings.py` (`GUARDRAIL_EGRESS_NER`, `check_egress_ner`), `api_schemas.py` (NER gövdeleri).
- **api / servis / runtime:** `api/guardrails.py` (iç uç, `local_ner`), `services/facade_guard.py`, `runtime/adapters.py` (`HttpNer`), `runtime/worker.py` + `main.py` (açılış denetimi), `core/readiness.py` (NER ısınma), `core/config.py` (`ner_model`, `ner_revision`).
- **knowledge:** `models.py` (adaylar), `ingest_mask.py` (`pii_ner@1`, async `mask`), `ingest.py` (filtre await), `raw_ingest.py` (filtre parametresi, NER ön denetimi, M3 kipi), `raw_staging.py` (`text_filter`, `is_prsim`), `cli.py`.
- **yapılandırma:** `deploy/docker-compose.yml` (`GUARDRAIL_EGRESS_NER` `${…:?}`, `NER_MODEL`, `NER_REVISION`), `.env.example`, `.env.test`, `scripts/m3_preflight.py`.
- **OpenAPI:** `backend/openapi/08.yaml` (yalnız ek; önyüz bu dosyayı tüketmiyor).
- **testler:** yeni `test_08t_ner.py`, `test_08t_15_pii_ner.py`, `test_08t_16_builtin_v3.py`, `test_08t_18_ner_candidates.py`; güncellenen `test_08_engine.py`, `integration/test_08_api.py` (`engine_unsupported` iddiaları yeni davranışa), `integration/test_19_ingest_raw.py` (`pii_regex` açık), `test_03a_write_flag.py`, `test_19_preflight.py`, `contract/test_08_openapi.py`, `test_08t_r3_url_scan.py` (FOLLOWUP-165).
- **docs:** `guardrail.md`, `bilgi-tabani.md`, `api.md`, `paycore-entegrasyon.md`.

### Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Ad-soyad recall ≥ 0,85 (llmaas 0,90 raporda) | `test_08t_1_ner_recall_person` (`-m models`) | **NOT_RUN** (ağırlık yok, ENV-163); yazılmadı, ağırlıkla gelir |
| 2 | TC/telefon/IBAN/e-posta ≥ 0,98 regresyonsuz, NER regex'i ezmez | `test_08t_2b_ner_never_overrides_a_regex_finding` (birim); gerçek modelle `test_08t_2_*` | birim geçti; model koşusu NOT_RUN |
| 3 | 1.000 karakter P95 < 300 ms | `test_08t_3_ner_latency_p95` (`-m models`) | **NOT_RUN** |
| 4 | Aday tablosu, lisans, boyut; TabiBERT elenme gerekçesi | ölçüm betiği | **NOT_RUN**; kazanan seçimi ertelendi (K-08T1B-0006: ölçümsüz seçim yok) |
| 5 | Ağırlık yoksa `model_missing`, indirme yok | `test_08t_5_ner_missing_weights_fail_loud`, `test_08t_5b_unknown_label_fails_at_load`, `test_08t_5c_ner_not_configured_is_loud` | geçti; `--network none` konteyner kanıtı ağırlıkla |
| 6 | Worker'da model yok, NER API'den; API düşerse fail-closed | `test_08t_6_worker_uses_http_ner`, `6b_ner_down_fails_closed`, `6c_http_ner_rebuilds_values_and_checks_model`, `6d_internal_ner_returns_spans_not_values` | geçti |
| 15 | `pii_ner` maskesi, PRSIM kabul/ret, eski manifest | `test_08t_15_*`, `15b`, `15c`, `15d`, `15e` | geçti |
| 16 | Yerleşik v3 egress PERSON; metin aşamaları NER çağırmaz; açılış denetimi; dış agent aynı politika | `test_08t_16_*` (a-g) | geçti |
| 17 | `engine: ner` kabul; `engine: regex` NER çağırmaz | `test_08t_17*` | geçti |
| 18 | Adaylar `make models` ile, yalnız izinli dosyalar | `test_08t_18*` | geçti |
| 19 | `make test` iki profil, `make lint`, test-int | kapı | make test/lint geçti; test-int aşağıda (ortam dışı kırmızılar ayrık) |

### Çalıştırılan komutlar

| Komut | Ortam | Exit | Sonuç |
|---|---|---|---|
| `make test` (tools 0.0.0-main + worktree, `--no-deps`) | `DEPLOY_PROFILE=llmaas`, `FAKE_LLM` varsayılan | 0 | 1572/1572 (e3e7eb6) |
| `make test` | `DEPLOY_PROFILE=airgap` | 0 | 1572/1572 (e3e7eb6) |
| `make lint` | — | 0 | temiz (e3e7eb6); f4f6332/9db7a05'te ruff check + format --check temiz |
| `pytest tests/unit/test_08t_r3_url_scan.py` ×2 | llmaas | 0 | 6/6 (f4f6332) |
| `make test-int` (tam) | yığın ffcore-08t1b: postgres, redis, litellm, fake-llm, qdrant; `DEPLOY_PROFILE=llmaas` | 2 | 844 geçti, 9 düştü, 3 hata, 5 atlandı (22 dk); `state/evidence/08t1b-testint-llmaas.log` |
| `make test-int` (tam) | aynı yığın; `airgap` | 2 | 843 geçti, 9 düştü, 4 hata, 5 atlandı; `08t1b-testint-airgap.log` |
| hedefli test-int `test_08_api`, `test_06b_direct`, `test_19_ingest_raw` (f6be9ae) | aynı yığın; airgap ve llmaas | 0 | 67 geçti, 1 atlandı (her profil); `08t1b-testint-targeted-*.log` |
| `make models` | kullanıcı makinesi | — | **NOT_RUN** (ENV-163, kullanıcıda) |

Tam test-int kırmızılarının dökümü (iki profil aynı):
- **Bu daldan, düzeltildi:** `test_08_s5_builtin_default_listed_until_overridden` (`builtin_version` 2 bekliyordu) → f6be9ae; hedefli koşu iki profilde yeşil.
- **Ortam (yalın yığında olmayan servisler, bu dal dokunmuyor):** `test_02_langfuse` 3 test (Langfuse yok), `test_05a_live_services` 5 test (backend/mcp-sql/mcp-search konteynerleri yok), `test_18td_tools_api` 3 hata (ticket-desk yok).
- **Koşu sırası:** airgap `test_06b_9` kurulum hatası: aynı LiteLLM, llmaas koşusundan kalan model kaydını silerken `/model/delete` 400; hedefli airgap koşusunda geçti.
Tam yığınla (Langfuse, mcp-*, ticket-desk) koşu inceleyicinin yığınında.

Not: d97f290'daki ilk llmaas koşusunda 1a'nın `test_08t_r3_long_line_in_one_character_pieces` süre testi yük altında düştü (1562/1563); tek başına 4/4 geçti; FOLLOWUP-165 ile f4f6332'de oran testine çevrildi.

### Varsayımlar (planın 1-4'üne ek)

5. `pii_ner` ingest'te yalnız `PERSON` maskelenir (kurum/konum kişi verisi değil; PRSIM bilinen sınırı kişi adıydı).
6. `ingest-raw`'da filtre seçeneği yok (plan/19 "maskeleme adla kapatılamaz" testi); yeni ingest `pii_ner`, `--accept-personnel-data` M3 ölçüm kipi = `pii_regex@1` (ölçülen manifest değişmez). Koordinatörün kabul ettiği varsayım 3'ün ("geriye uyumlu + deprecation") uygulaması budur: bayrak çalışır ve loglanır.
7. NER erişilemezse PRSIM içeren `ingest-raw` `prsim_requires_ner` (CLI çıkış 2, DB'den önce; eski sözleşme kodu korunur), diğer kaynaklar `ner_unavailable`.
8. Proje `default-egress` anahtarlı PII politikası saklarsa yerleşiği geçersiz kılar; saklamazsa ve `default` saklıysa egress PII'si ondan türetilir (r1 MAJOR-1 A). r1 MINOR-4 ile yerleşik `default-egress` PII listesinde `builtin: true` görünür ve saklı zincirde başvurulabilir.
9. `NER_MODEL`/`NER_REVISION` compose'da `${…:-}` (koşullu zorunluluk compose'da ifade edilemiyor); zorunluluğu açılış denetimi uygular.

### Kalan riskler

- Ölçüm yapılmadı: kazanan model, lisans (savasy kartında lisans etiketi olmayabilir; K-08T1B-0002: ürün seçimine giremez), `id2label` gerçek etiketleri ve P95 bilinmiyor. `ner_label_unknown` gerçek kartta tetiklenebilir.
- Uzun metin pencereleri (`stride=128`) yalnız gerçek modelle doğrulanır; sahte pipeline bunu kanıtlamaz.
- **Dağıtım:** `GUARDRAIL_EGRESS_NER` olmayan `.env` ile yığın açılmaz (PayCore sunucusu dahil, DECISION-166).
- 9b49514'te test ayrı kırmızı commit olarak yazılmadı.
- FOLLOWUP-162'nin 1b dışı kalemleri bu PR'da yok (MINOR-r3-7 `reserve_carried` araç/KB yolu dahil).

## r1 düzeltmeleri (K-08T1B-0010 DUZELT, KARARLAR "08 tam 1b r1 kararları")

**HEAD:** 4567ed62f63f0f0d0276c88e909c0d16838bfaa8 · f6be9ae'nin üstüne 22 commit (`git diff f6be9ae..HEAD --stat`: 29 dosya +1184/-109). Her bulgu için önce test commit'i, sonra kod commit'i; kırmızı kanıtları `state/evidence/08t1b-r2-red-*.log`.

| Bulgu | Test commit | Kod commit | Test | Ne değişti |
|---|---|---|---|---|
| MAJOR-1 (A) | 1c2f288 | 10de8fe | `test_08t_19_egress_from_default.py` (4) | `default-egress` saklı değilse ve `default` saklıysa egress PII'si `default`'tan türetilir (kategoriler, özel desenler; NER açıksa `PERSON` + `engine: ner`). Yerleşik beşli yalnız ikisi de yoksa. docs'taki "version 2's egress" cümlesi üç adımlı çözüm sırasıyla değişti. |
| MAJOR-2 | 0ddca77 | ee3404f | `test_08t_20_http_ner_windows.py` (4; 250.000 karakter, sahte HTTP NER 200.000 üstüne 422) | `HttpNer` 200.000 karakteri aşan metni 2.000 karakter örtüşmeli pencerelerle gönderir, offset'i kaydırır, örtüşen span'ları birleştirir (birleşimde skoru yüksek olanın kategorisi). Pencere sınırı `NerRequest` sınırıyla aynı sabit (`NER_TEXT_MAX_CHARS`). |
| MAJOR-3 | 2c92e32 | 0435695 | `test_08t_21_text_filter_mismatch.py` (2, entegrasyon) | Aynı bayt + kayıtlı filtre ≠ koşu filtresi: yeniden işleme yok. `text_filter_mismatch` sayacı konsol satırında ve manifestte. Manifest `text_filters`: filtre başına belge/chunk, DB'deki `metadata.text_filter`'dan. PRSIM M3 `failed` kaydı bayraksız koşuda dönüştürülmüyor. |
| MAJOR-4 | 27a1bbd | 01bdda5 | `test_08t_22_attachment_names.py` (2, entegrasyon) | Ekin görünen adı (Attachment.filename, silver `# Ek:` başlığı, chunk breadcrumb'ı) PRSIM'de `Ek <n>`. Diğer kaynaklarda ad, `_`/`-` boşluğa çevrilip filtreden geçer. Kapı 0 ve dönüştürücü gerçek adı görür; `raw_path` aynı. |
| MINOR-1 (A) | f5345cc | e6a0669 | `test_08t_23_egress_ner_fail_loud.py` (6; E4 probe senaryosu) | Egress'te enforce kural için NER hatası `on_error`'dan bağımsız `503 ner_unavailable` (`NerEgressUnavailable`, değer içermez). Metin aşamalarında `on_error` sürer. |
| MINOR-2 | 26fba3d | 11d3b6c | `test_08t_24_ner_transport_errors.py` (3) | `HttpNer` `EgressError`'ı (ret, DNS, zaman aşımı) `NerUnavailable`'a sarar. CLI'da PRSIM'le çıkış 2 + `prsim_requires_ner`, traceback yok. |
| MINOR-3 | 570f03d | 7373e74 | `test_08t_25_ner_weights_at_startup.py` (3) | API açılışında `check_ner_weights`: egress + NER açıkken `hf_path(NER_MODEL, NER_REVISION)` yoksa (yalnız varlık) `model_missing` ile durur. Agent worker'da model önbelleği yok (compose), denetim API'nin. docs ve `.env.example` buna göre. |
| MINOR-4 | 6f72540 | 3fcdfce | `test_08t_26_builtin_egress_key.py` (2, entegrasyon) | `default-egress` kullanılabilir anahtar. PII listesinde `builtin: true` (`resolve_pii`'nin verdiği spec). Test paneli `builtin`: o anahtarda saklı kayıt yok. GET'teki yerleşik zincir POST ile 201. `08.yaml`'da yalnız `builtin` açıklaması değişti. |
| MINOR-5/6 | 12fcfe8 | ffea023 | `test_08t_27_ner_span_trim.py` (6; E6'nın iki yazımı) | NER span'ı, regex/özel bulgunun ve mevcut `<<PII_n>>`'in dışında kalan parçalara kırpılır (kenarlar alfanümeriğe kadar; 2 karakterden kısası atılır). Motor ve `pii_ner` filtresi aynı `trim_names`'i kullanır. |
| MINOR-7, NOTE-1 | — | 8d97e65 | — (metin) | docs PayCore satırı DECISION-166'ya (açık, kullanıcı kararı) bağlandı. `.env.example`: "ölçüm dalında doldurulur". Bu PR'ın §4 C12 satırı düzeltildi. Kod yorumlarında yol `/api/v1/internal/guardrails/ner`. |
| NOTE-9 | e530f82 | — | `test_08t_28_internal_ner_http_auth.py` (1, entegrasyon) | HTTP yetki: anonim 401, üye 403 `service_account_required`, servis 200, cevapta değer yok. Davranış zaten doğruydu; kırmızısı yok (regresyon testi). |
| — | — | 4567ed6 | — | ruff format ve satır boyu (davranış değişmez). |

Değişen eski testler (kararla tersine dönen davranış; gerekçe test yorumunda):
- `test_08t_6b`: egress'te NER düşünce block yerine `NerEgressUnavailable` (MINOR-1 A).
- `test_08t_2b` ve `test_08t_15_pii_ner_never_overrides_regex`: çakışan NER span'ı atılmak yerine kırpılıyor (MINOR-5); regex bulgusu kategorisini koruyor.

Sıra notları:
- MAJOR-3 testi kırmızıdan önce bir kez sıkılaştırıldı (amend): ikinci koşu ayrı dönüştürücüyle çağrıldığı için `calls == []` boşuna geçiyordu.
- MINOR-1 testinde geçersiz `on_error: log` parametresi kod commit'inde düzeltildi (`ON_ERROR` yalnız `block`/`allow`).

### r2 komutları ve sonuçları

Tools 0.0.0-main + worktree kodu.
- Birim: `docker compose -p w08t1b --env-file .env.test run --rm --no-deps -e DEPLOY_PROFILE=<p> tools make test`.
- Entegrasyon: `ffcore-08t1b` yalın yığın (postgres, redis, litellm, fake-llm, qdrant; K-08T1B-0012), `-w /work/backend tools python -m pytest -q <dosyalar>`.

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make lint` | temiz (ruff check + format --check, 443 dosya) | `08t1b-r2-lint.log` |
| `make test` llmaas | 1598 passed | `08t1b-r2-maketest-llmaas.log` |
| `make test` airgap | 1598 passed | `08t1b-r2-maketest-airgap.log` |
| Hedefli test-int llmaas (08t_21/22/26/28, 08_api, 19_ingest_raw, 06b_direct, 04a_api) | 87 passed, 1 skipped (test_19 :ro mod testi, root dosya modunu yok sayar; önceki turlarla aynı) | `08t1b-r2-testint-targeted-llmaas.log` |
| Hedefli test-int airgap (aynı dosyalar) | 87 passed, 1 skipped (aynı) | `08t1b-r2-testint-targeted-airgap.log` |
| Kırmızı kanıtları | MAJOR-1/2/3/4, MINOR-1/2/3/4/5-6 kırmızı | `08t1b-r2-red-*.log` |
| Ölçüm, `-m models`, `--network none`, gerçek NER | NOT_RUN: ağırlık yok (ENV-163) | — |

### r2 varsayımları

10. (MAJOR-3) `text_filter_mismatch` bir ret sayacıdır, `failed` değil.
    - CLI çıkış kodunu değiştirmez (diğer `rejected` kodları gibi); konsolda ve manifestte ayrı satır.
    - Farklı baytlı yeni sürüm koşunun filtresiyle yazılır (yeni kayıt).
    - Filtresiz eski kayıt (`text_filter` yok) `none` etiketiyle sayılır ve aynı baytta reddedilir.
11. (MAJOR-2) Örtüşen span'lar birleşince kategori, skoru yüksek olanınkidir. Pencereler sözcük sınırı aramaz; 2.000 karakterlik örtüşme, kesilen adı sonraki pencerede bütün verir.
12. (MAJOR-4) `Ek <n>` numarası belge metadata'sındaki ek sırasıdır (1'den). Kaynak PRSIM ise bayraktan (M3) bağımsız `Ek <n>`. Filtresiz belgede (C6 `text_filter` yok) ek adı olduğu gibi kalır (main ile aynı).
13. (MINOR-1) Yalnız enforce egress kuralında geçerli. Monitor bir egress kuralı zaten maskelemez; hatası kaydedilir (`rule_error`), yükseltilmez (`test_08t_23c`).
14. (MINOR-5/6) "Bay <<PII_1>> Hanım" span'ında "Bay" ve "Hanım" ayrı PERSON değeri olur: fazla maskeleme, sızıntı değil.

### r2 kısıtları (FOLLOWUP, bu PR'da yok)

- FOLLOWUP-167 (NOTE-6): paycoreLLM `ffcore_stage_raw.py` PRSIM'i hâlâ yalnız M3 bayrağıyla stage ediyor. Bayraksız `pii_ner` PRSIM akışı için stager değişikliği gerekecek; bugün daha sıkı, sızıntı yok.
- FOLLOWUP-168 (NOTE-2/3/4/5/8), ölçüm dalında:
  - `local_ner()` kilitsiz kayıt ve tek kilitli çağrı (ölçümle bakılacak);
  - `stride` pencerelemesinin gerçek modelle doğrulanması;
  - docs kanıt biçimi, OpenAPI 503 listesi, `/readyz` `ner_label_unknown`;
  - `test_08t_secrets_linear` mutlak süre;
  - airgap `ingest-raw`'da NER ihtiyacının docs'ta açık yazılması.

## r2 ekleri, merge öncesi küçük tur (K-08T1B-0015, KARARLAR "08 tam 1b r2 ekleri")

**HEAD:** 7815d333671c53ebab48b20d51ff3661984946da · 4567ed6'nın (r2) üstüne 10 commit (`git diff 4567ed6..HEAD --shortstat`: 18 dosya, +350/-30). Önce test commit'i, sonra kod commit'i.

| Bulgu | Test commit | Kod commit | Test | Ne değişti |
|---|---|---|---|---|
| MINOR-r2-1 | add0c6d | 9352f06 | `test_08t_22c` (entegrasyon) | Tek kişisel veri kuralı: `raw_staging.personnel_data(source, relpath)` (kaynak PRSIM ya da yol PRSIM). Staging ve ek adı aynı kuralı kullanır; yolla PRSIM olan dosyanın eki `Ek <n>`. |
| MINOR-r2-2 | 37819c8 | 31a6bf0 | `test_08t_27e/27f` (birim) | NER span'ı yalnız eşikten ve örtüşme çözümünden geçen bulguların çevresinde kırpılır; eşik altı regex bulgusu adı kesmez. |
| MINOR-r2-4 | 2f77f2e | 2ab04db | `test_08t_29_manifest_filter_buckets.py` (birim) | Manifestte kayda girmemiş dosyalar `unregistered` kovasında; `none` yalnız gerçekten filtresiz kayıt. |
| NOTE-5 | e8b42ec | fb8ef38 | `test_08t_30_reindex_prsim.py` (2, entegrasyon) | `reindex_silver` iş düzeyinde: kapsamda `pii_regex` ile yazılmış kişisel veri kaydı varsa, hiçbir belgeye dokunmadan `ReindexRefused(prsim_requires_ner)`. `--accept-personnel-data` (yalnız CLI, M3) geçirir. CLI kuyruğa almadan önce denetler, çıkış 2. API gövdesinde bayrak yok. |
| MINOR-r2-3 | — | df38cd3 | — (metin; `test_08_openapi` yeşil) | `ner_unavailable`: docs/api.md (503 doğrudan, harici, istemci geçmişi denetimi, internal evaluate; facade agent koşusunda 502 koşu kodu), agentlar.md, guardrail.md; evaluate docstring'i ve yeniden üretilen `08.yaml` açıklaması; ner.py, NerUnavailable, `pii_ner` docstring'leri. |
| — | — | 7815d33 | — | ruff format (davranış değişmez). |

### r3 komutları ve sonuçları

| Koşu | Sonuç | Kanıt |
|---|---|---|
| Kırmızılar | r2-1: 1 düştü · r2-2: 2 düştü · r2-4: 1 düştü · NOTE-5: 2 düştü | `08t1b-r3-red-*.log` |
| Yeşiller (bulgu başına) | r2-1, r2-2, r2-4 yeşil | `08t1b-r3-green-r2-*.log` |
| NOTE-5 + r2-1 (08t_30, 08t_22), Docker dönüşünden sonra yeniden açılan yığında | 5 geçti | `08t1b-r3-green-note5.log` |
| `make lint` | geçti | `08t1b-r3-lint.log` |
| `make test` llmaas | 1601 geçti | `08t1b-r3-maketest-llmaas.log` |
| Hedefli test-int llmaas (08t_21/22/26/28/30, 19_ingest_raw, 04a_api) | 44 geçti, 1 atlandı (`test_19` :157, root dosya kipini yok sayar; önceden var) | `08t1b-r3-testint-targeted-llmaas.log` |
| airgap | NOT_RUN bu turda (DUZELT tek profil istedi; r2'de iki profil yeşildi) | — |

Not: Docker kesintisi (ENV-171, 00:46-02:53) sırasında ilk NOTE-5 yeşil denemesi motor hatasıyla düştü; o log Docker dönüşündeki gerçek koşuyla değiştirildi.

### r3 varsayımları

15. (NOTE-5) Denetim yalnız `silver` katmanında; `gold` yeniden dönüştürme yapmaz. Eski kayıt `text_filter` taşımıyorsa reddedilmez (M3 değil).
16. (r2-1) `personnel_data` kaynak adı ya da göreli yoldan biri PRSIM ise doğru (`_is_prsim(_norm(source)) or _prsim_path(relpath)`).
