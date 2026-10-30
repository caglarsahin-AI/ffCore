"""The scenario stack's env overlay (e2e.env, K-SEN-0024) stays in step with .env.test: same
internal hosts plus fake-llm, the fake embedder on, no secret. Runs without a stack."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def _values(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def test_18_env_1_overlay_hosts_are_env_test_plus_fake_llm():
    base = _values(REPO / ".env.test")["ALLOWED_INTERNAL_HOSTS"].split(",")
    overlay = _values(HERE / "e2e.env")["ALLOWED_INTERNAL_HOSTS"].split(",")
    assert overlay == [*base, "fake-llm"]


def test_18_env_2_overlay_is_fake_embed_and_nothing_else():
    assert _values(HERE / "e2e.env") == {
        "FAKE_EMBED": "1",
        "ALLOWED_INTERNAL_HOSTS": _values(HERE / "e2e.env")["ALLOWED_INTERNAL_HOSTS"],
    }
