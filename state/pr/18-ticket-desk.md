# PR 18-ticket-desk

**Paket:** 18-ticket-desk · **Sınıf:** [A] · **Branch:** feat/18-ticket-desk · **Baz commit:** main 6f2a1ec · `FFCORE_VERSION=0.0.0-18td`
GOREV K-SEN-0011, plan onayı K-SEN-0012. Durum: GATES_RUNNING

## Plan

1. Semboller: 05a `mcp_client.discover/call` (auth `none` → başlık yok), `mcp_tools.apply_discovery` (yeni eylem kapalı + onaylı, S8), `api/tools.py` invoke (admin test çağrısı), `mcp_sql.validate` / `SqlRejected` (kodlar: …, `sql_function_not_allowed`), `tests/mcp_fixture.py` (uvicorn iş parçacığı deseni), compose `fake-llm` deseni (backend imajı + salt-okunur bağlama), 13a `gen/agents._definition`.
2. Kapsam: sahte ticket-desk + compose; 05a kaydı/keşfi; iki agent şablonu; expected_code doğrulaması; FOLLOWUP-76. Kapsam dışı: triyaj agent'ı ve F2 e2e koşusu (07 onayları gerekli), 06a sözleşme testi (06a'nın).
3. Felsefe: ARCH-07 iki senaryo (F2, F11) bu sahte sisteme bağlı, kalıcı karmaşıklık tek dosya + compose bloğu, ürün koduna girmez. ARCH-09 MCP SDK ve 05a zinciri kullanıldı, yeni altyapı yok. ARCH-10 sessiz yol yok: bilinmeyen bilet `ticket_not_found`, yinelenen bilet id'si yüklemede hata, send_reply yalnız kayıt.

## Değişen dosyalar

- `services/ticket-desk/ticket_desk_server.py`, `services/ticket-desk/README.md` (yeni)
- `deploy/docker-compose.yml`: `ticket-desk` servisi (profil `test`, port yok, `restart: "no"`, mcp-health)
- `.env.test`: `ALLOWED_INTERNAL_HOSTS` + `ticket-desk`; `.env.example`: yalnız açıklama satırı (K-SEN-0012)
- `Makefile`: `lint` `services/`'ı da tarar (yeni Python kodu orada)
- `data/samples/scripts/gen/poison.py` (+ `AGENT` zehirli-belge-asistani), `gen/versions.py` (+ `AGENT` surum-asistani), `gen/scenarios_sql.py` (w12, w15 expected_code), üretilen `data/samples/agents/{zehirli-belge-asistani,surum-asistani}.json`, `data/samples/eval/sql-write-attempts.json`
- `data/samples/scripts/tests/test_18.py`: `Test18Agents` (ag_1-3), `SQL_REJECT_CODES` + `sql_function_not_allowed`, determinizm listesine iki ajan
- `backend/tests/unit/test_18td_server.py`, `backend/tests/unit/test_18td_sql_write_attempts.py`, `backend/tests/integration/test_18td_tools_api.py` (yeni)
- `backend/tests/unit/test_08_cost.py` (FOLLOWUP-76, touch-zone eki)
- `data/samples/scripts/README.md`, `docs/gelistirme-ortami.md` (birer madde)
- Ayrı dal `feat/18-scenarios-e2e` aa937b0: NOT_RUN gerekçeleri güncellendi (ticket-desk var; expected_code kanıtlandı; eksik olan 07, triyaj agent'ı, 13b demo DB fikstürü).

## Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Üç araç keşfediliyor, şemalar doğru | `test_18td_1` | geçti |
| 1b | list_tickets tüm örnekleri verir, body/pii yok; limit | `test_18td_2`, `2b` | geçti |
| 1c | get_ticket gövdeyle, `pii` test anahtarı yok; zehirli bilet aynen | `test_18td_3`, `3b` | geçti |
| 1d | Bilinmeyen bilet kodlu hata, gönderim yok | `test_18td_4` | geçti |
| 1e | send_reply yalnız kaydeder; /_calls, /_reset | `test_18td_5`, `5b` | geçti |
| 1f | Dış sisteme kimlik gitmez (auth none: Authorization, X-On-Behalf-Of, Cookie yok) | `test_18td_6` (+ gerçek zincirde `test_18td_11`) | geçti |
| 1g | Dışarı istek 0: modül dışa bağlantı açabilecek hiçbir şey import etmez | `test_18td_7` | geçti |
| 1h | `--network none`'da çalışır | elle kanıt (komut aşağıda): healthz + MCP initialize 200, arayüzler yalnız `lo` (+ çekirdek tünel aygıtları) | geçti |
| 2 | 05a API ile kayıt + keşif, gerçek konteyner, .env.test ayarlarıyla | `test_18td_9` | geçti |
| 2b | Okumalar açılır, `send_reply` `needs_approval=true` kalır | `test_18td_10` | geçti |
| 2c | iç listede olmayan hosta forward_user 400 (F2 kapsamı) | 05a `test_05a_forward_user_external_host_400` | geçti (05a entegrasyon koşusunda) |
| 3 | İki şablon 13a biçiminde; KB, araç, onay, prompt kuralları | `test_18_ag_1..3` | geçti |
| 3b | 06a `AgentDefinition` (extra=forbid) ile doğrulama | tek seferlik: 06a dalı 43dafa2'nin `ffcore.runtime.definition` kopyası, beş şablon VALID; fazladan alan reddediliyor | geçti; kalıcı kapı 06a merge sonrası 06a sözleşme testi (NOT_RUN, K-SEN-0012) |
| 4 | 15 kayıt merge edilmiş doğrulayıcıdan `expected_code` ile düşer | `test_18td_12` (16 test) | kırmızı 2/15 (w12, w15: `sql_function_not_allowed`) → veri düzeltildi → geçti |
| 5 | FOLLOWUP-76: 08 maliyet testi yük altında kararlı, özellik aynı | `test_08_9_*`, yük altında 5 koşu | kırmızı 3/3 → geçti 5/5 |

## Çalıştırılan komutlar

Ortak: `FFCORE_VERSION=0.0.0-18td MSYS_NO_PATHCONV=1 docker compose -p ffcore-18td --env-file .env.test run --rm [--no-deps] tools …`. Çıktılar tee ile dosyada (scratchpad `gates18td/`).

| Komut | Ortam | Exit | Sonuç |
|---|---|---|---|
| `make lint` | tools | 0 | All checks passed; 250 dosya biçimli |
| `make test-samples` (+ `generate.py`, git status: yalnız beklenen iki dosya) | tools | GATES | |
| `make test` | `DEPLOY_PROFILE=llmaas` | GATES | |
| `make test` | `DEPLOY_PROFILE=airgap` | GATES | |
| `pytest tests/integration/test_18td_tools_api.py test_05a_tools_api.py test_05a_sql.py` | postgres, redis, ticket-desk ayakta | GATES | |
| 08 yük kanıtı: 21 CPU yakıcı (7 çekirdek) + `pytest test_08_cost.py::test_08_9_repeated…[10000-1.0]` ×3 | tools | 1 | eski ölçü: 3/3 `evaluate did not finish within 1.0 s` |
| aynı yük + `pytest tests/unit/test_08_cost.py` ×5 | tools | 0 | yeni ölçü: 6 passed ×5; yüksüz 6 passed |
| küçük bütçe (0.01 s, HANG_FACTOR 1000) | tools | — | CPU ataması düşüyor: bütçe hâlâ dişli |
| `docker run --rm --network none … ffcore/backend:0.0.0-18td python /svc/ticket_desk_server.py` + healthz + initialize | yok ağ | 0 | `healthz {"status":"ok"}`, `initialize 200 True`, arayüzler `lo tunl0 ip6tnl0` |

Kırmızı kanıtları: slice 1 `1 failed, 10 errors` (sunucu yok); slice 2 `3 errors` (servis yok); slice 3 `FileNotFoundError` (şablon yok); slice 4 `2 failed, 14 passed`; slice 5 yük altında 3/3.

## Varsayımlar ve sapmalar

1. **FOLLOWUP-76 ölçüsü `thread_time` değil `process_time`** (onaylı plandan sapma, gerekçeli): `evaluate` kuralları `asyncio.to_thread` işçilerinde koşar (`guardrails/engine.py:256, 311`); çağıran iş parçacığının `thread_time`'ı işi neredeyse hiç görmez, test dişsiz kalırdı. `process_time` bu sürecin tüm iş parçacıklarını sayar, başka süreçleri saymaz: yük altında düşme nedeni (paralel CI süreçleri) dışarıda kalır. Asılı kalma koruması duvar saatinde, bütçe × 10. Testin döndürdüğü süre hâlâ duvar saati (`test_08_9_latency_includes_the_preview` anlamı aynı).
2. `expected_code` düzeltmesi: w12 (`lo_create`) ve w15 (`pg_sleep`) 05a r1'den beri `sql_function_not_allowed`; sınıfları değişmedi (w15 `catalog` = sistem fonksiyonu, yazma yok).
3. zehirli-belge-asistani `run_sql`'e sahip ve onaylı: P2'nin yasakladığı araç elinde olmasa F11 "çağırmadı" kanıtı boş olurdu. surum-asistani araçsız.
4. Şablonlar ilgili senaryo modülünden üretilir (poison → zehirli, versions → surum); 13a'nın `agents` modülü ve `test_13a` dokunulmadı.
5. ticket-desk sunucusu MCP'yi kimliksiz kabul eder (auth none); yalnız test yığınında, port yayınlamaz.

## Kalan riskler

- F2 e2e (triyaj doğruluğu, onay sonrası gönderim, PII maskesi) 07 ve bir triyaj agent'ı ister; şablonu bu GOREV'de yok (FOLLOWUP önerisi).
- `process_time` aynı süreçteki başka iş parçacıklarının CPU'sunu da sayar (ör. modül fikstürlerinin uvicorn'u); boşta oldukları için etkisi yok sayıldı.
