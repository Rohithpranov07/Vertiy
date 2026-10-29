"""Pure presentation helpers (no Streamlit, no engine imports)."""

import html
from urllib.parse import urlparse

from verity.schemas import BNNode, Evidence, Reason, VerdictLabel, VerdictRecord, WhatIf

VERDICT_TEXT: dict[VerdictLabel, str] = {
    "likely_false": "Likely false",
    "unverified": "Unverified",
    "likely_true": "Likely true",
}
VERDICT_COLORS: dict[VerdictLabel, tuple[str, str]] = {  # (background, text)
    "likely_false": ("#fee4e2", "#912018"),
    "unverified": ("#fef0c7", "#93370d"),
    "likely_true": ("#d1fadf", "#05603a"),
}
VERDICT_NOTE: dict[VerdictLabel, str] = {
    "likely_false": "The evidence points against this message.",
    "unverified": "There is not enough evidence to call it either way.",
    "likely_true": "The evidence points in favour of this message.",
}
NODE_TITLE: dict[BNNode, str] = {
    "source_cred": "Source",
    "claim_true": "Claim is true",
    "fact_check": "Fact-check match",
    "corroboration": "Trusted-outlet report",
    "sensational": "Alarming wording",
    "specifics": "Checkable details",
}
STATE_TEXT: dict[tuple[BNNode, str], str] = {
    ("source_cred", "trusted"): "linked to a trusted source",
    ("source_cred", "unknown"): "source unknown",
    ("source_cred", "low"): "linked to a low-credibility or look-alike site",
    ("fact_check", "refuted"): "a fact-check says it is false",
    ("fact_check", "supported"): "a fact-check supports it",
    ("fact_check", "none"): "no fact-check found",
    ("corroboration", "yes"): "a trusted outlet reports it",
    ("corroboration", "no"): "no trusted outlet reports it",
    ("sensational", "high"): "alarming wording",
    ("sensational", "low"): "calm wording",
    ("specifics", "yes"): "has checkable details",
    ("specifics", "no"): "few checkable details",
}
REDACTION_NAMES = {
    "PHONE": "phone number",
    "EMAIL": "e-mail address",
    "UPI": "UPI handle",
    "CARD": "card number",
    "ID12": "12-digit ID number",
}


def state_text(node: BNNode, state: str) -> str:
    return STATE_TEXT.get((node, state), f"{node} = {state}")


def percent(p: float) -> str:
    return f"{round(p * 100)}%"


def verdict_card_html(record: VerdictRecord) -> str:
    """HTML for the verdict card. Only enum-derived text and numbers go into the markup."""
    bg, fg = VERDICT_COLORS[record.verdict]
    label = html.escape(VERDICT_TEXT[record.verdict])
    note = html.escape(VERDICT_NOTE[record.verdict])
    return (
        f'<div style="background:{bg};color:{fg};padding:1rem 1.25rem;border-radius:12px;'
        f'border:1px solid {fg}33">'
        f'<div style="font-size:1.6rem;font-weight:700">{label}</div>'
        f'<div style="margin-top:.25rem">Probability the claim is true: '
        f"<b>{percent(record.p_true)}</b></div>"
        f'<div style="margin-top:.25rem;opacity:.85">{note}</div></div>'
    )


_EFFECT_EPS = 0.005  # shifts smaller than half a point are shown as "no effect"


def signed_points(shift: float) -> str:
    pts = round(shift * 100)
    return f"{pts:+d} pts" if pts else "0 pts"


def reason_line(reason: Reason) -> str:
    direction = (
        "towards true"
        if reason.shift > 0.005
        else "towards false"
        if reason.shift < -0.005
        else "no effect"
    )
    return (
        f"{NODE_TITLE[reason.node]}: {state_text(reason.node, reason.state)} "
        f"({signed_points(reason.shift)}, {direction})"
    )


def what_if_sentence(item: WhatIf, base_p_true: float) -> str:
    return (
        f"If {NODE_TITLE[item.node].lower()} were '{state_text(item.node, item.state)}', "
        f"the probability the claim is true would move from {percent(base_p_true)} "
        f"to {percent(item.p_true)}."
    )


def safe_link(url: str) -> str | None:
    """Only http(s) URLs are rendered as links."""
    parsed = urlparse(url)
    return url if parsed.scheme in ("http", "https") and parsed.netloc else None


def redaction_notice(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    parts = [
        f"{n} {REDACTION_NAMES.get(kind, kind)}{'s' if n != 1 else ''}"
        for kind, n in counts.items()
    ]
    return (
        "Privacy shield removed " + ", ".join(parts) + " from your message before anything was "
        "stored or sent anywhere. Names and addresses are not removed."
    )


CHILDREN: tuple[BNNode, ...] = ("fact_check", "corroboration", "sensational", "specifics")
_FILL = {
    "likely_false": "#fee4e2",
    "unverified": "#fef0c7",
    "likely_true": "#d1fadf",
}


def network_dot(evidence: Evidence, p_true: float, verdict: VerdictLabel) -> str:
    """Graphviz DOT for the belief network with observed states and P(true)."""
    ev = evidence.model_dump()

    def obs(node: BNNode) -> str:
        label = f"{NODE_TITLE[node]}\\n{ev[node]}"
        return (
            f'{node} [label="{label}", shape=box, style="rounded,filled", '
            'fillcolor="#eef2ff", color="#4f46e5"];'
        )

    claim = (
        f'claim_true [label="Claim is true\\nP(true) = {percent(p_true)}", shape=ellipse, '
        f'style=filled, fillcolor="{_FILL[verdict]}", color="#444444"];'
    )
    lines = [
        "digraph G {",
        "rankdir=TB; bgcolor=transparent; node [fontname=Helvetica, fontsize=11];",
        obs("source_cred"),
        claim,
        *(obs(n) for n in CHILDREN),
        "source_cred -> claim_true;",
        *(
            f"claim_true -> {n};"
            for n in ("fact_check", "corroboration", "sensational", "specifics")
        ),
        "}",
    ]
    return "\n".join(lines)
