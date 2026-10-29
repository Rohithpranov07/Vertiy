"""Ablation: drop each evidence node in turn (marginalise it out) and re-score."""

from dataclasses import dataclass

from eval.metrics import TRUTH_TO_VERDICT, VERDICTS, macro_f1
from verity.bn import decide, infer
from verity.bn.network import EVIDENCE_NODES
from verity.schemas import Evidence, PartialEvidence, Posterior


@dataclass(frozen=True)
class EvidenceRow:
    label: str  # ground truth: false | true | unverifiable
    evidence: Evidence


def _verdict(evidence: Evidence, drop: str | None, threshold: float) -> str:
    data: dict[str, str | None] = dict(evidence.model_dump())
    if drop is not None:
        data[drop] = None
    post: Posterior = infer(PartialEvidence(**data))  # type: ignore[arg-type]
    return decide(post, threshold)


def ablate(rows: list[EvidenceRow], threshold: float) -> dict[str, tuple[float, float]]:
    """{node: (macro_f1_without_node, change_vs_full)} on the three-class task."""
    truth = [TRUTH_TO_VERDICT[r.label] for r in rows]
    full = macro_f1(truth, [_verdict(r.evidence, None, threshold) for r in rows], VERDICTS)
    out: dict[str, tuple[float, float]] = {"(none dropped)": (full, 0.0)}
    for node in EVIDENCE_NODES:
        score = macro_f1(truth, [_verdict(r.evidence, node, threshold) for r in rows], VERDICTS)
        out[node] = (score, score - full)
    return out
