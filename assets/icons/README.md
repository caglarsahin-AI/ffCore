# FFCore marka ve ikon varlıkları

FFCore (LLM Agent Runtime), FastFlow ürün ailesinin (`ffengine.com`) üyesidir. Aile kimliği: iki italik **F** (mavi + turuncu), lacivert zemin, Inter yazı tipi. Bu dizin ürünün tanıtım görsellerini ve ikon paketini tutar. Vektör (SVG) kaynak **yoktur**; tüm varlıklar `png/ffcore-brand-variant-b.png` render'ından kırpılarak üretilmiştir (karar, 29 Ekim 2026).

## Renk belirteçleri

FFEngine sitesinden okunan değerler; `frontend/styles/tokens.css` koyu tema bunlara yakın durmalı.

| Belirteç | Değer | Kullanım |
|---|---|---|
| FastFlow mavi | `#1E88E5` (gradyan `#3898EC` → `#1565C0`) | sol F, birincil vurgu |
| FastFlow turuncu | `#FF6B00` (gradyan `#FF8A00` → `#E65100`) | sağ F, ikincil vurgu |
| Çekirdek cyan | `#00E5FF` | merkez ışık |
| Zemin | `#0A192F` | koyu zemin |
| Kart zemini | `#112240` | rozet, panel |
| Metin | `#CCD6F6` | alt başlık |

## Dosyalar

```text
assets/Icons/
├── ffcore_brand_icon_b_*.jpg                 # B varyantı, orijinal render (daire rozet, "LLM Agent Runtime")
├── ffcore_brand_icon_c_*.jpg                 # C varyantı, orijinal render (açık zemin, yedek)
├── png/
│   ├── ffcore-brand-variant-b.png            # B, 1024², tanıtım ve splash için ana görsel
│   ├── ffcore-brand-variant-b-agent-runtime.png  # B, "Agent Runtime" alt başlıklı
│   ├── ffcore-brand-variant-c.png            # C, 1024²
│   ├── ffcore-icon-1024x1024.png             # rozet kırpması (yazı yok): mağaza, PWA
│   ├── ffcore-icon-512x512.png               # rozet kırpması
│   ├── ffcore-icon-256x256.png               # rozet kırpması: masaüstü, bildirim
│   ├── ffcore-icon-128x128.png               # dar FF kırpması: header, avatar
│   ├── ffcore-icon-64x64.png                 # dar FF kırpması
│   ├── ffcore-icon-48x48.png                 # dar FF kırpması
│   ├── ffcore-icon-32x32.png                 # dar FF kırpması: sekme
│   ├── ffcore-icon-16x16.png                 # dar FF kırpması: görev çubuğu
│   └── apple-touch-icon-180x180.png
├── favicon/favicon.ico                       # 16, 32, 48, 64 px
├── preview-sizes.png                         # 256 → 16 px kontrol levhası
└── proposal/make_ffcore_mark.py              # alternatif düz vektör işaret üreticisi (kullanılmıyor, saklandı)
```

İki kırpma var: 256 px ve üstü **tam rozet** (daire ve halka görünür), 128 px ve altı **dar FF** (yalnız iki F ve çekirdek; küçükte okunurluk için). `preview-sizes.png` ikisini yan yana gösterir.

## Kullanım

Frontend'e bağlama 10b paketinin işidir; dosyalar `frontend/public/` altına kopyalanır, bu dizin kaynak olarak kalır.

```html
<link rel="icon" href="/favicon.ico" sizes="any" />
<link rel="icon" type="image/png" sizes="32x32" href="/icons/ffcore-icon-32x32.png" />
<link rel="apple-touch-icon" href="/icons/apple-touch-icon-180x180.png" />
```

Header'da `ffcore-icon-128x128.png` (dar FF) + "FFCore" metni; splash ve giriş ekranında `ffcore-brand-variant-b.png`.

## Yeniden üretme

Render değişirse kırpma koordinatları (`badge` 165,95-860,790; `tight` 250,225-790,705) yeni görsele göre güncellenir ve PNG'ler Pillow ile yeniden boyutlandırılır (LANCZOS). Vektör kaynak gerekirse Figma veya Recraft ile aynı iki F yeniden çizilir; `proposal/make_ffcore_mark.py` başlangıç geometrisi verir.

## Kurallar

- Küçük boyutlarda yazı içeren görsel kullanılmaz; 128 px altında dar FF kırpması zorunlu.
- Mor, yeşil veya cyan ağırlıklı türevler aile dışıdır; mavi + turuncu korunur.
- Açık zeminde C varyantı, koyu zeminde B kullanılır.
