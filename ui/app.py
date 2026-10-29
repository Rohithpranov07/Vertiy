"""VERITY Streamlit UI. HTTP client only: it computes nothing and imports no engine code."""

import streamlit as st

from components import api, history, theme
from components.cards import bento_html, stat_tiles_html, steps_html, verdict_guide_html
from components.examples import EXAMPLES
from components.format import notice_html, section_html
from components.render import render_record

CHIPS_PER_ROW = 4

st.set_page_config(page_title="VERITY", page_icon=None, layout="wide")
theme.inject()
theme.chrome_top("check", api.get_warnings())

st.markdown(
    '<div class="v-hero"><div class="v-display" role="heading" aria-level="1">Check before<br>you forward.</div>'
    '<p class="v-lede">Paste a forwarded message in English, Tamil or Hindi. Verity finds the '
    "claim, looks for published fact-checks and tells you how sure it is, and why. When the "
    "evidence is thin, it says so.</p></div>",
    unsafe_allow_html=True,
)

try:
    st.markdown(stat_tiles_html(api.get_health()), unsafe_allow_html=True)
except api.ApiError:
    pass  # the error notice appears when a check is attempted


def _use_example(text: str) -> None:
    st.session_state["draft"] = text
    st.session_state.pop("record", None)
    st.session_state.pop("error", None)


st.markdown(section_html("Try an example"), unsafe_allow_html=True)
with st.container(key="examples"):
    for start in range(0, len(EXAMPLES), CHIPS_PER_ROW):
        cols = st.columns(CHIPS_PER_ROW)
        for col, ex in zip(cols, EXAMPLES[start : start + CHIPS_PER_ROW], strict=False):
            col.button(
                ex.title,
                key=f"ex_{start}_{ex.title}",
                help=ex.kind,
                on_click=_use_example,
                args=(ex.text,),
            )

st.markdown('<div class="v-section" style="margin-top:32px"></div>', unsafe_allow_html=True)
with st.form("check"):
    text = st.text_area(
        "Paste the forwarded message",
        height=180,
        placeholder="Paste the message here...",
        key="draft",
    )
    url = st.text_input("Optional link that came with it")
    submitted = st.form_submit_button("Check", type="primary")

if submitted:
    st.session_state.pop("error", None)
    if not text.strip():
        st.session_state["error"] = "Please paste a message to check."
        st.session_state.pop("record", None)
    else:
        with st.spinner("Checking..."):
            try:
                st.session_state["record"] = api.post_check(text, url or None)
                history.add(st.session_state["record"])
            except api.ApiError as exc:
                st.session_state.pop("record", None)
                if exc.code == "unsupported_language":
                    st.session_state["error"] = (
                        "Verity reads English, Tamil and Hindi messages. This one looks like "
                        "another language."
                    )
                else:
                    st.session_state["error"] = exc.message

if "error" in st.session_state:
    st.markdown(
        notice_html(st.session_state["error"]).replace("v-note", "v-note err"),
        unsafe_allow_html=True,
    )
elif "record" in st.session_state:
    render_record(st.session_state["record"])
else:
    st.markdown(section_html("What you get"), unsafe_allow_html=True)
    st.markdown(bento_html(), unsafe_allow_html=True)
    st.markdown(section_html("How a check works"), unsafe_allow_html=True)
    st.markdown(steps_html(), unsafe_allow_html=True)
    st.markdown(section_html("What the verdicts mean"), unsafe_allow_html=True)
    st.markdown(verdict_guide_html(), unsafe_allow_html=True)

theme.chrome_bottom()
