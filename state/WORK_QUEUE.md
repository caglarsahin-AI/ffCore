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
| 04b | DONE | B (yeni oturum ROL=isci-b PAKET=04b, lease ffcore-isci-b-04b) | feat/04b-knowledge-ext (baz main ec89bb1) | K-04B-0001; B-04B-0001 ACK, B-04B-0002 PLANNED; B-04B-0007 5cc18bf (test 1929×2, hedefli test-int 102); R-04B-0003 ONAY B0 M0 m2 N3 → K-04B-0007; B-04B-0012 d30d165 (rebase 0a92084; test 1937×2, test-int 77); R-04B-0006 DEGISIKLIK B0 M2 m0 N1 → K-04B-0011; B-04B-0018 ca4c2f9 (test 1937×2, test-int 89); R-04B-0009 ONAY B0 M0 m0 N2; MERGED ef2ee83 (kapı gate-04b1-20261119.log: imaj build, lint, test 1937×2, test-int 1056, smoke, önyüz Vitest 279); B-04B-0021 PLANNED → K-04B-0021 PLAN-ONAY; B-04B-0027 5c40558 (16 commit, 47 dosya; test 1952×2, test-int 1074); R-04B-0012 ONAY B0 M0 m2 N3 → K-04B-0026; B-04B-0031 7ede8c1 (test 1959×2); R-04B-0015 ONAY B0 M0 m0 N0; MERGED 04b-1 ef2ee83 + 04b-2 d096bb3 (kapı gate-04b2-20261119.log: imaj build, lint, test 1959×2, test-int 1076, smoke, önyüz Vitest 279); B-04B-0034 HANDOFF, B-04B-0035 RETIRED; kanal arşivi 04b (35+34+16) |
| 12 | DONE | A (yeni oturum ROL=isci-a PAKET=12, lease ffcore-isci-a-12) | feat/12-kurulum (baz main a60228d) | K-12-0001; A-12-0001 ACK, A-12-0002 PLANNED → K-12-0002 PLAN-ONAY; A-12-0009 fc688b0 (7 commit, 22 dosya; test 2006×2, test-int 1076, egress/TLS 16); R-12-0003 ONAY B0 M0 m1 N5 → K-12-0008; A-12-0015 12e4d54 (test 2018×2, egress/TLS 22); A-12-0016 PLANNED → K-12-0013 PLAN-ONAY; R-12-0006 ONAY B0 M0 m0 N0; 12-1 MERGED a7c861f (kapı gate-121-20261120.log: hooks host 347, config egress+tls, lint, test 2073×2, test-int 1121, smoke, Vitest 279); A-12-0025 080facf (23 commit, 31 dosya; test 2106×2, test-int tam 1138 ffcore_app, hedefli 85, yedek provası); R-12-0009 DEGISIKLIK B0 M2 m0 N3 → K-12-0022; A-12-0029 5ff32ed (test 2117×2, hedefli 37); R-12-0012 ONAY B0 M0 m0 N2; MERGED 12-1 a7c861f + 12-2 9c65d1f (kapı gate-122-20261120.log: hooks host 347, config taban/egress+tls/vllm, lint, test 2117×2, test-int 1143 ffcore_app, smoke, Vitest 279); A-12-0030 HANDOFF, A-12-0031 RETIRED; kanal arşivi 12 |
| 11 | DONE (11-1 15f1da9 + d3f96ed; 11-2 6590719; kapı gate-112-20261121 + e2e-rerun yeşil) | C (yeni oturum ROL=isci-c PAKET=11, lease ffcore-isci-c-11) | feat/11-chat (baz main 029934a) | K-11-0001; C-11-0001 ACK, C-11-0002 PLANNED → K-11-0002 PLAN-ONAY; C-11-0007 d31574b (11 commit, 52 dosya; test 2120×2, test-int 18, Vitest 296, e2e 11 8/8 + tam 186); C-11-0008 PLANNED → K-11-0005 PLAN-ONAY; R-11-0003 ONAY B0 M0 m1 N3 → K-11-0006; C-11-0013 f9d213f (test_11_4 ×4 16/16); R-11-0006 ONAY B0 M0 m0 N0; gate-111-20261120.log → K-11-0012; C-11-0018 43f5ed8 (main 2 failed → dal 27, make test 2159); R-11-0007 ONAY B0 M0 m0 N0; gate-111p-20261121b.log yeşil → K-11-0018 MERGED; C-11-0024 b957c66 (8 commit, 43 dosya; test-int 1188/42, test 2159×2, Vitest 323, e2e 14+29); R-11-0010 ONAY B0 M0 m2 N2; C-11-0027 2085aa4 (3 commit, 8 dosya; kırmızı 3 → hedefli 154, make test 2159, Vitest 323); R-11-0011 ONAY B0 M0 m0 N0 → merge 6590719; gate-112 yeşil (test-int 1190, e2e 1+203) → K-11-0030 DONE |
| 14 | DONE (14-1 5c0354a + 14-2 782812e; kapı gate-141 + gate-142 yeşil) | C (yeni oturum ROL=isci-c PAKET=14, lease ffcore-isci-c-14) | feat/14-hafiza (baz main d6d2029) | K-14-0001; C-14-0002 PLANNED → K-14-0003 PLAN-ONAY (S1-S8 A); C-14-0006 → K-14-0006 CONTRACTS C3 istisnası; C-14-0007 tam test-int tam yığın 1240/42/0; C-14-0008 PR-HAZIR bb5ad0d (4 commit, 43 dosya +6526/-11) → K-14-0007 VERIFIED, K-14-0008 REVIEW-ISTEK; R-14-0002 DEGISIKLIK B0 M2 m2 N5 → K-14-0009 DUZELT r2 (rebase triage-2 merge sonrası); C-14-0015 PR-HAZIR r2 90aa8c1 (test 2202×2, test-int 1260/42/0) → K-14-0014 VERIFIED, K-14-0015 REVIEW-ISTEK r2; R-14-0006 ONAY B0 M0 m0 N2 → merge 5c0354a, K-14-0016 MERGED + kapı; K-14-0017 14-2 PLANNED isteği; gate-141 yeşil (test 2202×2, test-int 1260/42, e2e 1+203) → K-GEN-0046; C-14-0017 PLANNED → K-14-0020 PLAN-ONAY (S1-S9 A); K-14-0022 S9 analyst; C-14-0024 PR-HAZIR 14-2 8f07072 (5 commit, 47 dosya; e2e 8/8, test 2202×2, test-int 1262/42/0) → K-14-0024 VERIFIED, K-14-0025 REVIEW-ISTEK; R-14-0011 ONAY B0 M0 m2 N5 → K-14-0026 DUZELT r2 (MINOR-1 fail-loud, MINOR-2 docs; FOLLOWUP-224/225); C-14-0026 PR-HAZIR r2 bd37a16 (Vitest 349) → K-14-0028 VERIFIED, K-14-0029 REVIEW-ISTEK r2; R-14-0014 ONAY B0 M0 m0 N0 → merge 782812e, K-14-0030 MERGED + kapı; gate-142 yeşil (test-int 1262, Vitest 349, e2e 1+203+8 skip) → K-GEN-0050 14 DONE, K-14-0032 HANDOFF-ISTEK |
| 16 | 16-1 DONE (558178a); 16-2 MERGE c626a25, KAPI BEKLEMEDE (17-2 kısa koşusu bitince gate-162); 16-3 kod kapı sonrası | B (yeni oturum ROL=isci-b PAKET=16, lease ffcore-isci-b-16) | feat/16-kaynaklar (baz main 5c0354a) | K-16-0001; B-16-0002 PLANNED → K-16-0002 PLAN-ONAY (S1-S5 A); K-16-0003 kullanıcı sync-worker onayı; B-16-0004 IMPLEMENTED (test 2261×2) → K-16-0004 (RESERVED_HOSTS, C3); B-16-0005/0007 hedefli 37/37 → K-16-0006 tam test-int başla; B-16-0009 OOM (K-GEN-0048); B-16-0012 PR-HAZIR 044c148 (tam test-int 1310/42/1 → parity test düzeltmesi, 26/26) → K-16-0007 VERIFIED, K-16-0008 REVIEW-ISTEK; B-16-0013 16-2 PLANNED → K-16-0009 PLAN-ONAY; R-16-0003 DEGISIKLIK B0 M1 m2 N8 → K-16-0011 DUZELT r2 (MAJOR-1 A, MINOR-1/2, docs; FOLLOWUP-226); B-16-0020 PR-HAZIR r2 d914b47 (test 2265×2, hedefli 272/272) → K-16-0014 VERIFIED, K-16-0015 REVIEW-ISTEK r2; R-16-0006 DEGISIKLIK B0 M1 m0 N1 → K-16-0016 DUZELT r3 (test); B-16-0024 PR-HAZIR r3 a206aab → K-16-0018 VERIFIED, K-16-0019 REVIEW-ISTEK r3; R-16-0009 ONAY B0 M0 m0 N1 → merge 558178a, K-16-0020 MERGED + kapı; gate-161 yeşil (test-int 1320, e2e 1+211) → K-GEN-0052 16-1 DONE, 16-2 kod başla |
| 17 | 17-1 DONE (874e24a, gate-171c yeşil); 17-2 KOD (feat/17-2-oidc, PLAN-ONAY K-17-0006) | C (yeni oturum ROL=isci-c PAKET=17, lease ffcore-isci-c-17) | feat/17-kimlik (baz main 558178a, rebase) | K-17-0001; C-17-0002 PLANNED → K-17-0002 PLAN-ONAY (S1-S7 A); C-17-0007 SORU → K-17-0003 slot + zone; C-17-0010 PR-HAZIR 17-1 b89fc49 (10 commit, 39 dosya; test 2287×2, tam test-int 1353/42 + 4 bilerek değişen → 23 yeniden) → K-17-0004 VERIFIED, K-17-0005 REVIEW-ISTEK; C-17-0011 17-2 PLANNED → K-17-0006 PLAN-ONAY; R-17-0004 DEGISIKLIK B0 M1 m5 N9 → K-17-0008 DUZELT r2 (FOLLOWUP-228); C-17-0017 PR-HAZIR r2 561f255 (test 2294×2, tam test-int 1370/42 + 1 sıralama düzeltmesi) → K-17-0012 VERIFIED, K-17-0013 REVIEW-ISTEK r2 (FOLLOWUP-230); R-17-0008 ONAY B0 M0 m1 N4 → merge 874e24a, K-17-0014 MERGED; gate-171c yeşil (test 2294×2, test-int 1371/42, e2e 1+211) → K-GEN-0056 17-1 DONE |
| 18-kosu-3 | PLANLI (dalga 9 kapanışı öncesi; kullanıcı onayı A 2026-11-23) | test (yeni oturum, açılacak) | (kod yok; test rolü; yığın ffcore-18) | — |
| followup-triage-2 | DONE (MERGED e74276c; kapı gate-tr2-20261122 yeşil) | B (yeni oturum ROL=isci-b PAKET=triage-2, lease ffcore-isci-b-triage2) | fix/followup-triage-2 (baz main d6d2029) | K-TR2-0001; B-TR2-0002 PLANNED → K-TR2-0002 PLAN-ONAY (S1-S5 A); B-TR2-0004 SORU → K-TR2-0003 slot; B-TR2-0005 tam test-int 1193/42/0; B-TR2-0006 PR-HAZIR 135c369 (9 commit, 30 dosya) → K-TR2-0004 VERIFIED, K-TR2-0005 REVIEW-ISTEK (Fable 5.2 inceleyici); R-TR2-0003 ONAY B0 M0 m2 N4 → K-TR2-0006 DUZELT r2 (MINOR-1 B, MINOR-2, NOTE-2/4); B-TR2-0009 PR-HAZIR r2 89df928 (hooks 465) → K-TR2-0008 VERIFIED, K-TR2-0009 REVIEW-ISTEK r2; R-TR2-0006 ONAY B0 M0 m0 N2 → merge e74276c, K-TR2-0010 MERGED + kapı; gate-tr2 yeşil (hooks 465, test-int 1193, e2e 1+203, docs/images temiz) → K-GEN-0044 DONE, K-TR2-0011 HANDOFF-ISTEK |
| fix/hook-egress-1 | DONE | B (yeni oturum ROL=isci-b PAKET=hook-egress-1, lease ffcore-isci-b-hke1) | fix/hook-egress-1 (baz main 029934a) | K-HKE-0001; B-HKE-0001 ACK, B-HKE-0002 PLANNED → K-HKE-0002 PLAN-ONAY; B-HKE-0006 99bb7a3 (19 commit; hooks host 409, test 2145/2150, egress test-int 17); R-HKE-0003 ONAY B0 M0 m2 N3 → K-HKE-0005; B-HKE-0008 3da0bfb (hooks 432, test 2152); R-HKE-0004 ONAY B0 M0 m0 N2; gate-hke-20261120.log test-int 3 failed → K-HKE-0010; B-HKE-0012 a9cc701 (05a live 5/5, test 2156); R-HKE-0005 ONAY; MERGED c1d79f4 + f088aa8 (kapı gate-hkefix-20261120.log: hooks host 421, config'ler, lint, test 2156×2, test-int 1143, smoke, Vitest 279; block kipi etkin); B-HKE-0013 HANDOFF, B-HKE-0014 RETIRED; kanal arşivi hke (14+18+5) |
| fix/followup-triage-1 | DONE | B (yeni oturum ROL=isci-b PAKET=triage-1, lease ffcore-isci-b-triage1) | fix/followup-triage-1 (baz main a60228d) | K-TRJ-0001; B-TRJ-0001 ACK, B-TRJ-0002 PLANNED → K-TRJ-0002 PLAN-ONAY; B-TRJ-0007 292f290 (13 commit; test 1989×2, hook 358, test-int tam koşu DNS kesintili, tekrarlar yeşil); R-TRJ-0003 ONAY B0 M0 m1 N3 → K-TRJ-0005; B-TRJ-0011 f6ec3e5 (test 2014); R-TRJ-0004 ONAY B0 M0 m0 N0; MERGED e9d0de6 (kapı gate-trj-20261120.log: imaj build, hook 347 host, lint, test 2014×2, test-int 1121, smoke, önyüz Vitest 279); B-TRJ-0012 HANDOFF+RETIRED; kanal arşivi triage-1 (12+12+4) |
| 10c-3 | DONE | C (yeni oturum ROL=isci-c PAKET=10c-3, lease ffcore-isci-c-10c3) | feat/10c-3-mcp-ui (baz main ec89bb1) | K-10C3-0001; C-10C3-0001 ACK, C-10C3-0002 PLANNED; C-10C3-0006 b692ad6 (Vitest 279, backend 1925×2, e2e 188/189); R-10C3-0002 ONAY B0 M0 m1 N2 → K-10C3-0006; C-10C3-0007 2b79c34 (docs + en/tr; Vitest 279); R-10C3-0004 ONAY B0 M0 m0 N0; MERGED 0a92084 (kapı gate-10c3-20261119.log: imaj build, lint, test 1925×2, test-int 1012, smoke, önyüz Vitest 279; e2e r1 kanıtı) |
| 05b | DONE | B (yeni oturum ROL=isci-b PAKET=05b, lease ffcore-isci-b-05b) | feat/05b-openapi-mcp (baz main e56bcfa) | K-05B-0001; B-05B-0001 ACK, B-05B-0002 PLANNED; B-05B-0005 (lint 0, test 1851×2); B-05B-0008 749e37e (test 1851×2, test-int 995); R-05B-0004 DEGISIKLIK B0 M1 m2 N6 (upstream-origin-kacagi) → K-05B-0008; B-05B-0012 acc149b (test 1882×2, test-int 107); R-05B-0008 ONAY B0 M0 m1 N2 → K-05B-0012; B-05B-0016 5b00a63 (test 1903×2, test-int 42); R-05B-0011 ONAY B0 M0 m0 N2; MERGED 2e75ba2 (kapı gate-05b-20261118.log: lint, test 1903×2, test-int 1004, smoke yeşil kaynaktan; imaj build 19 Kasım 12:43 doğrulandı, ENV-196 kapandı) |
| fix/19r2-dis-inceleme | MERGED | B (yeni oturum, 4 Kasım 14:02, lease ffcore-isci-b-19r2) | paycoreLLM fix/19r2-dis-inceleme (silindi) | K-19R2-0010 |
| fix/19r3-env-tests | MERGED | B (yeni oturum ROL=isci-b PAKET=fix/19r3; kanal state/kanal/isci-d.md, lease ffcore-isci-d-19r3) | paycoreLLM fix/19r3-env-tests (silindi, HANDOFF sonrası) | K-19R3-0012 |
| 08-tam-1c-olcum | DONE (1c-a + 1c-b MERGED) | A (yeni oturum ROL=isci-a PAKET=08-tam-1c-olcum) | feat/08-tam-1c-olcum (main 63ffb16+) | A-08T1C-0025 |
| fix/19-dis-inceleme | MERGED | B (yeni oturum, 3 Kasım 09:27) | paycoreLLM feat/19-dis-inceleme (silindi) | R-19R-0004 |

## PoC sonrası

| Paket | Durum | Bağımlılık / not |
|---|---|---|
| 03c | DONE (dalga 6, 17 Kasım 2026) | 03b; 06b ile birlikte (API key, kota, usage, retention, uyarılar, bildirim) |
| 11 | DONE 2026-11-21 (dalga 8) | 06a, 07; kendi `/chat` ekranı (DECISION-193 A) |
| 08 tam | DONE (dalga 6, 17 Kasım 2026; 1a-1c) | 08-lite; Türkçe NER, injection, akış tamponlayıcı, PRSIM ingest guard'ı |
| 06b | DONE (dalga 6, 17 Kasım 2026) | 06a, 03c (facade, dış agent, manifest) |
| fix/06a-egress-all-messages | MERGED | A (yeni oturum) | fix/06a-egress-all-messages (silindi) | (kaldırıldı 2026-11-02 11:40) | backend/ffcore/runtime/graph.py (llm_call sınırı), guardrails çağrı yeri, tests/ | 2026-11-01 | | BLOCKERS 134; GOREV K-134-0001; 06b merge'ünden ÖNCE; danışman görüşü; PR-HAZIR (kısmi) A-134-0002 b9eefe3; r1 kod turu R-134-0002 KOD-ONAY (ön), MINOR 3 (tool_calls.arguments egress dışı; guard_in çift denetim; str olmayan content sessiz, TextTooLong generic) → DUZELT K-134-0003; nihai ONAY yığınlı turda ((e)/(f), test-int iki profil); DUZELT uygulandı 3d03bc9; PR-HAZIR A-134-0004 10e86bf0d54215e2783ed304e6af712798666858 (baz 07dc421, 3 commit, 6 dosya +469/-11, main ile çakışma yok, koordinatör doğruladı); kanıt tam tee state/evidence/134-*-20261102.log: make test 745/745 iki profil, test-int 682 + 4 atlandı, sağlayıcı isteği testi (fake-llm /_requests) kırmızı→yeşil; REVIEW-ISTEK r2 K-134-0006; r2 ONAY R-134-0004 (MINOR-4 → FOLLOWUP-139); merge d274bc9 (2 Kasım 11:19); **tam kapı yeşil** (state/evidence/gate-134-20261102.log, tam tee): build, compose config, up, lint 0, alembic heads tek (57_0002), make test 745/745 iki profil, test-samples, test-int 682 + 4 atlandı, smoke passed, önyüz lint/tsc/check:api 0, down -v; BLOCKERS 134 kapandı |
| 06b-2 | DONE (dalga 6, 17 Kasım 2026) | 06b merge (dış agent: external_config, SafeOutboundClient, SSRF matrisi; KARARLAR "06b S5 ... 06b-2") |
| 04b | DONE (dalga 6b, 19 Kasım 2026; 04b-1 + 04b-2) | 04a (DuckDB → Postgres göçü DEBT-1, migrate-vectors) |
| 05b | DONE (dalga 6b, 19 Kasım 2026) | 05a |
| 09 | DONE (dalga 6, 17 Kasım 2026; 09-1 + 09-2) | 06a, 02, 04a, 13a (Langfuse datasets) |
| 10c | DONE (10c-1 dalga 6; 10c-2/10c-3 dalga 6b, 19 Kasım 2026) | 03c, 05b, 09 |
| 12 | DONE (dalga 7, 20 Kasım 2026; 12-1 + 12-2; PENDING_ENV kalemleri kullanıcı donanımı) | hepsi |
| 14 | DONE 2026-11-22 (dalga 9; 14-1 + 14-2) | 03, 04a, 06a, 08, 11, 13a; isci-c |
| 17 | GOREV 2026-11-23 (dalga 9 üçüncü şerit, kullanıcı A) | 03a, 03b, 03c, 10a, 11, 12, 14; 15 Slack/Teams bunu bekler; isci-c |
| 16 | GOREV 2026-11-22 (dalga 9 ikinci şerit, kullanıcı A) | 03, 04a, 05a, 03b egress; isci-b |
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
| Dalga 6b (05b, 10c-2, 10c-3, 04b-1, 04b-2) | main d096bb3; kapı logları raporda | Rapor `state/dalga/dalga-6b-kapanis.md` (19 Kasım 2026, koordinatör); **kullanıcı onayladı 2026-11-20** (koordinatör oturumunda "Onay, A: 12 + triage"); geri çevrilen madde yok; dalga 7 = 12 + triage |
| Dalga 7 (triage-1, 12-1, 12-2) | main 9c65d1f; kapı logları raporda | Rapor `state/dalga/dalga-7-kapanis.md` (20 Kasım 2026, koordinatör); **kullanıcı onayladı 2026-11-20** (koordinatör oturumunda "Onay, A: 11"); geri çevrilen madde yok; dalga 8 = 11 + hook/egress dilimi |
| Dalga 8 (hook-egress-1 + fix, 11-1 + parity, 11-2) | main 6590719; kapı logları raporda | Rapor `state/dalga/dalga-8-kapanis.md` (21 Kasım 2026, koordinatör); **kullanıcı onayladı 2026-11-22** (koordinatör oturumunda "projede kalan kısımları tamamlamaya devam et"; koordinatör bunu önerilen A seçeneği saydı, KARARLAR 'Dalga 9'); geri çevrilen madde yok; dalga 9 = 14 + triage-2 |
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
