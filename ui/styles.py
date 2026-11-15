"""The only custom CSS for the page. Colors come from .streamlit/config.toml ([theme.light] / [theme.dark]).

Light mode is Catppuccin Latte, dark mode is Catppuccin Mocha (https://catppuccin.com/palette). Streamlit sets
`color-scheme` on .stApp, so light-dark() picks the Latte or Mocha value without knowing which theme is active.
Rules: no shadows, no gradients, no uppercase labels, sharp corners, peach only as a fill (never as text).
"""

FONT = "'CaskaydiaCove Nerd Font Mono', monospace"
FONT_URL = "/app/static/fonts/CaskaydiaCoveNerdFontMono-Regular.ttf"  # for iframes, which do not get the theme font

LATTE = {"base": "#EFF1F5", "mantle": "#E6E9EF", "surface0": "#CCD0DA", "surface1": "#BCC0CC", "surface2": "#ACB0BE",
	"subtext1": "#5C5F77", "text": "#4C4F69", "peach": "#FE640B", "blue": "#1E66F5"}
MOCHA = {"base": "#1E1E2E", "mantle": "#181825", "crust": "#11111B", "surface0": "#313244", "surface1": "#45475A",
	"surface2": "#585B70", "subtext0": "#A6ADC8", "text": "#CDD6F4", "peach": "#FAB387", "blue": "#89B4FA"}
INK = MOCHA["crust"]  # text on peach in both themes (7.0:1 on Latte peach, 10.6:1 on Mocha peach)

TEXT = f"light-dark({LATTE['text']}, {MOCHA['text']})"
MUTED = f"light-dark({LATTE['subtext1']}, {MOCHA['subtext0']})"  # 5.5:1 on Latte base, 7.4:1 on Mocha base
HAIRLINE = f"light-dark({LATTE['surface0']}, {MOCHA['surface0']})"
TINT = f"light-dark({LATTE['mantle']}, {MOCHA['surface0']})"
PEACH = f"light-dark({LATTE['peach']}, {MOCHA['peach']})"

CSS = f"""
<style>
[data-testid="stMain"] {{ align-items: flex-start; }}  /* left-aligned content, not a centered column */
.block-container {{ max-width: 1480px; padding: 3.5rem 3rem 4rem; }}
[data-testid="stHeader"] {{ background: transparent; }}
/* Sharp corners everywhere (theme baseRadius = none covers widgets; these are rounded outside the theme) */
.stApp img, .stApp iframe, .stApp [data-testid="stImage"], [data-testid="stDeckGlJsonChart"], [data-testid="stDeckGlJsonChart"] *,
[data-testid="stExpander"] details, [data-testid="stAlert"], [data-testid="stAlertContainer"], [data-testid="stTooltipContent"],
[data-baseweb="popover"] *, [data-testid="stCode"] pre, .st-key-exampleChips button {{ border-radius: 0 !important; }}
h1 {{ font-size: 2.25rem; font-weight: 700; letter-spacing: -0.02em; padding: 0 0 0.25rem; color: {TEXT}; }}
.rw-lede {{ color: {MUTED}; font-size: 1.05rem; margin: 0 0 1rem; max-width: 46rem; }}
.rw-label {{ color: {MUTED}; font-size: 0.92rem; font-weight: 600; margin: 0.75rem 0 0.25rem; }}
.rw-muted {{ color: {MUTED}; }}
.rw-num, [data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; }}

/* Peach is a fill, never text: slider values use the text color */
[data-testid="stSliderThumbValue"], [data-testid="stSliderThumbValue"] * {{ color: {TEXT} !important; font-weight: 600; }}

/* AI engine switch: the selected segment keeps the text color (peach stays on the border and tint) */
.st-key-aiMode button[aria-checked="true"], .st-key-aiMode button[aria-checked="true"] * {{ color: inherit !important; font-weight: 600; }}
.st-key-aiMode button[aria-checked="true"] {{ color: {TEXT} !important; }}

/* Primary action: peach fill, dark text in both themes */
[data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] p {{ color: {INK} !important; font-weight: 600; }}

/* Sidebar: brand, nav, footer pinned to the bottom */
[data-testid="stSidebarUserContent"] {{ display: flex; flex-direction: column; min-height: calc(100vh - 5rem); }}
[data-testid="stSidebarUserContent"] > div, [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {{
	flex: 1; display: flex; flex-direction: column; }}
[data-testid="stLayoutWrapper"]:has(> .st-key-sidebar-foot) {{ margin-top: auto; }}
.st-key-sidebar-foot {{ padding-top: 1rem; border-top: 1px solid {HAIRLINE}; gap: 0.35rem; }}
.st-key-sidebar-foot p {{ color: {MUTED}; font-size: 0.86rem; line-height: 1.4; }}
.rw-brand {{ display: flex; align-items: center; gap: 0.65rem; margin: 0 0 1.25rem; }}
.rw-brand img {{ width: 38px; height: 38px; border-radius: 0; background: #FFFFFF; border: 1px solid {HAIRLINE}; }}
.rw-brand span {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em; }}

/* Ranked list: flat rows with hairlines, not cards */
[class*="st-key-row-"] {{ border-bottom: 1px solid {HAIRLINE}; padding: 0.35rem 0.5rem 0.7rem; gap: 0.2rem; }}
[class*="st-key-row-sel-"] {{ background: {TINT}; }}
.rw-row {{ display: flex; align-items: baseline; gap: 0.6rem; }}
.rw-rank {{ flex: none; width: 1.6rem; color: {MUTED}; font-weight: 600; font-variant-numeric: tabular-nums; }}
.rw-row-title {{ font-weight: 600; line-height: 1.3; }}
.rw-dot {{ display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; background: {PEACH};
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
