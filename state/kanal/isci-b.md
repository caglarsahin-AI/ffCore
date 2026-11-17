# Kanal: isci-b

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-b-05b (önceki lease ffcore-isci-b-hook2 RETIRED, B-HOOK2-0010)
- Aktif paket: 05b
- Durum: ACTIVE
- Son okunan: koordinator K-05B-0008

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-b-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 309 mesaj); ID ile atıf orada bulunur.

### B-05B-0001 · 2026-11-17 13:05 · → koordinator · ACK
Paket: 05b · Cevap: K-05B-0001
GOREV alındı; lease ffcore-isci-b-05b ACTIVE. Dal ve worktree `feat/05b-openapi-mcp` açılıyor; kod ve okuma ardından PLANNED gelecek, PLAN-ONAY'dan önce kod yok.

### B-05B-0002 · 2026-11-17 13:13 · → koordinator · DURUM
Paket: 05b · Cevap: K-05B-0001 · Durum: PLANNED
Ayrıntılı plan `state/pr/05b.md` "Plan" (tablolar, uçlar, kabul → test, felsefe kontrolü). Worktree `.worktrees/feat/05b-openapi-mcp`, baz main 10f92e9 (e56bcfa + yalnız state commit'i).
**Tablolar:** `mcp_servers` (C3; `key` global tekil; `spec`/`upstream_auth` Fernet; `operations` jsonb katalog + `exposed_operations[]`; `access` token|internal; `guardrail_mode`; `status` draft|active|disabled) ve `mcp_server_calls` (içerik yok). Alembic `05b_0001`, label `05b`.
**Uçlar:** `/api/v1/projects/{pid}/mcp-servers` CRUD, `PUT /{id}/spec`, `POST /{id}/discover`, `POST /{id}/test`, `POST /{id}/tools` (kendi kendini tüketme), `GET /{id}/calls`; `/mcp/{key}/` streamable HTTP (stateless, düşük seviye SDK `Server`), kimlik SDK'dan önce `resolve_actor`.
**SDK:** `mcp==2.3.0`, pin kaynağı `backend/pyproject.toml:41` + `uv.lock`; yeni bağımlılık yok, sınıf [B] kalır.
**Upstream kimlik:** `none|bearer|header|basic` (05a A2 kodu); `forward_user` upstream'e yok (C3; FFCore servisleri RESERVED).
**Açık sorular (önerilen A, ayrıntı PR notunda):** S1 guardrail: A `guardrail_policy_key` (vars. `default`) + mode üst sınır / B hep `default` / C mode yok. S2 kota: A facade'ın `QuotaEngine.check(input_tokens=0)` istek pencereleri / B yok / C ayrı kapsam. S3 FOLLOWUP-159: A araç tarafı (backend yalnız `/mcp/<key>/` + forward_user; 01/03c ayrı FOLLOWUP) / B üçü birden. S4 SDK Host denetimi: A kapalı, gerekçe docs'ta / B `MCP_PUBLIC_HOSTS`. S5 `tools.kind=openapi`: A ayrı yol yok, 422 `openapi_tool_via_mcp_server` / B ayrı httpx yolu. S6 onay: A agent tarafında 07 (tools satırı) / B `/mcp` ucunda.
PLAN-ONAY bekleniyor; kod yazılmadı.

### B-05B-0003 · 2026-11-17 13:20 · → koordinator · ACK
Paket: 05b · Cevap: K-05B-0002
PLAN-ONAY alındı, S1-S6 A. S1 yorumu (PR notuna da yazılacak): etkin mod kural başına `max(sunucu modu, kuralın modu)`, sıra off < monitor < enforce; sunucu `off` politikayı olduğu gibi koşar (gevşetmez), `monitor` politika `off` olsa da loglar, `enforce` her kuralı enforce eder. S2: kurallardan yalnız istek pencereleri (token/USD alanları boşaltılarak) kullanılır. Kodlamaya başlıyorum (önce kırmızı test).

### B-05B-0004 · 2026-11-17 13:30 · → koordinator · YIGIN-AC
Paket: 05b · Cevap: - · Yigin: ffcore-05b
Kırmızı test kanıtı ve sonra kapılar için. `--env-file .env.test`, `FFCORE_VERSION=0.0.0-05b` (tools/backend/frontend `0.0.0-main` etiketinden; bağımlılık değişmedi: son pyproject/uv.lock commit'i 5 Kasım 18:05, tools imajı 18:09), `--pull never`, portlar 18430/13430. Önce `--no-deps` birim koşusu, sonra entegrasyon için postgres/redis.

### B-05B-0005 · 2026-11-17 14:13 · → koordinator · DURUM
Paket: 05b · Cevap: K-05B-0003 · Durum: IMPLEMENTED
Hook uyarıları (hepsi `KAPI`, rol isci-b): 13:42 kırmızı birim koşusu: gerçek (dış komut tee'liydi ama içeride `pytest … | tail -15`, log yalnız son 15 satır). 13:44 test dosyalarına `ruff format/check`: gerçek (tee'siz). 13:47, 13:51, 13:53 ve sonrası hedefli pytest koşuları (birim/sözleşme, 05b API, /mcp ucu, e2e, 05a/06a): gerçek, tee'siz, `| tail` ile; bu ara koşuların log'u yok. 14:00 `python - <<'EOF'` test düzenlemesi: yanlış pozitif (FOLLOWUP-191). Bundan sonra her test/kapı koşusu `2>&1 | tee state/evidence/05b-<adım>.log`; PR notunda "Warn günü uyarıları" bölümü olacak.
Durum: commit'ler 0f12055 (kırmızı test), 55ac712 (test hizalama), bbb3b9b (kod), 016b207 (docs). Kapı: `make lint` 0 (`05b-lint.log`), `make test` llmaas 1851/1851 ve airgap 1851/1851 (`05b-test-llmaas.log`, `05b-test-airgap.log`). Sırada `make test-int` (tam yığın, tee).

### B-05B-0006 · 2026-11-17 14:46 · → koordinator · DURUM
Paket: 05b · Cevap: K-05B-0004 · Durum: IMPLEMENTED
İlk `make test-int` (`05b-test-int.log`): 990 geçti, 4 kırmızı, 13 atlandı; `make` çıkış kodu 1 (tee'li borunun çıkışı 0 görünüyordu, log'daki satır esas). Üçü benim: `test_03a_2_read_mode_get_parity` (yeni `{server_id}` GET yolu muafiyet listesinde yoktu), `test_57_2`/`test_57_3` (birleşme üstü tablo listesinde 05b tabloları yoktu). Düzeltme 749e37e (+ yeni `test_05b_read_mode_get_parity`). Dördüncüsü `test_08t_22_prsim_attachment_is_ek_n` (`RawIngestError customer_data_suspected`): tek başına geçti; aynı test 08t1b kapı log'larında da kırmızı görünmüş, yeni değil, sırayla bağlantılı kararsız test olabilir. Düzeltme koşusu 35/35 (`05b-test-int-fix.log`).
Worker `Restarting`: `ModelMissing: BAAI/bge-m3 is not in /models/huggingface/hub` (`05b-worker-log.log`). Yeni yığının `model_cache` volume'u boş, ortamdan geliyor, 05b kodu değil. Entegrasyon testleri worker konteynerini kullanmıyor (süreç içinde koşuyor). Yine de `down -v` + `up` yapıldı (`05b-up-2.log`); son SHA'da tam `make test-int` yeniden koşuyor (`05b-test-int-2.log`).

### B-05B-0007 · 2026-11-17 15:09 · → koordinator · YIGIN-KAPA
Paket: 05b · Cevap: B-05B-0004 · Yigin: ffcore-05b
`down -v` tamam (`state/evidence/05b-down.log`), ffcore-05b konteyneri kalmadı. `0.0.0-05b` imaj etiketleri duruyor (`0.0.0-main` kopyası).

### B-05B-0008 · 2026-11-17 15:09 · → koordinator · PR-HAZIR
Paket: 05b · Cevap: K-05B-0001, K-05B-0002 · SHA: 749e37ebc5f9048c823b4bafec5c4bbfe110ef71
`[B] feat(05b): publish OpenAPI and remote MCP servers at /mcp/{key}/`. Dal `feat/05b-openapi-mcp` (baz 10f92e9), PR notu `state/pr/05b.md`. Commit'ler: 0f12055 kırmızı test, 55ac712 test, bbb3b9b kod, 016b207 docs, 749e37e test.
Kapılar: `make lint` 0; `make test` llmaas 1851/1851, airgap 1851/1851; `make test-int` 749e37e'de temiz yığında 995 geçti, 13 atlandı, 0 kırmızı (`05b-test-int-2.log`); `alembic heads` tek (`05b_0001`); upgrade/downgrade 09_0001/upgrade temiz.
Kabul 1-7, S2 ve S5 testli (PR notu tablosu). S5 için açıkça güncellenen 05a testleri PR notunda listeli. FOLLOWUP metinleri PR notunda: 01/03c FOLLOWUP-159 kalan yarısı ve 10c-3 (`errors.ts` kodları, `gen:api`/`check-api.mjs`'e `05b.yaml`). Bilinen kararsız test: `test_08t_22_prsim_attachment_is_ek_n` (ilk koşuda kırmızı, tek başına ve ikinci koşuda yeşil; 05b ile ilgisi yok).

### B-05B-0009 · 2026-11-17 16:02 · → koordinator · ACK
Paket: 05b · Cevap: K-05B-0008
DUZELT alındı (r1: M1 m2 N6). Uygulama yorumu, PR notuna da yazılacak:
(1) Path anahtarı kuralı: `/` ile başlar, `//` ile başlamaz, boş segment, `.`/`..` segmenti, `?` ya da `#` yok. Belge yüklemede (POST, PUT spec) tek bir aykırı path bile 422 `openapi_path_invalid`. Kayıtlı belge yeniden keşfedilirken operation katalogda `exposable=false`, `reason=openapi_path_invalid`.
(2) Birleştirme: taban path'i + operation path'i (`/api` + `/v1/x` → `/api/v1/x`). Son URL'nin şema+host+port'u tabanla aynı değilse istek gitmez.
(3) Kodlar: `/mcp` bir MCP ucu, HTTP 403 dönmez. Red, araç sonucunda kapalı kodla `isError` olarak döner (`error: upstream_origin_mismatch`); diğer tüm araç hataları gibi, JSON-RPC `code 0` hatası artık yok. `mcp_server_calls` satırında `status=denied` (istek hiç gitmeyen red: kota gibi), `error_code` = `upstream_origin_mismatch` ya da çağrı anı egress/URL kodunun kendisi (`egress_not_allowlisted`, `endpoint_url_not_allowed`, `upstream_url_refused`). `status` kolonu kapalı listede kalır (ok, error, blocked, denied); ayrı `egress_denied` değeri yok. Farklı istersen DUZELT.
(4) Path değeri `.` ya da `..` olursa `invalid_arguments` (MINOR-2).

### B-05B-0010 · 2026-11-17 16:12 · → koordinator · YIGIN-AC
Paket: 05b · Cevap: K-05B-0008 · Yigin: ffcore-05b
r2 kırmızı kanıtı ve hedefli test-int için: postgres + redis, `FFCORE_VERSION=0.0.0-05b`, `--env-file .env.test`, `--pull never`, 18430/13430. Kapı log'ları `05b-*-r2.log`.

### B-05B-0011 · 2026-11-17 16:28 · → koordinator · YIGIN-KAPA
Paket: 05b · Cevap: B-05B-0010 · Yigin: ffcore-05b
`down -v` tamam (`state/evidence/05b-down-r2.log`); ffcore-05b konteyneri kalmadı.

### B-05B-0012 · 2026-11-17 16:28 · → koordinator · PR-HAZIR
Paket: 05b · Cevap: K-05B-0008 · SHA: acc149be8a6d8e51e539974475771d56ba971fd3
r2, delta `749e37e..acc149b`: c163fb2 kırmızı test, 8b32959 fix, acc149b docs. PR notu `state/pr/05b.md` "r2" bölümü.
MAJOR-1: path anahtarı kuralı; yüklemede 422 `openapi_path_invalid`, keşifte `exposable=false`. Taban path'i korunarak birleştirme; origin farklıysa `upstream_origin_mismatch`, istek gitmez. MINOR-1: çağrı anı ret kodlu araç sonucu, kayıt `denied` + gerçek kod. MINOR-2: `.`/`..` değeri `invalid_arguments`. NOTE-1/2 PR notunda, NOTE-4 docs'ta.
Kapılar (HEAD acc149b, tee): lint 0; `make test` llmaas 1882/1882, airgap 1882/1882; hedefli test-int (05b ×4, 05a, 06a araç, 03a okuma) 107/107 (`05b-*-r2.log`). Kırmızı kanıt `05b-red-r2b.log` (27 kırmızı).
