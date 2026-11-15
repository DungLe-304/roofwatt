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

## AI engine: Cloud or Local

The sidebar has an **AI engine** switch with two modes. Both use the same prompt and tools; only the language model changes.

- **Cloud** (default): Gemini through the API (`GOOGLE_API_KEY`). If the free quota runs out, the run is answered by
  the local model and the switch moves to Local. Choosing Cloud again retries Gemini.
- **Local**: a model served by [Ollama](https://ollama.com) on this computer. The sidebar lists every model Ollama has
  pulled; `qwen3.5:4b` is the default.

```bash
brew install ollama        # or the installer from ollama.com
ollama serve               # leave running (the macOS app starts it for you)
ollama pull qwen3.5:4b     # or any other model, e.g. ollama pull llama3.2:3b
```

Ollama on another machine: set `ollamaHost` (e.g. `ollamaHost=http://192.168.1.20:11434`) in `.env`.
`localModelName` sets the default local model. Small local models may call the tools less reliably than Gemini.

See `docs/PROJECT_PLAN.md` for the full project plan and `AGENTS.md` for agent handoff notes
(`CLAUDE.md` only imports `AGENTS.md`). The CoStar data kit is described in `index.md`.
