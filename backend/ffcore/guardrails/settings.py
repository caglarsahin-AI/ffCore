"""Guardrail settings from the environment (names in .env.example, C12).

GUARDRAIL_EGRESS_ENABLED is the profile difference (llmaas true, airgap false) and has no default:
an installation that forgets it fails loudly instead of silently picking a profile (S3).
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GuardrailSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    guardrail_egress_enabled: bool
    # Lifetime of a run's tokenize mapping in Redis; renewed on every write. Longer than the
    # longest run (cpu run_timeout_s 900).
    pii_token_ttl_s: int = Field(default=1800, gt=0)
    redis_url: SecretStr | None = None


@lru_cache
def get_guardrail_settings() -> GuardrailSettings:
    return GuardrailSettings()
