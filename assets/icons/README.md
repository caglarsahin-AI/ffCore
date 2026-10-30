# FFCore marka ve ikon varlıkları

FFCore (Kurumsal Yapay Zekâ Platformu / Enterprise AI Agent Platform), FastFlow (FF) ürün ailesinin (`ffengine.com`) üyesidir. Aile kimliği: iki italik **F** (mavi + turuncu), lacivert zemin, Inter yazı tipi. Bu dizin ürünün tanıtım görsellerini ve ikon paketini tutar. Ürün ikonunun vektör (SVG) kaynağı **yoktur**: ürün varlıkları `png/ffcore-brand-variant-b.png` render'ından kırpılarak üretilmiştir (karar, 29 Ekim 2026). `concepts/` altındaki üç kavram taslağının (`cekirdek`, `dugum`, `yorunge`) SVG'leri vardır; bunlar seçilmeyen alternatiflerdir, üründe kullanılmaz.

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
├── ffcore_brand_icon_b_*.jpg                 # B varyantı, orijinal render (daire rozet; render'da gömülü eski slogan "LLM Agent Runtime", ekranda kullanılmaz)
├── ffcore_brand_icon_c_*.jpg                 # C varyantı, orijinal render (açık zemin, yedek)
├── png/
│   ├── ffcore-brand-variant-b.png            # B, 1024², tanıtım ve splash için ana görsel
│   ├── ffcore-brand-variant-b-agent-runtime.png  # B, render'da gömülü eski slogan "Agent Runtime", ekranda kullanılmaz
│   ├── ffcore-brand-variant-c.png            # C, 1024²
│   ├── ffcore-badge-transparent-1024.png     # yalnız daire rozet, köşeler saydam (yazı yok): giriş ekranı
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
├── concepts/                                 # seçilmeyen üç kavram taslağı (SVG + PNG), üründe yok
├── scripts/make_web_brand.py                 # önyüz dosyalarını üretir (aşağıda "Önyüz")
└── proposal/make_ffcore_mark.py              # alternatif düz vektör işaret üreticisi (kullanılmıyor, saklandı)
```

İki kırpma var: 256 px ve üstü **tam rozet** (daire ve halka görünür), 128 px ve altı **dar FF** (yalnız iki F ve çekirdek; küçükte okunurluk için). `preview-sizes.png` ikisini yan yana gösterir.

## Önyüz (10-marka)

Önyüze bağlama 10-marka paketinin işidir. Bu dizin kaynak olarak kalır; önyüzdeki kopyalar elle değil tek komutla üretilir:

```bash
py -3.12 assets/icons/scripts/make_web_brand.py          # yazar
py -3.12 assets/icons/scripts/make_web_brand.py --check  # karşılaştırır, fark varsa çıkış 1
```

Script her çıktıyı ya bayt kopyası ya da LANCZOS küçültmesi (metadata'sız PNG) olarak yazar; ikinci koşu aynı baytları verir (Pillow 12.2.0 ile ölçüldü). 1 MB'lık 1024 dosyaları web'e konmaz.

| Önyüz dosyası | Kaynak | Nerede |
|---|---|---|
| `frontend/app/favicon.ico` | `favicon/favicon.ico` (kopya) | sekme (Next.js dosya kuralı) |
| `frontend/app/icon.png` | `png/ffcore-icon-48x48.png` (kopya, dar FF) | sekme, PNG |
| `frontend/app/apple-icon.png` | `png/apple-touch-icon-180x180.png` (kopya) | iOS ana ekran |
| `frontend/public/brand/ffcore-icon-128.png` | `png/ffcore-icon-128x128.png` (kopya, dar FF) | kenar çubuğu, 32 px kutu |
| `frontend/public/brand/ffcore-icon-192.png` | `png/ffcore-icon-1024x1024.png` → 192 | `frontend/app/manifest.ts` |
| `frontend/public/brand/ffcore-icon-512.png` | `png/ffcore-icon-512x512.png` (kopya) | `frontend/app/manifest.ts` |
| `frontend/public/brand/ffcore-badge-256.png` | `png/ffcore-badge-transparent-1024.png` → 256 | giriş ekranı, 96 px |
| `frontend/public/brand/ffcore-badge-512.png` | `png/ffcore-badge-transparent-1024.png` → 512 | yedek büyük rozet |
| `frontend/public/brand/ffcore-brand-variant-b-512.png` | `png/ffcore-brand-variant-b.png` → 512 | yalnız tanıtım; ekranda kullanılmaz (render'da gömülü eski İngilizce slogan) |

Ekranda yazı içeren görsel kullanılmaz: ürün adı ve alt başlık `frontend/messages/{en,tr}.json`'dan gelir, görselde gömülü metin çevrilemez. Giriş ekranındaki rozetin köşeleri saydam olduğundan açık ve koyu temada aynı görünür.

## Yeniden üretme

Render değişirse kırpma koordinatları (`badge` 165,95-860,790; `tight` 250,225-790,705) yeni görsele göre güncellenir ve PNG'ler Pillow ile yeniden boyutlandırılır (LANCZOS). Vektör kaynak gerekirse Figma veya Recraft ile aynı iki F yeniden çizilir; `proposal/make_ffcore_mark.py` başlangıç geometrisi verir.

## Kurallar

- Küçük boyutlarda yazı içeren görsel kullanılmaz; 128 px altında dar FF kırpması zorunlu.
- Mor, yeşil veya cyan ağırlıklı türevler aile dışıdır; mavi + turuncu korunur.
- Açık zeminde C varyantı, koyu zeminde B kullanılır.
