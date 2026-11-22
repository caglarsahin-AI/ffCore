# Çoklu Agent Protokolü

## Roller

- **Koordinatör:** kuyruk, bağımlılık, dosya sahipliği, merge sırası, dalga kapısı, kullanıcıya karar listesi. Kod yazmaz.
- **İşçi A/B/C:** claim ettiği paketin kod, test ve docs'u (A kritik zincir, B yan paketler, C önyüz; BASLATMA.md 4). Ayrı oturum açma mesajları BASLATMA.md 1-3.
- **İnceleyici:** tek, ayrı ve kalıcı oturum; bütün PR review'larını ve güvenlik turlarını yapar. Kod yazmaz, düzeltmez; bulgu yazar.
- **Güvenlik gözden geçirmesi:** kimlik, secret, SQL, egress, kanal ve kaynak bağlayıcılarına dokunan paketlerde zorunlu (EXECUTION_HANDBOOK 7); inceleyicinin ayrı turu.
- **Test agent'ı (isteğe bağlı):** 13 ve dalga kapısında kara kutu ve olumsuz senaryo testleri ekler; uygulama dosyasına sahibiyle koordineli dokunur.

## Claim ve kilit

`state/WORK_QUEUE.md` tek sahiplik kaynağıdır. Claim alanları: paket, işçi, branch, worktree, touch-zone, başlangıç, durum.

Aynı dosya ya da glob iki aktif claim'de olamaz. Çakışmada:

1. paketler sırayla çalışır, ya da
2. ortak ön koşul küçük ayrı PR'a alınır ve önce merge edilir.

## Touch-zone'lar (varsayılan; claim'de daraltılır)

| Paket | Dokunduğu alan |
|---|---|
| 00 | ffcore: kök, `deploy/`, `Makefile`, iskeletler |
| 00i | **paycoreLLM deposu:** `pyproject.toml`, kök `CLAUDE.md`, `docs/paycore/`, `compose*.yml`, `.env.test`, `src/paycore_llm/api.py` (kimlik), `rag/retrieve.py`, `rag/pipeline.py`, `rag/embed.py` (to_thread, flagged); ffcore'da yalnızca `docs/paycore-entegrasyon.md` |
| 01 | `backend/app/services/litellm_*`, `deploy/litellm/` |
| 02 | `backend/app/core/tracing.py`, Langfuse compose |
| 03a / 03b / 03c | `backend/app/models/{identity,catalog}` / `{audit}`, `core/auth.py`, `core/egress.py` / `{keys,quota,usage,retention,alerts,notifications}`; ilgili router'lar |
| 04a / 04b | `backend/app/knowledge/` |
| 05a / 05b | `backend/app/services/mcp_*`, `services/mcp-sql`, `services/mcp-search` / `backend/app/api/mcp_servers*` |
| 06a / 06b | `backend/app/runtime/`, `backend/app/api/runs*` / `backend/app/api/facade*` |
| 07 | `backend/app/api/approvals*`, runtime interrupt entegrasyonu |
| 08 | `backend/app/guardrails/` |
| 09 | `backend/app/evaluation/` |
| 10a / 10b-poc / 10c / 11 | `frontend/app/(console)/{auth,projects,providers,models}` / `{knowledge,tools,agents,runs,approvals,status}` / `{dashboards,mcp,keys,quotas,alerts,retention,usage}` / `frontend/app/(chat)/`. `(console)/channels` 15'in, `(console)/sources` 16'nın, `(console)/memory` 14'ün |
| 12 | `deploy/offline/`, `docs/kurulum*`, `docs/donanim.md` |
| 13a / 13b | `data/samples/` (sentetik veri, test setleri) / `tests/e2e/`, `Makefile` seed/e2e/eval hedefleri, `docs/demo.md` |
| 14 | `backend/app/memory/`, chat ekranı hafıza paneli |
| 15 | `backend/app/channels/`, widget |
| 16 | `backend/app/sources/`, 04 worker'ına eklenen giriş noktası |

`backend/app/models/__init__.py` ve `alembic/versions/` paylaşımlıdır: her paket kendi dosyasını ekler, başkasınınkini değiştirmez; Alembic branch label'ı paket kodudur.

13b özel paralel claim'i: isci-a `tests/e2e/**` (`tests/e2e/negative/**` hariç), `Makefile`, `docs/demo.md`; test rolü `tests/e2e/negative/**` ve `data/samples/**`. Her rol ayrı branch/worktree kullanır ve aynı dosyaya iki rol yazmaz.

## Branch ve worktree

- Branch: `feat/<paket>-<kısa-slug>` (örn. `feat/03a-identity-catalog`); düzeltme `fix/<paket>-<slug>`.
- Worktree: `.worktrees/<branch>` (gitignore'da) ya da depo dışında.
- Her worktree kendi venv ve `node_modules`'ını kullanabilir. Gerçek `.env` okunmaz veya kopyalanmaz; testler yalnızca secret içermeyen `.env.test`/fixture değerleriyle çalışır.
- Merge sonrası diğer worktree'ler main'i alır (rebase), hedefli testleri tekrarlar.

## Oturumlar arası iletişim (kanal)

Her rol ayrı bir oturumdur (ayrı sohbet). Oturumlar birbirinin bağlamını görmez; birincil ve taşınabilir ortak bellek yalnızca dosyalardır. `SendMessage`/`ListAgents` varsa yalnızca bildirim kolaylığıdır; teslimat garantisi sayılmaz.

**Tek yazar kuralı.** Her paylaşılan dosyanın tek yazarı vardır; böylece iki oturum aynı dosyayı aynı anda değiştirmez:

| Dosya | Yazan | Okuyan |
|---|---|---|
| `state/WORK_QUEUE.md`, `state/BLOCKERS.md`, `KARARLAR.md` | yalnızca koordinatör | herkes |
| `state/kanal/<rol>.md` | yalnızca o rol | herkes |
| `state/pr/<paket>.md` (PR açıklaması) | paketin işçisi | koordinatör, inceleyici |
| `state/reviews/<paket>-r<n>.md` (review sonucu) | yalnızca inceleyici | koordinatör, işçi |
| `state/oturumlar.json` (oturum → rol kaydı), `state/arsiv/**`, `state/kanal/arsiv/**` | yalnızca koordinatör | herkes, guard |

**Hook ile zorlanır** (`.claude/hooks/ffcore_guard.py`, kural `TEK-YAZAR`): Edit/Write/MultiEdit/NotebookEdit bu tabloya göre denetlenir; koordinatör arşiv taşıması için rol kanallarını da düzenleyebilir ("Bağlam bütçesi ve arşiv"). Bash ile yapılan yazım denetlenmez (bilinen sınır); kural metin olarak da geçerlidir. Rol kaynağı: `FFCORE_ROL` (+ `FFCORE_PAKET`) ortamı, yoksa `state/oturumlar.json` (`session_id` ya da masaüstü `local_…` kimliği → `rol`, `paket`, isteğe bağlı `pr`, `lease`, `acildi`; şema docs/takim/ajanlarla-gelistirme.md 9.2). Koordinatör oturum açarken kaydı yazar; kayıt yoksa tek yazar dosyalarına yazım engellenir ve engel mesajı oturumun iki kimliğini verir, oturum bunu kanalına yazıp koordinatöre bildirir.

İşçi ya da inceleyici WORK_QUEUE'da durum değişikliği veya BLOCKERS'ta kayıt (`DECISION-`, `DRIFT-`, `FOLLOWUP-`, `BREAKING-`) gerektiğinde dosyayı kendisi değiştirmez; kendi kanalına mesaj yazar, kaydı koordinatör açar ve numarasını cevaplar. Bu kural CLAUDE.md ve diğer handbook dosyalarındaki "BLOCKERS'a kayıt aç" ifadelerinin paralel düzendeki anlamıdır.

**Mutlak yol.** `state/` her zaman ana çalışma kopyasındaki `C:\ai_paycore\ffcore\state\` yolundan okunur ve yazılır; worktree içindeki `state/` kopyasına dokunulmaz (hook ile zorlanır, her rol için: `STATE-YOL`), feature branch `state/` değişikliği commit etmez. `state/` değişikliklerini main'e koordinatör paket veya dalga kapanışında commit eder; aktif kanal mesajlarının main çalışma ağacını geçici olarak kirletmesi normaldir. paycoreLLM'de çalışan işçi de aynı mutlak yolu kullanır.

**Rol adları ve dosyaları:** `koordinator`, `inceleyici`, `isci-a`, `isci-b`, `isci-c`, `test` (yeni işçi gerekirse `isci-d`; dosyayı koordinatör açar). İşçi rolü bir şerittir, oturum değildir: her paket için yeni oturum açılır, aynı kanal dosyasını kullanır. Kanal başlığındaki `Aktif paket`, `Oturum kimliği` ve `Durum` (`ACTIVE`/`RETIRED`) bir lease'tir; koordinatör eski oturumu `RETIRED` yapmadan aynı role yeni paket vermez.

**Mesaj biçimi (16 Kasım 2026 kararı; yeni mesajlardan itibaren; eski mesajlar değişmez).** Kendi kanal dosyasının sonuna eklenir, eski mesaj değiştirilmez:

```
### <ID> · <YYYY-MM-DD HH:MM> · → <alici> · <TUR>
Paket: <kod> · Cevap: <ID|-> · <türe göre zorunlu alanlar>
<en fazla ~15 satır; ayrıntı dosyadaysa yolunu ver>
```

- **ID:** rol harfi, paket ve sıra: `K-00-0001`, `R-00-0001`, `A-00-0001`, `T-13a-0001`; aynı rolün yeni paket oturumunda çakışmaz.
- **Tür listesi (kapalı, ASCII; açıklama türün yanına değil gövdeye):** `GOREV`, `GOREV-EK`, `ACK`, `SORU`, `CEVAP`, `DURUM`, `KARAR-GEREK`, `KAYIT-TALEBI`, `PLAN-ONAY`, `PR-HAZIR`, `REVIEW-ISTEK`, `REVIEW-SONUC`, `DUZELT`, `ONAY-TEYIT-ISTEK`, `ONAY-TEYIT`, `YIGIN-AC`, `YIGIN-KAPA`, `MERGE-BASLIYOR`, `MERGED`, `HANDOFF-ISTEK`, `HANDOFF`, `RETIRED`.
- **Alıcı listesi (kapalı, ASCII):** `koordinator`, `inceleyici`, `isci-a`, `isci-b`, `isci-c`, `isci-d`, `test`, `sekreter` (rol kurulursa), `tumu`; `kullanici` yalnız koordinatör kanalında. Paket bilgisi alıcıya değil `Paket` alanına yazılır.
- **İkinci satır sabit alanlı** (`·` ile ayrılır):

| Tür | Zorunlu alanlar |
|---|---|
| hepsi | `Paket: <kod>` · `Cevap: <ID|->` (birden çok ID virgül ve boşlukla) |
| `PR-HAZIR`, `REVIEW-ISTEK`, `ONAY-TEYIT-ISTEK`, `ONAY-TEYIT` | `SHA: <40 hex>` |
| `REVIEW-SONUC` | `SHA: <40 hex>` · `Sonuc: ONAY|DEGISIKLIK` · `Bulgu: B<n> M<n> m<n> N<n>` |
| `DURUM` | `Durum: PLANNED|IMPLEMENTED|VERIFIED|BLOCKED|DUYURU` (DUYURU: koordinatörün pakete bağlı olmayan duyurusu) |
| `YIGIN-AC`, `YIGIN-KAPA` | `Yigin: <compose proje adı>` |

- `GOREV`, `GOREV-EK`, `DUZELT`, `REVIEW-ISTEK` ve `KARAR-GEREK` alıcısı `ACK` yazar; aynı ID ikinci kez uygulanmaz. `PR-HAZIR`, `REVIEW-ISTEK` ve `REVIEW-SONUC` tam SHA taşır.
- **`### ` yalnız mesaj başlığıdır:** gövdede alt başlık gerekiyorsa `####` ya da kalın yazı kullanılır; kod bloğu dışındaki her `### ` satırı yeni mesaj sayılır ve biçim kuralına girer.
- Doğrulama (uygulandı, fix/ajan-hooklari-2): hook kuralı `KANAL-BICIM` (`.claude/hooks/ffcore_guard.py`) Edit/Write/MultiEdit ile `state/kanal/<rol>.md`'ye **eklenen** her `### ` başlığını (kod bloğu içi hariç) ve ikinci satırını bu listelere ve alan tablosuna karşı denetler; uymayanı engeller, mesaj hangi alanın bozuk olduğunu söyler. Eski mesajlar, lease satırları ve `state/kanal/arsiv/**` denetlenmez. Listeler guard'da sabittir; `tests/hooks/test_kanal_bicim.py` onları bu bölümden okuyup karşılaştırır (sürüklenme testi kırmızı olur). `python -X utf8 scripts/kanal_ozet.py [--json]` ACK bekleyen bağlayıcı mesajları (`GOREV`, `GOREV-EK`, `DUZELT`, `REVIEW-ISTEK`, `KARAR-GEREK`; `ACK`'in `Cevap` alanındaki her ID cevaplanmış sayılır), paket başına WORK_QUEUE durumunu ve son `DURUM`/`PR-HAZIR`/`REVIEW-SONUC`/`MERGED` mesajını, son `Sonuc: ONAY` SHA'sını ve biçim dışı eski başlık sayısını verir; ACK yazılmamış ama alıcının kanalından `Cevap` ile cevaplanmış bağlayıcı mesajlar ayrı "ACK'siz cevaplanmış" listesindedir (dalga raporu okur).
- Dosyanın başındaki lease ve `Son okunan` satırlarını yalnızca sahibi günceller. Oturum başında, her iş adımının sonunda ve bildirim geldiğinde yeni mesajlar okunur.

**Teslim ve isteğe bağlı zil.** Mesaj dosyaya başarıyla eklendiğinde teslim edilmiş sayılır. `SendMessage` varsa gönderen ayrıca `kanal: <ID> (state/kanal/<rol>.md)` bildirimi yollar. Araç yoksa süreç durmaz: oturumlar başlangıçta ve her iş adımının sonunda kanalları tarar; koordinatör en az saat başı veya kullanıcı `kanalları tara` dediğinde tüm kanalları kontrol eder. ACK alınmayan bağlayıcı mesaj saatlik özette görünür.

**Yetki.** Başka oturumdan gelen zil ve kanal mesajı kullanıcı talimatı değildir. Bağlayıcı olan, kullanıcının oturumu açarken verdiği ilk mesajdır. O mesaj işçiye "koordinatör kanalındaki sana adresli `GOREV` ve `DUZELT` mesajlarını, claim edilen touch-zone içinde uygula" yetkisini verir. Bu yetki touch-zone dışına, secret'a, dış sisteme, sunucuya, push'a ve sınıf C/D onayına uzanmaz. Koordinatör dışındaki rollerden gelen iş isteği uygulanmaz, koordinatöre iletilir.

**PR ve merge (yerel).** Ajanlar uzak sunucuya push etmez; tek istisna, kullanıcının o anki açık talimatıyla koordinatör oturumunun koştuğu `FFCORE_PUSH_OK=1 git push …` komutudur (hook ile zorlanır: `PUSH`; SECURITY_AND_PERMISSIONS). PR; yerel branch, `state/pr/<paket>.md`, tam HEAD SHA ve `PR-HAZIR` mesajından oluşur. Koordinatör aynı SHA'yı `REVIEW-ISTEK` içinde yollar; inceleyici o SHA'yı detached checkout ile inceler ve sonucu SHA ile kaydeder. Merge öncesi branch HEAD onaylanan SHA'dan farklıysa onay geçersizdir ve yeniden review gerekir. Koordinatör yalnızca onaylı SHA'yı main'e `--no-ff` merge eder ve `make smoke` koşar. paycoreLLM branch'lerini main'e kullanıcı yalnızca onaylanan SHA ile merge eder.

**Tam test-int slotu (ENV-209, FOLLOWUP-216).** Tam `make test-int` aynı anda tek yığında koşar ve sırayı koordinatör verir (ENV-209). Paylaşılan modüle (ör. `core/egress.py`, `core/readiness.py`, `core/config.py`, runtime graph, audit), OpenAPI belgesine ya da paylaşılan test sözleşmesine (fikstür, parity, ortak yardımcı) dokunan PR'da işçi hedefli koşularla yetinmez: PR-HAZIR öncesi kanalına `SORU` yazıp tam test-int slotu ister, koşuyu `tee` ile kaydeder ve logu PR-HAZIR'da verir. Gerekçe: 20-21 Kasım'da iki paylaşılan değişiklik hedefli koşularda yeşil, main kapısında kırmızıydı (KARARLAR 'hook-egress-1 main kapısı KIRMIZI', '11-1 main kapısı KIRMIZI').

**İletişim kuralları:**

- İşçiler birbirleriyle doğrudan konuşmaz; koordinatör üzerinden. Bağımlı paketin teslimatı PR'daki "Teslimatlar" bölümüdür.
- Kullanıcı yalnızca koordinatörle konuşur; işçinin kullanıcıya sorusu koordinatörün karar listesine girer. İşçi `DECISION-` kaydında kendi önerisini korur; koordinatör katılmıyorsa işçinin önerisini görünür biçimde aktarır ve neden reddettiğini yazar. Kullanıcıya giden her karar sorusu 2-3 birbirini dışlayan A/B/C seçeneği taşır; koordinatörün önerisi önce “Önerilen” diye işaretlenir ve her seçeneğin etkisi/bedeli belirtilir (META-01).
- Brief'te çelişki gören işçi PR notuna yazar, koordinatör KARARLAR'a işler.

## Gözden geçiren bağımsızlığı

Aynı oturum hem uygulayıp hem son review'ı yapamaz. Review'ı inceleyici oturumu yapar; koordinatör review sonucunu ve test çıktısını okur ama ayrıca diff incelemesi yapmaz. Gözden geçiren diff'i ve test çıktısını bağımsız okur; uygulayanın açıklaması kanıt değildir. Blocker ya da major kapanmadan merge-ready verilmez.

## Handoff

Her işçi oturumu kapanmadan kendi kanalına `HANDOFF` mesajı yazar (şablon `state/HANDOFF.md`): tam sonraki adım, değişen dosyalar, koşan ve kalan testler, kararlar, blocker'lar, commit edilmemiş durum. "Devam edilecek" tek başına geçerli değildir.

## Bağlam bütçesi ve arşiv (16 Kasım 2026)

- Hedef: bir oturumun açılış okuması en fazla 60 KB (CLAUDE.md "Okuma sırası" zorunlu kümesi); geri kalanı gerektiğinde ID ya da dosya yoluyla okunur. Ölçüm: `py -3.12 scripts/context_budget.py` (hedef aşımı çıkış kodu 1; sonuç dalga raporunda bir satır).
- **Kanal arşivi:** paket MERGED olunca o pakete ait mesajlar `state/kanal/arsiv/<rol>-<paket>.md`'ye **taşınır** (koordinatör, HANDOFF sonrası ya da dalga kapanışında; taşıma öncesi/sonrası mesaj ID sayısı eşit olmalı). Aktif kanalda açık paketler ve lease kalır. İçerik ve ID'ler değişmez; arşiv salt okunurdur; bir ID'ye atıf aktif kanalda bulunmazsa arşivde aranır. "Yalnız sona eklenir, eski mesaj değiştirilmez" kuralı sürer: taşıma değiştirme değildir. Hedef: aktif kanal < 50 KB.
- **BLOCKERS:** açık kayıtlar `state/BLOCKERS.md`, kapalılar numaralarıyla `state/arsiv/blockers-kapali.md` (koordinatör taşır; kayıt ≤ 3 satır). Hedef < 30 KB.
- **WORK_QUEUE:** yalnız durum tablosu (paket, durum, işçi, branch, son mesaj ID'si); tarihçe `state/arsiv/work-queue-<dalga>.md`. Hedef < 15 KB.
- **KARARLAR:** başta tek satırlık indeks; yeni madde ≤ 600 karakter (gerekçe ayrıntısı PR notu/rapor yoluyla); eski maddeler kesilmez; tersine dönenler "Geçmiş" bölümüne iner (DOC-18). İndeks < 15 KB.
- Taşımaları yalnız koordinatör yapar (tek yazar); diğer roller arşivi okur, yazmaz.
