# Kanal: test

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-test-13a
- Aktif paket: 13a
- Durum: ACTIVE
- Son okunan: koordinator K-13a-0015 (2026-10-28 09:22)

## Mesajlar

### T-13a-0001 · 2026-10-28 02:21 · → koordinator · DURUM
Paket: 13a   Cevap: -
DURUM: OKUMA-TAMAM
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE; 3 PLAN v2.4 tamamı; 4 KARARLAR (28 Ekim eklemeleri dahil: Docker'da araçlar, chainguard MinIO, imaj çekme izni); 5 handbook tümü + templates/PR_SABLONU; 6 WORK_QUEUE, BLOCKERS, HANDOFF, altı kanal, state/pr; 7 plan/ 17 brief'in tamamı (13, 06 definition şeması, 08 PII kategorileri, 14 hafıza test gereksinimleri dahil); 8 BASLATMA.
Kullanıcı talimatı (ROL=test PAKET=13a) alındı; bu oturum yalnızca 13a içindir, 13b'ye geçilmez.

### T-13a-0002 · 2026-10-28 02:21 · → koordinator · ACK
Paket: 13a   Cevap: K-13a-0001
GOREV alındı. Branch feat/13a-sample-data, worktree C:\ai_paycore\ffcore\.worktrees\feat\13a-sample-data (53ae18c, temiz).
Touch-zone daraltması (kullanıcı talimatı, GOREV'e üstün): `data/samples/README.md` 00'ın dosyası sayılıyor, **dokunmuyorum**; açıklamalar `data/samples/scripts/README.md` ve alt dizin README'lerine gider. GOREV bunu touch-zone'a koymuştu; çakışmayı kayda geçirmeni isterim.
Kullanıcı talimatı ayrıca: yeni bağımlılık ve imaj koordinatör üzerinden C sınıfı onay ister. Sıradaki adım: state/pr/13a.md planı, sonra PLANNED DURUM'u.

### T-13a-0003 · 2026-10-28 02:21 · → koordinator · KARAR-GEREK
Paket: 13a   Cevap: K-13a-0001
Konu: PII (100 cümle) ve hafıza (40 konuşma) setlerinde sentetik kişi adı. Brief 13 "kişi adı üretilmez" der (madde 1 ve teknik notlar); GOREV (a) "PII setinde adlar sentetik ve etiketli (C18)" der; 08 kabulü ad-soyad recall ≥ 0,85 ve 14 kabulü "hasta adı içeren konuşmadan 0 madde" ad içeren örnek ister. Kullanıcı bu kategoride kararı bana bırakmadı.
A (Önerilen): ad yalnızca `pii/` ve `memory/` setlerinde, scriptte sabit uydurma ad/soyad havuzundan kombinasyon, her geçiş etiketli (`PERSON`); sözleşme, şema, sınav ve agent dosyalarında ad yok ve `test_13a_*_no_person_names` bunu kanıtlar. Bedel: depoda ad benzeri dizgiler bulunur (gerçek kişiyle eşleşme iddiası yok).
B: adlar `[AD_SOYAD]` yer tutucusu. Bedel: 08 NER recall'u ve 14'ün "0 kaçak" testi gerçek biçimle ölçülemez.
C: ad kategorisini 13a'dan çıkar, 08 tam / 14'te üret. Bedel: 13a teslimatı eksik kalır, iş o paketlere kayar.
Karar gelene kadar adsız üretimlerle (sözleşme, şema, ajan, sınav, OpenAPI, PII'nin ad dışı kategorileri) devam ediyorum.

### T-13a-0004 · 2026-10-28 02:21 · → koordinator · SORU
Paket: 13a   Cevap: K-13a-0001
1) Bağımlılık: GOREV (e) Faker/python-docx/reportlab listeler. Önerim **yalnız stdlib** (DOCX = zip+XML, PDF = elle yazılmış metin katmanlı PDF; sabit Türkçe kelime havuzları, `random.Random(seed)`). Böylece yeni bağımlılık ve C sınıfı onay yok, çıktı byte düzeyinde deterministik; brief 13 teknik nottaki "Faker" sapması PR'a yazılır. Onaylıyor musun, yoksa C sınıfı talebi mi açayım?
2) Demo SQL denemesi için izole test Postgres: 00'ın seçtiği `pgvector/pgvector:pg16` imajını (digest PR'a) port yayınlamadan geçici konteynerde koşup `docker exec psql` ile yüklemeyi öneriyorum; KARARLAR "imaj çekme izni" bunu kapsıyor mu, imaj/sürüm doğru mu?

### T-13a-0005 · 2026-10-28 02:21 · → koordinator · DURUM
Paket: 13a   Cevap: K-13a-0001
DURUM: PLANNED talebi. Plan state/pr/13a.md (PR_SABLONU 1-9, felsefe üç sorusu, 16 test satırı). Plandaki 8 varsayımdan 4'ü koordinatör görüşü ister:
(1) stdlib-only üretim (T-13a-0004/1); (2) sentetik ad (T-13a-0003);
(3) 5 SQL item'ı için 09 `style` enum'unda değer yok: `style=dogrudan` + `tags:["sql"]`, yeni enum değeri uydurmuyorum;
(4) Brief 13 `veri-soru-cevap`'ı "run_sql onaysız" tanımlar, PLAN 2d karar 5 PoC SQL asistanını "max_tool_calls 1, run_sql onaylı" tanımlar (PLAN kazanır). Soru: PoC'nin onaylı SQL asistanı `veri-soru-cevap` şablonunun kendisi mi olsun (onaylı + max_tool_calls 1, brief 13 düzeltilir), yoksa şablon brief 13'teki gibi kalıp PoC ayarı 13b seed'inde mi verilsin? Önerim: şablonun kendisi PLAN 2d'ye uysun; tek kaynak, 13b'de ikinci tanım olmaz.
Kodlama PLANNED onayı ve T-13a-0004 cevabı gelince başlıyor; ad kararı yalnız pii/ ve memory/'nin ad içeren kısmını bekletir.

### T-13a-0006 · 2026-10-28 02:35 · → koordinator · ACK
Paket: 13a   Cevap: K-13a-0002
Alındı ve uygulandı: stdlib-only; veri-soru-cevap PLAN 2d'ye göre (approval.actions ["mcp-sql.run_sql"], max_tool_calls 1); SQL item'ları style=dogrudan + tags ["sql"]; data/samples/README.md'ye dokunulmuyor; ad içeren PII/hafıza kayıtları DECISION-24'ü bekliyor.
Postgres: `docker pull` bu oturumda çalıştı (ENV-26 burada yok). 00'ın compose'u `pgvector/pgvector:0.8.1-pg16` pinliyor; 00'ınki kazanır kuralıyla o etiket kullanıldı, digest sha256:33198da2828a14c30348d2ccb4750833d5ed9a44c88d840a0e523d7417120337 (PR'a yazılacak).
İlerleme (branch feat/13a-sample-data):
- c01f955: schema (6 tablo, tam 10.000 satır, salt-okunur rol şablonu, schema_descriptions, 20 few_shot), 3 agent şablonu, Superset OpenAPI (6 işlem). test_13a_2/2b/2c/3/7/8 geçti.
- d7100f3: test_13a_2d (10.000 satır yüklendi) ve 2e (20 few_shot agent_readonly ile koştu, DELETE reddedildi) `ffcore-13a-pg` konteynerinde geçti, 53 s; konteyner silindi.
Sıradaki: sözleşmeler (PDF metin katmanı + ToUnicode, K-13a-0002 PDF şartı için stdlib zlib/ToUnicode geri okuma testi), sonra sınav seti, PII'nin ad dışı kategorileri, hafızanın ad içermeyen konuşmaları.

### T-13a-0007 · 2026-10-28 02:44 · → koordinator · KARAR-GEREK
Paket: 13a   Cevap: -
Konu: sınav setinin toplamı. plan/09 R8.1, plan/13 madde 4 ve GOREV (c) seti "35 soru" diye adlandırır, ama zorunlu dağılım 12 doğrudan + 8 dolaylı + 5 alan içi + 3 alan dışı + 5 SQL = **33**. plan/13 kabul tablosu da 20/8/5 üzerinden eşik verir (≥16/20, 7/8, ≥4/5), yani 33'e göre yazılmış.
A (Önerilen): dağılım aynen, toplam 33; dosya `sozlesme-33.json`, suite/dataset adı `sozlesme-33`, brief 09/13 dalga 1 kapanışında "35" → "33" düzeltilir. Bedel: ad değişikliği 09 ve 13b referanslarına yansır; eşiklerin hiçbiri değişmez.
B: 2 dolaylı soru eklenir (12+10+5+3+5 = 35), ad `sozlesme-35` kalır. Bedel: belge soruları 22 olur, 13 kabul tablosu (≥16/20) yeniden ölçeklenmeli; dolaylı ağırlığı artar (PayCore dersiyle uyumlu).
C: 2 SQL sorusu eklenir (7 SQL). Bedel: SQL eşiği (≥4/5) değişir; belge kalitesine katkısı yok.
Şimdilik: üretim 33 item, dosya adı değişmeden `sozlesme-35.json`; test dağılımı ve "toplam = dağılım toplamı"nı sabitliyor, "35" etiketini değil.

### T-13a-0008 · 2026-10-28 02:44 · → koordinator · DURUM
Paket: 13a   Cevap: -
İlerleme (feat/13a-sample-data, IMPLEMENTING):
- 14839fc: 5 sözleşme (2 PDF, biri 10 sayfa; 3 DOCX), manifest (ACL: analyst ×3, admin, boş C15). PDF metin katmanı: Helvetica + cp1254 /Differences + /ToUnicode, Flate; test stdlib ile CMap üzerinden geri okuyup madde metnini birebir karşılaştırıyor (K-13a-0002 şartı). Sınır: Docling okuması 04a ingest testinde kanıtlanır.
- a99b9d8: sınav seti + suite (contains, cites_source, sql_result, llm_judge; eşik 0,8). Testler: must_contain ilgili belgede var, cevapsız terimler KB'de 0 eşleşme, dolaylı soru belgenin terimini kullanmıyor, SQL beklenenleri Python'da ve Postgres'te (agent_readonly ile) eşit.
Testler: unit 14/14 geçti (2 Postgres testi opt-in), Postgres 3/3 geçti (52 s, konteyner silindi).
Sıradaki: PII setinin ad dışı kategorileri, hafıza setinin ad içermeyen konuşmaları; ad içeren kısımlar DECISION-24'ü bekliyor.

### T-13a-0009 · 2026-10-28 02:53 · → koordinator · ACK
Paket: 13a   Cevap: K-13a-0003
Karar A uygulandı: 7017e38 `data/samples/eval/sozlesme-35.json` → `sozlesme-33.json`, suite/dataset `sozlesme-33`; test toplamı 33'e ve dağılım toplamına sabitliyor. Brief'lere dokunulmadı (DRIFT-28 sende).

### T-13a-0010 · 2026-10-28 02:53 · → koordinator · DURUM
Paket: 13a   Cevap: -
Ad gerektirmeyen her şey bitti (feat/13a-sample-data, HEAD cdc5788):
- 518cc7d PII: 100 cümlenin 80'i; ad dışı 18 kategorinin hepsi ≥2 kez (TC/VKN/IBAN/kart checksum'ları geçerli, kartlar test BIN'lerinden), çoklu varlıklı cümleler, yanlış checksum'lı benzerlerle negatifler. Doğrulayıcılar bilinen açık örneklerle çapalı.
- 9f78afb Hafıza: 40 konuşmanın 36'sı; profil/tercih/gerçek/karar, "bunu hatırla", supersede, dedupe; negatifler geçici istek, belge içeriği, üçüncü kişi, PII (açık komut yolu dahil, C19), sağlık. Test: PII/sağlık içeren her konuşma expect_none.
- cdc5788 `data/samples/scripts/README.md`. Plandaki ayrı `validate.py` yazılmadı: unittest aynı kontrolleri yapıyor, ikinci doğrulayıcı tekrar olurdu (PR'a yazılacak).
Testler: 20 koştu, 15 geçti, 5 NOT_RUN (3 Postgres opt-in, ayrıca koşuldu ve geçti; 2 toplam testi DECISION-24).
Kalan tek iş: DECISION-24 cevabına göre 20 PII + 4 hafıza kaydı ve `test_13a_9_no_person_names_outside_pii_memory`. Karar gelince 1 dilim, sonra PR açıklaması ve VERIFIED talebi.

### T-13a-0011 · 2026-10-28 02:57 · → koordinator · ACK
Paket: 13a   Cevap: K-13a-0004
`state/pr/13a.md` ad dışı bölümleri dolduruldu (HEAD cdc5788): plan uygulamadaki sapmalarla güncel (validate.py yok), 38 dosyalık değişen dosya listesi, 22 satırlık kabul kriteri → test tablosu (17 geçti, 2 NOT_RUN DECISION-24, test_13a_9 yazılmadı), komutlar/exit/süre, pgvector digest, post-state, 10 varsayım ve 6 kalan risk (Docling okuması 04a'da dahil).
Not: `make lint`/`make test` NOT_RUN, 00'ın `tools` servisi bu branch'te yok; 13a Python dosyaları ruff'tan 00 merge'ünden sonra geçmeli. Host'a ruff kurmadım (KARARLAR "araçlar Docker'da").
DECISION-24 cevabını bekliyorum.

### T-13a-0012 · 2026-10-28 07:25 · → koordinator · DURUM
Paket: 13a   Cevap: K-13a-0006
DURUM: IMPLEMENTED. Son dilim commit 591add4823a957051982668c4a895ad4185b7db1 (branch feat/13a-sample-data, push yok).
- PII 100/100: 20 `PERSON` span'li cümle; adlar `gen/pii.py` içindeki sabit havuzdan (16 yaygın ad × 12 uydurma soyad), seed'e bağlı biçimler (normal, iki ad, BÜYÜK, küçük, SOYAD Ad). Unvan span dışında; havuz cinsiyet/ünlü uyumu tutmadığından Bey/Hanım ve ad sonrası ek yok. İlk 80 kayıt bayt olarak değişmedi.
- Hafıza 40/40: 4 `person_name` konuşması, hepsi `expect_none`; `contains_person_name` alanı 40 kaydın hepsinde (4'ünde true).
- `test_13a_9_no_person_names_outside_pii_memory`: havuzdaki her ad/soyad pii/, memory/ ve scripts/ dışındaki her dosyada (PDF/DOCX geri okunarak) 0 eşleşme; boş geçmesin diye her soyadın izinli setlerde gerçekten geçtiği de doğrulanıyor.
Testler (HEAD 591add4): unittest 21 test, 18 geçti, 3 NOT_RUN (Postgres opt-in); `RUN_PG_TESTS=1` ayrı koşu 3/3 geçti (67,8 s, konteyner silindi). `generate.py` sonrası git status temiz. 5b ve 6b artık geçiyor.
`state/pr/13a.md` güncellendi (tüm NOT_RUN satırları kapandı; make lint/test K-13a-0005 gereği NOT_RUN).
İşaret (karar istemiyor, DUZELT ile değişir): karar metni `PERSON` dediği için `KISI_ADI` → `PERSON` yaptım. Diğer 18 kod Türkçe (`TC_KIMLIK`…), set karışık dilli kaldı. 08 tek dilli kod isterse yalnız `CATEGORIES` sözlüğü değişir.
Doğrulanmadı: uydurma soyadların gerçek bir kişiyle hiç çakışmadığı (dış kaynağa bakılmadı).
Sıradaki: 00 MERGED → main'e rebase → `docker compose run --rm tools make lint` ve `make test` → VERIFIED talebi ve PR-HAZIR.

### T-13a-0013 · 2026-10-28 08:30 · → koordinator · DURUM
Paket: 13a   Cevap: K-13a-0008
DURUM: VERIFIED. Branch feat/13a-sample-data, main 78c8412 üzerine rebase (bb634e4 dahil; çakışma yok), HEAD 4c2981754b88be9dcf0171c89273a9b22dd2ab2a. Değişen dosyaların hepsi `data/samples/**` içinde (38 dosya).
- `tools make lint`: 0 (11 s). `tools make test`: llmaas 0 (18 passed), `-e DEPLOY_PROFILE=airgap` 0 (18 passed).
- Not: `make lint` hedefi `backend scripts`, `make test` hedefi backend; 13a kodu ikisinde de yok. Bu yüzden 13a testlerini tools konteynerinde ayrıca koştum: 18 geçti, 3 NOT_RUN (Postgres opt-in). Host'ta da 18/18, `RUN_PG_TESTS=1` 3/3 (57 s, konteyner silindi).
- Bulundu ve düzeltildi (yeni commit 4c29817, `fix(samples)`): ilk konteyner koşusunda `test_13a_8_deterministic` 3 DOCX'te düştü. Sebep zlib değil, `zipfile.ZipInfo.create_system` (Windows'ta 0, Linux'ta 3). 3'e sabitlendi, 3 DOCX yeniden üretildi; host (zlib 1.3.1) ve konteyner (zlib 1.2.13) artık aynı baytı üretiyor.
state/pr/13a.md güncel: kapı satırları, konteyner koşusu, düzeltme ve risk notu.

### T-13a-0014 · 2026-10-28 08:30 · → koordinator · PR-HAZIR
Paket: 13a   Cevap: K-13a-0008
PR: state/pr/13a.md · Branch: feat/13a-sample-data · SHA: 4c2981754b88be9dcf0171c89273a9b22dd2ab2a · Sınıf: [A] · push yok.

### T-13a-0015 · 2026-10-28 08:30 · → koordinator · KARAR-GEREK
Paket: 13a   Cevap: -
Ruff ve 13a betikleri: kök `ruff.toml` ile `data/samples/scripts` ayrıca koşulunca 163 bulgu çıkıyor (çoğu E501 >100 sütun, 2 I001, 1 B905 `zip` strict) ve 14 dosya formatlanmamış. Kapıda değil, davranış etkisi yok. Ayar değiştirmedim.
- **A (önerim):** 13a bu haliyle merge edilir; FOLLOWUP: `ruff format` + elle E501 düzeltmesi ve `data/samples/scripts`'in `make lint` hedefine eklenmesi tek PR'da (Makefile sahibi 00; `test_13a_8` aynı baytı kanıtlamalı). Etki: 13a gecikmez, stil borcu kayıtlı kalır.
- **B:** Merge'den önce 13a'da düzeltirim (format + ~elle E501, yeniden üretim, testler; tahmini 1 dilim). Kapıya ekleme yine Makefile işi. Etki: 13a temiz girer, review delta'sı büyür.
- **C:** Hiç düzeltilmez, betikler kapı dışında kalır. Etki: depo standardıyla kalıcı tutarsızlık. Önermiyorum.

### T-13a-0016 · 2026-10-28 08:31 · → koordinator · ACK
Paket: 13a   Cevap: K-13a-0009
DUZELT alındı, B uygulanıyor: `data/samples/scripts/**` için ruff format + check --fix + elle E501/B905 (ruff.toml değişmez), yeniden üretim ve test_13a_8 ile bayt eşitliği, Makefile lint hedefine `data/samples/scripts` (tek satır), tüm kapılar, PR güncellemesi ("test işçisi A önerdi, koordinatör B seçti" notu dahil), yeni tam SHA ile PR-HAZIR.

### T-13a-0017 · 2026-10-28 08:47 · → koordinator · DURUM
Paket: 13a   Cevap: K-13a-0009
DURUM: VERIFIED. DUZELT K-13a-0009 (B) uygulandı, commit `d70f77a` (`style(samples)`), HEAD d70f77acc0b466d2dd479b26419cfb6da617b148.
- `data/samples/scripts/**`: `ruff format` + `check --fix`; uzun metinler bitişik string birleştirmesiyle yeniden sarıldı ve her dosyanın AST'si değişmeden kaldı (otomatik karşılaştırma); DOCX XML sabitleri ortak öneklerden kuruldu ve eski değerlere eşit olduğu doğrulandı; B905 `zip(strict=True)`. `ruff.toml` değişmedi.
- Çıktı değişmedi: yeniden üretim sonrası hiçbir üretilmiş dosya değişmedi, `test_13a_8` aynı baytı kanıtlıyor.
- Makefile: "tek satır" yerine `lint` hedefinin iki satırı (`ruff check` ve `ruff format --check`) değişti, ikisi de dizini kapsamalıydı. `format` hedefine dokunmadım (PR riskleri altında not).
Kapılar (HEAD d70f77a): `tools make lint` 0 (46 dosya, 13a dahil); `tools make test` llmaas 0 ve airgap 0 (18 passed); 13a unittest host 18/18 ve konteyner 18/18 (3 NOT_RUN Postgres opt-in); `RUN_PG_TESTS=1` 3/3 (72 s, konteyner silindi). Branch: 39 dosya, 38'i data/samples/** içinde, +1 Makefile.
state/pr/13a.md güncel; varsayım 11'de "test işçisi A önerdi, koordinatör B seçti" yazıyor.

### T-13a-0018 · 2026-10-28 08:47 · → koordinator · PR-HAZIR
Paket: 13a   Cevap: K-13a-0009
PR: state/pr/13a.md · Branch: feat/13a-sample-data · SHA: d70f77acc0b466d2dd479b26419cfb6da617b148 · Sınıf: [A] · push yok.

### T-13a-0019 · 2026-10-28 09:08 · → koordinator · ACK
Paket: 13a   Cevap: K-13a-0012
DUZELT r1 alındı, uygulanıyor: MAJOR-1 şema açıklaması ve few-shot'lar `veri-soru-cevap` sistem prompt'una gömülür, prompt yalnız `run_sql` ister, `max_tool_calls` 1 kalır, test `test_13a_3b_sql_agent_single_call_consistent`; MAJOR-2 q14 `must_contain` referanstaki biçime iner, tüm item'lar için "altın cevap kendi must_contain'ını geçer" testi; MINOR-1 Postgres konteyner adı benzersiz sonekli, `rm -f` yalnız kendi adına, kurulum `try/finally` ile korunur. Kapılar yeniden, PR'a r1 bulgu → düzeltme → kanıt tablosu, yeni tam SHA ile PR-HAZIR.

### T-13a-0020 · 2026-10-28 09:20 · → koordinator · DURUM
Paket: 13a   Cevap: K-13a-0012
DURUM: VERIFIED. Review r1 düzeltmeleri commit `e663597` (`fix(samples)`), HEAD e663597d20bbda7046c3291e1a13f9c716bb4b45.
- MAJOR-1: `veri-soru-cevap` sistem prompt'una şema açıklaması (6 tablo, tüm kolonlar, ölçü formülleri) ve 20 few-shot gömüldü; araç listesi yalnız `run_sql`; prompt `get_schema` demiyor; `max_tool_calls` 1. Ayrıca `ask_user` false yaptım: plan/06'da `ask_user_question` ayrı bir araç ve sayaca girip girmediği yazmıyor, tek çağrılık bütçeyi tüketebilir. Belirsiz soruda agent araç çağırmadan eksik bilgiyi yazar. 06a sayılmadığını netleştirirse geri açılabilir; PR varsayım 4'te. Test `test_13a_3b_sql_agent_single_call_consistent` (üç şablonda da prompt'un andığı araçlar ⊆ izinli araçlar). Prompt ~6,3 bin karakter (~2 bin token).
- MAJOR-2: q14 `must_contain` "4 saat". Yeni `test_13a_4f_gold_answer_passes_must_contain` tüm item'ları tarıyor; değişiklikten önce yalnız q14'te düştü.
- MINOR-1: Postgres konteyneri benzersiz adlı (`ffcore-13a-pg-<pid>-<hex>`); aynı ad varsa silmek yerine hata; kurulum hatasında kendi konteynerini kaldırıyor. İki yol ayrı betikle denendi: yükleme hatasında geride konteyner kalmadı, önceden var olan aynı adlı konteyner korundu.
- Yeni testler değişiklikten önce düştü, sonra geçti. Üretilmiş veride yalnız iki dosya değişti, ikisi de bilerek: `agents/veri-soru-cevap.json`, `eval/sozlesme-33.json`.
Kapılar (HEAD e663597): `tools make lint` 0 (46 dosya); `tools make test` llmaas 0 ve airgap 0 (18 passed); 13a unittest host ve konteyner 23 test, 20 geçti, 3 NOT_RUN (Postgres opt-in); `RUN_PG_TESTS=1` 3/3 (86 s, konteyner kalmadı).
state/pr/13a.md: "Review r1 bulgu → düzeltme → kanıt" tablosu eklendi, test ve komut tabloları güncel.

### T-13a-0021 · 2026-10-28 09:20 · → koordinator · PR-HAZIR
Paket: 13a   Cevap: K-13a-0012
PR: state/pr/13a.md · Branch: feat/13a-sample-data · SHA: e663597d20bbda7046c3291e1a13f9c716bb4b45 · Sınıf: [A] · push yok · review r2 için.
