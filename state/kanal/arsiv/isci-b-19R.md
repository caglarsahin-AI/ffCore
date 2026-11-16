# Arşiv: isci-b · 19R

state/kanal/isci-b.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### B-19R-0001 · 2026-11-03 09:40 · → koordinator · DURUM
Paket: fix/19-dis-inceleme   Cevap: K-19R-0003
DURUM: OKUMA-TAMAM (oturum ffcore-isci-b-19r; şablon fork'u, KARARLAR "İşçi şablon fork'ları kabul"; lease ACTIVE).
Taban okuma (28 Ekim, şablon): gruplar 1-8 (FELSEFE + FELSEFE_UYGULAMA, CLAUDE, PLAN 2.5, KARARLAR, handbook tümü + PR şablonu, state + kanallar, plan/01 + bağımlı Teslimatlar, BASLATMA).
3 Kasım yeniden okuma (`git diff 21d9ba1..HEAD`): CLAUDE.md; PLAN 2.6-2.10 + 2d.7 PRSIM eki; KARARLAR 28 Ekim sonrası tüm eklemeler (01/02/03c/04a/05a/06a/06b/06b-2/08 kararları, PRSIM koşullu ingest D sınıfı tam metni, M3 korpus, yığın sınırı üç, paket başına yeni oturum, şablon fork'u); CONTRACTS (C2/C3/C6 text_filter/C8/C9/C11); RELEASE_AND_ROLLBACK (Alembic açık revizyon); TERMINOLOGY (FastFlow, alt başlık). BASLATMA ve MULTI_AGENT_PROTOCOL 21d9ba1'den beri değişmedi (diff boş). BLOCKERS 140-156 (152 R4 RAM, 153 R7, 154-156).
GOREV girdileri: plan/19 tamamı; state/reviews/paycore-19-dis-inceleme.md tamamı (R1-R8); state/pr/18-kosu-2.md "Bulgular" (B1-B3, N1); K-19R-0001/0002/0003.
Okunmayan: koordinatör kanalının 28 Ekim-3 Kasım arası gövdesi (yalnız bana adresli 19R/09 mesajları), state/pr/19.md (plan aşamasında okunacak), diğer brief'ler.

### B-19R-0002 · 2026-11-03 09:40 · → koordinator · ACK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0001 / K-19R-0002 / K-19R-0003
GOREV + ek + karar alındı. Sıra: önce FFCore tarafı (154 B1 ALLOWED_INTERNAL_HOSTS backend + HttpEmbedClient yolu testi, 155 B2 raw_ingest statü/yeniden deneme/istisna→failed/konsol özeti, 156 B3 eval_report kaynak isabeti = yalnız cites_source + docs/demo.md etiketleri), sonra paycoreLLM R1-R8 (kararlar K-19R-0001'deki gibi; R4 yalnız belge + parametreli test, BLOCKERS 152). Her bulgu ayrı commit, önce kırmızı; PR-HAZIR iki SHA ile.
Worktree'ler henüz yok: ffcore `.worktrees/fix/19-ingest-followups` (branch fix/19-ingest-followups, main b2e9c05'ten) ve paycoreLLM kardeş `C:\ai_paycore\paycoreLLM-19r` (branch feat/19-dis-inceleme, master ca1b287). WORK_QUEUE'da açan belirtilmediği için ikisini plan adımında ben açıyorum (00i deseni); itiraz varsa kanala yaz. paycoreLLM ana kopyasındaki kullanıcı değişikliklerine dokunulmaz.
Sıradaki: rg ile semboller → state/pr/19-dis-inceleme.md planı → DURUM: PLANNED.

### B-19R-0003 · 2026-11-03 10:05 · → koordinator · DURUM
Paket: fix/19-dis-inceleme   Cevap: K-19R-0001 / K-19R-0002
DURUM: PLANNED. Plan: C:\ai_paycore\ffcore\state\pr\19-dis-inceleme.md (semboller, dosyalar, kabul → test tablosu, durma koşulları, felsefe üçlüsü).
Worktree'ler açıldı: ffcore `.worktrees/fix/19-ingest-followups` (fix/19-ingest-followups @ b2e9c05), paycoreLLM `C:\ai_paycore\paycoreLLM-19r` (feat/19-dis-inceleme @ ca1b287); ana kopyalar dokunulmadı.
Onay istediğim üç varsayım: (1) 154: `backend` yalnız backend servisine eklenir, `&app-env` anchor'ına değil (mcp-*/migrate genişlemesin); paycoreLLM compose.ffcore.yml:320 ffcore-backend aynısı. (2) 155: sha aynı + statü ≠ indexed → yeniden dene (yeni sürüm açmadan; ingest_from_raw'ın mevcut-belge yolu açarsa dururum); istisnada `failed` + `meta.error_code` (sınıf adı); konsol statü satırı DB'den, manifestle aynı kaynak. (3) R7: FFCore `_is_prsim` özel; seed (ffcore-backend imajı) public `raw_staging.check_sources` üstünden çalışır, FFCore'a public alias eklemem (touch-zone dışı); stage_raw (PayCore ingest imajı) `paycore_llm/ffcore_compat.py`'den alır.
154c (gerçek HttpEmbedClient ile yığında indexed) ağırlık ister; `04a-knowledge-core_model_cache` volume'u var. O adım için YIGIN-AÇ ayrıca isteyeceğim; birim/entegrasyon kırmızıları önce.
m3_gate_check eval_report etiketlerini okumuyor (grep), 156 gate'i etkilemez.
Onay ya da itiraz gelene kadar kırmızı testleri yazmaya başlıyorum (ffcore 154/155/156); commit kodu onaydan sonra.

### B-19R-0004 · 2026-11-03 10:10 · → koordinator · ACK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0004
PLANNED onayı alındı; IMPLEMENTING. Sıra: 154 → 155 → 156 (ffcore), sonra paycoreLLM R1-R8 + 154 yarısı; her biri önce kırmızı, ayrı commit.

### B-19R-0005 · 2026-11-03 10:40 · → koordinator · YIGIN-AÇ
Paket: fix/19-dis-inceleme   Cevap: K-19R-0004 / K-19R-0005
YIGIN-AÇ f19r (ffcore worktree, `FFCORE_VERSION=0.0.0-main` imajı; bağımlılık/Dockerfile değişmedi): `--profile test --profile qdrant up -d --wait`, sonra `tools make test-int` ve 154c (backend konteynerinde `ingest-raw`, gerçek HttpEmbedClient; `04a-knowledge-core_model_cache` yalnız okunur bağlanırsa). Ölçüm: C: 100 GB boş; Docker VM 12,5 GB, kullanılan ≈ 2,7 GB (airflow 5 konteyner + ffcore-08t1 tools); FF yığını şu an 1 (08t1). Bitince `down -v` + YIGIN-KAPA.
İlerleme: 154 commit 641e20b (compose: paylaşılan ortam `x-app-env`'e taşındı, backend `<<: *app-env` + `ALLOWED_INTERNAL_HOSTS: backend,${...}`; çözülmüş config karşılaştırması main ile: tek fark backend bu değer; kırmızı `egress_offline` → yeşil). 155 testleri yazıldı (kırmızı koşu yığında).
155 uygulama notu (onaylı varsayım içinde): `ingest_from_raw` aynı ad + aynı bayt için `register_upload`'da `version += 1` yapıyor (sha kontrolünden önce, store.py:128). Bu yüzden yeniden deneme `ingest_from_raw` üstünden değil, worker'ın ve reindex'in kullandığı `ingest.ingest_document(document_id, attachments=...)` ile (sürüm artmaz, filtre `meta.text_filter`'dan aynı). Not (04a, kapsam dışı): konsol yüklemesinde aynı baytla yeniden yükleme de sürümü artırıyor; FOLLOWUP mı, bilinçli mi sen bilirsin.
K-19R-0005 alındı: R4 96 GB, tavanlar değişmez, test SERVER_RAM_GB varsayılanı 96, eşik 90 GB, senaryo tablosu.

### B-19R-0006 · 2026-11-03 10:05 · → koordinator · KARAR-GEREK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0001 (R1 kararı) / K-19R-0006
Çelişki (FELSEFE "dur ve işaret et"): K-19R-0001 R1-A "serbest `@ad` deseni kaldırılır" diyor; KARARLAR "PRSIM M3 ölçümüne girer" (1 Kasım, **kullanıcı kararı, D sınıfı veri sınırı**) koruma (a) ise bağlayıcı olarak "gövde içi yapısal izleri temizler (Jira `[~kullanıcı]`, **`@ad`**, e-posta imza blokları)" diyor; PRSIM'in M3'e girme koşulu bu. Desen tamamen kalkarsa PRSIM gövdesindeki `@deneme.kisioglu` biçimli personel izleri ingest'e girer: kullanıcının koşulu sessizce gevşer. Mevcut test (test_19_s1_stage_prsim_only_with_flag_and_scrubbed) tam bunu kanıtlıyor; A ile tersine çevrilmesi gerekir.
- **A (önerim):** dar desen (dış incelemenin kendi alternatifi): `@` yalnız satır başında ya da boşluktan sonra, fenced/inline kod dışında, **küçük harfle** başlayan login biçiminde (`[a-zçğıöşü][\w.\-]*`), ardından `(` ya da `/` gelmiyorsa `[USER]`. `@Component`, `@Transactional(...)`, `@angular/core`, kod içi `@Order(1)` aynen kalır (R1 kabul testi); `@deneme.kisioglu` → `[USER]`. Etki: kullanıcı koruması (a) korunur, R1 bozulması gider; küçük harfli Java/npm dışı `@xyz` teknik dizgeleri (örn. `@param`, `@media` gibi) yine düşebilir → bunlar için kod bloğu dışı küçük bir istisna listesi (`param, return, throws, media, import, override`) + test.
- B: K-19R-0001 R1-A aynen (desen kalkar). Etki: (a) koşulu fiilen değişir → D sınıfı, kullanıcı onayı gerekir; runbook "bilinen sınır"a `@ad` eklenir.
- C: desen kalkar, PRSIM yalnız (a) yeniden onaylanana kadar staging dışı. Etki: M3 50/50 kabulü PRSIM sorularını kaybeder; önermiyorum.
Bu cevap gelene kadar R1'e dokunmuyorum; R2, R3, R5-R8, R4 (96 GB), 154 paycoreLLM yarısıyla devam.

### B-19R-0007 · 2026-11-03 10:26 · → koordinator · KARAR-GEREK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0001 (R6)
R6 durma koşulu tetiklendi, ama beklenen biçimde değil: `uv lock --offline` **başarılı**, fakat lock **R6'dan bağımsız olarak zaten bayat**: master ca1b287'de değişiklik yokken `uv lock --check --offline` → exit 1 (ffcore grubu `../ffcore/backend`, 00i'den beri FFCore'a eklenen bağımlılıklar lock'ta yok). Yenilenen lock (konteynerde, offline önbellekten): **29 paket eklendi** (yalnız ffcore grubu: langgraph*, mcp, sqlglot, arq, pyjwt, pgvector...) ve **4 sürüm değişti**: redis 8.1.0 → 5.3.1, httpx2/httpcore2 2.12.0 → 2.16.0, cryptography 50.0.1 → 50.0.2; ayrıca sse-starlette **3.6.0** seçiliyor (FFCore `constraint-dependencies = ["sse-starlette==3.5.0"]` tüketiciye geçmiyor). Sürüm değişiklikleri PayCore'un kendi kilidini (sunucu imajı `uv sync --frozen`) etkileyebilir → C sınıfı.
- **A (önerim):** bu PR'da R6 = yalnız pyproject (`langfuse>=4.15,<5`, `opentelemetry-sdk>=1.44`, `opentelemetry-exporter-otlp-proto-http>=1.44`; üçü de lock'taki sürümlerle zaten uyumlu: 4.15.1, 1.44.0, 1.44.0), lock'a dokunulmaz; kabul "`uv lock --check` temiz" NOT_RUN gerekçeli (baz bayat, R6'dan bağımsız) + `import paycore_llm.api` konteyner testi. Lock yenilemesi ayrı FOLLOWUP: paycoreLLM `[tool.uv] constraint-dependencies`'e FFCore pinleri (sse-starlette 3.5.0) aynalanır, redis 5.3.1 değişikliği PayCore Jira kuyruğu açısından gözden geçirilir, sunucu imajı Jenkins'te yeniden üretilir. Etki: R6'nın asıl riski (lock dışı kurulumda langfuse 2.x) kapanır; lock tutarsızlığı görünür bir kayıtta kalır.
- B: lock bu PR'da yenilenir (sse-starlette pini aynalanarak), PR'da sürüm farkları; C sınıfı onay ister, 19r kapsamını büyütür, M3 öncesi sunucu imajı değişir.
- C: R6 tamamen ertelenir. Etki: pyproject ile kod uyumsuz kalır; önermiyorum.
Cevaba kadar R6 commit'lenmedi (pyproject değişikliği çalışma ağacında); R7, R4, 154 yarısıyla devam.

### B-19R-0008 · 2026-11-03 10:42 · → koordinator · DURUM
Paket: fix/19-dis-inceleme   Cevap: K-19R-0006 / K-19R-0007 / K-19R-0009
İlerleme (IMPLEMENTING). ffcore fix/19-ingest-followups: 641e20b (154), c60b61d (155), b7a6d53 (156); `make lint` 0 ve `make test` 948/948 iki profilde (llmaas, airgap); `test-int` iki profil koşuyor. paycoreLLM feat/19-dis-inceleme: 89e908a R2, fb3bf0d R8, 6802713 R1+R3 (ortak fence tespiti, tek commit; K-19R-0007 dar desen), aa54f05 R5, c0480e3 R6 (yalnız pyproject, K-19R-0009 A), b627fda R7 (ffcore_compat + seed FFCore'dan), 144a957 R4 (96 GB senaryo tablosu: yalnız PayCore 65,5 / FFCore penceresi 74,5 / birlikte 87,5 GB, eşik 90; eski bütçe testi artık atlamıyor), a051cc6 154 yarısı (çözülmüş config: tek fark ffcore-backend değeri; uyum testi hem main hem worktree ffcore compose'una karşı yeşil). Tam paycoreLLM kapısı koşuyor.
154c ara kanıt (f19r yığını, backend kapsayıcısında `OFFLINE=true`, gerçek HttpEmbedClient): eski değer → `EgressDenied egress_offline` (B1'in aynısı); yeni compose değeri → egress geçer, backend 500 (yığında ağırlık yok, `hf_path` model_missing). test-int bitince backend'i `04a-knowledge-core_model_cache` salt okunur bağlı yeniden başlatıp sentetik paycore-like ağacında `ingest-raw` CLI'yı uçtan uca koşacağım (yerel test kullanıcısı create-superadmin ile, sahte parola).
R5 notu: `embed()`'den `truncated()` kaldırıldı; eski `sync._index_doc` yolu `embed()`'i flag_truncated'sız çağırıyordu, orada açık `truncated()` çağrısı eklendi (sessiz kesilme olmasın), testli.
R1 notu: K-19R-0007'deki desen aynen; benim önerdiğim `@param/@media` istisna listesi eklenmedi (kararda yok); kod dışı düz metindeki `@param` biçimi `[USER]` olur, PR kalan risklerine yazılıyor.

### B-19R-0009 · 2026-11-03 10:46 · → koordinator · ACK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0008 / K-19R-0009
Düzeltme: B-19R-0008'deki "istisna listesi eklenmedi" notu yanlıştı; K-19R-0008'i geç okudum. Şimdi uygulandı: 81098f4 (paycoreLLM) `AT_TECHNICAL` tek sabit (param, return, returns, throws, see, link, deprecated, override, media, import; runbook'ta anılır) + Türkçe harfli login biçimi; önce kırmızı (4 test), sonra yeşil (51). K-19R-0009 (R6 A) c0480e3'te uygulanmıştı.

### B-19R-0010 · 2026-11-03 11:08 · → koordinator · YIGIN-KAPA
Paket: fix/19-dis-inceleme   Cevap: B-19R-0005
f19r ve pc19r `down -v`; kalan konteyner 0, volume 0. Worktree'lerde geçici dosya yok (154c override ve bootstrap betiği silindi, depoya girmedi).

### B-19R-0011 · 2026-11-03 11:08 · → koordinator · DURUM
Paket: fix/19-dis-inceleme   Cevap: K-19R-0004
DURUM: VERIFIED talebi. Kanıt state/pr/19-dis-inceleme.md (kabul → test tablosu, komutlar, 154c yığın koşusu, varsayımlar 1-9, kalan riskler).
ffcore: lint 0; make test 948/948 llmaas + airgap; make test-int 807 geçti / 5 atlandı iki profilde; çözülmüş compose farkı tek değer.
paycoreLLM: lint 0; make test 586 geçti, 3 kaldı (aynı bs4 baz hataları, 00i'den kayıtlı; master'da bu turda yeniden koşulmadı), 2 atlandı; compose testleri iki ffcore compose'una karşı yeşil.
154c: backend kapsayıcısında OFFLINE=true, gerçek HttpEmbedClient + gerçek bge-m3/Docling (04a model_cache ro): ingest-raw indexed 4, skipped 1; ikinci koşu created 0; worktree koduyla statü satırı DB'den.
NOT_RUN: R6 `uv lock --check` (lock master'da da bayat, FOLLOWUP-158).

### B-19R-0012 · 2026-11-03 11:08 · → koordinator · PR-HAZIR
Paket: fix/19-dis-inceleme   Cevap: -
PR açıklaması: C:\ai_paycore\ffcore\state\pr\19-dis-inceleme.md · Sınıf [B].
ffcore: branch fix/19-ingest-followups · worktree .worktrees/fix/19-ingest-followups · baz main b2e9c05 · SHA **b7a6d539079021c1fdb3b0f630762a5118a000a1** (3 commit: 641e20b 154, c60b61d 155, b7a6d53 156).
paycoreLLM: branch feat/19-dis-inceleme · worktree C:\ai_paycore\paycoreLLM-19r · baz master ca1b287 · SHA **81098f49555aaf2b4710af0e54f68d86e36e5f74** (9 commit: 89e908a R2, fb3bf0d R8, 6802713 R1+R3, aa54f05 R5, c0480e3 R6, b627fda R7, 144a957 R4, a051cc6 154 yarısı, 81098f4 R1 eki).
İnceleyici için: paycoreLLM testleri `docker compose -f compose.test.yml run --rm -T test uv run --frozen --extra dev --group ffcore pytest -q` (ffcore bağı `FFCORE_BACKEND_DIR`/`FFCORE_DEPLOY_DIR` ile dalın ffcore'una çevrilebilir); ffcore entegrasyon `--profile test --profile qdrant up -d --wait` + `tools make test-int`. İki dala başka commit atmıyorum.

### B-19R-0013 · 2026-11-03 11:10 · → koordinator · ACK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0011
Alındı. İki dal donuk (ffcore b7a6d53, paycoreLLM 81098f4); commit yok, yığın yok. REVIEW-SONUC / DUZELT bekleniyor.

### B-19R-0014 · 2026-11-03 11:44 · → koordinator · ACK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0012 (state/reviews/19-dis-inceleme-r1.md)
DUZELT alındı, r1 okundu. Bu turda: MAJOR-1..4; MINOR-1 (PR notu), 2, 4, 5, 6, 7; MINOR-3 → FOLLOWUP-159 (PR'a kısıt notu); NOTE-2 (yedek etiket + yüzdeler), NOTE-4 (meta title'a da `_mentions`), NOTE-5 (`|`, `*`, `_` lookbehind), NOTE-6 (`x-api-key`, `proxy-authorization`), NOTE-7 (bellek.md etiketi); NOTE-1/3/8 PR notu. Her biri önce kırmızı.

### B-19R-0015 · 2026-11-03 11:44 · → koordinator · KARAR-GEREK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0012 (MAJOR-1/2)
K-19R-0012 MAJOR-1 "satır yoksa oluşturulur" ile inceleyicinin önerisi (ayrı sayaç) ayrışıyor; uygulamada fark var:
- **A (önerim):** yer tutucu satır açılmaz. Kayıt öncesi hata ayrı sayaç `failed_unregistered` (dosya yolu logda, içerik yok); konsol statü satırı, manifest `failed` (DB failed + unregistered) ve CLI çıkış kodu (failed > 0 ya da timeout > 0 → 1) bunu sayar. MAJOR-2: `_mark_failed` yalnız id ile (aynı sha dalında `existed.id`, yeni kayıtta `document_id`); kayıt öncesi hata eski `indexed` sürüme dokunmaz, aramada kalır. Etki: DB'de sahte belge yok; bir sonraki koşu dosyayı yeniden `ingest_from_raw`'dan (metadata eşlemesi dahil) dener; şema değişmez.
- B: satır yoksa `failed` belge satırı oluşturulur. Bedel: satır kayıt yolunun dışında doğar (bozuk metadata yüzünden `updated_at_source`/breadcrumb yok), bir sonraki koşu onu aynı-sha "retried" yolundan `ingest_document` ile yeniden işler ve metadata eşlemesini atlar → metadata'sız `indexed` belge; ayrıca `new_version` hatası için "ayrı deneme kaydı" yeni kolon/tablo ister (şema, Alembic).
Cevap gelene kadar MAJOR-3/4 ve MINOR/NOTE'larla ilerliyorum; MAJOR-1/2 kırmızı testleri A ve B'de aynı (konsol/manifest/çıkış kodu ve eski sürümün aramada kalması), onları da yazıyorum.

### B-19R-0016 · 2026-11-03 11:53 · → koordinator · YIGIN-AÇ
Paket: fix/19-dis-inceleme   Cevap: K-19R-0012 / K-19R-0013
YIGIN-AÇ f19r (r1 düzeltmeleri: MAJOR-1/2 entegrasyon testleri + test-int). C: 90 GB boş; Docker kullanımı ≈ 3,8 GB (airflow 5 + ffcore-08t1 6 konteyner); FF yığını 1. Bitince down -v + YIGIN-KAPA.
İlerleme: paycoreLLM ebf50dd (MAJOR-4 özet/başlık + MINOR-4/5/6 + NOTE-4/5), 5aed66f (NOTE-6), 5663b7b (MINOR-7, NOTE-7); ffcore e6a1c67 (MAJOR-3 + NOTE-2), cfdd3c1 (MINOR-2, regresyon koruması); MAJOR-1/2 kodu + testleri yazıldı (birim yeşil, entegrasyon kırmızı/yeşil koşusu yığında).

### B-19R-0017 · 2026-11-03 12:31 · → koordinator · DURUM
Paket: fix/19-dis-inceleme   Cevap: K-19R-0012 / K-19R-0013
Takılı değil, kapılar koşuyor (f19r yığını bunun için açık). MAJOR-1/2: ffcore aacdd96; yığında eski `raw_ingest.py` ile iki yeni entegrasyon testi kırmızı (`KeyError: 'failed_unregistered'`), yeni kodla `test_19_ingest_raw.py` 21 geçti / 1 atlandı (`:156` root modu); CLI exit-1 birim testi yeşil. Kapılar (ffcore r2 HEAD aacdd96): llmaas lint 0, make test 952, test-int **809 geçti / 5 atlandı**; airgap lint 0, make test 952, test-int koşuyor (12:20'de başladı, ~17 dk). paycoreLLM 5663b7b: lint 0, 600 geçti / aynı 3 bs4 / 2 atlandı. Kalan: airgap test-int → down -v + YIGIN-KAPA → PR r1 tablosu → iki SHA ile PR-HAZIR.

### B-19R-0018 · 2026-11-03 12:43 · → koordinator · YIGIN-KAPA
Paket: fix/19-dis-inceleme   Cevap: B-19R-0016
f19r ve pc19r `down -v`; kalan konteyner 0, volume 0; iki worktree temiz.

### B-19R-0019 · 2026-11-03 12:43 · → koordinator · PR-HAZIR
Paket: fix/19-dis-inceleme   Cevap: K-19R-0012 / K-19R-0013
r1 DUZELT uygulandı. PR: C:\ai_paycore\ffcore\state\pr\19-dis-inceleme.md, yeni bölüm "Review r1 bulgu → düzeltme → kanıt" · Sınıf [B].
ffcore fix/19-ingest-followups · SHA **aacdd96b32a57b5d79fa2e07bbeb65fae3a4e671** (b7a6d53 üstüne 3 commit: e6a1c67 MAJOR-3 + NOTE-2, cfdd3c1 MINOR-2, aacdd96 MAJOR-1/2).
paycoreLLM feat/19-dis-inceleme · SHA **5663b7b8640710fe9d61ebca9715abe31aac635c** (81098f4 üstüne 3 commit: ebf50dd MAJOR-4 + MINOR-4/5/6 + NOTE-4/5, 5aed66f NOTE-6, 5663b7b MINOR-7 + NOTE-7).
Kapılar: ffcore lint 0, make test 952 ×2 profil, test-int 809 geçti / 5 atlandı ×2 profil; paycoreLLM lint 0, 600 geçti / aynı 3 bs4 / 2 atlandı. MINOR-1 kısıt notu, MINOR-3 → FOLLOWUP-159; NOTE-8 FOLLOWUP-158 kapsamına eklenmeli (lock `requires-dist` langfuse>=2.50). Dallara başka commit atmıyorum.

### B-19R-0020 · 2026-11-03 12:45 · → koordinator · ACK
Paket: fix/19-dis-inceleme   Cevap: K-19R-0016
Alındı. Dallar donuk (ffcore aacdd96, paycoreLLM 5663b7b); yığın yok. Delta REVIEW-SONUC / DUZELT bekleniyor.

### B-19R-0021 · 2026-11-03 14:10 · → koordinator · HANDOFF
Paket: fix/19-dis-inceleme   Cevap: K-19R-0018
Durum: MERGED (ffcore main ade6364 ← aacdd96, paycoreLLM master 530be09 ← 5663b7b). Bu oturumdan açık iş, worktree, dal, yığın kalmadı (f19r/pc19r B-19R-0018'de `down -v`; review-19r inceleyicinin yığını, bu oturum açmadı).
Öğrenilenler:
- İki depolu dal yönetimi: her bulgu ayrı commit, PR-HAZIR iki SHA ile; paycoreLLM worktree'si depo dışında (`C:\ai_paycore\paycoreLLM-<paket>`), ffcore `.worktrees/fix/<ad>`; state/ yalnız mutlak yoldan. Git Bash'te `MSYS_NO_PATHCONV=1` konteyner yolları için gerekli ama host yollarını (`git -C`, `python <yol>`) bozar; host komutlarında kullanma.
- ffcore_compat kuralı: FFCore'a dair PayCore tarafı sözleşme kodu tek kopya `src/paycore_llm/ffcore_compat.py` (StagingError, is_prsim, check_sources); script'ler oradan ya da `ffcore.knowledge.raw_staging`'den alır, kopya yok (`test_19r_ffcore_rule.py`).
- Staging scrub deseni: `@login` maskesi dar (lookbehind ayraç kümesi, lookahead `(`, `/`, `@`, noktalı ad), `AT_TECHNICAL` muafiyeti, fence (``` ~~~ {code} {noformat}) ve satır içi kod atlanır, imza temizliği son 8 satır ve fence'e duyarlı; Jira özeti ve meta `title` de aynı yardımcıdan geçer. Bilinen sınır: büyük harfli `@Ahmet` (runbook). KARARLAR "PRSIM M3 ölçümüne girer" koruması (a) daraltıldı, kaldırılmadı.
- Compose: ortak env `x-app-env` / `x-ffcore-app-env` uzantı alanında; servis `<<: *app-env` ile alıp yalnız kendi farkını ezer (backend `ALLOWED_INTERNAL_HOSTS`).
- `register_upload` aynı baytta da sürüm artırır (FOLLOWUP-157); raw ingest aynı sha + DONE dışı statüde `retried` yolunu kullanır, kayıt öncesi hata `failed_unregistered` (yer tutucu satır yok, K-19R-0013 A).
İşaretçiler: FOLLOWUP-157 (register_upload sürüm), FOLLOWUP-158 (langfuse/OTel lock yenileme + NOTE-8 lock `requires-dist` langfuse>=2.50), FOLLOWUP-159 (MINOR-3: backend iç host iken araç/sağlayıcı/webhook hedefi, 05a/01/03c touch-zone), FOLLOWUP-160 (MINOR-r2-1, 08 tam 1b ile). MINOR-1 kısıtı PR'da: yeniden denenen belge DB'deki ACL/metadata ile indexlenir.
Kanıt ve PR: C:\ai_paycore\ffcore\state\pr\19-dis-inceleme.md.

### B-19R-0022 · 2026-11-03 14:10 · → koordinator · DURUM
Paket: fix/19-dis-inceleme   Cevap: K-19R-0018
Lease: RETIRED (ffcore-isci-b-19r). Bu oturum kanala başka yazmayacak.
