# 12. Kurulum rehberi (llmaas ana, airgap ek), paketleme, egress ve donanım [FFCore Platform]

**Bağımlılık:** tüm paketler. **Süre:** 4 gün (inceleme v4-v6: iki rehber, egress proxy, geri yükleme provası). **Dalga:** PoC sonrası. **PoC:** hayır.

## Amaç

Kurulumun tekrarlanabilir olması, iki profilde (N24): `llmaas` (birincil) için egress izin listesi, sağlayıcı anahtarı yönetimi ve veri işleme belgesi; `airgap` için tüm imajlar, Python ve Node bağımlılıkları, model dosyaları ve Presidio/Türkçe NER modelleri iç registry ve aynadan çekilir ya da paket olarak taşınır; kurulum tek rehberle yapılır.

## Kapsam

1. **İmaj listesi:** `deploy/offline/images.txt` (postgres-pgvector, redis, ollama, litellm, langfuse ve bağımlıları: clickhouse, minio, langfuse-worker; backend (Docling kütüphane olarak içinde; R10.7: ayrı docling imajı yok, Docling'in layout ve OCR modelleri ile Türkçe NER ve reranker modelleri build sırasında imaja gömülür, çalışırken HF indirmesi yapılmaz); frontend; mcp-sql; mcp-search). Sürümler sabit (`:latest` yok). Langfuse `profiles: [observability]` ile isteğe bağlı: `llmaas`'ta açık, küçük `airgap` kurulumunda kapatılabilir (trace yalnızca `run_events`'te kalır). Langfuse her iki profilde zorunludur, isteğe bağlı değildir (N25; mimari karar: her çağrı izlenir).
2. **İç registry akışı:** `deploy/offline/mirror.sh`: geliştirme makinesinde imajları çeker, `REGISTRY_PREFIX` ile etiketler, iç registry'ye push eder. Compose tüm imajları `${REGISTRY_PREFIX}` ile referanslar (00'da kuruldu).
3. **Python bağımlılıkları:** backend ve MCP servisleri `uv` ile kilitli (`uv.lock`); imaj build'i iç PyPI aynası `PIP_INDEX_URL` ile. Ayna yoksa `deploy/offline/wheels.sh` ile wheel paketleri toplanıp imaja gömülür.
4. **Node bağımlılıkları:** `package-lock.json`; `npm ci` iç npm aynası `NPM_CONFIG_REGISTRY` ile; build çok aşamalı Dockerfile'da, üretim imajında yalnızca çıktı.
5. **Model dosyaları:** Ollama modelleri (Qwen 3.5 35B, embedding) sunucuda zaten varsa volume bağlanır; yoksa `ollama pull` geliştirme makinesinde yapılıp `~/.ollama/models` dizini kopyalanır. spaCy, Presidio ve reranker modelleri imaja gömülür ya da `data/models/` volume'u.
5b. **Donanım boyutlandırma rehberi** `docs/donanim.md` (PayCore düzeltmesi D8): CPU kurulumu alt sınırı ve beklenen süreler (D6 ölçümleri: prefill ~112 tok/s, üretim ~11 tok/s, RAG cevabı 84-114 sn, `mode: tool` turu ~3 dk; `OLLAMA_NUM_PARALLEL=1` ile 10 kullanıcı sıraya girer); GPU temel yapılandırma örneği: 1× 96 GB sınıfı GPU (ör. RTX PRO 6000 Blackwell) ile 35B-A3B FP8 (~35 GB) + küçük yönlendirme modeli + bge-m3 + reranker ≈ 45 GB, kalan bellek bağlam (KV) için, 10 eşzamanlı kullanıcı; kod modeli ya da büyük agent modeli eklenecekse 2-4 GPU, kasa baştan 4 GPU'ya hazır; sanallaştırmada GPU doğrudan geçişi (passthrough), vGPU yıllık lisans ister. **Bellek bütçesi tablosu** CPU ve GPU için ayrı: model + bağlam (`OLLAMA_CONTEXT_LENGTH` her yüklü model için baştan ayrılır) + embedding + reranker + Postgres/Qdrant + Langfuse (ClickHouse dahil) + ingest işçi süreçleri (her biri kendi Docling kopyası) + OS; konteyner `mem_limit` değerleri ölçülerek verilir (PayCore'da Ollama 36 GB sınırı swap'a düştü). Disk: raw + silver + gold + Ollama modelleri + Langfuse. CPU = PoC ve küçük kurulum, GPU = üretim (PLAN.md 2b). Satın alma kararı müşterinindir; rehber örnek verir.
5c. **vLLM sunum yolu** (PayCore düzeltmesi D8): `INFERENCE_BACKEND=vllm` ile compose `profiles: [vllm]` servisi; model dosyaları kapalı ağa Ollama ile aynı yöntemle taşınır; 01'deki LiteLLM yönlendirmesi; embedding ve reranker için ayrı GPU servisi (TEI ya da vLLM embedding) örneği. Rehberde 10 eşzamanlı RAG sorusunun P50/P95 süresi ölçülüp yazılır.
5d. **Ana kurulum rehberi** `docs/kurulum.md` (`llmaas`, varsayılan): ön koşullar, `.env` (`DEPLOY_PROFILE=llmaas`), sağlayıcı kaydı UI'dan ve anahtar rotasyonu, egress izin listesi kurulumu, `docs/veri-isleme.md` doldurma, ilk `docker compose up`, Langfuse init, ilk admin, sağlık kontrolü, yedekleme, güncelleme, geri alma. Kapalı ağ rehberi bunun üstüne imaj/wheel/model taşıma ve Ollama ayarlarını ekler.
6. **Kapalı ağ ek rehberi** `docs/kurulum-kapali-ag.md` (`airgap`): ön koşullar (Docker, Compose, disk, RAM; `docs/donanim.md`'ye bağlantı), `.env` doldurma (`OLLAMA_CONTEXT_LENGTH`, `OLLAMA_KEEP_ALIVE`, `mem_limit` değerleri zorunlu açıklamalı), ısınma (`make warmup`) ve `/readyz` beklemesi, ilk `docker compose up`, Langfuse init, ilk admin kullanıcı (`make create-admin`), sağlık kontrolü, yedekleme (Postgres dump + `data/storage` + Ollama modelleri), güncelleme adımları, geri alma.
7. **Yedekleme scripti:** `deploy/backup.sh` (pg_dump tüm DB'ler, storage tar), `deploy/restore.sh`.
8. **Güvenlik sıkılaştırma:** Compose'da yalnızca frontend ve backend portları dışa açık; Postgres, Redis, LiteLLM, Langfuse iç ağda; LiteLLM master key ve Langfuse admin yalnızca iç ağ; TLS için ters proxy (Caddy ya da nginx) örneği.

## Profil farkları (PLAN.md 2b)

`llmaas` profili için ek teslimatlar:

- `deploy/egress/` (C16): `llmaas` profilinde Compose'a hafif bir **forward proxy** (`egress-proxy`, Squid ya da dengi) eklenir; backend ve LiteLLM dışarıya yalnızca bu proxy'den çıkar ve alan adı izin listesi (`EGRESS_ALLOWLIST`: `api.anthropic.com`, `*.openai.azure.com`, etkin kanal/kaynak adresleri `slack.com`, `*.botframework.com`, `*.atlassian.net`, `graph.microsoft.com`) **proxy'de** uygulanır; nftables/iptables yalnızca "proxy dışından çıkış yok" kuralı için (L3/L4 joker alan adı filtreleyemez). Uygulama içi ikinci katman `core/egress.py` (03b, C5). Kurumsal güvenlik duvarı için liste de üretilir.
- `docs/veri-isleme.md` şablonu: sağlayıcıya giden veri türleri (soru, maskeli parçalar, araç sonuçları), gitmeyenler (belge dosyaları, indeks, hasta verisi), saklama süresi (sıfır saklama sözleşmesi referansı), bölge, sorumlu kişi, maskeleme kanıtı (`guardrail_events` raporu). Hukuk ve bilgi güvenliği onayı için hazırlanır. Teams için dışarıdan içeriye tek yol: ters proxy'de yalnızca `/channels/teams/messages` yolu açılır, başka hiçbir yol dışarıya yayınlanmaz (C16).
- Sağlayıcı anahtarı döndürme (rotation) adımı kurulum rehberinde.
- (Ana rehber `docs/kurulum.md` zaten `llmaas` içindir; bkz. 5d.)

## Teslimatlar

- `deploy/offline/` scriptleri ve listeler; `docs/kurulum.md` (ana) ve `docs/kurulum-kapali-ag.md` (ek); `deploy/egress/`; `docs/veri-isleme.md`; yedekleme scriptleri; ters proxy örneği (LiteLLM ve Langfuse dışa kapalı, yalnızca backend ve frontend).

## Kabul kriterleri

- Dış ağı kapatılmış bir test VM'inde (iç registry erişimi var) rehber takip edilerek kurulum 1 saat içinde tamamlanır ve 13'teki duman testi geçer.
- `docker compose config` çıktısında `REGISTRY_PREFIX` dışında imaj kaynağı yoktur.
- Yedek alınıp temiz kuruluma geri yüklendiğinde agent'lar, belgeler ve run geçmişi aynen gelir.

## Teknik notlar

- Docling ve reranker imajları büyük (GB düzeyi); registry disk planına yazılır.
- Qwen CPU'da ilk yanıt süresi uzun; rehberde beklenen gecikme ve `OLLAMA_NUM_THREAD` ayarı yazılır. (PayCore düzeltmesi D6, D8) Referans: PayCore `compose.yml` (ollama servisi ortam değişkenleri ve yorumları), CLAUDE.md "Donanım" ve "Bellek bütçesi (64 GB)" tablosu.
- Kabul: `INFERENCE_BACKEND=vllm` ile aynı `docker compose` sanal model adını vLLM'e yönlendirir, uygulama kodu değişmez; `make smoke` `OLLAMA_CONTEXT_LENGTH`'in set olduğunu doğrular; GPU ölçümü (10 eşzamanlı RAG sorusunun P50/P95'i) yalnızca GPU donanımı mevcutsa yapılır, yoksa `NOT_RUN (PENDING_ENV)` olarak işaretlenir (C22); paket bununla VERIFIED olabilir.

## Kapsam dışı

Kubernetes, yüksek erişilebilirlik, çoklu sunucu.
