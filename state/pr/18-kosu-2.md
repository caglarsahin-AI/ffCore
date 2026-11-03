# 18-kosu-2 · kullanım senaryoları tam koşusu (test rolü)

**Durum:** VERIFIED (koşu tamam; ürün kodu değişmedi) · **Paket:** 18-kosu-2 · **GOREV:** K-18K2-0001 (+ K-18K2-0002 06b-2 eki, K-18K2-0003) · **Baz:** main `0c7a100` (e9ad4b5 + 06b-2 merge 614c150 dahil) · **Oturum:** ffcore-test-18-kosu-2 · **Tarih:** 2026-11-03 08:52-09:17

Yığın `ffcore-18k2`, 18260/13260, `--env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test --profile qdrant`, `FFCORE_VERSION=0.0.0-main`. İmajlar: backend 2026-11-03 00:23 (614c150 merge'ünden sonra derlenmiş; içinde `services/external_config.py` doğrulandı), tools 01 Kasım (kodu `/work` bağlamasından okur), frontend 01 Kasım (API e2e'de kullanılmadı). Parolalar yalnız kabukta (scratchpad, depo dışı). Bitince `down -v` exit 0; konteyner 0, volume 0.

Kanıt (tam tee): `state/evidence/18k2-{up,seed,e2e,eval,ttl,facade-base,facade-ext,gate2,down}.log`; F tablosu `eval/results/e2e-20261103-0558.md`; eval raporu `eval/results/eval-20261103-0600.md`; ingest manifestleri `eval/results/18k2-ingest-manifest-{1,2}.json`.

## Süreler

| Adım | Süre | Sonuç |
|---|---|---|
| `up -d --wait` | 74 s | tümü healthy |
| `make seed` #1 | 75 s | created 36, uploaded 15 |
| `make seed` #2 | 48 s | **created 0, uploaded 0** |
| `make e2e` | 82 s pytest (102 s toplam) | **64 passed / 0 failed / 22 NOT_RUN** (31 Ekim tabanı 64/0/22 ile aynı) |
| `make eval MODEL=fake-llm APPROVE_SQL=1` | 37 s | 33/33 koşu `completed`; yalnız hat kanıtı |
| TTL negatif (`-k approval`) | 5 s | 2/2 passed |

## (1-2) F tablosu (main 0c7a100)

| Use case | Status | Passed | Failed | NOT_RUN | NOT_RUN gerekçesi (özet) |
|---|---|---|---|---|---|
| F1 | passed | 2 | 0 | 2 | gerçek model (declined etiketi; sozlesme-33 skoru) |
| F2 | passed | 5 | 0 | 3 | gerçek model (red sonrası cevap; triyaj ≥ %80; PII'li bilet maskesi) |
| F3 | passed | 2 | 0 | 1 | gerçek model (sql-20 ≥ %80) |
| F4 | passed | 4 | 0 | 2 | kota 03c; araca değer geçiren gerçek model |
| F9 | passed | 2 | 0 | 1 | düzeltilmiş cevap → dataset 09 |
| F10 | passed | 4 | 0 | 0 | |
| F11 | passed | 5 | 0 | 7 | gerçek model (5 kanarya); triyaj agent'ı; enjeksiyon tanıyıcısı 08 tam |
| F12 | passed | 2 | 0 | 4 | servis durdurma compose düzeyi koşucu ister (Langfuse, Qdrant, LLM_SLOTS, airgap) |
| F13 | passed | 2 | 0 | 2 | gerçek model (v2 değeri + 01.09.2025) |
| Negative | passed | 14 | 0 | 0 | |
| Setup | passed | 22 | 0 | 0 | |

`known_findings.json` boş (`{}`); hiçbir satır "known" değil.

## (3) `make eval` fake-llm (hat kanıtı, ölçüm değil)

33/33 koşu `completed`; outcome: answered 32, declined 1; judge NOT_RUN; cevap süresi medyan 0,6 s, P95 1,1 s; soru başına LLM çağrısı 0,97. Kalem başı `cites_source=ok`: **19/20** belge sorusu (q18 declined, kaynak yok). Özet satırı ise "Document questions with the right source: **0/20**", "Source accuracy: 0/20". Bu fark bulgu B3 (aşağıda): özet sayısı kaynak isabetini değil `contains` **ve** `cites_source` birlikteliğini sayıyor.

## (4) TTL negatif

`test_13b_neg_approval_1_expired_approval_closes_the_run` PASSED, `test_13b_neg_approval_2_sweep_hook_is_for_the_service_account_only` PASSED (`FFCORE_TEST_HOOKS=1`, e2e.env). Ayrıca tam `make e2e` içinde Negative 14/14.

## (5) 06b facade dumanı

Betik scratchpad'de (`facade_smoke.py`, depo dışı), tools konteynerinden `http://backend:8000`; anahtar 03c-1 konsol ucuyla (`POST /api/v1/projects/{id}/api-keys`, hastane-a-admin-edit oturumu).

**Taban yığın: 26/26 PASS** (`18k2-facade-base.log`)

| # | Kontrol | Beklenen | Ölçülen |
|---|---|---|---|
| 1-3 | anahtar oluştur (chat_direct+agents / agents / chat_direct) | 201 | 201 ×3 |
| 4 | `GET /v1/models` iki kapsam | model + agent | 4 model, 11 agent |
| 5 | kapsam `agents` | yalnız `agent:` | 11, hepsi `agent:` |
| 6 | kapsam `chat_direct` | yalnız model | 4, agent yok |
| 7 | başka projenin (klinik-b) adı | yok | yok |
| 8 | düz model `hastane-a.chat-default` akışsız | 200 + içerik | 200 `hello` |
| 9 | düz model akışlı | chunk + `[DONE]` | 3 chunk, `[DONE]`, `hello` |
| 10 | kısa ad `chat-default` | 200 | 200 |
| 11 | düz model, yalnız `agents` anahtarı | 403 `scope_missing` | 403 `scope_missing` |
| 12 | bilinmeyen alan | 400 `unsupported_field` | 400 `unsupported_field` |
| 13 | `top_p: "0.5"` | 400 `invalid_parameter` | 400 `invalid_parameter` |
| 14 | `temperature: 3` | 400 `invalid_parameter` | 400 `invalid_parameter` |
| 15 | `klinik-b.chat-default` | 404 `model_not_found` | 404 `model_not_found` |
| 16 | egress düz yol: mesajda e-posta | fake-llm `/_requests`'te ham değer yok | 1 istek, ham değer yok |
| 17 | `agent:hastane-a/sozlesme-asistani` akışsız | 200 + `X-Run-Id` | 200, run id var, `hello` |
| 18 | aynı agent akışlı | chunk + `[DONE]` | 6 chunk, `[DONE]`, x_platform `progress`, `sources` |
| 19 | agent, yalnız `chat_direct` anahtarı | 403 `scope_missing` | 403 `scope_missing` |
| 20 | agent bilinmeyen alan | 400 `unsupported_field` | 400 `unsupported_field` |
| 21 | agent `top_p: "x"` | 400 `invalid_parameter` | 400 `invalid_parameter` |
| 22 | egress agent yolu: mesajda e-posta | ham değer yok | 1 istek, ham değer yok |
| 23 | konsol oturumu facade'da | 401 `api_key_required` | 401 `api_key_required` |
| 24 | dış agent kaydı `http://fake-llm:9999/v1` | 422 `external_agent_host_reserved` | aynı |
| 25 | dış agent kaydı `http://ticket-desk:8080/v1` | 422 `external_agent_host_reserved` | aynı |
| 26 | dış agent kaydı `https://agent.example.org/v1` (allowlist boş) | 422 `external_agent_url_refused` | aynı |

**Dış agent uçtan uca: 15/15 PASS** (`18k2-facade-ext.log`). Test yığınında `EGRESS_ALLOWLIST` boş ve her iç host bir platform servisi (reserved), bu yüzden "dış host → 201" taban yığında kurulamaz. Yalnız bu adım için scratchpad'de iki geçici örtü: fake-llm'e ağ takma adı `ext-agent` (compose override) ve `ALLOWED_INTERNAL_HOSTS`'a `ext-agent` (üçüncü `--env-file`). Ürün kodu ve depo dosyası değişmedi; dış ağa bağlantı yok.

| # | Kontrol | Beklenen | Ölçülen |
|---|---|---|---|
| 2 | kayıt `http://ext-agent:9999/v1` (iç, reserved değil) | 201 | 201 |
| 3 | `GET .../external` | `external.api_key = "***"` | `"***"` |
| 4 | yayın öncesi `/v1/models` | yok | yok |
| 5 | yayın öncesi çağrı | (ölçüldü) | **404 `agent_not_published`** (501 değil; docs/api.md:429 ile tutarlı) |
| 6-7 | publish; sonra `/v1/models` | 200; listede | 200; listede |
| 8 | akışsız çağrı | 200 + içerik | 200 `hello` |
| 9 | egress: mesajda e-posta | upstream'de ham değer yok | 1 istek, ham değer yok |
| 10 | akışlı çağrı | tek chunk + `[DONE]` | 3 chunk, `[DONE]`, `hello` |
| 11 | `system` rolü | 400 | 400 `role_not_supported` |
| 12 | `PUT` başka origin, anahtar yok | 200, `api_key: null` | 200, `null` |
| 13 | anahtar sıfırlandıktan sonra çağrı | 501 `external_agent_not_available` | aynı |
| 14 | audit `external_agent_call` | ≥ 2 | 4 (iki betik koşusu birikimli) |
| 15 | audit `reset_external_agent_key` | ≥ 1 | 2 (birikimli) |

İlk ext koşusunda #3 FAIL göründü: betik `api_key`'i kökte arıyordu, alan `external.api_key` altında (`ExternalAgentOut.external`); betik düzeltildi, ürün doğru. İlk koşunun kaydı logda değil, bu not kayıttır.

## (6) Kapı 2 kuru koşusu (`data/samples/paycore-like`, `--limit 10`)

| Koşu | Sonuç |
|---|---|
| `--sources ... jira:PRSIM` | baştan red: `prsim_requires_ner` (beklenen, veritabanına dokunmadan) |
| tools konteyneri, KB `paycore-like-18k2`, #1 | created 4, `status: failed 5`, gates `-`; 4 `.md` `failed` (`model_missing: docling-project/docling-models`), DEMO-7.txt `EgressDenied` → satırı `gated`'da kaldı |
| aynı, #2 | created 0, **unchanged 5**, `status: -`; manifest yine `failed 4, gated 1` |
| backend imajı, KB `...-18k2b` | aynı: `.md` ×4 `model_missing`, DEMO-7 `EgressDenied` |
| backend imajı + `ALLOWED_INTERNAL_HOSTS=backend,...` (yalnız hipotez denetimi), KB `...-18k2c` | DEMO-7 **indexed** (gate0/1/2 ok, 1 chunk); `.md` ×4 yine `model_missing` |

**gate2:code_heavy = 0, gate2:no_prose = 0, n = 1** (Kapı 2'ye yalnız DEMO-7.txt ulaşabildi). `.md` dosyaları Docling'e gidiyor ve test yığınında Docling ağırlığı yok (ağırlık indirmek kullanıcının işi). **FOLLOWUP-145 için anlamlı veri bu yığından çıkmaz:** 7 dosyalık sentetik ağaç zaten küçük; sayı M3 aşama 0 raporundan (sunucu, gerçek korpus, ağırlıklar yüklü) alınmalı.

## Bulgular (kayıt talebi; ürün kodu değişmedi)

- **B1 (MAJOR adayı, 19, M3 ingest):** `ingest-raw` backend imajında koşunca `HttpEmbedClient` `POST http://backend:8000/internal/embed`'i `SafeOutboundClient` ile çağırıyor; backend servisinin `ALLOWED_INTERNAL_HOSTS`'unda `backend` yok (yalnız worker/agent-worker ortamları `backend,...` ekliyor, deploy/docker-compose.yml:334, :394). Sonuç: kapıları geçen her belge `EgressDenied` ile düşüyor. `backend` eklenince aynı dosya `indexed` (18k2c). Entegrasyon testi `test_19_ingest_raw.py` `LocalEmbedClient` enjekte ettiği için (satır 56, 238, 307) yol testte hiç koşmamış. Sunucuda PayCore compose'u `&app-env`'i birebir kopyalıyorsa (state/pr/19.md) aynı hata orada da olur; doğrulanmadı.
- **B2 (MAJOR adayı, 19 ve 04a):** `raw_ingest.py:252` aynı sha256'lı dosyayı statüsüne bakmadan `unchanged` sayıyor. Hata veren belge (`failed`, ya da istisna sonrası `gated`'da kalan) sonraki koşuda yeniden denenmiyor: `make models` ya da ortam düzeltmesinden sonra ikinci koşu `created 0, unchanged 5` ve konsolda `status: -` diyor, operatör temiz sanıyor (gerçek durum yalnız manifestte: `failed 4, gated 1`). Ayrıca istisnada belge satırı ara statüde (`gated`) kalıyor, `failed`'a çekilmiyor; konsol `failed 5` sayarken DB'de 4 failed + 1 gated var. Fail-loud açığı.
- **B3 (MINOR, M3 raporlama, 13b/19 `scripts/eval_report.py`):** "Document questions with the right source" ve "Source accuracy" `passed()` sayıyor (`contains` **ve** `cites_source`); fake-llm'de 0/20, kalem başı `cites_source=ok` 19/20. S1 kabulü (PayCore tabanıyla "kaynak isabeti" karşılaştırması) bu satırdan okunursa cevap doğruluğu ile kaynak isabeti karışır (ARCH-13). Öneri: `cites_source` sayısı ayrı satır ve "Source accuracy" yalnız onu saysın; ya da etiket "right answer and source" olsun. Kullanıcının S1 koşusundan önce.
- **N1 (not):** GOREV kalem 5 "publish'siz çağrı 501": ölçülen 404 `agent_not_published`; 501 yalnız anahtarı sıfırlanmış yayınlı dış agent'ta. Docs bu davranışı yazıyor; ürün hatası değil.

## plan/18 Durum sütunu önerisi

F1, F2, F3, F4, F9, F10, F11, F12, F13: "PoC hat kanıtı yeşil, 18-kosu-2 (main 0c7a100, 3 Kasım): F tablosu 64/0/22, NOT_RUN gerekçeli; gerçek model sütunu kullanıcı koşusunda". F5-F8 değişmez (planlı). Ek satır yok; 06b facade (F4'ün "yönetilen LLM geçidi" dış yüzü) için "facade dumanı 26/26 + dış agent 15/15 (18-kosu-2)" F4 kanıt sütununa eklenebilir.

## NOT_RUN

- Gerçek model (llmaas/airgap), judge: GOREV sınırı.
- Kapı 2 `.md`/Docling yolu: ağırlık yok (kullanıcı).
- Konsol Playwright e2e (`--profile e2e`): GOREV dışı.
- Entegrasyon testleri: e2e yığınında koşulmadı (FOLLOWUP-118).
- airgap profili: sunucu koşusu kullanıcıda.
