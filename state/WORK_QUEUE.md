# İş Kuyruğu (tek sahiplik kaynağı)

Durumlar: READY · CLAIMED · PLANNED · IMPLEMENTING · IMPLEMENTED · VERIFIED · REVIEWED · MERGED · BLOCKED (EXECUTION_HANDBOOK 1). Kapı kuralı: paket **doğrudan bağımlılıkları MERGED olunca** READY (E). **Yalnızca koordinatör yazar**; işçi durum değişikliğini kendi `state/kanal/<rol>.md` dosyasına `DURUM` mesajıyla bildirir (MULTI_AGENT_PROTOCOL).

## PoC (M1-M3, PayCore LLM'de `airgap`) · aktif dalga: 1

| Paket | Durum | İşçi | Branch | Worktree | Touch-zone | Başlangıç | PR | Bağımlılık / not |
|---|---|---|---|---|---|---|---|---|
| 00 | READY | A | | | ffcore: kök, deploy/, Makefile | | | dalga 1 |
| 00i | — | B | | | **paycoreLLM deposu**: pyproject, CLAUDE.md, docs/paycore, compose*, api.py kimlik, rag/retrieve+pipeline to_thread | | | 00; 03a/01/04a bunu bekler |
| 13a | READY | test agent'ı | | | data/samples/ | | | dalga 1, 00'a paralel |
| 03a | — | A | | | models/{identity,catalog}, core/auth, core/secrets | | | 00, 00i |
| 03b | — | B | | | models/audit, core/audit, core/egress, OBO | | | 00 |
| 08-lite | — | B | | | guardrails/ | | | 03a merge sonrası |
| 10a | — | C | | | (console)/{auth,projects,providers,models}, frontend/mocks/ | | | 00 MERGED sonrası sahte API ile (openapi-03a.yaml, msw) |
| 10a-bağlama | — | C | | | aynı; msw kapalı, gerçek backend | | | 03a MERGED sonrası küçük PR (ilk gerçek ekran ≈ 9-10. iş günü) |
| 01 | — | A | | | services/litellm_*, deploy/litellm | | | 00, 03a |
| 02 | — | A | | | core/tracing, Langfuse compose | | | 00, 01 |
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
