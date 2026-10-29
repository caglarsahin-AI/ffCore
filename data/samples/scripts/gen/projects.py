"""F10 data (plan/18): two projects for the isolation test that 13b seeds.

Each project has the three member kinds the test needs (admin/edit, admin/read,
analyst/edit; only 03a's assignable roles). Logins are role-shaped addresses on the reserved
.test domain, not names, and there is no password here: 13b's seed sets them the way
.env.test-based fixtures do. Project A gets the 13a contracts and agents; project B gets one
short procedure of its own, so B has something to see while A's resources stay invisible to it.
"""

import json
import random
from pathlib import Path

from . import write_text

MEMBERS = [("admin", "edit"), ("admin", "read"), ("analyst", "edit")]

PROJECTS = [
    {
        "key": "hastane-a",
        "name": "Örnek Şehir Hastanesi - Proje A",
        "knowledge_bases": [{"key": "sozlesmeler", "source": "contracts/"}],
        "agents": ["sozlesme-asistani", "veri-soru-cevap"],
    },
    {
        "key": "klinik-b",
        "name": "Örnek Şehir Hastanesi - Proje B",
        "knowledge_bases": [{"key": "b-prosedurler", "source": "projects/klinik-b/"}],
        "agents": ["sozlesme-asistani"],
    },
]

B_DOC_NAME = "b-el-hijyeni-proseduru.txt"
B_DOC = (
    "El Hijyeni Prosedürü (Proje B)\n\n"
    "1. Hasta temasından önce ve sonra eller en az 20 saniye yıkanır ya da alkol bazlı el "
    "antiseptiği kullanılır.\n\n"
    "2. El hijyeni uyumu her ay enfeksiyon kontrol hemşireliği tarafından gözlemle ölçülür.\n"
)

ISOLATION = {
    "viewer_project": "klinik-b",
    "target_project": "hastane-a",
    # every list, GET, search, tool call and run detail of these returns 404 to B's members
    "resources": ["knowledge_bases", "documents", "tools", "agents", "runs"],
    "expected_status": 404,
}


def _email(project_key: str, role: str, access: str) -> str:
    return f"{project_key}-{role}-{access}@example.test"


def document() -> dict:
    projects = []
    for p in PROJECTS:
        projects.append(
            {
                "key": p["key"],
                "name": p["name"],
                "members": [
                    {"email": _email(p["key"], role, access), "role": role, "access": access}
                    for role, access in MEMBERS
                ],
                "knowledge_bases": p["knowledge_bases"],
                "agents": p["agents"],
            }
        )
    return {"projects": projects, "isolation": ISOLATION}


def generate(rng: random.Random, out: Path, seed: int) -> None:
    # rng is unused: fixed content.
    base = out / "projects"
    write_text(base / "projects.json", json.dumps(document(), ensure_ascii=False, indent=2) + "\n")
    write_text(base / "klinik-b" / B_DOC_NAME, B_DOC)
