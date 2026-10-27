# 02. Langfuse izleme [FFCore Trace]

**Bağımlılık:** 00, 01. **Süre:** 1 gün. **Dalga:** 3. **PoC:** evet.

## Amaç

Her LLM çağrısı, agent koşusu ve araç çağrısı Langfuse'ta görünsün; maliyet hesaplansın; prompt'lar Langfuse'ta sürümlensin.

## Kapsam

1. Langfuse ilk kurulum otomasyonu: Langfuse'un headless init env değişkenleri (`LANGFUSE_INIT_*`, pinli v3 sürümünde doğrulanır, U2) ile organizasyon, proje ve API anahtar çifti oluşur. `deploy/langfuse/init.sh` `.env`'e **yazmaz** (SECURITY: agent ve script `.env` yazmaz, B6): anahtar çiftini bir kez ekrana basar, kullanıcı `.env`'e kendisi yazar; `make smoke` anahtar eksikse açık hata verir.
2. LiteLLM callback'i bu anahtarlarla bağlanır (01'deki config'in boş bıraktığı alanlar).
3. `backend/app/core/tracing.py`: Langfuse Python SDK ile `@observe` yardımcıları ve LangGraph için `CallbackHandler` üreten fonksiyon. Her run için `session_id = run_id`, `user_id`, `metadata.project_id`, `tags = [agent_key, agent_version]`.
4. (R10.6) Fiyat tek kaynak: `models.pricing` (03a) → `render-litellm` ile LiteLLM `input_cost_per_token`/`output_cost_per_token`; maliyet LiteLLM callback'inden Langfuse'a gelir. Langfuse'ta ayrı fiyat tablosu ve `LOCAL_MODEL_PRICE_PER_1K` yoktur; yerel modelin sanal fiyatı da `models.pricing`'de tutulur.
5. Prompt yönetimi: `backend/app/core/prompts.py`, Langfuse prompt API'sinden adla ve etiketle (`production`) prompt çeker, 60 s önbellek. Yerel `backend/prompts/*.md` yalnızca **ilk seed**'dir (`make seed-prompts` Langfuse'a yükler); çalışırken Langfuse erişilemezse son başarılı önbellek kullanılır, `prompt_cache_stale` olayı ve `service_down` uyarısı üretilir; önbellek de yoksa açık hata (sessiz yerel yedek yok, C13).
6. `docs/izleme.md`: Langfuse'ta bir run nasıl bulunur, maliyet raporu nasıl alınır.

7. İz ve oturum modeli alanları (`runs.model_ms`, `slowest_step`, `guardrail_hook` olayı, olay detayı, `system_prompt` parçaları, Agent sayfası özeti) **06a'nın Kapsam'ındadır** (karar B1: tablo sahibi doldurur); bu paket yalnızca `tracing.py`'de `session_id`, `user_id`, `metadata`, `tags` sözleşmesini ve Langfuse'a gönderim yardımcılarını sağlar.

## Teslimatlar

- `init.sh`, güncellenmiş compose ve `.env.example`.
- `tracing.py`, `prompts.py`, testleri.

## Kabul kriterleri

- LiteLLM üzerinden atılan istek 30 s içinde Langfuse'ta görünür (API ile doğrulama: `GET /api/public/traces`), token ve maliyet dolu; maliyet `models.pricing` ile hesaplanmış değere eşit.
- `tracing.py` ile sarılmış örnek bir fonksiyon çağrısı, LLM çağrısını alt span olarak içeren bir trace üretir.
- Langfuse kapalıyken backend çalışmaya devam eder (trace kaybolur, hata vermez).

## Teknik notlar

- Langfuse v3; ClickHouse ister, 00'da kurulu. PayCore'daki v2 kurulumu gönderilmiş iz içermediği için (CLAUDE.md "config var, gönderen kod yok") v3 ile değiştirilir, veri göçü yok (00i compose). LiteLLM callback'inin v3 ile uyumu pinli sürümde doğrulanır.
- Langfuse OTel endpoint'i de açık bırakılır; 06'daki LangGraph runtime isterse OTel ile de gönderebilir.
- PII: Langfuse'a giden içerik 08'deki maskelemeden sonra gider; 08 bitmeden önce geliştirme verisi sentetik olmalı.

## Kapsam dışı

Evaluation (09) Langfuse datasets/experiments üzerine kurulur (DECISION-4 kapandı, karar A5); bu paket yalnızca trace, maliyet ve prompt yönetimi verir, dataset API'si 09'un işidir.
