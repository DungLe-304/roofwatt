"""Streamlit building blocks for the RoofWatt page (layout and display only; no business logic)."""

import base64
import html
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import config
from ui.theme import CSS, NAVY
from ui.whatif import defaultAssumptions

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DEMO_QUERY = "Find the 10 office buildings in Houston with the best solar payback and draft a pitch for the top one."
EXAMPLE_QUERIES = {
	"Top 10 + pitch": DEMO_QUERY,
	"Large offices only": "Rank Houston office buildings over 200,000 sq ft by solar payback and pitch the top one.",
	"Quick top 5": "Which 5 Houston office buildings have the fastest solar payback? Draft a short pitch for the best one.",
}


def injectCss() -> None:
	st.markdown(CSS, unsafe_allow_html=True)


def header(city: str = "Houston, TX") -> None:
	logo = base64.b64encode((ASSETS / "roofwatt-logo.svg").read_bytes()).decode()
	with st.container(key="panel-header"):
		left, right = st.columns([4, 1], vertical_alignment="center")
		with left:
			st.markdown(f"<div style='display:flex;align-items:center;gap:1.25rem'>"
				f"<img src='data:image/svg+xml;base64,{logo}' alt='RoofWatt' style='height:72px'/>"
				f"<div><p class='rw-tagline'>Solar leads from every rooftop</p>"
				f"<p class='rw-sub'>AI agent that ranks commercial roofs by solar payback and drafts the owner pitch</p></div></div>",
				unsafe_allow_html=True)
		with right:
			st.markdown(f"<span class='rw-city'><span class='rw-dot'></span>{html.escape(city)}</span>", unsafe_allow_html=True)


def _useExample() -> None:
	choice = st.session_state.get("exampleChips")
	if choice:
		st.session_state.query = EXAMPLE_QUERIES[choice]
	st.session_state.exampleChips = None


def queryBar(disabled: bool = False) -> tuple[str, bool]:
	"""Prefilled query box, example chips and the Run button. Returns (query, run clicked)."""
	st.session_state.setdefault("query", DEMO_QUERY)
	with st.container(key="panel-query"):
		query = st.text_area("Ask RoofWatt", key="query", height=80, label_visibility="collapsed",
			placeholder="Ask about Houston commercial rooftops…")
		chips, button = st.columns([4, 1], vertical_alignment="center")
		with chips:
			st.pills("Try an example", list(EXAMPLE_QUERIES), key="exampleChips", on_change=_useExample,
				label_visibility="collapsed")
		with button:
			run = st.button("Run analysis", type="primary", icon=":material/bolt:", width="stretch", disabled=disabled)
	return query.strip(), run


def emptyState() -> None:
	steps = [
		(":material/travel_explore:", "1 · Scan", "Every office building in the CoStar Houston extract: size, stories, location."),
		(":material/solar_power:", "2 · Analyze", "Usable roof area → NREL PVWatts energy → savings, payback and CO₂ avoided, "
			"with every assumption cited."),
		(":material/edit_note:", "3 · Pitch", "Ranks the best paybacks, shows the roof from the air and drafts a proposal "
			"letter to the owner."),
	]
	for column, (icon, title, body) in zip(st.columns(3, gap="medium"), steps):
		with column, st.container(key=f"panel-step-{title[0]}"):
			st.markdown(f"#### {icon} {title}")
			st.markdown(f"<div class='rw-step-body'>{body}</div>", unsafe_allow_html=True)
	st.caption("Press **Run analysis** to try the demo query, or pick an example above.")


def kpiRow(result: dict, rows: list[dict]) -> None:
	excluded = result.get("excluded") or {}
	shown = len(rows)
	cards = [
		("Buildings analyzed", f"{result.get('totalMatches', shown):,}",
			f"{result.get('propertyType', '')} buildings in {result.get('city', '')} screened by rankBuildings: "
			f"{result.get('rankedCount', shown)} ranked, {excluded.get('belowMinimumSize', 0)} below "
			f"{config.MIN_SYSTEM_KW} kW, {len(excluded.get('errors') or [])} with data errors."),
		(f"Solar capacity · top {shown}", f"{sum(r['systemKw'] for r in rows):,.0f} kW",
			f"Sum of system sizes of the {shown} buildings shown. Usable roof × {config.POWER_DENSITY_KW_PER_M2:.4f} kW/m² "
			f"({config.SOURCES['POWER_DENSITY_KW_PER_M2']})."),
		(f"Annual savings · top {shown}", f"${sum(r['annualSavingsUsd'] for r in rows):,.0f}/yr",
			f"Sum over the {shown} buildings shown. Energy × electricity rate ({config.SOURCES['ELECTRICITY_RATE_USD_PER_KWH']})."),
		(f"CO₂ avoided · top {shown}", f"{sum(r['co2TonsPerYear'] for r in rows):,.0f} t/yr",
			f"Sum over the {shown} buildings shown. Energy × grid emission factor ({config.SOURCES['GRID_EF_KG_PER_KWH']})."),
	]
	for column, (label, value, help) in zip(st.columns(4, gap="medium"), cards):
		column.metric(label, value, help=help)


def _select(buildingId: str) -> None:
	st.session_state.selectedId = buildingId


def rankedCards(rows: list[dict], propertyType: str, selectedId: str, height: int) -> None:
	"""Top buildings as compact cards; the Details button selects one for the detail panel."""
	with st.container(height=height, border=False):
		for row in rows:
			buildingId = str(row["buildingId"])
			selected = buildingId == str(selectedId)
			with st.container(key=f"card-{'sel-' if selected else ''}{buildingId}"):
				badge = "rw-badge rw-badge-top" if row["rank"] == 1 else "rw-badge"
				name = html.escape(row.get("address") or f"Building {buildingId}")
				flag = " · <b>below 50 kW</b>" if row.get("belowMinimumSize") else ""
				text, action = st.columns([5, 2], vertical_alignment="center")
				with text:
					st.markdown(f"<div class='rw-card-head'><span class='{badge}'>{row['rank']}</span><div>"
						f"<div class='rw-card-title'>{name}</div><div class='rw-card-type'>{html.escape(propertyType)}{flag}"
						f"</div></div></div>", unsafe_allow_html=True)
				with action:
					st.button("Viewing" if selected else "Details", key=f"pick-{buildingId}", type="tertiary",
						icon=":material/visibility:" if selected else ":material/chevron_right:",
						on_click=_select, args=(buildingId,), disabled=selected, width="stretch")
				st.markdown(f"<div class='rw-card-stats'><span><b>{row['simplePaybackYr']:.2f} yr</b> payback</span>"
					f"<span><b>${row['annualSavingsUsd']:,.0f}</b>/yr</span><span><b>{row['co2TonsPerYear']:,.0f} t</b> CO₂</span>"
					f"</div>", unsafe_allow_html=True)


def copyButton(text: str) -> None:
	"""Copy-to-clipboard button (components iframe; Streamlit allows clipboard-write there)."""
	components.html(f"""
	<style>body {{ margin: 0; }}</style>
	<button id="copy" style="width:100%;height:40px;border-radius:12px;border:1px solid #DCE3EC;background:#fff;
		color:{NAVY};font:600 16px Inter,system-ui,sans-serif;cursor:pointer">Copy</button>
	<script>
	const text = {json.dumps(text)};
	const button = document.getElementById("copy");
	button.onclick = async () => {{
		try {{ await navigator.clipboard.writeText(text); }}
		catch (e) {{ const area = document.createElement("textarea"); area.value = text; document.body.appendChild(area);
			area.select(); document.execCommand("copy"); area.remove(); }}
		button.textContent = "Copied ✓"; setTimeout(() => button.textContent = "Copy", 1600);
	}};
	</script>""", height=44)


def proposalPanel(proposal: str, title: str, fileStem: str, model: str | None) -> None:
	with st.container(key="panel-letter"):
		head, copy, download = st.columns([6, 1.2, 1.8], vertical_alignment="center")
		with head:
			st.markdown(f"<div class='rw-eyebrow'>Drafted by the agent</div><h3 class='rw-h3'>{html.escape(title)}</h3>",
				unsafe_allow_html=True)
		with copy:
			copyButton(proposal)
		with download:
			st.download_button("Download .md", proposal, file_name=f"{fileStem}.md", mime="text/markdown",
				icon=":material/download:", width="stretch")
		with st.container(key="panel-letter-body"):
			st.markdown(proposal)
		notes = "Numbers in the letter come from the agent's tool results. Simple payback; the 30% ITC requires the " \
			"system to be placed in service by 2027-12-31."
		st.caption(f"{notes} {model or ''}".strip())


def assumptionsSidebar() -> None:
	"""What-if inputs; Recalculate stores them in st.session_state.assumptions (None = sourced defaults)."""
	defaults = defaultAssumptions()
	current = st.session_state.get("assumptions") or defaults
	st.markdown("### :material/tune: Assumptions")
	st.caption("What-if values recalculate the buildings shown, without re-running the agent.")
	with st.form("assumptionsForm", border=False):
		rate = st.number_input("Electricity rate ($/kWh)", min_value=0.01, max_value=0.50, step=0.005, format="%.4f",
			value=float(current["ratePerKwh"]))
		st.caption(f"Default ${defaults['ratePerKwh']} · {config.SOURCES['ELECTRICITY_RATE_USD_PER_KWH']}")
		useFlat = st.toggle("Flat installed price", value=current["flatCostPerWatt"] is not None)
		flat = st.slider("Installed cost ($/W)", min_value=1.0, max_value=4.0, step=0.05,
			value=float(current["flatCostPerWatt"] or 2.1))
		st.caption(f"Default: median by system size ($1.9–3.6/W) · {config.SOURCES['COST_PER_WATT_BY_SIZE_KW']}")
		incentive = st.slider("Incentive (ITC) %", min_value=0, max_value=50, step=5, value=round(current["incentivePct"] * 100))
		st.caption(f"Default {defaults['incentivePct']:.0%} · {config.SOURCES['INCENTIVE_PCT']}")
		usable = st.slider("Usable roof factor", min_value=0.30, max_value=0.90, step=0.05, value=float(current["usableFactor"]))
		st.caption(f"Default {defaults['usableFactor']} · {config.SOURCES['USABLE_FACTOR']}")
		if st.form_submit_button("Recalculate", type="primary", icon=":material/calculate:", width="stretch"):
			chosen = {"ratePerKwh": round(rate, 4), "flatCostPerWatt": round(flat, 2) if useFlat else None,
				"incentivePct": incentive / 100, "usableFactor": round(usable, 2)}
			st.session_state.assumptions = None if chosen == defaults else chosen
	if st.session_state.get("assumptions"):
		if st.button("Reset to sourced defaults", icon=":material/restart_alt:", width="stretch"):
			st.session_state.assumptions = None
			st.rerun()


def propertySearchSidebar() -> tuple[bool, dict]:
	"""Khoa's structured search form. Returns (submitted, filters)."""
	with st.expander("Property search (structured)", icon=":material/filter_alt:"):
		with st.form("propertyFilters", border=False):
			filters = {
				"city": st.selectbox("City", ["Houston", "Los Angeles"], index=0),
				"propertyType": st.selectbox("Property type", ["Office", "Industrial", "GeneralRetail", "Flex",
					"Multifamily", "Hospitality"], index=0),
				"minGrossArea": st.number_input("Minimum gross area (sq ft)", min_value=0, value=10000, step=1000),
				"limit": int(st.number_input("Number of properties", min_value=1, max_value=20, value=10, step=1)),
				"mode": st.radio("Mode", ["Rank", "Search"], index=0, horizontal=True,
					help="Rank orders buildings by solar payback; Search lists matching buildings."),
				"randomize": st.checkbox("Randomize search results", value=False),
			}
			submitted = st.form_submit_button("Run search", width="stretch")
	return submitted, filters
