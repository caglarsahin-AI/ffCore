"""16-2: Confluence and Jira are built-in drivers (C14 registry), with the profile rule
(Cloud needs outbound HTTP: refused when OFFLINE) and the credential/deployment rule."""

import pytest

from ffcore.sources import registry
from ffcore.sources.base import SourceError
from ffcore.sources.confluence import ConfluenceDriver
from ffcore.sources.jira import JiraDriver


def test_16_2_builtin_drivers_are_complete():
    assert registry.BUILTIN["confluence"] is ConfluenceDriver
    assert registry.BUILTIN["jira"] is JiraDriver
    for driver in (ConfluenceDriver, JiraDriver):
        assert registry._check(driver.kind, driver) is driver


@pytest.mark.parametrize("kind", ["confluence", "jira"])
def test_16_2_cloud_refused_offline_server_allowed(settings, kind):
    offline = settings.model_copy(update={"offline": True})
    with pytest.raises(SourceError) as error:
        registry.driver_for(kind, "cloud", offline)
    assert error.value.code == "source_kind_unavailable"
    assert registry.driver_for(kind, "server", offline) is registry.BUILTIN[kind]
    with pytest.raises(SourceError) as error:
        registry.driver_for(kind, None, settings)
    assert error.value.code == "deployment_invalid"


@pytest.mark.parametrize("driver", [ConfluenceDriver, JiraDriver])
@pytest.mark.parametrize(
    ("deployment", "secret"),
    [
        ("server", {"email": "svc@example.test", "api_token": "dummy-not-secret"}),
        ("cloud", {"token": "dummy-not-secret"}),
    ],
)
def test_16_2_credential_must_match_the_deployment(driver, deployment, secret):
    clean = driver.secret_model.model_validate(secret).model_dump(mode="json")
    assert "dummy-not-secret" in clean.values()  # stored as given (encrypted by the API)
    with pytest.raises(SourceError) as error:
        driver.check(deployment, {"base_url": "https://wiki.example.test"}, clean)
    assert error.value.code == "secret_invalid"
