# PR fake-llm-tool-mode

**Paket:** fake-llm-tool-mode (18 / 10b-poc-2 ortak) · **Sınıf:** [A] (yalnız test aracı) · **Branch:** fix/fake-llm-tool-mode · **Baz:** main 8622714 · **SHA:** cab06f1299e08750b5e739814c04d867b37b4749
GOREV K-SEN-0025. Durum: PR-HAZIR.

## Değişiklik

- `backend/tests/fakes/fake_openai.py` (additive): upstream model kimliği `tool-*` iken
  - istekte `tools` var → ilk aracın tek çağrısı (`finish_reason: tool_calls`), zorunlu argümanlar örnek değerle (`TOOL_SAMPLES`: `ticket_id=tkt-001`, `body`, `sql`, `reason`, `query`; diğerleri tipe göre); akışta `delta.tool_calls[0]` + `finish_reason: tool_calls` + usage;
  - son mesaj `role=tool` → `"hello " + sonucun ilk 50 karakteri`;
  - `tools` yok → `"hello"`.
  Diğer kimlikler (`fail-*`, `empty-*`, `slow-*`, varsayılan) değişmedi; stdlib-only kaldı.
- `backend/tests/unit/test_fake_openai_tool_mode.py` (yeni, 5 test).
- `docs/gelistirme-ortami.md`: fake-llm davranış paragrafı.

## Sapma (kabul K-SEN-0025 cevabı)

LiteLLM yapılandırmasına `tool-default` eklenmedi: `deploy/litellm/config.yaml`'da model listesi yok (`store_model_in_db`, C1); modeller proje model kayıtlarından uzlaştırıcıyla yazılır. Araç çağıran sahte model = upstream `model_id: tool-default` olan bir proje modeli (18 e2e seed'i `chat-tools`; 10b-poc-2 aynı yol).

## Kabul → test

| Kriter | Test | Durum |
|---|---|---|
| tools varken ilk aracın tek çağrısı, yalnız zorunlu argümanlar | `test_fake_tool_mode_calls_first_tool_once` | kırmızı → geçti |
| akışta tool_call | `test_fake_tool_mode_streams_the_tool_call` | kırmızı → geçti |
| araç sonucundan sonra metin (tek cevap + akış) | `test_fake_tool_mode_answers_after_the_tool_result` | kırmızı → geçti |
| tools yokken metin | `test_fake_tool_mode_without_tools_is_text` | geçti (baştan) |
| chat modelleri değişmedi | `test_fake_chat_models_unchanged_with_tools` | geçti (baştan) |

## Kapılar (tools 0.0.0-fakellm, `--no-deps`, servis yok)

| Komut | Sonuç |
|---|---|
| `make lint` | 0; 290 dosya biçimli |
| `make test` `DEPLOY_PROFILE=airgap` | 644 passed |
| `make test` `DEPLOY_PROFILE=llmaas` | ilk koşu 1 failed (`test_04a_9d_timeout_kills_worker_and_continues`, FOLLOWUP-97, bu dalın dışında); tekrar 644 passed |

01 entegrasyon testleri (fake-llm konteyneri) yığın gerektirir: NOT_RUN; değişiklik additive, mevcut kimlikler birim testinde değişmedi olarak kanıtlı.
