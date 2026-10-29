"""Rumour Radar page. Calls the API only."""

import pandas as pd
import streamlit as st

from components import api

st.set_page_config(page_title="VERITY - Rumour Radar", layout="wide")
st.title("Rumour Radar")
st.caption("Radar shows what is being checked, not what is true.")
st.write(
    "Unverified rumours that people are checking more than usual. A rumour appears here only "
    "after at least three checks, and only its keywords are shown - never the message."
)

c1, c2 = st.columns(2)
window = c1.number_input("Window (hours)", min_value=1, max_value=720, value=24, step=1)
limit = c2.number_input("Rows", min_value=1, max_value=100, value=10, step=1)

try:
    items = api.get_radar(int(window), int(limit))
except api.ApiError as exc:
    st.error(exc.message)
else:
    if not items:
        st.info("No unverified rumour has been checked often enough to appear yet.")
    else:
        top = max(i.surge for i in items)
        frame = pd.DataFrame(
            {
                "Rumour": [i.family_id for i in items],
                "Keywords": [", ".join(i.keywords) for i in items],
                "Previous": [i.previous for i in items],
                "Recent": [i.recent for i in items],
                "Surge": [i.surge for i in items],
                "Fact-check": [i.linked_url or "" for i in items],
            }
        )
        st.dataframe(
            frame,
            hide_index=True,
            column_config={
                "Surge": st.column_config.ProgressColumn(
                    "Surge", format="%.2f", min_value=0.0, max_value=float(top)
                ),
                "Fact-check": st.column_config.LinkColumn("Fact-check"),
            },
        )
