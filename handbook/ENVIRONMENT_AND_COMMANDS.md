# Ortam ve Komutlar

## Temel

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, `arq`; lint ve format `ruff`
- Node 20, Next.js 15, TypeScript, Tailwind, shadcn/ui, next-intl, next-themes
- Docker Compose (tek Linux sunucu); geliştirmede Docker Desktop (Windows)
- Kaynak düzeni PLAN.md 4; testler `backend/tests/{unit,contract,integration,e2e}`, `frontend/` Vitest + Playwright

Agent bu değerleri gerçek `pyproject.toml`, `package.json` ve CI'dan doğrular; uyuşmazlıkta `state/BLOCKERS.md`'ye `DRIFT-` kaydı.

## Taşınabilir Python komutu

- Windows: `py -3.12 -m ...`
- Linux: `python3.12 -m ...`

PR'da hangisinin kullanıldığı yazılır.

## Preflight (her oturum başı)

```bash
git status --short && git branch --show-current
py -3.12 --version
docker compose version
```

Agent `.env` oluşturmaz, kopyalamaz veya okumaz; gerekiyorsa kullanıcı doldurur. *(Hook ve `permissions.deny` ile zorlanır: `ENV`.)* Paket 00 MERGED olduktan ve Makefile hedefleri mevcut olduktan sonra ayrıca `make up && make smoke` koşulur. 00 öncesi bu iki komut preflight koşulu değildir.

## Kapı komutları

```bash
make lint      # ruff check + ruff format --check + npm run lint
make test      # pytest backend/tests/unit backend/tests/contract + vitest
make test-int  # pytest backend/tests/integration (compose ayakta)
make smoke     # /healthz, /readyz, Ollama /api/tags, OLLAMA_CONTEXT_LENGTH doğrulaması
make e2e       # Playwright, iki tema
make eval      # 13'ün sınav seti (M3 sonrası)
alembic heads  # tek head bekler
# Önyüz kapısı (node konteyneri, --network none, node_modules volume'u):
#   npm run lint && npm run typecheck && npm run check:api
# backend/openapi/*.yaml değiştiyse önce `npm run gen:api` (üretilen schema-*.d.ts aynı commit'te; PROSES-184)
```

Profil matrisi: `DEPLOY_PROFILE=airgap make test` ve `DEPLOY_PROFILE=llmaas make test` ikisi de koşar.

### Paralel yığınlar (işçi, inceleyici, main kapısı)

- Her yığın kendi compose projesi ve port aralığıyla açılır (`-p <ad>`, `BACKEND_PORT`/`FRONTEND_PORT`); konteyner açan her koşu önce kanala `YIGIN-AÇ`, kapanışta `down -v` + `YIGIN-KAPA`.
- **Dış bağlantı yok:** yığınlar `up -d --wait --no-build --pull never` ile ve işçinin doğruladığı etiketli imajla (`FFCORE_VERSION=<etiket>`) açılır. İmaj gerçekten yeniden derlenecekse `docker compose build --pull=false` (BuildKit aksi hâlde base imaj metadata'sı için docker.io/ghcr.io'ya gider; PROSES-175). `docker compose build` ve `up --build` çıplak kullanılmaz. *(Hook ile zorlanır: `PROSES-175`.)*
- **Bellek sınırı:** aynı anda en fazla üç yığın; main kapısı koşarken işçi/inceleyici yığınları açık kalabilir ama test koşmaz (KARARLAR "Üç yığın sınırı bellek sınırıdır"). Kapı adımı 137 (OOM) ile düşerse adım tek başına yeniden koşulur; ancak o yeşilse MERGED. *(Üç yığın sınırı hook ile zorlanır: `YIGIN`.)*
- Kapı çıktısı tamamen dosyaya alınır (`tee state/evidence/gate-<paket>-<tarih>.log`); yalnız son satır tutulmaz. *(Hook ile zorlanır: `KAPI`; `make lint|test|test-int|smoke|e2e`, test toplayan `pytest` ve `playwright test` aynı boru hattında `tee` ister. Bu, `docker compose … run|exec … tools make test` biçimi, `docker compose --profile e2e run --rm e2e` ve `sh -c '…'` içi için de geçerlidir.)*

### Hook ile zorlanan kurallar

`.claude/settings.json` her Bash ve dosya yazma çağrısından önce `.claude/hooks/ffcore_guard.py`'yi koşar (PreToolUse); `.env` ve PayCore verisi ayrıca `permissions.deny` ile kapalıdır. Kurallar, rol kaynağı ve bilinen sınırlar: docs/takim/ajanlarla-gelistirme.md 9.2.

- **Kip:** `FFCORE_GUARD_MODE=block` (varsayılan; çağrı çalışmaz, mesaj modele gider) ya da `warn` (çağrı çalışır; uyarı **modele gitmez**, yalnız kullanıcıya `systemMessage` olarak görünür ve kayda düşer). Bilinmeyen değer `block` sayılır.
- **Kayıt:** her tetiklenme `state/evidence/hook-guard.log`'a tek satır (zaman, kip, rol, araç, kural, komutun **maskeli** ilk 120 karakteri: URL kimliği, `*KEY/TOKEN/SECRET/PASS*=` değerleri, `Authorization`/`Bearer`, `-u`/`--user` `kullanıcı:parola` (bitişik ve `=` biçimi dahil) ve adı `token`, `secret`, `password`, `api_key`/`apiKey`, `key` ile biten JSON alanlarının değerleri (kaçışlı tırnakla da) `***` olur; dosya içeriği yok). Dalga raporu bu dosyayı sayar.
- **Yükleme (gözlem, docs/takim 9.2):** ana checkout'ta çalışan oturum oradaki `.claude/settings.json` ve guard ile denetlenir; ayar main'e merge edilince merge'den önce açılmış oturumlar da yeni ayarla denetlendi (`hook-guard.log`, 16 Kasım 22:26). Worktree'de değişen guard aynı oturumu etkilemez; tabanı eski worktree'lerde hook dosyaları rebase'e kadar yoktur.
- **Testler:** `py -3.12 -m pytest tests/hooks tests/scripts -q 2>&1 | tee state/evidence/hook-tests.log` (Docker gerekmez; `tests/scripts` = `scripts/kanal_ozet.py`).
- Hook güvenlik ağıdır, sandbox değil; bu belgedeki metin kuralları geçerliliğini korur. Bilinen sınırlar (docs/takim 9.2): değişkenle kurulan komut, betik dosyası, Makefile tarifleri, Bash ile state yazımı. Komut başındaki `env [K=V]…`, `command`, `exec`, `time`, `nice`, `nohup` sarmalayıcıları, kabuk anahtar sözcükleri (`if/then/do/while/until/!`), `bash -o <seçenek> -c '…'`, `$(…)` ve ters tırnak içi, `{ …; }` ve `( … )` grupları ile `for/while/if … done/fi` gövdeleri denetlenir; grubun ya da döngünün arkasındaki `| tee` gövdedeki kapıyı karşılar (fix/ajan-hooklari-2). İç içe `sh -c` / `compose run|exec` / `$(…)` 3 düzeyi aşarsa `GUARD-DERINLIK` ile engellenir. `ENV` yalnız yol konumundaki `.env`'i yakalar (argüman, yönlendirme, `--opt=` değeri, `-v` birimi, tırnak ya da `(` sonrası); boşluklu tırnaklı metin, veri heredoc'u (`cat > f <<EOF`) ve `grep`/`rg` deseni ya da `--exclude`/`-g` süzgeci serbesttir. `sh`/`bash`'in okuduğu heredoc gövdesi komut, `py`/`python`/`node`'un okuduğu gövde ve `-c`/`-e` argümanı kod sayılır ve taranır (kodda metin olarak geçen `.env` de engellenir; kabul edilen yanlış pozitif). Tek kelimelik metin (`echo .env`, `git commit -m ".env"`) yanlış pozitif verir. `timeout`, `xargs`, `sudo` sarmalayıcıları ve `case` kolları denetlenmez.

## Bayraklar

| Değişken | Anlam |
|---|---|
| `DEPLOY_PROFILE=llmaas\|airgap` | ürün profili; varsayılan `llmaas` |
| `INFERENCE_BACKEND=ollama\|vllm` | airgap çıkarım arka ucu |
| `VECTOR_BACKEND=pgvector\|qdrant` | vektör sürücüsü |
| `FAKE_LLM=1` | model çağrıları deterministik sahte; unit ve çoğu entegrasyon testinin varsayılanı |
| `RUN_OLLAMA_TESTS=1` | gerçek Ollama isteyen işaretli testler |
| `RUN_QDRANT_TESTS=1` | Qdrant konteyneri isteyen testler |
| `OFFLINE=true` | dış ağ gerektiren her şey kapalı ya da iç aynaya yönlü |
| `REGISTRY_PREFIX` | tüm imaj adlarının öneki; iç registry |

Bayraksız atlanan testler PR'da `NOT_RUN` olarak görünür.

## Geliştirme ve üretim farkı

| | Geliştirme makinesi | Üretim/test sunucusu |
|---|---|---|
| İnternet | var; Anthropic API ile geliştirme | yok; iç registry ve PyPI aynası |
| Model | Anthropic (llmaas) + Ollama küçük model | Qwen 3.5 35B Ollama CPU (airgap testi) ya da sağlayıcı (llmaas) |
| Veri | sentetik `data/samples/` | pilotta sentetik; gerçek belge kullanıcı kararıyla |

Hostname ya da IP üretim ya da kurum ağına işaret ediyorsa test çalıştırma; bağlantı testleri yalnızca `localhost` ve compose servis adlarına.

## PayCore referans deposu

`C:\ai_paycore\paycoreLLM`: yalnızca `src/`, `CLAUDE.md`, `docs/agentic/referans/`, `compose.yml` okunur; `eval/`, `data/`, `experts/` okunmaz. Ölçüm ve ders kaynağıdır; kod kopyalanmaz, bu planın veri modeline uyarlanır (PLAN 5, KARARLAR).
