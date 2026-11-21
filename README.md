# Hospital Staff Scheduling System using Optimisation and AI

Team PDS15, FIT3163, Monash University Malaysia.

An AI-assisted rostering system for Ministry of Health Malaysia Emergency Department (ED) and Intensive Care Unit (ICU) staff. It forecasts demand (ARIMA, gradient boosting), then builds and repairs rosters with Google OR-Tools CP-SAT. Planned rosters are published only after admin approval; urgent ICU/ED repairs go live first if every hard rule holds, and the admin reviews them afterwards.

## Repository layout

| Folder | Contents |
| --- | --- |
| `src/forecasting/` | Demand forecasting (seasonal naive baseline, ARIMA, gradient boosting) |
| `src/roster_engine/` | CP-SAT roster generation and repair |
| `src/rule_checker/` | Independent rule checker (separate from the engine) |
| `src/webapp/` | Web application: login, roster editing and approval |
| `data/` | Sample and synthetic data. No patient identifiers. |
| `config/` | Rules and thresholds stored as configuration, not code (R23) |
| `tests/` | Automated tests, one file per person per area |
| `docs/` | Diagrams, test-case documents and notes |

## Setup

```
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -v
```

## Working on this repository

See [CONTRIBUTING.md](CONTRIBUTING.md).
