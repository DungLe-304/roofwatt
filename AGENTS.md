# AGENTS.md — RoofWatt

Single source of truth for Claude Code and OpenAI Codex. `CLAUDE.md` imports this file.
Full plan (scope, timeline, pitch, risks): `docs/PROJECT_PLAN.md`. Read it before large changes.

---

# Part 1 — Static Project Context

## Overview
RoofWatt is an AI agent (HackPrinceton Fall 2026) that finds Houston commercial rooftops with the best
solar economics: energy, savings, payback, CO₂ avoided, plus a drafted proposal letter to the owner.
- Demo query (must work end-to-end): *"Find the 10 office buildings in Houston with the best solar payback and draft a pitch for the top one."*
- Tracks: Sustainability (main); CoStar, Amazon, LangChain deepagents (special).
- Deadlines (ET): MVP Sat Nov 14 18:00 · feature freeze Sun 02:00 · Devpost submit Sun Nov 15 08:00 (target 07:30).
- Team: Tony Le (data, models, finance, UI) · Khoa Nguyen (APIs, agent, backend).

## Tech Stack
| Part | Choice |
|---|---|
| Language | Python 3.11+ (local: 3.13) |
| Agent | LangChain `deepagents` + Claude or OpenAI LLM |
| Building data / imagery | CoStar hackathon toolkit (CoStar, Vexcel; Matterport stretch). API shapes are **unverified placeholders** |
| Solar energy | NREL PVWatts v8 API |
| Images | Pillow / OpenCV (stretch: Segment Anything) |
| UI | Streamlit + pydeck |
| Cache | Local JSON/SQLite keyed by `building_id` (`cache/`, gitignored) |
| Tests | pytest |

## Key Directories
```
app.py              Streamlit UI: query box, tool trace, map, ranked table, detail, proposal
config.py           ALL assumptions, each with a source string (several still TODO)
agent/agent.py      deepagents setup + system prompt
agent/tools.py      tool wrappers exposed to the agent
data/costar_client.py  CoStar building search/details
data/imagery.py     Vexcel aerial imagery (Matterport stretch)
data/cache.py       response cache
models/schemas.py   Building, RoofResult, SolarResult, FinanceResult dataclasses
models/roof.py      usable roof area (tier 1: footprint × USABLE_FACTOR)
models/solar.py     PVWatts client (cache + 429 handling)
models/finance.py   savings, payback, CO₂ (pure functions)
tests/              pytest (test_finance.py)
docs/PROJECT_PLAN.md   full plan, data contracts, calc model, agent design
design-system/roofwatt/MASTER.md  UI design system (colors, type, spacing); read before UI work
.streamlit/config.toml  Streamlit theme derived from MASTER.md
```

## Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill COSTAR/VEXCEL/MATTERPORT/NREL/ANTHROPIC/OPENAI keys
streamlit run app.py        # run UI
pytest -q                   # run tests
```

## Core Formulas (see plan §4)
```
usable_roof_m2 = footprint_m2 * USABLE_FACTOR
system_kw      = usable_roof_m2 * POWER_DENSITY_KW_PER_M2
annual_kwh     = PVWatts(lat, lon, system_kw, array_type=1, tilt=TILT_DEG, azimuth=180, losses=14)
savings_usd    = annual_kwh * ELECTRICITY_RATE_USD_PER_KWH
capex_usd      = system_kw * 1000 * COST_PER_WATT_USD;  net = capex * (1 - INCENTIVE_PCT)
payback_yr     = net_capex / savings;  co2_t/yr = annual_kwh * GRID_EF_KG_PER_KWH / 1000
```
Ranking: drop `system_kw < 50`; sort payback ascending, tie-break CO₂ descending.

## Conventions
- English everywhere. Small, focused modules; keep `models/` pure (no network except `solar.py`).
- Data contracts in `models/schemas.py` must match plan §3; change them only with a ledger note.
- Every assumption lives in `config.py` with a cited source. **Never invent numbers**; leave TODO if unsourced.
- Watch units: W vs kW, kg vs t, ft² vs m² (1 ft² = 0.092903 m²).
- Cache every CoStar/Vexcel/PVWatts response by `building_id`; demo must run offline from cache.
- Agent: plan before tool calls; deep-analyze ≤ 20 buildings; cap ~40 tool calls; every reported number comes from a tool.
- Never commit `.env` or keys. Commit at least hourly to `main`; Tony and Khoa own separate files.
- No stretch work (SAM, Matterport, NPV) until the step-7 checkpoint (one building end-to-end) passes.

## Handoff Protocol
Before ending a session, update Part 2: set `Last Active Agent`, move finished items to `Completed`,
list touched files, record issues, and rewrite `Immediate Next Steps`. Keep Part 2 short — prune stale entries.

---

# Part 2 — Dynamic Handoff Ledger

## Last Active Agent
Claude Code (Opus 5.5) — 2026-11-14

## Current Objective
Build order step 4 of plan §6: `models/solar.py` (PVWatts v8 client).

## Completed
- Step 1: scaffold (`004236f`). `AGENTS.md` + `docs/PROJECT_PLAN.md` (`7797fba`). Project plugins (`77e2b12`):
  `commit-commands`, `feature-dev`, `ui-ux-pro-max`, `andrej-karpathy-skills` (Claude Code only; skills, no hooks).
- Step 2: `models/schemas.py` dataclasses per plan §3.
- Step 3: `models/finance.py` `compute_financials(solar, *, rate_usd_per_kwh, cost_per_watt_usd, incentive_pct,
  grid_ef_kg_per_kwh)`; assumptions passed in explicitly (caller reads `config.py`). Zero savings → payback `inf`.
  `tests/test_finance.py`: 3 hand-computed cases, all passing (TDD).
- UI design system via ui-ux-pro-max → `design-system/roofwatt/MASTER.md`; theme in `.streamlit/config.toml`
  (primary `#15803D` instead of `#22C55E` for 4.5:1 contrast with white button text; system font for offline demo).

## Modified Files
- `models/schemas.py`, `models/finance.py`, `tests/test_finance.py`
- `design-system/roofwatt/MASTER.md` (new), `.streamlit/config.toml` (new), `AGENTS.md`

## Known Issues
- `config.py`: `POWER_DENSITY_KW_PER_M2`, `TILT_DEG`, `ELECTRICITY_RATE_USD_PER_KWH`, `COST_PER_WATT_USD`,
  `INCENTIVE_PCT`, `GRID_EF_KG_PER_KWH` are `None` — need cited sources before finance runs on real data.
- CoStar/Vexcel API shapes unknown until toolkit docs are read; footprint field may be missing.
- `requirements.txt` is unpinned; no LLM provider package (`langchain-anthropic`/`langchain-openai`) listed yet.
- Ranking (drop < 50 kW, sort by payback) not implemented yet; it should also drop `inf` payback rows.
- `simple_payback_yr` can be `math.inf` → `json.dumps` emits non-standard `Infinity`; convert before caching/tool output.
- `agent/tools.py` `compute_financials` wrapper must inject the `config.py` values (plan §5 signature differs).
- MASTER.md suggests Google Fonts (Fira); not used, to keep the demo offline-safe.

## Immediate Next Steps
1. `models/solar.py` — PVWatts v8 client with caching and 429 handling.
2. Read CoStar toolkit docs → `data/costar_client.py` / `data/imagery.py` (mocks first).
3. `models/roof.py` tier 1, then step-7 checkpoint: one Houston building end-to-end.
4. Tony: fill `config.py` TODO values with cited sources.
