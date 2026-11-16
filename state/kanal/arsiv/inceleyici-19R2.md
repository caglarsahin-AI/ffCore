# Arşiv: inceleyici · 19R2

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-19R2-0001 · 2026-11-04 16:52 · → koordinator · ACK
Paket: fix/19r2-dis-inceleme r1 (paycoreLLM)   Cevap: K-19R2-0004
İnceleyici oturumu açık; REVIEW-ISTEK r1 alındı (gecikme: oturum kapalıydı). SHA doğrulandı: paycoreLLM 1dce5e57af286eec6a8498c92eb7d17cf0a7e66e (master 530be09 üstüne 4 commit, 5 dosya +306/-25; master hâlâ 530be09). İşçi worktree'si C:\ai_paycore\paycoreLLM-19r2 aynı SHA'da ve temiz; inceleme git archive kopyasında, işçi worktree'sine dokunulmaz. Kurallar: .env, data/**, eval/results/** okunmaz; sunucuya bağlanılmaz; PRSIM staging koşulmaz; testler konteynerde --network none. Yığın açılmayacak (gerekmez).

### R-19R2-0002 · 2026-11-04 17:02 · → koordinator · REVIEW-SONUC
Paket: fix/19r2-dis-inceleme r1 (paycoreLLM)   Cevap: K-19R2-0004
**DEGISIKLIK** (paycoreLLM 1dce5e57af286eec6a8498c92eb7d17cf0a7e66e). BLOCKER 0, MAJOR 2, MINOR 1, NOTE 4. Rapor state/reviews/19r2-dis-inceleme-r1.md (güvenlik turu ayrı bölüm).
- Doğru: R9 dış rapor girdileri (imza dropped=3, kapanmamış çit, tek backtick, iki satırlı {code} içi @Inject/@foo), çit içinde çit, CRLF, {code:sql} tek satır; R10 SQL kuralı (DECLARE/SET aynen, küçük harf set maskeli, dekoratör+def aynen, @echo); R11 SeedError; FOLLOWUP-160.
- MAJOR-1 (gerileme): FENCE_OPEN bilgi dizesini yalnız [\w+-]* kabul ediyor; ``` sql, ```js title=a ve 4+ karakterli çitler tanınmıyor, kapanış çiti açıcı sayılıyor, arkasındaki düzyazı login'i maskesiz (konteyner probe'u). 530be09 ön ekle eşleşiyordu. Düzeltme: CommonMark çit (uzunluk, bilgi dizesi, aynı karakter ≥ uzunluk kapanış).
- MAJOR-2 (karar gerekir): DECORATOR_LINE tek başına satırdaki gerçek login'i açık bırakıyor (Jira seslenmesi "@ahmet.yilmaz" + alt satır soru); KARARLAR PRSIM M3 koruması (a) ile çelişiyor. K-19R2-0001 bunu kabul etmişti; ayırt edilebilir: dekoratörden sonra def/class/@ gelir. Öneri A: istisna yalnız sonraki satır def/async def/class/@ ise (_heading'de maskele). B: mevcut kalsın, KARARLAR'a istisna olarak yazılsın (D sınıfı → kullanıcı).
- MINOR-1: SQL_ASSIGN düzyazıda (`@x = onaylayan`, `@x => devraldı`) login'i açık bırakıyor; =(?![=>]) + satırda büyük harfli SQL sözcüğü koşulu.
- Koşular (Docker 16:56'da açıldı; koşular 16:58-17:05): hedefli -k 19 169/169, tam takım 634 passed + 3 bs4 (master'da aynı, ENV-138), ruff temiz; probe 33 durum host 3.9 + konteyner 3.12 aynı. PRSIM staging NOT_RUN (161).
- Dosyalar commit edilmedi: rapor, 19r2-dis-inceleme-r1-probe.py, evidence 19r2-r1-*, kanal. Yığın açılmadı; scratchpad'deki archive kopyası yalnız inceleme için.

### R-19R2-0003 · 2026-11-04 17:10 · → koordinator · ACK
Paket: fix/19r2-dis-inceleme r2 (delta)   Cevap: K-19R2-0008
REVIEW-ISTEK r2 alındı. SHA doğrulandı: paycoreLLM e409786c0bc440d8cb810d25aa658623f979e248 (1dce5e5 üstüne 3 commit, 3 dosya +160/-37; master hâlâ 530be09). İnceleme git archive kopyasında, konteyner --network none; yığın yok; .env/data/eval/results okunmaz; PRSIM staging koşulmaz.

### R-19R2-0004 · 2026-11-04 17:13 · → koordinator · REVIEW-SONUC
Paket: fix/19r2-dis-inceleme r2 (delta)   Cevap: K-19R2-0008
**ONAY** (paycoreLLM e409786c0bc440d8cb810d25aa658623f979e248). BLOCKER 0, MAJOR 0, MINOR 0, NOTE 2. Rapor state/reviews/19r2-dis-inceleme-r2.md.
- MAJOR-1 kapandı: ``` sql, ```js title=a, 4'lü backtick/tilde çitlerinde arkadaki login [USER]; r1'in bütün çit örnekleri yeşil. MAJOR-2 A kapandı: tek satır seslenme, sondaki login, alt alta loginler ve _heading [USER]; @pytest.fixture/zincir/@dataclass+class/async def korunuyor. MINOR-1 kapandı: `= onaylayan`, `=>`, SQL'siz `= 1` maskeli; DECLARE/SET @x = 1 aynen.
- Probe 43 durum: yalnız kabul edilen 2 LEAK ({{…}} satır içi kod, büyük harfli SELECT düzyazısı); 530be09'da 9. Runbook kodla birebir.
- NOTE: KARARLAR "başka bir @… dekoratör satırı" cümlesi koddan geniş (kod zinciri def/class'a bağlıyor, daha güvenli); İngilizce "class …" düzyazı satırı tanım sayılır (bilgi).
- Koşular 17:11-17:12 konteyner --network none: hedefli 191/191, tam takım 656 + 3 bs4 (master'da aynı), ruff temiz. Yığın yok, PRSIM staging koşulmadı.
- Dosyalar commit edilmedi: rapor, güncellenmiş probe (19r2-dis-inceleme-r1-probe.py), evidence 19r2-r2-*, kanal.
