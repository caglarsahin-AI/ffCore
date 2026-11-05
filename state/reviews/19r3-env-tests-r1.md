# paycoreLLM fix/19r3-env-tests r1 inceleme

- **SHA:** f2dfe4799b77c21be92100c4f93f18011543f7ce (paycoreLLM fix/19r3-env-tests; master ba3056d + 6 commit, 11 dosya +245/-20)
- **İstek:** K-19R3-0005 · ACK R-19R3-0001
- **Yöntem:**
  - `git archive f2dfe47` kopyası scratchpad'de; `data/**`, `eval/results/**` ve `.env` arşivden hariç.
  - İşçi worktree'si (`C:\ai_paycore\paycoreLLM-19r3`) dokunulmadı. `.env` okunmadı, sunucuya bağlanılmadı. Yığın yok.
  - FFCore `backend` ve `deploy` main'den (0b35b45; 63ffb16 dahil), `git archive` ile.
  - Testler `compose.test.yml` konteynerinde.
  - Beş denetim ajanı (dört kalem ve bir regresyon eleştirmeni). Her bulgu iki ayrı doğrulayıcıyla çürütülmeye çalışıldı. MAJOR'u ayrıca kendim kaynağından doğruladım.
- **Karar: DEGISIKLIK** — BLOCKER 0, MAJOR 1, MINOR 0, NOTE 12

## Kalemler

| Kalem | Durum | Kanıt |
|---|---|---|
| (1) R12 Settings `.env` okumuyor | **KAPANDI** | `config.py:18` `SettingsConfigDict(extra="ignore")`; `src/`'de başka `env_file`/`load_dotenv` yok. `test_19r3_env_tests.py:34-69`: tmp_path'teki `.env` alınmıyor (JIRA_URL, yarım Langfuse), ortam değişkeni hâlâ kazanıyor. compose.yml `env_file: ${APP_ENV_FILE:-.env}` değişmedi (`compose.yml:40`, api/worker/ingest miras alıyor); compose.test.yml'de env_file yok. Compose dışında `.env` okuyan iki betik (`atlassian_inventory.py`, `attachment_formats.py`) KURALLAR.md:229-230'da istisna olarak yazılı. |
| (2) FOLLOWUP-167 stager `text_filter` | **KAPANDI** | `ffcore_stage_raw.py:345-365`: `run_text_filter` (bayraksız `pii_ner`, M3 bayrağıyla `pii_regex`) `check_sources`'a hiçbir dosya okunmadan gidiyor, sayılarla birlikte yazdırılıyor. Bu, FFCore main `cli._raw_text_filter` ile ve `raw_ingest.TEXT_FILTER`/`M3_TEXT_FILTER` ile aynı. `test_19r3_3` ikisini FFCore kaynağından okuyup eşit tutuyor. `ffcore_compat.check_sources`, FFCore main `raw_staging.check_sources` ile aynı (`personnel_ok = accept or text_filter == "pii_ner"`); `test_19r_r7` eşitliği denetliyor. |
| (3) R13 runbook | **Kısmen → MAJOR-1** | KURALLAR.md ve m3-sunucu.md'deki iki yazım ve stager notu kodla aynı. Ama OCR komutları 1b sonrası çalışmıyor (MAJOR-1). |
| (4) compose NER | **KAPANDI** | `compose.ffcore.yml:106-110`: `GUARDRAIL_EGRESS_NER: ${…:?…}`, `NER_MODEL`/`NER_REVISION` `:-` (boş kabul). `.env.test` `false`. Runbook :150 "FFCore 63ffb16+ dağıtımından önce zorunlu" satırı var. `test_19_3_app_env_keys_match_ffcore` hedefli koşuda yeşil; referans konteynere bağlanan FFCore main `deploy/`. |
| (5) önce kırmızı test | uygun | 05372f6 testleri, ba3056d'de `env_file=".env"`, `text_filter` parametresi olmayan `check_sources` ve eksik runbook satırları yüzünden düşer (statik). Ayrı test → kod commit'leri; b63990a yalnız ruff. |
| Tam takım ve ruff | **yeşil** | 712 passed, 2 skipped, 3 failed (bs4, ENV-138; master'da aynı); ruff temiz. |
| Kabul (b): ana checkout = temiz kopya | **NOT_RUN** | Koordinatör kapısı (merge sonrası ana checkout `make test` karşılaştırması). |

## MAJOR

### MAJOR-1 · Runbook'taki OCR `ingest-raw` komutları FFCore 1b'den sonra sunucuda `ner_unavailable` ile düşüyor

`docs/paycore/m3-sunucu.md:278` (aşama 0) ve `:292` (tam korpus) `--sources confluence:OCR`'ı `--accept-personnel-data` olmadan koşuyor. Zincir:
1. FFCore main `cli._raw_text_filter` bayraksız `pii_ner` seçiyor (`cli.py:207-212`).
2. `ingest_tree` `pii_ner` için ilk dosyadan önce `check_ner`'i çağırıyor (`raw_ingest.py:326-327`).
3. Runbook :150 `NER_MODEL`/`NER_REVISION`'ı boş bırakıyor (DECISION-166 A). `HttpNer` `ner_not_configured` veriyor. Kaynak PRSIM değil, kod `ner_unavailable` (`raw_ingest.py:286-298`).

Sonuç: belgelenmiş M3 OCR adımları dağıtımda çalışmıyor. Düşüş yüksek sesli, veri sızmıyor. 7.3 metni (:286-288) yalnız PRSIM'in reddedildiğini söylüyor; sorun giderme tablosunda (:409) `ner_unavailable` satırı yok. Bu dal 1b compose uyumu ve R13 runbook için açıldı ve 7.3'ü değiştirdi; kapsam içinde. FFCore tarafında karşılığı BLOCKERS 168 NOTE-8 ("airgap'te pii_ner varsayılanı docs netliği").

Koordinatör kararı (META-01):
- **A (önerilen):** OCR komutlarına `--accept-personnel-data` eklenir. M3 ölçümü önceki gibi `pii_regex` ile ölçülür, kayıtlar `pii_regex@1`. Yanı: koşu M3 kipi uyarısını loglar, bayrak adı "personnel data" diyor ama kaynak OCR. FFCore `check_sources` bayrağı her kaynakta kabul ediyor.
- **B:** OCR için NER zorunlu yazılır. DECISION-166 A ile çelişir (airgap'te NER ağırlığı yok); M3 OCR ölçümü NER gelene kadar durur.
- **C:** FFCore'a PRSIM dışı kaynaklar için ayrı, M3 dışı bir `pii_regex` yolu. Yeni bayrak, FFCore değişikliği, en geniş kapsam.

Her durumda: 7.3 metni ve sorun giderme tablosuna `ner_unavailable` satırı (neden: NER yok; çözüm: seçilen yol). Test: runbook OCR komutlarının bayrak içerdiğini ya da NER gerektiğini söylediğini denetleyen bir R13 testi.

## NOTE

1. `tests/test_00i_jira.py:39,49` `Settings(_env_file=None)` artık gereksiz (zararsız).
2. İki host betiği `.env`'i python-dotenv ile kendisi okuyor; KURALLAR.md'de istisna olarak yazılı.
3. `scripts/ffcore_seed_paycore.py:57-71, 87-97` `check_sources`'u `text_filter` olmadan çağırıyor; orada PRSIM her zaman "NER gerekir" sayılıyor. Güvenli taraf, ama stager ile tutarsız.
4. FFCore NER guard'ı PayCore tarafında yalnız docstring'de iddia ediliyor (`test_19r3_env_tests.py:140-147`); kanıt FFCore testlerinde (`test_08t_15_*`). Sözleşme testi kapsamı istekteki gibi; uçtan uca değil.
5. Uyumluluk kopyası yalnız `check_sources`'u taşıyor. FFCore 1b r3'ün yol tabanlı `personnel_data(source, relpath)` kuralı kopyalanmadı. Stager bunu yapmıyor (kaynak düzeyinde karar veriyor), ingest tarafında FFCore uyguluyor. Bilinçli, `ffcore_compat.py:1-10` yazıyor.
6. Sorun giderme `prsim_requires_ner` satırı (:409) 1b öncesi nedeni veriyor ("PRSIM bayraksız"); 1b'den sonra neden "NER yok".
7. m3-sunucu.md:30 ve `ffcore_stage_raw.py:19-21` hâlâ "08 tam (NER) öncesi" diyor; 08 tam merge edildi, sınır artık "NER modeli yok". Bir doğrulayıcı kozmetik saydı.
8. `test_19_3` yeşil koşusu hedefli toplamın içinde, adıyla ayrı kanıt yok. Referans, konteynere bağlanan FFCore `deploy/`: bu turda main'in arşivi, işçide çalışma ağacı.
9. `.env.example` FFCore anahtarlarını listelemiyor (önceden de böyle; runbook tablosu yazıyor).
10. `test_19_stage_raw.py:103-112`'deki eski CLI düzeyi PRSIM reddi kaldırıldı. Stager'dan ret dalına artık varılamıyor (bayraksız `pii_ner` her zaman izinli); ret yalnız `ffcore_compat` biriminde test ediliyor.
11. `test_19r3_4` docstring'i stager'ın adları maskelediğini ima ediyor; assert zaten temizlenmiş alanları denetliyor. Stager ad maskelemez (bilinen sınır).
12. `test_19r3_7` iki bilinen temizleme kaçağını beklenen davranış olarak sabitliyor (R13 "bilinen sınırlar" ile aynı; bilgi).

## Güvenlik turu

- **Gizli değer:** `.env` okunmadı. Değişiklik `.env`'i uygulamanın dışına çekiyor (yalnız compose `env_file`). `.env.test`'e yalnız `GUARDRAIL_EGRESS_NER=false` eklendi; gizli değer yok.
- **Kişi verisi:** bayraksız PRSIM artık stage ediliyor (`pii_ner`). Staged ağaç, okunduğu ham katmandan az şey tutuyor; FFCore ingest'i NER yoksa reddediyor (`prsim_requires_ner`). Ad maskesiz staged PRSIM ağacı sunucuda diskte durabilir. Ham katman zaten aynı veriyi tuttuğu için yeni bir yüzey değil; sınırı FFCore'un NER guard'ı koruyor.
- **MAJOR-1:** veri sızıntısı değil, işletim kırılması (yüksek sesli düşüş).
- **NOT_RUN:**
  - Test imajı yeniden kurulmadı. Kurulum dış taban imajları çekecekti (`python:3.12-slim`, `ghcr.io/astral-sh/uv`, `docker:27.5.1-cli` yerelde yok); `--pull never` kuralı.
  - Koşu mevcut `paycore-llm-test:local` imajıyla yapıldı (28 Ekim). Bu dal Dockerfile'a dokunmuyor; bağımlılıklar `uv run --frozen` ile `uv.lock`'tan venv hacmine.
  - Sunucu, uçtan uca PRSIM staging ve kabul (b).

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| İmaj kurulumu | NOT_RUN: betikteki `build --pull never` geçersiz (compose `build` bunu desteklemiyor); dış çekim yasak olduğu için tekrarlanmadı | `state/evidence/19r3-r1-build.log` |
| Hedefli (`test_19r3_env_tests`, `test_19_compose`, `test_19_stage_raw`, `test_19r_ffcore_rule`) | **102 passed** | `19r3-r1-targeted.log` |
| Tam takım | **712 passed**, 2 skipped, 3 failed (bs4, ENV-138) | `19r3-r1-full.log` |
| ruff check + format | **temiz** (214 dosya) | `19r3-r1-lint.log` |

## Karar

DEGISIKLIK (f2dfe4799b77c21be92100c4f93f18011543f7ce). Tek gerekli değişiklik MAJOR-1: koordinatörün A/B/C kararıyla runbook OCR komutları ve sorun giderme satırı, artı bir R13 testi. NOTE 6-7 aynı küçük commit'e girebilir. Gerisi bilgi.
