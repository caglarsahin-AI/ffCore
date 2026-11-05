# 08-tam-1c-b r1 inceleme (NER ölçüm ve seçim)

- **SHA:** 5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809 (feat/08-tam-1c-b-olcum; main 105d176 + 8 commit; 2a7b430 + r1b öz-kontrol commit'i 5e9a688; `state/` 0)
- **İstek:** K-08T1C-0020 + K-08T1C-0022 (r1b ekleri 8-9) · ACK R-08T1C-0006 (2a7b430), R-08T1C-0008 (5e9a688)
- **Yöntem:**
  - Statik okuma 2a7b430'da: üç denetim ajanı; her bulgu iki ayrı doğrulayıcıyla çürütülmeye çalışıldı. Üstüne 2a7b430..5e9a688 delta'sı kendim okundu.
  - Koşular yalnız 5e9a688'de, yığınsız: `ffcore/tools:0.0.0-08t1c` imajı (build yok), `--network none`, `04a-knowledge-core_model_cache:/models:ro`. Komut satırı, ağ arayüzleri (yalnız `lo`, tünel) ve `/models ro` bağlaması logda.
- **Karar: ONAY** — BLOCKER 0, MAJOR 0, MINOR 6, NOTE 7

## Kontrol listesi

| Madde | Durum | Kanıt |
|---|---|---|
| (1) `aggregation_strategy="first"` | **KAPANDI** (MINOR-1) | `ner.py:156-164`; birim `test_08t1c_7c` (kırmızı kanıtı `08t1c-b-red.log:17`). Gerçek model: `test_08t1c_8` PERSON span'ları kelime sınırında, bu turda yeşil. `simple` ile parçalı maskeleme yalnız keşif çıktısında görülüyor (`explore2.log:192-250`: `'l'`, `'AR'`, `'LIK'`; PERSON kesinlik 0,56 → `first` ile 1,00); test koşusu olarak hiç kırmızı görülmedi (MINOR-1). |
| (2) int8 | **KAPANDI** | Nicemleme yalnız `torch.nn.Linear` (`ner.py:167`). Yükleme yolunda try/except yok, fp32'ye sessiz düşme yok; hata `/readyz`'e `warmup_failed` olarak çıkıyor. NER ağırlığını yükleyen her yol `NerRecognizer.load` üzerinden int8 alıyor (API `LocalNer`, readiness, facade, quality CLI); worker'lar `HttpNer` ile ağırlık yüklemiyor. Eşitlik testi `test_08t1c_11` (PERSON/ORG satırları eşit) bu turda yeşil. |
| (3) Seçim ve sabitleme | **KAPANDI** (MINOR-4) | akdeniz27 ölçümle seçildi; savasy tabloda "lisans belirtilmemiş", seçilmedi. `NER_REVISIONS` sabit commit (`99995f7…`), indirmede yalnız safetensors; `models.txt` güncel. `verify.sh --models /models` → **OK 73 dosya** (`--network none`). Eski ağırlıklı volume: MINOR-4. |
| (4) Uzun metin | **KAPANDI** (NOTE-5) | `test_08t1c_9`: üç 512-token penceresi; her adın her harfi kapsanıyor, ad dışı span yok. Kesin eşitlikten "her harf kapsanır" özelliğine gevşetilmesi gerekçeli (soyadı ayrı B-PER); ad dışı span yasağı korunuyor. |
| (5) Gecikme | **NOT_RUN (kabul, hedef donanım; ENV-177)** | PR'da açık. `make test-ner-latency` tek satır, kendi `ner_latency` işaretiyle (r1b), P95 yazıyor. Bilgi amaçlı koşu bu dizüstünde: **P95 191 ms** (< 300; kabul sayılmaz). docs tablosu ve geçiş şartı var (MINOR-5: docs aralığı loglarla uyumsuz). |
| (6) Egress PERSON uçtan uca (`-m models`) | **VAR** (NOTE-7) | `test_08t1c_10`: gerçek model + `builtin_default(True)` → ad ve telefon ham kalmıyor. r1b özellik assert'i aşağıda. |
| (7) lint, make test, `-m models`, verify | **yeşil** | Koşular tablosu. |
| (8) r1b işaret ayrımı | **KAPANDI** | `ner_latency` işareti `pyproject.toml` ve `conftest.FLAGS`'ta; gecikme testi ayrı dosyada; `-m models` koşusunda **1 deselected** (gecikme), `make test-models` onu koşmuyor. |
| (9) r1b egress özellik testi gevşedi mi | **Gevşemedi (sızıntı açısından)** | Kesin metin `"<<PII_1>> <<PII_2>> arar."` yerine: dört ham parça yok + `re.fullmatch(r"(<<PII_[0-9]+>> ){2,3}arar\.")`. "arar." dışındaki her şeyin yer tutucu olması zorunlu, kısmi maske geçemez. Kaybedilen: adın ve telefonun ayrı kategori olduğunun kanıtı (NOTE-6). |

## MINOR

1. **Gerçek model kelime-bütünlüğü testi `simple` ile hiç kırmızı görülmedi.** Kırmızı koşuda `test_08t1c_8` model yapılandırılmadığı için ERROR verdi; kanıt keşif çıktısı. PR metni "kırmızı" iddiasını keşif loguna bağlamalı.
2. **PII setindeki her altın PERSON span'ının tamamen kapsandığını assert eden test yok.** Kalite puanı herhangi bir örtüşmeyi "bulundu" sayıyor (`quality.py:49-70`; `'Ayşe'` tek başına `'Ayşe Demir'`'i bulmuş sayılıyor). Recall 1,00 ve kelime sınırlı span'lar soyadının açık kalmadığını kanıtlamıyor.
3. **Kalite ve int8 eşitlik ölçümü motorun `min_confidence` eşiğini yok sayıyor.** Motor 0,5 altını atıyor (`engine.py:196-200`); ölçüm her tahmini sayıyor. int8 skorları kaydırabildiği için eşikte bir PERSON ölçümde görünüp üretimde düşebilir.
4. **Eski volume'da lisanssız savasy ağırlıkları ve pickle dosyaları var; air-gap paketi onları da taşır.** Canlı kanıt (`08t1c-b-r1-rv-volume-ner.log`): `04a-knowledge-core_model_cache` içinde `models--savasy--bert-base-turkish-ner-cased` ve iki NER modelinde `pytorch_model.bin`.
   - `save.sh` volume'u bütünüyle paketliyor; `verify.sh` yalnız listelenen dosyaları denetliyor, fazlasını işaretlemiyor.
   - Öneri: `save.sh` yalnız `models.txt` dosyalarını paketlesin ya da `verify.sh` listede olmayan model dizinlerini fail-loud işaretlesin; docs'a temizlik adımı.
5. **docs gecikme iddiaları kanıt loglarıyla uyuşmuyor** (`guardrail.md:361, 384-387`). "P95 297-840 ms" diyor, PR ve log 158-840 ms; "int8 her koşuda 2-3 kat hızlı" 4 iş parçacığı turu için tutmuyor. Bu turda dizüstü 191 ms.
6. **Uzun metin testi kod commit'inden sonra kesin eşitlikten gevşetildi.** Gerekçeli ve ad dışı span yasağı duruyor; doğrulayıcılar NIT'e indirdi. MINOR-2 ile birlikte "ad tam kapsandı" kanıtı zayıf.

## NOTE

1. int8 eşitliği sayıları karşılaştırıyor, span'ları değil (ofsetler tokenizer'dan, kaymaz; etiket değişimi `test_08t1c_8` ile sınırlı).
2. Bulgu kanıt metni int8'i göstermiyor (commit kimliği yeterli).
3. Yalnız safetensors kuralı indirmede uygulanıyor, yüklemede değil (`use_safetensors` yok). transformers ikisi varsa safetensors'ı seçer; doğrulanmadı.
4. `.env.example` "`make models` tam bu commit'i indirir" diyor ama indirme ve denetim `NER_REVISION` env'ini değil kod sabitini okuyor; kurulumcu env'i değiştirirse `make models` "ok" der, API `model_missing` ile durur.
5. Uzun metin token sayısı (1.862) kanıt logunda yok; test yalnız > 1536 assert ediyor.
6. r1b egress testi adın ve telefonun ayrı yer tutucu (kategori) olduğunu artık ayırt etmiyor; sızıntı kanıtı korunuyor.
7. Egress PERSON gerçek model testi yalnız süreç içi `LocalNer`; worker yolu (`HttpNer` → iç uç → `merge_spans`) gerçek ağırlıkla sınanmıyor. Tek koşuluk geçiş kapısı (`make test-ner-latency`) aynı makinede 158-840 ms oynuyor; tekrar önerisi docs'a.

## Güvenlik turu

- **Kişi adı sınırı:** `first` birleştirme parçalı maskelemeyi kapatıyor (keşifte `simple` 'LIK', 'AR' sızdırıyordu). int8 PERSON kalitesini koruyor. Egress özelliği gerçek modelle yeşil. Kalan kanıt boşlukları MINOR-2/3.
- **Air-gap:** koşular `--network none`, model volume `:ro`; `verify.sh` OK. Paket içeriği MINOR-4: lisanssız model ve pickle taşınabilir.
- **Lisans:** seçilen akdeniz27 MIT (PR tablosu).

## Koşular

Saatler yerel (TST). Kanıtlar `state/evidence/08t1c-b-r1-rv-*`.

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make lint` | **geçti** (477 dosya) | `rv-lint.log` |
| `make test` llmaas | **1743 passed** | `rv-unit-llmaas.log` |
| `make test` airgap | **1743 passed** | `rv-unit-airgap.log` |
| `-m models tests/models` (`--network none`, `/models:ro`) | **20 passed, 1 deselected** (gecikme). 3 error: `test_04a_e2e_stack.py` (1/2/14) canlı yığın ve E2E kimlik bilgisi ister; 1c-b dışı, NOT_RUN | `rv-models.log` |
| `-m ner_latency` (bilgi amaçlı, dizüstü) | 1 passed, **P95 191 ms**; kabul hedef donanımda (NOT_RUN) | `rv-latency.log` |
| `verify.sh --models /models` (`--network none`) | **OK 73 dosya** | `rv-verify-models.log` |
| Volume NER içeriği | akdeniz27 + **savasy** + iki `pytorch_model.bin` (MINOR-4) | `rv-volume-ner.log` |

## Karar

ONAY (5e9a68881a4f51d9a2cd1ad91aeab8eaabc0a809). MINOR-4 (air-gap paketine lisanssız model) ve MINOR-2 (ad tam kapsama testi) merge öncesi küçük commit önerilir; diğerleri FOLLOWUP. Koordinatör kararı. Gecikme kabulü (kabul 3) hedef donanımda, ENV-177.
