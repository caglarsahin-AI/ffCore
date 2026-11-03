# PR: 08-tam-1a — çıkışta geri çevirme (C17, FOLLOWUP-141), secrets 106/107, egress 147

**Paket:** 08-tam-1a (08 tam dilim 1'in modelsiz yarısı, K-08T1-0002 S7) · **Sınıf:** [B] (yeni bağımlılık, migration, compose yok) · **Branch:** feat/08-tam-1-ner · **Baz commit:** ea0db36 · **HEAD:** 33a0268f66bacde2cd57204e942b62b0ea2385cb (r1 incelenen: fb7130d, r2 incelenen: 6d0d9ba, r3 incelenen: 370912d, r4 incelenen: 4aecdbc, r5 incelenen: 60f2250) · **Oturum:** ffcore-isci-a-08-tam-1

Plan ve onay: `state/pr/08-tam-1.md` (PLANNED, K-08T1-0002: S1-S9 hepsi A). 08-tam-1b (NER + PRSIM) ayrı PR, ağırlıklar gelince.

## Değişen dosyalar (main...HEAD, 52 dosya, +4629/-121, 39 commit)

r5 DUZELT turu (60f2250..HEAD, 6 commit, 17 dosya +225/-81; karar KARARLAR "C17 HTML kuralı, düzeltmeler" (g)-(i)):

- **MAJOR-r5-1** (d1c2960): `masking._HTML_TAG` istisnası önceki karaktere bakmaz (`<(?!PII_[0-9]{1,8}>>)[a-z]`); `tests/unit/test_08t_r5_tail.py` (inceleyicinin kuyruk probe'u: 1-11 karakterlik parçalar iki yolda + rastgele 1-6 parçalama 200 deneme).
- **MINOR-r5-1** (14b8db7): `PLACEHOLDER` `<<PII_[0-9]{1,7}>>`, verme üst sınırı 9.999.999; 10.000.000'dan büyük ya da ASCII olmayan rakamlı numara yer tutucu değil; `tests/unit/test_08t_r3_range.py`, `test_08t_m2_history.py`, `test_08t_r2_rescope.py` (7 hane).
- **NOTE-7** (07c17ee): `test_08t_r3_url_scan.py` süreç CPU süresi.
- **MINOR-r5-4 + NOTE-1** (bb720a1): `api/guardrails.py` evaluate açıklaması 400 `placeholder_out_of_range` (additive), `backend/openapi/08.yaml` yeniden üretildi (sözleşme testi yeşil), `test_08_api.py` 400 testi; `api/runs.py` `exc_info=True`.
- **MINOR-r5-3** (4c5e732): test açıklamaları ve bir test adı (`..._does_not_reopen_after_html`).
- **MINOR-r5-2/4 docs** (33a0268): `docs/{guardrail,api,agentlar}.md`.

r4 DUZELT turu (4aecdbc..HEAD, 5 commit, 14 dosya +282/-188; kararlar KARARLAR "C17 geri çevirme: cevap düzeyinde HTML fail-closed", (d′), (f′)):

- **MAJOR-r4-1** (c22894a): `guardrails/masking.py` cevap düzeyinde HTML (`_HTML_TAG`, istisna tam yer tutucu; `UrlLines._html`), `tag`/`tag_dq`/`tag_sq`/`expect`/CSS paren kipleri, öznitelik taşıması ve `_gap` kalktı (masking.py +56/−99 satır, net 43 satır küçülme), parça sonundaki `\r` satırı bitirmez, satır kuyruğu satır sonunda sıfırlanır; `tests/unit/test_08t_r4_html_response.py`; kaldırılan davranışın testleri güncellendi (`test_08t_r2_url_lines.py` kapanmış hedef testi yalnız markdown, `test_08t_r3_blank_line.py` açılı hedef `<./a`, `test_08t_r3_url_rules.py` `<img src=x>` olumlu kontrolü kalktı).
- **MINOR-r4-3/6** (a0795ad): `UrlLines.lose`, `ContextReveal.fail_closed` → `_lost`; `api/runs.py` `prime` her hatada fail-closed (`detokenize_rebuild_failed` logu); `tests/integration/test_08t_r3_resume.py`.
- **MINOR-r4-1/2** (7a10789): `masking.py` `PLACEHOLDER` 99.999.999'u dışlar, verme üst sınırı 99.999.998, `reserve_carried` artık hata vermez; `guardrails/engine.py` `PlaceholderOutOfRange` `on_error`'dan bağımsız yeniden yükseltilir; `tests/unit/test_08t_r3_range.py`, `tests/integration/test_08t_m2_history.py`.
- **MINOR-r4-4** (8897584): `tests/integration/test_08t_r2_paths.py` güçlü iddia geri, `style` yazımı kısaltıldı.
- **MINOR-r4-1/5 docs** (60f2250): `docs/{guardrail,api,agentlar}.md`.

r3 DUZELT turu (370912d..HEAD, 9 commit, 19 dosya +801/-98):

- **MAJOR-r3-2** (1d6e84e): `guardrails/masking.py` `UrlLines` artımlı (parça + 32 karakter örtüşme, işaret/kesme sonrası tarama yok, satır metni yalnız 8.192'ye kadar tutulur, öznitelik adı + boşluk `_gap`), `tests/unit/test_08t_r3_url_scan.py`.
- **MAJOR-r3-1** (0ad2aab): `masking.py` sınıf kuralı (HTML etiketi `<harf`, yer tutucu hariç; şema-iki nokta; `style=`, `data=`, `url(`), `_open_target` etiket/etiket içi tırnak/CSS paren modları, satır sonunda öznitelik adı → değer bekleniyor; `tests/unit/test_08t_r3_url_rules.py`, `tests/integration/test_08t_r2_paths.py` (inceleyicinin dört yazımı gerçek LiteLLM ile).
- **MINOR-r3-4** (4c3f5ae): boş satır yalnız markdown hedefini kapatır (K-08T1-0020 A); `tests/unit/test_08t_r3_blank_line.py`.
- **MINOR-r3-1** (77cc903): `runtime/events.py` `token_texts`, `api/runs.py` `detokenizer(after=)`/`exit_hook(after=)`, `masking.ContextReveal.prime/fail_closed`, `UrlLines.mark`, `services/facade_agent.py` (K-08T1-0021 A); `tests/integration/test_08t_r3_resume.py`.
- **MINOR-r3-2** (2e35856): `masking.py` `PLACEHOLDER` en çok 8 hane, `PlaceholderOutOfRange` (400 `placeholder_out_of_range`), `reserve_carried` ≤ 99.999.998, Lua ve bellek deposu sayaç sınırı; `tests/unit/test_08t_r3_range.py`, `test_08t_m2_history.py` (Redis senaryosu), `tests/unit/test_08_masking.py` (sahte `eval` imzası).
- **MINOR-r3-3/6** (de30d05): `services/facade_guard.py` `token_store_errors` + `reveal` içinde, `facade_proxy.py` oradan alır; `tests/unit/test_08t_r3_minors.py`.
- **NOTE-1** (aa26bd7): `tests/unit/test_08t_secrets_linear.py` süre alt süreç içinde ölçülür (sınır 2 s, sert zaman aşımı 120 s).
- **MINOR-r3-5** (8837a72): `docs/{guardrail,api,agentlar}.md`.

r2 DUZELT turu (6d0d9ba..HEAD, 4 commit, 19 dosya +1060/-136):

- **MAJOR-r2-1** (87b7e7b): `guardrails/masking.py` (`UrlLines`, `_open_target`, `reveal_text(lines=)`; `StreamDetokenizer`/`ContextReveal` satır durumu taşır; NOTE-1 yorumu), `tests/unit/test_08t_r2_url_lines.py`, `tests/unit/test_08t_m3_url_context.py` ve `tests/integration/test_08t_m3_paths.py` (beklentiler satır kuralına göre).
- **MAJOR-r2-2/r2-3 + MINOR-r2-1/r2-4** (e2c32b2): `masking.py` (`i:<token>` kimlik alanı, `entry()` TTL yenilemez, `placeholder_numbers` ≤ 8 hane, `reserve_carried`, `rescope`), `runtime/adapters.py` (`_history(question=)`; `context_factory` soruyu verir), `services/facade_agent.py` (istemci geçmişi egress çıktısıyla, run kapsamında saklanır; `reserve_carried` döngüden önce), `services/facade_guard.py` (`reserve_carried`; `guard_messages` başında), `services/facade_external.py`, testler `tests/unit/test_08t_r2_rescope.py`, `tests/integration/test_08t_m2_history.py`, `test_08t_m2_facade_history.py`, `test_08t_r2_paths.py`, `test_08t_r2_history_e2e.py`.
- **MINOR-r2-2/r2-3** (07279b1): `runtime/events.py` (`delivered` kimliği), `services/facade_proxy.py` (`_token_store_errors`, `_LiveReveal.held`), `masking.StreamDetokenizer.abandon`, `tests/unit/test_08t_r2_minors.py`.
- **MINOR-r2-5** (370912d): `docs/agentlar.md`, `docs/guardrail.md`, `docs/api.md`.

r1 ve öncesi:

- **147** (e46e4ca): `backend/ffcore/core/egress.py` (`check_http_destination`, ortak `_checked_addresses`; `check_destination` aynı denetimi kullanır), `services/external_config.py` (`check_base_url` yalnız base URL'nin eklediklerini yapar: userinfo, query, rezerve host), `tests/unit/test_08t_egress_http.py`.
- **106** (ee0d6ca): `guardrails/rules.py` (`_SHORT_TOKEN`, `SHORT_TOKEN_MIN_CHARS = 13`), `tests/unit/test_08t_secrets_short.py`, `docs/guardrail.md` (ölçüm tablosu).
- **107** (b193c54): `runtime/graph.py` (`_egress_sources`; `retrieve` ve `_search_tool`), `tests/unit/test_08t_source_egress.py`, `tests/e2e/scenarios/seed.py` (secrets enforce'a döndü, S6), `tests/e2e/scenarios/test_18_f11_f13_content.py` (P5 beklentisi), `docs/agentlar.md`, `docs/guardrail.md`.
- **C17 yardımcıları** (fdcbecd): `guardrails/masking.py` (`PlaceholderAligner`, `StreamDetokenizer`, `detokenize_json`, `log_unresolved`), `tests/unit/test_08t_c17_masking.py`.
- **K-08T1-0004 ekleri** (fb7130d): `masking.count_placeholders`/`log_skipped_policy`, `api/runs.py` `exit_mode`/`exit_hook`/`skip_counter`, facade guard/proxy sayaç, iki profile duyarlı facade testleri, docs cümleleri.
- **C17 çıkış sınırı** (675f857): `runtime/graph.py` (model düğümünde hizalayıcı), `api/runs.py` (`is_run_owner`, `policy_allows_reveal`, `reveals_values`, `detokenizer`, `live_transform`, `_replay_rows(reveal)`, `_stream(reveal=)`), `services/facade_agent.py`, `services/facade_guard.py` (`reveals`, `reveal`, `stream_reveal`), `services/facade_proxy.py` (`_LiveReveal`, tek parça ve tamponlu yol), `services/facade_external.py`, `guardrails/engine.py` (`masks_pii_at`), testler `tests/unit/test_08t_c17_{runtime,facade}.py`, `tests/integration/test_08t_c17_{exit,facade_direct}.py`, `docs/{agentlar,api,guardrail}.md`.

`state/` değişikliği yok (branch'te). Yeni bağımlılık, migration, compose, OpenAPI değişikliği yok.

## Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 7 | C17: tam metin geri çevrilir (konsol sahibi, facade agent, facade düz yol tek parça, dış agent) | `test_08t_7_console_owner_gets_values_others_placeholders` (gerçek Postgres+Redis), `test_08t_7c_direct_answer_reversed_for_the_caller` (gerçek LiteLLM + fake sağlayıcı), `test_08t_7_detokenize_json_walks_every_string`, `test_06b2_*` (dış agent, değişmeden yeşil) | geçti |
| 8 | C17 akış: `<<PII_` ve `1>>` ayrı chunk'larda istemciye ham yer tutucu gitmez; en çok 15 karakter tutulur (en uzun yer tutucu 16 karakter: `<<PII_` + 8 hane + `>>`) | `test_08t_8_aligner_never_publishes_a_partial_placeholder` (her bölme noktası), `test_08t_8_aligner_random_chunks` (300 rastgele bölme), `test_08t_8_stream_split_placeholder_reversed`, `test_08t_8_live_tokens_carry_whole_placeholders`, `test_08t_7c_live_content_split_placeholder_reversed`, `test_08t_7c_tool_call_arguments_split_reversed`, `test_08t_8_direct_live_stream_reversed` (gerçek akış), `test_08t_8b_text_that_is_not_a_placeholder_is_not_held` | geçti |
| 9 | C17 yetki ve kapsam: yalnız koşu sahibi/facade çağıranı (S8); başka kapsamın yer tutucusu çözülmez; Postgres tokenize kalır; çıkışta enforce `pii` kuralı varsa yer tutucu kalır; çözülemeyen sayısı loglanır, değer yok (S9) | `test_08t_7_console_owner_gets_values_others_placeholders`, `test_08t_9_enforced_output_pii_keeps_placeholders`, `test_08t_9_enforced_output_pii_keeps_the_placeholder` (facade), `test_08t_9_other_scope_placeholder_stays_and_is_logged`, `test_08t_9_unknown_placeholder_stays_and_is_counted` | geçti |
| 10 | airgap (egress kapalı): davranış değişmez | iki profil `make test` / `make test-int`; `test_08t_12_egress_disabled_changes_nothing` | (kapı tablosu) |
| 11 | 106: 13-23 karakterlik token kimlik sözcüğüyle yakalanır, sözcüksüz değişmez, düz değerler muaf | `test_08t_11_short_token_with_credential_word_caught` (5 biçim × 2.000), `test_08t_11_short_token_without_context_unchanged`, `test_08t_11_credential_word_with_plain_value_not_caught`, `test_08t_11_finding_covers_the_value_only` | geçti (ölçüm aşağıda) |
| 12 | 107: tek parçadaki blob cevabı düşürmez; parça düşer, `sources.blocked`; hepsi düşerse run failed; `search_documents` da | `test_08t_12_blocked_source_dropped_answer_goes_on`, `test_08t_12b_every_source_blocked_fails_the_run`, `test_08t_12c_search_result_item_dropped`, `test_08t_12c_search_result_all_blocked_fails_the_run` | geçti |
| 13 | 107: seed secrets enforce'a döner; F11 P5 parçası modele gitmez | `tests/e2e/scenarios/seed.py`, `test_18_f11_5b_encoded_chunk_left_out_at_egress` | **NOT_RUN** (e2e yığını; K-08T1-0002 S6: F11 doğrulaması test rolünün yığınında) |
| 14 | 147: isim + çözülen her adres + şema/port; 06b-2 testleri yeşil | `test_08t_14_*` (15 test), `test_06b2_*` birim + entegrasyon, `test_03c_18_check_destination*` | geçti |
| 17 | Kapılar | aşağıda | (kapı tablosu) |

NER (1-6), PRSIM (15), yerleşik v3 (16): 08-tam-1b.

### 106 ölçümü (seed 106, biçim başına 2.000; dokuz farklı kimlik sözcüğü kalıbı)

| Biçim (13-23 karakter) | Kimlik sözcüğüyle | Aynı değerler sözcüksüz |
|---|---|---|
| büyük harf 2x6 | %95,15 (1903/2000) | 0/200 |
| büyük harf 3x6 | %99,00 (1980/2000) | 0/200 |
| büyük harf 16 | %99,05 (1981/2000) | 0/200 |
| karışık + rakam 14 | %99,95 (1999/2000) | 0/200 |
| büyük harf + rakam 20 | %100 (2000/2000) | 0/200 |

Tek tablo; r3 HEAD'inde yeniden ölçüldü (`test_08t_secrets_short.py` üreteci ve bağlamları, geçici ölçüm betiği; kaçanların hangi muafiyete girdiği değer düzeyinde kontrol edildi). Kaçakların nedeni:
- 2x6 (97), 3x6 (20), 16 (19): `_CODE_NAME`/`_TICKET_ID` değil. Değer "düz tanımlayıcı" sayılıyor: her parça ≥ %30 sesli ve 3 ünsüz dizisi yok. Belge adları ve kodlar için gereken muafiyet bu; gevşetilmedi (yanlış pozitif riski). 2x6 test tabanı 0,94.
- karışık 14'teki 1/2000 (`gumGhfCgtFggsx`): r1 MAJOR-5'in `_CODE_NAME` (tam tümsekli camelCase) muafiyeti. r1 öncesi tabloda %100 yazıyordu; düşüş bu muafiyetten geliyor (doğrulandı).

08 r3 probe'ları (`08-entropy-probe*.py`) bu turda yeniden koşulmadı; r1 notundaki "aynı sayılar" cümlesi kaldırıldı.

### ReDoS ölçümü (r3 HEAD, tools konteyneri, `find_secrets` tek çağrı)

| Girdi | Süre |
|---|---|
| `token` + 200.000 boşluk | 0,036 s |
| `password` + 200.000 boşluk | 0,027 s |
| `api_key=` + 200.000 sekme | 0,028 s |
| `token` + 60.000 × ` is` | 0,037 s |
| `token` + 100.000 tırnak | 0,009 s |
| `token: aaaaaaaaaaaa ` × 9.000 (180 bin karakter) | 0,030 s |

r1 öncesi eşdeğer girdiler 43 s ve 59 s sürüyordu (inceleyici r1). Testteki sınır (alt süreç, < 10 s) yalnız regresyon bekçisi.

## Çalıştırılan komutlar

**r6 (r5 düzeltmesi; yalın yığın postgres + redis + litellm + fake-llm + qdrant, tee çıktıları scratchpad `r6-*.txt`; kapılar HEAD'de):**

| Komut | Ortam | Exit | Süre | Sonuç |
|---|---|---|---|---|
| `tools make lint` | | 0 | | temiz |
| `tools make test` | llmaas | 0 | 137 s | 1525 passed |
| `tools make test` | `GUARDRAIL_EGRESS_ENABLED=false DEPLOY_PROFILE=airgap` | 0 | 133 s | 1525 passed |
| hedefli test-int: `test_08t_*` (11 dosya), `test_06b_agent`, `test_06b_direct`, `test_06b2_external_agent`, `test_06a_runs_api`, `test_134_provider_request`, `test_08_api` | llmaas | 0 | 262 s | 150 passed |
| aynı | airgap | 0 | 266 s | 148 passed, 2 skipped (profil koşullu) |
| `down -v` | | 0 | | konteyner 0, volume 0 |

Tam `make test-int` bu turda koşulmadı (K-08T1-0028: hedefli yeter).

**r5 (r4 düzeltmesi; yalın yığın postgres + redis + litellm + fake-llm + qdrant, tee çıktıları scratchpad `r5-*.txt`):**

| Komut | Ortam | Exit | Süre | Sonuç |
|---|---|---|---|---|
| `tools make lint` | | 0 | | temiz |
| `tools make test` | llmaas | 0 | 148 s | 1505 passed |
| `tools make test` | `GUARDRAIL_EGRESS_ENABLED=false DEPLOY_PROFILE=airgap` | 0 | 135 s | 1505 passed |
| hedefli test-int: `test_08t_*` (11 dosya), `test_06b_agent`, `test_06b_direct`, `test_06b2_external_agent`, `test_06a_runs_api`, `test_134_provider_request`, `test_08_api` | llmaas | 0 | 263 s | 149 passed |
| aynı | airgap | 0 | 276 s | 147 passed, 2 skipped (profil koşullu) |
| `down -v` | | 0 | | konteyner 0, volume 0 |

Kapılar son commit'te (HEAD) koşuldu. Tam `make test-int` bu turda koşulmadı (K-08T1-0024: hedefli yeter; inceleyici r5'i tam yığınla koşar).

**r4 (r3 düzeltmesi, HEAD 4aecdbc; yalın yığın postgres + redis + litellm + fake-llm + qdrant, tee çıktıları scratchpad `r4-*.txt`):**

| Komut | Ortam | Exit | Süre | Sonuç |
|---|---|---|---|---|
| `tools make lint` | | 0 | | temiz |
| `tools make test` | llmaas | 0 | 147 s | 1382 passed |
| `tools make test` | `GUARDRAIL_EGRESS_ENABLED=false DEPLOY_PROFILE=airgap` | 0 | 152 s | 1382 passed |
| hedefli test-int: `test_08t_*` (11 dosya), `test_06b_agent`, `test_06b_direct`, `test_06b2_external_agent`, `test_06a_runs_api`, `test_134_provider_request`, `test_08_api` | llmaas | 1 | 271 s | 147 passed, 1 failed: `test_08t_r2_direct_url_lines_keep_the_placeholder[<span style=…url(…)>]`. Fake sağlayıcı uzun cevabı kesiyor; yer tutucu cevaba ulaşmadı, değer de ulaşmadı. Test beklentisi düzeltildi (4aecdbc: sağlayıcıya giden istekte değer yok + cevapta değer yok) |
| aynı | airgap | 0 | 267 s | 146 passed, 2 skipped (profil koşullu) |
| `test_08t_r2_paths.py` yeniden (4aecdbc) | llmaas / airgap | 0 / 0 | 25 s | 12 / 12 passed; ruff format + check temiz |
| `down -v` | | 0 | | konteyner 0, volume 0 |

Tam `make test-int` bu turda koşulmadı (K-08T1-0018: hedefli yeter; inceleyici r4'ü tam yığınla koşar).

**r3 (r2 düzeltmesi, HEAD 370912d; yalın yığın postgres + redis + litellm + fake-llm + qdrant, tee çıktıları scratchpad `r3-*.txt`):**

| Komut | Ortam | Exit | Süre | Sonuç |
|---|---|---|---|---|
| `tools make lint` | | 0 | | ruff check + format temiz (418 dosya) |
| `tools make test` | llmaas | 0 | 137 s | 1210 passed |
| `tools make test` | `GUARDRAIL_EGRESS_ENABLED=false DEPLOY_PROFILE=airgap` | 0 | 140 s | 1210 passed |
| hedefli `pytest` test-int: `test_08t_*` (10 dosya), `test_06b_agent`, `test_06b_direct`, `test_06b2_external_agent`, `test_06a_runs_api`, `test_134_provider_request`, `test_08_api` | llmaas | 0 | 262 s | 138 passed |
| aynı | `GUARDRAIL_EGRESS_ENABLED=false` | 0 | 271 s | 136 passed, 2 skipped (profil koşullu) |
| `down -v` | | 0 | | konteyner 0, volume 0 |

Tam `make test-int` bu turda koşulmadı (K-08T1-0014: hedefli yeter; inceleyici r3'ü tam yığınla koşar).

**r2 (r1 düzeltmesi, HEAD 6d0d9ba; aynı yalın yığın, tee çıktıları scratchpad `r2-*.txt`):**

| Komut | Ortam | Exit | Süre | Sonuç |
|---|---|---|---|---|
| `tools make lint` | | 0 | 9 s | temiz |
| `tools make test` | llmaas | 0 | 158 s | 1046 passed |
| `tools make test` | airgap | 0 | 167 s | 1046 passed |
| `tools make test-int` | llmaas | 2 | 1062 s | 813 passed, 5 skipped; kırmızılar yalnız üç ortam dosyası (02 langfuse 3, 05a live 5, 18td 3 error) |
| `tools make test-int` | airgap | 2 | 1035 s | 811 passed, 7 skipped; aynı üç ortam dosyası |
| `down -v` | | 0 | | konteyner 0, volume 0 |

**r1 (fb7130d):**

Ortam: tools konteyneri `ffcore/tools:0.0.0-08t1` (bağımlılık değişmedi, yalnız etiket), compose proje `ffcore-08t1`, `--env-file .env.test`; yığın postgres + redis + litellm + fake-llm (`--profile test`), langfuse/qdrant **açılmadı** (bellek koşulu: f19r tam yığını + airflow açıktı, K-08T1-0003).

Son SHA fb7130d, tam çıktılar oturum scratchpad'inde (`final-*.txt`, tee).

| Komut | Ortam | Exit | Süre | Sonuç |
|---|---|---|---|---|
| `tools make lint` | | 0 | 14 s | ruff check + format temiz (404 dosya) |
| `tools make test` | `DEPLOY_PROFILE=llmaas GUARDRAIL_EGRESS_ENABLED=true` | 0 | 197 s | 1010 passed |
| `tools make test` | `DEPLOY_PROFILE=airgap GUARDRAIL_EGRESS_ENABLED=false` | 0 | 212 s | 1010 passed |
| `tools make test-int` | llmaas | 2 | 1417 s | 798 passed, 5 skipped; 8 failed + 3 error **yalnız ortam** (aşağıda) |
| `tools make test-int` | airgap | 2 | 1435 s | 796 passed, 7 skipped; 8 failed + 3 error **yalnız ortam** |
| C17 entegrasyon dosyaları ayrıca | iki profil | 0 | | `test_08t_c17_exit.py` 3/3, `test_08t_c17_facade_direct.py` 3/3 (her profil) |
| `docker compose -p ffcore-08t1 ... down -v` | | 0 | | konteyner 0, volume 0 |

**NOT_RUN, ortam (K-08T1-0005 A; inceleyici ve main kapısı tam yığınla koşar):** `tests/integration/test_02_langfuse.py` (3, Langfuse yok), `tests/integration/test_05a_live_services.py` (5, mcp-search/mcp-sql konteynerleri yok, `egress_dns_failed`), `tests/integration/test_18td_tools_api.py` (3 error, ticket-desk yok). Bu PR bu servislerin yoluna dokunmuyor (izleme, MCP aktarıcıları, ticket-desk); hata nedenleri DNS/bağlantı, başka neden yok. Yığın: postgres + redis + litellm + fake-llm + qdrant (bellek koşulu: f19r/review19r tam yığını + airflow açıktı).

Ara koşu notu: fb7130d öncesi airgap test-int'te `test_08t_c17_facade_direct.py` 3 testi düştü: testler egress'in airgap'te olmadığını hesaba katmıyordu (kod hatası değil); fb7130d'de iki profile göre düzeltildi.

**F11 e2e** (`test_18_f11_5b_encoded_chunk_left_out_at_egress`, seed geri alma): NOT_RUN, e2e yığını test rolünde (K-08T1-0002 S6).

## Review r1 bulgu → düzeltme → kanıt (state/reviews/08-tam-1a-r1.md, DUZELT K-08T1-0009)

fb7130d üstüne 9 commit; her MAJOR ayrı commit, önce kırmızı test (kırmızı kanıtı: yeni test commit öncesi kodla koşuldu).

| Bulgu | Düzeltme (commit) | Kanıt |
|---|---|---|
| MAJOR-4 ReDoS (`_SHORT_TOKEN`, `_ASSIGNMENT`) | ayırıcı grubu ilk `\s*`'ı içerir, tek eşleşme yolu (298cce3) | `test_08t_m4_*`: 200.000 boşluk alt süreçte < 10 s (eskisi zaman aşımı; re GIL'i bırakmadığı için iş parçacığı değil alt süreç), 180 bin karakter tekrar; 3.000 rastgele örnekte eski desenle span eşitliği |
| MAJOR-5 yanlış pozitif → block | `anahtar` yalnız `erişim/API/gizli anahtar(ı)`; tam tümsekli camel/PascalCase ve harf+6 hane bilet kimliği muaf (852a1fb) | raporun 5 örneği + 3 benzer negatif, 3 bileşik pozitif; yakalama tablosu yukarıda (tek tablo) |
| MAJOR-6 hepsi engellenince `sources` olayı yok | olay (`selected=[]`, `blocked=[…]`) önce yazılır, sonra `StopRun` (e851997) | `test_08t_12b`, `test_08t_12c_*all_blocked*` olayı doğrular; e2e F11 5b'nin `failed` dalı artık erişilebilir (e2e NOT_RUN, S6) |
| MAJOR-7 `blocked` silinmiş belge maskesi | `_SOURCE_LISTS` + `blocked` (bd0f0d1) | `test_08t_m7_blocked_source_masked_on_list_and_live_stream`, `..._on_db_replay` (gerçek API, Redis, Postgres) |
| MAJOR-1 TTL sonrası numara tekrarı | sayaç ayrı uzun ömürlü anahtarda (400 gün; eski hash'in `n`'inden tohumlanır), `lookup` TTL yeniler, `reserve()` (90dca7f) | `test_08t_m1_*` (gerçek Redis, inceleyicinin probe'u: TTL 2 s, eski cevap yeni değere çözülmez; lookup yenileme; reserve geri gitmez); eski kodla 3/3 kırmızı |
| MAJOR-2 geçmişteki yer tutucu yeni kapsamda | `_history` önceki koşunun yer tutucusunu kendi kapsamında çözer (egress yeni kapsamda yeniden tokenize eder), çözülemeyen kalır, yeni kapsam sayacı taşınan en büyük numaranın üstüne alınır; facade agent istemci geçmişini egress öncesi metinle saklıyordu (5083e5e). **r2'de tersine döndü:** geçmiş doğrudan yeni yer tutucuya eşlenir, istemci geçmişi run kapsamında tokenize saklanır (e2c32b2, aşağıdaki r2 tablosu) | `test_08t_m2_history_*` (A/B kapsam probe'u), r1'de `test_08t_m2_client_history_stored_before_egress` (eski kodla kırmızı; r2'de `test_08t_r2_client_history_stored_in_the_runs_scope` olarak tersine döndü); `test_06b_agent`, `test_134_provider_request` yeşil |
| MAJOR-3 URL/markdown sızdırma kanalı (karar A) | `](…)`, `href=…`, `scheme://…` içindeki yer tutucu geri çevrilmez, `detokenize_skipped_url` (sayı); akışlar son boşluktan beri metni bağlam olarak tutar (≤ 8.192) (1850df3) | `test_08t_m3_url_context.py` (7 bağlam, parça sınırı 3 biçim), `test_08t_m3_paths.py` (dış agent, facade agent `_events`, konsol canlı akış), `test_08t_m3_direct_placeholder_in_a_url_stays` (tek parça + canlı); docs "kim neyi görür" tablosu |
| MINOR-1 hata/iptalde kuyruk | graph model düğümü `finally`; facade düz akış `ApiError`'da önce kuyruk (1a36dfa) | `test_08t_r1_minor1_*` (eski kodla kırmızı) |
| MINOR-2 `rest` usage'dan sonra, finish'siz | usage chunk'ından önce, `finish_reason` ile (yoksa `stop`) (1a36dfa) | `test_08t_r1_minor2_*` (eski kodla kırmızı) |
| MINOR-3 araç argümanında JSON kaçışı | değer JSON-escape (tek parça ve canlı) (1850df3) | `test_08t_r1_minor3_*` (`"` içeren değer, JSON ayrışır) |
| MINOR-7 S8 uç nokta + rol | test (6d0d9ba) | `test_08t_m7_owner_sees_values_approver_and_admin_placeholders` (gerçek `resume_run` + `GET /stream`) |
| MINOR-8 dış agent / facade agent olumlu | test (1850df3) | `test_08t_m8_external_agent_echo_reversed_for_the_caller`, `test_08t_m8_facade_agent_events_reversed` |
| MINOR-11 okuma tarafı Redis hatası | `RevealUnavailable` → akış `error` olayı `detokenize_unavailable` ile biter (koşu sürer) (1850df3) | `test_08t_r1_minor11_*` |
| MINOR-12 16 ↔ 15 | docs/api.md 15 (1850df3) | — |

**FOLLOWUP-162'ye ertelenenler (kısıt olarak):** MINOR-4 (politika okuma anında çözülür; koşu sırasında enforce olan kural sonradan monitor'a alınırsa saklanan cevap sahibine açılır), MINOR-5 (açık SSE bağlantısı üyelik/rol değişikliğini görmez; yeniden bağlanmada reddedilir), MINOR-6 (canlı facade akışında sayaç logları iki kez), MINOR-9 (enforce politikada C17 fiilen kapalı; seed hedef projesinde C17 çalışmaz), MINOR-10 (`masks_pii_at` aksiyon/kategoriye bakmaz; yön güvenli), MINOR-13 (106 yanlış negatifleri: `auth_token:`, `DB_TOKEN=` öneki, boşluklu `api key`), MINOR-14 (`search_documents` kaynak numarası çakışması; F11 5b sızıntı iddiası bütün injection satırıyla), NOTE 1-8 (impersonation sahip sayılır; başarılı geri çevirme audit'i yok; `Run.input` ham; 9+ haneli yer tutucu hizalanmaz; tümü engellenen `search_documents` koşuyu düşürür ve bütçe boşluğu doldurulmaz; parça başına egress olay çoğalması; konsol arayüzü `blocked`'ı göstermez; `check_http_destination` userinfo/query/rezerve reddi yapmaz, webhook için 06b-2 kuralları ayrıca gerekir).

**Bilinen sınırlar (r4 sonrası):**
- Cevap düzeyinde HTML (karar A, r4): HTML yazan cevapta ilk etiketten sonraki değerler yer tutucu kalır, `a<b` gibi düzyazı dahil. Konsol düz metin gösterdiği için etki ham HTML işleyen üçüncü taraf istemcilerde.
- r1 notundaki "URL başı 8.192'den önceyse açılabilir" sınırı kalktı (fail-closed, MAJOR-r2-1).
- Sayaç anahtarı 400 gün yaşar (en uzun saklama sınıfının üstü). Daha eski saklanan bir yer tutucunun kapsamı tekrar açılırsa numara çakışabilir.
- URL satırı kuralının takası: bağlantı ya da işaret içeren satırdaki değer okuyucuya yer tutucu olarak gider; düzyazıdaki işaretler de dahil (`Personal data:` → `data:`, `Attached file:` → `file:`, `//` yorumu) (docs/guardrail.md).
- Akışta 8.192 karakteri aşan satır yer tutucularını tutar. Açık bir satır böyle kesilirse cevabın geri kalanı da tutar; yeniden bağlanmada durum kurulamazsa da (r4 (d′)).
- Bir kapsam en çok 9.999.999 numara verir (r5, karar (h)); aşarsa istek ya da koşu `placeholder_out_of_range` ile düşer (`on_error`'dan bağımsız). 10.000.000'dan büyük ya da ASCII olmayan rakamlı `<<PII_n>>` yer tutucu değildir; taşınırsa yok sayılır.
- HTML kuralının kapsamı okuyucunun akışının geri kalanı (r5, karar (i)): turlar arası sıfırlanmaz, onay sonrası hazırlık önceki girdileri yeniden oynatır; bedel konsol sahibine de düşer (`<br>`, `List<String>`, `#include <stdio.h>`, `Bearer <token>`, `<your-email>`, `x<y`).
- Replay'de (canlı akış süresi dolmuş) `after` ile bağlanan okuyucu saklanan bütün satırların yer tutucularını tutar (d′'nin yan etkisi, fail-closed; r5 NOTE-2).
- Facade agent istemci geçmişi satırları artık run kapsamında tokenize (llmaas). airgap'te egress olmadığı için denetlenmiş metinle saklanır (önceden olduğu gibi). Kullanıcı sorusu (`Run.input`, soru satırı) ham saklanmaya devam eder (r1 NOTE, FOLLOWUP-162).

## Review r2 bulgu → düzeltme → kanıt (state/reviews/08-tam-1a-r2.md, DUZELT K-08T1-0014)

6d0d9ba üstüne 4 commit. Kırmızı kanıtı: yeni testler `6d0d9ba`'nın `backend/ffcore`'u ile koşuldu (llmaas, yalın yığın): 118 kırmızı / 53 yeşil. Yeşil kalanlar kontrol satırları: r1 kuralının zaten tuttuğu `![x](https://…)`, kapanmış hedef, kesik satırın yeni satırda bitmesi gibi. `test_08t_r2_rescope.py` eski kodda import hatası verir (`rescope` yok).

| Bulgu | Düzeltme (commit) | Kanıt |
|---|---|---|
| MAJOR-r2-1 URL bağlamı atlatılıyor | Kural satır düzeyinde (KARARLAR "satır düzeyinde ve fail-closed"): `](`, `]:`, `//`, `src=`, `href=`, `srcset=`, `action=`, `poster=`, `background=` içeren satırdaki yer tutucu çözülmez. Satır sonunda açık kalan hedef (tırnaklı öznitelik, markdown hedefi, değeri alt satırda `]:`/`=`) sonraki satıra taşınır, kapanana kadar sürer. Akışta 8.192'yi aşan satır tutulur. Dört yol aynı `reveal_text`/`UrlLines`'ı kullanır (87b7e7b). | `test_08t_r2_url_lines.py`: raporun tablosunun tamamı + `srcset/action/poster/background`, büyük harf `SRC =`, alt satıra taşan dört hedef. Her biri tek parça ve akışta (parça 1/3/7/64, `StreamDetokenizer` + `ContextReveal`), JSON dizgileri, 8.192 öncesi URL başı, uzun satır, boşluklu öznitelik. Negatif kontrol: kapanmış hedef ve düzyazıdaki kesme işareti sonraki satırı tutmaz. Entegrasyon: `test_08t_r2_direct_url_lines_keep_the_placeholder` (inceleyicinin probe şekilleri + `<img src=…>` iki biçim, gerçek LiteLLM + fake sağlayıcı, iki profil) |
| MAJOR-r2-2 bayat yer tutucu yeni değere | `reserve_carried` ilk tokenize öncesi kapsama giren bütün metnin en büyük numarasını ayırır: konsol (`_history` soru + geçmiş, konuşmasız koşu dahil), facade agent (`guard.text` döngüsünden önce, istemci geçmişi + soru), facade düz yol (`guard_messages` başı), dış agent (e2c32b2). | `test_08t_r2_stale_client_placeholder_never_becomes_a_new_value` (inceleyicinin probe senaryosu: `<<PII_1>>` çözülmez, e-posta `<<PII_2>>`), `test_08t_r2_question_numbers_are_reserved_first`, `test_08t_r2_direct_stale_placeholder_is_passed_by_the_counter`, `test_08t_r2_external_agent_stale_placeholder_is_passed_by_the_counter` |
| MAJOR-r2-3 geçmiş ham değere çevriliyor | `_history` eski yer tutucuyu eski kapsamda `entry()` ile (değer + `i:` kimliği, TTL yenilemeden) okur, yeni kapsamda `token_for(kimlik, değer)` ile yeni yer tutucu verir (`rescope`). Ham metin üretmez; bulunamayan kalır. Run'sız satırlar (facade agent istemci geçmişi) kendilerinden sonraki ilk run'lı satırın kapsamında okunur. Facade agent istemci geçmişini egress çıktısıyla, run kapsamında saklar (e2c32b2). | `test_08t_r2_history_reaches_the_provider_as_a_placeholder`: inceleyicinin senaryosu, `min_confidence` 0,8. Bağlamsız cümlede telefon; kontrol: egress tek başına numarayı bulmuyor. Gerçek graph, runner, EngineGuard ve `_history` ile koşulur. Modele giden mesajda yer tutucu var, numara yok. `messages`, `run_events`, `guardrail_events`, `checkpoints.checkpoint_blobs/writes/checkpoints` içinde numara yok. Ayrıca `test_08t_m2_history_maps_to_the_new_scope_without_the_raw_value`, `test_08t_r2_client_history_rows_take_the_following_runs_scope`, `test_08t_r2_client_history_stored_in_the_runs_scope` (eski `..._stored_before_egress` tersine döndü) |
| MINOR-r2-1 büyük numara sayacı bozuyor | `placeholder_numbers` yalnız ≤ 8 haneli (en çok 16 karakterlik) yer tutucuyu sayar (e2c32b2) | `test_08t_r2_only_numbers_a_scope_can_issue_are_reserved` (9 hane ve 2^63 üstü yok sayılır, 8 hane ayrılır), `test_08t_r2_numbers_are_at_most_eight_digits`. "Eski kapsamın aralığı" tercihi uygulanmadı: soru ve istemci geçmişinin eski kapsamı bilinmiyor; 8 hane sınırı akış hizalamasını ve `INCR`'ı korur |
| MINOR-r2-2 hata olayı kimliği | `follow` son teslim edilen girdinin kimliğini tutar (`delivered`): canlı dal, replay, bitmiş koşunun replay'i (07279b1) | `test_08t_r2_minor2_live_error_carries_the_last_delivered_id`, `..._replay_...` (ikisi eski kodla kırmızı). Kapsama testi (eski kodda da yeşil): `test_08t_r2_minor2_store_error_becomes_reveal_unavailable` (`RedisError` → `RevealUnavailable`), `test_08t_r2_minor2_facade_agent_maps_the_error_to_502` |
| MINOR-r2-3 facade düz akış olaysız kesiliyor | `_LiveReveal.choice/rest` `RedisError`/`OSError`/`RevealUnavailable` → `ApiError(502, api_error, detokenize_unavailable)`. Tutulan parça ve kuyruk geri çevrilmeden önce gider, sonra hata olayı ve `[DONE]` (07279b1). | `test_08t_r2_minor3_direct_store_failure_ends_with_a_coded_error` (eski kodla kırmızı: `ConnectionError` kaçıyordu) |
| MINOR-r2-4 geçmiş okuması TTL yeniliyor | `entry()` TTL yenilemez; `_history` yalnız onu kullanır (e2c32b2) | `test_08t_r2_history_does_not_renew_the_earlier_mapping` |
| MINOR-r2-5 docs | agentlar.md (geçmiş davranışı, TTL yenileme), guardrail.md (sayaç 400 gün, ayırma, URL satır kuralı ve takası, hata davranışları, `_TICKET_ID` büyük harf, `erisim`), api.md (URL satırı, 502 `detokenize_unavailable`) (370912d) | — |
| MINOR-r2-6 PR notu | bu not: dosya/commit sayısı, kriter 8, tek 106 tablosu ve 1/2000'in nedeni, ReDoS süreleri, varsayım 5/6, güvenlik notu | — |
| MINOR-r2-7 kapsanmayan yollar | yukarıdaki testler | — |
| NOTE-1 yorum 16 → 15 | `masking.py:20` (87b7e7b) | — |

## Review r3 bulgu → düzeltme → kanıt (state/reviews/08-tam-1a-r3.md, DUZELT K-08T1-0018; kararlar K-08T1-0020/0021)

370912d üstüne 9 commit (son commit 4aecdbc yalnız test beklentisi). Kırmızı kanıtı her testin commit öncesi koduyla koşusu: url_scan 2/6 kırmızı (1 karakterlik parçalarla 13,6 s / 12,8 s); url_rules 36 kırmızı; blank_line 12 kırmızı; resume 5/5 kırmızı (eski `detokenizer` `after` almıyordu); range 3/4 kırmızı; r3_minors 1/3 kırmızı (reveal dönüşümü; diğer ikisi kapsama testi, eski kodda da yeşil).

| Bulgu | Düzeltme (commit) | Kanıt |
|---|---|---|
| MAJOR-r3-2 tarama gerilemesi | `UrlLines` artımlı (1d6e84e) | `test_08t_r3_long_line_in_one_character_pieces` (100 bin karakter, 1 karakterlik parça, StreamDetokenizer ve ContextReveal < 1 s), `..._in_four_pieces` (64 bin, < 0,2 s), `test_08t_r3_marker_split_over_pieces_still_seen` |
| MAJOR-r3-1 HTML yeniden yazımları | sınıf kuralı (a)+(b) (0ad2aab) | `test_08t_r3_url_rules_keep_the_placeholder`: inceleyicinin dört yazımı + 9 ek (çok satırlı etiket, erken kapanan etiket + satır sonunda öznitelik, `http:`/`HTTPS:`/`javascript:`/`data:`, CSS `url(`, `<<img`, `<p>`) + r2 tablosu; tek parça, JSON, StreamDetokenizer, konsol (hizalı girdiler). Negatif kontrol: düz yer tutucu, `a < b`, `3:5`, boş satırdan sonra. Entegrasyon: dört yazım facade düz yolda gerçek LiteLLM ile (iki profil) |
| MINOR-r3-1 yeniden bağlanma | durum saklanan girdilerden kurulur, kurulamazsa ilk satır tutulur (77cc903) | `test_08t_r3_resume.py`: inceleyicinin senaryosu (e1 `](https://…?q=` + yeniden bağlanma + e2), önceki satırdan taşınan HTML değeri, onay sonrası temiz satır değer gösterir, bilinmeyen girdi ve Redis hatası fail-closed; `test_08t_m7_owner_sees_values_approver_and_admin_placeholders` (sahip onay sonrası değeri görür) yeşil |
| MINOR-r3-2 9 hane çakışması | sayaç sınırı ve 9+ hane yer tutucu değil (2e35856); r4'te f′, r5'te karar (h) ile değişti: sınır 9.999.999, 10.000.000 ve üstü taşınan numara yok sayılır | `test_08t_r3_range.py`; r3'teki `test_08t_r3_history_number_past_the_range_fails_loudly` r4'te `..._99999999_is_ignored_...`, r5'te `test_08t_r5_large_carried_numbers_are_ignored_and_the_range_ends_loudly` oldu |
| MINOR-r3-3 komşu facade yolları | `FacadeGuard.reveal` → 502 `detokenize_unavailable` (de30d05) | `test_08t_r3_minor3_facade_reveal_maps_store_errors_to_502` (gerçek `FacadeGuard`, düşük Redis), `..._buffered_stream_ends_with_the_error_and_done` |
| MINOR-r3-4 boş satır | yalnız markdown hedefi kapanır (4c3f5ae) | `test_08t_r3_blank_line.py` (markdown 4 biçim açılır; HTML 5 biçim ve `_lost` tutulur) |
| MINOR-r3-5 docs | (8837a72) | agentlar.md URL kuralı + yeniden bağlanma; guardrail.md sınıf kuralı, boş satır, yeniden bağlanma, facade hata biçimi (kimliksiz, `X-Resume-Run-Id`), 8 hane; api.md aynı; takas ifadesi "a line with a link, an HTML tag, a URL scheme or a marker" |
| MINOR-r3-6 canlı dalda yeniden bağlanma | test (de30d05) | `test_08t_r3_minor6_reconnect_after_the_error_gets_the_failed_entry` |
| MINOR-r3-7 araç/KB metnindeki düz yer tutucu | FOLLOWUP-162 (koordinatör ekledi) | kısıt aşağıda |
| MINOR-r3-8 PR notu r1 satırı | r1 tablosu MAJOR-2 satırı r2 tersine dönüşünü anlatır | bu not |
| NOTE-1 süre bütçesi | ölçüm alt süreç içinde (aa26bd7) | `test_08t_secrets_linear.py` 7/7 |
| NOTE-2 güvenlik notu | varsayım 9'a göre yazıldı | bu not |

## Review r4 bulgu → düzeltme → kanıt (state/reviews/08-tam-1a-r4.md, DUZELT K-08T1-0024; karar A)

4aecdbc üstüne commit'ler yukarıda. Kırmızı kanıtı commit öncesi kodla: html_response 96 kırmızı / 29 yeşil (yeşiller olumlu kontroller ve r3'ün zaten tuttuğu biçimler); resume 3/6 kırmızı (bilinmeyen girdi, Redis hatası, beklenmeyen hata); range 4 kırmızı (99.999.999 yok sayma, 99.999.998 sınırı, 9+ hane/99.999.999 yer tutucu değil, motor `on_error=log`). MINOR-r4-4 yalnız test (kırmızı yok).

| Bulgu | Düzeltme (commit) | Kanıt |
|---|---|---|
| MAJOR-r4-1 HTML yazımları (yapısal) | karar A: cevap düzeyinde HTML; HTML kipleri ve öznitelik taşıması kalktı; CR bekletme (c22894a) | `test_08t_r4_after_the_first_tag_nothing_is_reversed`: raporun yedi yazımı ((a), (a′), (b), (b′), (c), (d) iki biçim) + etiketli satırdan sonraki düz satır + `a<b` × dört okuma biçimi × parça 1/7/50; `test_08t_r4_crlf_split_over_pieces_is_one_line_break` ((e)); `test_08t_r4_answers_without_html_before_it_are_reversed` (HTML'siz cevap, tam yer tutucu, ilk etiketten önceki satır, `a < b`, yalnız markdown); r2/r3 tabloları (`test_08t_r2_url_lines.py`, `test_08t_r3_url_rules.py`) ve r3 entegrasyon şekilleri yeşil |
| MINOR-r4-1 aralık hatası `on_error` yolundan | motor `PlaceholderOutOfRange`'ı yeniden yükseltir (7a10789); docs yola göre (60f2250) | `test_08t_r4_engine_fails_loudly_whatever_on_error_says` (`on_error=log`, enforce, sağlayıcıya gidecek metin dönmez) |
| MINOR-r4-2 kalıcı konuşma düşmesi | (f′): 99.999.999 verilmez/ayrılmaz/açılmaz, taşınan yok sayılır (7a10789) | `test_08t_r4_carried_99999999_is_ignored`, `test_08t_r4_issuing_past_99999998_fails_loudly`, `test_08t_r4_history_99999999_is_ignored_and_the_range_ends_loudly` (gerçek Redis: konuşma çalışır, sonraki değer `<<PII_2>>`, 99.999.998'den sonra fail-loud) |
| MINOR-r4-3 hazırlık hatasında ikinci satır | (d′): `_lost` (a0795ad) | `test_08t_r3_unknown_entry_keeps_the_rest`, `test_08t_r3_redis_failure_keeps_the_rest` |
| MINOR-r4-4 zayıf test | güçlü iddia geri, `style` kısaltıldı (8897584) | `test_08t_r2_paths.py` 12/12 (iki profil) |
| MINOR-r4-5 takaslar docs'ta | guardrail.md "The trade-off" paragrafı (60f2250) | — |
| MINOR-r4-6 `prime` beklenmeyen hata | her hata fail-closed (a0795ad) | `test_08t_r4_unexpected_rebuild_error_keeps_the_rest` |
| NOTE-6 PR notu | r1 tablosu MAJOR-2 satırı, "Bilinen sınırlar", r3 NOTE-4 FOLLOWUP listesinde | bu not |

## Review r5 bulgu → düzeltme → kanıt (state/reviews/08-tam-1a-r5.md, DUZELT K-08T1-0028; kararlar (g)-(i))

Kırmızı kanıtı commit öncesi kodla: r5_tail 10/17 kırmızı (yeşiller parça boyu 4, 5, 11 gibi pencerenin yer tutucuyu kesmediği durumlar); range + history 7 kırmızı. NOTE-7, MINOR-r5-3 ve docs için kırmızı yok (test/metin). Evaluate 400 testi kapsama testi (davranış r4'ten beri var).

| Bulgu | Düzeltme (commit) | Kanıt |
|---|---|---|
| MAJOR-r5-1 kuyruk penceresi | istisna önceki karaktere bakmaz, (g) (d1c2960) | `test_08t_r5_facade_stream_shows_every_value` ve `test_08t_r5_console_live_shows_every_value` (parça 1, 2, 3, 4, 5, 6, 8, 11: 3/3), `test_08t_r5_random_token_pieces_lose_no_value` (200 deneme, 0 kayıp); `<PII_1 style` testi (r4) yeşil |
| MINOR-r5-1 konuşma kalıcı bozulması | (h): eşik 10.000.000, ASCII rakam (14b8db7) | `test_08t_r5_carried_numbers_from_ten_million_are_ignored` (`<<PII_99999999>>`, `<<PII_99999998>>`, `<<PII_10000000>>`, Arap-Hint rakamları), `test_08t_r5_issuing_past_9999999_fails_loudly`, `test_08t_r5_large_and_non_ascii_numbers_are_no_placeholders`, `test_08t_r5_large_carried_numbers_are_ignored_and_the_range_ends_loudly` (gerçek Redis: konuşma çalışır, değerler normal numara) |
| MINOR-r5-2 HTML bedeli ve kapsamı | (i) docs: "okuyucunun akışının geri kalanı", konsol sahibi dahil, tetikleyici listesi (33a0268) | — (kod değişikliği yok) |
| MINOR-r5-3 bayat test/PR metni | test açıklamaları (4c5e732), PR varsayım 10/12, r3 tablo satırı, güvenlik notu | bu not |
| MINOR-r5-4 docs sapmaları | evaluate 400 docs + openapi (bb720a1), api.md tamponlu akış, guardrail.md "işaretli ya da açık satır" (33a0268) | `test_08t_r5_evaluate_used_up_range_is_400` (`on_error=log`), `test_08_22_openapi_draft_matches_app` |
| NOTE-1 | `exc_info=True` (bb720a1) | — |
| NOTE-2 | PR "Bilinen sınırlar" | — |
| NOTE-7 | CPU süresi (07c17ee) | `test_08t_r3_url_scan.py` 6/6 |

**FOLLOWUP-162'ye (r5, koordinatör ekledi):** NOTE-3 (9 haneli ve `x<PII_1>>` gibi biçimler, `<` + Unicode harf etiket sayılır; fail-closed), NOTE-4 (CR CR tek parçada ve akışta tutarsız; ikisi de güvenli). r4 NOTE-3 (replay'de `fail_closed` saklanan cevabı gereksiz tutar) d′ ile "Bilinen sınırlar"da.

**FOLLOWUP-162'ye (r4, koordinatör ekledi):** NOTE 1 (`gate.commit` `finally` içinde Redis hatası akışı olaysız bitirir), NOTE 2 (ikinci hata dalında `rest()` 502), NOTE 4 (hazırlık XRANGE `COUNT` ile sayfalansın), NOTE 5 (büyük tek parça cevapta span × yer tutucu karşılaştırması); r3 NOTE-4 (probe'un hizalanmamış parçalarla `ContextReveal` kullanması yapay; gerçek yolda yazar hizalar, testler hizalı girdi kullanıyor).

**FOLLOWUP-162'ye (r3):** MINOR-r3-7 (araç sonucu ve KB parçasındaki düz `<<PII_n>>` metni ayrılmıyor; koşunun kendi değerine açılabilir, kapsamlar arası sızıntı değil), NOTE-3 (r2 öncesi istemci geçmişi satırları; yalnız dağıtım öncesi veri), NOTE-5 (onay bekleyen koşunun checkpoint'i ölçülmedi; kod okumasıyla ham değer girmez).

**FOLLOWUP-162'ye (r2):** NOTE 2-8 (koordinatör ekledi): `finally` içinde `events.live` hatası özgün hatayı örter; hata dalında rest chunk `stop` + hata; MAJOR-5 yan etkileri; URL'den sonraki yer tutucu (satır kuralıyla artık bilinçli takas); S8 kapsanmayan roller ve tek parça MINOR-3 testi; İngilizce sabit hata mesajı; `_search_tool` tümü engellenince koşuyu düşürür.

## Varsayımlar ve sapmalar

1. **Yazma tarafında hizalama (plandan sapma; K-08T1-0004 kabul):** plan konsol akışında okuma tarafında durumlu tampon öngörüyordu. Uygulanan: model düğümü canlı `token` girdisini yer tutucu ortasında bitirmez (`PlaceholderAligner`), okuyucu girdi başına durumsuz geri çevirir. Neden: okuma tarafı tamponu tutulan kuyruğu ayrı bir SSE mesajıyla, aynı SSE kimliğiyle yollamak zorunda kalırdı; `Last-Event-ID` ile yeniden bağlanan istemci o kuyruğu kaybederdi. Yazma tarafında tutmak kimlik/yeniden oynatma düzenini değiştirmez; Redis'teki metin yine tokenize.
2. **Çıkışta enforce `pii` kuralı varsa geri çevirme yok (plana ek; K-08T1-0004 kabul, `detokenize_skipped_policy` sayaç logu fb7130d):** `output.pre`/`output.stream.delta`'da enforce bir `pii` kuralı varsa, cevap yer tutucularla denetlendiği için değerleri sonradan açmak politikanın gizlediğini gösterirdi (`test_06b_4_stream_output_buffered_then_checked` bunu yakalardı). Güvenli taraf: yer tutucu kalır (`engine.masks_pii_at`). Yerleşik politika monitor olduğu için varsayılan kurulumda geri çevirme çalışır; e2e hedef projesi (enforce) yer tutucu görür.
3. **Facade `x_platform.sources`:** `blocked` listesi koşu olayında ve konsol SSE'sinde var; facade `x_platform.sources` olayına eklenmedi (C11 donmuş biçim; additive olurdu ama GOREV kapsamı koşu olayıydı). FOLLOWUP adayı.
4. **107 sırası:** kaynak başına egress `retrieve` düğümünde, `sources` olayından önce koşar; soru `input.pre`'de bloklanırsa kaynaklar için egress olayları yine yazılmış olur (gönderilmemiş metin için kayıt). Kaynak egress'i `guard_in`'e taşımak `sources` olay sırasını değiştirirdi.
5. **S9 TTL (r2 güncel):** eşleme son kullanımdan `PII_TOKEN_TTL_S` (1800 s) sonra düşer. Koşunun kendi okuması ve çıkış okuması TTL'i yeniler (r1 MAJOR-1). Sonraki bir koşunun geçmiş okuması yenilemez (MINOR-r2-4). Onay beklerken hiç okunmayan bir koşunun eşlemesi 1800 s sonra düşer; yer tutucu kalır ve loglanır. Onay beklerken TTL uzatma FOLLOWUP adayı olarak duruyor.
6. **Model çağrısı yarıda düşerse (r2 güncel):** hizalayıcının tuttuğu en çok 15 karakterlik kuyruk `finally` ile canlı akışa yazılır (r1 MINOR-1). Facade düz akışta token deposu düşerse tutulan parça geri çevrilmeden gider (MINOR-r2-3).
9. **URL satırı, akışta işaretten önceki yer tutucu (r2, KARARLAR metninden dar sapma):** karar "satırdaki hiçbir yer tutucu çözülmez" diyor. Tek parça metinde öyle. Akışta (canlı konsol, facade düz canlı) satırın işaretinden önce gelmiş ve gönderilmiş bir yer tutucu geri alınamaz. Satırı sonuna kadar tutmak canlı akışı satır satır yapardı. Güvenlik amacı korunuyor: her hedef işaretinden sonra başlar, hedefteki yer tutucu her durumda tutulur. `test_08t_r2_placeholder_before_the_marker` iki davranışı da yazılı tutar. Koordinatör farklı isterse satır tamponu tek değişiklik.
10. **Alt satıra taşan hedef (r2, karara ek; r4'te daraldı):** CommonMark hedefi `](`'dan sonra satır sonuna yayılabilir; açık kalan markdown hedefi sonraki satıra taşınır, boş satırla kapanır. r2-r3'teki HTML tırnağı ve öznitelik taşıması r4'te karar A ile kalktı; HTML artık okuyucunun akışı düzeyinde tutulur.
11. **`i:` alanı olmayan eski eşleme (r2):** dağıtım öncesi yazılmış eşlemede kimlik alanı yok. `rescope` kimliği `PII:<değer>` sayar; yalnız aynı değerin yeni kapsamda ayrı bir yer tutucu alabilmesi demek, değer doğru.
7. `docs/guardrail.md` `output.stream.delta` satırı: "C17 buffer gerekir" yerine "henüz kural türü yok" (C17 tamponu kural aşaması değil, çıkış sınırı).
8. C17 bir CONTRACTS kimliği değil (DRIFT-151); bu PR plan/08 kabulünü testle kanıtlar.
12. **Yeniden bağlanmada durum kurma (r3, KARARLAR ek (d)/(d′)):** karar "yalnız son satırın kuyruğu" diyor. Uygulama `after`'a kadarki **bütün** canlı token girdilerini artımlı taramadan geçirir; tutulan durum yine en çok 8.192 karakter. Neden (r4 sonrası): HTML durumu (`_html`) ve kayıp durumu (`_lost`) satırdan bağımsız, önceki bir satırda görülmüş olabilir; yalnız son satırla kurulamaz. Maliyet koşunun token metniyle doğrusal. Canlı akış süresi dolmuşsa (replay) durum kurulamaz ve d′ gereği saklanan satırların hepsi tutulur.
13. **HTML beklenen değer `<` ile başlarsa (r3):** `src=<x` açılı hedef sayılmaz. r4'te HTML kipleri tümden kalktığı için konu kapandı (`<x` cevap düzeyinde HTML).
14. **Markdown açılı hedefte harf (r4):** `](<a b>)` içindeki `<a` HTML etiketi sayılır ve cevabın kalanı tutulur (fail-closed); açılı hedefin ilk karakteri harf değilse (`](<./a b>)`) yalnız markdown satır kuralı geçerli.
15. **CSS `url(` (r4):** CSS paren taşıması HTML ile birlikte kalktı; `url(` satır işareti olarak duruyor, CSS ancak HTML içinde (`style`) yüklenir ve o durumda cevap düzeyi kural geçerli.

## Güvenlik turu için notlar (zorunlu)

- Geri çevrilmiş değer yalnız koşu sahibine (`runs.user_id == actor`) ve facade isteğinin çağıranına; onaylayıcı, diğer analist ve admin yer tutucu görür (S8). Saklanan görünümler (`GET /runs/{id}`, olay listesi, onaylar) geri çevrilmez.
- Geri çevirme yalnız aynı kapsamın (run id ya da `facade-<hex>`) Redis eşlemesiyle; dış agent/model kendi uydurduğu yer tutucuyla başka kapsamın değerine ulaşamaz. Kendi isteğinin yer tutucusunu yankılayan upstream, değeri aynı çağırana geri getirir (docs/api.md'de yazılı).
- Log: `detokenize_unresolved scope=<id> count=<n>`; değer yok (`test_08t_9_other_scope_placeholder_stays_and_is_logged` logda ad olmadığını doğrular).
- Kaynak düşürmede `blocked` girdisi parça metni taşımaz (`test_08t_12_blocked_source_dropped_answer_goes_on`).
- HTML (r4 karar A, r5 (g)/(i)): ilk HTML etiketinden (`<` + harf; tek istisna `<PII_n>>`, öncesine bakılmaz) sonra okuyucunun akışının geri kalanında hiçbir yer tutucu açılmaz; r4 raporunun yedi yazımı ((a) tırnak uyuşmazlığı, (a′), (b) `](` + `<img`, (b′) `<pre>` + boş satır, (c) `<PII_1 style`, (d) `<style>` CSS kaçışları iki biçim, (e) CRLF bölünmesi) bu sınıfla kapalı. URL satırı kuralı (r2, r3): şema-iki nokta ya da işaret (`](`, `]:`, `//`, `url(`, `src=`, `href=`, `style=`, `data=`, …) içeren satırdaki ve açık kalan markdown hedefinin sonraki satırlarındaki **hedef içindeki** yer tutucu açılmaz. Tek parça metinde satırın bütün yer tutucuları tutulur; akışta satırın işaretinden ya da ilk etiketten önce gönderilmiş yer tutucu geri alınamaz (varsayım 9; hedefte değil). Akışta kesik satır fail-closed; yeniden bağlanan okuyucu durumu saklanan girdilerden kurar, kuramazsa akışın kalanını tutar.
- Geçmiş (r2): sağlayıcıya, state'e, checkpoint'e, `messages`'a ve `guardrail_events`'e geçmişten ham değer girmez. Yeniden tespite güvenilmez (`min_confidence` 0,8 uçtan uca testi). Bir kapsamın sayacı içeri taşınan her numaranın üstünden başlar, bayat yer tutucu yeni değere çözülmez (S9).

## Kalan riskler

- F11 e2e (P5) bu PR'da koşulmadı; P5 belgesinin "48 saat" cevabı blob ile aynı parçadaysa koşu `guardrail_block` ile biter (test her iki sonucu da kabul eder, sessiz düşüş yok).
- Langfuse ve Qdrant gerektiren entegrasyon testleri bu yığında koşmadı (kapı tablosunda NOT_RUN satırları).
