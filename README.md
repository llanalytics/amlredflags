# amlredflags-v2

Clean-slate rebuild of the AML Red Flags service.

## Goals
- Keep architecture simple and observable.
- Use migrations from day 1.
- Separate app concerns: API, models, batch orchestration.

## Stack
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL (Heroku)

## Local Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

## Core Endpoints
- `GET /api/health`
- `POST /api/batch/trigger`
- `GET /api/batch/status`
- `GET /api/redflags`

Batch scraping supports pagination per source (configurable with `max_pages`
on each source and global `MAX_PAGES_PER_SOURCE` in `.env`).

## Utility Scripts
```bash
# Check current batch and health
./scripts/check_batch.sh

# Trigger batch once
./scripts/trigger_batch.sh

# Trigger and watch until completion
./scripts/trigger_batch.sh http://localhost:8001 --wait
```

## Deploy (Heroku)
```bash
heroku create amlredflags-v2
heroku config:set OPENAI_API_KEY=... -a amlredflags-v2
git push heroku main
```

`Procfile` runs migrations during release:
- `release: alembic upgrade head`
