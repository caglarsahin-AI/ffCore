"""Sample channels for scripts/kanal_ozet.py tests.

Unique module name: tests/hooks imports its own `conftest` by name.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "kanal_ozet.py"
SHA_A = "1111111111111111111111111111111111111111"
SHA_B = "2222222222222222222222222222222222222222"
SHA_C = "3333333333333333333333333333333333333333"

KOORDINATOR = f"""# Kanal: koordinator

## Mesajlar

### K-01-0001 · 2026-11-01 09:00 · → isci-a (01) · GOREV (eski biçim)
eski biçimli mesaj; sayılır ama değerlendirilmez

### K-X1-0001 · 2026-11-16 10:00 · → isci-a · GOREV
Paket: fix/x1 · Cevap: -
iş

### K-X1-0002 · 2026-11-16 12:00 · → inceleyici · REVIEW-ISTEK
Paket: fix/x1 · Cevap: A-X1-0002 · SHA: {SHA_A}
incele

### K-X1-0003 · 2026-11-16 14:00 · → isci-a · DUZELT
Paket: fix/x1 · Cevap: R-X1-0001
düzelt

### K-X1-0004 · 2026-11-16 11:40 · → isci-a · DUZELT
Paket: fix/x1 · Cevap: -
ACK yok, PR-HAZIR ile cevaplanır

### K-X1-0005 · 2026-11-16 11:41 · → isci-a · GOREV
Paket: fix/x1 · Cevap: -
başka kanaldan cevap sayılmaz

### K-X2-0001 · 2026-11-16 10:30 · → isci-b · GOREV
Paket: fix/x2 · Cevap: -
iş

### K-GEN-0001 · 2026-11-16 15:00 · → tumu · DURUM
Paket: - · Cevap: - · Durum: DUYURU
duyuru

### K-X2-0002 · 2026-11-16 16:00 · → tumu · MERGED
Paket: fix/x2 · Cevap: R-X2-0002
merge
"""

ISCI_A = f"""# Kanal: isci-a

```
### <ID> · <YYYY-MM-DD HH:MM> · → <alici> · <TUR>
```

## Mesajlar

### A-X1-0001 · 2026-11-16 10:05 · → koordinator · ACK
Paket: fix/x1 · Cevap: K-X1-0001

### A-X1-0002 · 2026-11-16 11:00 · → koordinator · PR-HAZIR
Paket: fix/x1 · Cevap: K-X1-0001 · SHA: {SHA_A}

### A-X1-0004 · 2026-11-16 11:45 · → koordinator · CEVAP
Paket: fix/x1 · Cevap: K-X1-0004

### A-X1-0003 · 2026-11-16 11:30 · → koordinatör · DURUM
biçim dışı (alıcı)
"""

INCELEYICI = f"""# Kanal: inceleyici

## Mesajlar

### R-X1-0000 · 2026-11-16 12:05 · → koordinator · ACK
Paket: fix/x1 · Cevap: K-X1-0002

### R-X1-0009 · 2026-11-16 12:10 · → koordinator · CEVAP
Paket: fix/x1 · Cevap: K-X1-0005

### R-X1-0001 · 2026-11-16 13:00 · → koordinator · REVIEW-SONUC
Paket: fix/x1 · Cevap: K-X1-0002 · SHA: {SHA_A} · Sonuc: DEGISIKLIK · Bulgu: B0 M1 m0 N0
"""

ARSIV_ISCI_B = f"""# Arşiv: isci-b fix/x2

### B-X2-0001 · 2026-11-16 10:40 · → koordinator · ACK
Paket: fix/x2 · Cevap: K-X2-0001, K-GEN-0001

### R-X2-0001 · 2026-11-16 13:00 · → koordinator · REVIEW-SONUC
Paket: fix/x2 · Cevap: - · SHA: {SHA_B} · Sonuc: ONAY · Bulgu: B0 M0 m1 N0

### R-X2-0002 · 2026-11-16 14:30 · → koordinator · REVIEW-SONUC
Paket: fix/x2 · Cevap: - · SHA: {SHA_C} · Sonuc: ONAY · Bulgu: B0 M0 m0 N0

### B-X2-0002 · 2026-11-16 14:00 · → kullanici · DURUM
Paket: fix/x2 · Cevap: - · Durum: VERIFIED
"""

WORK_QUEUE = """# İş kuyruğu

| Paket | Durum | İşçi | Branch | Son mesaj ID |
|---|---|---|---|---|
| fix/x1 | REVIEW | A | fix/x1 | R-X1-0001 |
| fix/x2 | MERGED | B | fix/x2 | K-X2-0002 |
| fix/x3 | PLANNED | C | fix/x3 | - |
"""


def make_sample_root(tmp_path: Path) -> Path:
    root = tmp_path / "ffcore"
    kanal = root / "state" / "kanal"
    (kanal / "arsiv").mkdir(parents=True)
    (kanal / "koordinator.md").write_text(KOORDINATOR, encoding="utf-8")
    (kanal / "isci-a.md").write_text(ISCI_A, encoding="utf-8")
    (kanal / "inceleyici.md").write_text(INCELEYICI, encoding="utf-8")
    (kanal / "arsiv" / "isci-b-fix-x2.md").write_text(ARSIV_ISCI_B, encoding="utf-8")
    (root / "state" / "WORK_QUEUE.md").write_text(WORK_QUEUE, encoding="utf-8")
    return root


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
