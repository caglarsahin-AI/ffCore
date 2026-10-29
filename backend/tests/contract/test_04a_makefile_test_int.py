"""FOLLOWUP-84 (review 04a r2 MINOR-1): `make test-int` gives the Qdrant tests the Compose URL
also when Compose hands QDRANT_URL to the tools container as an empty value (GNU make's `?=`
does not fill a variable that is defined but empty)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = "QDRANT_URL=http://qdrant:6333 RUN_QDRANT_TESTS=1"


def rendered(env_update: dict[str, str | None]) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("QDRANT_URL", "RUN_QDRANT_TESTS")}
    env.update({k: v for k, v in env_update.items() if v is not None})
    out = subprocess.run(
        ["make", "-n", "-C", str(ROOT), "test-int"], env=env, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.mark.skipif(shutil.which("make") is None, reason="make runs in the tools image only")
@pytest.mark.parametrize(
    "env", [{}, {"QDRANT_URL": "", "RUN_QDRANT_TESTS": ""}], ids=["unset", "empty"]
)
def test_04a_test_int_defaults_fill_unset_and_empty(env):
    assert DEFAULT in rendered(env)


@pytest.mark.skipif(shutil.which("make") is None, reason="make runs in the tools image only")
def test_04a_test_int_keeps_an_explicit_url():
    command = rendered({"QDRANT_URL": "http://other:6333", "RUN_QDRANT_TESTS": "0"})
    assert "QDRANT_URL=http://other:6333 RUN_QDRANT_TESTS=0" in command
