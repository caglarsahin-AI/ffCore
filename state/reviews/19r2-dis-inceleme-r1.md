# paycoreLLM fix/19r2-dis-inceleme r1 inceleme (dış inceleme r2 kapanışı)

- **SHA:** paycoreLLM 1dce5e57af286eec6a8498c92eb7d17cf0a7e66e (master 530be09 üstüne 4 commit: 7a59267 R9 + R10 + FOLLOWUP-160, 4b35a19 R11, 8fb9716 runbook, 1dce5e5 ruff; 5 dosya +306/-25)
- **İstek:** K-19R2-0004 · Kaynak: state/reviews/paycore-19-dis-inceleme-r2.md, BLOCKERS 160/161, K-19R2-0001 kararları
- **Yöntem:** `git archive 1dce5e5` kopyası (scratchpad; işçi worktree'si `C:\ai_paycore\paycoreLLM-19r2` aynı SHA'da temiz, dokunulmadı). `.env`, `data/**`, `eval/results/**` okunmadı. Sunucuya bağlanılmadı. PRSIM staging koşulmadı. Yığın yok.
- **Koşu zamanı:** Docker 16:52'de kapalıydı; statik inceleme ve host Python (`-I`) ile sentetik metin probe'u yapıldı. Docker 16:56'da açıldı; konteyner koşuları 16:58-17:05.
- **Karar: DEGISIKLIK** — BLOCKER 0, MAJOR 2, MINOR 1, NOTE 4

R9'un dış rapor girdileri, R11 ve FOLLOWUP-160 doğru. R10'un dar SQL kuralı da doğru. Ama iki MAJOR var:
1. R9'un yeni çit açıcısı, bilgi dizesinde boşluk ya da `=` olan çiti tanımıyor (```` ``` sql ````, ```` ```js title=a ````). 4+ karakterli çitler de tanınmıyor. Kapanış çiti yeni bir "blok" açıyor ve arkasındaki gerçek düzyazı **maskesiz** kalıyor. 530be09'da bu açıcılar ön ekle eşleşiyordu; yani bu bir **gerileme**.
2. R10'un dekoratör satırı istisnası, satırda tek başına duran gerçek bir login'i açık bırakıyor. Bu, Jira/Confluence yanıtlarında yaygın bir biçim (`@ahmet.yilmaz` + alt satırda soru) ve KARARLAR PRSIM M3 koruması (a) ile çelişiyor. Bunu koordinatör kararıyla sınıyorum; daha dar bir kural öneriyorum.

## İstenen kontroller

| # | Kontrol | Durum | Kanıt |
|---|---|---|---|
| 1 | R9 dış rapor girdileri | **KAPANDI** | `{code}SELECT 1{code} @ali.veli` + imza → `[USER]`, `dropped=3`; kapanmamış çit → maskeli; tek backtick → maskeli; iki satırlı `{code}` içindeki `@Inject @foo` aynen. |
| 1 | R9 inceleyici yazımları | **KISMİ** | Tutulanlar: `{noformat}x{noformat} @x`; `~~~` bloğu; girintili çit; `{code:sql}SELECT{code} @x`; CRLF; çit içinde çit (`~~~` içinde ```` ``` ````, `{code}` içinde `{noformat}`); `{code:title=A b\|…}`. Açılanlar: bilgi dizesinde boşluk/`=` olan çit ve 4+ karakterli çit (MAJOR-1). |
| 1 | R1/R3 testleri | **YEŞİL** | `-k 19` hedefli 169/169 (konteyner). |
| 2 | R10 SQL ve maskeleme | **KAPANDI** (kural) / **açık** (MAJOR-2, MINOR-1) | `DECLARE @x INT`, `SET @x = 1` aynen; `lutfen @ahmet.yilmaz bak` → `[USER]`; küçük harfli `set @x olarak` → `[USER]`; `@pytest.fixture` + `def` aynen; `@echo off` aynen, `@echo @ahmet.yilmaz` → `[USER]`. |
| 3 | R11 | **KAPANDI** | `_needs_ner`: `prsim_requires_ner` → True, diğer `StagingError` → `SeedError(code: msg)` (kod okuması); `test_19r2_r11_seed_reraises_other_codes` yeşil. |
| 4 | FOLLOWUP-160 | **KAPANDI** | `@ahmet-yilmaz@firma.com` bütün kalıyor (e-posta maskesine gidiyor); `@app_get(path)` aynen. |
| 5 | Runbook "bilinen sınırlar" | **KISMİ** | `@al` 3 karakter, `@Ahmet`, `@ahmet.Yilmaz`, `{{…}}`, R10 istisnaları kodla birebir. Çit tanımının sınırları (bilgi dizesi, 4+ karakter) yazılı değil; zaten düzeltilmeli. |
| 6 | Kanıt logları | **TUTARLI** | `19r2-red-base-530be09.log` 21 failed / 13 passed; `19r2-targeted-1dce5e5.log` 113 passed; `19r2-full-1dce5e5.log` 634 passed + 3 failed (bs4). Bu turda konteynerde aynısı: 634 passed, 3 failed (`test_data_dump`, `test_mhtml`, `test_reconvert`: `ModuleNotFoundError: bs4`, master'da da aynı; ENV-138). |
| 7 | PRSIM staging | koşulmadı | Yalnız birim testleri ve sentetik metin. |

## MAJOR-1 · Bilgi dizesinde boşluk/öznitelik olan ya da 4+ karakterli çit tanınmıyor; çit durumu terse dönüyor ve düzyazıdaki login maskesiz kalıyor (gerileme) — CONFIRMED (konteyner)

`FENCE_OPEN = ^\s*(?:(```|~~~)[\w+-]*|\{(code|noformat)(?::[^}]*)?\})\s*$`. Bilgi dizesi yalnız `[\w+-]*`; ardından satır sonu bekleniyor. CommonMark'ta bilgi dizesi boşluk ve diğer karakterleri içerebilir (```` ``` sql ````, ```` ```js title=a ````, ```` ```{python} ````). Çit 3'ten uzun da olabilir (```` ```` ````, `~~~~`); kapanış en az açılış kadar uzun ve aynı karakterden olmalı.

Probe (`19r2-r1-probe-container.log`):

| Girdi | Çıktı |
|---|---|
| ```` ``` sql ```` / `SELECT 1` / ```` ``` ```` / `@ali.veli bak` / ```` ``` ```` / … | `@ali.veli bak` **maskesiz** |
| ```` ```js title=a ```` … | aynı |
| ```` ```` ```` / ```` ``` ```` / ```` ```` ```` / `@ali.veli bak` / ```` ``` ```` | aynı |
| `~~~~` / `~~~` / `~~~~` / `@ali.veli bak` / `~~~` | aynı |

Mekanizma: açıcı tanınmadığı için asıl kod satırları metin sayılıyor (fazla maske, zararsız). Bloğun kapanış çiti ise kendi satırında duran ```` ``` ```` olduğu için **açıcı** sayılıyor; sonraki düzyazı "kod" sayılıp maskelenmiyor. Bir sonraki çit (sıradaki gerçek kod bloğunun açıcısı) bunu kapatıyor, yani "kapanmamış çit çit sayılmaz" güvencesi devreye girmiyor.

530be09'daki `FENCE = ^\s*(```|~~~|\{…\})` ön ek eşleşmesiydi ve ```` ``` sql ````'i açıcı sayıyordu; bu yüzden gerileme. Markdown dışa aktarımlarında ```` ``` sql ```` / ```` ```bash title ```` sık görülüyor; 4'lü çit markdown örneği gösteren sayfalarda var.

**Düzeltme:** Markdown açıcısı `^\s*(`{3,}|~{3,})(?P<info>[^`]*)$` olsun (backtick çitinde bilgi dizesi backtick içeremez); kapanış `^\s*(\1 aynı karakter, uzunluk ≥ açılış)\s*$`. Jira kısmı aynen kalsın. Testler: yukarıdaki dört girdi, `~~~ python` ve ```` ```{r} ```` ile 4'lü bloğun içinde ```` ``` ````.

## MAJOR-2 · Satırda tek başına duran gerçek login maskelenmiyor (R10 dekoratör istisnası fazla geniş) — CONFIRMED (konteyner); koordinatör kararıyla çelişiyor, karar gerekir

`DECORATOR_LINE = ^\s*@[A-Za-z_][\w.]*(\(.*\))?\s*$` satırın tamamını atlıyor. `@ahmet.yilmaz` + alt satırda `Kontrol eder misin?` (Jira/Confluence yorumunda bir kişiye seslenme) **maskesiz**. Virgülle (`@ahmet.yilmaz,`) maskeleniyor, virgülsüz değil.

- K-19R2-0001 bu davranışı kabul etmişti ("tek başına duran `@ad`/`@a.b` maskelenmez, kural"); PR "Kalan riskler" de "dekoratör biçimiyle ayırt edilemez" diyor.
- Bence ayırt edilebilir: kodda dekoratör satırının ardından her zaman `def` / `async def` / `class` ya da başka bir dekoratör satırı gelir. Yorumda seslenmenin ardından düzyazı gelir.
- KARARLAR "PRSIM M3 ölçümüne girer" koruması (a) "gövde içi yapısal izleri temizler (… `@ad` …)" diyor; D sınıfı veri sınırının bir koşulu. Yaygın bir yazımı açık bırakmak bu korumayla çelişiyor. PRSIM staging bu ONAY'a bağlı (BLOCKERS 161).

**Karar (koordinatör; önerilen A):**
- **A (önerilen).** Dekoratör istisnası yalnız sonraki boş olmayan satır `def`, `async def`, `class` ya da başka bir `@…` dekoratör satırıysa geçerli olsun (ya da satır bir kod çitinin içindeyse, zaten çit içi). Etki: `@property`/`@pytest.fixture` + `def` aynen kalır; seslenme satırı `[USER]` olur. Yanlış maske: düzyazıda kodsuz yazılmış tek bir dekoratör satırı (zararsız, fazla maske). Bir-iki satırlık değişiklik ve test.
- **B.** Mevcut davranış kalsın; risk koruma (a)'nın istisnası olarak KARARLAR'a ve runbook'a yazılsın. Etki: PRSIM gövdelerindeki tek satırlık seslenmeler maskesiz kalır; kullanıcı kararı gerektirir (D sınıfı sınır).

## MINOR-1 · R10 SQL kuralları düzyazıda login'i açık bırakıyor — CONFIRMED (konteyner)

- `SQL_ASSIGN = \s*=(?!=)` satırın neresinde olursa olsun `@ad =`'i değişken sayıyor: `Sorumlu: @ahmet.yilmaz = onaylayan` ve `@ahmet.yilmaz => devraldı` (ok işareti, `=>`) maskesiz.
- Büyük harfli `SELECT @ahmet.yilmaz ekibinden` de maskesiz. Bu PR'da kabul edilmiş risk; büyük harfli düzyazı nadir.

**Düzeltme:** atama istisnası `=`'den sonra `>` olmamalı (`=(?![=>])`) ve satırda büyük harfli bir SQL anahtar sözcüğü bulunmalı (`DECLARE|SET|SELECT|…`). T-SQL'de `@x = 1` hemen her zaman böyle bir satırda olur.

## NOTE

1. Jira `{{…}}` içindeki `@ad` maskelenmiyor (K-19R2-0001 kararı, runbook'ta); `_heading` (Jira özeti) için de aynı.
2. `_heading` da `DECORATOR_LINE`'dan geçiyor: yalnız `@ahmet.yilmaz` olan bir Jira özeti maskesiz (MAJOR-2 A ile kapanır; özette bir sonraki satır yok, A kuralı burada "maskele" demeli).
3. `@echo` istisnası satır başı biçimine bağlı değil: herhangi bir yerdeki `@echo` aynen kalıyor. `echo` adlı bir login olasılığı düşük (V2).
4. Probe ilk hâlinde host Python 3.9 ile, konteyner açılınca 3.12 ile koşuldu; sonuçlar aynı.

## Güvenlik turu

- **Kişi verisi (PRSIM M3 koruması a):** MAJOR-1 (çit terslemesiyle düzyazı maskesiz, gerileme) ve MAJOR-2 (tek satırlık seslenme) PRSIM staging öncesi kapanmalı; ikisi de `@login`'i ham bırakıyor. E-posta, telefon, TC, IBAN ve kart maskesi FFCore ingest'te ayrı katmanda; bu dal onlara dokunmuyor.
- **R11 fail-loud:** doğru; bilinmeyen FFCore reddi artık "NER gerekmez" sayılmıyor.
- **Ağ:** testler ve probe `--network none`; sunucuya bağlantı yok.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| Hedefli test (`-k 19`; R1/R3/r2 dahil), konteyner, `--network none` | 169 passed | `state/evidence/19r2-r1-targeted.log` |
| Tam takım, konteyner | 634 passed, 3 failed (bs4, master'da aynı, ENV-138), 2 skipped | `19r2-r1-full.log` |
| ruff check + format | temiz | `19r2-r1-lint.log` |
| Sentetik metin probe'u (host 3.9, sonra konteyner 3.12) | 33 durum; 10 açılma (MAJOR-1: 4, MAJOR-2: 1, MINOR-1: 3, NOTE-1 kararı: 1, 4'lü çit: MAJOR-1'e dahil) | `19r2-r1-probe.log`, `19r2-r1-probe-container.log`, `state/reviews/19r2-dis-inceleme-r1-probe.py` |
| PRSIM staging | NOT_RUN (BLOCKERS 161: bu ONAY'a kadar koşulmaz) | — |

## İşçiye kısa liste (DUZELT önerisi)

1. MAJOR-1: CommonMark çit tanıma (uzunluk, bilgi dizesi, aynı karakterli ve en az aynı uzunlukta kapanış) + 6 test.
2. MAJOR-2: koordinatör kararına göre A (sonraki satır kuralı, `_heading` dahil) ya da B (KARARLAR ve runbook).
3. MINOR-1: `=(?![=>])` ve satırda büyük harfli SQL sözcüğü koşulu + iki test.
4. Runbook "bilinen sınırlar" çit tanımı cümlesi.
