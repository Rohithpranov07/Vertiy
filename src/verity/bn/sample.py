"""Likelihood weighting, written from scratch (Module 5.4). No library sampler."""

import random
from pathlib import Path

from verity.bn.network import PARENT, STATES, cpt_path_in_use, load_cpt_file
from verity.errors import ModelError
from verity.schemas import BNNode, PartialEvidence, Posterior

# topological order: parents before children
ORDER: list[BNNode] = [
    "source_cred",
    "claim_true",
    "fact_check",
    "corroboration",
    "sensational",
    "specifics",
]


def sample(evidence: PartialEvidence, n: int, seed: int, cpt_path: Path | None = None) -> Posterior:
    """Approximate P(claim_true | evidence) with n weighted samples."""
    tables = load_cpt_file(cpt_path or cpt_path_in_use()).tables
    observed = {k: v for k, v in evidence.model_dump().items() if v is not None}
    rng = random.Random(seed)
    weight_true = weight_false = 0.0
    for _ in range(n):
        state: dict[str, str] = {}
        weight = 1.0
        for node in ORDER:
            parent = PARENT[node]
            col = 0 if parent is None else STATES[parent].index(state[parent])
            probs = [row[col] for row in tables[node].values]
            if node in observed and node != "claim_true":
                state[node] = observed[node]
                weight *= probs[STATES[node].index(observed[node])]
            else:
                state[node] = rng.choices(STATES[node], weights=probs)[0]
        if state["claim_true"] == "true":
            weight_true += weight
        else:
            weight_false += weight
    total = weight_true + weight_false
    if total <= 0.0:
        raise ModelError("all samples had zero weight", code="sampling_failed")
    return Posterior(p_true=weight_true / total, p_false=weight_false / total)
