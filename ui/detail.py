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


# Display order follows the calculation chain, roof to payback.
ORDER = ["Usable roof", "System size", "Energy · kWh/yr", "Annual savings", "Installed cost", "Net cost after ITC",
	"Payback", "CO₂ avoided"]
DELTA_FIELDS = {"Payback": ("simplePaybackYr", "{:+.2f} yr"), "Annual savings": ("annualSavingsUsd", "{:+,.0f} $/yr"),
	"Net cost after ITC": ("netCapexUsd", "{:+,.0f} $"), "System size": ("systemKw", "{:+,.0f} kW"),
	"Energy · kWh/yr": ("annualKwh", "{:+,.0f}"), "CO₂ avoided": ("co2TonsPerYear", "{:+,.0f} t/yr"),
	"Installed cost": ("capexUsd", "{:+,.0f} $"), "Usable roof": ("usableRoofM2", "{:+,.0f} m²")}


def whatIfChange(label: str, row: dict, baseline: dict | None) -> str | None:
	"""Signed change of one metric against the sourced-default row, or None when there is none to show."""
	if baseline is None or label not in DELTA_FIELDS:
		return None
	field, pattern = DELTA_FIELDS[label]
	change = row[field] - baseline[field]
	return pattern.format(change) if abs(change) >= 0.005 else None


def showDetail(row: dict, imagePath: str | None, imageError: str | None, building=None, *,
		baseline: dict | None = None, assumptions: dict | None = None, propertyType: str | None = None) -> None:
	"""Aerial roof image beside a key-value list; every row's tooltip gives the formula and its source."""
	import streamlit as st

	facts = {fact["label"]: fact for fact in detailFacts(row, building, assumptions)}
	details = [propertyType, f"CoStar ID {row['buildingId']}"] + ([facts["Building"]["value"]] if "Building" in facts else [])
	st.markdown(f"<p class='rw-lede'>{' · '.join(part for part in details if part)}</p>", unsafe_allow_html=True)
	imageColumn, listColumn = st.columns([5, 7], gap="large")
	with imageColumn:
		if imagePath:
			st.image(imagePath, caption="Aerial roof image · Vexcel Imaging", width="stretch")
		else:
			st.info(f"Aerial image unavailable: {imageError or 'not available'}")
		usable = (assumptions or {}).get("usableFactor", config.USABLE_FACTOR)
		st.caption(f"Roof method: {ROOF_METHOD} {usable}", help=f"Usable factor: {S['USABLE_FACTOR']}. CoStar has no roof "
			"footprint, so footprint = gross building area ÷ stories.")
	with listColumn:
		for index, label in enumerate(ORDER):
			fact = facts[label]
			with st.container(key=f"kv-{index}"):
				name, value = st.columns([3, 2], vertical_alignment="center")
				name.markdown(label, help=fact["help"])
				change = whatIfChange(label, row, baseline)
				note = f"<span class='rw-kv-delta'>{change} vs sourced defaults</span>" if change else ""
				value.markdown(f"<div class='rw-kv-value'>{fact['value']}{note}</div>", unsafe_allow_html=True)
