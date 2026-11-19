# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-10c3
- Aktif paket: 10c-3 (MCP Sunucuları ekranı + MCP İzleme; FOLLOWUP-195, FOLLOWUP-197)
- Durum: ACTIVE
- Son okunan: koordinator K-10C3-0006; son yazılan C-10C3-0007 (PR-HAZIR r2)
- Önceki lease: ffcore-isci-c-10c2 RETIRED (10c-2 MERGED b93cd96; son C-10C2-0016 RETIRED); ondan önce ffcore-isci-c-sse RETIRED (fix/10b-sse-bekci MERGED 4216718; son C-SSE-0011 RETIRED); ondan önce ffcore-isci-c-10c1 RETIRED (10c-1 MERGED; son C-10C1-0015 RETIRED); ondan önce ffcore-isci-c-10bp2 RETIRED (10b-poc-2 MERGED b43770d; son C-10bp2-0019 HANDOFF)

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-c-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 97 mesaj); ID ile atıf orada bulunur.

### C-10C3-0001 · 2026-11-19 14:05 · → koordinator · ACK
Paket: 10c-3 · Cevap: K-10C3-0001
GOREV alındı; lease ffcore-isci-c-10c3 ACTIVE. Dal feat/10c-3-mcp-ui açılıyor; okuma ve keşif sonrası PLANNED gelecek, PLAN-ONAY'dan önce kod yazılmaz.

### C-10C3-0002 · 2026-11-19 14:05 · → koordinator · DURUM
Paket: 10c-3 · Cevap: K-10C3-0001 · Durum: PLANNED
Worktree `.worktrees/feat/10c-3-mcp-ui` (dal feat/10c-3-mcp-ui, baz main bd240ca). Tam plan (dosya listesi, kabul→test, felsefe kontrolü): `state/pr/10c-3.md` "Plan" + "Açık sorular".
Rota/menü: `/mcp-servers` (Yapı menüsü, `ready:true`, developer+), `/mcp-servers/[serverId]` sekmeler Ayarlar · Operasyonlar · İzleme. Commit sırası: D0 197 (kırmızı test → eval.py), D1 tipler/SPECS/sorgular/errors (+ araç formundan `openapi` türü çıkar, 05b S5), D2 ekranlar, D3 izleme, D4 read/rol/tema/axe, docs ayrı commit.
Açık sorular (ayrıntı PR notunda):
S1 roller: 05b'de bütün mutasyonlar admin, brief "developer yükler" diyor. **A (önerilen)** backend'e uy: developer okur, mutasyon `DisabledWithReason needs=admin`, kabul 1 admin ile; B 05b'yi developer'a aç (touch-zone dışı); C ekran admin+.
S2 e2e upstream: **A (önerilen)** `http://litellm:4000` (ALLOWED_INTERNAL_HOSTS'ta; `/test` her HTTP cevabını reachable sayar), compose/backend değişmez; B test profiline sahte Superset servisi (touch-zone dışı); C Playwright ağ taklidi.
S3 izleme verisi: **A (önerilen)** ok/error/blocked/denied gösterimi Vitest fikstürüyle + e2e'de gerçek çağrı (`error upstream_http_404`); B e2e'de DB'ye satır (test kancası); C yalnız Vitest.
S4 audit: **A (önerilen)** çağrı `run_id` → koşu sayfası + audit eylem adları açıklamada (audit ekranı `ready:false`); B admin'e `GET /audit?resource_type=mcp_server` listesi (sunucuya göre süzme yok); C backend'e `resource_id` filtresi (kapsam dışı).
Varsayım: spec'i URL'den çekme yok (backend ucu yok; tarayıcıdan dış istek egress'i atlar). PLAN-ONAY bekliyorum.

### C-10C3-0003 · 2026-11-19 14:33 · → koordinator · KARAR-GEREK
Paket: 10c-3 · Cevap: K-10C3-0002
S2-A uygulanamaz (benim keşif hatam): 05b `check_upstream_url` (`services/mcp_publish.py:121`) `RESERVED_HOSTS`'taki (`services/external_config.py:62`) her adı 422 `upstream_url_refused` ile reddediyor; `.env.test` `ALLOWED_INTERNAL_HOSTS`'taki adların hepsi (litellm, langfuse-web, mcp-search, mcp-sql, ticket-desk) orada. e2e'de sunucu litellm ile oluşturulamaz; ayrılmamış ad da egress'te `egress_not_allowlisted`.
**A (önerilen):** e2e konteynerini `run --name ffcore-10c3-e2e-upstream` ile açıp spec içinde Node ile sahte Superset upstream'i (örnek yollara 200/404 JSON) dinlemek; yığın `ALLOWED_INTERNAL_HOSTS=...,ffcore-10c3-e2e-upstream` komut satırı değeriyle (dosya değişmez). Etkisi: bağlantı testi geçer, İzleme'de gerçek `ok` ve `error upstream_http_404` satırları; değişiklik yalnız `tests/e2e/**` + docs/onyuz.md komut dizisi.
B: `test` profiline sahte upstream servisi (compose + `backend/tests/fakes`; compose servisi = sınıf C, touch-zone dışı).
C: e2e'de erişilebilir upstream yok: bağlantı testi "erişilemiyor + kod" gösterir; "geçer" kanıtı Vitest ve 05b test-int'te kalır.
Yan bulgu (FOLLOWUP adayı, düşük): `RESERVED_HOSTS` yalnız servis adını eşler; platform servisinin konteyner adı (`<proje>-litellm-1`) ya da IP'si operatör `ALLOWED_INTERNAL_HOSTS`'a koyarsa upstream olarak geçer. A bu boşluğu kullanmaz (sahte upstream platform servisi değil), ama "e2e" servis adı ayrılmışken run konteyneri adı ayrılmamış.
İlerleme: D0 (197) 22e45c5, D1 6c5f61b, D2 d1f9a2f, D3 0b3d829 commit'li; Vitest 275 yeşil. Cevap beklerken D4 (read/rol Vitest + upstream'e bağlı olmayan e2e'ler) sürüyor.

### C-10C3-0004 · 2026-11-19 14:52 · → koordinator · YIGIN-AC
Paket: 10c-3 · Cevap: K-10C3-0003 · Yigin: ffcore-10c3
18450/13450, `--profile test`, `--pull never`, imajlar `0.0.0-main` → `0.0.0-10c3` etiketi (build yok; e2e backend'i eval.py düzeltmesini içermez, e2e'yi etkilemez). Sıra: e2e (10c-3 + etkilenen araç/salt-okunur spec'leri, sonra tam koşu), hedefli test-int (09 özet) kaynaktan. Shell: `ALLOWED_INTERNAL_HOSTS=<.env.test listesi>,fake-llm,ffcore-10c3-e2e-upstream`, `EGRESS_ALLOWLIST=superset.example.com`, `FAKE_EMBED=1`.

### C-10C3-0005 · 2026-11-19 16:05 · → koordinator · YIGIN-KAPA
Paket: 10c-3 · Cevap: C-10C3-0004 · Yigin: ffcore-10c3
`down -v` tamam; konteyner 0, volume 0 (`10c-3-down.log`). e2e tam 188/189 (tek kırmızı `test_10a_1_theme_switch` ilk test soğuk başlangıç; tek başına 3/3 yeşil), backend 1925×2, test-int 76.

### C-10C3-0006 · 2026-11-19 15:34 · → koordinator · PR-HAZIR
Paket: 10c-3 · Cevap: K-10C3-0001, K-10C3-0003 · SHA: b692ad696b479cd4a4031328f1f5e19322b5f470
Dal `feat/10c-3-mcp-ui` (baz bd240ca; main'e sonradan yalnız state/KARARLAR geldi, rebase gerekmedi), 12 commit, çalışma ağacı temiz. PR notu `state/pr/10c-3.md` (kabul 1-7 → test, komutlar, e2e upstream bölümü, varsayımlar, riskler).
Kapılar: önyüz gen:api (diff yok) / check:api / lint / typecheck 0, Vitest 279; backend `make lint && make test` llmaas ve airgap 1925 passed; hedefli test-int 76; e2e 10c-3 + etkilenen 27/27, tam koşu 188/189 (tek kırmızı `test_10a_1_theme_switch` soğuk başlangıç, tek başına 3/3). Backend diff'i yalnız `api/eval.py` + iki test.
Notlar: developer e2e NOT_RUN (03a `role_reserved`, Vitest'te); D4 read-only Vitest ilk koşuda yeşil (kapılar D2'de). Hook uyarısı kaydı yok. Düzeltme: C-10C3-0005 YIGIN-KAPA başlığındaki saat yanlış (16:05 yazıldı, gerçek ~15:30).

### C-10C3-0007 · 2026-11-19 16:46 · → koordinator · PR-HAZIR
Paket: 10c-3 · Cevap: K-10C3-0006 · SHA: 2b79c345bfdce904f1cdc72e29f03172ebef5028
r2 metin dilimi, delta `b692ad6..2b79c34`: `bd3a824` docs (`docs/araclar.md` durum tablosu ve paragraf: `denied` = istek gitmedi, kota/egress/origin/path kuralı, `openapi_path_invalid` belge ya da çağıranın `a/b`, `../x` değeri; `error` = istek gitti ya da argüman denetimi düştü; "belgeyi düzelt" cümlesi kalktı, "nedeni `error_code` söyler" kaldı), `2b79c34` messages (`statusNote` en/tr, örnek `upstream_http_404`). Kod, test, yığın yok; çalışma ağacı temiz.
Kapı: node konteyneri `--network none`: lint 0, typecheck 0, i18n Vitest 14 passed, tam Vitest 279 passed (`10c-3-r2-frontend-gate.log`, `10c-3-r2-vitest.log`). PR notuna "r2" bölümü eklendi. FOLLOWUP-199/200 dokunulmadı. Hook uyarısı yok.
