# FFCore'u ajanlarla nasıl geliştirdik

> Hedef kitle: FFCore'u devralacak ya da ekibe katılacak geliştiriciler.
> Amaç: ajanlarla nasıl çalıştığımızı, neden böyle çalıştığımızı ve bunu nasıl tekrarlayacağınızı anlatmak.
> Kaynak: depodaki dosyalar ve git geçmişi (16 Kasım 2026'daki durum). Her sayının yanında nereden alındığı yazıyor. "(doğrulanmadı)" işareti, kaynaklarda çelişki olan ya da kaynağa dayandıramadığım iddiaları gösterir.
>
> Terim notu: bu belgede **ajan**, geliştirmede kullanılan Claude Code oturumu demektir (koordinatör, işçi, inceleyici). **agent** ise ürünün kendi agent'ıdır (`agents` tablosu, LangGraph; `handbook/TERMINOLOGY.md`). İkisini karıştırmayın (FELSEFE ARCH-13).

---

## 1. Bir sayfada

**Ne yaptık.** FFCore'un PoC paketlerinin neredeyse tamamını ve PoC sonrası dalganın bir kısmını, bir insan ve birden çok Claude Code oturumuyla yazdık. FFCore kurumsal yapay zekâ platformudur: kapı (LiteLLM), bilgi tabanı, araçlar (MCP), agent çalışma zamanı, onay kuyruğu, guardrail/PII, izleme (Langfuse) ve evaluation. Oturumlar ayrı rollerdeydi: koordinatör, işçiler, inceleyici ve test işçisi.

**Ne kadar sürede.**
- Plan, handbook ve ilk kararlar 27 Ekim 2026 tarihli (`KARARLAR.md`). İlk commit 28 Ekim 2026 00:06 (`git log --reverse`).
- Yoğun geliştirme 28 Ekim ile 5 Kasım arasında, 9 takvim günü sürdü. Bu günlerde günde 47 ile 212 arası commit atıldı (`git log --format=%ad --date=short | uniq -c`).
- Makine 5 Kasım 22:14 ile 9 Kasım arasında kapalıydı (`state/kanal/koordinator.md`). 9-16 Kasım arasında yalnız küçük işler yapıldı.

**Sayılar (16 Kasım 2026).**

| Ölçü | Değer | Kaynak |
|---|---|---|
| Commit | 984 | `git log --oneline \| wc -l` |
| Merge commit'i | 55 | `git log --merges --oneline \| wc -l`. Birkaçı "main'i dala al" türü (ör. `d0b1d76`); paket merge'ü sayısı biraz daha az. |
| PoC tablosundaki iş satırı | 36; bunların 34'ü MERGED/DONE, 09 yarım (09-1 MERGED, 09-2 VERIFIED), 18-kosu-2 VERIFIED | `state/WORK_QUEUE.md` ilk tablo |
| İnceleme turu raporu | 113 dosya, 53 ayrı inceleme konusu | `state/reviews/*-rN.md`. Paket, düzeltme dalı ve dış inceleme dahil. |
| En uzun inceleme | 08-tam-1a 7 tur; 09-1 6 tur + r7 onay teyidi | `state/reviews/` |
| Kanal mesajı | yaklaşık 2.033 başlık | `grep -c '^### ' state/kanal/*.md`: koordinatör 839, işçi A 344, işçi B 310, inceleyici 323, test 121, işçi C 87, işçi D 9 |
| Kanıt dosyası | 820 | `ls state/evidence \| wc -l` |
| BLOCKERS kaydı | 181 numara | `state/BLOCKERS.md` |
| Paket brief'i | 20 dosya | `ls plan` |

**İnsanın rolü: sınırlı human-in-the-loop.** Kodu neredeyse tamamen ajanlar yazdı. İnsanın (Çağlar) yazdığı kod payını depodan ölçemedim, çünkü bütün commit'ler aynı git kullanıcısıyla atılmış **(doğrulanmadı)**.
- 28 Ekim'de teknik kararlar koordinatöre devredildi ("şu ana kadarki kararları sen alabilirdin"; `KARARLAR.md` "Koordinatöre karar yetkisi devri"). O günden sonra kararların tamamına yakınını koordinatör verdi.
- İnsana kalanlar:
  - oturumları açmak,
  - kâğıt üstünde kendisinde kalan sınırlı bir karar listesi (veri sınırı, secret, donmuş sözleşme, kapsam, bütçe; bkz. 2.1),
  - dış ağa çıkan adımlar: model ağırlığı indirme, PayCore sunucusunda komut,
  - ortam sorunları: Docker Desktop'ı yeniden başlatma, disk temizliği, makineyi açık tutma.

**Sekreter.** Koordinatörün yanında ayrıca bir sekreter ajan çalıştı. Ajanlar arasındaki iletişimi (zil ve mesaj aktarımı) ve commit ile push işlemlerini sekreter yürüttü. Böylece pahalı ajanların (koordinatör, işçi, inceleyici) token tüketimi azaldı. Ayrıntı 2.2'de.

---

## 2. Roller ve sorumluluklar

```mermaid
flowchart LR
    U([İnsan · sınırlı HITL]) -- oturum açma, seyrek onay --> K[Koordinatör]
    K -- KARAR-GEREK A/B/C, seyrek --> U
    K <--> S[Sekreter]
    S -- zil, mesaj aktarımı --> I[İşçi A/B/C/D]
    S -- zil, mesaj aktarımı --> R[İnceleyici]
    S -- zil, mesaj aktarımı --> T[Test işçisi]
    I -- PLANNED, PR-HAZIR, KARAR-GEREK --> ST[(state/ kanal dosyaları)]
    R -- REVIEW-SONUC, ONAY-TEYIT --> ST
    T -- DURUM, bulgu --> ST
    K -- GOREV, DUZELT, PLAN-ONAY --> ST
    K -- merge + main kapısı --> M[(main)]
    S -- state/ commit, push --> O[(origin)]
```

Mesajların kalıcı yeri her zaman kanal dosyalarıdır (bkz. 3.1). Sekreter mesajı taşımaz, alıcıyı uyarır ve gerekeni ona iletir.

| Rol | Yapar | Yapmaz | Tek yazarı olduğu dosyalar |
|---|---|---|---|
| **İnsan** | Oturum açma, sınırlı karar listesi (2.1), model ağırlığı indirme, sunucu komutları | Kod yazmaz; işçiyle doğrudan konuşmaz | `FELSEFE.md` |
| **Sekreter** | Zil ve mesaj aktarımı, kanal taraması, `state/` commit'i, push | Karar vermez; kod yazmaz | (depoda kaydı yok; bkz. 2.2) |
| **Koordinatör** | Kuyruk, bağımlılık, touch-zone, brief, karar (A/B/C), SHA doğrulama, merge, main kapısı, dalga kapanışı | Kod yazmaz; diff incelemesi yapmaz (bağımsızlık) | `state/WORK_QUEUE.md`, `state/BLOCKERS.md`, `KARARLAR.md`, `state/kanal/koordinator.md` |
| **İşçi** (A kritik zincir, B yan paketler, C önyüz, D ek) | Claim ettiği paketin testini, kodunu ve docs'unu yazar; kendi kapısını koşar; PR notunu yazar | Touch-zone dışına çıkmaz; kullanıcıya soru sormaz; push yapmaz; `state/` dosyalarını commit etmez | `state/pr/<paket>.md`, kendi kanalı |
| **İnceleyici** | Her PR'ı tam SHA ile, detached checkout'ta bağımsız inceler; kendi yığınında kapıları ve canlı probe'ları koşar; güvenlik turu yapar | Kod düzeltmez; yalnız bulgu yazar | `state/reviews/<paket>-rN.md`, kendi kanalı |
| **Test işçisi** | Sentetik veri (13a), senaryo e2e (18), olumsuz testler, ölçüm koşuları | Uygulama dosyasına sahibiyle koordineli dokunur | `state/kanal/test.md` |

Kaynak: `handbook/MULTI_AGENT_PROTOCOL.md` "Roller" ve "Tek yazar kuralı".

**Neden tek yazar?** İki oturum aynı dosyayı aynı anda değiştiremesin diye. İşçi ya da inceleyici, kuyrukta durum değişikliği ya da BLOCKERS kaydı gerektiğinde dosyaya dokunmaz. Kendi kanalına `DURUM` ya da `KAYIT-TALEBI` yazar; kaydı koordinatör açar.

**Rol bir şerittir, oturum değildir.** Her paket için yeni oturum açılır, ama aynı kanal dosyası kullanılır. Kanal başlığındaki lease'te `Oturum kimliği`, `Aktif paket` ve `Durum: ACTIVE|RETIRED` yazar. Örnek `state/kanal/isci-b.md` başlığı:

```
- Oturum kimliği: ffcore-isci-b-09
- Aktif paket: 09 (feat/09-evaluation)
- Durum: ACTIVE
```

**Örnek: kararın kime ait olduğu.** 29 Ekim'de işçi B, 00i → 01 → 02 → 05a → 07 paketlerini tek oturumda sürdürmüştü. Kullanıcı bunu geri aldı: "Paket başına yeni oturum, istisnasız" (`KARARLAR.md`). Nedeni şu: uzun oturum bağlam taşır, eski paketin varsayımları yenisine sızar. Her paket temiz bir okuma ile başlamalı.

### 2.1 Karar sınırı: koordinatör kararı mı, insan kararı mı?

Ayırıcı kelime **"geri alınamaz ya da dışarıyı etkiler"**dir. Kod içinde kalan ve bir sonraki PR ile düzeltilebilen her karar koordinatörün işidir. Veriyi, secret'ı, dış sistemi, donmuş sözleşmeyi ya da parayı etkileyen karar insanındır. Kaynak: `KARARLAR.md` "Koordinatöre karar yetkisi devri" (28 Ekim 2026).

| Koordinatör kararı (sormadan verir, KARARLAR'a yazar) | İnsan kararı (koordinatör A/B/C ile sorar) |
|---|---|
| Ortam ve araç yerleşimi (ör. ENV-19/20: araçlar Docker'da) | **Veri güvenliği:** veri sınırı, kişi verisi, secret ve `.env` |
| Pinli imaj ve bağımlılık seçimi, C sınıfı dahil (ör. DECISION-23) | Dış sisteme bağlanma, `origin`'e push izni |
| Brief–PLAN çelişkisi ve brief düzeltmesi (DRIFT) | Donmuş sözleşme kırma (`BREAKING-`), D sınıfı değişiklik |
| Örnek veri ve test tasarımı (ör. DECISION-24) | Çekirdek kapsama özellik ekleme ya da çıkarma |
| İşçi izinleri, iş sırası, inceleme bulgularında A/B/C seçimi | Bütçe, donanım, marka, alan adı |
| SHA doğrulama, merge (paycoreLLM merge'ü dahil, 28 Ekim tersine kararı) | M3/M4 model ve eşik kararları (ölçümden sonra) |

```mermaid
flowchart TB
    Q{Karar ne etkiliyor?}
    Q -- "yalnız kod, test, ortam, sıra" --> K[Koordinatör verir<br/>KARARLAR'a gerekçeyle yazar]
    Q -- "veri, secret, dış sistem,<br/>sözleşme, kapsam, para" --> H[İnsana A/B/C sorulur<br/>önerilen işaretli]
    K -. kullanıcı geri çevirebilir .-> H
```

Uygulamada insana giden karar sayısı az oldu. Geri çevrilen koordinatör kararı silinmez, "tersine karar" diye işaretlenir (DOC-18).

### 2.2 Sekreter: iletişimi ucuz ajana devretmek

- **Neden:** Koordinatör, işçi ve inceleyici pahalı modellerle çalışıyordu. Kanal taramak, zil çalmak ve commit atmak bu ajanların bağlamını ve token'ını tüketiyordu.
- **Ne yaptı:** ajanlar arası iletişim (zil, mesajı alıcıya iletme), `state/` dosyalarının commit'i ve push.
- **Ne yapmadı:** karar vermedi. Koordinatörün kayıtlarındaki öneriye göre her `KARAR-GEREK` ve inceleme sonucu yine koordinatöre ya da insana gitmeliydi.
- **Kaynak:**
  - Koordinatör oturumunda bir A/B/C önerisi var: Haiku'yu "koordinatör değil **sekreter** olarak" kullanmak; görevleri "kanal taraması, kapı koşturma, MERGED kaydı, zil".
  - Sekreterin gerçekte yaptığı işler (iletişim, commit, push) kullanıcının anlatımına dayanıyor.
  - Depoda sekreterin kanal dosyası, KARARLAR maddesi ya da BLOCKERS kaydı yok **(doğrulanmadı: hangi model ve hangi tarihten itibaren çalıştığı)**.
- **Protokolle ilişkisi:** `MULTI_AGENT_PROTOCOL.md` "ajanlar uzak sunucuya push etmez" diyor. Uygulamada push'u sekreter yaptı. Bu kural işçi ve inceleyici için geçerli kaldı; sekreter istisnası handbook'a henüz yazılmadı (DRIFT adayı).

---

## 3. İletişim modeli

### 3.1 Oturumlar birbirini görmez

Her rol ayrı bir sohbettir. Ortak bellek yalnız dosyalardır. `SendMessage` (zil) yalnız bir bildirimdir, teslim garantisi sayılmaz. Mesaj dosyaya yazıldığında teslim edilmiş olur (`MULTI_AGENT_PROTOCOL.md` "Teslim ve isteğe bağlı zil").

- `state/kanal/<rol>.md`: o rolün giden mesajları. Yalnız sona eklenir, eski mesaj değiştirilmez.
- Okuma sırası: oturum başında, her iş adımının sonunda ve zil geldiğinde.
- `state/` her zaman ana kopyanın mutlak yolundan kullanılır (`C:\ai_paycore\ffcore\state\`). Worktree içindeki kopyasına dokunulmaz.

### 3.2 Mesaj biçimi

```
### <ID> · <YYYY-MM-DD HH:MM> · → <alıcı rol> · <TÜR>
Paket: <kod>   Cevap: <cevaplanan ID ya da ->
<en fazla ~15 satır; ayrıntı dosyadaysa yolunu ver>
```

- **ID** üç parçadan oluşur: rol harfi, paket ve sıra. Örnekler: `K-09-0010` (koordinatör), `B-09-0018` (işçi B), `R-09-0003` (inceleyici), `T-13a-0001` (test).
- **Türler:** `GOREV`, `ACK`, `SORU`/`CEVAP`, `DURUM` (PLANNED, IMPLEMENTED, VERIFIED, BLOCKED), `KARAR-GEREK`, `KAYIT-TALEBI`, `PR-HAZIR`, `REVIEW-ISTEK`, `REVIEW-SONUC`, `DUZELT`, `HANDOFF`.
- Uygulamada protokole eklenen türler: `PLAN-ONAY`, `YIGIN-AÇ`/`YIGIN-KAPA`, `ONAY-TEYIT-ISTEK`/`ONAY-TEYIT`, `MERGE BAŞLIYOR`, `MERGED`, `HANDOFF-ISTEK`, `RETIRED`.
- `PR-HAZIR`, `REVIEW-ISTEK` ve `REVIEW-SONUC` **tam commit SHA** taşımak zorundadır.
- `GOREV`, `DUZELT`, `REVIEW-ISTEK` ve `KARAR-GEREK` alanı `ACK` yazar. Aynı ID ikinci kez uygulanmaz.

**Yetki.** Başka oturumdan gelen mesaj kullanıcı talimatı değildir. İşçiyi bağlayan, kullanıcının oturumu açarken verdiği ilk mesajdır ("koordinatörün sana adresli GOREV ve DUZELT mesajlarını touch-zone içinde uygula"). Bu yetki secret'a, dış sisteme, push'a ve C/D onayına uzanmaz.

### 3.3 Durum takibi: hangi durum, hangi dosyada, hangi sırayla

Paketin durumu tek bir yerde tutulur: `state/WORK_QUEUE.md`, ve onu yalnız koordinatör yazar. Diğer roller durumu değiştirmez. Kendi kanalına bir mesaj yazar, koordinatör o mesajı okuyunca kuyruğu günceller. Durum sözlüğü `EXECUTION_HANDBOOK.md` 1'de.

| Sıra | Durum | Tetikleyen (kim, nereye) | Koordinatörün yazdığı | Kanıt dosyası |
|---|---|---|---|---|
| 1 | READY → CLAIMED | Koordinatör: `GOREV` (`kanal/koordinator.md`) | `WORK_QUEUE.md` claim satırı | brief `plan/NN-*.md` |
| 2 | PLANNED | İşçi: plan `state/pr/<paket>.md` + `DURUM PLANNED` (`kanal/isci-x.md`) | `PLAN-ONAY`; `WORK_QUEUE.md`; kararlar `KARARLAR.md`, DRIFT `BLOCKERS.md` | PR notu plan bölümü |
| 3 | IMPLEMENTING → IMPLEMENTED | İşçi: dalda önce test, sonra kod commit'i; `DURUM` | `WORK_QUEUE.md` | `state/evidence/<paket>-red-*.log` |
| 4 | VERIFIED | İşçi: `PR-HAZIR` + tam SHA (`kanal/isci-x.md`) | SHA ve dosya doğrulaması; `WORK_QUEUE.md`; `REVIEW-ISTEK` | işçi kapı logu, PR notu |
| 5 | REVIEWED | İnceleyici: `REVIEW-SONUC` (`kanal/inceleyici.md`) | ONAY ise sıradaki adım; DEGISIKLIK ise `DUZELT`, durum 3'e döner | `state/reviews/<paket>-rN.md` |
| 6 | MERGED | Koordinatör: `MERGE BAŞLIYOR`, `--no-ff` merge, main kapısı, `MERGED` | `WORK_QUEUE.md` MERGED | `state/evidence/gate-<paket>-<tarih>.log` |
| 7 | Kapanış | İşçi: `HANDOFF`; kanal başlığında lease `RETIRED` | worktree ve imaj etiketi temizliği | kanal başlığı |
| — | BLOCKED (her an) | İşçi ya da inceleyici: `KAYIT-TALEBI` / `KARAR-GEREK` | `BLOCKERS.md` kaydı (DECISION, ENV, FOLLOWUP…) | kayıt numarası |

Sekreter bu akışta zili çalar ve `state/` değişikliklerini commit eder. Durum yazmaz (bkz. 2.2).

```mermaid
stateDiagram-v2
    [*] --> CLAIMED: GOREV · WORK_QUEUE
    CLAIMED --> PLANNED: işçi pr/paket.md + DURUM · koordinatör PLAN-ONAY
    PLANNED --> IMPLEMENTED: kırmızı test (evidence) → kod commit
    IMPLEMENTED --> VERIFIED: işçi PR-HAZIR (tam SHA) · koordinatör doğrular
    VERIFIED --> REVIEWED: inceleyici reviews/paket-rN.md
    REVIEWED --> IMPLEMENTED: DEGISIKLIK · koordinatör DUZELT
    REVIEWED --> MERGED: ONAY · merge --no-ff · gate log
    MERGED --> [*]: HANDOFF · RETIRED
    CLAIMED --> BLOCKED: KAYIT-TALEBI → BLOCKERS.md
    IMPLEMENTED --> BLOCKED
    BLOCKED --> IMPLEMENTED: kayıt kapandı
```

**Neden böyle?** Durumun tek yazarı olunca iki oturum aynı satırı aynı anda değiştiremez. Her geçişin bir mesaj ID'si ve bir kanıt dosyası olur. Böylece bir paketin neden o durumda olduğu her zaman dosyalardan geri okunabilir.

### 3.4 Gerçek bir PR döngüsü: 09-1 (Evaluation çekirdeği)

Aşağıdaki akış `state/kanal/koordinator.md`, `isci-b.md` ve `inceleyici.md` dosyalarından kısaltılarak alındı. Tarihler 2026.

```mermaid
sequenceDiagram
    participant K as Koordinatör
    participant B as İşçi B
    participant R as İnceleyici
    K->>B: K-09-0001 GOREV (03.11 08:55)
    B->>K: B-09-0010 KARAR-GEREK S-J (A/B/C)
    K->>B: K-09-0006 KARAR: A
    B->>K: B-09-0011 PLANNED (S1-S8)
    K->>B: K-09-0007 PLAN ONAY
    B->>K: B-09-0018 PR-HAZIR d4a2f02 (04.11 22:12)
    K->>R: K-09-0010 REVIEW-ISTEK d4a2f02
    R->>K: R-09-0003 REVIEW-SONUC r1 DEGISIKLIK (MAJOR 4)
    K->>B: K-09-0012 DUZELT
    Note over B,R: r2…r5 aynı döngü (PR-HAZIR → REVIEW-ISTEK → SONUC → DUZELT)
    R->>K: R-09-0026 r6 ONAY 9def741 (+ küçük öneri)
    K->>B: K-09-0037 DUZELT (küçük, merge öncesi)
    K->>R: K-09-0039 ONAY-TEYIT-ISTEK 331e2e9
    R->>K: R-09-0028 ONAY-TEYIT
    K->>K: merge --no-ff → main 1e7a184, main kapısı
    K->>B: K-09-0044 MERGED (05.11 16:07)
```

Adım adım:

1. **GOREV** (K-09-0001, 3 Kasım 08:55). İlk satır "Yeni isci-b oturumu gerekir (ROL=isci-b PAKET=09)". Mesaj şunları içeriyor:
   - branch `feat/09-evaluation`, worktree yolu ve baz commit,
   - brief, ve brief'teki bir düzeltme ("35 soru" → 33, DRIFT-28),
   - zorunlu maddeler ve kabul kriterleri,
   - ilk iş olarak bir ölçüm: pinli Langfuse 3.120.0'da datasets/experiments API'si ve LLM-as-judge OSS'de var mı, `--network none` yığında "ölçerek doğrula".
2. **Ölçüm ve KARAR-GEREK** (B-09-0010, 4 Kasım 19:14). Judge nerede koşacak?
   - "**A (Önerilen):** `llm_judge` bizim motorda … egress'ten geçer"
   - B: Langfuse değerlendiricisi. Bedeli: llmaas'ta maskesiz içerik, yani D sınıfı veri sınırı.
   - C: ikisi birden. Bedeli: iki judge yolu, hangi skorun geçerli olduğu belirsiz.

   Koordinatör bir dakika sonra yanıt verdi (K-09-0006): "S-J: A kabul". Karar `KARARLAR.md`'ye gerekçesiyle yazıldı.
3. **PLANNED** (B-09-0011). Plan `state/pr/09.md` içinde, PR şablonunun 1-9 maddeleriyle. Sekiz alt karar (S1-S8) var, hepsinde öneri A. Örnek: S1 "iki PR (09-1/09-2)". Onay gelene kadar işçi yalnız kırmızı test ve saf kod yazdı. Koordinatör **PLAN ONAY** verdi (K-09-0007), ek koşullar koydu ve bir DRIFT kaydı açtı (164).
4. **PR-HAZIR** (B-09-0018, 22:12). Mesajda tam SHA `d4a2f020…`, 8 commit ve işçinin kapı kanıtı var: `make test` llmaas 1602 / airgap 1602, `test-int` 862 geçti / 21 NOT_RUN (gerekçeli), Alembic gidiş-dönüş, smoke. Kırmızı kanıt logları `state/evidence/09-1-red-*.log` dosyalarında. İnceleyici için güvenlik turu işaretleri de eklenmiş.
5. **REVIEW-ISTEK** (K-09-0010). Aynı SHA, yığın adı ve portlar (`review09` 18300/13300) ve neyin kontrol edileceği: "judge egress'ten geçiyor mu".
6. **r1 REVIEW-SONUC** (R-09-0003): **DEGISIKLIK**, BLOCKER 0, MAJOR 4, MINOR 11, NOTE 8. "Çalışanlar" bölümü de probe kanıtıyla yazılmış: "TC/e-posta/IBAN/telefon → `<<PII_n>>`, model ham değer görmüyor". MAJOR'lardan biri: "`sql_result` reddedilen ya da hiç çalışmamış SQL'i yeniden çalıştırıyor … 07 kapısı atlanıyor".
7. **DUZELT** (K-09-0012). Her MAJOR için ne yapılacağı ve hangi testin yazılacağı tek tek yazılmış: "ayrı commit'ler, önce kırmızı test".
8. **r2-r5.** Aynı döngü dört kez tekrarlandı. Zamanlama hataları dördünde de sürdü (bkz. 7.1).
9. **r6 ONAY** (R-09-0026, SHA `9def741`): MAJOR 0. İnceleyici yine de bir fail-loud riski gördü ve A/B/C önerdi: "B seçilirse ONAY değişmez". Koordinatör A'yı seçti ve merge öncesi küçük bir DUZELT verdi (K-09-0037).
10. **ONAY-TEYIT** (K-09-0039 → R-09-0028). İnceleyiciden yalnız `git diff 9def741..331e2e9` okuması istendi. Sonuç: "ONAY-TEYIT 331e2e9 … Yalnız okuma".
11. **Merge ve main kapısı.** K-09-0041 "MERGE BAŞLIYOR": kapı bitene kadar diğer yığınlar test koşmaz. K-09-0042: merge tamam, main `1e7a184`, kapı koşuyor, log `state/evidence/gate-09-1-20261105.log`. K-09-0044 **MERGED**: "Kapı yeşil, kırmızı yok … Push kullanıcıda."

Toplam süre 3 Kasım 08:55 → 5 Kasım 16:07. GOREV ile PLANNED arasındaki 4 Kasım 19:02 boşluğu yeni oturumun açılmasını beklerken geçti (B-09-0006).

---

## 4. Çalışma kuralları

### 4.1 Felsefe önce

`FELSEFE.md` her kuralın üstündedir. `handbook/FELSEFE_UYGULAMA.md` her ilkeyi FFCore'daki bir kurala bağlar. Bir karar felsefeyle çelişiyorsa ajan durur ve bunu işaret eder; sessizce ihlal etmez. Her PR planında üç soru zorunludur:

1. **ARCH-07:** Kaç senaryoya değer katıyor? Çekirdeğe kalıcı karmaşıklık ekliyor mu?
2. **ARCH-09:** LiteLLM, Langfuse, LangGraph, Postgres, `arq` ya da Next.js bunu zaten sunuyor mu?
3. **ARCH-10 / ARCH-06:** Gizli otomatik davranış ya da sessiz fallback var mı?

*Örnek:* 10b önyüzünde sahte API (msw) ile ekranları önceden yazma planı bırakıldı. Gerekçe: tahminle yazılan sözleşme ikinci bir kod yolu ve kayma üretir (ARCH-07, 80/20; `KARARLAR.md` "10b sıralaması değişti").

### 4.2 Önce kırmızı test, test ve kod ayrı commit

- Önce başarısız test yazılır, sonra en küçük dilim (`EXECUTION_HANDBOOK.md` 4).
- Kırmızı koşunun çıktısı `state/evidence/<paket>-red-*.log` dosyasına alınır.
- İnceleyici commit sırasını denetler. *Örnek* (`state/reviews/09-1-r3.md`): "düzeltmeler bu kez test (a5d91ad) → kod commit'lerinde; … İstisna: 0a02d0f (NER) test ve kod aynı commit'te, kırmızı kanıtı ayrı log (NOTE)."

### 4.3 Touch-zone ve claim

- Kod yazmadan önce `state/WORK_QUEUE.md`'de claim yapılır: paket, işçi, branch, worktree, touch-zone.
- Aynı dosya iki aktif claim'de olamaz. Varsayılan touch-zone tablosu `MULTI_AGENT_PROTOCOL.md`'de.
- Paylaşılan dosyalar (`backend/ffcore/models/__init__.py`, `alembic/versions/`) için kural: her paket kendi dosyasını ekler; Alembic branch label'ı paket kodudur.
- Kapsam dışı bir iş görürsen kodu değiştirme; `FOLLOWUP-` kaydı iste (`CHANGE_CONTROL.md`).

*Örnek:* 09-1'de işçi, 06a'nın koşu başlatma kodunu `services/runs_start`'a çıkarmak zorunda kaldı. Bunu ayrı commit yaptı (7d461a2, 18f9650) ve PR'da "başka paketin üç test dosyası değişti" diye açıkça yazdı (B-09-0018).

### 4.4 Donmuş sözleşmeler ve değişiklik sınıfları

| Sınıf | Ne | Gereken |
|---|---|---|
| **[A]** | Paket içi, dışarıya görünmeyen ekleme ya da düzeltme | PR + test |
| **[B]** | Additive yapılandırma, enum, isteğe bağlı alan, yeni ekran | Docs aynı PR'da + geriye uyumluluk testi |
| **[C]** | Bağımlılık, imaj, compose servisi, egress listesi, güvenlik davranışı | Onay (koordinatöre devredildi, bkz. 4.5) + `deploy/offline` + docs |
| **[D]** | Donmuş sözleşme, profil anlamı, veri sınırı, ürün kapsamı | `KARARLAR.md` + kullanıcı onayı |

Kaynak: `handbook/CHANGE_CONTROL.md`. Sınıf PR başlığında etiketlenir. Emin değilsen bir üst sınıfı seç.

Sözleşmeler (`handbook/CONTRACTS.md`, C1-C14) bir merge ile donar ve o andan sonra yalnız additive değişir. *Örnek:* "**C7 dondu** (29 Ekim 2026, 05a merge 4f285b7) … Bundan sonra yalnız additive; kırma `BREAKING-C7` + kullanıcı onayı" (`KARARLAR.md`).

### 4.5 Kararlar A/B/C ile alınır ve gerekçesiyle yazılır

- Kullanıcı kararı gereken her soru 2-3 birbirini dışlayan seçenekle sorulur. Önerilen seçenek önce gelir ve "Önerilen" diye işaretlenir. Her seçeneğin etkisi ya da bedeli yazılır (META-01).
- İşçi kendi önerisini korur. Koordinatör katılmıyorsa işçinin önerisini görünür bırakır ve neden reddettiğini yazar.
- Her karar `KARARLAR.md`'ye tarih, karar sahibi, mesaj ID'si ve reddedilen seçeneklerin gerekçesiyle yazılır (ARCH-14).
- Karar tersine dönerse eski karar silinmez, "tersine karar" diye işaretlenir (DOC-18). *Örnek:* "Ürün dili: İngilizce varsayılan, Türkçe yerel (28 Ekim 2026, kullanıcı kararı, **tersine karar**…)".
- **Karar yetkisi devri** (28 Ekim). Ortam, araç yerleşimi, pinli imaj ve bağımlılık seçimi (C dahil), brief düzeltmesi, test tasarımı ve iş sırası koordinatörde. Kullanıcıda kalanlar `KARARLAR.md` "Koordinatöre karar yetkisi devri" maddesinde listeli.
- Kullanıcı kendi kararının da sınanmasını istedi (META-03). Zayıf bulunan karar argümanla geri getirilir.

### 4.6 İşçi kullanıcıya soru sormaz

İşçinin bütün soruları koordinatöre gider (`KARAR-GEREK` + zil). Koordinatör ya kendi yetkisinde karar verir ya da soruyu kullanıcıya A/B/C olarak taşır. Teknik belirsizlikte işçi bir varsayım seçer, PR notuna yazar ve durmaz (`CLAUDE.md` "Belirsizlikte").

### 4.7 Fail-loud

Sessiz fallback, kırpma ya da atlama yok; her red kayıtlı ve gerekçelidir (ARCH-06). Bu kural testler için de geçerli: ortama bağlı testler işaretlidir ve koşmazlarsa raporda `NOT_RUN` gerekçesiyle görünür, sessizce atlanmaz (`KARARLAR.md` "Main merge kapısı genişledi").

*Örnek:* 08 tam 1c-b'de int8 nicemlemesinin yüklemesi try/except ile sarılmadı. İnceleyici bunu ayrıca doğruladı: "fp32'ye sessiz düşme yok; hata `/readyz`'e `warmup_failed` olarak çıkıyor" (`state/reviews/08-tam-1c-b-r1.md`).

### 4.8 Kanıt

- **PR notu** (`state/pr/<paket>.md`, şablon `handbook/templates/PR_SABLONU.md`) şunları içerir: plan (1-9), değişen dosyalar, kabul kriteri → test tablosu, komut/ortam/exit/süre tablosu, kontrol listesi, varsayımlar, kalan riskler.
- **Kapı çıktısı tamamen dosyaya alınır:** `tee state/evidence/gate-<paket>-<tarih>.log`. Yalnız son satır tutulmaz (`ENVIRONMENT_AND_COMMANDS.md`; neden için bkz. 7.2).
- **Kırmızı kanıtı ayrı log'dadır:** `*-red-*.log`.
- Kural ile uygulama arasında bir çelişki var: `EXECUTION_HANDBOOK.md` 6 hâlâ "Ayrı kanıt dosyası yok" diyor, uygulamada `state/evidence/` altında 820 dosya var. **(doğrulanmadı: bu sapmanın bilinçli bir kararla kapatılıp kapatılmadığını bulamadım; DRIFT adayı.)**

---

## 5. Kalite kapıları

Bir değişiklik main'e girene kadar beş kapıdan geçer.

```mermaid
flowchart LR
    A[İşçi kapısı<br/>lint, test ×2 profil,<br/>test-int, alembic, smoke] --> B[Koordinatör doğrulaması<br/>SHA, commit/dosya listesi,<br/>state yok, merge-tree]
    B --> C[İnceleyici turu<br/>BLOCKER/MAJOR/MINOR/NOTE<br/>kendi yığını + probe]
    C -- DEGISIKLIK --> D[DUZELT] --> A
    C -- ONAY --> E[merge --no-ff<br/>onaylı SHA]
    E --> F[Main kapısı<br/>tee ile log]
    F --> G[MERGED · HANDOFF · RETIRED]
```

### 5.1 İşçi kapısı

İşçi kendi yığınında şunları koşar: build/config, `make lint`, `make test` iki profilde (`DEPLOY_PROFILE=llmaas` ve `airgap`), `make test-int`, Alembic gidiş-dönüş (`upgrade → downgrade -1 → upgrade`, tek head), seed idempotency ve `make smoke`. Sonuçlar PR notunun komut tablosuna yazılır.

### 5.2 Koordinatör doğrulaması

Koordinatör diff incelemesi yapmaz; inceleme bağımsız kalmalı. Yalnız şunları doğrular: SHA, commit ve dosya sayısı, dalda `state/` değişikliği olmadığı, ve main ile çakışma olmadığı (merge-tree). *Gerçek örnek* (`koordinator.md`, 08-tam-1c-b): "PR-HAZIR r1b alındı; 5e9a688 doğrulandı (1 commit, 7 dosya, state yok, main ve 09-2 ile çakışma yok). … VERIFIED."

### 5.3 İnceleyici turu

- **Girdi:** tam SHA. İnceleyici bu SHA'yı kendi worktree'sinde detached olarak açar.
- **Rapor:** `state/reviews/<paket>-rN.md`. Başlık bölümünde SHA, istek ID'si, yöntem ve karar (**ONAY** / **DEGISIKLIK**) ile BLOCKER/MAJOR/MINOR/NOTE sayıları yer alır.
- **Önceki turun kapanış tablosu:** her bulgu için **KAPANDI / Kısmen → yeni bulgu** ve dosya:satır kanıtı.
- **Bulgu yapısı:** kod yolu → sonuç → ulaşılabilirlik → hangi karara ya da kurala aykırı → öneri (A önerilen, B, C) → istenen test. Koordinatörün kararı aynı başlığın altına eklenir (ör. "Koordinatör kararı (K-09-0022): A").
- **Yöntem:** inceleyici birden çok denetim alt ajanı kullanır ve her bulguyu iki ayrı doğrulayıcıyla çürütmeye çalışır. Raporlar bunu yazıyor: "Altı denetim ajanı … Her bulgu iki ayrı doğrulayıcıyla çürütülmeye çalışıldı" (09-1-r3).
- **Canlı probe:** iddia yığında doğrulanır. Örnekler: judge'a giden metin fake-llm `/_requests` ile okundu; sabit sınırlarda (540 / 541 sn) başlangıç ve bitiş ölçüldü.
- **İmaj bütünlüğü:** inceleyici işçinin imajını kullanırsa önce kaynakla eşleştirir: "imajdaki 168 `ffcore/**.py` dosyasının sha256'sı worktree ile eşleşti … `--no-build --pull never`" (09-1-r3).
- **Ağırlık:** BLOCKER ya da MAJOR açıkken ONAY verilmez. MINOR ve NOTE'lar ya merge öncesi küçük bir DUZELT'e ya da `FOLLOWUP-` kaydına gider (ör. FOLLOWUP-176: "09-1 incelemelerinden 09-2'ye kalan kalemler").
- **Yığınlı inceleme zorunluluğu:** önyüz, uçtan uca ve güvenlik iddiası taşıyan PR'larda inceleyici yığın açar, e2e'yi kendisi koşar ve en az bir kendi negatif testini yazar (`KARARLAR.md` "Review kuralı", K-INC-0008).

### 5.4 Merge

Yalnız onaylanan SHA, `--no-ff` ile merge edilir. Dal HEAD'i onaylanan SHA'dan farklıysa onay geçersizdir. Merge öncesi küçük bir düzeltme yapıldıysa inceleyiciden yalnız o delta için **ONAY-TEYIT** istenir (09-1 r7). Merge mesajı paket ve SHA taşır, ör. `Merge feat/09-evaluation: 09 Evaluation PR 09-1 - … (331e2e9)`.

### 5.5 Main kapısı

Gerçek adımlar `state/evidence/gate-09-1-20261105.log` dosyasından:

| Saat | Adım | Sonuç |
|---|---|---|
| 15:46 | build backend frontend tools, `compose config`, `up` | 0 |
| 15:47 | lint | "All checks passed!" |
| 15:47 | `alembic heads` | tek head |
| 15:47 | `make test` llmaas | 1739 passed |
| 15:50 | `make test` airgap | 1739 passed |
| 15:53 | test-samples | geçti |
| 15:53 | `test-int` | 903 passed, 13 skipped |
| 16:05 | smoke | backend, litellm, langfuse, mcp-search, mcp-sql 200; ollama profili kapalı |
| 16:05 | frontend lint/typecheck/`check:api` (`--network none`) | geçti |
| 16:05 | `down -v` | kapı yığını kaldırıldı |

Toplam yaklaşık 20 dakika. Bir kapı adımı 137 (OOM) ile düşerse o adım tek başına yeniden koşulur; MERGED ancak bu tekrar yeşilse yazılır (`KARARLAR.md` "Üç yığın sınırı bellek sınırıdır").

### 5.6 MERGED, HANDOFF, RETIRED

- Koordinatör kuyruğu MERGED yapar ve `→ tumu` MERGED mesajı yazar. Bu mesajda sıradaki işler ve diğer dalların main'i nasıl alacağı da yer alır.
- İşçi kapanırken `HANDOFF` yazar. İçeriği: tam sonraki adım, değişen dosyalar, koşan ve kalan testler, kararlar, blocker'lar, commit edilmemiş durum. "Devam edilecek" tek başına geçerli değildir.
- Lease `RETIRED` olur. *Örnek* A-00-0021: "Durum: RETIRED · Tam sonraki adım: yeni isci-a oturumu K-03b-0001 GOREV'ini alır…". Ardından yeni oturuma gereken pratik notlar (Docker'da araç komutları, `MSYS_NO_PATHCONV=1`, CRLF tuzağı) geliyor.
- İşçi ve inceleyici uzak sunucuya push etmez (`MULTI_AGENT_PROTOCOL.md` "PR ve merge (yerel)"). `state/` commit'ini ve push'u sekreter yaptı (bkz. 2.2). K-09-0044'teki "Push kullanıcıda" ifadesi push kararının insanda olduğunu anlatıyor.

---

## 6. Ortam ve güvenlik kuralları

### 6.1 Her şey Docker'da

- Host'ta yalnız Python 3.12 (ajan betikleri), Docker Desktop ve git var. Node, npm ve `make` konteynerde koşar (`tools` servisi; `KARARLAR.md` "Geliştirme araçları Docker'da", 28 Ekim, kullanıcı kararı).
- Her yığının kendi compose proje adı ve port aralığı vardır:

| Yığın | Sahibi | Örnek port | Kaynak |
|---|---|---|---|
| `ffmain` | koordinatör (main kapısı) | 18000 / 13000 | K-09-0042 |
| `ffcore-<paket>` | işçi | ör. 18160 / 13160 (19) | koordinator.md |
| `review<paket>` | inceleyici | ör. 18300 / 13300 (`review09`) | R-09-0002 |

- Paralel worktree'lerde imaj etiketi paket başınadır (`FFCORE_VERSION=0.0.0-<paket>`). Aksi hâlde bir oturumun derlemesi diğerinin imajını ezer. Bu, 04a'nın torch'lu imajı 01'in derlemesiyle değiştiğinde öğrenildi (`KARARLAR.md`).

### 6.2 YIGIN-AÇ / YIGIN-KAPA ve bellek sınırı

- Konteyner açan her koşudan önce kanala `YIGIN-AÇ <proje>` yazılır. Bitince `down -v` + `YIGIN-KAPA`. Koordinatör sıra verir.
- Docker Desktop VM'i 12,5 GB. Aynı anda **en fazla üç yığın** açık olabilir. Main kapısı koşarken diğer yığınlar açık kalabilir ama test koşmaz (`ENVIRONMENT_AND_COMMANDS.md`, `KARARLAR.md` 5 Kasım).
- Kural zamanla değişti: 30 Ekim kararı "aynı anda en çok iki Docker yığını" diyor, 5 Kasım kararı ve handbook "üç" diyor. 30 Ekim maddesi `KARARLAR.md`'de "tersine karar" diye işaretlenmemiş. **(doğrulanmadı: geçerli sınır uygulamada üç; eski madde DRIFT adayı.)**
- Her yığın açışından önce `YIGIN-AÇ` yazılır; `tools --no-deps` bile volume açar.

### 6.3 Dış bağlantı yok

- Yığınlar `up -d --wait --no-build --pull never` ile ve işçinin doğruladığı etiketli imajla açılır.
- Çıplak `docker compose build` ve `up --build` kullanılmaz. BuildKit, katmanlar önbellekte olsa bile base imaj metadata'sı için docker.io/ghcr.io'ya bağlanır (PROSES-175; bkz. 7.6).
- Model süreçleri varsayılan olarak offline çalışır (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`). Ağırlık eksikse süreç model adı ve yoluyla kodlu hata verir; indirme yapmaz.
- Gerçek model koşusundan önce indirme yolu kontrol edilir ve `--network none` kanıtı alınır.

### 6.4 Model ağırlıkları kullanıcı adımıdır

Ağırlıkları `model_cache` volume'una koyan tek yol `make models`'tır. Dışarı bağlandığı için **yalnız kullanıcı** koşturur, işçi ve inceleyici koşturmaz (`KARARLAR.md` "Model ağırlıkları ve dış ağ", K-04a-0020). *Örnek:* ENV-163. NER aday ağırlıkları kullanıcıyı bekledi; sonra işçi `--network none` ile `models-check` kanıtını aldı.

### 6.5 Secret ve veri sınırı

- Ajan `.env` okumaz, yazmaz ve kopyalamaz. Testler yalnız secret içermeyen `.env.test` ve fixture değerleriyle koşar (`SECURITY_AND_PERMISSIONS.md`).
- Hasta ve kişi düzeyi kurum verisi platforma girmez. Geliştirmede Anthropic API'ye yalnız sentetik veri gider. Sentetik kişi adları yalnız `data/samples/pii/` ve `memory/` setlerinde, sabit uydurma bir havuzdan gelir (DECISION-24).
- **PayCore LLM** (`C:\ai_paycore\paycoreLLM`) canlı test yeri ve tüketicidir:
  - `.env`, `data/**`, `eval/results/**` okunmaz.
  - `eval/scenario*/questions.jsonl` ve `experts/*.yaml` okunabilir ama kopyalanmaz.
  - Kod kopyalanmaz; ya uzantıda kalır ya da C14 ile terfi eder.
  - Sunucuya ajan bağlanmaz. Komutları kullanıcı çalıştırır, çıktıyı PR'a yapıştırır.
- Not: `ENVIRONMENT_AND_COMMANDS.md` "PayCore referans deposu" bölümü hâlâ "`eval/`, `data/`, `experts/` okunmaz" diyor. Bu DRIFT-16 olarak açık ve CLAUDE.md, PLAN 5 ile SECURITY_AND_PERMISSIONS'ın dosya düzeyi kuralı geçerli.

### 6.6 Temizlik sınırı

Koordinatör yalnız kendi açtığı yığını ve kendi worktree'sini kaldırır. Şunları kullanıcıya bırakır: `--force`, imaj/volume silme, `prune` ve başka oturumların kopyaları (`KARARLAR.md` "Temizlik sınırı"). Uygulamada toplu `docker stop` da kullanılmadı; her oturum kendi konteynerini adıyla durdurdu. **(doğrulanmadı: bu kural depoda yazılı değil, koordinatörün çalışma notlarından alındı.)**

---

## 7. Dersler ve tuzaklar

### 7.1 Zamanlama sınıfı dört turda kapandı: "tek sabit" dersi

09-1'de sınav ilerleticisinin süre bütçesi her turda yeni bir kenar hatası üretti:

| Tur | Bulgu | Kaynak |
|---|---|---|
| r2 | MAJOR-r2-2: sabit 600 sn tick zaman aşımı hata sayılıyor; airgap'te judge sınavları `failed` | `09-1-r2.md` |
| r3 | MAJOR-r3-1: bütçeye sığmayan madde sonsuza dek yeniden deneniyor, sayaç her tick sıfırlanıyor | `09-1-r3.md` |
| r4 | MAJOR-r4-1: ortak son süre tükenince sonraki sınavın ilk maddesi 0 sn ile kesiliyor ve yanlışlıkla `judge_out_of_time` sayılıyor | `09-1-r4.md` |
| r5 | MAJOR-r5-1: 570 ve 285×2 planı ne hata ne başlangıç alıyor, sonsuz `running` geri gelmiş | `KARARLAR.md` "09-1 r5 kararı" |
| r6 | ONAY: "`TICK_PLAN_S=540` tek kaynak üç yerde" | `09-1-r6.md` |

Kök neden: aynı sınır üç yerde farklı sayılarla (570, 600, config üst sınırı) ifade ediliyordu. Çözüm: tek türetilmiş sabit `TICK_PLAN_S = TICK_TIMEOUT_S − TICK_MARGIN_S − TICK_OVERHEAD_S` (540). Planı ≤ 540 olan iş başlar, > 540 olan kodlu biter, arası yoktur. Bu da sınırda (`TICK_PLAN_S` ve `TICK_PLAN_S − ε`) testlerle sabitlendi.

**Ders:**
- Bir süre ya da sınır birden fazla yerde karşılaştırılıyorsa tek bir sabitten türetin.
- Sınırın iki yanını test edin.
- Bir tasarım sınıfı iki turda kapanmıyorsa yamayı bırakın ve değişmezi (invariant) yazın.

### 7.2 Kapı çıktısının yalnız son satırını tutmanın bedeli

05a r1 düzeltmesinde işçi şunu bildirdi: "llmaas'ta ilk `make test` koşusu `Error 1` ile bitti. Düşen test kaydedilmedi; ardından üç koşu 556/556 geçti. Neden doğrulanmadı" (B-05a-0012). Koordinatörün cevabı: "bundan sonra her kapı koşusunun çıktısını dosyaya al (`tee`), kaydedilmemiş kırmızı kalmasın" (K-05a-0011).

**Ders:** Aralıklı bir kırmızı, tekrar koşunca kaybolur. Kanıt yalnız dosyadadır. Kural artık `ENVIRONMENT_AND_COMMANDS.md`'de.

### 7.3 `simple` NER birleştirmesiyle parçalı maskeleme

08 tam 1c-b ölçümünde `aggregation_strategy="simple"`, akdeniz27 modelinde kelimeyi alt parçalara bölüyordu ve adı **parçalı maskeliyordu**. PERSON precision 0,56'ydı ve sızıntı riski vardı. `first` ile recall 1,00 / precision 1,00 oldu (`KARARLAR.md` "08 tam 1c-b"). İnceleyici bir şeyi daha yakaladı: gerçek model testi `simple` ile hiç kırmızı görülmemişti, kırmızı kanıt yalnız keşif çıktısındaydı (`08-tam-1c-b-r1.md` MINOR-1).

**Ders:**
- Maskeleme testi "bir örtüşme var" değil, "her harf kapsandı" diye assert etmeli.
- Kırmızı kanıt gerçek modelle alınmalı.

### 7.4 Dizüstünde gecikme ölçümü temsilî değil

NER gecikme kabulü (boşta P95 < 300 ms) geliştirme dizüstünde ölçüldü. int8 sonuçları 297-840 ms arasında, yaklaşık 3 kat oynadı (ENV-177, `state/evidence/08t1c-b-idle-p95.log`). İnceleyicinin aynı makinedeki bilgi amaçlı koşusu 191 ms çıktı. Karar: kabul **hedef donanımda** kullanıcı komutuyla verilir (`make test-ner-latency`). Dizüstü ölçümü kabul sayılmaz.

**Ders:**
- NFR ölçümünü hedef donanıma bağlayın.
- Birim testlerinde mutlak süre sınırı koymayın; algoritmik sınırı oranla test edin (`KARARLAR.md` "Birim testinde mutlak süre sınırı yok", K-SEN-0015).

### 7.5 Makine uykusu ve çevrimdışı oturumlar

- Makine 5 Kasım 22:14 ile 9 Kasım arasında kapalıydı. Docker açılınca işçinin eski yığını kendiliğinden geri kalktı (17 konteyner).
- Eski inceleyici oturumu 5 Kasım'dan beri çevrimdışıydı. Kullanıcı kararıyla aynı kanalda yeni bir inceleyici oturumu açıldı; numaralar R-09-0038'den devam etti (`koordinator.md`).
- Bir test düşüşü de "yük/uyku kaynaklı" diye ayrıştırılıp tek başına tekrar koşuyla kabul edildi.
- Docker Desktop motoru üç gün içinde iki kez yeni konteyner başlatamaz hâle geldi (ENV-171).

**Ders:**
- Oturumlar kalıcı değildir; durumun tamamı dosyada olmalı. HANDOFF ve kanal bu yüzden var.
- Sessiz oturumu koordinatör zil ile uyandırır.
- Uzun koşular için makine uyumamalıdır.

### 7.6 `docker compose build` dışarı bağlanıyor

İnceleyici yalın yığın için ayrı bir `docker compose build backend` koştu. BuildKit, katmanlar önbellekte olduğu hâlde base imaj metadata'sı için iki kez docker.io/ghcr.io'ya bağlandı. İnceleyici bunu kendisi bildirdi ve PROSES-175 kaydı açıldı.

**Ders:** "Önbellekten derliyorum" demek dış bağlantı olmadığını kanıtlamaz. Kural: işçinin derlediği imajla `--no-build --pull never`; gerçekten derlenecekse `build --pull=false`. Not: main kapısı logu da bir "build" adımıyla başlıyor; kapı betiği bu adımı `docker compose build --pull=false backend frontend tools` ile koşar (koordinatörün `gate09.sh` betiği; logda bayraklar yazmaz).

### 7.7 Kısa ek dersler

- **LiteLLM `/config/update`, master key'i ve DB şifresini düz metin yazıyor.** Bu ölçümle bulundu; uç hiç çağrılmıyor (`KARARLAR.md` "01 fallback istek düzeyinde").
- **"Brief'teki varsayımı ölç".** 09 GOREV'i Langfuse yeteneğini ölçtürdü. Sonuç: judge OSS'de var ama API'si yok. Brief varsayımı düzeltildi (K-09-0006).
- **Koordinatör de hata yapar.** "ffcore kararı paycoreLLM'e uygulanmadan 00i host venv ile doğrula[ndı]" (`KARARLAR.md` "paycoreLLM'de de araçlar Docker'da"). Hata kayda geçti, kural genişletildi.
- **Windows tuzakları:** Python ile dosya yazarken `write_bytes(text.encode())` kullanın; Windows'ta `write_text` CRLF yazar. Git Bash'te `-w /work/...` Windows yoluna çevrilir; `MSYS_NO_PATHCONV=1` gerekir (A-00-0021 HANDOFF).

---

## 8. Bunu nasıl tekrarlarsınız

### 8.1 FFCore'da yeni bir paket: adım adım

1. **Hazırlık (koordinatör).**
   - Paketin doğrudan bağımlılıkları MERGED mi? (`EXECUTION_HANDBOOK.md` 2)
   - Brief'i (`plan/NN-*.md`) ve bağımlı paketlerin "Teslimatlar" bölümünü oku.
   - Touch-zone çakışmasına bak. Kuyrukta claim aç.
   - Kanalda önceki oturum `RETIRED` mı? Değilse önce HANDOFF iste.
2. **GOREV (koordinatör → işçi).** Mesajın içeriği:
   - "Yeni isci-X oturumu gerekir (ROL=… PAKET=…)",
   - branch, worktree, baz commit,
   - brief ve düzeltmeleri, bağımlı teslimatlar,
   - zorunlu maddeler, kabul kriterleri, sınıf,
   - varsa ilk ölçüm işi.
3. **Oturum açma (insan).** Yeni oturumu açın ve ilk mesajda yetkiyi verin. Model Opus 5.5 olmalı; açılışta doğrulayın. İşçi önce `CLAUDE.md` okuma sırasını izler, sonra kanalını tarar.
4. **Ölçüm ve KARAR-GEREK (işçi).** Brief'teki varsayımlar yığında ölçülür. Kullanıcı ya da koordinatör kararı gereken her nokta A/B/C ile, öneri işaretli olarak yazılır.
5. **PLANNED (işçi).** `state/pr/<paket>.md` içinde şablonun 1-9 maddeleri. Felsefe üçlüsü zorunlu. Onay gelene kadar yalnız kırmızı test ve saf kod yazılır.
6. **PLAN-ONAY (koordinatör).** Kararlar `KARARLAR.md`'ye, DRIFT ve FOLLOWUP kayıtları `BLOCKERS.md`'ye yazılır.
7. **Kodlama (işçi).**
   - Kırmızı test → `*-red-*.log` → kod. Test ve kod ayrı commit.
   - Kapsam dışı iş için `FOLLOWUP` iste.
   - Yığın gerekiyorsa `YIGIN-AÇ` yaz.
8. **İşçi kapısı + PR-HAZIR.** Kapıyı `tee` ile dosyaya al. Mesajda tam SHA, kanıt özeti, NOT_RUN gerekçeleri ve inceleyici için işaretler olsun. Yığını kapat (`YIGIN-KAPA`). Dala başka commit atma.
9. **Doğrulama + REVIEW-ISTEK (koordinatör).** SHA, dosya listesi, `state/` yok, merge-tree. Ardından aynı SHA inceleyiciye gider; istekte yığın adı, portlar ve kontrol listesi bulunur.
10. **İnceleme turları.** DEGISIKLIK ise koordinatör DUZELT yazar ve önerilerden birini seçer. Döngü ONAY'a kadar sürer. Merge öncesi küçük bir delta varsa ONAY-TEYIT istenir.
11. **Merge + main kapısı (koordinatör).**
    - `→ tumu MERGE BAŞLIYOR` yaz; diğer yığınlar test koşmaz.
    - Onaylı SHA'yı `--no-ff` ile merge et.
    - Kapıyı `gate-<paket>-<tarih>.log` dosyasına alarak koş.
    - Yeşilse `MERGED` yaz.
    - Kanal dosyalarını merge'den önce commit edin. Çakışan bir merge iptal edilirse commit edilmemiş kanal satırları silinir.
12. **Kapanış.** İşçi HANDOFF yazar, lease RETIRED olur, worktree ve paket imaj etiketi temizlenir. Sekreter `state/` dosyalarını commit eder ve push'u yapar.

### 8.2 Yeni bir projede kurulum listesi

**Kurallar ve giriş dosyaları**
- [ ] `FELSEFE.md`: meta-ilkeler (A/B/C sorma, sycophancy yok, doğrula), mimari ilkeler (fail-loud, yeniden inşa etme, açık kontrol, donmuş sözleşme), dokümantasyon disiplini.
- [ ] `CLAUDE.md`: okuma sırası, bağlayıcı kısa kurallar, komutlar.
- [ ] `PLAN.md`: amaç, kısıtlar, profiller, mimari, ortak kurallar, paket tablosu (bağımlılık + süre), kilometre taşları, sürüm geçmişi.
- [ ] `KARARLAR.md`: bölümler (ürün, veri, mimari, geliştirme düzeni, **reddedilenler**, **ertelenenler**). Her madde tarihli ve gerekçeli.

**Handbook** (`handbook/`)
- [ ] `INDEX.md`, `FELSEFE_UYGULAMA.md` (ilke → somut kural tablosu + PR'daki üç soru)
- [ ] `EXECUTION_HANDBOOK.md` (yaşam döngüsü, DoR, plan sözleşmesi, doğrulama katmanları, kanıt, review başlıkları, dalga kapısı)
- [ ] `MULTI_AGENT_PROTOCOL.md` (roller, claim, touch-zone, kanal biçimi, tek yazar, yetki, yerel PR/merge, handoff)
- [ ] `CHANGE_CONTROL.md` (A-D, deprecation), `CONTRACTS.md` (donma anı + additive kuralı)
- [ ] `SECURITY_AND_PERMISSIONS.md` (secret, veri sınırı, ajan izin matrisi), `ENVIRONMENT_AND_COMMANDS.md` (kapı komutları, paralel yığın kuralları)
- [ ] `TERMINOLOGY.md`, `TEST_STRATEGY.md`, `templates/PR_SABLONU.md`

**Canlı durum** (`state/`)
- [ ] `WORK_QUEUE.md` (durum sözlüğü + paket tablosu + kapılar), `BLOCKERS.md` (önekler: DECISION, DRIFT, FOLLOWUP, DEBT, ENV, BREAKING, PROSES), `HANDOFF.md` şablonu
- [ ] `kanal/<rol>.md`: başlıkta lease, altında `## Mesajlar`
- [ ] `pr/`, `reviews/`, `evidence/` dizinleri

**Ortam**
- [ ] Araçlar konteynerde (`tools` servisi), host'ta en az kurulum
- [ ] Yığın başına compose proje adı ve port aralığı; paket başına imaj etiketi
- [ ] Bellek bütçesine göre eşzamanlı yığın sınırı (bizde 12,5 GB VM ile üç)
- [ ] `--pull never`, offline model süreçleri, ağırlık indirme yalnız insan adımı

**Oturum düzeni**
- [ ] 1 koordinatör + rol başına işçi şeridi + 1 kalıcı inceleyici (+ gerekirse test işçisi)
- [ ] İletişim, zil ve commit/push için ucuz modelli bir sekreter ajan; karar yetkisi yok
- [ ] Karar sınırı yazılı: koordinatörün sormadan verdiği kararlar ve insanda kalanlar (veri güvenliği, secret, dış sistem, sözleşme, kapsam, bütçe)
- [ ] Paket başına yeni oturum; ilk mesajda yetki sınırı
- [ ] Koordinatör karar yetkisi listesi ve kullanıcıda kalanlar, açıkça yazılı
- [ ] Koordinatör kanalları belirli aralıklarla tarar ve sessiz oturumu zil ile uyandırır

---

## 9. Sözlük ve dosya haritası

### 9.1 Sözlük

| Terim | Anlam |
|---|---|
| ajan | Geliştirmede bir Claude Code oturumu (koordinatör, işçi, inceleyici, test). Ürünün **agent**'ıyla karıştırmayın. |
| agent | Ürün kavramı: tanımı JSON, LangGraph ile çalışan yürütücü (`agents`, `agent_versions`) |
| paket | `plan/NN-*.md` brief'i olan iş birimi (ör. 09, 08-tam-1c-b); bazıları dilimlere bölünür (09-1, 09-2) |
| dalga | Bağımlılığa göre gruplanmış paketler; kapısı Alembic merge ve tutarlılık denetimi |
| brief | Paketin kapsam, kabul kriteri ve teslimat belgesi (`plan/`) |
| claim | Paketin kuyrukta bir işçiye bağlanması |
| touch-zone | Claim'in dokunabileceği dosya ve glob listesi |
| lease | Kanal başlığındaki oturum kimliği, aktif paket ve ACTIVE/RETIRED durumu |
| kanal | `state/kanal/<rol>.md`; yalnız sona eklenen mesaj dosyası |
| zil | `SendMessage` bildirimi; teslim garantisi değil |
| PR (yerel) | Yerel branch + `state/pr/<paket>.md` + tam SHA + `PR-HAZIR` mesajı |
| kapı | Belirli komutların sırayla ve kanıtlı koşulması (işçi kapısı, main kapısı, dalga kapısı) |
| tur (rN) | Bir inceleme dönüşü; rapor `state/reviews/<paket>-rN.md` |
| BLOCKER / MAJOR / MINOR / NOTE | İnceleme bulgu ağırlıkları; BLOCKER ve MAJOR açıkken ONAY verilmez |
| probe | İnceleyicinin bir iddiayı canlı yığında doğrulayan küçük betiği |
| NOT_RUN | Koşulamayan test; gerekçesi yazılır, sessiz atlama değildir |
| YIGIN-AÇ / YIGIN-KAPA | Docker yığını açma ve kapatma bildirimi |
| [A]-[D] | Değişiklik sınıfı (`CHANGE_CONTROL.md`) |
| C1-C14 | Donmuş sözleşmeler (`CONTRACTS.md`) |
| llmaas / airgap | Dağıtım profilleri; fark yapılandırma değeridir, `if profile` değil |
| fail-loud | Beklenmeyen durumda açık hata; sessiz fallback yok (ARCH-06) |

### 9.2 Dosya haritası

```
FELSEFE.md                  geliştirme felsefesi (her kuralın üstünde)
CLAUDE.md                   giriş, okuma sırası, kısa kurallar
PLAN.md                     amaç, mimari, ortak kurallar (5), paketler (7)
KARARLAR.md                 kararlar defteri (gerekçeli, tarihli, reddedilenler)
BASLATMA.md                 oturum açma mesajları, dalga takvimi
plan/NN-*.md                paket brief'leri
handbook/
  INDEX.md                  dizin
  FELSEFE_UYGULAMA.md       ilke → FFCore kuralı; PR'daki üç soru
  EXECUTION_HANDBOOK.md     yaşam döngüsü, kanıt, review
  MULTI_AGENT_PROTOCOL.md   roller, kanal, tek yazar, yerel PR
  CHANGE_CONTROL.md         [A]-[D]
  CONTRACTS.md              donmuş sözleşmeler
  SECURITY_AND_PERMISSIONS.md
  ENVIRONMENT_AND_COMMANDS.md
  TERMINOLOGY.md, TEST_STRATEGY.md, CODE_MAP.md, RELEASE_AND_ROLLBACK.md
  templates/PR_SABLONU.md
state/                      (yalnız ana kopyanın mutlak yolundan)
  WORK_QUEUE.md             kuyruk (koordinatör yazar)
  BLOCKERS.md               DECISION/DRIFT/FOLLOWUP/ENV/PROSES… (koordinatör yazar)
  HANDOFF.md                şablon
  kanal/<rol>.md            oturumlar arası mesajlar (yalnız o rol yazar)
  pr/<paket>.md             PR notu (işçi yazar)
  reviews/<paket>-rN.md     inceleme raporu (inceleyici yazar)
  evidence/*.log            kapı, kırmızı ve ölçüm çıktıları (tee)
docs/                       ürün belgeleri (İngilizce)
docs/takim/                 ekip içi süreç belgeleri (bu dosya)
```
