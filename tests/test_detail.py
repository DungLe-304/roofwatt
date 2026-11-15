"""Detail panel facts for one ranked building: every value comes from the tool row, every tooltip cites config."""

import config
from models.schemas import Building
from ui.detail import detailFacts

ROW = {"rank": 1, "address": "5959 Corporate Dr", "buildingId": "240117", "usableRoofM2": 7906.04, "systemKw": 1167.72,
	"annualKwh": 1660572.5, "annualSavingsUsd": 142145.01, "costPerWattUsd": 1.9, "capexUsd": 2218672.19,
	"netCapexUsd": 1553070.53, "simplePaybackYr": 10.93, "co2TonsPerYear": 552.76}


def facts_by_label(building=None):
	return {fact["label"]: fact for fact in detailFacts(ROW, building)}


def test_every_metric_is_formatted_from_the_row_and_cites_a_source():
	facts = facts_by_label()
	assert list(facts) == ["Payback", "Annual savings", "Net cost after ITC", "CO₂ avoided", "System size",
		"Energy · kWh/yr", "Installed cost", "Usable roof"]
	assert facts["Payback"]["value"] == "10.93 yr"
	assert facts["Annual savings"]["value"] == "$142,145/yr"
	assert facts["Net cost after ITC"]["value"] == "$1,553,071"
	assert facts["CO₂ avoided"]["value"] == "553 t/yr"
	assert facts["System size"]["value"] == "1,168 kW"
	assert facts["Energy · kWh/yr"]["value"] == "1,660,572"
	assert facts["Installed cost"]["value"] == "$2,218,672"
	assert facts["Usable roof"]["value"] == "7,906 m²"
	for fact in facts.values():
		assert fact["help"]


def test_tooltips_use_config_values_and_sources():
	facts = facts_by_label()
	assert f"${config.ELECTRICITY_RATE_USD_PER_KWH}/kWh" in facts["Annual savings"]["help"]
	assert config.SOURCES["ELECTRICITY_RATE_USD_PER_KWH"] in facts["Annual savings"]["help"]
	assert f"{config.INCENTIVE_PCT:.0%}" in facts["Net cost after ITC"]["help"]
	assert "2027-12-31" in facts["Net cost after ITC"]["help"]  # ITC caveat
	assert "$1.9/W" in facts["Installed cost"]["help"]  # the row's size-based price
	assert f"{config.USABLE_FACTOR}" in facts["Usable roof"]["help"] and "unsourced" in facts["Usable roof"]["help"]
	assert f"{config.TILT_DEG}°" in facts["Energy · kWh/yr"]["help"]


def test_building_facts_are_added_when_the_building_is_known():
	building = Building(buildingId="240117", propertyType="Office", buildingSqft=250000, stories=5, yearBuilt=1982)
	facts = facts_by_label(building)
	assert facts["Building"]["value"] == "250,000 ft² · 5 stories · built 1982"
	assert config.SOURCES["BUILDING"] in facts["Building"]["help"]


def test_what_if_assumptions_change_the_tooltips_and_keep_the_sourced_default():
	assumptions = {"ratePerKwh": 0.12, "flatCostPerWatt": 2.5, "incentivePct": 0.2, "usableFactor": 0.7}
	facts = {fact["label"]: fact for fact in detailFacts(ROW, None, assumptions)}
	assert "$0.12/kWh" in facts["Annual savings"]["help"] and f"default ${config.ELECTRICITY_RATE_USD_PER_KWH}/kWh" in facts["Annual savings"]["help"]
	assert "1 − 20%" in facts["Net cost after ITC"]["help"] and "default 30%" in facts["Net cost after ITC"]["help"]
	assert "flat what-if price" in facts["Installed cost"]["help"]
	assert "× 0.7." in facts["Usable roof"]["help"] and "default 0.6" in facts["Usable roof"]["help"]
	assert "What-if" not in facts_by_label()["Annual savings"]["help"]  # sourced defaults: no what-if note


def test_trace_markdown_numbers_steps_nests_todos_and_marks_errors():
	from ui.trace import traceMarkdown
	trace = [
		{"name": "write_todos", "args": "", "ok": True, "result": "ok", "summary": "planned 1 step", "todos": ["Rank offices"]},
		{"name": "computeFinancials", "args": 'buildingId="9"', "ok": False, "result": "error: missing"},
	]
	assert traceMarkdown(trace) == ("1. :material/checklist: **Plan** · planned 1 step\n    - Rank offices\n"
		"2. :material/error: **Financials** · :red[error: missing]")
