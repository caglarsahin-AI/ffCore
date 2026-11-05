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

---

# PR 1c-b: 08 tam dilim 1c — NER ölçümü, kazanan model, int8 (D6-D8 + FOLLOWUP-168 NOTE-2b/3)

**Paket:** 08 tam 1c-b · **Sınıf:** [B] · **Branch:** feat/08-tam-1c-b-olcum · **Baz commit:** 105d176 · **HEAD:** b567b7d66c55bb4559a26f081b328a37e4ef6440 (r1c; r1b 5e9a688, r1 2a7b430) · push yok

## Plan
1. Semboller: `NerRecognizer.load` (pipeline ayarı), `LocalNer`, `quality` (13a ölçümü), `knowledge/models.py` (`NER_CANDIDATES`, `download`, `ner_missing`), `.env.example` NER bloğu, `deploy/offline/models.txt`, docs/guardrail.md NER bölümü.
2. Kapsam: iki adayın lisans/etiket okuması, ölçümü, kazanan seçimi ve yapılandırması, `-m models` testleri, egress PERSON testi, NOTE-2b/3. Kapsam dışı: torchao/ONNX geçişi, PayCore runbook'u (paycoreLLM), sunucuda gecikme koşusu (kullanıcı, ENV-177).
3. Dosyalar: ner.py (`first` + int8), quality.py (NER raporu + CLI `--ner`), models.py (`NER_REVISIONS` sabit indirme, yalnız safetensors, kaybeden çıkar), `.env.example`, models.txt (7 satır + sha256), Makefile (`test-ner-latency`), docs/guardrail.md.
4. Sözleşme/yapılandırma/profil: C12 değişkeni eklenmedi; `.env.example` `NER_MODEL`/`NER_REVISION` dolu. Profil dalı yok; `.env.test` `GUARDRAIL_EGRESS_NER=false` değişmedi. OpenAPI değişmedi.
5. Kabul → test: aşağıdaki tablo.
6. Migration: yok.
7. Geri alma: `.env`'de `NER_MODEL` boş + `GUARDRAIL_EGRESS_NER=false` (bugünkü PayCore durumu); kod geri alınırsa `simple` + fp32'ye döner.
8. Durma koşulları: lisanssız iki aday → yok (akdeniz27 MIT); recall < 0,85 → yok (1,00); `id2label` eşlenmiyor → yok; **P95 < 300 ms boşta tutmadı → KARAR-GEREK A-08T1C-0016 → K-08T1C-0018 A** (bütçe 300 ms kalır, hedef donanımda ölçülür).
9. Felsefe: ARCH-07 tek model, tek yükleme yolu, yeni ayar yok (int8 her zaman açık). ARCH-09 nicemleme torch'un tek çağrısı, pipeline transformers'ın; yeniden yazılan yok. ARCH-10/06 nicemleme API yoksa yükleme fail-loud (sessiz fp32 yok); indirme sabit commit, `main` kayması sessizce farklı ağırlık getirmez.

## Değişen dosyalar
`git diff --stat 105d176..2a7b430`: 10 dosya, +441/-47.
- backend/ffcore/guardrails/recognizers/ner.py, backend/ffcore/guardrails/quality.py, backend/ffcore/knowledge/models.py
- backend/tests/unit/test_08t1c_7_ner_quality.py (yeni), backend/tests/models/test_08t_ner_models.py (yeni), backend/tests/unit/test_08t_18_ner_candidates.py
- .env.example, deploy/offline/models.txt, Makefile, docs/guardrail.md

Commit sırası: 5f3dc68 kırmızı test → 728ed2d kırmızı test (sabit commit, safetensors, int8=fp32) → eee321e test → 264c063 kod → e2ee8f8 docs → 1514453 test → 2a7b430 build/docs.

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Ad-soyad recall ≥ 0,85 (llmaas 0,90) | `test_08t_1_ner_recall_person` (`-m models`) | geçti: 1,00 (22/22), precision 1,00 |
| 1b | Docs tablosu = ölçüm | `test_08t_1b_ner_quality_report_matches_docs` (`-m models`) | geçti |
| 3 | 1.000 karakter, yerel kurallar + NER, boşta P95 < 300 ms | `test_08t_3_ner_latency_p95` / `make test-ner-latency` | **NOT_RUN (hedef donanım, ENV-177; K-08T1C-0018 A).** Geliştirme dizüstü (i7-1165G7, 4 çekirdek/8 iş parçacığı, Docker VM 7 CPU, 4 torch iş parçacığı): int8 P95 158 / 297 / 825 / 840 ms (aynı kod, farklı anlar), tek CPU 442-458 ms; fp32 936-1.462 ms |
| 4 | Aday tablosu (recall/precision/P95/lisans/boyut) PR'da ve docs'ta | `python -m ffcore.guardrails.quality ... --ner` | docs/guardrail.md "NER quality report"; aşağıda |
| D6 | `--network none` models-check, lisans + `id2label` offline | 08t1c-b-models-check.log | geçti: arayüz `lo` (+ tünel aygıtları), `/models ro`, exit 0; akdeniz27 MIT, savasy lisans yok; iki `id2label` PER/ORG/LOC |
| D7 | NOTE-3 pencere/stride gerçek modelle | `test_08t1c_9_long_text_windows_find_every_name` | geçti: 1.862 token, 60 ad, her harf kapsanıyor, ad dışı span yok, tekrar yok |
| D7 | NOTE-2b tek kilit gecikmesi | 08t1c-b-lock-latency.log | ölçüldü (aşağıda); kod değişmedi |
| D8 | Kelime bütünü span (`first`) | `test_08t1c_7c_pipeline_aggregates_whole_words`, `test_08t1c_8_person_spans_are_whole_words` | geçti |
| D8 | int8 her zaman, kalite fp32'ye eşit | `test_08t1c_7c` (birim), `test_08t1c_11_int8_quality_equals_fp32` (`-m models`) | geçti |
| D8 | Kazanan `.env.example` + models.txt, kaybeden listeden çıkar, sabit commit indirme, yalnız safetensors | `test_08t1c_7d_measured_winner_is_the_only_candidate`, `test_08t_18_*`, `verify.sh --models` | geçti; verify `OK models (73 files)` |
| D8 | `GUARDRAIL_EGRESS_NER=true` egress PERSON tokenize, gerçek model | `test_08t1c_10_egress_person_tokenized_with_the_real_model` | geçti: `<<PII_1>> <<PII_2>> arar.` |
| — | NER raporu sayımı (birim) | `test_08t1c_7_ner_quality_report_counts`, `test_08t1c_7b_regex_report_unchanged` | geçti |

Aday tablosu (13a pii-100; PERSON 22 / ORG 4 / LOC 4; `--network none`, volume salt-okunur):

| Model | Lisans | PERSON r/p | ORG r/p | LOC r/p | P95 1.000 kr. |
|---|---|---|---|---|---|
| akdeniz27, int8, `first` (seçilen) | MIT | 1,00/1,00 | 1,00/0,67 | 1,00/0,17 | 158-840 ms (dizüstü) |
| akdeniz27, fp32, `first` | MIT | 1,00/1,00 | 1,00/0,67 | 1,00/0,17 | 484 ms (yük altında) |
| akdeniz27, fp32, `simple` (1b ayarı) | MIT | 1,00/0,56 | 1,00/0,40 | 1,00/0,11 | ölçülmedi ayrıca |
| savasy, int8, `first` | kartta yok | 0,95/0,88 | 1,00/0,31 | 1,00/0,17 | 490 ms |

## Çalıştırılan komutlar
| Komut | Ortam | Exit | Süre / sonuç |
|---|---|---|---|
| `make models` | kullanıcı, `-p 04a-knowledge-core` | 0 | iki aday tam |
| `make models-check` | `docker run --network none`, `/models:ro` | 0 | 08t1c-b-models-check.log |
| `make lint` | tools, HEAD 2a7b430 | 0 | 476 dosya (08t1c-b-lint.log) |
| `make test` | `--env-file .env.test`, `DEPLOY_PROFILE=llmaas`, HEAD 2a7b430 | 0 | 1743 passed, 3:52 (08t1c-b-test-llmaas.log) |
| `make test` | aynı, `DEPLOY_PROFILE=airgap` | 0 | 1743 passed, 3:44 (08t1c-b-test-airgap.log) |
| hedefli birim + `-m models` (gecikme hariç) + `make test-ner-latency` + `verify.sh --models` | `--network none`, `/models:ro`, `.env.test`, `RUN_MODEL_TESTS=1` | 0 | 48 passed; P95 158 ms; verify OK 73 dosya (08t1c-b-green-models.log; çalışma ağacı 2a7b430 ile aynı içerik) |
| ölçüm CLI `python -m ffcore.guardrails.quality ... --ner` (iki aday) | `--network none`, `/models:ro` | 0 | 08t1c-b-measure-candidates.log |
| boşta P95 (fp32/int8, 4 iş parçacığı ve `--cpus=1`) | pencere K-08T1C-0017, 0 konteyner | 0 | 08t1c-b-idle-p95.log |
| `make test-int`, `make smoke` | — | NOT_RUN | yığın açılmadı; değişiklik DB/API/compose'a dokunmuyor; kapı koordinatörde |

Keşif betikleri ve logları: state/evidence/08t1c-b-scripts/, 08t1c-b-explore{,2,3,4}.log. Ölçüm verisi sentetik 13a seti; kişi düzeyi kurum verisi yok.

## Çıktı özeti ve post-state
- NOTE-2b (`_recognize` tek kilit; 08t1c-b-lock-latency.log; ölçüm sırasında başka yığınlar açıktı, 20 konteyner): 1 çağıran medyan 190 ms; 2 çağıran 460 ms; 4 çağıran medyan 716 ms, P95 2.047 ms; verim kilitli 4,0-4,7 çağrı/s, kilitsiz deneme 4,5-5,6 çağrı/s (4 çağıranda P95 931 ms). İşlem CPU'ya bağlı ve torch çekirdekleri zaten kullanıyor; kilit verimi değil yalnız kuyruk ucunu etkiliyor. Kilit kalır (HF pipeline'ın iş parçacığı güvenliği belgelenmemiş). API süreci başına kapasite bu makinede ~4-5 egress NER çağrısı/s.
- Sunucudaki eski önbellek: savasy dizini ve akdeniz27 `pytorch_model.bin` artık okunmuyor; silme notu docs'ta.

## Kontrol listesi
- [x] Felsefe ile çelişen nokta yok (int8 yeni ayar değil; fail-loud korunuyor)
- [x] Donmuş sözleşme kırılmadı (C12 değişkeni yok; OpenAPI aynı)
- [x] İki profil testi koştu
- [x] Mutasyon ucu yok
- [x] Log/evidence secret-free, kişi verisi yok
- [x] Önyüz yok
- [x] Docs ve `.env.example` güncel
- [ ] `state/WORK_QUEUE.md` koordinatörde

## Varsayımlar ve brief'teki çelişkiler
0. **`aggregation_strategy` `simple` → `first`** (A-08T1C-0015 varsayımı, K-08T1C-0016 onay): `simple` akdeniz27'de kelimeyi alt parçalara bölüyordu (`I`, `h`, `lam`), yani bir ad parça parça maskelenebiliyordu. Kartın önerdiği `first` kelime düzeyinde etiketler.
1. **int8 dinamik nicemleme her zaman açık** (K-08T1C-0016 A). `torch.ao.quantization.quantize_dynamic`: torch bu API'yi torchao'ya taşıma yolunda (uyarı veriyor); kaldırılırsa yükleme fail-loud olur. FOLLOWUP önerisi: torchao/ONNX geçişi (koordinatör kaydı).
2. **İndirme sabit commit'e bağlandı** (`NER_REVISIONS`): önceden `main` indiriliyordu; `main` kayarsa volume, `NER_REVISION`'ın adlandırdığı snapshot'ı tutmazdı (`model_missing`). Yalnız safetensors: pickle dosyası (`pytorch_model.bin`) artık indirilmiyor ve listede yok.
3. **`test_08t1c_9` beklentisi değişti** (eee321e → 1514453): ilk biçim her adı tek span sanıyordu; model soyadı bazen ayrı `B-PER` etiketliyor (`Mehmet` + `Yılmaz`, kısa metinde de). Pencerelerin doğruluğu "her harf kapsanıyor, ad dışı span yok, tekrar yok" ile sınanır; iki bitişik yer tutucu maskelemede güvenli yön.
4. **`test_08t1c_11` (int8 = fp32)** kodla birlikte yeşile dönebilen bir eşitlik testi; int8'den önce iki taraf da fp32 olduğundan kırmızı aşaması anlamlı değildi (int8 çağrısını birim tarafında `test_08t1c_7c` kırmızıdan geçirdi).
5. LOC precision 0,17: altın set adres içindeki mahalle/ilçe/il adlarını `TR_ADDRESS` sayıyor, model konum diyor. Maskelemede güvenli yön; docs yazar.
6. Ölçüm makinesi temsilî değil (kabul 3 NOT_RUN): aynı kod 20 dk arayla 297 ve 825 ms verdi; tek iş parçacığı dört iş parçacığından hızlı çıktı (hiper-iş parçacığı / host yükü).

## 1c-a r1 NOTE'ları (devredilen, kod değişikliği yok)
1. `pii_regex` ile PRSIM yolunda adıyla test yok (parametrize `None`/`"pii_regex"` önerisi).
2. `--accept-personnel-data` + açık `--text-filter pii_regex` (izinli yol) testsiz.
3. `pii_regex` kayıtlarının NER gelince `pii_ner`'e yükseltme yolu docs'ta yok (yeniden ingest / reindex).
4. Worker `reindex_job` gold + bayrak reddini kendisi yapmıyor; yalnız CLI'da (API'de bayrak yok, bugün erişilemez).
5. M3 audit olayı kuyruğa yazılmadan önce commit ediliyor; kuyruk hatasında olay var, iş yok.

## Kalan riskler
- Kabul 3 hedef donanımda koşmadı (ENV-177): `docker compose run --rm --no-deps tools make test-ner-latency` sunucuda yeşil olmadan `GUARDRAIL_EGRESS_NER=true` yapılmaz (docs/guardrail.md iki yerde). Tutmazsa B (bütçe, kullanıcı) ya da C (ONNX/iş parçacığı ayarı).
- PayCore runbook'u (paycoreLLM) `true` geçiş adımına bu şartı ve `make models`'in yeni sabit commit'ini almalı: touch-zone dışı.
- torch nicemleme API'si kullanımdan kalkma yolunda (varsayım 1).
- Egress NER kapasitesi API süreci başına ~4-5 çağrı/s (bu makinede); yoğun eşzamanlı egress'te kuyruk ucu büyür (NOTE-2b).
- Ölçüm seti küçük ve sentetik (22 ad); 1,00 "bilinen biçimlerde gerileme yok" demek, saha recall'u değil.

## r1b: öz-kontrol bulguları → düzeltme → kanıt (K-08T1C-0021)
HEAD **5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809** (2a7b430 + 1 commit, 7 dosya +59/-21). Kaynak: A-08T1C-0019 (kullanıcı isteğiyle öz-kontrol).

| Bulgu | Düzeltme | Kanıt |
|---|---|---|
| Kanıt boşluğu: "verify OK 73 dosya" logda yoktu | yeniden koşuldu (kod değişikliği yok) | 08t1c-b-verify-models.log (`OK models (73 files)`, HEAD 2a7b430; models.txt r1b'de değişmedi) |
| MINOR-a: docs aday tablosunda P95 "297-840 ms", ölçülen aralık 158-840 ms | docs/guardrail.md tablo + makine paragrafı (158 ms koşusu eklendi) | diff |
| MINOR-b: `.env.example` `GUARDRAIL_EGRESS_NER=true` yorumunda gecikme şartı yok | "Set true only after `make test-ner-latency` is green on this machine" | diff |
| NOTE-3: `make test-models` gecikme testini de koşuyordu (makineye bağlı, hedef olmayan makinede kırmızı) | `test_08t_3` ayrı dosyaya (`tests/models/test_08t_ner_latency.py`) ve ayrı işarete (`ner_latency`, bayrak `RUN_NER_LATENCY`, pyproject + conftest); `make test-ner-latency` ikisini de açar (dosya `tests/models` altında olduğu için conftest dizin anahtar kelimesiyle `RUN_MODEL_TESTS` da ister; testin ağırlığa zaten ihtiyacı var) | 08t1c-b-r1b-models.log: `-m models` iki dosyada `6 passed, 1 deselected`; bayraksız `NOT_RUN`; `make test-ner-latency` koştu (bu koşuda 266 ms, geçti; önceki koşuda 367 ms, düştü: dizüstü oynaklığı, ENV-177) |
| NOTE-1: egress testi modelin span bölmesine bağlıydı | özellik testi: çıktıda ham ad (`Ayşe`, `Demir`) ve telefon yok; `(<<PII_n>> ){2,3}arar.` | 08t1c-b-r1b-models.log (6 passed) |

Kapı (5e9a688): `make lint` 0 (477 dosya); `make test` airgap **1743/1743** (12:25); llmaas **1742/1743** (28:53, review09 yığını ~%180 CPU'da koşarken ve makine 18:50-19:40 arası uykudayken): düşen `test_02_r1_m3_child_process_exits_by_itself` mutlak duvar saati testi (`elapsed < SHUTDOWN_TIMEOUT_S + 3`, alt süreç); r1b tracing'e dokunmuyor, 2a7b430'da yeşildi. **Yük altında 1 kez düştü, tek başına 3/3 yeşil** (7,2-7,7 s; 08t1c-b-r1b-tracing-rerun.log). Loglar: 08t1c-b-r1b-test-{llmaas,airgap}.log.

NOTE'lar (kod değişikliği yok, K-08T1C-0021):
- **NOTE-2:** revizyon iki yerde: `.env.example` `NER_REVISION` ve `models.py` `NER_REVISIONS`; `test_08t1c_7d` eşitliği tutuyor. Başka revizyon seçen kurulum `make models` ile onu indiremez; bilinçli (ölçülen commit), docs yazar.
- **NOTE-4:** int8'in çalışma belleği ölçülmedi; `quantize_dynamic` kopya üretir, yüklemede kısa süre fp32 + int8 birlikte bellekte. Docs'taki 0,44 GB disk boyutu.
- **NOTE-5:** her API açılışında torch nicemleme kullanım dışı uyarısı loga düşer; FOLLOWUP-178 ile gider.

## r1c: Review r1 (ONAY, MAJOR 0) bulgu → düzeltme → kanıt (K-08T1C-0024)
HEAD **b567b7d66c55bb4559a26f081b328a37e4ef6440** (5e9a688 + 2 commit: 1f3f391 kırmızı test → b567b7d kod/docs; 9 dosya +326/-48). Rapor: state/reviews/08-tam-1c-b-r1.md.

| Bulgu | Düzeltme | Kanıt |
|---|---|---|
| MINOR-1: `simple` → `first` için "kırmızı" iddiası gerçek model testine değil keşif çıktısına dayanıyor | PR ve docs düzeltildi: parçalı maskeleme **keşif koşularında** görüldü (08t1c-b-explore2.log), gerçek model testi olarak hiç kırmızı görülmedi; birim tarafındaki kırmızı yalnız pipeline ayarıydı (`test_08t1c_7c`, 08t1c-b-red.log). Varsayım 0 bu tümceyle okunmalı | docs/guardrail.md "exploration runs, not as a failing test" |
| MINOR-2: altın adın tamamen kapsandığı sayılmıyor (örtüşme = bulundu) | `quality`: NER satırına `covered` (altın span'ın her harfi aynı kategorideki tahmin span'larının içinde) ve tabloya `Covered` sütunu; regex tablosu değişmedi | birim `test_08t1c_7e/7f` (1f3f391'de kırmızı, 08t1c-b-r1c-red.log); `-m models` `test_08t1c_13_person_names_fully_covered`; ölçüm: **PERSON covered 22/22 = 1,00** (recall düşmedi; durma yok) |
| MINOR-3: ölçüm motorun `min_confidence` eşiğini yok sayıyor | `NER_MIN_CONFIDENCE` = yerleşik egress PII politikasının eşiği (0,5); ölçüm altını önce atar (motor gibi); int8 = fp32 testi aynı raporu kullanır | birim `test_08t1c_7g`; ölçüm: akdeniz27 ORG tahmin 6 → 5 (precision 0,67 → 0,80), PERSON/LOC değişmedi; savasy PERSON 0,95 / 0,91 / covered 0,95 (08t1c-b-r1c-measure-candidates.log) |
| MINOR-4: eski volume'da lisanssız savasy ve pickle; `save.sh` volume'un tamamını paketliyor, `verify.sh` fazlayı görmüyor | `deploy/offline/models-files.sh` (models.txt yolları + repo `refs/`); `save.sh` yalnız bunları `tar --dereference --files-from=-` ile paketler; `verify.sh --models` listede olmayan hub model dizinini ve snapshot dosyasını **FAIL** ile adlandırır, silmez; docs'a tek seferlik temizlik komutu (kullanıcı koşar; ben silmedim); deploy/offline/README | birim `test_08t1c_12*` (5 test); gerçek volume: `FAIL model dir models--savasy--...` + `FAIL model akdeniz27/... pytorch_model.bin`, exit 1 (beklenen); paketlenen akdeniz27 ağacı ağsız açıldı, `verify` OK 7 dosya, `NerRecognizer.load` ondan yükledi (`Ayşe Demir` PERSON) (08t1c-b-r1c-checks.log) |
| MINOR-5: docs gecikme iddiaları loglarla uyumsuz | aralık 158-840 ms; hız farkı iş parçacığına göre: 4 iş parçacığında 1,5-1,7 kat, tek iş parçacığında 2,1-2,8 kat; "iki-üç kez koş" notu | docs/guardrail.md |
| MINOR-6: uzun metin testi gevşetildi | değişiklik yok (r1b'de gerekçeli; MINOR-2 tam kapsama testi altın set için aynı boşluğu kapatır) | — |

Kapı (b567b7d): `make lint` 0 (478 dosya); birim 52 passed; `-m models` NER: 7 passed, 1 deselected (gecikme) (08t1c-b-r1c-checks.log); `make test` llmaas **1751/1751** (2:59), airgap **1751/1751** (2:51) (08t1c-b-r1c-test-{llmaas,airgap}.log; +8 yeni birim testi).

**Kullanıcı için (tek seferlik):** `04a-knowledge-core_model_cache` volume'unda savasy dizini ve akdeniz27 `pytorch_model.bin` duruyor; `verify.sh --models` artık bunlarla FAIL verir ve `save.sh` öncesinde verify koştuğu için paketleme durur. Temizlik komutu docs/guardrail.md "Old volumes" maddesinde.

NOTE'lar (r1, kod değişikliği yok): NOTE-1 int8 eşitliği sayıları karşılaştırır (covered dahil); NOTE-2 bulgu kanıtında int8 yazmaz; NOTE-3 yüklemede `use_safetensors` yok (transformers ikisi varsa safetensors seçer; yeni indirmede pickle yok, eski volume verify ile yakalanır); NOTE-4 `NER_REVISION` env'i ile kod sabiti ayrı (r1b NOTE-2); NOTE-5 uzun metin token sayısı logda yok; NOTE-6 egress testi kategori ayrımını kanıtlamaz; NOTE-7 worker yolu (`HttpNer`) gerçek ağırlıkla sınanmadı, gecikme tek koşu yerine 2-3 koşu (docs'a yazıldı).
