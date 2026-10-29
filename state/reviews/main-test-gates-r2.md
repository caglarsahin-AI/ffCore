# Main test kapıları / DRIFT-85 — r2 delta

İstek **K-04a-0037**, ACK **R-gates-0006**, kapsam kararı **K-04a-0034 B**. İncelenen tam SHA **4418a3f94a7e228ea9ffc0353221b82ce3db64bb**; PR baz **fe0d434**, delta baz/r1 **7605022c46b3ad2d9fe6b82631b50592811e906b**. İnceleyici ffcore-inceleyici-20261028-0203; ayrı detached review-gates-r2.

**Karar: ONAY. BLOCKER 0, MAJOR 0, MINOR 0.** R1 MAJOR-1 kapandı. İnceleme yalnız DNS opt-in düzeltmesini kapsar; r1 test/ürün/model alanları yeniden açılmadı.

## Bulgu kapanışı

Beş dosyalık delta okundu. Pyproject yalnız `dns` pytest işaretini kaydediyor, bağımlılık değişmiyor. Kök conftest mevcut opt-in FLAGS mekanizmasına `dns: RUN_DNS_TESTS` ekliyor; yalnız tam `1` değeri çalıştırır, diğer durumda toplamada gerekçeli skip ekler. Gerçek resolver test modülü dns işaretli; import sırasında arama/istemci başlatma yok. Belge bayrağın host/kurum DNS'ine yığın dışı sorgu gönderdiğini ve varsayılanın kapalı olduğunu açıkça söylüyor. Testin timeout başarısızlığını başarı saymayan mevcut davranışı korunmuş.

Bağımsız runtime probe gerçek pytest çağrısında, fixture başlamasını ve `egress.system_resolver` çağrısını saydı. **Bayraksız**, iki profilde de `NOT_RUN: needs RUN_DNS_TESTS=1`, resolver0/fixture0 oldu. Böylece yalnız işaretin varlığı değil, testin fixture/arama öncesinde atlandığı doğrulandı.

**Bayrak açıkken**, aynı probe resolver'ı sayan ve sentetik `socket.gaierror(EAI_NONAME)` atan yerel fonksiyonla değiştirdi: iki profilde test geçti, resolver1/fixture1. Bu opt-in'in testi gerçekten devreye aldığını kanıtlar; gerçek dış DNS davranışı kanıtı olarak sunulmaz. Tüm konteynerler `--network none`; gerçek DNS sorgusu0. Kaynak testlere patch yok; probe `.worktrees/review-gates-r2-evidence/dns_guard_plugin.py` dosyasında.

## Bağımsız kapılar

| Kapı | Sonuç |
|---|---|
| Lint | passed;198 dosya |
| DNS opt-in + mevcut 03b egress unit, llmaas | **56 passed**,4,64sn |
| Aynı hedefli unit, airgap | **56 passed**,4,86sn |
| Bayraksız gerçek pytest / llmaas |1 gerekçeli NOT_RUN,0,30sn;resolver0/fixture0 |
| Bayraksız gerçek pytest / airgap |1 gerekçeli NOT_RUN,0,11sn;resolver0/fixture0 |
| Bayraklı, yalnız sentetik resolver / llmaas |1 passed,0,25sn;resolver1/fixture1;gerçekDNS0 |
| Bayraklı, yalnız sentetik resolver / airgap |1 passed,0,13sn;resolver1/fixture1;gerçekDNS0 |
| Baz state diff / diffcheck / r1 atasallığı |boş / passed / passed |

R1'in iki profil tam385unit ve207int+2NOT_RUN sonuçları önceki SHA'ya aittir (`main-test-gates-r1.md`); yeni SHA için bağımsız tam387unit veya206int+3NOT_RUN koşulduğu iddia edilmez. İşçi yeni tam kapıları PR'da bildirmiş; bu tur bunlar bağımsız tekrar edilmedi. Delta yalnız işaret/bayrak/belge olduğu ve hedefli davranış iki profilde doğrudan doğrulandığı için geniş kapı/Compose/model tekrarı **NOT_RUN**. Gerçek bayraklı dış resolver, kurum/sunucu/PayCore bağlantısı ve model ölçümü **NOT_RUN**.

## Güvenlik turu

- **Kimlik:** ürün auth/OBO/session kodunda delta yok; yeni yetki/uç yok.
- **ACL:** r1 ACL/pipeline testleri değişmedi; yeni mock ACL sınırına dokunmuyor.
- **Secret:** gerçek .env okunmadı/yazılmadı; bu tur sentetik env dosyası dahi gerekmedi. Probe yalnız sayaç/sonuç basıyor.
- **SQL:** DB/migration değişikliği yok; bu tur DB bağlantısı kurulmadı.
- **Egress:** varsayılan gerçek resolver yolu fixture öncesinde kapalı. Bayrak açık testi yalnız sentetik resolver ile doğrulandı; gerçek dış DNS yapılmadı. Aşağıdaki Docker imaj etiketi hatası ayrıca kaydedildi.
- **PII:** gerçek veri yok; yeni test/belge ve sayaç çıktıları kişisel veri taşımıyor.
- **Log sızıntısı:** ürün logging değişmedi, uygulama yığını açılmadı. Yeni skip gerekçesi yalnız bayrak adı; önceki 02 bulgusu bu incelemeyle kapatılmadı.

## Ortam ve yürütme notu

Mevcut yerel **ffcore/tools:0.0.0-fixgates /45181f3a7331** kullanıldı; r1'deki tools ile aynı. Kaynak exact SHA `/work:ro`; bytecode/pytest cache kapalı, ruff cache /tmp; tüm başarılı çağrılarda `docker run --pull=never --rm --network none`. Lint `make lint`, hedefli unit `pytest -q tests/unit/test_03b_dns_opt_in.py tests/unit/test_03b_egress.py`. Runtime probe `pytest -p no:cacheprovider -p dns_guard_plugin -q -rs tests/integration/test_03b_egress_dns.py`, iki DEPLOY_PROFILE; bayraklı varyantta RUN_DNS_TESTS1 ve sentetik resolver sayacı1.

İlk komutta önceki review imaj etiketi temizlenmişti. `--pull=never` eksik olduğundan Docker otomatik registry erişimi denedi ve `pull access denied` döndü; testler başlamadı, imaj indirilmedi. Bu bir reviewer komut hatasıdır; dış sisteme erişim denemesi olmadığı iddia edilmez. Kullanıcıya açıklandı; sonraki tüm çağrılar mevcut imaj ve `--pull=never` ile yapıldı. Ürün bulgusu sayılmadı.

## Temizlik

2026-10-29 13:34: tüm başarılı run'lar --rm ile bitti, Compose yığını/volume oluşturulmadı. Tam HEAD sabit ve worktree temiz doğrulandı; `git worktree remove` exit0, hedef artık yok; force kullanılmadı. Başka stack/cache ve ana checkout'a dokunulmadı. R1/r2 evidence paket kapanışına kadar korundu. Ürün kodu değişikliği/commit/push yok.
