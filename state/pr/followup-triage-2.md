# [B] fix/followup-triage-2: FOLLOWUP 219, 216, 220, 221, 214, 215

**Paket:** followup-triage-2 · **Sınıf:** [B] (davranış düzeltmeleri; sözleşme ve API değişmez; 220 [B] K-TR2-0002 S2) · **Branch:** `fix/followup-triage-2` · **Baz commit:** d6d2029 (main 31a9944 + dalga 9 state) · **HEAD:** `135c36924d99b4ff8d9a4709c6c9cc29dfde72d3` · **Delta:** `main..135c369` (d6d2029..135c369), 9 commit, 30 dosya · **İşçi:** isci-b (lease ffcore-isci-b-triage2) · **Görev / onay:** K-TR2-0001, K-TR2-0002 (PLAN-ONAY, S1-S5 A), K-TR2-0003 (test-int slotu, zone A)

## Plan

Plan, bulunan semboller ve riskler B-TR2-0002 ile yazıldı ve onaylandı; özeti aşağıda. Plandan iki sapma:
- **215:** düşüş listesi `knowledge.worker` ile değil **boş** liste ile kapandı. Düşüş ortama bağlıydı: modül import anında `REDIS_URL` ister; compose `tools` servisi onu verir, çıplak `docker run` vermez. Yürüyüş sahte bir `REDIS_URL` (yalnız ayrıştırılır, bağlanılmaz) verir; böylece iki bağlamda aynı sonuç alınır ve her düşüş testi kırar (listede olup artık düşmeyen de).
- **221:** ekran görüntüsü çağrısı 21 değil **19** (13 spec); 20. eşleşme bir yorum satırıydı.

### Felsefe kontrolü
1. ARCH-07: altı dilim de var olan davranışı düzeltir; yeni özellik yok. Kalıcı ek olarak tek bir `Dockerfile.e2e` ve 30 satırlık bir test yardımcısı geliyor.
2. ARCH-09: Docker'ın boş adlandırılmış volume'u imaj içeriğiyle doldurma davranışı kullanıldı; ayrı bir önbellek ya da senkron mekanizması kurulmadı.
3. ARCH-06/10: 219'da sessiz `skipped` biter (model penceresi agent olmadan da denetlenir); 220'de kilit uyuşmazlığı `e2e_deps_stale` ile durur, sessiz `npm ci` yok; 221'de yazma yeri açık değişken, boşsa yazmaz, verilmiş ama olmayan dizin açık hata; 215'te bilinmeyen import düşüşü testi kırar.

## Değişen dosyalar
- `.claude/hooks/ffcore_guard.py` (214: `unquoted_heredocs` yorum kesimi; `heredoc_commands` yorumsuz satırı okur; `unwrap` `timeout`; `reader_command`'daki artık ölü `timeout` dalı kaldırıldı)
- `backend/ffcore/core/readiness.py` (219: `_context_needs` `context_window`; `NO_NEED` metni; detay `largest needed context=N`; docstring)
- `deploy/docker-compose.yml` (yalnız `e2e` servisi: `build` + `image: ffcore/e2e:${FFCORE_VERSION}`, `PLAYWRIGHT_IMAGE` build argümanı aynı digest, komut `npm run test:e2e`, `E2E_SCREENSHOT_DIR`)
- `frontend/Dockerfile.e2e` (yeni; 220)
- `frontend/tests/e2e/screenshots.ts` (yeni; 221) + 13 spec'in yalnız screenshot satırları ve import'u
- testler: `tests/hooks/test_comments_timeout.py` (yeni), `backend/tests/unit/test_hke_208_settings_classes.py`, `backend/tests/integration/test_04a_readyz.py`, `test_04b_2_readyz.py`, `test_06a_readyz.py`
- docs: `docs/onyuz.md`, `docs/bilgi-tabani.md`, `docs/degisiklikler.md`, `docs/takim/ajanlarla-gelistirme.md` (tek satır, K-TR2-0003 A), `handbook/MULTI_AGENT_PROTOCOL.md`, `handbook/templates/PR_SABLONU.md`, `handbook/ENVIRONMENT_AND_COMMANDS.md`
- `frontend/app/**` ve `backend/ffcore/memory/**` diff'te **yok** (`git diff --name-only main..135c369`).

## Commit'ler (test / kod / docs ayrı)
| SHA | Tür | Dilim |
|---|---|---|
| bcfa9d5 | test | 214 hook testleri (kırmızı: 14 düştü, `tr2-214-red.log`) |
| d363613 | kod | 214 yorum + `timeout` |
| efdc596 | test | 215 (kırmızı: `knowledge.worker` düşüşü, `tr2-215-red.log`) |
| b882340 | test | 219 readyz testleri (kırmızı: 10 düştü, `tr2-219-red.log`) |
| b964a07 | kod | 219 readiness |
| 5dcab87 | test | 221 yardımcı + 19 çağrı |
| b0d43c0 | kod | 220 imaj + compose (221 ortam değişkeni) |
| aa35180 | docs | 219/220/221/214/216 |
| 135c369 | docs | ajanlarla-gelistirme.md:670 |

## Kabul kriterleri → testler
| Dilim | Kriter | Test / kanıt | Durum |
|---|---|---|---|
| 219 | model anahtarı `context_window`, agent `context_tokens` toplanır | `test_04a_17b_context_configuration_invalid` (yalnız model satırı, agent yok: 8192 → 503, None → 503, 32768 → 200 + `largest needed context=16000`) | geçti ×2 profil |
| 219 | `ollama_runtime_context` agent olmadan çalışır | **yeni** `test_04b_2_219_model_window_is_checked_without_an_agent` (`/api/ps` 8192 < pencere 16000 → 503) + mevcut 7 test yeni anahtarla | geçti ×2 |
| 219 | eski `context_tokens` model satırı sayılmaz (S5 A) | **yeni** `test_04a_17b_legacy_context_tokens_key_is_not_counted` (900000 değeri detayda yok, 503 yok) | geçti ×2 |
| 219 | model penceresi ve agent bütçesi birlikte, büyüğü kazanır | **yeni** `test_06a_219_model_window_and_agent_budget_both_count` (pencere 32768 + agent 24000; 24000 → 503 `largest needed context=32768`) | geçti ×2 |
| 214 | `#` yorumundaki kesme işareti sonraki komutları saklamaz | `test_214_apostrophe_in_comment_does_not_hide_later_commands` (7 biçim: KAPI, PUSH, PROSES-175, heredoc, grup) | geçti |
| 214 | `timeout`/`nice`/`nohup` ardındaki komut denetlenir | `test_214_timeout_nice_nohup_wrappers_are_checked` (11 biçim; `nice`/`nohup` regresyon) | geçti |
| 214 | yanlış pozitif yok | `test_214_harmless_forms_allowed` (`$#`, `${#a}`, `a#b`, tırnak içi `#`, `-m 'fix #12'`, tee'li `timeout`) | geçti |
| 215 | beklenmeyen import düşüşü testi kırar | `test_hke_215_import_failures_are_the_expected_ones` | geçti |
| 215 | egress alan kümesinin tamamı | `test_hke_215_egress_fields_match_what_the_egress_client_reads` (egress.py kaynağıyla sürüklenme) + `test_hke_every_egress_settings_class_declares_the_proxy` (beş alan) | geçti |
| 221 | boşsa yazmaz | e2e `test_10mrk_5` 4/4, `git status docs/images` 0 satır (`tr2-221-e2e-empty.log`) | geçti |
| 221 | doluysa yazar | `E2E_SCREENSHOT_DIR=/tmp/shots` 4/4, 4 PNG (`tr2-221-e2e-set.log`) | geçti |
| 221 | olmayan dizin açık hata | `E2E_SCREENSHOT_DIR=/tmp/missing` → `… is not a directory` (`tr2-221-e2e-missing.log`) | geçti (beklenen düşüş) |
| 220 | e2e koşusu ağa çıkmaz, `down -v` etkilemez | volume silindikten sonra imajdan dolum 498 paket + kilit eşit (`tr2-220-lock.log`); koşularda `npm ci` yok, imaj kurulumu `#3 load metadata … DONE 0.0s` yerel (`tr2-220-build.log` satır 12-13) | geçti |
| 220 | kilit değişince sessiz kurulum yok | damga bozulunca `e2e_deps_stale`, çıkış 1 (`tr2-220-lock.log`) | geçti |
| 220 | compose geçerli | `docker compose … --profile e2e config` 0 (`tr2-220-compose-config.log`) | geçti |
| 216 | handbook + şablon cümlesi | `handbook/MULTI_AGENT_PROTOCOL.md` "Tam test-int slotu (ENV-209, FOLLOWUP-216)", PR şablonu satırı | docs |

## Bilerek değişen testler
- `test_04a_readyz.py::_ollama_model`: parametre `context_window` (eski `context_tokens` yazıyordu; API'nin yazamadığı anahtar). `test_04a_17b_context_configuration_invalid` artık kendi modelini sonunda pasifler (paylaşılan DB'ye sızmıyor) ve detayı doğrular.
- `test_04b_2_readyz.py` `untagged_project` fikstürü: `{"context_window": 16000}`; modül docstring'i.
- `test_06a_readyz.py::_ollama_agent`: isteğe bağlı `model_limits`; mevcut test aynı.
- `test_hke_208_settings_classes.py`: `_settings_classes` artık `(sınıflar, düşenler)` döner; düşüş yutulmaz.
- 13 e2e spec: yalnız screenshot satırı (`saveScreenshot`) ve import; assert'ler aynı.

## Çalıştırılan komutlar
Tümü `ffcore-tr2` (18220/13220, `FFCORE_VERSION=0.0.0-tr2`, `.env.test`), Windows host `py -3.12`; kayıt `state/evidence/`.

| Komut | Ortam | Sonuç | Log |
|---|---|---|---|
| `make lint` + `ruff check/format --check .claude/hooks tests/hooks` | tools | 0 | `tr2-gate-unit.log` |
| `alembic heads` | tools | tek head | `tr2-gate-unit.log` |
| `make test` (`pytest tests/unit tests/contract`) | `DEPLOY_PROFILE=llmaas` | 2161 passed | `tr2-gate-unit.log` |
| `make test` | `DEPLOY_PROFILE=airgap` | 2161 passed | `tr2-gate-unit.log` |
| önyüz `lint`, `typecheck`, `check:api`, Vitest | node 20.19.5-alpine `--network none` | 0 / 0 / 0 / 323 passed (60 dosya) | `tr2-gate-unit.log` |
| `py -3.12 -m pytest tests/hooks` | host | 448 passed | `tr2-gate-unit.log`, `tr2-214-hooks.log` |
| readyz test-int (04a, 04b-2, 06a) | llmaas, airgap | 17/17 ×2 (kod öncesi 10 düştü) | `tr2-219-red.log`, `tr2-219-green-{llmaas,airgap}.log` |
| **tam test-int** `QDRANT_URL=http://qdrant:6333 RUN_QDRANT_TESTS=1 pytest tests/integration` (ENV-209 slotu K-TR2-0003, HEAD aa35180) | `.env.test` | **1193 passed, 42 skipped, 0 failed** (16:54) | `tr2-test-int-full.log` |
| e2e imaj kurulumu `--profile e2e up --build --pull never --no-start --no-deps e2e` | | 0, metadata yerel | `tr2-220-build.log` |
| e2e kısa koşu `test_10mrk_5` × üç kip | e2e | yukarıdaki tablo | `tr2-221-e2e-*.log` |

Tam test-int aa35180'de koştu; sonraki tek commit (135c369) yalnız `docs/takim/ajanlarla-gelistirme.md`'de bir cümle; o dosyayı okuyan tek kod `scripts/context_budget.py` (boyut ölçümü, test değil).

## Çıktı özeti ve post-state
- R1 (219) çıkmadı: tam test-int'te `/readyz` çağıran hiçbir test kırılmadı; fikstür değişikliği gerekmedi.
- Kurulum etkisi (`degisiklikler.md` "Action"): `INFERENCE_BACKEND=ollama` ve `OLLAMA_CONTEXT_LENGTH` aktif bir Ollama modelinin `context_window`'undan küçükse `/readyz` artık 503 `context_configuration_invalid` (önceden gizliydi). Seed (32768) ve `.env.test`/`.env.example` (32768) uyumlu.
- Koordinatör kapı betiği: 221 varsayılanı boş olduğu için değişmez; e2e adımı yalnız `npm ci && ` önekini bırakmalı ve önce imajı kurmalı (`docs/onyuz.md` reçetesi; `npm ci` kalırsa çalışır ama yine ağa çıkar).
- isci-c (14): yeni spec'ler `saveScreenshot` kullanmalı (K-14-0002 notu).
- Yığın `ffcore-tr2` PR-HAZIR sonrası `down -v` + YIGIN-KAPA ile kapanır; `ffcore/e2e:0.0.0-tr2` ve `ffcore/tools:0.0.0-tr2` etiketleri kalır (temizlik koordinatörde).

## r2 (R-TR2-0003 MINOR-1/2, NOTE-2/4; K-TR2-0006)

SHA `89df92829fa76c6eea1975fcad5136c1091e36d5`; delta `135c369..89df928`: 3 commit, 7 dosya, +91/-21. Yığın açılmadı (compose yığını yok; yalnız `--network none` çıplak konteynerler, volume yok).

| Commit | İçerik |
|---|---|
| 95731be | test(hooks): iki yönlü r2 biçimleri (`tests/hooks/test_comments_timeout.py`) |
| ae327cf | fix(hooks): `unquoted_heredocs` bash gibi okur (`LineState`: tırnak, `${` derinliği, satır sonu `\` birleşmesi; kaçışlı karakter sonrası `#` yorum değil; `<` `>` kelime başı) |
| 89df928 | docs: onyuz reçetesi, degisiklikler 219 ikinci etki, protokol atfı, docs/takim 668/670, handbook ENV:62 |

- **MINOR-1:** kırmızı önce (`tr2-r2-hooks-red.log`: 9 failed / 8 passed). Yakalanır (PUSH/KAPI): X1 `${a/ #x/y}`, X2 `${a# #}`, X3/X4 `foo\`⏎`#bar`, X24 `${a// #}`, iç içe `${a:-${b/ #x}}`, kaçışlı boşluk `foo\ #x` (rapor dışı, aynı sınıf; bash'te push koşar). Yorum kalır: `[[ a =~ #b ]]`, `>#b`, `<#x`, `${a} # …`, `foo \`⏎`# …`, `foo\\ # …`, `&& \`⏎`#c`, `&&\`⏎`#c`, ters bölüyle biten yorum satırı. Her biçim bash 5.2'de stdin ile doğrulandı (`tr2-r2-bash-semantics.log`; `bash -c` Windows argv'de ters bölüyü bozduğu için stdin). İnceleyici probe biçimleri r1 ve r2 hook'unda yan yana (`tr2-r2-hook-probe.log`, logdan ayrıştırılan 65 biçim): 7 değişti, hepsi beklenen: X1, X2, X3, X4, X24 `[]`→PUSH/KAPI; X10 `>#b`, X21 `<#x` PUSH→`[]` (bash yorum sayıyor, komut koşmuyor). Hook testleri host `py -3.12`: **465 passed** (`tr2-r2-hooks.log`, HEAD 89df928); ruff check + format temiz (`tr2-r2-lint.log`).
- **Varsayım (r2):** `>#b` ve `<#x` bash'te yorum (sözdizimi hatası, sonraki komut koşmaz); hook artık onları yorum sayar. Bu yanlış pozitifin kalkmasıdır, yanlış negatif değildir.
- **MINOR-2:** reçete göreli `E2E_SCREENSHOT_DIR=../docs/images` (yardımcı `/work/frontend`'den çözer) + Git Bash notu. Koşarak doğrulandı (`tr2-r2-221-recete.log`): `compose config` göreli değeri olduğu gibi, mutlak değeri `C:/Program Files/Git/work/docs/images` gösteriyor; çıplak e2e imajında (`--network none`, backend'siz probe spec) göreli değer `/work/docs/images`'a PNG yazdı (1 passed). Checkout'un `docs/images`'ı değişmedi (probe dizini scratch).
- **NOTE-2:** `docs/degisiklikler.md` Action: aktif Ollama modeli + yayımlanmış agent yok + Ollama cevap vermiyor → 503 `ollama_unreachable` (önceden `skipped`).
- **NOTE-4:** protokol atfı '11-1 main kapısı KIRMIZI'; docs/takim 668 sarmalayıcı listesine `timeout`; 670 yorum kuralı açık (satırın kalanını saklar, denetlenmez; `${…}`, kaçış ve `\`-birleşme istisnaları); handbook ENV:62 aynı cümle.
- **Kural (5):** r2 loglarının hepsi komut satırı + `HEAD=` ile başlıyor.
- Bilerek değişen test yok (yalnız eklenen testler).

## Kapsam dışı / öneriler
- FOLLOWUP-222 (koordinatör açtı): `docker compose run --build` hook'ta denetlenmiyor.
- Hook `ENV` kuralı yorumdaki `.env`'i hâlâ yakalar (bilinçli, güvenli yön; handbook cümlesinde yazılı).

## Kontrol listesi
- [x] Felsefe ile çelişen nokta yok; sapmalar yukarıda yazılı
- [x] Donmuş sözleşme kırılmadı (API, OpenAPI, C13 metni aynı; yalnız `/readyz` detay metni)
- [x] İki profil testi koştu
- [x] Mutasyon ucu değişmedi
- [x] Log, PR, kanal secret-free (yalnız `.env.test` sahte değerleri)
- [x] UI metni değişmedi; e2e iki tema spec'leri aynı assert'lerle

🤖 Generated with [Claude Code](https://claude.com/claude-code)
