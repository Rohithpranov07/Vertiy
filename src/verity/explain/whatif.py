"""What-if hints: the alternative evidence state that would move P(true) the most."""

from verity.bn import infer
from verity.bn.network import EVIDENCE_NODES, STATES
from verity.schemas import BNNode, Evidence, PartialEvidence, WhatIf

TOP_N = 3


def what_if(evidence: Evidence) -> list[WhatIf]:
    """For each node, the other state with the largest |change in p_true|; top three nodes."""
    base = infer(PartialEvidence(**evidence.model_dump())).p_true
    order: dict[BNNode, int] = {n: i for i, n in enumerate(EVIDENCE_NODES)}
    best: list[tuple[float, BNNode, str, float]] = []
    for node in EVIDENCE_NODES:
        current = str(getattr(evidence, node))
        candidates: list[tuple[float, str, float]] = []
        for state in STATES[node]:
            if state == current:
                continue
            changed = evidence.model_dump()
            changed[node] = state
            p = infer(PartialEvidence(**changed)).p_true
            candidates.append((abs(p - base), state, p))
        delta, state, p = max(candidates, key=lambda c: (c[0], c[1] == "yes"))
        best.append((delta, node, state, p))
    best.sort(key=lambda t: (-t[0], order[t[1]]))
    return [WhatIf(node=node, state=state, p_true=p) for _, node, state, p in best[:TOP_N]]
