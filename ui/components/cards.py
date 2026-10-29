"""HTML builders for tiles, bento blocks, rows and chips (pure; no Streamlit).

Every dynamic value is escaped. Only enum-derived text and numbers reach the markup raw.
"""

import html
from collections.abc import Mapping
from datetime import datetime

from components.format import (
    DOT_COLORS,
    NODE_TITLE,
    VERDICT_NOTE,
    VERDICT_TEXT,
    percent,
    safe_link,
    state_text,
)
from verity.schemas import (
    BNNode,
    ClaimRecord,
    HealthResponse,
    Passport,
    RadarItem,
    VerdictLabel,
    VerdictRecord,
)

REDACTION_LABEL = {
    "PHONE": "Phone numbers",
    "EMAIL": "E-mail addresses",
    "UPI": "UPI handles",
    "CARD": "Card numbers",
    "ID12": "12-digit ID numbers",
}
FAMILY_LABEL = {"variant": "Edited copy", "existing": "Seen before", "new": "First sighting"}
CLAIM_CHARS = 140


def _e(value: object) -> str:
    return html.escape(str(value))


def tile(value: str, label: str) -> str:
    return (
        f'<div class="v-tile"><div class="num">{_e(value)}</div>'
        f'<div class="v-cap">{_e(label)}</div></div>'
    )


def stat_tiles_html(health: HealthResponse) -> str:
    refreshed = "Never"
    if health.last_refresh:
        try:
            refreshed = datetime.fromisoformat(health.last_refresh).strftime("%d %b %Y")
        except ValueError:
            refreshed = health.last_refresh[:10]
    return (
        '<div class="v-tiles">'
        + tile(f"{health.factchecks:,}", "Published fact-checks indexed")
        + tile(f"{health.headlines:,}", "Trusted news headlines")
        + tile(f"{health.domains:,}", "Rated website domains")
        + tile(refreshed, "Fact-checks last refreshed")
        + "</div>"
    )


def bento_html() -> str:
    return (
        '<div class="v-bento">'
        '<div class="c a ink"><div class="v-h1" role="heading" aria-level="3">Reasons, not rulings</div>'
        "<p>Every verdict comes with the evidence behind it: the fact-checks it matched, "
        "what pushed the probability up or down, and what would change it.</p></div>"
        '<div class="c b"><h4>Privacy shield</h4><p>Phone, e-mail, UPI, card and ID numbers '
        "are removed before anything is stored or sent.</p></div>"
        '<div class="c c3"><h4>Link guard</h4><p>Flags look-alike domains and shortened links '
        "that hide where they lead.</p></div>"
        '<div class="c d line"><h4>Rumour fingerprint</h4><p>An edited copy of a known rumour '
        "still finds its fact-check.</p></div>"
        '<div class="c e"><h4>Evidence passport</h4><p>The same message, data and settings give '
        "the same verdict and the same id.</p></div></div>"
    )


STEPS = (
    ("Clean", "Private details are removed from your message on this device first."),
    ("Find", "The claim is pulled out and matched against published fact-checks."),
    ("Weigh", "Source, wording, details and news coverage are combined in a belief network."),
    ("Explain", "You get a verdict, the reasons for it and what would change it."),
)


def steps_html() -> str:
    cells = "".join(
        f'<div class="s"><div class="n">{i}</div><h4>{_e(t)}</h4><p>{_e(d)}</p></div>'
        for i, (t, d) in enumerate(STEPS, start=1)
    )
    return f'<div class="v-steps">{cells}</div>'


def verdict_guide_html() -> str:
    order: tuple[VerdictLabel, ...] = ("likely_false", "unverified", "likely_true")
    extra = {
        "likely_false": "Check the linked fact-checks before you forward.",
        "unverified": "Verity would rather say this than guess. Look for a trusted source.",
        "likely_true": "Still worth a glance at the sources it links.",
    }
    rows = "".join(
        '<div class="v-row"><div style="flex:1;min-width:200px">'
        f'<span class="v-cap"><span class="dot" style="background:{DOT_COLORS[v]};display:inline-block;'
        f'width:10px;height:10px;border-radius:9999px;margin-right:10px"></span>{_e(VERDICT_TEXT[v])}'
        f'</span></div><div style="flex:2;min-width:240px"><b>{_e(VERDICT_NOTE[v])}</b>'
        f'<div class="v-cap">{_e(extra[v])}</div></div></div>'
        for v in order
    )
    return rows


def metrics_html(record: VerdictRecord) -> str:
    family = FAMILY_LABEL[record.family.source] if record.family else "None"
    removed = sum(record.redactions.values())
    return (
        '<div class="v-tiles">'
        + tile(percent(record.p_true), "Chance the claim is true")
        + tile(str(len(record.matches)), "Fact-checks matched")
        + tile(str(removed), "Private details removed")
        + tile(family, "Rumour family")
        + "</div>"
    )


def signals_html(record: VerdictRecord) -> str:
    ev = record.evidence
    pairs: tuple[tuple[BNNode, str], ...] = (
        ("source_cred", ev.source_cred),
        ("fact_check", ev.fact_check),
        ("corroboration", ev.corroboration),
        ("sensational", ev.sensational),
        ("specifics", ev.specifics),
    )
    cells = "".join(
        f'<div class="v-sig"><div class="v-cap">{_e(NODE_TITLE[n])}</div>'
        f"<b>{_e(state_text(n, s))}</b></div>"
        for n, s in pairs
    )
    return f'<div class="v-sigs">{cells}</div>'


def claim_detail_html(claim: ClaimRecord) -> str:
    groups = (
        ("Names and places", claim.entities),
        ("Numbers", claim.numbers),
        ("Links", claim.links),
    )
    rows = []
    for title, values in groups:
        chips = "".join(f'<span class="v-chip">{_e(v)}</span>' for v in values)
        rows.append(
            f'<div class="v-row"><div class="v-cap" style="min-width:140px">{_e(title)}</div>'
            f'<div style="flex:1">{chips or "<span class=v-cap>None found</span>"}</div></div>'
        )
    return "".join(rows)


def privacy_html(redactions: Mapping[str, int]) -> str:
    if not redactions:
        body = '<div class="v-row"><b>Nothing in this message needed removing.</b></div>'
    else:
        body = "".join(
            f'<div class="v-row"><b>{_e(REDACTION_LABEL.get(k, k))}</b>'
            f'<span class="v-pill">{n} removed</span></div>'
            for k, n in redactions.items()
        )
    return (
        body + '<div class="v-cap" style="margin-top:12px">Only a one-way hash of the cleaned '
        "text is kept. Names and addresses are not removed.</div>"
    )


def passport_html(passport: Passport) -> str:
    fields = (
        ("Passport id", passport.passport_id),
        ("Fact-check index", passport.index_version[:16]),
        ("Model version", passport.cpt_version[:16]),
        ("Verdict threshold", f"{passport.threshold:.2f}"),
        ("Created", passport.created_at),
    )
    rows = "".join(
        f'<div class="v-row"><div class="v-cap" style="min-width:150px">{_e(k)}</div>'
        f'<div style="flex:1;word-break:break-all;font-weight:500">{_e(v)}</div></div>'
        for k, v in fields
    )
    return rows + (
        '<div class="v-cap" style="margin-top:12px">The same message with the same index, model '
        "and threshold always gives the same id and verdict.</div>"
    )


def history_tiles_html(items: list[dict[str, object]]) -> str:
    counts = {v: sum(1 for i in items if i["verdict"] == v) for v in VERDICT_TEXT}
    return (
        '<div class="v-tiles">'
        + tile(str(len(items)), "Checks this session")
        + "".join(tile(str(counts[v]), VERDICT_TEXT[v]) for v in VERDICT_TEXT)
        + "</div>"
    )


def history_rows_html(items: list[dict[str, object]]) -> str:
    rows = []
    for i in items:
        claim = str(i["claim"]) or "(no claim sentence found)"
        if len(claim) > CLAIM_CHARS:
            claim = claim[: CLAIM_CHARS - 1].rstrip() + "..."
        verdict: VerdictLabel = i["verdict"]  # type: ignore[assignment]
        rows.append(
            '<div class="v-row"><div style="flex:1;min-width:220px">'
            f'<b>{_e(claim)}</b><div class="v-cap">{_e(i["time"])} UTC | '
            f"{_e(i['matches'])} fact-check(s) matched</div></div>"
            f'<div><span class="v-pill">{_e(VERDICT_TEXT[verdict])}</span> '
            f'<span class="v-impact">{percent(float(i["p_true"]))}</span></div></div>'  # type: ignore[arg-type]
        )
    return "".join(rows)


def radar_tiles_html(items: list[RadarItem]) -> str:
    strongest = f"{max((i.surge for i in items), default=0.0):.2f}x"
    linked = sum(1 for i in items if i.linked_url and safe_link(i.linked_url))
    return (
        '<div class="v-tiles">'
        + tile(str(len(items)), "Rumours on the list")
        + tile(strongest, "Strongest surge")
        + tile(str(linked), "With a fact-check")
        + "</div>"
    )
