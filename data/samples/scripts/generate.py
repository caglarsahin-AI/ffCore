"""Generate FFCore synthetic sample data (package 13a).

Usage:
    py -3.12 data/samples/scripts/generate.py [--seed 13] [--out data/samples] [--only eval,pii]

Stdlib only. Every module gets its own random.Random seeded with "<seed>:<module>",
so regenerating one module never changes another and the output is byte-identical
for the same seed.
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen import (  # noqa: E402
    agents,
    contracts,
    memory,
    openapi,
    pii,
    poison,
    projects,
    scenarios_sql,
    schema,
    tickets,
    versions,
)
from gen import eval as eval_set  # noqa: E402

MODULES = {
    "contracts": contracts.generate,
    "eval": eval_set.generate,
    "schema": schema.generate,
    "agents": agents.generate,
    "openapi": openapi.generate,
    "pii": pii.generate,
    "memory": memory.generate,
    # package 18-hazirlik (plan/18 F2, F3, F11, F10, F13)
    "scenarios_sql": scenarios_sql.generate,
    "tickets": tickets.generate,
    "poison": poison.generate,
    "projects": projects.generate,
    "versions": versions.generate,
}
DEFAULT_SEED = 13
DEFAULT_OUT = Path(__file__).resolve().parents[1]


def module_rng(seed: int, name: str) -> random.Random:
    return random.Random(f"{seed}:{name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--only", default=",".join(MODULES), help=f"comma separated subset of: {', '.join(MODULES)}"
    )
    args = parser.parse_args(argv)

    selected = [m.strip() for m in args.only.split(",") if m.strip()]
    unknown = [m for m in selected if m not in MODULES]
    if unknown:
        parser.error(f"unknown module(s): {', '.join(unknown)}")

    for name in selected:
        MODULES[name](module_rng(args.seed, name), args.out, args.seed)
        print(f"generated {name} -> {args.out / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
