# [A] fix(04a): Markdown headings are not code lines in Kapı 2 (FOLLOWUP-137)

**Paket:** fix/04a-gate2-headings · **Sınıf:** [A] · **Branch:** fix/04a-gate2-headings · **Baz commit:** d365811 · **HEAD:** (henüz commit yok) · Oturum ffcore-isci-b-137-7e3079e2 · GOREV K-137-0001

## Plan (onay bekliyor)
1. **Bulunan semboller:** `backend/ffcore/knowledge/gates.py:66` `_CODE_LINE`: `^\s*(?:[{}\[\]();]|//|#|--|<\w|import |...)`, `re.I`. Buradaki `#` dalı her `#` ile başlayan satırı kod sayıyor, Markdown başlıkları da buna dahil. Tek kullanım yeri `gates.py:166`, `text_quality` içinde (`> max_code_ratio` 0,5 → `skipped, code_heavy`). `text_quality` üç yerden çağrılıyor: `knowledge/ingest.py:389` ek dosya, `:495` belge, `:533` parça (breadcrumb'sız gövde). Mevcut testler: `tests/unit/test_04a_text_rules.py` (boilerplate, no_prose; `code_heavy` testi **yok**) ve `tests/integration/test_19_ingest_raw.py:79` (`gates == {"gate2:boilerplate": 1}`). Bu test `convert_without_weights` ile koşuyor ve başlıkları ayrı satırda tutuyor, bu yüzden 1001/1002 orada geçiyor. Hata yalnız Docling'in satırları paragraflara birleştirdiği gerçek dönüşümde çıkıyor (B-19-0013: 3 başlık / 5 satır = 0,6).
2. **Kapsam:** `_CODE_LINE`'daki `#` dalı yalnız başlık olmayan `#` satırlarına uyar. Kapsam dışı: eşik (0,5) ve öteki desenler. Gözlem (değiştirilmiyor): `--` dalı Markdown yatay çizgisine (`---`) de uyuyor. Docling çıktısında görülürse ayrı FOLLOWUP açılır; bu PR'da ölçülmedi.
3. **Değişecek dosyalar:**
   - `backend/ffcore/knowledge/gates.py`: `#` dalı `#(?!#{0,5}\s+\S)` olur. Başlık (`#`…`######` + boşluk + metin) kod sayılmaz. `#include`, `#!/bin/sh`, `#define`, `#pragma` gibi `#` + boşluksuz satırlar kod kalır.
   - `backend/tests/unit/test_137_gate2_headings.py` (yeni).
   - `docs/bilgi-tabani.md` Kapı 2 cümlesi: "Markdown heading lines are not code lines".
4. **Sözleşme, yapılandırma, profil:** sözleşme yok (C5/C6 dokunulmuyor), yapılandırma yok, profil farkı yok. Davranış daralıyor: önceden `code_heavy` ile elenen bazı belgeler/parçalar artık indekslenecek. Var olan indeks yeniden işlenmez; yeni ingest'te geçerli olur. Bu, M3 ingest'inden önce kapanmasının gerekçesi.
5. **Kabul kriteri → test** (`backend/tests/unit/test_137_gate2_headings.py`):
   | # | Kriter | Test |
   |---|---|---|
   | 1 | 1001/1002 biçimindeki başlıklı kısa sayfa (Docling birleşik paragraf biçimi, 3 başlık / 5 satır) Kapı 2'den geçer | `test_137_1_short_headed_page_passes` (önce kırmızı: bugün `code_heavy`) |
   | 2 | `#`…`######` + boşluk + metin kod sayılmaz; `#` yalnız ya da `#` + boşluk + boş satır başlık değildir | `test_137_2_heading_levels_not_code` (parametrik) |
   | 3 | `#include`, `#!/bin/bash`, `#define`, `#pragma` kod kalır | `test_137_3_hash_without_space_is_code` |
   | 4 | Gerçek kod bloğu hâlâ `code_heavy` (C ön işlemcili ve kabuk betiği) | `test_137_4_real_code_still_code_heavy` |
   | 5 | Eşik değişmedi: tam 0,5 geçer, üstü elenir (başlıksız satırlarla) | `test_137_5_threshold_unchanged` |
   | 6 | Parça düzeyi (breadcrumb'sız gövde, başlıkla başlayan parça) geçer | `test_137_6_chunk_with_heading_passes` |
   - Entegrasyon: `test_19_ingest_raw.py` ve 04a ingest testleri aynen yeşil kalmalı (regresyon). Yığın gerekirse YIGIN-AÇ 18220/13220. Gerçek Docling dönüşümü ağırlık istiyor (`make models` kullanıcıda); onun yerine 1001/1002'nin Docling biçimi birim testte metin olarak kurulur. Gerçek Docling koşusu NOT_RUN (gerekçe: ağırlık).
6. **Migration:** yok.
7. **Geri alma:** tek regex satırını geri almak. Veri değişikliği yok. Bu sürümle indekslenen belgeler eski kurala dönülürse yeniden ingest'te elenir.
8. **Durma koşulları:** başlık ile kabuk yorumu arasında satır düzeyinde ayrım yapılamıyor (aşağıdaki varsayım 1). Koordinatör kabuk yorumlarının `# ` biçiminde de kod sayılmasını isterse bu, satır düzeyi regex ile mümkün değil. Bağlam (fence içi) gerekir; o zaman durup KARAR-GEREK yazarım.
9. **Felsefe kontrolü:**
   - **ARCH-07:** Başlıklı her kısa sayfaya dokunuyor (Confluence/OCR korpusunun yaygın biçimi), tek regex, kalıcı karmaşıklık yok.
   - **ARCH-09:** Platform bunu sunmuyor; Docling yalnız dönüştürüyor, kalite kapısı bizim. Yeni kütüphane yok.
   - **ARCH-10/06:** Gizli davranış yok. Elenen belge yine `gate2_reason` ile raporda görünür. Sessiz geçiş riski şu: başlık gibi görünen kabuk yorumu artık kod sayılmıyor. Bunu test 4 sınırlıyor (gerçek kod bloğunda öteki satırlar oranı taşıyor).

## Varsayımlar ve brief'teki çelişkiler
1. **Kabuk yorumu ile H1 başlık aynı biçimde** (`# metin`). GOREV "yalnız `#` + boşluksuz ya da kabuk yorumu deseni kod kalır" diyor. Ama `# install deps` ile `# Kurulum` satır düzeyinde ayırt edilemez. Varsayımım: `#` + boşluk + metin her zaman başlık sayılır. Kabuk yorumları ancak `#` + boşluksuz (`#!`, `#comment`) biçimindeyse kod kalır. Gerekçe: Kapı 2 metin kalitesidir; kod bloğunda yorumdan başka satırlar (komutlar, `{`, `import` …) oranı zaten taşır (test 4). Fence içi bağlam takibi kapsamı ve karmaşıklığı büyütür (ARCH-07). Koordinatör aksini isterse durma koşulu 8.
2. `#123` (boşluksuz numara, ör. talep no) bugün olduğu gibi kod sayılmaya devam eder. Kapsam dışı, davranış değişmez.

## Değişen dosyalar
(kodlama sonrası)

## Kabul kriterleri → testler
(kodlama sonrası)

## Çalıştırılan komutlar
(kodlama sonrası; tam tee `state/evidence/137-gate-<tarih>.log`)

## Kalan riskler
- `---` yatay çizgi `--` dalına uyuyor (madde 2 gözlemi); ölçülmedi.
