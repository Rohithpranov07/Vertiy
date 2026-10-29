"""Deterministic, stratified (label x language) dev/test split of the labelled set."""

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

from scripts.validate_labelled import COLUMNS, read_raw, validate
from verity.config import get_settings

FULL_SIZE = 300
FULL_TEST = 100


def split(
    rows: list[dict[str, str]], seed: int
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    n = len(rows)
    test_target = round(n * FULL_TEST / FULL_SIZE)
    strata: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["id"]):
        strata[(r["label"], r["language"])].append(r)
    rng = random.Random(seed)
    quotas: dict[tuple[str, str], int] = {}
    remainders: list[tuple[float, tuple[str, str]]] = []
    for key in sorted(strata):
        exact = len(strata[key]) * test_target / n
        quotas[key] = int(exact)
        remainders.append((exact - int(exact), key))
    short = test_target - sum(quotas.values())
    for _, key in sorted(remainders, key=lambda t: (-t[0], t[1]))[:short]:
        quotas[key] += 1
    dev: list[dict[str, str]] = []
    test: list[dict[str, str]] = []
    for key in sorted(strata):
        group = list(strata[key])
        rng.shuffle(group)
        test.extend(group[: quotas[key]])
        dev.extend(group[quotas[key] :])
    return sorted(dev, key=lambda r: r["id"]), sorted(test, key=lambda r: r["id"])


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out", type=Path, default=Path("eval/labelled"))
    ap.add_argument("--allow-small", action="store_true")
    args = ap.parse_args(argv)

    problems = validate(args.csv)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        print("refusing to split: fix validation problems first", file=sys.stderr)
        return 1
    _, rows = read_raw(args.csv)
    if len(rows) < FULL_SIZE:
        if not args.allow_small:
            print(
                f"REFUSING: only {len(rows)} rows, need {FULL_SIZE}. "
                "Pass --allow-small to split anyway (NOT for real evaluation).",
                file=sys.stderr,
            )
            return 1
        print(f"WARNING: splitting only {len(rows)} rows; metrics will be unreliable.")
    dev, test = split(rows, get_settings().random_seed)
    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "dev.csv", dev)
    _write(args.out / "test.csv", test)
    print(f"dev={len(dev)} test={len(test)} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
