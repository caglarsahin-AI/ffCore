# PR 1c-a: 08 tam dilim 1c — FOLLOWUP-168/172/174 (ağırlıksız); ölçüm 1c-b'de

**Paket:** 08-tam-1c-olcum · **Sınıf:** [B]; ağırlık indirme [C] kullanıcıda (ENV-163) · **Branch:** feat/08-tam-1c-olcum · **Baz commit:** 8aa8442 (main; 63ffb16 + state) · **Oturum:** ffcore-isci-a-08-tam-1c-olcum (Opus 5.5) · **GOREV:** K-08T1C-0001, iş sırası A (K-08T1C-0002) · **Durum:** r1 ONAY + DUZELT küçük (K-08T1C-0009) uygulandı · **HEAD:** 60c6169c93b65399b25283b63f096c8e4cec4732 (15 commit; r1 HEAD a4ec5f5) · D6-D8 ölçüm ayrı PR 1c-b (`feat/08-tam-1c-b-olcum`, ENV-163 sonrası)

## Plan

1. **Bulunan semboller ve dosyalar** (worktree'de `rg`):
   - `guardrails/recognizers/ner.py`: `LocalNer` (`_lock` hem `load` hem `_recognize`, :192-209), modül sözlüğü `_local` + `local_ner()` kilitsiz (:212-221), `windows()`/`STRIDE` (:159, :285).
   - `api/knowledge.py:505-526` `reindex_knowledge_base`: 202, `queue.enqueue("reindex_job", ...)`, ön denetim yok.
   - `knowledge/ingest.py:761-782` `check_reindex_silver` (bayrakla hemen döner, log yok), `:826` `reindex_silver` ilk satırda çağırır.
   - `cli.py:79-111, 147, 271-281` reindex CLI `--accept-personnel-data`; `raw_ingest.py:321-325` ingest-raw M3 kipi `log.warning` (örnek desen).
   - `knowledge/models.py:33` `NER_CANDIDATES`, `NER_ALLOW_PATTERNS`; Makefile `models`/`models-check`/`test-models` (:34-44).
   - Testler: `backend/tests/unit/test_04a_convert.py:191` `test_04a_9d` (30 s mutlak), `test_08t_secrets_linear` (2 s mutlak).
   - Ağırlık: `04a-knowledge-core_model_cache` hub'ında NER adayı **yok** (A-08T1C-0003, 10:55).
2. **Kapsam:** ağırlıksız: FOLLOWUP-168 NOTE-1/2a/4/5/8, FOLLOWUP-172 N1/N2 (+ r3 N2'nin `--layer gold` bayrak kenarı). Ağırlıkla: `--network none` `models-check`, lisans + `id2label`, kriter 1/3/4 ölçümü (`-m models`), NOTE-2b tek kilit gecikmesi, NOTE-3 pencere/stride, kazanan `NER_MODEL`/`NER_REVISION`, kaybeden temizliği, `GUARDRAIL_EGRESS_NER=true` egress PERSON testi. **Kapsam dışı:** r3 NOTE-3/4/5/6/9-11 (FOLLOWUP-172 dışı; gerekirse ayrı kayıt), paycoreLLM stager (r1 NOTE-6), injection sınıflandırıcısı ve akış tamponlayıcı (08 tam sonraki dilimler).
3. **Dilimler ve dosyalar** (her dilimde önce kırmızı test commit'i, sonra kod):
   - **D1 (168 NOTE-2a):** `ner.py` `local_ner()` modül kilidi (çift denetim); iki iş parçacığı aynı anda → tek `LocalNer`, tek yükleme.
   - **D2 (168 NOTE-5):** `test_08t_secrets_linear` mutlak 2 s → CPU süresi oranı (4x girdi, sınır 8, en iyi 3) + asılı kalma koruması (FOLLOWUP-165 `url_scan` deseni); `test_04a_9d` mutlak 30 s → yapılandırılan zaman aşımına göre bağıl sınır + asılı kalma koruması (testin iddiası değişmez: zaman aşımında işçi öldürülür, sıradaki belge sürer).
   - **D3 (172 N1):** `api/knowledge.py` reindex ucu kuyruğa yazmadan `check_reindex_silver` (silver katmanında) → 409 `prsim_requires_ner` (OpenAI hata şeması, `@audited` `outcome=denied`); iş denetimi derinlik savunması olarak kalır; OpenAPI'ye 409 yanıtı (additive).
   - **D4 (172 N2):** `check_reindex_silver` bayrakla dönerken etkilenen kişi verisi kaydı sayısını `log.warning` ile yazar (ingest-raw deseni) ve CLI yolu `audit_events`'e sistem aktörlü olay yazar (`reindex_personnel_data_accepted`, sayılar; içerik yok); `--accept-personnel-data` + `--layer gold` açık hata (çıkış 2, `flag_not_applicable`), sessiz etkisizlik yok.
   - **D5 (168 NOTE-1/4/8, docs):** kod yorumlarında uç yolu `/api/v1/internal/guardrails/ner`; docs kanıt biçimi 7 karakterlik revizyon (kodla aynı); `08.yaml` iç NER ucuna 503 yanıtı (açıklamada vardı, listede yok; additive); `/readyz` docs `ner_label_unknown`; `docs/bilgi-tabani.md` + `guardrail.md` airgap'te `pii_ner` varsayılanı ve `ner_unavailable` (M3 bayrağıyla geçer) netliği.
   - **D6 (ağırlık, ENV-163 sonrası):** `--network none` `models-check`; lisans ve `id2label` model kartından (offline); `ner_label_unknown` gerçek etiketlerle.
   - **D7 (ağırlık):** `-m models` testleri `test_08t_1_ner_recall_person`, `test_08t_3_ner_latency_p95`, ölçüm betiği (kriter 4: iki aday, `pii-100.jsonl`, PERSON/ORG/LOC recall/precision, P95 boşta + tek CPU, boyut, lisans); NOTE-3 pencere iddiası (uzun metinde `model_max_length` ve bölünme gerçek modelle); NOTE-2b eşzamanlı çağrıda tek kilit gecikmesi ölçümü (rapor; kilit değişikliği yalnız ölçüm gerektirirse, ayrı karar).
   - **D8 (ağırlık):** kazanan `NER_MODEL`/`NER_REVISION` (`.env.example` llmaas, compose `${…:?}` zaten), `deploy/offline/models.txt`, kaybeden `NER_CANDIDATES`'ten çıkar + cleanup listesine (volume'dan silmeyi kullanıcı yapar); `GUARDRAIL_EGRESS_NER=true` ile egress PERSON tokenize testi (`-m models`); `docs/guardrail.md` Türkçe PII kalite raporu.
4. **Sözleşme, yapılandırma, profil:** C4 değişmez; C12'de yeni ad yok (yalnız `.env.example` değerleri); reindex 409 ve iç NER 503 OpenAPI'ye additive; `GUARDRAIL_EGRESS_NER` `.env.test` `false` kalır (ağırlıksız kapılar). Profil farkı yalnız `.env.example` değerleri; testler iki profil.
5. **Kabul kriteri → test:** brief 08 kriter 1 → `test_08t_1_ner_recall_person` (`-m models`); kriter 3 → `test_08t_3_ner_latency_p95` (`-m models`); kriter 4 → ölçüm betiği + `test_08t_1b_quality_report_matches_docs`; D1 → `test_08t1c_1_local_ner_single_load`; D2 → `test_08t_secrets_linear` (oran), `test_04a_9d` (bağıl); D3 → `test_08t1c_3_reindex_api_409_prsim`, `test_08t1c_3b_reindex_api_ok_without_personnel`; D4 → `test_08t1c_4_reindex_m3_logged_and_audited`, `test_08t1c_4b_accept_flag_with_gold_refused`; D5 → `test_08_openapi` (503/409 yanıtları); D8 → `test_08t1c_8_egress_person_tokenized` (`-m models`).
6. **Migration:** yok.
7. **Geri alma:** kod değişiklikleri bayraksız ve küçük; 409 ön denetimi kaldırılırsa iş denetimi yine reddeder. Kazanan model `.env.example` değeri; geri dönüş eski değer + `make models`.
8. **Durma koşulları:** (a) iki adayın da lisansı kartta yoksa ya da ürün kullanımına uygun değilse → KARAR-GEREK (lisanssız aday seçilmez); (b) iki aday da ad-soyad recall < 0,85 → KARAR-GEREK (M4 eşik kararı kullanıcıda, DECISION-3); (c) gerçek `id2label` `PER/ORG/LOC` eşlemesine oturmuyorsa → KARAR-GEREK; (d) D4 audit olayı için yeni `action` adı kabul edilmezse koordinatöre; (e) main kapısı koşarken test başlatmam (KARARLAR "Üç yığın sınırı bellek sınırıdır").
9. **Felsefe kontrolü:** ARCH-07: her dilim mevcut bir yolun boşluğunu kapatır (kilit, görünürlük, test kararlılığı, docs); yeni kalıcı yüzey yalnız 409 yanıtı ve bir audit eylemi. ARCH-09: NER pencereleme `transformers` pipeline'ında; ayrı bölücü yazılmaz (NOTE-3 yalnız doğrular); audit 03b decorator/olay tablosu. ARCH-10/06: kazanan seçimi ölçümle ve `.env.example`'da açık, "auto" yok; `--layer gold` ile bayrağın sessizce etkisiz kalması açık hataya çevrilir; 409 iş reddinin sessiz 202'sini görünür yapar.

## Değişen dosyalar
`git diff --stat $(merge-base)..HEAD`: 17 dosya, +412/-61; state yok.
- kod: `backend/ffcore/cli.py` ayrıca FOLLOWUP-174 (`ingest-raw --text-filter`); `backend/ffcore/guardrails/recognizers/ner.py` (D1 kayıt kilidi), `api/knowledge.py` (D3 409), `knowledge/ingest.py` (D4 sayım + log; `check_reindex_silver` artık `int` döner, çağıranlar dönüşü kullanmıyordu), `cli.py` (D4 audit + `flag_not_applicable`), `api/guardrails.py` (D5 503 yanıtı)
- OpenAPI: `backend/openapi/08.yaml` (yeniden üretildi; yalnız iç NER ucuna 503, additive)
- testler: yeni `tests/unit/test_08t1c_1_local_ner_single_load.py`, `tests/unit/test_08t1c_6_ingest_raw_text_filter.py` (174); `tests/unit/test_19_raw_staging.py` (S1 testi, aşağıda); `tests/unit/test_08t_secrets_linear.py` (oran), `tests/unit/test_04a_convert.py` (9d koruma), `tests/integration/test_08t_30_reindex_prsim.py` (+4 test), `tests/contract/test_08_openapi.py` (+1)
- docs: `docs/api.md`, `docs/bilgi-tabani.md`, `docs/guardrail.md`, `docs/paycore-entegrasyon.md` (174 satırı)

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| D1 (168 NOTE-2a) | eşzamanlı ilk çağrıda tek `LocalNer`, tek yükleme | `test_08t1c_1_local_ner_single_load` | geçti; e6d3ebf'de düştü (4 yükleme) |
| D2 (168 NOTE-5) | doğrusallık CPU oranıyla, mutlak süre yalnız asılı kalma koruması | `test_08t_m4_*` (oran < 8, 4x girdi), `test_04a_9d` (< 300 s, uyku 600 s) | geçti; eski kare desen aynı ölçümde oran 20,7 (yakalanıyor) |
| D3 (172 N1) | silver reindex ucu kişi verisi kaydında 409, kuyruk boş, audit `error` | `test_08t1c_3_reindex_api_409_prsim`, `test_08t1c_3b_reindex_api_ok_without_personnel` | geçti; f62f4f4'te düştü (202) |
| D4 (172 N2) | M3 kipi `records=N` logu + sistem aktörlü audit (yalnız sayılar); gold + bayrak çıkış 2 | `test_08t1c_4_reindex_m3_logged_and_audited`, `test_08t1c_4b_accept_flag_with_gold_refused` | geçti; 3bfa9b5'te düştü (log yok; çıkış 0) |
| D5 (168 NOTE-4) | iç NER 503 yanıt listesinde | `test_08t1c_5_internal_ner_503_listed` | geçti; 2771e24'te düştü |
| 174 | `--text-filter pii_regex` NER'siz, M3 bayrağından ayrı; PRSIM yine ret; varsayılan `pii_ner`; M3 + açık `pii_ner` çatışma; kapatma seçimi yok | `test_08t1c_6_*` (6, 6b, 6c, 6d, 6e) | geçti; 627e067'de 6/6b/6d düştü (6c/6e değişmeyen davranışın koruması) |
| plan/19 S1 | maskeleme adla kapatılamaz | `test_19_s1_masking_cannot_be_disabled` (güncellendi) | geçti |
| brief 08 kriter 1 | ad-soyad recall ≥ 0,85 | `test_08t_1_ner_recall_person` (`-m models`) | NOT_RUN (ENV-163) |
| brief 08 kriter 3 | 1.000 karakter P95 < 300 ms | `test_08t_3_ner_latency_p95` (`-m models`) | NOT_RUN (ENV-163) |
| brief 08 kriter 4 | aday tablosu, lisans, boyut | ölçüm betiği | NOT_RUN (ENV-163) |

## Çalıştırılan komutlar
Hepsi `FFCORE_VERSION=0.0.0-main`, `--env-file .env.test`, tools konteyneri (host'ta araç yok); kanıt `state/evidence/08t1c-*.log` (tee).
| Komut | Ortam | Exit | Süre |
|---|---|---|---|
| hedefli birim D1/D2/D5 (kırmızı ve yeşil) | `--no-deps` | 1 → 0 | < 15 s |
| hedefli test-int `test_08t_30`, `test_04a_api`, `test_19_ingest_raw` | yalın yığın `ffcore-08t1c` (postgres, redis, litellm, fake-llm, qdrant) | 0; 40 passed / 1 skipped | 96 s |
| `make lint` (D1-D5) | | 0 (446 dosya) | |
| `make test` (D1-D5) | llmaas / airgap | 0; 1603 / 1603 | 164 / 176 s |
| hedefli 174 + S1 + CLI testleri | `--no-deps` | 1 → 0; 33 passed | 6 s |
| **`make lint` (HEAD a4ec5f5)** | | 0 (447 dosya); `08t1c-a-lint.log` | |
| **`make test` (HEAD a4ec5f5)** | `DEPLOY_PROFILE=llmaas FAKE_LLM=1` | 0; 1608 passed; `08t1c-a-test-llmaas.log` | 174 s |
| **`make test` (HEAD a4ec5f5)** | `DEPLOY_PROFILE=airgap FAKE_LLM=1` | 0; 1608 passed; `08t1c-a-test-airgap.log` | 151 s |
| tam `make test-int` | | NOT_RUN (koordinatör: yalnız hedefli; kapı koordinatörde) | |
| ağırlık kontrolü `04a-knowledge-core_model_cache` (alpine, `--network none`, salt-okunur) | | NER adayı yok | |
| `-m models`, `models-check --network none`, ölçüm | | NOT_RUN (ENV-163) | |
Yığın `down -v` ile kapatıldı (konteyner 0, volume 0).

## Review r1 bulgu → düzeltme → kanıt
| Bulgu | Test commit'i | Düzeltme | Kanıt |
|---|---|---|---|
| MINOR-1 docs `pii_regex` "durdurur" | — (metin) | 60c6169 | docs/bilgi-tabani.md: regex kategorileri maskelenir, koşu durmaz, NER yok, PRSIM ret; varsayım 3 düzeltildi |
| MINOR-2 NER 503'te `ner_offsets_unavailable` yok | b1cd3ab (düştü: eksik kod) | 60c6169 | `test_08t1c_5` dört kod (`model_missing` dahil, NOTE-6); 08.yaml yeniden üretildi; contract 85/85; `make lint` 0 (`08t1c-a-r2-lint.log`) |

## Varsayımlar ve brief'teki çelişkiler
0. **plan/19 S1 testi değişti (koordinatör kabulü K-08T1C-0006, inceleyici bakar).** Eski kural (`test_19_s1_masking_cannot_be_disabled`): `ingest-raw`'ın hiçbir seçeneğinin adında `mask` ya da `filter` geçmez. Yeni kural: adında `mask`/`filter` geçen tek seçenek `--text-filter`, seçimleri tam `{pii_ner, pii_regex}`. Gerekçe: testin amacı "maskeleme adla kapatılamaz" (plan/19 S1); FOLLOWUP-174 kararı (K-08T1C-0005) açık bir filtre seçeneği istiyor; iki seçim de maskeler (`pii_regex` kimlik numaralarını, `pii_ner` ek olarak kişi adlarını), kapatan değer yok (`none` argparse 2, `test_08t1c_6e`), PRSIM `pii_regex` ile reddedilir (`test_08t1c_6b`); yani amaç korunur, yalnız ad tabanlı yasak dar sınıf tabanlı denetime döner.
1. FOLLOWUP-172 N2 "audit olayı": reindex CLI'sı istek bağlamı dışında; olay sistem aktörlü yazılır (`actor_type=system`), içerik yok, yalnız KB kimliği ve kayıt sayısı.
2. `test_04a_9d` 04a'nın testi; GOREV bu dalda açıkça istediği için dokunuluyor, yalnız süre iddiası.

3. FOLLOWUP-174: `--text-filter pii_regex` seçmek operatörün "kaynaklarda kişi verisi yok" beyanıdır; beyan yanlışsa adlar maskelenmez. Regex kimlik numaraları (kart, IBAN, TC, e-posta, telefon) maskelenir; koşu onlarda **durmaz** (müşteri verisinde durma yalnız kişi verisi yolunun kuralıdır; r1 MINOR-1 düzeltmesi). docs/bilgi-tabani.md bunu açık yazar.
4. D3: `check_reindex_silver` uçta kendi oturumunu açar (istek oturumu değil); yalnız SELECT.

## Kalan riskler
- Ölçüm ve kazanan seçimi ENV-163'e (kullanıcı `make models`) bağlı; 1c-b'de (D6-D8).
- PayCore runbook'u (paycoreLLM, `docs/paycore/m3-sunucu.md`) OCR için geçici `--accept-personnel-data` yolunu anlatıyor; `--text-filter pii_regex`'e çevrilmesi paycoreLLM'de ayrı iş (1c-a merge sonrası).
- Tam `make test-int` bu dalda koşmadı (koordinatör: yalnız hedefli); kapı koordinatörde.
- Hedefli test-int'te 1 skipped (test_19_ingest_raw; nedenine bakılmadı, dalın dokunmadığı bir test).
