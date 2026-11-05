# 08-tam-1b r3 teyit (yalnız diff + test okuması)

- **SHA:** 7815d333671c53ebab48b20d51ff3661984946da (4567ed6 + 10 commit, 18 dosya +350/-30, `state/` 0)
- **İstek:** K-08T1B-0020 · ACK R-08T1B-0010 · Kararlar: KARARLAR "08 tam 1b r2 ekleri", K-08T1B-0017 (NOTE-5 tasarımı)
- **Yöntem:** `git diff 4567ed6..7815d33` ve testler; yığın yok, test koşulmadı (istek gereği). Altı denetim ajanı: beş kalem ve bir regresyon eleştirmeni. Her bulgu iki ayrı doğrulayıcıyla çürütülmeye çalışıldı. Testlerin düzeltme commit'inin atasında düşeceği statik olarak doğrulandı, koşularak değil.
- **Karar: ONAY-TEYIT** — BLOCKER 0, MAJOR 0, MINOR 0 (iki düşük madde NOTE'a indi), NOTE 12

## Kalem kapanışı

| Kalem | Durum | Kanıt |
|---|---|---|
| MINOR-r2-1 tek kişi verisi kuralı | **KAPANDI** | Tek kural `raw_staging.personnel_data(source, relpath)` (`raw_staging.py:67-71`): staging, sayaç, `Ek <n>` (`ingest.py:494`) ve reindex aynı fonksiyonu soruyor. Ham ingest yollarında `Document.filename` ağaç relpath'i (`raw_staging.py:225-235` → `store.py:114`). `test_08t_22c`: kaynak `confluence:HR`, yol `PRSIM-ARSIV` → ek `Ek 1`; silver ve breadcrumb'da ad yok. Test add0c6d'de `== ["Ek 1"]`'de düşer. |
| MINOR-r2-2 kırpma eşik sonrası | **KAPANDI** | `engine.py:191-198`: `kept = resolve_overlaps(hits)` eşik süzgecinden sonra; `trim_names` yalnız `kept`'e göre. r2'nin iki örneği (0,8 özel desen / `min_confidence` 0,85; 0,75 telefon / 0,8) `test_08t_27e/f`'de; ikisi de 37819c8'de düşer. r1 MINOR-5/6 yolu (yer tutucuya değen span) değişmedi. |
| NOTE-5 reindex sınırı | **KAPANDI** (kabul edilen tasarımla) | `check_reindex_silver` (`ingest.py:761-782`) yalnız SELECT çalıştırıyor, `reindex_silver`'ın ilk satırı (`:826`): ret olursa hiçbir belgeye dokunulmuyor. CLI kuyruğa yazmadan önce denetliyor, çıkış 2 + `prsim_requires_ner` (`cli.py:102-109, 271-281`). API gövdesinde bayrak yok; iş varsayılanı False. `pii_ner` kayıtları reddedilmiyor. Yol tabanlı PRSIM de sayılıyor (r2-1 kuralı). `test_08t_30`: dönüştürücü çağrılmıyor, kayıt `failed` ve `pii_regex@1` kalıyor; bayrakla 1 belge. `test_08t_30b`: CLI 2 + kod. |
| MINOR-r2-3 docs | **KAPANDI** | api.md, agentlar.md, guardrail.md, `08.yaml` açıklaması ve `ner.py`/`NerUnavailable` docstring'i kodla aynı: iç evaluate 503 `ner_unavailable`; facade koşusu 502 + koşu kodu `ner_unavailable` (`services/facade_agent.py:389-396`). OpenAPI değişikliği yalnız açıklama. |
| MINOR-r2-4 manifest | **KAPANDI** | Kayıtsız dosya `unregistered` kovasında (`raw_ingest.py:93-95`), `none` yalnız gerçek filtresiz kayıt. `test_08t_29` 2f77f2e'de düşer. |
| Sıra | uygun | Her kalemde önce test commit'i, sonra düzeltme; 7815d33 yalnız ruff format. |
| 09-1 merge sırası notu | geçerli | 1b önce merge; 09-1 judge `EgressGuard`'ına `ner=HttpNer(settings)` 09-1 dalında eklenmeli. |

## NOTE (hepsi engelsiz; FOLLOWUP adayı olanlar işaretli)

1. **(FOLLOWUP önerisi)** API reindex 202 dönüyor, audit'e başarılı yazılıyor; `prsim_requires_ner` reddi yalnız worker işinde görünüyor (`api/knowledge.py:505-526`). Kabul edilen tasarım bu (iş düzeyi, CLI ve API aynı yol); veri sızıntısı yok. Seçenek: uçta `check_reindex_silver` + 409, iş denetimi derinlik savunması olarak kalır. Doğrulayıcılar NOTE'a indirdi.
2. **(FOLLOWUP önerisi)** `--accept-personnel-data` ile reindex M3 kipinde loglanmıyor (`ingest.py:768-769` hemen dönüyor). `ingest-raw` aynı kip için `log.warning` yazıyor (`raw_ingest.py:321-325`); reindex de kayıt sayısıyla yazmalı. Bayrak `--layer gold` ile sessizce etkisiz.
3. NER hazırlık kodu hâlâ yalnız kaynağa bakıyor (`raw_ingest.py:296`, `cli.py:231`): yalnız yolu PRSIM olan ağaç NER düşükken `ner_unavailable` ile reddediliyor (`prsim_requires_ner` değil). İlk dosyadan önce red, sızıntı yok; 4567ed6'dan beri böyle.
4. Filtresiz (`text_filter` yok) kişi verisi kaydı reindex'te reddedilmiyor; bugün ağaçtaki tek `ingest_from_raw` çağıranı her zaman filtre veriyor (bir doğrulayıcı çürüttü). Sağlamlaştırma: "`pii_ner@` değilse ret".
5. Yol kuralı, çağıranın dizinli `filename` vermesine bağlı (`ingest.py:697` C6 girişi `path.name`'e düşebilir). Ağaçta tek çağıran relpath veriyor.
6. Silver reindex ve worker yeniden ingest ek listesi geçmiyor (önceden de böyle; ek adı yazılmaz, sızıntı yok).
7. Test boşlukları: `test_08t_30`'da negatif kontrol yok (yalnız yolu PRSIM kayıt, karışık kapsam, kişi verisi olmayan `pii_regex`, `full=True`, API/iş yolu); eşik testinde yer tutucu yok; facade 502 `ner_unavailable` testsiz.
8. Eşik altı telefon + ada yapışık rakamlar: rakamlar ad span'ının içinde `PERSON` olarak maskeleniyor (sızıntı değil, kategori kayması).
9. docs/bilgi-tabani.md yeni `unregistered` kovasını yazmıyor; geri alınan yeni sürüm kaydı eski satırın filtresinde sayılıyor (önceden de böyle).
10. Ret mesajı kaydın relpath'ini yazdırıyor (yol, içerik değil; PRSIM yolunda dizin adı kişi adı taşımıyorsa sorun yok, doğrulanmadı).
11. Küçük metin: agentlar.md "enforce" niteleyicisini atlıyor; `ingest_mask.PiiNerFilter.mask` docstring'i "never dropped whole" diyor, yer tutucu içine düşen span bütünüyle düşüyor; `RawIngestReport.current` tip notu eski.
12. 37819c8 test commit'i tek başına ruff formatlı değil (7815d33 düzeltti).

## Güvenlik turu

- **Kişi adı sınırı:** yol tabanlı PRSIM'de ek adı artık `Ek <n>`; eşik altı bulgu adı açık bırakmıyor. Kalan dar kenarlar NOTE 3-5 (sızıntısız).
- **M3 sınırı reindex'te:** bayraksız ret, belgeye dokunmadan; bayrak yalnız CLI'da. Görünürlük eksikleri NOTE 1-2.
- **Sözleşme:** OpenAPI yalnız açıklama; CLI bayrağı additive; iş imzası geriye uyumlu (varsayılan False).
- **NOT_RUN:** test ve yığın koşusu (istek gereği yalnız okuma). Testlerin düşüp geçtiği statik akıl yürütmeyle denetlendi; koşu kanıtı işçinin r3 kanıtları ve koordinatörün main kapısı.

## Karar

ONAY-TEYIT (7815d333671c53ebab48b20d51ff3661984946da). NOTE 1-2 için FOLLOWUP önerilir (koordinatör kararı).
