# RoofWatt

AI agent that finds the commercial rooftops in Houston with the best solar economics, estimates energy, savings, payback and CO2 avoided, and drafts a proposal to the building owner.

Built at HackPrinceton Fall 2026 by Tony Le and Khoa Nguyen.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
streamlit run app.py
```

See `CLAUDE.md` for the full project plan.
