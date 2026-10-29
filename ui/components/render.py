"""Streamlit rendering of a VerdictRecord in the Nike-style design system.

Calm wording; never a bare FAKE or REAL. Photography is absent here, so type carries the
editorial weight: display-size verdict, flat cards, hairline rows, pill buttons.
"""

import streamlit as st

from components import api
from components.cards import (
    claim_detail_html,
    metrics_html,
    passport_html,
    privacy_html,
    signals_html,
)
from components.format import (
    claim_html,
    family_html,
    lookalike_text,
    matches_html,
    network_dot,
    notice_html,
    reasons_html,
    redaction_notice,
    section_html,
    verdict_card_html,
    warning_html,
    what_if_html,
)
from verity.schemas import UserLabel, VerdictRecord


def render_record(record: VerdictRecord) -> None:
    notice = redaction_notice({k: v for k, v in record.redactions.items()})
    if notice:
        st.markdown(notice_html(notice), unsafe_allow_html=True)

    st.markdown(claim_html(record.claim.text), unsafe_allow_html=True)
    st.markdown('<div class="v-section" style="margin-top:24px"></div>', unsafe_allow_html=True)
    st.markdown(verdict_card_html(record), unsafe_allow_html=True)
    st.markdown(metrics_html(record), unsafe_allow_html=True)

    for flag in record.lookalikes:
        text = lookalike_text(flag.kind, flag.domain, flag.lookalike_of, flag.distance)
        st.markdown(warning_html(text), unsafe_allow_html=True)

    st.markdown('<div class="v-section" style="margin-top:24px"></div>', unsafe_allow_html=True)
    summary, evidence, reply, details = st.tabs(
        ["Summary", "Evidence", "Reply and save", "Privacy and passport"]
    )

    with summary:
        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(section_html("Why it says so"), unsafe_allow_html=True)
            st.markdown(reasons_html(record.reasons), unsafe_allow_html=True)
        with right:
            st.markdown(section_html("What would change it"), unsafe_allow_html=True)
            st.markdown(what_if_html(record.what_if, record.p_true), unsafe_allow_html=True)
        st.markdown(section_html("Belief network"), unsafe_allow_html=True)
        st.graphviz_chart(network_dot(record.evidence, record.p_true, record.verdict))

    with evidence:
        st.markdown(section_html("Matched fact-checks"), unsafe_allow_html=True)
        st.markdown(matches_html(record), unsafe_allow_html=True)
        fam = family_html(record)
        if fam:
            st.markdown(fam, unsafe_allow_html=True)
        st.markdown(section_html("Signals Verity read"), unsafe_allow_html=True)
        st.markdown(signals_html(record), unsafe_allow_html=True)
        st.markdown(section_html("Inside the claim"), unsafe_allow_html=True)
        st.markdown(claim_detail_html(record.claim), unsafe_allow_html=True)

    with reply:
        st.markdown(section_html("Reply card"), unsafe_allow_html=True)
        st.caption("Copy this and send it back to the group.")
        st.code(record.reply_card, language=None, wrap_lines=True)
        st.download_button(
            "Save evidence file",
            data=record.model_dump_json(indent=2),
            file_name=f"verity-{record.message_hash[:8]}.json",
            mime="application/json",
        )
        st.caption("A JSON file with the verdict, reasons, sources and passport.")

    with details:
        st.markdown(section_html("Privacy shield"), unsafe_allow_html=True)
        st.markdown(
            privacy_html({str(k): v for k, v in record.redactions.items()}), unsafe_allow_html=True
        )
        st.markdown(section_html("Evidence passport"), unsafe_allow_html=True)
        st.markdown(passport_html(record.passport), unsafe_allow_html=True)

    _feedback(record)


def _feedback(record: VerdictRecord) -> None:
    st.markdown(section_html("Was this right?"), unsafe_allow_html=True)
    key = f"fb_{record.message_hash}"
    if st.session_state.get(key):
        st.markdown(notice_html("Thanks, your feedback was recorded."), unsafe_allow_html=True)
        return
    c1, c2, _ = st.columns([1, 1, 6])
    for col, label, value in ((c1, "Yes", "right"), (c2, "No", "wrong")):
        if col.button(label, key=f"{key}_{value}"):
            _send(record, value)  # type: ignore[arg-type]
            st.rerun()


def _send(record: VerdictRecord, label: UserLabel) -> None:
    try:
        api.post_feedback(record.message_hash, record.verdict, label)
        st.session_state[f"fb_{record.message_hash}"] = True
    except api.ApiError as exc:
        st.session_state["error"] = exc.message
