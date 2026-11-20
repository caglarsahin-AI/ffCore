# PR hook-egress-1 [B]: hook block geçişi + FOLLOWUP-208/210/212/213

**Paket:** hook-egress-1 · **Sınıf:** [B] · **Branch:** fix/hook-egress-1 · **Baz commit:** 1c0abcd · **HEAD:** 99bb7a39787a40ca053dade6611d1d4703d547cd

Durum: PR-HAZIR (B-HKE-0005). PLAN-ONAY K-HKE-0002 (K1 A, K2 A). Delta `1c0abcd..99bb7a3` (19 commit; test / kod / docs ayrı). Plan bölümü aşağıda değişmeden duruyor; uygulama notları "Teslim" bölümünde.

## Teslim

### Değişen dosyalar (20, hepsi touch-zone içinde)
- `.claude/hooks/ffcore_guard.py`: `check_docker_build` (210); `heredoc_commands` + `has_tee`: komut kuralları heredoc gövdesini komut saymaz, sh/bash gövdesi bir düzey derinde, kendi satırının tee'siyle (K1 A); `state/pr/<pr>-<n>.md` alt PR adı; `LOG_DETAIL_MAX` 240.
- `.claude/settings.json`: `FFCORE_GUARD_MODE=block` (ayrı commit fcc2978, 208'den önce).
- `tests/hooks/{conftest.py,test_guard.py,test_heredoc_commands.py}`: `settings_hook_argv` (py yoksa gerekçeli skip, 212); 210, K1, TEK-YAZAR, block kipi testleri.
- `deploy/postgres/initdb/20-app-role.sh`, `scripts/compose_preflight.py`, `.env.example`: 213.
- `backend/ffcore/core/config.py`: `egress_proxy_url` (+ `egress_proxy_url_invalid` doğrulaması: yalnız `http://host:port`).
- `backend/ffcore/core/egress.py`: `_ProxyOnlyBackend` (yalnız proxy kökünü arar), `_ProxyTransport` (httpcore2 `AsyncHTTPProxy`; https CONNECT adla, http mutlak biçim), `_EgressTransport` (istek başına yol: iç host / boş ayar → pinli doğrudan; diğerleri → proxy; proxy reddi `egress_proxy_denied`; yollar arası geri düşüş yok); `SafeOutboundClient` ve `policy_http_client` bunu kullanır; `check_http_destination` proxy'de dış host için `[]` (adres denetimi proxy'de).
- `deploy/docker-compose.egress.yml`: backend, worker, agent-worker, agent-worker-bg → `EGRESS_PROXY_URL=http://egress-proxy:3128` + `depends_on egress-proxy healthy`; "Known limit" yorumu kalktı.
- `backend/tests/unit/test_hke_208_egress_proxy.py` (23), `test_hke_208_compose.py` (6), `test_12_46_app_role_static.py` (+4), `test_12_compose_preflight.py` (+1), `backend/tests/integration/test_12_egress.py` (+8).
- `docs/kurulum.md` (Egress: proxy yolu + nerede hangi denetim tablosu, SMTP/readyz dışarıda, sorun giderme), `docs/degisiklikler.md`, `handbook/ENVIRONMENT_AND_COMMANDS.md` (block, 240, heredoc kuralı, 210, alt PR, kapı hook adımı host).

### Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 212 | py yoksa açık gerekçeli skip; host'ta koşar | `test_settings_command_skips_without_py_launcher`, `test_settings_command_runs_guard` | geçti (host) |
| 210 | çıplak `docker build`/`buildx build` PROSES-175 | `test_bare_docker_build_blocked[8]`, `test_docker_non_build_allowed[8]` | geçti |
| K1 | heredoc veri/kod gövdesi sessiz; sh/bash gövdesi ve gerçek kapı engel; `pytest \| tee` sessiz | `test_heredoc_commands.py` (16) | geçti |
| K1 | TEK-YAZAR `<pr>-<n>` yalnız `state/pr/` | `test_worker_writes_sub_pr_note_allowed[3]`, `..._non_sub_pr_note_blocked[5]`, `test_sub_pr_alias_from_registry_allowed`, `test_sub_pr_rule_only_under_state_pr` | geçti |
| K1 | kayıt 240 karakter | `test_log_truncates_to_240` | geçti |
| block | settings block; settings ortamıyla gerçek ihlal engel + kayıt `block`, bilinen YP sessiz + kayıt yok | `test_settings_mode_is_block`, `test_settings_env_real_violations_blocked[3]`, `test_settings_env_known_false_positives_silent[4]` | geçti |
| 213 | yalnız-parola initdb durur (`false`), `set -e` altında kaynaklanınca da | `test_hke_213_initdb_refuses_a_password_without_user`, `test_hke_213_initdb_half_pair_stops_when_sourced[2]` | geçti (konteyner) |
| 213 | `.env.example` ve `db_role_owner` metni gerçek durum | `test_hke_213_env_example_says_initdb_stops_for_either_half`, `test_hke_213_owner_message_names_both_settings` | geçti |
| 208 | ayar biçimi; boşken bugünkü yol | `test_hke_208_setting_*` (9), `test_hke_208_empty_setting_keeps_the_direct_pinned_path` | geçti |
| 208 | ad kuralları proxy'den önce; hedef adı backend'de çözülmez; CONNECT adla; proxy reddi açık hata; geri düşüş yok; iç host doğrudan; proxy taşıyıcısı yalnız proxy kökü | `test_hke_208_*` (birim, 14) | geçti |
| 208 | overlay dört servise proxy | `test_hke_208_compose.py` (6) | geçti |
| 208 | test-int Squid: izinli 200; Squid reddi (izin dışı / rebind / bench) `egress_proxy_denied`; CONNECT reddi; backend izin listesi dışı proxy'ye gitmez; proxy'siz doğrudan çıkış hata; iç host doğrudan | `test_12_egress.py::test_hke_208_*` (8) | geçti (17/17 dosya) |

Test-int testleri birim TDD'sinden sonra yazıldı; kırmızılık, aynı yığında main'in `ffcore` paketi bağlanarak gösterildi: 5 failed / 3 passed (`hke-208-test-int-red-on-main.log`; geçen üçü main'de de doğru olan davranış: izin listesi reddi, proxy'siz hata, iç host).

### Çalıştırılan komutlar (`state/evidence/`)
| Komut | Ortam | Sonuç | Log |
|---|---|---|---|
| `py -3.12 -m pytest tests/hooks tests/scripts` | host, son SHA 99bb7a3 | 409 passed | `hke-hooks-final.log` (önceki: `hke-block-green.log` 409 passed) |
| `make test` llmaas | tools imajı, `--network none`, `.env.test` | 2145 passed | `hke-make-test.log` |
| `make test` airgap | aynı + `DEPLOY_PROFILE=airgap OFFLINE=true` | 2150 passed, 1 failed: `test_08t_secrets_linear[API_KEY]` 10.8 s > 8 s (zamanlama; dokunulmayan dosya); tek başına 7/7 | `hke-make-test.log`, `hke-make-test-airgap-rerun.log` |
| `make lint` | ffcore-hke tools | ilk koşu 1 E501 (yeni test-int satırı) → format; tekrar `All checks passed`, 553 dosya formatlı | `hke-lint-smoke.log`, `hke-lint-r2.log` |
| ruff `.claude/hooks tests/hooks` | host ruff 0.17.3 | temiz | (B-HKE ilerleme) |
| `test_12_egress.py` (RUN_EGRESS_TESTS=1) | ffcore-hke egress+tls+test | 17 passed, son SHA 99bb7a3 | `hke-208-test-int.log` (Squid erişim logu ve backend `EGRESS_PROXY_URL` dahil) |
| `make smoke` | ffcore-hke egress+tls | geçti (`database: ffcore_app`, egress 3 host, tls) | `hke-lint-smoke.log` |
| `alembic` | — | göç yok | — |
| tam `make test-int` | — | NOT_RUN: ENV-209 (tek tam koşu kuralı); hedefli koşu yapıldı; değişen backend yüzeyi `core/egress.py` + `config.py`, birim kapsamı 2145/2150 | — |

### Bilerek değişen testler
- `backend/tests/unit/test_03b_egress.py::test_03b_2_transport_pool_uses_pinned_backend`: httpx2 iç yapısını bekliyor; pinli havuz artık yönlendirici taşıyıcının altında (`_transport._direct._pool`); proxy havuzu da (`AsyncHTTPProxy` + `_ProxyOnlyBackend`) denetlenir.
- `tests/hooks/test_guard.py::test_log_truncates_to_120` → `..._to_240` (K-HKE-0002).
- `tests/hooks/test_guard.py::test_settings_command_runs_guard`: settings komutunu `settings_hook_argv()` ile kurar (212).
- Kırmızı commit'ten sonra düzeltilen iki test hatası (kendi testlerim): `.env.example` blok kesimi `\nAPP_DB_USER=` (d126235), `exc.value.detail` → `str(exc.value)` (31a8f49).

### Varsayımlar ve brief'le farklar
- 213 brief'te "exit 1": betik postgres giriş noktası tarafından kaynaklanabildiği için `exit` yerine `false` (K-HKE-0002 onayı); `set -e` altında kaynaklanınca da durduğu test edildi.
- 208 çağrı noktaları (`mcp_client`, kanal/kaynak) değişmedi: yol seçimi `core/egress.py` içinde tek yerde; `mcp_client` `policy_http_client` üzerinden aynı yolu alır. Kanal/kaynak bağdaştırıcıları bu depoda henüz yok.
- Proxy reddi tespiti: CONNECT'te httpcore `ProxyError`; düz istekte Squid'in `X-Squid-Error` başlığı (gerçek Squid 6.6 ile test-int'te doğrulandı). Hedef sunucu bu başlığı kendisi gönderirse çağrı `egress_proxy_denied` olur (yalnız hata yönünde; atlatma değil).
- `.env.example`'a `EGRESS_PROXY_URL=` satırı eklenmedi: değeri overlay verir, taban compose `app-env`'i (touch-zone dışı) okumaz; yorum satırı olarak belgelendi (test bunu bağlar).
- `docs/takim/ajanlarla-gelistirme.md` 648/654/672'de "ilk 120 karakter" ve `warn` örneği eskidi; touch-zone dışı, değiştirmedim → koordinatöre not.
- Hook gerçek denemesi: bu oturum main'deki eski guard ve `warn` ile denetlendi (worktree ayarı oturumu etkilemez, handbook "Yükleme"); kayıttaki iki KAPI uyarısı (19:37, 19:38) yeni guard'la yeniden üretildi, sessiz (`hke-replay-session-warns.log`). 19:44 ENV uyarısının komutu kesik kayıttan kurulamadı; ENV kuralına dokunulmadı (kod gövdesinde metin `.env` = kararla kabul edilen sınıf).

### Kalan riskler
- Block kipinde ENV'nin yorumlayıcı-gövdesi yanlış pozitifi (kararla kabul, MINOR-2) artık engeller; geçici yol Edit/Write aracı.
- Proxy yolunda belge aralıkları ve 192.0.0.0/24 Squid'de serbest (backend'de redli); docs tablosunda yazılı.
- SMTP alarmları egress profilinde çalışmaz (docs'ta yazılı; webhook kanalı önerilir).

## Plan

### Felsefe kontrolü
1. ARCH-07: hook düzeltmeleri bütün oturumlara (block'ta her Bash çağrısı); 208 backend'in dört dış çağrı ailesini (uzak MCP, OpenAPI araçları, webhook, dış agent) egress profilinde çalışır kılar. Çekirdeğe eklenen: tek ayar + proxy taşıyıcısı (egress.py içinde, tek yer).
2. ARCH-09: proxy işini Squid yapar (izin listesi, adres reddi, log); backend yeniden inşa etmez. httpcore'un kendi proxy taşıyıcısı (CONNECT tüneli) kullanılır, el yazımı CONNECT yok.
3. ARCH-10/06: `EGRESS_PROXY_URL` açık ayar (boş = bugünkü doğrudan pinli yol); proxy'de hata açık `EgressRequestFailed`/`EgressDenied`, doğrudan yola sessiz düşüş yok.

### Bulunan semboller
- `.claude/hooks/ffcore_guard.py`: `check_bash` (KAPI ve PROSES-175 heredoc gövdesini de komut sanıyor), `strip_heredocs` (yalnız ENV yolunda kullanılıyor), `check_compose` (yalnız compose), `check_write` (`pr` eşleşmesi tam ad), `resolve_mode`.
- `tests/hooks/test_guard.py::test_settings_command_runs_guard` (settings komutunu olduğu gibi koşuyor).
- `backend/ffcore/core/egress.py`: `_PinnedBackend.connect_tcp`, `_PinnedTransport`, `SafeOutboundClient`, `policy_http_client`, `check_http_destination`, `check_destination` (SMTP).
- `deploy/postgres/initdb/20-app-role.sh` (kaynaklanabilir, `exit` yok → `false`), `scripts/compose_preflight.py` (`db_role_incomplete`, `db_role_owner`), `.env.example` APP_DB yorumu.
- `deploy/docker-compose.egress.yml`, `deploy/egress/squid.conf`, `backend/tests/integration/test_12_egress.py` (uygulama ağında dış ad çözülmüyor: `test_12_e1_outside_names_do_not_resolve_on_the_app_network`).

### hook-guard.log incelemesi (98 satır, 16-20 Kasım, warn)
| Kural | Sayı | Sınıf |
|---|---|---|
| KAPI | 65 | ≥20 heredoc gövdesi (`cat >> state/kanal/… <<EOF`, `python - <<EOF` belge düzenleme; gövdede `make test`/`pytest` satırı) = **yanlış pozitif, kök neden**: `check_bash` gövde satırlarını komut olarak bölüyor (yeniden üretildi). ~7 görünür gerçek `pytest … \| tail` (tee'siz) = kurala göre doğru pozitif (S7). Kalan 38 satır 120 karaktere kesik; sınıflanamıyor (çoğu inceleyici/işçi `S=…; cd …` zinciri). |
| ENV | 23 | 16 Kasım'dakiler 189(e) öncesi; 19-20 Kasım 3 satır `python - <<EOF` kod gövdesinde metin `.env` = kararla kabul edilmiş YP (MINOR-2, FN yönü). |
| PROSES-175 | 5 | 4'ü heredoc gövdesi (kanal YIGIN-AC metni, belge düzenleme) = YP, KAPI ile aynı kök neden; 1'i gerçek. |
| TEK-YAZAR | 3 | `state/pr/04b-2.md`, `state/pr/followup-triage-1.md`: kayıttaki paket/pr adı ile alt PR dosya adı uyuşmuyor = YP (block'ta işçi kendi PR notunu yazamaz). |
| YIGIN, PAYCORE | 1+1 | gerçek / inceleme probu. |

### Dilim sırası (her dilim önce kırmızı test; test/kod/docs ayrı commit)
1. **212**: `test_settings_command_runs_guard` `shutil.which("py")` yoksa `pytest.skip("py launcher yok (Linux konteyner); kapı hook adımı host py -3.12, FOLLOWUP-212")`; handbook ENVIRONMENT_AND_COMMANDS hook satırı "kapı hook adımı host".
2. **210**: `check_compose` yanında `docker build` / `docker buildx build` / `docker image build` (+ `docker builder build`) → PROSES-175; `docker buildx ls`, `docker build --help` vb. serbest.
3. **Block öncesi daraltma** (öneri A, aşağıda) + TEK-YAZAR alt PR adı.
4. **Block**: `.claude/settings.json` `FFCORE_GUARD_MODE=block` ayrı commit; testler block kipinde: gerçek ihlal çıkış 2, bilinen YP fikstürleri sessiz (çıkış 0, kayıt satırı yok).
5. **213**: initdb yalnız-parola → stderr + `false`; `.env.example` yorumu ve `db_role_owner` mesajı (kullanıcı da boş olabilir: "set APP_DB_USER=ffcore_app and APP_DB_PASSWORD"); preflight testi + initdb için kabuk testi (host'ta `sh` yoksa tools konteynerinde).
6. **208** (öneri A, aşağıda): birim testleri (sahte proxy, httpcore2 sahte backend) + test-int Squid.

### Karar 1: KAPI daraltması
- **A (Önerilen):** KAPI ve PROSES-175 (bütün komut kuralları) `strip_heredocs` sonrası metne bakar: veri heredoc'u (`cat > f <<EOF`) ve yorumlayıcı kodu (`python - <<EOF`) komut sayılmaz; `sh`/`bash` gövdesi komut kalır. ENV bugünkü gibi kod gövdesini tarar (karar MINOR-2). Gerçek `make test` / `pytest` (tee'siz, `\| tail` dahil) block'ta engellenir: S7 kararı korunur. Etki: kök neden kapanır, kural gevşemez; YP sınıfı ≥20+4 susar.
- B: A + `state/kanal/` ya da `state/pr/` hedefli komutların tamamı muaf. Bedel: aynı zincirdeki gerçek kapı da geçer (muafiyet hedefe değil komuta bağlı olmalı) → fail-loud ihlali.
- C: KAPI yalnız `make <hedef>`; çıplak `pytest` serbest. Bedel: 16 Kasım S7 kararını tersine çevirir; hedefli koşu çıktıları kaybolur (K-05a-0011 dersi).
- Ek (A ile): TEK-YAZAR `state/pr/<ad>.md` için `<pr>` ya da `<pr>-<n>` / `<paket>-<n>` (alt PR) kabul; kayıt satırı 120 karakter kalır (değiştirmiyorum).
- Bilinen etki: block'ta herkes hedefli `pytest … | tail` yerine `… 2>&1 | tee state/evidence/<x>.log | tail` yazmalı; geçişten önce `tumu`'ya duyuru önerisi (koordinatör).

### Karar 2: 208 tasarımı
Gerçek: egress profilinde uygulama ağı `internal`, dış adlar backend'de **çözülmüyor** (test_12 e1). Backend tarafında çözümleme + IP pinleme proxy ile birlikte yapılamaz.
- **A (Önerilen):** `EGRESS_PROXY_URL` doluyken **iç olmayan** hedefler httpcore2 proxy taşıyıcısıyla çıkar (https → `CONNECT host:port`, http → mutlak biçim); backend proxy'den önce bütün **ad düzeyi** kuralları uygular (şema, port, OFFLINE, EGRESS_ALLOWLIST, platform hedefi, yönlendirme başına tekrar, kimlik başlığı düşürme), **adres düzeyi** denetimi (özel IP / DNS rebinding) çözümleyen ve bağlanan bileşene, Squid'e geçer (`to_private`, 12-1 r1 NOTE-3 ile `is_global` hizalı; fark: belge aralıkları, squid.conf'ta yazılı). TLS uçtan uca (SNI/sertifika backend'de). Proxy bağlantısının kendisi yalnız `EGRESS_PROXY_URL` köküne pinli (başka iç host'a değil). `ALLOWED_INTERNAL_HOSTS` hedefleri bugünkü doğrudan pinli yoldan. `policy_http_client` (MCP SDK) aynı seçimi kullanır. SMTP (`check_destination`) proxy'lenemez → egress profilinde bağlantı hatası, docs'ta açık. Etki: kanal/kaynak/uzak MCP/webhook egress profilinde çalışır; pinleme sınırı belgelenir.
- B: backend ad çözer + denetler, sonra `CONNECT host` (ad) gönderir. Bedel: internal ağda ad çözülmüyor (çalışmaz); çözülse bile Squid ikinci kez çözer → denetim/bağlantı ayrışır (rebinding açığı), sahte güvence.
- C: backend çözer, `CONNECT <ip>:port` (IP) + SNI ad. Bedel: aynı DNS engeli; Squid `dstdomain` izin listesi IP görür ve işlevsiz kalır (ikinci savunma hattı kaybolur).
- Not: A'da ayar boşken davranış bire bir bugünkü (regresyon testi). `EGRESS_PROXY_URL` yalnız `http://host:port` (kimlik, yol, https proxy yok → açılışta açık hata).

### Test-int (208)
`backend/tests/integration/test_12_egress.py` ek testler (RUN_EGRESS_TESTS=1, aynı yığın tarifi + backend'e `EGRESS_PROXY_URL=http://egress-proxy:3128`): SafeOutboundClient ile izinli alan 200 (proxy erişim logunda satır), izin listesi dışı backend'de `egress_not_allowlisted` (proxy'ye gitmeden), Squid reddi (rebind/bench) `EgressDenied`/403 açık hata, `EGRESS_PROXY_URL` boş istemciyle doğrudan çıkış bağlantı hatası. Yığın `ffcore-hke` (18880/13880), hedefli (ENV-209: tam test-int için sıra istenecek).
