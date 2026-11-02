# [B] fix(06a): every model message passes egress at the llm_call boundary (BLOCKERS 134)

**Paket:** fix/06a-egress-all-messages · **Sınıf:** [B] (güvenlik/guardrail, incelemeli) · **Branch:** fix/06a-egress-all-messages · **Baz:** 07dc421 · **HEAD:** 3d03bc98ad5517ad9da293415e312edada618285 (2 commit; r1 DUZELT K-134-0003) · GOREV K-134-0001 · **06b merge'ünden önce**

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
backend/ffcore/runtime/graph.py, backend/ffcore/runtime/state.py, docs/agentlar.md, backend/tests/unit/test_134_egress_all_messages.py (yeni), backend/tests/integration/test_134_egress_real_engine.py (yeni)

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

## Koşulmayanlar / açık
- **Koşulmadı (Docker Desktop kapalı, 2 Kasım):** iki entegrasyon testi (Postgres+Redis) ve K-134-0001 (e) tam senaryo (kalıcı konuşma 2. tur + run_sql satırı → fake-llm `/_requests`, F4 deseni) ve (f) F4 senaryo genişletmesi: YIGIN-AÇ gerekir; koordinatör onayıyla ayrı turda. Bu PR şimdilik "yığınsız yeşil".
- Host (Windows) `pytest tests/unit tests/contract`: 730 passed, 8 failed; hepsi ortam (asyncio proactor/subprocess/kaynak limiti) ve dokunmadığım dosyalar (test_02_tracing, 04a_convert, 04a_review_r1_*, 05a_unverified_claims, 06a_no_langsmith, 08_cost). Resmi kapı docker `tools` imajıyla `make test` iki profil: **koşulmadı** (imaj derlemesi disk ister, C: 24 GB).
- `make lint` eşdeğeri: `uv run ruff check .` + `ruff format` temiz (backend).

## Felsefe (3 soru)
1. Kök neden tek sınırda çözülüyor; kanal başına yama yok. 2. Sessiz düşüş yok, block run'ı düşürür. 3. Platformun token_store'u yeniden kullanıldı, yeni mekanizma yok.
