# fake-llm tool-* modu · review r1

**Dal:** fix/fake-llm-tool-mode · **Tam SHA:** cab06f1299e08750b5e739814c04d867b37b4749 (1 commit, 3 dosya) · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 0.

## Kapsam ve okuma

- `backend/tests/fakes/fake_openai.py`: yalnız `tool-*` dalı eklendi; `fail-*`, `empty-*`, `slow-*` ve varsayılan `hello` yolu değişmedi. `tool-*` istekte `tools` yoksa "hello", varsa ilk aracı tek çağrıyla verir (zorunlu argümanlar örnek değerlerle), son mesaj araç sonucuysa "hello " + sonucun ilk 50 karakteri.
- `backend/tests/unit/test_fake_openai_tool_mode.py`: 5 yeni test.
- `docs/gelistirme-ortami.md`: `tool-*` ve `tool-default` model kaydı notu. Metin C1 ile uyumlu: LiteLLM yapılandırmasında model listesi yok, model kaydı uzlaştırıcıyla DB'ye yazılır. Koordinatörün sorduğu "LiteLLM config yerine DB modeli" sapması C1'e uyuyor.
- Dosya dışında değişiklik yok; fake yalnız test profilinde (`tests/fakes`) kullanılıyor.

## Komutlar

| Komut | Ortam | Sonuç |
|---|---|---|
| `ruff check` ve `ruff format --check` (2 Python dosyası) | `ffcore/tools:0.0.0-review-06a`, worktree `/work` | temiz |
| `pytest tests/unit/test_fake_openai_tool_mode.py` | `DEPLOY_PROFILE=llmaas` | 5 passed |
| `pytest test_01_reconcile_params.py test_02_pricing.py test_fake_openai_tool_mode.py` | aynı | 24 passed |

Görev tanımında kapı yığınsız kısa tur istendi; yığın açılmadı. Tools imajı 06a etiketli; testlerin bağımlılıkları bu imajda mevcut. `airgap` profili bu kısa turda koşulmadı (dosyalar profil dalı içermiyor).

## Kalan riskler

- `tool-*` modu bu incelemede yalnız birim düzeyinde kanıtlandı; LiteLLM üzerinden uçtan uca doğrulama F3/F4/F11 ve 10b-poc-2 testlerinde yapılacak.
