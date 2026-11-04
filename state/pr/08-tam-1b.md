# PR: 08 tam dilim 1b — Türkçe NER tanıyıcısı, `/internal/ner`, `pii_ner` ingest filtresi, PRSIM guard'ı

**Paket:** 08-tam-1b · **Sınıf:** [B]; NER ağırlıkları [C] (kullanıcı `make models`, K-08T1B-0002 A) · **Branch:** feat/08-tam-1b-ner · **Baz commit:** 7af41e5 (main; 1d836a0 + yalnız state commit'leri) · **Oturum:** ffcore-isci-a-08-tam-1b (Opus 5.5) · **Durum:** PLANNED

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

- C4 donmuş: aşama/`action_taken`/`Decision` değişmez; `engine: ner` kabulü additive. C6: `text_filter` yeni ad `pii_ner` additive; eski `pii_regex@1` belgeleri değişmez. C11/C17: 1a biçimi aynen (NER kategorileri aynı `tokenize` yolundan). C12: yeni ortam değişkenleri `NER_MODEL`, `NER_REVISION`.
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
