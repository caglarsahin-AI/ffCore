# Test Stratejisi

## Piramit

1. **Unit:** doğrulayıcılar (sqlglot, Pydantic şemaları, Kapı 0-2), bağlam bütçesi, ad uzayı çözümleme, guardrail kuralları, hata yolları.
2. **Sözleşme:** CONTRACTS.md'deki donmuş ID'ler `tests/contract/` altında; imza, enum, event adı, `schema_version` geriye uyumluluğu.
3. **Profil matrisi:** aynı test `DEPLOY_PROFILE=llmaas` ve `airgap` ile (pytest parametresi); `INFERENCE_BACKEND` ve `VECTOR_BACKEND` için işaretli testler (`-m vectorstore`).
4. **Entegrasyon:** compose ayakta; gerçek Postgres+pgvector, Redis, Qdrant konteyneri (04b), sahte MCP sunucusu, sahte Confluence/Jira/SharePoint (16). Model çağrıları varsayılan `FAKE_LLM=1` (deterministik sahte LiteLLM); gerçek Ollama yalnızca işaretli testlerde (`-m ollama`).
5. **Uçtan uca:** `make smoke`; M3 sonrası 13'ün 35 soruluk sınavı (`make eval`) ve CPU/GPU/llmaas ölçümleri.
6. **Önyüz:** Vitest bileşen testleri; Playwright akışları ve iki temada ekran görüntüsü karşılaştırması.
7. **NFR:** CPU'da süre sınırları (brief'teki ölçülebilir değerler), bellek üst sınırı, SSE keepalive, kuyruk bekleme.

## Zorunlu eksenler (pakete uygulanabildiği ölçüde)

- Fail-loud: sessiz fallback, kırpma, atlama yok; her reddin gerekçesi kayıtta.
- Idempotent yeniden çalışma: aynı dosya sha256 ile ikinci yükleme, senkron delta, run `resume`.
- ACL ve on-behalf-of: analyst admin belgesini göremez; yanlış JWT yok sayılır.
- Salt-okunur mod: her mutasyon ucunda 403.
- Audit: her mutasyon tek audit olayı üretir.
- Secret maskeleme: log, API, audit, hata gövdesi.
- İki profil: egress izin listesi (`llmaas`), `OFFLINE=true` (`airgap`).
- Türkçe: `tr.json` dışında sabit metin yok (lint kuralı); Türkçe NER ve normalizer testleri gerçek örneklerle.
- Tema: her ekran iki temada.
- Zaman aşımı: CPU 600 s, llmaas 60 s, gpu 120 s ayarları testte sahte saatle.

## Adlandırma

Brief'teki kabul kriterleri sırayla numaralanır. Test adı `test_<paket>_<n>_<slug>`; örnek `test_05a_2_run_sql_delete_rejected`. PR'daki kabul kriteri → test tablosu bu adı kullanır. Sözleşme testleri `test_c<ID>_<slug>`.

## Gerçekçilik

Sürücü ya da dış sistem davranışı kritikse mock yetmez: pgvector HNSW ve BM25, Qdrant filtreleri, LangGraph checkpoint'ten devam, LiteLLM DB model API'si, MCP streamable HTTP, SSE kesilmesi (`abandoned`), Ollama `OLLAMA_CONTEXT_LENGTH` doğrulaması, Docling dönüşümü gerçek konteyner ya da süreçle test edilir. Mock yalnızca modelin ürettiği metin için (`FAKE_LLM`).

## Model kalitesi

Model çıktısına bağlı davranış (araç seçimi, atıf, `declined`) unit testte sahte modelle deterministik; gerçek kalite 09'un sınav setiyle ölçülür ve M3'te karar verilir. Sınav sonucu test değil ölçümdür; CI'ı kırmaz, raporlanır.

## Kanıt

PR açıklamasında: komut, exit code, süre, ortam (`DEPLOY_PROFILE`, `FAKE_LLM`, `VECTOR_BACKEND`), atlanan ve `NOT_RUN` testler, post-state (tablo sayıları, oluşan dosyalar). Çıktı dökümü secret ve kurum verisi içermez.
