"""Obviously fake settings values for tests (never real secrets; same values as .env.test)."""

SERVICE_TOKEN = "dummy-not-secret-service-token-0123456789"
OBO_SECRET = "dummy-not-secret-obo-jwt-secret-0123456789"
SECRET_KEY = "dummy-not-secret-session-key-0123456789"
# urlsafe base64 of b"dummy-not-secret-fernet-key-0000"
FERNET_KEY = "ZHVtbXktbm90LXNlY3JldC1mZXJuZXQta2V5LTAwMDA="
EMBED_DIM = 1024

SETTINGS_03A = {"secret_key": SECRET_KEY, "fernet_key": FERNET_KEY, "embed_dim": EMBED_DIM}
