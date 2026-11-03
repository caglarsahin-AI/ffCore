# PR: 08-tam-1a — çıkışta geri çevirme (C17, FOLLOWUP-141), secrets 106/107, egress 147

**Paket:** 08-tam-1a (08 tam dilim 1'in modelsiz yarısı, K-08T1-0002 S7) · **Sınıf:** [B] (yeni bağımlılık, migration, compose yok) · **Branch:** feat/08-tam-1-ner · **Baz commit:** ea0db36 · **HEAD:** (PR-HAZIR mesajında tam SHA) · **Oturum:** ffcore-isci-a-08-tam-1

Plan ve onay: `state/pr/08-tam-1.md` (PLANNED, K-08T1-0002: S1-S9 hepsi A). 08-tam-1b (NER + PRSIM) ayrı PR, ağırlıklar gelince.

## Değişen dosyalar (main...HEAD, 24 dosya, 5 commit)

- **147** (e46e4ca): `backend/ffcore/core/egress.py` (`check_http_destination`, ortak `_checked_addresses`; `check_destination` aynı denetimi kullanır), `services/external_config.py` (`check_base_url` yalnız base URL'nin eklediklerini yapar: userinfo, query, rezerve host), `tests/unit/test_08t_egress_http.py`.
- **106** (ee0d6ca): `guardrails/rules.py` (`_SHORT_TOKEN`, `SHORT_TOKEN_MIN_CHARS = 13`), `tests/unit/test_08t_secrets_short.py`, `docs/guardrail.md` (ölçüm tablosu).
- **107** (b193c54): `runtime/graph.py` (`_egress_sources`; `retrieve` ve `_search_tool`), `tests/unit/test_08t_source_egress.py`, `tests/e2e/scenarios/seed.py` (secrets enforce'a döndü, S6), `tests/e2e/scenarios/test_18_f11_f13_content.py` (P5 beklentisi), `docs/agentlar.md`, `docs/guardrail.md`.
- **C17 yardımcıları** (fdcbecd): `guardrails/masking.py` (`PlaceholderAligner`, `StreamDetokenizer`, `detokenize_json`, `log_unresolved`), `tests/unit/test_08t_c17_masking.py`.
- **C17 çıkış sınırı** (675f857): `runtime/graph.py` (model düğümünde hizalayıcı), `api/runs.py` (`is_run_owner`, `policy_allows_reveal`, `reveals_values`, `detokenizer`, `live_transform`, `_replay_rows(reveal)`, `_stream(reveal=)`), `services/facade_agent.py`, `services/facade_guard.py` (`reveals`, `reveal`, `stream_reveal`), `services/facade_proxy.py` (`_LiveReveal`, tek parça ve tamponlu yol), `services/facade_external.py`, `guardrails/engine.py` (`masks_pii_at`), testler `tests/unit/test_08t_c17_{runtime,facade}.py`, `tests/integration/test_08t_c17_{exit,facade_direct}.py`, `docs/{agentlar,api,guardrail}.md`.

`state/` değişikliği yok (branch'te). Yeni bağımlılık, migration, compose, OpenAPI değişikliği yok.

## Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 7 | C17: tam metin geri çevrilir (konsol sahibi, facade agent, facade düz yol tek parça, dış agent) | `test_08t_7_console_owner_gets_values_others_placeholders` (gerçek Postgres+Redis), `test_08t_7c_direct_answer_reversed_for_the_caller` (gerçek LiteLLM + fake sağlayıcı), `test_08t_7_detokenize_json_walks_every_string`, `test_06b2_*` (dış agent, değişmeden yeşil) | geçti |
| 8 | C17 akış: `<<PII_` ve `1>>` ayrı chunk'larda istemciye ham yer tutucu gitmez; 16 karakteri aşan dizgi tutulmaz | `test_08t_8_aligner_never_publishes_a_partial_placeholder` (her bölme noktası), `test_08t_8_aligner_random_chunks` (300 rastgele bölme), `test_08t_8_stream_split_placeholder_reversed`, `test_08t_8_live_tokens_carry_whole_placeholders`, `test_08t_7c_live_content_split_placeholder_reversed`, `test_08t_7c_tool_call_arguments_split_reversed`, `test_08t_8_direct_live_stream_reversed` (gerçek akış), `test_08t_8b_text_that_is_not_a_placeholder_is_not_held` | geçti |
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
| büyük harf 2x6 | %95,2 | 0/200 |
| büyük harf 3x6 | %99,0 | 0/200 |
| büyük harf 16 | %99,1 | 0/200 |
| karışık + rakam 14 | %100 | 0/200 |
| büyük harf + rakam 20 | %100 | 0/200 |

2x6'daki ~%5 kaçak: rastgele altılı çiftin her iki parçası "sözcük" sayılıyor (≥ %30 sesli, 3 ünsüz dizisi yok) ve belge adları/kodlar için gereken düz tanımlayıcı muafiyetine giriyor. Muafiyet gevşetilmedi (yanlış pozitif riski); test tabanı 0,94.

## Çalıştırılan komutlar

Ortam: tools konteyneri `ffcore/tools:0.0.0-08t1` (bağımlılık değişmedi, yalnız etiket), compose proje `ffcore-08t1`, `--env-file .env.test`; yığın postgres + redis + litellm + fake-llm (`--profile test`), langfuse/qdrant **açılmadı** (bellek koşulu: f19r tam yığını + airflow açıktı, K-08T1-0003).

(KAPI TABLOSU: kapılar bitince doldurulur)

## Varsayımlar ve sapmalar

1. **Yazma tarafında hizalama (plandan sapma):** plan konsol akışında okuma tarafında durumlu tampon öngörüyordu. Uygulanan: model düğümü canlı `token` girdisini yer tutucu ortasında bitirmez (`PlaceholderAligner`), okuyucu girdi başına durumsuz geri çevirir. Neden: okuma tarafı tamponu tutulan kuyruğu ayrı bir SSE mesajıyla, aynı SSE kimliğiyle yollamak zorunda kalırdı; `Last-Event-ID` ile yeniden bağlanan istemci o kuyruğu kaybederdi. Yazma tarafında tutmak kimlik/yeniden oynatma düzenini değiştirmez; Redis'teki metin yine tokenize.
2. **Çıkışta enforce `pii` kuralı varsa geri çevirme yok (plana ek, koordinatör görüşü istenir):** `output.pre`/`output.stream.delta`'da enforce bir `pii` kuralı varsa, cevap yer tutucularla denetlendiği için değerleri sonradan açmak politikanın gizlediğini gösterirdi (`test_06b_4_stream_output_buffered_then_checked` bunu yakalardı). Güvenli taraf: yer tutucu kalır (`engine.masks_pii_at`). Yerleşik politika monitor olduğu için varsayılan kurulumda geri çevirme çalışır; e2e hedef projesi (enforce) yer tutucu görür.
3. **Facade `x_platform.sources`:** `blocked` listesi koşu olayında ve konsol SSE'sinde var; facade `x_platform.sources` olayına eklenmedi (C11 donmuş biçim; additive olurdu ama GOREV kapsamı koşu olayıydı). FOLLOWUP adayı.
4. **107 sırası:** kaynak başına egress `retrieve` düğümünde, `sources` olayından önce koşar; soru `input.pre`'de bloklanırsa kaynaklar için egress olayları yine yazılmış olur (gönderilmemiş metin için kayıt). Kaynak egress'i `guard_in`'e taşımak `sources` olay sırasını değiştirirdi.
5. **S9 TTL:** onay bekleyen uzun koşularda (`PII_TOKEN_TTL_S` 1800 s) yer tutucu açılmaz, log düşer. FOLLOWUP adayı: onay beklerken TTL uzatma (K-08T1-0002 notu).
6. **Model çağrısı yarıda düşerse** (LiteLLM yeniden deneme/hata) hizalayıcının tuttuğu en çok 15 karakterlik kuyruk o denemenin canlı akışına yazılmaz; koşu zaten hata ile biter ya da yeni deneme kendi akışını yazar. Saklanan cevap etkilenmez.
7. `docs/guardrail.md` `output.stream.delta` satırı: "C17 buffer gerekir" yerine "henüz kural türü yok" (C17 tamponu kural aşaması değil, çıkış sınırı).
8. C17 bir CONTRACTS kimliği değil (DRIFT-151); bu PR plan/08 kabulünü testle kanıtlar.

## Güvenlik turu için notlar (zorunlu)

- Geri çevrilmiş değer yalnız koşu sahibine (`runs.user_id == actor`) ve facade isteğinin çağıranına; onaylayıcı, diğer analist ve admin yer tutucu görür (S8). Saklanan görünümler (`GET /runs/{id}`, olay listesi, onaylar) geri çevrilmez.
- Geri çevirme yalnız aynı kapsamın (run id ya da `facade-<hex>`) Redis eşlemesiyle; dış agent/model kendi uydurduğu yer tutucuyla başka kapsamın değerine ulaşamaz. Kendi isteğinin yer tutucusunu yankılayan upstream, değeri aynı çağırana geri getirir (docs/api.md'de yazılı).
- Log: `detokenize_unresolved scope=<id> count=<n>`; değer yok (`test_08t_9_other_scope_placeholder_stays_and_is_logged` logda ad olmadığını doğrular).
- Kaynak düşürmede `blocked` girdisi parça metni taşımaz (`test_08t_12_blocked_source_dropped_answer_goes_on`).

## Kalan riskler

- F11 e2e (P5) bu PR'da koşulmadı; P5 belgesinin "48 saat" cevabı blob ile aynı parçadaysa koşu `guardrail_block` ile biter (test her iki sonucu da kabul eder, sessiz düşüş yok).
- Langfuse ve Qdrant gerektiren entegrasyon testleri bu yığında koşmadı (kapı tablosunda NOT_RUN satırları).
