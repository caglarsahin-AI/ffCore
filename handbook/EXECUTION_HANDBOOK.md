# Yürütme El Kitabı

Bir iş paketinin brief'ten merge'e nasıl gittiğini tanımlar. Mimariyi yeniden tasarlamaz; PLAN.md ve brief'lerdeki kararları adımlara çevirir.

## 1. Paket yaşam döngüsü

| Durum | Giriş koşulu | Çıkış |
|---|---|---|
| READY | paketin **doğrudan bağımlılıkları** MERGED (E: dalganın tamamı beklenmez; dalga yalnızca Alembic merge ve denetim noktası) | claim edilebilir |
| CLAIMED | işçi, branch, worktree, touch-zone `state/WORK_QUEUE.md`'de | plan |
| PLANNED | PR taslağında plan (bölüm 3) | kodlama |
| IMPLEMENTING | önce başarısız test, sonra en küçük dilim | kod tamam |
| IMPLEMENTED | hedefli testler yeşil | tam doğrulama |
| VERIFIED | bölüm 5 katmanları geçti, PR'da kanıt | review |
| REVIEWED | kalıcı inceleyici tam commit SHA'yı onayladı; blocker/major yok | yalnızca onaylanan SHA'yı merge |
| MERGED | main'de, `make smoke` yeşil | paket bitti |
| BLOCKED | kullanıcı kararı, ortam ya da brief eksikliği | `state/BLOCKERS.md` kaydı |

Geçişler `state/WORK_QUEUE.md`'de kaydedilir; atlanmaz. "Bitti" demek MERGED demektir.

## 2. Başlamaya hazırlık (Definition of Ready)

- Doğrudan bağımlı paketler MERGED (PLAN 7); aynı dalgadaki diğer paketlerin bitmesi beklenmez (E).
- İşçi CLAUDE.md, PLAN.md, KARARLAR.md, kendi brief'ini ve bağımlı paketlerin "Teslimatlar" bölümünü okudu.
- Touch-zone başka aktif claim ile çakışmıyor (MULTI_AGENT_PROTOCOL).
- Kabul kriterleri ölçülebilir; değilse koordinatöre sor, tahmin etme.
- D sınıfı değişiklik gerektirmiyor (CHANGE_CONTROL).
- Geliştirme ortamı `make smoke` ile yeşil.

## 3. Plan sözleşmesi (PR taslağının ilk yorumu)

1. Gerçek kodda bulunan semboller ve dosyalar (rg ile; CODE_MAP ipucu, otorite değil)
2. Kapsam ve kapsam dışı
3. Değişecek dosyalar ve neden
4. Sözleşme, yapılandırma, profil (`llmaas`/`airgap`) etkisi
5. Test listesi: kabul kriteri → test adı (TEST_STRATEGY adlandırması)
6. Migration ve Alembic branch label'ı
7. Geri alma: migration downgrade, bayrak, veri temizliği
8. Durma koşulları: neyi görünce koordinatöre döneceksin
9. Felsefe kontrolü: `handbook/FELSEFE_UYGULAMA.md` sonundaki üç soru (ARCH-07, ARCH-09, ARCH-10/06) ve cevapları

Plan kaynak okunmadan yazılmaz. 1 günden kısa paketlerde plan 8 satıra inebilir, atlanmaz.

## 4. Kodlama sözleşmesi

- Önce başarısız test, sonra kod. Her dilimden sonra hedefli test.
- Kapsam dışı refactor yok; `FOLLOWUP-` kaydı.
- Donmuş sözleşme ve profil kuralı her edit'te yeniden kontrol edilir.
- Hatalar tipli ve eyleme dönük; secret ve kurum verisi içermez.
- Yapılandırma additive, eski varsayılan korunur; profil farkı `if profile` dalı değil yapılandırma değeridir (PLAN 5).
- Docs (`docs/`, `.env.example` açıklaması, brief'teki teslimat listesi) aynı PR'da.
- Türkçe metin yalnızca `messages/tr.json`; kodda sabit Türkçe yok.
- Her mutasyon endpoint'i audit üretir; salt-okunur mod 403 döner.

## 5. Doğrulama katmanları

1. Statik: `ruff`, `tsc`, import
2. Hedefli unit
3. Lint (`make lint`)
4. Tam unit (`make test`)
5. Sözleşme testleri (CONTRACTS.md'deki donmuş ID'ler için `tests/contract/`)
6. Profil matrisi: aynı testler `DEPLOY_PROFILE=llmaas` ve `airgap` ile
7. Entegrasyon: compose ayakta, gerçek Postgres/Redis; model çağrıları `FAKE_LLM=1` ile sahte, pakete göre gerçek Ollama
8. Uçtan uca: `make smoke`; M3 sonrası 13'ün sınav seti
9. NFR: zaman aşımı, bellek, CPU'da süre (brief'teki ölçülebilir sınırlar)
10. Bağımsız review
11. CI temiz checkout

Entegrasyon koşulamıyorsa paket VERIFIED olamaz; `PENDING_ENV` notu ile BLOCKED kalır.

## 6. Kanıt standardı (PR açıklamasında)

Kanıtın özeti PR açıklamasındadır; ham çıktılar (kapı koşularının `tee` ile alınan tam logu, kırmızı kanıt `*-red-*.log`, ölçüm çıktıları) `state/evidence/` altında durur ve PR açıklaması onlara yolla işaret eder (DRIFT-182 ile düzeltildi, 16 Kasım 2026). PR açıklaması şunları taşır:

- Paket kodu, branch, baz commit
- Değişen dosyalar (gruplu)
- Kabul kriteri → test adı tablosu; atlanan kriter varsa nedeni
- Çalıştırılan komutlar, exit code, süre; `NOT_RUN` olanlar
- Çıktı özeti (secret-free, kurum verisi yok)
- Migration: upgrade ve downgrade denendi mi
- Sözleşme, profil, güvenlik kontrol listesi (SECURITY_AND_PERMISSIONS)
- Varsayımlar ve brief'te görülen çelişkiler
- Kalan riskler

Şablon: `handbook/templates/PR_SABLONU.md`.

## 7. Bağımsız review

Gözden geçiren, uygulayandan farklı ve kalıcı **inceleyici oturumudur** (MULTI_AGENT_PROTOCOL; tek ajan düzeninde koordinatör). Sonuç `state/reviews/<paket>-r<n>.md` dosyasına yazılır. 03a, 03b, 05a, 06a, 06b, 08, 12, 15, 16 ve 00i için ayrıca güvenlik gözden geçirmesi yapılır (inceleyicinin ayrı turu, aynı dosyada ayrı bölüm). Review başlıkları:

- Brief kapsamı ve kabul kriterleri karşılandı mı
- Kaynak kod gerçekten okunmuş mu (plan bölüm 3 ile diff uyuşuyor mu)
- Donmuş sözleşme ve additive tasarım
- İki profil
- Fail-loud: sessiz fallback, sessiz kırpma, sessiz atlama var mı
- Felsefe: yeniden inşa edilen platform yeteneği (ARCH-09), gizli otomatik seçim (ARCH-10), %1 senaryo için çekirdek karmaşıklığı (ARCH-07) var mı
- Kimlik, ACL, on-behalf-of, salt-okunur mod
- Secret ve kurum verisi sızıntısı (log, API, audit, test fixture, PR metni)
- Idempotent yeniden çalışma, atomiklik, geri alma
- Testlerin gerçekçiliği (mock'un gizlediği davranış)
- Terminoloji ve Türkçe metin
- Audit olayı ve Langfuse izi

Uygulayanın açıklaması kanıt değildir; gözden geçiren diff'i ve test çıktısını okur.

### Tur kuralı (16 Kasım 2026, kullanıcı kararı)

- İnceleyici her MAJOR'a kısa bir **sınıf adı** verir (ör. `tick-bütçesi`, `url-html-atlatma`); önceki turun devamıysa "tekrar: rN MAJOR-x" yazar. Rapor başlığında MAJOR sayısıyla birlikte sınıf listesi yer alır.
- **Tetik 1:** aynı sınıf iki ardışık turda MAJOR verirse yama durur. İşçi kod yazmadan önce PR notuna **Tasarım notu** yazar: korunacak değişmez(ler), sınırın iki yanındaki testler, önceki yamanın neden yetmediği. İnceleyici notu kanalda onaylar (kısa), kod ondan sonra gelir.
- **Tetik 2:** üçüncü turun sonunda hâlâ MAJOR varsa koordinatör kapsam kararı verir ve KARARLAR'a yazar: (a) tasarım notu, (b) paketi bölmek, (c) MAJOR'u gerekçesiyle FOLLOWUP'a indirmek. Güvenlik ve veri sınırı bulgularında (c) seçeneği yoktur.
- Beşinci tura varan paket dalga raporunda ayrı satır olur.
- MINOR ve NOTE turu uzatmaz; ONAY yine yalnız BLOCKER ve MAJOR sıfırken verilir.

## 8. Dalga kapanışı

Dalga kapısı paket kapılarından geniştir: temiz checkout, tam test, Alembic tek head, `make smoke`, iki profil, docs güncel, açık blocker yok, kilometre taşı tanımı (PLAN 8) sağlandıysa kullanıcıya rapor. Ayrıca **iç tutarlılık denetimi** (FELSEFE DOC-19): PLAN.md sürüm ve geçmişi, brief ↔ CONTRACTS ↔ KARARLAR çapraz referansları, TERMINOLOGY'ye aykırı terim, "X yasak" deyip X kullanan yer; bulgular `DRIFT-` kaydı. Kapı kanıtı olmadan sonraki dalga READY olmaz.
