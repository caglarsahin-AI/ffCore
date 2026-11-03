# fix/19-dis-inceleme: M3 ingest öncesi düzeltmeler (FFCore 154-156 + paycoreLLM dış inceleme R1-R8)

**Paket:** fix/19-dis-inceleme · **Sınıf:** [B] (iki depo, ayrı SHA) · **İşçi:** isci-b (ffcore-isci-b-19r)
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
(uygulamada doldurulur)

## Kabul kriterleri → testler
(uygulamada doldurulur)

## Çalıştırılan komutlar
(uygulamada doldurulur)

## Varsayımlar ve brief'teki çelişkiler
1. Worktree'leri işçi açtı (WORK_QUEUE açanı yazmıyor; 00i deseni).
2. R7: FFCore `_is_prsim` özel; seed public `check_sources` üstünden çalışır, FFCore'a public alias eklenmez (ffcore touch-zone'u raw_staging'i içermiyor).
3. 154: anchor değil yalnız backend servisi genişletilir.

## Kalan riskler
(uygulamada doldurulur)
