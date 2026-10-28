"""03a acceptance 7 and 9, unit part: driver configuration rules and Fernet storage."""

import anyio
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from ffcore.core.errors import ApiError
from ffcore.core.secrets import SecretDecryptError, decrypt_json, encrypt_json
from ffcore.services import providers


def test_03a_7_fernet_round_trip_and_wrong_key_fails_loud(settings):
    token = encrypt_json({"api_key": "dummy-not-secret-x"}, settings)
    assert b"dummy-not-secret-x" not in token
    assert decrypt_json(token, settings) == {"api_key": "dummy-not-secret-x"}
    other = settings.model_copy(update={"fernet_key": SecretStr(Fernet.generate_key().decode())})
    with pytest.raises(SecretDecryptError):
        decrypt_json(token, other)


def test_03a_7_mask_and_merge():
    stored = {"base_url": "http://a", "api_key": "dummy-not-secret-k"}
    assert providers.mask_config("vllm", stored) == {"base_url": "http://a", "api_key": "***"}
    merged = providers.merge_config("vllm", stored, {"base_url": "http://b", "api_key": "***"})
    assert merged == {"base_url": "http://b", "api_key": "dummy-not-secret-k"}
    with pytest.raises(ApiError) as caught:
        providers.merge_config(
            "vllm", {"base_url": "http://a"}, {"base_url": "x", "api_key": "***"}
        )
    assert caught.value.code == "invalid_config_field"


def test_03a_7_new_secret_cannot_be_the_mask():
    with pytest.raises(ApiError):
        providers.validate_config("anthropic", {"api_key": "***"})


def test_03a_9_every_driver_has_test_or_reason():
    for name, spec in providers.DRIVERS.items():
        assert (spec.test_call is None) == bool(spec.no_test_reason), name


def test_03a_9_unsupported_returns_explicit_result(settings):
    result = anyio.run(providers.test_connection, "bedrock", {}, settings)
    assert (result.supported, result.ok, result.code) == (
        False,
        False,
        "connection_test_unsupported",
    )
