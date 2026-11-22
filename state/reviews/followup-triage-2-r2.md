# Review followup-triage-2 r2 · teyit (yorum kesimi, reçete, belge cümleleri)
SHA: 89df92829fa76c6eea1975fcad5136c1091e36d5 · Sonuc: ONAY · Bulgu: B0 M0 m0 N2

- **İncelenen tam SHA:** `89df92829fa76c6eea1975fcad5136c1091e36d5` (dal `fix/followup-triage-2`).
- **Delta** `135c369..89df928`: 3 commit (test 95731be, kod ae327cf, docs 89df928), 7 dosya, +91/−21. `state/` yok.
- **İstek:** K-TR2-0009 (beş teyit maddesi); DUZELT K-TR2-0006; önceki tur `state/reviews/followup-triage-2-r1.md`.
- **Yöntem:** delta satır satır okundu; yığınsız. Üç guard (baz d6d2029, r1 135c369, r2 89df928) aynı komutlarda yan yana `decide()` ile; her biçimin bash 5.2 davranışı zararsız `echo` ile; hook testleri host `py -3.12`, `git archive 89df928` kopyasından.
- **Karar: ONAY.** r1 MINOR-1 kapandı: baz guard'ın yakaladığı beş satırın hepsi yeniden yakalanıyor, bash'in yorum saydığı biçimler yorum kalıyor. MINOR-2 ve NOTE-2/4 belge düzeltmeleri yerinde.

## Testler
Loglar `state/evidence/tr2-r2-rv-*.log` (`HEAD=` ve komut satırlı).

| Koşu | Sonuç |
|---|---|
| Hook + script testleri (`-hooks.log`) | `tests/hooks tests/scripts` **476 passed**; yalnız `tests/hooks` **465 passed** (işçinin sayısıyla aynı) |
| r2 probe'u, 40 biçim, üç guard (`-hook-probe.log`) | kural beklenen 25 biçimin hepsinde kural var (kaçan 0); bash'in yorum saydığı 12 biçimin hepsinde kural yok; 3 biçim yalnız gözlem (NOTE-1 ve heredoc) |
| r1 probe'unun 65 biçimi r2 guard'ıyla (`-hook-probe.log` ikinci yarı) | X1, X2, X3, X4, X24 baz ile aynı (PUSH/KAPI); r1'deki iyileşmelerin hepsi duruyor |
| Bash davranışı (`-bash-semantics.log`) | 19 biçim; aşağıdaki tablo |

## Teyit maddeleri (K-TR2-0009)

| # | Madde | Sonuç |
|---|---|---|
| 1 | X1-X4, X24 | `${a/ #x/y}`, `${a# #}`, `${a// #}` ve `foo\`⏎`#bar` ardındaki `git push` / `pytest`: r1 kural yok → r2 PUSH/KAPI (baz ile aynı). |
| 2 | `>#b`, `<#x`, `foo\ #x` | `>#b`, `<#x`, `>>#b`, `2>#b`: bash'te sözdizimi hatası, sonraki komut koşmuyor; r2 yorum sayıyor (tutarlı). `foo\ #x`: bash `foo #x` yazıp sonraki komutu koşuyor; r2 PUSH (r1'de kaçıyordu). |
| 3 | İç içe `${` ve tırnakla `\` birleşmesi | `${a:-${b# #}}`: bash koşuyor, r2 PUSH. Tırnak ve kaçış içindeki `}` (`${a/'}'/ #x}`, `${a/\}/ #x}`): bash koşuyor, r2 PUSH. `${a/}/ #x}`: ilk `}` kapatıyor, kalan yorum; r2 yorum. `'foo'`⏎`# x; git push`: yorum (bash ve r2). `'a'\`⏎`#b; git push` ve `"a"\`⏎`#b`: bash `a#b` yazıp koşuyor; r2 PUSH. `foo \`⏎`# …` ve `a\`⏎` #c`: yorum (bash ve r2). `&&\`⏎`#c; …`: bash sözdizimi hatası; r2 yorum. İki ardışık birleşme (`a\`⏎`b\`⏎`#c; …`): bash koşuyor, r2 PUSH. |
| 4 | Belge cümleleri | `docs/degisiklikler.md`: `ollama_unreachable` cümlesi eklendi (r1 NOTE-2). `docs/onyuz.md`: göreli `../docs/images` ve Git Bash açıklaması (r1 MINOR-2); işçi logu `tr2-r2-221-recete.log` göreli değerle PNG yazıldığını ve mutlak değerin çevrildiğini gösteriyor (kendim tekrar koşmadım). MULTI_AGENT_PROTOCOL atfı 'KIRMIZI'; docs/takim 668'de `timeout`, 670 ve handbook cümlesi üç istisnayı (`${…}`, kaçışlı karakter, `\` birleşmesi) sayıyor (r1 NOTE-4). |
| 5 | hooks bağımsız koşu | 465 passed. |

## NOTE-1 · Kapanmamış `${` sonraki satırlara taşınıyor
- `LineState.braces` satırlar arasında taşınıyor; `echo ${a`⏎`# don't`⏎`git push` biçiminde r2 kural vermiyor (r1 PUSH veriyordu). Bash bu komutu hiç koşturmuyor (`unexpected EOF while looking for matching '}'`; `}` sonradan gelirse `bad substitution` ve sonraki komut koşmuyor), yani davranış tutarlı. Kayıt için not; düzeltme önermiyorum.

## NOTE-2 · İşçinin reçete kanıtı çıplak `docker run` ile
- `tr2-r2-221-recete.log` adım 2 `docker run --rm --network none …` kullanıyor (compose değil, volume yok). B-TR2-0009 bunu açıkça yazıyor; yığın sayılıp sayılmayacağı ve YIGIN-AC gerekip gerekmediği koordinatörün kuralı. Log başlığı `HEAD=ae327cf` (kod commit'i); sonraki commit yalnız docs.

## Bekleyen dosyalar (commit edilmedi)
- `state/reviews/followup-triage-2-r2.md`
- `state/evidence/tr2-r2-rv-{hook-probe,bash-semantics,hooks}.log`
- `state/kanal/inceleyici.md`
