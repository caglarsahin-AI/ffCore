# Arşiv: isci-a · 57

state/kanal/isci-a.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### A-57-0001 · 2026-11-01 05:10 · → koordinator · ACK
Paket: fix/57-alembic-merge   Cevap: K-57-0001
GOREV alındı. Worktree .worktrees/fix/57-alembic-merge @ 148eadd, sınıf [B]. Sıra: önce kırmızı test (tek head, temiz DB `upgrade head`, `downgrade -1` → `upgrade head`, `upgrade heads` geriye uyum), sonra boş merge revizyonu + docs/gelistirme-ortami.md paragrafı. 06b kodu bu merge main'e girene kadar yok; 06b planı paralel.

### A-57-0002 · 2026-11-01 05:25 · → koordinator · YIGIN-AÇ 57
Paket: fix/57-alembic-merge   Cevap: K-57-0001
Proje ffcore-57, FFCORE_VERSION=0.0.0-main (bağımlılık/Dockerfile değişmiyor, derleme yok; worktree kodu tools bind mount), portlar 18150/13150, --env-file .env.test. C: 41 GB boş; açık FF yığını yok (docker ps). Amaç: migration round-trip (yeni test_57_2 + mevcut 03a/06a/07/08 şema testleri) ve make test-int. Durum: kırmızı kanıtlandı (contract 3 failed, state/evidence/57-red-contract-20261101.log); merge revizyonu 57_0001 yazıldı, contract yeşil. Bulgu: merge revizyonu tüm dal etiketlerini miras alıyor (`alembic heads` → `57_0001 (03a, 03c, ...)`); `03a@-1` belgeli geri alma komutunun anlamı değişebilir, yığında ölçeceğim.

### A-57-0003 · 2026-11-01 05:55 · → koordinator · KARAR-GEREK
Paket: fix/57-alembic-merge   Cevap: K-57-0001
Ölçüm (yığın ffcore-57, alembic 1.20.1; log state/evidence/57-*): (1) **Tek merge revizyonu (8 ebeveyn) çalışmıyor:** `upgrade heads` → `KeyError: '03a_0001'`. Neden: 03a_0001, 03b_0001, 06a_0002, 07_0001 başkalarının `depends_on`'u olduğu için `alembic_version`'da satırı yok ("effective head"; main DB'de yalnız 03c_0002, 04a_0001, 05a_0001, 08_0001 satırı var); alembic merge adımı her ebeveynin satırını varlığına bakmadan siler. (2) **İki adımlı merge çalışıyor:** 57_0001 = (03a_0001, 03b_0001, 06a_0002, 07_0001) birleşimi, 57_0002 = (57_0001 + 4 satırlı uç); boş DB'de `upgrade head` ve `upgrade heads` → tek satır 57_0002, `alembic heads` tek satır. (3) **Ama birleştirilmiş dallarda `<etiket>@-1` ve `downgrade -1` artık "Ambiguous walk"** (merge revizyonu tüm dal etiketlerini miras alır; alembic merge noktasından göreli inemez). Açık revizyonla geri alma çalışıyor: `downgrade 06a_0001` yalnız 06a_0002 + bağımlısı 03c_0002 + iki merge'ü kaldırır, diğerleri kalır; `downgrade 57_0001` 2. adımı geri alır; `downgrade 0001` hepsi. Yani GOREV'deki "her paketin dal etiketi çalışmaya devam eder" ve "`downgrade -1`" varsayımları alembic'te tutmuyor.
A (Önerilen): iki adımlı merge; geri alma kuralı "açık revizyon kimliğiyle" (`alembic downgrade <önceki revizyon>`), belgeli `03a@-1`/`03c@-1`/`04a@-1` komutları (docs/api.md, compose yorumu, docs/gelistirme-ortami.md) buna çevrilir; yeni paketler (06b dahil) merge ucunun üstüne zincirlenir, böylece onların `-1`'i çalışır. Eski round-trip testleri (03a/06a/07/08, 04a heads) açık hedeflere çevrilir; bir dalın ilk revizyonunu tek başına kaldırmak (eski `03a@-1`) artık ifade edilemez, test `downgrade 0001` + seçili `upgrade` ile aynı downgrade fonksiyonunu sınar. Etki: [B], migrate `upgrade heads` değişmez, prod DB'de (4 satır) `upgrade head` testle kanıtlanır.
B: merge yok, çok uç kalır, tek-head kuralı 12'ye ertelenir. Bedel: 06b 10. ucu açar; aynı sorun 12'de büyümüş hâliyle gelir.
C: eski revizyonların `depends_on`'unu `down_revision`'a çevirmek. Reddediyorum: kurulu DB'lerin (PayCore) revizyon grafiği değişir, tarih yeniden yazımı.
A ile devam ediyorum (geri alınabilir, kod dalda); B/C dersen dururum.

### A-57-0004 · 2026-11-01 06:40 · → koordinator · ACK
Paket: fix/57-alembic-merge   Cevap: K-57-0002
CEVAP alındı (A). Uygulanacak: (1) RELEASE_AND_ROLLBACK "Geri alma ilkeleri" tek cümle + docs/api.md, compose yorumu, gelistirme-ortami (son üçü yapıldı); (2b) main-şekilli DB'de veri korunumu testi, (2c) `downgrade 0001` açık hedefli round-trip testi; (2d) kapsam daralması PR'da açıkça; (3) migrate servisi yığında: mevcut main-şekilli DB'ye ve `down -v` sonrası temiz DB'ye `0.0.0-57` imajıyla (migration dosyaları imaja gömülü olduğu için tek backend derlemesi, bağımlılık değişmiyor); (4) 06b planına "57_0002 üstüne zincir" cümlesi.

### A-57-0005 · 2026-11-01 07:20 · → koordinator · YIGIN-KAPA 57
Paket: fix/57-alembic-merge   Cevap: K-57-0002
`down -v` exit 0; ffcore-57 konteyner 0, volume 0. Yerelde `ffcore/backend:0.0.0-57` (7 GB) kaldı: temizlik listesine.

### A-57-0006 · 2026-11-01 07:20 · → koordinator · PR-HAZIR
Paket: fix/57-alembic-merge   Cevap: K-57-0001, K-57-0002
Branch fix/57-alembic-merge @ 5dbf11ec1eae40003b108cee09fc768943bdee0b (148eadd üstüne 1 commit, 14 dosya +370/−88). Sınıf [B], push yok, ağaç temiz. PR: state/pr/57-alembic-merge.md.
İçerik: iki boş merge revizyonu (57_0001 satırsız 4 uç, 57_0002 satırlı 4 uç + 57_0001); `scratch_db` fikstürü; 03a/06a/07/08 round-trip ve 04a heads testleri açık hedeflere; docs/api.md, gelistirme-ortami, compose yorumu, RELEASE_AND_ROLLBACK.
K-57-0002 şartları: (2a) boş DB `upgrade head`/`heads` → 57_0002; (2b) main şekilli 4 satırlı DB veri korunarak 57_0002 (test + yığında migrate servisiyle sentinel satır); (2c) `downgrade 57_0001`, `06a_0001`, `0001` açık hedefli round-trip; (2d) kapsam daralması PR'da "Kapsam daralması" bölümü; (3) migrate servisi (`upgrade heads` değişmedi) `0.0.0-57` imajıyla main şekilli ve temiz DB'de exit 0, tek satır 57_0002, idempotent; (4) 06b planı §6'da zincir kuralı.
Kapılar: make lint 0; make test llmaas 737 / airgap 737; make test-int llmaas 677 + 4 opt-in, airgap 678 + 4 opt-in; test_57 son hâl 10 passed. Loglar state/evidence/57-*-20261101.log.
06b: plan state/pr/06b.md hazır (S1-S9 KARAR-GEREK orada); bu merge main'e girince 06b worktree'sini rebase edip PLANNED/KARAR-GEREK mesajını yazarım.
