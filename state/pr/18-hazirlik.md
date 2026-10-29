# PR 18-hazirlik · Kullanım senaryoları veri hazırlığı (F2, F3, F4)

**Paket:** 18-hazirlik (plan/18 "Aşama 1") · **Sınıf:** [A] (yeni bağımlılık yok; stdlib üreticiler, K-SEN-0001) · **Branch:** feat/18-scenario-data · **Baz commit:** main 68ab763 (b49e476 üstünde yalnız state commit'i; rebase 2026-10-29 18:40) · **Son commit:** — (kod yok) · `FFCORE_VERSION=0.0.0-18`

> Durum: PLANNED talebi. Kod, plan onayından sonra.

## Plan (kodlamadan önce)

1. **Bulunan semboller ve dosyalar** (68ab763 ve feat/05a-tools-mcp a55ca54'te okundu):
   - `data/samples/scripts/generate.py`: `MODULES` sözlüğü, modül başına `random.Random("<seed>:<modül>")`, `--only`; yeni modüller buraya kayıt olur, mevcutların akışı değişmez.
   - `gen/schema.py`: `build(rng) -> rows` (10.000 satır; eval beklentileri de bundan hesaplanır), `TABLES`, `COLUMNS`, `FEW_SHOTS`. `gen/eval.py`: `SQL_QUESTIONS` (q29-q33, `sql` + `compute(rows)`), item biçimi plan/09 Langfuse eşlemesi (`input`, `expected_output{answer, must_contain, sql_result}`, `metadata{tags, answerable, style, expected_docs}`), `SUITE`.
   - `gen/pii.py`: kanonik kategori kodları `CATEGORIES` (08-lite, FOLLOWUP-33 kapalı: `TR_NATIONAL_ID`, `TR_PHONE`, `TR_IBAN`, `EMAIL_ADDRESS`, `CREDIT_CARD`…), `gen_value(code, rng)`, doğrulayıcılar `tc_valid`, `iban_valid`, `luhn_valid`; e-posta yerel parçası rol adı (`destek1234@…`), kişi adı yok. `gen/words.py`: `DEPARTMENTS`, `DEVICE_TYPES`, `FAULT_TYPES`, `CONTRACTS`, `HOSPITAL_NAME`. `gen/__init__.write_text` (UTF-8, LF).
   - `scripts/tests/test_13a.py` (stdlib unittest; `test_13a_8_deterministic`, `test_13a_9_no_person_names_outside_pii_memory`), `test_13a_pg.py` (`RUN_PG_TESTS=1`, `pgvector/pgvector:0.8.1-pg16`, benzersiz konteyner, `agent_readonly` ile koşu). Not: 13a testleri `make test`'te değil (Makefile `test` yalnız `backend/tests`); README'deki `unittest discover` ile koşar, `make lint` `data/samples/scripts`'i kapsar.
   - `backend/tests/fakes/fake_openai.py` (01, main'de): **her istek gövdesini zaten kaydediyor**; `GET /_requests` döker, `POST /_reset` temizler; compose `fake-llm` servisi `profiles: ["test"]`.
   - 05a (incelemede, feat/05a-tools-mcp): MCP sunucuları `backend/ffcore/services/mcp_{search,sql}_server.py`, ortak `mcp_server_common.py` (`MCPServer`, `CallerCheck`, compose servisi backend imajından `python -m …`); test sunucusu deseni `backend/tests/mcp_fixture.py` (gerçek `MCPServer`, streamable HTTP, her `tools/call` başlık ve argümanıyla kaydedilir). SQL ret kodları `SqlRejected`: `sql_parse_error, sql_multiple_statements, sql_not_select, sql_system_catalog, sql_too_deep, sql_unknown_table`; araç `sql_rejected: <code> (…)` döndürür.
   - `tests/` kökü ve `tests/e2e/` yok (13b açacak); `services/mcp-*` yalnız README.

2. **Kapsam / kapsam dışı**
   - Kapsam (bu PR, kod): (a) `data/samples/eval/sql-20.json` + `suite-sql-20.json`; (b) `data/samples/eval/sql-write-attempts.json` (F3 olumsuz testinin girdisi); (c) `data/samples/tickets/` 20 bilet + ayrı etiket dosyası; (d) üreticiler `gen/scenarios_sql.py`, `gen/tickets.py` ve `generate.py` kaydı; (e) `scripts/tests/test_18.py` (stdlib) + `test_18_pg.py` (seed'e karşı, opt-in); (f) `docs/demo.md` taslağı (F1-F4, F9 adımları, İngilizce); (g) `data/samples/scripts/README.md` ve `data/samples/tickets/README.md` açıklaması.
   - Kapsam (bu PR, yalnız tasarım; kod 05a merge sonrası ayrı dilim): sahte `ticket-desk` MCP aracı (bölüm "Tasarım: ticket-desk"), F4 yakalama yolu (bölüm "F4 yakalama").
   - Kapsam dışı: senaryo koşuları (`tests/e2e/scenarios/test_18_*.py` gerçek akış; 06a/07/10b-poc-2 merge sonrası, plan/18 aşama 2-4); `make eval`/`make e2e` hedefleri (13b, isci-a); 05a validator'ına dokunmak; 01 `fake_openai.py`'ye dokunmak (gerek kalmadı); kota (03c).

3. **Değişecek dosyalar ve neden**
   - `data/samples/scripts/gen/scenarios_sql.py` (yeni): `SQL20` listesi = `eval.SQL_QUESTIONS`'tan 5'i (kopya değil, import; tek kaynak) + 15 yeni `{id, q, sql, compute(rows)}`; `WRITE_ATTEMPTS` (12 kayıt); `generate()` → `eval/sql-20.json`, `eval/suite-sql-20.json`, `eval/sql-write-attempts.json`.
   - `data/samples/scripts/gen/tickets.py` (yeni): 20 bilet şablonu (sabit Türkçe metin, `{TR_NATIONAL_ID}` gibi yer tutucular `pii.fill` ile doldurulur), `generate()` → `tickets/tickets-20.jsonl`, `tickets/labels.json`.
   - `data/samples/scripts/generate.py`: `MODULES`'e `scenarios_sql`, `tickets` (iki satır + import). Mevcut modüllerin çıktısı bayt aynı kalır (`test_13a_8`).
   - `data/samples/scripts/tests/test_18.py`, `test_18_pg.py` (yeni).
   - `data/samples/scripts/README.md`: iki modül ve testlerin komutu (birkaç satır).
   - `docs/demo.md` (yeni, taslak; 13b sahibi devralır).
   - Touch-zone içinde: `data/samples/{eval,tickets}/**`, `data/samples/scripts/**`, `docs/demo.md`. `tests/e2e/scenarios/**` bu PR'da boş kalır (ticket-desk ve senaryo testleri sonraki dilimler).

4. **Sözleşme, yapılandırma, profil etkisi:** Donmuş sözleşmeye dokunulmaz. Sınav item biçimi 13a/plan/09 ile aynı (yeni alan yalnız `metadata.origin`, additive, 09 yok sayar). PII span biçimi `pii-100.jsonl` ile aynı (C18), kategori kodları 08-lite kanonik listesi. Profil bağımsız veri; profil matrisi bu PR'da uygulanmaz (`make test` dokunulan backend kodu yok); yine de iki profille `make test` koşulur ve yazılır.

5. **Kabul kriteri → test** (adlar `test_18_<senaryo>_<n>_<slug>`)

   | # | Kriter (plan/18, K-SEN-0001) | Test |
   |---|---|---|
   | 1 | `sql-20.json` tam 20 item, kimlikler benzersiz, item biçimi 13a ile aynı | `test_18_f3_1_sql20_shape` |
   | 2 | 5 item 13a q29-q33 ile birebir (soru, SQL, sonuç) | `test_18_f3_2_reuses_13a_sql_items` |
   | 3 | Beklenen sonuçlar seed'den hesaplanır (elle yazılmaz): `compute(build(rng))` = dosyadaki `sql_result`; `must_contain` sonuçtan türetilir | `test_18_f3_3_expected_from_seed` |
   | 4 | Seed'e karşı doğrulama: her referans SQL gerçek Postgres'te `agent_readonly` ile koşar, sonucu `sql_result`'a eşit (sayısal normalize) | `test_18_f3_4_reference_sql_matches_postgres` (`RUN_PG_TESTS=1`) |
   | 5 | Zorluk dağılımı: tek tablo ≥ 5, JOIN ≥ 5, GROUP BY/üst-N ≥ 4, tarih aralığı ≥ 3, NULL ≥ 1, çok satırlı sonuç ≥ 3 | `test_18_f3_5_difficulty_mix` |
   | 6 | `sql-write-attempts.json` her kaydın `expected_code`'u 05a kod listesinde; DELETE/UPDATE/INSERT/DROP + CTE içi yazma + yorumla gizlenmiş ikinci ifade + `SELECT INTO` + sistem kataloğu var | `test_18_f3_6_write_attempts_cover_classes` |
   | 7 | Yazma denemeleri gerçek Postgres'te `agent_readonly` ile reddedilir ve satır sayıları değişmez (DB katmanı; validator 05a/13b'de) | `test_18_f3_7_write_attempts_fail_readonly` (`RUN_PG_TESTS=1`) |
   | 8 | `tickets-20.jsonl` 20 bilet; `labels.json` her bilete tek sınıf, kapalı liste `access, billing, bug, how_to, other`; dağılım 5/4/5/4/2 | `test_18_f2_1_tickets_shape_and_labels` |
   | 9 | Tam 5 bilette sentetik PII; span'ler doğru (`text[start:end]`), değerler geçerli (TC checksum, IBAN mod-97, Luhn), kategoriler yalnız 08-lite regex kategorileri | `test_18_f2_2_pii_spans_valid` |
   | 10 | PII'siz 15 bilette 08-lite regex'inin yakalayacağı hiçbir desen yok (`pii.py` doğrulayıcılarıyla tarama) | `test_18_f2_3_no_stray_pii` |
   | 11 | Kişi adı yok: `pii.py` ad havuzundan hiçbir ad bilet ve sql dosyalarında geçmez (DECISION-24) | `test_18_f2_4_no_person_names` |
   | 12 | Etiket bilet dosyasına sızmaz (bilet kaydında `class`/`label` alanı yok, metinde sınıf adı geçmez) | `test_18_f2_5_labels_not_in_tickets` |
   | 13 | Deterministik: yeniden üretim depodaki baytlarla aynı; 13a çıktıları değişmez | `test_18_0_deterministic` + mevcut `test_13a_8_deterministic` |
   | 14 | F4 yakalama yolu hazır: `fake-llm` `/_requests` gövdeleri döndürüyor (01 testinin varlığı) | test yok, plan kararı; kanıt 06a sonrası `test_18_f4_*` |

   Testler önce kırmızı (üretici yokken dosya yok → fail), sonra yeşil.

6. **Migration:** yok.
7. **Geri alma:** yalnız yeni dosyalar + `generate.py`'de iki satır; PR revert'i. 13a çıktıları bayt aynı (`test_13a_8`).
8. **Durma koşulları:** (a) 05a ret kodları incelemede değişirse `expected_code` 05a merge'ünden sonra güncellenir (13a'daki gibi tek dosya), bu PR beklemez; (b) ticket-desk kodu için touch-zone dışı dosya gerekirse (compose servisi, aşağıda S2) koordinatöre dönerim; (c) seed'den hesaplanan bir sonuç Postgres'le uyuşmazsa (ör. `ROUND` yarım yuvarlama, tarih aritmetiği) soruyu değiştirmeden önce raporlarım; (d) bilet metninde 08-lite'ın beklenmedik eşleşmesi (yanlış pozitif) çıkarsa metni düzeltirim, kuralı değil.
9. **Felsefe kontrolü**
   - ARCH-07: F2/F3/F4 PoC kabulünün girdisi (M3 kapısı); ürün koduna sıfır kalıcı karmaşıklık, hepsi `data/samples/` ve test. ticket-desk yalnız test profili, kurulumda yok.
   - ARCH-09: 13a'nın üretici çatısı, `schema.build`, `eval.SQL_QUESTIONS`, `pii.gen_value`/doğrulayıcıları yeniden kullanılır; ikinci veri modeli ya da doğrulayıcı yazılmaz. F4 için 01'in `fake-llm` kaydı kullanılır, yeni yakalayıcı yazılmaz. ticket-desk 05a'nın `MCPServer` deseniyle.
   - ARCH-10 / ARCH-06: sınıf listesi kapalı ve açık; beklenen sonuç hesaplanamazsa (boş sonuç, None) üretici hata verir, sessiz boş değer yazılmaz; sayı/dağılım tutmazsa üretim durur.

## Veri tasarımı

**sql-20.json** (ids `sql-01`…`sql-20`; ilk 5 `metadata.origin = "sozlesme-33/q29"`… ). 15 yeni soru örnekleri (son metin kodda): bölüm katı ve kapasite (tek tablo), hizmet dışı yoğun bakım yatağı (filtre), 2025 Q1 en çok yatış alan bölüm (JOIN + tarih + üst-1), Kardiyoloji ortalama doluluk (oran, `ROUND(…,3)`), bakımdaki ventilatör sayısı, en eski kurulu infüzyon pompası tarihi, üretici başına aktif cihaz (çok satırlı), kritik açık arıza sayısı (NULL), 2025 Haziran arıza sayısı (tarih), YBAK cihazlarının toplam kesintisi (iki JOIN), arıza türü başına adet (çok satırlı), 2026'da biten sözleşme sayısı, bildirim süresi 90 günden uzun sözleşmeler (çok satırlı), bakım sözleşmelerinin toplam bedeli, kesintisi en yüksek bölüm. Few-shot'larla aynı soru yok (test kanıtlar: `FEW_SHOTS` soru ve SQL'iyle eşleşme 0), aksi halde ölçüm few-shot ezberini ölçer. `sql_result` satır listesi; ondalıklar string (`"0.732"`) olarak, Postgres `numeric` ile birebir karşılaştırma için. `must_contain` tek değerli sonuçta değerin kendisi, çok satırlıda ilk satırın anahtar değeri. Suite: `suite-sql-20.json` `{key: "sql-20", scorers: ["sql_result", "contains"], pass_threshold: 0.8}` (plan/18 F3 ≥ %80).

**sql-write-attempts.json** (12 kayıt `{id, sql, class, expected_code}`): `DELETE`, `UPDATE`, `INSERT`, `DROP TABLE`, `TRUNCATE`, `ALTER`, `WITH d AS (DELETE … RETURNING *) SELECT …` (CTE içi yazma → `sql_not_select`), `SELECT 1; DELETE …` ve `SELECT 1 /* */; DROP …` (yorumla gizlenmiş ikinci ifade → `sql_multiple_statements`), `SELECT … UNION SELECT … FROM pg_shadow` (UNION ile katalog → `sql_system_catalog`), `SELECT * INTO yeni FROM beds` (→ `sql_not_select`), `SELECT pg_sleep(30)` (→ `sql_system_catalog`). `expected_code` 05a'nın a55ca54'teki listesinden; 05a merge'ünde değişirse güncellenir. Bu dosya F3 olumsuz e2e'sinin girdisidir; e2e "400/ret + satır sayısı değişmez"i 06a sonrası kanıtlar.

**tickets/** — bağlam: Örnek Şehir Hastanesi bilgi işlem ve biyomedikal destek masası (demo DB'nin cihaz/bölüm/sözleşme sözlüğüyle tutarlı). `tickets-20.jsonl` satırı: `{id: "tkt-001", channel: "email"|"portal", received_at, subject, body, pii: [{start, end, category}]}` (span'ler `body` üzerinde; PII'siz bilette `[]`). `labels.json`: `{"classes": ["access","billing","bug","how_to","other"], "labels": {"tkt-001": {"class": "access", "rationale": "…"}}}`; ticket-desk yalnız `tickets-20.jsonl`'ı okur, etiket modele ulaşmaz. Dağılım access 5 · billing 4 · bug 5 · how_to 4 · other 2; her sınıfta en az bir dolaylı anlatım (anahtar kelime eşlemesiyle değil anlamla sınıflanır). PII'li 5 bilet: TC kimlik (2), TR telefon (2), e-posta (2), IBAN (1) (biri birden fazla kategori); imza "Biyomedikal Birimi", "Muhasebe" gibi birim adları, kişi adı yok. Faker yok, stdlib + sabit metin.

## Tasarım: ticket-desk (sahte bilet kaynağı ve gönderim ucu; kod 05a merge sonrası)

GOREV'deki `ticket-sink` adını genişletiyorum: plan/18 F2 hem "sahte bilet kaynağı" hem "gönder" ucu istiyor; ikisi tek sunucuda, `ticket-desk`. Ad önerisi, koordinatör `ticket-sink` isterse öyle kalır.

- Yer: `tests/e2e/scenarios/fakes/ticket_desk.py` (touch-zone içi). Gerçek `MCPServer` (05a'nın onaylı `mcp==2.3.0`), streamable HTTP, 05a `mcp_fixture.py` deseni; yeni bağımlılık yok. Kurulumun parçası değil.
- Araçlar (`tools/list`): `list_tickets(status="open") -> [{id, subject, received_at}]`, `get_ticket(ticket_id) -> {id, channel, subject, body}`, `send_reply(ticket_id, category, body) -> {accepted: true, reply_id}`. Onay sunucunun işi değil: 13b seed'i `tool_actions`'ta `send_reply`'ı `needs_approval=true` kaydeder (05a/07).
- Kayıt: her `tools/call` (yöntem, argüman, gelen başlık adları; değer yok) bellekte; `send_reply` ayrıca `/sink/sent.jsonl`'a (konteyner içi tmpfs). Muayene uçları fake-llm gibi: `GET /_calls`, `GET /_sent`, `POST /_reset`. Dışarı istek kodu yok (HTTP istemcisi import edilmez; test bunu `ast` taramasıyla kanıtlar).
- Kimlik: sahte araç kimlik doğrulamaz, gelen `Authorization`/`X-On-Behalf-Of` başlıklarının **varlığını** kaydeder (05a `forward_user` davranışını e2e'de görmek için); değerleri yazmaz.
- Çalıştırma: birim testi tools konteynerinde `docker compose run --rm --network none tools …` ile, sunucu 127.0.0.1'de süreç içi (dış ağ yok kanıtı). e2e'de compose servisi olarak backend'in görebileceği ağda olmalı → **S2**.
- Olumsuz kanıt (F2): onaysız ya da reddedilen run'dan sonra `/_sent` boş; onaylı run'dan sonra tam bir kayıt, `body`'de PII yer tutucusu/etiketi var, ham TC yok.

## F4 yakalama (S1)

- **A (Önerilen): 01 `fake-llm`'in mevcut `GET /_requests` kaydı.** LiteLLM'in sağlayıcıya gönderdiği gövdenin kendisi; 01'in dosyasına dokunmak gerekmiyor (zaten kaydediyor, `POST /_reset` var). e2e: `pii-100.jsonl`'dan sentetik PII içeren mesajla run → `/_requests` gövdelerinde ham değer 0, etiket/yer tutucu var. Bedel: yalnız sahte sağlayıcıyla kanıt; gerçek sağlayıcı yolu (llmaas elle testi) ayrıca.
- **B: LiteLLM erişim/ayrıntılı logu.** Gövdeyi loglamak için ayrıntılı log açılmalı; bu, K-02-0009 "log'da kişi verisi" kuralına ve 01 r1 MAJOR-1/2 (secret/upstream metni logda) derslerine ters; ayrıca logdan ayrıştırma kırılgan. Önermiyorum.
- **C: Langfuse izindeki girdi.** Bu FFCore'un gönderdiğini söyler, sağlayıcının aldığını değil; LiteLLM'in eklediği/değiştirdiği gövdeyi görmez. Ek kanıt olarak kullanılabilir, birincil değil.

## Koordinatöre sorular (karar istenen)

- **S1 F4 yakalama:** yukarıda; önerim A (01 dosyasına dokunmadan).
- **S2 ticket-desk compose servisi (kod dilimi, 05a merge sonrası):** backend sahte araca ağdan ulaşmalı. A (Önerilen): `deploy/docker-compose.yml`'a `fake-llm` kalıbında tek servis, `profiles: ["test"]`, backend imajı, `./tests/e2e/scenarios/fakes:/fakes:ro`, port yayınlamaz; touch-zone'a o dilimde tek servis bloğu eklenir. B: 13b'nin compose override dosyası (`tests/e2e/compose.e2e.yml`) içinde; ana compose'a dokunmaz ama ikinci compose dosyası açar (isci-a 13b touch-zone'u). C: e2e koşucusu içinde süreç içi sunucu; backend'in ona ulaşacağı sabit ad yok, kırılgan. Önerim A: fake-llm emsali var, tek dosya.
- **S3 ad:** `ticket-desk` (kaynak + gönderim) mi, GOREV'deki `ticket-sink` mi? Önerim `ticket-desk`.

## Değişen dosyalar
(kodlama sonrası)

## Kabul kriterleri → testler
(yukarıdaki tablo; durum sütunu kodlama sonrası)

## Çalıştırılan komutlar
(kodlama sonrası: `docker compose run --rm tools make lint`, `make test` iki profil, `py -3.12 -m unittest discover -s data/samples/scripts/tests -v` host + tools, `RUN_PG_TESTS=1` pg testleri)

## Varsayımlar ve brief'teki çelişkiler
1. Faker yok, stdlib + `gen/words.py`/sabit metin (K-SEN-0001 kabul).
2. plan/18 F1 `sozlesme-35.json` → `sozlesme-33.json` (DRIFT-28; koordinatör düzeltti).
3. 13a örnek testleri `make test` kapısında değil (Makefile `test` yalnız `backend/tests`); 18 de 13a gibi `unittest` ile koşar ve PR'da ayrı satır olarak yazılır. Kapıya eklenmesi FOLLOWUP adayı (koordinatör karar verir), bu PR'da Makefile'a dokunmuyorum.
4. `sql-20` ilk 5 item 13a'dan import edilir; ids yeniden numaralanır, köken `metadata.origin`'de.
5. Yazma denemelerinin `expected_code`'u 05a incelemedeki koddan; merge'de değişirse tek dosya güncellenir.

## Kalan riskler
- 05a ret kodları ve araç adı (`run_sql`) incelemede değişebilir.
- Bilet sınıflandırma isabeti (≥ %80) modele bağlıdır; veri yalnız sınıfların anlamca ayrışmasını sağlar, ölçüm 07 sonrası e2e'de.
