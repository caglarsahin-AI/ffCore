# 10-marka r1 bağımsız inceleme

**İncelenen tam SHA:** `2843d40d8fe0e1641bea80947b6bc90b7e5b7ebd`  
**Baz:** `b6fc3d8`  
**Karar:** **ONAY**  
**Bulgular:** BLOCKER 0 · MAJOR 0 · MINOR 1

Baz diff'inde `state/**` değişikliği yoktur. İnceleme yalnız exact SHA'nın detached `.worktrees/review-10-marka-r1` ağacında yapıldı. MINOR-1 açık bulgudur; giderilmiş veya ertelenmesi kabul edilmiş sayılmaz. Runtime marka bağlantısını engellemediği için karar ONAY, takip/merge kararı koordinatördedir.

## MINOR-1 — Marka üreticisinin tekrarlanabilir araç ortamı tanımlı değil

`assets/icons/scripts/make_web_brand.py` doğrudan `PIL` import ediyor. README komutu host `py -3.12` ve “Pillow 12.2.0 ile ölçüldü” diyor; ancak Pillow bu script için doğrudan/pinli bir üretim bağımlılığı olarak tanımlanmamış ve repository'nin standart `ffcore/tools` imajlarında import edilemiyor. İki mevcut yerel tools imajıyla ağsız/salt-okunur probe `ModuleNotFoundError: No module named 'PIL'` verdi. `backend/uv.lock` içinde başka paketlerin transitifi olarak Pillow 12.3.0 kayıtları bulunması script için çalıştırılabilir ortam sağlamıyor ve belgelenen 12.2.0 ile de aynı değil.

Bu makinedeki host Python'da Pillow 12.2.0 bulunduğu için `--check` 9/9 dosyada geçti; fakat temiz geliştirici/CI ortamında belgelenen tek komutun çalışacağı ve aynı PNG baytlarını üreteceği repo tarafından güvence altına alınmıyor.

Beklenen: asset üretimi için sürümü sabitlenmiş, standart bir ortam/komut tanımlanmalı (ör. ayrı kilitli asset bağımlılık grubu ve tools hedefi); README aynı komutu kullanmalı. En az iki temiz koşuda byte-eşitlik ve `--check` testi CI'da çalışmalıdır.

## Kapsam sonucu

- Next dosya kurallarıyla `favicon.ico`, 48 px `icon.png`, 180 px `apple-icon.png` ve `/manifest.webmanifest` bağlanmış. Manifest adı/açıklaması `messages/en.json` kaynak anahtarlarından, tema rengi marka sabitinden geliyor; 192/512 ikon referansları doğru.
- Kenar çubuğu 32 CSS px kutuda dar FF 128 kaynağını, giriş ekranı yazısız saydam rozeti kullanıyor. Her ikisi `next/image`; metinler ve alt metinler en/tr mesaj dosyalarından geliyor.
- EN “Enterprise AI Agent Platform”, TR “Kurumsal Yapay Zekâ Platformu” tek mesaj anahtarında; bileşenlerde sabit ürün sloganı yok.
- Gömülü eski sloganlı variant-B dosyası görev gereği üretilmiş ancak hiçbir konsol bileşeninde kullanılmıyor. Kaynak ve kullanım sınırı README/docs'ta açık.
- `backend/pyproject.toml` değişikliği yalnız proje açıklaması; bağımlılık/kilit değişikliği gerektirmiyor.
- Son commit `2843d40` yalnız yeniden üretilen doküman ekran görüntülerini değiştiriyor; ürün kodu `62c8b21` ile aynı.
- `docs/onyuz.md`, `FAKE_EMBED=1` değerinin shell'e export edilmesi ve `langfuse-web` iç-host gereksinimini açıkça düzeltiyor.
- Dört yeni marka ekran görüntüsü ve örnek yenilenmiş ekranlar görsel olarak incelendi: açık/koyu temada marka okunaklı, yanlış/gömülü slogan görünmüyor. Provider/proje ekranlarındaki içerik sentetik `e2e-*` kayıtları; görünür secret veya gerçek kişi verisi saptanmadı.

## Güvenlik turu

- **Kimlik:** kimlik doğrulama/oturum kodu değişmedi. Login sayfasına yalnız yerel statik marka alanı eklendi; redirect/session davranışı korunuyor.
- **ACL:** sidebar ve manifest değişiklikleri yetki kararına dokunmuyor. Ekran görüntüleri yalnız test fixture verisi içeriyor.
- **Secret:** yeni kodda secret/credential yok. Görsel turda provider formundaki base URL sentetik `fake-llm`; gizli değer görünmüyor.
- **SQL:** SQL veya veri erişim kodu değişmedi; kapsam dışı.
- **Egress:** bütün marka dosyaları aynı origin'den `/brand/**` veya Next app dosya yollarından geliyor; dış görsel/telemetri çağrısı eklenmedi. Üretim probe'ları `--network none` ile yapıldı.
- **PII:** ekran görüntülerinde gerçek kişi/kurum PII'si saptanmadı; yalnız sentetik e2e anahtarları ve genel ürün metni var.
- **Log:** loglama kodu değişmedi; marka dosyaları veya çeviri metinleri log yüzeyi eklemiyor.

## Komutlar ve sonuçlar

| Komut / kontrol | Sonuç |
|---|---|
| Exact SHA ve `b6fc3d8` baz soy kontrolü | geçti |
| `git diff --name-status b6fc3d8..2843d40 -- state` | boş |
| `git diff --check b6fc3d8..HEAD` | geçti |
| Host: `py -3.12 .../make_web_brand.py --check` | 9 dosya güncel; Pillow 12.2.0 |
| Yerel `ffcore/tools:0.0.0-main` ve `0.0.0-06a`, `--network none`, kaynak salt-okunur | ikisinde de `PIL` import yok; MINOR-1 |
| PNG boyut/mod kontrolü | icon 48 RGBA; apple 180 RGBA; brand 128/192/256/512 beklenen boyut ve modlarda |
| Görsel inceleme | login + projects light/dark ve provider ekranları incelendi; marka/slogan doğru, sentetik veri |
| PR kanıtı çapraz kontrolü | export'lu son e2e: aşama 1 1/1, aşama 2 108/108; bağımsız geçiş olarak sahiplenilmedi |

## NOT_RUN

- Playwright 108 testlik tam e2e yığını koordinatörün kısa-tur talimatı gereği yeniden açılmadı; işçi kanıtı, test kaynakları ve üretilen ekran görüntüleri çapraz kontrol edildi.
- Frontend ESLint/TypeScript/Vitest bağımsız tekrar edilmedi; ürün kodu statik incelendi ve işçi kanıtı 114/114 olarak kaydedildi.
- Backend `make test` koşulmadı; backend değişikliği yalnız paket açıklaması.
- Lighthouse FOLLOWUP-37 kapsamında NOT_RUN.
- Gerçek iOS cihazında saydam apple-touch-icon köşelerinin görünümü doğrulanmadı.
