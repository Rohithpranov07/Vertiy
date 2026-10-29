"""Guide page: how Verity decides, what it can and cannot do. Static content."""

import streamlit as st

from components import api, theme
from components.cards import bento_html, steps_html, verdict_guide_html
from components.format import NODE_TITLE, section_html
from verity.schemas import BNNode

st.set_page_config(page_title="VERITY - Guide", layout="wide")
theme.inject()
theme.chrome_top("guide", api.get_warnings())

st.markdown(
    '<div class="v-hero"><div class="v-display" role="heading" aria-level="1">How Verity<br>decides.</div>'
    '<p class="v-lede">Verity does not ask a chatbot for an opinion. It looks up published '
    "fact-checks, reads a few simple signals and combines them with fixed, inspectable "
    "arithmetic. Every step is shown to you.</p></div>",
    unsafe_allow_html=True,
)

st.markdown(section_html("The steps"), unsafe_allow_html=True)
st.markdown(steps_html(), unsafe_allow_html=True)

st.markdown(section_html("Five things that set it apart"), unsafe_allow_html=True)
st.markdown(bento_html(), unsafe_allow_html=True)

st.markdown(section_html("The signals it weighs"), unsafe_allow_html=True)
SIGNALS: tuple[tuple[BNNode, str], ...] = (
    ("source_cred", "Whether a link came from a trusted site, an unknown one, or a look-alike."),
    ("fact_check", "Whether a published fact-check refutes or supports the claim, or none exists."),
    ("corroboration", "Whether a trusted news outlet is reporting the same thing."),
    ("sensational", "Whether the wording is alarming, such as shouting or panic phrases."),
    ("specifics", "Whether the message has names, dates, places or numbers that can be checked."),
)
st.markdown(
    "".join(
        f'<div class="v-row"><b style="min-width:200px">{NODE_TITLE[n]}</b>'
        f'<span class="v-cap" style="flex:1">{d}</span></div>'
        for n, d in SIGNALS
    ),
    unsafe_allow_html=True,
)

st.markdown(section_html("What the verdicts mean"), unsafe_allow_html=True)
st.markdown(verdict_guide_html(), unsafe_allow_html=True)

st.markdown(section_html("Questions"), unsafe_allow_html=True)
with st.expander("Is my message stored?"):
    st.write(
        "No. Private details are removed first. Only a one-way hash of the cleaned text, a "
        "similarity fingerprint and up to five non-personal keywords are kept."
    )
with st.expander("Why does it so often say Unverified?"):
    st.write(
        "Because a verdict needs evidence. If no published fact-check matches and no trusted "
        "outlet is reporting it, Verity says it does not know instead of guessing."
    )
with st.expander("Which languages work?"):
    st.write("English, Tamil and Hindi. Other languages are declined rather than guessed at.")
with st.expander("Can I trust a Likely false?"):
    st.write(
        "It means published fact-checks point against the message. Open the linked fact-checks "
        "and read them. Verity is a first filter, not a ruling."
    )
with st.expander("What is the Rumour Radar?"):
    st.write(
        "A list of unverified rumours that many people are checking at once. It shows "
        "keywords only, never messages, and never changes a verdict."
    )

theme.chrome_bottom()
