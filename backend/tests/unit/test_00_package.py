"""Package 00: backend is the installable `ffcore` distribution a consumer imports."""

import ast
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPORTS = ("paycore_llm",)


def test_00_1_pyproject_builds_ffcore_with_pinned_backend():
    pyproject = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["name"] == "ffcore"
    assert pyproject.get("tool", {}).get("uv", {}).get("package", True) is not False
    requires = pyproject["build-system"]["requires"]
    assert len(requires) == 1 and "==" in requires[0], requires
    assert (BACKEND / "ffcore" / "__init__.py").exists()
    assert not (BACKEND / "app").exists()


def test_00_1_ffcore_never_imports_consumer():
    # ffcore is the product; consumers (PayCore LLM) depend on it, never the reverse.
    offenders = []
    for path in (BACKEND / "ffcore").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            hits = [n for n in names if n.split(".")[0] in FORBIDDEN_IMPORTS]
            offenders += [f"{path.name}: {n}" for n in hits]
    assert offenders == []
