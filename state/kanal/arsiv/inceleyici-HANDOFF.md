# Arşiv: inceleyici · HANDOFF

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-HANDOFF-20261029-0001 · 2026-10-29 15:58 · → koordinator · HANDOFF
Paket: inceleyici-oturum-devri   Cevap: kullanıcının oturumu kapatma talimatı
Kullanıcı token tüketimi nedeniyle bu oturumu kapatıp yeni inceleyici oturumu açacak. Yeni görev alınmıyor. Bu oturumda alınmış tüm review istekleri teslim edildi. Son doğrulanmış kapanış K-02-0024 / R-02-0017 (15:22): 02r4 ve10b-poc-1r2 onaylı SHA'ları main atası; izin verilen evidence kaldırıldı, kalıcı raporlar korundu. Daha sonraki koordinatör mesajları bu kapanış adımında taranmadı; yeni oturum son okunan ID'den itibaren yeni adresli mesajları kontrol etmeli.
Yeni rol inceleyici. Kullanıcının zorunlu1-8 okuması yeni oturumda tamamlanmalı. Her review tam SHA ACK sonrası ayrı detached worktree; ana checkout/switch/force/push yok. Gerçek.env/PayCore korpusu/kurum-sunucu bağlantısı yasak; Docker --pull=never, Compose run için pull_policy:never; offline/fake render servis öncesi doğrulanır. ffcore-10a-nm(-pw) ve04a-knowledge-core_model_cache korunur; bayatpw seed kopyalanmaz. Kanıtlar state/reviews ve önceki kanal mesajlarında.
Yerel watcher yeni oturum yaratmaz; config.json ThreadId hedefli codex queue kullanır. Yeni oturum kimliğine yönlendirme ve teslim testi gerekir. Bu kapanışta scheduler yapılandırması değiştirilmedi.
