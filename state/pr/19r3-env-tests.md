# PR: fix/19r3-env-tests (paycoreLLM)

**Paket:** fix/19r3 (FOLLOWUP-169 + R13 + FOLLOWUP-167) · **Sınıf:** [B] · **Branch:** fix/19r3-env-tests · **Worktree:** C:\ai_paycore\paycoreLLM-19r3 · **Baz commit:** paycoreLLM master ba3056d · GOREV K-19R3-0001 · Oturum ffcore-isci-d-19r3

## Plan (kısa; K-19R3-0002: onay beklenmez)
1. **Bulunan semboller:**
   - `src/paycore_llm/config.py:15` `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`. Src ve scripts içinde 129 `Settings()`/`get_settings()` çağrısı var, hiçbiri `_env_file` geçmiyor. Testlerde iki yer `Settings(_env_file=None)` kullanıyor (test_00i_jira); değişiklikten sonra da geçerli kalır.
   - `compose.yml:40` `env_file: ${APP_ENV_FILE:-.env}`: konteynerler değeri buradan almaya devam eder.
   - `compose.test.yml` depoyu `/app`'e bağlıyor; R12'nin kaynağı bu bağlama ve `config.py`'nin `.env`'i okuması.
   - `rag/trace.py:312` "Langfuse is half configured": ana checkout'ta düşen 3 testin hata yolu.
   - `src/paycore_llm/ffcore_compat.py` `check_sources(sources, *, accept_personnel_data)`; `text_filter` parametresi yok. FFCore 63ffb16 `raw_staging.check_sources(..., text_filter=None)`: `personnel_ok = accept_personnel_data or text_filter == "pii_ner"`. FFCore main'de 63ffb16'dan bu yana bu dosyada değişiklik yok.
   - FFCore `cli._raw_text_filter`: bayrak varsa `pii_regex`, yoksa `pii_ner`.
   - `scripts/ffcore_stage_raw.py:352` `check_sources(sources, accept_personnel_data=...)`.
   - `tests/test_19r_ffcore_rule.py`: eşitlik testi, şu an yalnız `accept_personnel_data` parametresini karşılaştırıyor.
   - `docs/paycore/m3-sunucu.md:29-58` "Bilinen sınırlar" bölümü.
   - Host'ta `load_dotenv` kullanan iki betik var: `scripts/atlassian_inventory.py` ve `scripts/attachment_formats.py`. İkisi `.env`'i Settings'ten bağımsız, kendileri okur; kapsam dışı, (c) maddesinde dokümante edilir.
2. **Kapsam:**
   - (169) `env_file` ve `env_file_encoding` kaldırılır.
   - (R13) Runbook'a iki yazım eklenir: `SET @login` ve `@login(acil)`.
   - (167) `ffcore_compat.check_sources` `text_filter` anahtar parametresini alır (FFCore'la aynı kural). Stager koşunun filtresini FFCore CLI ile aynı türetir: varsayılan `pii_ner`, `--accept-personnel-data` ile `pii_regex`. Bu filtreyi `check_sources`'a iletir ve çıktısında yazar. Bayraksız PRSIM `pii_ner` ile stage edilir; FFCore `ingest-raw` NER yoksa `prsim_requires_ner` ile reddeder (1b guard'ı).

   **Kapsam dışı:** iki host betiğinin `load_dotenv`'i, FFCore kodu, stager'ın maskeleme kuralları.
3. **Değişecek dosyalar:**
   - `src/paycore_llm/config.py`: yalnız `model_config` ve modül docstring'i.
   - `src/paycore_llm/ffcore_compat.py`
   - `scripts/ffcore_stage_raw.py`
   - `tests/test_19r_ffcore_rule.py`: eşitlik matrisine `text_filter` eklenir.
   - `tests/test_19r3_*.py`: yeni testler.
   - `docs/paycore/m3-sunucu.md`: R13 ve stager filtresi.
   - `docs/paycore/KURALLAR.md`: Settings `.env` okumaz; compose dışı komut değişkenleri ortamdan alır.
4. **Sözleşme ve profil:**
   - C14 ile tek yön korunur: paycoreLLM FFCore'u yalnız testte import eder.
   - `ffcore_compat` FFCore kuralına additive olarak eşitlenir.
   - Profil farkı yok.
   - Davranış değişikliği: compose dışında `get_settings()` artık `.env`'i okumaz.
5. **Kabul → test:**
   - (a) `test_19r3_1_settings_ignore_dotenv`: `tmp_path`'te `.env` var ve cwd oraya çevrilmiş; `get_settings()` o değeri almaz.
   - (b) `test_19r3_2_half_langfuse_dotenv_does_not_leak`: cwd'de sahte, yarım Langfuse `.env`'i varken Langfuse istemcisi "half configured" hatasına düşmez.
   - (b) kanıtı: ana checkout'taki 3 testin bu yolla yeniden üretilmesi (baz kırmızı, dal yeşil). Ana checkout'ta gerçek `.env` ile `make test` merge sonrası koşulur; ajan gerçek `.env` bulunan dizinde test başlatmaz.
   - `test_19r3_3_compat_text_filter_matches_ffcore` ve genişleyen `test_19r_r7_compat_matches_ffcore`
   - `test_19r3_4_stager_prsim_pii_ner_staged`
   - `test_19r3_5_stager_flag_gives_pii_regex`
   - `test_19r3_6_stager_reports_text_filter`
   - `test_19r3_7_runbook_lists_r13_spellings`
6. **Migration:** yok.
7. **Geri alma:** dalın revert'i; veri ya da şema yok.
8. **Durma koşulları:**
   - `.env` kaldırılınca compose dışında `.env`'e dayanan ve fail-loud olmayan bir üretim yolu bulunursa: KARAR-GEREK.
   - FFCore kuralı ile kopyası ayrışırsa: KARAR-GEREK.
9. **Felsefe kontrolü:**
   - ARCH-07: bütün test ve geliştirme koşularına değer katar; kalıcı karmaşıklık eklemez (bir satır silinir, bir parametre eklenir).
   - ARCH-09: pydantic-settings ve compose `env_file` zaten var; yeni mekanizma kurulmaz.
   - ARCH-10/06: gizli `.env` okuması kalkar. Stager filtresi açıkça yazılır ve çıktıda görünür. Eksik değer sessiz varsayılana düşmez; koşu çağrı anında açık hata verir.

**Tam SHA:** `f2dfe4799b77c21be92100c4f93f18011543f7ce` (ba3056d üstüne 6 commit, 11 dosya +245/-20). Ana kopyadaki commit'lenmemiş kullanıcı dosyalarıyla (`.gitignore`, `docs/archive/*.svg`, `docs/handover/...`) kesişme yok.

Commit'ler:
- `05372f6` test: önce kırmızı testler.
- `a886c87` fix(config): R12.
- `de3f076` fix(stage-raw): FOLLOWUP-167.
- `c9aa765` docs(m3): R13 ve stager filtresi.
- `b63990a` style: ruff.
- `f2dfe47` fix(compose): 08 tam 1b NER ayarları (K-19R3-0004 A).

## Değişen dosyalar
- **Kod:**
  - `src/paycore_llm/config.py`: `env_file` ve `env_file_encoding` kaldırıldı; docstring güncellendi.
  - `src/paycore_llm/ffcore_compat.py`: `check_sources(text_filter=)`, FFCore 63ffb16 kuralıyla aynı.
  - `scripts/ffcore_stage_raw.py`: `run_text_filter()`. Filtre `check_sources`'a iletilir ve çıktı `text_filter <ad>; ...` diye başlar.
- **Compose:**
  - `compose.ffcore.yml`: app-env'e `GUARDRAIL_EGRESS_NER` (`:?`), `NER_MODEL` ve `NER_REVISION` eklendi.
  - `.env.test`: `GUARDRAIL_EGRESS_NER=false`.
- **Testler:**
  - `tests/test_19r3_env_tests.py` (yeni).
  - `tests/test_19r_ffcore_rule.py`: eşitlik matrisi × `text_filter`.
  - `tests/test_19_stage_raw.py`: `test_19_s1_stage_refuses_prsim` → `test_19_s1_stage_prsim_follows_the_run_filter`.
  - `tests/test_19_compose.py`: `GUARDRAIL_EGRESS_NER == "false"`.
- **Belgeler:**
  - `docs/paycore/m3-sunucu.md`: R13'ün iki yazımı, stager filtresi (7.3), `.env` tablosuna `GUARDRAIL_EGRESS_NER=false` satırı.
  - `docs/paycore/KURALLAR.md`: Settings `.env` açmaz; compose dışı komutlar değerleri ortamdan alır; host'ta `.env` okuyan iki eski betik.

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 169a | `tmp_path`'te `.env` varken `get_settings()` o değeri almaz | `test_19r3_1_settings_ignore_dotenv` | geçti (bazda kırmızı) |
| 169b | ana checkout = temiz kopya | `test_19r3_2_half_langfuse_dotenv_does_not_leak`: R12'nin hatası "Langfuse is half configured" bazda birebir üretilir, dalda istemci `None`. Ortam değişkeni hâlâ geçerli: `test_19r3_2_environment_still_counts` | geçti. Gerçek ana checkout koşusu merge sonrası koordinatörde (K-19R3-0003) |
| 169c | compose dışında `.env`'e dayanan komut | kod yok; `docs/paycore/KURALLAR.md` notu | belge |
| 167 | compat `text_filter` FFCore'la eşit | `test_19r3_3_compat_text_filter_matches_ffcore` (30 durum), `test_19r_r7_compat_matches_ffcore` (× 3 filtre) | geçti |
| 167 | stager filtresi FFCore `ingest-raw` ile aynı | `test_19r3_3_stager_filter_is_ffcores`: FFCore `raw_ingest` sabitleri ve `cli._raw_text_filter` satırı kaynaktan okunur, çünkü PayCore test ortamında greenlet yok ve `ffcore.cli` import edilemez | geçti |
| 167 | bayraksız PRSIM `pii_ner` ile stage edilir, iz temizlenir | `test_19r3_4_stager_prsim_pii_ner_staged`, `test_19_s1_stage_prsim_follows_the_run_filter` | geçti |
| 167 | bayrakla `pii_regex`; çıktıda filtre görünür | `test_19r3_5_stager_flag_gives_pii_regex`, `test_19r3_6_stager_reports_text_filter` | geçti |
| R13 | runbook iki yazım; scrub gerçekten bırakıyor | `test_19r3_7_runbook_lists_r13_spellings` | geçti |
| K-19R3-0004 | backend ortamı FFCore compose ile eşit; sunucuda `false` | `test_19_3_app_env_keys_match_ffcore` (bazda kırmızıydı), `test_19_s4_m3_values_fixed_in_compose` | geçti |

## Çalıştırılan komutlar
Hepsi konteynerde: `docker compose -f compose.test.yml run --rm -T test uv run --frozen --extra dev --group ffcore ...`, Git Bash `MSYS_NO_PATHCONV=1`. Host'ta make yok; bunlar make hedeflerinin açılımı.

| Komut | Ortam | Exit / sonuç | Süre | Kanıt |
|---|---|---|---|---|
| `pytest tests/test_19r3_env_tests.py` @ 05372f6 (kod = ba3056d) | konteyner | 39 kırmızı / 1 geçti, doğru nedenle (TypeError `text_filter`, `run_text_filter` yok, R12 iletisi, `prsim_requires_ner`, runbook) | 5 s | state/evidence/19r3-red-ba3056d.log |
| tam takım (ara) | konteyner | 710 geçti, 5 kırmızı: 3 bs4, 1 kendi testim (düzeltildi), 1 `test_19_3` | 77 s | state/evidence/19r3-full-1.log |
| hedefli (19r3, 19r, 19, 19r2, 00i jira/langfuse) | konteyner | 195/195 | 9 s | — |
| tam takım @ f2dfe47 | konteyner | **712 geçti, 3 kırmızı (bs4 bazı, ENV-138), 2 atlandı** | 77 s | state/evidence/19r3-full-2.log |
| `ruff check . && ruff format --check .` @ f2dfe47 | konteyner | 0 (214 dosya) | — | state/evidence/19r3-ruff.log |

NOT_RUN:
- Gerçek ana checkout'ta `make test`: varsayım 1.
- bs4'e bağlı 3 test (`test_data_dump`, `test_mhtml`, `test_reconvert`): ENV-138, baz.

## Varsayımlar ve brief'teki çelişkiler
1. (b) "ana checkout `make test`" ajan tarafından koşulmaz: ana checkout'ta gerçek `.env` var ve bazda o koşu secret'ları test sürecine yükler (R12'nin kendisi). Kanıt sahte yarım `.env` ile `tmp_path`'te üretilir; gerçek koşu merge sonrası koordinatörde (K-19R3-0003 kabul).
2. 167 ile stager PRSIM'i kendi başına artık hiç reddetmez: filtre ya `pii_ner` ya da (bayrakla) `pii_regex`, ikisinde de kural PRSIM'e izin verir. Bekçi FFCore `ingest-raw`'dadır: NER yoksa `prsim_requires_ner`, kayıtla koşu filtresi uyuşmazsa `text_filter_mismatch`. Staging ağacı, okunduğu raw katmandan daha az bilgi taşır (yapısal kişi alanları ve `@`/imza izleri temizlenmiş), bu yüzden yeni bir açıklık yok. GOREV böyle istiyor. Eski `test_19_s1_stage_refuses_prsim` bu davranışa göre yeniden adlandırıldı ve yeniden yazıldı. Kuralın kendisi (`text_filter="pii_regex"`, bayraksız) hâlâ reddediyor ve test bunu tutuyor.
3. K-19R3-0004 A: `compose.ffcore.yml`'deki NER satırları kapsam dışıydı; bazda zaten kırmızı olan `test_19_3` ortaya çıkardı. Touch-zone koordinatör onayıyla genişletildi.

## Kalan riskler
- **Sunucu `.env`'i:** `GUARDRAIL_EGRESS_NER` satırı kullanıcının sunucu `.env`'inde yoksa compose `GUARDRAIL_EGRESS_NER is not set` ile durur. Bu fail-loud bir davranış ve runbook 4.1'de yazılı.
- **Compose dışında koşan komut:** `get_settings()` artık `.env`'i okumaz. Secret'lar varsayılanı `None` olan alanlar olduğu için açılışta değil, kullanıldıkları anda hata verirler (ör. Atlassian çağrısı). Compose dışında koşan üretim yolu bulunmadı. Bunu grep ile kontrol ettim: CLAUDE.md ve runbook'taki komutların hepsi compose `run` ya da `exec` kullanıyor.

## Review r1 bulgu → düzeltme → kanıt (r2)

**Tam SHA r2:** `a3fed7f25eae608aa3e881fddc046a7928af8f05`. f2dfe47 üstüne 2 commit:
- `884af80`: kırmızı test.
- `a3fed7f`: runbook ve stager docstring'i.

Toplam 2 dosya, +14/-9; test dosyası ayrıca.

| Bulgu | Karar | Düzeltme | Kanıt |
|---|---|---|---|
| MAJOR-1 runbook OCR `ingest-raw` NER'siz sunucuda `ner_unavailable` | A (K-19R3-0007, KARARLAR "M3 OCR ingest'i NER'siz sunucuda") | `m3-sunucu.md` 7.2 ve 7.3 OCR komutlarına `--accept-personnel-data`. 7.3 metni: NER yokken her `ingest-raw` M3 bayrağıyla `pii_regex`, PRSIM'in NER şartı değişmez, kalıcı çözüm FOLLOWUP-174. Sorun giderme tablosuna `ner_unavailable` satırı | `test_19r3_8_runbook_ocr_ingest_runs_without_ner`: f2dfe47'de kırmızı (state/evidence/19r3-r2-red.log), a3fed7f'de yeşil |
| NOTE-6 | uygulandı | `prsim_requires_ner` satırının nedeni: "PRSIM, NER modeli olmadan ve bayraksız" | aynı test dosyası (runbook) |
| NOTE-7 | uygulandı | runbook bilinen sınırlar (1) ve stager docstring'i "08 tam öncesi" yerine "NER modeli yok" | — |
| NOTE 1-5, 8-12 | bilgi | değişiklik yok | — |

**Kısıt (PR notu):** OCR için `--accept-personnel-data` geçici çözümdür. Bayrağın adı "personel verisi" diyor ama OCR'da anlamı "NER'siz regex kipi". FFCore'da kalıcı `--text-filter pii_regex` yolu FOLLOWUP-174.

**r2 kapıları @ a3fed7f (konteyner):**
- Tam takım: **713 geçti, 3 kırmızı (bs4, ENV-138), 2 atlandı** (state/evidence/19r3-r2-full.log).
- ruff check + format: 0 (state/evidence/19r3-r2-ruff.log).
