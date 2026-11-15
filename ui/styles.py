"""Custom styling for Catppuccin Latte / Mocha; preserve the five-page layout."""
from ui.palette import LATTE, MOCHA


def themed(name: str) -> str:
    return f"light-dark({LATTE[name]}, {MOCHA[name]})"


MUTED = themed("subtext")
HAIRLINE = themed("border")
TINT = themed("mantle")

CSS = f"""
<style>
/* Native radii do not cover all portals, images and map controls.
   Leave circular radio indicators, status dots and spinners alone. */
:is(button, input, textarea, select, fieldset, pre, code, img, iframe, canvas,
    table, details, summary),
[data-testid="stMetric"], [data-testid="stExpander"],
[data-testid="stForm"], [data-testid="stDataFrame"], [data-testid="stAlert"],
[data-testid="stChatMessage"], [data-testid="stChatInput"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-baseweb="popover"], [data-baseweb="menu"], [data-baseweb="select"] > div,
[data-baseweb="input"], [data-baseweb="textarea"],
[role="dialog"], [role="listbox"], [role="option"], [role="tooltip"],
label:has([role="switch"]) > div:not([data-testid="stWidgetLabel"]),
.maplibregl-ctrl-group, .deckgl-tooltip {{
    border-radius: 0 !important;
}}
button:focus-visible, a:focus-visible, summary:focus-visible {{
    outline: 2px solid {themed("mauve")}; outline-offset: 2px;
}}

[data-testid="stMain"] {{ align-items: flex-start; }}  /* left-aligned content, not a centered column */
.block-container {{ max-width: 1480px; padding: 3.5rem 3rem 4rem; }}
[data-testid="stHeader"] {{ background: transparent; }}
h1 {{ font-size: 2.25rem; font-weight: 700; letter-spacing: -0.02em; padding: 0 0 0.25rem; color: {themed("text")}; }}
.rw-lede {{ color: {MUTED}; font-size: 1.05rem; margin: 0 0 1rem; max-width: 46rem; }}
.rw-label {{ color: {MUTED}; font-size: 0.92rem; font-weight: 600; margin: 0.75rem 0 0.25rem; }}
.rw-muted {{ color: {MUTED}; }}
.rw-num, [data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; }}

/* Preserve readable slider values in both appearances. */
[data-testid="stSliderThumbValue"], [data-testid="stSliderThumbValue"] * {{ color: {themed("text")} !important; font-weight: 600; }}

/* AI engine selection retains readable theme text. */
.st-key-aiMode button[aria-checked="true"], .st-key-aiMode button[aria-checked="true"] * {{ color: inherit !important; font-weight: 600; }}
.st-key-aiMode button[aria-checked="true"] {{ color: {themed("text")} !important; }}

/* Mauve primary action: pale text in Latte, dark text in Mocha. */
[data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] p {{ color: light-dark({LATTE["base"]}, {MOCHA["base"]}) !important; font-weight: 600; }}

/* Sidebar: brand, nav, footer pinned to the bottom */
[data-testid="stSidebarUserContent"] {{ display: flex; flex-direction: column; min-height: calc(100vh - 5rem); }}
[data-testid="stSidebarUserContent"] > div, [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {{
	flex: 1; display: flex; flex-direction: column; }}
[data-testid="stLayoutWrapper"]:has(> .st-key-sidebar-foot) {{ margin-top: auto; }}
.st-key-sidebar-foot {{ padding-top: 1rem; border-top: 1px solid {HAIRLINE}; gap: 0.35rem; }}
.st-key-sidebar-foot p {{ color: {MUTED}; font-size: 0.86rem; line-height: 1.4; }}
.rw-brand {{ display: flex; align-items: center; gap: 0.65rem; margin: 0 0 1.25rem; }}
.rw-brand img {{ width: 38px; height: 38px; border-radius: 0; background: {themed("base")}; border: 1px solid {HAIRLINE}; }}
.rw-brand span {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em; }}

/* Ranked list: flat rows with hairlines, not cards */
[class*="st-key-row-"] {{ border-bottom: 1px solid {HAIRLINE}; padding: 0.35rem 0.5rem 0.7rem; gap: 0.2rem; }}
[class*="st-key-row-sel-"] {{ background: {TINT}; border-radius: 0; }}
.rw-row {{ display: flex; align-items: baseline; gap: 0.6rem; }}
.rw-rank {{ flex: none; width: 1.6rem; color: {MUTED}; font-weight: 600; font-variant-numeric: tabular-nums; }}
.rw-row-title {{ font-weight: 600; line-height: 1.3; }}
.rw-dot {{ display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; background: {themed("mauve")};
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
