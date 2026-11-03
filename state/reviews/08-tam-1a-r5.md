# 08-tam-1a r5 inceleme (delta, r4 DEGISIKLIK kapanışı)

- **SHA:** 60f2250caf8fa089abb0ee476b7a0325394d3c44 (feat/08-tam-1-ner; 4aecdbc üstüne 5 commit, 14 dosya +282/-188, `state/` 0)
- **İstek:** K-08T1-0026 · Cevap: R-08T1-0009 (r4), K-08T1-0024 (DUZELT)
- **Kararlar:** KARARLAR "C17 geri çevirme: cevap düzeyinde HTML fail-closed" (+ d′, f′)
- **İnceleyici worktree:** `.worktrees/review-08t1a-r5` (temiz; probe'lar tek dosya mount ile koşuldu, mount noktaları silindi)
- **Yığın:** review08t1a, 18290/13290, `--profile test --profile qdrant`, `--pull never`, hepsi healthy
- **Karar: DEGISIKLIK** — BLOCKER 0, MAJOR 1, MINOR 4, NOTE 7

Karar A doğru uygulanmış; sıfır tık sızıntı yolu bulunamadı. Doğrulananlar:
- r2/r3/r4 yazım tabloları, r4'ün yedi HTML/CSS/CRLF atlatması ve bu turun markdown/CRLF listesi tutuluyor.
- `on_error=allow` altında aralık hatası kodlu 400; sağlayıcı hiç çağrılmıyor.
- Konuşmadaki `<<PII_99999999>>` artık hiçbir şeyi bozmuyor.
- Hazırlık hatası cevabın kalanını tutuyor.
- Performans: 100 bin karakter, 1 karakterlik parçalarla 0,34-0,42 s.

Tek MAJOR bir gerileme: 32 karakterlik tarama penceresi bütün bir yer tutucuyu, ilk `<`'i pencereden düştüğünde HTML etiketi sanıyor. Canlı akışta ilk yer tutucudan sonraki değerler sahibe yer tutucu olarak gidiyor; rastgele token parçalamasında cevapların yaklaşık yarısında bu oluyor. Sızıntı değil, ama C17'nin "sahip değeri görür" işlevini bozuyor. Düzeltmesi tek satır.

## r4 bulgularının kapanışı

| r4 | Durum | Kanıt |
|---|---|---|
| MAJOR-r4-1 karar A | **KAPANDI** | r4 adversarial probe'u bu SHA'da 7 yazımda ve `fail_closed` ikinci satırda tutuldu (`08t1a-r5-rerun-r4-adv-probe.log`: hiç açılma yok). r3 ve r4 yazım tabloları tutuldu (`08t1a-r5-rerun-r3-probe.log`, `08t1a-r5-rerun-r4-probe.log`; açılanlar yalnız düz metin ve CommonMark'ta bağlantı olmayan boş satır durumları). Facade düz yol uçtan uca: r2'nin 4 markdown yazımı ve r4'ün 7 HTML yazımı sağlayıcıda yer tutucu, cevapta yer tutucu, değer dönmedi (`08t1a-r5-int-probe-llmaas.log`). |
| MINOR-r4-1 aralık hatası `on_error`'dan bağımsız | **KAPANDI** | `engine.py:334` yeniden yükseltiyor. Uçtan uca (`08t1a-r5-int-probe2-llmaas.log`): politika `on_error: allow`, araç sonucunda `<<PII_99999997>>` + iki e-posta → 400 `placeholder_out_of_range`, sağlayıcıya istek 0, ham değer yok. Docs yola göre doğru: facade düz/dış agent/istemci geçmişi 400, agent koşusu 502 `api_error`. |
| MINOR-r4-2 f′ | **KAPANDI** (99.999.999) | `<<PII_99999999>>` + e-posta → 200; sağlayıcı `<<PII_1>>` gördü; cevapta değer döndü. Mağaza: `<<PII_99999999>>` ve 9 haneli ayrılmıyor, sayaç 1'den başlıyor; 99.999.999 açılmıyor. Kalan kenar: MINOR-r5-1. |
| MINOR-r4-3/6 hazırlık hatası | **KAPANDI** | Gerçek Redis, akışta olmayan `after`: ikinci ve üçüncü satırdaki değerler tutuldu. `prime` her istisnada `fail_closed` (`runs.py:294-305`). |
| MINOR-r4-4 test | **KAPANDI** | `test_08t_r2_paths.py:59` `"<<PII_" in content` iddiasını geri getirdi. `style` yazımı kısaltıldı; on yazımın hepsi fake'in 50 karakterlik kesimine sığıyor (`style` tek karakter payla). |
| MINOR-r4-5 kullanılabilirlik takası docs | **KISMİ** | `guardrail.md:156` takası yazıyor ama bedelin kime düştüğü yanlış (MINOR-r5-2). |
| NOTE-6 PR | **KAPANDI** | Bayat metin kalıntıları: MINOR-r5-4. |

## Koordinatör maddeleri (K-08T1-0026)

1. **Karar A doğrulaması:** yukarıda; HTML'siz cevapta değerler görünüyor; `a<b` düzyazısı tutuluyor (docs takası yazılı, kapsamı eksik: MINOR-r5-2).
2. **Markdown ve CRLF adversarial** (`08t1a-r5-probe.log`, tek parça + akış 1/4/7/50 + canlı parçalar). Tutulanlar:
   - CR-only satır sonu, parça sonunda CR + LF, iki parçaya bölünmüş CRLF (varlık kodlu değerle);
   - referans tanımı: önünde 3 boşluk, büyük/küçük harf etiket, değer sonraki satırda (`//` ve ters bölü `\\evil`);
   - `](\n\\evil…)`, `](\\evil…)`, çok satırlı açılı hedef, otomatik bağlantı `<https://…>`, `[x]: <//host>`, `[x]: <host>`;
   - blockquote ve liste içinde referans tanımı.

   Açılanlar yalnız CommonMark'ta bağlantı olmayan durumlar: `](…` + boş satır + değer, `](` + CR CR + değer (tek parça ve bazı akış bölünmeleri). Boş satır hedefi bitirdiği için değer bir hedefin içinde değil. CommonMark'ın boş satır istisnası aranmadı/bulunmadı: bağlantı hedefi satır sonu içeremez, açılı hedef de satır sonu içeremez.
3. **f′:** `<<PII_99999999>>` konuşmada → sonraki koşu çalışıyor. `<<PII_99999998>>` + iki değer: ilk değer de reddediliyor (MINOR-r5-1).
4. **`on_error=allow`:** ham değer gitmiyor; docs/api.md yola göre doğru.
5. **Hazırlık hataları:** cevap sonuna kadar fail-closed.
6. **MINOR-r4-4:** kapandı.
7. **Performans:** gerileme yok (r4 probe'u bu SHA'da). 100 bin/1'lik parça 0,42/0,34 s; 64 bin/4'lük 0,10/0,08 s; düz metin 122 bin 0,19 s; hazırlık 20 bin girdi 0,28 s.
8. **docs/PR notu:** MINOR-r5-2, MINOR-r5-4.
9. **Tam yığın ve 06b-2:** Koşular tablosunda.

- **Varsayım 14 KABUL.** `](<a b>)` HTML kuralına takılıyor (fazla tutma); `](<./a b>)` yalnız satır kuralı. İkisi de probe'da tutuldu.
- **Varsayım 15 KABUL.** CSS yalnız HTML içinde yükleniyor; orada cevap düzeyi kural geçerli.

## Yeni bulgular

### MAJOR-r5-1 · Tarama penceresi bütün bir yer tutucuyu HTML etiketi sanıyor; canlı akışta sonraki değerler sahibe yer tutucu gidiyor (gerileme) — CONFIRMED (backend konteyneri, gerçek sınıflar)

`_HTML_TAG = <(?!(?<=<<)PII_\d{1,8}>>)[a-z]` istisnası, yer tutucunun ilk `<`'inin pencerede olmasına bağlı. Pencere = son 32 karakter + yeni parça (`UrlLines._add`). Akış ilerledikçe kuyruk bir yer tutucunun iki `<`'i arasından kesilince pencere `<PII_1>>…` ile başlıyor. Geriye bakış tutmuyor, `<P` etiket sayılıyor, `_html=True` oluyor ve cevabın geri kalanında hiçbir değer açılmıyor.

Ölçüm (`08t1a-r5-tail-probe.log`), 3 yer tutuculu bir cevap; tek parça 3/3:

| Parça boyu | Facade düz akış (StreamDetokenizer) | Konsol canlı (ContextReveal, bütün yer tutuculu girdiler) |
|---|---|---|
| 1 | 1/3 | 1/3 |
| 2 | 1/3 | 1/3 |
| 3 | 2/3 | 1/3 |
| 4 | 3/3 | 1/3 |
| 5 | 3/3 | 3/3 |
| 6 | 3/3 | 1/3 |
| 8 | 3/3 | 1/3 |
| 11 | 3/3 | 3/3 |

Rastgele 1-6 karakterlik token girdileri, 200 deneme: **97/200 cevapta** en az bir değer kayboldu.

C17'nin temel kabul ölçütü olan "sahip canlı akışta değeri görür", çok yer tutuculu cevaplarda yaklaşık yarı yarıya bozuluyor. Replay ve tek parça doğru. Bu delta'nın gerilemesi (c22894a): r4'te etiket istisnası `(?!PII_\d)` önceki karaktere bakmıyordu.

**Düzeltme (tek satır):** istisna önceki karaktere bakmasın: `<(?!PII_\d{1,8}>>)[a-z]`. `<PII_n>>` biçimi en fazla özniteliksiz, bilinmeyen boş bir öğe olarak ayrıştırılır ve hiçbir şey yükleyemez. r4'ün `<PII_1 style…` atlatması yine yakalanır, çünkü orada `>>` yok. Test: bu probe'un tablosu (1-11 karakterlik parçalar ve rastgele parçalama) 3/3.

### MINOR-r5-1 · Taşınan `<<PII_99999998>>` kapsamı tüketiyor; konuşma yine kalıcı bozuluyor (f′'nin amacı 99.999.998'de karşılanmıyor) — CONFIRMED (mağaza düzeyi)

`reserve_carried` artık hiç yükseltmiyor; sayaç taşınan numaraya ayrılıyor.
- `<<PII_99999998>>` → sayaç 99.999.998 → ilk yeni değer `PlaceholderOutOfRange`.
- `<<PII_99999997>>` → bir değer, sonra hata.

Konuşmaya bir kez giren `<<PII_99999998>>` (kullanıcı yazmış ya da belgeden enjekte edilip cevaba yankılanmış), o konuşmada PII tokenize eden her koşuyu kalıcı düşürüyor. Bu, r4 MINOR-r4-2'nin bir numara aşağı kaymış hâli.

Ayrıca `\d` Unicode rakamları da eşliyor. `<<PII_٩٩٩٩٩٩٩٩>>` (Arap-Hint rakamları) 99.999.999 olarak okunuyor, istisnayı atlatıyor ve aynı etkiyi doğuruyor (kod okuması).

**Öneri (koordinatör):** gerçek bir kapsamın asla ulaşamayacağı bir eşiğin üstündeki taşınan numaralar yok sayılsın, örneğin ≥ 10.000.000. Böyle bir numara yeni değerlerle çakışamaz; sayaç eşiğe ulaşırsa fail-loud. Desen `[0-9]` ya da `re.ASCII` olmalı.

### MINOR-r5-2 · HTML kuralının bedeli docs'ta yanlış yere yazılmış ve kapsamı "cevap" değil "okuyucunun akışı" — CONFIRMED (kod)

- **Bedelin yeri:** KARARLAR ve `guardrail.md` "FFCore konsolu düz metin gösterdiği için etki üçüncü taraf istemcilerde" diyor. Bu, sızıntı riski için doğru. Ama bedel, yani değerin gizlenmesi, konsolun sahibine de düşüyor: konsol akışı da aynı `ContextReveal`/`UrlLines`'tan geçiyor (`api/runs.py:289`).
  - Model cevaplarında sık görülen tetikleyiciler: tablo hücresinde `<br>`, `List<String>`, `#include <stdio.h>`, `Bearer <token>`, `<your-email>`, boşluksuz `x<y`.
  - Docs yalnız `a<b`'yi anıyor. Konsol düz metin gösterdiği için konsol okuyucusunda sızıntı riski yok, bedel ise tam.
- **Kapsam:** `UrlLines` okuyucu başına bir kez kuruluyor ve model turları arasında sıfırlanmıyor. Onay sonrası `prime` bütün önceki girdileri yeniden oynatıyor. İlk turda `<br>` yazan bir koşunun onaydan sonraki son cevabındaki değerler de tutuluyor; docs "o cevabın geri kalanı" diyor.
- **Seçenekler (koordinatör):**
  - **(a)** Docs ve gerekçe düzeltilsin ("okuyucunun akışının geri kalanı", konsolda da tutulur, tetikleyici listesi).
  - **(b)** Konsol okuyucusu, istemci düz metin gösterdiği için HTML kuralından muaf tutulsun (markdown satır kuralı kalsın). Bu kodda okuyucu türüne göre ayrım demek.

  Ben (a)'yı öneriyorum. (b) FFCore konsolu ileride markdown işlerse sessizce açık kalır.

### MINOR-r5-3 · Testlerde ve PR notunda kaldırılan HTML kiplerinin bayat anlatımı

- `test_08t_r3_blank_line.py:1-5` ve `:40` adı, `test_08t_r3_url_rules.py:3-6`, `:34`, `test_08t_r2_url_lines.py:2-5`, `:118` hâlâ tırnak, `expect` ve öznitelik taşımasını anlatıyor. Testler cevap düzeyi kural sayesinde geçiyor.
- `test_08t_r3_resume.py:5` "ilk satır tutulur" diyor; aynı dosya `:80-81` tersini doğruluyor.
- PR:
  - varsayım 10 (265) ve 12 (269) kaldırılan HTML taşımasını gerekçe olarak anlatıyor; 12'nin "replay → ilk satır tutulur" cümlesi d′ ile yanlış;
  - r3 tablosunun MINOR-r3-2 satırı (~224) yeniden adlandırılan bir testi ve f′'nin tersine çevirdiği davranışı anıyor;
  - güvenlik notu (280) r4'ün yedi yazımını anmıyor;
  - r4 NOTE-3 hiçbir yerde yok.

### MINOR-r5-4 · docs küçük sapmalar

- `/internal/guardrails/evaluate` (C4) artık 400 `placeholder_out_of_range` dönebiliyor (`api/guardrails.py:466-485`). Additive bir hata ama docs ve openapi yazmıyor; o çağrıda toplanan guardrail olayları da kaydedilmiyor.
- `api.md:540` facade düz yol için yalnız 400 diyor. Tamponlu akışta başlıklar gittikten sonra hata olayı + `[DONE]` geliyor.
- `guardrail.md:154` "açık satır kesilirse" diyor; kod işaretli ve kesilen satırda da `_lost` yapıyor (daha güvenli taraf).

## NOTE

1. `prime` geniş `except` ile yalnız scope'u logluyor (`runs.py:303`); bir programlama hatası iz bırakmadan fail-closed'a dönüşür. `exc_info=True` önerilir.
2. Replay'de (canlı akış süresi dolmuş) `after` ile bağlanan okuyucu artık saklanan bütün cevap satırlarını tutuyor (d′'nin yan etkisi; r4'te yalnız ilk satır). Fail-closed; PR'a yazılmalı.
3. `<<PII_123456789>>` (9 hane) ve `x<PII_1>>` HTML etiketi sayılıyor ve cevabın kalanı tutuluyor; `<` + `ı/İ/ſ/K` (Kelvin) da etiket sayılıyor (büyük/küçük harf duyarsızlığı). Hepsi fail-closed.
4. CR CR (boş satır) tek parçada değeri açıyor, bazı akış bölünmelerinde tutuyor. İkisi de güvenli (bağlantı değil), sadece tutarsız.
5. FOLLOWUP-162'ye eklenenler (r4 NOTE 1/2/4/5, r3 NOTE-4) PR:250'de var.
6. İşçinin kapı sayıları (1505, 149/147+2) bu turda yeniden sayılmadı; tam yığın koşuları aşağıda.
7. `test_08t_r3_url_scan` 1 s bütçesi yük altında kararsız: llmaas `make test`'te 1,33 s ile kırmızı, tek başına 0,33-0,42 s. Bütçe, r3 NOTE-1'deki gibi alt süreçte ya da gevşetilerek ölçülsün.

## Güvenlik turu

- **Sağlayıcıya ham değer:** gitmiyor. r3 uçtan uca `min_confidence` 0,8 bu SHA'da yeşil; `on_error=allow` + aralık taşması → sağlayıcı çağrılmıyor.
- **İstemci tarafı sıfır tık:** r1-r4'ün bütün yazımları ve bu turun markdown/CRLF listesi kapalı; adversarial okumada yeni yol bulunamadı.
- **Kişi verisinin karışması:** f′ ile 99.999.999 kapalı; 99.999.998 kenarı erişilebilirlik (MINOR-r5-1).
- **Erişilebilirlik ve işlev:** MAJOR-r5-1 (sahip değer görmüyor), MINOR-r5-1 (konuşma kalıcı düşmesi).
- **S8:** değişmedi.
- **06b-2 SSRF ve 147:** bu SHA'da iki profilde 138/138; gerileme yok.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | 1503 passed, 2 failed: `test_08t_r3_url_scan` 1 s bütçesi (1,33 s; aynı makinede başka iş yükü varken); dosya tek başına 3 kez 6/6, 0,33-0,42 s (`08t1a-r5-urlscan-rerun-llmaas.log`); NOTE-7 | `state/evidence/08t1a-r5-unit-llmaas.log` |
| `make test` airgap | 1505 passed (2:30) | `08t1a-r5-unit-airgap.log` |
| `make test-int` llmaas (tam yığın) | 849 passed, 5 skipped (11:15), kırmızı yok | `08t1a-r5-int-llmaas.log` |
| `make test-int` airgap (tam yığın) | 847 passed, 7 skipped (10:43), kırmızı yok | `08t1a-r5-int-airgap.log` |
| r2 + r3 + r4 entegrasyon probe'ları llmaas | 13/13 yeşil | `08t1a-r5-int-probe-llmaas.log` |
| r5 entegrasyon probe'u (`on_error=allow` aralık, taşınan 99.999.999) llmaas | 2/2 yeşil | `08t1a-r5-int-probe2-llmaas.log`, `state/reviews/08-tam-1a-r5-int-probe.py` |
| r3/r4/r4-adv mağaza probe'ları bu SHA'da | saldırı yazımlarının hepsi tutuldu | `08t1a-r5-rerun-*.log` |
| r5 markdown/CRLF + yeniden bağlanma + sınır probe'u | yukarıda | `08t1a-r5-probe.log`, `state/reviews/08-tam-1a-r5-probe.py` |
| Kuyruk penceresi probe'u | MAJOR-r5-1 | `08t1a-r5-tail-probe.log`, `state/reviews/08-tam-1a-r5-tail-probe.py` |
| 06b-2 SSRF probe + 06b-2/147 | 138/138 llmaas, 138/138 airgap | `08t1a-r5-06b2-probe-{llmaas,airgap}.log` |
| lint | NOT_RUN: işçi kanıtı "lint 0" | — |

## İşçiye kısa liste (DUZELT önerisi)

1. MAJOR-r5-1: `_HTML_TAG` istisnası `<(?!PII_\d{1,8}>>)[a-z]`; parçalı akış testi (1-11 karakterlik parçalar, rastgele parçalama, iki yol).
2. MINOR-r5-1 (karar): taşınan numaralar için yok sayma eşiği; `[0-9]`/`re.ASCII`.
3. MINOR-r5-2 (karar): docs/gerekçe (a) ya da konsol muafiyeti (b).
4. MINOR-r5-3/4, NOTE-1/2: bayat test ve PR metni, docs, `exc_info`.
