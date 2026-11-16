# fix/ajan-hooklari-2 · kanal biçim kuralı, sarmalayıcı önekleri, maske, ENV konumu, kanal_ozet

**Paket:** fix/ajan-hooklari-2 (FOLLOWUP-189 a-e) · **Sınıf:** [B] · **Branch:** fix/ajan-hooklari-2 · **Baz commit:** main 7d87f04 (rebase; plan anında 6dafd1c) · **HEAD:** `571ae6fe40560ac108234c7011829cdef65d4c14` · **GOREV:** K-HOOK2-0001, PLAN-ONAY K-HOOK2-0002 (Q1 A + `DUYURU`, Q2-Q4 A, ENV eki 189 e), GOREV-EK K-HOOK2-0003

## Plan (PLANNED B-HOOK2-0002, onay K-HOOK2-0002)

1. **Bulunan semboller:** `.claude/hooks/ffcore_guard.py`: `check_write` (yalnız yolu görüyordu), `owner_of`, `check_tokens`/`check_bash` (`MAX_NESTING=3`), `shell_inner` (değer alan `-o`'da duruyordu: r2 R15), `strip_assignments`, `tokens`, `split_pipelines`, `check_push`, `MASKS`/`mask_secrets`, `ENV_RE` (düz metin kalıbı). Testler `tests/hooks/conftest.py` + `test_guard.py` (142). `tests/scripts/` yoktu.
2. **Kapsam:** D1 `KANAL-BICIM`; D2 sarmalayıcılar + kabuk anahtar sözcükleri (Q2); D3 iki maske; ENV eki (189 e); D4 `scripts/kanal_ozet.py`; D5 belge (+ K-HOOK2-0003). **Kapsam dışı:** `block` geçişi, Bash ile tek yazar yazımı (S4), yeni kural sınıfları, değişkenle kurulan komut.
4. **Sözleşme/yapılandırma/profil:** donmuş sözleşme yok; `.claude/settings.json` değişmedi (kural mevcut Edit|Write matcher'ında). Protokole additive `Durum: DUYURU` (Q1).
6. **Migration:** yok. 7. **Geri alma:** merge commit'i geri alınır; warn kipinde zaten engel yok.
9. **Felsefe kontrolü:** ARCH-07: her kanal mesajına ve her Bash çağrısına değer; kalıcı karmaşıklık guard'da (~+540 satır, çoğu tarayıcı) mevcut özyineleme yapısı üzerinde. ARCH-09: Claude Code hook'u dosya farkı vermez, fark guard'da kurulur; platformda karşılığı yok. ARCH-10/06: listeler protokole sürüklenme testiyle bağlı (fail-loud); `old_string` bulunamazsa sessiz serbest değil, `new_string` farkı denetlenir; kanal okunamazsa mevcut `GUARD-HATA` yolu; derin `$(…)` `GUARD-DERINLIK`.

### Tasarım
- **D1 fark:** eski metin diskteki kanal (yoksa boş); yeni metin Write `content`, Edit `replace(old,new,1|hepsi)`, MultiEdit sırayla. Eklenen başlık = `Counter(yeni ### satırları) − Counter(eski)`, çit (```) içi atlanır; her biri ve yeni metindeki sonraki satır `parse_message` ile denetlenir. Kapsam yalnız ana kökte `state/kanal/<rol>.md` (`arsiv/**` `owner_of`'ta koordinatör dosyası, denetlenmez). `kullanici` alıcısı yalnız `koordinator.md`. `Cevap`: `-` ya da `, ` ile ayrılmış ID'ler (Q4). Zorunlu olmayan ek alanlar serbest.
- **D2:** `split_pipelines` artık `( … )`, `{ …; }`, `$( … )`, ters tırnak ve `for/while/until/if/case … done/fi/esac` içinde bölmez (dıştaki `| tee` gövdeyi karşılar). `extract_nested` grup gövdelerini aynı düzeyde, `$(…)`/ters tırnağı bir düzey derinde (`>3` → `GUARD-DERINLIK`) denetler; tek tırnak içi denetlenmez. `unwrap` `env [opts] [K=V]`, `command` (`-v/-V` sorgu → komut yok), `time [-p]`, `nice [-n N|-N]`, `nohup`, `exec [-a x]`, `! { } then do else elif while until if` öğelerini atar; `env`'in `K=V`'leri push bayrağına sayılır. `shell_inner` `-o/-O` değerini (küme içinde de: `-euo pipefail`) ve `--rcfile/--init-file`'ı atlar.
- **ENV eki:** kural tek kelime içinde yol konumundaki `.env`'e bakar: `ENV_PATH_RE` `(^|[/\\=<>:])\.env(?![.\w-])`, boşluklu kelime metin sayılır. Heredoc gövdesi (`<<EOF`/`<<-'EOF'`, `<<<` değil) atlanır; `grep/egrep/fgrep/rg` için desen (`-e`/ilk konumsal) ve `--exclude=/--include=/--exclude-dir=/-g/--glob` süzgeçleri atlanır, `-f` desen dosyası denetlenir. Gruplar, `$(…)`, `sh -c` ve `compose run|exec` içi özyinelemeli.
- **D3:** `(?<!\S)(-u|--user)\s+[^\s:]+:\S+` → `\1 ***`; `"(token|secret|password|api_key|key)"\s*:\s*"[^"]*"` → `"\1":"***"` (harf duyarsız), kesmeden önce.
- **D4:** `kanal_ozet.py` ayrıştırıcıyı guard'dan dosya yoluyla alır (Q3 A; biçim dışı = guard'ın reddedeceği). Kök: betiğin yolu `.worktrees` içindeyse ana checkout, ya da `--root`. `state/kanal` yoksa çıkış 2. Arşiv dosyasının rolü en uzun bilinen rol önekiyle (`isci-b-09.md` → `isci-b`).

## Değişen dosyalar
`.claude/hooks/ffcore_guard.py`, `scripts/kanal_ozet.py`, `scripts/README.md`, `tests/hooks/{test_kanal_bicim,test_wrappers,test_masks,test_env_position}.py`, `tests/scripts/{kanal_ornek,test_kanal_ozet}.py`, `handbook/{MULTI_AGENT_PROTOCOL,ENVIRONMENT_AND_COMMANDS,SECURITY_AND_PERMISSIONS}.md`, `docs/takim/ajanlarla-gelistirme.md`. `main...HEAD`: 13 commit, 13 dosya +1578/-57; state, backend, frontend, `.claude/settings.json` değişmedi. **Not (r1 N1):** `git diff main...HEAD -- .claude/` boş değil; guard bu PR'ın konusu.

| Commit | Tür | İçerik |
|---|---|---|
| bf1969c | test | D1 kırmızı (31 kırmızı / 19 yeşil → `hook2-d1-red.log`) |
| 93adc31 | test | sürüklenme testi: alıcı cümlesi ve yalnız sayılı değerler |
| 5fa50ae | feat | D1 `KANAL-BICIM` + protokol `DUYURU` |
| b7baeb4 | test | D2 kırmızı (40 / 23 → `hook2-d2-red.log`) |
| 6d43f70 | feat | D2 tarayıcı, `unwrap`, `extract_nested`, `shell_inner -o` |
| 7b6ac9e | test | D3 kırmızı (10 / 3 → `hook2-d3-red.log`) |
| 9fa12d2 | feat | D3 maskeler + docstring |
| 057b29a | test | ENV eki kırmızı (11 / 31 → `hook2-env-red.log`) |
| cdaf457 | fix | ENV yol konumu, heredoc, grep deseni |
| 98a0216, 7b5f31b | test | D4 kırmızı (9 kırmızı → `hook2-d4-red.log`) + lint |
| c38ffed | feat | D4 `kanal_ozet.py` |
| 571ae6f | docs | D5 + K-HOOK2-0003 |

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | D1 geçerli başlıklar (ACK, PR-HAZIR, REVIEW-SONUC, DURUM PLANNED/DUYURU, YIGIN-AC, çoklu Cevap, ek alan) serbest | `test_kanal_bicim::test_valid_*`, `test_kullanici_allowed_in_coordinator_channel` | geçti |
| 2 | D1 geçersiz: `YIGIN-AÇ`, açıklamalı tür, `koordinatör`, paketli alıcı, ID, tarih, başlık biçimi; mesaj alanı söyler | `test_invalid_header_blocked[*]`, `test_kullanici_blocked_in_worker_channel` | geçti |
| 3 | D1 ikinci satır: Paket/Cevap eksik, kısa/bozuk SHA, Sonuc, Bulgu, Durum (`WARN-GUNU`), Yigin | `test_invalid_second_line_blocked[*]`, `test_header_as_last_line_blocked` | geçti |
| 4 | D1 eski mesaja dokunma serbest; yalnız eklenen; kod bloğu; replace_all; old_string yok; MultiEdit; yeni dosya; arşiv/PR kapsam dışı; süreç çıkışı + kayıtta içerik yok | `test_old_malformed_*`, `test_write_keeping_old_malformed_allowed`, `test_lease_line_edit_allowed`, `test_duplicate_of_existing_header_is_new`, `test_header_in_code_fence_ignored`, `test_edit_*`, `test_multiedit_checked`, `test_new_channel_file_checked`, `test_archive_not_checked`, `test_other_markdown_not_checked`, `test_hook_process_*` | geçti |
| 5 | D1 listeler = protokol (sürüklenme fail-loud) | `test_types_match_protocol`, `test_recipients_match_protocol`, `test_required_fields_match_protocol` | geçti |
| 6 | D2 her önek için engel/serbest çifti: `env X=1 git push` işçi engel; `$(git push)` engel; `time make test \| tee …` serbest | `test_wrappers::test_worker_push_through_wrapper_blocked[31]`, `test_worker_harmless_forms_allowed[10]`, `test_coordinator_flagged_push_through_wrapper_allowed[3]`, `test_gate_through_wrapper_*[14]`, `test_compose_through_wrapper_blocked[3]`, `test_substitution_depth_is_loud` | geçti |
| 7 | D3 iki desen için kayıtta değer yok; zararsız metin değişmez | `test_masks::test_mask_hides_value[9]`, `test_mask_leaves_harmless_text[3]`, `test_log_line_has_no_credentials` | geçti |
| 8 | ENV eki: `cat .env`, `source .env` engel; `grep … --exclude='.env'`, `echo "… .env …"`, heredoc içi serbest | `test_env_position::test_env_path_blocked[25]`, `test_env_text_allowed[16]`, `test_command_after_heredoc_still_checked` | geçti |
| 9 | D4 fixture ile beklenen özet, `--json` şeması, state yoksa çıkış 2, gerçek kanallarda koşar | `tests/scripts/test_kanal_ozet.py` (9) | geçti |
| 10 | Mevcut 142 test yeşil | `tests/hooks/test_guard.py` | geçti |

## Çalıştırılan komutlar
| Komut | Ortam | Exit | Süre |
|---|---|---|---|
| `py -3.12 -m pytest tests/hooks tests/scripts -q 2>&1 \| tee state/evidence/hook2-tests.log` (ilk satır HEAD) | host Python 3.12, pytest 9.0.2, HEAD 571ae6f, ağ yok | 0 (**319 passed**) | 84 sn |
| `ruff check` + `ruff format --check` `.claude/hooks tests/hooks tests/scripts scripts/kanal_ozet.py` → `state/evidence/hook2-ruff.log` | ruff 0.17.3: uv önbelleğindeki `ruff.exe` (backend pin'i), cwd worktree, kökteki `ruff.toml`; ağ yok | 0 / 0 | <1 sn |
| kırmızı koşular → `state/evidence/hook2-{d1,d2,d3,env,d4}-red.log` | kod öncesi | 1 | |
| `py -3.12 -X utf8 scripts/kanal_ozet.py` (gerçek kanallar) | HEAD | 0 | 54 geçerli mesaj, 2073 biçim dışı (eski), 3 ACK bekleyen: C-10C1-0010, K-HOOK-0006, K-HOOK-0010 |
| `py -3.12 scripts/context_budget.py` | worktree | 1 | zorunlu küme 47,2K/60K (+0,8K bu PR); aşım yalnız `state/BLOCKERS.md` 47,1K/30K (önceden var, koordinatör dosyası) |

## Warn günü uyarıları (K-HOOK2-0004; bu oturum, main guard'ı, 22:42-23:06)
`hook-guard.log`'da `isci-b` rolüyle 12 satır:
- **9 × `KAPI` gerçek:** kırmızı/yeşil yineleme sırasında `pytest … | tail`/`| grep` tee'siz koşuldu (22:42, 22:44, 22:51, 22:54, 22:58:05, 23:02, 23:04, 23:05, 23:06; `sed …;`/`RUFF=…;` ile başlayan satırlarda da aynı komut zincirindeki tee'siz pytest tetikledi, sed/ruff değil). Kural doğru; bundan sonra her pytest koşusu tee ile. Kapı ve kırmızı kanıt koşuları baştan tee'liydi.
- **3 × `ENV` yanlış pozitif:** 22:57 ve 23:00 commit mesajında, 22:58:36 `py -3.12 -c "…"` metninde `.env` sözcüğü (okuma yok). Eski guard'ın düz metin kalıbı; bu PR'ın ENV eki kapatır (boşluklu tırnaklı kelime metindir): `test_env_text_allowed` içindeki `git commit -m "docs: .env is never read"` aynı sınıf; yeni sınıf yok.
- **Bulgu (r1 N2 a):** warn kipinde ne stderr ne `systemMessage` modele (bu oturuma) görünmedi; uyarıları ancak koordinatörün bildirimiyle ve kayıttan öğrendim. Block'a geçişte mesaj modele gider (çıkış 2); warn günü verisi için oturumların kendi uyarısını görmediği hesaba katılmalı.

## Varsayımlar ve brief'teki çelişkiler
- `tests/scripts/conftest.py` yok: `tests/hooks` modülleri `from conftest import …` kullanıyor; ikinci bir `conftest.py` aynı oturumda o adı ezdi (toplama hatası). Örnek veri `tests/scripts/kanal_ornek.py` (benzersiz ad), fikstür test dosyasında.
- `DUYURU` protokol tablosuna D1 commit'inde girdi (sürüklenme testi aynı commit'te yeşil kalsın diye); "Doğrulama" metni D5'te.
- `Cevap` satırında protokol notu backtick'siz yazıldı: sürüklenme testi backtick'li her şeyi tür/alan sayar.
- Grup gövdeleri derinlik saymaz (metin her özyinelemede kısalır, sonlanır); yalnız `$(…)`/ters tırnak ve mevcut `sh -c`/compose sayar.
- Heredoc gövdesini yalnız `ENV` atlar (GOREV-EK kapsamı); öteki kurallar gövde satırlarını komut gibi okur (`bash <<EOF` içeriği çalışır, güvenli yön).

## Kalan riskler
- Değişkenle kurulan komut, betik dosyası, Makefile tarifi, compose olmayan `docker exec/run`, `case` kolları ve Bash ile state yazımı yakalanmaz (belgede).
- Tarayıcı tam bir kabuk ayrıştırıcısı değil: `case … in a) …;;` kolları ve process substitution `>(…)` yaklaşık; dengesiz parantez/tırnak sonuna kadar grup sayılır (komut zaten sözdizimi hatası).
- Heredoc gövdesindeki `git push`/`make test` satırları `PUSH`/`KAPI`'yı tetikleyebilir (yanlış pozitif yönü); warn günü gösterir.
- `kanal_ozet` ACK eşlemesi yalnız yeni biçimli `ACK`'lerden: eski biçimli ACK'le cevaplanmış yeni biçimli bağlayıcı mesaj (ör. K-HOOK-0006/0010) "bekleyen" görünür.
- Hook çağrı başı gecikmesi (~1 sn) değişmedi; kanal yazımında dosya bir kez okunur.
