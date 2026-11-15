"""Streamlit building blocks for the RoofWatt pages (layout and display only; no business logic)."""

import base64
import html
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import config
from ui.whatif import defaultAssumptions

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DEMO_QUERY = "Find the 10 office buildings in Houston with the best solar payback and draft a pitch for the top one."
EXAMPLE_QUERIES = {
	"Top 10 and a pitch": DEMO_QUERY,
	"Large offices only": "Rank Houston office buildings over 200,000 sq ft by solar payback and pitch the top one.",
	"Quick top 5": "Which 5 Houston office buildings have the fastest solar payback? Draft a short pitch for the best one.",
}


def darkTheme() -> bool:
	"""True when Streamlit reports the dark theme (can lag one rerun right after the viewer switches)."""
	try:
		return st.context.theme.type == "dark"
	except Exception:  # no browser context (tests) or an older client
		return False


AI_MODES = {"cloud": ":material/cloud: Cloud", "local": ":material/computer: Local"}


def aiEngine(localModels: list[str], localProblem: str | None, geminiReady: bool, defaultLocal: str) -> str | None:
	"""Cloud / Local switch (st.session_state.aiMode) and, in Local mode, the Ollama model picker
	(st.session_state.localModel). Returns why the agent cannot run in the chosen mode, or None."""
	st.segmented_control("AI engine", list(AI_MODES), format_func=AI_MODES.get, key="aiMode", required=True,
		width="stretch")
	if st.session_state.get("fallbackNote"):
		st.caption(st.session_state.fallbackNote)
	if st.session_state.aiMode == "local":
		if localModels:
			if st.session_state.get("localModel") not in localModels:
				st.session_state.localModel = defaultLocal if defaultLocal in localModels else localModels[0]
			_status("Ollama", True, "Models are listed from Ollama on this machine.")
			st.selectbox("Local model", localModels, key="localModel", help="Models pulled into Ollama on this machine.")
			return None
		problem = localProblem or "Ollama is running but has no models yet."
		_status("Ollama", False, f"{problem} Install Ollama and pull any model, for example `ollama pull {defaultLocal}` "
			"(suggested).")
		return problem
	if not geminiReady:
		_status("Gemini", False, "GOOGLE_API_KEY is not set. Add it to .env.")
		return "GOOGLE_API_KEY is not set, so the cloud model cannot run."
	_status("Gemini", True, "Gemini API. Switches to the local model if the free quota runs out.")
	return None


def _status(engine: str, active: bool, help: str) -> None:
	st.markdown(f"{engine}: {':green[Active]' if active else ':red[Offline]'}", help=help)


def sidebar(pages: dict, city: str, engine=None):
	"""Brand, the five page links, the AI engine switch (`engine()`), and a footer pinned to the bottom.
	Returns (placeholder for the model label, engine result); the label is filled after the page has run."""
	logo = base64.b64encode((ASSETS / "roofwatt-logo-square.svg").read_bytes()).decode()
	st.markdown(f"<div class='rw-brand'><img src='data:image/svg+xml;base64,{logo}' alt=''/><span>RoofWatt</span></div>",
		unsafe_allow_html=True)
	for page in pages.values():
		st.page_link(page)
	problem = engine() if engine else None
	with st.container(key="sidebar-foot"):
		st.markdown(html.escape(city))
		st.markdown("Appearance follows your system. Change it in the menu at the top right.")
		model = st.empty()
		st.markdown("Built at HackPrinceton F26")
	return model, problem


def emptyState(analyzePage) -> None:
	st.markdown("No analysis yet.")
	st.page_link(analyzePage, label="Run one on the Analyze page")


def _useExample() -> None:
	choice = st.session_state.get("exampleChips")
	if choice:
		st.session_state.query = EXAMPLE_QUERIES[choice]
	st.session_state.exampleChips = None


def queryForm(default: str = DEMO_QUERY, disabled: bool = False) -> tuple[str, bool]:
	"""Prefilled query field, example chips and the Run button. Returns (query, run clicked)."""
	st.session_state.setdefault("query", default)  # widget state is dropped while another page is shown
	query = st.text_area("Question", key="query", height=96, label_visibility="collapsed",
		placeholder="Ask about Houston commercial rooftops")
	chips, button = st.columns([4, 1], vertical_alignment="center")
	with chips:
		st.pills("Examples", list(EXAMPLE_QUERIES), key="exampleChips", on_change=_useExample, label_visibility="collapsed")
	with button:
		run = st.button("Run analysis", type="primary", width="stretch", disabled=disabled)
	return query.strip(), run


def structuredSearch(disabled: bool = False) -> tuple[bool, dict]:
	"""Khoa's structured search form, tucked under the query. Returns (submitted, filters)."""
	with st.expander("Structured search"):
		with st.form("propertyFilters", border=False):
			left, right = st.columns(2)
			filters = {
				"city": left.selectbox("City", ["Houston", "Los Angeles"], index=0),
				"propertyType": right.selectbox("Property type", ["Office", "Industrial", "GeneralRetail", "Flex",
					"Multifamily", "Hospitality"], index=0),
				"minGrossArea": left.number_input("Minimum gross area (sq ft)", min_value=0, value=10000, step=1000),
				"limit": int(right.number_input("Number of properties", min_value=1, max_value=20, value=10, step=1)),
				"mode": left.radio("Mode", ["Rank", "Search"], index=0, horizontal=True,
					help="Rank orders buildings by solar payback; Search lists matching buildings."),
				"randomize": right.checkbox("Randomize search results", value=False),
			}
			submitted = st.form_submit_button("Run search", disabled=disabled)
	return submitted, filters


def kpiRow(result: dict, rows: list[dict]) -> None:
	excluded = result.get("excluded") or {}
	shown = len(rows)
	tiles = [
		("Buildings analyzed", f"{result.get('totalMatches', shown):,}",
			f"{result.get('propertyType', '')} buildings in {result.get('city', '')} screened by rankBuildings: "
			f"{result.get('rankedCount', shown)} ranked, {excluded.get('belowMinimumSize', 0)} below "
			f"{config.MIN_SYSTEM_KW} kW, {len(excluded.get('errors') or [])} with data errors."),
		(f"Capacity, top {shown}", f"{sum(r['systemKw'] for r in rows):,.0f} kW",
			f"Solar capacity: sum of system sizes of the {shown} buildings shown. Usable roof × {config.POWER_DENSITY_KW_PER_M2:.4f} kW/m² "
			f"({config.SOURCES['POWER_DENSITY_KW_PER_M2']})."),
		(f"Savings/yr, top {shown}", f"${sum(r['annualSavingsUsd'] for r in rows):,.0f}",
			f"Annual savings, summed over the {shown} buildings shown. Energy × electricity rate "
			f"({config.SOURCES['ELECTRICITY_RATE_USD_PER_KWH']})."),
		(f"CO₂ avoided, top {shown}", f"{sum(r['co2TonsPerYear'] for r in rows):,.0f} t/yr",
			f"Sum over the {shown} buildings shown. Energy × grid emission factor ({config.SOURCES['GRID_EF_KG_PER_KWH']})."),
	]
	for column, (label, value, help) in zip(st.columns(4, gap="medium"), tiles):
		column.metric(label, value, help=help, border=True)


def rankedList(rows: list[dict], selectedId: str, height: int, onView) -> None:
	"""Top buildings as flat rows; #1 carries a small orange dot. View opens the Building page via `onView(id)`."""
	with st.container(height=height, border=False):
		for row in rows:
			buildingId = str(row["buildingId"])
			selected = buildingId == str(selectedId)
			with st.container(key=f"row-{'sel-' if selected else ''}{buildingId}"):
				text, action = st.columns([6, 1.4], vertical_alignment="center")
				name = html.escape(row.get("address") or f"Building {buildingId}")
				dot = "<span class='rw-dot' title='Best payback'></span>" if row["rank"] == 1 else ""
				flag = " · below 50 kW" if row.get("belowMinimumSize") else ""
				text.markdown(f"<div class='rw-row'><span class='rw-rank'>{row['rank']}</span>"
					f"<span class='rw-row-title'>{name}{dot}</span></div>"
					f"<div class='rw-row-stats'><b>{row['simplePaybackYr']:.2f} yr</b> payback · "
					f"<b>${row['annualSavingsUsd']:,.0f}</b>/yr · <b>{row['co2TonsPerYear']:,.0f} t</b> CO₂/yr{flag}</div>",
					unsafe_allow_html=True)
				action.button("View", key=f"view-{buildingId}", type="tertiary", on_click=onView, args=(buildingId,),
					width="stretch")


def copyButton(text: str, dark: bool) -> None:
	"""Copy-to-clipboard button (components iframe; Streamlit allows clipboard-write there)."""
	ink, paper, line = ("#F5F5F7", "#1C1C1E", "#38383A") if dark else ("#1D1D1F", "#FFFFFF", "#E5E5EA")
	components.html(f"""
	<style>body {{ margin: 0; }}</style>
	<button id="copy" style="width:100%;height:40px;border-radius:12px;border:1px solid {line};background:{paper};
		color:{ink};font:500 16px Inter,-apple-system,system-ui,sans-serif;cursor:pointer">Copy</button>
	<script>
	const text = {json.dumps(text)};
	const button = document.getElementById("copy");
	button.onclick = async () => {{
		try {{ await navigator.clipboard.writeText(text); }}
		catch (e) {{ const area = document.createElement("textarea"); area.value = text; document.body.appendChild(area);
			area.select(); document.execCommand("copy"); area.remove(); }}
		button.textContent = "Copied"; setTimeout(() => button.textContent = "Copy", 1600);
	}};
	</script>""", height=42)


def letter(proposal: str, fileStem: str, model: str | None) -> None:
	"""The drafted letter in one readable column with Copy and Download."""
	with st.container(key="letter"):
		note, copy, download = st.columns([5, 1.3, 2], vertical_alignment="center")
		note.markdown("<span class='rw-muted'>Drafted by the agent from its tool results.</span>", unsafe_allow_html=True)
		with copy:
			copyButton(proposal, darkTheme())
		download.download_button("Download .md", proposal, file_name=f"{fileStem}.md", mime="text/markdown", width="stretch")
		with st.container(key="letter-body"):
			st.markdown(proposal)
		st.caption("Simple payback. The 30% ITC requires the system to be placed in service by 2027-12-31. "
			f"{model or ''}".strip())


def assumptionsForm() -> bool:
	"""Grouped what-if inputs with source notes. Stores st.session_state.assumptions (None = sourced defaults).

	Returns True when Recalculate was pressed.
	"""
	defaults = defaultAssumptions()
	current = st.session_state.get("assumptions") or defaults
	with st.form("assumptionsForm", border=False, enter_to_submit=False):
		energy, cost, roof = st.columns(3, gap="large")
		with energy:
			st.markdown("<p class='rw-label'>Electricity</p>", unsafe_allow_html=True)
			rate = st.number_input("Rate ($/kWh)", min_value=0.01, max_value=0.50, step=0.005, format="%.4f",
				value=float(current["ratePerKwh"]))
			st.caption(f"Default ${defaults['ratePerKwh']}. {config.SOURCES['ELECTRICITY_RATE_USD_PER_KWH']}.")
		with cost:
			st.markdown("<p class='rw-label'>Cost and incentive</p>", unsafe_allow_html=True)
			useFlat = st.toggle("Use one flat installed price", value=current["flatCostPerWatt"] is not None)
			flat = st.slider("Installed cost ($/W)", min_value=1.0, max_value=4.0, step=0.05,
				value=float(current["flatCostPerWatt"] or 2.1))
			st.caption(f"Default: median by system size, $1.9 to $3.6/W. {config.SOURCES['COST_PER_WATT_BY_SIZE_KW']}.")
			incentive = st.slider("Incentive (ITC) %", min_value=0, max_value=50, step=5, value=round(current["incentivePct"] * 100))
			st.caption(f"Default {defaults['incentivePct']:.0%}. {config.SOURCES['INCENTIVE_PCT']}.")
		with roof:
			st.markdown("<p class='rw-label'>Roof</p>", unsafe_allow_html=True)
			usable = st.slider("Usable roof factor", min_value=0.30, max_value=1.00, step=0.05, value=float(current["usableFactor"]))
			st.caption(f"Default {defaults['usableFactor']}. {config.SOURCES['USABLE_FACTOR']}.")
		pressed = st.form_submit_button("Recalculate", type="primary")
		if pressed:
			chosen = {"ratePerKwh": round(rate, 4), "flatCostPerWatt": round(flat, 2) if useFlat else None,
				"incentivePct": incentive / 100, "usableFactor": round(usable, 2)}
			st.session_state.assumptions = None if chosen == defaults else chosen
	return pressed
