"""Detail panel for one ranked building: roof image + key numbers, each with how it was computed and its source."""

import config
from models.roof import M2_PER_FT2

S = config.SOURCES
ROOF_METHOD = "Tier 1 · footprint (gross area ÷ stories) × usable factor"


def _whatIf(value: str, default: str, changed: bool) -> str:
	return f" What-if value set in the sidebar: {value} (sourced default {default})." if changed else ""


def detailFacts(row: dict, building=None, assumptions: dict | None = None) -> list[dict]:
	"""[{label, value, help}] for one ranked row; values come from the row, tooltips from config (+ what-if notes)."""
	a = assumptions or {}
	rate = a.get("ratePerKwh", config.ELECTRICITY_RATE_USD_PER_KWH)
	incentive = a.get("incentivePct", config.INCENTIVE_PCT)
	usable = a.get("usableFactor", config.USABLE_FACTOR)
	flatPrice = a.get("flatCostPerWatt")
	facts = [
		("Payback", f"{row['simplePaybackYr']:.2f} yr",
			"Net cost after ITC ÷ annual savings. Simple payback: no panel degradation, rate escalation or O&M."),
		("Annual savings", f"${row['annualSavingsUsd']:,.0f}/yr",
			f"Energy × ${rate}/kWh. Source: {S['ELECTRICITY_RATE_USD_PER_KWH']}. All-in average rate (includes demand "
			f"charges).{_whatIf(f'${rate}/kWh', f'${config.ELECTRICITY_RATE_USD_PER_KWH}/kWh', rate != config.ELECTRICITY_RATE_USD_PER_KWH)}"),
		("Net cost after ITC", f"${row['netCapexUsd']:,.0f}",
			f"Installed cost × (1 − {incentive:.0%}). Source: {S['INCENTIVE_PCT']}."
			f"{_whatIf(f'{incentive:.0%}', f'{config.INCENTIVE_PCT:.0%}', incentive != config.INCENTIVE_PCT)}"),
		("CO₂ avoided", f"{row['co2TonsPerYear']:,.0f} t/yr",
			f"Energy × {config.GRID_EF_KG_PER_KWH:.4f} kg/kWh ÷ 1000. Source: {S['GRID_EF_KG_PER_KWH']}."),
		("System size", f"{row['systemKw']:,.0f} kW",
			f"Usable roof × {config.POWER_DENSITY_KW_PER_M2:.4f} kW/m². Source: {S['POWER_DENSITY_KW_PER_M2']}."),
		("Energy · kWh/yr", f"{row['annualKwh']:,.0f}",
			f"Annual AC output, tilt {config.TILT_DEG}°, azimuth 180°, losses {config.PVWATTS_LOSSES_PCT}%. "
			f"Source: {S['PVWATTS']}."),
		("Installed cost", f"${row['capexUsd']:,.0f}",
			f"System size × ${row['costPerWattUsd']:g}/W " + ("(flat what-if price set in the sidebar; sourced default is "
			f"the median for this system size: {S['COST_PER_WATT_BY_SIZE_KW']})." if flatPrice else
			f"(median price for this system size). Source: {S['COST_PER_WATT_BY_SIZE_KW']}.")),
		("Usable roof", f"{row['usableRoofM2']:,.0f} m²",
			f"{ROOF_METHOD}: gross area ÷ stories × {M2_PER_FT2} m²/ft² × {usable}. "
			f"Usable factor: {S['USABLE_FACTOR']}. Gross area and stories: {S['BUILDING']}."
			f"{_whatIf(str(usable), str(config.USABLE_FACTOR), usable != config.USABLE_FACTOR)}"),
	]
	if building is not None:
		parts = [f"{building.buildingSqft:,.0f} ft²" if building.buildingSqft else None,
			f"{building.stories} stories" if building.stories else None,
			f"built {building.yearBuilt}" if building.yearBuilt else None]
		if any(parts):
			facts.append(("Building", " · ".join(part for part in parts if part), f"Source: {S['BUILDING']}."))
	return [{"label": label, "value": value, "help": help} for label, value, help in facts]


DELTA_FIELDS = {"Payback": ("simplePaybackYr", "{:+.2f} yr", "inverse"), "Annual savings": ("annualSavingsUsd", "{:+,.0f} $/yr", "normal"),
	"Net cost after ITC": ("netCapexUsd", "{:+,.0f} $", "inverse"), "System size": ("systemKw", "{:+,.0f} kW", "normal"),
	"Energy · kWh/yr": ("annualKwh", "{:+,.0f}", "normal"), "CO₂ avoided": ("co2TonsPerYear", "{:+,.0f} t/yr", "normal"),
	"Installed cost": ("capexUsd", "{:+,.0f} $", "inverse"), "Usable roof": ("usableRoofM2", "{:+,.0f} m²", "normal")}


def showDetail(row: dict, imagePath: str | None, imageError: str | None, building=None, *,
		baseline: dict | None = None, assumptions: dict | None = None, propertyType: str | None = None) -> None:
	"""Roof image beside the key numbers. With a what-if `baseline` row, each metric shows its change."""
	import streamlit as st

	name = row.get("address") or f"Building {row['buildingId']}"
	facts = detailFacts(row, building, assumptions)
	with st.container(key="panel-detail"):
		st.markdown(f"<div class='rw-eyebrow'>Selected building</div><h3 class='rw-h3'>#{row['rank']} · {name}</h3>",
			unsafe_allow_html=True)
		details = [propertyType, f"CoStar ID {row['buildingId']}"] + [f["value"] for f in facts if f["label"] == "Building"]
		st.markdown(f"<div class='rw-muted'>{' · '.join(part for part in details if part)}</div>", unsafe_allow_html=True)
		imageColumn, numbersColumn = st.columns([5, 7], gap="large")
		with imageColumn:
			if imagePath:
				st.image(imagePath, caption="Aerial roof image · Vexcel Imaging", width="stretch")
			else:
				st.info(f"Aerial image unavailable: {imageError or 'not available'}", icon=":material/hide_image:")
			st.markdown(f"<span class='rw-chip'>Roof method: {ROOF_METHOD} {(assumptions or {}).get('usableFactor', config.USABLE_FACTOR)}"
				f"</span>", unsafe_allow_html=True, help=f"Usable factor: {S['USABLE_FACTOR']}. CoStar has no roof footprint, "
				"so footprint = gross building area ÷ stories.")
		with numbersColumn:
			metrics = [fact for fact in facts if fact["label"] != "Building"]
			for start in range(0, len(metrics), 2):
				for column, fact in zip(st.columns(2), metrics[start:start + 2]):
					delta, color = None, "normal"
					if baseline is not None and fact["label"] in DELTA_FIELDS:
						field, pattern, color = DELTA_FIELDS[fact["label"]]
						change = row[field] - baseline[field]
						delta = pattern.format(change) if abs(change) >= 0.005 else None
					column.metric(fact["label"], fact["value"], delta=delta, delta_color=color, help=fact["help"], border=True)
