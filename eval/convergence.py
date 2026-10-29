"""Likelihood weighting vs exact inference: |approx - exact| P(true) against sample count.

python -m eval.convergence [--out eval/convergence.png]
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from verity.bn import infer, sample  # noqa: E402
from verity.config import get_settings  # noqa: E402
from verity.schemas import PartialEvidence  # noqa: E402

SAMPLE_COUNTS = [10, 100, 1000, 10000]
REPEATS = 20  # seeds averaged per sample count, so the trend is not one lucky draw

EXAMPLES: dict[str, PartialEvidence] = {
    "refuted, no corroboration": PartialEvidence(fact_check="refuted", corroboration="no"),
    "trusted, supported": PartialEvidence(source_cred="trusted", fact_check="supported"),
    "alarmist, no details": PartialEvidence(sensational="high", specifics="no"),
    "all five observed": PartialEvidence(
        source_cred="unknown",
        fact_check="none",
        corroboration="yes",
        sensational="low",
        specifics="yes",
    ),
}


def error_table() -> dict[str, list[float]]:
    seed = get_settings().random_seed
    table: dict[str, list[float]] = {}
    for name, ev in EXAMPLES.items():
        exact = infer(ev).p_true
        table[name] = [
            sum(abs(sample(ev, n, seed + r).p_true - exact) for r in range(REPEATS)) / REPEATS
            for n in SAMPLE_COUNTS
        ]
    return table


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("eval/convergence.png"))
    args = ap.parse_args(argv)
    table = error_table()
    print("mean |approx - exact| P(true), over", REPEATS, "seeds")
    print("example".ljust(28), *[f"n={n}".rjust(9) for n in SAMPLE_COUNTS])
    fig, ax = plt.subplots(figsize=(6, 4))
    for name, errs in table.items():
        print(name.ljust(28), *[f"{e:9.5f}" for e in errs])
        ax.plot(SAMPLE_COUNTS, errs, marker="o", label=name)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("number of samples")
    ax.set_ylabel("mean absolute error in P(true)")
    ax.set_title("Likelihood weighting converges to exact inference")
    ax.legend(fontsize=7)
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
