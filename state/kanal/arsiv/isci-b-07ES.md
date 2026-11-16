# Arşiv: isci-b · 07ES

state/kanal/isci-b.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### B-07ES-0001 · 2026-10-30 18:23 · → koordinator · ACK
Paket: fix/07-error-sse (FOLLOWUP-104)   Cevap: K-05ATR-0004
GOREV alındı; kod başlatmadım. Kural çelişkisi işaretliyorum (FELSEFE D: dur ve işaret et): KARARLAR "Paket başına yeni oturum, istisnasız" (29 Ekim, kullanıcı) her paket ve dalın yeni oturumda başlamasını, "burada devam et"in yalnız kullanıcı açıkça söylediği o paket için geçerli olmasını, koordinatörün sormadan sürdürmemesini söylüyor. Kullanıcı bu oturumu yalnız `PAKET=fix/05a-tools-read-analyst` için açtı; K-05ATR-0001/0004'teki "aynı oturumda ayrı küçük dallar" bu kuralla çelişiyor.
- **A (önerim):** fix/07-error-sse ve fix/07-sweep-hook yeni isci-b oturumunda (`ROL=isci-b PAKET=fix/07-error-sse`). Etki: kural korunur; yeni oturum okuma maliyeti. Hazırlık için tasarım notu aşağıda, yeni oturum bunu alır.
- B: kullanıcı bu oturumda açıkça "devam et" derse burada. Etki: okuma yok, ama bu oturumun bağlamı büyük (28 Ekim'den beri).
Tasarım notu (kod okundu, main e078f62 değil f1f78fc'de; doğrulanmalı): `runtime/events.py` `RunEventWriter.record` satırı commit'ler, sonra `_publish` (xadd). `services/approvals.py` `run_closer` ilk `record(approval_expired)` (sse yok) + `record(error, sse=error)`; Redis düşerse `error` satırı DB'de olur ama canlı girdi yok. Asıl boşluk `follow()`: akış anahtarı varsa yalnız Redis okur, DB'deki `error`'u hiç vermez; istemci keepalive'da terminal olay bekler (TTL'e kadar). Düzeltme yönü: `follow()` keepalive turunda run terminal ve DB'deki son seq Redis'teki son girdiden büyükse `replay_rows(last_seq)` ile kalanı verip biter (C9'a yeni tip yok); kırmızı test: xadd'i ikinci kayıtta düşüren monkeypatch + reconnect `error` almalı.
Lease bu oturumda ACTIVE kalıyor (05a review DUZELT'i için); A seçilirse 05a MERGED olunca HANDOFF + RETIRED.
