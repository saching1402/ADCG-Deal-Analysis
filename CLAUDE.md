# CLAUDE.md — Mindari / Deal Analysis

Context for AI assistants working on this repo. Keep it current.

**What it is:** the PE team's deal pipeline ("IC Agent"). Landing page (`''`, `pages/HomePage.tsx`) = a quiet glossy
canvas with one action — "What are we looking at today?" + company search (+ voice mic) → **Analyse a new deal** (→ `new?q=&w=`); no deal
count or quick links on it;
the pipeline of every deal analysed is its own tab (`#pipeline`);
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
   - Protected files (common in data rooms): AES copy/print-protected PDFs open via `cryptography` (owner password
     removed); `extract.unwrap_office` handles OLE-wrapped .xlsx/.docx/.pptx — encrypted without a prompt (Excel's
     default "VelvetSweatshop" password) → decrypted with `msoffcrypto-tool`; real password / IRM sensitivity label →
     blocked with the exact fix; legacy binary saved under a modern extension → converted. Messages say the true cause.
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
   - Each file gets a `doc_role` (`roles.py`: cim, model, qoe, market, structure, sponsor_memo, legal, financials,
     other) guessed from name + fact sheet; the user can change it in the Files tab (PATCH `files/<fid>/` {doc_role}).
ORDER (independent view first, data room second):
2. **research** (`stage_research`) — INDEPENDENT deep research, web only (`ANALYSIS_MAX_SEARCHES`, 40). The data room is
   withheld; only `identity_hint()` (a ≤500-char company description from the CIM digest, marked "not evidence") is
   passed so codenamed deals resolve. Dossier organised like the memo blueprint; estimates where only the company knows.
   JSON: track, sector, sub_sector, website, sources.
2b. **risk** (`stage_risk`) — independent risk review, web only (`RISK_MAX_SEARCHES`, 18): PE track record in the
   sub-sector (graveyard themes), sponsor record, 2nd/3rd-order risks, capital structure / exit → `Deal.risk_review` +
   `Deal.risk_items` {risks[], track_record[], theme_verdict}.
2c. **integrate** (`stage_integrate`) — brings in the data room: materials + independent dossier + risk review → a
   "# Data-room integration" section appended to `Deal.research` (`INTEGRATION_HEAD`): identity check, numbers that
   replace estimates, actuals, management 5-yr plan + growth bridge + plan vs reality, terms, disagreements between
   materials and research, reconciliation across uploads; JSON sets headline `facts` (6 fixed keys, ≤22 chars, `src`
   tag "IM"/"Press"/"Est.", `engine.clean_facts`), ev/multiple/leverage/one_liner/sponsor, marks each independent risk
   `in_cim` yes|understated|no, adds risks only the materials raise, and `reconciliation`. ≤6 searches.
   HOW TO USE THE SOURCES (`prompts.APP_CONTEXT`): story from research, IM for the numbers only the company has (plan =
   base case), tags HARD / IM / MGMT / ESTIMATE, no page refs except where documents disagree. Memo sections show risk
   review as 8 (buyout) / 10 (VG, Armada order 7 Verdict · 8 Pros & Cons · 9 Gates · 10 Risk review).
NO RISK SCORE (deal lead's rule): ADCG does not score risk. `scoring.no_risk()` strips the risk card / gauge / formula
from the rendered scorecard, the VG risk register isn't scored or shown, `summary` has no `risk`, `Deal.risk_score` is
set to None, prompts (`APP_CONTEXT`, `frameworks.prompt_text`) forbid any numeric risk score; risks are highlighted
qualitatively (risk review, Pros & Cons). The UI shows no risk score (deal header, pipeline, memo history, Framework
tab has no Risk model section). The `risk` key stays in framework configs only for backward compatibility.
3. **score** — scorecard JSON in the skill schema → `apps/deals/scoring` (verbatim `adcg_scorecard.py` + the VG engine:
   Marquee GP Index, VJR, venture risk register). Retries once on bad JSON.
MEMO CONTENT RULES (deal lead): section 6 is written by the app = the score bars + overall only (`scoring.memo_bars`;
criteria, weightings, Marquee GP Index and VJR live in the Scorecard tab); no Contrarian app/note, no staged gates or kill
criteria, no Prior Deals appendix; Recommendation is plain-English (decision · why · what to confirm · next step · what
we don't know yet); Pros & Cons is the centrepiece (7–10 each with evidence + "Why it matters" + Net assessment) as two STACKED numbered
lists (pros first, then cons — `.pc-list`); Recommendation is neutral/balanced, ~half a page (leaning · why ·
what would change our view · next step); Key risks = numbered bold-led paragraphs (`.risk-list`, **Valuation —** …), no
table, ≤ a page; section 5 is concise (current valuation first, ONE financials table, ONE compact comps table ≤ 6 names);
tables only where numbers are compared, ~12–16 pages.
4. **memo** — house format in `framework/memo_blueprint.md` (modelled on the Armada VG memo; buyout variant adds the
   IM's actuals, 5-yr business plan, growth bridge, plan vs reality, returns). Three calls (`prompts.MEMO_TASKS[track]`:
   1–3 story, 4–6 deal/financials/weights, 7–10) with components `.src` tags, `.gap`, `.explain`, `.flow`, `.chain`,
   `.cards`, SVG charts → `framework/memo_shell.html` + scorecard fragment +
   app-built "Appendix — Prior Deals" from the pipeline. Every completed memo is saved as a `MemoVersion` (html, scores,
   model, framework version, timestamp); `Deal.memo_html` = latest. `GET memo/` → latest + `versions`; `?version=<id>`;
   `?list=1`. UI never shows a previous memo while a run is in progress or after an unfinished run (status card +
   dated History instead); older versions open only on request, with an "Older memo — vN, <date>" banner.
REVIEW & REVISE (cheap re-run): `MemoComment` (deal, memo version, author, stance agree|disagree|context|question|change,
text, quote = selected passage, section, via typed|voice, status open|applied|dismissed, applied_in, response).
API `<id>/comments/` GET/POST · `<id>/comments/<cid>/` PATCH/DELETE (applied ones are kept) · `<id>/revise/` POST {model}
→ `AnalysisJob.mode='revise'` → `engine.stage_revise`: stages `rescore` (scorecard JSON + comments → changed criteria →
`score()` → new bars) and `revise` (memo with scorecard placeholder → only the affected sections as ```html blocks,
each starting with its original <h2>, swapped in by `apply_sections`/`memo_sections`) → new `MemoVersion`, comments
marked applied with a response, "Deal lead review — comments applied" table at the end. No digest/research/risk/
integrate. UI (`components/MemoReader.tsx`): memo iframe + sticky Review panel; the frame is sandboxed WITHOUT scripts,
so the selection is POLLED (220 ms) — a selection shows a "Comment on this" button, a click inside a highlighted passage
focuses its note; quotes are painted with the CSS Custom Highlight API (`findRange` matches ignoring whitespace);
no stance labels (deal lead wants plain comments: highlight → "Comment on this", or a general comment); composer has ⌘/Ctrl+Enter and voice dictation via the Web Speech API (Chrome/Edge/Safari).
Cost: `request_cost` uses per-model prices in `settings.ANALYSIS_MODELS` (Sonnet/Opus 5.5 cache reads 0.05× input);
meta `recent_costs` = actual avg of the last 10 done runs per model, shown next to the estimate on the New deal page.
`ask()` continues replies cut off at max_tokens (up to 3 continuations) and retries an empty reply once with twice the
room; digests get 12K tokens per 25-page part. THINKING: the 5.x models think by default and `max_tokens` covers
thinking + text, so `engine.thinking_opts` turns thinking off for reading/memo writing (Haiku 5.5 `disabled`, Sonnet 5.5
`between_tools`, Opus effort low) and keeps it with +16K room for research/risk/score (`think=True`). Without this a
digest can spend its whole budget thinking and return no text ("summary came back empty").
Files card: read failures (not missing files) are retried by "Re-read N files & run".
Prompts in `prompts.py`; framework + materials are prompt-cached.

## Frameworks (editable, versioned — Framework tab)
ADCG PREFERENCES (`Framework` key `house`, `#framework/house`, `pages/HousePrefs.tsx`, defaults `defaults.HOUSE_CONFIG`):
house rules applied to every deal on every framework — preferences[{id,title,importance high|medium|low,applies[buyout|cv|vg],
guidance}] + `max_adjust` (0.5). `frameworks.house_text(track)` is appended to every stage's system prompt (memo: weave
into the narrative, never a list/section); the scorer returns `house_fit[{id,fit −2..2|null,why}]`;
`scoring.apply_house` → importance-weighted mean fit (−1..1) × max_adjust added to the overall (band recomputed), saved
as `scorecard.house` + `summary.framework_overall/house_adj`, noted under the memo bars, shown in the Criteria tab.
Not in `KEYS` (not a scoring track); `ALL_KEYS` for the API/seed.
THREE frameworks (Nov-26): `buyout` = **ADCG Buyout** (buyouts, co-invests alongside a sponsor) — sections Sector Focus ·
**Sponsor Quality** (replaced Trophy Asset; weights placeholder until the deal lead sets them) · Business Quality ·
Valuation & Leverage · Alignment (no sponsor criterion); `cv` = **ADCG CV** (continuation vehicles / GP-led secondaries)
= the ORIGINAL buyout framework (Trophy Asset; history copied by migration 0012, which also rebuilt `buyout` via
`defaults.buyout_from_cv`); `vg` = ADCG Venture Growth (unchanged). Track `cv` everywhere (`Deal.track`, research JSON,
`TRACK_RULE`, `SCORE_TASK['cv']`; CV memos use the buyout memo templates via `prompts.base()`; badge "CV";
`#framework/cv`). Existing deals keep their track until re-analysed. Alignment has NO Mark credibility / Minority
protections-information rights criteria in any framework (migration 0013 `defaults.drop_alignment_extras`, which also
rewrites the co-invest weighting rule so it never re-adds them): Buyout = management + structure/governance; CV = sponsor
track record + management + structure/governance.
`Framework` (key `buyout` | `cv` | `vg`: name, description, `config` JSON, `guidance` markdown, `version`) + `FrameworkVersion`
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
Skin = lsvp.com language on the same white canvas/layout: header + tabs float over the page in `.topbar` (no box;
soft blur/fade edge; `#main` is absolute with padding-top so content slides under), uppercase letter-spaced text tabs
with sliding underline, black clipped-corner primary buttons (`--clip`), big light display type, flat 3px cards with
pastel washes (`--wash-*`) instead of shadows, faint pastel glow top-right. Motion: Lenis inertia scroll on `#main` tuned to lsvp.com's Locomotive feel (lerp 0.088, wheelMultiplier 0.72 — measured: a 100px tick travels 72px, settles in ~0.85s)
(`useSmoothScroll`; inner scrollers excluded via `prevent`). Home search has a glowing silver mic (`HomePage` `MicButton`, `lib/dictation.ts` `useDictation({continuous:false})`): speak a company name → it fills the box live and opens the suggestions (`CompanySearch` `trailing` + `openSignal`); hidden where the browser has no Web Speech API, route fade/blur-in, blur-in reveal on scroll (`useReveal`),
reduced-motion respected. Banners render inside `#main`. Pipeline table hover: `RowGlowTable` — one floating `.row-glow` (shadow + pastel wash + glossy sweep) glides behind the hovered row; row lifts, logo pops.
White header with navy top rule + tab bar (Home · Deals (route `#pipeline`) · Framework · Usage · Activity · open deal · **+ New deal** on the
right); the logo goes home. Deal tabs: IC memo · **Criteria** (`components/CriteriaTab.tsx` — "how this deal was scored": framework + version, sector playbook, Standard vs Tailored criteria per section (fuzzy-matched against `criteria_basis` = the framework snapshot the last scoring run used, from `views.criteria_basis`), defaults not used, default-vs-deal weight bars with the reason for each move) · Scorecard · Risk review · Research · Files · Runs · Activity. Hash
routes: `''` home (landing), `pipeline`, `framework` / `framework/vg`, `new` / `new?q=<name>` New deal page (not a modal), `deal-<uuid>[/<tab>]`. Logos: `components/Logo.tsx`
(Google favicon service by domain, initials fallback) — every deal row, board card, deal header, suggestion.
`components/CompanySearch.tsx` = search box with dropdown: mode `pipeline` (existing deals + "Analyse X as a new deal")
and mode `company` (real companies via `GET /api/v1/deals/suggest/?q=` → `apps/deals/suggest.py`: pipeline matches +
Clearbit Autocomplete + Clearout + Wikidata, keyless, merged by domain, cached 6h, each source fail-soft).
Ledger rows get websites from `data/ledger_seed.json`; `seed_ledger --if-empty` backfills empty websites on existing rows.

New deal page never creates or runs anything on its own: **Run analysis** unlocks with a company name (+ API key);
files are OPTIONAL — files = VDR access; no files = public-information analysis ("Run analysis — public info only").
**Save as draft** creates the deal without running.
No data room: `deal_brief` says "Data room: NONE" (every company figure HARD or ESTIMATE, gaps → diligence gates);
digest is skipped; `stage_integrate` → `finalise_without_dataroom` (headline facts from research + what a VDR must
answer, no searches); risks get `in_cim = 'n/a'` ("No data room" in the Risk tab).

## Accounts & activity log
Each person has their own account (`apps/users`): **username login** (`USERNAME_FIELD='username'`, case-insensitive;
email is optional and, where set, also signs in — `LoginSerializer`; old clients posting `email` still work). Roles admin |
analyst | viewer. No emails in the UI. `seed_team` (start.sh, idempotent, never resets a password) creates ali, ray, lyes
(analysts) and admin (admin) with DJANGO_SUPERUSER_PASSWORD as the starter password, names the owner account `sachin`,
renames an untouched `lyees` → `lyes` and clears placeholder `@deal-analysis.local` emails (migration 0003 too).
`password_changed_at` null = still on a starter password → amber banner until they set their own. **Account** page
(`#account`): profile, change password (`POST users/me/password/`), and for admins a Team table (add user, role,
deactivate, reset password → `users/`, `users/<id>/`, `users/<id>/reset-password/`). Logout clears the query cache.
**Activity log** (`apps/audit`): `AuditMiddleware` writes an `AuditEvent` for every POST/PUT/PATCH/DELETE under
`/api/v1/` plus file downloads and sign-ins (failed ones too) — actor, action (`deal.update`, `file.upload`,
`analysis.start`, `framework.update`, `credit.sync`, `user.reset_password`, `auth.login`…), human summary, deal id +
name snapshot, old→new values for deal/file edits, status, IP, user agent; passwords/tokens never stored. The worker
adds `analysis.done|failed|blocked` (memo version, scores, cost). Append-only (no edit/delete API). `GET /api/v1/audit/`
?deal ?user ?group ?q ?before; `?export=csv`. UI: **Activity** tab (`#activity[?user=<id>]`) and a deal's Activity tab.
New mutating endpoints get a generic entry automatically — add a specific branch in `middleware._log` for a nice summary.

## Usage & capacity (Usage tab, header meters)
`apps/deals/usage.py` → `GET /api/v1/usage/` (meters + suggestions); `PATCH` = one of {console_balance} (deal lead types
the Claude Console balance → new anchor, drift vs estimate logged) | {topup} (adds to the estimate) | settings
(`storage_capacity_gb`, `db_capacity_gb`, `plan` hobby|pro|bucket, `warn_below`, `stop_below` — blank = off);
`POST` frees space on approved/passed/on-hold deals (or `deal_ids`); per deal `POST /api/v1/deals/<id>/free-space/`.
**Claude credit is user-controlled**: nothing is detected from billing and there is no default budget. Remaining =
recorded balance − Σ `AnalysisJob.cost` since `credit_as_of` (an estimate; re-sync from the Console). `stop_below`
makes `/analyze/` return 409 `code=credit_paused` (UI asks, then retries with `override_credit`). Log of syncs/top-ups
in `AppSetting` `credit_log`. Storage = real volume size via `shutil.disk_usage('/data')` when mounted (else setting;
bucket = no limit); DB = `pg_database_size`. Storage/DB levels warn 70% / high 85% / critical 95%. "Free up" deletes
original files with fact sheets (`DealFile.archived_at`); digests, research, scores and memos stay; re-analysis skips
archived files. `settings.STORAGE_PERSISTENT` false on Railway without a /data volume or bucket → critical banner.

## Uploads
File rows report `missing` when the stored copy is gone (e.g. lost in a redeploy before a volume); the Files tab
offers per-file **Re-upload** and **Re-upload missing files…** (multi-select matched by name, extras optionally added).
One file per request (`POST /api/v1/deals/<id>/files/`), 3 in parallel from the browser with per-file progress and
retries; sha256 de-dup per deal; `MAX_UPLOAD_MB` (200) / `MAX_FILES_PER_DEAL` (60). Storage: `MEDIA_ROOT` (start.sh uses
`/data/media` when a Volume is mounted at `/data`) or an S3-compatible bucket when `S3_BUCKET` is set.

## API (`/api/v1/deals/`, JWT; edits need admin/analyst/staff)
GET list (+meta) · POST create · `suggest/?q=` · `<id>/` GET/PATCH/DELETE · `<id>/files/` POST · `<id>/files/<fid>/` GET (download,
`?digest=1`) / DELETE · `<id>/files/<fid>/replace/` POST (re-upload into the same slot; identical sha + existing
fact sheet → kept, otherwise reset to `uploaded`) · `<id>/analyze/` POST {model, instructions, redigest} · `<id>/cancel/` · `<id>/memo/` GET.

## Railway variables
`DATABASE_URL=${{Postgres.DATABASE_URL}}`, `ANTHROPIC_API_KEY`, `DJANGO_SUPERUSER_EMAIL` / `_PASSWORD`, optional
`SECRET_KEY`, `ANALYSIS_MODEL` (default claude-sonnet-5-5), `DIGEST_MODEL` (claude-haiku-5-5), `ANALYSIS_CONCURRENCY`,
`DIGEST_CONCURRENCY`, `MAX_UPLOAD_MB`, S3_* for a bucket. Attach a Volume mounted at `/data`.

## Conventions
Commit format `type(scope): message`. Tests: `cd backend && pytest` (pipeline test mocks `engine.ask`).
