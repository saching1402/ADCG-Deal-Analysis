# CLAUDE.md — Mindari / Deal Analysis

Context for AI assistants working on this repo. Keep it current.

**What it is:** the PE team's deal pipeline (Mindari suite, "IC Agent"). Landing page = pipeline of every deal analysed;
**+ New deal** takes a company name, optional terms and 15–20+ data-room files, then a background worker reads the files,
researches the web, scores the deal on the **ADCG Buyout** or **ADCG Venture Growth** framework and writes the IC memo.

**Stack:** same as Venture GP Atlas (`saching1402/Venture-Tracker`) and Dynamo — Django 5 + DRF + SimpleJWT + PostgreSQL
(`backend/`), React 18 + TS + Vite + React Query (`frontend/`), ONE Railway service from the repo root (root `Dockerfile`
builds the React app into Django as `frontend_dist`, served by WhiteNoise + `spa_index`) + Railway Postgres + a Railway
Volume at `/data` for uploaded files. Look: white canvas, navy ink, gold accent; Bricolage Grotesque / IBM Plex.

## Data model (`apps/deals/models.py`)
- `Deal` — name, website, `track` (auto|buyout|vg requested) / `track_resolved`, sponsor, sector, sub_sector, notes,
  `stage` (new → analyzed → internal → pre_ic → final_ic → approved | passed | on_hold), headline ev/multiple/leverage/
  one_liner, `adcg_score`, `risk_score`, band, recommendation, facts, `summary` (engine output), `scorecard` (full deal
  JSON with criteria + rationales), `research` (dossier markdown), `memo_html` (assembled memo), sources, status, `legacy`
  (seeded from the prior ADCG ledger: scores only).
- `DealFile` — the upload + `digest` (fact sheet Claude wrote), method (native-pdf | text | image), status.
- `AnalysisJob` — one run: stage, model, tokens, searches, cost, log, instructions (deal lead's steer/rationale).

## Analysis pipeline (`apps/deals/engine.py`, run by `analysis_worker`, never in a request)
1. **digest** — each un-read file → fact sheet (≤2.5K words, page-referenced). PDFs ≤100 pages/30 MB go to Claude as
   native documents (tables, charts, scans); larger PDFs and Word/Excel/PowerPoint/CSV/text are extracted
   (`extract.py`) and chunked at 160K chars. `DIGEST_CONCURRENCY` files in parallel; failures don't stop the deal.
   Re-runs reuse existing digests unless `redigest`.
2. **research** — web search (`ANALYSIS_MAX_SEARCHES`) + all digests → dossier + metadata JSON (track, sector, facts…).
3. **score** — scorecard JSON in the skill schema → `apps/deals/scoring` (verbatim `adcg_scorecard.py` + the VG engine:
   Marquee GP Index, VJR, venture risk register). Retries once on bad JSON.
4. **memo** — two calls (sections 1–6 weights, then 7–9) → `framework/memo_shell.html` + scorecard fragment +
   app-built "Appendix — Prior Deals" from the pipeline.
Framework text lives in `apps/deals/framework/` (copies of the two skills, methodology, memo structure, shell, `lens.md`).
Update those files when the skills change. Prompts in `prompts.py`; framework + materials are prompt-cached.

## Uploads
One file per request (`POST /api/v1/deals/<id>/files/`), 3 in parallel from the browser with per-file progress and
retries; sha256 de-dup per deal; `MAX_UPLOAD_MB` (200) / `MAX_FILES_PER_DEAL` (60). Storage: `MEDIA_ROOT` (start.sh uses
`/data/media` when a Volume is mounted at `/data`) or an S3-compatible bucket when `S3_BUCKET` is set.

## API (`/api/v1/deals/`, JWT; edits need admin/analyst/staff)
GET list (+meta) · POST create · `<id>/` GET/PATCH/DELETE · `<id>/files/` POST · `<id>/files/<fid>/` GET (download,
`?digest=1`) / DELETE · `<id>/analyze/` POST {model, instructions, redigest} · `<id>/cancel/` · `<id>/memo/` GET.

## Railway variables
`DATABASE_URL=${{Postgres.DATABASE_URL}}`, `ANTHROPIC_API_KEY`, `DJANGO_SUPERUSER_EMAIL` / `_PASSWORD`, optional
`SECRET_KEY`, `ANALYSIS_MODEL` (default claude-sonnet-5-5), `DIGEST_MODEL` (claude-haiku-5-5), `ANALYSIS_CONCURRENCY`,
`DIGEST_CONCURRENCY`, `MAX_UPLOAD_MB`, S3_* for a bucket. Attach a Volume mounted at `/data`.

## Conventions
Commit format `type(scope): message`. Tests: `cd backend && pytest` (pipeline test mocks `engine.ask`).
