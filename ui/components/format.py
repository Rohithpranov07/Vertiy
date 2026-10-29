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


DOT_COLORS: dict[VerdictLabel, str] = {  # semantic accents only: sale / neutral / success
    "likely_false": "#d30005",
    "unverified": "#9e9ea0",
    "likely_true": "#007d48",
}


def verdict_card_html(record: VerdictRecord) -> str:
    """HTML for the verdict block. Only enum-derived text and numbers go into the markup."""
    label = html.escape(VERDICT_TEXT[record.verdict])
    note = html.escape(VERDICT_NOTE[record.verdict])
    width = max(0, min(100, round(record.p_true * 100)))
    return (
        '<div class="v-verdict">'
        f'<span class="v-cap"><span class="dot" style="background:{DOT_COLORS[record.verdict]}">'
        "</span>Verdict</span>"
        f'<div class="label">{label}</div>'
        f'<div class="p">{percent(record.p_true)} chance the claim is true</div>'
        f'<div class="v-bar"><i style="width:{width}%"></i></div>'
        f'<div class="v-cap" style="margin-top:12px">{note}</div></div>'
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


def network_dot(evidence: Evidence, p_true: float, verdict: VerdictLabel) -> str:
    """Graphviz DOT for the belief network with observed states and P(true)."""
    ev = evidence.model_dump()

    def obs(node: BNNode) -> str:
        label = f"{NODE_TITLE[node]}\\n{ev[node]}"
        return (
            f'{node} [label="{label}", shape=box, style="rounded,filled", '
            'fillcolor="#f5f5f5", color="#111111"];'
        )

    claim = (
        f'claim_true [label="Claim is true\\nP(true) = {percent(p_true)}", shape=ellipse, '
        f'style=filled, fillcolor="#111111", fontcolor="#ffffff", color="#111111"];'
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


def _esc(value: object) -> str:
    return html.escape(str(value))


def section_html(title: str) -> str:
    return f'<div class="v-section"><div class="v-h1" role="heading" aria-level="2">{_esc(title)}</div></div>'


def claim_html(claim_text: str) -> str:
    text = _esc(claim_text) if claim_text else "(no claim sentence found)"
    return (
        '<div class="v-section"><div class="v-cap">The claim Verity read</div>'
        f'<div class="v-h2" style="margin-top:8px">{text}</div></div>'
    )


def notice_html(text: str) -> str:
    return f'<div class="v-note">{_esc(text)}</div>'


def warning_html(text: str) -> str:
    return f'<div class="v-note"><span class="tag">Warning</span>{_esc(text)}</div>'


def lookalike_text(flag_kind: str, domain: str, of: str | None, distance: int | None) -> str:
    if flag_kind == "lookalike":
        return (
            f"The link to {domain} looks like {of} (edit distance {distance}) but is a different "
            "site. The source is treated as low credibility."
        )
    return (
        f"{domain} is a link shortener, so the real destination is hidden. "
        "The source is treated as unknown."
    )


def matches_html(record: VerdictRecord) -> str:
    if not record.matches:
        return '<div class="v-cap" style="margin-top:12px">No published fact-check matched this claim.</div>'
    rows = []
    for m in record.matches:
        link = safe_link(m.url)
        name = (
            f'<a href="{_esc(link)}" target="_blank" rel="noopener">{_esc(m.publisher)}</a>'
            if link
            else _esc(m.publisher)
        )
        rows.append(
            f'<div class="v-row"><div><b>{name}</b>'
            f'<div class="v-cap">Similarity {m.similarity:.2f}</div></div>'
            f'<span class="v-pill">Rated {_esc(m.rating)}</span></div>'
        )
    return "".join(rows)


def family_html(record: VerdictRecord) -> str | None:
    fam = record.family
    if fam is None:
        return None
    if fam.source == "variant":
        tail = "An edited copy of a rumour that has a published fact-check."
    elif fam.source == "existing":
        tail = "Similar messages have been checked before."
    else:
        tail = "First time this rumour is seen."
    return (
        f'<div class="v-cap" style="margin-top:12px">Rumour family '
        f'<span class="v-pill">{_esc(fam.family_id)}</span> {_esc(tail)}</div>'
    )


def reasons_html(reasons: list[Reason]) -> str:
    rows = []
    for r in reasons:
        half = 60
        span = min(abs(r.shift) * 100 * 1.2, half)  # 1 point ~ 1.2px, capped at the half-width
        left = half if r.shift >= 0 else half - span
        cls = "" if r.shift >= 0 else ' class="neg"'
        rows.append(
            f'<div class="v-row"><div><b>{_esc(NODE_TITLE[r.node])}</b>'
            f'<div class="v-cap">{_esc(state_text(r.node, r.state))}</div></div>'
            f'<div><span class="v-mini"><i{cls} style="left:{left:.0f}px;width:{span:.0f}px"></i>'
            f'</span><span class="v-impact">{_esc(signed_points(r.shift))}</span></div></div>'
        )
    return "".join(rows)


def what_if_html(items: list[WhatIf], base_p_true: float) -> str:
    rows = [
        f'<div class="v-row"><div><b>{_esc(NODE_TITLE[w.node])}</b>'
        f'<div class="v-cap">If: {_esc(state_text(w.node, w.state))}</div></div>'
        f'<span class="v-impact">{percent(base_p_true)} to {percent(w.p_true)}</span></div>'
        for w in items
    ]
    return "".join(rows)
