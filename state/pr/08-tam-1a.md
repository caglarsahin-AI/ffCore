# PR: 08-tam-1a — çıkışta geri çevirme (C17, FOLLOWUP-141), secrets 106/107, egress 147

**Paket:** 08-tam-1a (08 tam dilim 1'in modelsiz yarısı, K-08T1-0002 S7) · **Sınıf:** [B] (yeni bağımlılık, migration, compose yok) · **Branch:** feat/08-tam-1-ner · **Baz commit:** ea0db36 · **HEAD:** 6d0d9ba0aa0efcf04eddf9409d36e42f16053f55 (r1 incelenen: fb7130d) · **Oturum:** ffcore-isci-a-08-tam-1

Plan ve onay: `state/pr/08-tam-1.md` (PLANNED, K-08T1-0002: S1-S9 hepsi A). 08-tam-1b (NER + PRSIM) ayrı PR, ağırlıklar gelince.

## Değişen dosyalar (main...HEAD, 24 dosya, 6 commit)

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
| MAJOR-5 yanlış pozitif → block | `anahtar` yalnız `erişim/API/gizli anahtar(ı)`; tam tümsekli camel/PascalCase ve harf+6 hane bilet kimliği muaf (852a1fb) | raporun 5 örneği + 3 benzer negatif, 3 bileşik pozitif; yakalama: büyük 2x6 %95,2, 3x6 %99,0, 16 %99,1, karışık 14 %99,95, büyük+rakam 20 %100 (sözcüksüz 0/200); 08 r3 probe'ları (`08-entropy-probe*.py`) aynı sayılar |
| MAJOR-6 hepsi engellenince `sources` olayı yok | olay (`selected=[]`, `blocked=[…]`) önce yazılır, sonra `StopRun` (e851997) | `test_08t_12b`, `test_08t_12c_*all_blocked*` olayı doğrular; e2e F11 5b'nin `failed` dalı artık erişilebilir (e2e NOT_RUN, S6) |
| MAJOR-7 `blocked` silinmiş belge maskesi | `_SOURCE_LISTS` + `blocked` (bd0f0d1) | `test_08t_m7_blocked_source_masked_on_list_and_live_stream`, `..._on_db_replay` (gerçek API, Redis, Postgres) |
| MAJOR-1 TTL sonrası numara tekrarı | sayaç ayrı uzun ömürlü anahtarda (400 gün; eski hash'in `n`'inden tohumlanır), `lookup` TTL yeniler, `reserve()` (90dca7f) | `test_08t_m1_*` (gerçek Redis, inceleyicinin probe'u: TTL 2 s, eski cevap yeni değere çözülmez; lookup yenileme; reserve geri gitmez); eski kodla 3/3 kırmızı |
| MAJOR-2 geçmişteki yer tutucu yeni kapsamda | `_history` önceki koşunun yer tutucusunu kendi kapsamında çözer (egress yeni kapsamda yeniden tokenize eder), çözülemeyen kalır, yeni kapsam sayacı taşınan en büyük numaranın üstüne alınır; facade agent istemci geçmişini egress öncesi metinle saklar (run'sız satırdaki yer tutucu hiçbir kapsamda çözülemezdi; graph egress her model çağrısında tokenize ediyor, BLOCKERS 134) (5083e5e) | `test_08t_m2_history_*` (A/B kapsam probe'u), `test_08t_m2_client_history_stored_before_egress` (eski kodla kırmızı); `test_06b_agent`, `test_134_provider_request` yeşil |
| MAJOR-3 URL/markdown sızdırma kanalı (karar A) | `](…)`, `href=…`, `scheme://…` içindeki yer tutucu geri çevrilmez, `detokenize_skipped_url` (sayı); akışlar son boşluktan beri metni bağlam olarak tutar (≤ 8.192) (1850df3) | `test_08t_m3_url_context.py` (7 bağlam, parça sınırı 3 biçim), `test_08t_m3_paths.py` (dış agent, facade agent `_events`, konsol canlı akış), `test_08t_m3_direct_placeholder_in_a_url_stays` (tek parça + canlı); docs "kim neyi görür" tablosu |
| MINOR-1 hata/iptalde kuyruk | graph model düğümü `finally`; facade düz akış `ApiError`'da önce kuyruk (1a36dfa) | `test_08t_r1_minor1_*` (eski kodla kırmızı) |
| MINOR-2 `rest` usage'dan sonra, finish'siz | usage chunk'ından önce, `finish_reason` ile (yoksa `stop`) (1a36dfa) | `test_08t_r1_minor2_*` (eski kodla kırmızı) |
| MINOR-3 araç argümanında JSON kaçışı | değer JSON-escape (tek parça ve canlı) (1850df3) | `test_08t_r1_minor3_*` (`"` içeren değer, JSON ayrışır) |
| MINOR-7 S8 uç nokta + rol | test (6d0d9ba) | `test_08t_m7_owner_sees_values_approver_and_admin_placeholders` (gerçek `resume_run` + `GET /stream`) |
| MINOR-8 dış agent / facade agent olumlu | test (1850df3) | `test_08t_m8_external_agent_echo_reversed_for_the_caller`, `test_08t_m8_facade_agent_events_reversed` |
| MINOR-11 okuma tarafı Redis hatası | `RevealUnavailable` → akış `error` olayı `detokenize_unavailable` ile biter (koşu sürer) (1850df3) | `test_08t_r1_minor11_*` |
| MINOR-12 16 ↔ 15 | docs/api.md 15 (1850df3) | — |

**FOLLOWUP-162'ye ertelenenler (kısıt olarak):** MINOR-4 (politika okuma anında çözülür; koşu sırasında enforce olan kural sonradan monitor'a alınırsa saklanan cevap sahibine açılır), MINOR-5 (açık SSE bağlantısı üyelik/rol değişikliğini görmez; yeniden bağlanmada reddedilir), MINOR-6 (canlı facade akışında sayaç logları iki kez), MINOR-9 (enforce politikada C17 fiilen kapalı; seed hedef projesinde C17 çalışmaz), MINOR-10 (`masks_pii_at` aksiyon/kategoriye bakmaz; yön güvenli), MINOR-13 (106 yanlış negatifleri: `auth_token:`, `DB_TOKEN=` öneki, boşluklu `api key`), MINOR-14 (`search_documents` kaynak numarası çakışması; F11 5b sızıntı iddiası bütün injection satırıyla), NOTE 1-8 (impersonation sahip sayılır; başarılı geri çevirme audit'i yok; `Run.input` ham; 9+ haneli yer tutucu hizalanmaz; tümü engellenen `search_documents` koşuyu düşürür ve bütçe boşluğu doldurulmaz; parça başına egress olay çoğalması; konsol arayüzü `blocked`'ı göstermez; `check_http_destination` userinfo/query/rezerve reddi yapmaz, webhook için 06b-2 kuralları ayrıca gerekir).

**Bilinen sınırlar (yeni):** URL bağlamı son boşluktan beri en çok 8.192 karakter; daha uzun bir URL'nin başı kaybolursa içindeki yer tutucu açılabilir. Sayaç anahtarı 400 gün yaşar (en uzun saklama sınıfının üstü); daha eski saklanan bir yer tutucu kapsamı tekrar açılırsa numara çakışabilir. Facade agent'ın istemci geçmişi satırları artık ham (egress öncesi) metin taşır; kullanıcı mesajları zaten ham saklanıyordu.

## Varsayımlar ve sapmalar

1. **Yazma tarafında hizalama (plandan sapma; K-08T1-0004 kabul):** plan konsol akışında okuma tarafında durumlu tampon öngörüyordu. Uygulanan: model düğümü canlı `token` girdisini yer tutucu ortasında bitirmez (`PlaceholderAligner`), okuyucu girdi başına durumsuz geri çevirir. Neden: okuma tarafı tamponu tutulan kuyruğu ayrı bir SSE mesajıyla, aynı SSE kimliğiyle yollamak zorunda kalırdı; `Last-Event-ID` ile yeniden bağlanan istemci o kuyruğu kaybederdi. Yazma tarafında tutmak kimlik/yeniden oynatma düzenini değiştirmez; Redis'teki metin yine tokenize.
2. **Çıkışta enforce `pii` kuralı varsa geri çevirme yok (plana ek; K-08T1-0004 kabul, `detokenize_skipped_policy` sayaç logu fb7130d):** `output.pre`/`output.stream.delta`'da enforce bir `pii` kuralı varsa, cevap yer tutucularla denetlendiği için değerleri sonradan açmak politikanın gizlediğini gösterirdi (`test_06b_4_stream_output_buffered_then_checked` bunu yakalardı). Güvenli taraf: yer tutucu kalır (`engine.masks_pii_at`). Yerleşik politika monitor olduğu için varsayılan kurulumda geri çevirme çalışır; e2e hedef projesi (enforce) yer tutucu görür.
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
