# Arşiv: test · 13b

state/kanal/test.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### T-13b-0001 · 2026-10-30 17:29 · → koordinator · PLANNED-taslak (GOREV bekleniyor)
Paket: 13b test tarafı   Cevap: K-SEN-0055 / K-13b-0000
K-13b-0000 okundu. Hazırlık state/pr/13b-test.md'de; kod yok.
Bulunanlar:
- projects.json'da 6 kullanıcı zaten var (2 proje × admin/edit, admin/read, analyst/edit). Eksik: full_name.
- eval/results/ .gitignore'da yok; isci-a'nın alt-claim'i.
Üç dilim, her biri önce kırmızı:
1. gen/projects.py'ye full_name (rol biçimli, kişi adı değil) + örnek veri testi.
2. tests/e2e/negative/: başka testte olmayan olumsuz yollar, fake-llm ile koşabilenler. Kapsam:
   - oturumsuz 401, yabancı Origin 403;
   - read erişimi tüm mutasyonlarda 403;
   - yayınlanmamış agent 404, bilinmeyen değişken 422, bitmiş koşuda 409;
   - SSRF kayıt reddi;
   - secrets enforce → guardrail_block, sağlayıcıya istek 0;
   - 200.000 karakter sınırı 422;
   - onay TTL;
   - audit'te adımlar (brief 13 madde 6).
3. F-tablosu: tests/e2e pytest eklentisi. Test adından F satırı; geçti / kaldı / NOT_RUN gerekçesiyle. Bilinen bulgular known_findings.json'dan. Markdown stdout + dosya. Yığınsız birim testi var.
Açık sorular (öneriler önce): S1 full_name rol biçimli; S2 tablo eklentisi test tarafında, make e2e çağırır; S3 TTL testi için tetik yolu yoksa NOT_RUN.

### T-13b-0002 · 2026-10-30 17:37 · → koordinator · DURUM + yığın sırası
Paket: 13b test tarafı   Cevap: K-13b-0001
feat/13b-test @ 1acf584d5afd4c59cda749cade8dbf27afcff39f (main caa2dfd üstünde, 3 commit):
1. 9f4e743 full_name (rol biçimli): önce kırmızı → test-samples 54 OK.
2. 20817c1 F-tablosu (tests/e2e/ftable.py + conftest + known_findings.json). Birim testi 5 test: önce kırmızı → yeşil.
   Bulunan ve düzeltilen hata: scenarios/conftest'in skip kancası oturumdaki TÜM öğeleri skip ediyordu; artık yalnız kendi klasörünü. Yoksa F-tablosu ve negatif testler sessizce NOT_RUN olurdu.
3. negatif testler (tests/e2e/negative, 12 + TTL NOT_RUN FOLLOWUP-111). Kodlar kaynaktan:
   - 401 unauthenticated;
   - 403 cross_origin_forbidden;
   - 403 read_only_access;
   - 404 agent_not_published, 422 variable_unknown;
   - run input sınırı 20.000 (200.000 değil) → 422 validation_error;
   - 409 run_not_waiting;
   - egress_*;
   - guardrail_block;
   - audit eylem adları.
   Yığınsız: 12 kırmızı, 1 NOT_RUN.
Yığın sırası istiyorum (18020/13020): koşu için e2e.env + seed + tests/e2e tümü --f-table. Ayrıca ruff format/check (tests/e2e lint kapsamında değil).

### T-13b-0003 · 2026-10-30 17:37 · → koordinator · YIGIN-AÇ 13bt
Paket: 13b test tarafı   Cevap: K-13b-0002
Proje ffcore-13bt, FFCORE_VERSION=0.0.0-13bt, BACKEND_PORT=18020 FRONTEND_PORT=13020, --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test.

### T-13b-0004 · 2026-10-30 17:47 · → koordinator · PR-HAZIR + YIGIN-KAPA 13bt
Paket: 13b test tarafı   Cevap: K-13b-0002
feat/13b-test @ fa437b12dde76776ad5d4f2c628f35ef88df4a88 (main caa2dfd üstünde, 4 commit).
Yığın koşusu: seed 0; pytest tests/e2e 49 passed, 2 failed (bilinen: FOLLOWUP-103, -108), 25 NOT_RUN gerekçeli.
- Negatif 12/12 geçti; TTL NOT_RUN FOLLOWUP-111.
- F tablosu PR dosyasında: F1-F4, F9 hat düzeyinde passed; F10 failed (known); F13 NOT_RUN.
- ruff tests/e2e temiz.
Yol üstünde iki hata düzeltildi:
1. scenarios conftest tüm oturumu skip ediyordu.
2. tests.e2e importları yalnız python -m pytest ile çalışıyordu.
eval/results gitignore'u isci-a'da; dalda dosya yok.
YIGIN-KAPA: down -v, konteyner 0. PR dosyası state/pr/13b-test.md.

### T-13b-0005 · 2026-10-30 17:49 · → koordinator · CEVAP
Paket: 18 / 13b   Cevap: K-13b-0004
Evet, kaldırabilirsin. feat/18-scenarios-e2e (07778bf) main'in atası (git merge-base --is-ancestor), worktree temiz. feat/18-f2-stage3 zaten kaldırılmış. 13b dalına commit yok; review bekliyorum.

### T-13b-0006 · 2026-10-30 17:57 · → koordinator · HANDOFF
Paket: 18 + 13b-test   Cevap: K-13b-0005
Lease RETIRED (ffcore-test-18-hazirlik). Açık iş yok, worktree yok, yığın yok (son: 13bt down -v, konteyner 0).

Main'de olanlar (bu oturum):
- **18 veri**: 18-hazirlik, ticket-desk, iki agent şablonu, expected_code, FOLLOWUP-76 ölçek-oran testi.
- **fake-llm tool-\* modu**.
- **18 aşama 2 + F2 aşama 3**, tests/e2e/scenarios:
  - seed.py, idempotent; superadmin login-önce ve hata koduyla.
  - e2e.env, ikinci env-file: FAKE_EMBED=1 + fake-llm host.
  - F1-F13 testleri; NOT_RUN gerekçeli.
- **08 düzeltmeleri**: yerleşik egress PII enforce, Rule.mode, entropi muafiyeti; builtin_version testi.
- **docs/demo.md** F1-F13.
- **13b test tarafı**:
  - projects.json full_name.
  - tests/e2e/ftable.py + conftest (--f-table) + known_findings.json.
  - tests/e2e/negative (12 + TTL NOT_RUN).

Açık bulgular (kayıtlı): FOLLOWUP-101 (upload'da tarih yok, F13), -103 (üye olmayana 403), -106 (kısa büyük harf token'lar), -107 (secrets enforce'ta kodlu parça tüm cevabı blokluyor), -108 (breadcrumb), -111 (07 TTL tetik). known_findings.json'da 103 ve 108 var; düzeldikçe oradan silinmeli, yoksa F tablosu "known" demeye devam eder.

Sonraki oturum için:
- **Yığın komutu**: docker compose -p <ad> --env-file .env.test --env-file tests/e2e/scenarios/e2e.env --profile test, BACKEND_PORT/FRONTEND_PORT projeye özgü.
- **Parolalar**: E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD, E2E_PASSWORD yalnız kabuktan.
- **Koşu**: seed (python -m tests.e2e.scenarios.seed), sonra pytest tests/e2e --f-table <yol>.
- **Tuzaklar**:
  - Docling ağırlığı yok: seed .docx'i .txt yükler.
  - Hedef projede secrets=log (FOLLOWUP-107).
  - tests/e2e importları tests/e2e köküne göre; "tests.e2e." kullanma.
  - scenarios conftest skip'i yalnız kendi klasörü.
  - Windows host'ta process_time 15.6 ms adımlı; CPU oran ölçümü yalnız Linux konteynerinde.
- **13b A tarafı** (make seed/e2e/eval, eval/results gitignore) isci-a'da; birlikte koşu orada.
