# İş Kuyruğu (tek sahiplik kaynağı)

Durumlar: READY · CLAIMED · PLANNED · IMPLEMENTING · IMPLEMENTED · VERIFIED · REVIEWED · MERGED · BLOCKED (EXECUTION_HANDBOOK 1). Kapı kuralı: paket **doğrudan bağımlılıkları MERGED olunca** READY (E). **Yalnızca koordinatör yazar**; işçi durum değişikliğini kendi `state/kanal/<rol>.md` dosyasına `DURUM` mesajıyla bildirir (MULTI_AGENT_PROTOCOL).

## PoC (M1-M3, PayCore LLM'de `airgap`) · aktif dalga: 1

| Paket | Durum | İşçi | Branch | Worktree | Touch-zone | Başlangıç | PR | Bağımlılık / not |
|---|---|---|---|---|---|---|---|---|
| 00 | MERGED | A | feat/00-repo-skeleton (silindi) | (kaldırıldı 08:30) | kök, backend/ ve frontend/ iskelet, deploy/, Makefile, docs/gelistirme-ortami.md (data/samples hariç) | 2026-10-28 | | dalga 1; GOREV K-00-0001; plan state/pr/00.md onaylandı (K-00-0004); ENV-19/20/23 kapandı; cc4829a compose+tools; review r1 DUZELT → r2 ONAY (1f5fbc6, state/reviews/00-r2.md); main'e --no-ff merge bb634e4 2026-10-28 08:18, smoke passed |
| 00i | MERGED | B | paycoreLLM: feat/00i-ffcore-integration (baz master 81e3609); ffcore: feat/00i-docs | (paycoreLLM-00i worktree kaldırıldı 13:08; ffcore 00i-docs kaldırıldı) | ... plan onaylı K-00i-0003 (K1-K4 A); VERIFIED 09:58: paycoreLLM 1a2ba24 (7 commit, 64 kabul testi, takım 466), ffcore docs c18de09; NOT_RUN kriter 55/56 sunucu ölçümü (ENV-45, kullanıcı), make test/lint (ENV-43), docker build (ayna); review r1 (R-00i-0002, state/reviews/00i-r1.md): DUZELT, MAJOR 1 (redact iç içe alanlara inmiyor: headers.Authorization ve Langfuse exporter istisnasında secret açık); r1 düzeltmesi 9763404 (config.scrub özyinelemeli, secret kümesi config'ten, structlog config.py'de; 6 negatif test, 00i 70/70); VERIFIED (ölçüm bekliyor) 10:26; r2 ONAY (R-00i-0004, state/reviews/00i-r2.md) 10:33; ffcore docs c18de09 main'e merge ea83d78, smoke passed, worktree kaldırıldı; paycoreLLM feat/00i-ffcore-integration @ 9763404 MERGE'E HAZIR, kullanıcı merge eder (önce ENV-38 nexus, ENV-45 ölçüm sonuçları docs'a işlenir → docs-only r3); isci-b ölçüm sonuçlarını bekliyor; r3 (K-00i-0015 konteynerde test): 0498829 compose.test.yml + Dockerfile test aşaması + Makefile (00i 70, takım 472, ruff check 0), biçim commit'i baf9dde; r3 PR-HAZIR baf9dde doğrulandı 12:10 (konteynerde lint 0, takım 472, 00i 70); r3 ONAY (R-00i-0007, state/reviews/00i-r3.md) 12:24; paycoreLLM feat/00i-ffcore-integration @ baf9dde MERGE'E HAZIR, kullanıcı merge eder (ENV-45 ölçümleri merge sonrası da olabilir, docs ayrı küçük PR); ENV-38/43/50 kapandı, ENV-45 kullanıcıda; paycoreLLM master'a --no-ff merge 8594bb0 2026-10-28 13:06 (koordinatör, kullanıcı yetkisi, KARARLAR); ENV-45 sayıları ayrı docs PR'ı |
| 13a | MERGED | test | feat/13a-sample-data (silindi) | (kaldırıldı 09:36) | data/samples/** + Makefile `lint` hedefine tek satır (K-13a-0009) | 2026-10-28 | | dalga 1, 00'a paralel; HEAD 4c29817 (main 78c8412 üstüne rebase): VERIFIED 08:30 (tools lint/test 0, 13a testleri konteyner+host 18/18 + Postgres 3/3; DOCX create_system düzeltmesi); ruff B uygulandı d70f77a (çıktı bayt aynı, Makefile lint 2 satır); review r1 (R-13a-0002, state/reviews/13a-r1.md): DUZELT, MAJOR 2 (veri-soru-cevap prompt get_schema+run_sql vs max_tool_calls 1; q14 must_contain), MINOR 1 (Postgres fixture rm -f); r1 düzeltmeleri e663597 (şema prompt'ta, yalnız run_sql, ask_user false; q14; pg fixture benzersiz ad); VERIFIED 09:22; r2 ONAY (R-13a-0004, state/reviews/13a-r2.md); main'e --no-ff merge c8024fe 2026-10-28 09:33, smoke+lint passed |
| 03a | MERGED | A | feat/03a-identity-catalog (silindi) | (kaldırıldı 15:16) | backend/ffcore/{models/{identity,catalog}.py, api/*, core/{auth.py resolver kaydı + require_role, secrets.py, config ekleri}, services/catalog_loader.py}, alembic 03a, openapi/, tests, deploy/seed/model_catalog.yaml, docs/api.md | 2026-10-28 | | 00, 00i, 03b MERGED; GOREV K-03a-0001; oturum ffcore-isci-a-03a ACK 13:16; PLANNED 13:22, plan onaylı K-03a-0002 (S1-S6 A; DRIFT-53/54/55; touch-zone + main.py, core/session.py, core/passwords.py, services/providers.py, services/catalog_events.py, cli.py, scripts/export_openapi.py, pyproject+uv.lock, docker-compose.yml app-env + migrate.command); dilim 0-6 tamam; HEAD b578ac0 (7 commit): VERIFIED 14:21 (lint 0, test 133 + test-int 78 iki profil, temiz volume up 67 s + migrate 03a+03b + katalog 2 kayıt + smoke, iki head beklenen, downgrade 03a@-1, CLI superadmin + curl login/C6/401); NOT_RUN yalnız gerçek satıcı testleri; review r1 (R-03a-0003, state/reviews/03a-r1.md): DUZELT, MAJOR 3 (OBO proje sınırı global yollarda atlanıyor → karar A; PATCH explicit null 500; kullanımdaki sağlayıcı PATCH ile pasifleşiyor → 409); r1 düzeltmesi 6ede802 (OBO sınırı A, Patch tabanı 422, provider_in_use 409; OpenAPI 21 alanda null kalktı); VERIFIED 14:58 (lint 0, 134 + 94 iki profil, up + smoke); r2 ONAY (R-03a-0005, state/reviews/03a-r2.md); main'e --no-ff merge 591aac3 2026-10-28 15:14, smoke + lint passed, heads 03a_0001 + 03b_0001 (dalga sonu merge revizyonu FOLLOWUP-57) |
| 03b | MERGED | A | feat/03b-audit-egress (silindi) | (kaldırıldı 12:31) | backend/ffcore/{models/audit.py, core/audit.py, core/egress.py, core/auth.py (resolve_actor OBO+servis yolu), core/db.py, core/config ek}, alembic 03b etiketi + alembic/env.py, tests, docs/api.md; ek (S4): models/base.py, models/__init__.py (kendi satırı), core/errors.py, main.py (handler), pyproject+uv.lock, .env.example (tamamı İngilizce) | 2026-10-28 | | 00 MERGED; dağılım değişikliği 2026-10-28: A; GOREV K-03b-0001 + DUZELT K-03b-0002 (İngilizce OpenAPI); oturum ffcore-isci-a-03b; rebase 8ba004c; plan onaylı K-03b-0004 (S1-S6 = A); IMPLEMENTING: dilim 1-3 tamam (51e8cbe, f16bee9, 2813c25, cd730c2; lint 0, test 42/42 iki profil, egress 26/26); migrate servisi (K-03b-0005 B); HEAD de56c75: VERIFIED 11:34 (lint 0, test 70 + test-int 9 iki profil, temiz volume up 62 s + smoke, tek head 03b_0001, partition 2026_10/11, NOT_RUN yok); review r1 (R-03b-0002, state/reviews/03b-r1.md): DUZELT, MAJOR 3 (kwargs follow_redirects politikayı atlatıyor; origin değişiminde credential başlıkları taşınıyor; @audited flush/commit hatasında audit satırı yok); r1 düzeltmeleri 480c60e (227930c egress açık imza + cross-origin credential düşürme, 480c60e @audited tam transaction; kırmızı koşuldu); VERIFIED 12:04 (lint 0, 89 + 12 iki profil, temiz volume up 123 s + smoke, tek head); review r2 (R-03b-0004, state/reviews/03b-r2.md): DUZELT, MAJOR 1 (httpx2 cookie jar Set-Cookie'yi saklayıp cross-origin redirect'te yeniden ekliyor; r1 MAJOR-1/3 kapandı); r2 düzeltmesi 8b83a85 (istemci cookie saklamaz, ham jar; 5 kırmızı test; lint 0, test 95/95 iki profil); VERIFIED 12:22; r3 ONAY (R-03b-0006, state/reviews/03b-r3.md); main'e --no-ff merge 2804d03 2026-10-28 12:29, smoke + lint passed, tek head 03b_0001 |
| 08-lite | CLAIMED | test | feat/08-lite-guardrails | .worktrees/feat/08-lite-guardrails | backend/ffcore/guardrails/**, api/guardrails.py, models/guardrails.py, alembic 08, openapi/08.yaml, docs/guardrail.md, tests | 2026-10-28 | | 03a, 03b, 13a MERGED; GOREV K-08lite-0001; FOLLOWUP-33 burada; yeni test oturumu (ffcore-test-08-lite) bekleniyor |
| 10a | MERGED | C | feat/10a-console-skeleton (silindi) | (kaldırıldı 09:36) | frontend/** (iskelet, (console)/{auth,projects,providers,models}, mocks/), docs/onyuz.md | 2026-10-28 | | 00 MERGED; GOREV K-10a-0001; plan onaylı K-10a-0002; HEAD 7f3f0c7: VERIFIED 09:20 (lint/typecheck/Vitest 19, Playwright 36 + 1 fixme, axe 7 ekran × 2 tema 0 ihlal, 14 PNG; sahte API, dilim 5 yok); sapmalar kabul K-10a-0004 (msw/TanStack 10a-bağlama'ya, Kullanım=admin DRIFT-41); r1 ONAY (R-10a-0002, state/reviews/10a-r1.md, MINOR-1 → FOLLOWUP-44); main'e --no-ff merge 891cf3a 2026-10-28 09:33, smoke+lint passed |
| 10a-bağlama | CLAIMED | C | feat/10a-binding | .worktrees/feat/10a-binding | frontend/** (mocks/, lib/api, lib/session.ts, lib/access.ts, screen/nav-user/login-form, tests/e2e), docs/onyuz.md, Makefile `e2e` | 2026-10-28 | | 03a MERGED (OpenAPI `backend/openapi/03a.yaml` @ 591aac3); GOREV K-10ab-0001; yeni isci-c oturumu bekleniyor |
| 01 | CLAIMED | B | feat/01-litellm-gateway | .worktrees/feat/01-litellm-gateway | services/{litellm_client,litellm_reconcile,seed_models}.py, core/config ekleri, deploy/litellm/**, deploy/seed/models.*.yaml, Makefile seed/render hedefleri, docs/gateway.md, tests | 2026-10-28 | | 00, 03a MERGED; GOREV K-01-0001; FOLLOWUP-56; yeni isci-b oturumu bekleniyor |
| 02 | — | B | | | core/tracing, Langfuse compose | | | 00, 01; dağılım değişikliği 2026-10-28: B |
| 04a | — | A | | | knowledge/ (+ KnowledgeStore bağdaştırıcısı, paycoreLLM rag/ingest sarılır) | | | 00i, 03a, 01, 13a |
| 05a | — | B | | | services/mcp_*, services/mcp-sql, mcp-search | | | 03a, 03b, 04a, 08 |
| 06a | — | A | | | runtime/, api/runs* | | | 03a, 03b, 01, 02, 04a, 05a, 08 |
| 07 | — | B | | | api/approvals* | | | 06a, 03b |
| 10b-poc | — | C | | | (console)/{knowledge,tools,agents,runs,approvals,status}, frontend/mocks/ | | | 10a-bağlama sonrası sahte API ile (openapi-04-07.yaml); bağımlılık beklemez |
| 10b-bağlama | — | C | | | aynı; msw kapalı, gerçek backend | | | 04a, 05a, 06a, 07 MERGED sonrası küçük PR; 13b bunu bekler |
| 13b | — | A + test | | | A: tests/e2e (negative hariç), Makefile, docs/demo.md; test: tests/e2e/negative, data/samples | | | ayrı branch/worktree ve alt-claim; PoC paketleri, 10b-bağlama, 00i S1 tabanı; **M3 / PoC kapısı** |

## PoC sonrası

| Paket | Durum | Bağımlılık / not |
|---|---|---|
| 03c | — | 03b; 06b ile birlikte (API key, kota, usage, retention, uyarılar, bildirim) |
| 11 | — | 06a, 07 (PoC'de Open WebUI) |
| 08 tam | — | 08-lite; Türkçe NER, injection, akış tamponlayıcı, PRSIM ingest guard'ı |
| 06b | — | 06a, 03c (facade, dış agent, manifest) |
| 04b | — | 04a (DuckDB → Postgres göçü DEBT-1, migrate-vectors) |
| 05b | — | 05a |
| 09 | — | 06a, 02, 04a, 13a (Langfuse datasets) |
| 10c | — | 03c, 05b, 09 |
| 12 | — | hepsi |
| 14 | — | 03, 04a, 06a, 08, 11, 13a |
| 17 | — | 03, 11 (brief M6 sonrası yazılır) |
| 16 | — | 03, 04a, 05a |
| 15 | — | 06a, 07, 11; Slack/Teams: 17 |

## Kapılar

| Kapı | Kanıt (tarih, kim, `make smoke`, Alembic head, tutarlılık denetimi) |
|---|---|
| Dalga 1 (00, 00i, 13a) | |
| Dalga 2 (03a, 03b, 08, 10a) | |
| Dalga 3 (01, 02, 04a) | |
| Dalga 4 (05a, 06a) | |
| M3 / PoC (07, 10b-poc, 13b; PayCore sunucusu, cpu) | |
| PoC sonrası dalgalar | |
