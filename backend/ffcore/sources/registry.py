"""Which driver serves a kind (C14: entry point group `ffcore.sources`).

The built-in drivers are listed here; a consumer package (PayCore) adds one through the entry
point group without FFCore importing it. A kind served twice, or an entry point that is not a
driver class, stops start-up (fail-loud): which code reads a source must never depend on install
order. A kind the database allows but no driver serves is refused at registration (422
`source_kind_unavailable`), as is a driver that needs outbound HTTP when OFFLINE=true (the
profile difference is the OFFLINE value, not a profile branch).
"""

from functools import lru_cache
from importlib.metadata import entry_points

from ffcore.core.config import Settings
from ffcore.sources.base import SourceError
from ffcore.sources.fs import FsDriver

GROUP = "ffcore.sources"
BUILTIN: dict[str, type] = {FsDriver.kind: FsDriver}
REQUIRED = (
    "kind",
    "tombstones",
    "internet_deployments",
    "deployments",
    "config_model",
    "secret_model",
    "test_connection",
    "count",
    "list_changes",
    "fetch_raw",
    "list_attachments",
    "fetch_attachment",
    "acl",
    "render",
    "aclose",
)


class RegistryError(RuntimeError):
    pass


def _check(name: str, driver: object) -> type:
    if not isinstance(driver, type) or any(not hasattr(driver, a) for a in REQUIRED):
        raise RegistryError(f"entry point {GROUP}:{name} is not a source driver class")
    return driver


def build(builtin: dict[str, type], extra: list[tuple[str, object]]) -> dict[str, type]:
    drivers = dict(builtin)
    for name, loaded in extra:
        driver = _check(name, loaded)
        if driver.kind in drivers:
            raise RegistryError(
                f"source kind {driver.kind!r} is served twice ({GROUP}:{name}); remove one"
            )
        drivers[driver.kind] = driver
    return drivers


@lru_cache
def drivers() -> dict[str, type]:
    extra = [(ep.name, ep.load()) for ep in entry_points(group=GROUP)]
    return build(BUILTIN, extra)


def driver_for(kind: str, deployment: str | None, settings: Settings) -> type:
    driver = drivers().get(kind)
    if driver is None:
        raise SourceError("source_kind_unavailable", f"no driver serves source kind {kind!r}")
    if driver.deployments is None:
        if deployment is not None:
            raise SourceError("deployment_invalid", f"{kind} sources take no deployment")
    elif deployment not in driver.deployments:
        raise SourceError(
            "deployment_invalid", f"{kind} needs deployment one of {list(driver.deployments)}"
        )
    if deployment in driver.internet_deployments and settings.offline:
        raise SourceError(
            "source_kind_unavailable",
            f"{kind} ({deployment}) needs outbound HTTP; this installation is OFFLINE",
        )
    return driver
