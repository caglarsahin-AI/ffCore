# Değişiklik Kontrolü

## Değişiklik sınıfları

| Sınıf | Ne | Gereken |
|---|---|---|
| **A** | Paket içi, dışarıya görünmeyen ekleme ya da düzeltme | PR + test; koordinatör merge eder |
| **B** | Additive yapılandırma, enum değeri, isteğe bağlı alan, nullable kolon, yeni ekran | Docs aynı PR'da + geriye uyumluluk testi (eski değer/alan hâlâ çalışır) |
| **C** | Bağımlılık, imaj, compose servisi, Python/Node sürümü, egress izin listesi, güvenlik davranışı, lisans | Kullanıcı onayı; `deploy/offline` manifesti ve `docs/` güncellenir |
| **D** | Donmuş sözleşme (CONTRACTS.md), profil anlamı (`llmaas`/`airgap`), veri sınırı, ürün kapsamı, kilometre taşı tanımı | KARARLAR.md kaydı + kullanıcı onayı olmadan yasak; brief güncellenir |

Sınıfı PR başlığında etiketle: `[A]`, `[B]`, `[C]`, `[D]`. Emin değilsen bir üst sınıf.

## Deprecation (ad ve alan değişimi)

1. Yeni ad additive eklenir.
2. Eski ad çalışmaya devam eder, loga `DeprecationWarning` düşer.
3. Migration notu (`docs/degisiklikler.md`) ve geçiş testi eklenir.
4. En az iki küçük sürüm sonra kaldırma planlanır; kaldırma ayrı PR.
5. Sessiz yeniden yorumlama yok: eski değerin anlamı değişmez, yalnızca yeni ad eklenir.

## Brief ile kod çelişirse

- Brief'teki iki cümle çelişiyorsa: PR notunda işaretle, varsayımını yaz, durma (PLAN 5). Koordinatör KARARLAR'a işler.
- Brief ile PLAN.md çelişiyorsa: PLAN.md kazanır; brief düzeltilir.
- Brief ile CONTRACTS.md çelişiyorsa: donmuş sözleşme kazanır; aksi D sınıfı.
- PayCore referansı ile brief çelişiyorsa: brief kazanır; referans yalnızca ölçüm ve ders kaynağıdır (KARARLAR).

## Kapsam dışı iş görürsen

Kodu değiştirme; `state/BLOCKERS.md`'ye `FOLLOWUP-` kaydı aç (ne, nerede, neden). Koordinatör yeni paket ya da mevcut pakete ek olarak planlar. Gizli refactor yok.
