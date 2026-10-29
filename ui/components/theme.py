"""Nike-style design system (DESIGN-nike.md) for the Streamlit UI.

Photography-first editorial look: pure black / white / one soft gray, pill CTAs, flat
cards, hairline dividers, no shadows. Fonts are local stacks only (no third-party font
requests from the browser, which suits a privacy-first tool).
"""

import streamlit as st

# colour tokens (DESIGN-nike.md)
INK, CANVAS, CLOUD = "#111111", "#ffffff", "#f5f5f5"
MUTE, STONE, HAIRLINE, HAIRLINE_SOFT = "#707072", "#9e9ea0", "#cacacb", "#e5e5e5"
SALE, SUCCESS = "#d30005", "#007d48"

DISPLAY = (
    '"Nike Futura ND","Futura","Futura PT","Bebas Neue","DIN Condensed",'
    '"Arial Narrow",Impact,sans-serif'
)
TEXT = '"Helvetica Now Text","Helvetica Neue",Helvetica,Inter,Arial,sans-serif'

CSS = f"""
<style>
:root {{
  --ink:{INK}; --canvas:{CANVAS}; --cloud:{CLOUD}; --mute:{MUTE}; --stone:{STONE};
  --hairline:{HAIRLINE}; --hairline-soft:{HAIRLINE_SOFT}; --sale:{SALE}; --success:{SUCCESS};
  --display:{DISPLAY}; --text:{TEXT};
}}
html, body, [class*="st-"], .stApp {{ font-family: var(--text); color: var(--ink); }}
.stApp {{ background: var(--canvas); }}
/* keep Streamlit's icon font for icon glyphs (the global font rule must not replace it) */
[data-testid="stIconMaterial"], span[class*="material-symbols"], .material-icons {{
  font-family: "Material Symbols Rounded", "Material Icons" !important; }}

/* strip default Streamlit chrome */
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stSidebarNav"], [data-testid="collapsedControl"], #MainMenu, footer,
[data-testid="stDecoration"] {{ display: none !important; }}
.block-container, [data-testid="stMainBlockContainer"] {{
  max-width: 1440px; padding: 0 40px 0 40px !important;
}}
@media (max-width: 640px) {{ .block-container, [data-testid="stMainBlockContainer"] {{
  padding: 0 16px !important; }} }}
[data-testid="stVerticalBlock"] {{ gap: 0.75rem; }}

/* utility bar + primary nav */
.v-util {{ background: var(--cloud); min-height: 36px; margin: 0 -40px; padding: 0 40px;
  display:flex; align-items:center; justify-content:flex-end; gap:18px;
  font-size:12px; font-weight:500; }}
.v-util a, .v-util span {{ color: var(--ink); text-decoration:none; }}
.v-nav {{ height:56px; display:flex; align-items:center; gap:32px;
  box-shadow: inset 0 -1px 0 var(--hairline-soft); margin: 0 -40px 0; padding: 0 40px; }}
.v-logo {{ font-family: var(--display) !important; font-weight:700; font-size:28px; letter-spacing:.02em;
  text-transform:uppercase; line-height:1; }}
.v-nav a {{ color: var(--ink); text-decoration:none; font-weight:500; font-size:16px;
  height:56px; display:flex; align-items:center; border-bottom:2px solid transparent; }}
.v-nav a.on {{ border-bottom-color: var(--ink); }}
.v-nav .sp {{ flex:1; }}
@media (max-width: 640px) {{ .v-util, .v-nav {{ margin:0 -16px; padding:0 16px; }}
  .v-nav {{ gap:18px; }} .v-nav .v-fine {{ display:none; }} .v-util {{ justify-content:center; }} }}

/* campaign headline */
.v-hero {{ padding: 48px 0 24px; }}
.v-display {{ font-family: var(--display) !important; font-weight:700 !important;
  text-transform:uppercase; font-size: clamp(48px, 9vw, 96px) !important; line-height:.9 !important;
  letter-spacing:0; margin:0 !important; padding:0 !important; color: var(--ink); }}
.v-lede {{ font-size:16px; line-height:1.5; color: var(--mute); max-width:640px; margin:28px 0 0 !important; }}

/* section rhythm and headings */
.v-section {{ margin-top: 48px; }}
@media (max-width: 960px) {{ .v-section {{ margin-top:32px; }} }}
.v-h1 {{ font-size:32px !important; line-height:1.2 !important; font-weight:700 !important;
  margin:0 0 16px !important; text-transform:uppercase; font-family: var(--display) !important;
  letter-spacing:.01em; }}
.v-h2 {{ font-size:24px; line-height:1.2; font-weight:500; margin:0; font-family: var(--text); }}
.v-cap {{ font-size:14px; font-weight:500; color: var(--mute); }}
.v-fine {{ font-size:12px; font-weight:500; color: var(--mute); }}
.v-row {{ border-bottom:1px solid var(--hairline); padding:18px 0; display:flex; gap:16px;
  align-items:center; justify-content:space-between; }}
.v-row:first-of-type {{ border-top:1px solid var(--hairline); }}
.v-row b {{ font-weight:500; }}
.v-row a {{ color: var(--ink); text-decoration: underline; font-weight:500; }}

/* verdict */
.v-verdict {{ background: var(--cloud); padding: 32px; }}
.v-verdict .dot {{ display:inline-block; width:12px; height:12px; border-radius:9999px;
  margin-right:10px; vertical-align:middle; }}
.v-verdict .label {{ font-family: var(--display) !important; font-weight:700; text-transform:uppercase;
  font-size: clamp(40px, 7vw, 72px) !important; line-height:.9 !important; margin:12px 0 0; }}
.v-verdict .p {{ font-size:24px; font-weight:500; margin-top:16px; }}
.v-bar {{ height:8px; background: var(--hairline-soft); margin-top:16px; }}
.v-bar > i {{ display:block; height:100%; background: var(--ink); }}

/* pills, badges, chips */
.v-pill {{ display:inline-block; border:1px solid var(--hairline); border-radius:30px;
  padding:4px 12px; font-size:12px; font-weight:500; background: var(--canvas); }}
.v-chip {{ display:inline-block; border:1px solid var(--hairline); border-radius:30px;
  padding:8px 16px; font-size:14px; font-weight:500; margin:0 8px 8px 0; }}
.v-note {{ background: var(--cloud); padding:16px 18px; font-size:14px; font-weight:500;
  line-height:1.5; margin-top:12px; }}
.v-note .tag {{ color: var(--sale); margin-right:8px; }}
.v-impact {{ display:inline-block; min-width:64px; text-align:right; font-weight:500; }}
.v-mini {{ display:inline-block; width:120px; height:8px; background: var(--hairline-soft);
  vertical-align:middle; margin-right:12px; position:relative; }}
.v-mini i {{ position:absolute; top:0; height:100%; background: var(--ink); }}
.v-mini i.neg {{ background: var(--stone); }}
.v-util .warn {{ margin-right:auto; color: var(--mute); }}

/* inputs */
.stTextArea textarea, .stTextInput input {{ background: var(--cloud) !important;
  color: var(--ink) !important; border:2px solid transparent !important; font-size:16px;
  font-family: var(--text); }}
.stTextArea div[data-baseweb="textarea"], .stTextInput div[data-baseweb="base-input"],
.stTextArea div[data-baseweb="base-input"] {{ background: var(--cloud) !important;
  border: none !important; border-radius: 24px !important; }}
.stTextArea textarea {{ border-radius:24px !important; padding:16px 20px !important; }}
.stTextInput input {{ border-radius:24px !important; height:40px; padding:8px 16px !important; }}
.stTextArea textarea:focus, .stTextInput input:focus {{ background: var(--canvas) !important;
  border-color: var(--ink) !important; box-shadow: 0 0 0 12px var(--cloud) !important;
  outline:none !important; }}
.stTextArea label p, .stTextInput label p {{ font-size:14px; font-weight:500; color: var(--ink); }}
[data-testid="stForm"] {{ border:none !important; padding:0 !important; }}

/* buttons: pills only */
.stButton button, [data-testid="stFormSubmitButton"] button, .stLinkButton a {{
  border-radius:30px !important; height:48px; padding:16px 32px; font-size:16px;
  font-weight:500; border:none; background: var(--cloud); color: var(--ink);
  transition: transform .08s, opacity .08s; box-shadow:none; }}
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"],
button[kind="primaryFormSubmit"] {{ background: var(--ink) !important; color: var(--canvas) !important; }}
.stButton button:active, [data-testid="stFormSubmitButton"] button:active {{
  transform: scale(.94); opacity:.5; }}
.stButton button:focus-visible, [data-testid="stFormSubmitButton"] button:focus-visible {{
  outline:2px solid var(--ink); outline-offset:3px; }}
.stButton button p, [data-testid="stFormSubmitButton"] button p {{ font-size:16px; font-weight:500; }}
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] *,
.stButton button[kind="primary"] * {{ color: var(--canvas) !important; }}

/* reply card (code block with copy) */
[data-testid="stCode"], [data-testid="stCode"] pre, [data-testid="stCode"] code {{
  background: var(--cloud) !important; border-radius:0 !important; color: var(--ink) !important;
  font-family: var(--text) !important; font-size:16px !important; line-height:1.5; }}
[data-testid="stCode"] {{ padding: 8px; }}

/* disclosure rows */
[data-testid="stExpander"] {{ border:none !important; border-bottom:1px solid var(--hairline) !important;
  border-radius:0 !important; background: var(--canvas); }}
[data-testid="stExpander"] summary {{ padding:24px 0 !important; font-weight:500; font-size:16px; }}
[data-testid="stExpander"] details {{ border:none !important; }}

/* graph */
[data-testid="stGraphVizChart"] svg {{ max-width:100%; height:auto; background: transparent; }}

/* footer */
.v-footer {{ margin-top:96px; border-top:1px solid var(--hairline); padding:32px 0 48px; }}
.v-cols {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:32px; }}
@media (max-width: 960px) {{ .v-cols {{ grid-template-columns: repeat(2, 1fr); }} }}
.v-cols h4 {{ font-size:16px; font-weight:500; margin:0 0 12px; }}
.v-cols p {{ font-size:14px; font-weight:500; color: var(--mute); margin:0 0 8px; line-height:1.5; }}
.v-legal {{ margin-top:32px; border-top:1px solid var(--hairline); padding-top:16px;
  font-size:9px; font-weight:500; color: var(--mute); line-height:1.75; }}
</style>
"""


def inject() -> None:
    """Apply the design system to the current page."""
    st.markdown(CSS, unsafe_allow_html=True)


def chrome_top(active: str, warnings: list[str] | None = None) -> None:
    """Utility bar and primary nav in one block. ``active`` is 'check' or 'radar'."""
    import html as _html

    note = ""
    if warnings:
        joined = _html.escape("  |  ".join(w.split(":", 1)[0] for w in warnings))
        note = f'<span class="warn" title="degraded mode">{joined}</span>'
    check_cls = "on" if active == "check" else ""
    radar_cls = "on" if active == "radar" else ""
    st.markdown(
        f'<div class="v-util">{note}<span>English</span><span>Tamil</span><span>Hindi</span></div>'
        '<div class="v-nav"><span class="v-logo">Verity</span>'
        f'<a class="{check_cls}" href="/" target="_self">Check</a>'
        f'<a class="{radar_cls}" href="/radar" target="_self">Radar</a>'
        '<span class="sp"></span><span class="v-fine">Shows its work. Admits when it does not know.'
        "</span></div>",
        unsafe_allow_html=True,
    )


def chrome_bottom() -> None:
    st.markdown(
        """
<div class="v-footer"><div class="v-cols">
  <div><h4>Verity</h4><p>A misinformation checker that shows its work, and admits when it does not know.</p></div>
  <div><h4>How it decides</h4><p>Fact-check match</p><p>Source and link check</p><p>Wording and details</p><p>A Bayesian belief network combines them</p></div>
  <div><h4>Your privacy</h4><p>Phone numbers, e-mail, UPI, card and ID numbers are removed first.</p><p>Names and addresses are not removed.</p></div>
  <div><h4>Good to know</h4><p>Unverified means not enough evidence.</p><p>Radar shows what is being checked, not what is true.</p></div>
</div>
<div class="v-legal">Verity gives a probability and reasons, not a ruling. Always look at the linked fact-checks.</div></div>
""",
        unsafe_allow_html=True,
    )
