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
| Agent | LangChain `deepagents` + Gemini (`google_genai:gemini-4-hydrogen`, key `GOOGLE_API_KEY`); fallback: local Ollama `qwen3.5:4b` when Gemini quota is exhausted |
| Building data / imagery | CoStar hackathon toolkit (CoStar, Vexcel; Matterport stretch). API shapes are **unverified placeholders** |
| Solar energy | NREL PVWatts v8 API |
| Images | Pillow / OpenCV (stretch: Segment Anything) |
| UI | Streamlit + pydeck |
| Cache | Local JSON/SQLite keyed by `building_id` (`cache/`, gitignored) |
| Tests | pytest |

## Key Directories
```
app.py              Streamlit UI: query bar, live tool trace, KPIs, map + ranked cards, detail, proposal letter
config.py           ALL assumptions, each with a source string (several still TODO)
agent/agent.py      deepagents setup + system prompt + Gemini → Ollama quota fallback
agent/tools.py      tool wrappers exposed to the agent
data/costar_client.py  CoStar building search/details
data/imagery.py     Vexcel aerial imagery (Matterport stretch)
data/cache.py       response cache
ui/components.py    page blocks: header, query bar, empty state, KPI row, ranked cards, proposal, sidebars
ui/theme.py         brand colors + custom CSS (theme itself in .streamlit/config.toml)
ui/ranking.py       pydeck map (light, size ~ kW, rank 1 orange) + table for a rankBuildings result
ui/detail.py        detail panel for the selected building (roof image + metrics with source tooltips)
ui/trace.py         live tool trace (LangChain callback) + "How the agent got here" expander
ui/whatif.py        sidebar what-if recalculation of the shown rows (models.finance, no API calls)
ui/proposal.py      splits the drafted owner letter out of the agent's answer
models/schemas.py   Building, RoofResult, SolarResult, FinanceResult dataclasses
models/roof.py      usable roof area (tier 1: footprint × USABLE_FACTOR)
models/solar.py     PVWatts client (cache + 429 handling)
models/finance.py   savings, payback, CO₂ (pure functions)
tests/              pytest (test_finance.py)
docs/PROJECT_PLAN.md   full plan, data contracts, calc model, agent design
index.md, schemas/, models/*.md, tools/expand_records.py   CoStar data kit docs (data in data/*.jsonl via Git LFS)
assets/             app icon
design-system/roofwatt/MASTER.md  old dark/green design system; superseded by the brand palette in ui/theme.py
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
Agent + chat UI answer the demo query over all Houston offices. Gemini quota is covered by a local Ollama
fallback (Khoa); verify the fallback end-to-end on the demo machine.

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

- Tool trace + detail panel: `agent/results.py` `toolTrace` pairs each AI tool call with its ToolMessage (short
  result, `write_todos` items nested); `ui/trace.py` shows it in an "Agent steps" expander. Ranked table is
  single-row selectable (key `ranking-<message index>`, survives reruns); `ui/detail.py` shows the selected row
  (default rank 1): roof image (agent's image, else `getRoofImage` memoized 5 min so clicks never re-hit a failing Vexcel), 8 metrics whose tooltips give the
  formula with `config` values + `config.SOURCES` citation (ITC 2027-12-31 caveat on net cost), CoStar sqft/stories/
  year. Images already in the detail panel are not repeated below. Trace args capped at 160 chars. Clicks verified in headless Chrome. 77 tests.

- UI redesign (light brand theme: navy #13294B, orange #FF9F1C, blue #2F80ED, Inter with offline fallback):
  header + query bar with demo query and example chips; live tool trace while the agent runs (worker thread +
  `ui.trace.LiveTrace` callback, `QuotaFallbackAgent.invoke(state, config=None)` passes config through), then a
  "How the agent got here" expander; 4 KPI cards (buildings screened, top-N kW, $/yr, t CO₂/yr); map (click a dot)
  + ranked cards (Details selects); detail panel with metric tooltips citing config; proposal letter card with
  Copy / Download .md; empty state (Scan → Analyze → Pitch). Sidebar (collapsed): what-if assumptions with
  Recalculate (rate, flat $/W, ITC %, usable factor; recalculates the shown rows only, labeled what-if) and Khoa's
  structured search form. Results live in `st.session_state.run`; the last good run is saved to
  `cache/ui/last_run.json` (env `ROOFWATT_LAST_RUN` overrides) and shown if the agent fails. Chat history UI removed
  (follow-ups still send history to the agent). PVWatts linearity checked live (350 vs 100 kW: exactly 3.5x).
  Checked in headless Chrome with real Houston data; live trace checked through a real deepagents graph with a
  fake model. 89 tests.
- LLM fallback (Khoa, `f4e7734`, `a257785`): `agent/agent.py` `createRoofWattAgent(pingGemini)` builds two deepagents
  with the same prompt and tools, Gemini and local Ollama `ChatOllama(model="qwen3.5:4b")` (Qwen 3.5 4B on Khoa's
  machine), wrapped in `QuotaFallbackAgent`. An error containing `RESOURCE_EXHAUSTED` or `429` switches the session to
  Ollama for good (other errors still raise). `app.py` `loadAgent(checkGemini=True)` pings Gemini once at startup
  ("Reply with OK only."), so an exhausted key goes straight to Ollama; the sidebar checkbox was removed.
  `langchain-ollama` added to `pyproject.toml`/`uv.lock`; `python-dotenv` is back (`agent.py` calls `load_dotenv()`).
- After the fallback: `langchain-ollama` added to `requirements.txt`. `d5724ff` had dropped the detail panel
  (`showDetail`, `roofImageFor`, `lookupBuilding`) from `app.py`; restored, Khoa's per-message trace kept.
  `tests/test_app.py` fake factory accepts `pingGemini`. 77 tests pass (`9854c15`).
- Active model in the UI: `app.py` `modelLabel(agent)` reads `QuotaFallbackAgent.useLocalModel` after each invoke
  ("Model: Gemini · gemini-4-hydrogen" or "Model: Ollama · qwen3.5:4b (local fallback, Gemini quota exhausted)").
  Shown as a caption under each reply (stored per message as `model`) and in the sidebar (placeholder filled at the
  end of the run, so a mid-request switch shows). `tests/test_app.py` clears `st.cache_resource` per test. 78 tests.

## Modified Files
- Khoa (fallback): `agent/agent.py`, `agent/tools.py` (docstring), `app.py`, `ui/ranking.py` (reformat), `pyproject.toml`, `uv.lock`
- UI redesign: `app.py`, `.streamlit/config.toml`, `ui/{components,theme,whatif,proposal}.py` (new),
  `ui/{detail,ranking,trace}.py`, `agent/results.py` (`toolSummary`), `agent/agent.py` (config passthrough only),
  `tests/test_{app,detail,ranking}.py`, `tests/test_{whatif,proposal,trace}.py` (new), `AGENTS.md`

## Known Issues
- `config.py` caveats: ITC 30% requires placed-in-service by 2027-12-31 (OBBBA) and < 1 MW AC or PWA;
  EIA rate is an all-in average (incl. demand charges); eGRID uses total-output rate, not marginal.
- PVWatts cache lives in `models/solar.py`; `data/cache.py` (CoStar/Vexcel) may absorb it later.
- `requirements.txt` is unpinned; `pillow` is listed there but not used or in `pyproject.toml`.
- `USABLE_FACTOR = 0.6` is an unsourced assumption (plan §4 says label it as such in the UI).
- MASTER.md suggests Google Fonts (Fira); not used, to keep the demo offline-safe.
- Proposal letter omits the ITC caveat (placed in service by 2027-12-31). Pending decision: return a `caveats`
  list from the finance tools and require it in pitches.
- Gemini key is Free Tier: 20 requests/day for `gemini-4-hydrogen` (exhausted 2026-11-14 ~15:45 ET, resets ~03:00 ET
  Nov 15); one demo query uses ~3-12 requests. The Ollama fallback keeps the demo running, but:
  - Ollama must be running on the demo machine (default `localhost:11434`) with `ollama pull qwen3.5:4b` done;
    the code has no host setting, so it only works on a machine that runs Ollama itself (Khoa's laptop).
    Not installed on Tony's machine.
  - Not yet checked: whether a 4B model calls the tools reliably and keeps every number from tool output.
  - The startup ping costs 1 Gemini request each time the agent is created (`st.cache_resource` makes that once per server).
- Proposal panel splits the letter out of the agent's answer at a pitch/proposal/letter heading or a "Dear" line;
  if the agent formats it differently the whole answer is shown as "Agent answer". Not yet seen with a live reply.
- Map tiles come from CARTO (needs internet); offline, markers still draw on a blank background. Inter loads from
  Google Fonts; offline it falls back to the system sans-serif.
- `streamlit-hotkeys` is no longer used by `app.py` (still in requirements).
- Roof image frame uses the tier-1 footprint (sqft / stories), which undershoots wide low buildings (e.g. 362982
  spills past the frame edges). `cache/` is gitignored: run `python tools/prefetch_images.py` on the demo machine.
- CoStar extract has no roof footprint (tier 1 uses sqft / stories).
- `COST_PER_WATT_BY_SIZE_KW` uses national medians; Texas prices are not broken out by LBNL.
- Repo is PUBLIC and now contains the CoStar extract (`commercial-properties.csv`, `data/*.jsonl`): check
  CoStar data terms before submission. Cloning needs `git lfs`.

## Immediate Next Steps
1. On the demo machine: `ollama pull qwen3.5:4b`, run `python tools/prefetch_images.py`, then run the demo query
   on both Gemini and Ollama. Check that Qwen calls `rankBuildings` and that the "Agent steps" trace looks right.
2. Live demo once Gemini quota is back: check the live trace, the proposal split and the Copy button in a real browser.
3. Optional: unit test for `QuotaFallbackAgent` (agent/agent.py, Khoa's file) with fake agents.
4. ITC `caveats` in finance tool output so the pitch states them (pending decision; the UI tooltip already does).
