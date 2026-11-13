# Mindari / Deal Analysis

Deal pipeline + automated IC analysis on the ADCG Buyout and ADCG Venture Growth frameworks.

## Deploy on Railway (same pattern as Venture GP Atlas)
1. New project → **Deploy from GitHub repo** → this repo (no Root Directory; `railway.toml` + root `Dockerfile` do the rest).
2. Add **Postgres**; on the service set `DATABASE_URL=${{Postgres.DATABASE_URL}}`.
3. Service → **Volumes** → add a volume mounted at **`/data`** (uploaded deal files live there).
4. Variables: `ANTHROPIC_API_KEY`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` (≥12 chars), optional `SECRET_KEY`.
5. Generate a domain. Sign in with the superuser; add teammates in `/admin/` (role analyst = can add/analyse deals).

## Local dev
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env && python manage.py migrate && python manage.py seed_ledger && python manage.py createsuperuser
python manage.py runserver & python manage.py analysis_worker
cd ../frontend && npm ci && npm run dev   # http://localhost:5173
```
See `CLAUDE.md` for the architecture.
