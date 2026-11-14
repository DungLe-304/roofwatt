# RoofWatt

AI agent that finds the commercial rooftops in Houston with the best solar economics, estimates energy, savings, payback and CO2 avoided, and drafts a proposal to the building owner.

Built at HackPrinceton Fall 2026 by Dung Le (Tony Le) and Khoa Nguyen.

## Setup

The CoStar extract in `data/*.jsonl` is stored with Git LFS, so install it before cloning
(`brew install git-lfs && git lfs install`). Python 3.13+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or: uv sync
cp .env.example .env              # then fill in your keys (NLR_API_KEY for PVWatts, GOOGLE_API_KEY for Gemini)
pytest -q                         # run the tests
streamlit run app.py
```

See `docs/PROJECT_PLAN.md` for the full project plan and `AGENTS.md` for agent handoff notes
(`CLAUDE.md` only imports `AGENTS.md`). The CoStar data kit is described in `index.md`.
