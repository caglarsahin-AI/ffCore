# deploy/langfuse

Langfuse v3 servisleri (`langfuse-web`, `langfuse-worker`, kendi Postgres, ClickHouse, MinIO ve Redis'i)
`deploy/docker-compose.yml` içinde, FFCore'un Postgres ve Redis'inden ayrı adlarla tanımlıdır.
İlk kurulum otomasyonu (`init.sh`, `LANGFUSE_INIT_*`) ve LiteLLM callback bağlantısı paket 02'dedir.
MinIO imajı DECISION-23 (A) ile `cgr.dev/chainguard/minio` digest pinli.
