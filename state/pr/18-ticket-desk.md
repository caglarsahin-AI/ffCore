# PR 18-ticket-desk — plan

Durum: PLANNED (2026-10-29 22:08) · GOREV K-SEN-0011 · Branch feat/18-ticket-desk (main ba48932, rebase hedefi 5bb675e) · Sınıf [A] · `FFCORE_VERSION=0.0.0-18td`

## Felsefe soruları

1. Değer: F2 (bilet triyajı, onaylı taslak) ve F11 (zehirli bilet) e2e'si sahte bir bilet sistemi olmadan koşamaz; NOT_RUN satırları kapanır.
2. Platformda var mı: MCP sunucusu resmi `mcp` SDK'sıyla (05a deseni), kayıt/keşif 05a'nın kendi zinciri; yeni altyapı yok.
3. Fail-loud: `send_reply` yalnız kaydeder, dışarı istek 0; bilinmeyen bilet `ticket_not_found` ToolError; her expected_code tek tek doğrulanır.

## Dilimler (her biri önce kırmızı)

1. **ticket-desk sunucusu** — `services/ticket-desk/ticket_desk_server.py` + `README.md`. Backend imajından, fake-llm gibi salt-okunur bağlanır (`python /svc/ticket_desk_server.py`); veri `data/samples/tickets/tickets-20.jsonl` + `poison/tickets-poison.jsonl` salt-okunur bağlanır. Araçlar: `list_tickets(limit=20)` (id, subject, received_at), `get_ticket(ticket_id)` (body dahil), `send_reply(ticket_id, body)` (bellekte kaydeder). Muayene: `GET /_calls`, `GET /_sent`, `POST /_reset`, `GET /healthz`. Compose: `ticket-desk` servisi `profiles: ["test"]`, port yok, `make smoke`'a dokunulmaz.
   Testler: birim (`backend/tests/unit/test_18td_server.py`: araç listesi, bilinmeyen bilet hatası, send_reply kaydı ve dışarı istek yok: `SafeOutboundClient`/httpx çağrılmaz) + entegrasyon (`backend/tests/integration/test_18td_live.py`: konteynere keşif, `send_reply` sonrası `/_sent`).
2. **05a'ya kayıt + keşif gerçek zincirle** — 05a API (`POST /tools`, keşif) ile `ticket-desk` kaydı; yeni eylemler devre dışı + `needs_approval=true` (K-05a-0002 S8); admin `list_tickets`/`get_ticket`'i açıp onaysız yapar, `send_reply` `needs_approval=true` kalır; test bunu doğrular.
3. **İki agent şablonu** — `data/samples/agents/zehirli-belge-asistani.json`, `surum-asistani.json` (mevcut `sozlesme-asistani.json` biçimi). Doğrulama: `feat/06a-agent-runtime:backend/openapi/06a.yaml` agent tanım şemasına karşı tek seferlik komut (kanıt PR'da) + stdlib yapısal test (`test_18.py`: anahtar kümesi mevcut şablonlarla aynı, tools/kb anahtarları var olan örneklere işaret ediyor).
4. **expected_code doğrulaması** — `backend/tests/unit/test_18td_sql_write_attempts.py`: her `sql-write-attempts.json` kaydı `mcp_sql.validate(sql, TABLES, max_rows=…)`'dan `SqlRejected(code == expected_code)` alır; e2e `test_18_f3_9` NOT_RUN gerekçesi buna göre güncellenir (e2e dalında).
5. **FOLLOWUP-76** — `backend/tests/unit/test_08_cost.py` (touch-zone eki): bütçe ölçüsü duvar saatinden işçi iş parçacığının CPU süresine (`time.thread_time()`) geçer; yük altında başka süreçlerin CPU'su sayılmaz. Asılı kalma koruması duvar saatinde kalır ama geniş (bütçe × 10): sonsuz döngü yine düşer. Doğrulanan özellik aynı (sınırlı + maskeli + hiçbir bulgu atlanmaz). Kırmızı kanıtı: eski ölçü yapay yük altında (paralel CPU yakıcı süreçler) düşer, yenisi geçer; komut ve çıktı PR'da.

## Varsayımlar

1. ticket-desk sahte *dış* sistemi temsil eder: `forward_user` değil `auth_type=none`. Kayıt için host `ticket-desk` gerekli: `.env.test` ve `.env.example`'da `ALLOWED_INTERNAL_HOSTS`'a `ticket-desk` eklenir (secret değil; touch-zone eki). Alternatif: testte settings override (gerçek backend konteyneri kaydı reddeder, "gerçek zincir" şartı bozulur).
2. 06a henüz main'de değil; şablon doğrulaması 06a dalının OpenAPI'sine karşı elle yapılır, 06a merge sonrası 06a'nın sözleşme testi kalıcı kapı olur.
3. Kod `services/ticket-desk/**`'da (GOREV); backend paketine girmez çünkü ürün kodu değil test aracı.

## Touch-zone

`services/ticket-desk/**`, `deploy/docker-compose.yml` (yalnız `ticket-desk` servisi), `.env.test`/`.env.example` (`ALLOWED_INTERNAL_HOSTS` tek satır), `data/samples/agents/{zehirli-belge-asistani,surum-asistani}.json`, `data/samples/scripts/tests/test_18.py`, `backend/tests/unit/test_18td_*.py`, `backend/tests/integration/test_18td_*.py`, `backend/tests/unit/test_08_cost.py` (FOLLOWUP-76), `data/samples/scripts/README.md` / `docs/gelistirme-ortami.md` (birer satır).
