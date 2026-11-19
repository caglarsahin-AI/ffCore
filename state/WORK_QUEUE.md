# İş Kuyruğu (tek sahiplik kaynağı)

Durumlar: READY · CLAIMED · PLANNED · IMPLEMENTING · IMPLEMENTED · VERIFIED · REVIEWED · MERGED · BLOCKED (EXECUTION_HANDBOOK 1). Kapı kuralı: paket **doğrudan bağımlılıkları MERGED olunca** READY (E). **Yalnızca koordinatör yazar**; işçi durum değişikliğini kendi `state/kanal/<rol>.md` dosyasına `DURUM` mesajıyla bildirir (MULTI_AGENT_PROTOCOL).

## PoC (M1-M3, PayCore LLM'de `airgap`) · aktif dalga: 1

Bu tablo yalnız durumdur (bağlam bütçesi kararı, 16 Kasım 2026). Tam satırlar (worktree, touch-zone, tarih, kabul/kapı özetleri, karar işaretçileri) `state/arsiv/work-queue-dalga1.md` dosyasındadır; yeni paket satırı bu biçimde açılır, ayrıntı PR notu ve kanal mesajlarındadır.

| Paket | Durum | İşçi | Branch | Son mesaj ID |
|---|---|---|---|---|
| 00 | MERGED | A | feat/00-repo-skeleton (silindi) | K-00-0004 |
| 00i | MERGED | B | paycoreLLM: feat/00i-ffcore-integration (baz master 81e3609); ffcore: feat/00i-docs | R-00i-0007 |
| 13a | MERGED | test | feat/13a-sample-data (silindi) | R-13a-0004 |
| 03a | MERGED | A | feat/03a-identity-catalog (silindi) | R-03a-0005 |
| 03b | MERGED | A | feat/03b-audit-egress (silindi) | R-03b-0006 |
| 08-lite | MERGED | test | feat/08-lite-guardrails (silindi) | R-08lite-0009 |
| 10a | MERGED | C | feat/10a-console-skeleton (silindi) | R-10a-0002 |
| 10a-bağlama | MERGED | C | feat/10a-binding (silindi) | R-10ab-0006 |
| 10a-formlar | MERGED | C | feat/10a-forms (silindi) | R-10af-0008 |
| 01 | MERGED | B | feat/01-litellm-gateway (silindi) | R-01-0012 |
| 02 | MERGED | B | feat/02-langfuse-trace (silindi) | R-02-0016 |
| 04a | MERGED | A | feat/04a-knowledge-core (silindi) | A-04a-0036 |
| 05a | MERGED | B | feat/05a-tools-mcp (silindi) | R-05a-0008 |
| 06a | MERGED | A | feat/06a-agent-runtime (silindi) | R-06a-0011 |
| 07 | MERGED | B | feat/07-approvals (silindi) | R-07-0007 |
| 10b-poc-1 | MERGED | C | feat/10b-poc-1 (silindi) | R-10bp1-0008 |
| 10-marka | MERGED | C | feat/10-brand-icon (silindi) | R-MRK-0002 |
| 10b-poc-2 | MERGED | C | feat/10b-poc-2 (silindi) | K-10bp2-0011 |
| 18-hazirlik | MERGED | test | feat/18-scenario-data (silindi) | R-18-0004 |
| 18-ticket-desk | MERGED | test | feat/18-ticket-desk (silindi) | K-SEN-0013 |
| 18-cost-timing | MERGED | test | fix/18-cost-timing (silindi) | K-SEN-0015 |
| 08-default-egress-enforce | MERGED | test | fix/08-default-egress-enforce (silindi) | T-18-0044 |
| 08-builtin-version-test | MERGED | test | fix/08-builtin-version-test (silindi) | R-08T-0001 |
| fake-llm-tool-mode | MERGED | test | fix/fake-llm-tool-mode (silindi) | R-FL-0001 |
| fix/07-followups | MERGED | B | fix/07-followups (silindi) | R-07F-0002 |
| fix/04a-06a-followups | MERGED | A | fix/04a-06a-followups (silindi) | R-AF-0007 |
| fix/05a-tools-read-analyst | MERGED | B | fix/05a-tools-read-analyst (silindi) | R-05ATR-0001 |
| fix/03a-nonmember-404 | MERGED | A | fix/03a-nonmember-404 (silindi) | R-03ANM-0002 |
| fix/04a-worker-ready | MERGED | A | fix/04a-worker-ready (silindi) | R-04AWR-0001 |
| 18-f2-stage3 | MERGED | test | feat/18-f2-stage3 (silindi) | R-SEN-0007 |
| 18-e2e-iskelet | MERGED | test | feat/18-scenarios-e2e | R-SEN-0006 |
| 13b | MERGED (A + test) | A + test | feat/13b-e2e-eval (silindi), feat/13b-test (silindi) | R-13BA-0002 |
| 13b-kosu | MERGED | test | feat/13bk-ttl-negative | R-13BK-0002 |
| fix/06a-checkpoint-sources | MERGED | A | fix/06a-checkpoint-sources | R-116-0005 |
| fix/07-test-hooks-flag | MERGED | B | fix/07-test-hooks-flag | R-114-0002 |
| 03c | MERGED (03c-1 + 03c-2) | B (yeni oturum) | feat/03c-governance | R-03C2-0006 |
| 06b | MERGED | A (yeni oturum) | feat/06b-facade | K-06b2-0001 |
| fix/57-alembic-merge | MERGED | A (isci-a-06b oturumu) | fix/57-alembic-merge | K-57-0003 |
| 19 M3-sunucu | MERGED | B (yeni oturum) | feat/m3-server-package (+ paycoreLLM kardeş worktree işçi önerisiyle) | R-19-0004 |
| fix/04a-gate2-headings | MERGED | B (yeni oturum, 2 Kasım 15:46) | fix/04a-gate2-headings | R-137-0002 |
| 06b-2 | MERGED | A (yeni oturum, 2 Kasım 18:03) | feat/06b-2-external-agent | R-06b2-0006 |
| 18-kosu-2 | VERIFIED (test koşusu tamam) | test (yeni oturum, 3 Kasım 08:50) | (kod yok; test rolü) | T-18k2-0004 |
| 08-tam-1a | MERGED | A (yeni oturum, 3 Kasım 09:00) | feat/08-tam-1-ner (1a: C17+106+107+147, modelsiz) | K-08T1-0037 |
| 08-tam-1b | MERGED | A (yeni oturum ROL=isci-a PAKET=08-tam-1b, 4 Kasım 14:06, lease ffcore-isci-a-08-tam-1b, Opus 5.5) | feat/08-tam-1b-ner | K-08T1B-0026 |
| 09 | DONE (09-1 + 09-2 MERGED) | B (yeni taze oturum, 4 Kasım 19:02, lease ffcore-isci-b-09, Opus 5.5) | feat/09-evaluation | R-09-0042 |
| 10c-1 | DONE (MERGED) | isci-c (ffcore-isci-c-10c1, 2026-11-16) | feat/10c-1-eval-ui | R-10C1-0007 |
| fix/ajan-hooklari | DONE | isci-a (ffcore-isci-a-hook, 2026-11-16) | fix/ajan-hooklari | A-HOOK-0002; A-HOOK-0007; r1 R-HOOK-0002 DEGISIKLIK (M2: kapi-tee-kapsami, kayit-secret-sizintisi; m2) → K-HOOK-0006; A-HOOK-0008 49b4343; r2 R-HOOK-0004 ONAY B0 M0 m3 N5 → K-HOOK-0010; A-HOOK-0009 7a1195a; r3 R-HOOK-0006 ONAY B0 M0 m0 N3; MERGED 2d44b0c (kapı gate-hook-20261116.log 142 passed, ruff temiz) |
| fix/ajan-hooklari-2 | DONE | B (yeni oturum ROL=isci-b PAKET=fix/ajan-hooklari-2, lease ffcore-isci-b-hook2) | fix/ajan-hooklari-2 (baz main e2ce5e7) | K-HOOK2-0001; B-HOOK2-0001 ACK (hook kimliği eşleşti), B-HOOK2-0002 PLANNED; B-HOOK2-0006 571ae6f (319 test); R-HOOK2-0002 ONAY B0 M0 m5 N6 → K-HOOK2-0007; B-HOOK2-0008 d5e9c11 (355 test); R-HOOK2-0004 ONAY B0 M0 m0 N2; MERGED 4d09310 (kapı gate-hook2-20261117.log 355 passed, ruff temiz) |
| fix/10b-sse-bekci | DONE | C (yeni oturum ROL=isci-c PAKET=fix/10b-sse-bekci, lease ffcore-isci-c-sse) | fix/10b-sse-bekci (baz main a46f147) | K-SSE-0001; C-SSE-0001 ACK, C-SSE-0002 PLANNED; C-SSE-0005 5894610 (Vitest 208); R-SSE-0004 DEGISIKLIK B0 M1 m0 N5 (yoklama-hatada-sessiz-durma) → K-SSE-0005; C-SSE-0009 8c01f04 (Vitest 211); R-SSE-0008 ONAY B0 M0 m0 N2; MERGED 4216718 (önyüz kapısı gate-sse-20261117.log: lint/typecheck/check:api 0, Vitest 211) |
| 10c-2 | DONE | C (yeni oturum ROL=isci-c PAKET=10c-2, lease ffcore-isci-c-10c2) | feat/10c-2-governance-ui (baz main e56bcfa) | K-10C2-0001; C-10C2-0001 ACK, C-10C2-0002 PLANNED; C-10C2-0006 (D1-D9 commit'li); C-10C2-0008 5c27543 (Vitest 250, backend 1813×2, e2e 178); R-10C2-0004 ONAY B0 M0 m0 N3 → K-10C2-0006; C-10C2-0014 877cc34 (rebase 2afb68d; backend 1918×2, test-int 74, Vitest 250); R-10C2-0008 ONAY B0 M0 m1 N2; MERGED b93cd96 (kapı gate-10c2-20261119.log: imaj build, lint, test 1918×2, test-int 1010, smoke, önyüz Vitest 250; e2e r1 kanıtı) |
| 04b | DUZELT r1 (04b-2 ONAY m2; r2 readyz/409 dilimi) | B (yeni oturum ROL=isci-b PAKET=04b, lease ffcore-isci-b-04b) | feat/04b-knowledge-ext (baz main ec89bb1) | K-04B-0001; B-04B-0001 ACK, B-04B-0002 PLANNED; B-04B-0007 5cc18bf (test 1929×2, hedefli test-int 102); R-04B-0003 ONAY B0 M0 m2 N3 → K-04B-0007; B-04B-0012 d30d165 (rebase 0a92084; test 1937×2, test-int 77); R-04B-0006 DEGISIKLIK B0 M2 m0 N1 → K-04B-0011; B-04B-0018 ca4c2f9 (test 1937×2, test-int 89); R-04B-0009 ONAY B0 M0 m0 N2; MERGED ef2ee83 (kapı gate-04b1-20261119.log: imaj build, lint, test 1937×2, test-int 1056, smoke, önyüz Vitest 279); B-04B-0021 PLANNED → K-04B-0021 PLAN-ONAY; B-04B-0027 5c40558 (16 commit, 47 dosya; test 1952×2, test-int 1074); R-04B-0012 ONAY B0 M0 m2 N3 → K-04B-0026 |
| 10c-3 | DONE | C (yeni oturum ROL=isci-c PAKET=10c-3, lease ffcore-isci-c-10c3) | feat/10c-3-mcp-ui (baz main ec89bb1) | K-10C3-0001; C-10C3-0001 ACK, C-10C3-0002 PLANNED; C-10C3-0006 b692ad6 (Vitest 279, backend 1925×2, e2e 188/189); R-10C3-0002 ONAY B0 M0 m1 N2 → K-10C3-0006; C-10C3-0007 2b79c34 (docs + en/tr; Vitest 279); R-10C3-0004 ONAY B0 M0 m0 N0; MERGED 0a92084 (kapı gate-10c3-20261119.log: imaj build, lint, test 1925×2, test-int 1012, smoke, önyüz Vitest 279; e2e r1 kanıtı) |
| 05b | DONE | B (yeni oturum ROL=isci-b PAKET=05b, lease ffcore-isci-b-05b) | feat/05b-openapi-mcp (baz main e56bcfa) | K-05B-0001; B-05B-0001 ACK, B-05B-0002 PLANNED; B-05B-0005 (lint 0, test 1851×2); B-05B-0008 749e37e (test 1851×2, test-int 995); R-05B-0004 DEGISIKLIK B0 M1 m2 N6 (upstream-origin-kacagi) → K-05B-0008; B-05B-0012 acc149b (test 1882×2, test-int 107); R-05B-0008 ONAY B0 M0 m1 N2 → K-05B-0012; B-05B-0016 5b00a63 (test 1903×2, test-int 42); R-05B-0011 ONAY B0 M0 m0 N2; MERGED 2e75ba2 (kapı gate-05b-20261118.log: lint, test 1903×2, test-int 1004, smoke yeşil kaynaktan; imaj build 19 Kasım 12:43 doğrulandı, ENV-196 kapandı) |
| fix/19r2-dis-inceleme | MERGED | B (yeni oturum, 4 Kasım 14:02, lease ffcore-isci-b-19r2) | paycoreLLM fix/19r2-dis-inceleme (silindi) | K-19R2-0010 |
| fix/19r3-env-tests | MERGED | B (yeni oturum ROL=isci-b PAKET=fix/19r3; kanal state/kanal/isci-d.md, lease ffcore-isci-d-19r3) | paycoreLLM fix/19r3-env-tests (silindi, HANDOFF sonrası) | K-19R3-0012 |
| 08-tam-1c-olcum | DONE (1c-a + 1c-b MERGED) | A (yeni oturum ROL=isci-a PAKET=08-tam-1c-olcum) | feat/08-tam-1c-olcum (main 63ffb16+) | A-08T1C-0025 |
| fix/19-dis-inceleme | MERGED | B (yeni oturum, 3 Kasım 09:27) | paycoreLLM feat/19-dis-inceleme (silindi) | R-19R-0004 |

## PoC sonrası

| Paket | Durum | Bağımlılık / not |
|---|---|---|
| 03c | CLAIMED (üstteki PoC sonrası satırı) | 03b; 06b ile birlikte (API key, kota, usage, retention, uyarılar, bildirim) |
| 11 | — | 06a, 07 (PoC'de Open WebUI) |
| 08 tam | — | 08-lite; Türkçe NER, injection, akış tamponlayıcı, PRSIM ingest guard'ı |
| 06b | — | 06a, 03c (facade, dış agent, manifest) |
| fix/06a-egress-all-messages | MERGED | A (yeni oturum) | fix/06a-egress-all-messages (silindi) | (kaldırıldı 2026-11-02 11:40) | backend/ffcore/runtime/graph.py (llm_call sınırı), guardrails çağrı yeri, tests/ | 2026-11-01 | | BLOCKERS 134; GOREV K-134-0001; 06b merge'ünden ÖNCE; danışman görüşü; PR-HAZIR (kısmi) A-134-0002 b9eefe3; r1 kod turu R-134-0002 KOD-ONAY (ön), MINOR 3 (tool_calls.arguments egress dışı; guard_in çift denetim; str olmayan content sessiz, TextTooLong generic) → DUZELT K-134-0003; nihai ONAY yığınlı turda ((e)/(f), test-int iki profil); DUZELT uygulandı 3d03bc9; PR-HAZIR A-134-0004 10e86bf0d54215e2783ed304e6af712798666858 (baz 07dc421, 3 commit, 6 dosya +469/-11, main ile çakışma yok, koordinatör doğruladı); kanıt tam tee state/evidence/134-*-20261102.log: make test 745/745 iki profil, test-int 682 + 4 atlandı, sağlayıcı isteği testi (fake-llm /_requests) kırmızı→yeşil; REVIEW-ISTEK r2 K-134-0006; r2 ONAY R-134-0004 (MINOR-4 → FOLLOWUP-139); merge d274bc9 (2 Kasım 11:19); **tam kapı yeşil** (state/evidence/gate-134-20261102.log, tam tee): build, compose config, up, lint 0, alembic heads tek (57_0002), make test 745/745 iki profil, test-samples, test-int 682 + 4 atlandı, smoke passed, önyüz lint/tsc/check:api 0, down -v; BLOCKERS 134 kapandı |
| 06b-2 | — | 06b merge (dış agent: external_config, SafeOutboundClient, SSRF matrisi; KARARLAR "06b S5 ... 06b-2") |
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
| Dalga 1 - 5 (geriye dönük) | Main kapısı logları `state/evidence/gate-*.log`; DOC-19 tutarlılık denetimi dalga başına koşulmadı (DRIFT-187); insan onayı alınmadı. |
| Dalga 16 Kasım (09-1/09-2, 08-tam-1c-a/1c-b, 10c-1; main 6157752) | Rapor `state/dalga/dalga-16kasim-rapor.md` (16 Kasım 2026, koordinatör); **kullanıcı onayladı 2026-11-16** (koordinatör oturumunda "Onaylıyorum"); geri çevrilen madde yok |
| Dalga 6 (PoC sonrası, kapanış) | 03c, 06b/06b-2, 09, 08 tam 1a-1c, 10c-1, fix/ajan-hooklari, fix/ajan-hooklari-2, fix/10b-sse-bekci | main 4216718; kapı logları raporda | Rapor `state/dalga/dalga-17kasim-rapor.md` (17 Kasım 2026, koordinatör); **kullanıcı onayladı 2026-11-17** (koordinatör oturumunda "Onaylıyorum, DECISION-193 A, oturumları sen aç"); geri çevrilen madde yok; dalga 6b READY (10c-2 isci-c, 05b isci-b, 04b sonraki slot) |
| PoC sonrası sonraki dalgalar | |

## Kullanım senaryoları (plan/18-kullanim-senaryolari.md; koordinatör takip)

| Senaryo | Evre | Aşama | Durum | Kanıt |
|---|---|---|---|---|
| F1 doküman asistanı | PoC | 06a sonrası | bekliyor | 13b make eval |
| F2 talep triyajı + onaylı taslak | PoC | 07 sonrası | veri main'de (5a5200e); ticket-desk 05a sonrası | 13b e2e |
| F3 salt okunur veri sorgusu | PoC | 06a sonrası | veri main'de (sql-20 + hidden_write 7) | 13b make eval + olumsuz |
| F4 yönetilen LLM geçidi | PoC (kota 03c) | 06a sonrası; kota 03c | bekliyor | 13b e2e |
| F5 kalite izleme | PoC sonrası | 09 | planlı | 09 |
| F6 uzun belge özeti/karşılaştırma | PoC sonrası | 04b | planlı | 04b |
| F7 hafıza | PoC sonrası | 14 | planlı | 14 |
| F8 kanal asistanı | PoC sonrası | 15/17 | planlı | 15 |
| F9 uzman değerlendirme kuyruğu | PoC-lite | 06a + 10b-poc-2 | 06a'ya uç eklendi (K-06a-0005; 80de141'de yazıldı) | 13b e2e |
| F10 proje izolasyonu + denetim izi | PoC | 06a sonrası | veri main'de (projects.json) | 13b e2e |
| F11 zehirli belge / istem enjeksiyonu | PoC-lite (tam 08) | 06a sonrası | veri main'de (poison) | 13b e2e |
| F12 kesinti davranışı | PoC | 06a sonrası | bekliyor | 13b e2e |
| F13 belge güncelliği | PoC sonrası (04b); prompt kuralı 06a | 06a / 04b | veri main'de (versions/) | 13b e2e + 04b |
