"""Streamlit rendering of a VerdictRecord. Calm wording; never a bare FAKE or REAL."""

import streamlit as st

from components import api
from components.format import (
    network_dot,
    percent,
    reason_line,
    redaction_notice,
    safe_link,
    verdict_card_html,
    what_if_sentence,
)
from verity.schemas import UserLabel, VerdictRecord


def render_record(record: VerdictRecord) -> None:
    notice = redaction_notice({k: v for k, v in record.redactions.items()})
    if notice:
        st.info(notice)

    st.subheader("The claim VERITY read")
    st.write(record.claim.text or "(no claim sentence found)")

    st.markdown(verdict_card_html(record), unsafe_allow_html=True)

    for flag in record.lookalikes:
        if flag.kind == "lookalike":
            st.warning(
                f"The link to {flag.domain} looks like {flag.lookalike_of} "
                f"(edit distance {flag.distance}) but is a different site. "
                "The source is treated as low credibility."
            )
        else:
            st.warning(
                f"{flag.domain} is a link shortener, so the real destination is hidden. "
                "The source is treated as unknown."
            )

    if record.matches:
        st.markdown("**Matched fact-checks**")
        for m in record.matches:
            link = safe_link(m.url)
            target = f"[{m.publisher}]({link})" if link else m.publisher
            st.markdown(f"- {target}: rated *{m.rating}* (similarity {m.similarity:.2f})")
    else:
        st.caption("No published fact-check matched this claim.")

    if record.family is not None:
        fam = record.family
        text = f"Rumour family: `{fam.family_id}`"
        if fam.source == "variant":
            text += " - an edited copy of a rumour that has a published fact-check."
        elif fam.source == "existing":
            text += " - similar messages have been checked before."
        else:
            text += " - first time this rumour is seen."
        st.caption(text)

    left, right = st.columns(2)
    with left:
        st.markdown("**Why (what moved the number)**")
        for r in record.reasons:
            st.write("- " + reason_line(r))
    with right:
        st.markdown("**What would change the answer**")
        for w in record.what_if:
            st.write("- " + what_if_sentence(w, record.p_true))

    st.markdown("**Belief network**")
    st.graphviz_chart(network_dot(record.evidence, record.p_true, record.verdict))

    st.markdown("**Reply card** (copy and send back to the group)")
    st.code(record.reply_card, language=None, wrap_lines=True)

    with st.expander("Evidence passport"):
        p = record.passport
        st.write(f"Passport id: `{p.passport_id}`")
        if record.matches:
            for m in record.matches:
                st.write(f"- {m.publisher} | {m.rating} | similarity {m.similarity:.3f} | {m.url}")
        else:
            st.write("No retrieved sources for this verdict.")
        st.write(
            f"Index version: `{p.index_version[:16]}` | model (CPT) version: "
            f"`{p.cpt_version[:16]}` | threshold: {p.threshold} | created: {p.created_at}"
        )
        st.caption("Every sentence shown comes from a template or a retrieved record.")

    _feedback(record)
    st.caption(f"Estimated probability the claim is true: {percent(record.p_true)}.")


def _feedback(record: VerdictRecord) -> None:
    key = f"fb_{record.message_hash}"
    if st.session_state.get(key):
        st.success("Thanks, your feedback was recorded.")
        return
    st.markdown("**Was this right?**")
    c1, c2, _ = st.columns([1, 1, 4])
    for col, label, value in ((c1, "Yes", "right"), (c2, "No", "wrong")):
        if col.button(label, key=f"{key}_{value}"):
            _send(record, value)  # type: ignore[arg-type]
            st.rerun()


def _send(record: VerdictRecord, label: UserLabel) -> None:
    try:
        api.post_feedback(record.message_hash, record.verdict, label)
        st.session_state[f"fb_{record.message_hash}"] = True
    except api.ApiError as exc:
        st.error(exc.message)
