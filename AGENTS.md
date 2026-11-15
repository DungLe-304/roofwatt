# AGENTS.md — RoofWatt

Single source of truth for Claude Code and OpenAI Codex. `CLAUDE.md` imports this file.
Full plan (scope, data contracts, calc model, agent design): `docs/PROJECT_PLAN.md`. Read it before large changes.

---

# Part 1 — Static Project Context

## Overview
RoofWatt is an AI agent (HackPrinceton Fall 2026) that ranks Houston commercial rooftops by solar economics
(energy, savings, payback, CO₂ avoided) and drafts a proposal letter to the owner.
- Demo query (must work end-to-end): *"Find the 10 office buildings in Houston with the best solar payback and draft a pitch for the top one."*
- Tracks: Sustainability (main); CoStar, Amazon, LangChain deepagents (special).
- Deadline: Devpost submit Sun Nov 15 08:00 ET (target 07:30).
- Team: Tony Le (data, models, finance, UI) · Khoa Nguyen (APIs, agent, backend).

## Tech Stack
| Part | Choice |
|---|---|
| Language | Python 3.13 |
| Agent | LangChain `deepagents`. AI engine switch: Cloud = Gemini `gemini-4-hydrogen` (`GOOGLE_API_KEY`), Local = any Ollama model (suggested `qwen3.5:4b`) |
| Building data | CoStar hackathon extract, local JSONL via Git LFS (`data/*.jsonl`) |
| Imagery | Vexcel ortho extract API (`VEXCEL_API_KEY`) |
| Solar energy | NREL/NLR PVWatts v8 (`NLR_API_KEY`, sent as `X-Api-Key` header) |
| UI | Streamlit 1.67 + pydeck |
| Cache | JSON/image files in `cache/` (gitignored) |
| Tests | pytest + Streamlit `AppTest` with fake agents (no LLM, no network) |

## Key Directories
```
app.py              Streamlit entry: 5 pages (Analyze, Results, Building, Proposal, Assumptions), agent run, state
config.py           every assumption with a source string (config.SOURCES) + Settings (model, Ollama host/model)
agent/agent.py      system prompt; createAgent(cloud|local), listLocalModels, QuotaFallbackAgent (Khoa's file)
agent/tools.py      tools the agent calls (rankBuildings, computeFinancials, getRoofImage, ...)
agent/results.py    reads tool results out of agent messages (ranking, trace, roof images)
data/costar_client.py  CoStar extract adapter (Khoa)
data/imagery.py     Vexcel roof images · data/buildings.py: OSM footprints via Overpass (Khoa) · data/cache.py
models/             schemas (data contracts), roof, solar (PVWatts), finance (pure functions)
ui/components.py    page blocks: sidebar + AI engine switch, query form, KPIs, ranked list, letter, assumptions
ui/styles.py        the only custom CSS (works in light and dark); theme in .streamlit/config.toml
ui/ranking.py       pydeck 2D map (best rank green through lowest rank red) · ui/sunlight.py: local query dates
ui/palette.py       Catppuccin Latte / Mocha tokens for custom surfaces and map layers
static/fonts/       CaskaydiaCove Nerd Font Mono (SIL OFL), served via [server] enableStaticServing
ui/detail.py, ui/trace.py, ui/whatif.py, ui/proposal.py   Building page, agent steps, what-if, letter split
tools/prefetch_images.py   fill cache/vexcel/ for the top 20 before a demo
index.md, schemas/, models/*.md   CoStar data kit docs
```

## Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # or: uv sync
cp .env.example .env                # NLR_API_KEY, GOOGLE_API_KEY, VEXCEL_API_KEY
streamlit run app.py
pytest -q                           # run before every push
python tools/prefetch_images.py --top 20
```

## Core Formulas (plan §4)
```
footprint_m2   = min(typical floor ft², gross ft² / stories) * 0.092903   (typical floor < 25% of gross/stories = data error, ignored)
usable_roof_m2 = footprint_m2 * USABLE_FACTOR                             (0.6, unsourced assumption)
system_kw      = usable_roof_m2 * POWER_DENSITY_KW_PER_M2                 (0.211 module × 0.70 coverage = 0.1477)
annual_kwh     = PVWatts(lat, lon, system_kw, array_type=1, tilt=TILT_DEG, azimuth=180, losses=14)
savings_usd    = annual_kwh * ELECTRICITY_RATE_USD_PER_KWH
capex_usd      = system_kw * 1000 * cost_per_watt_for_size(system_kw);  net = capex * (1 - INCENTIVE_PCT)
payback_yr     = net_capex / savings;  co2_t/yr = annual_kwh * GRID_EF_KG_PER_KWH / 1000
```
Ranking: drop `system_kw < 50`; sort payback ascending, tie-break CO₂ descending; ranks are unique (1, 2, 3, ...).

## Conventions
- English everywhere. Small, focused modules; `models/` stays pure (no network except `solar.py`).
- Data contracts in `models/schemas.py` must match plan §3; change them only with a ledger note.
- Every assumption lives in `config.py` with a cited source. **Never invent numbers**; leave TODO if unsourced.
- Watch units: W vs kW, kg vs t, ft² vs m².
- Every reported number comes from a tool; the agent never computes or copies numbers itself.
- UI: Catppuccin Latte (light) / Mocha (dark), bundled CaskaydiaCove Nerd Font Mono, square rectangular corners.
  Preserve the five-page layout; no gradients or extra decoration. Keep custom CSS in `ui/styles.py`.
- Never commit `.env`, keys, or `.agents/` / `.claude/skills/developing-with-streamlit` (symlinks into `.venv`).
- Tony and Khoa own separate files. `main` is the only working branch: branch from it and `git push origin main`.
  `master` is paused (it holds a set-aside restyle, 87db0a8): do not push to it or merge it.

## Handoff Protocol
Before ending a session, update Part 2: set `Last Active Agent`, add finished work to `Completed`, record issues,
and rewrite `Immediate Next Steps`. Keep Part 2 short: state what is true now, not the history (that is in git).

---

# Part 2 — Dynamic Handoff Ledger

## Last Active Agent
Claude Code (Opus 5.5) - 2026-11-15 (`main` official; `master` paused)

## Current Objective
Demo-ready: the demo query works end-to-end in either AI engine, with results, 2D map, roof images and letter.

## Completed (current state)
- Tools: `rankBuildings` screens every matching building in code (185 Houston offices → 171 ranked, 14 below 50 kW);
  per-building tools take only a `buildingId`. PVWatts and Vexcel errors redact API keys.
- Roof footprint uses min(typical floor, gross ÷ stories), checked against Vexcel images (gross ÷ stories alone
  overstated towers up to 2×). Top 3: 240117, 362982, 23573.
- UI (`minimal-ui`, merged): 5 sidebar pages, native light/dark theme (follows the system; switch in the ⋮ menu),
  live tool trace, KPIs, 2D map (OSM footprints load on a worker thread), what-if Assumptions (usable factor 0.30–1.00),
  letter with Copy/Download. Last good run saved to `cache/ui/last_run.json` and shown if the agent fails.
- AI engine switch (`ai-mode`, merged): sidebar Cloud / Local with Active/Offline status. Local lists the models
  pulled into Ollama. Cloud falls back to the local model on a Gemini quota error and flips the switch to Local;
  picking Cloud again retries Gemini. Run is disabled with the reason when the chosen engine cannot run.
- Latte / Mocha native appearance switching; locally served CaskaydiaCove fonts, square controls, matching map
  markers and tooltip. Existing layout preserved. Analyze and Assumptions checked visually in both appearances.
- Local engine works with `qwen3.5:4b` (Ollama, thinking off: `reasoning=False`, else hidden thinking used the
  whole 1200-token budget and cut the answer): the demo query runs in ~45 s (rankBuildings, getBuilding,
  getRoofImage) and drafts a letter. The Local engine gets `localRules` on top of `systemPrompt` (no arithmetic,
  fixed calls, table + `## Proposal letter`, no file tools); 6 of 7 browser runs gave a full letter with tool numbers.
- Sidebar engine switch and local model picker keep their value across pages (`persist_state="session"`) and
  across reloads / new tabs (last choice saved in `cache/ui/engine.json`, shared by every browser on this server).
- Ranking: unique ranks 1, 2, 3, ... in `rankBuildings` and the what-if recalculation (equal payback ordered by
  CO₂ avoided; no shared ranks). The agent prompt no longer says equal payback shares a rank.
- Structured search: "Use prompt" writes the filters into the query field (no run); Run analysis sends it.
  City and Property type sit outside the filter form; City is kept across pages and sets the sidebar city at once
  (starts at the last run's city, else Houston).
- 118 tests pass, including native/custom palette consistency. Corrected stale status expectations and Windows
  path escaping in test fixtures. `retro-ui` (Windows 98 restyle) exists only as a local branch.

## Known Issues
- Rotate the NLR (PVWatts) key: it was printed in a session log before the redaction fix.
- Gemini Free Tier: 20 requests/day; one demo query uses ~3–12. The 4B local model still sometimes uses sales
  wording ("excellent investment") against rule 7; its numbers are copied from tools.
- Local engine: about 1 in 7 browser runs never reached Results within 400 s (cause not yet found; no error in
  the Streamlit log). A repeated "Dear ..." line is dropped from the shown letter (`ui/proposal.py`).
- Overpass (OSM) answered 429 / timed out: building footprints show only if `cache/osm-buildings/` was filled earlier.
- PVWatts answers 429 when `rankBuildings` (8 threads) hits many uncached sizes; warm the cache sequentially.
- Roof estimate: irregular shapes (V, X plans) can be ~20% over the imaged roof; `USABLE_FACTOR` is unsourced.
- `config.py` caveats: ITC 30% needs placed-in-service by 2027-12-31; EIA rate is an all-in average; eGRID is not
  marginal; `COST_PER_WATT_BY_SIZE_KW` uses national medians. The letter omits the ITC caveat.
- Letter split (`ui/proposal.py`) works on Local replies; not yet seen on a live Gemini reply (last one was empty).
- Map tiles (CARTO) need internet; fonts are bundled. Restart Streamlit after newly enabling static serving.
- Restart Streamlit after editing `ui/` or `agent/` modules: without `watchdog` the running server once kept the old
  `ui/components.py` while loading the new `app.py` (TypeError on the Analyze page). `pip install watchdog` may help.
- `cache/ui/last_run.json` = Houston demo on Local `qwen3.5:4b` (Nov 15 02:50): unique ranks 1-10, roof image, full
  letter. The letter adds its own "over 20 years ≈ $2.8 million" (savings × 20, model arithmetic, not a tool number).
- Gemini (`gemini-4-hydrogen`, Nov 15 02:47): the demo query ran 12 tool calls (rankBuildings, 10× getBuilding,
  getRoofImage) and then returned an EMPTY final reply, so no table and no letter. Suspected, not confirmed: hidden
  thinking uses the whole `agentMaxOutputTokens` = 1200 budget (same failure as qwen before `reasoning=False`).
- Sidebar city shows the City filter, not the city of the results on screen, until the next run.
- Unused dependency: `streamlit-hotkeys` is still in `pyproject.toml` / `uv.lock` (removed from requirements.txt).
- Repo is PUBLIC and contains the CoStar extract: check CoStar data terms before submission.

## Immediate Next Steps
1. Rotate the NLR key. Open Results once when Overpass answers, so the 2D footprints are cached for the demo.
2. On the demo machine: `python tools/prefetch_images.py` and `ollama pull qwen3.5:4b`.
3. Fix the empty Gemini reply (raise the output cap or limit Gemini thinking), then one Gemini demo run after the
   quota reset (~12 of 20 daily requests) to confirm it and check the letter split. Until then demo on Local.
4. Optional: ITC `caveats` in finance tool output so the pitch states them.
