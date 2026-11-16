"""scripts/kanal_ozet.py (fix/ajan-hooklari-2 D4, FOLLOWUP-189 b).

Summary of channel files: binding messages still waiting for an ACK, latest state per
package (WORK_QUEUE + last DURUM/PR-HAZIR/REVIEW-SONUC/MERGED), latest approved SHA,
and the count of old-format headers ("biçim dışı", not an error).
"""

from __future__ import annotations

import json

import pytest
from kanal_ornek import SHA_A, SHA_C, make_sample_root, run_script


@pytest.fixture
def sample_root(tmp_path):
    # no conftest.py here: tests/hooks modules import their own `conftest` by name
    return make_sample_root(tmp_path)


def summary(root) -> dict:
    proc = run_script("--json", "--root", str(root))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_json_schema(sample_root):
    data = summary(sample_root)
    assert set(data) == {
        "kok",
        "mesaj",
        "bicim_disi",
        "bekleyen_ack",
        "acksiz_cevaplanmis",
        "paketler",
    }
    for item in data["bekleyen_ack"]:
        assert set(item) == {"id", "tarih", "kaynak", "alici", "tur", "paket"}
    for item in data["acksiz_cevaplanmis"]:
        assert set(item) == {"id", "tarih", "kaynak", "alici", "tur", "paket", "cevap_id"}
    for info in data["paketler"].values():
        assert set(info) == {"work_queue", "son_durum", "son_onay_sha"}


def test_counts_valid_and_old_format(sample_root):
    data = summary(sample_root)
    # K-01-0001 (old), A-X1-0003 (koordinatör), B-X2-0002 (kullanici outside coordinator)
    assert data["bicim_disi"] == 3
    assert data["mesaj"] == 17


def test_pending_ack(sample_root):
    pending = {p["id"] for p in summary(sample_root)["bekleyen_ack"]}
    # K-X1-0001 ACKed by A-X1-0001, K-X1-0002 by R-X1-0000, K-X2-0001 by a multi-ID Cevap
    assert pending == {"K-X1-0003", "K-X1-0005"}


def test_pending_ack_item_fields(sample_root):
    item = next(p for p in summary(sample_root)["bekleyen_ack"] if p["id"] == "K-X1-0003")
    assert item == {
        "id": "K-X1-0003",
        "tarih": "2026-11-16 14:00",
        "kaynak": "state/kanal/koordinator.md",
        "alici": "isci-a",
        "tur": "DUZELT",
        "paket": "fix/x1",
    }


def test_package_state(sample_root):
    pkgs = summary(sample_root)["paketler"]
    assert pkgs["fix/x1"]["work_queue"] == "REVIEW"
    assert pkgs["fix/x1"]["son_durum"]["id"] == "R-X1-0001"
    assert pkgs["fix/x1"]["son_durum"]["tur"] == "REVIEW-SONUC"
    assert pkgs["fix/x2"]["son_durum"]["id"] == "K-X2-0002"
    assert pkgs["fix/x2"]["son_durum"]["tur"] == "MERGED"
    assert pkgs["fix/x3"] == {"work_queue": "PLANNED", "son_durum": None, "son_onay_sha": None}
    assert "-" not in pkgs


def test_latest_approved_sha(sample_root):
    pkgs = summary(sample_root)["paketler"]
    assert pkgs["fix/x1"]["son_onay_sha"] is None  # DEGISIKLIK is not an approval
    assert pkgs["fix/x2"]["son_onay_sha"] == SHA_C  # later ONAY wins (archive is read)


def test_text_output(sample_root):
    proc = run_script("--root", str(sample_root))
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "K-X1-0003" in out
    assert "biçim dışı: 3" in out
    assert SHA_C in out
    assert SHA_A not in out.split("ACK bekleyen")[0]


def test_missing_kanal_dir_is_loud(tmp_path):
    proc = run_script("--root", str(tmp_path))
    assert proc.returncode == 2
    assert "state/kanal" in proc.stderr


def test_real_channels_parse():
    """Smoke on the repository's own channels: runs, counts are sane."""
    proc = run_script("--json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["mesaj"] > 0 and data["bicim_disi"] >= 0


def test_answered_without_ack(sample_root):
    """r2 MINOR-3: a reply from the recipient's channel (Cevap names the ID) without an
    ACK is listed apart and leaves the pending list; a reply from another channel does not."""
    data = summary(sample_root)
    (item,) = data["acksiz_cevaplanmis"]
    assert item["id"] == "K-X1-0004"
    assert item["cevap_id"] == "A-X1-0004"
    assert "K-X1-0004" not in {p["id"] for p in data["bekleyen_ack"]}
    assert "K-X1-0005" in {p["id"] for p in data["bekleyen_ack"]}


def test_text_lists_answered_without_ack(sample_root):
    out = run_script("--root", str(sample_root)).stdout
    assert "ACK'siz cevaplanmış" in out
    assert "K-X1-0004" in out
