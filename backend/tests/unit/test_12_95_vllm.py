"""12-2: FOLLOWUP-95 (tools image without its own apt layer) and the vLLM serving path (5c).

Static checks; no image is built or pulled here. The vLLM image is pinned by its registry
manifest only (not pulled, K-12-0002 S5); GPU P50/P95 is NOT_RUN (PENDING_ENV).
"""

import re
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
DOCKERFILE = (REPO / "backend" / "Dockerfile").read_text(encoding="utf-8")
VLLM = REPO / "deploy" / "docker-compose.vllm.yml"
OFFLINE = REPO / "deploy" / "offline"
IMAGES = (OFFLINE / "images.txt").read_text(encoding="utf-8")
SEED = (REPO / "deploy" / "seed" / "models.airgap.yaml").read_text(encoding="utf-8")


def _stage(name):
    match = re.search(rf"^FROM .* AS {name}\n(.*?)(?=^FROM |\Z)", DOCKERFILE, re.M | re.S)
    assert match, name
    return match.group(1)


def test_12_95_tools_stage_has_no_apt_layer():
    assert "apt-get" not in _stage("tools")


def test_12_95_base_apt_layer_carries_make_and_curl():
    base = _stage("base")
    install = next(line for line in base.splitlines() if "apt-get install" in line)
    assert "make" in install.split() and "curl" in install.split()


def test_12_95_uv_index_can_point_at_an_internal_mirror():
    base = _stage("base")
    assert re.search(r"^ARG UV_INDEX_URL$", base, re.M)
    assert re.search(r"^ARG UV_FIND_LINKS$", base, re.M)


def test_12_95_wheels_script_help():
    script = REPO / "deploy" / "offline" / "wheels.sh"
    result = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "usage:" in result.stdout.lower()


def test_12_5c_vllm_overlay_service():
    service = yaml.safe_load(VLLM.read_text(encoding="utf-8"))["services"]["vllm"]
    image = service["image"]
    assert image.startswith("${REGISTRY_PREFIX}vllm/vllm-openai:v") and "latest" not in image
    assert service["profiles"] == ["vllm"]
    assert "ports" not in service  # internal network only; LiteLLM calls it
    assert service["mem_limit"].startswith("${VLLM_MEM_LIMIT:?")
    devices = service["deploy"]["resources"]["reservations"]["devices"]
    assert devices[0]["driver"] == "nvidia" and devices[0]["capabilities"] == ["gpu"]
    env = service["environment"]
    assert env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1"
    command = " ".join(service["command"])
    assert "--port 8000" in command
    # One name: what vLLM serves is what the seed registers (deploy/seed/models.airgap.yaml).
    assert "--served-model-name ${SEED_VLLM_MODEL:?" in command
    assert "--max-model-len ${VLLM_MAX_MODEL_LEN:?" in command
    volumes = service["volumes"]
    assert any(v.startswith("${VLLM_MODELS_DIR:?") and v.endswith(":/models:ro") for v in volumes)


def test_12_5c_seed_points_at_the_vllm_service():
    assert "${SEED_VLLM_BASE_URL:-http://vllm:8000}" in SEED
    assert "model_id: ${SEED_VLLM_MODEL}" in SEED


def test_12_5c_vllm_image_is_pinned_in_its_own_list():
    # Its own list: the CPU archive (images.txt, package 19) must not carry a ~10 GB GPU image.
    service = yaml.safe_load(VLLM.read_text(encoding="utf-8"))["services"]["vllm"]
    name = service["image"].removeprefix("${REGISTRY_PREFIX}")
    assert name not in IMAGES
    rows = (OFFLINE / "images-vllm.txt").read_text(encoding="utf-8").splitlines()
    line = next(row for row in rows if row.startswith(name + " "))
    _, digest, image_id, platform = line.split()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
    assert platform == "linux/amd64"


def test_12_5c_save_takes_another_image_list():
    save = (OFFLINE / "save.sh").read_text(encoding="utf-8")
    assert 'IMAGES="${IMAGES_TXT:-$HERE/images.txt}"' in save
    assert '"$HERE/images.txt"' not in save.replace('${IMAGES_TXT:-$HERE/images.txt}', "")
