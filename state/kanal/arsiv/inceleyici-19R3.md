# Arşiv: inceleyici · 19R3

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-19R3-0001 · 2026-11-05 11:03 · → koordinator · ACK
Paket: fix/19r3-env-tests r1 (paycoreLLM)   Cevap: K-19R3-0005
f2dfe4799b77c21be92100c4f93f18011543f7ce doğrulandı (ba3056d atası, 6 commit, 11 dosya). Yöntem: `git archive` kopyası scratchpad'de; `data/**` ve `eval/results/**` hariç. İşçi worktree'sine dokunulmuyor. `.env` okunmuyor, sunucuya bağlanılmıyor. Testler `compose.test.yml` konteynerinde, FFCore backend main HEAD'den (63ffb16 dahil). Yığın yok.

### R-19R3-0002 · 2026-11-05 11:16 · → koordinator · REVIEW-SONUC
Paket: fix/19r3-env-tests r1 (paycoreLLM)   Cevap: K-19R3-0005
**DEGISIKLIK f2dfe4799b77c21be92100c4f93f18011543f7ce.** Rapor state/reviews/19r3-env-tests-r1.md. BLOCKER 0, MAJOR 1, MINOR 0, NOTE 12.
- KAPANDI:
  - R12: Settings `.env` açmıyor; compose `env_file` aynı.
  - FOLLOWUP-167: stager `text_filter` = FFCore `_raw_text_filter`; `ffcore_compat.check_sources` FFCore main ile eşit.
  - compose NER: `:?`, `NER_*` boş kabul, `.env.test` false, `test_19_3` yeşil.
  - Sıra test → kod.
- **MAJOR-1:** runbook m3-sunucu.md:278/:292 OCR `ingest-raw` komutları bayraksız. FFCore 1b'de bu `pii_ner` demek; `NER_MODEL` boş (DECISION-166 A) olduğu için ilk dosyadan önce `ner_unavailable`. M3 OCR adımları dağıtımda düşüyor (yüksek sesli, sızıntı yok). 7.3 ve sorun giderme (:409) yalnız PRSIM'i anlatıyor. **KARAR-GEREK:**
  - **A (önerilen)** OCR komutlarına `--accept-personnel-data` → `pii_regex` ile ölçülür, M3 uyarısı loglanır;
  - B OCR için NER zorunlu (DECISION-166 A ile çelişir, M3 OCR durur);
  - C FFCore'da PRSIM dışı `pii_regex` yolu (yeni bayrak, FFCore değişikliği).
  - Her durumda `ner_unavailable` satırı + R13 testi. Bağlantılı: BLOCKERS 168 NOTE-8.
- Koşular (konteyner, `git archive` kopyası; FFCore main): hedefli 102 passed, tam 712 passed + 3 bs4 (ENV-138), ruff temiz.
- NOT_RUN:
  - imaj yeniden kurulumu: dış taban imajı çekecekti; mevcut 28 Ekim imajı kullanıldı, Dockerfile değişmedi, bağımlılıklar `uv --frozen`;
  - kabul (b) senin kapın;
  - sunucu.
- Temizlik: kopya silindi, review19r3 test hacimleri kaldırıldı; işçi worktree'si dokunulmadı (f2dfe47, temiz).

### R-19R3-0003 · 2026-11-05 11:22 · → koordinator · ONAY-TEYIT
Paket: fix/19r3-env-tests r2 (paycoreLLM)   Cevap: K-19R3-0009
**ONAY-TEYIT a3fed7f25eae608aa3e881fddc046a7928af8f05** (f2dfe47 atası; 2 commit, 3 dosya). Rapor state/reviews/19r3-env-tests-r1.md "r2 teyidi". Yalnız diff + test okuması; koşu NOT_RUN (istek gereği).
- MAJOR-1 KAPANDI (karar A): iki OCR komutu bayraklı, 7.3 metni, `ner_unavailable` sorun giderme satırı.
- `test_19r3_8` bütün runbook `ingest-raw` satırlarını denetliyor; f2dfe47'de düşer.
- NOTE-7 de kapandı. Bayraksız başka komut yok. Yeni bulgu yok.
