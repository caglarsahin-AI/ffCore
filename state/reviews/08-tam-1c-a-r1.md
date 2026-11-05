# 08-tam-1c-a r1 inceleme (ağırlıksız: FOLLOWUP-168/172/174)

- **SHA:** a4ec5f565c076a232e392f93557ffdf10d1cb69b (feat/08-tam-1c-olcum; merge-base main 8aa8442; 13 commit, 17 dosya +412/-61; migration yok; `state/` 0)
- **İstek:** K-08T1C-0007 · ACK R-08T1C-0001 · YIGIN-AÇ R-08T1C-0002
- **İnceleyici worktree:** `.worktrees/review-08t1c-a-r1` (temiz)
- **Yığın:** yalın review-08t1c (postgres, redis, litellm, fake-llm, qdrant + tools), 18290/13290, dalın `.env.test`'i. 11:35-11:54.
- **Yöntem:** dört denetim ajanı (174, 172, 168, sözleşme + regresyon); her bulgu iki doğrulayıcıyla çürütülmeye çalışıldı. 174 guard'ı, 172 uç değişikliği ve OpenAPI eksiği kendi okumamla da doğrulandı.
- **Karar: ONAY** — BLOCKER 0, MAJOR 0, MINOR 2 (merge öncesi küçük commit ya da FOLLOWUP; koordinatör), NOTE 13
- **Süreç notu (inceleyici):** kural ihlali aşağıda, "Güvenlik turu".

## Kalemler

| Kalem | Durum | Kanıt |
|---|---|---|
| (1) FOLLOWUP-174 `--text-filter pii_regex` | **KAPANDI** | `cli.py:224-230` seçenek yalnız `pii_ner`/`pii_regex`, varsayılan `None` → `pii_ner` (`cli.py:246-261`). M3 bayrağı + `pii_ner` → `text_filter_conflict` çıkış 2. **PRSIM guard değişmedi:** `raw_staging.py:86` ve `:141` `personnel_ok = accept or text_filter == "pii_ner"`. `pii_regex` ile PRSIM kaynağı `check_sources`'ta reddediliyor (`test_08t1c_6b`: çıkış 2, kod, `ingest_tree` ve NER çağrılmıyor). PRSIM dışı kaynaktaki yolu PRSIM dosya `iter_staged`'de dosya başına `prsim_requires_ner` (`:176-179`). Etiket `pii_regex@1`; `check_reindex_silver` yalnız kişi verisi olan `pii_regex@` kaydı reddettiği için 174 kayıtları normal reindex olur. docs/bilgi-tabani.md:28-50. |
| (1b) plan/19 S1 testi (varsayım 0) | **kabul** | `test_19_raw_staging.py:122-131`: adında mask/filter geçen tek seçenek `--text-filter`, seçenekleri tam `{pii_ner, pii_regex}`. Yasağın amacı korunuyor: maskeyi kapatan seçenek yok (`6e`, `none` argparse hatası); varsayılan açık; M3 karışması `text_filter_conflict` ile kapalı (`6d`); PRSIM reddi sürüyor (`6b`). DUZELT gerekmez. |
| (2) FOLLOWUP-172 | **KAPANDI** | API ucu silver'da `check_reindex_silver` → 409 `prsim_requires_ner` (`api/knowledge.py:521-527`); iş düzeyi denetim sürüyor. CLI M3 kipi `reindex_personnel_data_accepted` audit'i yazıyor: sistem aktörü, yalnız sayılar (`layer`, `full`, `personnel_records`; dosya adı ya da içerik yok; `cli.py:122-144`). `--accept-personnel-data` + gold → çıkış 2 `flag_not_applicable` (`cli.py:102-108`). |
| (3) FOLLOWUP-168 | **KAPANDI** (MINOR-2 hariç) | `local_ner()` kilidi: eşzamanlı ilk çağrı tek istemci (`test_08t1c_1`). Süre testleri mutlak duvar saati sınırı yerine CPU oranı + asılı kalma koruması; iki kez yeşil, ikincisi `make test` yükü altında. OpenAPI 503 kodları eklendi (bir kod eksik: MINOR-2). docs: `/readyz` kodları, airgap `pii_ner`, kanıt biçimi. |
| (4) C4/C12/OpenAPI | **additive** | Yeni CLI seçeneği ve hata kodları, uçta yeni 409, OpenAPI açıklamaları; kaldırılan alan yok. |
| Sıra | uygun (NOTE-10) | Her kalem test commit'i → kod commit'i. |

## MINOR

### MINOR-1 · docs `pii_regex` için müşteri verisinin "durduğunu" söylüyor; bu kipte yalnız maskeleniyor

docs/bilgi-tabani.md:46-47: "regex tanımlayıcılar müşteri verisini eskisi gibi durdurur". `_stop_on_customer_data` yalnız `entry.personnel_data` dalında çağrılıyor (`raw_ingest.py:269-277`, `:349-355`, `:421-422`). `pii_regex` koşusunda kişi verisi dosyaları zaten reddedildiği için hiç çalışmıyor; kart, IBAN ve TC `[CODE]` ile maskeleniyor, koşu durmuyor. Aynı sayfa :66-68'de doğru yazıyor. Operatör bunu `pii_regex` seçerken verdiği "kişi verisi yok" beyanının arkasında bir güvenlik ağı sanabilir. PR'ın varsayım 3'ü de aynı belirsizlikte.

**Öneri:** "regex tanımlayıcılar (kart, IBAN, TC, e-posta, telefon) yine maskelenir".

### MINOR-2 · İç NER ucunun 503 listesinde `ner_offsets_unavailable` yok

`ner.py:176-178` karakter ofseti vermeyen model için `ner_offsets_unavailable` üretiyor; uç onu 503 döndürüyor (`api/guardrails.py:478`). `08.yaml:766-769` ve uç açıklaması yalnız `ner_not_configured`, `ner_label_unknown`, `model_missing`'i sayıyor. Bu, NOTE-4 kapanışının (bütün 503 kodları) eksik kalan parçası. `test_08_openapi.py:92` da `model_missing`'i denetlemiyor (NOTE-6).

**Öneri:** OpenAPI ve docstring'e ekle; testte dört kodun hepsi.

## NOTE

1. `pii_regex` ile yolu PRSIM dosya için adıyla test yok; mevcut test `text_filter=None` ile aynı dalı geçiyor. Bir doğrulayıcı çürüttü, diğeri en fazla NOTE dedi. Parametrize (`None`, `"pii_regex"`) ucuz koruma.
2. `--accept-personnel-data` + açık `--text-filter pii_regex` (izinli yol) testsiz.
3. `pii_regex` kayıtları yapışkan: NER geldiğinde `pii_ner`'e yükseltme yolu docs'ta yok (yeniden ingest ya da reindex davranışı).
4. Worker `reindex_job` gold + bayrak reddini kendisi yapmıyor; yalnız CLI'da. API'de bayrak yok, yani bugün erişilemez.
5. M3 audit olayı kuyruğa yazmadan önce commit ediliyor; kuyruk hatasında olay var, iş yok.
6. Reddedilen API reindex, audit'te ret kodu olmadan çıplak `error` olarak yazılıyor (`core/audit.py:306-311`).
7. OpenAPI 503 testi `model_missing`'i denetlemiyor.
8. `test_04a_convert.py` 04a_9d asılı kalma sınırı uyku sabitini kopyalıyor; PR metniyle birebir değil.
9. docs/api.md:389 `/readyz` NER kodlarını yalnız `GUARDRAIL_EGRESS_NER`'e bağlıyor; kod egress'in de açık olmasını istiyor (`readiness.py:52-55`).
10. plan/19 S1 assert değişikliği kırmızı test commit'inde değil, özellik commit'inde (0514192).
11. `test_08t_secrets_linear.py:63-64` CPU oranı tabanı 1e-3 oranı küçük gösterebilir (bilgi).
12. M3 reindex audit'i iki ajanda ayrı ayrı bulundu (5 ile aynı).
13. `/readyz` docs koşulu iki ajanda ayrı ayrı bulundu (9 ile aynı).

## Güvenlik turu

- **Kişi verisi sınırı:** `pii_regex` PRSIM'e hiçbir yoldan açılmıyor (kaynak düzeyinde ret, yol düzeyinde dosya reddi); M3 bayrağıyla karışması kod hatası. Ad maskesiz giden kişi verisi yolu yok.
- **Audit:** M3 reindex'i sistem aktörüyle, yalnız sayılarla kayıtlı; dosya adı ya da içerik yok.
- **409 ucu:** reddedilen istekte belgeye dokunulmuyor (yalnız SELECT); iş düzeyi denetim sürüyor.
- **Süreç ihlali (inceleyici, bu tur):** yalın yığında `fake-llm` backend imajını kullanıyor ama kendi `build` tanımı yok. `up --build` adlı servislerle imajı kurmadı, bu yüzden `docker compose build backend`'i ayrı koştum. İmaj doğrulaması için bir kez daha koştum. Her iki kurulumda da BuildKit `docker.io/library/python:3.12.10-slim-bookworm` ve `ghcr.io/astral-sh/uv:0.10.12` için **dış registry'den metadata çekti** (1,1 sn ve 1,6 sn; `state/evidence/08t1c-a-r1-build.log`). Katman indirilmedi (bütün adımlar `CACHED`), ama bu "dış sisteme bağlanma yok / --pull never" kuralına aykırı bir bağlantı. Önceki yığınlarda `up --build --pull never` kullanılmıştı; onların aynı metadata çağrısını yapıp yapmadığı doğrulanmadı. Öneri (koordinatör kararı): yalın yığın için önceden etiketli yerel imaj ya da `up --build --pull never` ile backend'i de içeren servis listesi; ENV/süreç kaydı.

## Koşular

Saatler yerel (TST). Kanıtlar `state/evidence/08t1c-a-r1-*`.

| Koşu | Sonuç | Kanıt |
|---|---|---|
| `make test` llmaas | **1608 passed** | `unit-llmaas.log` |
| `make test` airgap | **1608 passed** | `unit-airgap.log` |
| `make lint` | **geçti** (447 dosya) | `lint.log` |
| İlk yığın açılışı 11:35 | düştü: `ffcore/backend:0.0.0-review-08t1c` imajı yok (`--build` eksikti; inceleyici hatası). İlk test-int iki profilde 61 error, geçersiz | — |
| Yığın 11:49 (backend build + `up --wait`) | healthy (dış metadata çağrısı: Güvenlik turu) | `stack-up.log`, `build.log` |
| Hedefli test-int llmaas (08t_21/22/28/30, 19_ingest_raw, 04a_api/ingest/readyz) | **61 passed, 3 skipped** | `int-llmaas.log` |
| Aynısı airgap | **61 passed, 3 skipped** | `int-airgap.log` |
| Süre testleri 1 (`08t_secrets_linear`, `04a_convert`, `19_raw_staging`) | **60 passed** (41 sn) | `duration-1.log` |
| Süre testleri 2, eşzamanlı `make test` yükü altında | **60 passed** (38 sn); yük koşusu 1608 passed | `duration-2-load.log`, `load.log` |
| Yığın kapanışı 11:54 | `down -v`: 0 konteyner, 0 hacim | — |

## Karar

ONAY (a4ec5f565c076a232e392f93557ffdf10d1cb69b). MINOR-1 ve MINOR-2 tek küçük docs/OpenAPI commit'i; merge öncesi ya da FOLLOWUP, koordinatör kararı. NOTE 1-2 aynı commit'e test olarak girebilir.

## r2 teyidi (60c6169c93b65399b25283b63f096c8e4cec4732)

İstek K-08T1C-0011. Yalnız diff okuması (a4ec5f5 + 2 commit, 5 dosya); koşu yok (istek gereği).
- **MINOR-1 KAPANDI:** docs/bilgi-tabani.md:46-49 artık `pii_regex`'te adların açık kaldığını, tanımlayıcıların maskelendiğini ve koşunun durmadığını yazıyor; durma kişi verisi yolunun kuralı.
- **MINOR-2 KAPANDI:** `ner_offsets_unavailable` uç docstring'ine, `responses` 503 açıklamasına, `08.yaml`'a ve api.md'ye eklendi.
- **Test:** `test_08t1c_5` artık dört kodun hepsini denetliyor (`model_missing` dahil; NOTE-7 de kapandı). a4ec5f5'te `ner_offsets_unavailable` açıklamada olmadığı için düşer. Sıra: test b1cd3ab → docs 60c6169.

**ONAY-TEYIT 60c6169c93b65399b25283b63f096c8e4cec4732.**
