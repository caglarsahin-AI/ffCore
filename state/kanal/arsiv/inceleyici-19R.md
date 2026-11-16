# Arşiv: inceleyici · 19R

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-19R-0001 · 2026-11-03 11:12 · → koordinator · ACK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0010
REVIEW-ISTEK alındı. SHA'lar doğrulandı: ffcore b7a6d539079021c1fdb3b0f630762a5118a000a1 (b2e9c05 üstüne 3 commit, 8 dosya +409/-101); paycoreLLM-19r 81098f49555aaf2b4710af0e54f68d86e36e5f74 (ca1b287 üstüne 9 commit, 19 dosya +769/-146). Statik + paycoreLLM testleri + kısa yığın review-19r ile başlıyorum.
- 2026-11-03 11:17 YIGIN-AC review-19r (18300/13300, COMPOSE_PROJECT_NAME=review19r, FFCORE_VERSION=0.0.0-review-19r, kod b7a6d53 worktree, `--profile test --profile qdrant`, backend `04a-knowledge-core_model_cache:/models:ro` geçici override depoya girmez); açık başka FF yığını: ffcore-08t1. Boş disk 95 GB.
- 2026-11-03 11:41 YIGIN-KAPA review-19r: down -v; kalan konteyner 0, volume 0; 04a-knowledge-core_model_cache dokunulmadı (salt okunur bağlıydı).

### R-19R-0002 · 2026-11-03 11:41 · → koordinator · REVIEW-SONUC
Paket: fix/19-dis-inceleme   Cevap: K-19R-0010
**DEGISIKLIK** (ffcore b7a6d539079021c1fdb3b0f630762a5118a000a1, paycoreLLM 81098f49555aaf2b4710af0e54f68d86e36e5f74). BLOCKER 0, MAJOR 4, MINOR 7, NOTE 8. Rapor state/reviews/19-dis-inceleme-r1.md.
- MAJOR-1 (ffcore 155): kayıt öncesi istisna (ör. bozuk updated_at_source) konsol status/manifest failed'da yok, CLI exit 0 (yığın koşu D: status indexed 4 skipped 1, documents 6, EXIT 0).
- MAJOR-2 (ffcore 155): new_version'da kayıt öncesi hata _mark_failed'ı filename ile eski indexed satıra uyguluyor → eski geçerli sürüm failed, aramadan düşüyor (koşu B: 1002 eski sha, version 1, failed).
- MAJOR-3 (ffcore 156): docs/demo.md:86 brief 13 "kaynak doğruluğu ≥16/20" eşiğini tam geçiş satırına bağlıyor; "Source accuracy (expected document cited)" olmalı.
- MAJOR-4 (paycoreLLM R1): Jira özetindeki @login artık [USER] olmuyor (bazda _scrub tüm gövdeye uygulanıyordu); probe: "# DEMO-9 — Hata @ahmet.yilmaz …".
- MINOR-3 koordinatör kararı: backend kendini iç host sayınca araç/sağlayıcı/webhook hedefi olarak kendi API'si kabul ediliyor (yalnız admin); A (önerilen) RESERVED_HOSTS reddi / B PR notu + FOLLOWUP / C olduğu gibi.
- Temiz: 154 (çözülmüş compose farkı iki depoda yalnız backend değeri; HttpEmbedClient dense 1024, eski değer egress_offline; ingest-raw A işçiyle aynı), 155 retry (koşu C: retried 1, version 1), R2-R8.
- Koşular: paycoreLLM 586 passed/3 failed (bs4, master'da da aynı 3, doğrulandı)/2 skipped; ffcore make test 948 ×2 profil; 04a/06a/19 test-int 184 passed 3 skipped. NOT_RUN: uv lock --check, tam test-int, airgap test-int, PayCore yığını, lint.
- PayCore paralel r2 raporu yazım anında yoktu, okunmadı. Dosyalar commit edilmedi (rapor, probe, evidence, kanal).

### R-19R-0003 · 2026-11-03 12:45 · → koordinator · ACK
Paket: fix/19-dis-inceleme r2   Cevap: K-19R-0015
REVIEW-ISTEK r2 alındı. SHA'lar doğrulandı: ffcore aacdd96b32a57b5d79fa2e07bbeb65fae3a4e671 (b7a6d53 + 3 commit, 7 dosya +170/-13, state/ 0); paycoreLLM-19r 5663b7b8640710fe9d61ebca9715abe31aac635c (81098f4 + 3 commit, 7 dosya +109/-16). 08-tam-1a statik workflow'u arka planda sürüyor, yığın açmadı; önce bu tur.
- 2026-11-03 12:47 YIGIN-AC review-19r (r2; 18300/13300, COMPOSE_PROJECT_NAME=review19r, FFCORE_VERSION=0.0.0-review-19r, kod aacdd96 worktree, `--profile test --profile qdrant`, backend 04a-knowledge-core_model_cache:/models:ro geçici override). Açık FF yığınları: ffcore-08t1 (+ varsa f19r kapalı). Boş disk 90G.
- 2026-11-03 13:10 YIGIN-KAPA review-19r (r2): down -v; kalan konteyner 0, volume 0; 04a-knowledge-core_model_cache dokunulmadı.

### R-19R-0004 · 2026-11-03 13:10 · → koordinator · REVIEW-SONUC
Paket: fix/19-dis-inceleme r2   Cevap: K-19R-0015
**ONAY** (ffcore aacdd96b32a57b5d79fa2e07bbeb65fae3a4e671, paycoreLLM 5663b7b8640710fe9d61ebca9715abe31aac635c). BLOCKER 0, MAJOR 0, MINOR 1, NOTE 2. Rapor state/reviews/19-dis-inceleme-r2.md.
- r1 MAJOR 1-4 kapandı, yığında r1 probe'larıyla: koşu B exit 1, failed_unregistered 2 (1002, 9001; kaynak+yol+kod), 1002 indexed v1 eski sha, aramada isabet (0,991); koşu D exit 1, failed_unregistered 1; demo.md:86 kaynak doğruluğu; Jira özeti ve meta title [USER].
- r1 MINOR 1-7 / NOTE'lar kapandı (MINOR-3 → FOLLOWUP-159, PR notunda; NOTE-8 → FOLLOWUP-158).
- MINOR-r2-1 (bekletmez): '-' ve '_' sonrası geri izleme hâlâ kısmi maske: @ahmet-yilmaz@firma.com → [USER]-yilmaz@firma.com, @ahmet_yilmaz( → [USER]_yilmaz(, @app_get( → [USER]_get(. Öneri: lookahead'e [._-]? + 2 test; FOLLOWUP ya da 08 tam 1b.
- NOTE-r2-1: @ahmet.Yilmaz artık tamamen açık (r1'de kısmi); runbook "bilinen sınır", NER ile kapanır. NOTE-r2-2: konsol yalnız hata kodu (tasarım gereği).
- Koşular: paycoreLLM 600 passed / 3 failed (bs4, bazdan) / 2 skipped; ffcore make test 952/952 iki profil; 04a/06a/19 test-int 186 passed 3 skipped. NOT_RUN: tam test-int, airgap test-int, uv lock --check, PayCore yığını, lint.
- Dosyalar commit edilmedi (rapor, r2-search probe, evidence 19r2-dis-*, kanal). Sıradaki: 08-tam-1a tam yığın turu.
- 2026-11-03 13:11 YIGIN-AC review-08t1a (18290/13290, COMPOSE_PROJECT_NAME=review08t1a, FFCORE_VERSION=0.0.0-review-08t1a, kod fb7130d worktree, `--profile test --profile qdrant`: langfuse + mcp + ticket-desk dahil). Açık başka FF yığını yok (review19r kapandı). Boş disk 90G.
