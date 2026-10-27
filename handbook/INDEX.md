# FFCore Handbook Dizini

Kalıcı kurallar burada, canlı durum `state/` altında, plan `PLAN.md` ve `plan/` içinde. Bir oturum önce `CLAUDE.md`'yi, sonra buradaki sırayla gerekenleri okur.

## Başlangıç
- `../CLAUDE.md` (giriş, okuma sırası)
- `../FELSEFE.md` (geliştirme felsefesi; her kuralın üstünde) ve `FELSEFE_UYGULAMA.md` (FFCore'daki karşılığı)
- `EXECUTION_HANDBOOK.md` (paket yaşam döngüsü, kanıt, review)
- `../state/WORK_QUEUE.md` (kim neyi aldı)

## Ürün ve mimari
- `../PLAN.md` bölüm 1-3 (amaç, kısıtlar, profiller, mimari) ve 1b (ürün adı, modüller)
- `../KARARLAR.md` (kararlar defteri)
- `CONTRACTS.md` (donmuş ve additive sözleşmeler)
- `TERMINOLOGY.md` (bağlayıcı terimler)
- `CODE_MAP.md` (kod haritası; 00 sonrası dolar)

## Operasyon
- `ENVIRONMENT_AND_COMMANDS.md`
- `SECURITY_AND_PERMISSIONS.md`
- `MULTI_AGENT_PROTOCOL.md`
- `CHANGE_CONTROL.md`
- `TEST_STRATEGY.md`
- `RELEASE_AND_ROLLBACK.md`

## Yürütme
- `../BASLATMA.md` (oturum mesajları, dalga takvimi)
- `../plan/` (paket brief'leri)
- `../state/HANDOFF.md`, `../state/BLOCKERS.md`
- `../state/kanal/` (oturumlar arası mesajlar), `../state/pr/` (yerel PR açıklamaları), `../state/reviews/` (review sonuçları)

## Yazılmayanlar ve nedeni
- Edition/lisans dosyası yok: tek edition, lisans yok (KARARLAR.md). İleride lisans gelirse `core/features.py` kapısına takılır.
- Borç sahipliği (debt ownership) dosyası yok: sıfırdan yazılan kodda borç yok; ilk borç çıktığında `state/BLOCKERS.md`'de `DEBT-` kaydı açılır, üçüncü kayıtta bu dosya oluşturulur.
