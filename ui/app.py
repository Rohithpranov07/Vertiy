"""VERITY Streamlit UI. HTTP client only: it computes nothing and imports no engine code."""

import streamlit as st

from components import api
from components.render import render_record

st.set_page_config(page_title="VERITY", page_icon=None, layout="wide")

st.title("VERITY")
st.caption("A misinformation checker that shows its work, and admits when it does not know.")

with st.form("check"):
    text = st.text_area(
        "Paste the forwarded message (English, Tamil or Hindi)",
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
                        "VERITY reads English, Tamil and Hindi messages. This one looks like "
                        "another language."
                    )
                else:
                    st.session_state["error"] = exc.message

if "error" in st.session_state:
    st.error(st.session_state["error"])
elif "record" in st.session_state:
    render_record(st.session_state["record"])
