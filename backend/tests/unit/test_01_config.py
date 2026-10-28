"""Package 01: LiteLLM settings and the static LiteLLM config file (no model_list, C1/P1)."""

from pathlib import Path

import pytest
import yaml

from ffcore.core.config import Settings
from ffcore.services.litellm_client import LiteLLMNotConfigured, litellm_settings
from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A

REPO = Path(__file__).resolve().parents[3]


def _settings(**extra) -> Settings:
    return Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        **SETTINGS_03A,
        **extra,
    )


def test_01_3_config_has_no_model_list():
    config = yaml.safe_load((REPO / "deploy/litellm/config.yaml").read_text(encoding="utf-8"))
    assert "model_list" not in config
    assert config["general_settings"]["store_model_in_db"] is True
    # Guardrail hooks live in the backend only (B3); no callbacks that rewrite requests.
    assert "guardrails" not in config.get("litellm_settings", {})


def test_01_settings_missing_litellm_is_loud():
    with pytest.raises(LiteLLMNotConfigured, match="LITELLM_URL"):
        litellm_settings(_settings())


def test_01_settings_keys_are_secret():
    s = _settings(
        litellm_url="http://litellm:4000",
        litellm_master_key="sk-dummy-not-secret-litellm-master",
        litellm_internal_key="sk-dummy-not-secret-litellm-internal",
    )
    conf = litellm_settings(s)
    assert conf.url == "http://litellm:4000"
    assert "dummy-not-secret" not in repr(s)
    assert "dummy-not-secret" not in repr(conf)
