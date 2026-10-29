"""Session history page. Calls nothing; reads this browser session's earlier checks."""

import streamlit as st

from components import api, history, theme
from components.cards import history_rows_html, history_tiles_html, verdict_guide_html
from components.format import notice_html, section_html

st.set_page_config(page_title="VERITY - History", layout="wide")
theme.inject()
theme.chrome_top("history", api.get_warnings())

st.markdown(
    '<div class="v-hero"><div class="v-display" role="heading" aria-level="1">Your<br>checks.</div>'
    '<p class="v-lede">Everything you checked in this browser session. It is kept only in this '
    "tab: closing it clears the list, and the pasted messages are never stored, only the claim "
    "sentence Verity read.</p></div>",
    unsafe_allow_html=True,
)

items = history.items()
if not items:
    st.markdown(
        notice_html("Nothing checked yet. Paste a message on the Check page and it appears here."),
        unsafe_allow_html=True,
    )
    st.page_link("app.py", label="Go to Check")
    st.markdown(section_html("What the verdicts mean"), unsafe_allow_html=True)
    st.markdown(verdict_guide_html(), unsafe_allow_html=True)
else:
    st.markdown(history_tiles_html(items), unsafe_allow_html=True)
    st.markdown(section_html("Most recent first"), unsafe_allow_html=True)
    st.markdown(history_rows_html(items), unsafe_allow_html=True)
    st.markdown('<div class="v-section" style="margin-top:24px"></div>', unsafe_allow_html=True)
    st.button("Clear history", on_click=history.clear)

theme.chrome_bottom()
