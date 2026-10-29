"""Reasons panel: how far each observed node moved P(true)."""

from verity.bn import infer
from verity.bn.network import EVIDENCE_NODES
from verity.schemas import BNNode, Evidence, PartialEvidence, Reason


def reasons(evidence: Evidence) -> list[Reason]:
    """shift(node) = p_true(all evidence) - p_true(evidence with node unobserved).

    Sorted by absolute shift, descending; ties keep the fixed node order.
    """
    full = infer(PartialEvidence(**evidence.model_dump())).p_true
    out: list[Reason] = []
    for node in EVIDENCE_NODES:
        partial = evidence.model_dump()
        partial[node] = None
        without = infer(PartialEvidence(**partial)).p_true
        out.append(Reason(node=node, state=str(getattr(evidence, node)), shift=full - without))
    order: dict[BNNode, int] = {n: i for i, n in enumerate(EVIDENCE_NODES)}
    return sorted(out, key=lambda r: (-abs(r.shift), order[r.node]))
