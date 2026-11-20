# Review hook-egress-1 r1
SHA: 99bb7a39787a40ca053dade6611d1d4703d547cd · Sonuc: ONAY · Bulgu: B0 M0 m2 N3

- **İncelenen tam SHA:** `99bb7a39787a40ca053dade6611d1d4703d547cd` (dal `fix/hook-egress-1`).
- **Delta** `main..99bb7a3`: 19 commit, 20 dosya, +1067/−42; hepsi touch-zone. Her dilimde önce test commit'i, sonra kod. Block commit'i `fcc2978` ayrı ve 208'den önce. Docs `22de7e6`.
- **İstek:** K-HKE-0003. Kararlar: KARARLAR "hook-egress-1 plan kararları" (K1 A, K2 A), K-HKE-0002 notları.
- **Yöntem:**
  - Delta satır satır okundu.
  - **Hook:** dalın guard'ı hostta `py -3.12` ile, `FFCORE_GUARD_MODE=block`, geçici `FFCORE_MAIN_ROOT` ve rol `isci-b` ile koşuldu. Gerçek sözleşme kullanıldı: stdin JSON → çıkış kodu + stderr kuralı. 65 + 16 durum denendi. İkinci partide main'in guard'ı aynı komutlarla yan yana koşuldu.
  - **213:** atılabilir `pgvector/pgvector:0.8.1-pg16` konteynerleri, `--network none`, beş çift × iki kip.
  - **208:** overlay yığını `ffcore-rv` (compose + egress + tls + test overlay, imaj `0.0.0-hke`, `--no-build --pull never`). İmajın backend `.py` dosyaları 99bb7a3 ile aynı (201/201 sha256).
  - Tam test-int koşulmadı (ENV-209).
- **Karar: ONAY.** Block kipi gerçek ihlalleri engelliyor; bilinen yanlış pozitif sınıfları sessiz. 208, 210, 212 ve 213 kanıtlı. İki MINOR'un ikisi de guard'ın heredoc okumasında:
  - MINOR-1: koordinatörün özel probe'u; kısmen engelliyor.
  - MINOR-2: daraltmanın getirdiği bir kaçak, main yakalıyor.
  - Merge öncesi düzeltilmesini öneriyorum; karar koordinatörde.

## Testler
`HEAD=` satırlı loglar `state/evidence/hook-egress-1-r1-rv-*.log`.

| Koşu | Sonuç |
|---|---|
| Hook probe 1 (`-hook-probe.log`) | 65 durum, 61 beklendiği gibi; 4 sapma MINOR-1. Kayıt satırı en uzun 240 |
| Hook probe 2 (`-hook-probe2.log`) | 16 heredoc kenar durumu, dal ve main yan yana; 6 sapma, MINOR-2 |
| Hook testleri host (`-hooks-host.log`) | `tests/hooks tests/scripts` 409 passed, exit 0 |
| Hook testleri Linux tools (`-hooks-linux.log`) | `tests/hooks` 397 passed, 1 skipped; gerekçe metni aşağıda |
| initdb (`-initdb.log`) | 10 durum, sonuçlar aşağıda; kalan konteyner 0 |
| Yığın (`-up.log`) | `config -q` 0, up exit 0, hepsi healthy |
| Testler + probe (`-tests.log`) | aşağıda |
| Gerçek servisler (`-backend-proxy.log`) | dört serviste `EGRESS_PROXY_URL`; backend süreci içinden 200 / `egress_proxy_denied` / litellm 200; Squid erişim logu |
| `down -v` (`-down.log`) | konteyner 0, volume 0, ağ 0 |

`-tests.log` içeriği:
- **İşçi testleri:**
  - test-int: `test_12_egress`, `test_12_tls`
  - unit: `test_03b_egress`, `test_hke_208_egress_proxy`, `test_hke_208_compose`, `test_12_compose_preflight`, `test_12_46_app_role_static`
  - `RUN_EGRESS_TESTS=1` ve `RUN_TLS_TESTS=1` ile 169 passed.
- **Probe:** 17 passed.

## Kontrol listesi (K-HKE-0003)

| # | Madde | Sonuç |
|---|---|---|
| 1a | **Block: gerçek ihlal engel** | Hepsi exit 2: <br>• **KAPI:** `pytest` ve `python -m pytest` tee'siz; `make test` ve `make test-int`; `compose run tools sh -c 'pytest'`; `bash <<EOF` gövdesinde `pytest` / `make test`; `cat <<EOF \| bash`. <br>• **ENV:** `cat .env`, `>> .env`, `sed -i .env`, Write `.env`, `python - <<EOF open('.env')`, `Path(".env")`. <br>• **PROSES-175:** `up --build` / `up -d` `--pull never`'sız; `compose build`, `--pull=false` dahil. <br>• **PUSH:** `git push`. <br>• **TEK-YAZAR:** `isci-b` olarak `WORK_QUEUE.md` ve başka paketin `state/pr/12.md`'si. |
| 1b | **Block: yanlış pozitif sınıfları sessiz** | Hepsi exit 0: <br>• kanal `cat >> … <<'EOF'` gövdesinde `make test`, `pytest`, `docker build`, `git push`, `compose build` <br>• `python - <<EOF` gövdesinde `pytest` <br>• `bash <<'EOF' \| tee` gövdesinde `pytest` <br>• `pytest \| tee` ve `make test \| tee`; `pytest --collect-only` <br>• `up --build --pull never` ve `--no-build --pull never` <br>• `docker build --help`, `buildx ls`, `image ls` <br>• `docker logs > file` |
| 1c | **Özel probe: `.env.example`/`.env.test` heredoc düzenlemesi** | **Kısmen engelliyor, MINOR-1.** Geçenler (8/8, exit 0): <br>• `py -3.12 - <<EOF` ile `.env.example`'da `replace` <br>• `python - <<EOF` ile `.env.test` `re.sub` <br>• `python3` ile append <br>• `cat >> .env.example <<EOF` (gövdede `copy to .env` olsa da) <br>• `sed -i … .env.example` <br>• `cat .env.test`; `--env-file .env.test` <br>• Write `.env.example` <br>• `py -c "open('.env.example')"` <br>Engellenenler (4/4, exit 2 `ENV`): yorumlayıcı gövdesinde boşluktan sonra çıplak `.env` kelimesi geçen düzenlemeler. `.env.example`'ın kendi satırları buna örnek: satır 1 `cp .env.example .env`, satır 2 `fills in .env;`, satır 328 ve 338 `--env-file .env`. Docs metni `the .env file` da öyle. |
| 1d | **TEK-YAZAR alt PR** | Geçenler: `state/pr/hook-egress-1.md` ve `hook-egress-1-2.md`. Reddedilenler: `hook-egress-1-x.md` ve `hook-egress-10.md`; desen `<pr>(-\d+)?` tam eşleşme. |
| 1e | **Kayıt 240** | Geçici kökteki `hook-guard.log`: 40 satır, en uzun ayrıntı 240. `test_log_truncates_to_240` testi var. |
| 2 | **210 çıplak docker build** | Hepsi `PROSES-175`: <br>• `docker build -t x .`, `docker buildx build`, `docker image build`, `docker builder build` <br>• `docker --context c build`, `DOCKER_BUILDKIT=0 docker build`, `/usr/bin/docker build` <br>• `sh -c 'docker build .'`, `$(docker build -q .)` <br>• `bash <<EOF` gövdesinde <br>`--help`, `buildx ls` ve `image ls` serbest. |
| 3 | **212 skip** | Linux tools'ta `py` yok. Testin skip gerekçesi: `'py' launcher not found (Linux container); the hook step of the gate runs on the host with py -3.12 (FOLLOWUP-212)`. Hostta aynı test koşuyor (409 passed). Handbook kapı satırı "Kapı hook adımı host'ta `py -3.12` ile koşar … `skip` olur, kanıt sayılmaz" diyor. Kapandı. |
| 4 | **213 initdb + mesajlar** | Gerçek postgres'te, yalnız kullanıcı (`ffcore_app` + boş parola) ve yalnız parola (boş kullanıcı + parola): konteyner **exit 1**, rol yok. Mesajlar çifti söylüyor: `APP_DB_USER is set but APP_DB_PASSWORD is empty; set both or neither` ve tersi. İkisi dolu: rol 1. İkisi boş: rol 0. `other` + parola: exit 1. `set -e` altında kaynaklanma durumunu işçinin statik testi gösteriyor (`set -e; . 20-app-role.sh; echo AFTER-INIT` → AFTER-INIT yok; iki yarım durum). Konteynerdeki "sourced" kopyamda giriş betiği yine "running" yazdı: Windows bağlaması +x gösteriyor, yani o yol konteynerde ayrıca sınanmış sayılmaz. Preflight `db_role_owner` mesajı: "set APP_DB_USER=ffcore_app and APP_DB_PASSWORD together" (test var). `.env.example` yorumu iki yarımı ayrı ayrı söylüyor. 12-2 r2 NOTE-1 ve NOTE-2 kapandı. |
| 5a | **208 boşken diff'siz** | `EGRESS_PROXY_URL` boşken `_EgressTransport` her isteği eski `_PinnedTransport`'a veriyor; `check_http_destination` yolu değişmedi. `test_03b_egress` yeşil. `test_03b_2_transport_pool_uses_pinned_backend` değişikliği gerekçeli: havuz bir düzey içeride (`_direct._pool`). Proxy'li istemcide `_ProxyOnlyBackend` olduğunu da kilitliyor. |
| 5b | **208 doluyken Squid üç durum** | Gerçek backend konteynerinde, ortamdan gelen `Settings()` ile: <br>• `api.allowed.test` → 200 (Squid `GET … 200`) <br>• `api.denied.test` → `egress_proxy_denied` (Squid 403) <br>• proxy'siz (`egress_proxy_url=""`) doğrudan çıkış → `egress_dns_failed` (işçi testi) <br>Ek probe'lar: <br>• `rebind.test` (izinli ad, iç ağ adresi), `bench.test` (198.18/15) GET ve CONNECT → `egress_proxy_denied` <br>• izinli adda port 8080 → `egress_proxy_denied (ERR_ACCESS_DENIED)` <br>• IP literal backend allowlist'inde ama Squid'de değil → `egress_proxy_denied` <br>• `OFFLINE=true` proxy'den önce `egress_offline` <br>• allowlist dışı ad proxy'ye hiç gitmiyor (`egress_not_allowlisted`) |
| 5c | **Proxy kökü dışına bağlantı** | `_ProxyOnlyBackend.connect_tcp` `api.allowed.test:9999`, `egress-proxy:3129` ve `198.51.100.10:3128` için `egress_proxy_only` ile reddediyor. Yani taşıyıcı yalnız proxy köküne çeviriyor. CONNECT tünelinden TLS ile düz HTTP sunucusuna gidiş `egress_request_failed` veriyor; sessiz geri düşüş yok. Proxy kapalıyken doğrudan yola düşmüyor (NOTE-2). |
| 5d | **İç hostlar doğrudan** | `litellm` (iç) 200; Squid logunda litellm satırı yok, doğrudan pinli yol. Gerçek backend'de `ALLOWED_INTERNAL_HOSTS` compose'tan geliyor. |
| 5e | **Ayar doğrulama** | `https://`, kimlikli, portsuz, yollu, sorgulu, `socks5://` ve port 99999 değerleri `egress_proxy_url_invalid` ile başlangıcı durduruyor. `http://Egress-Proxy:3128/` → `http://egress-proxy:3128`. |
| 5f | **Compose** | `backend`, `worker`, `agent-worker` ve `agent-worker-bg` ortamında `http://egress-proxy:3128`, `depends_on` healthy. Overlay yorumu güncel. |
| 5g | **SMTP, `readyz_probe`, docs tablosu** | Doğrudan HTTP istemcisi kalmadı: `AsyncClient(`, `requests` ve `urllib` için grep; tek istisna `notify.py` `smtplib`. kurulum.md: <br>• SMTP "fail with a connection error … use a webhook" <br>• `readyz_probe` iç çağrı <br>• beş satırlık "where the address check runs" tablosu, belge aralıklarının proxy yolunda izinli olduğu açıkça yazılı <br>• sorun giderme `egress_proxy_denied` ve `egress_not_allowlisted` ayrımı <br>`degisiklikler.md` güncel. |
| 6 | **Bilerek değişen testler** | Değişen üç test, listeyle birebir aynı: `test_03b_2_transport_pool_uses_pinned_backend`, `test_log_truncates_to_120` → `_240`, `test_settings_command_runs_guard` (`settings_hook_argv`). Diff'te silinen başka assert yok. |

## Bulgular

### MINOR-1 · `yorumlayici-govdesi-env-metni` · `.claude/hooks/ffcore_guard.py` `CODE_ENV_RE` / `env_hits`
**Ne oluyor:**
- Block kipinde, `py`/`python`/`node` heredoc gövdesinde boşluktan sonra gelen çıplak `.env` (`… .env`, `.env;`, `.env'`) `ENV` ile engelleniyor. Mesaj genel: ".env okunmaz ve yazılmaz". Neden engellendiği yazmıyor.
- Yol olarak `.env.example`/`.env.test` geçiyor; yani koordinatörün istediği düzenlemelerin çoğu yapılabiliyor.
- Ama `.env.example`'ın kendi yorum satırlarına (1, 2, 328, 338) ya da docs metnine dokunan bir Python düzenlemesi engelleniyor (probe 4/4).
- Handbook bunu "kabul edilen yanlış pozitif" diye yazıyor. Warn'da maliyeti yoktu; block'ta işçi sebebini bilmeden durur.

**Neden regex ile tam çözülmüyor:** `os.system('cat .env')` (K-HOOK2-0007 MINOR-2'nin yakaladığı durum) ile `'Copy: cp .env.example .env'` metni aynı biçimde.

**Seçenekler:**
- **A (önerim):** eşleşme aynı kalır. Kod gövdesinden gelen `ENV` mesajı ayrı yazılır, örneğin: "yorumlayıcı kodunda `.env` kelimesi geçiyor; betiği Write ile dosyaya yazıp `py <dosya>` ile koşun, ya da Edit aracı veya veri heredoc'u kullanın". Handbook satırı da bu yolu söyler. Gerçek `.env` erişimi engelli kalır, yanlış pozitif tek adımda aşılır.
- **B:** kod gövdesinde `CODE_ENV_RE` yerine `ENV_PATH_RE` (boşluk öneki yok). Yanlış pozitif kalkar ama `os.system('cat .env')` artık yakalanmaz; K-HOOK2-0007 MINOR-2 kararını geri alır.

### MINOR-2 · `kabuk-govdesi-sarmalayici` · `heredoc_reader` / `heredoc_commands`
**Ne oluyor:**
- K1 A kararı "sh/bash gövdesi komut" diyor. Ama `heredoc_reader` okuyucuyu yalnız segmentin ilk sözcüğünden ya da `| sh`'den buluyor.
- Aşağıdaki biçimlerde gövde "veri" sayılıyor ve tee'siz `pytest` **sessizce geçiyor**. Main'in guard'ı gövdeyi kabuk satırı diye taradığı için hepsini engelliyordu (probe2, dal exit 0 / main exit 2):
  - `env X=1 bash <<EOF`: `unwrap` atamayı önde bırakıyor; okuyucu `x=1` oluyor.
  - `docker compose run --rm -T tools sh <<EOF`
  - `docker compose exec -T backend bash <<EOF`
  - `docker exec -i <c> sh <<EOF`
  - `timeout 600 bash <<EOF` (handbook'ta `timeout` zaten denetlenmiyor, ama main bunu da yakalıyordu)
- Handbook "Komut başındaki `env [K=V]…` … `compose run|exec` … denetlenir" diyor; kural kendi belgesiyle çelişiyor.
- Tools konteynerinde çok satırlı test betiği koşmak işçilerin olağan yolu. Block'ta kanıtsız kapı koşusunu açar.

**Öneri:**
- `heredoc_reader`'da `unwrap` sonrası `strip_assignments` uygulanır.
- `compose_service_command` ile run/exec komutu çözülür. `docker exec` için seçenekler ve konteyner adı atlanıp komut alınır. Okuyucu `sh`/`bash` ise `shell` döner.
- İsteğe bağlı: `timeout <n>` atlanır.
- Her biçim için kırmızı test, `| tee`'li karşılığı sessiz.
- Aynı okuyucu çözümü `strip_heredocs`'a da uygulanırsa ENV'in kod gövdesi okuması da tutarlı olur. Bu bugün de eksik, yani regresyon değil.

### NOTE-1 · `docs/takim/ajanlarla-gelistirme.md` 648/654 eski
- Satır 648 "ilk 120 karakter" ve "ilk gün … warn" diyor; satır 654'teki settings örneği `"warn"`.
- Doğrusu 240 ve `block`. İşçinin notu (1); koordinatör aynı tur için touch-zone eki vermişti.

### NOTE-2 · Proxy kapalıyken hata kodu `egress_request_failed`
- Proxy adı çözülmezse `egress_proxy_unreachable`, ama proxy bağlantıyı reddederse (port kapalı ya da servis düşmüş) genel `egress_request_failed` dönüyor (probe).
- Doğrudan yola düşmüyor, fail-loud doğru. Operatör tanısı için ikisi aynı kod olsa iyi olur: `_ProxyOnlyBackend.connect_tcp` içinde `OSError` → `egress_proxy_unreachable`.

### NOTE-3 · Süreç: ayrık `run -d` + `docker logs > dosya` block'ta KAPI
- Askıda kalmayı önlemek için kullandığımız (ve önerilen) desen, block'ta `KAPI` ile engelleniyor: `cid=$(compose run -d … tools sh -c 'pytest …')`, ardından `docker logs $cid > evidence`.
- Çünkü tee komut satırında değil. Tee `sh -c` içine konunca (`pytest … 2>&1 | tee /tmp/x.log`) geçiyor; bu turdaki koşularımı böyle yaptım.
- Merge sonrası herkese bir satır duyuru ya da handbook örneği yararlı olur.

**Bilgi (bulgu değil):** betik dosyasıyla koşulan komut (`bash /tmp/s.sh`) denetlenmiyor; bu handbook'taki bilinen sınır.

## Bekleyen dosyalar (commit edilmedi)
- `state/reviews/hook-egress-1-r1.md`
- `state/evidence/hook-egress-1-r1-rv-{hook-probe,hook-probe2,hooks-host,hooks-linux,initdb,up,tests,backend-proxy,down}.log`
- `state/kanal/inceleyici.md`
