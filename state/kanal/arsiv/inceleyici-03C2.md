# Arşiv: inceleyici · 03C2

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-03C2-0001 · 2026-10-31 19:26 · → koordinatör · ACK
Paket: 03c-1 r2 (delta)   Cevap: K-03c-0016
REVIEW-ISTEK alındı. Tam SHA `3ae38086f6d9fc35ac8c0cc18def72069b25fc25` (r1 f065481... üstüne 3 commit, 11 dosya; state/ değişikliği yok) yerelde doğrulandı. YIGIN-AÇ review-03c (18120/13120, `FFCORE_VERSION=0.0.0-review-03c`); başka açık yığın yok. Statik delta okundu (throttle, keys.py, auth.py, reconcile stop). Koşular: yeni/değişen testler, 03c dosyaları, test_01_*, kendi delta probe'larım, unit+contract. Bitince down -v ve YIGIN-KAPA.

### R-03C2-0002 · 2026-10-31 19:48 · → koordinatör · REVIEW-SONUC
Paket: 03c-1 r2 (delta)   Cevap: K-03c-0016
03c-1 r2 **ONAY (ürün kodu)**. Tam SHA `3ae38086f6d9fc35ac8c0cc18def72069b25fc25`. BLOCKER 0 · MAJOR 0 · MINOR 2. Rapor: `state/reviews/03c-1-r2.md` (Güvenlik delta bölümüyle).
r1 MAJOR-1 kapandı: denetim satırı IP başına pencerede bir (SET NX EX), küresel tavan 100/dk + tek audit_rate_capped; probe: 30 engelli istek ≤ 1 satır (r1'de 30). Redis yokken 503 auth_backend_unavailable, denetim yazılmıyor (probe geçti). impersonation_denied throttled yola bağlı, _audit_denied değişmedi.
MINOR-1 (merge öncesi düzeltilmeli, test-only): test_03c_6_auth_failures_rate_limited hâlâ aralıklı kırmızı. Kök neden DOĞRULANDI: hata sayacı sabit 60 s kovası, test 20+1 istekle ~20-25 s sürüyor; dakika sınırını aşınca 21. istek 429 yerine 401 (döngüde 2. koşuda assert 401 == 429). Seçenek A (önerilen): küresel tavan testinde yaptığınız gibi dakikayı sabitle, kısa r3 yalnız test dosyası; B: birleştir + FOLLOWUP (ana kapıyı aralıklı bozar).
MINOR-2: ReconcileScheduler.stop() çağıranın iptalini de yutuyor (probe 3 gösterdi); cancelling() ile ayır.
Koşular: 88 passed + 2 failed (probe 3 ve MINOR-1 testi); unit+contract 734 passed iki profil. Yığın kapatıldı: down -v. YIGIN-KAPA review03c. Worktree kaldırma denemesi aşağıda. Not: kanal ve review dosyaları commit edilmemiş.

## R-03C3-0001 | 2026-10-31 20:39 | REVIEW-SONUC (ACK+sonuç birlikte) | K-03c-0019
- Paket/SHA: 03c-1 r3 delta, bbf10d2e0b764928d8ed169aa22a028a4a3dfdd0
- Karar: **ONAY** (BLOCKER 0, MAJOR 0, MINOR 0). state/ diff 0.
- r2 MINOR-1 ve MINOR-2 kapandı; varsayılan saat gerçek, üretim davranışı değişmedi; delta başka üretim davranışı değiştirmiyor.
- Rapor: state/reviews/03c-1-r3.md; probe: state/reviews/03c-1-r3-probe.py. Stack açılmadı; birim/lint kanıtı işçiden, benim koşmadığım "doğrulanmadı".
- Koordinatör 03c-1'i main'e merge edebilir.

## R-03C2-0003 | 2026-10-31 21:42 | ACK | K-03c-0022
- REVIEW-ISTEK 03c-2 alındı; SHA dea5c092fc90a69dc525ed5d595d0d97f6897ff9 mevcut. Güvenlik turu + yığınlı. Worktree .worktrees/review-03c2-r1.
- YIGIN-AÇ review-03c2 (18140/13140) — açmadan önce açık FF yığını ve disk kontrolü yapılıyor.
- 2026-10-31 21:43 YIGIN-AÇ review-03c2: proje review03c2, portlar 18140/13140, FFCORE_VERSION=0.0.0-review-03c2, --profile test --profile qdrant, .env.test; açık başka FF yığını yok, C: 44 GB boş. Statik tur (retention, notify/egress, alerts, migration) yapıldı; yığın: entegrasyon + negatif probe'lar.

## R-03C2-0004 | 2026-10-31 21:59 | REVIEW-SONUC | K-03c-0022
- Paket/SHA: 03c-2, dea5c092fc90a69dc525ed5d595d0d97f6897ff9. Güvenlik turu + yığın review03c2 yapıldı, `down -v`; YIGIN-KAPA review03c2.
- Karar: **DUZELT**. BLOCKER 0 · MAJOR 1 · MINOR 3. state/ diff 0.
- MAJOR-1: audit sınıfındaki hata tüm retention geçişini durduruyor (audit_partitions try/except dışında; sınıflar alfabetik, audit content'ten önce) → content temizliği engellenir, partial/failed kaydı yok. Probe düştü: state/reviews/03c-2-r1-probe.py::test_p2. Düzeltme: sar + testle.
- MINOR: (1) audit DROP kaydı trigger="schedule" sabit; (2) string_agg ile partition özeti büyük aylarda bellek riski (test etmedim); (3) DROP sonrası olay yazımı hatası.
- Geçenler: entegrasyon 50 passed; unit+contract iki profil 734; ruff temiz; migration down/up temiz; 21/22 probe (audit 365 tabanı, iki bayrak, dry-run değişiklik yok, SMTP/webhook özel adres/rebinding/port reddi, ACL, parola sızıntısı yok).
- NOT_RUN: önyüz/e2e, gerçek SMTP, büyük partition. Rapor: state/reviews/03c-2-r1.md. Worktree dizini .worktrees/review-03c2-r1 yine "Permission denied" ile silinemedi (git kaydı kalktı, çalışma ağacı temizdi, --force kullanmadım) — kullanıcı temizlik listesinde.
- Kanal/review dosyaları commit edilmemiş (koordinatör merge öncesi commit eder).

## R-03C2-0005 | 2026-10-31 23:28 | ACK | K-03c-0025
- REVIEW-ISTEK 03c-2 r2 delta alındı; SHA 47a49a460b8390490c4c152e12e2bd4557b4754a mevcut (dea5c09 üstüne 2 commit, 3 dosya; state/ diff 0). Statik delta + probe dosyam; yığın gerekirse YIGIN-AÇ yazarım.
- 2026-10-31 23:29 YIGIN-AÇ review-03c2 (18140/13140, FFCORE_VERSION=0.0.0-review-03c2); açık başka yığın yok. Statik delta okundu (retention_job.py, 3 test dosyası); koşu: retention_job + 03c dosyaları + test_01_events x3 + probe dosyam.

## R-03C2-0006 | 2026-10-31 23:34 | REVIEW-SONUC | K-03c-0025
- Paket/SHA: 03c-2 r2 delta, 47a49a460b8390490c4c152e12e2bd4557b4754a. Yığın review03c2 açıldı ve `down -v` ile kapatıldı (YIGIN-KAPA review03c2).
- Karar: **ONAY** (BLOCKER 0, MAJOR 0, MINOR 0). state/ diff 0.
- MAJOR-1 ve MINOR-1/2/3 kapandı (probe + 73 passed; test_01_events 3×3). 47a49a4 testi kararlı. 5 madde tek tek rapor dosyasında.
- Doğrulanmadı: unit/lint (işçi kanıtı), "iki reconcile LiteLLM 400" gerekçesi. Not: detached kalan partition yeniden denenmez (r1'de de böyle), elle temizlik notu önerilir.
- Rapor: state/reviews/03c-2-r2.md. Koordinatör 03c-2'yi merge edebilir. Kanal/review dosyaları commit edilmemiş.

## R-57-0001 | 2026-11-01 05:51 | ACK | K-57-0003
- REVIEW-ISTEK fix/57-alembic-merge alındı; SHA 5dbf11ec1eae40003b108cee09fc768943bdee0b mevcut (baz 148eadd, 1 commit, 14 dosya; state/ diff 0). Yığınlı migration turu + statik. YIGIN-AÇ review-57 (18170/13170, FFCORE_VERSION=0.0.0-review-57); açık FF yığını yok, C: 39 GB boş.
- 2026-11-01 05:51 YIGIN-AÇ review-57 (18170/13170, FFCORE_VERSION=0.0.0-review-57, yalnız postgres+tools gerekli); açık FF yığını yok.

## R-57-0002 | 2026-11-01 06:13 | REVIEW-SONUC | K-57-0003
- Paket/SHA: fix/57-alembic-merge, 5dbf11ec1eae40003b108cee09fc768943bdee0b. Yığın review57 açıldı ve `down -v` ile kapatıldı (YIGIN-KAPA review57). state/ diff 0.
- Karar: **ONAY** (BLOCKER 0, MAJOR 0, MINOR 1). Ana şekilli DB gerçek merge-öncesi kodla kuruldu: veri kayıpsız 57_0002'ye, şema özdeş; açık hedefli geri alma ve round-trip temiz; göreli geri alma "Ambiguous walk" ile reddediliyor, hiçbir şey oynamıyor; yeni paket revizyonu tek uçtan çalışıyor; scratch_db sızıntı yok. Tam entegrasyon 678 passed + 4 skipped.
- NOT_RUN: unit/lint/airgap (işçi kanıtı); migrate'in ikinci çalıştırmasının çıkış kodunu doğrudan okumadım (probe'da idempotent exit 0 kanıtlı).
- Rapor: state/reviews/57-alembic-merge-r1.md; probe'lar 57-r1-probe.py, 57-r1-probe2.py. Worktree .worktrees/review-57-* silme sonucu aşağıda. Kanal/review dosyaları commit edilmemiş.
- Worktree'ler (.worktrees/review-57-r1, review-57-base) temiz doğrulandıktan sonra `git worktree remove` ile (--force yok) sorunsuz kaldırıldı.

## R-134-0001 | 2026-11-02 09:55 | ACK | K-134-0002
- REVIEW-ISTEK fix/06a-egress-all-messages alındı; SHA b9eefe3b93bd1d6ca55b5a4a22c26db45111a20d mevcut (baz 07dc421, 1 commit, 4 dosya; state/ diff 0). Kod turu, yığınsız (disk 21 GB uyarısı: yığın açmıyorum). Güvenlik turu bölümü dahil.

## R-134-0002 | 2026-11-02 10:01 | REVIEW-SONUC | K-134-0002
- Paket/SHA: fix/06a-egress-all-messages, b9eefe3b93bd1d6ca55b5a4a22c26db45111a20d. Kod turu, yığınsız (yığın açılmadı).
- Karar: **KOD-ONAY (ön)**, nihai ONAY yığınlı turdan sonra. BLOCKER 0 · MAJOR 0 · MINOR 3. state/ diff 0.
- Kanıt: birim paketi 669 passed; gerçek motorla probe (state/reviews/134-r1-probe.py) 17 kontrol FAIL yok: system/geçmiş/assistant/tool tokenize, idempotent, önbellek bağlama özel, enforce'ta sır → guardrail_block.
- MINOR-1: assistant tool_calls.arguments egress'e girmiyor; default politikada tool.pre PII'ı uygulamıyor (probe: ham e-posta kalıyor) → "zaten maskeli" cümlesi yanlış; etki küçük. MINOR-2: guard_in'in egress ettiği user mesajı model düğümünde ikinci kez denetleniyor (önbellek beslenmiyor) → monitor kurallarında çift olay riski (koddan çıkarım, DB'de gözlemlenmedi). MINOR-3: str olmayan content sessiz geçiyor; TextTooLong generic run_error.
- NOT_RUN: iki entegrasyon testi, (e)/(f), make test iki profil, contract+ruff. Rapor: state/reviews/06a-egress-r1.md. Worktree temiz doğrulandı ve git worktree remove ile kaldırıldı. Dosyalar commit edilmemiş.

## R-134-0003 | 2026-11-02 11:00 | ACK | K-134-0006
- REVIEW-ISTEK 06a-egress r2 alındı; SHA 10e86bf0d54215e2783ed304e6af712798666858 mevcut (b9eefe3 üstüne 2 commit, 4 dosya; state/ diff 0). Yığınlı tur. YIGIN-AÇ review-134 (18190/13190, FFCORE_VERSION=0.0.0-review-134, --profile test --profile qdrant); açık yığın yalnız ffcore-19, C: 43 GB.
- 2026-11-02 11:00 YIGIN-AÇ review-134 başlatılıyor (build + up).

## R-134-0004 | 2026-11-02 11:18 | REVIEW-SONUC | K-134-0006
- Paket/SHA: fix/06a-egress-all-messages r2, 10e86bf0d54215e2783ed304e6af712798666858. Yığın review-134 (18190/13190) açıldı ve `down -v` ile kapatıldı (YIGIN-KAPA review134). state/ diff 0.
- Karar: **ONAY** (BLOCKER 0, MAJOR 0, MINOR 1 düşük). r1 MINOR 1-3 kapandı: arguments değer değer tokenlı (iç içe JSON, detokenize geri getiriyor), mesaj başına tek denetim (hook satırı çiftlenmiyor), str olmayan içerik / JSON olmayan arguments / 200.001 karakter kodlu hata ve sağlayıcıya hiçbir şey gitmiyor.
- Koşular: hedefli 12; tam entegrasyon llmaas 682 passed + 4 skipped; unit+contract llmaas 745, airgap 749 (iki 134 entegrasyonu dahil); kendi probe'um 4/4. Sağlayıcı isteğinde (fake-llm /_requests) ham e-posta/telefon yok; worker/backend/litellm/fake-llm loglarında 0 eşleşme (sınırlı: testler model düğümünü tools konteynerinde sürüyor).
- Madde 5 (işçi sınırı): kabul edilebilir; gerçek API→worker→mcp-sql koşusu koşulmadı, DUZELT şartı yapmadım.
- MINOR-4: sayısal JSON değerleri (örn. TCKN sayı) egress'ten geçmiyor; probe'da ham gitti; düşük etki, merge'ü engellemez.
- NOT_RUN: lint (işçi kanıtı), uçtan uca run. Rapor: state/reviews/06a-egress-r2.md. Koordinatör merge edebilir (06b bekliyordu). Worktree .worktrees/review-134-r2 temiz doğrulandı ve kaldırıldı. Dosyalar commit edilmemiş.
- Sıradaki: K-M3S-0013 (19 M3 sunucu paketi) mesajı alındı; kanalı okuyup ayrı ACK ile başlayacağım.

## R-19-0001 | 2026-11-02 11:19 | ACK | K-M3S-0013
- REVIEW-ISTEK 19 M3 sunucu paketi alındı. SHA'lar mevcut: ffcore 987dd62721c346fd376a8861944ecd1ab6de2422 (feat/m3-server-package, baz 3f20541), paycoreLLM-m3 3adbb3a98d671137b77a70680ac18126ab43d754 (baz 8594bb0). Güvenlik turu + yığınlı, iki depo ayrı başlık. paycoreLLM tarafında .env, data/**, eval/results/** okunmaz; PayCore sunucusuna bağlanılmaz; paycoreLLM'i `git archive` ile salt-okunur çıkarıp (depoya yazmadan) inceliyorum.
- YIGIN-AÇ review-19 (18200/13200, FFCORE_VERSION=0.0.0-review-19, --profile test --profile qdrant) hazırlığı; açık FF yığını yok, C: 42 GB.
- 2026-11-02 11:23 YIGIN-AÇ review-19 (18200/13200, FFCORE_VERSION=0.0.0-review-19, imajlar 0.0.0-main'den etiketlendi; kod worktree salt-okunur), --profile test --profile qdrant; açık FF yığını yok.

## R-19-0002 | 2026-11-02 11:46 | REVIEW-SONUC | K-M3S-0013
- Paket/SHA: 19 M3 sunucu paketi. ffcore 987dd62721c346fd376a8861944ecd1ab6de2422; paycoreLLM-m3 3adbb3a98d671137b77a70680ac18126ab43d754. Güvenlik turu + yığın review-19 (18200/13200) yapıldı, down -v (YIGIN-KAPA review19). state/ diff 0.
- Karar: **DUZELT**. BLOCKER 0, MAJOR 2, MINOR 6.
- MAJOR-1: compose.ffcore.yml digest'li imaj referansları (ffcore-qdrant, langfuse-minio) docker save/load sonrası çözülmüyor: kendi denememde `docker run --pull never repo:tag@sha256:...` "No such image" (RepoDigests boş); airgap sunucuda ffcore-qdrant kalkmaz. Brief madde 6 cevabı: image-id doğrulaması yeter ama compose referansı tag'e çevrilmeli; minio adı images.txt (cgr.dev/...) ile compose (chainguard/minio) tutmuyor. Sunucunun depo türü doğrulanmadı.
- MAJOR-2: meta title/breadcrumb/source_url maskelenmiyor (silver frontmatter, documents.metadata, arama breadcrumb'ında ham e-posta/telefon; probe) ve PRSIM müşteri-verisi taraması bu alanlara bakmıyor.
- MINOR: PRSIM tespiti yalnız meta source; preflight ALLOWED_INTERNAL_HOSTS'a bakmıyor; temizlik manifests/pg-dump bırakıyor; PR metni 26. satır Qdrant tutarsız; _text_findings strict decode; imza ayıklama sessiz içerik kaybı.
- Geçenler: ffcore tam entegrasyon 690 passed + 5 skipped; paycoreLLM 41 passed; yol/symlink/.. probe'ları temiz; PRSIM bayraksız ret ve müşteri verisi durması (değer yok); preflight değer basmıyor; compose config temiz, FFCore portları 127.0.0.1, mem 24 GB tutarlı.
- NOT_RUN: PayCore yığınıyla up, kuru koşunun iç ağ tekrarı, save/load gerçek koşusu, bellek ölçümü, lint, PDF/DOCX PRSIM yolu, m3_gate_check host'ta. Rapor: state/reviews/19-r1.md; probe'lar 19-r1-probe.py, 19-r1-probe-stage.py. Worktree temiz doğrulanıp kaldırıldı, geçici imaj etiketleri silindi. Dosyalar commit edilmemiş.

## R-19-0003 | 2026-11-02 12:17 | ACK | K-M3S-0017
- REVIEW-ISTEK 19 r2 delta alindi. SHA ffcore 990abdb35abef0887689c6dcdf307b849929dfc4 (987dd62 + 1 commit, 12 dosya, state/ diff 0), paycoreLLM-m3 6f03007746b016e9b773942fb01ac1b5138fd45e (3adbb3a + 1 commit, 8 dosya) mevcut. Statik delta + r1 probe dosyalari; yigin gerekirse YIGIN-AC yazarim (C: 42 GB, acik FF yigini yok).
- 2026-11-02 12:18 YIGIN-AC review-19 (18200/13200, FFCORE_VERSION=0.0.0-review-19, imajlar 0.0.0-main etiketli, kod worktree salt-okunur); kisa tur: r1 probe yeniden + meta kapanisi. Acik FF yigini yok.

## R-19-0004 | 2026-11-02 13:05 | REVIEW-SONUC | K-M3S-0017
- Paket/SHA: 19 r2 delta. ffcore 990abdb35abef0887689c6dcdf307b849929dfc4; paycoreLLM-m3 6f03007746b016e9b773942fb01ac1b5138fd45e. Yığın review-19 (18200/13200) açıldı ve down -v ile kapatıldı (YIGIN-KAPA review19). state/ diff 0.
- Karar: **ONAY** (BLOCKER 0, MAJOR 0, MINOR 0). r1 MAJOR-1/2 ve MINOR-1..6 kapandı.
- Kanıt: tam entegrasyon 693 passed + 5 skipped; hedefli 76 passed; paycoreLLM 50 passed; r1 probe'larının güncellenmiş hâli 8/8 (meta artık maskeli: breadcrumb/metadata/silver/chunk'ta ham değer yok; PRSIM meta'da IBAN → customer_data_suspected; geçersiz UTF-8 → invalid_encoding, koşu sürüyor; prsim* önek/yol kuralı); compose.ffcore.yml'de @sha256 = 0; kendi denememde docker load sonrası yalnız tag çalışıyor.
- Doğrulanmadı: containerd/sunucu imaj deposu türü; save.sh/load.sh gerçek koşusu; PayCore yığınıyla up; kuru koşu tekrarı; lint/unit 798 (işçi kanıtı). Not: minio etiketi (e70b2b1e) yalnız arşivle anlamlı.
- Rapor: state/reviews/19-r2.md. Koordinatör ffcore merge + main kapısı ve paycoreLLM-m3 -> master merge yapabilir. Worktree'ler temiz doğrulanıp kaldırıldı. Dosyalar commit edilmemiş.

## R-06B-0001 | 2026-11-02 12:37 | ACK | K-06b-0010
- REVIEW-ISTEK 06b facade alindi. Tam SHA 45d901b5a9699bf871bddeb40445fd954b8df6ff (mesajdaki duzeltilmis hali; kanal ve git ile dogrulandi; feat/06b-facade, 6 commit, 33 dosya, baz 4532a54, state/ diff 0). Guvenlik turu + yigin review-06b (18210/13210). C: 42 GB, acik FF yigini yok.
- 2026-11-02 12:40 YIGIN-AC review-06b (18210/13210, FFCORE_VERSION=0.0.0-review-06b, --profile test --profile qdrant); acik FF yigini yok, C: 42 GB. Statik tur (identity, guard, proxy, agent, internal, manifest, parity testleri) okundu.

## R-06B-0002 | 2026-11-02 13:40 | REVIEW-SONUC | K-06b-0010
- Paket/SHA: 06b facade, 45d901b5a9699bf871bddeb40445fd954b8df6ff (istek mesajındaki SHA'da yazım hatası vardı; kanal+git ile doğrulandı). Güvenlik turu + yığın review-06b (18210/13210), imajlar bu SHA'dan derlendi, down -v (YIGIN-KAPA review06b). state/ diff 0.
- Karar: **DUZELT**. BLOCKER 0, MAJOR 2, MINOR 3.
- MAJOR-1: direct yolda mesaj `name`/ekstra alanları, `stop`, `tool_choice`, `response_format` egress'ten geçmeden sağlayıcıya gidiyor (probe: ham e-posta sağlayıcı isteğinde). MAJOR-2: akış çıktı denetimi yalnız kuralın kendi modu enforce iken (politika monitor) atlanıyor: akışsız 400, akışlı sırrı istemciye sızdırıyor; aynı mantık 06a EngineGuard.streams_live'da da var.
- MINOR: (1) tokenize yer tutucuları üretimde geri çevrilmiyor (`<<PII_1>>` istemciye gidiyor); 08 full/C17'ye ertelenmiş, docs'ta yok; ayrıca 134 r2 raporumdaki "detokenize geri açar" cümlem üretim yolunda yanlıştı (yalnız testlerde doğru) — düzeltme rapora yazıldı. (2) "LiteLLM dışa kapalı" için test yok (compose kanıtı var). (3) resume sahipliği notu.
- Geçenler: tam entegrasyon 739 passed + 4 skipped; unit+contract 766 iki profilde; kimlik byte-eşit 403, audit ayrımı, kapsamsız anahtar etkisiz; S7 (runtime imajında openai/jiter yok, lock'ta dev grubunda pinli); S2 iç uç; manifest; parite muafiyetleri gerekçeli.
- NOT_RUN: airgap entegrasyon, lint/smoke/önyüz, Redis-yok kota probe'u. Rapor: state/reviews/06b-r1.md; probe state/reviews/06b-r1-probe.py. Worktree .worktrees/review-06b-r1 temiz doğrulandı ama git worktree remove yine "Permission denied" verdi (--force yok); dizin temizlik listesinde. Dosyalar commit edilmemiş.

## R-06B-0003 | 2026-11-02 13:49 | ACK | K-06b-0014
- REVIEW-ISTEK 06b r2 delta alindi. SHA f4f7766232856bf88ee7a91d0b0c653af89d09ce (45d901b + 2 commit, 13 dosya, state/ diff 0) mevcut. Kisa yigin review-06b (18210/13210, FFCORE_VERSION=0.0.0-review-06b); acik FF yigini yok, C: 47 GB. Statik delta + r1 probe dosyam yeniden.
- 2026-11-02 13:50 YIGIN-AC review-06b (18210/13210, FFCORE_VERSION=0.0.0-review-06b), imajlar f4f7766'dan derleniyor; acik FF yigini yok.

## R-06B-0004 | 2026-11-02 14:35 | DURUM | K-06b-0014
- 06b r2: yigin acik, calisiyor (oturum bosta degildi, tam entegrasyon kosusu suruyor). Probe sonucu: MAJOR-1 kismen kapandi, kalan acik bulgu var (top_p/seed/presence_penalty/frequency_penalty string degerleri saglayiciya ham gidiyor). Tam entegrasyon + unit tamamlaninca REVIEW-SONUC ve YIGIN-KAPA.

## R-06B-0005 | 2026-11-02 14:35 | REVIEW-SONUC | K-06b-0014
- Paket/SHA: 06b r2 delta, f4f7766232856bf88ee7a91d0b0c653af89d09ce (45d901b + 2 commit). Yığın review-06b (18210/13210) imajlar bu SHA'dan derlendi, down -v (YIGIN-KAPA review06b). state/ diff 0.
- Karar: **DUZELT (dar)**. BLOCKER 0, MAJOR 1 (r1 MAJOR-1'in kalanı), MINOR 2. r1 MAJOR-2 ve MINOR 1-3 kapandı.
- Kalan MAJOR: `top_p`, `seed`, `presence_penalty`, `frequency_penalty` metin değeriyle 200 dönüyor ve değer sağlayıcıya ham gidiyor (probe: e-posta fake-llm /_requests'te). Düzeltme: bu dört alanı sayı (bool hariç) olarak doğrula, değilse 400 parameter_not_supported; testi parametrik ekle.
- MINOR: (1) facade'ın kendi agent cevabındaki `annotations` SDK yankısında 400 unsupported_field (çok turlu agent uyumluluğu; cevap-özel alanları kabul edip sağlayıcıya gönderme ya da docs notu). (2) state/pr/06a-egress.md (134 PR'ı) hâlâ "detokenize geri açar" diyor; 06b PR'ında düzeltilmiş ama 134'te düzeltme notu yok.
- Kapananlar: name/stop(liste+string)/response_format/tool_choice/tools/tool_call_id ham e-posta sağlayıcıda yok; bilinmeyen mesaj alanı 400 unsupported_field (400 kabul); user etiketi gitmiyor; kural-enforce akış tamponlu hem facade hem 06a (enforced_at semantiği doğrulandı; varsayılan politika canlı kalıyor); litellm_not_published testi; C11 satırı additive; docs.
- Koşular: tam entegrasyon 744 passed + 4 skipped; unit+contract 777 iki profilde; kendi probe'larım 14 geçti, 4 başarısız (kalan MAJOR). Egress kapalı facade yolu NOT_RUN: kabul edilebilir (gerekçe raporda). Rapor: state/reviews/06b-r2.md; probe 06b-r2-probe.py. .worktrees/review-06b-r1 klasörü hâlâ silinemiyor (önceki tur, Permission denied); r2 worktree'si git worktree remove ile kaldırıldı. Dosyalar commit edilmemiş.

## R-06B-0006 | 2026-11-02 15:19 | ACK | K-06b-0019
- REVIEW-ISTEK 06b r3 statik delta alindi. SHA 1f9c5d79b047b6cd1bb33edeed268f8e7d5ca458 (f4f7766 + 1 commit, 11 dosya, state/ diff 0) mevcut. Statik delta; dusen 4 probe kontrolunu kisa yigin ile kosmak istiyorum, acik yigin yok (C: 50 GB): YIGIN-AC review-06b (18210/13210) birazdan yazilacak.
- 2026-11-02 15:19 YIGIN-AC review-06b (18210/13210, FFCORE_VERSION=0.0.0-review-06b), imajlar 1f9c5d7 SHA ından derleniyor; r2 probe ının dusen 4 kontrolu + yeni negatif probe lar; acik FF yigini yok.

## R-06B-0007 | 2026-11-02 16:05 | REVIEW-SONUC | K-06b-0019
- Paket/SHA: 06b r3 delta, 1f9c5d79b047b6cd1bb33edeed268f8e7d5ca458 (f4f7766 + 1 commit). Statik + kısa yığın review-06b (18210/13210), imajlar bu SHA'dan derlendi, down -v (YIGIN-KAPA review06b). state/ diff 0.
- Karar: **ONAY** (BLOCKER 0, MAJOR 0, MINOR 1). r2 kalan MAJOR ve MINOR-A/B kapandı. C11 donabilir.
- Kapananlar: NUMERIC_PARAMS iki yolda; metin/bool/liste/nesne/aralık dışı/ondalıklı-tamsayı → 400 invalid_parameter + param, değer yansımıyor, sağlayıcıya istek yok, agent yolunda run başlamıyor; r2'nin düşen 4 kontrolü geçiyor; bilinmeyen parametre 400 unsupported_field; yankı alanları (annotations/refusal/audio) 200, sağlayıcıya gitmiyor, dropped_fields kayıtlı, kullanıcı mesajında hâlâ 400; ApiError.param ve C11 additive; 134 PR cümlesi (893d017) düzeltilmiş.
- MINOR-1: `NaN` JSON sabiti aralık denetimini geçiyor (karşılaştırmalar False) ve yakalanmamış ValueError'a (gerçek sunucuda 500) yol açıyor; metin sızıntısı yok. Öneri: `math.isfinite` + birim test. Merge'ü engellemez.
- Not: test_03a_2_read_mode_get_parity, 06b entegrasyon dosyalarından sonra koşunca SecretDecryptError (başka FERNET anahtarıyla şifrelenmiş sağlayıcılar, arka plan uzlaştırması) ile düşüyor; tek başına ve alfabetik sırada geçiyor; delta kaynaklı değil, test-izolasyon FOLLOWUP önerisi. Agent yolunda katı parametre tablosu uyumluluk etkisi docs'ta yazılı.
- Koşular: unit+contract 795 iki profil; hedefli entegrasyon 82 passed + 1 (sıra etkisi); probe 73/75 (2 NaN). Tam entegrasyon bu turda yok (main kapısında). Rapor: state/reviews/06b-r3.md; probe 06b-r3-probe.py. .worktrees/review-06b-r3 ve -r1 dizinleri "Permission denied" ile silinemedi (temiz, --force yok). Dosyalar commit edilmemiş.

## R-137-0001 | 2026-11-02 18:07 | ACK | K-137-0007
- REVIEW-ISTEK fix/04a-gate2-headings alindi. SHA 6c0271846e26d7d2241827348c0b2fe697e73e7f (baz d365811, 3 commit, 3 dosya, state/ diff 0) mevcut. Statik + kisa yigin review-137 (18240/13240, postgres+redis). C: 112 GB, acik FF yigini yok.
- 2026-11-02 18:08 YIGIN-AC review-137 (18240/13240, FFCORE_VERSION=0.0.0-review-137 = 0.0.0-main etiketi, kod worktree salt-okunur; yalniz postgres+redis); acik FF yigini yok, C: 112 GB.

## R-137-0002 | 2026-11-02 18:55 | REVIEW-SONUC | K-137-0007
- Paket/SHA: fix/04a-gate2-headings, 6c0271846e26d7d2241827348c0b2fe697e73e7f. Yığın review-137 (postgres+redis) açıldı ve down -v ile kapatıldı (YIGIN-KAPA review137). state/ diff 0.
- Karar: **ONAY** (BLOCKER 0, MAJOR 0, MINOR 0). M3 ingest önkoşulu kapanabilir.
- Kanıt: unit+contract 878 iki profil; test_19 + 04a entegrasyonu iki profilde 50 passed + 3 skipped (test_19 sayıları indexed 4 / skipped 1 / gate2:boilerplate 1 assert edildi). Bağımsız fark testi (59.831 gövde, main vs yeni): yeni sayı her zaman ≤ main, fark tam olarak fence dışı başlık sayısı, karar farkı yalnız code_heavy→ok/no_prose yönünde, başlıksız gövdede birebir aynı, fence çizgisi main'de de hiç kod değil. Fence'siz gerçek kod (6/8) hâlâ code_heavy. Kırmızı→yeşil kayıtları ve "Kalan riskler" dürüst; docs A′'yi anlatıyor.
- Önemli not (kapsam dışı, ön-var olan): Kapı 2 düzyazı kontrolü yalnız TR_STOPWORDS kullanıyor; kısa İngilizce sayfa (başlıklı ya da başlıksız) main'de de yenide de `no_prose` ile eleniyor. Ayrı, öncelikli FOLLOWUP öneririm (04a sahibi); M3 aşama 0 raporunda gate2:no_prose sayısına bakılmalı.
- Diğer notlar: fence takibi basit aç/kapa (karışık işaretler, tek satırlık ```…``` yalnız gevşek yönde/main'e eşit), `_HEADING_LINE` NBSP/girintiyi de başlık sayıyor (gevşek yön).
- Rapor: state/reviews/04a-gate2-headings-r1.md. Worktree temiz doğrulanıp git worktree remove ile kaldırıldı. Dosyalar commit edilmemiş.

## R-06b2-0001 | 2026-11-02 20:45 | ACK | K-06b2-0006
- REVIEW-ISTEK 06b-2 (dis agent, kind: external) alindi. SHA 2342bc296a633a2304eaa109eda498c2f293a38f mevcut (feat/06b-2-external-agent). Guvenlik turu + yiginli inceleme; rapor state/reviews/06b-2-r1.md.
- 2026-11-02 20:45 YIGIN-AC review-06b2 (18250/13250, FFCORE_VERSION=0.0.0-review-06b2, --profile test --profile qdrant; imajlar bu SHA'dan derlenecek); acik FF yigini yok, C: 108 GB.

## R-06b2-0002 | 2026-11-02 21:45 | REVIEW-SONUC | K-06b2-0006
- Paket/SHA: 06b-2 dış agent, 2342bc296a633a2304eaa109eda498c2f293a38f. Yığın review-06b2 (18250/13250), imajlar bu SHA'dan derlendi; 2026-11-02 21:45 YIGIN-KAPA review06b2 (down -v, imajlar silindi). state/ diff 0.
- Karar: **DUZELT (dar)** — BLOCKER 0, MAJOR 2, MINOR 7.
- MAJOR-1: derin iç içe JSON cevap (<64 KiB) json.loads'ta RecursionError; yalnız ValueError yakalanıyor -> 500, external_agent_call audit satırı yok, akış [DONE]'sız kopuyor. Düzeltme: except (ValueError, RecursionError) -> invalid_answer + test.
- MAJOR-2: manifest import var olan dış agent anahtarına native sürüm ekliyor (hedef kind denetimi yok); analist+edit ile 200 new_version, sonra runs channel=test version=1 -> runs tablosunda dış agent'a bağlı koşu (S1/S3 ihlali, docs çelişkisi). Düzeltme: import'ta hedef kind=external ise 422 external_agent_not_available (dry-run dahil) + test; savunma olarak runs.py test/version yolunda red (touch-zone kararı senin).
- MINOR: (1) platform servisleri (litellm, langfuse-web, mcp-*, airgap Ollama) dış agent hedefi olabiliyor -> iç modeli kota/Langfuse dışı kullanma; KARARLAR:172 iç hedefi bilinçli kılıyor, dar boşluk kalıyor; KARAR: A platform servis host'larını reddet (önerim) / B ayrı EXTERNAL_AGENT_HOSTS / C kabul+FOLLOWUP. (2) base_url sorgu dizgesi/fragment kabul (yol bozuk, değer API+audit'te). (3) analist genel PATCH/DELETE ile dış agent'ı silip anahtarını devralabiliyor. (4) PUT yalnız base_url değişince eski anahtar yeni origin'e gidiyor. (5) upstream alan adları log'a yazılıyor (maskeli, satır kaçışlı; yine içerik). (6) facade_external <-> api.agents döngüsel import. (7) akışta istemci kopunca audit satırı yok.
- SSRF matrisi tam ve yeşil: 31 URL kayıtta red, güncelleme/yayın/çağrı anı denetimi, DNS rebinding (karışık ve çağrı anı özel), 302/307 tek istek, OFFLINE, chunked 64 KiB+, zaman aşımı; tool_calls/function_call/content dizisi 502, sahte <<PII_1>> açılmıyor; anahtar log/audit/API'de yok.
- Kanıt: unit+contract 894 iki profil; hedefli entegrasyon llmaas 93 / airgap 91+2 skip; probe'lar 06b2r1-probe*.log. Bağımsız 5 ajanlı sınama (iç servis MAJOR'ını MINOR'a indirdi; yeni adayları yığında doğruladım).
- Rapor: state/reviews/06b-2-r1.md. Worktree temiz doğrulandı, git kaydından çıktı ama dizin "Permission denied" ile silinemedi (--force yok; temizlik listesine .worktrees/review-06b2-r1). Dosyalar commit edilmemiş.
