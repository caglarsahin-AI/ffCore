# paycoreLLM fix/19r2-dis-inceleme r2 inceleme (delta, r1 DEGISIKLIK kapanışı)

- **SHA:** paycoreLLM e409786c0bc440d8cb810d25aa658623f979e248 (1dce5e5 üstüne 3 commit: e02299a MAJOR-1 CommonMark çit, 575c7b3 MAJOR-2 A + MINOR-1, e409786 runbook; 3 dosya +160/-37)
- **İstek:** K-19R2-0008 · Cevap: R-19R2-0002 (r1) · Karar: KARARLAR "PRSIM staging `@` istisnaları daraltıldı"
- **Yöntem:** `git archive e409786` (karşılaştırma için `530be09`) kopyası; konteyner `--network none`; yığın yok. `.env`, `data/**`, `eval/results/**` okunmadı. PRSIM staging koşulmadı.
- **Koşu zamanı:** 17:11-17:12 (Docker açık)
- **Karar: ONAY** — BLOCKER 0, MAJOR 0, MINOR 0, NOTE 2

## r1 bulgularının kapanışı

| r1 | Durum | Kanıt (`state/evidence/19r2-r2-probe-container.log`, 43 durum) |
|---|---|---|
| MAJOR-1 CommonMark çit | **KAPANDI** | ```` ``` sql ````, ```` ```js title=a ````, ```` ```` ```` içinde ```` ``` ````, `~~~~` içinde `~~~`: hepsinde arkadaki düzyazı login'i `[USER]` (r1'de dördü açıktı). r1'in diğer çit örnekleri yeşil kalıyor: dış rapor girdileri, kapanmamış çit, tek backtick, `{noformat}` tek satır, `~~~`, girintili, CRLF, çit içinde çit, `{code:sql}…{code}`, `{code:title=A b\|…}`. Kod: açıcı 3+ backtick/tilde + herhangi bir bilgi dizesi (backtick çitinde bilgi dizesinde backtick yok); kapanış aynı karakter, uzunluk ≥ açılış, bilgi dizesiz. |
| MAJOR-2 karar A | **KAPANDI** | `@ahmet.yilmaz` + düzyazı → `[USER]`; boş satır + düzyazı → `[USER]`; metnin sonundaki login → `[USER]`; alt alta iki login → ikisi `[USER]`; `@ahmet.yilmaz` + `definitely…` → `[USER]` (`\b` ile `def` değil). Korunanlar: `@pytest.fixture` + `def`; zincir (`@pytest.fixture` / `@pytest.mark.slow` / boş satır / `def`); `@dataclass` + `class`; `@app.get('/x')` + `async def`. `_heading("@ahmet.yilmaz")` → `[USER]`. |
| MINOR-1 SQL ataması | **KAPANDI** | `Sorumlu: @ahmet.yilmaz = onaylayan` → `[USER]`; `@ahmet.yilmaz => devraldı` → `[USER]`; `@ali.veli = 1` (SQL'siz) → `[USER]`; `declare @ali.veli = 1` (küçük harf) → `[USER]`; `DECLARE @x = 1` ve `SET @x = 1` aynen. |
| Kalan açılmalar | **yalnız kabul edilenler** | 43 durumda 2 LEAK: `{{@ali.veli}}` (K-19R2-0001: satır içi kod sayılır) ve `SELECT @ahmet.yilmaz ekibinden` (büyük harfli SQL sözcüğünden sonra; runbook'ta kabul edilen sınır). Başka açılma yok. Aynı probe 530be09'da 9 açılma veriyor (`19r2-r2-probe-base-530be09.log`). |
| Runbook "bilinen sınırlar" | **KAPANDI** | CommonMark çit (bilgi dizesi, 4'lü çit), daraltılmış dekoratör kuralı, kodsuz tek dekoratör satırının maskelenmesi (kabul edilen fazla maske), `=>`, küçük harfli SQL ve `SELECT` düzyazısı sınırı kodla birebir. |

## NOTE

1. KARARLAR "başka bir `@…` dekoratör satırı" diyor; kod (`_decorators`, `marks[following]`) ve runbook o satırın da dekoratör sayılmasını (zincirin `def`/`class` ile bitmesini) istiyor. Kod daha dar ve daha güvenli: alt alta iki login satırı ikisi de maskeleniyor. KARARLAR cümlesi koda göre netleştirilebilir.
2. `DEFINITION_LINE` İngilizce düzyazıda `class`/`def` ile başlayan satırı da tanım sayar (`@ahmet.yilmaz` + `class notes …`): seslenme açık kalır. Türkçe gövdede olasılık çok düşük; bilgi.

## Güvenlik turu

- **PRSIM M3 koruması (a):** `@ad` izleri r1'in bütün açılma biçimlerinde temizleniyor. Kalan iki açılma koordinatör kararıyla kabul edilen sınır ve runbook'ta yazılı.
- **Ağ:** testler ve probe `--network none`; sunucuya bağlantı yok.
- **PRSIM staging:** bu ONAY'la BLOCKERS 161 koşulu sağlanır; staging kararı ve dış PayCore r3'e SHA koordinatörde.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| Hedefli (`-k 19`; R1/R3/19r/19r2), konteyner | 191 passed | `state/evidence/19r2-r2-targeted.log` |
| Tam takım, konteyner | 656 passed, 3 failed (bs4, master'da aynı, ENV-138), 2 skipped | `19r2-r2-full.log` |
| ruff check + format | temiz | `19r2-r2-lint.log` |
| Probe (43 durum) e409786 / 530be09 | 2 (kabul edilen) / 9 açılma | `19r2-r2-probe-container.log`, `19r2-r2-probe-base-530be09.log`, `state/reviews/19r2-dis-inceleme-r1-probe.py` (r2 durumları eklendi) |
| PRSIM staging | NOT_RUN (bu turun konusu değil) | — |

## Sonuç

ONAY. paycoreLLM master merge'ü, PRSIM staging serbestliği ve dış PayCore r3'e SHA koordinatörde.
