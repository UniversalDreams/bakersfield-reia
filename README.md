# Bakersfield REIA (Real Estate Investment Analyzer)

Personal quantitative decision-support tool for buy-and-hold rental investing in
Bakersfield/Kern County, CA. See `PROJECT_PLAN.md` for the full build plan,
phased rollout, and explicit exclusions. This is a work in-progress, and has not been fully implemented due to constraints on computation. 

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in RENTCAST_API_KEY
```

