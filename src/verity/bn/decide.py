"""The ONLY place a verdict label is computed."""

from verity.schemas import Posterior, VerdictLabel


def decide(posterior: Posterior, threshold: float) -> VerdictLabel:
    """p_false >= threshold -> likely_false; p_true >= threshold -> likely_true; else unverified."""
    if posterior.p_false >= threshold:
        return "likely_false"
    if posterior.p_true >= threshold:
        return "likely_true"
    return "unverified"
