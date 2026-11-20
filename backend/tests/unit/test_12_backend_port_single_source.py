"""12-2 (K-TRJ-0013 HANDOFF note): the backend's container port is defined once.

core/egress.py (FOLLOWUP-194) and services/external_config.py (06b-2) both compare loopback
addresses with it; external_config takes egress's value instead of keeping its own copy.
"""

import ast
from pathlib import Path

from ffcore.core import egress
from ffcore.services import external_config

SOURCE = Path(external_config.__file__).read_text(encoding="utf-8")


def test_12_2_external_config_has_no_own_backend_port():
    assigned = {
        target.id
        for node in ast.walk(ast.parse(SOURCE))
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "BACKEND_CONTAINER_PORT" not in assigned
    assert external_config.BACKEND_CONTAINER_PORT == egress.BACKEND_CONTAINER_PORT
