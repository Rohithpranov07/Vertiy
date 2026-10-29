"""Reply card: a deterministic, polite template. No model writes any text."""

from dataclasses import dataclass

from verity.config import get_settings
from verity.schemas import BNNode, Match, Reason, VerdictLabel

REASON_TEXT: dict[tuple[BNNode, str], str] = {
    ("fact_check", "refuted"): "a published fact-check rates a matching claim as false",
    ("fact_check", "supported"): "a published fact-check supports a matching claim",
    ("fact_check", "none"): "no published fact-check matched it",
    ("corroboration", "yes"): "a trusted news outlet reports something similar",
    ("corroboration", "no"): "no trusted news outlet was found reporting it",
    ("sensational", "high"): "it is worded in an alarming way",
    ("sensational", "low"): "it is worded calmly",
    ("specifics", "yes"): "it gives checkable details such as names, dates or places",
    ("specifics", "no"): "it gives very few checkable details",
    ("source_cred", "trusted"): "it links to a trusted source",
    ("source_cred", "unknown"): "its source is unknown",
    ("source_cred", "low"): "it links to a low-credibility or look-alike site",
}

OPENING: dict[VerdictLabel, str] = {
    "likely_false": "Hi, I checked this message and it looks likely to be false",
    "unverified": "Hi, I checked this message but could not confirm it either way",
    "likely_true": "Hi, I checked this message and it looks likely to be true",
}
CLOSING: dict[VerdictLabel, str] = {
    "likely_false": "Please hold off on forwarding it.",
    "unverified": "Until a reliable source reports it, it is best not to forward it.",
    "likely_true": "It is still worth checking the source before forwarding.",
}


@dataclass(frozen=True)
class ReplyParts:
    verdict: VerdictLabel
    reasons: list[Reason]
    matches: list[Match]


def reply_card(parts: ReplyParts) -> str:
    """Verdict wording + one sentence for the top reason + the best fact-check link."""
    sentences = [OPENING[parts.verdict]]
    if parts.reasons:
        top = parts.reasons[0]
        why = REASON_TEXT.get((top.node, top.state))
        if why:
            sentences[0] += f": {why}"
    text = sentences[0] + "."
    if parts.matches:
        best = max(parts.matches, key=lambda m: m.similarity)
        text += f" Fact-check ({best.publisher}): {best.url}."
    full = f"{text} {CLOSING[parts.verdict]}"
    return full if len(full) <= get_settings().reply_max_chars else text
