"""08 tam 1c-b r1 MINOR-4 (K-08T1C-0024): only the models.txt files reach the offline package.

A volume filled by `make models` before 1c-b still holds the unlicensed candidate
(`models--savasy--...`) and pickle weights (`pytorch_model.bin`). `verify.sh --models` names
every model directory and snapshot file that models.txt does not list (fail-loud, nothing is
deleted), and `save.sh` packs only the listed files (plus the repos' `refs/`), resolved through
the hub symlinks, via `models-files.sh`.
"""

import hashlib
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OFFLINE = REPO / "deploy" / "offline"
REV = "a" * 40


def _run(script, *args, env=None):
    return subprocess.run(
        ["bash", str(OFFLINE / script), *args],
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
    )


def _volume(tmp_path) -> tuple[Path, Path]:
    """A model_cache tree: one listed repo (snapshot files are symlinks into blobs, as the
    hub writes them), an extra pickle in its snapshot and an unlisted repo."""
    models = tmp_path / "m"
    hub = models / "huggingface" / "hub"
    repo = hub / "models--acme--ner"
    (repo / "blobs").mkdir(parents=True)
    (repo / "refs").mkdir()
    (repo / "refs" / "main").write_text(REV, encoding="utf-8")
    snap = repo / "snapshots" / REV
    snap.mkdir(parents=True)
    rows = []
    for name, data in (("config.json", b"{}"), ("model.safetensors", b"weights")):
        blob = repo / "blobs" / hashlib.sha1(data).hexdigest()
        blob.write_bytes(data)
        (snap / name).symlink_to(os.path.relpath(blob, snap))
        rows.append(f"hf acme/ner {REV} {name} {hashlib.sha256(data).hexdigest()} {len(data)}")
    (models / "paddleocr" / "det").mkdir(parents=True)
    (models / "paddleocr" / "det" / "inference.pdiparams").write_bytes(b"p")
    rows.append(f"paddle paddleocr - det/inference.pdiparams {hashlib.sha256(b'p').hexdigest()} 1")
    listed = tmp_path / "models.txt"
    listed.write_text("# kind repo revision path sha256 bytes\n" + "\n".join(rows) + "\n")
    return models, listed


def test_08t1c_12_verify_passes_a_clean_volume(tmp_path):
    models, listed = _volume(tmp_path)
    env = os.environ | {"MODELS_TXT": str(listed)}
    result = _run("verify.sh", "--models", str(models), env=env)
    assert result.returncode == 0, result.stdout + result.stderr


def test_08t1c_12b_verify_names_unlisted_model_dirs_and_files(tmp_path):
    models, listed = _volume(tmp_path)
    hub = models / "huggingface" / "hub"
    (hub / "models--savasy--ner" / "snapshots" / REV).mkdir(parents=True)
    (hub / "models--savasy--ner" / "snapshots" / REV / "pytorch_model.bin").write_bytes(b"x")
    pickle = hub / "models--acme--ner" / "snapshots" / REV / "pytorch_model.bin"
    pickle.write_bytes(b"pickle")
    env = os.environ | {"MODELS_TXT": str(listed)}
    result = _run("verify.sh", "--models", str(models), env=env)
    assert result.returncode == 1
    out = result.stdout
    assert "FAIL model dir models--savasy--ner: not in models.txt" in out
    assert f"FAIL model acme/ner {REV}/pytorch_model.bin: not in models.txt" in out
    assert "OK models" not in out
    assert pickle.exists()  # verify names, never deletes


def test_08t1c_12c_models_files_lists_only_the_listed_files(tmp_path):
    _, listed = _volume(tmp_path)
    result = _run("models-files.sh", str(listed))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "huggingface/hub/models--acme--ner/refs",
        f"huggingface/hub/models--acme--ner/snapshots/{REV}/config.json",
        f"huggingface/hub/models--acme--ner/snapshots/{REV}/model.safetensors",
        "paddleocr/det/inference.pdiparams",
    ]


def test_08t1c_12d_save_packs_only_the_listed_files(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (bin_dir / "docker").chmod(0o755)
    env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FFCORE_VERSION": "9.9.9"}
    result = _run("save.sh", str(tmp_path / "out"), "--dry-run", env=env)
    assert result.returncode == 0, result.stderr
    tar_line = next(line for line in result.stdout.splitlines() if "models.tar" in line)
    assert "models-files.sh /offline/models.txt" in tar_line
    assert "tar --dereference" in tar_line and "--files-from=-" in tar_line
    assert "-C /models ." not in tar_line  # never the whole volume


def test_08t1c_12e_packed_tree_loads_offline(tmp_path):
    """The packed files (symlinks resolved) are a valid hub tree: verify passes on it."""
    import tarfile

    models, listed = _volume(tmp_path)
    (models / "huggingface" / "hub" / "models--savasy--ner").mkdir()
    names = _run("models-files.sh", str(listed)).stdout.split()
    archive = tmp_path / "models.tar"
    with tarfile.open(archive, "w", dereference=True) as tar:
        for name in names:
            tar.add(models / name, arcname=name)
    out = tmp_path / "loaded"
    with tarfile.open(archive) as tar:
        tar.extractall(out, filter="data")
    assert not (out / "huggingface" / "hub" / "models--savasy--ner").exists()
    env = os.environ | {"MODELS_TXT": str(listed)}
    result = _run("verify.sh", "--models", str(out), env=env)
    assert result.returncode == 0, result.stdout
