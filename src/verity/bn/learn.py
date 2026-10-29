"""Parameter learning: Bayesian estimation with the expert priors as pseudo-counts.

  python -m verity.bn.learn --csv eval/labelled/dev.csv

Pseudo-counts = CPT_EQUIVALENT_SAMPLE_SIZE x the prior probabilities, per parent
configuration, so empty cells never become zero. Refuses to read the test split.
"""

import argparse
import csv
import hashlib
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pgmpy.estimators import BayesianEstimator
from pgmpy.models import DiscreteBayesianNetwork

from verity import db
from verity.bn.evidence_table import Truth, build_table
from verity.bn.network import (
    EDGES,
    LEARNED_FILE,
    PRIORS_FILE,
    STATES,
    CptFile,
    CptTable,
    load_cpt_file,
    validate_cpts,
)
from verity.config import get_settings
from verity.cues.source import db_lookup
from verity.errors import InputError
from verity.retrieval import Retriever
from verity.schemas import BNNode, Evidence


def _guard(path: Path) -> None:
    if "test" in path.stem.lower():
        raise InputError(
            f"refusing to read {path.name}: the test split is never used for learning",
            code="test_split_refused",
        )


def learn_cpts(
    table: list[tuple[Evidence, Truth]], priors: CptFile, ess: int, dev_hash: str | None = None
) -> CptFile:
    """Estimate every CPT from the fully labelled table with the priors as pseudo-counts."""
    records = [{**ev.model_dump(), "claim_true": truth} for ev, truth in table]
    columns = list(STATES)
    data = pd.DataFrame(records, columns=columns)
    model = DiscreteBayesianNetwork(EDGES)
    model.add_nodes_from(columns)
    estimator = BayesianEstimator(model, data, state_names={k: v for k, v in STATES.items()})
    tables: dict[BNNode, CptTable] = {}
    for node in STATES:
        pseudo = np.array(priors.tables[node].values, dtype=float) * ess
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cpd = estimator.estimate_cpd(node, prior_type="dirichlet", pseudo_counts=pseudo)
        values = np.asarray(cpd.get_values(), dtype=float)
        tables[node] = CptTable(
            rationale=f"learned from {len(table)} labelled rows, prior weight {ess}",
            values=values.tolist(),
        )
    stamp = (dev_hash or "no-hash")[:12]
    learned = CptFile(
        source="learned-bayesian-estimation",
        status=None,
        dev_set_hash=dev_hash,
        version=f"learned-{stamp}-ess{ess}-n{len(table)}",
        tables=tables,
    )
    validate_cpts(learned)
    return learned


def diff_report(priors: CptFile, learned: CptFile) -> str:
    lines: list[str] = []
    for node in STATES:
        p, q = priors.tables[node].values, learned.tables[node].values
        lines.append(f"[{node}]")
        for r, state in enumerate(STATES[node]):
            cells = " ".join(f"{p[r][c]:.3f}->{q[r][c]:.3f}" for c in range(len(p[r])))
            lines.append(f"  {state:10s} {cells}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=Path("eval/labelled/dev.csv"))
    ap.add_argument("--out", type=Path, default=LEARNED_FILE)
    args = ap.parse_args(argv)
    try:
        _guard(args.csv)
    except InputError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    raw = args.csv.read_bytes()
    with args.csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with db.session() as conn:
        retriever = Retriever.load(conn)
        trusted = [d.domain for d in db.list_domains(conn) if d.cls == "trusted"]
        table = build_table(rows, retriever, db_lookup(conn), trusted)
    if not table:
        print("no true/false rows to learn from", file=sys.stderr)
        return 1
    priors = load_cpt_file(PRIORS_FILE)
    learned = learn_cpts(
        table, priors, get_settings().cpt_equivalent_sample_size, hashlib.sha256(raw).hexdigest()
    )
    args.out.write_text(json.dumps(learned.model_dump(), indent=2) + "\n", encoding="utf-8")
    print(diff_report(priors, learned))
    print(f"wrote {args.out} ({len(table)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
