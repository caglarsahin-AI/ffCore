# PR: 08-lite guardrail engine, regex PII, policy API

**Paket:** 08-lite · **Sınıf:** [A] (bağımlılık yok; paylaşılan dosya dokunuşları S1-S5'te soruldu) · **Branch:** feat/08-lite-guardrails · **Baz commit:** 591aac3 · **Oturum:** ffcore-test-08-lite · **Durum:** VERIFIED (r1 düzeltmesi) · **HEAD:** 7a7dc35e156b17f72e567dad3bfbf584f4f7a898 (r1 incelenen: 21812317)

## Plan (kodlamadan önce)

### 1. Bulunan semboller ve dosyalar (worktree @ 591aac3, rg/okuma ile)

| Sembol / dosya | Ne için |
|---|---|
| `ffcore/core/auth.py`: `resolve_actor`, `Actor`, `SERVICE_ACTOR` (`actor_type="system", actor_id="service"`), `require_role(min_role, write=)`, `require_superadmin`, `authorize`, `RoleRequirement` | politika uçlarının yetkisi; `/internal` için servis hesabı kontrolü. OBO altında aktör `user` olur, servis kontrolü onu reddeder |
| `ffcore/core/audit.py`: `@audited(action, resource_type, load_before=)`, `write_event_detached`, `mask` | her mutasyon tek audit olayı; Enforce geçişi before/after `mode` ile görünür |
| `ffcore/api/common.py`: `ERROR_RESPONSES`, `SessionDep`, `not_found`, `conflict`, `invalid`, `path_resource` | router kalıbı (03a `api/models.py` örnek alınır) |
| `ffcore/api/schemas.py`: `Strict`, `Patch` (exclude_unset kuralı, r1 MAJOR-2) | kendi şemalarım `guardrails/schemas.py`'de bu tabanlardan türer; 03a dosyası değişmez |
| `ffcore/core/errors.py`: `ApiError`, OpenAI hata gövdesi | `guardrail_*` hata kodları |
| `ffcore/models/base.py` `Base` (adlandırma kuralı), `models/identity.py` `Timestamps` | `guardrail_policies`, `pii_policies` kök tablo (C3 ortak kolonlar) |
| `ffcore/api/__init__.py` `api_router` (prefix `/api/v1`), `models/__init__.py` | kendi satırım (GOREV izni) |
| `ffcore/api/openapi_export.py` `render()` = `api_router.routes`'un tamamı → `openapi/03a.yaml`; `tests/contract/test_03a_openapi.py` bayt eşitliği | **çakışma, S1**: router eklenince 03a.yaml testi kırılır |
| `tests/unit/test_03a_write_flag.py` `WRITE_EXEMPT = {login, logout, change_password}`, `RoleRequirement.write` taraması | **çakışma, S2**: `/internal/...evaluate` ve test paneli POST'tur |
| `tests/contract/test_c3_common_columns.py` `C3_EXCEPTIONS` | `guardrail_events` append-only istisnası (CONTRACTS C3'te zaten adlı, yeni istisna değil) eklenir |
| `alembic/versions/03a_0001` (`branch_labels=("03a",)`, `down_revision="0001"`), `03b_0001` | dal `08`: `down_revision="0001"`, `branch_labels=("08",)`, **`depends_on=("03a_0001",)`** (FK `projects` için sıra) |
| `deploy/docker-compose.yml` `&app-env`: `REDIS_URL` zaten var; `GUARDRAIL_EGRESS_ENABLED`, `PII_TOKEN_TTL_S` yok | **S3** |
| `pyproject.toml`: `redis==8.1.0` (asyncio istemcisi) zaten runtime'da | tokenize eşlemesi; yeni bağımlılık yok |
| `data/samples/pii/pii-100.jsonl` (100 satır, C18 span), `categories.md`, `scripts/gen/pii.py` `CATEGORIES` + `gen_value`, `gen/memory.py` (`gen_value("EPOSTA")`), `scripts/tests/test_13a.py` (`TC_KIMLIK`, `PERSON`) | ölçüm seti; FOLLOWUP-33 kod değişimi bu 4 dosya + yeniden üretim (**S4**) |
| Set dağılımı (ölçüldü): PERSON 22, TC 9, TR telefon 9, e-posta 8, IBAN 6, kart 5, VKN 5, adres 5, doğum 5, plaka 4, kurum 4, konum 4, pasaport/CVV/PIN/MAC/API token/şifre 3, GPS 2 | TC ve telefonda n=9: recall ≥ 0,98 tek kaçırmaya izin vermez (9/9 gerekir); raporda n ile yazılır |
| plan/06: `guard_in` (`input.pre`, llmaas'ta ayrıca `egress`), `tools` (`tool.pre`/`tool.post`), `guard_out` (`output.pre`); `definition.guardrail_policy_key: "default"`; engel → run `failed`, `error_code=guardrail_block`, mesaj `block_message`'dan | engine arayüzünün tüketicisi 06a; kanca bağlama bu pakette yok |

`backend/ffcore/guardrails/__init__.py` boş; `runtime/` boş. `rg "guardrail"` backend'de başka sembol vermedi.

### 2. Kapsam / kapsam dışı

**Kapsam (08-lite, GOREV K-08lite-0000/0001):**
- `engine.evaluate(text, stage, policy, *, ctx) -> Decision(action, text_out, events)`; 7 aşama (C4 sırası); zincir: yerel kurallar sırayla, `Decision.text_out` sonraki kuralın girdisi, `block` zinciri keser, `short_circuit=false` iken hepsi koşar, en sert aksiyon kazanır.
- Kural türleri: `pii` (engine `regex`), `secrets` (vendor desenleri + entropi), `tool_args` (araç/aksiyon bazlı regex).
- Regex tanıyıcılar: TC kimlik (11 hane, ilk ≠ 0, 10. ve 11. hane algoritması), TR telefon, TR IBAN (mod-97), e-posta, kart (Luhn). Bulgu: kategori, offset, güven, **kanıt** ("checksum valid · context word 'tc kimlik'").
- Maskeleme: `redact` (`[TR_NATIONAL_ID]` gibi kategori kodu etiketi), `mask` (son haneler açık: `*******8950`, `a***********@ornek.com`), `tokenize` (`<<PII_n>>`, aynı değer aynı yer tutucu; eşleme Redis'te `PII_TOKEN_TTL_S`, kapsam run kimliği; `detokenize()` tam metin için).
- Modlar `off|monitor|enforce`: monitor'da karar hesaplanır, olay `action_taken` ile yazılır, `Decision.action=allow`, metin değişmez. `on_error` fail-closed (`block`).
- Tablolar: `guardrail_policies`, `pii_policies`, `guardrail_events` (Alembic dalı `08`).
- API: politika CRUD (iki varlık), `POST .../guardrails/test` (kanıt alanı zorunlu, olay yazmaz), `POST /internal/guardrails/evaluate` (yalnız `SERVICE_TOKEN`; olayları yazar).
- `GUARDRAIL_EGRESS_ENABLED`: kapalıyken `egress` aşaması açık hata (`egress_stage_disabled`), sessiz geçiş yok.
- Ölçümler `docs/guardrail.md`'ye: regex kategorileri recall/precision, gecikme P95 (1.000 karakter).
- FOLLOWUP-33 kanonik kategori kodları (S4).

**Kapsam dışı (08 tam ya da başka paket):** Türkçe NER (`PERSON`, kurum, konum), Presidio, `injection`, `topic`, akış tamponlayıcı (C17), `egress` kalibrasyonu, PRSIM guard'ı, `output_format`, `banned_words`; 06a kanca bağlama; 10 ekranları; `guardrail_events` saklama/partition (03c retention). Desteklenmeyen kural türü ya da tanıyıcısız kategori politikada **422 ile reddedilir** (`rule_type_unsupported`, `category_unsupported`), "açık görünüp çalışmayan" ayar yok (ARCH-13).

### 3. Değişecek dosyalar ve neden

- `backend/ffcore/guardrails/`: `engine.py` (evaluate, zincir, mod, on_error), `schemas.py` (Decision, Finding, GuardrailEvent, politika ve kural Pydantic şemaları), `categories.py` (kanonik kod listesi, tek kaynak), `recognizers/regex.py` (5 tanıyıcı + doğrulayıcılar + bağlam kelimeleri), `rules/{pii,secrets,tool_args}.py`, `masking.py` (redact/mask/tokenize, `TokenStore` arayüzü + Redis gerçekleştirmesi), `builtin.py` (yerleşik `default` politika, S5), `settings.py` (kendi `BaseSettings`'i: `GUARDRAIL_EGRESS_ENABLED`, `PII_TOKEN_TTL_S`, `REDIS_URL`; `core/config.py` değişmez), `service.py` (politika çözümleme, olay yazımı).
- `backend/ffcore/models/guardrails.py` + `models/__init__.py` kendi satırı.
- `backend/ffcore/api/guardrails.py` + `api/__init__.py` kendi satırı.
- `backend/alembic/versions/08_0001_guardrails.py`.
- `backend/openapi/08.yaml` (koddan üretim; S1).
- `backend/tests/unit/test_08_*.py`, `tests/integration/test_08_*.py`, `tests/contract/test_c4_guardrail_stages.py`; `tests/contract/test_c3_common_columns.py`'ye `guardrail_events` satırı.
- `docs/guardrail.md` (kural türleri, aksiyonlar, kategori listesi, kalite ve gecikme raporu).
- `.env.example`, `.env.test`: `GUARDRAIL_EGRESS_ENABLED`, `PII_TOKEN_TTL_S` (ad + İngilizce açıklama, değer yok/sahte).
- S1-S4 onaylanırsa: `api/openapi_export.py`, `tests/unit/test_03a_write_flag.py`, `deploy/docker-compose.yml` `&app-env` (2 satır), `data/samples/scripts/gen/{pii,memory}.py`, `scripts/tests/test_13a.py`, yeniden üretilmiş `data/samples/pii/*`.

### 4. Sözleşme, yapılandırma, profil etkisi

- **C4 bu PR'la donar** (08 merge): aşama adları ve sırası `prompt.pre, input.pre, output.pre, output.stream.delta, tool.pre, tool.post, egress`; `action_taken` enum `block|redact|mask|tokenize|warn|log`; `Decision(action, text_out, events)` — `action` = `action_taken` değerleri + `allow` (bulgu yok ya da monitor); `POST /internal/guardrails/evaluate` gövdesi. `tests/contract/test_c4_*` kilitler.
- `evaluate(text, stage, policy)` imzasına anahtar kelimeli `ctx` (run_id, project_id, source, locale, tool_name/action) eklenir; konumsal üçlü değişmez.
- Profil: kodda dal yok. Fark yalnız `GUARDRAIL_EGRESS_ENABLED` (llmaas true, airgap false; `.env.example` llmaas varsayılanıyla `true`, airgap kurulum notu). İki profil testi aynı matris; egress testleri bayrağı parametre olarak verir.
- C12: iki yeni ortam değişkeni (additive). C3: yeni kök tablolar ortak kolonlu; `guardrail_events` CONTRACTS'ta adlı append-only istisna.
- Yüzey İngilizce; `block_message` jsonb `{"en", "tr"}`, istekteki `locale` (varsayılan `en`), yoksa `en` (K-INIT-0007).

### 5. Kabul kriteri → test adı

Brief kabul + GOREV kabul payı + bağlayıcı davranışlar; 08 tam'a kalan kısım ayrıca yazılır.

| # | Kriter | Test |
|---|---|---|
| 1 | TC kimlik ve telefon recall ≥ 0,98 pii-100'de (ad-soyad 0,85 → 08 tam); 5 regex kategorisinin recall/precision'ı ölçülür, docs'a yazılır | `test_08_1_regex_recall_tc_phone`, `test_08_1b_quality_report_matches_docs` |
| 2 | Gecikme: regex yolu, 1.000 karakter, P95 ölçülür ve yazılır (P95 < 300 ms bütçesinin regex payı; NER + injection 08 tam) | `test_08_2_regex_latency_p95` |
| 3 | `tokenize`: aynı değer aynı `<<PII_n>>`, `detokenize` tam metni geri çevirir, eşleme TTL'li ve run kapsamlı (akış C17 → 08 tam) | `test_08_3_tokenize_roundtrip`, `test_08_3b_tokenize_redis_ttl` (entegrasyon) |
| 4 | `block` → `Decision(action=block)`, `guardrail_events` satırı `status=failed`, mesaj locale'e göre `block_message`'dan, `block` zinciri keser | `test_08_4_block_decision_event_message` |
| 5 | Monitor: karar uygulanmaz (metin aynı, `action=allow`) ama olay `action_taken` ile kaydedilir | `test_08_5_monitor_records_not_applies` |
| 6 | Monitor → Enforce geçişi tek audit olayı (before/after `mode`); yeni politika `monitor` başlar | `test_08_6_enforce_switch_audited` |
| 7 | TC algoritması: ilk hane 0, 10./11. hane hatalı → bulgu yok; pii-100 negatiflerindeki geçersiz TC benzerleri yakalanmaz | `test_08_7_tc_checksum` |
| 8 | Maskeleme biçimleri: redact kategori etiketi, mask son haneleri açık, offset kaymasız çoklu bulgu | `test_08_8_masking_formats` |
| 9 | Zincir: `text_out` sonraki kurala akar; `short_circuit=false` hepsini koşar; en sert aksiyon kazanır | `test_08_9_chain_semantics` |
| 10 | `on_error=block` fail-closed: kural istisnası → block + olay; `allow` → geçer ama olay `status=failed` kayıtlı | `test_08_10_on_error_fail_closed` |
| 11 | `secrets`: vendor desenleri ve yüksek entropi `block`; düşük entropili sıradan metin geçer | `test_08_11_secrets_rule` |
| 12 | `tool_args`: araç/aksiyon eşleşmesinde yasak kalıp (`pg_`, dış domain) yakalanır, başka araçta değil | `test_08_12_tool_args_rule` |
| 13 | Aşama seçimi `rules[].stages[]`; yedi aşama C4 sırasıyla, bilinmeyen aşama 422 | `test_08_13_stage_binding`, `test_c4_guardrail_stages` |
| 14 | `pii` kuralındaki `pii_policy_key` kayıtta doğrulanır (yoksa 422); kullanılan PII politikası silinemez (409) | `test_08_14_pii_policy_reference` |
| 15 | Desteklenmeyen kural türü / tanıyıcısız kategori / `engine=ner` 422 (sessiz kabul yok) | `test_08_15_unsupported_rejected` |
| 16 | Test paneli: Detect/Redact/Mask/Tokenize; her bulguda kanıt ve offset; olay yazmaz; analyst çağırabilir | `test_08_16_test_panel_evidence` |
| 17 | `/internal/guardrails/evaluate` yalnız `SERVICE_TOKEN`: kullanıcı oturumu, OBO, anahtarsız → 401/403; olayları yazar (source, run_id) | `test_08_17_internal_service_only` |
| 18 | `GUARDRAIL_EGRESS_ENABLED=false` iken `egress` 409 `egress_stage_disabled`; true iken çalışır | `test_08_18_egress_flag` |
| 19 | Politika uçları: her mutasyon audit; `access=read` 403; analyst yazamaz; başka proje 403/404; OBO proje sınırı | `test_08_19_policy_access_audit` |
| 20 | `input_preview` (60 karakter) ve `matches` her modda maskeli; ham değer olaya ve loga girmez | `test_08_20_events_masked` |
| 21 | Kanonik kategori listesi tek yerde; pii-100 kodları listeyle birebir, karışık dil yok (FOLLOWUP-33) | `test_08_21_canonical_categories` |
| 22 | OpenAPI `08.yaml` koddan üretilen çıktıyla aynı, İngilizce; 03a.yaml bayt aynı kalır | `test_08_22_openapi_draft` |
| 23 | Migration: `upgrade heads` → `downgrade 08@-1` → `upgrade heads`; 03a/03b tabloları etkilenmez | `test_08_23_migration_roundtrip` (entegrasyon) |

### 6. Migration

`08_0001_guardrails.py`: `revision="08_0001"`, `down_revision="0001"`, `branch_labels=("08",)`, `depends_on=("03a_0001",)` (GOREV `down_revision="0001"` der; `projects` FK'si için `depends_on` şart, yoksa 08 dalı 03a'dan önce koşabilir). Tablolar: `pii_policies`, `guardrail_policies` (kök, C3 kolonları; `(project_id, key)` canlı satırlarda tekil, `is_default` proje başına en çok bir canlı satır, CHECK'ler enum'lar için), `guardrail_events` (append-only; `id, ts, project_id FK, run_id uuid NULL` FK'siz (runs 06a'da), indeks `(project_id, ts)`, `(run_id)`). Partition ve saklama yok (03c retention, FOLLOWUP önerisi). Üç head beklenir (FOLLOWUP-57).

### 7. Geri alma

`docker compose run --rm migrate alembic downgrade 08@-1` (asla `08@base`). Kod tarafı: 06a bağlayana kadar engine çağrılmaz; politika yoksa yerleşik `default` monitor modundadır (S5), yani merge hiçbir trafiği engellemez. Veri temizliği yok (yeni tablolar).

### 8. Durma koşulları

- C4'ü 06a'nın gerçek kullanımı kırarsa (Decision alanı ya da imza): koordinatöre dönerim, donmadan önce düzeltilir.
- S1-S5'ten biri reddedilir ve alternatif touch-zone dışına çıkar.
- pii-100'de TC/telefon recall < 0,98 çıkar ve neden set hatasıysa: seti değiştirmem (13a'nın), KAYIT-TALEBI.
- Gecikme regex yolunda P95 > 50 ms (beklenen ≪ 300 ms bütçesi): rapor + koordinatör.
- Redis entegrasyonu tools konteynerinde erişilemez: `PENDING_ENV`.

### 9. Felsefe kontrolü

- **ARCH-07:** Engine her model ve araç çağrısının yolunda; tüm senaryolar. Kalıcı karmaşıklık: 3 kural türü, 5 tanıyıcı, 3 tablo. Kapsam dışı türler eklenmiyor, desteklenmeyen ayar 422.
- **ARCH-09:** Presidio 08-lite'ta **alınmaz**: 5 regex tanıyıcı (checksum'lı) Presidio'da da özel tanıyıcı olarak yazılmak zorunda (TC, TR telefon, TR IBAN yerleşik değil); paket + spaCy bağımlılık zinciri (C sınıfı, imaj büyümesi) karşılığında yalnız e-posta/kart desenini kazandırır. 08 tam NER için Presidio'yu getirdiğinde tanıyıcı arayüzü (`category, start, end, score, evidence`) Presidio `RecognizerResult`'a birebir eşlenir; kategori kodları Presidio adlarıyla uyumlu seçilir (S4) ki geçiş yeniden adlandırma istemesin. Tokenize eşlemesi Redis'te (zaten var); olaylar Postgres'te; Langfuse'a ayrı iz yok (06a `run_events.guardrail_hook` referansı). LiteLLM içinde kanca yazılmaz (B3).
- **ARCH-10 / ARCH-06:** "auto" yok: politika açık seçilir, yoksa yerleşik `default` görünür biçimde (`builtin: true`, API'de listelenir) ve monitor modunda; egress bayrağı zorunlu ve kapalıyken açık hata; `on_error` varsayılan fail-closed; metin sınırı aşılırsa kırpma yok, 422 `text_too_long`; desteklenmeyen tür/kategori reddedilir. Monitor modu sessiz değil: her bulgu olay olarak yazılır.

## Koordinatör görüşü gereken noktalar (S1-S5)

- **S1 OpenAPI dışa aktarımı (03a dosyası):** `render()` bütün `api_router`'ı 03a.yaml'a yazar; guardrails router'ı eklenince `test_03a_16_openapi_draft_matches_app` kırılır. **A (önerim):** `openapi_export.py`'ye paket → router modülleri eşlemesi (`render(package="03a")`, `python -m ffcore.api.openapi_export 08 > openapi/08.yaml`); 03a.yaml bayt aynı (test kanıtlar), 04a/05a aynı kalıbı kullanır. B: 08 için ayrı dışa aktarıcı `guardrails/` içinde, 03a'nınki tag filtresiyle daraltılır (yine 03a dosyası değişir, iki kalıp). C: 03a.yaml'ı 08 yollarıyla yeniden üret (03a sözleşme dosyası başka paketin yollarını taşır, 10a-bağlama kopyası kirlenir).
- **S2 Yazma taraması (03a testi):** `POST /internal/guardrails/evaluate` (servis hesabı, `RoleRequirement` yok) ve `POST .../guardrails/test` (salt hesap, durum değiştirmez) taramaya takılır. **A (önerim):** testteki `WRITE_EXEMPT`'e iki ad, gerekçe yorumuyla; test paneli `require_role("analyst")` (read modundaki kullanıcı da dener, brief "önyüzde dene"). B: test paneli `write=True` (read modu deneyemez) ve yalnız internal muaf. C: taramaya `ServiceRequirement` tipini tanıt (03a testinde daha büyük değişiklik).
- **S3 Compose ortamı (00/03 dosyası):** `GUARDRAIL_EGRESS_ENABLED` profil farkıdır ve varsayılansız (fail-loud) olmalı; backend'e ulaşması için `&app-env`'e iki satır (`GUARDRAIL_EGRESS_ENABLED: ${...:?}`, `PII_TOKEN_TTL_S: ${PII_TOKEN_TTL_S:-1800}`) gerekir. **A (önerim):** bu PR'da additive iki satır. B: kodda varsayılan `true` (airgap'te `.env` unutulursa egress sessizce açık; ARCH-10'a ters). C: bayrağı politika seed'ine taşı (seed yükleyici + migrate komutu değişir, 08-lite'a fazla).
- **S4 FOLLOWUP-33 kanonik kodlar:** İngilizce, Presidio adlarıyla uyumlu tek liste: `TR_NATIONAL_ID, TR_PHONE, TR_IBAN, TR_TAX_ID, TR_PLATE, TR_PASSPORT, TR_ADDRESS, PERSON, ORGANIZATION, LOCATION, EMAIL_ADDRESS, CREDIT_CARD, CVV, PIN, GPS, MAC_ADDRESS, API_TOKEN, PASSWORD, DATE_OF_BIRTH`. **A (önerim):** bu PR'da `data/samples/scripts/gen/{pii,memory}.py` `CATEGORIES`/çağrılar, `scripts/tests/test_13a.py` kod adları, yeniden üretim (`generate.py --only pii`; metin ve span'ler bayt aynı, yalnız `category` değişir, test kanıtlar); ayrı commit. B: ayrı küçük PR önce merge (13a'nın sahibi yok, aynı işçi; iki review turu). C: Türkçe kodlar kalır (`TC_KIMLIK`…) ve `PERSON` → `KISI_ADI`; kod İngilizce kuralına ve Presidio uyumuna ters. Not: GOREV redact etiketi örneği `[TC_KIMLIK]` idi; A seçilirse `[TR_NATIONAL_ID]` olur.
- **S5 Politika yoksa ne olur:** 06a `definition.guardrail_policy_key: "default"` gönderir; yeni projede satır yok. **A (önerim):** kodda sürümlü yerleşik `default` politika (mode `monitor`; pii redact metin aşamalarında, egress'te tokenize; secrets block), API listesinde `builtin: true` görünür; aynı anahtarla satır yaratılırsa onu geçersiz kılar; `default` dışındaki eksik anahtar 404 `guardrail_policy_not_found`. B: proje yaratılırken satır seed'le (03a proje ucu değişir, touch-zone dışı). C: politika yoksa açık hata (06a her projede önce politika ister; PoC kurulumu bir adım uzar).

## Varsayımlar ve brief'teki çelişkiler

1. Brief iki değer kümesi verir: veri modelinde `on_error: block|allow`, davranış bölümünde `open|closed`. Veri modeli seçildi (`block|allow`, varsayılan `block`).
2. `pii_policies.default_action` eski `detect` = `log` (N23); `detect` kabul edilmez.
3. `block_message_tr` → `block_message` jsonb `{en, tr}` (K-INIT-0007, DRIFT-36).
4. Brief "Kurallar paralel çalışır" (Entegrasyon) ile "yerel kurallar sırayla, `text_out` sonrakinin girdisi" (davranış) çelişir; sıralı zincir seçildi (redact çıktısının akması bunu gerektirir).
5. `/internal/guardrails/evaluate` yolu `api_router` altında `/api/v1/internal/guardrails/evaluate` olur (main.py'ye dokunmamak için); brief yolu önek hariç aynı.
6. Varsayılan açık CVV ve PIN (brief) bağlam olmadan regex'le güvenilir değil; 08-lite'ta tanıyıcısı yok, yerleşik politikada açık **gösterilmez**, docs'ta "08 tam" diye yazılır. Brief'teki genel "telefon" ile "TR telefon" tek kategori (`TR_PHONE`) sayıldı; set de tek kod taşıyor.
7. Test paneli olay yazmaz (kuru koşu; `source` enum'unda karşılığı yok); 10'daki olay listesi gerçek trafikten.
8. `guardrail_events` append-only ama trigger'sız (audit kadar kritik değil); partition/saklama 03c.
9. Metin üst sınırı 200.000 karakter (egress paketi RAG parçalarıyla büyür); aşımda 422, kırpma yok.
10. Kullanıcı tanımlı `custom_patterns` kayıtta derlenir, desen uzunluğu ≤ 200; Python `re` zaman aşımı vermez (ReDoS riski yalnız admin girdisinde; kalan risk).

11. (uygulamada) `short_circuit`: brief "kapalıysa hepsi çalışır" der, block'un zinciri kestiğini de söyler. Yorum: `true` (varsayılan) block'ta durur; `false` block'tan sonra da kalan kuralları **kayıt için** koşar, karar yine `block`. "İlk bulguda dur" yorumu reddedildi: redact eden ilk kural sonraki `secrets` kuralını atlatırdı.
12. (uygulamada) `pii` kuralında `action` isteğe bağlı: verilirse tüm kategorilere uygulanır (brief "bir kuralın tek aksiyonu"); verilmezse kategori aksiyonu, o da yoksa PII politikasının `default_action`'ı. Yerleşik politika aşamaya göre iki kural kullanır (redact / egress'te tokenize).
13. (uygulamada) `tool_args` yalnız `tool.pre` ve yalnız `block|warn|log` (ofsetler JSON metnine değil argüman değerine işaret eder; yeniden yazma yanlış yere düşerdi).
14. (uygulamada) `is_default`: proje başına en çok bir canlı satır (kısmi tekil indeks); ikinci `true` 409 `default_policy_exists` (sessizce diğerini kapatmak yok). Çözümleme `policy_key` ile; `default` anahtarlı satır yoksa yerleşik politika.
15. (uygulamada) 04a ile hizalama: `service_actor` 04a'nın `api/internal.py`'sindeki 5 satırın kopyası (04a merge edilmedi); iki paket main'deyken tek yardımcıya iner. 04a `/internal/embed`'i kök yola, 08 ise onaylı varsayım 5 gereği `/api/v1/internal/...`'a koydu; yol birliği merge sırasında koordinatör kararı.
16. (uygulamada) 03a'nın GET eşitlik taraması (`test_03a_read_side.py`) tüm uygulama yollarını gezer; 08'in tekil politika GET'leri 04a'nın aynı adlı `PARITY_EXEMPT_PREFIXES` kalıbıyla muaf, liste yolları taramada kalır, tekiller `test_08_19b`'de. Merge'de iki demet birleşir.

## Review r1 bulgu → düzeltme → kanıt (state/reviews/08-lite-r1.md, DUZELT K-08lite-0008)

r1 düzeltmesi tek commit `7a7dc35` (21812317 üstüne). Kırmızı testler önce 21812317'nin ayrı bir kopyasında koşuldu ve düştü; sonra düzeltme.

| Bulgu | Düzeltme | Kanıt (önce kırmızı) |
|---|---|---|
| MAJOR-1 olay önizlemesi ve maskeli eşleşme ham değer taşıyabiliyor | Önizlemeler zincir bittikten sonra kurulur: her olayda regex PII + `secrets` + zincirdeki **herhangi** bir kuralın bulduğu her değer redakte (mod ve kural sırasından bağımsız; hata yolunda da). `mask_value` ham değeri asla döndürmez: en çok son dört ve en çok yarısı açık; tek harfli e-posta local kısmı `*`; alfanümeriksiz değer tamamen `*`. `matches[].value` → `masked_value`, API `FindingOut.value` → `masked_value` (C4 donmadan) | `test_08_20_preview_never_raw_across_the_chain` (monitor/block, enforce/warn, enforce/log), `test_08_8_masked_value_is_never_the_raw_value` (`a@example.org` → `*@example.org`, `7` → `*`, CVV `**8`), gerçek DB + API cevabı: `test_08_20_short_and_chained_values_never_raw_in_db_or_response` (kısa e-posta, tek haneli özel desen değeri, sentetik parola; zincirde **sonraki** kuralın bulduğu değer önceki olayın önizlemesinde de gizli) |
| MAJOR-2 farklı e-postalar aynı yer tutucuya çöküyor | tokenize kimliği `kategori:ham değer` (normalizasyon yok). Bedel (kabul, K-08lite-0008): biçimi farklı yazılmış aynı numara ayrı yer tutucu alır; yanlış değer geri konmaz | `test_08_3_distinct_values_never_share_a_token` (`a.b@` / `ab@` → `<<PII_1>>` / `<<PII_2>>`, tam gidiş-dönüş) |
| MAJOR-3 Redis ileri/geri eşleme atomik değil | get-or-create tek Lua `EVAL`: HGET → HINCRBY → iki alanlı HSET → EXPIRE aynı script içinde (sayaç, iki yön, TTL atomik) | `test_08_3_redis_store_publishes_both_directions_atomically` (ağ gecikmeli sahte istemci; eski kodda ikinci çağrı ters kayıt yokken token döndürdü). **Sınır:** gerçek Redis'te 50 eşzamanlı çağrı (`test_08_3b_concurrent_tokenize_resolves_every_token`) eski kodda da geçiyor, yerel Redis pencereyi kapatıyor; kırmızı kanıt sahte istemcili unit testtir. Süreç kesilmesinde TTL'siz hash riski artık yok (tek komut); crash senaryosu ayrıca koşulmadı |
| MAJOR-4 yerleşik zincir projenin `default` PII satırını kullanmıyor | K-08lite-0006 A: `service.resolve_policy` yerleşik zincirin `pii_policy_key` referanslarını `resolve_pii` ile çözer (proje satırı, yoksa sürümlü yerleşik) | `test_08_s5_builtin_chain_uses_the_projects_stored_pii_default` (21812317'de düştü); kısa değer testi aynı yolu özel desenle kullanır |

## C4 donmuş biçim (bu PR'la donar)

- **Aşamalar ve sırası:** `prompt.pre, input.pre, output.pre, output.stream.delta, tool.pre, tool.post, egress` (`ffcore/guardrails/categories.py` `STAGES`; migration'da donmuş kopya; `test_c4_stage_and_action_lists`, `test_c4_decision_contract_in_draft`).
- **`action_taken`:** `block, redact, mask, tokenize, warn, log`. `Decision.action` bunlara ek olarak `allow`.
- **Olay alanları:** `GuardrailEvent.matches[]` = `{category, start, end, masked_value}` (r1'de `value`'dan yeniden adlandırıldı; ham değer hiçbir alanda yok), `input_preview` ≤ 60 karakter, zincirdeki tüm bulgular redakte.
- **`Decision`:** `action`, `text_out` (block'ta boş), `events: list[GuardrailEvent]`, `message` (block'ta locale'e göre, yoksa `en`), `reference_id` (block'ta). Güç sırası `block` > `redact|mask|tokenize` > `warn` > `log` > `allow`.
- **İmza:** `async evaluate(text, stage, policy: ResolvedPolicy, *, ctx: EvalContext | None) -> Decision`; `EvalContext(run_id, project_id, source, locale, tool, token_store, egress_enabled)` anahtar kelimeli, additive genişler.
- **Uç:** `POST /api/v1/internal/guardrails/evaluate`, gövde `EvaluateRequest {project_id, stage, text, policy_key="default", run_id?, source, tool?, locale}`, cevap `DecisionOut {action, text_out, message, reference_id, policy_key, builtin, events[]}`; block = 200 + `action=block` (06a run'ı `failed` yapar, 06b 400 `guardrail_blocked`).
- **Hatalar:** bilinmeyen aşama / desteklenmeyen kural 422 kodlu; egress kapalıyken 409 `egress_stage_disabled`; 200.000 karakter üstü 422 `text_too_long`.

## Değişen dosyalar

Branch `feat/08-lite-guardrails` @ 7a7dc35 (baz 591aac3), 8 commit (r1 ilk 7 + düzeltme 1), 37 dosya.
- **guardrails (yeni):** `backend/ffcore/guardrails/{categories,findings,recognizers/regex,masking,rules,schemas,engine,builtin,settings,service,quality,api_schemas}.py`
- **API ve model:** `backend/ffcore/api/guardrails.py` (yeni), `api/__init__.py` (kendi satırı), `models/guardrails.py` (yeni), `models/__init__.py` (kendi satırı)
- **Migration:** `backend/alembic/versions/08_0001_guardrails.py` (dal `08`, `depends_on=("03a_0001",)`)
- **Sözleşme:** `backend/openapi/08.yaml` (koddan); `api/openapi_export.py` paket eşlemesi (S1, 04a kalıbı ve imzası; `03a.yaml` bayt aynı)
- **Testler:** `tests/unit/test_08_{recognizers,masking,engine}.py`, `tests/contract/test_08_openapi.py`, `tests/integration/test_08_api.py`; paylaşılan: `tests/unit/test_03a_write_flag.py` (S2, iki muafiyet), `tests/contract/test_c3_common_columns.py` (`guardrail_events` append-only, CONTRACTS'ta adlı), `tests/integration/test_03a_read_side.py` (varsayım 16)
- **Ortam:** `deploy/docker-compose.yml` `&app-env` 2 satır (S3), `.env.example` (İngilizce açıklama), `.env.test` (sahte değerler)
- **13a seti (S4, ayrı commit'ler ec7847f, 5f9a7f4):** `data/samples/scripts/gen/{pii,memory}.py`, `scripts/tests/test_13a.py`, yeniden üretilen `data/samples/pii/{pii-100.jsonl,categories.md}`; metin ve span bayt aynı (eski kodlara kanonik eşleme uygulanınca JSON eşit), `memory/` çıktısı değişmedi
- **Docs:** `docs/guardrail.md`

## Kabul kriterleri → testler

| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | TC/telefon recall ≥ 0,98; 5 regex kategorisi ölçülüp docs'a | `test_08_1_regex_recall_tc_phone`, `test_08_1_every_regex_category_is_measured`, `test_08_1b_quality_report_matches_docs`, `test_08_1_findings_carry_evidence`, `test_08_1_iban_inside_text_is_not_read_as_card`, `test_08_1_bare_ten_digits_are_not_a_phone` | geçti (TC 9/9, telefon 9/9); ad-soyad 0,85 → 08 tam |
| 2 | Regex gecikme P95, 1.000 karakter | `test_08_2_regex_latency_p95` | geçti (0,61 ms); NER + injection payı 08 tam |
| 3 | tokenize gidiş-dönüş, run kapsamı, TTL | `test_08_3_tokenize_roundtrip`, `test_08_3_same_value_same_token_across_calls_in_a_run`, `test_08_3_unknown_placeholder_is_reported_not_invented`, `test_08_3_tokenize_without_scope_fails_loud`, `test_08_3b_tokenize_redis_ttl` | geçti; akış (C17) 08 tam |
| 4 | block → Decision + olay `failed` + locale mesajı + zincir kesilir | `test_08_4_block_decision_event_message`, `test_08_4_block_cuts_the_chain`, `test_08_4_missing_locale_message_falls_back_to_english`, `test_08_4_block_decision_through_internal_endpoint` | geçti |
| 5 | Monitor kaydeder, uygulamaz; off hiçbir şey | `test_08_5_monitor_records_not_applies`, `test_08_5_off_mode_evaluates_nothing` | geçti |
| 6 | Enforce geçişi audit (before/after), yeni politika monitor | `test_08_6_enforce_switch_audited` | geçti |
| 7 | TC algoritması, negatiflerde bulgu yok | `test_08_7_tc_checksum`, `test_08_7_negatives_have_no_regex_findings` | geçti |
| 8 | Maskeleme biçimleri, çoklu bulguda ofset | `test_08_8_masking_formats`, `test_08_8_redact_and_mask_keep_offsets_with_several_findings`, `test_08_8_non_transforming_actions_leave_text` | geçti |
| 9 | Zincir: text_out akar, short_circuit, en sert aksiyon, metin sınırı | `test_08_9_text_out_flows_into_the_next_rule`, `test_08_9_short_circuit_off_runs_every_rule_but_still_blocks`, `test_08_9_per_category_actions_and_strongest_action`, `test_08_9_text_limit_fails_loud` | geçti |
| 10 | on_error fail-closed / allow | `test_08_10_on_error_fail_closed` | geçti |
| 11 | secrets | `test_08_11_secrets_rule` | geçti |
| 12 | tool_args | `test_08_12_tool_args_rule` | geçti |
| 13 | Aşama bağlama, bilinmeyen aşama 422 | `test_08_13_stage_binding`, `test_c4_stage_and_action_lists` | geçti |
| 14 | pii_policy_key doğrulama, kullanılan PII politikası silinemez | `test_08_14_pii_policy_reference` | geçti |
| 15 | Desteklenmeyen tür/kategori/motor/aşama 422 | `test_08_15_unsupported_rejected`, `test_08_15_unsupported_rejected_by_api`, `test_08_15_custom_pattern_and_min_confidence`, `test_08_15_stream_stage_and_rewriting_tool_args_rejected` | geçti |
| 16 | Test paneli kanıt + ofset + maskeli değer, olay yazmaz, read modu kullanır | `test_08_16_test_panel_evidence` | geçti |
| 17 | internal yalnız servis hesabı (anonim 401, kullanıcı ve OBO 403), olay yazar | `test_08_17_internal_service_only` | geçti |
| 18 | Egress bayrağı | `test_08_18_egress_flag`, `test_08_18_egress_flag_from_environment` | geçti |
| 19 | Erişim + audit + read modu eşitliği | `test_08_19_policy_access_audit`, `test_08_19b_read_mode_get_parity` | geçti |
| 20 | Olaylar maskeli (bellek ve DB) | `test_08_20_events_masked`, `test_08_20_events_masked_in_database` | geçti |
| 21 | Kanonik kategori listesi tek (FOLLOWUP-33) | `test_08_21_canonical_categories`, `test_08_21_set_generator_uses_the_same_list` | geçti |
| 22 | OpenAPI 08.yaml = kod, İngilizce, 03a.yaml etkilenmez; C4 | `test_08_22_*` (5 test), `test_c4_decision_contract_in_draft` | geçti |
| 23 | Migration döngüsü `downgrade 08@-1` → `upgrade heads` | `test_08_23_migration_roundtrip` | geçti |
| S5 | Yerleşik default (monitor), API'de görünür, satır geçersiz kılar | `test_08_s5_builtin_default_is_monitor_and_valid`, `test_08_s5_builtin_default_listed_until_overridden` | geçti |

## Çalıştırılan komutlar

**r2 (HEAD 7a7dc35, imaj `0.0.0-08lite` yeniden derlendi):**

| Komut | Ortam | Exit | Süre |
|---|---|---|---|
| `make lint` | | 0 | 1 s |
| `make test` | `DEPLOY_PROFILE=llmaas GUARDRAIL_EGRESS_ENABLED=true` | 0 (184 passed) | 19 s |
| `make test-int` | `DEPLOY_PROFILE=llmaas GUARDRAIL_EGRESS_ENABLED=true` | 0 (110 passed) | 96 s |
| `make test` | `DEPLOY_PROFILE=airgap GUARDRAIL_EGRESS_ENABLED=false` | 0 (184 passed) | 29 s |
| `make test-int` | `DEPLOY_PROFILE=airgap GUARDRAIL_EGRESS_ENABLED=false` | 0 (110 passed) | 72 s |
| `python -m ffcore.api.openapi_export 08 > openapi/08.yaml` (`masked_value` adı) | | 0 | |
| `up -d --wait backend litellm langfuse-web langfuse-worker` (`BACKEND_PORT=18008`) + `make smoke` | | 0 | |
| `down -v` | | 0 | |

**r1 (HEAD 21812317):**

Ortam: tools konteyneri, imaj `ffcore/tools:0.0.0-08lite` (K-INIT-0010, ENV-74), compose proje `08lite`, `--env-file .env.test`, Postgres + Redis (`up -d --wait postgres redis`).

| Komut | Ortam | Exit | Süre |
|---|---|---|---|
| `FFCORE_VERSION=0.0.0-08lite docker compose -p 08lite --env-file .env.test build backend tools` | | 0 | |
| `make lint` (ruff check + format; backend, scripts, data/samples/scripts) | | 0 | 3 s |
| `make test` (unit + contract) | `DEPLOY_PROFILE=llmaas GUARDRAIL_EGRESS_ENABLED=true` | 0 (180 passed) | 37 s |
| `make test-int` | `DEPLOY_PROFILE=llmaas GUARDRAIL_EGRESS_ENABLED=true` | 0 (107 passed) | 193 s |
| `make test` | `DEPLOY_PROFILE=airgap GUARDRAIL_EGRESS_ENABLED=false` | 0 (180 passed) | 33 s |
| `make test-int` | `DEPLOY_PROFILE=airgap GUARDRAIL_EGRESS_ENABLED=false` | 0 (107 passed) | 106 s |
| `alembic downgrade 08@-1` → `alembic upgrade heads` (test DB, `test_08_23`) | | 0 | |
| `py -3.12 -m unittest tests.test_13a` (data/samples/scripts, host) | | 0 (20 OK) | 1,5 s |
| `generate.py --only pii,memory` + JSON eşitlik karşılaştırması (eski kodlara kanonik eşleme) | host | eşit | |
| `python -m ffcore.guardrails.quality ../data/samples/pii/pii-100.jsonl` | | 0 | |
| `FFCORE_VERSION=0.0.0-08lite BACKEND_PORT=18008 docker compose -p 08lite --env-file .env.test up -d --wait backend litellm langfuse-web langfuse-worker` (8000 başka yığında dolu; port yalnız bu koşu için, `.env.test` değişmedi) | | 0 | ~60 s |
| migrate servisi: `alembic upgrade heads` (0001 → 03a_0001, 0001 → 08_0001, 0001 → 03b_0001) + katalog 2 kayıt | | 0 | |
| `make smoke` | | 0 (backend, litellm, langfuse 200; ollama profili kapalı, açıkça atlandı) | 13 s |
| `alembic heads` | | `03a_0001`, `03b_0001`, `08_0001` | |
| `curl -X POST :18008/api/v1/internal/guardrails/evaluate` (kimliksiz) | | 401 | |
| `docker compose -p 08lite ... down -v` | | 0 | |

Not: duraklamadan önce paylaşılan `ffcore/tools:0.0.0` imajıyla aynı matris de yeşildi; kanıt `0.0.0-08lite` koşusudur.

## Çıktı özeti ve post-state

- Tablolar: `pii_policies`, `guardrail_policies`, `guardrail_events` (test DB'lerinde); Alembic head'leri `03a_0001`, `03b_0001`, `08_0001` (üç head beklenen, FOLLOWUP-57).
- pii-100: TR_NATIONAL_ID 9/9, TR_PHONE 9/9, TR_IBAN 6/6, EMAIL_ADDRESS 8/8, CREDIT_CARD 5/5, precision 1,00; 10 negatif cümlede bulgu 0. Regex P95 0,61 ms / 1.000 karakter.
- Yeni bağımlılık yok (redis zaten runtime'da).

## Kontrol listesi
- [x] Felsefe ile çelişebilecek noktalar işaretlendi (varsayım 11-13)
- [x] Donmuş sözleşme kırılmadı; C4 bu PR'la donuyor (yukarıdaki biçim)
- [x] İki profil testi koştu
- [x] Her mutasyon ucu audit; salt-okunur 403 (`test_08_19`)
- [x] Log, API, audit, olay secret-free ve maskeli (`test_08_20`)
- [ ] Türkçe metinler / iki tema: önyüz yok (10'un işi)
- [x] Docs ve `.env.example` güncel
- [x] WORK_QUEUE durumu kanalla bildirildi

## Kalan riskler
- n=9 TC/telefon örneğinde recall kararı kaba; llmaas eşiği 0,99 bu setle ancak 9/9 ile karşılanır. Set ve tanıyıcı aynı ekipten: 1,00 alan recall'u değildir (docs'ta yazılı).
- ReDoS: kullanıcı tanımlı `custom_patterns` ve `tool_args` desenleri yalnız admin girdisi; Python `re` zaman aşımı vermez (varsayım 10).
- C4 06a bağlamadan donuyor; 06a'nın ihtiyacı farklı çıkarsa yalnız additive genişler (`EvalContext` alanları).
- `/internal` yol farkı 04a ile (varsayım 15) ve `service_actor` kopyası: merge sırasında tek yere iner.
- `guardrail_events` büyür; saklama 03c'de (FOLLOWUP önerisi: retention sınıfı + partition).
- Redis istemcisi istek başına açılıp kapanıyor (basit ve döngü güvenli); yük altında havuz gerekirse 06a bağlarken ölçülür.
