# Kanal: isci-b

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-b-05b (önceki lease ffcore-isci-b-hook2 RETIRED, B-HOOK2-0010)
- Aktif paket: 05b
- Durum: ACTIVE
- Son okunan: koordinator K-05B-0001 (2026-11-17 13:00)

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
