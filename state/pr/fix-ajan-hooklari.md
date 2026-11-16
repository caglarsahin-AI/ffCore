# fix/ajan-hooklari: ajan kurallarının hook ile zorlanması

**Paket:** fix/ajan-hooklari · **Sınıf:** [C] (güvenlik davranışı; kullanıcı onayı 16 Kasım, KARARLAR "Ajan kuralları hook ile zorlanır…") · **Branch:** fix/ajan-hooklari · **Worktree:** `.worktrees/fix/ajan-hooklari` · **Baz commit:** 9d38bc4 (plan anında 38ced4d; b9f9fd7 ve 10c-1 merge sonrası docs çakışmasın diye iki kez rebase; ikisi de temiz) · **İşçi:** isci-a (`ffcore-isci-a-hook`) · **Brief:** K-HOOK-0001 GOREV + K-HOOK-0002 EK (push kuralı)

Durum: **VERIFIED** (PLAN-ONAY K-HOOK-0003; S1-S10 A + iki ek). HEAD `3ab062dc5447c9f1fed9a1bd2a32108c2689898b`; gerçek oturum kanıtı 2026-11-16 19:09 (`state/evidence/hook-real-call.log`). PR-HAZIR A-HOOK-0007.

## Plan

### 1. Bulunan semboller ve dosyalar

- Depoda `.claude/` yalnız `scheduled_tasks.lock` içeriyor (ana checkout; izlenmiyor). **Mevcut proje `.claude/settings.json` / `settings.local.json` yok**; birleştirilecek dosya yok. Kullanıcı düzeyi `~/.claude/settings.json` yalnız `permissions.allow` taşıyor; ona dokunulmaz.
- `.gitignore`: `.worktrees/`, `.env`, `.env.*.local`; `.claude/` yok sayılmıyor → `.claude/settings.json` ve `.claude/hooks/*.py` izlenir. `.claude/settings.local.json` için satır yok (bkz. S1).
- Kök `pyproject.toml` yok; `tests/` altında yalnız `tests/e2e` (kendi `conftest.py`'si, kökte conftest yok). `ruff.toml` kökte (py312, 100 sütun, E/F/I/B/UP). Host: `py -3.12` = Python 3.12, pytest 9.0.2.
- `Makefile` `lint` hedefi `ruff check backend scripts data/samples/scripts services`: `.claude/` ve `tests/hooks` kapsamda değil; hook dosyaları `ruff check .claude/hooks tests/hooks` ile ayrıca denetlenir (Makefile'a dokunmuyorum, touch-zone dışı; bkz. kalan riskler).
- Claude Code: masaüstü uygulamasına gömülü **2.1.321** (`%APPDATA%\Claude\claude-code\2.1.321\…\claude.exe`; PATH'te `claude` yok). Oturum ortamında `CLAUDE_CODE_SESSION_ID` (= hook girdisindeki `session_id` olması beklenen UUID; bu oturum `aa799275-…`) ve `CLAUDE_CODE_HOST_SESSION_ID` (masaüstü `local_…` kimliği) var. Bu, rol kaydının anahtarı için önemli (S1).
- Kurallar kaynağı: KARARLAR madde 210 (16 Kasım), docs/takim/ajanlarla-gelistirme.md 9.2 (taslak; push satırı "yalnız sekreter" diyor, KARARLAR ve K-HOOK-0002 ile **eskimiş** → D3'te düzeltilir), MULTI_AGENT_PROTOCOL "Tek yazar kuralı" ve "Mutlak yol", ENVIRONMENT_AND_COMMANDS "Paralel yığınlar", SECURITY_AND_PERMISSIONS "Veri sınırı".

### 2. Kapsam / kapsam dışı

**Kapsam:** D1 hook betiği + testler; D2 `.claude/settings.json` (deny + PreToolUse); D3 handbook (ENVIRONMENT_AND_COMMANDS, SECURITY_AND_PERMISSIONS, MULTI_AGENT_PROTOCOL), BASLATMA (rol adımı + oturum kaydı), docs/takim 9.2 uygulanan hâl; D4 `state/oturumlar.json` şeması + okuyucu + boş örnek.

**Kapsam dışı:** `bash -c`, değişkenle kurulan komut, `eval`, betik dosyası içinden yapılan ihlaller (hook komut metnini görür; bilinen sınır, PR notunda ve docs'ta); Bash ile (`python -c`, `echo >>`) state dosyalarına yazım tek yazar kuralının dışında kalır (yalnız Edit/Write/MultiEdit/NotebookEdit denetlenir; bkz. S4); Makefile `lint` kapsamı; `make up` gibi Makefile içinden çalışan compose komutları (hook `make up` metnini görür, içindeki compose'u değil; Makefile zaten `--pull never` kullanıyorsa sorun yok, ayrıca doğrulanacak); paycoreLLM deposu (onun `.claude/` ayarı yok, bu PR eklemiyor; PayCore okuma yasağı ffcore oturumlarının mutlak yol deny'ı ile).

### 3. Değişecek dosyalar ve neden (dal: fix/ajan-hooklari)

| Dosya | Neden | Dilim |
|---|---|---|
| `.claude/hooks/ffcore_guard.py` (yeni) | PreToolUse guard; stdlib only, ağ yok; `decide(payload, env, ...)` saf fonksiyon + `main()` | D1 |
| `tests/hooks/test_guard.py` (yeni) | her kural için engel/serbest çifti, warn kipi, rol yok, kayıt satırı; çoğu alt süreçle (gerçek sözleşme: stdin JSON → çıkış kodu + stderr), yığın sayımı import + monkeypatch | D1 |
| `tests/hooks/conftest.py` (yeni, küçük) | geçici state kökü, `run_hook()` yardımcısı | D1 |
| `.claude/settings.json` (yeni) | `permissions.deny` + `hooks.PreToolUse` | D2 |
| `handbook/ENVIRONMENT_AND_COMMANDS.md` | "hook ile zorlanır" işaretleri; `FFCORE_GUARD_MODE`; `state/evidence/hook-guard.log` | D3 |
| `handbook/SECURITY_AND_PERMISSIONS.md` | push kuralı (yalnız koordinatör + kullanıcı talimatı + komut başına bayrak); `.env`/PayCore deny | D3 |
| `handbook/MULTI_AGENT_PROTOCOL.md` | tek yazar hook'u, `state/oturumlar.json`, worktree `state/` yasağı; "Ajanlar push etmez" cümlesi koordinatör istisnasıyla | D3 |
| `BASLATMA.md` | koordinatörün oturum açarken `state/oturumlar.json` kaydı; işçi/inceleyici ilk mesajında kimlik bildirimi | D3 |
| `docs/takim/ajanlarla-gelistirme.md` 9.1 tablo satırı 1 ve 9.2 | taslak → uygulanan hâl (gerçek ayar, doğrulama kanıtı, push satırı düzeltmesi) | D3 |
| `state/oturumlar.json` | **dalda değil**: D4 şeması `docs/takim` + MULTI_AGENT_PROTOCOL'de; boş örnek dosyayı (`{"sessions": {}}`) ana checkout'ta koordinatör oluşturur (tek yazar: koordinatör, bkz. kural f). Okuyucu dosya yoksa "kayıt yok" sayar (rol yok yoluna düşer, sessiz serbest değil) | D4 |
| `state/pr/fix-ajan-hooklari.md`, `state/evidence/hook-*.log` | mutlak yoldan, commit edilmez | — |

Commit sırası: (1) `test(hooks): …` kırmızı testler; (2) `feat(hooks): …` betik + settings.json; (3) `docs(hooks): …` handbook/BASLATMA/docs. Test/kod/docs ayrı.

### 4. Sözleşme, yapılandırma, profil etkisi

Donmuş sözleşme yok; backend/frontend/deploy yok; `llmaas`/`airgap` etkisi yok. Yeni yapılandırma: `FFCORE_GUARD_MODE=warn|block` (varsayılan `block`; bilinmeyen değer → `block` + stderr uyarısı, fail-loud), `FFCORE_ROL`, `FFCORE_PAKET` (isteğe bağlı, `FFCORE_ROL` ile birlikte `state/pr` sahipliği için), komut önekli `FFCORE_PUSH_OK=1`. Etki: merge sonrası **bu depoda açılan her Claude Code oturumu** (proje ayarı) hook'u yükler; dalı eski olan worktree'ler rebase edene kadar yüklemez (madde 8 ve S6).

### 4a. Kural tablosu

Ortak: kural tetiklenince stderr'e `FFCORE-GUARD [<kural>] <mesaj>`; `block` → çıkış 2 (çağrı çalışmaz, mesaj modele gider), `warn` → çıkış 0 (çağrı çalışır; görünürlük S2). Her tetiklenme `state/evidence/hook-guard.log`'a tek satır. Bash kuralları komut metnine uygulanır (tırnak içi dahil; bilinçli: ARCH-06 yönünde yanlış pozitif, sessiz geçişten iyi).

| # | Kural | Tetikleyici (araç + kalıp) | Serbest örnek | Engel örneği | Mesaj |
|---|---|---|---|---|---|
| a | `.env` okunmaz/yazılmaz | Bash; `(?<![\w.])\.env(?![.\w])` (ön ek koşulu: `x.env` dosya adı değil) | `cat .env.test`, `cp .env.example /tmp/x`, `docker compose --env-file .env.test up …` | `cat .env`, `grep KEY .env`, `echo X >> .env`, `cat backend/.env` | `ENV: .env okunmaz ve yazılmaz; testler .env.test ile (SECURITY_AND_PERMISSIONS)` |
| a2 | aynı, dosya araçları | `permissions.deny` `Read(**/.env)`, `Edit(**/.env)` (Edit kuralı Write/MultiEdit/NotebookEdit'i de kapsar; ayrıca hook Edit/Write yolunda `.env` adına bakar, deny çalışmazsa ikinci ağ) | `Read .env.test` | `Read C:\…\.env`, `Write …/.env` | `ENV: .env okunmaz ve yazılmaz` |
| a3 | PayCore veri sınırı | `permissions.deny` `Read(//c/ai_paycore/paycoreLLM/data/**)`, `Read(//c/ai_paycore/paycoreLLM/eval/results/**)`, `Read(//c/ai_paycore/paycoreLLM/.env)`; Bash'te `paycoreLLM[/\\](data\|eval[/\\]results)[/\\]` kalıbı da engel | `Read paycoreLLM/src/...`, `cat …/paycoreLLM/eval/scenario1/questions.jsonl` | `cat /c/ai_paycore/paycoreLLM/data/x`, `Read …\paycoreLLM\eval\results\…` | `PAYCORE: paycoreLLM data/** ve eval/results/** okunmaz (CLAUDE.md, PLAN 2d)` |
| b | push yalnız koordinatör + kullanıcı talimatı (K-HOOK-0002) | Bash; `\bgit\b(\s+-[Cc]\s+\S+)*\s+push\b`. Serbest **yalnız** rol = `koordinator` **ve** bayrak var. Bayrak: komut metninde `FFCORE_PUSH_OK=1 git push …` öneki (o komuta özgü; kalıcı değil) ya da hook ortamında `FFCORE_PUSH_OK=1` (bkz. S5) | (koordinator) `FFCORE_PUSH_OK=1 git push origin main` | (koordinator) `git push origin main`; (isci-a) `FFCORE_PUSH_OK=1 git push`; (rol yok) `FFCORE_PUSH_OK=1 git push`; `git -C x push` | `PUSH: git push yalnız koordinatör, kullanıcının o anki açık talimatıyla ve komut önekinde FFCORE_PUSH_OK=1 ile (KARARLAR 16 Kasım)` |
| c1 | dış bağlantılı derleme yok | Bash; `docker compose … build` ya da `docker-compose … build`, `--pull=false` yoksa | `docker compose -p x build --pull=false backend` | `docker compose build`, `docker compose -f compose.yaml build backend` | `PROSES-175: compose build yalnız --pull=false ile (BuildKit base imaj için dışarı bağlanır)` |
| c2 | `up --build` yok | Bash; `compose … up` içinde `--build` | — | `docker compose up -d --build --pull never` | `PROSES-175: up --build yok; imaj önce build --pull=false, sonra up --no-build --pull never` |
| c3 | yığın `--pull never` ile | Bash; `compose … up` içinde `--pull never` / `--pull=never` yoksa | `docker compose -p ffcore-x up -d --wait --no-build --pull never` | `docker compose up -d`, `docker compose up -d --pull missing` | `PROSES-175: yığın up -d --wait --no-build --pull never ile açılır (ENVIRONMENT_AND_COMMANDS)` |
| d | en çok üç FF yığını | Bash; `compose … up` (c2/c3 geçtiyse) → `docker compose ls --format json` (zaman aşımı 5 sn); ad `^(ff\|review)` olan **çalışan** proje sayısı ≥ 3 **ve** komutun `-p <ad>`'ı bu listede değilse engel (zaten açık yığına `up` yeni yığın açmaz). Sayım yapılamazsa (docker yok, zaman aşımı, bozuk JSON) → engel (S3) | 2 FF yığını açıkken yeni `up`; 3 açıkken o üçünden birine `up` | 3 FF yığını açıkken 4. projeye `up` | `YIGIN: aynı anda en çok üç FF yığını (açık: <adlar>); YIGIN-AÇ sırası koordinatörde (KARARLAR "Üç yığın sınırı")` |
| e | kapı çıktısı dosyaya | Bash; `\bmake\s+(lint\|test\|test-int\|smoke)\b` ya da `\bpytest\b` (`-m pytest` dahil), komutta `\btee\b` yoksa | `make test 2>&1 \| tee state/evidence/x.log`, `py -3.12 -m pytest tests/hooks -q 2>&1 \| tee state/evidence/hook-tests.log`, `py -3.12 -m pytest --version` (S7) | `make test`, `make lint \| tail -5`, `py -3.12 -m pytest tests/hooks -q` | `KAPI: kapı/test çıktısı tamamen dosyaya: … 2>&1 \| tee state/evidence/<paket>-<adım>.log (K-05a-0011)` |
| f | tek yazar | Edit/Write/MultiEdit/NotebookEdit; yol (`file_path`/`notebook_path`) normalize edilir (`\`→`/`, küçük harf sürücü), **ana state kökü** (`C:/ai_paycore/ffcore/state` ya da `KARARLAR.md` için ana kök) altına göre sahip: `state/WORK_QUEUE.md`, `state/BLOCKERS.md`, `KARARLAR.md`, `state/oturumlar.json` → `koordinator`; `state/kanal/<r>.md` → `<r>`; `state/pr/<s>.md` → kaydında `pr == <s>` (yoksa `paket` içindeki `/`→`-`) olan işçi rolü (`isci-*`, `test`); `state/reviews/**` → `inceleyici`. Diğer `state/**` (evidence, HANDOFF, dalga…) serbest | (isci-a) Edit `C:\ai_paycore\ffcore\state\kanal\isci-a.md`; (isci-a, paket fix/ajan-hooklari) Write `state/pr/fix-ajan-hooklari.md`; (koordinator) Edit `state/WORK_QUEUE.md`; herkes `state/evidence/x.log` | (isci-a) Edit `state/WORK_QUEUE.md`; (isci-a) Edit `state/kanal/koordinator.md`; (isci-c) Write `state/pr/fix-ajan-hooklari.md`; (rol yok) Edit `state/kanal/isci-a.md` | `TEK-YAZAR: <göreli yol> → <sahip>; senin rolün <rol\|yok>` |
| f2 | rol yok | f'nin tek yazar dosyalarında rol bulunamazsa engel; mesaja çözüm adımı eklenir | (rol yok) Edit `state/evidence/x.log`, Edit `backend/app/x.py` | (rol yok) Edit `KARARLAR.md` | `TEK-YAZAR: rol bulunamadı (FFCORE_ROL yok, state/oturumlar.json'da session_id=<id> / host=<local_…> kaydı yok); koordinatöre bu kimliği bildir` |
| g | worktree `state/` kopyası | Edit/Write/…; yol `/.worktrees/` içeriyor ve worktree kökünden sonra `state/` ile başlıyorsa → her rol için engel (koordinator dahil) | `C:\ai_paycore\ffcore\state\kanal\isci-a.md` | `C:\ai_paycore\ffcore\.worktrees\fix\ajan-hooklari\state\pr\x.md` | `STATE-YOL: state/ yalnız C:\ai_paycore\ffcore\state\ mutlak yolundan (MULTI_AGENT_PROTOCOL "Mutlak yol")` |
| h | kip | `FFCORE_GUARD_MODE` ortamı: `block` (varsayılan) çıkış 2; `warn` çıkış 0 + mesaj; başka değer → `block` gibi davran + `FFCORE-GUARD: bilinmeyen FFCORE_GUARD_MODE=<x>, block uygulandı` | — | — | — |
| i | kayıt | her tetiklenme (warn ve block): `state/evidence/hook-guard.log`'a `<ISO-zaman>\t<kip>\t<rol\|->\t<araç>\t<kural>\t<komutun ya da yolun ilk 120 karakteri, satır sonları boşluk>` (dosya içeriği yok; Edit/Write `content`/`new_string` hiç yazılmaz). Kayıt yazılamazsa stderr'e not, karar değişmez | — | — | — |

Rol çözümü sırası (açık, gizli seçim yok): (1) `FFCORE_ROL` ortamı (+ isteğe bağlı `FFCORE_PAKET`); (2) `state/oturumlar.json` → `sessions[<hook girdisi session_id>]`, yoksa `sessions[<CLAUDE_CODE_HOST_SESSION_ID>]` (S1); (3) yok. Rol bilinen kümede değilse (`koordinator, inceleyici, isci-a, isci-b, isci-c, isci-d, test, sekreter`) "rol yok" sayılır ve mesajda yazılır. `oturumlar.json` bozuksa (JSON hatası, şema dışı) → rol yok + stderr'de `oturumlar.json okunamadı: <hata>` (fail-loud; sessiz serbest yok).

Ana state kökü: hook kendi yolundan bulur: `.../ffcore/.worktrees/<…>/.claude/hooks/ffcore_guard.py` → `.../ffcore`; aksi hâlde `CLAUDE_PROJECT_DIR`. Testler için `FFCORE_MAIN_ROOT` ortam değişkeni (açık, belgelenmiş; bkz. S8).

### 4b. `state/oturumlar.json` şeması (D4)

```json
{
  "sessions": {
    "<session_id veya local_… host kimliği>": {
      "rol": "isci-a",
      "paket": "fix/ajan-hooklari",
      "pr": "fix-ajan-hooklari",
      "lease": "ffcore-isci-a-hook",
      "acildi": "2026-11-16T10:47"
    }
  }
}
```

Zorunlu: `rol`, `acildi`. İşçi rolleri için `paket` zorunlu (yoksa `state/pr` yazımı engellenir). `pr` isteğe bağlı (paket kodu dosya adına eşit değilse; ör. `08-tam-1c-b-olcum` → `08-tam-1c`). Tek yazar: koordinatör. Okuyucu: yalnız okur, yazmaz; dosya yoksa "kayıt yok".

### 5. Kabul kriteri → test adı (tests/hooks/test_guard.py; kırmızıdan başlar)

| # | Kriter | Testler |
|---|---|---|
| 1 | (a) `.env` | `test_env_cat_blocked`, `test_env_test_allowed`, `test_env_example_allowed`, `test_env_file_flag_with_env_test_allowed`, `test_env_write_tool_blocked`, `test_env_test_write_tool_allowed` |
| 2 | (a3) PayCore | `test_paycore_data_bash_blocked`, `test_paycore_eval_results_blocked`, `test_paycore_src_allowed` |
| 3 | (b) push | `test_push_coordinator_with_flag_allowed`, `test_push_coordinator_without_flag_blocked`, `test_push_worker_with_flag_blocked`, `test_push_no_role_with_flag_blocked`, `test_push_git_c_variant_blocked`, `test_git_status_allowed` |
| 4 | (c) compose | `test_compose_build_bare_blocked`, `test_compose_build_pull_false_allowed`, `test_compose_up_build_blocked`, `test_compose_up_without_pull_never_blocked`, `test_compose_up_pull_never_allowed`, `test_compose_up_pull_equals_never_allowed` |
| 5 | (d) üç yığın | `test_fourth_stack_blocked`, `test_third_stack_allowed`, `test_up_into_running_stack_allowed`, `test_stack_count_failure_blocks` (import + monkeypatch `running_ff_stacks`) |
| 6 | (e) tee | `test_make_test_without_tee_blocked`, `test_make_test_with_tee_allowed`, `test_make_lint_tail_blocked`, `test_pytest_without_tee_blocked`, `test_pytest_with_tee_allowed`, `test_pytest_version_allowed` |
| 7 | (f) tek yazar | `test_worker_writes_work_queue_blocked`, `test_coordinator_writes_work_queue_allowed`, `test_worker_writes_own_channel_allowed`, `test_worker_writes_other_channel_blocked`, `test_worker_writes_own_pr_allowed`, `test_other_worker_writes_pr_blocked`, `test_pr_alias_field_allowed`, `test_reviewer_writes_reviews_allowed`, `test_worker_writes_reviews_blocked`, `test_evidence_free_for_all`, `test_backslash_windows_path_normalized` |
| 8 | (f2) rol yok + kayıt | `test_no_role_single_writer_blocked`, `test_no_role_message_contains_session_id`, `test_no_role_non_owned_file_allowed`, `test_role_from_registry_session_id`, `test_role_from_registry_host_id`, `test_env_role_overrides_registry`, `test_registry_corrupt_is_loud`, `test_unknown_role_is_no_role` |
| 9 | (g) worktree state | `test_worktree_state_write_blocked_for_coordinator`, `test_worktree_non_state_write_allowed` |
| 10 | (h) kip | `test_warn_mode_exit0_with_message`, `test_block_is_default`, `test_unknown_mode_blocks_loudly` |
| 11 | (i) kayıt | `test_block_writes_log_line_without_content`, `test_warn_writes_log_line`, `test_log_truncates_to_120` |
| 12 | dayanıklılık | `test_non_matching_tool_allowed` (Read/Glob), `test_malformed_stdin_blocks_loudly` (bozuk JSON → çıkış 2 + mesaj; S9), `test_fast_under_200ms` (yığın kuralı hariç, tek çağrı) |
| 13 | ayar biçimi | `test_settings_json_valid_and_wires_guard` (JSON parse; PreToolUse'da `Bash` ve `Edit\|Write\|MultiEdit\|NotebookEdit` matcher; komut `ffcore_guard.py`'yi gösterir; deny listesinde `.env` ve PayCore kalıpları) |
| 14 | gerçek çağrı (kabul "gerçek oturumda tetikleme") | test değil, kanıt dosyası `state/evidence/hook-real-call.log` (madde 5a) |

### 5a. Ayar biçimini gerçek çağrıyla doğrulama

Bilinen (belgeye karşı **doğrulanmadı**, dış ağ açılmadı; 2.1.321 bilgimden): PreToolUse girdisi stdin JSON `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `tool_name`, `tool_input`; çıkış 2 = engel ve stderr modele; çıkış 0'da stderr modele **gitmez** (yalnız ayrıntılı kipte kullanıcıya), stdout JSON `systemMessage`/`hookSpecificOutput` alanları var; ayar proje kökü `.claude/settings.json`; `$CLAUDE_PROJECT_DIR` = oturumun proje kökü (worktree'de açılan oturumda worktree yolu); hook'lar oturum başında anlık görüntü alınır.

Doğrulama adımları (hepsi kanıt dosyasına, `tee`):
1. **Girdi kaydı:** settings.json'a geçici olarak bir "dump" hook'u değil, guard'ın kendisi; guard `FFCORE_GUARD_DEBUG_DUMP` olmadan girdi yazmaz. Bunun yerine warn kipindeki kayıt satırı + stderr, alan adlarını kanıtlar (`session_id` kayıt mesajında görünür).
2. **Kendi oturumumda (önce bu):** worktree'de `.claude/settings.json` yazıldıktan sonra zararsız tetikleyici `echo make test` (kural e, warn) ve `echo .env` koşarım; `state/evidence/hook-guard.log`'da satır oluşursa bu oturumun worktree ayarını okuduğu kanıtlanır. Bu oturum ana checkout'ta başlayıp worktree'ye geçti ve hook'lar oturum başında anlık görüntü alınıyorsa **tetiklenmeyebilir**; bu da kanıt olarak yazılır (worktree ayarının hangi koşulda okunduğunu gösterir).
3. **Başsız gerçek oturum (S10):** worktree dizininde `claude.exe -p --model haiku --permission-mode default "Run: echo make test"` + `FFCORE_GUARD_MODE=warn`, ayrıca `block` ile `echo make test` (engellenir, hiçbir şey çalışmaz). Çıktı: modelin stderr mesajını görüp görmediği (block), warn'da çıkış 0, kayıt satırı, `CLAUDE_PROJECT_DIR` değeri (guard warn mesajında yazar), `CLAUDE_CODE_HOST_SESSION_ID`'nin hook ortamına geçip geçmediği.
4. **Mutlak yol deny kalıbı:** PayCore verisine dokunmadan, scratchpad'de kanarya dosyası ve aynı biçimde (`Read(//c/Users/…/scratchpad/kanarya/**)`) geçici deny ile Read denemesi; engellenirse `//c/...` biçimi doğrulanır, sonra kalıp PayCore yollarına yazılır. Gerçek PayCore yolu hiçbir doğrulamada okunmaz.

### 6. Migration

Yok.

### 7. Geri alma

`git revert` (üç commit) ya da yalnız `.claude/settings.json`'dan `hooks` bloğunu kaldırmak; acil durumda `FFCORE_GUARD_MODE=warn` engeli kaldırır ama kaydı sürdürür. Hook bozulursa (Python yok vb.) Claude Code çağrıyı engellemez, hata gösterir: bu fail-open durumu docs'ta yazılır (S9).

### 8. Durma koşulları

- Gerçek çağrıda hook girdisi alanları ya da çıkış kodu anlamı beklenenden farklıysa: dur, DURUM + KARAR-GEREK.
- `//c/...` deny kalıbı kanaryada çalışmazsa PayCore kalıbını tahminle yazmam; KARAR-GEREK (Bash hook kalıbı yine korur).
- Hook warn kipinde bile bir oturumu kilitleyecek yanlış pozitif üretirse (ör. her Edit'te engel): dur.
- Merge sonrası etki: hook bu depodaki **bütün** oturumlarda (koordinatör dahil) devreye girer; eski tabanlı worktree'ler rebase edene kadar yüklemez. Koordinatörün `oturumlar.json`'ı merge'den önce doldurması gerekir, yoksa block kipinde herkes tek yazar dosyalarında engellenir (bu yüzden ilk gün warn).

### 9. Felsefe kontrolü

- **ARCH-07:** Değer: üç gerçek ihlal sınıfını (PROSES-175, K-05a-0011, OOM) ve tek yazar/push kuralını her oturumda, her çağrıda kapatır; ürün çekirdeğine (backend/frontend) sıfır karmaşıklık. Bedel: tek stdlib betiği + ayar dosyası + oturum kaydı bakımı (koordinatör). Kalıcı karmaşıklık süreç katmanında, kabul edilebilir.
- **ARCH-09:** Claude Code'un kendi `permissions.deny` ve `PreToolUse` mekanizması kullanılıyor; deny ile ifade edilebilen (dosya okuma/yazma) deny'a, ifade edilemeyen (komut bağlamı, rol, yığın sayımı) hook'a. Paralel izin sistemi kurulmuyor. `permissions.deny` Bash kalıpları (`Bash(git push:*)`) push için yeterli değil (rol + bayrak koşulu yok) → hook.
- **ARCH-10 / ARCH-06:** Kip açık (`FFCORE_GUARD_MODE`, varsayılan `block`, bilinmeyen değer `block` + uyarı); rol kaynağı sırası açık ve mesajda yazılı; rol yok, kayıt bozuk, yığın sayılamıyor, stdin bozuk → engel + gerekçe (sessiz serbest yok). Bilinen fail-open'lar (Python yok, `bash -c`, Bash ile state yazımı) gizlenmiyor, docs'ta "güvenlik ağı, sandbox değil" altında listeleniyor.

## Açık sorular (koordinatöre; her biri A/B/C, önerilen önce)

- **S1 Rol kaydının anahtarı.** **A (önerilen):** `oturumlar.json` anahtarı hem Claude Code `session_id` (hook girdisi) hem masaüstü `local_…` kimliği olabilir; hook önce `session_id`, sonra ortamdaki `CLAUDE_CODE_HOST_SESSION_ID`'ye bakar (ortama geçtiği gerçek çağrıda doğrulanırsa). Koordinatör `local_…`'ı start_session'dan zaten bilir; bilmediği `session_id`'yi oturum `echo $CLAUDE_CODE_SESSION_ID` ile ACK'te bildirir. Etki: kayıt koordinatöre ek adım istemez. **B:** yalnız `session_id` (brief'teki gibi); her oturum ilk mesajında kimliğini bildirir, koordinatör yazar. Etki: bir gidiş-dönüş gecikme, rol yokken ilk tek yazar yazımı engellenir. **C:** worktree başına `.claude/settings.local.json` `env.FFCORE_ROL` (gitignore satırı gerekir). Etki: ana checkout'taki koordinatör/inceleyici ayrışmaz, ek gitignore değişikliği; önermiyorum.
- **S2 warn kipinin görünürlüğü.** Çıkış 0'da stderr modele gitmiyor (doğrulanacak). **A (önerilen):** warn'da stderr + stdout JSON `{"systemMessage": "<mesaj>"}` (kullanıcıya görünür uyarı; izin kararını değiştirmez, `permissionDecision` yazılmaz) + kayıt satırı. Etki: warn günü yanlış pozitifleri kullanıcı da görür. **B:** brief'teki gibi yalnız stderr + kayıt. Etki: ajan ve kullanıcı uyarıyı görmez, yalnız log; warn günü değerlendirmesi log'a dayanır. **C:** warn'da `hookSpecificOutput.additionalContext` ile modele de bildir (sürümde destek doğrulanmalı). Gerçek çağrı A'nın çalıştığını göstermezse B'ye düşmem, DURUM yazarım.
- **S3 yığın sayılamazsa.** **A (önerilen):** engel (fail-loud; docker yoksa `up` zaten başarısız olurdu, mesaj nedeni söyler). **B:** serbest + stderr uyarı. Etki: Docker Desktop yavaş açılırken sınır sessizce delinebilir.
- **S4 Bash ile state yazımı.** **A (önerilen):** bu PR'da kapsam dışı, bilinen sınır (kanal mesajlarımız da `python … newline=''` ile yazılıyor; Bash'te dosya yolu + yönlendirme tespiti yanlış pozitif doğurur). FOLLOWUP adayı. **B:** Bash komutunda tek yazar dosya adı + `>`/`>>`/`open(… 'w'`/`newline` kalıbı görülürse sahiplik denetimi. Etki: kısmi koruma, yüksek yanlış pozitif, rol yoksa kanal yazımı da engellenir.
- **S5 push bayrağının yeri.** **A (önerilen):** yalnız komut öneki `FFCORE_PUSH_OK=1 git push …` (kalıcı olamaz, o komuta özgü, kayıtta görünür). **B:** önek ya da hook ortamı (oturuma kalıcı `FFCORE_PUSH_OK=1` verilirse her push serbest kalır; "kalıcı değil" kuralını deler). Brief "ortam değişkeni" diyor; A daha dar ve kuralın amacına uygun → A'yı öneriyorum.
- **S6 Merge sonrası yayılım.** **A (önerilen):** koordinatör merge öncesi `oturumlar.json`'ı açık oturumlarla doldurur, merge sonrası açık worktree'lere rebase/merge-main ister ve warn gününü ilan eder; hook, `FFCORE_GUARD_MODE` belirtilmemişse `block`'tur, warn günü için `.claude/settings.json` `env.FFCORE_GUARD_MODE=warn` ile **gönderilir** ve block'a geçiş ayrı küçük commit. **B:** varsayılan `block` ile gönder, warn günü her oturumun kendi ortamında. Etki: masaüstü oturumlarında ortam değişkeni vermek pratik değil; ilk gün kilitlenme riski.
- **S7 pytest kapsamı.** **A (önerilen):** test toplayan her `pytest` çağrısı `tee` ister; `--version`, `--help`, `--collect-only` serbest. **B:** yalnız `make` kapı hedefleri. Etki: K-05a-0011'in kaynağı olan doğrudan pytest koşuları korunmaz.
- **S8 test için kök ayarı.** **A (önerilen):** `FFCORE_MAIN_ROOT` ortamı ana kökü açıkça geçersiz kılar (testler geçici dizin kullanır, gerçek `state/`'e yazmaz); belgelenir. **B:** testler gerçek ana köke yazar. Etki: test koşusu gerçek hook-guard.log'u kirletir.
- **S9 bozuk stdin / beklenmeyen istisna.** **A (önerilen):** engel (çıkış 2) + mesaj; guard'ın kendi hatası da kayda yazılır. **B:** serbest (çıkış 0). Etki: guard'daki bir hata bütün kuralları sessizce kapatır.
- **S10 Başsız gerçek oturum.** **A (önerilen):** worktree'de `claude.exe -p --model haiku` ile 2-3 kısa çağrı (warn: `echo make test`; block: `echo make test`), çıktı `state/evidence/hook-real-call.log`. Etki: kullanıcı hesabından birkaç küçük çağrı; Anthropic API zaten oturumların kullandığı yol, yeni dış sistem yok. **B:** yalnız kendi oturumumda dene; tetiklenmezse kullanıcıdan worktree'de yeni oturum açmasını iste (koordinatör üzerinden). Etki: kanıt kullanıcı adımına bağlı, gecikir.

## Uygulama (PLAN-ONAY sonrası)

Dal `fix/ajan-hooklari`, main **9d38bc4** üzerine rebase edildi (önce b9f9fd7, 10c-1 merge sonrası 9d38bc4) (main'de docs/handbook ilerlediği için; dal yalnız yeni dosyalar eklediğinden temiz). Commit'ler (test/kod/docs ayrı):

| Commit | Tür | İçerik |
|---|---|---|
| 8248a00 | test | kırmızı testler (her kural engel/serbest çifti, warn, rol çözümü, kayıt, S9) |
| 6eb6c89 | test | guard modülünü `sys.modules`'a kaydeden fixture düzeltmesi; settings.json komutunu kabuksuz koşan uçtan uca test |
| 4a77cb7 | feat | `.claude/hooks/ffcore_guard.py`, `.claude/settings.json` (warn) |
| fc65c99 | test | arşiv dosyaları yalnız koordinatör; koordinatör rol kanallarından mesaj taşıyabilir (main'e gelen "Bağlam bütçesi ve arşiv" kuralı) |
| 20bbd6b | feat | aynı kural guard'da |
| 3ab062d | docs | ENVIRONMENT_AND_COMMANDS, SECURITY_AND_PERMISSIONS, MULTI_AGENT_PROTOCOL, BASLATMA, docs/takim 9.1 satır 1 + 9.2 |

Plandan sapmalar (gerekçeli):
1. **Hook komutu modül içe aktarır, betik koşmaz.** Ölçüm (`state/evidence/` dışı, oturum içi): bu makinede `py -3.12 -c pass` ≈ 0,9-1,2 sn; `py -3.12 ffcore_guard.py` ≈ 2,0-2,4 sn; aynı modülün `import`'u ≈ 1,1-1,3 sn. Tek satırlık `pass` betiği bile 3 sn sürdü: maliyet betik dosyasının kendisinde (büyük olasılıkla dosya taraması), guard kodunda değil (içe aktarmalar ~0,1 sn). Komut: `py -3.12 -c "import os, sys; sys.path.insert(0, os.path.dirname(sys.argv[1])); import ffcore_guard; sys.exit(ffcore_guard.run())" "$CLAUDE_PROJECT_DIR/.claude/hooks/ffcore_guard.py"`. `.pyc` `.claude/hooks/__pycache__/`'a yazılır (`.gitignore` `__pycache__/`). Ek olarak `dataclasses` (inspect çeker), `subprocess`, `datetime` tembel/çıkarıldı. `test_settings_command_runs_guard` bu tam komutu kabuksuz koşar.
2. **Arşiv kuralı** (plan sonrası main'e geldi): `state/arsiv/**`, `state/kanal/arsiv/**` → koordinatör; `state/kanal/<rol>.md` → o rol **ya da koordinatör** (MULTI_AGENT_PROTOCOL "Taşımaları yalnız koordinatör yapar"). İnceleyici/işçi başka rolün kanalına yine yazamaz.
3. **warn çıktısı:** stderr + stdout `{"systemMessage": "(warn) …"}` (S2 A); `permissionDecision` yazılmaz.

## Değişen dosyalar
- `.claude/hooks/ffcore_guard.py` (yeni, 560 satır; stdlib, ağ yok; yalnız `compose up`'ta `docker compose ls` alt süreci, 5 sn zaman aşımı)
- `.claude/settings.json` (yeni; `env.FFCORE_GUARD_MODE=warn`, deny, PreToolUse Bash + Edit|Write|MultiEdit|NotebookEdit)
- `tests/hooks/conftest.py`, `tests/hooks/test_guard.py` (yeni; 101 test)
- `handbook/ENVIRONMENT_AND_COMMANDS.md`, `handbook/SECURITY_AND_PERMISSIONS.md`, `handbook/MULTI_AGENT_PROTOCOL.md`, `BASLATMA.md`, `docs/takim/ajanlarla-gelistirme.md`
- backend/frontend/deploy/Makefile/state: **yok** (`git diff --stat main...HEAD`: 9 dosya +1419/-88)

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | `.env` engel / `.env.test`, `.env.example` serbest (Bash + yazma araçları) | `test_env_*` (9) | geçti |
| 2 | PayCore `data/**`, `eval/results/**` | `test_paycore_*` (3) + deny kalıbı `test_settings_json_valid_and_wires_guard` | geçti; `//c/` mutlak deny biçimi gerçek oturumda **doğrulanmadı** (Read ret çıktısı görülmedi; kalan risk) |
| 3 | push: koordinator+bayrak serbest; koordinator bayraksız, isci-a+bayrak, rol yok+bayrak, hook ortamında bayrak engel | `test_push_*` (6), `test_git_status_allowed` | geçti |
| 4 | compose build/up PROSES-175 | `test_compose_*` (8) | geçti |
| 5 | üç yığın sınırı, sayım hatası engel | `test_fourth_stack_blocked`, `test_third_stack_allowed`, `test_up_into_running_stack_allowed`, `test_stack_count_failure_blocks`, `test_stack_parser_counts_only_running_ff` | geçti |
| 6 | kapı `tee` | `test_make_*`, `test_pytest_*` (10) | geçti |
| 7 | tek yazar | `test_worker_*`, `test_coordinator_*`, `test_reviewer_*`, `test_pr_alias_field_allowed`, `test_evidence_free_for_all`, `test_*_path_normalized`, `test_all_write_tools_checked` | geçti |
| 8 | rol yok / kayıt | `test_no_role_*`, `test_role_from_registry_*`, `test_env_role_overrides_registry`, `test_registry_corrupt_is_loud`, `test_unknown_role_is_no_role` | geçti |
| 9 | worktree `state/` | `test_worktree_*`, `test_review_worktree_state_write_blocked` | geçti |
| 10 | warn/block kipi | `test_warn_mode_exit0_with_message`, `test_block_is_default`, `test_unknown_mode_blocks_loudly`, `test_allowed_call_prints_nothing` | geçti |
| 11 | kayıt satırı, içeriksiz, 120 karakter | `test_block_writes_log_line_without_content`, `test_warn_writes_log_line`, `test_log_truncates_to_120`, `test_allowed_call_writes_no_log` | geçti |
| 12 | dayanıklılık + S9 ek | `test_non_matching_tool_allowed`, `test_malformed_stdin_blocks_loudly`, `test_guard_internal_error_*` (5), `test_fast_decide` | geçti |
| 13 | settings biçimi + komut | `test_settings_json_valid_and_wires_guard`, `test_settings_command_runs_guard` | geçti |
| 14 | gerçek oturumda tetikleme (warn) | `state/evidence/hook-real-call.log` | **geçti (kısmi)**: worktree oturumunda Bash hook tetiklendi, `ENV` warn satırı ana `state/evidence/hook-guard.log`'a yazıldı (19:09:21), komut engellenmedi. Doğrulanmadı: kullanıcıya görünen `systemMessage` metni ve `Read .env` deny reddi (oturum çıktısı işçiye ulaşmadı). `echo make test` doğru biçimde tetiklemedi (kapı komutu değil) |

## Çalıştırılan komutlar
| Komut | Ortam | Exit | Süre |
|---|---|---|---|
| `py -3.12 -m pytest tests/hooks -q -p no:cacheprovider 2>&1 \| tee state/evidence/hook-tests-red.log` | host Python 3.12.10, pytest 9.0.2, kod yokken | 1 (80 failed, 14 error) | 22 sn |
| `… \| tee state/evidence/hook-tests-red-arsiv.log` (arşiv testleri, kod öncesi) | aynı | 1 (3 failed) | 5 sn |
| `py -3.12 -m pytest tests/hooks -q -p no:cacheprovider 2>&1 \| tee state/evidence/hook-tests.log` | HEAD 3ab062d (rebase sonrası) | 0 (**101 passed**) | 70 sn |
| `ruff check` + `ruff format --check` `.claude/hooks tests/hooks` → `state/evidence/hook-ruff.log` | ruff 0.17.3 (backend pin'i; yerel uv önbelleğindeki exe, ağ yok) | 0 | <1 sn |
| `make lint` / `make test` / iki profil | — | NOT_RUN: backend/frontend'e dokunulmadı (diff'te yok); `make lint` `.claude/` ve `tests/hooks`'u kapsamaz, yukarıdaki ruff koşusu onun yerine | — |
| başsız `claude.exe -p --model haiku` (S10) | worktree, warn | 1: CLI OAuth girişi süresi dolmuş; model çağrısı yok (sayım 1/3 deneme) | — |

Not: pytest koşuları ~60-80 sn; neredeyse tamamı alt süreç başına ~1 sn Python açılışı (makine).

## Varsayımlar ve brief'teki çelişkiler
- docs/takim 9.2 taslağındaki "push yalnız sekreter" satırı KARARLAR 16 Kasım ve K-HOOK-0002 ile çelişiyor; uygulanan: yalnız koordinatör + bayrak. Dalın tabanındaki (38ced4d) KARARLAR metni "rolden bağımsız engeller" diyor; ana checkout'taki güncel metin "yalnız koordinatör oturumunda koşar" (K-HOOK-0002); güncel metin uygulanır, dal tabanı state commit'iyle güncellenir.
- GOREV (b) "`FFCORE_PUSH_OK=1` ortam değişkeni" diyor; hook çağrının kendi ortamını değil Claude Code sürecinin ortamını görür, bu yüzden "o komut için" bayrak ancak komut önekinde anlamlı (S5).
- Baz main 38ced4d (GOREV f3fb5f9 dedi; arada yalnız state commit'i).

## Kalan riskler
- Hook bir güvenlik ağıdır, sandbox değil: `bash -c "…"` içi yakalanır (metin içinde), ama değişkenle kurulan komut (`c=pu; git ${c}sh`), betik dosyası, Makefile içi komutlar yakalanmaz.
- `.env` kalıbı tırnak içi metinlerde yanlış pozitif verebilir (ör. `grep -n "\.env" .gitignore`); warn günü bunu gösterir.
- `make lint` `.claude/hooks` ve `tests/hooks`'u denetlemiyor; PR'da ayrı `ruff check` koşusu.
- Her Bash ve dosya yazma çağrısı bu makinede ~1 sn hook gecikmesi alır (Python açılışı); yığın kuralı ayrıca `docker compose ls` (≤5 sn) bekler. Warn günü bu gecikmenin kabul edilebilirliği de gözlenmeli.
- Merge sonrası koordinatörün kendi oturumu da hook'a tabi: `state/oturumlar.json` kaydı yoksa ilk tek yazar yazımında (warn'da uyarı, block'ta engel) görünür.
