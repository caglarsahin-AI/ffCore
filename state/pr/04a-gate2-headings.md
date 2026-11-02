# [A] fix(04a): Markdown headings are not code lines in Kapı 2 (FOLLOWUP-137)

**Paket:** fix/04a-gate2-headings · **Sınıf:** [A] · **Branch:** fix/04a-gate2-headings · **Baz commit:** d365811 · **HEAD:** 6c0271846e26d7d2241827348c0b2fe697e73e7f (3 commit: d358bae A, 0eed4c8 A′, 6c02718 test docstring satır boyu) · Oturum ffcore-isci-b-137-7e3079e2 · GOREV K-137-0001 · Kararlar K-137-0003 (plan), K-137-0004 (A), K-137-0006 (A′)

## Plan (onaylı K-137-0003; uygulamada A′'ye evrildi)
1. **Bulunan semboller:**
   - `backend/ffcore/knowledge/gates.py:66` `_CODE_LINE`: `#` dalı her `#` satırını kod sayıyor.
   - Tek kullanım `text_quality` (`code_heavy`, eşik 0,5). Çağıranlar `knowledge/ingest.py:389` (ek dosya), `:495` (belge), `:533` (parça).
   - `_FENCE_LINE` aynı dosyada, data_dump için zaten var.
   - **Uygulamada bulunan:** `convert/text_formats.py:44` düz metin dönüştürücüsü her .txt'yi tek bir ```` ``` ```` bloğuna sarıyor.
   - `tests/converters.py` `convert_without_weights` Markdown'u olduğu gibi okuyor. Bu yüzden test_19'da 1001/1002 başlıkları ayrı satırda kalıyor ve hata orada görünmüyordu. Hata yalnız Docling paragraf birleştirmesinde çıkıyor (B-19-0013).
2. **Kapsam:** Kapı 2 kod oranında satırın kod sayılıp sayılmadığı. Eşik ve öteki kurallar (boilerplate, no_prose, data_dump) değişmedi. Kapsam dışı: dönüştürücüler (C reddi, K-137-0006), `--` / `---` (Kalan riskler).
3. **Değişen dosyalar:**
   - `backend/ffcore/knowledge/gates.py`: `_CODE_LINE` main ile birebir aynı. Yeni `_HEADING_LINE` (`^\s*#{1,6}\s+\S`), `_is_code_line(line, fenced)` ve `_code_lines(lines)`. Fence dışında başlık kod değil. Fence içinde main kuralı geçerli (`# metin` kod). Fence çizgisi kod değil. Kapanmamış fence'ten sonra fence içi kural uygulanır (fail-safe = main).
   - `backend/tests/unit/test_137_gate2_headings.py` (yeni).
   - `docs/bilgi-tabani.md`: Kapı 2 cümlesi.
4. **Sözleşme, yapılandırma, profil:** sözleşme yok (C5/C6 değişmedi), yapılandırma yok, profil farkı yok. Davranış değişikliği yalnız fence dışındaki Markdown başlık satırlarında. Önceden `code_heavy` ile elenen başlıklı kısa sayfa/parça artık indekslenir. Var olan indeks yeniden işlenmez; kural yeni ingest'te uygulanır (M3 ingest'inden önce).
5. **Kabul → test:** aşağıdaki tablo.
6. **Migration:** yok.
7. **Geri alma:** `_code_lines` yerine eski tek satır (`sum(bool(_CODE_LINE.match(ln)) …)`) yazılır. `_CODE_LINE` zaten main ile aynı. Veri değişikliği yok.
8. **Durma koşulları:** iki kez uygulandı.
   - B-137-0004: onaylı varsayım 1 yanlış çıktı (düzyazı yorumlu Python geçiyordu) → karar A.
   - B-137-0007: A entegrasyonda .txt belgelerini eledi → karar A′.
9. **Felsefe kontrolü:**
   - **ARCH-07:** Confluence/OCR korpusundaki başlıklı her kısa sayfaya değer katıyor. Kalıcı ek: bir regex ve 8 satırlık sayaç; yeni mekanizma yok (`_FENCE_LINE` yeniden kullanıldı).
   - **ARCH-09:** Docling dönüştürür, kalite kapısı bizde; platformda karşılığı yok.
   - **ARCH-10/06:** Gizli seçim yok, kural belgede. Elenen belge yine `gate2_reason` ile raporda görünür. Fence içi ve kapanmamış fence main davranışında kalıyor, böylece daha gevşek bir sessiz geçiş açılmıyor. Fence dışındaki düzyazı yorumlu kod bilinen sınır olarak testle sabitlendi (test 9).

## Değişen dosyalar
- backend/ffcore/knowledge/gates.py
- backend/tests/unit/test_137_gate2_headings.py (yeni)
- docs/bilgi-tabani.md

## Kabul kriterleri → testler
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | 1001/1002 Docling biçimi (3 başlık / 5 satır), fence dışı başlıklı kısa sayfa Kapı 2'den geçer | `test_137_1_short_headed_page_passes` | önce kırmızı (`code_heavy`, 137-red), geçti |
| 2 | `#`…`######` + boşluk + metin fence dışında kod değil | `test_137_2_heading_levels_not_code[1-6]` | önce kırmızı, geçti |
| 3 | `#include`, `#!/bin/bash`, `#define`, `#pragma`, `#`, `# `, 7× `#` kod | `test_137_3_hash_without_heading_text_is_code` | geçti (koruma) |
| 4 | Gerçek kod `code_heavy` kalır: C; ```` ``` ```` ve `~~~` içinde düzyazı yorumlu Python (main gibi) | `test_137_4_real_code_still_code_heavy[c, fenced_python_with_prose_comments, tilde_fenced_python]` | A'da kırmızı → yeşil (137-red2); A′'de yeşil |
| 5 | Eşik değişmedi (0,5 geçer, 0,6 elenir) | `test_137_5_threshold_unchanged` | geçti |
| 6 | Breadcrumb'sız parça, başlıklarla başlıyor, geçer | `test_137_6_chunk_with_heading_passes` | önce kırmızı, geçti |
| 7 | Fence'li düz metin (.txt dönüştürücü biçimi, DEMO-7) geçer (main gibi) | `test_137_7_fenced_plain_text_passes` | A'nın gerilemesi (137-test-int, 137-probe-samples); A′'de geçti |
| 8 | Kapanmamış fence: kalan satırlar main kuralıyla (`# metin` kod) | `test_137_8_unclosed_fence_keeps_main_rule` | geçti |
| 9 | Bilinen sınır: fence dışında düzyazı yorumlu kod geçer | `test_137_9_unfenced_prose_commented_code_known_limit` | geçti (sabitlendi) |
| E | test_19 ve 04a ingest entegrasyonu; `indexed 4, skipped 1`, `gate2:boilerplate 1` main ile aynı | `test_19_1_ingest_raw_paycore_like_idempotent` + `tests/integration/test_04a_*.py` | A'da kırmızı (indexed 3 / skipped 2); A′'de iki profil geçti (test değişmeden, main beklentisiyle) |

## Çalıştırılan komutlar
Hepsi `FFCORE_VERSION=0.0.0-main docker compose -p fix137 --env-file .env.test run --rm -T tools …` ile koştu: imaj derlenmedi, worktree `/work` olarak bağlı. Entegrasyon yığını fix137 (yalnız postgres + redis). Tam çıktılar `C:\ai_paycore\ffcore\state\evidence\` altında.

| Komut | Kod | Ortam | Exit | Sonuç | Log |
|---|---|---|---|---|---|
| `pytest tests/unit/test_137_gate2_headings.py` | d365811 + yeni test (düzeltme yok) | — | 1 | 8 kırmızı (`code_heavy` / `assert not True`), 10 geçti | 137-red-20261102.log |
| `make lint` + `make test` | ilk regex (commit öncesi) | llmaas, airgap | 0 / 2 | 873 geçti, 1 kaldı (test_137_4 Python, B-137-0004) | 137-gate-20261102.log |
| `pytest test_137` | A testleri, A kodu yok | — | 1 | 4 kırmızı (fence vakaları) | 137-red2-20261102.log |
| `make lint`, `make test` | A (commit öncesi) | llmaas, airgap | 0, 0, 0 | lint 0, 878/878 iki profil | 137-gate2-20261102.log |
| `pytest test_19_ingest_raw + test_04a_*` | d358bae (A) | llmaas, airgap | 1, 1 | 78 geçti / 1 kaldı (test_19: indexed 3, skipped 2) | 137-test-int-20261102.log |
| örnek ağaç ölçümü (`convert_without_weights` + `_code_lines`) | d358bae | — | 0 | DEMO-7 7/7, 1003-kontrol 6/6, PRSIM-1 4/4 → `code_heavy` | 137-probe-samples-20261102.log |
| `make lint` | 0eed4c8 (A′) | — | 2 | E501 (test docstring 101 karakter) → 6c02718 | 137-gate3-20261102.log |
| `make test` | 0eed4c8 (A′) | llmaas | 0 | 878 geçti | 137-gate3-20261102.log |
| `make test` | 0eed4c8 (A′) | airgap | 0 | 878 geçti | 137-gate3-20261102.log |
| `pytest test_19_ingest_raw + test_04a_*` | 0eed4c8 (A′), yığın fix137 | llmaas | 0 | 79 geçti, 11 NOT_RUN (bayraklı: model 2, Qdrant 8, tree_is_read_only 1) | 137-gate3-20261102.log |
| aynı | 0eed4c8 (A′), yığın fix137 | airgap | 0 | 79 geçti, 11 NOT_RUN | 137-gate3-20261102.log |
| `make lint` | **6c02718 (son HEAD)** | — | 0 | All checks passed, 390 dosya biçimli | 137-gate3-20261102.log (son bölüm) |
| `pytest test_137 + test_04a_text_rules` | **6c02718** | — | 0 | 52 geçti | 137-gate3-20261102.log (son bölüm) |

6c02718 ile 0eed4c8 arasındaki tek fark test dosyasında bir docstring satırı. Tam `make test` ve entegrasyon 0eed4c8'de koştu, son HEAD'de yeniden koşulmadı (NOT_RUN gerekçesi: davranış farkı yok).

## Çıktı özeti ve post-state
- test_19 iki profilde main beklentisiyle yeşil: `created 5`, `indexed 4, skipped 1`, `gates: gate2:boilerplate 1`, maske sayıları aynı. Yeni `code_heavy` yok.
- Örnek ağaçta (main kodu / A′) 1001 ve 1002 `ok`. Fence'li .txt üçü (DEMO-7, 1003-kontrol, PRSIM-1) main'deki gibi 0 kod satırı.
- Migration yok, veri değişikliği yok.
- Yığın fix137 kapatıldı: `down -v` exit 0, kalan konteyner 0, volume 0. İmaj derlenmedi (`0.0.0-main` kullanıldı, temizlenecek paket etiketi yok).

## Kontrol listesi
- [x] Felsefe ile çelişen nokta işaretlendi (iki varsayım düzeltmesi kanalda, B-137-0004/0007)
- [x] Donmuş sözleşme kırılmadı (C5/C6 dokunulmadı)
- [x] İki profil testi koştu (make test + entegrasyon)
- [x] Mutasyon ucu yok; audit/salt-okunur etkisi yok
- [x] Log, API, audit, hata gövdesi değişmedi; secret yok
- [x] Önyüz yok (tema/i18n konu dışı)
- [x] Docs güncel (`docs/bilgi-tabani.md`); `.env.example` değişkeni yok
- [x] WORK_QUEUE durumu kanaldan bildirildi (DURUM/PR-HAZIR)

## Ölçüm: Docling fence (K-137-0004 şart 3)
Ağırlıksız, `--network none`, `ffcore/tools:0.0.0-main` içindeki docling. Docling HTML `<pre>` bloğunu (Confluence kod makrosuna benzeyen `<pre class="syntaxhighlighter-pre">` ve `<pre><code class="language-python">`) ve Markdown fence/girintili kodu **dil etiketsiz ```` ``` ````** ile veriyor. Gerçek Confluence dışa aktarımı ve PDF/DOCX yolu denenmedi.

## Varsayımlar ve brief'teki çelişkiler
1. `# metin` satırı satır düzeyinde H1 ile kabuk yorumunu ayırt edemez. Fence dışında başlık, içinde kod sayılır (K-137-0003 + K-137-0006 A′).
2. Düz metin dönüştürücüsünün her .txt'yi fence'e sarması `docs/bilgi-tabani.md`'de yazmıyordu. Kapı 2 cümlesi artık bunu söylüyor.
3. Plan sürecindeki iki varsayım düzeltmesi (B-137-0004, B-137-0007) bu PR'ın kararlarıdır; brief çelişkisi değildir.

## Kalan riskler
- **Fence dışında düzyazı yorumlu kod geçer** (test 9). Eski davranışta `code_heavy` idi. Docling kodu fence'lediği için (ölçüldü, HTML/MD) pratikte fence dışı kod az olmalı. Fence'siz yapıştırılmış kod (Confluence'ta düz paragraf) indekse girebilir: arama gürültüsü, güvenlik değil.
- **Confluence dışa aktarımında Docling fence'i doğrulanmadı.** Yalnız HTML ve MD örnekleriyle ölçüldü.
- **`---` yatay çizgi `--` dalına uyuyor** (main davranışı, değişmedi). 19 sentetik ağacında `---` satırı 0 (ölçüldü), etkisi ölçülemedi.
- `#123` (boşluksuz numara) main'deki gibi kod sayılır.
- Gerçek Docling ile uçtan uca ingest NOT_RUN: ağırlıklar `make models` ile kullanıcıda. Entegrasyonda `RUN_MODEL_TESTS` 2, Qdrant 8, `tree_is_read_only` 1 test bayraklı NOT_RUN (main ile aynı).
