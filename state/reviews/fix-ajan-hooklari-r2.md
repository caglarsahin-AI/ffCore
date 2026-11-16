# Review fix/ajan-hooklari r2 · delta turu (r1 MAJOR-1/2, MINOR-1/2)
SHA: 49b4343aa9b84840163c79639c396bb7859ad312 · Sonuc: ONAY · Bulgu: B0 M0 m3 N5

- **İncelenen tam SHA:** `49b4343aa9b84840163c79639c396bb7859ad312` (`fix/ajan-hooklari`, worktree `.worktrees/fix/ajan-hooklari`, salt okunur). Delta `3ab062d..49b4343`: 4 commit (test 6aeb07f, test c19fc8d, fix 54933c0, docs 49b4343). 6 dosya, +395/−41. state, backend ve frontend değişikliği yok.
- **İstek:** K-HOOK-0008 REVIEW-ISTEK (5 madde). r1 raporu `fix-ajan-hooklari-r1.md`, tur kuralı K-GEN-0012.
- **Yöntem:** yığın açılmadı, ağ kullanılmadı.
  - Önce delta diff'i okundu.
  - Host `py -3.12` ile `pytest tests/hooks` koşuldu.
  - r1 probe'u (59 çağrı) aynen tekrarlandı. Üstüne 45 yeni vaka eklendi: compose run/exec, e2e, `sh -c` düzeyleri, önek ve gruplama biçimleri, dengesiz tırnak, 12 maske biçimi ve `.env` harf varyantları.
  - Toplam 104 doğrudan çağrı, `.claude/settings.json`'daki komut biçimiyle. `FFCORE_MAIN_ROOT` geçici köke ayarlandı, gerçek `hook-guard.log`'a yazılmadı.
- **Karar: ONAY**
- **Sayılar:** BLOCKER 0 · MAJOR 0 · MINOR 3 · NOTE 5
- **MAJOR sınıfları:** yok. r1 MAJOR-1 `kapi-tee-kapsami` ve MAJOR-2 `kayit-secret-sizintisi` **kapandı**; tekrar yok, tur kuralı tetiklenmedi.

## Kontrol listesi (K-HOOK-0008)

| # | Madde | Sonuç | Kanıt (`-r2-rv-probe.log`) |
|---|---|---|---|
| 1 | MAJOR-1: compose run/exec, e2e, playwright, `sh -c` özyinelemesi | **Kapandı.** <br>• r1 B20 tekrarı (`… run --rm --no-deps -e DEPLOY_PROFILE=airgap tools make test`, tee yok) artık engel (R01); aynısı `2>&1 \| tee` ile serbest (R02). <br>• `--entrypoint`, `-w`, `-u`, `--name`, `-e` seçenekleri atlanıp servis bulunuyor (R03). <br>• `make seed` serbest (R04). `exec -T backend pytest` (R05), komutsuz `e2e` servisi (R06), `e2e sh -c "npx playwright test"` (R07) ve `make e2e` (R09) engel. <br>• Dıştaki `\| tee` iç kapıyı karşılıyor (R08). `run tools sh -c 'make test'` engel (R14). <br>• `bash -c "git push"` ve `bash -lc` işçi rolünde engel (R10, R11; r1 P07 artık 2). <br>• 3 düzey iç içe kabukta push engel (R12). **4. düzey sessiz geçiyor (R13) → MINOR-2.** | R01-R14, B20, B21, P07 |
| 2 | MAJOR-2: `mask_secrets` | **Kapandı.** Maske kesmeden önce uygulanıyor; kural adı ve komut başı kayıtta kalıyor. Maskelenen biçimler: <br>• URL kimliği: `https://***@`, `postgresql://***@` (M01, M06) <br>• `OPENAI_API_KEY=***` (M02) <br>• IGNORECASE ile `db_password=***` (M05) ve `-e POSTGRES_PASSWORD=***` (M07) <br>• `--api-token=***` (M04) <br>• `Authorization: ***`, küçük harf `authorization: bearer` dahil (M03, M08) <br>• 120 karakter sınırındaki secret: maskeli kesiliyor (M11) <br><br>Maskelenmeyenler: `--token abc` (M09; belgede sınır olarak yazılı), `curl -u user:pass` (M12) ve JSON gövdesindeki `"token":"…"` (M10) → MINOR-3. | M01-M12 ve kayıt dökümü |
| 3 | MINOR-1: `.ENV` ve deny | **Kapandı.** `cat .ENV` ve `cat .Env` engel, `.Env.Test` serbest (E01-E03, B04). `Write .ENV` engel, `Write .Env.test` serbest (E04, E05, F02). deny'a `Edit(//c/ai_paycore/paycoreLLM/.env)` eklendi; handbook ve docs'ta karşılığı var. | E01-E05 |
| 4 | Tırnağa duyarlı ayırıcı | Tırnak içindeki `&&` tek komut kalıyor (R24). `\|&` tee'li serbest (R25). `>\|` ayırıcı sayılmıyor ve tee yoksa engel (R26). `2>&1 &` engel (R27). Dengesiz tek ya da çift tırnakta çökme yok, `GUARD-HATA` da yok; çıkış 0 (R22, R23). Bash bu metni sözdizimi hatasıyla koşmayacağı için zarar yok. Fail-loud açısından değerlendirmesi N2'de. | R22-R27 |
| 5 | docs/handbook uyumu | ENVIRONMENT KAPI satırı, docs 9.2 tablosu, "Kip ve kayıt" maske paragrafı ve "İç içe komutlar" davranışla tutarlı. r1 MINOR-2 kapandı: `bash -c` cümlesi artık doğru. **Eksik:** "Bilinen sınırlar" listesinde yaygın önek ve gruplama biçimleri (MINOR-1), 4. düzey davranışı (MINOR-2) ve JSON gövdesi maskesi (MINOR-3) yok. | diff |

Kapı: `py -3.12 -m pytest tests/hooks -q` **136 passed**, exit 0, 94,3 s → `state/evidence/fix-ajan-hooklari-r2-rv-tests.log` (HEAD satırlı). İşçinin ve koordinatörün sonucuyla aynı.
r1 regresyonu: 59 r1 vakasının hepsi beklenen sonucu verdi. r1'de açık olan B20, B21, B04, F02 ve P07 artık 2 dönüyor.

## MINOR

### MINOR-1 · Yaygın önek ve gruplama biçimleri push ve kapı kuralını atlatıyor; belgede yok
İşçi rolünde şu push biçimlerinin hepsi çıkış 0 verdi:
- `bash -o pipefail -c 'git push …'` (R15): `shell_inner` değer alan `-o pipefail`'da duruyor
- `env FOO=1 git push …` (R16)
- `command git push …` (R17)
- `echo $(git push …)` (R19)
- `{ git push …; }` (R20)

`time make test` de tee'siz serbest (R18). `(git push)` ise yakalanıyor (R21).

KARARLAR hook'u "güvenlik ağı, sandbox değil" diye kabul ediyor, bu yüzden MAJOR değil. Ama bu biçimler "değişkenle kurulan komut" değil, düz yazılmış komutlar ve 9.2 "Bilinen sınırlar" listesinde yoklar.

**Öneri (ucuz):**
- `strip_assignments` yanında bir sarmalayıcı listesi soyulsun: `env [-i] [K=V]…`, `command`, `exec`, `time`, `nice`, `nohup`.
- `shell_inner`, `-o <değer>` ve `-O <değer>` çiftlerini atlasın.
- `{` belirteci baştan atılsın.
- `$(…)` ve ters tırnak içi `split_pipelines` ile ayrıca denetlensin, ya da yapılmayanlar "Bilinen sınırlar"a yazılsın.

### MINOR-2 · 4. iç içe düzey sessizce geçiyor (fail-loud)
`check_tokens` `depth >= MAX_NESTING` olunca iç komuta inmeden dönüyor. `sh -c 'sh -c "sh -c \"sh -c git\ push\""'` işçi rolünde çıkış 0 verdi ve kayıt düşmedi (R13). CLAUDE.md fail-loud ilkesine göre sınır aşımı sessiz serbest olmamalı.

**Öneri:** sınırda hâlâ `shell_inner` ya da `compose_service_command` bir iç komut buluyorsa ayrı bir kural döndürülsün (ör. `GUARD-DERINLIK` "iç içe komut 3 düzeyi aşıyor; denetlenemedi"), engel olsun ve testi yazılsın. 4 düzey pratikte nadir, maliyet bir satır.

### MINOR-3 · Maskenin kalan iki biçimi
`curl -u probe:<parola>` (M12) ve JSON gövdesi `-d '{"token":"<değer>"}'` (M10) kayda maskesiz girdi. Belgedeki "boşlukla ayrılmış değer maskelenmez" cümlesi M12'yi kapsıyor, M10'u kapsamıyor. Kayıt dosyası commit edilen kanıt yolunda olduğu için not ediyorum. Yalnız `.env`/kapı/push tetiklenince ve bu biçimler birlikte yazılırsa sızar; olasılık düşük, MAJOR değil.

**Öneri:** iki desen eklensin ve test edilsin:
- `(-u|--user)\s+[^\s:]+:\S+` → `\1 ***`
- `"(token|secret|password|api_key|key)"\s*:\s*"[^"]*"` → `"\1":"***"`

Eklenmezse 9.2 sınır cümlesine "JSON gövdesi ve `-u user:pass`" yazılsın.

## NOTE

1. **Dışarıdaki tee içteki tail'i örtüyor:** `sh -c 'make test | tail -5' | tee x.log` serbest (R28). Kayda yalnız son 5 satır girer; K-05a-0011'in kaçınmak istediği durum bu. Pratikte nadir; kural "dışarıdaki tee iç kapıyı karşılar" diye yazılı olduğundan bulgu değil.
2. **Dengesiz tırnak:** ayırıcı çökmüyor ve çıkış 0 dönüyor (R22, R23). Bash bu komutu koşmayacağı için güvenlik etkisi yok. Ama "girdiyi çözümleyemedim" durumu sessiz. İstenirse dengesiz tırnak için warn mesajı eklenebilir; zorunlu değil.
3. **Yinelenen ihlaller tekilleştiriliyor** (`unique` sözlüğü). Örneğin compose run içindeki `make test` ve dış kural aynı KAPI'yı iki kez yazmıyor. Kayıt sayımı (dalga raporu) için doğru.
4. **r1 N2 hâlâ açık (warn günü):** `systemMessage`'ın kullanıcı arayüzünde görünmesi, `Read` deny reddi (`//c/` biçimi) ve `Edit` kuralının Write'ı da kapsadığının canlı kanıtı. Yeni `Edit(//c/…/paycoreLLM/.env)` satırı da aynı gözlemle doğrulanır.
5. **Delta düzeni:** önce kırmızı testler (6aeb07f, c19fc8d), sonra fix, sonra docs. Ayırıcıdaki sapma (tırnağa duyarlı yazım) gerekçeli ve testli. r1 NOTE'ları (N1 guard'ı guard'lanan düzenleyebilir, N3 gecikme, N7 `context_budget.py`) bu tur kapsamı dışında, koordinatörde.

## Kanıt
- `state/evidence/fix-ajan-hooklari-r2-rv-tests.log`: `pytest tests/hooks` 136 passed.
- `state/evidence/fix-ajan-hooklari-r2-rv-probe.log`: 104 doğrudan çağrı (girdi, ortam, çıkış kodu, stdout, stderr) ve geçici kökteki maskeli kayıt dökümü.
- `state/evidence/fix-ajan-hooklari-r2-rv-probe.py.txt`: probe betiği. r1 betiği ve r2 ekleri; gerçek `hook-guard.log`'a yazmaz.
