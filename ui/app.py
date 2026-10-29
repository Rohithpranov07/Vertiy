"""VERITY Streamlit UI. HTTP client only: it computes nothing and imports no engine code."""

import streamlit as st

from components import api, theme
from components.format import notice_html
from components.render import render_record

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

with st.form("check"):
    text = st.text_area(
        "Paste the forwarded message",
        height=180,
        placeholder="Paste the message here...",
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

theme.chrome_bottom()
