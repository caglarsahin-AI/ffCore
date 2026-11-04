# PR: fix/19r2-dis-inceleme (paycoreLLM, dış inceleme r2)

**Paket:** fix/19r2-dis-inceleme · **Sınıf:** [B] · **Branch:** paycoreLLM `fix/19r2-dis-inceleme` · **Worktree:** `C:\ai_paycore\paycoreLLM-19r2` · **Baz commit:** master 530be09 · **GOREV:** K-19R2-0001 · **Kaynak:** state/reviews/paycore-19-dis-inceleme-r2.md, BLOCKERS 161, 160

ffcore'da kod değişikliği yok (yalnız bu dosya ve kanal).

## Plan (kodlamadan önce)

1. **Bulunan semboller ve dosyalar** (worktree, 530be09):
   - `scripts/ffcore_stage_raw.py`: `FENCE` (:86, yalnız satır başı işareti; aç/kapa aynı desen), `_fenced` (:105, her eşleşmede `inside = not inside`), `_mentions` (:144, `line.split("`")` tek/çift parça), `AT_MENTION` (:55, lookahead `(?![(/@]|\.?[A-Za-z0-9…])`), `AT_TECHNICAL` (:61), `_drop_signatures` (:117, `_fenced` kullanır), `_scrub` (:154), `_heading` (:177).
   - `scripts/ffcore_seed_paycore.py`: `_needs_ner` (:57, `prsim_requires_ner` dışı her `StagingError` → `False`), `plan` (:80), `SeedError` (:47).
   - Testler: `tests/test_19r_stage_raw.py` (R1/R3, korunacak), `tests/test_19_stage_raw.py`, `tests/test_19_seed.py`.
   - Runbook: `docs/paycore/m3-sunucu.md:29` "Bilinen sınırlar".
2. **Kapsam:** R9 (MAJOR), R10, R11 (MINOR), FOLLOWUP-160, runbook bilinen sınırlar (`{{…}}`, `@al` 3 karakter, R10 istisnaları). **Kapsam dışı:** bs4/`--extra ingest` test komutu (ENV-138), mypy baz hataları, uv.lock (FOLLOWUP-158), NER (08 tam).
3. **Değişecek dosyalar:**
   - `scripts/ffcore_stage_raw.py`: çit açılış/kapanış desenleri ayrı (GOREV'deki regex'ler); kapanış açılışın ailesiyle eşleşir (``` ↔ ```, ~~~ ↔ ~~~, `{code…}` ↔ `{code}`, `{noformat}` ↔ `{noformat}`); kapanmamış çit: son açılış satırından itibaren çit dışı; satır içi kod: yalnız kapanan backtick dizisi (aynı uzunlukta), Jira `{{…}}`, aynı satırda açılıp kapanan `{code…}…{code}` / `{noformat}…{noformat}`; kapanmayan backtick kod değildir. R10: SQL değişkeni kuralı ve tek başına dekoratör satırı kuralı. FOLLOWUP-160: lookahead `(?![(/@]|[._-]?[harf/rakam])`.
   - `scripts/ffcore_seed_paycore.py`: `_needs_ner` başka kodda `SeedError(f"{exc.code}: {exc}")`.
   - `tests/test_19r2_stage_raw.py`, `tests/test_19r2_seed.py` (yeni).
   - `docs/paycore/m3-sunucu.md`: bilinen sınırlar.
4. **Sözleşme/profil:** C6/C14 değişmez; profil bağımsız (staging betiği). KARARLAR "PRSIM M3 ölçümüne girer" (a): R9 maskeyi geri getirir (şüphede maskele), R10 yalnız teknik biçimi muaf tutar.
5. **Kabul → test:** tablo aşağıda (`test_19r2_r9_*`, `test_19r2_r10_*`, `test_19r2_r11_seed_reraises_other_codes`, `test_19r2_f160_*`); R1/R3 testleri (`test_19r_*`) geçmeye devam eder.
6. **Migration:** yok.
7. **Geri alma:** dal revert; veri yok. Staging çıktısı (`--out`) yeniden üretilebilir; PRSIM staging bu dal merge olana kadar koşulmaz.
8. **Durma koşulları:** R10 kuralının kişi maskesini daraltması gerekirse (ör. bir mention biçimi açığa çıkıyorsa) KARAR-GEREK; çit ailesi eşleşmesi R1/R3 testlerinden birini kırarsa koordinatöre.
9. **Felsefe:** ARCH-07: tek betik, kalıcı karmaşıklık iki desen + bir kural; çekirdeğe (ffcore) dokunmaz. ARCH-09: platformda karşılığı yok (PayCore uzantısı; NER 08 tam). ARCH-10/06: R9 fail-open'ı fail-closed yapar (şüphede maskele); R11 sessiz yutmayı açık hataya çevirir; R10 istisnaları runbook'ta açık.

### Varsayımlar (GOREV/raporda açık olmayan)

- **V1 çit ailesi:** kapanış yalnız kendi ailesinin açılışını kapatır (```` ``` ```` bloğu içindeki `{code}` satırı kod satırıdır, kapanış değil). Rapor ailesiz bir kapanış deseni verir; ailesiz kapatma bir bloğu erken bitirip kod içeriğini maskelerdi (fazla maske, kişi verisi açısından zararsız) ama ters yönde kapanmamış çit kuralıyla birleşince belirsizleşir.
- **V2 `@echo off`:** raporun R10 satırlarından biri; GOREV'in iki kuralı (SQL anahtar sözcüğü, tek başına dekoratör) bunu kapsamaz (`@echo` satır başında ve arkasından sözcük gelir, `@ahmet.yilmaz bakar` ile aynı biçim). Kural yolu yok; `AT_TECHNICAL`'a yalnız `echo` eklenir (batch dosyalarının `@` önekli tek yaygın komutu) ve runbook'a yazılır. Alternatif: maskeli kalır (fazla maske).
- **V3 SQL kuralı:** anahtar sözcük büyük harf ve hemen önde (`DECLARE`, `SET`, `SELECT`, `EXEC`, `EXECUTE`, `PRINT`); `@ad =` (atama, `==` değil); `DECLARE` ile başlayan satırdaki tüm `@ad` (değişken listesi). Küçük harfli SQL maskelenir (fazla maske; düzyazıda "set @ahmet.yilmaz" açığa çıkmasın diye).

## Dış inceleme bulgu → düzeltme → kanıt

HEAD **1dce5e57af286eec6a8498c92eb7d17cf0a7e66e** (530be09 üstüne 4 commit: 7a59267 R9+R10+F160, 4b35a19 R11, 8fb9716 runbook, 1dce5e5 ruff).

| Bulgu | Düzeltme | Test | Durum |
|---|---|---|---|
| R9 (MAJOR) çit tanıma | `FENCE_OPEN`/`FENCE_CLOSE` ayrı, yalnız kendi satırında; kapanış kendi ailesiyle (V1); `_fenced` kapanmamış çitte son açılıştan itibaren çit dışı; `INLINE_CODE`: kapanan backtick dizisi, Jira `{{…}}` (sayılır, dönüştürülmez), tek satırlık `{code…}…{code}`/`{noformat}…{noformat}`; `_mentions` yalnız span dışını maskeler | `test_19r2_r9_one_line_code_block_is_not_a_fence` (`[USER]`, imza ≥ 3 satır), `_same_line_block_is_inline_code` ×3, `_unclosed_fence_is_no_fence`, `_unclosed_jira_block_is_no_fence`, `_single_backtick_is_not_code`, `_closed_backtick_spans_still_code`, `_multiline_block_kept` ×5 (`@Inject`/`@foo` aynen), `_closer_of_another_family_does_not_close`, `_fenced_marks` | geçti; bazda 9'u kırmızı |
| R10 (MINOR) teknik `@` | `DECORATOR_LINE` (satırda tek başına dekoratör), `SQL_BEFORE` (büyük harfli DECLARE/SET/SELECT/EXEC/EXECUTE/PRINT hemen önde), `SQL_DECLARE_LIST` (DECLARE satırında `, @b`), `SQL_ASSIGN` (`@x =`, `==` değil); `AT_TECHNICAL` + `echo` (V2) | `test_19r2_r10_technical_at_kept` ×10 (raporun satırları + SQL biçimleri), `_mentions_still_cleaned` ×5 (`lutfen @ahmet.yilmaz bak` → `[USER]`, küçük harf `set`, `DECLARE notu:`, `==`) | geçti; bazda 9 kırmızı |
| R11 (MINOR) seed | `_needs_ner`: `prsim_requires_ner` → True, başka kod → `SeedError(f"{code}: {exc}")` | `test_19r2_r11_seed_reraises_other_codes`, `_seed_prsim_code_still_refused` | geçti; bazda ilki kırmızı |
| FOLLOWUP-160 | `AT_MENTION` lookahead `(?![(/@]\|[._-]?[harf/rakam])` | `test_19r2_f160_hyphen_login_before_email_not_split`, `_underscore_call_kept` (`@ali_veli` yine `[USER]`) | geçti; bazda 2 kırmızı |
| Not `@al` (3 karakter), `{{…}}` | runbook "Bilinen sınırlar" | `test_19_runbook` geçti | kapandı |

R1/R3 testleri (`tests/test_19r_stage_raw.py`) değişmeden geçiyor.

## Değişen dosyalar (paycoreLLM)

- `scripts/ffcore_stage_raw.py`: çit/satır içi kod (R9), teknik `@` kuralları (R10), lookahead (F160)
- `scripts/ffcore_seed_paycore.py`: `_needs_ner` (R11)
- `tests/test_19r2_stage_raw.py`, `tests/test_19r2_seed.py` (yeni)
- `docs/paycore/m3-sunucu.md`: bilinen sınırlar (R9 kod kuralları, `{{…}}`, R10 istisnaları, `@al`, F160)

ffcore: kod değişikliği yok.

## Çalıştırılan komutlar

Hepsi paycoreLLM worktree'sinde, `MSYS_NO_PATHCONV=1 docker compose -f compose.test.yml run --rm -T test …` (test imajı, `uv run --frozen --extra dev --group ffcore`). Tam çıktılar `state/evidence/19r2-*.log`.

| Komut | Ortam | Exit | Süre / sonuç |
|---|---|---|---|
| Kırmızı: yeni testler **baz 530be09 betiklerine** karşı (`/base` salt okunur bağlama: `git show 530be09:scripts/…` + yeni testler + conftest) | test konteyneri | 1 | 21 failed, 13 passed (geçenler korunması gereken davranışlar); `19r2-red-base-530be09.log` |
| `pytest -q` tam takım @ 1dce5e5 | test konteyneri | 1 | 634 passed, 2 skipped, **3 failed** (`test_data_dump`, `test_mhtml`, `test_reconvert`: `bs4` yok, ENV-138, baz aynı; dala ilgisiz) 52 s; `19r2-full-1dce5e5.log` |
| hedefli: test_19r2_*, test_19r_stage_raw, test_19_stage_raw, test_19_seed, test_19_runbook, test_19r_ffcore_rule | test konteyneri | 0 | 113 passed 6 s; `19r2-targeted-1dce5e5.log` |
| `ruff check . && ruff format --check .` @ 1dce5e5 | test konteyneri | 0 | 213 dosya; `19r2-lint-1dce5e5.log` |

NOT_RUN: `test_workers::test_a_slow_file_times_out…` zamanlama testi bu koşuda geçti (GOREV'de NOT_RUN olabilir denmişti); bs4'lü 3 test yukarıda (ENV-138). PRSIM staging koşulmadı (GOREV). Gerçek PayCore verisiyle staging koşulmadı (veri okunmaz).

## Kontrol listesi
- [x] Felsefe: R9 fail-open → fail-closed (şüphede maskele); R11 sessiz yutma → açık hata; R10 istisnaları runbook'ta açık (ARCH-10)
- [x] Donmuş sözleşme kırılmadı (C6/C14 dokunulmadı)
- [x] Betik çıktısı yalnız sayı; içerik/kişi verisi yazılmaz (değişmedi)
- [x] Docs (runbook) güncel
- [x] `.env`, `data/**`, `eval/results/**` okunmadı; push yok

## Kalan riskler

- R10 kişi maskesinden bilinçli istisnalar açar: satırda **tek başına** duran `@ahmet.yilmaz` (dekoratör biçimiyle ayırt edilemez) ve büyük harfli SQL sözcüğünden hemen sonraki `@ad` (`SELECT @ahmet.yilmaz …` düzyazısı) maskelenmez. Rapor ve GOREV bu takası kabul ediyor; runbook'ta yazılı.
- V2 `@echo` liste girdisi: satır başındaki `@echo …` maskelenmez; `echo` adlı bir login olasılığı yok sayıldı.
- Jira `{{…}}` içindeki `@ad` maskelenmez (sayma kararı); `{{@ahmet.yilmaz}}` biçiminde bahsetme nadir, runbook'ta.
- Bilinen sınırlar değişmedi: büyük harfli `@Ahmet`, gövdedeki personel adı (NER 08 tam).
