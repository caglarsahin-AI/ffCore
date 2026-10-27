# 08. Guardrail ve PII (Türkçe) [FFCore Guard]

**Bağımlılık:** 03a (migration FK ve `projects`), 03b (audit decorator'ı). **Süre:** 5,5 gün, iki PR. **08-lite (PoC, 3 gün):** engine, 7 aşama, `regex` PII (TC, telefon, IBAN, e-posta, kart), `secrets`, `tool_args`, Monitor/Enforce, test paneli, `POST /internal/guardrails/evaluate`. **08 tam (M4, 2,5 gün):** Türkçe NER (ad-soyad/kurum/konum), `injection` sınıflandırıcısı, akış tamponlayıcı, `egress` kalibrasyonu, PRSIM ingest guard'ı (karar 5). **Dalga:** 08-lite dalga 2, **03a merge edildikten sonra** başlar (B3; 03b ile paralel). 06a bu paketin engine'ini ve hook adlarını bağlar; 08-lite önce biter. **PoC:** 08-lite.

## Amaç

Modele giden ve modelden dönen her metni politika setine göre taramak: kişisel veri maskeleme (TC kimlik dahil), gizli anahtar tespiti, prompt injection, konu dışı, araç argümanı kuralları. Sonuç: engelle, maskele, uyar ya da sadece logla.

## Kapsam

### Veri modeli

- `guardrail_policies(id, project_id, key, name, rules jsonb, mode: off|monitor|enforce, short_circuit bool (varsayılan true), on_error: block|allow (varsayılan block, fail-closed), block_message_tr, is_default)` (C23: metinde geçen alanlar tabloya alındı)
- (R7.1, tek doğru liste; N23) `guardrail_events(id, run_id?, project_id, policy_key, stage: prompt.pre|input.pre|output.pre|output.stream.delta|tool.pre|tool.post|egress, rule, action_taken: block|redact|mask|tokenize|warn|log, status: passed|redacted|failed, input_preview (ilk 60 karakter, maskeli), findings jsonb (kategori · güven), severity, source: agent-playground|chat|api|channel, matches jsonb (maskeli), latency_ms, ts)`. Aşamalar: `prompt.pre` kullanıcı turunda bir kez; `input.pre` her model çağrısından önce; `output.pre` cevap çağırana ulaşmadan; `output.stream.delta` akış sırasında; `tool.pre` araç adı ve argümanları; `tool.post` araç sonucu modele gitmeden; `egress` (`llmaas`) modele gidecek nihai paket.
- (R7.1) `pii_policies(id, project_id, key, engine: regex|ner, default_action: log|redact|mask|tokenize|block (tek aksiyon listesi `guardrail_events.action_taken` ile aynı; eski `detect` = `log`, N23), languages[], min_confidence, context_boost bool, categories jsonb (kategori → {enabled, severity, action, lang}), custom_patterns jsonb, is_default)`; Türkçe kategori seti: TC kimlik (checksum), TR telefon, TR IBAN, VKN, plaka, TR pasaport, TR adres, kişi adı, kurum adı, konum, e-posta, kart, CVV, PIN, GPS, MAC, API token, şifre. Varsayılan açık: e-posta, telefon, kart, IBAN, TC, TR telefon, TR IBAN, CVV, PIN; kişi adı `egress`'te `tokenize`; kapalı: doğum tarihi, VKN, plaka, pasaport, adres, kurum, konum (politika ile açılır).

### Kural türleri (`rules` JSON'daki her öğe `{type, action, params}`)

| type | Ne yapar | Uygulama |
|---|---|---|
| `pii` | TC kimlik (algoritmik doğrulama), telefon, e-posta, IBAN, kart no, doğum tarihi, ad-soyad, kurum, konum | Presidio + özel Türkçe tanıyıcılar; **ad-soyad/kurum/konum için gerçek Türkçe NER modeli** (R7.2 kararı): Hugging Face'teki Türkçe BERT tabanlı NER modellerinden biri (`savasy/bert-base-turkish-ner-cased` ya da dengi; lisans kontrolü), Presidio'ya özel `NlpEngine` olarak bağlanır; model imaja gömülür ve 12'de aynaya eklenir; spaCy Türkçe modeli yoktur, kullanılmaz. CPU gecikmesi ayrı ölçülür ve `docs/guardrail.md`'ye yazılır |
| `secrets` | API anahtarı, şifre, bağlantı dizesi | regex + entropi |
| `injection` | "önceki talimatları yok say", rol değiştirme, kodlanmış payload | kural listesi + küçük sınıflandırıcı (LLM Guard'ın `PromptInjection` modeli yerel; CPU gecikmesi **doğrulanmadı**, DeBERTa sınıflandırıcı yük altında 150-500 ms olabilir; işçi ölçer ve `docs/guardrail.md`'ye yazar, kriter R7.3'teki koşullu bütçedir) |
| `topic` | izin verilen konular dışı | LiteLLM üzerinden ucuz model çağrısı ya da anahtar kelime; `action: warn` varsayılan |
| `tool_args` | araç argümanlarında yasak kalıp (örn. SQL'de `pg_`, dış domain) | regex, aksiyon bazlı |
| `output_format` | JSON şema doğrulama | jsonschema |
| `banned_words` | yasaklı kelime listesi | basit |

### Maskeleme modu

- `redact`: `[TC_KIMLIK]` gibi etiket.
- `tokenize`: `<<PII_1>>` yer tutucu; eşleme Redis'te run süresince (`PII_TOKEN_TTL_S`), çıkışta geri çevrilir. Belgeden gelen ad-soyadın cevapta görünmesi gerektiğinde bu mod; sağlayıcıya yine de gitmez. **Akışta geri çevirme (C17):** `output.stream.delta` aşamasında kayan tamponlayıcı `<<` görünce `>>` gelene kadar (en çok 16 karakter) metni tutar; yer tutucu iki SSE chunk'ına bölünse de istemciye ham `<<PII_n>>` sızmaz (kabul kriteri).

### Entegrasyon

- `backend/app/guardrails/engine.py`: `evaluate(text, stage, policy) -> Decision(action, text_out, events)`. Kurallar paralel çalışır, en sert aksiyon kazanır.
- 06a'daki `guard_in`, `guard_out`, `tool.pre`, `tool.post` (ve `llmaas`'ta `egress`) kancalarına 06a işçisi bağlar; bu paket engine'i, kural türlerini, tanıyıcıları ve `POST /internal/guardrails/evaluate` (yalnızca iç ağ, `SERVICE_TOKEN`) ucunu teslim eder ve kendi testleriyle kanıtlar (B3).
- (P3, düzeltildi B3) **Doğrudan model yolu da kapsanır, ama LiteLLM içinde kanca yoktur:** dış istemci LiteLLM'e hiç ulaşmaz (PLAN 5 R1.2); `chat-default`'a giden düz model isteği facade'da (06b) aynı engine'in `input.pre`/`output.pre` (`llmaas`'ta `egress`) aşamalarından geçer. `litellm_hook.py`, `CustomGuardrail` ve model başına `guardrails:` kaydı **yazılmaz** (ARCH-09: tek denetim noktası facade; çift HTTP döngüsü yok). API anahtarı kapsamı `scopes` ile doğrudan model erişimi (`chat_direct`) kapatılabilir; kapalıysa yalnızca `agent:` yolu kullanılabilir (03c).
- 02: Langfuse'a giden içerik `guard_in` sonrası metin.
- 07: onay ekranında gösterilen argümanlar maskeli.
- API: politika CRUD; `POST /guardrails/test` (metin ver, karar gör; önyüzde "dene").

### Politika modeli ve davranış gereksinimleri (konsol incelemesinden, bağlayıcı)

- İki ayrı varlık: PII politikası (`pii_policies`, yeniden kullanılabilir) ve guardrail politikası (`guardrail_policies`: kural zinciri + aşama bağlama + mod). Guardrail'deki `pii` kuralı `rules[].pii_policy_key` ile bir PII politikasına referans verir; referans kayıt anında doğrulanır. Kural çalışamazsa davranış `guardrail_policies.on_error: open|closed`; varsayılan `closed` (Cognipeer'de fail-open gözlendi; bizde kapalı).
- `pii_policies` alanları (Veri modelinde tanımlı): `engine` (regex ya da ner; motor değişince kategoriler sıfırlanır), `default_action` (detect, redact, mask, tokenize, block), `languages[]` (dil bazlı kalıplar yalnızca dil açıkken), `min_confidence` (0 / 0,5 / 0,8 / özel), `context_boost` (yakında "TC", "kimlik no" gibi kelime varsa skoru artır), `categories` (her biri önem, dil, aksiyon), `custom_patterns`. Maskeleme biçimi son haneleri açık bırakır (`*******8950`, `a***********@ornek.com`).
- Test paneli (`POST /guardrails/test`): metin + Detect / Redact / Mask / Tokenize; çıktı metni ve bulgular tablosu (kategori, önem, değer, güven, **kanıt**: "checksum doğrulandı · bağlam kelimesi 'tc kimlik'", offset). Kanıt alanı zorunlu (denetimde "neden maskelendi").
- Modlar `off|monitor|enforce`: Monitor'da her şey çalışır ve kaydedilir, karar uygulanmaz ("gerçek trafikle ölç, sonra aç"); yeni politika Monitor başlar; Enforce'a geçiş audit olayı.
- Aşamalar `stage` enum'undaki yedi değer; politika başına hangi aşamalarda çalışacağı seçilir (`rules[].stages[]`).
- Zincir: yerel kurallar sırayla, model ve webhook tabanlı olanlar sonda birlikte; `guardrail_policies.short_circuit bool` (kapalıysa hepsi çalışır); bir kuralın tek aksiyonu vardır, aynı kuralı başka aşamada farklı aksiyonla istemek için kural kopyalanır. `Decision.text_out` sonraki kuralın girdisidir (redact çıktısı sonraki kurala akar); `block` zincirin tamamını keser.
- `injection` kuralı: yerel sınıflandırıcı + isteğe bağlı LLM judge; hassasiyet `low|balanced|high`; önce Monitor ile yanlış pozitif oranı ölçülür ("numaramı geri yaz" gibi masum cümleler Cognipeer'de engellendi).
- `secrets` kuralı (vendor pattern + yüksek entropi, `block`) varsayılan politikada açık.
- `guardrail_policies.block_message_tr`: engellemede son kullanıcıya gösterilen metin, kural başına sebep; 06'daki hata gövdesine girer.
- `guardrail_events` ek alanlar: `status (passed|redacted|failed), input_preview (ilk 60 karakter, maskeli), findings jsonb (kategori · güven), severity, source (agent-playground|chat|api|channel)`. 10'da liste ve dashboard: toplam / geçen / kalan, geçme oranı, ortalama gecikme, bulgu türü ve önem dağılımı, günlük grafik.
- Gecikme referansı: regex PII 13–18 ms, model tabanlı shield 650–1.700 ms (Cognipeer ölçümü); kabul kriteri R7.3'te.
- Ham mesaj saklama (02 ve 03 ile ortak): maskelenmiş istek gövdesi saklanır, ham kullanıcı mesajı `content` sınıfında kısa ömürlü.


## Profil farkları (PLAN.md 2b)

- `llmaas` profilinde `engine.evaluate` için yeni aşama `egress`: modele gönderilmek üzere olan nihai paket (sistem prompt'u, geçmiş, RAG parçaları, araç sonuçları) birlikte taranır; bu, giriş aşamasından farklı olarak belgeden ve veritabanından gelen metni de kapsar.
- (R7.4) `egress` aşamasında **aşama bazlı varsayılan kategori seti**: TC kimlik, telefon, e-posta, kart, CVV, PIN → `tokenize` (çıkışta geri çevrilir); ad-soyad → `tokenize`; IBAN ve VKN → politikaya göre (sözleşme karşılaştırmasında gerekebilir, varsayılan `tokenize`); doğum tarihi, tutar, tarih → kapalı (model karşılaştırma yapabilmeli); `secrets` → `block`. Sözleşme parçalarındaki karşı taraf adı tokenize edilir, geri çevrilir; model yer tutucuyla tutarlı çalışır (aynı kişi aynı `<<PII_n>>`).
- (R7.2) `llmaas` kabul eşikleri: TC kimlik, telefon, IBAN, e-posta recall ≥ 0,99; ad-soyad ≥ 0,90 (gerçek NER ile). Test seti ekip dışı 100 cümle (sentetik, çeşitli yazım biçimleri). Yayın kapısı (06 `publish` admin onayı) yalnızca TC/telefon/IBAN/e-posta eşikleri altında tetiklenir; ad-soyad eşiği altı yayını engellemez, raporda kırmızı görünür ve M4'te karar verilir.
- `guardrail_events` için `egress` olayları ayrı rapor: "dışarı giden metinde ne maskelendi" (10'da ekran).
- `egress` aşaması seed bayrağı `GUARDRAIL_EGRESS_ENABLED` ile açılır (`llmaas` seed'inde true, `airgap` seed'inde false; kodda profil dalı yok, N21).

## Teslimatlar

- Migration, engine, tanıyıcılar, router, testler.
- Türkçe PII test seti `data/samples/pii/` (100 cümle, etiketli, sentetik) **13a'da bağımsız üretilir** (C18); bu paket onu tüketir, kendi test setini yazmaz.
- `docs/guardrail.md`: kural türleri, aksiyonlar, Türkçe PII kalite raporu (precision/recall).

## Kabul kriterleri

- Test setinde TC kimlik ve telefon için recall ≥ 0,98; ad-soyad için ≥ 0,85 gerçek NER ile (ölçülüp yazılır; `llmaas` eşikleri yukarıda).
- (R7.3) Gecikme, koşullu: boşta makinede yerel kurallar + NER + injection modeli, 1.000 karakterlik metin, P95 < 300 ms; model üretirken (yük altında) ayrı ölçülür ve `docs/guardrail.md`'ye yazılır, kriter değil. LLM tabanlı `topic` kuralı ayrı bütçe (< 2 s, yalnızca `llmaas`/`gpu`).
- `tokenize` modunda çıkıştaki yer tutucular doğru geri çevrilir; `<<PII_` ve `1>>` ayrı chunk'larda gelse de istemciye ham yer tutucu ulaşmaz (C17).
- Politika `block` dediğinde run `failed` olur ve kullanıcıya Türkçe açıklama döner; olay `guardrail_events`'te.

## Teknik notlar

- Presidio Analyzer ve Anonymizer Python paketleri; Türkçe NER modeli (`savasy/bert-base-turkish-ner-cased` ya da lisansı doğrulanmış dengi, `transformers` ile) imaja gömülür ve 12'deki aynaya tam adıyla eklenir; spaCy Türkçe modeli yoktur ve gerekmez (N20).
- TC kimlik doğrulama: 11 hane, ilk hane 0 değil, 10. ve 11. hane kontrol algoritması.
- Geliştirmede gerçek kişisel veri kullanılmaz; test seti sentetik.

## Kapsam dışı

Red-team otomasyonu, LLM tabanlı serbest politika yargıcı (09'daki judge altyapısı ileride buraya bağlanabilir).
