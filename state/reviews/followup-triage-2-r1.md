# Review followup-triage-2 r1 · FOLLOWUP 219, 216, 220, 221, 214, 215
SHA: 135c36924d99b4ff8d9a4709c6c9cc29dfde72d3 · Sonuc: ONAY · Bulgu: B0 M0 m2 N4

- **İncelenen tam SHA:** `135c36924d99b4ff8d9a4709c6c9cc29dfde72d3` (dal `fix/followup-triage-2`).
- **Delta** `d6d2029..135c369`: 9 commit, 30 dosya, +405/−82. `state/`, `.env`, `frontend/app/**`, `backend/ffcore/memory/**` yok.
  - test bcfa9d5, efdc596, b882340, 5dcab87
  - kod d363613, b964a07, b0d43c0
  - docs aa35180, 135c369
- **İstek:** K-TR2-0005 (yedi odak). Kararlar: KARARLAR "triage-2 plan kararları" (S1-S5 A), BLOCKERS 214, 215, 216, 219, 220, 221 (222 kapsam dışı).
- **İnceleyici:** lease `ffcore-inceleyici-d9` (Fable 5.2). Tam test-int koşmadım (ENV-209; işçinin 1193/42/0 logu `tr2-test-int-full.log`).
- **Yöntem:**
  - Delta satır satır okundu (guard, readiness, testler, compose, Dockerfile.e2e, yardımcı, 13 spec, docs, handbook).
  - `git archive 135c369` kopyası; probe dosyaları yalnız kopyada (dalın parçası değil).
  - Hook: dal guard'ı ile baz guard'ı (d6d2029) aynı 70 komutta yan yana `decide()` ile karşılaştırıldı; şüpheli biçimlerin gerçek bash davranışı zararsız `echo` ile doğrulandı.
  - Yığın `ffcore-rv` (R-TR2-0002): `postgres` + `redis`, `tools` imajı `0.0.0-tr2` (kaynak kopyadan bağlı), e2e imajı `0.0.0-rv` kopyadan kuruldu. Backend, frontend, LiteLLM açılmadı.
- **Karar: ONAY.** Yedi odağın hepsi kodda ve probe'da doğrulandı; BLOCKER ve MAJOR yok. İki MINOR merge'ü bekletmez: MINOR-1 odak 7'nin cevabıdır (yeni yorum kesimiyle dört biçimde kural atlanıyor, bazda yakalanıyordu) ve FOLLOWUP-222 hook dilimine eklenmesini öneriyorum.

## Testler
`HEAD=` satırlı loglar `state/evidence/tr2-r1-rv-*.log`.

| Koşu | Sonuç |
|---|---|
| Hook + script testleri, host `py -3.12` (`-hooks.log`) | `tests/hooks tests/scripts`: **459 passed** |
| Hook probe'u, dal ve baz yan yana (`-hook-probe.log`) | 70 biçim; 40'ında sonuç değişti: 33 iyileşme, 7'sinde baz yakalıyor dal yakalamıyor (5 satır, dört ayrı biçim gerçek: MINOR-1; 2'si bash'te de yorum) |
| Bash davranışı (`-bash-semantics.log`) | bash 5.2.12: dört biçimde sonraki komut koşuyor; `[[ a =~ #b ]]`, `$(( 2 # 1 ))`, `>#b` bash'te de yorum (hook ile tutarlı) |
| Yığın (`-up.log`) | `postgres`, `redis` sağlıklı |
| readyz test-int + probe, llmaas (`-readyz-llmaas.log`) | `test_04a_readyz`, `test_04b_2_readyz`, `test_06a_readyz` 17 + probe 3: **20 passed** |
| aynı, airgap (`-readyz-airgap.log`) | **20 passed** |
| 215 unit + probe (`-215.log`) | 6 passed; `REDIS_URL` ortamda yokken de 6 passed; bozuk import ve altıncı egress alanı testi kırıyor |
| e2e imaj kurulumu (`-220-build.log`) | `up --build --pull never --no-start --no-deps e2e` 0; `load metadata … DONE 0.0s`, katmanlar CACHED |
| Volume dolumu (`-220-volume.log`) | boş volume ilk bağlamada 498 paket, kilit damgası eşit, `npm` çağrısı yok |
| Kilit ve ekran görüntüsü kipleri (`-220-221.log`, `-221b.log`) | aşağıda odak 4 ve 5 |
| ruff, tsc, eslint (`-lint.log`) | ruff check/format 0 (14 dosya); `tsc --noEmit` 0; `eslint tests/e2e` 0 |
| `down -v` (`-down.log`) | 0; ffcore-rv konteyner, volume ve ağ 0 |

Koşmadıklarım: tam test-int, `make test` iki profil, Vitest, gerçek konsola karşı e2e (`test_10mrk_5` üç kip). Bunlar için işçi logları okundu, bağımsız tekrar edilmedi.

## Kontrol listesi (K-TR2-0005)

| # | Odak | Sonuç |
|---|---|---|
| 1 | **219 readiness** | `_context_needs` yalnız `limits["context_window"]` okuyor; ikinci anahtar yolu yok. `api/agents.py` 183-185 aynı anahtarı (`context_window`) kullanıyor; seed (`models.airgap.yaml`, `model_catalog.yaml`) da. <br>Eski anahtar: `test_04a_17b_legacy_context_tokens_key_is_not_counted` var; probe P2'de yalnız `context_tokens: 900000` taşıyan satırla iki denetim de `skipped`, yeni `NO_NEED` metniyle. <br>Agent yokken: `test_04b_2_219_…without_an_agent` (stub'lı `/api/ps`) ve probe P1 (stub'sız, Ollama yok): `ollama_context` ok, `ollama_runtime_context` **failed `ollama_unreachable`**, HTTP 503; `skipped` değil. P3: pencere 65536 > 32768 → 503 `context_configuration_invalid`, `largest needed context=65536`. <br>Docstring, `NO_NEED`, iki detay metni ve `docs/bilgi-tabani.md` tutarlı. Açık nokta: NOTE-2. |
| 2 | **214 hook** | İstenen biçimlerin hepsi doğru: `# don't` sonrası satırda `pytest` KAPI, `git push` PUSH, `docker build` PROSES-175 (bazda üçü de sessizdi). `echo '#x'`, `$#`, `${#a}`, URL içi `#`, veri heredoc'u gövdesindeki `#` komutu saklamıyor. `timeout 600 pytest` tee'siz KAPI, tee'li serbest; `timeout -k 5 10 git push` PUSH. `timeout` 22 biçimde denendi (`-k5`, `--kill-after=`, `--`, iç içe, `nice timeout`, `/usr/bin/timeout`, `timeout.exe`, `sh -c`, heredoc okuyucu): hepsi denetleniyor; `timeout`, `timeout -k`, `timeout 5` tek başına hata vermiyor. <br>Yan kazanç: yorumdaki `| tee` ve `--pull never` artık kuralı karşılamıyor (`pytest … # | tee x.log` KAPI; bazda sessizdi). <br>ENV değişmedi: `git status # cat .env` ve `# cat .env` satırı hâlâ ENV (bilinçli; handbook "`ENV` yorumu da tarar" diyor). |
| 3 | **215 egress testi** | Beklenen düşüş listesi boş ve doğru: `REDIS_URL` yokken yürüyüş yalnız `ffcore.knowledge.worker`'ı düşürüyor (`RuntimeError: REDIS_URL is not set`), `IMPORT_ENV` ile hiçbirini. Bilinmeyen düşüş (probe: import'ta hata veren `ffcore/rv_broken_probe.py`) `test_hke_215_import_failures_are_the_expected_ones`'ı kırıyor. Beş alan `core/egress.py`'nin okuduklarıyla birebir (`internal_api_url`, `offline`, `egress_allowlist`, `allowed_internal_hosts`, `egress_proxy_url`); altıncı bir `settings.<alan>` okuması sürüklenme testini kırıyor. Açık nokta: NOTE-3. |
| 4 | **221 ekran görüntüsü** | 19 `saveScreenshot` çağrısı (13 spec); `tests/` altında yardımcı dışında doğrudan `.screenshot(` kalmadı; `docs/images` yalnız yorumlarda. Compose `E2E_SCREENSHOT_DIR: ${E2E_SCREENSHOT_DIR:-}`. <br>Probe (backend'siz iki testlik spec, sayfa + locator): boşken `screenshotDir()` null, `/work` ve `/tmp` altında yeni PNG 0; dizin varken iki PNG yazıldı, yol içeren ad (`../x.png`) reddedildi; olmayan dizin ve dosya yolu `… is not a directory` ile testi düşürüyor, dizin oluşturulmuyor. Açık nokta: MINOR-2. |
| 5 | **220 e2e imajı** | `Dockerfile.e2e` tabanı compose'daki `PLAYWRIGHT_IMAGE` argümanı, digest eskisiyle aynı (`47b510dd…`). `npm ci` imaj katmanında; servis komutu `npm run test:e2e`. Boş volume imajdan doluyor (498 paket). Kilit dosyasına bir bayt eklenince varsayılan komutla ve argümanlı koşuda `e2e_deps_stale`, çıkış 1; mesajdaki komut belgedekiyle aynı. Kurulum `--pull never` ile yerel metadata'dan (kendi kurulumumda da `DONE 0.0s`). <br>Volume'u silip yeniden doldurma adımını koşmadım: silme komutum oturumun güvenlik denetimine takıldı. Yeni oluşturulan boş volume'un ilk bağlamada dolması aynı yolu kanıtlıyor; silme sonrası dolum işçinin `tr2-220-lock.log`'unda. FOLLOWUP-222 (`run --build`) kapsam dışı, bulgu sayılmadı. |
| 6 | **216 + docs** | MULTI_AGENT_PROTOCOL'de "Tam test-int slotu (ENV-209, FOLLOWUP-216)" paragrafı; "ENV-209" aramayla bulunuyor. PR şablonunda satır var. `docs/onyuz.md` iki reçetesi de imaj kurulum satırını içeriyor, `npm ci &&` kalmadı (depo genelinde grep). `docs/bilgi-tabani.md:328`, handbook ENVIRONMENT_AND_COMMANDS:62 ve docs/takim:670 `timeout` denetlenir, `xargs`/`sudo` sınır diyor. Küçük tutarsızlıklar NOTE-4. |
| 7 | **Kural atlatma denemesi** | Dört biçimde atlatma var: **MINOR-1**. Baz ve dalda ortak, önceden var olan bir biçim: NOTE-1. |

Diğer başlıklar: sözleşme ve OpenAPI değişmedi; profil dalı yok, readyz testleri iki profilde yeşil; secret yok (yalnız `dummy-not-secret` değerleri); test, kod ve docs commit'leri ayrı.

## MINOR-1 · `yorum-kesimi-fn`: yeni yorum kesimi dört biçimde sonraki komutu saklıyor (bazda yakalanıyordu)
- **Durum:** `unquoted_heredocs` tırnak dışındaki `#`'i, önündeki karakter boşluk, sekme, `;`, `&`, `|`, `(` ya da `)` ise yorum sayıp satırın kalanını atıyor. Bash'te iki durumda bu `#` yorum değildir: `${…}` genişletmesinin içinde ve önceki satır boşluksuz `\` ile bittiğinde (satırlar birleşir, `#` kelime ortasında kalır).
- **Kanıt** (`tr2-r1-rv-hook-probe.log` X1, X2, X3, X4, X24; bash doğrulaması `tr2-r1-rv-bash-semantics.log`):

| Komut | Baz d6d2029 | Dal 135c369 | bash |
|---|---|---|---|
| `echo ${a/ #x/y}; git push origin x` | PUSH | kural yok | push koşar |
| `echo ${a# #}; git push origin x` | PUSH | kural yok | push koşar |
| `echo ${a// #}; pytest backend/tests` | KAPI | kural yok | pytest koşar |
| `echo foo\`⏎`#bar; git push origin x` | PUSH | kural yok | push koşar (`foo#bar`) |

- **Neden MINOR, MAJOR değil:** değişiklik net kazanç (yorumdaki kesme işareti çok yaygın bir biçimdi ve her şeyi saklıyordu; 33 biçim iyileşti). Bu dört biçim kazara yazılacak türden değil; bilerek atlatmak isteyen için `$CMD` zaten belgeli sınır. Ama yön yanlış negatif ve PUSH'u da kapsıyor, bu yüzden kayıt altına alınmalı.
- **Öneri (koordinatör kararı):**
  - **A (önerim):** FOLLOWUP-222 hook dilimine eklensin: `${` … `}` derinliği sayılır ve içinde `#` yorum sayılmaz; önceki satır tırnak dışı `\` ile bitiyorsa satır başındaki `#` yorum sayılmaz. Dört biçim iki yönlü teste girer. O güne kadar docs/takim "Bilinen sınırlar"a bir cümle.
  - B: bu PR'da r2 ile düzeltilsin. Küçük dilim ama bir tur ve bir kapı daha.
  - C: yalnız belgelenmiş sınır olarak kalsın. Bazda yakalanan bir biçimin kalıcı olarak bırakılması; önermiyorum.

## MINOR-2 · `docs-recete-git-bash`: `export E2E_SCREENSHOT_DIR=/work/docs/images` Git Bash'te çalışmıyor
- **Durum:** `docs/onyuz.md` belge görüntülerini yenilemek için `export E2E_SCREENSHOT_DIR=/work/docs/images` diyor. Git Bash (ajanların ve geliştirme makinesinin kabuğu) `/` ile başlayan değeri Windows yoluna çeviriyor.
- **Kanıt** (`tr2-r1-rv-221b.log` adım 8): konteyner `E2E_SCREENSHOT_DIR=[C:/Program Files/Git/work/docs/images]` görüyor; `compose config` da aynı değeri gösteriyor. `MSYS_NO_PATHCONV=1` ile değer `/work/docs/images` kalıyor (8b).
- **Etki:** sessiz değil; yardımcı `… is not a directory` ile testi düşürür (fail-loud tasarım burada işini yapıyor). Ama belgedeki komut yazıldığı gibi koşmuyor ve hata metnindeki yol şaşırtıcı.
- **Öneri:** reçeteye `MSYS_NO_PATHCONV=1` eklemek ya da göreli yol önermek (`E2E_SCREENSHOT_DIR=../docs/images`; yardımcı göreli yolu `/work/frontend`'den çözüyor, kabuk çevirmez). Göreli biçimi koşarak denemedim.

## NOTE-1 · `$'…\'…'` sonrası komutlar bazda da dalda da görünmüyor
- `echo $'it\'s' # x`⏎`git push origin x` → iki guard'da da kural yok (X13). Tırnak sayacı ANSI-C tırnağındaki `\'` kaçışını bilmiyor. Regresyon değil; 222 dilimine not.

## NOTE-2 · 219'un ikinci görünür etkisi `degisiklikler.md`'de yok
- "Action" yalnız `OLLAMA_CONTEXT_LENGTH` < pencere durumunu anlatıyor. Probe P1: aktif Ollama model satırı var, yayımlanmış agent yok, Ollama cevap vermiyor → önceden `skipped` (200), şimdi 503 `ollama_unreachable`. Doğru ve istenen davranış (R1'in kendisi), ama kurulumun fark edeceği değişiklik bu; bir cümle eklenmeli.
- Probe'da detay `EgressDenied` idi (adres izin listesinde değildi): kod `ollama_unreachable` ama neden egress reddi. Önceden var olan davranış; kod adı nedeni tam söylemiyor.
- `core/config.py:113` yorumu hâlâ "models' context_tokens" diyor. Dosya bu dilimin zone'unda değil (14 dokunuyor); sonraki dokunuşta düzeltilebilir.

## NOTE-3 · 215 yürüyüşü gerçek `REDIS_URL`'i sahte değerle eziyor
- `_settings_classes` `IMPORT_ENV`'i koşulsuz kuruyor; `tools` konteynerinde gerçek `REDIS_URL` varken de modüller sahte URL ile import ediliyor ve oturumun kalanında öyle kalıyor (`ffcore.knowledge.worker` modül düzeyi ayarı). Birim testleri Redis'e bağlanmadığı için bugün etkisi yok (2161 ×2 yeşil). İsteğe bağlı: yalnız değişken yoksa kurmak.
- Sürüklenme testi yalnız `settings.<alan>` yazımını yakalar; `getattr(settings, …)` ya da `self._settings.<alan>` okuması kaçar. Bugün `egress.py`'de böyle bir okuma yok.

## NOTE-4 · Küçük belge tutarsızlıkları
- MULTI_AGENT_PROTOCOL 216 paragrafı gerekçe olarak KARARLAR '11-1 main kapısı YEŞİL'i gösteriyor; kırmızı kapı '11-1 main kapısı KIRMIZI' başlığında.
- docs/takim 668 "İç içe komutlar" sarmalayıcı listesinde `timeout` yok; 670 "Bilinen sınırlar" denetlendiğini söylüyor.
- docs/takim 670 "`#` yorumları FOLLOWUP-214'ten beri denetlenir" cümlesi ters okunabiliyor (yorum denetlenmiyor, yorum olarak okunuyor); handbook cümlesi doğru.
- İşçi logları `tr2-219-green-*.log` komut ve `HEAD=` satırı taşımıyor; sonuç doğru (kendi koşumla aynı 17), ama log tek başına neyin koştuğunu söylemiyor.

## Kalan imaj ve bekleyen dosyalar (commit edilmedi)
- İmaj etiketi `ffcore/e2e:0.0.0-rv` duruyor (katmanları `0.0.0-tr2` ile ortak); temizlik koordinatörde.
- `state/reviews/followup-triage-2-r1.md`
- `state/evidence/tr2-r1-rv-{hook-probe,bash-semantics,hooks,up,readyz-llmaas,readyz-airgap,215,220-build,220-volume,220-221,221b,lint,down}.log`
- `state/kanal/inceleyici.md`
