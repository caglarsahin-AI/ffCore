# Review fix/ajan-hooklari r1 · ajan kurallarının PreToolUse hook'u ile zorlanması
SHA: 3ab062dc5447c9f1fed9a1bd2a32108c2689898b · Sonuc: DEGISIKLIK · Bulgu: B0 M2 m2 N8

- **İncelenen tam SHA:** `3ab062dc5447c9f1fed9a1bd2a32108c2689898b` (`fix/ajan-hooklari`, worktree `.worktrees/fix/ajan-hooklari`; inceleme salt okunur, worktree'de değişiklik yok). `main...HEAD`: 6 commit (test → test → feat → test → feat → docs), 9 dosya, +1419/−88. state, backend ve frontend değişikliği yok.
- **İstek:** K-HOOK-0004 REVIEW-ISTEK (9 madde). Kararlar: KARARLAR "Ajan kuralları hook ile zorlanır…", "fix/ajan-hooklari plan kararları" (S1-S10 ve ekler), K-HOOK-0002 (push kuralı), tur kuralı K-GEN-0012.
- **Yöntem:** yığın açılmadı, ağ kullanılmadı. Önce diff okundu (guard, settings, testler, handbook, BASLATMA, docs/takim 9.2, PR notu). Ardından host `py -3.12` ile `pytest tests/hooks` koşuldu. Son olarak guard, `.claude/settings.json`'daki komut biçimiyle (`py -3.12 -c "…import ffcore_guard…" <yol>`) 59 örnek JSON ile doğrudan çağrıldı. Bu çağrılarda `FFCORE_MAIN_ROOT` geçici bir köke ayarlandı, gerçek `hook-guard.log` kirlenmedi. Betik `state/evidence/fix-ajan-hooklari-r1-rv-probe.py.txt`, çıktı `-probe.log`.
- **Karar: DEGISIKLIK**
- **Sayılar:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NOTE 8
- **MAJOR sınıfları:** `kapi-tee-kapsami` (MAJOR-1), `kayit-secret-sizintisi` (MAJOR-2). İkisi de bu pakette ilk tur, tekrar yok.

## Kontrol listesi (K-HOOK-0004)

| # | Madde | Sonuç | Kanıt |
|---|---|---|---|
| 1 | Kural tablosu a-i: engelle/serbest çiftleri | **Büyük ölçüde doğru.** `.env` engellenir; `.env.test` ve `.env.example` serbest (B01-B06). PayCore POSIX ve Windows yolu engellenir (B07-B08). `compose build` engellenir, `build --pull=false` serbest; `up --build` ve `up` (`--pull never` yoksa) engellenir (B10-B13). Yığın sayımı gerçek `docker compose ls` ile serbest döndü (B14). `make test`, `make -C backend test` ve `pytest` tee'siz engellenir, tee'li ve `--co` serbest (B15-B19). Tek yazar tablosu, `oturumlar.json` rol kaynağı ve bozuk JSON → engel (F03-F18). Worktree `state/` engellenir (F11). Arşiv koordinatöre ait (F08). **Açıklar:** projenin asıl kapı biçimi olan `docker compose … run … tools make test` tee'siz **serbest** (B20) → **MAJOR-1**. `.ENV` yazımı Bash'te de Write'ta da serbest (B04, F02) → MINOR-1. | `-probe.log` B01-B21, F01-F20 |
| 2 | Push kuralı | **Doğru.** Koordinatör + önek bayrağı serbest (P02). Koordinatör bayraksız, bayrak yalnız ortamda, `export` + push ve `git -C x push` engellenir (P03, P05, P06, P08). isci-a + bayrak ve rol yok engellenir (P04, P01). `oturumlar.json`'da inceleyici + bayrak engellenir (F18). `bash -c "git push"` serbest (P07): KARARLAR'da bilinen sınır, ama belge bunu yanlış anlatıyor → MINOR-2. | `-probe.log` P01-P08, F18 |
| 3 | warn/block, S9, bozuk stdin | **Doğru.** warn: çıkış 0; stderr'e mesaj; stdout'a `{"systemMessage": "(warn) FFCORE-GUARD [ENV] …"}`; kayıtta `warn` (W01). block: çıkış 2 (B01). Bilinmeyen kip (`Warn`) → block + uyarı (W04). Bozuk stdin, JSON dizisi ve boş stdin → 2 + `GUARD-HATA` kaydı; warn'da 0 (W02, W03, W05, W06). `.claude/settings.json` düzenlemesi serbest (F19). Guard'ın iç hatasında `.claude/hooks/**` istisnası testte var (`test_guard_internal_error_*`). | `-probe.log` W01-W07, F19 |
| 4 | `settings.json`: deny, mutlak yol, `$CLAUDE_PROJECT_DIR`, matcher | Biçim belgeyle tutarlı (aşağıdaki NOTE'lar). **`Write(**/.env)`:** Claude Code belgesine göre `Edit(…)` kuralı dosya düzenleyen bütün yerleşik araçlara (Write, MultiEdit, NotebookEdit) uygulanır. Bu yüzden ayrı satır gerekmez; çevrimdışıyım, belgeye karşı canlı doğrulanmadı (N2). **`//c/…`:** belgeye göre Windows yolları `/c/Users/…` POSIX biçimine çevrilir ve `//` kök mutlak yoldur, yani biçim doğru. Gerçek oturumda Read ret mesajı görülmedi, **doğrulanmadı** (N2). paycoreLLM `.env` için `Edit` deny yok; `Read` var (MINOR-1). **`$CLAUDE_PROJECT_DIR`:** oturumun açıldığı kökü gösterir. Worktree'de açılan oturum worktree'nin guard kopyasını koşar, `main_root()` `.worktrees` üstünü bulur. Gerçek kanıtta kayıt ana `state/evidence`'a düştü, doğru. Sonucu N1'de. Matcher'lar `Bash` ve `Edit\|Write\|MultiEdit\|NotebookEdit`; ikisi de `test_settings_*` ile test edilmiş. | diff; `hook-real-call.log` |
| 5 | Gerçek kanıt + doğrudan çağrı | Gerçek oturumda Bash hook tetiklendi; ana `hook-guard.log` 19:09:21 `warn - Bash ENV`. Doğrudan çağrıda warn çıktısı (çıkış 0, `systemMessage` JSON) ve block çıktısı (çıkış 2, stderr) doğrulandı. **Kalan, doğrulanmadı:** `systemMessage`'ın kullanıcı arayüzünde görünmesi, `Read` deny reddi, `//c/` biçimi. Üçü warn gününde tek denemeyle kapanır (N2). | `-probe.log` W01/B01; `hook-real-call.log` |
| 6 | Fail-loud, kayıt satırında secret | Hata yolları sessiz değil. `docker compose ls` hatası → engel (`test_stack_count_failure_blocks`). Bozuk `oturumlar.json` → engel (F16). Kayıt yazılamazsa stderr'e yazılır, karar değişmez (kabul). **Ama kayıt satırı komutun ilk 120 karakterini maskesiz yazıyor:** `git push https://u:<token>@…` ve `OPENAI_API_KEY=<değer> make test` değerleri olduğu gibi kayda geçti (S01, S02). Dosya `state/evidence/` altında, yani commit edilen kanıt yolunda → **MAJOR-2**. | `-probe.log` S01-S03 ve kayıt dökümü |
| 7 | handbook/BASLATMA/docs tutarlılığı | Push kuralı dört yerde aynı (SECURITY tablosu, MULTI_AGENT "PR ve merge", BASLATMA 1 ve 5, docs 9.2). Arşiv ve `oturumlar.json` tek yazar satırı tabloda. `FFCORE_ROL` ve `oturumlar.json` adımı BASLATMA 5a'da, işçi ACK'inde kimlik satırı var. **Tutarsız:** ENVIRONMENT "içerik yok" diyor, oysa MAJOR-2'ye göre secret yazılabiliyor. docs 9.2 "`bash -c` içindeki düz metin yakalanır" diyor; bu yalnız ENV ve PAYCORE için doğru (MINOR-2). Kapı kuralının compose içi biçimi belgede yok (MAJOR-1). | diff |
| 8 | NOTE: `scripts/context_budget.py` | N7 | main `scripts/context_budget.py` |
| 9 | Tur kuralı | MAJOR'lara sınıf adı verildi (başlıkta). | — |

Kapı: `py -3.12 -m pytest tests/hooks -q` **101 passed**, exit 0, 77,6 s → `state/evidence/fix-ajan-hooklari-r1-rv-tests.log` (HEAD satırlı). İşçinin 101 sonucuyla aynı.

## MAJOR

### MAJOR-1 · `kapi-tee-kapsami`: projenin kapı biçimi KAPI kuralından kaçıyor
**Bulgu.** `ffcore_guard.py:290` `is_gate_command` yalnız ilk sözcüğü `make` ya da `pytest` olan parçalara bakıyor. Projede kapılar konteynerde koşar: Makefile başlığı `docker compose run --rm tools make <hedef>`, ENVIRONMENT "Kapı komutları", inceleyici ve main kapısı tarifleri hep `docker compose -p … --profile tools run --rm --no-deps -e DEPLOY_PROFILE=… tools make test` biçiminde. Bu biçimde ilk sözcük `docker` olduğundan kural çalışmıyor. Probe B20'de `docker compose -p review1 --env-file .env.test --profile tools run --rm --no-deps -e DEPLOY_PROFILE=airgap tools make test` tee'siz verildi, sonuç **çıkış 0, kayıt yok**. KARARLAR maddesi "`make lint|test|test-int|smoke` yalnız `tee` ile" diyor, PR kabul satırı 6 "geçti" diyor; kuralın asıl hedefi olan kapı koşusu (K-05a-0011 olayı da kapı koşusuydu) kapsanmıyor. Testler yalnız host biçimini (`make test`) sınıyor.

**Beklenen düzeltme:**
1. `check_compose`'daki alt komut çözümlemesinden yararlan. Alt komut `run` ya da `exec` ise, seçenekler (`--rm`, `--no-deps`, `-e K=V`, `--entrypoint`, `-w`, `-u`, `--name` gibi değer alanlar) ve servis adı atlandıktan sonra kalan belirteçleri `is_gate_command`'a ver. Aynı boru hattında `tee` varsa serbest olsun.
2. `sh -c "<metin>"` ve `bash -c "<metin>"` içini de aynı yoldan özyinelemeyle denetlemek ucuz. Bu MINOR-2'yi de kapatır.
3. Kırmızı testler (engel/serbest çiftleri):
   - `docker compose … run --rm --no-deps -e DEPLOY_PROFILE=airgap tools make test` → engel.
   - Aynı komut `2>&1 | tee state/evidence/x.log` ile → serbest.
   - `docker compose run --rm tools make lint` → engel.
   - `docker compose run --rm tools make seed` → serbest (kapı hedefi değil).
   - `docker compose exec backend pytest -q` → engel.
4. e2e (`npx playwright test`) KARARLAR listesinde yok. Eklenip eklenmeyeceği koordinatör kararı; ben bulgu saymıyorum.

### MAJOR-2 · `kayit-secret-sizintisi`: kayıt satırı komuttaki secret'ı maskesiz yazıyor
**Bulgu.** `ffcore_guard.py:492` `log_line`, komutun ilk 120 karakterini olduğu gibi `state/evidence/hook-guard.log`'a yazıyor. Probe kaydı:
```
block	isci-a	Bash	PUSH	git push https://probeuser:ghp_PROBEFAKETOKEN0000@github.com/o/r.git main
block	inceleyici	Bash	KAPI	OPENAI_API_KEY=sk-PROBEFAKE0000 make test
```
(değerler sahte). Bu iki biçim gerçekçi; ikisi de kuralın tetiklendiği komutlar. `-H "Authorization: Bearer …"` (S03) 120 karaktere sığarsa o da yazılır. Dosya commit edilen kanıt yolunda; dalga raporu bu dosyayı sayıyor. SECURITY_AND_PERMISSIONS "log … secret içermez" kuralına, ENVIRONMENT'taki "içerik yok" vaadine ve brief'teki "(içerik yok …)" koşuluna aykırı. Tur kuralı (c) güvenlik bulgusunda yok, bu yüzden MAJOR.

**Beklenen düzeltme:** `log_line` içinde, kesmeden **önce**, şunlar maskelensin:
- URL kimliği: `(\w+://)[^/\s@]+@` → `\1***@`
- Adı `KEY|TOKEN|SECRET|PASS|PASSWORD|AUTH|CREDENTIAL` içeren atamalar ve `--opt=` biçimi: `\b([A-Za-z0-9_-]*(?:key|token|secret|pass(?:word)?|auth|credential)[A-Za-z0-9_-]*)=\S+` (IGNORECASE) → `\1=***`
- `Authorization:\s*\S+(\s+\S+)?` ve `Bearer\s+\S+` → `Authorization: ***`

SECURITY'deki merkezi sanitizer desenleri (`Authorization`, `X-On-Behalf-Of`, `api_key`, `password`, `token`) referans alınabilir.

Kırmızı testler: bu üç biçimin her biri için kayıt satırında sahte değer **yok**, kural adı ve komutun başı (`git push`, `make test`) **var**. ENVIRONMENT satırı "maskeli" diye güncellensin.

## MINOR

### MINOR-1 · `.env` kuralı büyük/küçük harf ve paycoreLLM Edit açığı
Windows dosya sistemi harf duyarsız, `.ENV` aynı dosyadır. `ENV_RE` (`:55`) ve `check_write` (`:403`) harfe duyarlı: `cat .ENV` ve `Write …\.ENV` serbest (B04, F02). Ayrıca `settings.json`'da `Edit(//c/ai_paycore/paycoreLLM/.env)` yok; `**/.env` göreli kalıbı proje köküne bağlı, paycoreLLM'i kapsamaz. Guard bunu `ENV` kuralıyla yakalıyor, ama `env.FFCORE_GUARD_MODE=warn` iken yalnız uyarıyor; warn gününde PayCore `.env`'ine Edit/Write'ın tek engeli kalmıyor. **Öneri:**
- `ENV_RE`'ye `re.IGNORECASE`; `check_write`'ta `.lower() == ".env"`. `.Env.test` yine serbest kalmalı.
- deny'a `Edit(//c/ai_paycore/paycoreLLM/.env)`.
- Testler: `cat .ENV` engel, `.Env.Test` serbest, `Write .ENV` engel.

### MINOR-2 · `bash -c` sınırı belgede yanlış anlatılıyor
docs 9.2 "Bilinen sınırlar" ve PR notu "Kalan riskler" diyor ki "`bash -c` içindeki düz metin yakalanır". Bu yalnız tüm metin üzerinde çalışan `ENV` ve `PAYCORE` regex'leri için doğru. `bash -c "git push origin main"` isci-a rolüyle **serbest** (P07). `PROSES-175`, `YIGIN` ve `KAPI` de `bash -c` içinde çalışmaz. **Öneri:** MAJOR-1 madde 2'deki özyineleme yapılırsa cümle doğru olur. Yapılmazsa cümle "yalnız ENV/PAYCORE; push, compose ve kapı kuralları `bash -c` içinde çalışmaz" diye düzeltilsin.

## NOTE

1. **Guard'ı guard'lanan düzenleyebilir.** `$CLAUDE_PROJECT_DIR` worktree'yi gösterdiğinden, worktree'de açılan oturum kendi dalındaki guard kopyasını koşar. S9 istisnası `.claude/hooks/**` ve `.claude/settings.json` düzenlemesini serbest bırakıyor. Yani bir işçi kendi worktree'sinde guard'ı gevşetirse değişiklik aynı oturumda etkin olur. Bu kabul edilmiş bir tasarım (güvenlik ağı, kilitlenme yok). Öneri: koordinatörün PR-HAZIR doğrulamasına "`git diff main...HEAD -- .claude/` boş mu, değilse inceleme maddesi" satırı eklensin.
2. **Warn gününde kapatılacak üç doğrulama:**
   - (a) Kullanıcı arayüzünde `systemMessage` görünüyor mu.
   - (b) `Read` ile `C:\ai_paycore\paycoreLLM\data\<olmayan-dosya>` denemesi deny mesajı veriyor mu (`//c/` biçimi ve `paycoreLLM` harf duyarlılığı).
   - (c) Proje içindeki `.env` olmayan bir yolda değil, gerçek `**/.env` yolunda Write denemesi deny ile reddediliyor mu (`Edit` kuralının Write'ı kapsadığının kanıtı).

   Belgeye göre üçü de beklenen davranış; canlı kanıt yok.
3. **Gecikme:** doğrudan çağrılarda her çağrı ~1-2 s sürdü (probe zaman damgaları). Her Bash ve her yazma çağrısı bu kadar uzar; PR notunda yazılı, warn gününde gözlenmeli.
4. **Koordinatörün her kanala yazabilmesi (20bbd6b):** arşiv taşıması için gerekli ve MULTI_AGENT'ta yazılı. Bunun sonucu, koordinatör için kanal tek yazar kuralının hook düzeyinde açık olması. Kabul edilebilir, sadece görünür olsun diye not ediyorum.
5. **`.env` yanlış pozitifi:** `if [ -f .env ]` ve `grep '\.env' .gitignore` de tetikler. Gerçek kanıtta ilk satır tam olarak buydu. Bilinçli ve belgede yazılı; warn günü sayısı dalga raporunda.
6. **Göreli yol:** `check_write` göreli `file_path`'i (`state/WORK_QUEUE.md`) kök altında saymaz ve serbest bırakır. Claude Code yazma araçları mutlak yol istediği için pratikte risk düşük; fail-loud açısından göreli yol bir uyarı ya da engel olabilirdi.
7. **`scripts/context_budget.py` (koordinatör araç betiği istisnası):** okunur ve kısa. İki fail-loud açığı var:
   - `size()` olmayan dosya için 0 döner ve satır "ok" olur. Ad değişirse (ör. `FELSEFE_UYGULAMA.md` taşınırsa) ölçüm sessizce düşer.
   - `kararlar_index_size()` `## İndeks` başlığı bulunamazsa 0 döner. Başlık yeniden adlandırılırsa indeks hedefi her zaman "ok" görünür.

   Öneri: iki durumda da satır "YOK" yazılsın ve çıkış 1 olsun. Ürün koduna dokunmuyor; bulgu değil, bu tur NOTE.
8. **Kapsam ve dürüstlük:** PR notundaki "doğrulanmadı" işaretleri (systemMessage, Read deny, `//c/`) doğru. S10 sayımı (1/3 deneme, 0 model çağrısı) kanıtla tutarlı. Test/kod/docs ayrı commit, önce kırmızı test (`hook-tests-red*.log`).

## Kanıt
- `state/evidence/fix-ajan-hooklari-r1-rv-tests.log`: `pytest tests/hooks` 101 passed.
- `state/evidence/fix-ajan-hooklari-r1-rv-probe.log`: 59 doğrudan çağrı (girdi, ortam, çıkış kodu, stdout, stderr) ve geçici kökteki kayıt dosyası dökümü.
- `state/evidence/fix-ajan-hooklari-r1-rv-probe.py.txt`: probe betiği. Gerçek `hook-guard.log`'a yazmaz. Yalnız B14'te `docker compose ls` çalıştırır; yığın açmaz.
