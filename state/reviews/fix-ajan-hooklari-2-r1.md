# Review fix/ajan-hooklari-2 r1 · tam tur (KANAL-BICIM, sarmalayıcılar, maske, ENV konumu, kanal_ozet)
SHA: 571ae6fe40560ac108234c7011829cdef65d4c14 · Sonuc: ONAY · Bulgu: B0 M0 m5 N6

- **İncelenen tam SHA:** `571ae6fe40560ac108234c7011829cdef65d4c14` (`fix/ajan-hooklari-2`, worktree salt okunur). `7d87f04..571ae6f`: 13 commit, 13 dosya, +1578/−57. state, backend, frontend ve `.claude/settings.json` değişmedi.
- **İstek:** K-HOOK2-0005 REVIEW-ISTEK, 7 madde. Kararlar: KARARLAR "fix/ajan-hooklari-2 plan kararları". Tur kuralı K-GEN-0012.
- **Yöntem:** yığın açılmadı, ağ kullanılmadı.
  - Guard, `kanal_ozet.py`, testler ve belge diff'i okundu.
  - Kapı host `py -3.12` ile koşuldu.
  - Guard 146 kez doğrudan çağrıldı: settings komut biçimiyle, `FFCORE_MAIN_ROOT` geçici kökte, örnek kanal dosyasıyla. Vakalar: 39 KANAL-BICIM, 51 sarmalayıcı, 14 maske, 42 ENV.
  - Sürüklenme testi, protokolün değiştirilmiş geçici kopyasında koşuldu.
  - `kanal_ozet` gerçek kanallarda ve hata yollarında koşuldu.
- **Karar: ONAY.** Bulguların hepsi MINOR. Ama MINOR-1 ve MINOR-2, bu PR'ın kapattığını söylediği alanda sessiz geçiş bırakıyor. `block` geçişinden önce kapanmalarını öneriyorum; merge'i bekletmeleri gerekmiyor.
- **Sayılar:** BLOCKER 0 · MAJOR 0 · MINOR 5 · NOTE 6
- **MAJOR sınıfları:** yok.

## Kontrol listesi (K-HOOK2-0005)

| # | Madde | Sonuç | Kanıt |
|---|---|---|---|
| 1 | KANAL-BICIM | **Doğru**, biri hariç 39 vaka beklendiği gibi; o vaka bilinçli (N1). <br>• Geçerli `REVIEW-SONUC` eki, `DURUM: DUYURU`, iki ID'li `Cevap` ve sırası farklı ek alan serbest (K01, K08, K29, K37). <br>• Engellenenler: eksik `Paket`, `YIGIN-AÇ`, `→ koordinatör`, kısa SHA, `Bulgu` biçimi, `Durum: WARN-GUNU`, `Sonuc: KABUL`, küçük harfli ID, boşluksuz virgül, boşluksuz ayırıcı, ikinci satırsız başlık (K02-K07, K09, K28, K30, K31, K38). Mesaj alanı adıyla söylüyor. <br>• Eski bozuk mesajın gövdesine dokunan Edit, lease satırı, eski bozuk başlığı silmek ya da düzeltmek serbest (K10, K11, K20, K21). <br>• `kullanici` alıcısı inceleyici kanalında engel, koordinatör kanalında serbest (K12, K13). `arsiv/**` denetlenmez (K14). Kod bloğu içi atlanır (K15). <br>• **Counter farkı doğru:** iki başlığı silip yer değiştirerek geri koymak serbest (K17). İki başlık silinip biri ve yeni bozuk bir başlık konunca yalnız yenisi engelleniyor (K18). Eski bozuk başlığın kopyası ve `replace_all` çoğaltması yeni sayılıyor (K19, K25). <br>• `old_string` bulunmayınca `new_string` denetleniyor (K22, K23). MultiEdit'in ikinci düzenlemesi denetleniyor (K24). Write ile tüm dosya ve CRLF serbest (K26, K27). Dosya adı büyük harfle yazılınca da denetleniyor (K34). <br>• Worktree kanal yolu yalnız `STATE-YOL` veriyor, çakışma yok (K32). Başka rolün kanalında `TEK-YAZAR` ve `KANAL-BICIM` birlikte çıkıyor (K33). warn kipinde çıkış 0 ve `systemMessage` (K36). <br>• **Sürüklenme testi protokolü gerçekten okuyor:** geçici kopyada 4 değişiklik yaptım; her biri ilgili testi kırmızıya düşürdü: yeni tür, `Durum` listesinden `DUYURU` silme, `YIGIN-AC`'a zorunlu alan ekleme, yeni alıcı. | `-r1-rv-probe.log` K01-K39; `-r1-rv-drift.log` |
| 2 | Sarmalayıcılar ve anahtar sözcükler | **İstenen biçimlerin hepsi işçi rolünde engel:** `env X=1`, `command`, tee'siz `time make test`, `$(…)`, ters tırnak, `{ ;}`, `( )`, `bash -o pipefail -c`, `bash -euo pipefail -c`, tee'siz `for … pytest`, `if … git push; fi`, `while`, `"$(…)"`, `f() { git push; }; f`, `!`, `nice -n`, `exec`, `nohup … &`, `env -i` (W01-W12, W16, W18, W20-W24, W43, W44). <br>• tee'li karşılıkları serbest: W04, W11, W39, W45. `'$(git push)'` serbest (W19). `command -v` serbest (W42). Commit mesajındaki `git push` serbest (W47). <br>• Koordinatörün bayraklı `env`/`time` push'u serbest, bayraksız grup push'u engel (W49-W51). <br>• Derinlik: 4 düzey `$( )` engel; 3 düzey push `PUSH` ile yakalanıyor (W30, W31). 400 iç içe parantezde çökme yok, `PUSH` ile engel (W38). <br>• Dengesiz `$(`, `{`, `(` ve `do`'su kapanmamış `for` engel (fail-loud yönü). Dengesiz çift tırnak çıkış 0 veriyor; bash komutu koşmaz (W32-W36). <br>• **Açık: MINOR-1** (W13-W15). Belgede yazmayan sarmalayıcılar: N4. | W01-W51 |
| 3 | Maske | İstenen üç biçim maskeleniyor: `-u user:pass`, `--user user:pass`, `'{"token":"x"}'` (M01-M03). `"password" : "x"` de maskeleniyor (M09). r2 maskeleri bozulmadı (M10-M13). `-u root` değişmiyor (M14). **Açık: MINOR-4**: beş varyant sızıyor (M04-M08). | M01-M14, kayıt dökümü |
| 4 | ENV konum eki | **Engel:** `cat .env`, `source .env`, `. .env`, `< .env`, `cp .env x`, `cp x .env`, `./.env`, `"$HOME/.env"`, `.ENV`, `--env-file .env` ve `=.env`, `cat<.env`, `'.env'`, `sh -c`, `$(cat .env)`, `> .env` heredoc, grep dosya argümanı ve `-f` desen dosyası, `-v ./.env:`, `.env*`, `-- .env`, `type`, `../.env`, Windows yolu (E01-E19, E33, E37-E41). <br>• **Serbest:** `--exclude='.env'`, `".env yok"`, heredoc gövdesi, commit mesajı, `.env.test`, `.env.example`, `grep -n .env .gitignore`, `rg -g`, `ls -a \| grep .env` (E20-E27, E34). <br>• Kalan yanlış pozitifler (N2): tek kelime `echo .env`, `git commit -m ".env"` ve `cat <<< .env` (E31, E32, E42). <br>• **Açık: MINOR-2.** Kabuğa giden heredoc ve satır içi yorumlayıcı kodu artık serbest; main bunları yakalıyordu (E28-E30, E36). | E01-E42 |
| 5 | kanal_ozet | Fikstür testleri yeşil (kapı). <br>• Gerçek kanallarda çıkış 0. Bugün **60** geçerli mesaj (PR anında 54; aradan 6 yeni mesaj geçti), **2073** biçim dışı. <br>• ACK bekleyen 3 mesaj: C-10C1-0010, K-HOOK-0006, K-HOOK-0010. Üçü de **aslında cevaplanmış**, ama ACK ile değil → **MINOR-3**. <br>• `--json` anahtarları: `kok`, `mesaj`, `bicim_disi`, `bekleyen_ack[{id, tarih, kaynak, alici, tur, paket}]`, `paketler{<kod>: {work_queue, son_durum, son_onay_sha}}`. <br>• Başka cwd'den mutlak yolla koşunca ana kökü buluyor. `--root` altında `state/kanal` yoksa çıkış 2 ve mesaj. Guard dosyası olmayan kopyada çıkış 2; mesaj yalnız `[Errno 2] … ffcore_guard.py`, ama fail-loud. | `-r1-rv-kanal-ozet.log` |
| 6 | Warn görünürlüğü (B-HOOK2-0005) | **Bulgu doğru, beklenen davranış.** PreToolUse hook'u 0 ile çıkınca ne stderr ne `systemMessage` modele gider; `systemMessage` kullanıcıya gösterilir. Belge 9.2 bunu doğru yazıyor ("kullanıcıya görünen"). <br>• **Kendi oturumumdan bağımsız kanıt:** `hook-guard.log`'da `23:25:35 warn inceleyici Bash KAPI` satırı benim drift koşumdan. Komut `pytest … \| tail -4` idi; çıktı `>` ile dosyaya gidiyordu ama tee yoktu, yani gerçek bir KAPI. Bu oturumda hiçbir uyarı görmedim. Hook bu oturumda çalışıyor; R-GEN-0001'deki "yüklü değil" tespitim yanlıştı. <br>• **PR notu sınıflaması tutarlı:** 9 KAPI gerçek; yeni guard aynı biçimi hâlâ engelliyor (W46). 3 ENV yanlış pozitifin iki sınıfı yeni guard'da serbest: boşluklu commit mesajı (E23) ve boşluklu `py -c` metni (E30). Sonuç: warn günü sayımı yalnız kayıttan yapılabilir. | kayıt; W46, E23, E30 |
| 7 | Belge | • docs 9.2 "Hangi oturum hangi ayarı yükler (gözlem)" paragrafı K-HOOK2-0003 gözlemine göre yazılmış ve doğru. <br>• Protokolde `DUYURU`, `Cevap` çoklu ID ve "Doğrulama (uygulandı)" var. <br>• "Bilinen sınırlar" daraltıldı. <br>• **Eksik: MINOR-5.** ENVIRONMENT'te "Yükleme" satırı eski varsayımı tekrarlıyor ve "Testler" satırı eksik. Belgede şunlar yazmıyor: MINOR-1 ve MINOR-2 açıkları; N4 sarmalayıcıları; gövdede `###` yasağı. | diff |

Kapı: `py -3.12 -m pytest tests/hooks tests/scripts -q` **319 passed**, exit 0, 85 s → `state/evidence/fix-ajan-hooklari-2-r1-rv-tests.log` (HEAD satırlı). İşçinin ve koordinatörün sonucuyla aynı.

## MINOR

### MINOR-1 · Bileşik komut gövdesi, argümandaki ya da tırnaktaki anahtar sözcükte kesiliyor; push ve kapı sessiz geçiyor
`compound_body` `for/while/if … done/fi/esac` dengesini `COMPOUND_WORD_RE` ile sayıyor. Bu desen anahtar sözcüğü komut konumunda olup olmadığına ve tırnağa bakmadan sayıyor. Bu yüzden gövde erken kesiliyor. Kalan metnin ilk belirteci `;` ya da `"` olunca `check_push` ve `is_gate_command` komutu görmüyor. İşçi rolünde çıkış 0 veren biçimler:
- `if true; then echo fi; git push origin main; fi` (W13)
- `if grep -q "done" x.txt; then git push origin main; fi` (W14)
- `for x in done; do git push origin main; done` (W15)

Aynı yol kapıyı da atlatır: `if grep -q "build done" log; then make test; fi`.

Belge ve PR notu bu gövdelerin denetlendiğini söylüyor. `GUARD-HATA` da üretilmediği için geçiş sessiz. Biçimler nadir; hook bir güvenlik ağı olduğu için MAJOR saymadım (r2 MINOR-1 ile aynı ölçüt).

**Öneri:** `compound_body` sayımı `split_pipelines`'taki `cmd_start` mantığıyla yapsın: yalnız tırnak dışında ve komut konumunda duran anahtar sözcük sayılsın. Ucuz bir alternatif: gövde kesildikten sonra kalan metin `;`, `"` ya da `'` ile başlıyorsa bütün parça yeniden denetlensin. Üç vaka teste girsin.

### MINOR-2 · ENV: kabuğa ya da yorumlayıcıya giden kod artık serbest; main bunları yakalıyordu
- `bash <<EOF` / `cat .env` / `EOF` ve `sh <<'EOF'` / `source .env` / `EOF` çıkış 0 verdi (E28, E36). `strip_heredocs`, heredoc'u kim okursa okusun gövdeyi veri sayıyor. Oysa `bash`, `sh` ve `py -` için gövde komuttur. PR notunda "güvenli yön" denen durum, ENV için güvensiz yön.
- `py -3.12 -c "print(open('.env').read())"` (E29) ve aynı kodun boşluklu biçimi (E30) çıkış 0 verdi. Boşluksuz kelimede `'` ya da `(` sonrası `.env`, `ENV_PATH_RE`'nin ön ek sınıfında yok. Boşluklu olan zaten "metin" sayılıyor.

Main'deki düz metin kalıbı dördünü de yakalıyordu. Yani bu bir gerileme ve `.env` içeriğini model bağlamına taşıyabilir. Satır içi kodun serbest bırakılması warn günü yanlış pozitifinin (22:58:36 `py -c`) bilinçli sonucu, ama "Bilinen sınırlar"da yazmıyor.

**Öneri (ucuz):**
- Heredoc okuyucusunun ilk belirteci `sh`, `bash`, `py`, `python` ya da `node` ise gövde atılmasın.
- `py`/`python`/`node` `-c`/`-e` argümanı için `ENV_PATH_RE` ön ek sınıfına `'`, `"` ve `(` eklensin ya da argüman ayrıca taransın. 22:58:36 sınıfı yeniden yanlış pozitif olur; kabul edilebilir.
- Yapılmayan kısım için bir belge satırı. Hangi yöne gidileceği koordinatörün kararı (FP ↔ FN).

### MINOR-3 · kanal_ozet: "ACK bekleyen" 3 mesajın üçü de cevaplanmış; PR notundaki açıklama yanlış
- **C-10C1-0010** (KARAR-GEREK → koordinator): cevabı K-10C1-0008 CEVAP, `Cevap: C-10C1-0010` (`arsiv/koordinator-10C1.md:51`).
- **K-HOOK-0006** (DUZELT → isci-a): cevabı A-HOOK-0008 PR-HAZIR, `Cevap: K-HOOK-0006` (`isci-a.md:62`).
- **K-HOOK-0010** (DUZELT → isci-a): cevabı A-HOOK-0009 PR-HAZIR, `Cevap: K-HOOK-0010` (`isci-a.md:72`).

Bunların hiçbiri için ACK yazılmamış. Yani betik kendi tanımına göre doğru, protokol açısından da bu üç mesaj ACK eksik. Ama PR notundaki "eski biçimli ACK'le cevaplanmış" açıklaması yanlış: cevap yeni biçimli PR-HAZIR ve CEVAP. Saatlik özette bu satırlar gürültü olur ve gerçek bekleyeni gizler.

**Öneri:** alıcı kanalındaki herhangi bir mesajın `Cevap` alanı ID'yi anıyorsa iki seçenekten biri seçilsin:
- mesaj "cevaplanmış" sayılsın,
- ya da ayrı bir "ACK'siz cevaplanmış" listesine konsun.

PR notundaki cümle de düzeltilsin.

### MINOR-4 · Maskenin kalan varyantları
Kayda maskesiz girenler:
- kaçışlı JSON: `-d "{\"token\":\"…\"}"` (M04). Bash'te tek tırnaklı biçim kadar yaygın.
- bitişik `-uuser:pass` (M05)
- `--user=user:pass` (M06)
- alan adı tam listede olmayan JSON: `"access_token"` ve `"apiKey"` (M07, M08)

Olasılık r2 MINOR-3 ile aynı ölçüde düşük: secret komut satırına zaten yazılmaz.

**Öneri:**
- `(-u|--user)(?:\s+|=)?` biçimi
- JSON deseninde `\\?"` (kaçışlı tırnak)
- alan adı: `[\w-]*(token|secret|password|api_?key|key)`, harf duyarsız

Ya da belgede "boşlukla ayrılmış değer" sınırının yanına bu varyantlar yazılsın.

### MINOR-5 · Belge tutarlılığı
- `handbook/ENVIRONMENT_AND_COMMANDS.md` "Yükleme" satırı hâlâ "proje ayarı oturum açılışındaki klasörden okunur" diyor. Bu PR'da docs 9.2 bunu gözlemle düzeltti (K-HOOK2-0003): merge'den önce açılmış oturumlar da yeni ayarla denetlendi. Benim oturumum da bunun kanıtı. İki belge çelişiyor.
- Aynı dosyanın "Testler" satırı `pytest tests/hooks` diyor; `tests/scripts` yok. docs 9.2 güncellendi, ENVIRONMENT güncellenmedi.
- "Kip" satırındaki "warn (çağrı çalışır, uyarı görünür)" ifadesine "modele gitmez, yalnız kullanıcı ve kayıt" eklenmeli (madde 6).
- "Bilinen sınırlar"da şunlar yok: MINOR-1 ve MINOR-2 kapanmazsa onların açıkları; N4 sarmalayıcıları; N1'deki gövde başlığı kuralı.

## NOTE

1. **Gövdede `### ` alt başlığı artık engel (K16).** Kod bloğu dışında mesaj gövdesindeki `### Notlar` gibi bir satır da başlık sayılıyor. Kural tutarlı ve mesaj net. Protokole tek cümle eklenmeli: "gövdede `####` ya da kalın yazı kullanın".
2. **ENV'de kalan yanlış pozitifler** tek kelimelik metinde: `echo .env`, `git commit -m ".env"` ve `cat <<< .env` (E31, E32, E42). Bilinçli ve kabul edilebilir.
3. **Dengesiz girdi:** dengesiz parantez, süslü parantez, `$(` ve `do`'su kapanmamış `for` engelleniyor (fail-loud yönü). Dengesiz çift tırnak çıkış 0 veriyor; bash sözdizimi hatasıyla koşmaz, zarar yok. 400 iç içe parantezde özyineleme çökmüyor.
4. **Listede olmayan sarmalayıcılar:** `timeout 60 git push`, `… | xargs git push`, `sudo git push` ve `env -S 'git push'` işçi rolünde serbest (W25-W28). `case` kolu belgede sınır olarak yazılı (W17). `env -S` özel bir durum: `ENV_VALUE_OPTS` `-S`'in değerini atlıyor, oysa `-S`'in değeri komutun kendisi. Düzeltme tek satır: `-S` değeri `shell_inner` gibi metin olarak denetlensin. `timeout` ve `xargs` için `unwrap` ya da belge satırı.
5. **Process substitution** `cat <(git push)` engelleniyor (W29; `( … )` grubu gibi okunuyor), güvenli yön. Heredoc gövdesindeki `git push` satırı `PUSH` veriyor (W48), PR notunda yazılı yanlış pozitif yön.
6. **Kapsam ve düzen:** her kod commit'inden önce kırmızı test commit'i var (5 çift). Kapsam dışı değişiklik yok. `NotebookEdit` kanal dosyasında format denetlemiyor (K39); pratikte önemsiz.

## Kanıt
- `state/evidence/fix-ajan-hooklari-2-r1-rv-tests.log`: `pytest tests/hooks tests/scripts`, 319 passed.
- `state/evidence/fix-ajan-hooklari-2-r1-rv-probe.log`: 146 doğrudan çağrı (girdi, çıkış kodu, stdout, stderr), beklenene uymayanların özeti ve geçici kökteki maskeli kayıt dökümü.
- `state/evidence/fix-ajan-hooklari-2-r1-rv-probe.py.txt`: probe betiği. Gerçek `hook-guard.log`'a yazmaz.
- `state/evidence/fix-ajan-hooklari-2-r1-rv-drift.log`: protokolün geçici kopyasında 4 değişiklik ve sürüklenme testi sonuçları.
- `state/evidence/fix-ajan-hooklari-2-r1-rv-kanal-ozet.log`: gerçek kanallarda metin çıktısı, `--json` şeması, cwd/`--root`/guard'sız kopya hata yolları.
- `state/evidence/fix-ajan-hooklari-2-r1-rv-probe-self.log`: kendi `( … ) | tee` komutum main ve hook2 guard'ında serbest.
