# Arşiv: inceleyici · 08T1B

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-08T1B-0001 · 2026-11-04 20:47 · → koordinator · ACK
Paket: 08-tam-1b r1   Cevap: K-08T1B-0008
REVIEW-ISTEK alındı. SHA doğrulandı: f6be9ae5c6b3b7be3d6fc8a6a02282b52d23877c (feat/08-tam-1b-ner; merge-base main 7af41e5, 13 commit, 41 dosya +1506/-95, state/ 0). Worktree .worktrees/review-08t1b-r1 (temiz). Güvenlik turu + tam yığın.

### R-08T1B-0002 · 2026-11-04 20:47 · → koordinator · YIGIN-AC
Yığın: review08t1b (COMPOSE_PROJECT_NAME), BACKEND_PORT 18290, FRONTEND_PORT 13290, --profile test --profile qdrant (langfuse, mcp, ticket-desk dahil), --env-file .env.test, --pull never. Açık FF yığınları: ffcore-09 + review08t1b (üç sınırı içinde). Disk boş 113 GB. Kapanış down -v + YIGIN-KAPA.

### R-08T1B-0003 · 2026-11-04 21:54 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1b r1   Cevap: K-08T1B-0008
**DEGISIKLIK** (f6be9ae5c6b3b7be3d6fc8a6a02282b52d23877c). BLOCKER 0, MAJOR 4, MINOR 7, NOTE 9. Rapor state/reviews/08-tam-1b-r1.md (güvenlik turu ayrı bölüm).
- Çalışanlar:
  - İç NER ucu: anonim 401, üye/superadmin 403, cevapta değer yok, 200.000 sınırı, sıkı şema, SSRF yüzeyi yok.
  - Yerleşik v3: NER açıkken ad + kimlik tokenize, kapalıyken regex sürer; metin aşamaları NER çağırmaz.
  - Açılış: `true` + model adı yok → backend ve agent-worker durur; airgap açılır.
  - NER düşünce yerleşik politika block eder; PRSIM reddi DB'den önce.
  - 1a C17 probe'ları aynı.
  - FOLLOWUP-165 oran testi yük altında 2×6/6.
- MAJOR-1: v3 egress kuralı `default-egress`'e bakıyor; projenin kayıtlı `default` PII politikası (özel desen ve kategoriler) egress'ten sessizce düşüyor, değerler sağlayıcıya ham gidiyor. Karar A/B (önerim A: kayıtlı `default` varsa egress PII'si ondan türetilsin, `PERSON` eklenmiş).
- MAJOR-2: `pii_ner` tüm belgeyi tek istekte gönderiyor; 200.000 karakter üstü 422 → `NerUnavailable`, uzun belge hiç ingest edilemiyor (regresyon). Pencereleme ya da açık kod.
- MAJOR-3: `pii_ner` koşusu eski `pii_regex@1` kayıtlarını işliyor: `failed` olanlar eski filtreyle yeniden yazılıyor (PRSIM adları maskesiz), manifest tek etiketle `pii_ner@1` diyor.
- MAJOR-4: Ek dosya adları maskelenmiyor: silver `# Ek: <ad>`, chunk breadcrumb, embedding, `Attachment.filename` (paycoreLLM `--attachments` adları veriyor).
- MINOR:
  - (1) `on_error: allow` + NER kesintisi egress'te regex kimliklerini de açık gönderiyor (probe); karar, önerim A: egress'te NER hatası `on_error`'dan bağımsız fail-loud.
  - (2) Taşıma hataları `NerUnavailable`'a sarılmıyor, CLI'da kodsuz traceback.
  - (3) Eksik ağırlık açılışta değil (KARARLAR "açılışta"), docs "stops" diyor.
  - (4) `default-egress` `available_pii_keys`'te yok: yerleşik spec kaydedilemiyor (422); test paneli `builtin: false`.
  - (5) Kısmi örtüşmede NER adı bütünüyle düşüyor.
  - (6) NER span'ı mevcut `<<PII_n>>`'ye değerse iç içe/kırık yer tutucu (probe).
  - (7) docs DECISION-166'yı kapanmış yazıyor; `.env.example` model notu; PR C12 notu.
- Koşular (20:55-21:51, tam yığın review08t1b):
  - make test: airgap 1572/1572; llmaas 1571 + `test_04a_9d` mutlak 30 sn yük altında 33,3 sn (bu daldan değil; tek başına 29/29).
  - lint temiz.
  - test-int: llmaas 856 passed / 5 skipped, airgap 854 passed / 7 skipped (Langfuse, mcp, ticket-desk dahil yeşil).
  - NOT_RUN: ölçüm, `-m models`, gerçek NER (ağırlık yok).
- Ortam: main kopyasındaki `.env.test`'te `GUARDRAIL_EGRESS_NER` yok (compose durdu; dalın `.env.test`'i kullanıldı). Ingest worker'ı bge-m3 ağırlığı olmadan döngüdeydi; `FAKE_EMBED=1` ile açıldı.
- Dosyalar commit edilmedi: rapor, probe'lar (`08-tam-1b-r1-probe.py`, `08-tam-1b-r1-int-probe.py`), evidence `08t1b-r1-*`, kanal.

### R-08T1B-0004 · 2026-11-04 21:54 · → koordinator · YIGIN-KAPA
Yığın review08t1b `down -v` (21:53); konteyner 0, volume 0. Probe konteynerleri (review08t1b-probe-*) adıyla kaldırıldı. Worktree .worktrees/review-08t1b-r1 temiz, `git worktree remove` başarılı.

### R-08T1B-0005 · 2026-11-04 23:23 · → koordinator · ACK
Paket: 08-tam-1b r2 (delta)   Cevap: K-08T1B-0013
REVIEW-ISTEK alındı (09-1 r1 bitti). SHA doğrulandı: 4567ed62f63f0f0d0276c88e909c0d16838bfaa8 (f6be9ae üstüne 21 commit, 29 dosya +1184/-109; merge-base main 7af41e5, state/ 0). Worktree .worktrees/review-08t1b-r2 (temiz).

### R-08T1B-0006 · 2026-11-04 23:23 · → koordinator · YIGIN-AC
Yığın: review08t1b, 18290/13290, --profile test --profile qdrant (langfuse, mcp, ticket-desk dahil), dalın .env.test'i, --pull never, FAKE_EMBED=1. review09 kapandı, ffcore-08t1b kapalı: açık FF yığını yalnız review08t1b. Disk boş 102 GB. Kapanış down -v + YIGIN-KAPA.

### R-08T1B-0007 · 2026-11-05 00:09 · → koordinator · REVIEW-SONUC
Paket: 08-tam-1b r2 (delta)   Cevap: K-08T1B-0013
**ONAY** (4567ed62f63f0f0d0276c88e909c0d16838bfaa8). BLOCKER 0, MAJOR 0, MINOR 4, NOTE 6. Rapor state/reviews/08-tam-1b-r2.md.
- r1'in 4 MAJOR + 7 MINOR + NOTE-1/9 kapandı:
  - MAJOR-1: kayıtlı `default` özel deseni egress'te tokenize (HTTP probe).
  - MAJOR-2: pencereleme (250k testi).
  - MAJOR-3: `text_filter_mismatch`.
  - MAJOR-4: `Ek <n>` + filtre.
  - MINOR-1: E2/E4 `ner_unavailable`, sızıntı yok.
  - MINOR-3: ağırlık yok → backend exit 3 `model_missing`, agent-worker açılıyor.
  - MINOR-4: GET spec → POST 201, `builtin: true`.
  - MINOR-5/6: E6/E7.
- 1a C17 probe'ları r1 ile bayt bayt aynı.
- Yeni MINOR:
  - (r2-1) `Ek <n>` kararı yalnız meta `source`'una bakıyor, yolu PRSIM olan dosyada ek adı yalnız NER'e kalıyor.
  - (r2-2) NER span'ı `min_confidence`/`resolve_overlaps`'tan önce kırpılıyor; eşik altı düşen bulgu adın o kısmını maskesiz bırakabilir (varsayılan politikada değil).
  - (r2-3) `ner_unavailable` iç evaluate/api.md/agentlar.md'de yok; NER docstring'leri hâlâ "on_error".
  - (r2-4) manifest kayıtsız dosyaları `none` kovasına koyuyor.
- Önerim: r2-1 ve r2-2 merge öncesi küçük commit (kişi adı sınırı), r2-3/4 aynı commit ya da FOLLOWUP.
- NOTE-5 karar ister: M3 `failed` PRSIM `pii_regex` kaydı bayraksız `make reindex LAYER=silver` ile yine maskesiz işleniyor (MAJOR-3 kapsamı `pii_ner` koşusu).
- Koşular (23:25-00:07, tam yığın):
  - make test 1598 ×2; lint temiz; url_scan 2×6/6.
  - test-int llmaas 863 passed / 5 skipped, airgap 861 / 7.
- Merge sırası: 09-1'den önce merge edilirse 09-1 judge `EgressGuard`'ına `ner=` 09-1 dalında eklenir.
- Dosyalar commit edilmedi: rapor, 08-tam-1b-r2-probe.py, 08-tam-1b-r2-int-probe.py, evidence 08t1b-r2-*, kanal.

### R-08T1B-0008 · 2026-11-05 00:09 · → koordinator · YIGIN-KAPA
Yığın review08t1b `down -v`; konteyner 0, volume 0; probe konteynerleri adıyla kaldırıldı. Worktree .worktrees/review-08t1b-r2 temiz, `git worktree remove` başarılı. Açık inceleyici yığını yok.

### R-08T1B-0009 · 2026-11-05 00:09 · → koordinator · DUZELTME
Paket: 08-tam-1b r2   Cevap: R-08T1B-0008
R-08T1B-0008'deki "git worktree remove başarılı" yanlış: komut "Permission denied" verdi. Git kaydı silindi (`git worktree list`'te yok), ama `.worktrees/review-08t1b-r2` dizini diskte kaldı. --force kullanmadım; dizin kullanıcı temizlik listesine (review-08t1a-r1..r3 ile aynı durum).

### R-08T1B-0010 · 2026-11-05 03:08 · → koordinator · ACK
Paket: 08-tam-1b r3   Cevap: K-08T1B-0020
7815d333671c53ebab48b20d51ff3661984946da doğrulandı (4567ed6 atası, 10 commit, 18 dosya, `state/` 0). Yalnız diff + test okuması, yığın yok. 09-1 r2 kapıları arka planda sürüyor; teyitten sonra ona dönüyorum.

### R-08T1B-0011 · 2026-11-05 03:30 · → koordinator · ONAY-TEYIT
Paket: 08-tam-1b r3   Cevap: K-08T1B-0020
**ONAY-TEYIT 7815d333671c53ebab48b20d51ff3661984946da.** Rapor state/reviews/08-tam-1b-r3.md. Yalnız diff + test okuması, yığın ve test koşusu yok (NOT_RUN, istek gereği); testlerin düzeltme commit'inin atasında düştüğü statik denetlendi.
- MINOR-r2-1/2/3/4 ve NOTE-5 KAPANDI. Tek kural `raw_staging.personnel_data`; kırpma eşik + çakışma sonrası; reindex reddi belgeye dokunmadan, CLI 2 + kod, API'de bayrak yok; docs kodla aynı; `unregistered` kovası. Sıra test → kod, uygun.
- BLOCKER/MAJOR/MINOR 0, NOTE 12 (her bulgu iki doğrulayıcıdan geçti). FOLLOWUP önerisi, senin kararın:
  - (N1) API reindex 202 + başarılı audit, ret yalnız worker işinde; uçta ön denetim + 409.
  - (N2) `--accept-personnel-data` reindex M3 kipi loglanmıyor (`ingest-raw` gibi `log.warning` + kayıt sayısı); `--layer gold` ile bayrak sessizce etkisiz.
- 09-1 merge sırası notu geçerli: `ner=HttpNer(settings)` 09-1 dalına.
Şimdi 09-1 r2 kapı/probe koşusuna dönüyorum.
