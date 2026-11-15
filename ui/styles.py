"""The only custom CSS for the page. Colors come from .streamlit/config.toml ([theme.light] / [theme.dark]).

Streamlit does not expose its theme as CSS variables, so muted text and hairlines are derived from currentColor
with color-mix(): one block is correct in both themes without knowing which one is active. Streamlit does set
`color-scheme` on .stApp, so light-dark() gives headings brand navy in light mode only.
Rules: no shadows, no gradients, no uppercase labels, orange only as a fill (never as text: 2.0:1 on white).
"""

ORANGE = "#FF9F1C"  # the one accent: primary action and the #1 building
BLUE = "#2F80ED"  # data only (map points)
INK = "#1D1D1F"  # text on orange (8.3:1)
NAVY = "#13294B"  # brand navy, light-mode headings only (14:1 on white)

MUTED = "color-mix(in srgb, currentColor 62%, transparent)"  # ~4.6:1 on white, ~6.9:1 on black
HAIRLINE = "color-mix(in srgb, currentColor 13%, transparent)"
TINT = "color-mix(in srgb, currentColor 6%, transparent)"

CSS = f"""
<style>
[data-testid="stMain"] {{ align-items: flex-start; }}  /* left-aligned content, not a centered column */
.block-container {{ max-width: 1480px; padding: 3.5rem 3rem 4rem; }}
[data-testid="stHeader"] {{ background: transparent; }}
h1 {{ font-size: 2.25rem; font-weight: 700; letter-spacing: -0.02em; padding: 0 0 0.25rem; color: light-dark({NAVY}, #F5F5F7); }}
.rw-lede {{ color: {MUTED}; font-size: 1.05rem; margin: 0 0 1rem; max-width: 46rem; }}
.rw-label {{ color: {MUTED}; font-size: 0.92rem; font-weight: 600; margin: 0.75rem 0 0.25rem; }}
.rw-muted {{ color: {MUTED}; }}
.rw-num, [data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; }}

/* Orange is a fill, never text: slider values use the text color */
[data-testid="stSliderThumbValue"], [data-testid="stSliderThumbValue"] * {{ color: light-dark({INK}, #F5F5F7) !important; font-weight: 600; }}

/* AI engine switch: the selected segment keeps the text color (orange stays on the border and tint) */
.st-key-aiMode button[aria-checked="true"], .st-key-aiMode button[aria-checked="true"] * {{ color: inherit !important; font-weight: 600; }}
.st-key-aiMode button[aria-checked="true"] {{ color: light-dark({INK}, #F5F5F7) !important; }}

/* Primary action: orange fill, dark text in both themes */
[data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] p {{ color: {INK} !important; font-weight: 600; }}

/* Sidebar: brand, nav, footer pinned to the bottom */
[data-testid="stSidebarUserContent"] {{ display: flex; flex-direction: column; min-height: calc(100vh - 5rem); }}
[data-testid="stSidebarUserContent"] > div, [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {{
	flex: 1; display: flex; flex-direction: column; }}
[data-testid="stLayoutWrapper"]:has(> .st-key-sidebar-foot) {{ margin-top: auto; }}
.st-key-sidebar-foot {{ padding-top: 1rem; border-top: 1px solid {HAIRLINE}; gap: 0.35rem; }}
.st-key-sidebar-foot p {{ color: {MUTED}; font-size: 0.86rem; line-height: 1.4; }}
.rw-brand {{ display: flex; align-items: center; gap: 0.65rem; margin: 0 0 1.25rem; }}
.rw-brand img {{ width: 38px; height: 38px; border-radius: 9px; background: #FFFFFF; border: 1px solid {HAIRLINE}; }}
.rw-brand span {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em; }}

/* Ranked list: flat rows with hairlines, not cards */
[class*="st-key-row-"] {{ border-bottom: 1px solid {HAIRLINE}; padding: 0.35rem 0.5rem 0.7rem; gap: 0.2rem; }}
[class*="st-key-row-sel-"] {{ background: {TINT}; border-radius: 10px; }}
.rw-row {{ display: flex; align-items: baseline; gap: 0.6rem; }}
.rw-rank {{ flex: none; width: 1.6rem; color: {MUTED}; font-weight: 600; font-variant-numeric: tabular-nums; }}
.rw-row-title {{ font-weight: 600; line-height: 1.3; }}
.rw-dot {{ display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; background: {ORANGE};
	margin-left: 0.45rem; vertical-align: middle; }}
.rw-row-stats {{ color: {MUTED}; font-size: 0.93rem; margin-left: 2.2rem; font-variant-numeric: tabular-nums; }}
.rw-row-stats b {{ color: inherit; font-weight: 600; }}

/* Key-value list on the Building page */
[class*="st-key-kv-"] {{ border-bottom: 1px solid {HAIRLINE}; padding: 0.5rem 0; }}
.rw-kv-value {{ text-align: right; font-weight: 600; font-size: 1.1rem; font-variant-numeric: tabular-nums; }}
.rw-kv-delta {{ display: block; color: {MUTED}; font-weight: 400; font-size: 0.86rem; }}

/* Proposal: one readable column */
.st-key-letter {{ max-width: 720px; margin: 0 auto; }}
.st-key-letter-body {{ border-top: 1px solid {HAIRLINE}; border-bottom: 1px solid {HAIRLINE}; padding: 1.25rem 0; }}
.st-key-letter-body p, .st-key-letter-body li {{ font-size: 1.05rem; line-height: 1.65; }}
</style>
"""


def injectCss() -> None:
	import streamlit as st

	st.markdown(CSS, unsafe_allow_html=True)
