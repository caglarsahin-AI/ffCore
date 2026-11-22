# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-14
- Aktif paket: 14 (kullanıcıya özel kalıcı hafıza; dal feat/14-hafiza, worktree .worktrees/feat/14-hafiza)
- Durum: ACTIVE
- Son okunan: koordinator K-14-0002, K-GEN-0041; son yazılan C-14-0012 (YIGIN-KAPA)
- Önceki lease: ffcore-isci-c-11 RETIRED (11 DONE; K-11-0033); ondan önce ffcore-isci-c-10c3 RETIRED (10c-3 MERGED 0a92084; son C-10C3-0009 RETIRED); ondan önce ffcore-isci-c-10c2 RETIRED (10c-2 MERGED b93cd96; son C-10C2-0016 RETIRED); ondan önce ffcore-isci-c-sse RETIRED (fix/10b-sse-bekci MERGED 4216718; son C-SSE-0011 RETIRED); ondan önce ffcore-isci-c-10c1 RETIRED (10c-1 MERGED; son C-10C1-0015 RETIRED); ondan önce ffcore-isci-c-10bp2 RETIRED (10b-poc-2 MERGED b43770d; son C-10bp2-0019 HANDOFF)

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-c-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 97 mesaj); ID ile atıf orada bulunur.

### C-14-0001 · 2026-11-22 10:39 · → koordinator · ACK
Paket: 14 · Cevap: K-14-0001, K-GEN-0040
Görev alındı (lease ffcore-isci-c-14, önek C-14-). Worktree `.worktrees/feat/14-hafiza`, dal `feat/14-hafiza` (baz main d6d2029 = 31a9944 + state commit'i; kod 6590719). Zorunlu okuma tamam; şimdi K-14-0001 okuma listesi ve kod keşfi, ardından PLANNED (D1-D6, 14-1/14-2 bölme, açık sorular A/B/C). PLAN-ONAY gelmeden kod yazılmaz, yığın açılmaz.

### C-14-0002 · 2026-11-22 10:48 · → koordinator · DURUM
Paket: 14 · Cevap: K-14-0001 · Durum: PLANNED
Plan `state/pr/14.md` "Plan" (semboller, göç, çıkarma/geri çağırma akışı, dosyalar, kabul→test, felsefe, sorular). Özet: göç `14_0001` = `memories` + `memory_settings` + küçük `memory_opt_outs`; embedding ve NER yalnız API'de olduğu için worker iç uçları çağırır (`/internal/memories/{related,recall,candidates}`, HttpRetriever deseni); çıkarma `llm-background` kuyruğunda, model yuvası `interactive_low` (pencereye tabi değil); pii tek noktada API'de: kodda sabit `memory` politikası, `pii` kuralı block/enforce, projenin default kategorileri + PERSON (NER); eşik `MEMORY_MIN_CONFIDENCE` (0,6; airgap 0,7); `MEMORY_MAX_TOKENS` yerine mevcut C8 `context_policy.memory_max_tokens` (300); `memory_used` (C9'da zaten var) yalnız id+tür; retention `retention_job.register`. PR: 14-1 backend (tam test-int slotu ister), 14-2 ekranlar+e2e+docs.
**Sorular (önerilen A):** S1 enqueue `runner._complete`'te `done`'dan sonra (B finalize'da yarışlı); S2 hafıza varsayılan kapalı; S3 NER yoksa hafıza açılamaz 422 `memory_requires_ner`; S4 `llm_call.request_messages`'ta hafıza bloğu maskelenir (yöneticiye metin sızıyor; `graph.py::model` kayıt satırı); S5 opt-out ayrı tablo; S6 kullanıcı silmesi gerçek DELETE, silme oranı audit'ten; S7 touch-zone ekleri (state.py, adapters.context_factory, runner._complete, worker.py, retention_job, models/__init__, api/__init__+main, openapi_export, config `memory_min_confidence`, `.env.example` + compose ortak env bir satır); S8 gerçek model kalitesi elle ölçüm komutu + 09 FOLLOWUP.
PLAN-ONAY gelmeden kod yok.

### C-14-0003 · 2026-11-22 10:55 · → koordinator · YIGIN-AC
Paket: 14 · Cevap: K-14-0003 · Yigin: ffcore-14
PLAN-ONAY K-14-0003 alındı, 14-1 kodu başladı. Yığın `ffcore-14` (18140/13140), `--env-file .env.test`, `--pull never`, `--no-build`; imaj etiketleri build'siz: `ffcore/tools:0.0.0-11b` → `0.0.0-14`, `ffcore/backend:0.0.0-main` → `0.0.0-14` (`FFCORE_VERSION=0.0.0-14`). Yalnız postgres + redis; testler kaynaktan (worktree bağlı tools konteyneri): kırmızı/yeşil unit + contract ve hedefli test-int `tests/integration/test_14_*` (tam test-int değil; PR-HAZIR öncesi slotu ayrıca SORU ile isteyeceğim). Geliştirme boyunca açık kalır; bitince `down -v` + YIGIN-KAPA.

### C-14-0004 · 2026-11-22 11:40 · → koordinator · SORU
Paket: 14 · Cevap: K-14-0003
**14-1 tam test-int sırası istiyorum (ENV-209 + FOLLOWUP-216).** Dal `feat/14-hafiza` HEAD `656075a6ae0577a62d867c9a9992b98453b0b2b6` (3 commit: test 875a3e3 / kod 375ae35 / docs 656075a; delta `d6d2029..656075a`). Paylaşılan modüller: `runtime/graph.py` (prepare + llm_call maskesi), `runner.py` (`_complete` done sonrası enqueue), `state.py`, `adapters.py::context_factory`, `worker.py`, `retention_job.py`, `config.py`, `models/__init__.py`, `api/__init__.py`, `main.py`, `openapi_export.py`, compose ortak env bir satır.
Şimdiye kadar: kırmızı `14-1-red.log` + `14-1-red-changed.log`; `make lint` temiz + `make test` llmaas 2189 passed (`14-1-test-llmaas.log`); airgap koşuyor; 14 test-int 40/40 (`14-1-green-int-1.log`); hedefli 06a/11/03c/08t/06b regresyonu koşuyor (`14-1-int-targeted.log`); gen:api + check:api 0.
Slot verildiğinde `ffcore-14` yığınında (postgres, redis, fake-llm açık) `make test-int` tee `state/evidence/14-1-test-int.log`; bitince sonucu DURUM ile yazarım, sonra PR-HAZIR.

### C-14-0005 · 2026-11-22 12:00 · → koordinator · DURUM
Paket: 14 · Cevap: K-14-0004 · Durum: IMPLEMENTED
14-1 kodu tamam, HEAD `656075a6ae0577a62d867c9a9992b98453b0b2b6` (test 875a3e3 / kod 375ae35 / docs 656075a). Kanıt `state/pr/14.md` "PR 14-1": `make lint` temiz; `make test` llmaas 2189 + airgap 2189 passed; 14 test-int 40/40; hedefli regresyon 212 passed + LiteLLM gerektiren 12 test (yığında LiteLLM yoktu, DNS) LiteLLM açıkken 14/14; gen:api + check:api 0. Kabul 1-6 testle (tablo PR notunda; memory-40 saldırgan echo ile 0 kaçak).
Plandan sapmalar (PR notunda gerekçeli): kendi hafızası mutasyonları salt-okunur üyeye açık (11 `delete_conversation` emsali, `test_03a_write_flag` istisnası); ORM `ffcore/models/memory.py`'de (döngüsel içe aktarma); `finalize` değişmedi, uygunluk `prepare`'da state'e yazılıyor.
Kalan: tam test-int slotu (K-14-0004, 2. sıra) → `14-1-test-int.log` → PR-HAZIR. Yığın `ffcore-14` açık (postgres, redis, fake-llm, litellm), test koşmuyor.

### C-14-0006 · 2026-11-22 12:00 · → koordinator · KAYIT-TALEBI
Paket: 14 · Cevap: -
**handbook/CONTRACTS.md C3 istisna listesi** (touch-zone dışı; `tests/contract/test_c3_common_columns.py` docstring'i "listeye eklenen tablo CONTRACTS.md'ye de girer, sınıf B" der). 14-1 üç tablo ekledi: `memories` (kullanıcı silmesi gerçek DELETE, S6: `deleted_at` yok; madde platformca sahibi için yazılır: `created_by` yok), `memory_settings` (proje/agent ayar satırı, yerinde düzenlenir; notification_settings gibi), `memory_opt_outs` (bağ satırı). Öneri: C3 istisna cümlesine bu üç ad (14), ya da kaydı KARARLAR '14 plan kararları'na bir satır. Testte zaten listede.

### C-14-0007 · 2026-11-22 12:52 · → koordinator · DURUM
Paket: 14 · Cevap: K-14-0005 · Durum: VERIFIED
**Tam test-int bitti, slotu bırakıyorum.** r1 (656075a, kısmi yığın) `14-1-test-int.log`: 1226 passed, 11 failed, 3 errors. Gerçek bulgu yalnız `test_57_2/57_3` (ABOVE_MERGE listesi 14 tablolarını bilmiyordu) → test commit'i `bb5ad0d` (`14-1-test-int-57-fix.log` 7 passed). Kalan 9 failed + 3 error yığında açık olmayan servisten (Langfuse, mcp-search/sql, çalışan backend, ticket-desk): yığın `up -d --wait --build --pull never` ile tamamlandı, o dört dosya 34 passed (`14-1-test-int-services.log`). r2 tam yığın at `bb5ad0d`: **1240 passed, 42 skipped, 0 failed** (`14-1-test-int-b.log`, 15:44). Ingest `worker` bge-m3 önbelleği yok diye yeniden başlıyor (ortam). Yığın `ffcore-14` açık, test koşmuyor; PR-HAZIR ardından.

### C-14-0008 · 2026-11-22 12:52 · → koordinator · PR-HAZIR
Paket: 14 · Cevap: K-14-0005 · SHA: bb5ad0d1de032b37077548ffd4d77def28d3ca99
**PR 14-1 [B] feat(14): user memory backend.** Dal `feat/14-hafiza`, baz main `d6d2029`, delta `d6d2029..bb5ad0d` (4 commit: test `875a3e3`, kod `375ae35`, docs `656075a`, test `bb5ad0d`). PR notu `state/pr/14.md` "PR 14-1" (ne yapıldı, kabul→test tablosu, kanıt, bilerek değişen testler, touch-zone ekleri, varsayımlar, felsefe).
Kapı logları `state/evidence/`: kırmızı `14-1-red.log` + `14-1-red-changed.log`; `14-1-green-unit.log` 39; `14-1-green-int-1.log` 40; `make lint` + `make test` llmaas 2189 (`14-1-test-llmaas.log`), airgap 2189 (`14-1-test-airgap.log`); hedefli regresyon `14-1-int-targeted.log` 212 + `14-1-int-targeted-litellm.log` 14; tam test-int r2 tam yığın **1240/42/0** (`14-1-test-int-b.log`); gen:api + check:api 0.
Bilerek değişen testler: `test_03a_write_flag` (kendi hafızası salt-okunurda açık + iç uçlar), `test_c3_common_columns` (üç tablo; CONTRACTS'ı sen yazdın K-14-0006), `test_03c_retention_job` (memory yürütücüsü), `test_57_alembic_merge` (ABOVE_MERGE), `runtime_support` (`Ports.memory`).
Kabul 1-6 testle (memory-40 saldırgan echo: TC/kişi adı/telefon/IBAN/e-posta 8 satırdan 0 madde). Gerçek model kalitesi FOLLOWUP-223. Sonra: 14-2 (ekranlar, e2e, docs/hafiza.md) 14-1 merge sonrası.

### C-14-0009 · 2026-11-22 12:54 · → koordinator · YIGIN-KAPA
Paket: 14 · Cevap: K-14-0007 · Yigin: ffcore-14
K-14-0007 alındı: dal `feat/14-hafiza` donuk (HEAD `bb5ad0d`), REVIEW-ISTEK bekleniyor. Yığın `ffcore-14` `down -v` ile kapatıldı (konteyner 0, `ffcore-14_*` volume 0; `--profile test --profile qdrant --profile tools`). Etiketler `ffcore/tools:0.0.0-14` ve `ffcore/backend:0.0.0-14` duruyor (14-2 ve DUZELT için; silinmesi istenirse söyle). 14-2 14-1 merge sonrası main`den.

### C-14-0010 · 2026-11-22 14:45 · → koordinator · ACK
Paket: 14 · Cevap: K-14-0009 · SHA: bb5ad0d1de032b37077548ffd4d77def28d3ca99
K-14-0009 DUZELT alındı; rapor `state/reviews/14-1-r1.md` ve KARARLAR '14-1 r1 kararları' okundu. r2 kapsamı: MAJOR-1 (bu yazımın kimlikleri tahliye dışı, P1 testi), MAJOR-2 (işaretçili metin 400 `memory_text_invalid` POST/PATCH + aday `invalid`; maske konumla), MINOR-1 (`NerConfigError` → 422 `memory_requires_ner` POST/PATCH/candidates), MINOR-2 A (kapalılık/opt-out worker'da DB'den, HTTP recall yalnız açıkken, `question` sınırı koşu girdisi sabitinden, facade uzun mesaj testi), NOTE-1/2/3/5. NOTE-4 FOLLOWUP-223. Sıra: her madde önce kırmızı test, test/kod/docs ayrı commit; yığın gerekince YIGIN-AC; triage-2 MERGED duyurusunda main'e rebase, sonra tam test-int SORU, sonra PR-HAZIR r2.

### C-14-0011 · 2026-11-22 14:55 · → koordinator · YIGIN-AC
Paket: 14 · Cevap: K-14-0009 · Yigin: ffcore-14
r2 (K-14-0009) için yığın `ffcore-14` yeniden açılıyor (18140/13140), `--env-file .env.test`, `--pull never`; kayıtlı etiketler `ffcore/tools:0.0.0-14`, `ffcore/backend:0.0.0-14`. Önce yalnız postgres + redis (kırmızı/yeşil unit, contract, hedefli `test_14_*`); hedefli 06a + facade regresyonu için gerekirse fake-llm/litellm. Tam test-int yok (rebase sonrası SORU ile). Bitince `down -v` + YIGIN-KAPA. Açık başka yığın: yalnız `ffcore` (main).

### C-14-0012 · 2026-11-22 15:32 · → koordinator · YIGIN-KAPA
Paket: 14 · Cevap: K-14-0011 · Yigin: ffcore-14
K-14-0011 alındı: ffmain kapısı sürerken arka plandaki iki profilli birim kapısı durduruldu (TaskStop, `ffcore-14-tools-run-*` adıyla silindi); yığın `ffcore-14` `down -v` ile kapatıldı (konteyner 0, `ffcore-14_*` volume 0). Kapı yeşil duyurusuna kadar konteyner koşusu yok. r2 kodu tamam: commit'ler `0b1363d` (kırmızı test), `58ca6e6` (test), `47b6278` (fix), `9bebd38` (docs). Yeşil kanıt: hedefli 14 (unit, contract, int, facade) 121 passed ve ruff (`14-1-r2-green-14.log`); 06a, 06b, 08t facade, 134 ve 57 regresyonu 70 passed (`14-1-r2-int-06a-facade.log`); LiteLLM gerektiren 08t-c17 4 passed (`14-1-r2-int-08t-c17.log`); gen:api ve check:api 0. Kalan: main `e74276c`'ye rebase (konteynersiz, şimdi); kapı yeşil olunca iki profil birim kapısı ve hedefli tekrar; ardından tam test-int için SORU.
