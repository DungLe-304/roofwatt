"""Detail panel for one ranked building: roof image + key numbers, each with how it was computed and its source."""

import config
from models.roof import M2_PER_FT2

S = config.SOURCES


def detailFacts(row: dict, building=None) -> list[dict]:
	"""[{label, value, help}] for one rankBuildings row; values come from the row, tooltips from config."""
	facts = [
		("Payback", f"{row['simplePaybackYr']:.2f} yr",
			"Net cost after ITC ÷ annual savings. Simple payback: no panel degradation, rate escalation or O&M."),
		("Annual savings", f"${row['annualSavingsUsd']:,.0f}/yr",
			f"Energy × ${config.ELECTRICITY_RATE_USD_PER_KWH}/kWh. Source: {S['ELECTRICITY_RATE_USD_PER_KWH']}. "
			"All-in average rate (includes demand charges)."),
		("Net cost after ITC", f"${row['netCapexUsd']:,.0f}",
			f"Installed cost × (1 − {config.INCENTIVE_PCT:.0%}). Source: {S['INCENTIVE_PCT']}."),
		("CO₂ avoided", f"{row['co2TonsPerYear']:,.0f} t/yr",
			f"Energy × {config.GRID_EF_KG_PER_KWH:.4f} kg/kWh ÷ 1000. Source: {S['GRID_EF_KG_PER_KWH']}."),
		("System size", f"{row['systemKw']:,.0f} kW",
			f"Usable roof × {config.POWER_DENSITY_KW_PER_M2:.4f} kW/m². Source: {S['POWER_DENSITY_KW_PER_M2']}."),
		("Energy", f"{row['annualKwh'] / 1000:,.0f} MWh/yr",
			f"Annual AC output, tilt {config.TILT_DEG}°, azimuth 180°, losses {config.PVWATTS_LOSSES_PCT}%. "
			f"Source: {S['PVWATTS']}."),
		("Installed cost", f"${row['capexUsd']:,.0f}",
			f"System size × ${row['costPerWattUsd']:g}/W (median price for this system size). "
			f"Source: {S['COST_PER_WATT_BY_SIZE_KW']}."),
		("Usable roof", f"{row['usableRoofM2']:,.0f} m²",
			f"Gross area ÷ stories × {M2_PER_FT2} m²/ft² × usable factor {config.USABLE_FACTOR}. "
			f"Usable factor: {S['USABLE_FACTOR']}. Gross area and stories: {S['BUILDING']}."),
	]
	if building is not None:
		parts = [f"{building.buildingSqft:,.0f} ft²" if building.buildingSqft else None,
			f"{building.stories} stories" if building.stories else None,
			f"built {building.yearBuilt}" if building.yearBuilt else None]
		if any(parts):
			facts.append(("Building", " · ".join(part for part in parts if part), f"Source: {S['BUILDING']}."))
	return [{"label": label, "value": value, "help": help} for label, value, help in facts]


def selectedIndex(selection, rowCount: int) -> int:
	"""Row picked in the ranked table, or 0 (the top building) when nothing valid is selected."""
	rows = ((selection or {}).get("selection") or {}).get("rows") or []
	return rows[0] if rows and 0 <= rows[0] < rowCount else 0


def showDetail(row: dict, imagePath: str | None, imageError: str | None, building=None) -> None:
	import streamlit as st

	name = row.get("address") or f"Building {row['buildingId']}"
	st.markdown(f"**#{row['rank']} · {name}** (building {row['buildingId']})")
	facts = detailFacts(row, building)
	imageColumn, numbersColumn = st.columns([2, 3])
	with imageColumn:
		if imagePath:
			st.image(imagePath, caption="Aerial roof image (Vexcel Imaging)", width="stretch")
		else:
			st.caption(f"No roof image: {imageError or 'not available'}")
	with numbersColumn:
		metrics = [fact for fact in facts if fact["label"] != "Building"]
		for start in range(0, len(metrics), 2):
			for column, fact in zip(st.columns(2), metrics[start:start + 2]):
				column.metric(fact["label"], fact["value"], help=fact["help"])
		for fact in facts:
			if fact["label"] == "Building":
				st.caption(f"{fact['value']} · {fact['help']}")
