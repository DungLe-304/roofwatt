# CLAUDE.md — RoofWatt (HackPrinceton Fall 2026)

> Hand-off brief for Claude Code. Read this whole file before writing any code.
> Team: **Tony Le** (Data Science — data, models, finance, UI, pitch) and **Khoa Nguyen** (Computer Science — APIs, agent, backend).
> Hard deadline: **Devpost submission by Sunday Nov 15, 2026, 8:00 AM ET** (team target: 7:30 AM). Feature freeze: **Sunday 2:00 AM ET**.

---

## 1. What we are building

**One line:** RoofWatt is an AI agent that finds the commercial rooftops in Houston with the best solar economics, estimates energy, savings, payback and CO₂ avoided, and drafts a proposal letter to the building owner.

**Target users:** commercial solar installers looking for leads, brokers and commercial building owners, city sustainability offices.

**Demo query (must work end-to-end):**

> "Find the 10 office buildings in Houston with the best solar payback and draft a pitch for the top one."

### Scope

**MVP (must work by Saturday 6:00 PM ET):**
- Natural-language query → agent filters buildings from CoStar data → pulls Vexcel aerial imagery → estimates usable roof area → energy (PVWatts) → savings, payback, CO₂.
- Ranked results on a map + table + detail panel + drafted owner proposal.
- Visible **tool trace** in the UI (judges score "agentic depth").

**Stretch (only after MVP works):**
- Roof segmentation with Segment Anything (SAM) to subtract rooftop equipment (tier 2).
- Third data layer: Matterport.
- City-wide impact number; sliders for financial assumptions; 25-year NPV instead of simple payback.

**Out of scope:** structural load analysis, real-time electricity pricing, cities other than Houston (LA only if huge time left).

### Tracks we submit to

| Type | Track | Why |
|---|---|---|
| Main (pick exactly one) | **Sustainability** | Least crowded main track at the last two HackPrinceton events |
| Special | **CoStar — Inside and Out: AI for the Built World** | Must use ≥2 of 3 data layers (CoStar, Matterport, Vexcel); must be agentic |
| Special | **Amazon — Best Practical AI Innovation** | Agentic, real-world impact, UX |
| Special | **LangChain — Best use of deepagents** | Agent must be built with `deepagents` |
| Optional | Best Rookie Hack | Eligibility unclear (team may need ≥2/3 first-time hackers) — confirm with organizers |

### CoStar judging criteria (optimize for these)

| Criterion | Weight | How RoofWatt meets it |
|---|---|---|
| Use of the data | 30% | Combines CoStar building data (type, size, owner) with Vexcel aerial imagery (roof); Matterport as stretch |
| Agentic depth | 30% | Agent plans, screens, runs multi-step analysis, ranks, and acts (drafts proposal). Not a chat wrapper |
| Usefulness | 25% | An installer could use it Monday to find leads |
| Demo and polish | 15% | Map, sourced numbers, cached demo path |

---

## 2. Architecture

```
User query (Streamlit)
   ↓
Agent (LangChain deepagents) — plans, then calls tools:
   ├─ searchBuildings   → CoStar toolkit (SDK / MCP / OpenAPI)
   ├─ getBuilding()       → CoStar building details
   ├─ get_aerial()         → Vexcel imagery
   ├─ analyze_roof()       → usable roof area (m²)
   ├─ estimate_solar()     → NREL PVWatts v8 API (kWh/yr)
   ├─ compute_financials() → savings, payback, CO₂
   └─ draft_proposal()     → LLM-written owner letter
   ↓
UI: pydeck map + ranked table + detail panel + proposal + tool trace
```

### Tech stack

| Part | Choice |
|---|---|
| Language | Python 3.11+ |
| Agent | LangChain `deepagents` + whichever LLM key the team has (Claude or OpenAI) |
| Building data & imagery | CoStar hackathon toolkit (SDK, MCP servers, OpenAPI) — **read its docs first; API shapes below are placeholders** |
| Solar energy | NREL PVWatts v8 API (free key at developer.nrel.gov) |
| Image processing | Pillow / OpenCV; stretch: Segment Anything |
| UI | Streamlit + pydeck |
| Cache | Local JSON or SQLite keyed by `building_id` (demo must survive bad Wi-Fi) |

### Repo layout

```
roofwatt/
├── app.py                 # Streamlit UI
├── config.py              # ALL financial/physical assumptions, with source notes
├── agent/
│   ├── agent.py           # deepagents setup + system prompt
│   └── tools.py           # tool wrappers exposed to the agent
├── data/
│   ├── costar_client.py   # CoStar building search/details
│   ├── imagery.py         # Vexcel tiles; Matterport (stretch)
│   └── cache.py
├── models/
│   ├── schemas.py         # Building, RoofResult, SolarResult, FinanceResult dataclasses
│   ├── roof.py            # usable roof area
│   ├── solar.py           # PVWatts call
│   └── finance.py         # savings, payback, CO₂
├── tests/
│   └── test_finance.py
├── .env.example
├── requirements.txt
└── README.md
```

**Repo rules (HackPrinceton):** public GitHub repo, created after **Nov 13, 2026, 8:00 PM ET**. All coding within the 36-hour window.

---

## 3. Data contracts (agree on these first)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Building:
    building_id: str
    address: str
    lat: float
    lon: float
    property_type: str
    building_sqft: Optional[float]
    footprint_m2: Optional[float]   # if CoStar lacks it: building_sqft / stories, converted to m²
    stories: Optional[int]
    year_built: Optional[int]
    owner_name: Optional[str]

@dataclass
class RoofResult:
    building_id: str
    usable_roof_m2: float
    method: str                     # "tier1_footprint_factor" | "tier2_sam"
    image_path: Optional[str]

@dataclass
class SolarResult:
    building_id: str
    system_kw: float
    annual_kwh: float

@dataclass
class FinanceResult:
    building_id: str
    annual_savings_usd: float
    capex_usd: float
    net_capex_usd: float
    simple_payback_yr: float
    co2_tons_per_year: float
```

---

## 4. Calculation model

```python
# Roof — tier 1 baseline
usable_roof_m2 = footprint_m2 * USABLE_FACTOR

# System size
system_kw = usable_roof_m2 * POWER_DENSITY_KW_PER_M2

# Energy — NREL PVWatts v8
annual_kwh = pvwatts(lat, lon, system_capacity=system_kw,
                     array_type=1,      # fixed, roof mount
                     tilt=TILT_DEG, azimuth=180, losses=14)

# Finance
annual_savings_usd = annual_kwh * ELECTRICITY_RATE_USD_PER_KWH
capex_usd          = system_kw * 1000 * COST_PER_WATT_USD
net_capex_usd      = capex_usd * (1 - INCENTIVE_PCT)
simple_payback_yr  = net_capex_usd / annual_savings_usd

# Impact
co2_tons_per_year  = annual_kwh * GRID_EF_KG_PER_KWH / 1000
```

### `config.py` parameters

Every value must carry a source string shown as a tooltip in the UI. Values marked **TODO** must be looked up and cited — do not invent numbers.

| Parameter | Initial value | Source |
|---|---|---|
| `USABLE_FACTOR` | 0.6 (assumption) | Label as assumption; replaced by SAM in tier 2 |
| `POWER_DENSITY_KW_PER_M2` | TODO | Typical commercial module specs incl. row spacing |
| `TILT_DEG` | TODO | Typical low-slope commercial racking |
| `losses` | 14% | PVWatts default |
| `ELECTRICITY_RATE_USD_PER_KWH` | TODO | EIA average commercial price, Texas |
| `COST_PER_WATT_USD` | TODO | NREL or SEIA commercial solar cost benchmarks |
| `INCENTIVE_PCT` | TODO | Current federal/state incentive rules for commercial solar — verify, law changes |
| `GRID_EF_KG_PER_KWH` | TODO | EPA eGRID, ERCOT subregion (ERCT) |

### Ranking
- Drop buildings with `system_kw < 50` (not worth an installer's visit).
- Sort by `simple_payback_yr` ascending; tie-break by `co2_tons_per_year` descending.
- Stretch: 25-year NPV.

### Tests
`tests/test_finance.py`: 2–3 hand-computed cases. Watch units (W vs kW, kg vs tons, ft² vs m²: 1 ft² = 0.092903 m²).

---

## 5. Agent design

### Tools (`agent/tools.py`)

| Tool | Input | Output | Owner |
|---|---|---|---|
| `search_buildings` | city, property_type, min_sqft, limit | list of `Building` (basic fields) | Khoa |
| `get_building` | building_id | `Building` (full) | Khoa |
| `get_aerial` | building_id | image path / URL | Khoa |
| `analyze_roof` | building_id | `RoofResult` | Tony |
| `estimate_solar` | lat, lon, system_kw | `SolarResult` | Tony |
| `compute_financials` | SolarResult, system_kw | `FinanceResult` | Tony |
| `draft_proposal` | building_id + analysis results | proposal (markdown) | Khoa |

### System prompt (key points)
- You are a commercial solar analyst. Always write a plan before calling tools.
- Screen broadly with `search_buildings`, then deep-analyze **at most 20** buildings per run.
- Every number you report must come from a tool result. Never invent figures. State assumptions.
- Finish with a ranked table, a short explanation of why #1 wins, and offer to draft a proposal.

### Guardrails
- Cache every CoStar / Vexcel / PVWatts response by `building_id`.
- Cap agent loop at ~40 tool calls per request.
- Pre-run the demo query once so the cache is warm before judging.
- Show the tool trace (tool name, args, short result) in the UI.

---

## 6. Build order (tasks for Claude Code)

Work in this order. Do not start stretch items until step 7 passes.

1. Scaffold repo layout, `requirements.txt`, `.env.example`, `.gitignore` (include `.env`).
2. `models/schemas.py` dataclasses.
3. `models/finance.py` + `tests/test_finance.py` (pure functions, no network).
4. `models/solar.py` — PVWatts v8 client with caching and 429 handling.
5. `data/costar_client.py` + `data/imagery.py` — **first read the CoStar toolkit docs/MCP schema**; start with mocks matching `Building` if access is not ready.
6. `models/roof.py` tier 1.
7. **Checkpoint:** one Houston building end-to-end in a script/notebook.
8. `agent/tools.py` + `agent/agent.py` with deepagents (mock tools first, then real).
9. `app.py` Streamlit: query box, tool trace, pydeck map, ranked table, detail panel (roof image + numbers with source tooltips), proposal panel.
10. **Checkpoint (Sat 6 PM ET):** demo query → ranked map works.
11. Polish, error handling, offline cache. Then stretch: SAM roof segmentation, city-wide impact, Matterport.
12. README: problem, how it works, stack, assumptions and sources, setup steps, future work.

---

## 7. Timeline (ET)

| Time | Khoa (CS) | Tony (Data Science) | Checkpoint |
|---|---|---|---|
| Sat 07:30–09:00 | Repo, `.env`, scaffold; test CoStar + Vexcel calls | NREL key, test PVWatts; look up `config.py` values | Each API returns real data once |
| 09:00–10:30 | `costar_client.py` | `solar.py`, `finance.py` + tests | |
| 10:30–11:00 | LangChain "How to use Deepagents" workshop | Continue finance | |
| 11:00–12:00 | Agent skeleton with mock tools | `roof.py` tier 1; 15 min at Career Fair asking CoStar engineers about footprint/roof data | **12:00: one building end-to-end** |
| 12:00–13:00 | Lunch | Lunch | |
| 13:00–18:00 | Real tools in agent; `draft_proposal` | Batch 50–200 buildings; Streamlit map/table/detail | **18:00: query → ranked map** |
| 18:00–19:00 | Dinner | Dinner | If behind: drop all stretch |
| 19:00–23:00 | Tool trace UI, errors, cache | Stretch; source tooltips | **23:00: first stable demo** |
| Sun 23:00–02:00 | Sleep | Bug fixes, README, Devpost draft | **02:00: feature freeze** |
| 02:00–05:00 | Bug fixes, warm demo cache | Sleep | |
| 05:00–07:00 | Record demo video (≤2 min) | Finish Devpost, screenshots, verify repo public | Rehearse pitch 3× |
| 07:00–07:30 | Upload video, add link | Select tracks on Devpost | **07:30: submit** |
| 09:30 | Judging begins (in-person demo required) | | |

---

## 8. Pitch (2 minutes)

1. **Problem (20 s):** Houston has thousands of sun-baked commercial roofs sitting empty. Owners don't know if solar pays off; installers don't know whose door to knock on.
2. **Live demo (70 s):** type the query → agent plans and calls tools → top-10 map → click #1: roof image, savings, payback, CO₂ → drafted proposal.
3. **Impact (30 s):** CO₂ avoided per year if applied to every building in the dataset; next steps (LA, Matterport, NPV).

## 9. Devpost checklist

- [ ] Public GitHub repo link (created after Nov 13, 8 PM ET)
- [ ] Exactly one main track: Sustainability
- [ ] Special tracks: CoStar, Amazon, LangChain deepagents
- [ ] Demo video ≤ 2 min uploaded and linked
- [ ] Both teammates' Discord usernames
- [ ] Description: problem, approach, stack, assumptions + sources, future work
- [ ] UI screenshots

## 10. Risks & fallbacks

| Risk | Signal | Fallback |
|---|---|---|
| CoStar has no footprint field | `get_building` lacks roof/footprint | Ask CoStar engineers on Discord; use `building_sqft / stories` |
| SAM eats time | Not working by Sat 9 PM | Drop it; keep tier 1, labeled as assumption |
| PVWatts rate limit | HTTP 429 | Cache; reuse kWh/kW for nearby buildings |
| Agent slow or loops | >1 min per query | Cap iterations; fewer deep-analyzed buildings |
| Weak Wi-Fi at judging | Slow loads | Run from local cache; have the video ready |
| Exhaustion | Rising silly bugs | Sleep in shifts per timeline |

## 11. Conventions

- All code, comments and docs in English.
- Commit at least hourly to `main`; Tony and Khoa work in separate files to avoid conflicts.
- Never commit API keys. Use `.env`.
- Keep every assumption in `config.py` with a source string.
