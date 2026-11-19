# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-10c3
- Aktif paket: 10c-3 (MCP Sunucuları ekranı + MCP İzleme; FOLLOWUP-195, FOLLOWUP-197)
- Durum: ACTIVE
- Son okunan: koordinator K-10C3-0001; son yazılan C-10C3-0001 (ACK)
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
