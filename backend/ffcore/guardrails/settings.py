"""Guardrail settings from the environment (names in .env.example, C12).

GUARDRAIL_EGRESS_ENABLED is the profile difference (llmaas true, airgap false) and has no default:
an installation that forgets it fails loudly instead of silently picking a profile (S3).
GUARDRAIL_EGRESS_NER (08 tam 1b, K-08T1B-0004 A) has no default either: true masks person names
at egress with the NER model (llmaas production), false keeps the regex identifiers only (tests
and airgap; false in llmaas production is a [C] decision).
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GuardrailSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    guardrail_egress_enabled: bool
    guardrail_egress_ner: bool
    # Lifetime of a run's tokenize mapping in Redis; renewed on every write. Longer than the
    # longest run (cpu run_timeout_s 900).
    pii_token_ttl_s: int = Field(default=1800, gt=0)
    redis_url: SecretStr | None = None


@lru_cache
def get_guardrail_settings() -> GuardrailSettings:
    return GuardrailSettings()


def check_egress_ner(guard: GuardrailSettings, settings) -> None:
    """Start-up check (API and agent worker): person names at egress need a NER model. A missing
    weight is the API's `/readyz` `model_missing`; a missing name stops the start here."""
    if not (guard.guardrail_egress_enabled and guard.guardrail_egress_ner):
        return
    if not (settings.ner_model and settings.ner_revision):
        raise RuntimeError(
            "ner_not_configured: GUARDRAIL_EGRESS_NER=true needs NER_MODEL and NER_REVISION"
        )
