# İş Kuyruğu (tek sahiplik kaynağı)

Durumlar: READY · CLAIMED · PLANNED · IMPLEMENTING · IMPLEMENTED · VERIFIED · REVIEWED · MERGED · BLOCKED (EXECUTION_HANDBOOK 1). Kapı kuralı: paket **doğrudan bağımlılıkları MERGED olunca** READY (E). **Yalnızca koordinatör yazar**; işçi durum değişikliğini kendi `state/kanal/<rol>.md` dosyasına `DURUM` mesajıyla bildirir (MULTI_AGENT_PROTOCOL).

## PoC (M1-M3, PayCore LLM'de `airgap`) · aktif dalga: 1

| Paket | Durum | İşçi | Branch | Worktree | Touch-zone | Başlangıç | PR | Bağımlılık / not |
|---|---|---|---|---|---|---|---|---|
| 00 | MERGED | A | feat/00-repo-skeleton (silindi) | (kaldırıldı 08:30) | kök, backend/ ve frontend/ iskelet, deploy/, Makefile, docs/gelistirme-ortami.md (data/samples hariç) | 2026-10-28 | | dalga 1; GOREV K-00-0001; plan state/pr/00.md onaylandı (K-00-0004); ENV-19/20/23 kapandı; cc4829a compose+tools; review r1 DUZELT → r2 ONAY (1f5fbc6, state/reviews/00-r2.md); main'e --no-ff merge bb634e4 2026-10-28 08:18, smoke passed |
| 00i | IMPLEMENTING | B | paycoreLLM: feat/00i-ffcore-integration (baz master 81e3609); ffcore: feat/00i-docs | paycoreLLM kardeş worktree C:\ai_paycore\paycoreLLM-00i (açıldı, 81e3609); ffcore .worktrees/feat/00i-docs | ... plan onaylı K-00i-0003 (K1-K4 = A); dilim 1-2 tamam (75371b3, 86b8d0d; 428 test geçti, 3 bazda da kalan); dilim 3 tamam 16aa1c9; touch-zone + tests/conftest.py, tests/test_api.py (K-00i-0004), warmup.py 1 satır (K-00i-0005); ENV-38 nexus ve ENV-43 offline önbellek kullanıcıda | **paycoreLLM deposu**: pyproject, CLAUDE.md, docs/paycore, compose*, api.py kimlik, rag/retrieve+pipeline to_thread; ffcore'da yalnızca docs/paycore-entegrasyon.md | | | 00; 03a/01/04a bunu bekler |
| 13a | MERGED | test | feat/13a-sample-data (silindi) | (kaldırıldı 09:36) | data/samples/** + Makefile `lint` hedefine tek satır (K-13a-0009) | 2026-10-28 | | dalga 1, 00'a paralel; HEAD 4c29817 (main 78c8412 üstüne rebase): VERIFIED 08:30 (tools lint/test 0, 13a testleri konteyner+host 18/18 + Postgres 3/3; DOCX create_system düzeltmesi); ruff B uygulandı d70f77a (çıktı bayt aynı, Makefile lint 2 satır); review r1 (R-13a-0002, state/reviews/13a-r1.md): DUZELT, MAJOR 2 (veri-soru-cevap prompt get_schema+run_sql vs max_tool_calls 1; q14 must_contain), MINOR 1 (Postgres fixture rm -f); r1 düzeltmeleri e663597 (şema prompt'ta, yalnız run_sql, ask_user false; q14; pg fixture benzersiz ad); VERIFIED 09:22; r2 ONAY (R-13a-0004, state/reviews/13a-r2.md); main'e --no-ff merge c8024fe 2026-10-28 09:33, smoke+lint passed |
| 03a | — | A | | | models/{identity,catalog}, core/auth, core/secrets | | | 00, 00i |
| 03b | CLAIMED | A | feat/03b-audit-egress | .worktrees/feat/03b-audit-egress | backend/ffcore/{models/audit.py, core/audit.py, core/egress.py, core/auth.py (resolve_actor OBO+servis yolu), core/db.py, core/config ek}, alembic 03b etiketi, tests, docs/api.md | 2026-10-28 | | 00 MERGED; dağılım değişikliği 2026-10-28: A; GOREV K-03b-0001; yeni isci-a oturumu gerekli (A-00-0020) |
| 08-lite | — | test | | | guardrails/ | | | 03a merge sonrası; dağılım değişikliği 2026-10-28: test (yeni oturum ffcore-test-08-lite) |
| 10a | MERGED | C | feat/10a-console-skeleton (silindi) | (kaldırıldı 09:36) | frontend/** (iskelet, (console)/{auth,projects,providers,models}, mocks/), docs/onyuz.md | 2026-10-28 | | 00 MERGED; GOREV K-10a-0001; plan onaylı K-10a-0002; HEAD 7f3f0c7: VERIFIED 09:20 (lint/typecheck/Vitest 19, Playwright 36 + 1 fixme, axe 7 ekran × 2 tema 0 ihlal, 14 PNG; sahte API, dilim 5 yok); sapmalar kabul K-10a-0004 (msw/TanStack 10a-bağlama'ya, Kullanım=admin DRIFT-41); r1 ONAY (R-10a-0002, state/reviews/10a-r1.md, MINOR-1 → FOLLOWUP-44); main'e --no-ff merge 891cf3a 2026-10-28 09:33, smoke+lint passed |
| 10a-bağlama | — | C | | | aynı; msw kapalı, gerçek backend | | | 03a MERGED sonrası küçük PR (ilk gerçek ekran ≈ 9-10. iş günü) |
| 01 | — | B | | | services/litellm_*, deploy/litellm | | | 00, 03a; dağılım değişikliği 2026-10-28: B |
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
