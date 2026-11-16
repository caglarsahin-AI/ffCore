# Arşiv: isci-a · 134

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-134-0001 · 2026-11-01 · → koordinator · PLANNED
Paket: fix/06a-egress-all-messages   Cevap: K-134-0001   [B]
Worktree .worktrees/fix/06a-egress-all-messages (main 07dc421'den). **Model uyarısı:** oturum Sonnet 5.5 açıldı (Opus 5.5 beklenmişti); ayrıca bildirdim.
Plan: tek kontrol noktası `graph._egress_messages` (model düğümünde, `ctx.model.call` öncesi): tüm mesajların `content`'i (system, geçmiş, user, assistant, tool) `guard.check("egress")`; run içi önbellek (`RunContext.egress_cache`, hash→maskeli metin, additive alan); aynı run token_store ile idempotent; block → StopRun failed/`guardrail_block` (sessiz atlama yok; araç sonucunda da aynı tek kural); `llm_call.request_messages` maskeli liste. Airgap'te egress aşaması zaten yok (EngineGuard allow döner) → yapılandırma farkı, `if profile` yok. assistant `tool_calls.arguments` tool_guard'da zaten maskeli, dokunmuyorum. Kırmızı test: tests/unit/test_134_egress_all_messages.py (eski kodda 2 düşüyor). Sonra entegrasyon testi (F4 deseni, fake-llm /_requests) için YIGIN-AÇ isteyeceğim.
Felsefe: (1) sorunun kökü tek sınırda çözülüyor, her kanala yama yok; (2) sessiz düşüş yok; (3) platform (token_store) yeniden inşa edilmedi.

### A-134-0002 · 2026-11-01 · → koordinator · PR-HAZIR (kısmi: yığınsız) + YIGIN-AÇ + HANDOFF
Paket: fix/06a-egress-all-messages   Cevap: K-134-0001
fix/06a-egress-all-messages @ b9eefe3b93bd1d6ca55b5a4a22c26db45111a20d (1 commit, 4 dosya, migration yok). PR açıklaması state/pr/06a-egress.md.
Kırmızı→yeşil: 4 birim test (eski kodda 2 düşer). Host `tests/unit tests/contract`: 730 geçti, 8 düştü (hepsi Windows ortamı, dokunmadığım testler). Lint temiz. **Koşulmadı:** docker `make test` iki profil; iki entegrasyon testi (gerçek motor+Redis, `test_134_egress_real_engine.py`); (e) tam senaryo ve (f) F4 genişletmesi (fake-llm /_requests).
YIGIN-AÇ talebi: bir yığın (Postgres+Redis+fake-llm, LiteLLM) ile (e)/(f)'yi yazıp koşmak ve `make test` iki profil; C: 24 GB uyarısı geçerli. Onay gelirse devam; yoksa PR yukarıdaki sınırla incelemeye gider. Model: oturum Sonnet 5.5 açıldı (Opus 5.5 değil).
HANDOFF: durum yukarıda; kalan iş = (e)/(f) + docker kapıları. Worktree .worktrees/fix/06a-egress-all-messages temiz.

### A-134-0003 · 2026-11-02 · → koordinator · DUZELT uygulandı + YIGIN-AÇ (Docker kapalı)
Paket: fix/06a-egress-all-messages   Cevap: K-134-0003
3 MINOR tamam: fix/06a-egress-all-messages @ 3d03bc98ad5517ad9da293415e312edada618285 (baz 07dc421, 2 commit). (1) tool_calls.arguments değer değer egress, JSON bozulmaz; (2) guard_in sonucu egress_cache'e yazılır, mesaj başına 1 denetim; (3) `unsupported_message_content`, `guardrail_text_too_long` (+docs/agentlar.md). 4 yeni birim test önce kırmızı (eski kodda 4/4 düştü), şimdi 8/8 yeşil; ruff temiz. PR metni güncel (state/pr/06a-egress.md; "tool_guard zaten maskeli" cümlesi çıktı).
YIGIN-AÇ: `docker info` 60 sn denendi, daemon hâlâ kapalı (Docker Desktop açık değil); C: 44 GB. Açılınca ffcore-134 yığını (18180/13180, 0.0.0-134, --profile test) açıp 2 entegrasyon testi + (e)/(f) + make test iki profil koşacağım. Docker Desktop'ı kendim başlatmadım; açıldığında haber ver ya da kullanıcı açsın.

### A-134-0004 · 2026-11-02 · → koordinator · PR-HAZIR + YIGIN-KAPA + HANDOFF
Paket: fix/06a-egress-all-messages   Cevap: K-134-0003 / K-134-0005   [B]
**PR-HAZIR:** fix/06a-egress-all-messages @ 10e86bf0d54215e2783ed304e6af712798666858 (baz 07dc421, 3 commit, migration yok). PR açıklaması state/pr/06a-egress.md (güncel).
Kanıt (tam tee, state/evidence/134-*-20261102.log): `make lint test` llmaas 745 / airgap 745 passed; `make test-int` (qdrant ile, llmaas yığını) 682 passed, 4 skipped; hedefli 32 passed; yeni sağlayıcı-isteği testi (fake-llm /_requests) yeşil, eski kodda kırmızı. Sınırlar: test-int yalnız llmaas yığınında; kalıcı konuşma + gerçek run_sql run'ı yerine aynı model düğümü gerçek LiteLLM/fake-llm yoluyla koşuldu (PR'da yazılı).
**YIGIN-KAPA:** ffcore-134 `down -v` yapıldı (konteyner 0, volume 0); imajlar `ffcore/backend:0.0.0-134`, `ffcore/tools:0.0.0-134` yerelde duruyor (temizlik listenize: 7 GB x2). C: 43 GB boş.
HANDOFF: iş tamam; kalan = inceleme turu (yığınlı r2) ve merge. Worktree .worktrees/fix/06a-egress-all-messages temiz. Model notu: oturum Sonnet 5.5.

### A-134-0005 · 2026-11-02 · → koordinator · RETIRED
Paket: fix/06a-egress-all-messages   Cevap: K-134-0009
ACK: main'de d274bc9, BLOCKERS 134 kapandı, FOLLOWUP-139 kayıtlı. Bu oturum (isci-a, fix/06a-egress-all-messages) lease RETIRED; açık iş yok, yığın ve worktree yok.
