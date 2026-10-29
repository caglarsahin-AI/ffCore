# deploy/langfuse

Langfuse v3 servisleri (`langfuse-web`, `langfuse-worker`, kendi Postgres, ClickHouse, MinIO ve Redis'i)
`deploy/docker-compose.yml` içinde, FFCore'un Postgres ve Redis'inden ayrı adlarla tanımlıdır.
İlk kurulum (paket 02): `init.sh` (`make langfuse-init`) yeni anahtar çiftini ve yönetici parolasını
bir kez ekrana basar, dosya yazmaz; kullanıcı `.env`'e `LANGFUSE_INIT_*` olarak yazar, Langfuse
açılışta organizasyon, proje, anahtar ve kullanıcıyı oluşturur (idempotent). LiteLLM callback'i
(`langfuse`) ve backend aynı anahtar çiftini kullanır. Kullanım: `docs/izleme.md`.
MinIO imajı DECISION-23 (A) ile `cgr.dev/chainguard/minio` digest pinli.
