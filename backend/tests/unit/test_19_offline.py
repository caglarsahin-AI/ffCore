"""19 kabul 4 ve şart 3: offline archive lists in git, load/verify against them.

The bash scripts run for real with a stub `docker` first on PATH (no daemon, no network): the
stub answers `image inspect` from a file and records every other call.
"""

import hashlib
import os
import re
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
OFFLINE = REPO / "deploy" / "offline"
COMPOSE = (REPO / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")


def _lines(name):
    return [
        line.split()
        for line in (OFFLINE / name).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


@pytest.fixture
def stub(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ids = tmp_path / "ids"
    ids.write_text("", encoding="utf-8")
    calls = tmp_path / "calls"
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$*" >> {calls}\n'
        'if [ "$1 $2" = "image inspect" ]; then\n'
        f'  line="$(grep -F -- " ${{@: -1}}" {ids} | tail -1)"\n'
        '  [ -n "$line" ] || exit 1\n'
        '  echo "${line%% *}"\n'
        "fi\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FFCORE_VERSION": "9.9.9"}
    return {"env": env, "ids": ids, "calls": calls}


def _run(script, *args, env):
    return subprocess.run(
        ["bash", str(OFFLINE / script), *args], env=env, capture_output=True, text=True
    )


# --- the lists ---


def test_19_4_images_txt_pins_match_compose():
    images = {row[0]: row for row in _lines("images.txt")}
    for name in (
        "pgvector/pgvector:0.8.1-pg16",
        "redis:7.4.6-alpine",
        "ghcr.io/berriai/litellm:v1.80.0-stable",
    ):
        assert name in COMPOSE and name in images
    for pinned in re.findall(r"image: \$\{REGISTRY_PREFIX\}(\S+)@(sha256:[0-9a-f]{64})", COMPOSE):
        ref, digest = pinned
        if "playwright" in ref:
            continue  # e2e only, never on the server
        base = ref if ref in images else next(k for k in images if k.startswith(ref))
        assert images[base][1] == digest, ref
    assert {r[2] for r in images.values() if r[1] == "local-build"} == {"PENDING"}
    for row in images.values():
        assert row[1] == "local-build" or re.fullmatch(r"sha256:[0-9a-f]{64}", row[1])
        assert row[2] == "PENDING" or re.fullmatch(r"sha256:[0-9a-f]{64}", row[2])


def test_19_s3_models_txt_has_revisions_and_hashes():
    rows = _lines("models.txt")
    repos = {(r[0], r[1]) for r in rows}
    assert {
        ("hf", "BAAI/bge-m3"),
        ("hf", "BAAI/bge-reranker-v2-m3"),
        ("paddle", "paddleocr"),
    } <= repos
    for kind, _, rev, _, sha, size in rows:
        assert kind == "paddle" or re.fullmatch(r"[0-9a-f]{40}", rev)
        assert re.fullmatch(r"[0-9a-f]{64}", sha) and int(size) > 0


# --- verify.sh ---


def test_19_4_verify_red_on_pending_and_mismatch(stub, tmp_path):
    result = _run("verify.sh", "--images", env=stub["env"])
    assert result.returncode == 1
    assert "PENDING" in result.stdout and "ffcore/backend:9.9.9" in result.stdout

    listed = tmp_path / "images.txt"
    listed.write_text(
        "redis:7.4.6-alpine sha256:aa sha256:1111 linux/amd64\n"
        "qdrant/qdrant:v1.11.3 sha256:bb sha256:2222 linux/amd64\n",
        encoding="utf-8",
    )
    stub["ids"].write_text(
        "sha256:1111 nexus.example.test/redis:7.4.6-alpine\n"
        "sha256:9999 nexus.example.test/qdrant/qdrant:v1.11.3\n",
        encoding="utf-8",
    )
    env = stub["env"] | {"IMAGES_TXT": str(listed), "REGISTRY_PREFIX": "nexus.example.test/"}
    result = _run("verify.sh", "--images", env=env)
    assert result.returncode == 1
    assert "OK image nexus.example.test/redis:7.4.6-alpine" in result.stdout
    assert "FAIL image nexus.example.test/qdrant/qdrant:v1.11.3: id differs" in result.stdout

    stub["ids"].write_text(
        "sha256:1111 nexus.example.test/redis:7.4.6-alpine\n"
        "sha256:2222 nexus.example.test/qdrant/qdrant:v1.11.3\n",
        encoding="utf-8",
    )
    assert _run("verify.sh", "--images", env=env).returncode == 0


def test_19_4_verify_models(stub, tmp_path):
    models = tmp_path / "m"
    weight = models / "huggingface/hub/models--BAAI--bge-m3/snapshots/" / ("a" * 40) / "w.bin"
    weight.parent.mkdir(parents=True)
    weight.write_bytes(b"weights")
    digest = hashlib.sha256(b"weights").hexdigest()
    listed = tmp_path / "models.txt"
    listed.write_text(f"hf BAAI/bge-m3 {'a' * 40} w.bin {digest} 7\n", encoding="utf-8")
    env = stub["env"] | {"MODELS_TXT": str(listed)}
    assert _run("verify.sh", "--models", str(models), env=env).returncode == 0
    weight.write_bytes(b"tampered")
    result = _run("verify.sh", "--models", str(models), env=env)
    assert result.returncode == 1 and "w.bin: sha256 or size differs" in result.stdout


# --- load.sh ---


def _archive(tmp_path, files: dict[str, bytes]) -> Path:
    out = tmp_path / "archive"
    for name, data in files.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(data)
    _rehash(out)
    return out


def _rehash(out: Path) -> None:
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "manifest.sha256")
    (out / "manifest.sha256").write_text(
        "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()} *{p.relative_to(out).as_posix()}\n"
            for p in files
        ),
        encoding="utf-8",
    )


def _empty_tar(path: Path) -> None:
    with tarfile.open(path, "w"):
        pass


def test_19_4_manifest_vs_archive(stub, tmp_path):
    archive = _archive(
        tmp_path, {"images/redis.tar": b"r", "images/qdrant.tar": b"q", "models.tar": b"m"}
    )
    models = str(tmp_path / "models")
    result = _run("load.sh", str(archive), "--models-dir", models, "--dry-run", env=stub["env"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("docker load -i") == 2
    assert f"verify.sh --images --models {models}" in result.stdout

    (archive / "images" / "extra.tar").write_bytes(b"x")  # not in the manifest
    result = _run("load.sh", str(archive), "--models-dir", models, "--dry-run", env=stub["env"])
    assert result.returncode == 1 and "differ" in result.stderr

    (archive / "images" / "extra.tar").unlink()
    (archive / "images" / "redis.tar").write_bytes(b"tampered")
    result = _run("load.sh", str(archive), "--models-dir", models, env=stub["env"])
    assert result.returncode == 1
    calls = stub["calls"]
    assert not calls.exists() or "load -i" not in calls.read_text(encoding="utf-8")


def test_19_s3_load_verifies_against_the_repo_list(stub, tmp_path):
    # An images.txt shipped inside the archive is ignored: the repo's list decides.
    archive = _archive(
        tmp_path,
        {"images/redis.tar": b"r", "images.txt": b"redis:7.4.6-alpine x sha256:1 y\n"},
    )
    _empty_tar(archive / "models.tar")
    _rehash(archive)
    result = _run("load.sh", str(archive), "--models-dir", str(tmp_path / "m"), env=stub["env"])
    assert result.returncode == 1
    assert "PENDING" in result.stdout  # the repo's images.txt was the one checked


@pytest.mark.parametrize("script", ["save.sh", "load.sh", "verify.sh"])
def test_19_2_offline_scripts_help(script, stub):
    result = _run(script, "--help", env=stub["env"])
    assert result.returncode == 0 and result.stdout.strip()


def test_19_2_save_dry_run_lists_every_image(stub, tmp_path):
    result = _run("save.sh", str(tmp_path / "out"), "--dry-run", env=stub["env"])
    assert result.returncode == 0, result.stderr
    third_party = [r for r in _lines("images.txt") if r[1] != "local-build"]
    assert result.stdout.count("docker pull") == len(third_party)
    assert result.stdout.count("docker save") == len(_lines("images.txt"))
    assert "models.tar" in result.stdout and "manifest.sha256" in result.stdout
