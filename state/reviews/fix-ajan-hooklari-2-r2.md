# Review fix/ajan-hooklari-2 r2 · teyit turu (r1 MINOR-1..5, NOTE-1, NOTE-4)
SHA: d5e9c1142c6f5f9f7d356aafbf3533257c5d2ed2 · Sonuc: ONAY · Bulgu: B0 M0 m0 N2

- **İncelenen tam SHA:** `d5e9c1142c6f5f9f7d356aafbf3533257c5d2ed2` (worktree salt okunur).
- **Delta** `571ae6f..d5e9c11`: 4 commit, 11 dosya, +341/−54. Commit'ler: test 00c25b7, fix 1207df2, feat 60edb43, docs d5e9c11. state, backend, frontend ve settings değişmedi.
- **İstek:** K-HOOK2-0009 (kapsam K-HOOK2-0008). r1 raporu `fix-ajan-hooklari-2-r1.md`.
- **Yöntem:** yığın açılmadı, ağ kullanılmadı.
  - Guard diff'i okundu.
  - Kapı koşuldu.
  - r1 probe'unun 146 vakası aynen yeniden koşuldu. Kapanması beklenen vakaların beklentisi 2'ye çevrildi: W27 `env -S` ve E28, E29, E30, E36.
  - Üstüne 28 yeni vaka (N01-N28) eklendi: iç içe ENV, kod heredoc'ları, kapı yolu, `--split-string` ve yeni maske adları.
  - Toplam **174 doğrudan çağrı**, settings komut biçimiyle, geçici kökte.
  - `kanal_ozet` gerçek kanallarda koşuldu.
- **Karar: ONAY**
- **Sayılar:** BLOCKER 0 · MAJOR 0 · MINOR 0 · NOTE 2
- **MAJOR sınıfları:** yok.

## Kontrol listesi (K-HOOK2-0009)

| # | Madde | Sonuç | Kanıt (`-r2-rv-probe.log`) |
|---|---|---|---|
| 1 | **"ENV yalnız en üst düzeyde koşar": iç içe `.env` gerileme mi?** | **Gerileme yok.** <br>• `check_bash(top=False)` iç çağrılarda ENV'i atlıyor. Ama `env_hits` kendi özyinelemesini koruyor: gruplar, `$(…)`, `shell_inner` ve `compose_service_command`. Ayrıca her düzeyde `strip_heredocs`'u yeniden uyguluyor. <br>• İşçi rolünde ya da inceleyici rolünde engellenen ENV vakaları: <br>&nbsp;&nbsp;– `sh -c 'cat .env'` (N01) ve `bash -c "source .env"` (N02) <br>&nbsp;&nbsp;– compose run tools `sh -c 'cat .env'` (N03) ve compose exec `bash -lc 'cat /app/.env'` (N04) <br>&nbsp;&nbsp;– 2 düzey `sh -c` (N05) <br>&nbsp;&nbsp;– `( )`, `{ ;}` ve `if … fi` içi (N06-N08) <br>&nbsp;&nbsp;– `$(sh -c 'cat .env')` (N09) <br>&nbsp;&nbsp;– `env -S 'cat .env'` (N10) ve `time bash -o pipefail -c` (N11) <br>• r1'deki E14 `sh -c 'cat .env'`, E15 `$(cat .env)` ve E19 compose `-v` de engel. <br>• `sh -c` içindeki veri heredoc'u serbest (N12). Bu, değişikliğin amacı: iç çağrı gövdeyi komut gibi okumuyor. <br>• PAYCORE da yalnız en üstte, ama tüm metinde arıyor. `sh -c` içi paycore verisi engel (N18). | N01-N12, N18; E14, E15, E19 |
| 2 | MINOR-1 bileşik gövde | **Kapandı.** <br>• `command_words` yalnız tırnak dışında ve komut konumunda duran anahtar sözcüğü sayıyor. <br>• W13 (`echo fi`), W14 (`"done"`) ve W15 (`for x in done`) artık engel. Tee'siz `if grep -q "build done" log; then make test; fi` de engel (N20). <br>• tee'li `for` ve `while … echo done` serbest (N23, N24; W11 ve W39 da). <br>• Kapanmamış bileşik komut engelleniyor (W36). | W13-W15, N20, N23, N24 |
| 3 | MINOR-2 ENV kodu | **Kapandı (koordinatörün yön kararı: yanlış negatif yerine yanlış pozitif).** <br>• Engellenenler: <br>&nbsp;&nbsp;– `bash <<EOF` + `cat .env` (E28) ve `sh <<'EOF'` + `source .env` (E36) <br>&nbsp;&nbsp;– `py -c`, boşluksuz ve boşluklu (E29, E30) <br>&nbsp;&nbsp;– `cat <<EOF \| bash` (N13), `py - <<'EOF'` (N14), `node -e` (N15) <br>• Veri heredoc'u serbest: `cat > x.py <<'EOF'` + `open('.env')` (N17), E22. <br>• Bilinçli yanlış pozitif: kodda metin olarak geçen `.env` engelleniyor (N16) ve belgede yazılı. | E28-E30, E36, N13-N17 |
| 4 | MINOR-3 kanal_ozet | **Kapandı.** <br>• Gerçek kanallarda çıkış 0. ACK bekleyen **0**. "ACK'siz cevaplanmış" listesinde 3 mesaj, doğru cevaplarla eşleşmiş: C-10C1-0010 ← K-10C1-0008, K-HOOK-0006 ← A-HOOK-0008, K-HOOK-0010 ← A-HOOK-0009. <br>• Eşleme alıcının kanalına göre yapılıyor; arşiv dosyaları da rol önekiyle eşleşiyor; `tumu` için her kanal sayılıyor. <br>• PR notundaki yanlış cümlenin üstü çizilmiş ve düzeltilmiş. | `-r2-rv-kanal-ozet.log` |
| 5 | MINOR-4 maske | **Kapandı.** Probe kaydında hiçbir `PROBE*` değeri kalmadı. <br>• Maskelenenler: kaçışlı JSON (M04), `-uuser:pass` (M05), `--user=` (M06), `access_token` (M07), `apiKey` (M08), `x-api-key` (N27), kaçışlı `client_secret` (N28). <br>• r1 ve r2 maskeleri bozulmadı (M01-M03, M09-M13). `-u root` değişmiyor (M14). <br>• Zararsız yan etki: `exec -u 1000:1000` de maskeleniyor (N26). | kayıt dökümü |
| 6 | NOTE-4 `env -S` ve sarmalayıcı belgesi | `env -S 'git push'` (W27) ve `--split-string=` (N22) engel. `timeout`, `xargs` ve `sudo` serbest kalıyor (W25, W26, W28); ENVIRONMENT, docs 9.2 ve SECURITY'de bilinen sınır olarak yazılı. | W25-W28, N22 |
| 7 | Belge (MINOR-5, NOTE-1) | ENVIRONMENT'teki şu satırlar r1 bulgusuna göre düzeltildi: <br>• "Yükleme" gözleme dayanıyor. <br>• "Testler" satırında `tests/scripts` var. <br>• "Kip" satırı warn uyarısının **modele gitmediğini** söylüyor. <br>• "Kayıt" satırında yeni maskeler var. <br>Docs 9.2'de Kip ve ENV satırı güncel; bilinen sınırlar listesinde sarmalayıcılar ve kalan yanlış pozitifler yazılı. Protokolde "`### ` yalnız mesaj başlığıdır" kuralı ve ACK'siz liste var. Küçük bir eksik N1'de. | diff |

Kapı: `py -3.12 -m pytest tests/hooks tests/scripts -q` **355 passed**, exit 0, 87 s → `state/evidence/fix-ajan-hooklari-2-r2-rv-tests.log` (HEAD satırlı). İşçinin sonucuyla aynı.

Regresyon: r1'in 146 vakasının hepsi beklenen sonucu verdi. Beklentisi 2'ye çevrilen 5 vaka (W27, E28, E29, E30, E36) artık engel. Ölçülmüş tüm vakalarda beklentiye uymayan **0**.

## NOTE

1. **Docs 9.2 "Kip ve kayıt" paragrafında maske cümlesi eski:** hâlâ `"token|secret|password|api_key|key"` diyor. Bitişik ya da `=` biçimindeki `-u`/`--user`, kaçışlı tırnak ve `*_token`/`apiKey` adları yalnız ENVIRONMENT'te yazılı. Tek cümlelik düzeltme; birleştirmeyi beklemez.
2. **`case` kolu:** belge "`case` kolları yakalanmaz" diyor. Bu push ve kapı için doğru: `case x in x) git push;; esac` serbest (W17). Ama ENV, kelimeleri düz taradığı için `case` kolundaki `cat .env`'i engelliyor (N21). Daha güvenli yönde bir tutarsızlık; belge "push ve kapı için" diye daraltılabilir.

## Kanıt
- `state/evidence/fix-ajan-hooklari-2-r2-rv-tests.log`: 355 passed.
- `state/evidence/fix-ajan-hooklari-2-r2-rv-probe.log`: 174 doğrudan çağrı, beklenene uymayanların özeti (0) ve maskeli kayıt dökümü.
- `state/evidence/fix-ajan-hooklari-2-r2-rv-probe.py.txt`: probe betiği (r1'in 146 vakası ve r2'nin 28 vakası).
- `state/evidence/fix-ajan-hooklari-2-r2-rv-kanal-ozet.log`: gerçek kanallarda metin çıktısı.
