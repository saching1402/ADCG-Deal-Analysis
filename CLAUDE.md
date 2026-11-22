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
DEAL FLOW (deal lead, Nov-26, redrawn 18-Nov as a diagram: Materials lane (factual base) + Web lane (sense check) →
7 steps → the business-plan panel (history bars + sponsor projections, value creation, sponsor cases, ADCG independent
review) → memo outline I–IV + Appendix; materials AND web TOGETHER at every step; shown on top of every framework page by
`components/DealFlow.tsx`, keep the two in sync): digest → overview → research → risk → integrate → score → memo
(`AnalysisJob.STAGES`, UI labels in `lib/format.ts`). `deal.research` = `OVERVIEW_HEAD` "# Opportunity summary" +
`RESEARCH_HEAD` "# Research & analysis" + `INTEGRATION_HEAD` "# Business plan, actuals & reconciliation".
2. **overview** (`stage_overview`, `prompts.OVERVIEW_TASK`) — materials + ≤10 web searches (`OVERVIEW_SEARCHES`) → the
   Opportunity summary: what the company does / for whom / how it delivers, how it makes money, customers, value chain,
   competition (IM list + web), history, management, the deal, claims to test. The IM leads the description (it explains
   a private, unglamorous business best — e.g. facility management), the web verifies. JSON: track, sector, sub_sector,
   website, sources. Replaces the old web-only "independent research" (data room withheld) and `identity_hint`.
3. **research** (`stage_research`, `RESEARCH_TASK`) — materials + summary + web (`ANALYSIS_MAX_SEARCHES`, 28): industry
   from first principles, market, competitors beyond the IM, people checks, comps & valuation, testing the claims; does
   not re-describe the company.
4. **risk** (`stage_risk`) — materials + research + web (`RISK_MAX_SEARCHES`, 18): PE track record in the sub-sector
   (graveyard themes), sponsor record, 2nd/3rd-order risks, capital structure / exit → `Deal.risk_review` +
   `Deal.risk_items` {risks[], track_record[], theme_verdict}.
5. **integrate** (`stage_integrate`, `INTEGRATE_TASK`) — business plan, actuals & reconciliation: identity check, numbers
   that replace estimates, actuals, management 5-yr plan + growth bridge + plan vs reality, terms, disagreements between
   materials and research, reconciliation across uploads; JSON sets headline `facts` (6 fixed keys, ≤22 chars, `src`
   tag "IM"/"Press"/"Est.", `engine.clean_facts`), ev/multiple/leverage/one_liner/sponsor, marks each risk
   `in_cim` yes|understated|no, adds risks only the materials raise, and `reconciliation`. ≤6 searches.
   HOW TO USE THE SOURCES (`prompts.APP_CONTEXT`, `MEMO_RULES`, `memo_blueprint.md`): describe the business from the
   Opportunity summary (IM-led, web-verified); market, competition beyond the IM, comps, precedents and risks from
   research; numbers only the company has from the materials; no generic web padding; tags HARD / IM / MGMT / ESTIMATE,
   no page refs except where documents disagree.
   SPONSOR MATERIALS = FACTUAL BASE (deal lead, 18-Nov-26): IM / market study / model / QoE are reviewed by many
   sophisticated LPs, so numbers and terms are summarised faithfully; the web contests the STORY (industry growth,
   position, oversold claims). `prompts.DEAL_TERMS` = key terms per deal type (buyout incl. co-invest fees & carry; CV:
   size, price vs NAV, lead, LP election, GP commitment/carry roll, CV fee/carry/hurdle, term; VG: instrument, pre/post,
   valuation cap & discount, liquidation preference, anti-dilution, pro-rata…) — appended to OVERVIEW_TASK (Deal /
   Company / Industry primer summary) and INTEGRATE_TASK (business plan: ONE history+plan table, value-creation levers,
   sponsor cases as presented, "ADCG independent review" + sensitivity tables). RESEARCH_TASK = independent market
   assessment (claims table Confirmed / Partly / Not supported, industry risks, exitability).
   18-Nov-26 (2): RISK_TASK = ONE combined review, all sources at the same time and ranked only by materiality
   (deal lead: the sponsor's own risks are INCLUDED, never handled first or separately) — sponsor-flagged, across all
   materials (QoE, DD, market study, model), independent web sense-check (regulation, disruption incl. AI labs, rates & capital structure, macro, geopolitics &
   tariffs, input costs/labour, 2nd/3rd-order, graveyard themes); each risk has `flagged_by` sponsor|materials|independent
   (Risk tab shows "Flagged by the sponsor / Found in the materials / Found by the independent review"). INTEGRATE_TASK
   adds 4a every case (sponsor · management · CV secondary lead's haircut · lender/VDD), value creation ranked in 3–4
   drivers, 4c returns across scenarios, 4d WHAT LOOKS OVERSTATED (3–6 crisp checks, memo `.overstated` box in §8).
   DEAL-SPECIFIC FACTORS: framework config `deal_specific {weight 10, min 2, max 4, guidance}` (defaults
   `with_deal_specific`, migration 0023, validated 0–30, editable card `#fw-deal-specific` on each framework page,
   rendered into the prompt); scorer returns `deal_specific[{name, why, score, rationale}]` → `scoring._clean` scales the
   framework sections to (100−w)% and adds section `Deal-specific factors` (w%) — none returned = no scaling. Criteria tab
   tags them "This deal" and compares defaults at the scaled weight. SCORE PANEL: `scoring.score_header` (total + band
   left; GP tier — `apply_gp_tiers` records `scorecard.gp_tiers` — / Marquee index, framework score before preferences,
   deal-specific factors right) inserted by `stage_memo` right under the Part III banner (`.sc-head`).
   FIGURES (deal lead, 18-Nov-26, all frameworks): DIGEST_SYSTEM adds "## Charts & figures worth reusing" (≤8 per file:
   location, title, type, the data read off the chart); MEMO_RULES / blueprint "Figures": redraw the important ones as
   inline SVG in `<figure class="fig">` with a caption + "Redrawn from IM p.x" (or "ADCG analysis"), ~5–8 per memo, only
   where a picture carries the argument; never copy the data room's charts wholesale or chart what a table shows.
NO RISK SCORE (deal lead's rule): ADCG does not score risk. `scoring.no_risk()` strips the risk card / gauge / formula
from the rendered scorecard, the VG risk register isn't scored or shown, `summary` has no `risk`, `Deal.risk_score` is
set to None, prompts (`APP_CONTEXT`, `frameworks.prompt_text`) forbid any numeric risk score; risks are highlighted
qualitatively (risk review, Pros & Cons). The UI shows no risk score (deal header, pipeline, memo history, Framework
tab has no Risk model section). The `risk` key stays in framework configs only for backward compatibility.
6. **score** — scorecard JSON in the skill schema → `apps/deals/scoring` (verbatim `adcg_scorecard.py` + the VG engine:
   Marquee GP Index, VJR, venture risk register). Retries once on bad JSON.
MEMO STRUCTURE (deal lead, 18-Nov-26 — all three frameworks; `memo_blueprint.md` "The memo structure",
`prompts.memo_tasks(track, sections)` = 4 calls): I Summary and Analysis (banner `.part-h`) — 1 Deal Overview · 2 Company
Overview · 3 Industry Primer and Independent Market Assessment · 4 Business Model, Value Chain, Competitive Landscape and
Exitability · 5 Value Creation Plan · 6 Financials and Business Plan (`table.bp`, plan cols `.plan`) · 7 Valuation
Analysis · 8 Returns Analysis and Independent Sensitivities (`.indep` box) | `h2.part` II · Investment Pros and Cons (+
Key risks inside) | III ADCG <Buyout|CV|Venture Growth> Deal Scoring — III.n per framework section (score, weight,
criterion table) + app-built `III.<n+1> · Framework Scoring Summary` (`scoring.memo_bars`) | `h2.part` IV · Recommendation
and Next Steps (.tldr first) | Appendix A.1 Sources and References · A.2 Definitions and Methodology. Shell: SCORECARD =
parts 1–3 + bars, BODY = part 4. Older memos (1–10 numbering) still render and revise.
OLDER MEMO CONTENT RULES (deal lead, still apply inside the new structure): section 6 is written by the app = the score bars + overall only (`scoring.memo_bars`;
criteria, weightings, Marquee GP Index and VJR live in the Scorecard tab); no Contrarian app/note, no staged gates or kill
criteria, no Prior Deals appendix; Recommendation is plain-English (decision · why · what to confirm · next step · what
we don't know yet); Pros & Cons is the centrepiece (7–10 each with evidence + "Why it matters" + Net assessment) as two STACKED numbered
lists (pros first, then cons — `.pc-list`); Recommendation is neutral/balanced, ~half a page (leaning · why ·
what would change our view · next step); Key risks = numbered bold-led paragraphs (`.risk-list`, **Valuation —** …), no
table, ≤ a page; section 5 = historical financials + business plan together (below); tables only where numbers are compared. SECTION BRIEF (deal lead, Nov-26 — `memo_blueprint.md` "WHERE EACH PART COMES
FROM"): 1 Company overview from the materials first (incl. the sponsor: who, where they invest, track record), verified
on the web · 2 **Industry primer** (never "technology primer") — materials' market claims CONTESTED with reliable external
sources (real growth, competition, sponsor crowding, valuation hype) · 3 business model / value chain / competition =
materials + web + any data-room market study (competitor revenues, locations, customers) · 4 transaction = `.kf` key-facts
grid (structure, EV, EBITDA adj/reported, multiple, leverage, debt terms, interest cover, equity, CV size, unfunded),
sources & uses `.su` REPLICATED from the materials, only 3–6 key findings · 5 **Financials, valuation & business plan** —
historical financials replicated EXACTLY from the materials (source of truth), business plan alongside, history vs plan,
bridge by driver + neutral market read per driver, our case (ESTIMATE). Story that flows, easy on the eye, ~20–28
pages. Source pills are tiny (`.src` 8px; doc/page refs inside the pill or `.ref`); `memo_css.patch` adds the current
pill/`.su`/`.kf` CSS to old memos at read time (preview + PDF).
7. **memo** — house format in `framework/memo_blueprint.md` (modelled on the Armada VG memo; buyout variant adds the
   IM's actuals, 5-yr business plan, growth bridge, plan vs reality, returns). Three calls (`prompts.MEMO_TASKS[track]`:
   1–3 story, 4–6 deal/financials/weights, 7–10) with components `.src` tags, `.gap`, `.explain`, `.flow`, `.chain`,
   `.cards`, SVG charts → `framework/memo_shell.html` + scorecard fragment +
   app-built "Appendix — Prior Deals" from the pipeline. Every completed memo is saved as a `MemoVersion` (html, scores,
   model, framework version, timestamp); `Deal.memo_html` = latest. `GET memo/` → latest + `versions`; `?version=<id>`;
   `?list=1`. **Download PDF** (memo toolbar, next to Download HTML; replaced the browser Print button): `GET memo/pdf/
   [?version=]` → `memo_pdf.render` = headless Chromium (Docker installs `chromium`; `CHROMIUM_PATH` overrides) with the
   paper colour forced (`print-color-adjust: exact`, `@page` background #f6f4ee, old memos' white print body / 12 mm
   margin neutralised) — looks like the preview; file name = the asset: "<Deal name> – Mindari IC memo vN.pdf" (HTML
   download named the same); audit `memo.download_pdf`. UI never shows a previous memo while a run is in progress or after an unfinished run (status card +
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
MAIN vs PERSONAL (Nov-26): `Framework` rows = the MAIN framework (the deal lead's; team default) — only admins
(`users.views.is_admin`: superuser or role admin) edit it (`PUT ?scope=main`, restore, reset-to-defaults). Everyone else
edits their own `PersonalFramework` (user, key incl. `house`; created on first save, `base_version` = main version copied),
which ONLY their analyses use: `run_job` sets `frameworks.ACTIVE_USER` = job.created_by, so `frameworks.get(key)` returns
their copy (`as_framework`, unsaved Framework) else the main; each run records `AnalysisJob.framework_source` (username or
'' = main) + `framework_config` snapshot (Criteria tab uses it). `frameworks.main(key)` always = main. API: GET/PUT
`<key>/` default scope = main for admins, mine for others (`?scope=main` read-only view); `<key>/reset-mine/`;
`<key>/propose/` {note} → `FrameworkProposal` (changes = `frameworks.diff(main, mine)`); `proposals/` (admin: all,
others: own); `proposals/<id>/` {action approve|reject|withdraw, response} — approve saves the proposer's config as a new
MAIN version (note "Approved X's proposal") and drops their copy if identical. UI: `ScopeBar` on each framework page
(Main framework / My framework · View main · Reset to main · Propose to main), same in the ADCG preferences panel;
Account page "Framework change requests" (admin approve/reject with reply; others see status / withdraw). The Claude
skills follow the MAIN framework only — nothing on the site writes to them.
ADCG PREFERENCES (`Framework` key `house`, defaults `defaults.HOUSE_CONFIG`) — NOT a fourth framework in the UI: each
framework page has an "ADCG preferences" subsection (`FrameworkPage` `PrefsSection`, the ones whose `applies` include it)
and a glossy red "ADCG preferences" pill centred in the tab bar on the Framework tab (static next to + New deal under 1100px) opens the shared editor as a slide-out
(`pages/HousePrefs.tsx`, `openPrefs()` event; `#framework/house` also opens it):
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
track record + management + structure/governance. Business Quality (Buyout + CV) always includes Competitive intensity &
pricing pressure, Disruption risk, Moat & barriers to entry (`defaults.COMPETITION_CRITERIA`, migration 0014; never
swapped out by the sector library — `frameworks.render` says so). CV Trophy Asset (migration 0016,
`defaults.TROPHY_CRITERIA`) = the sponsor's STAR asset kept by choice to compound, not a failed sale: performance within
the sponsor's fund · why a CV (kept by choice vs no buyer) · compounding runway · value creation so far · market position.
VG (migration 0017, `defaults.THEME_CRITERIA` / `VAL_CRITERIA`, live weights kept): Theme = themes we must not miss —
early signals · technology step-change · TAM & revenue momentum · crowding & timing · value capture · durability & policy;
Valuation & Evolution = entry multiple vs comps · quality-adjusted multiple (EV/gross profit, margins & moat) · VJR ·
evolution across rounds · terms · exit maths. `scoring.vjr` measures the fundamental step-up on GROSS PROFIT when
`valuation_evolution.gm_from/gm_to` are given (else ARR) and echoes `milestone`. VG weights (migration 0018,
`defaults.reweight_vg`): Theme 25 · Valuation & Evolution 15 · Investor Syndicate 25 · Company & Management 20 ·
Competition 10 · Venture Fundamentals 5. Syndicate = Marquee GP index (auto) · tier-1 lead in each round · insiders
doubling down · strategic investors (Nvidia, AMD, Broadcom, Google…) · tier-1 concentration. Company & Management =
founder track record (exits) · pedigree & network · moat & IP · customer quality & scaling · execution · team.
ADCG GP TIERS (key `gps`, `defaults.GPS_CONFIG`, ONE list shared by Buyout + CV; personal copies like any framework):
`sponsor_tiers` T1/T2/T3 (buyout sponsors) + `secondary_tiers` P1/P2/P3 (lead secondaries investors, CV) + `unlisted_score`.
Criteria with `auto: sponsor_tier` (Buyout: Sponsor Quality; CV: Alignment "Underlying sponsor tier") and `auto:
secondary_tier` (CV: Alignment "Lead secondaries investor tier") — the CV dual manager check — are scored by
`scoring.apply_gp_tiers` from the scorer's `sponsor_gp` / `secondary_lead` (fuzzy `gp_tier` match; not listed → the
scorer's own score, else `unlisted_score`). `frameworks.gps_text` adds the lists to Buyout/CV prompts (migration 0020).
UI: `GpTiersSection` on the Buyout and CV framework pages (P1–P3 edited on the CV page).
GP TIER MEMBERS ARE FIRMS (migration 0021, `framework/gp_entities.py`): every tier member (ADCG GP tiers AND the VG
Marquee tiers) is `{name, domain, aliases?, note?, heard?}` — old plain strings still load via `gpe.as_member`
('NVentures / NVIDIA' → aliases; `VG_DOMAINS` gives VG names their websites). Matching is by IDENTITY, never shared words:
`gpe.find(tiers, name, domain)` = website first (`same_domain`), else the exact `name_key` of the name or an alias, and a
member whose website differs is never matched by name (The Sterling Group ≠ Sterling Investment Partners; 'TPG Capital'
≠ 'TPG' unless the scorer gives tpg.com). The scorer returns `sponsor_gp_domain` / `secondary_lead_domain` and each VG
investor's `domain`. Deal lead's verified lists (`SPONSOR_T1` 19, `SPONSOR_T2` 47; `heard` = the dictated spelling) are
loaded by `load_sponsor_lists`; lead secondaries `SECONDARY_P1` 8 / `SECONDARY_P2` 10 by `load_secondary_lists` (migration 0022;
a website-less entry under one of the firm's names is replaced). `GET /api/v1/frameworks/gp-lookup/?q=` = firms already on the lists (+ where) + live
web lookup (`suggest.external`). UI: `components/GpPicker.tsx` — `MemberChips` (logo chips; dashed = no website yet) and
the small **Find GP** voice/type finder next to the GP tiers / Marquee GP Index headings (pick a firm → tier buttons; a
firm already listed is moved; manual name + website fallback). Proposals list GP tier adds/moves (`frameworks.diff`).
SYNDICATE CLUSTERS (deal lead, 20-Nov-26, migration 0024): VG `marquee.floors` {t1_one 8, t1_two 9, t1_three 9.5,
good_three 8} — `scoring.marquee` lifts the formula score to the floor for distinct tier-1 names (and 3+ T1/T2/S names);
smaller / unlisted VCs never lower it; guidance on Marquee GP depth + Tier-1 concentration + `render` text says so;
editable on the VG framework page. Buyout / CV: scorer may return `co_sponsor_gp` / `_domain`; `apply_gp_tiers` checks
both, the stronger sets the sponsor-tier score (rationale names both), `scorecard.co_sponsor_tier` shows in the score panel.
GP tier moves (migration 0019, `defaults.move_tiers`): AlleyCorp → T1; 8VC, Factorial Funds, True Ventures, SOSV, Monolith → T2.
FUND MANAGER EVALUATION (deal lead, 20-Nov-26): 4th framework key/track `fund` = **ADCG Fund Manager Evaluation** — primary
fund commitments (large-cap / mid-market / lower mid-market buyout, venture & growth, GP-led and LP-led secondaries) from
the manager's data room. `defaults.FUND_CONFIG` (+ `framework/fund_skill.md` guidance): Strategy & Positioning 15 · Track
Record 25 · Underlying Portfolio Quality 20 · Team & Stability 20 · DDQ, ODD & Governance 10 · Terms & Market Standing 10
("Manager tier" auto=sponsor_tier, matched against BOTH ADCG GP lists — sponsor T1–T3 and secondaries P1–P3), weighting
rules for venture / secondaries / emerging managers, deal-specific 10%. Stage prompts via `prompts.task(name, track)`
(`FUND_OVERVIEW_TASK`, `FUND_RESEARCH_TASK` incl. background/litigation/departures/HEC–Dow Jones standing, `FUND_RISK_NOTE`,
`FUND_INTEGRATE_TASK`, `SCORE_TASK_FUND`). TRACK-RECORD ANALYTICS ARE COMPUTED BY THE APP, never by the model:
`fund_analytics.py` reads the portfolio workbook (deal schedule, fund table, long or wide cash flows; Total rows skipped;
xlsb/xls/ods converted) → `compute`: pooled MOIC / IRR (cash-flow XIRR, else two-point or weighted), loss ratio, ex-top-1/2/3,
top-2 share of gains, by fund / sector / deal lead / vintage / region, outcome buckets, dispersion → `Deal.analytics`
(migration 0025); fallback = deals/funds the model extracted. `fa.brief` feeds the prompts; `engine.insert_analytics` drops
`fa.memo_block` (KPI tiles + SVG scatter / histogram / ex-top bars / group bars) under "4 · Underlying Portfolio Analysis"
(re-inserted on revise). Fund memo (`prompts.fund_memo_tasks`): I — 1 Introduction to the Manager · 2 Strategy · 3 Track
Record · 4 Underlying Portfolio Analysis · 5 Team and Management Biographies · 6 Independent Background Verification · 7 DDQ
Check · 8 Operational Due Diligence (RAG visual) · 9 Market Standing and Peer Ranking · 10 Fund Terms and Alignment | II Pros
& Cons | III ADCG Fund Manager Evaluation Scoring | IV Recommendation | Appendix. `GET <id>/dashboard/` = standalone sortable
HTML dashboard (`fa.dashboard_html`; detail JSON `has_dashboard`) → "Track-record dashboard" button on the memo toolbar.
VINTAGE QUARTILES (deal lead, 22-Nov-26): every fund vs ITS OWN vintage-year quartiles for the narrowest published peer
group (e.g. Europe buyout). FUND_RESEARCH_TASK finds the thresholds (manager's own benchmark first, checked; else Cambridge /
Burgiss / Preqin / PitchBook / Invest Europe on the web; "not found" never estimated) → "Vintage benchmarks" table;
FUND_INTEGRATE_TASK returns `benchmarks[{fund, vintage, peer_group, source, as_of, origin materials|web, net_irr/net_tvpi/dpi
{uq, med, lq}}]` and the manager's claimed quartile verbatim — the model never assigns a quartile. `fa.benchmark` places each
fund per metric (≥UQ Q1, ≥median Q2, ≥LQ Q3, else Q4; inconsistent thresholds ignored; matched by fund then vintage), overall
= IRR & TVPI (a split rounds to the more conservative), `claim_check` confirmed / better / overstated, `too_early` < 4 yrs →
`Deal.analytics.quartiles`; `fa.quartile_brief` appended to `deal.research` (scorer + memo use it); `engine.insert_quartiles`
puts `fa.quartile_block` (KPIs, table with Q pills, net TVPI / net IRR band charts, "no benchmark" gap) under "3 · Track
Record" (memo, revise, dashboard). Migration 0026 updates the criterion guidance (`defaults.QUARTILE_GUIDE`).
UI: Framework tab "ADCG Fund Manager Evaluation" (`#framework/fund`, `DealFlow` → `FundFlow`), New deal "ADCG Fund Manager",
badge "Fund". ADCG preferences can now be ticked for Fund (none apply by default).
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
reduced-motion respected. Banners render inside `#main`. Deals page views: **Cards** (default; `components/DealCards.tsx` — swipeable
glossy carousel, scroll-snap, centre card highlighted via JS-set --s/--o/--ry, mouse drag / trackpad / ← → / arrows,
click centre card = open, side card = centre it) and **Table**; choice remembered in localStorage `deals-view`. No board view. Pipeline table hover: `RowGlowTable` — one floating `.row-glow` (shadow + pastel wash + glossy sweep) glides behind the hovered row; row lifts, logo pops.
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
RE-RUN AN EXISTING DEAL (deal lead, 18-Nov-26 — e.g. a ledger deal with scores only): the New deal page spots a company
already in the pipeline by name (`twin`, ignoring Group/Holdings/Inc… suffixes) and offers **Re-run <deal>** (uploads go
into that deal, analysis starts with `redigest`, empty fields never overwrite its saved values) · Open it · create a
separate deal; picking a pipeline row there opens `deal-<id>?run=1` (the run dialog opens once). The deal page's empty
memo state has a **Run the analysis →** button, and the run dialog (`RerunDialog`) has a file picker, so files can be
added and the run started in one step ("Run — public info only" when there are none). HEADLINE REFRESH: `engine.refresh_headline`
(both integrate paths) overwrites ev / multiple / leverage / sponsor / one_liner / facts with whatever the run found
(never "only if empty"), logging "Headline figures replaced with the latest materials: EV old → new; …"; a successful run
sets `legacy=False`; the run dialog and the Re-run banner say the headline figures will be replaced.
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
Accepted spreadsheets (`extract.SHEETS`): .xlsx .xlsm .xltx .xltm .xlsb .xls .ods .numbers (xlsb/xls/ods/numbers converted to
.xlsx via LibreOffice first) — an .xlsb model used to be greyed out in the file window; `FilePicker` also has "Show all
file types" (an unfiltered input; unsupported types are skipped with the reason). One file per request (`POST /api/v1/deals/<id>/files/`), 3 in parallel from the browser with per-file progress and
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
