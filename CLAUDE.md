# CLAUDE.md — Mindari / Deal Analysis

Context for AI assistants working on this repo. Keep it current.

**What it is:** the PE team's deal pipeline ("IC Agent"). Landing page = pipeline of every deal analysed;
**+ New deal** takes a company name, optional terms and 15–20+ data-room files, then a background worker reads the files,
researches the web, scores the deal on the **ADCG Buyout** or **ADCG Venture Growth** framework and writes the IC memo.

**Independence (hard rule):** this app is fully separate from the Venture GP Atlas website — different end users, own
GitHub repo, own Railway project, own Postgres, own Volume, own user accounts and own `ANTHROPIC_API_KEY`. No shared
database, API calls, imports, auth or data feeds in either direction. The venture GP tier list used for the Marquee GP
Index lives in `framework/venture_growth_skill.md`; edit it there, never fetch it from another app.

**Stack:** Django 5 + DRF + SimpleJWT + PostgreSQL
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
1. **read & verify** (`digest`) — HARD GATE: every file must be fully read before research starts.
   - Upload: `extract.inspect` (local, free) runs on every file; `block` (password-protected, damaged, empty, no values)
     → 422, file not stored; `ok`/`warn` + notes saved in `DealFile.readability` (pages, text-layer coverage, sheets…).
   - `extract.prepare` → `Part`s covering everything: PDFs of ANY size are split natively (`PART_PAGES` 40 pages /
     `PART_MB` 18 MB per part; owner-password removed; an oversize page is rasterised); pptx/ppt/doc/rtf/odt → PDF via
     LibreOffice; xlsx/xls/ods → all sheets/rows (recalculated through LibreOffice when formulas have no saved values);
     docx paragraphs+tables in order; images; text/CSV/HTML/email.
   - Each part's fact sheet is checked by `extract.digest_ok` (length, "can't read" phrases, figures); a failed part is
     retried as page images (poppler `pdftoppm`) or with the main model; still failing → recorded in
     `DealFile.coverage.failed`; file status `partial` / `error`.
   - Any `partial`/`error` file → `FilesBlocked` → job + deal status `blocked` ("Files need attention" panel: re-read,
     replace, remove, or run with `allow_partial`, which skips re-reading and tells the memo exactly what wasn't read).
   - Bad key / no credit aborts the read without marking files failed (`preflight()` checks the key first).
   - Migration 0004 re-queues files read before the gate existed (old text-only fallback or failing fact sheets).
   Docker image includes `poppler-utils` + LibreOffice (writer/calc/impress) + fonts for this.
2. **research** — web search (`ANALYSIS_MAX_SEARCHES`) + all digests → dossier + metadata JSON (track, sector, facts…).
3. **score** — scorecard JSON in the skill schema → `apps/deals/scoring` (verbatim `adcg_scorecard.py` + the VG engine:
   Marquee GP Index, VJR, venture risk register). Retries once on bad JSON.
4. **memo** — two calls (sections 1–6 weights, then 7–9) → `framework/memo_shell.html` + scorecard fragment +
   app-built "Appendix — Prior Deals" from the pipeline.
Prompts in `prompts.py`; framework + materials are prompt-cached.

## Frameworks (editable, versioned — Framework tab)
`Framework` (key `buyout` | `vg`: name, description, `config` JSON, `guidance` markdown, `version`) + `FrameworkVersion`
(snapshot per save; history/restore). Seeded by `seed_frameworks` from `framework/defaults.py` (structured from the two
ADCG skills; guidance = skill text minus what is now structured). `config`: `weights_flex`, `sections[{name, weight,
description, criteria[{name, guidance, auto?}]}]`, `bands[{label,min}]`, `risk{method derived|register, formula,
register[{name,weight}]}`, `overlays[]`, buyout: `weighting_rules[{when,rule}]`, `sector_library[{name,anchor,criteria,
comps}]`; vg: `tiers[{id,label,lead,part,cap?,members[]}]`, `marquee{base,slope}`, `vjr{ok,caution}`; `anchors[]`,
`calibration_note`. `frameworks.validate` enforces section weights = 100 and register = 100.
`frameworks.prompt_text(key)` = guidance + rendered AUTHORITATIVE "SCORECARD DEFINITION" + app-internal JSON schema
(`defaults.SCHEMA`) → used by every stage. `scoring.score(deal, track, cfg)` applies fixed weights, bands, tier points
+ member re-matching, marquee formula, VJR thresholds and register weights from the config. Each run records
`AnalysisJob.framework_version`. Edits apply to the next analysis; existing deals keep their scores until re-analysed.
API `/api/v1/frameworks/`: GET list · `<key>/` GET (`?preview=1` → rendered prompt block) / PUT {config, guidance, name,
description, note, base_version} (409 on stale base) · `<key>/history/` · `<key>/restore/` {version} | {reset: true}.
Other reference text stays in `apps/deals/framework/` (memo structure, memo shell, `lens.md`; the original skill copies
are the source for defaults).

## UI (`frontend/src`)
White header with navy top rule + tab bar (Pipeline · Framework · open deal · **+ New deal** on the right, gold). Hash
routes: `''` pipeline, `framework` / `framework/vg`, `new` / `new?q=<name>` New deal page (not a modal), `deal-<uuid>[/<tab>]`. Logos: `components/Logo.tsx`
(Google favicon service by domain, initials fallback) — every deal row, board card, deal header, suggestion.
`components/CompanySearch.tsx` = search box with dropdown: mode `pipeline` (existing deals + "Analyse X as a new deal")
and mode `company` (real companies via `GET /api/v1/deals/suggest/?q=` → `apps/deals/suggest.py`: pipeline matches +
Clearbit Autocomplete + Clearout + Wikidata, keyless, merged by domain, cached 6h, each source fail-soft).
Ledger rows get websites from `data/ledger_seed.json`; `seed_ledger --if-empty` backfills empty websites on existing rows.

New deal page never creates or runs anything on its own: **Run analysis** unlocks only with a company name + at least one
file (+ API key); **Save as draft** creates the deal without running.

## Usage & capacity (Usage tab, header meters)
`apps/deals/usage.py` → `GET /api/v1/usage/` (meters + suggestions), `PATCH` settings (`AppSetting` key `usage`:
`monthly_budget_usd`, `storage_capacity_gb`, `db_capacity_gb`, `plan` hobby|pro|bucket), `POST` frees space on all
approved/passed/on-hold deals (or `deal_ids`); per deal `POST /api/v1/deals/<id>/free-space/`. Storage = real volume size
via `shutil.disk_usage('/data')` when mounted (else setting; bucket = no limit); DB = `pg_database_size`; model spend =
Σ `AnalysisJob.cost` this month vs budget, projected to month end, by model, 6-month history, failed/paused spend.
Levels warn 70% / high 85% / critical 95% drive colours, suggestions and the red site banner. "Free up" deletes original
files with fact sheets (`DealFile.archived_at`); digests, research, scores and memos stay; re-analysis skips archived files.
`settings.STORAGE_PERSISTENT` false on Railway without a /data volume or bucket → critical banner.

## Uploads
One file per request (`POST /api/v1/deals/<id>/files/`), 3 in parallel from the browser with per-file progress and
retries; sha256 de-dup per deal; `MAX_UPLOAD_MB` (200) / `MAX_FILES_PER_DEAL` (60). Storage: `MEDIA_ROOT` (start.sh uses
`/data/media` when a Volume is mounted at `/data`) or an S3-compatible bucket when `S3_BUCKET` is set.

## API (`/api/v1/deals/`, JWT; edits need admin/analyst/staff)
GET list (+meta) · POST create · `suggest/?q=` · `<id>/` GET/PATCH/DELETE · `<id>/files/` POST · `<id>/files/<fid>/` GET (download,
`?digest=1`) / DELETE · `<id>/analyze/` POST {model, instructions, redigest} · `<id>/cancel/` · `<id>/memo/` GET.

## Railway variables
`DATABASE_URL=${{Postgres.DATABASE_URL}}`, `ANTHROPIC_API_KEY`, `DJANGO_SUPERUSER_EMAIL` / `_PASSWORD`, optional
`SECRET_KEY`, `ANALYSIS_MODEL` (default claude-sonnet-5-5), `DIGEST_MODEL` (claude-haiku-5-5), `ANALYSIS_CONCURRENCY`,
`DIGEST_CONCURRENCY`, `MAX_UPLOAD_MB`, S3_* for a bucket. Attach a Volume mounted at `/data`.

## Conventions
Commit format `type(scope): message`. Tests: `cd backend && pytest` (pipeline test mocks `engine.ask`).
