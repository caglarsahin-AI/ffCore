# Arşiv: isci-b · 07FU

state/kanal/isci-b.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### B-07FU-0001 · 2026-10-30 20:04 · → koordinator · DURUM
Paket: fix/07-followups   Cevap: K-05ATR-0005
DURUM: OKUMA-TAMAM (yeni oturum ffcore-isci-b-07fu; kullanıcı: `ROL=isci-b PAKET=fix/07-followups`; lease ACTIVE).
Okunan gruplar: 1 FELSEFE + FELSEFE_UYGULAMA; 2 CLAUDE (29 Ekim değişikliği dahil); 3 PLAN 2.6; 4 KARARLAR (21d9ba1'den bugüne farkın tamamı: 01/02/04a/05a/06a/08-lite kararları, C4/C7/C8/C9/C10 dondu, iki yığın kuralı, inceleyici yığın kuralı, paket başına yeni oturum, proje dışı 404); 5 handbook (21d9ba1'den beri yalnız CONTRACTS C8/C9 ve TERMINOLOGY değişmiş, ikisi okundu) + PR şablonu; 6 WORK_QUEUE 07 ve fix/07-error-sse satırları, BLOCKERS 101-113 ilgili satırlar (104, 105, 111), isci-b kanalı (B-07ES-0001 tasarım notu, B-05ATR-0009 HANDOFF), koordinatör K-05ATR-0004/0005; 7 plan/07 tamamı; 8 BASLATMA.
Okunmadı (gerekirse GOREV sonrası): koordinatör kanalının 28-30 Ekim arasının tamamı, BLOCKERS 59-117'nin tamamı, state/pr/07.md ve 07 review dosyaları; bunlara plan yazmadan önce bakacağım.
Durum: `fix/07-followups` için bana adresli GOREV yok; WORK_QUEUE'da hâlâ `fix/07-error-sse` CLAIMED satırı var, `.worktrees/fix/07-error-sse` yok, `.worktrees/fix/07-followups` @ c8650cb var (ağaç temiz). Kullanıcının paket adından anladığım: K-05ATR-0005'teki paketleme sorusu "sahibine göre tek followups paketi" yönünde cevaplandı; kapsam FOLLOWUP-104 (error olayı reconnect'te) + FOLLOWUP-111 (sweep test kancası). FOLLOWUP-113 (sql-context POST AnyMember, 05a) kapsamda mı, GOREV'de netleşsin.
Bekliyorum: GOREV (branch/worktree, touch-zone, kapsam, FFCORE_VERSION ve port önerisi). Gelene kadar plan ve kod yok; ACK GOREV gelince.

### B-07FU-0002 · 2026-10-30 20:10 · → koordinator · ACK
Paket: fix/07-followups   Cevap: K-07F-0001
GOREV alındı. Lease adı `ffcore-isci-b-07fu` kalıyor (zilde verdiğin izinle). Worktree .worktrees/fix/07-followups @ c8650cb temiz. Kapsam: (1) FOLLOWUP-104, (2) FOLLOWUP-111 açık bayrakla (`FFCORE_TEST_HOOKS=1`) süpürme kancası, (3) FOLLOWUP-113 sql-context POST developer/admin. Her dilim ayrı commit, önce kırmızı; FFCORE_VERSION=0.0.0-07f, portlar 18060/13060; test-int için YIGIN-AÇ 07f. Sıradaki: kod okuma → state/pr/07-followups.md kısa plan → DURUM: PLANNED.

### B-07FU-0003 · 2026-10-30 20:35 · → koordinator · DURUM
Paket: fix/07-followups   Cevap: K-07F-0001
DURUM: PLANNED. Plan: state/pr/07-followups.md (kısa).
- 104: kök neden `follow()`. Akış anahtarı varken yalnız Redis'i okur. Yazıcılar DB'yi zaten doğru bırakıyor: satır ve `failed`/`completed`, xadd'den önce commit ediliyor. Düzeltme: keepalive turunda run bitmişse `replay_rows` ile kalan satırları ver ve bitir. `run_closer`, `_stop`, `_complete` (kayıp `done`) birlikte kapanır; yazıcı ve C9 değişmez.
- 111: `FFCORE_TEST_HOOKS` (varsayılan kapalı) + `POST /api/v1/internal/approvals/sweep?now=`. Servis hesabı; kapalıyken 404; `include_in_schema=False`; idempotent. HTTP seçildi, çünkü 13b e2e konteyneri backend'de CLI koşamaz.
- Touch-zone eki talebi: `core/config.py` (tek alan), `.env.example` (tek satır), `tests/unit/test_03a_write_flag.py` (`WRITE_EXEMPT`'e `sweep_approvals`).
- 113 için ayrı KARAR-GEREK B-07FU-0004.

Onay beklemeden dilim 1'e (104, önce kırmızı) başlıyorum. Plana itiraz gelirse dururum.

### B-07FU-0004 · 2026-10-30 20:35 · → koordinator · KARAR-GEREK
Paket: fix/07-followups   Cevap: K-07F-0001
FOLLOWUP-113'ün dayanağı koda uymuyor (META-03). `POST /projects/{id}/tools/sql-context` yazma ucu değil, bir okuma. mcp-sql'in `get_schema`'sı run'ı başlatan kullanıcı adına (OBO) bu uçla tablo açıklamalarını ve örnek SQL'leri okuyor (`services/mcp_sql_server.py:75`). Hiçbir şey yazmıyor. `test_03a_write_flag.py` `WRITE_EXEMPT` yorumu da "a read that is POST because the question travels in the body" diyor. Run başlatma `require_role("user")` (`api/runs.py:63`).
GOREV'deki gibi developer/admin'e daraltılırsa:
- analyst'in başlattığı SQL asistanı `get_schema`'da 403 alır (PoC SQL asistanı, M3 kabulü);
- PoC'de `developer` atanmadığı için (A3) aracı fiilen yalnız admin kullanabilir.

- **A (önerim):** 113 "dayanak hatalı" diye kapanır, kod değişmez. Bu dilimde iki şey eklenir: `analyst` ve `user` rolündeki üyenin OBO ile 200 aldığını sabitleyen pozitif test, üye olmayana 404. Ayrıca `docs/araclar.md`'ye "okuma ucu, run'ı başlatabilen her üye" satırı yazılır. Etki: güvenlik açığı yok, çünkü doğrudan çağıran kullanıcı aynı veriyi zaten agent'ı koşturarak görür.
- B: doğrudan konsol çağrısı analyst+ (FOLLOWUP-100 ile hizalı), OBO ile gelen (mcp-sql) çağrı run'ı başlatabilen her üye. Etki: tek uca özel rol dalı (ARCH-07). Görünürlük kazancı yok, çünkü veri agent üstünden yine görülür.
- C: GOREV'deki gibi developer/admin. Etki: analyst ve user için SQL asistanı kırılır. Önermiyorum.

Cevap gelene kadar 104 ve 111'de çalışıyorum. 113 dilimi bekliyor.

### B-07FU-0005 · 2026-10-30 20:14 · → koordinator · DURUM
Paket: fix/07-followups   Cevap: K-07F-0002
K-07F-0002 alındı (113 = A; saat damgası artık `date`'ten; B-07FU-0003/0004'teki 20:35 yanlıştı, gerçek ~20:07).
Dilim 1 (104) commit 9efdb26: `follow()` ardışık ikinci boş keepalive turunda run bitmişse saklı satırları verip biter. İlk tur, commit ile xadd arasındaki pencerede canlı girdiye zaman tanır; tokenlar çift gelmez. Birim 3/3 (önce kırmızı: `finished` parametresi yok). Entegrasyon testi test_07f_2 yazıldı, koşulmadı.
Dilim 2 (111) kodu ve testleri yazıldı, bağlanmadı; kırmızı/yeşil entegrasyon ister.
**YIGIN-AÇ 07f** (portlar 18060/13060): test_07f_2 için önce baz koda karşı kırmızı (geçici dosya geri alma), sonra yeşil; ardından 111 ve 113 testleri ve tam `make test-int`. Sıra bekliyorum.

### B-07FU-0006 · 2026-10-30 20:15 · → koordinator · DURUM
Paket: fix/07-followups   Cevap: K-07F-0003
YIGIN-AÇ 07f alındı; yığın açılıyor (18060/13060, 0.0.0-07f, --profile test --profile qdrant, temiz volume).

### B-07FU-0007 · 2026-10-30 20:30 · → koordinator · KARAR-GEREK
Paket: fix/07-followups   Cevap: K-07F-0002
Üç dilim commit'li: 9efdb26 (104), 3038435 (111), fce0b50 (113).
Kırmızı kanıtı:
- 104: baz kodla test_07f_2 akışı 20 s sınırında asılı kaldı (state/evidence/fix-07f-red-104-20261030.log).
- 111: bağlantı yokken test_07f_4/5 kırmızı.
- 113: kod değişmediği için test baştan yeşil (sabitleme testi).

Kapılar:
- lint 0;
- make test llmaas 701 / airgap 701 geçti;
- test-int koşuyor.

Karar: kanca `FFCORE_TEST_HOOKS` ile açılıyor, ama compose backend servisi bu değişkeni konteynere geçirmiyor. Backend env'i açık liste; `FAKE_EMBED: ${FAKE_EMBED:-0}` kalıbı var. Bu haliyle 13b yığınında kanca açılamaz.
- **A (önerim):** bu PR'a `deploy/docker-compose.yml` backend env'ine tek satır `FFCORE_TEST_HOOKS: ${FFCORE_TEST_HOOKS:-0}` (FAKE_EMBED kalıbı). Etki: touch-zone eki; varsayılan kapalı; 13b env dosyasında 1 yapar.
- B: compose satırını 13b PR'ı ekler. Etki: bu PR'ın kancası yığında denenmemiş kalır, 13b'ye iş kayar.
- C: `:?` zorunlu değişken (varsayılansız). Etki: her kurulumun `.env`'ine yeni satır gerekir; bayrak için ağır.
Cevaba göre ya küçük bir commit + PR-HAZIR, ya doğrudan PR-HAZIR.

### B-07FU-0008 · 2026-10-30 20:33 · → koordinator · ACK
Paket: fix/07-followups   Cevap: K-07F-0004
A uygulandı, commit d9d66fb: backend env'ine `FFCORE_TEST_HOOKS: ${FFCORE_TEST_HOOKS:-0}` + `docs/onaylar.md` notu (`.env.test` kapalı, e2e.env'e =1 satırını 13b ekler) + `test_07f_compose.py`.
Not: worker'lar backend'in env bloğunu YAML anchor'ı ile paylaşıyor, satır onlara kendiliğinden gidiyor. Ayrı satır eklemedim; worker bayrağı okumuyor, süpürmeyi kanca backend sürecinde koşuyor. `.env.example` satırı 3038435'te. compose config 0, lint 0. test-int sürüyor; bitince canlı backend kontrolü (bayrak 0 → 404, 1 → 200), sonra PR-HAZIR.

### B-07FU-0009 · 2026-10-30 20:44 · → koordinator · DURUM
Paket: fix/07-followups   Cevap: K-07F-0003
**YIGIN-KAPA 07f**: `down -v` exit 0, konteyner 0, volume 0. Duran imajlar `ffcore/{backend,tools,...}:0.0.0-07f`; silme sende.

### B-07FU-0010 · 2026-10-30 20:44 · → koordinator · PR-HAZIR
Paket: fix/07-followups   Cevap: K-07F-0001
PR: C:\ai_paycore\ffcore\state\pr\07-followups.md · Sınıf [A] · branch fix/07-followups · baz c8650cb · SHA **d9d66fbabf74b3bb22c19a106c6b5489fed26739** (4 commit: 9efdb26 104, 3038435 111, fce0b50 113, d9d66fb compose). Ağaç temiz.
Kanıt (state/evidence/fix-07f-*-20261030.log):
- Kırmızı: 104 baz kodla akış 20 s'de asılı; 111 bağlantı yokken 404.
- `make lint` 0; `make test` llmaas 701 / airgap 701; `make test-int` 526 passed, 4 skipped (main ile aynı sayı).
- d9d66fb için compose testi + repo skeleton 12 passed, `compose config` 0.
- Canlı backend (HEAD imajı): bayrak 0 → 404 (servis ve anonim); 1 → servis 200, anonim 401.

İnceleyiciye notlar:
- `follow()` ikinci boş turda tekrar oynatır. Canlı `done` kaybolmuş run'da cevap metni bir kez daha `token` olarak gelebilir (PR varsayımlar).
- Kanca `include_in_schema=False`, OpenAPI 07 değişmedi.
- 113 kodsuz; sabitleme testi var.
Branch'e başka commit atmıyorum.

### B-07FU-0011 · 2026-10-30 21:19 · → koordinator · HANDOFF
Paket: fix/07-followups   Cevap: K-07F-0008
- **Durum:** MERGED, main a47febe; r1 ONAY d9d66fb. FOLLOWUP-104 ve 111 kapandı, 113 dayanak hatalı diye kapandı (K-07F-0002 A).
- **Kanıt:** state/pr/07-followups.md; loglar state/evidence/fix-07f-*-20261030.log (kırmızı 104/111, lint, iki profil test, test-int, canlı kanca).
- **Commit edilmemiş iş:** yok. **Açık yığın:** yok (07f `down -v`). Duran imajlar `ffcore/*:0.0.0-07f`, silme koordinatörde.
- **Sonraki oturuma devredilenler:**
  - FOLLOWUP-114 (r1 MINOR-1): `test_07f_3_sweep_hook_404_when_flag_off` bayrağı ortamdan varsayıyor. Test, `hooks` fixture'ının tersiyle `ffcore_test_hooks=False` override etmeli.
  - 13b A tarafı: e2e env dosyasına `FFCORE_TEST_HOOKS=1`. Kanca `POST /api/v1/internal/approvals/sweep?now=<ISO+tz>`, servis jetonu; cevap `{"expired":[ids]}` (docs/onaylar.md).
  - Bilinen sınır (PR varsayımı): canlı `done` Redis hatasıyla kaybolursa tekrar oynatma cevap metnini bir kez daha `token` olarak verebilir.
- **Karar/blocker:** yok.
Lease: RETIRED. Bu oturum kanala başka yazmayacak.
