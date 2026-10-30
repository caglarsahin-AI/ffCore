"""FOLLOWUP-111 (K-07F-0004 A): the test hook flag reaches the backend container, off by default.

The hook runs the sweep in the backend process; the agent workers share the backend's
environment block, so they carry the flag too (unread there).
"""

from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[3] / "deploy" / "docker-compose.yml"


def test_07f_3_compose_passes_test_hook_flag_off_by_default():
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    assert services["backend"]["environment"]["FFCORE_TEST_HOOKS"] == "${FFCORE_TEST_HOOKS:-0}"
