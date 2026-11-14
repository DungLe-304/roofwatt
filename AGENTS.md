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
| Agent | LangChain `deepagents` + Gemini (`google_genai:gemini-4-hydrogen`, key `GOOGLE_API_KEY`) |
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
cp .env.example .env        # fill VEXCEL/MATTERPORT/NLR/GOOGLE keys (CoStar is a local extract, needs git lfs)
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
Claude Code (Fable 5.2) — 2026-11-14

## Current Objective
Agent answers the demo query end-to-end over all Houston offices. Next: Streamlit UI, imagery.

## Completed
- Step 1: scaffold (`004236f`). `AGENTS.md` + `docs/PROJECT_PLAN.md` (`7797fba`). Project plugins (`77e2b12`):
  `commit-commands`, `feature-dev`, `ui-ux-pro-max`, `andrej-karpathy-skills` (Claude Code only; skills, no hooks).
- Step 2: `models/schemas.py` dataclasses per plan §3.
- Step 3: `models/finance.py` `compute_financials(solar, *, rate_usd_per_kwh, cost_per_watt_usd, incentive_pct,
  grid_ef_kg_per_kwh)`; assumptions passed in explicitly (caller reads `config.py`). Zero savings → payback `inf`.
  `tests/test_finance.py`: 3 hand-computed cases, all passing (TDD).
- UI design system via ui-ux-pro-max → `design-system/roofwatt/MASTER.md`; theme in `.streamlit/config.toml`
  (primary `#15803D` instead of `#22C55E` for 4.5:1 contrast with white button text; system font for offline demo).
  Steps 2–3 + design system committed in `8cc0026`.
- Step 4: `models/solar.py` `estimate_solar(building_id, lat, lon, system_kw, *, tilt_deg, losses_pct=14)`.
  Endpoint `developer.nlr.gov` (NREL renamed; `developer.nrel.gov` no longer resolves). Cache: `cache/pvwatts/<hash>.json`
  keyed by request params (not `building_id`, so a new size/tilt is never a stale hit). 429 → backoff 1/2/4 s, 4 attempts.
  `tests/test_solar.py`: 7 tests, HTTP faked. Live smoke test with `DEMO_KEY`: Houston 100 kW, tilt 10° → 137,948 kWh/yr.
- Step 6: `models/roof.py` `estimate_roof(building, *, usable_factor) -> RoofResult` (tier 1). Uses `footprint_m2`,
  else `building_sqft / stories * 0.092903`; raises `ValueError` if neither is available (caller skips the building).
  `tests/test_roof.py`: 6 tests (TDD). Full suite: 16 passing.
- Env: `.env.example` restored (names only; `.env` holds real keys, gitignored). Key var is `NLR_API_KEY` (NREL renamed to NLR).
  `config.py` calls `load_dotenv(<repo>/.env, override=False)`, so any module importing `config` gets keys
  without relying on VS Code's `python.terminal.useEnvFile`.
- `config.py` filled with cited sources (verified 2026-11-14): power density 0.211 kW/m² module (DOE 2025Q1)
  × 0.70 module/roof (Gagnon 2016 T1) = 0.1477; tilt 15° (Gagnon T1); rate $0.0856 (EIA EPA T2.10, TX 2025);
  $1.98/W (DOE 2025Q1 MMP); ITC 30% (§48E); grid 733.862 lb/MWh → 0.3329 kg/kWh (eGRID2023 ERCT).
  Live sanity run (hypothetical 100k ft², 4 stories, Houston): 206 kW, 289 MWh/yr, payback 11.5 yr, 96 t CO₂/yr.
- Khoa (`f822a22`, merged into `main`): CoStar extract adapter `data/costar_client.py` (local JSONL, LFS),
  pydantic `models/schemas.py` (camelCase + snake_case aliases/properties), `config.Settings`. 21 tests pass.
  Real-data run: 185 Houston offices, all have sqft/stories/lat-lon (no footprint); 12 run through
  roof → PVWatts → finance OK (payback 11.05–11.78 yr).
- `14b775a` broke `config.py` (indentation, dropped `load_dotenv`, `rootPath` outside repo); fixed with
  `tests/test_config.py`. Run `pytest -q` before pushing.
- Agent tools (`agent/tools.py`): `analyzeRoof`, `estimateSolar`, `computeFinancials`, each taking only a
  `buildingId` and recomputing the chain (no numbers copied by the LLM); errors return `{"buildingId","error"}`;
  `inf` payback → `null`. `tests/test_tools.py` (12). LLM switched fully to Gemini: `Settings.modelName =
  "google_genai:gemini-4-hydrogen"` (agent reads it), Anthropic key/package removed, live mode needs `GOOGLE_API_KEY`.
  Live demo query: 1 search + 20 `computeFinancials`, 74 s, ranked top 10 + pitch, numbers all from tools.
- `rankBuildings(city, propertyType, minSqft, limit)`: screens every match in code (`CostarClient.allBuildings`,
  8 threads, PVWatts cached: 17 s cold, < 1 s warm), drops errors / < `MIN_SYSTEM_KW` / null payback, sorts payback
  (0.01-yr precision) asc then CO₂ desc; equal payback shares a rank (1, 1, 1, 4). Houston offices: 185 matches,
  173 ranked, 12 too small. Live demo query now: 1 `rankBuildings` + 10 `getBuilding`, 50 s. 40 tests pass.
- `uv` installed (brew); `uv.lock` regenerated for `langchain-google-genai`.

## Modified Files
- Latest session: `agent/tools.py`, `agent/agent.py`, `data/costar_client.py` (`iterMatches`/`allBuildings`),
  `config.py` (Gemini `Settings`), `tests/test_tools.py` (new), `tests/test_config.py`, `tests/test_costar_client.py`,
  `pyproject.toml`, `uv.lock`, `requirements.txt`, `.env.example`, `docs/PROJECT_PLAN.md`, `AGENTS.md`

## Known Issues
- `config.py` caveats: ITC 30% requires placed-in-service by 2027-12-31 (OBBBA) and < 1 MW AC or PWA;
  EIA rate is an all-in average (incl. demand charges); eGRID uses total-output rate, not marginal.
- Vexcel imagery API shape still unknown (`data/imagery.py` is a stub). CoStar extract has no roof footprint.
- PVWatts cache lives in `models/solar.py`; `data/cache.py` (CoStar/Vexcel) may absorb it later.
- `requirements.txt` is unpinned and lists `dotenv` (deprecated PyPI package; `python-dotenv` is the real one).
  `pyproject.toml` gets `requests`/`pydeck`/`pandas`/`pillow` only transitively.
- `USABLE_FACTOR = 0.6` is an unsourced assumption (plan §4 says label it as such in the UI).
- MASTER.md suggests Google Fonts (Fira); not used, to keep the demo offline-safe.
- PVWatts key is `NLR_API_KEY` (`.env`, `.env.example`, `models/solar.py`); `config.Settings` still has an unused
  `pvwattsApiKey` field — align or drop it.
- Proposal letter omits the ITC caveat (placed in service by 2027-12-31). Pending decision: return a `caveats`
  list from the finance tools and require it in pitches.
- `app.py`, `data/imagery.py`, `data/cache.py` are still one-line stubs: `streamlit run app.py` shows a blank page.
- `config.Settings`: `dataMode`/`agentMode`/`costarSource`/`costarExportPath`/`*ApiKey` are unused; the default
  `costarExportPath` (`../CoStar Data Extract`) does not exist.
- Tier-1 payback is nearly flat across Houston (11.05–11.78 yr; only the PVWatts weather cell varies): 12 offices
  tie at rank 1, so the top 10 is effectively ordered by CO₂/size. Needs a real differentiator (cost or rate by size).
- Repo is PUBLIC and now contains the CoStar extract (`commercial-properties.csv`, `data/*.jsonl`): check
  CoStar data terms before submission. Cloning needs `git lfs`.

## Immediate Next Steps
1. Streamlit UI (`app.py`): query box, tool trace, map, ranked table, detail, proposal — MVP blocker.
2. Khoa: Vexcel imagery in `data/imagery.py` (roof image for the detail panel).
3. Payback differentiator (size-dependent $/W or rate), then ITC `caveats` in tool output.
