# deploy

`docker-compose.yml` (depo kökündeki `compose.yaml` bunu içerir), `docker-compose.ollama.yml` (yalnızca airgap + Ollama; `COMPOSE_FILE` ile eklenir), `docker-compose.egress.yml` + `egress/` (llmaas forward proxy, profil `egress`), `docker-compose.tls.yml` + `tls/` (TLS ters proxy, profil `tls`); profil/overlay uyumu `scripts/compose_preflight.py` (docs/kurulum.md), `litellm/`, `ollama/`, `langfuse/`, `postgres/initdb/`.
