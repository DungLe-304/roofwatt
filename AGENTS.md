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
ui/ranking.py       ranked table + pydeck map for a rankBuildings result (rendered in app.py)
models/schemas.py   Building, RoofResult, SolarResult, FinanceResult dataclasses
models/roof.py      usable roof area (tier 1: footprint × USABLE_FACTOR)
models/solar.py     PVWatts client (cache + 429 handling)
models/finance.py   savings, payback, CO₂ (pure functions)
tests/              pytest (test_finance.py)
docs/PROJECT_PLAN.md   full plan, data contracts, calc model, agent design
index.md, schemas/, models/*.md, tools/expand_records.py   CoStar data kit docs (data in data/*.jsonl via Git LFS)
assets/             app icon
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
capex_usd      = system_kw * 1000 * cost_per_watt_for_size(system_kw, COST_PER_WATT_BY_SIZE_KW);  net = capex * (1 - INCENTIVE_PCT)
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
Agent + chat UI answer the demo query over all Houston offices. Blocked by Gemini quota. Next: imagery, UI.

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
  $1.98/W (DOE 2025Q1 MMP; later replaced by LBNL size bins); ITC 30% (§48E); grid 733.862 lb/MWh → 0.3329 kg/kWh (eGRID2023 ERCT).
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
- Khoa's merge `c093a56` dropped every function body in `agent/tools.py` (conflict resolved to his 3-line file);
  `34ad05e` then removed the names. Restored from `e5990b2`; Khoa's `randomize` search kept.
- Payback differentiator: `COST_PER_WATT_BY_SIZE_KW` (LBNL 2026 Data Update, slide 36, 2025 non-res medians:
  <=10 kW $3.6 ... >1 MW $1.9/W) via `models.finance.cost_per_watt_for_size`. Houston offices: payback 10.93-16.45 yr,
  71 distinct ranks (was 35), single rank-1. Tool rows now include `costPerWattUsd`.
- Cleanup: `Settings` trimmed to `agentMode`/`modelName` (keys read from real env names); `dotenv` package dropped,
  `requests` added to `pyproject.toml`, `socksio` to `requirements.txt`, `uv.lock` updated; README (Git LFS, uv,
  keys, tests); `app.py` icon path fixed + duplicate import removed; stub pointers -> `docs/PROJECT_PLAN.md`. 47 tests.
- Guard: `tests/test_agent.py` fails if the system prompt names a tool missing from `roofWattTools` (prompt is now
  module-level `agent.agent.systemPrompt`). Verified it catches the `34ad05e` regression.
- Plan B: `data/cache.py` (file cache `cache/<ns>/<key>.<ext>`), `data/imagery.py` `get_roof_image` (Vexcel
  ExtractOrthoImages, cached, clear errors), tool `getRoofImage`, `tools/prefetch_images.py --top 20`. 55 tests.
- Vexcel working: real API is `GET https://api.vexcelgroup.com/v2/ortho/extract` (OpenAPI at `/v2/api-docs/ortho`;
  the blog's `ExtractOrthoImages` was outdated). `VEXCEL_API_KEY` is an API key → `api_key` query param (`token`
  param and `/auth/verify` give 401). Layer `urban`, `wkt=POINT(lon lat)`, square frame = max(80 m, 1.5×√footprint),
  640 px JPEG. Top 20 Houston offices prefetched to `cache/vexcel/` (20/20, 3.1 MB, 10 s). 57 tests.
- `app.py` shows roof images: `agent/results.py` `roofImages(messages)` reads successful `getRoofImage` results;
  images render under the reply and stay in chat history (stored per message, not sent to the agent).
  `tests/test_app.py` drives the app with a fake agent (no Gemini quota). 60 tests; server health OK.
- Khoa: `bea18d2` chat scrollToBottom; `642af2b` token limits (`agent/agent.py`, `app.py`, `config.py`).
- Assets cleanup: `assets/` now holds only `roofwatt-logo.svg`, `roofwatt-logo-square.svg`,
  `roofwatt-overview-concept.png` (poster concept). Old `RoofWatt solar power icon.png` and the draft
  icon/overview files and Khoa's unused `Star.png`/`SolarPanel.png` were deleted. `app.py` `page_icon` -> `assets/roofwatt-logo-square.svg` (was a missing PNG).
- Tests green again (60): `streamlit-hotkeys` installed in `.venv`; `test_config` lists Khoa's 4 new `agent*`
  Settings fields; `app.py` stores `images` on assistant messages again (merge `9b99b6c` dropped it, so roof
  images vanished from history after the next turn).

- Ranked table + map (`ui/ranking.py`, `agent/results.py` `rankingResult`): `app.py` shows the last successful
  `rankBuildings` result under the reply (caption with scope/exclusions/unsourced usable factor, dark CARTO pydeck
  map with numbered markers, rank 1 green, tooltips; table with units in headers) and keeps it in chat history.
  Coordinates are looked up from CoStar in the UI (one pass), not added to the tool output, to save Gemini tokens.
  Map view: own `fitView` (deck.gl world = 512 px at zoom 0; `pdk.data_utils.compute_view` cropped rank 6).
  Verified in headless Chrome with the real Houston top 10. `pandas`/`pydeck` added to `pyproject.toml`. 68 tests.

## Modified Files
- Latest session: `ui/` (new), `agent/results.py`, `app.py`, `tests/test_ranking.py` (new), `tests/test_results.py`,
  `tests/test_app.py`, `pyproject.toml`, `uv.lock`, `AGENTS.md`

## Known Issues
- `config.py` caveats: ITC 30% requires placed-in-service by 2027-12-31 (OBBBA) and < 1 MW AC or PWA;
  EIA rate is an all-in average (incl. demand charges); eGRID uses total-output rate, not marginal.
- PVWatts cache lives in `models/solar.py`; `data/cache.py` (CoStar/Vexcel) may absorb it later.
- `requirements.txt` is unpinned; `pillow` is listed there but not used or in `pyproject.toml`.
- `USABLE_FACTOR = 0.6` is an unsourced assumption (plan §4 says label it as such in the UI).
- MASTER.md suggests Google Fonts (Fira); not used, to keep the demo offline-safe.
- Proposal letter omits the ITC caveat (placed in service by 2027-12-31). Pending decision: return a `caveats`
  list from the finance tools and require it in pitches.
- **Gemini key is Free Tier: 20 requests/day for `gemini-4-hydrogen`, exhausted 2026-11-14 ~15:45 ET (resets
  ~03:00 ET Nov 15).** One demo query uses ~3-12 requests. Demo is blocked until billing is enabled or quota resets.
- `app.py` has chat, ranked map + table and roof images; no tool trace or detail panel yet (plan §6 step 9).
  Map tiles come from CARTO (needs internet); offline, markers still draw on a blank background.
- Roof image frame uses the tier-1 footprint (sqft / stories), which undershoots wide low buildings (e.g. 362982
  spills past the frame edges). `cache/` is gitignored: run `python tools/prefetch_images.py` on the demo machine.
- CoStar extract has no roof footprint (tier 1 uses sqft / stories).
- `COST_PER_WATT_BY_SIZE_KW` uses national medians; Texas prices are not broken out by LBNL.
- Repo is PUBLIC and now contains the CoStar extract (`commercial-properties.csv`, `data/*.jsonl`): check
  CoStar data terms before submission. Cloning needs `git lfs`.

## Immediate Next Steps
1. Gemini quota: enable billing on the Google AI project (or wait for reset) before any demo run.
2. Run `python tools/prefetch_images.py` on the demo machine; live demo once Gemini quota resets.
3. Streamlit UI: tool trace and detail panel (click a ranked row → roof image + numbers with sources).
4. ITC `caveats` in finance tool output (pending decision).
