"""Render the 03a OpenAPI draft (`backend/openapi/03a.yaml`) from the application routes.

Tools container: python -m ffcore.api.openapi_export > openapi/03a.yaml
The contract test compares the committed file with this output, so the file never drifts.
"""

import sys

import yaml
from fastapi.openapi.utils import get_openapi

from ffcore.api import api_router


def render() -> str:
    spec = get_openapi(
        title="FFCore API",
        version="0.3a",
        description="Identity, projects, providers, models and audit (package 03a).",
        routes=api_router.routes,
    )
    return yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    sys.stdout.write(render())
