import pytest

from ffcore.core.config import Settings
from tests.dummy import SETTINGS_03A

SERVICE_TOKEN = "dummy-not-secret-service-token-0123456789"
OBO_SECRET = "dummy-not-secret-obo-jwt-secret-0123456789"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        egress_allowlist=[],
        allowed_internal_hosts=[],
        **SETTINGS_03A,
    )
