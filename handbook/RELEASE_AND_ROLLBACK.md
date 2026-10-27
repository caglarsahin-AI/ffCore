# Sürüm ve Geri Alma

## Merge öncesi

- Paket VERIFIED + bağımsız REVIEWED (EXECUTION_HANDBOOK).
- Migration'ın `downgrade`'i yazılmış ve CI'da `upgrade → downgrade → upgrade` koşmuş.
- Alembic tek head (dalga sonunda merge PR'ı).
- İki profil testleri yeşil; `make smoke` yeşil.
- Davranış ya da yapılandırma değişikliği `docs/degisiklikler.md`'ye (CHANGELOG) girildi.
- C sınıfı değişiklik varsa `deploy/offline` manifesti güncel.

## Sürümleme

- Pilot boyunca `0.<kilometre taşı>.<düzeltme>`; kilometre taşı tag'leri `m1` … `m7`.
- İmaj tag'i = git tag; compose'da `FFCORE_VERSION` ile pinli, `latest` yok.
- `airgap` paketi (12) sürüm başına tek arşiv: imajlar, wheel'ler, model listesi, SHA-256 manifesti.

## Geri alma ilkeleri

- Her yeni davranış `settings.features` bayrağı ya da additive yapılandırma ile kapatılabilir; eski varsayılan korunur.
- Geri alma = önceki imaj tag'i + `alembic downgrade <önceki>`; veri migration'ı şema migration'ından ayrı dosyada ve tersine çevrilebilir.
- Vektör yeniden indeksleme (embedding modeli ya da sürücü değişimi) yeni koleksiyona yazar; eski koleksiyon geçiş doğrulanana kadar silinmez (`migrate-vectors`, 04b).
- Bilgi tabanı silme güvenli kurallara bağlı (04 safe prune): tombstone, sonra fiziksel silme; raw katmanı yeniden dönüşüm için kalır.
- LiteLLM model kayıtları tablolardan üretilir (PLAN 5); geri alma `render-litellm` ile DB'den yeniden yazmaktır, elle config düzeltmesi yok.
- LangGraph checkpoint şeması değişirse bekleyen run'lar tamamlanır ya da `abandoned` işaretlenir; sessiz kayıp yok.
- Çalışan run'lar deploy sırasında bitirilir (worker graceful shutdown, `SIGTERM` sonrası bekleme), yeni run kuyruğa alınır.

## Geri alma kanıtı

Riskli paketler (03a, 04a, 06a, 12, 16) en az bir geri alma ya da devre dışı bırakma testi içerir: bayrak kapalıyken eski davranış, downgrade sonrası uygulama açılır, yeniden indeksleme yarıda kesilince eski koleksiyon sağlam.
