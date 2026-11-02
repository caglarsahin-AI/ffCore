# [B] fix(06a): every model message passes egress at the llm_call boundary (BLOCKERS 134)

**Paket:** fix/06a-egress-all-messages · **Sınıf:** [B] (güvenlik/guardrail, incelemeli) · **Branch:** fix/06a-egress-all-messages · **Baz:** 07dc421 · **HEAD:** 10e86bf0d54215e2783ed304e6af712798666858 (3 commit; r1 DUZELT K-134-0003) · GOREV K-134-0001 · **06b merge'ünden önce**

## Sorun
`egress` yalnız `guard_in`de ilk kullanıcı mesajına uygulanıyordu; geçmiş, araç sonuçları (run_sql satırları, `search_documents` parçaları) ve sistem prompt'u sağlayıcıya ham gidiyordu.

## Çözüm (tek kontrol noktası)
`graph._egress_messages(ctx, messages)`: `model` düğümünde `ctx.model.call`dan hemen önce, listedeki her `content` (system, geçmiş, user, assistant, tool) `guard.check("egress")`.
- **(a)** Aynı run token_store (EngineGuard); egress iki kez = aynı metin, verilmiş `<<PII_n>>` yeniden eşleşmez (birim: sahte guard; entegrasyon: gerçek motor + Redis).
- **(b)** `RunContext.egress_cache` (additive alan): mesaj hash → maskeli metin; aynı run içinde aynı metin yeniden denetlenmez.
- **(c) Tek kural:** `block` → `StopRun(failed, "guardrail_block")` (guard_in ile aynı); araç sonucu dahil tüm mesajlarda; sessiz atlama/kırpma yok. (`tool.post` bloğu BLOCKED_TOOL_TEXT ile modele giden metni zaten değiştirir; egress bloğu ise run'ı düşürür.)
- **(d)** `llm_call.request_messages` = modele giden maskeli liste.
- Airgap: `EngineGuard` egress'i kapalıyken `allow` döner → ek `if profile` yok; liste değişmeden gider.
- Detokenize: davranış değişmedi; cevap `guard_out`/finalize yolunda eskisi gibi geri açılır. Entegrasyon testi, tokenize edilen e-posta/telefonun `detokenize` ile geri geldiğini kanıtlar.
- assistant `tool_calls[].function.arguments` da aynı sınırda: JSON çözülür, her string değer egress'ten geçer, yeniden `json.dumps` (yapı bozulmaz). (Default politikada `tool.pre` PII kuralı monitor; bu yüzden tool_guard'a güvenilmez.)
- `guard_in` sonucu `egress_cache`e yazılır; model düğümü ilk kullanıcı mesajını ikinci kez denetlemez (monitor kuralında çift olay yok). Önbellek hem ham hem maskeli metnin hash'ini tutar.
- Yeni kodlar (C9 additive, docs/agentlar.md): `unsupported_message_content` (content str değil / argüman JSON değil), `guardrail_text_too_long` (`TextTooLong`).
- `block` = run `failed` yalnız `enforce` politikada geçerli; default politika monitor olduğu için `secrets` egress'te kaydeder, engellemez (08'in mevcut anlamı, bu PR değiştirmez).
- **06b ile çift maske yok:** 06b facade S3 geçmiş denetimi ayrı kalır; token_store aynı run kapsamlı olduğu için ikisinin üst üste gelmesi aynı metni üretir (idempotent). 06b S3'e dokunulmadı.

## Değişen dosyalar
backend/ffcore/runtime/graph.py, backend/ffcore/runtime/state.py, docs/agentlar.md, backend/tests/unit/test_134_egress_all_messages.py (yeni), backend/tests/integration/test_134_egress_real_engine.py (yeni), backend/tests/integration/test_134_provider_request.py (yeni)

## Kabul → test
| Kriter | Test | Durum |
|---|---|---|
| Tüm mesajlar maskeli gider, request_messages maskeli | unit `test_134_all_messages_masked_before_model_call` | geçti (kırmızı: eski kodda düştü) |
| İdempotent + önbellek + taze önbellekte aynı metin | unit `test_134_idempotent_and_cached_per_run` | geçti |
| block = run failed/guardrail_block, model çağrılmaz | unit `test_134_block_fails_run_loud` (kırmızı eski kodda) | geçti |
| tool_calls.arguments maskeli, JSON geçerli | unit `test_134_tool_call_arguments_masked_and_stay_json` | geçti (kırmızı önce) |
| guard_in + model: mesaj başına 1 egress | unit `test_134_guard_in_result_is_not_checked_again_by_the_model_node` | geçti (kırmızı önce) |
| str olmayan content / TextTooLong kodlu hata | unit `test_134_non_text_content_fails_loud`, `test_134_text_too_long_has_its_own_code` | geçti (kırmızı önce) |
| Airgap: egress kapalı, değişmeden | unit `test_134_airgap_egress_off_sends_unchanged`; entegr. `test_134_airgap_has_no_egress_stage` | unit geçti; entegr. **koşulmadı** |
| Gerçek motor/Redis: her mesaj tokenize, iki kez aynı, detokenize geri açar | entegr. `test_134_llmaas_every_message_tokenized_and_idempotent` | **koşulmadı** (yığın gerekir) |

## Çalıştırılan komutlar (yığın `ffcore-134`, 18180/13180, `0.0.0-134`, `--profile test` + qdrant)
`MSYS_NO_PATHCONV=1 FFCORE_VERSION=0.0.0-134 docker compose -p ffcore-134 --env-file .env.test --profile tools run --rm -T tools ...`. Loglar `state/evidence/134-*-20261102.log`.
| Komut | Ortam | Sonuç |
|---|---|---|
| hedefli entegrasyon: egress_real_engine + 06a_graph + 06a_adapters | llmaas | 32 passed (`134-int-targeted`) |
| `test_134_provider_request.py` (gerçek graph model düğümü + EngineGuard + LiteLLM + fake-llm `/_requests`) | llmaas / egress kapalı | 2 passed (`134-int-provider`); eski graph.py ile llmaas testi **kırmızı** (`134-red-provider`) |
| `make lint test` | `DEPLOY_PROFILE=llmaas` | 745 passed (`134-gate-llmaas`) |
| `make lint test` | `DEPLOY_PROFILE=airgap` | 745 passed (`134-gate-airgap`) |
| `make test-int` (tam, qdrant ile) | llmaas yığını | 682 passed, 4 skipped (`134-test-int`) |
| `down -v` | | konteyner 0, volume 0 (`134-down`) |

(e)/(f): sağlayıcı isteğinde sistem prompt'u e-postası, geçmiş e-posta, araç sonucu telefonu ve araç argümanı yok; `detokenize` geri açar; airgap'te egress aşaması yok, metin olduğu gibi gider (profil farkı yapılandırma değeri). Tam kalıcı konuşma + gerçek `run_sql` run'ı yerine aynı `model` düğümü gerçek sağlayıcı yoluyla koşuldu: kapsam sınırı.
Not: `make test-int` yalnız llmaas yığınında koşuldu; airgap profili için test-int koşulmadı (egress kapalı davranışı birim ve yukarıdaki iki entegrasyon testiyle kanıtlı). Host Windows koşusundaki 8 ortam hatası docker kapılarında yok (745 passed).

## Felsefe (3 soru)
1. Kök neden tek sınırda çözülüyor; kanal başına yama yok. 2. Sessiz düşüş yok, block run'ı düşürür. 3. Platformun token_store'u yeniden kullanıldı, yeni mekanizma yok.
