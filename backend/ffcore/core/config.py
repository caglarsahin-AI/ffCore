"""Process settings read from the environment (.env.example documents every name, C12).

Profile differences are configuration values, never `if profile` branches (PLAN 5).
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

CommaList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    deploy_profile: Literal["llmaas", "airgap"]
    offline: bool
    # Contains the database password, so it is a secret too.
    database_url: SecretStr | None = None

    # Internal service account (mcp-search, workers). Bearer token, compared in constant time.
    service_token: SecretStr = Field(min_length=32)
    # HS256 key for X-On-Behalf-Of tokens; separate from service_token so they rotate independently.
    obo_jwt_secret: SecretStr = Field(min_length=32)
    # Audience this backend accepts in X-On-Behalf-Of tokens addressed to itself.
    obo_audience: str = "ffcore-backend"

    # Hosts external calls may reach (exact name or "*.suffix"). Empty means no external host.
    egress_allowlist: CommaList = []
    # Hosts or CIDRs that may resolve to private addresses (compose service names, internal APIs).
    allowed_internal_hosts: CommaList = []

    @field_validator("egress_allowlist", "allowed_internal_hosts", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
