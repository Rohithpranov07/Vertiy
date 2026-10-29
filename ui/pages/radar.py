"""Rumour Radar page. Calls the API only."""

import html

import streamlit as st

from components import api, theme
from components.cards import radar_tiles_html
from components.format import notice_html, safe_link, section_html

st.set_page_config(page_title="VERITY - Rumour Radar", layout="wide")
theme.inject()
theme.chrome_top("radar", api.get_warnings())

st.markdown(
    '<div class="v-hero"><div class="v-display" role="heading" aria-level="1">Rumour<br>radar.</div>'
    '<p class="v-lede">Unverified rumours that people are checking more than usual. A rumour '
    "appears only after at least three checks, and only its keywords are shown, never the "
    "message. <b>Radar shows what is being checked, not what is true.</b></p></div>",
    unsafe_allow_html=True,
)

c1, c2, _ = st.columns([1, 1, 4])
window = c1.number_input("Window (hours)", min_value=1, max_value=720, value=24, step=1)
limit = c2.number_input("Rows", min_value=1, max_value=100, value=10, step=1)

st.markdown(section_html("Surging now"), unsafe_allow_html=True)
try:
    items = api.get_radar(int(window), int(limit))
except api.ApiError as exc:
    st.markdown(notice_html(exc.message), unsafe_allow_html=True)
else:
    if not items:
        st.markdown(
            notice_html("No unverified rumour has been checked often enough to appear yet."),
            unsafe_allow_html=True,
        )
    if items:
        st.markdown(radar_tiles_html(items), unsafe_allow_html=True)
    top = max((i.surge for i in items), default=1.0)
    rows = []
    for rank, i in enumerate(items, start=1):
        chips = "".join(f'<span class="v-chip">{html.escape(k)}</span>' for k in i.keywords)
        link = safe_link(i.linked_url) if i.linked_url else None
        fact = (
            f'<a href="{html.escape(link)}" target="_blank" rel="noopener">Fact-check</a>'
            if link
            else '<span class="v-cap">No fact-check yet</span>'
        )
        width = max(2, round(i.surge / top * 100))
        rows.append(
            '<div class="v-row" style="align-items:flex-start;flex-wrap:wrap">'
            f'<div style="flex:1;min-width:240px"><div class="v-cap">#{rank} '
            f'{html.escape(i.family_id)}</div><div style="margin-top:8px">{chips}</div></div>'
            f'<div style="min-width:220px"><div class="v-h2">{i.surge:.2f}x</div>'
            f'<div class="v-bar" style="margin-top:8px"><i style="width:{width}%"></i></div>'
            f'<div class="v-cap" style="margin-top:8px">{i.previous} before, {i.recent} recent</div>'
            f"</div><div>{fact}</div></div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)

theme.chrome_bottom()
