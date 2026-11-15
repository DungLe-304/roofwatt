"""Brand colors and the small amount of custom CSS on top of .streamlit/config.toml."""

NAVY = "#13294B"
ORANGE = "#FF9F1C"
YELLOW = "#FFB627"
BLUE = "#2F80ED"
LIGHT_BLUE = "#8DB8F2"
BACKGROUND = "#F7F9FC"
CARD = "#FFFFFF"
MUTED = "#5B6B7F"  # 5.2:1 on the background

CSS = f"""
<style>
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 3.5rem; padding-bottom: 4rem; max-width: 1480px; }}
h1, h2, h3, h4 {{ color: {NAVY}; letter-spacing: -0.01em; }}

/* Cards: keyed containers (st-key-panel-*, st-key-card-*) and metric tiles */
[class*="st-key-panel-"], [class*="st-key-card-"], [data-testid="stMetric"] {{
	background: {CARD}; border: 1px solid #E3E9F1; border-radius: 14px;
	box-shadow: 0 1px 2px rgba(19,41,75,0.04), 0 6px 18px rgba(19,41,75,0.06);
}}
[class*="st-key-panel-"] {{ padding: 1.25rem 1.5rem; }}
[class*="st-key-card-"] {{ padding: 0.8rem 1rem; gap: 0.35rem; }}
[class*="st-key-card-sel-"] {{ border: 2px solid {ORANGE}; box-shadow: 0 6px 20px rgba(255,159,28,0.18); }}
[data-testid="stMetric"] {{ padding: 0.9rem 1.1rem; }}
[class*="st-key-panel-step-"] {{ min-height: 12.5rem; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: 0.95rem; font-weight: 500; }}
[data-testid="stMetricValue"] {{ color: {NAVY}; font-weight: 700; }}

/* Primary buttons: orange with navy text (white on orange fails contrast) */
button[kind^="primary"], [data-testid^="stBaseButton-primary"] {{ color: {NAVY} !important; font-weight: 700; }}
button[kind^="primary"] p, [data-testid^="stBaseButton-primary"] p {{ color: {NAVY} !important; font-weight: 700; }}
[data-testid="stSliderThumbValue"], [data-testid="stSliderThumbValue"] * {{ color: {NAVY} !important; font-weight: 600; }}

/* Header */
.rw-tagline {{ color: {NAVY}; font-size: 1.35rem; font-weight: 600; margin: 0.2rem 0 0; }}
.rw-sub {{ color: {MUTED}; font-size: 1rem; margin: 0.15rem 0 0; }}
.rw-city {{ display: inline-flex; align-items: center; gap: 0.4rem; float: right; margin-top: 0.9rem;
	background: #EAF2FD; color: {NAVY}; border: 1px solid {LIGHT_BLUE}; border-radius: 999px;
	padding: 0.35rem 0.9rem; font-weight: 600; font-size: 0.95rem; }}
.rw-dot {{ width: 0.55rem; height: 0.55rem; border-radius: 50%; background: {BLUE}; display: inline-block; }}

/* Text helpers */
.rw-eyebrow {{ color: {MUTED}; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }}
.rw-h3 {{ margin: 0.1rem 0 0.2rem; padding: 0; font-size: 1.45rem; font-weight: 700; color: {NAVY}; }}
.rw-muted {{ color: {MUTED}; font-size: 0.98rem; margin-bottom: 0.6rem; }}
.rw-chip {{ display: inline-block; background: #FFF4E3; color: {NAVY}; border-radius: 999px;
	padding: 0.25rem 0.75rem; font-size: 0.9rem; font-weight: 500; margin-top: 0.4rem; }}

/* Ranked cards */
.rw-card-head {{ display: flex; align-items: center; gap: 0.6rem; }}
.rw-badge {{ flex: none; min-width: 2.1rem; height: 2.1rem; border-radius: 10px; display: inline-flex;
	align-items: center; justify-content: center; font-weight: 700; background: {NAVY}; color: #FFFFFF; }}
.rw-badge-top {{ background: {ORANGE}; color: {NAVY}; }}
.rw-card-title {{ font-weight: 600; color: {NAVY}; line-height: 1.25; }}
.rw-card-type {{ color: {MUTED}; font-size: 0.88rem; }}
.rw-card-stats {{ display: flex; flex-wrap: wrap; gap: 0.2rem 0.9rem; color: {NAVY}; font-size: 0.93rem; margin-left: 2.7rem; }}
.rw-card-stats span {{ white-space: nowrap; }}
.rw-card-stats b {{ font-weight: 700; }}

/* Empty state */
.rw-step {{ font-size: 0.85rem; font-weight: 700; color: {MUTED}; letter-spacing: 0.06em; text-transform: uppercase; }}
.rw-step-title {{ font-size: 1.3rem; font-weight: 700; color: {NAVY}; margin: 0.2rem 0 0.3rem; }}
.rw-step-body {{ color: {MUTED}; font-size: 1rem; line-height: 1.5; }}
.rw-step-icon {{ width: 2.6rem; height: 2.6rem; border-radius: 12px; display: inline-flex; align-items: center;
	justify-content: center; font-size: 1.4rem; margin-bottom: 0.5rem; }}

/* Proposal letter */
.st-key-panel-letter-body {{ background: #FFFDF8; border-left: 4px solid {YELLOW}; box-shadow: none; padding: 1.5rem 2rem; }}
.st-key-panel-letter-body p, .st-key-panel-letter-body li {{ font-size: 1.05rem; line-height: 1.65; }}
</style>
"""
