"""Exact inference by variable elimination (pgmpy). Unobserved nodes are marginalised out."""

import warnings
from functools import lru_cache
from pathlib import Path

from pgmpy.inference import VariableElimination

from verity.bn.network import cpt_path_in_use, get_network
from verity.schemas import PartialEvidence, Posterior


def _observed(evidence: PartialEvidence) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((k, v) for k, v in evidence.model_dump().items() if v is not None))


@lru_cache(maxsize=4096)
def _infer(observed: tuple[tuple[str, str], ...], path: str, mtime_ns: int) -> Posterior:
    model = get_network(Path(path))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = VariableElimination(model).query(
            ["claim_true"],
            evidence=dict(observed),  # type: ignore[arg-type]  # pgmpy accepts state names
            show_progress=False,
        )
    p_true = float(result.get_value(claim_true="true"))
    return Posterior(p_true=p_true, p_false=1.0 - p_true)


def infer(evidence: PartialEvidence, cpt_path: Path | None = None) -> Posterior:
    """P(claim_true | evidence), exact. Memoised per (evidence, CPT file version)."""
    path = cpt_path or cpt_path_in_use()
    return _infer(_observed(evidence), str(path), path.stat().st_mtime_ns)
