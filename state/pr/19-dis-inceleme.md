# fix/19-dis-inceleme: M3 ingest öncesi düzeltmeler (FFCore 154-156 + paycoreLLM dış inceleme R1-R8)

**Paket:** fix/19-dis-inceleme · **Sınıf:** [B] (iki depo, ayrı SHA) · **İşçi:** isci-b (ffcore-isci-b-19r)
**PR-HAZIR SHA'ları:** ffcore `b7a6d539079021c1fdb3b0f630762a5118a000a1` (main b2e9c05 üstüne 3 commit) · paycoreLLM `81098f49555aaf2b4710af0e54f68d86e36e5f74` (master ca1b287 üstüne 9 commit)
**ffcore:** branch `fix/19-ingest-followups` · worktree `.worktrees/fix/19-ingest-followups` · baz main b2e9c05 (614c150+)
**paycoreLLM:** branch `feat/19-dis-inceleme` · kardeş worktree `C:\ai_paycore\paycoreLLM-19r` · baz master ca1b287
**GOREV:** K-19R-0001, K-19R-0002, K-19R-0003. Kaynaklar: `state/reviews/paycore-19-dis-inceleme.md` (R1-R8), `state/pr/18-kosu-2.md` "Bulgular" (B1-B3).

## Plan (kodlamadan önce)

### 1. Bulunan semboller ve dosyalar (rg/grep, iki worktree)

ffcore:
- `deploy/docker-compose.yml:263` `&app-env` içinde `ALLOWED_INTERNAL_HOSTS: ${ALLOWED_INTERNAL_HOSTS:-}`; backend bunu olduğu gibi alıyor. worker `:334` ve agent-worker `:394` başa `backend` ekliyor.
- `backend/ffcore/knowledge/ingest.py:73` `HttpEmbedClient.embed` → `SafeOutboundClient` ile `POST {internal_api_url}/internal/embed`; `core/config.py:111` `internal_api_url = "http://backend:8000"`, `:35` `allowed_internal_hosts`.
- `backend/ffcore/knowledge/raw_ingest.py`: `ingest_tree` `:206`; sha aynıysa statüye bakmadan `unchanged` (`:251-254`); istisna yolu `:266-269` (`statuses["failed"] += 1`, DB satırı dokunulmadan kalır); `RawIngestReport.lines()` `:90` `status:` yalnız bu koşunun sayacı (unchanged olanlar `-`); `_fill_current` `:150` DB statüleri (yalnız manifestte).
- `backend/tests/integration/test_19_ingest_raw.py`: her yol `ingest.LocalEmbedClient` enjekte ediyor (`:56, :238, :307`); gerçek `HttpEmbedClient` yolu hiç koşmuyor.
- `scripts/eval_report.py`: `passed()` `:114` tüm skorların VE'si; `markdown()` `:162-165` "Document questions with the right source" ve "Source accuracy" `passed()` sayıyor. Birim testi `backend/tests/unit/test_19_eval_out.py` (scripts'i `_load` ile yükler).
- `docs/demo.md:86, :96` etiketler ("Document questions, right source", "Source accuracy").

paycoreLLM:
- `scripts/ffcore_stage_raw.py`: `MENTION :42`, `AT_MENTION :43`, `SIGNATURE :44`, `SIGNATURE_LINES :48`, `StagingError :51`, `_is_prsim :60`, `check_sources :65`, `_drop_signatures :87`, `_scrub :109`. PayCore `ingest` imajında koşar (runbook `m3-sunucu.md:238`), ffcore paketi yok.
- `scripts/ffcore_seed_paycore.py:57` `is_prsim` (ikinci kopya); **ffcore-backend imajında** koşar (`m3-sunucu.md:191, :216`).
- `tests/test_19_stage_raw.py:192` `test_19_s1_source_rule_matches_ffcore` (ffcore import'u; bağlı test konteynerinde).
- `src/paycore_llm/config.py`: `_CREDENTIAL_NAME :355` (alt dize deseni), `secret_values :361`, `scrub :373`, `redact :392`, `get_settings :342` (`lru_cache`).
- `src/paycore_llm/rag/embed.py:63` `embed()` içinde `truncated(texts)`; `ingest/sync.py:1506` `flag_truncated` aynı kontrol.
- `pyproject.toml:16` `langfuse>=2.50`; opentelemetry bildirimi yok.
- `compose.ffcore.yml:320` ffcore-backend `ALLOWED_INTERNAL_HOSTS` (backend yok); 20 `mem_limit`.
- `tests/test_19_compose.py:160` `test_19_3_mem_budget_within_limit` (bellek.md "Fiziksel bellek" yoksa skip, NOT_RUN gerekçeli); `docs/paycore/bellek.md`, `docs/paycore/m3-sunucu.md`.

### 2. Kapsam / kapsam dışı

Kapsam: FFCore FOLLOWUP-154 (B1), 155 (B2), 156 (B3); paycoreLLM R1-R8 (K-19R-0001 kararları) ve B1'in paycoreLLM yarısı (compose.ffcore.yml app-env).
Kapsam dışı: R4 tavan değişikliği (BLOCKERS 152, kullanıcı kararı; ayrı commit sonra); ffcore `raw_staging.py` (dokunulmaz, R7 yalnız tüketici tarafı); FOLLOWUP-145 (no_prose); sunucu koşusu.

### 3. Değişecek dosyalar ve neden

ffcore (sıra 1, M3 ingest önkoşulu):
- `deploy/docker-compose.yml`: backend servisinin environment'ına `ALLOWED_INTERNAL_HOSTS: backend,${ALLOWED_INTERNAL_HOSTS:-}` (154). Anchor'a eklenmez: anchor'ı kullanan diğer servisleri (mcp-*, migrate) genişletmemek için.
- `backend/ffcore/knowledge/raw_ingest.py` (155): `unchanged` yalnız sha aynı **ve** mevcut statü `indexed`; `failed`/`gated` (ve indexed dışı her ara statü) yeniden denenir (`retried` outcome sayacı, yeni sürüm açmaz: aynı bayt, aynı belge; ingest_from_raw'ın mevcut-belge yolu planda kontrol edilir); istisnada belge satırı `failed` + hata kodu (`meta.error_code` = istisna sınıf adı, içerik yok); konsol `lines()` statü satırı `indexed/unchanged/gated/failed` sayılarını manifestle aynı kaynaktan (DB, `_fill_current`) yazar.
- `scripts/eval_report.py` (156): "Source accuracy" = yalnız `cites_source`; ayrı satır "Answer contains the expected text" (`contains`); "right source" etiketi kalkar; `passed` (tam geçiş) ayrı ve açık adla ("Document questions passed (answer and source)").
- `docs/demo.md`: "Real-model results" ve S1 tablosu etiketleri aynı adlarla.
- `backend/tests/unit/test_19r_compose_internal_hosts.py`, `backend/tests/integration/test_19_ingest_raw.py` (ek testler), `backend/tests/unit/test_19_eval_out.py` (ek testler).

paycoreLLM (sıra 2):
- R1 `scripts/ffcore_stage_raw.py`: `AT_MENTION` kaldırılır, yalnız `MENTION` (`[~user]`); runbook `m3-sunucu.md` "bilinen sınır" cümlesi: gövdedeki kişi adı ve `@ad` NER'e (08 tam) kadar maskelenmez.
- R2 `src/paycore_llm/config.py`: `_CREDENTIAL_NAME` → açık ad kümesi (casefold tam eşleşme): authorization, password, secret, api_key, token, access_token, refresh_token, cookie, set-cookie + Settings secret alan adları; `scrub` ve `redact` aynı yardımcıdan; değer tabanlı maske aynen.
- R3 `scripts/ffcore_stage_raw.py`: `_drop_signatures` fence içini atlar, yalnız son 8 satırda arar; belge başına `signature_lines_dropped` meta'ya.
- R4 `docs/paycore/bellek.md` (senaryo tablosu: yalnız PayCore / yalnız FFCore penceresi / birlikte, Ollama dahil), `docs/paycore/m3-sunucu.md` ("Aynı anda hangi yığınlar": M3 penceresinde PayCore api/worker/open-webui durur), `tests/test_19_compose.py` (senaryo parametreli tavan toplamı testi; `SERVER_RAM_GB` ortam değişkeni ya da bellek.md ölçüm satırı yoksa skip "NOT_RUN (BLOCKERS 152, ENV-45)"; eşik RAM − 6 GB).
- R5 `src/paycore_llm/rag/embed.py`: `embed()` içindeki `truncated()` çağrısı kalkar; kontrol yalnız `flag_truncated`.
- R6 `pyproject.toml` (`langfuse>=4.15,<5`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`), `uv.lock` (`uv lock --offline`; olmazsa KAYIT-TALEBI + PR'da "lock yenilenmedi").
- R7 yeni `src/paycore_llm/ffcore_compat.py` (`StagingError`, `is_prsim`, `check_sources`; gerekçe + FFCore kaynak yolu `backend/ffcore/knowledge/raw_staging.py` yorumu); `ffcore_stage_raw.py` oradan import eder; `ffcore_seed_paycore.py` FFCore imajında koştuğu için `ffcore.knowledge.raw_staging`'ten alır (kopya silinir). Varsayım: FFCore'da public `is_prsim` yok (`_is_prsim` özel); seed public `check_sources` üstünden çalışır (StagingError `prsim_requires_ner` yakalanır), özel ada import edilmez. Uyum testi `make test`'te zorunlu (ffcore yoksa skip değil, hata).
- R8 `src/paycore_llm/config.py`: `secret_values` sonucu settings ömrüyle önbellekli (`lru_cache`), test fikstürü önbelleği temizler.
- B1 yarısı `compose.ffcore.yml:320`: ffcore-backend `ALLOWED_INTERNAL_HOSTS`'a `backend`; `tests/test_19_compose.py`'ye test.

### 4. Sözleşme, yapılandırma, profil etkisi

Donmuş sözleşme yok: C6 `ingest_from_raw` imzası değişmez (yalnız çağıran `raw_ingest`); raw_ingest konsol satırları ve manifest anahtarları additive (`retried`, statü satırı); eval raporu etiketleri değişir (rapor bir sözleşme değil; `scripts/m3_gate_check.py` bu etiketleri ve `passed`/`cites_source`/`contains` adlarını okumuyor, grep ile doğrulandı). Compose: backend'e tek değer (yeni servis, imaj, port yok) → [B]. Profilden bağımsız; testler iki profille.

### 5. Kabul kriteri → test

| # | Kriter | Test |
|---|---|---|
| 154a | backend servisinin `ALLOWED_INTERNAL_HOSTS`'unda `backend` (ffcore compose) | `test_19r_154_backend_allows_itself` (unit, compose parse) |
| 154b | `HttpEmbedClient` (enjeksiyonsuz) backend ortamıyla `EgressDenied` almaz | `test_19r_154_http_embed_client_egress_allowed` (integration; ayarlar compose backend env'inden; çağrının egress denetimini geçtiği, sahte /internal/embed'e ulaştığı) |
| 154c | yığında `ingest-raw` gerçek `HttpEmbedClient` ile indexed | yığın koşusu (backend konteynerinde CLI); ağırlık gerektirir → `model_cache` volume yoksa NOT_RUN gerekçeli |
| 154d | paycoreLLM ffcore-backend aynısı | `test_19r_154_ffcore_backend_allows_itself` (paycoreLLM test_19_compose) |
| 155a | ikinci koşu failed belgeyi yeniden dener | `test_19r_155_rerun_retries_failed` |
| 155b | gated belge de yeniden denenir; indexed `unchanged` kalır | `test_19r_155_rerun_retries_gated_keeps_indexed` |
| 155c | istisnada satır `failed` + hata kodu, gated'da kalmaz | `test_19r_155_exception_marks_failed` |
| 155d | konsol özeti statü sayıları manifestle aynı | `test_19r_155_console_statuses_match_manifest` |
| 156a | Source accuracy yalnız cites_source | `test_19r_156_source_accuracy_is_cites_source` |
| 156b | contains ayrı satır, etiketler açık | `test_19r_156_contains_separate_line` |
| R1 | `@Component`, `@Transactional(REQUIRES_NEW)`, `@angular/core`, fence içi `@Order(1)` aynen; `[~ahmet.yilmaz]` → `[USER]` | `test_19r_r1_*` (paycoreLLM) |
| R2 | `tokens=5`, `issue_key=PRSIM-1`, `api_key=***`, `password=***`; serbest metindeki secret değeri `***` | `test_19r_r2_*` |
| R3 | fence içi `--` satırı kalır; ortadaki "Teşekkürler" + 3 madde kalır; son blok imzası düşer; meta `signature_lines_dropped` | `test_19r_r3_*` (3 + meta) |
| R4 | senaryo başına tavan toplamı ≤ RAM − 6 GB | `test_19r_r4_mem_budget_by_scenario` (RAM yoksa NOT_RUN gerekçeli) |
| R5 | 9.000 token'lık parçada `embedding_truncated` bir kez, tokenizer bir kez | `test_19r_r5_truncation_checked_once` |
| R6 | `uv lock --check` temiz; `import paycore_llm.api` konteynerde | `test_19r_r6_*` + komut |
| R7 | `is_prsim` depoda tek yerde; uyum testi `make test`'te atlanmadan | `test_19r_r7_single_prsim_rule`, `test_19_s1_source_rule_matches_ffcore` (skip yok) |
| R8 | 1.000 log satırında `secret_values` bir kez | `test_19r_r8_secret_values_cached` |

### 6. Migration

Yok.

### 7. Geri alma

Her bulgu ayrı commit; `git revert <sha>`. Compose değişikliği tek değer. raw_ingest değişikliği DB şemasına dokunmaz (statü değerleri mevcut enum).

### 8. Durma koşulları

- `ingest_from_raw` aynı baytla yeniden denemede yeni sürüm açıyor ya da C6 imzası değişmeden yeniden deneme yapılamıyor → KARAR-GEREK.
- `m3_gate_check` eval raporunun eski etiketlerini okuyor ve değişiklik gate kuralını etkiliyor → KARAR-GEREK.
- `uv lock --offline` başarısız → KAYIT-TALEBI (kullanıcı ağ açık koşar), R6 lock'suz.
- R1 testinde başka bir yapısal kişi izi (ör. `@ad` Jira ADF mention düğümü) görürsem → SORU.
- Yığın gerekiyor (154c): kanala `YIGIN-AÇ`, koordinatör sırası.

### 9. Felsefe kontrolü

- **ARCH-07:** hepsi düzeltme; yeni özellik yok, çekirdeğe kalıcı karmaşıklık eklenmiyor (155 tek koşul + bir statü yazımı; R7 bir modül azaltıyor).
- **ARCH-09:** platform zaten sunuyor mu: R8 `functools.lru_cache` (stdlib), R6 bağımlılığı uv'ye bildirmek; kendi önbellek/kuyruk yok.
- **ARCH-10 / ARCH-06:** 155 sessiz `unchanged` (fail-loud açığı) kapatılıyor; 156 iki ölçüyü tek etikette karıştırma (ARCH-13) ayrılıyor; R1/R3 sessiz içerik kaybı kaldırılıyor ve sayısı belge başına görünür; R2 gizli maskeleme ile kaybolan sayı geri geliyor, secret koruması değer tabanlı kalıyor.

## Değişen dosyalar

**ffcore** (`git diff main...b7a6d53`, 8 dosya):

| Commit | Bulgu | Dosyalar |
|---|---|---|
| 641e20b | 154 (B1) | `deploy/docker-compose.yml` (paylaşılan ortam `x-app-env`'e taşındı; backend `<<: *app-env` + `ALLOWED_INTERNAL_HOSTS: backend,${ALLOWED_INTERNAL_HOSTS:-}`), `backend/tests/unit/test_19r_154_internal_hosts.py` (yeni) |
| c60b61d | 155 (B2) | `backend/ffcore/knowledge/raw_ingest.py`, `backend/tests/integration/test_19_ingest_raw.py` (+4 test, `_ingest` yardımcısı `convert`/`embed_client` alır) |
| b7a6d53 | 156 (B3) | `scripts/eval_report.py`, `backend/tests/unit/test_19_eval_out.py` (+2 test, 1 etiket), `tests/e2e/test_13b_eval_report.py` (1 etiket satırı), `docs/demo.md` |

**paycoreLLM** (`git diff ca1b287..81098f4`, 19 dosya):

| Commit | Bulgu | Dosyalar |
|---|---|---|
| 89e908a | R2 | `src/paycore_llm/config.py`, `tests/test_19r_redact.py` (yeni) |
| fb3bf0d | R8 | `src/paycore_llm/config.py`, `tests/conftest.py` (autouse önbellek temizliği), `tests/test_19r_redact.py` |
| 6802713 | R1 + R3 | `scripts/ffcore_stage_raw.py`, `tests/test_19r_stage_raw.py` (yeni), `tests/test_19_stage_raw.py` (meta anahtar seti + sınırlı imza testi R3'e göre), `docs/paycore/m3-sunucu.md` |
| aa54f05 | R5 | `src/paycore_llm/rag/embed.py`, `src/paycore_llm/ingest/sync.py` (`_index_doc` açık `truncated()`), `tests/test_19r_embed_truncation.py` (yeni) |
| c0480e3 | R6 | `pyproject.toml`, `tests/test_19r_langfuse_floor.py` (yeni) |
| b627fda | R7 | `src/paycore_llm/ffcore_compat.py` (yeni), `scripts/ffcore_stage_raw.py`, `scripts/ffcore_seed_paycore.py`, `tests/test_19_seed.py`, `tests/test_19r_ffcore_rule.py` (yeni) |
| 144a957 | R4 | `docs/paycore/bellek.md` (senaryo tablosu, sunucu satırları), `docs/paycore/m3-sunucu.md` ("Aynı anda hangi yığınlar"), `tests/test_19_compose.py` |
| a051cc6 | 154 yarısı | `compose.ffcore.yml` (`x-ffcore-app-env`; ffcore-backend `backend,` önekli), `tests/test_19_compose.py` |
| 81098f4 | R1 eki (K-19R-0008) | `scripts/ffcore_stage_raw.py` (`AT_TECHNICAL`, Türkçe harfli login), `tests/test_19r_stage_raw.py`, `docs/paycore/m3-sunucu.md` |

R1 ve R3 tek commit: ikisi aynı fence tespitini (`_fenced`) kullanıyor; ayırmak ara commit'te ölü kod bırakırdı.

## Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 154a | ffcore backend `ALLOWED_INTERNAL_HOSTS`'ta `backend` (operatör ekleri korunur) | `test_19r_154_backend_allows_itself` | geçti (önce kırmızı) |
| 154b | gerçek `HttpEmbedClient`, backend ortamıyla (`OFFLINE=true`), egress geçer | `test_19r_154_http_embed_client_reaches_backend` | geçti (önce kırmızı: `egress_offline`) |
| 154c | yığında backend kapsayıcısında `ingest-raw`, gerçek `HttpEmbedClient` + gerçek ağırlık, indexed | yığın koşusu (aşağıda) | geçti |
| 154d | paycoreLLM ffcore-backend `backend` önekli; migrate genişlemez | `test_19r_154_ffcore_backend_allows_itself` | geçti (önce kırmızı) |
| 155a | ikinci koşu failed belgeyi yeniden dener, yeni sürüm yok | `test_19r_155_rerun_retries_failed` | geçti (önce kırmızı) |
| 155b | gated yeniden denenir; indexed/skipped `unchanged` | `test_19r_155_rerun_retries_gated_keeps_indexed` | geçti (önce kırmızı) |
| 155c | istisna → satır `failed` + `metadata.error_code` (sınıf adı, mesaj yok); başarılı yeniden deneme kodu temizler | `test_19r_155_exception_marks_failed` | geçti (önce kırmızı: satır `gated`'da) |
| 155d | konsol statü satırı = manifest (DB) | `test_19r_155_console_statuses_match_manifest` | geçti (önce kırmızı: `status: -`) |
| 156a | Source accuracy yalnız `cites_source` (18-kosu-2 biçimi 19/20) | `test_19r_156_source_accuracy_is_cites_source` | geçti (önce kırmızı: 0/20) |
| 156b | `contains` ayrı satır, tam geçiş kendi adıyla | `test_19r_156_contains_separate_line` | geçti (önce kırmızı) |
| R1 | `@Component`, `@Transactional(REQUIRES_NEW)`, `@angular/core`, kod içi `@Order(1)`, e-posta `@`'si, `@param`/`@media`… aynen; `[~ahmet.yilmaz]`, `@ahmet.yilmaz`, Türkçe harfli login → `[USER]` | `test_19r_r1_technical_text_kept[*]`, `test_19r_r1_login_mentions_cleaned[*]` | geçti (önce kırmızı) |
| R2 | `tokens=5`, `issue_key=PRSIM-1`, `api_key=***`, `password=***`; serbest metindeki secret değeri `***` | `test_19r_r2_*` + mevcut `test_00i_redact.py` | geçti (önce kırmızı 11) |
| R3 | fence içi `--` kalır; ortadaki "Teşekkürler" + 3 madde kalır; son blok imzası düşer; belge başına `signature_lines_dropped` | `test_19r_r3_*` (4) | geçti (önce kırmızı) |
| R4 | senaryo başına tavan ≤ RAM − 6 GB (`SERVER_RAM_GB` varsayılan 96 → 90 GB); tablo = compose | `test_19r_r4_mem_budget_by_scenario[*]`, `test_19r_r4_scenario_table_matches_compose`, `test_19_3_mem_budget_within_limit` (artık atlamıyor) | geçti (tablo testi önce kırmızı) |
| R5 | 9.000 token'lık parça: `embedding_truncated` bir kez, tokenizer bir kez; eski `_index_doc` yolu yine bildirir | `test_19r_r5_truncation_checked_once`, `test_19r_r5_legacy_index_path_still_reports` | geçti (önce kırmızı: 2 kez / 0 kez) |
| R6 | pyproject sınırları; `import paycore_llm.api` konteynerde | `test_19r_r6_langfuse_and_otel_declared`, `test_19r_r6_api_imports` | geçti; `uv lock --check` **NOT_RUN** (aşağı bakınız) |
| R7 | PRSIM kuralı depoda tek yerde; uyum testi atlanmadan | `test_19r_r7_single_prsim_rule`, `test_19r_r7_scripts_take_the_rule_from_one_place`, `test_19r_r7_compat_matches_ffcore[*]` | geçti (önce kırmızı: modül yok) |
| R8 | 1.000 log satırında `secret_values` bir kez | `test_19r_r8_secret_values_cached` | geçti (önce kırmızı) |

## Çalıştırılan komutlar

Host'ta make yok (ENV-19); hedefler kendi konteynerlerinde, `MSYS_NO_PATHCONV=1`. ffcore: `FFCORE_VERSION=0.0.0-main` (bağımlılık/Dockerfile değişmedi), proje `f19r`.

| Komut | Ortam | Exit | Sonuç / süre |
|---|---|---|---|
| `docker compose -p f19r --env-file .env.test run --rm --no-deps tools make lint` | llmaas, airgap | 0 / 0 | |
| `... tools make test` | `DEPLOY_PROFILE=llmaas` | 0 | 948 geçti, 3 dk 37 s |
| `... tools make test` | `DEPLOY_PROFILE=airgap` | 0 | 948 geçti, 3 dk 21 s |
| `... --profile test --profile qdrant up -d --wait` sonra `tools make test-int` | llmaas | 0 | 807 geçti, 5 atlandı, 28 dk 9 s |
| aynı | airgap | 0 | 807 geçti, 5 atlandı, 17 dk 47 s |
| çözülmüş compose karşılaştırması (`config --format json`, main ↔ dal, `--profile '*'`) | | 0 | tek fark: backend `ALLOWED_INTERNAL_HOSTS` |
| paycoreLLM `docker compose -p pc19r -f compose.test.yml run --rm -T test sh -c "ruff check . && ruff format --check ."` (= `make lint`) | | 0 | 211 dosya |
| paycoreLLM `... test uv run --frozen --extra dev --group ffcore pytest -q` (= `make test`) @ 81098f4 | | 1 | 586 geçti, 3 kaldı, 2 atlandı, 82 s |
| paycoreLLM `test_19_compose.py` `FFCORE_DEPLOY_DIR=../ffcore/deploy` ve `=../ffcore/.worktrees/fix/19-ingest-followups/deploy` | | 0 / 0 | 17 / 17 (app-env uyumu iki ffcore compose'una karşı) |
| paycoreLLM çözülmüş config karşılaştırması (ca1b287 ↔ dal) | | 0 | tek fark: ffcore-backend `ALLOWED_INTERNAL_HOSTS` |
| paycoreLLM `uv lock --check --offline` (master ca1b287, değişikliksiz) | | 1 | lock zaten bayat → R6 lock kısmı FOLLOWUP-158 |

**paycoreLLM 3 kalan:** `test_data_dump::test_an_html_email_becomes_its_text_not_an_xml_pile`, `test_mhtml::test_only_the_html_part_becomes_text`, `test_reconvert::test_msg_html_body_bytes_are_decoded`: hepsi `No module named 'bs4'` (test konteynerine `ingest` extra'sı kurulmuyor); 00i'den beri kayıtlı aynı üç baz hatası (B-00i-0019). Bu turda master'da yeniden koşulup doğrulanmadı. 2 atlanan: `fitz` yok, `build_scenario2_eval.py` seti üretilmemiş (ikisi de önceden var).

**ffcore 5 atlanan (test-int):** `test_03b_egress_dns` (resolver bütçesi), `test_04a_ingest` ×2 ve `test_05a_sql` ×1 (atlama nedenleri bu turda `-rs` ile listelenmedi; bu dosyalara dokunulmadı), `test_19_ingest_raw:156` (root dosya modunu yok sayar; `:ro` bağlama testi ayrı koşar); beşi de bu PR'ın yeni testleri değil.

**154c yığın koşusu** (f19r, YIGIN-AÇ B-19R-0005, onay K-19R-0006): backend `04a-knowledge-core_model_cache:/models:ro` ile yeniden başlatıldı (geçici override, depoya girmedi); yerel test yöneticisi `create-superadmin` (atılan rastgele parola, yazdırılmadı), proje `f19r-paycore-like`, KB `paycore-like`; `ingest-raw` backend kapsayıcısında `-e OFFLINE=true`, ağaç `data/samples/paycore-like/raw:/raw:ro`:

| Adım | Sonuç |
|---|---|
| eski değerle (`ALLOWED_INTERNAL_HOSTS` backend'siz) `HttpEmbedClient.embed` | `EgressDenied egress_offline` (B1'in aynısı) |
| yeni compose değeriyle, ağırlıksız | egress geçer, backend 500 (`hf_path`: ağırlık yok) |
| yeni compose değeriyle, ağırlık bağlı | `EMBED_OK dense 1024` |
| `ingest-raw` koşu 1 (imaj kodu) | created 5, `status: indexed 4, skipped 1`, gates `gate2:boilerplate 1`, masked EMAIL 1 / TR_NATIONAL_ID 1 / TR_PHONE 1, `prsim_requires_ner 1`, manifest 5 belge 5 parça |
| koşu 2 (imaj kodu = main) | created 0, unchanged 5, `status: -` (eski konsol davranışı, 155'in düzelttiği) |
| koşu 3 (worktree `backend/ffcore` salt okunur bağlı) | created 0, unchanged 5, retried 0, `status: indexed 4, skipped 1` (manifestle aynı) |

Kapanış: `down -v` (f19r ve pc19r), kalan konteyner 0, volume 0.

## Varsayımlar ve brief'teki çelişkiler
1. Worktree'leri işçi açtı (WORK_QUEUE açanı yazmıyor; 00i deseni).
2. R7: FFCore `_is_prsim` özel; seed public `raw_staging.check_sources` üstünden çalışır, FFCore'a public alias eklenmedi (K-19R-0004).
3. 154: anchor değil yalnız backend servisi genişletildi (K-19R-0004); iki compose'da da paylaşılan blok `x-` uzantı alanına taşındı (YAML'da aynı eşlemede anchor tanımlayıp birleştirmek mümkün değil).
4. **R1 — KARARLAR (a) daraltıldı, kaldırılmadı** (K-19R-0007/0008): dış incelemenin "deseni kaldır" önerisi kullanıcının D sınıfı PRSIM kararıyla (koruma a: "`@ad` izleri temizlenir") çelişiyordu (B-19R-0006). Dar desen: küçük harfli login biçimi (Türkçe harf dahil, ≥ 3 karakter), satır başı ya da boşluk/noktalama sonrası, fence ve satır içi kod dışında, ardından `(`, `/` ya da sözcük karakteri gelmiyor; `AT_TECHNICAL` istisnaları.
5. R3: imza kuralı her **mesaja** ayrı uygulanır (Jira açıklaması ve her yorum); tüm gövdeye uygulansaydı açıklamanın imzası yorumlar yüzünden "son 8 satır" dışında kalırdı.
6. R5: dış inceleme "kontrol yalnız gold'da" diyordu; eski `sync._index_doc` yolu `embed()`'i `flag_truncated`'sız çağırıyor; orada açık `truncated()` çağrısı eklendi (sessiz kesilme olmasın, ARCH-06).
7. R6 (K-19R-0009 A): yalnız pyproject; `uv.lock` master'da da bayat (ffcore grubu kayması; yenileme 29 paket ekliyor, redis 8.1.0 → 5.3.1, httpx2/httpcore2 2.12 → 2.16, cryptography 50.0.1 → 50.0.2, sse-starlette 3.6.0 ≠ FFCore pini 3.5.0) → FOLLOWUP-158 [C].
8. R4 (K-19R-0005 A): sunucu belleği 96 GB **kullanıcı kararından**; `free -g` teyidi ve kullanım sütunları kullanıcı ölçümü. Senaryo toplamlarında `ingest` ve `ffcore-migrate` tek seferlik sayıldı (hariç).
9. 155: yeniden deneme `ingest_from_raw` değil `ingest.ingest_document` ile; `register_upload` aynı baytta da `version += 1` yapıyor (store.py:128) → FOLLOWUP-157 (04a). `timeout` ve ara statüler de yeniden denenir; yalnız `indexed` ve `skipped` (kapı kararı) atlanır.

## Kalan riskler
- R1: kod bloğu dışında, listede olmayan küçük harfli teknik `@sözcük` (ör. `@keyframes`, `@font-face` bileşenleri dışı biçimler) `[USER]` olur; liste tek sabit (`AT_TECHNICAL`), genişletmek bir satır. Gövde içi kişi adları NER'e (08 tam) kadar maskelenmez (bilinen sınır, runbook).
- 155: `timeout` olan bir belge her koşuda yeniden denenir (dönüşüm süresi kadar); bu bilinçli (ortam/limit düzeltmesi sonrası iyileşsin), konsolda `retried` sayısıyla görünür.
- R6: lock dışı kurulum artık langfuse 2.x seçemez, ama lock bayat kalıyor (FOLLOWUP-158); sunucu imajı `--frozen` ile bugünkü lock'tan kurulur, davranış değişmez.
- 154c koşusu `0.0.0-main` imajıyla yapıldı (kod değişikliği 155 bağlama ile koşu 3'te); dal için yeni imaj derlenmedi (bağımlılık değişmedi).
- paycoreLLM 3 `bs4` hatası bu turda master'da yeniden doğrulanmadı.
- İmaj çekme: içeriğe bakmak için `alpine:3.20` çekildi (işçi imaj izni kapsamında); silinmedi (temizlik kullanıcıda).
