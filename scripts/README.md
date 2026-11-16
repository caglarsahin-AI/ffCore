# scripts

Geliştirme betikleri; `tools` konteynerinde Makefile hedefleriyle koşar (`smoke.py`).

`kanal_ozet.py` host'ta koşar (stdlib, yazmaz): `python -X utf8 scripts/kanal_ozet.py [--json]`; ana checkout'taki `state/kanal/**` ve `state/WORK_QUEUE.md`'den ACK bekleyen bağlayıcı mesajları, paket başına son durumu, son onaylı SHA'yı ve biçim dışı başlık sayısını verir (MULTI_AGENT_PROTOCOL "Mesaj biçimi").
