"""Fernet encryption for secrets stored in Postgres (provider configurations; later tools, sources).

The key is FERNET_KEY from the environment. A value that cannot be decrypted is an error, never
an empty configuration (fail-loud): a changed key must be noticed, not silently ignored.
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from ffcore.core.config import Settings


class SecretDecryptError(RuntimeError):
    """Stored value does not decrypt with the current FERNET_KEY (wrong or rotated key)."""


def _fernet(settings: Settings) -> Fernet:
    return Fernet(settings.fernet_key.get_secret_value())


def encrypt_json(value: dict[str, Any], settings: Settings) -> bytes:
    return _fernet(settings).encrypt(json.dumps(value, sort_keys=True).encode("utf-8"))


def decrypt_json(token: bytes, settings: Settings) -> dict[str, Any]:
    try:
        return json.loads(_fernet(settings).decrypt(bytes(token)))
    except InvalidToken:
        raise SecretDecryptError(
            "stored secret does not decrypt with FERNET_KEY (was the key changed?)"
        ) from None
