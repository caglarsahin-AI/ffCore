"""03a acceptance 3: every mutation route has a write=True role dependency, or CI fails."""

from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute

from ffcore.core.auth import RoleRequirement, require_role
from ffcore.main import app

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Own-data endpoints that stay open in read-only access mode (brief 03 "salt-okunur modun
# istisnaları"): signing in and out, changing one's own password.
WRITE_EXEMPT = {"login", "logout", "change_password"}
# 08: the guardrail test panel is a POST dry run (nothing stored, open in read-only mode),
# and the service-account-only internal evaluation endpoint (no user role applies there).
WRITE_EXEMPT |= {"test_guardrails", "evaluate_guardrails"}


def api_routes(routes):
    """Every APIRoute, also inside included routers (FastAPI 0.162 keeps them nested)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from api_routes(route.original_router.routes)


def _requirements(dependant):
    for dep in dependant.dependencies:
        if isinstance(dep.call, RoleRequirement):
            yield dep.call
        yield from _requirements(dep)


def unmarked_mutations(application: FastAPI) -> list[str]:
    missing = []
    for route in api_routes(application.routes):
        if not (route.methods & MUTATING) or route.name in WRITE_EXEMPT:
            continue
        if not any(req.write for req in _requirements(route.dependant)):
            missing.append(f"{sorted(route.methods)} {route.path}")
    return missing


def test_03a_3_every_mutation_requires_write():
    assert unmarked_mutations(app) == []


def test_03a_3_scan_sees_every_mutation():
    # Guards against a vacuous pass: the walk must reach the nested /api/v1 routers.
    mutations = [r for r in api_routes(app.routes) if r.methods & MUTATING]
    assert len(mutations) >= 15


def test_03a_3_exemptions_are_real_routes():
    names = {route.name for route in api_routes(app.routes)}
    assert names >= WRITE_EXEMPT


def test_03a_3_scan_catches_an_unmarked_mutation():
    probe = FastAPI()
    router = APIRouter()

    @router.post("/marked")
    async def marked(actor=Depends(require_role("admin", write=True))):  # noqa: B008
        return {}

    @router.post("/read-only-dependency")
    async def read_only(actor=Depends(require_role("admin"))):  # noqa: B008
        return {}

    @router.delete("/bare")
    async def bare():
        return {}

    probe.include_router(router)
    assert unmarked_mutations(probe) == ["['POST'] /read-only-dependency", "['DELETE'] /bare"]
