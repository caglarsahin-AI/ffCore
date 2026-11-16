# Arşiv: inceleyici · 09

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-09-0001 · 2026-11-04 22:16 · → koordinator · ACK
Paket: 09-1 r1   Cevap: K-09-0010
REVIEW-ISTEK alındı. SHA doğrulandı: d4a2f020c898f77b3f22e1fe42cbbb651030dcf8 (feat/09-evaluation; merge-base main 80bba17, 8 commit, 38 dosya +4992/-67, state/ 0, migration 09_0001). Worktree .worktrees/review-09-1-r1 (temiz). Güvenlik turu + tam yığın.

### R-09-0002 · 2026-11-04 22:16 · → koordinator · YIGIN-AC
Yığın: review09 (COMPOSE_PROJECT_NAME), BACKEND_PORT 18300, FRONTEND_PORT 13300, --profile test --profile qdrant (langfuse, mcp, ticket-desk dahil), dalın .env.test'i, --pull never, FAKE_EMBED=1 (ağırlık yok, ffcore-09 ile aynı). ffcore-09 kapalı; açık FF yığınları ffcore-08t1b + review09 (üç sınırı içinde). Disk boş 107 GB. Kapanış down -v + YIGIN-KAPA.

### R-09-0003 · 2026-11-04 23:22 · → koordinator · REVIEW-SONUC
Paket: 09-1 r1   Cevap: K-09-0010
**DEGISIKLIK** (d4a2f020c898f77b3f22e1fe42cbbb651030dcf8). BLOCKER 0, MAJOR 4, MINOR 11, NOTE 8. Rapor state/reviews/09-1-r1.md (güvenlik turu ayrı bölüm).
- Çalışanlar:
  - judge metni gerçek EgressGuard + yerleşik politika ile maskeli (probe: TC/e-posta/IBAN/telefon → `<<PII_n>>`, model ham değer görmüyor); background yuva, bozuk çıktı skor değil hata; Langfuse değerlendiricisi yok.
  - scoreIds koruyucusu, S8 (comment'te cevap metni yok), proje izolasyonu, otomatik onay yok.
  - 06a çıkarımı davranış aynı.
  - migration gidiş-dönüş tek head; seed-eval idempotent.
- MAJOR-1: sql_result reddedilen ya da hiç çalışmamış SQL'i yeniden çalıştırıyor (tool_call onaydan önce kaydediliyor; load_facts approval/tool_result denetlemiyor); agent'a bağlı olmayan proje aracını da kullanabiliyor. 07 kapısı atlanıyor; docs tersini söylüyor.
- MAJOR-2: ilerletici tick'leri kilitsiz örtüşüyor (unique yalnız zaman damgası): çift judge, item_runs son-yazan-kazanır. Uzun tick mark_listening'i geciktiriyor, koşular abandoned.
- MAJOR-3: approval_required/waiting_user iptali commit'lenip not commit'lenmeden hata olursa madde başarısız sayılıyor (NOT_RUN_CODES yalnız approval_expired); geri almada puanlananlar yeniden judge'a gidiyor.
- MAJOR-4: sınav suite yapılandırmasını dondurmuyor; koşu sürerken PATCH scorer/eşik/approve_tools'u değiştiriyor; 09-2 kapısı bu passed'e güvenecek.
- MINOR:
  - (1) parse_judge yedeği ilk `score: n`'yi alıyor, alıntılanan sahte skor kabul (probe: 5 döndü); kod çitli JSON hata; rubrikte sınırlayıcı yok.
  - (2) madde×tekrar sınırı yok, POST içinde eşzamanlı başlatma, queued asılı.
  - (3) boş beklenende judge; repeat birleştirme.
  - (4) SQL reddi boş sonuç + audit is_error=false.
  - (5) approve_tools=false iptali onay satırını bırakıyor, yarış, audit yok.
  - (6) onay sonrası koşu interaktif kuyruğa.
  - (7) SuiteUpdate doğrulayıcısız / null.
  - (8) Langfuse taşıma hataları eşlenmiyor, hata sayacı sıfırlanmıyor.
  - (9) **08-tam-1b birleşme tehlikesi:** judge EgressGuard'da ner= yok; 1b sonrası llmaas'ta her judge `judge_failed:ner_not_configured`; ikinci merge edilen dal HttpNer eklemeli.
  - (10) docs/yorumlar (approved-only, otomatik onay yorumu).
  - (11) dataset adında önekten sonra desen yok; 09-2'de yol bölümü olunca `..` ile başka projeye geçebilir (httpx normalleştiriyor, denendi).
- NOTE-2 09-2 kapısı için: çoğu madde not_run iken passed=true olabiliyor (complete=false); kapı complete ya da asgari oran istemeli.
- Koşular (22:21-23:18, tam yığın review09 + plan/18 katmanı):
  - make test 1602/1602 iki profil; lint temiz.
  - test-int llmaas 870 passed / 13 skipped, airgap 868 / 15.
  - alembic gidiş-dönüş; seed + seed-eval ×2.
  - RUN_EVAL_STACK 8/8; smoke passed.
  - fake-llm 200 judge isteği ham TC/e-posta yok.
  - NOT_RUN: gerçek model judge tutarlılığı; MAJOR'ların çalışma zamanı probe'u (kod yolu + ayrı doğrulayıcı ile teyit).
- Dosyalar commit edilmedi: rapor, 09-1-r1-probe.py, evidence 09-1-r1-*, kanal.

### R-09-0004 · 2026-11-04 23:22 · → koordinator · YIGIN-KAPA
Yığın review09 `down -v` (23:22); konteyner 0, volume 0. Worktree .worktrees/review-09-1-r1 temiz, `git worktree remove` başarılı.

### R-09-0005 · 2026-11-05 00:14 · → koordinator · ACK
Paket: 09-1 r2 (delta)   Cevap: K-09-0015
REVIEW-ISTEK alındı. SHA doğrulandı: e13ec6b4efed38787e4d37a7dd134dcf31e11472 (d4a2f02 üstüne 2 commit: 528f09b düzeltmeler, e13ec6b docs; 23 dosya +1686/-334; merge-base main 80bba17; state/ 0). Worktree .worktrees/review-09-1-r2 (temiz). Not: 1b r3 PR-HAZIR henüz yok; bu tura başlıyorum, gelince araya 1b r3 diff teyidini alırım.

### R-09-0006 · 2026-11-05 00:14 · → koordinator · YIGIN-AC
Yığın: review09, 18300/13300, --profile test --profile qdrant (langfuse, mcp, ticket-desk dahil), dalın .env.test'i + plan/18 senaryo katmanı (e2e.env), --pull never. Açık FF yığınları: review09 (+ isci-a ffcore-08t1b açılırsa iki). Disk boş 102 GB. Kapanış down -v + YIGIN-KAPA.

### R-09-0007 · 2026-11-05 00:49 · → koordinator · DURUM
Paket: 09-1 r2   Cevap: koordinatör ortam bildirimi (Docker)
Kesinti kaydedildi: `make test` llmaas 00:46'da %97'de takıldı; kapı betiğini 00:47'de durdurdum. Statik delta denetimi bitti, taslak rapor state/reviews/09-1-r2.md (karar taslağı DEGISIKLIK).
- r1 MAJOR-2/3/4 ve çoğu MINOR kapandı.
- Yeni MAJOR:
  - (r2-1) reddedilen run_sql madde düzeyinde not_run değil, "nothing_scored" başarısızlığı (karar B-09-0022 A'ya aykırı).
  - (r2-2) 600 sn tick zaman aşımı + süresiz yuva bekleyişi: airgap'te pencere kapanınca sınav advance_failed:TimeoutError.
  - (r2-3) mcp-sql `sql_error:` metni başarılı tool_result sayılıyor; agent'ın almadığı satırla puan.
- Docker yeniden başlayınca yığını yeniden açıp kapıları ve probe'ları baştan koşacağım.

### R-09-0008 · 2026-11-05 02:56 · → koordinator · YIGIN-AC
Paket: 09-1 r2   Cevap: K (Docker geri geldi, 02:53)
review09 `down -v --remove-orphans` ile silindi (02:54), aynı ayarlarla (18300/13300, test+qdrant profilleri, e2e.env katmanı, --pull never) baştan açılıyor; kapılar ve probe'lar baştan koşacak. Disk boş 106 GB.
DUZELTME (R-09-0007'ye): 00:47'deki durdurma yalnız görev kaydını kapattı; kapı betiğinin bash süreci yaşamaya devam etti ve Docker dönünce (02:53-02:55) kendiliğinden yeniden başlamış yığına karşı adım koşmaya devam etti (state/evidence/09-1-r2-* dosyalarından bazıları o koşunun çıktısıydı). Süreci (PID 106724) ve kendi tools-run konteynerlerimi adlarıyla durdurdum. Yeni koşu bu kanıt dosyalarının üzerine yazacak; eski içerik geçersiz.

### R-09-0009 · 2026-11-05 10:09 · → koordinator · REVIEW-SONUC
Paket: 09-1 r2   Cevap: K-09-0015
**DEGISIKLIK e13ec6b4efed38787e4d37a7dd134dcf31e11472.** Rapor state/reviews/09-1-r2.md. BLOCKER 0, MAJOR 3, MINOR 8, NOTE 9.
- r1: MAJOR-2/3/4 ve çoğu MINOR KAPANDI. MAJOR-1'in yeniden çalıştırma yarısı kapandı, sınıflama yarısı açık.
- MAJOR:
  - (r2-1) reddedilen `run_sql` madde düzeyinde not_run değil (B-09-0022 A).
  - (r2-2) 600 sn tick zaman aşımı + süresiz yuva bekleyişi → airgap'te `advance_failed:TimeoutError`.
  - (r2-3) `sql_error:` metni çalışmış SQL sayılıyor.
- Yeni MINOR-r2-8: exam-stack testi skorları yoklamıyor. İki koşuda da düştü, her seferinde başka bir skor eksikti; saatler sonra skorlar tamdı (Langfuse gecikmesi). 09-2 kapısı için merge öncesi öneri.
- Probe P1-P4 geçti: judge'a ham PII gitmiyor; çıktı ayrıştırma adversarial girdilerde doğru; kilit çekişme, bırakma, yenileme ve eski kilit durumlarında doğru.
- Kapılar: unit iki profil 1623, lint, test-int llmaas 877, alembic, seed, seed-eval idempotent ve smoke yeşil.
- **ENV önerisi:** Docker yeniden başlatmasından sonra review09 ağında aralıklı DNS düşmesi (`postgres` çözülmüyor, redis zaman aşımı). Yalnız agent-worker-bg ve tools konteynerinde görüldü; agent-worker-bg 7 kez yeniden başladı. airgap test-int iki koşuda da yalnız 09 dışı testlerde kırmızı → NOT_RUN (ortam); r3 tam yığında yeniden.
- Kesinti 00:46-02:53 rapora yazıldı.
- worktree git'ten kaldırıldı, dizin Windows izni yüzünden diskte kaldı (temizlik listesine; `--force` yok).

### R-09-0010 · 2026-11-05 10:09 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans` (10:08): 0 konteyner, 0 hacim. Açık inceleyici yığını yok. Disk boş 106 GB.

### R-09-0011 · 2026-11-05 12:04 · → koordinator · ACK
Paket: 09-1 r3   Cevap: K-09-0020
472e04faffb8d6cb75b9ea1c77ac75098c7a5e40 doğrulandı (e13ec6b atası; main merge d0b1d76 + 6 commit). Merge-base main 63ffb16'ya göre 48 dosya, `state/` 0; delta `d0b1d76..472e04f` 18 dosya. Worktree `.worktrees/review-09-1-r3` (temiz). Statik inceleme başladı; review-09 koşuları 1c-a main kapısı bitince (KARARLAR üç yığın sınırı).

### R-09-0012 · 2026-11-05 12:17 · → koordinator · DURUM
Paket: 09-1 r3   Cevap: K-09-0020
Statik delta bitti, taslak state/reviews/09-1-r3.md (karar taslağı DEGISIKLIK; MAJOR 1, MINOR 5, NOTE 15). r2 MAJOR-1/3 ve MINOR'ların çoğu kapandı; main merge temiz; judge `ner=HttpNer` testli.
- **MAJOR-r3-1:** tick bütçesine hiç sığmayan madde (repeat × yavaş judge ya da tek 570-600 sn çağrı) her tick kesilip sayaçsız yeniden deneniyor. Commit'siz tick yine `failures_key`'i siliyor (`worker_tick.py:231`; "commit'leyen tick sıfırlar" kararına aykırı). Sınav sonsuza dek `running`.
- **KARAR-GEREK:**
  - **A (önerilen)** madde başına ardışık süre kesmesi sayacı → `MAX_ATTEMPTS`'ta `error(judge_out_of_time)`, sayaç yalnız commit'li tick'te sıfırlanır;
  - B koşu başına judge sonucu saklama (A ile birlikte);
  - C açılışta `LLM_CALL_TIMEOUT_S` < tick payı denetimi.
- Koşular "koşu serbest" bekliyor: işçinin imajı `ffcore/backend:0.0.0-09` 472e04f ile dosya dosya eşleşti (168 py, fark 0); `--no-build --pull never`.

### R-09-0013 · 2026-11-05 12:29 · → koordinator · YIGIN-AC
Paket: 09-1 r3   Cevap: K-08T1C-0014 (koşu serbest)
review09, 18300/13300, `--profile test --profile qdrant` + plan/18 katmanı, işçinin `0.0.0-09` imajı, `--no-build --pull never`. Açık FF yığını yok → bu tek. Disk boş 105 GB. Kapanış down -v + YIGIN-KAPA.

### R-09-0014 · 2026-11-05 13:01 · → koordinator · REVIEW-SONUC
Paket: 09-1 r3   Cevap: K-09-0020 / K-09-0022
**DEGISIKLIK 472e04faffb8d6cb75b9ea1c77ac75098c7a5e40.** Rapor state/reviews/09-1-r3.md. BLOCKER 0, MAJOR 1, MINOR 5, NOTE 15.
- Kapanan: r2 MAJOR-1/3 ve MINOR-r2-1/2/3/4/7/8; judge `ner=HttpNer` (MINOR-9). main merge temiz; tek head 09_0001.
- Açık: MAJOR-r3-1 (madde başına süre kesmesi sayacı yok → sınav sonsuz `running`), senin kararın A.
- MINOR:
  - r3-1 judge çağrı sınırı yumuşak, docs "at most" diyor;
  - r3-2 son süre sınavlar arasında adaletsiz;
  - r3-3 docs `make seed` yerine `make seed-prompts`;
  - r3-4 judge NER kesintisi testsiz;
  - r3-5 docs NER bağımlılığı.
  - r3-3 ve r3-4 merge öncesi önerilir.
- Kapılar (işçinin doğrulanmış `0.0.0-09` imajı, build yok): unit 1712 ×2, lint, test-int 892 / 890, alembic, seed, seed-eval idempotent, exam-stack 8/8, smoke, probe P0-P4 yeşil. DNS hatası 0.
- NOT_RUN: `GUARDRAIL_EGRESS_NER=true` canlı yığın (ağırlık yok).

### R-09-0015 · 2026-11-05 13:01 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans` (13:01): 0 konteyner, 0 hacim. Worktree git kaydından kaldırıldı; dizin Windows izni yüzünden diskte kaldı (temizlik listesine, `--force` yok). Açık inceleyici yığını yok.

### R-09-0016 · 2026-11-05 13:28 · → koordinator · ACK
Paket: 09-1 r4   Cevap: K-09-0025
b424013f02a1c88955e7d9e31a513625234d750a doğrulandı (472e04f atası; 3 commit, 9 dosya; merge-base main'e göre `state/` 0). Delta incelemesi başladı. Yığın kararı: işçi imajı commit ile eşleşirse review09 tam yığın ama yalnız hedefli koşular; eşleşmezse yalın yığın (build yok, PROSES-175).

### R-09-0017 · 2026-11-05 13:29 · → koordinator · YIGIN-AC
review09, 18300/13300, tam yığın + plan/18 katmanı. İşçinin `0.0.0-09` imajı b424013 ile dosya dosya eşleşti (168 py, fark 0); `--no-build --pull never`. Koşular: unit ×2, lint, hedefli test-int ×2 (09/05a), alembic heads, seed, seed-eval ×2, exam-stack, smoke, probe. Açık FF yığını: bu tek. Kapanış down -v + YIGIN-KAPA.

### R-09-0018 · 2026-11-05 13:45 · → koordinator · REVIEW-SONUC
Paket: 09-1 r4   Cevap: K-09-0025
**DEGISIKLIK b424013f02a1c88955e7d9e31a513625234d750a.** Rapor state/reviews/09-1-r4.md. BLOCKER 0, MAJOR 1, MINOR 1, NOTE 14.
- KAPANDI:
  - MAJOR-r3-1 A: madde başına sayaç kalıcı, `judge_out_of_time`, sayaç yalnız commit'li tick'te siliniyor; `start_items` bir kez koşuyor, döngü açmıyor.
  - NER kesintisi → `not_run(ner_unavailable)`.
  - MINOR-r3-1 katı sınır; r3-3/5 docs; "09-2'ye kalan" listesi tam.
- **MAJOR-r4-1 (KARAR-GEREK):** tick'in ortak son süresi önceki sınavlarca tüketilince sonraki sınavın ilk maddesi taze `Budget` (`started=0`) ile yine başlıyor, `timeout(0.0)` ile kesiliyor ve sayaca yazılıyor. Kesme commit'i `updated_at`'ı ilerlettiği için `ORDER BY updated_at` aynı sınavı yine sona koyuyor. 5 tick'te yavaş olmayan madde `judge_out_of_time`: yanlış sonuç. Yığında probe: son süre geçmişken `may_judge(1)=True`, `time_left=0.0`.
  - **A (önerilen)** ilk madde de `time_left >= call_s × calls` değilse başlamaz (sınav bekler, sayılmaz);
  - B kesme yalnız planlanan süre verildiyse sayılır ve commit edilir;
  - C sınav başına süre payı.
  - Test: iki sınav tek son süre.
- MINOR-r4-1: modül docstring'lerinde eski tick kuralı.
- Kapılar (işçinin doğrulanmış imajı, build yok): unit 1717 ×2, lint, hedefli test-int 36 ×2, alembic tek head, seed-eval idempotent, exam-stack 8/8, smoke, probe P0-P4. DNS hatası 0.
- NOT_RUN: tam test-int (delta turu).

### R-09-0019 · 2026-11-05 13:45 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans` (13:45): 0 konteyner, 0 hacim. Worktree kaldırıldı (dizin de silindi). Açık inceleyici yığını yok.

### R-09-0020 · 2026-11-05 14:17 · → koordinator · ACK
Paket: 09-1 r5   Cevap: K-09-0030
b443a54b15688404e4fb63bcdc0ded32482049de doğrulandı (b424013 atası; 5 commit, 12 dosya; merge-base main'e göre `state/` 0). Worktree `.worktrees/review-09-1-r5` (temiz).

### R-09-0021 · 2026-11-05 14:17 · → koordinator · YIGIN-AC
review09, 18300/13300, tam yığın + plan/18 katmanı. İşçinin `0.0.0-09` imajı b443a54 ile dosya dosya eşleşti (168 py, fark 0); `--no-build --pull never`. Koşular: unit ×2, lint, **tam test-int ×2**, alembic, seed, seed-eval ×2, exam-stack, smoke, probe P0-P4 + r4 bütçe probe'u. Açık FF yığını: bu tek. Kapanış down -v + YIGIN-KAPA.

### R-09-0022 · 2026-11-05 14:54 · → koordinator · REVIEW-SONUC
Paket: 09-1 r5   Cevap: K-09-0030
**DEGISIKLIK b443a54b15688404e4fb63bcdc0ded32482049de.** Rapor state/reviews/09-1-r5.md. BLOCKER 0, MAJOR 1, MINOR 1, NOTE 8.
- KAPANDI:
  - MAJOR-r4-1 A: ilk madde de planlanan süreyi istiyor; sığmazsa commit yok, sayaç yok, `updated_at` sabit; iki sınavlı test var; yığın probe'unda son süre geçmişken `may_judge(1)=False`.
  - ek (`planned_exceeds_tick_budget`); B (`EVAL_JUDGE_CALL_S` C12 additive, 422 `eval_plan_exceeds_tick`, zamanlayıcı hâlâ `time_left`).
  - r3 A korunuyor; docstring'ler ve NOTE-1/5/9.
- **MAJOR-r5-1 (KARAR-GEREK):** plan bütçeye eşit ya da tick yükü kadar altındaysa (ör. `EVAL_JUDGE_CALL_S=570`, `le=570` izin veriyor, repeat 1; ya da 285 × 2) `exceeds_tick` (`>`) bitirmiyor, `may_judge` hiç başlatmıyor. Sınav sonsuza dek `running`. Yığında probe: plan 570 → `exceeds_tick=False`, `may_judge=False`.
  - **A (önerilen)** tek "kullanılabilir pencere" sabiti (ör. 570 − 30 sn) `exceeds_tick`, 422 ve `EVAL_JUDGE_CALL_S` üst sınırında;
  - B o tick'in `time_left`'ine göre bitirme.
- MINOR-r5-1: çok sınavda kesilen madde sona düşüyor, tahminden yavaş ama sağlıklı judge 5 kısmi kesmede `judge_out_of_time` olabiliyor (öneri: `full_window` işareti ya da docs'ta "üst uç tahmin").
- Kapılar (işçinin doğrulanmış imajı, build yok): unit 1724 ×2, lint, **tam test-int 895 / 893**, alembic tek head, seed-eval idempotent, exam-stack 8/8, smoke, probe P0-P4. DNS hatası 0.

### R-09-0023 · 2026-11-05 14:54 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans` (14:54): 0 konteyner, 0 hacim. Worktree kaldırıldı (dizin de silindi). Açık inceleyici yığını yok.

### R-09-0024 · 2026-11-05 15:23 · → koordinator · ACK
Paket: 09-1 r6   Cevap: K-09-0035
9def741db3eb911c4e4e29b6dbceda0ce9a89fb9 doğrulandı (b443a54 atası; 3 commit, 11 dosya; merge-base main'e göre `state/` 0). Worktree `.worktrees/review-09-1-r6` (temiz).

### R-09-0025 · 2026-11-05 15:23 · → koordinator · YIGIN-AC
review09, 18300/13300, tam yığın + plan/18 katmanı (exam-stack için). İşçinin `0.0.0-09` imajı 9def741 ile dosya dosya eşleşti (169 py, fark 0); `--no-build --pull never`. Koşular: unit ×2, lint, hedefli test-int ×2 (09/05a), alembic heads, seed, seed-eval ×2, exam-stack, smoke, probe P0-P4, 540 sınır probe'u. Açık FF yığını: bu tek.

### R-09-0026 · 2026-11-05 15:38 · → koordinator · REVIEW-SONUC
Paket: 09-1 r6   Cevap: K-09-0035
**ONAY 9def741db3eb911c4e4e29b6dbceda0ce9a89fb9.** Rapor state/reviews/09-1-r6.md. BLOCKER/MAJOR 0, MINOR 2 (aynı kök), NOTE 8.
- KAPANDI:
  - `TICK_PLAN_S=540` tek kaynak üç yerde (config `le` sabitten). Yığın probe'u: 540 / 539 / 2 × 270 başlar, 541 / 2 × 271 kodlu biter; beklemede kalan yok.
  - Kesme sayma `min(LLM_CALL_TIMEOUT_S × calls, 540)`; kısmi kesme commit'siz, sıra önde. K-09-0034 testi var.
  - 422 HTTP testi; docs NOTE'ları; `runtime/worker.py` additive.
- **PR not 3 pozisyonum: MINOR, MAJOR değil.** Ön koşul her tick ilk maddeden önce >30 sn iş (kalıcı altyapı bozulması). Ama risk not 3'ten geniş: aynı koşulda airgap'te (`LLM_CALL_TIMEOUT_S=600`) asılı judge her tick "kısmi" kesiliyor, sayılmıyor, commit yok, yalnız info logu; sınav sessizce sonsuz `running` ve tick başına ~539 sn judge harcıyor. Fail-loud kuralı gereği öneri:
  - **A** merge öncesi küçük commit: ilk sınavın penceresi < `TICK_PLAN_S` ise ölçülen yükle `warning` logu + docs:176 "arada hiçbir şey sonsuza dek beklemez" cümlesine koşul + FOLLOWUP-176 genişletmesi;
  - B yalnız FOLLOWUP + docs;
  - C ilk sınavın ilk maddesindeki kesme her zaman sayılır (09-2).
  - B seçilirse ONAY değişmez.
- Kapılar (işçinin doğrulanmış imajı, build yok): unit 1730 ×2, lint, hedefli test-int 42 ×2, alembic tek head, seed-eval idempotent, exam-stack 8/8, smoke, probe P0-P4. DNS hatası 0.

### R-09-0027 · 2026-11-05 15:38 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans` (15:37): 0 konteyner, 0 hacim. Worktree kaldırıldı (dizin de silindi). Açık inceleyici yığını yok.

### R-09-0028 · 2026-11-05 15:44 · → koordinator · ONAY-TEYIT
Paket: 09-1 r7   Cevap: K-09-0039
**ONAY-TEYIT 331e2e911a5f86d446ed134fcb928e70e8734e59** (9def741 atası; 2 commit, 3 dosya). Rapor 09-1-r6.md "r7 teyidi".
- `_check_overhead` tick başına bir kez, ilk sınavdan önce; yalnız `overhead_s`; sınavsız tick'te uyarı yok.
- Test gerçek `tick()`'i sahte saatle sürüyor (aşım → tek uyarı, normal → yok); sıra test → kod. docs koşulu eklendi.
- NOTE-r7-1: ölçüm `_advance_one` ön işini kapsamıyor (dar kenar, bilgi).
- Yalnız okuma.

### R-09-0029 · 2026-11-05 17:04 · → koordinator · ACK
Paket: 09-2 r1   Cevap: K-09-0046
892bdfecc83f22ae1ac70347bd7f796beef324b2 doğrulandı (merge-base main 30df97f; 9 commit, 22 dosya +1869/-21; `state/` 0). Worktree `.worktrees/review-09-2-r1` (temiz). Statik inceleme başladı; review09 yığını "koşu serbest" ziline kadar açılmıyor.

### R-09-0030 · 2026-11-05 17:19 · → koordinator · YIGIN-AC
Paket: 09-2 r1   Cevap: koşu serbest
review09, 18300/13300, tam yığın + plan/18 katmanı. İşçinin `0.0.0-09` imajı 892bdfe ile dosya dosya eşleşti (172 py, fark 0); `--no-build --pull never`. Koşular: unit ×2, lint, **tam test-int ×2**, alembic, seed, seed-eval ×2, exam-stack, smoke, probe P0-P4, yeni probe'lar (yayın kapısı 409/force/audit/rollback; from-run maskeleme + Langfuse öğesi). Açık FF yığını: bu tek. Kapanış down -v + YIGIN-KAPA.

### R-09-0031 · 2026-11-05 19:42 · → koordinator · DURUM
Paket: 09-2 r1   Cevap: koordinatör (sessizlik sorusu)
Takılı değil, yığın yavaş.
- Kapılar arka planda sürüyor: unit 1755 ×2, lint ve test-int llmaas bitti. test-int airgap normal ~10 dk yerine 52 dk sürdü; seed-eval-1 52 dk (18:48 → 19:40). Şu an exam-stack (19:40), sonra smoke ve yeni probe'lar.
- Yavaşlık: `review09-langfuse-clickhouse-1` sürekli ~%99 CPU; başka FF yığını yok. Neden araştırılmadı.
- Bulunanlar:
  - test-int llmaas 1 failed: `test_03a_2_read_mode_get_parity`. Yeni `GET /eval-runs/compare` parametresiz 422; deterministik, kod bulgusu (MAJOR).
  - airgap'te aynısı + `test_09_advance` içindeki 5 zaman duyarlı test (0,2-0,4 sn son süreli r2/r3/r5/K-34 testleri). Yük altında; tek başına yeniden koşacağım.
- Statik: MAJOR (draft düzenlenince eski sınav kapıyı açıyor) + MINOR'lar.
- REVIEW-SONUC tahmini 20:30.
- 1c-b statik okuması bitti (MAJOR yok); `-m models` yeni SHA ve 09-2 sonucundan sonra.

### R-09-0032 · 2026-11-05 19:52 · → koordinator · REVIEW-SONUC
Paket: 09-2 r1   Cevap: K-09-0046
**DEGISIKLIK 892bdfecc83f22ae1ac70347bd7f796beef324b2.** Rapor state/reviews/09-2-r1.md. BLOCKER 0, MAJOR 2, MINOR 12, NOTE 15.
- **MAJOR-1 (KARAR-GEREK):** taslağın sınavı, taslak sonradan düzenlense de kapıyı açıyor (kapı sınavı yalnız `agent_version_id` ile eşliyor, taslak düzenlenebilir, sınav tanımı tutmuyor). Force ve iz olmadan atlatma.
  - **A (önerilen):** sınav başında tanım özeti `eval_runs.config`'e, kapıda farklıysa 409 `stale_exam` (migration yok);
  - B sınavlı taslağı düzenlemeyi reddet;
  - C `updated_at > started_at`.
- **MAJOR-2:** yeni `GET /eval-runs/compare` `test_03a_2_read_mode_get_parity`'yi kırıyor (parametresiz 422). Deterministik; tam test-int iki profilde kırmızı. İşçi yalnız hedefli koştu. `PARITY_EXEMPT`'e gerekçeyle ya da teste `a`/`b`.
- **Merge öncesi önerilen MINOR'lar:**
  - (1) yalnız boşluktan `force_reason` kabul (canlı probe 200);
  - (9) from-run'da `expected` Langfuse'a maskesiz;
  - (12) zaman duyarlı `test_09_advance` testleri kararsız: yük altında 5 düştü; tek başına `slow_judge_spreads` 2 koşunun 1'inde düştü, `q2` kesilip yeniden judge ediliyor ama test tek çağrı bekliyor.
- **Canlı probe'lar:** kapı 409 `no_exam` / 403 / 422 / 422 / 200 + `eval_gate_forced` audit içeriksiz. from-run'da TC ve e-posta maskeli, audit temiz, ikinci kayıt idempotent. **Kişi adı NER kapalı yığında Langfuse öğesine açık gidiyor:** karar gereği (yalnız regex), kod bulgusu değil; NER'siz kurulumda bilinçli bir veri sınırı.
- Sapma notu 2 pozisyonu: bu PR için kabul; `error.details` additive FOLLOWUP.
- Kapılar: unit 1755 ×2, lint, alembic, seed-eval, exam-stack 8/8, smoke, P0-P4 yeşil.
- **Ortam:** langfuse-clickhouse ~%99 CPU, test-int airgap 52 dk.

### R-09-0033 · 2026-11-05 19:52 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans` (19:51): 0 konteyner, 0 hacim (geçici probe superadmin'leri de silindi). Worktree kaldırıldı. Açık inceleyici yığını yok. Sıradaki: 1c-b r1b (5e9a688).

### R-09-0034 · 2026-11-05 21:05 · → koordinator · ACK
Paket: 09-2 r2   Cevap: K-08T1C-0030 (REVIEW-ISTEK bekleniyor)
4e2fcadd4d8dc0c566ec47ce0bd27851ac6e9835 doğrulandı (892bdfe atası; 10 commit, 23 dosya +1002/-149; merge-base main'e göre `state/` 0). Worktree `.worktrees/review-09-2-r2`. Statik delta okuması başladı (KARARLAR "09-2 r1 kararları"); koşular 1c-b main kapısı bitince "koşu serbest" ile.

### R-09-0035 · 2026-11-05 21:32 · → koordinator · YIGIN-AC
Paket: 09-2 r2   Cevap: K-08T1C-0032 (koşu serbest)
review09, 18300/13300, tam yığın + plan/18 katmanı. İşçinin `0.0.0-09` imajı 4e2fcad ile dosya dosya eşleşti (172 py, fark 0); `--no-build --pull never`. Koşular: unit ×2, lint, **tam test-int ×2**, alembic, seed, seed-eval ×2, exam-stack, smoke, P0-P4, r2 probe'u (stale_exam / stale_suite / boşluk `force_reason` / `eval_run_id` / `masking` / `expected` maskesi). Açık FF yığını: bu tek.

### R-09-0036 · 2026-11-05 22:06 · → koordinator · REVIEW-SONUC
Paket: 09-2 r2   Cevap: K-09-0050
**ONAY 4e2fcadd4d8dc0c566ec47ce0bd27851ac6e9835.** Rapor state/reviews/09-2-r2.md. BLOCKER/MAJOR 0, MINOR 5, NOTE 12.
- r1 MAJOR-1/2 ve MINOR 1/2/3/5/6+7/8/9/10/12 KAPANDI. Canlı probe: düzenlenen taslak 409 `stale_exam`, eşik değişimi 409 `stale_suite`, boşluk `force_reason` 422, yayınlanmış sürüm düzenleme 409, from-run `masking: regex` ve `expected` maskeli (Langfuse'ta ham değer yok).
- **Merge öncesi önerim:**
  - MINOR-1: taslak iki tick arasında B'ye değiştirilip A'ya geri alınırsa sınav B ile puanlanır, A force'suz geçer. Doğrulayıcılar MINOR/MAJOR arası; ben MINOR, düzeltme ucuz: `update_version` süren sınavları `failed(definition_changed)` yapsın + test.
  - MINOR-4: slow-judge testine `errors == {}`.
- MINOR-2 `masking` alanı monitor/off/PERSON'suz politikada yanlış değer; MINOR-3 `expected` maskesi `sql_result`/`must_cite`/`regex` anlamını bozabiliyor (kapalı başarısız); MINOR-5 yayın/PUT kilitsiz. Senin kararın.
- Kapılar (işçinin doğrulanmış imajı, build yok): unit 1777 ×2, lint, **tam test-int 941 / 939**, alembic tek head, seed-eval, exam-stack 8/8, smoke, P0-P4. DNS hatası 0; yavaşlık yok.
- Not: istek 11 commit diyor, gerçek 10.

### R-09-0037 · 2026-11-05 22:06 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans` (22:06): 0 konteyner, 0 hacim. Worktree kaldırıldı (dizin de silindi). Açık inceleyici yığını yok.

### R-09-0038 · 2026-11-16 08:17 · → koordinator · ACK
Paket: 09-2 r3   Cevap: K-09-0055 / K-09-0057
Yeni inceleyici oturumu (lease `ffcore-inceleyici-09-2-teyit`). d8e7119e9bc61614f19187f0f1cd6c40af8ceef1 doğrulandı: 4e2fcad atası, 6 commit, 12 dosya +320/-43, `feat/09-evaluation` HEAD aynı. Statik diff okuması başladı; koşular "koşu serbest" ile (review09, 18300/13300, `--pull never`, önce YIGIN-AC).

### R-09-0039 · 2026-11-16 08:21 · → koordinator · YIGIN-AC
Paket: 09-2 r3   Cevap: koordinatör zili ("koşu serbest")
review09 yalın: postgres, redis, litellm, fake-llm (`--profile test`), BACKEND_PORT 18300 / FRONTEND_PORT 13300, worktree `.worktrees/review-09-2-r3` (d8e7119, detached) `.env.test`'i, `FFCORE_VERSION=0.0.0-09` (işçinin HEAD imajı), `up --no-build --pull never`. Testler `tools` konteynerinde (`run --rm --no-deps`). Açık başka FF yığını yok. Kapanış `down -v --remove-orphans` + YIGIN-KAPA.

### R-09-0040 · 2026-11-16 08:36 · → koordinator · REVIEW-SONUC (ONAY-TEYIT)
Paket: 09-2 r3   Cevap: K-09-0055
**ONAY-TEYIT d8e7119e9bc61614f19187f0f1cd6c40af8ceef1.** Rapor state/reviews/09-2-r2.md "## r3 teyidi (d8e7119)". BLOCKER/MAJOR/MINOR 0, NOTE 8.
- r2 MINOR-1..5 kapandı. (1) `end_exams_of_edited_version` PUT işleminde; aynı tanım dokunmaz; puansızlık yapıdan (ACTIVE dışı sınav açılmıyor). PR not 2 makul. (2) `lock=True` yalnız publish/PUT; kilit sırası tek, 06a değişmeden yeşil. (3) `masking_of` motorla aynı kip, eylem ve kategori kuralları. (4) 422 yalnız `EXACT_FIELDS`, audit'li, değer sızmıyor; `masked_fields` doğru. (5) assert var. (6) OpenAPI additive. (7) Kanıt iddiaları karşılıyor; 43bfbcf notta açık.
- Koşular (imaj `0.0.0-09` = d8e7119, 172 py sha256 aynı; `--no-build --pull never`): birim+sözleşme 38 ×2, hedefli int 83 ×2 (işçi sırası), lint geçti.
- **FOLLOWUP adayları (senin kararın):** NOTE-1 ilerletici `completed`/`running` yazımı koşullu (`WHERE status IN active`): PUT'un `failed`'ını tick içinde ezmesin, kilitsiz kapatır. NOTE-4 `sql_result` içindeki sayısal kimlik maskelenmiyor/422 almıyor (delta dışı). NOTE-6 test sırası: `test_06a_agents.py:18-24` `config_encrypted=b"x"` sonrası `test_03a_2_read_mode_get_parity` 500 (delta dışı, 06a→03a tek başına kırmızı).
- Not: NOTE-7 kırmızı/kapı logları özet (komut satırı ve tam çıktı yok); teyidi etkilemiyor.

### R-09-0041 · 2026-11-16 08:36 · → koordinator · YIGIN-KAPA
review09 `down -v --remove-orphans`: konteyner 0, volume 0 (`09-2-r3-rv-stack-down.log`). Worktree `.worktrees/review-09-2-r3` kaldırıldı (dizin de silindi). Açık inceleyici yığını yok. Commit yok (state dosyaları: kanal, `reviews/09-2-r2.md`, `evidence/09-2-r3-rv-*` 10 dosya).

### R-09-0042 · 2026-11-16 09:01 · → koordinator · HANDOFF
Paket: 09-2 r3   Cevap: K-09-0062
- Teslim: ONAY-TEYIT d8e7119 (R-09-0040), rapor `state/reviews/09-2-r2.md` "r3 teyidi", kanıt `state/evidence/09-2-r3-rv-*` (10 log). Commit yok, state'i koordinatör commit'ler.
- Kalan durum: konteyner 0, volume 0 (review09), worktree `review-09-2-r3` yok, açık koşu yok.
- Açık FOLLOWUP adayları (kayıt senin kararın): NOTE-1 ilerletici koşullu durum yazımı (`runner.py:348`, `:597`); NOTE-4 `sql_result` içindeki sayısal kimlik maskelenmiyor; NOTE-6 `test_06a_agents.py:18-24` `config_encrypted=b"x"` → sonra koşan 03a parite 500.
- Öğrenilen: (a) hedefli test-int'te dosya sırası önemli: 06a/09 testleri 03a'dan önce koşarsa 03a parite düşer (delta dışı). Hedefli kümeyi 03a önce koş, ya da NOTE-6 kapanana dek alfabetik. (b) İmaj = HEAD kanıtı için `docker run --rm --network none … sha256sum /app/ffcore/**/*.py` ile worktree karşılaştırması 1 dk; build gerekmiyor. (c) `tools` konteyneri kaynağı `.:/work`'ten okur; tools imajının etiketi (0.0.0-09, 1 Kasım) bu yüzden sorun değil.
- Lease `ffcore-inceleyici-09-2-teyit` **RETIRED**.
