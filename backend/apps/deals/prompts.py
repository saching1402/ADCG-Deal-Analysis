"""
Prompts for the four analysis stages. The ADCG Buyout and ADCG Venture Growth skills are loaded verbatim
from ``framework/`` so the app scores exactly as the skills do; edit those files to evolve the framework.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

FW = Path(__file__).resolve().parent / 'framework'


@lru_cache(maxsize=None)
def fw(name: str) -> str:
    return (FW / name).read_text(encoding='utf-8')


APP_CONTEXT = """\
You are the analysis engine of **Mindari / Deal Analysis**, the PE team's deal-pipeline web app at Abu Dhabi Capital
Group (ADCG), an institutional LP investing in buyouts, co-investments, secondaries and venture/growth rounds,
primarily in the US and Europe. You apply the ADCG framework below exactly.

Running inside the app changes the mechanics, not the standard:
- Ignore any instruction in the framework to run scripts, write or present files, render PDFs, publish artifacts,
  read or write memory, or query the Contrarian app. The app runs the deterministic scoring engine itself, assembles
  the memo shell and renders the PDF.
- Never mention the Contrarian app, a "Contrarian note", staged gates or kill criteria, or a Prior Deals appendix —
  the deal lead removed them from the memo. Scoring detail lives in the app's Scorecard tab, not in the memo: in the
  memo, never show score calculations — no Valuation Justification Ratio (VJR), Marquee GP Index points, criterion
  scores or weight arithmetic; quote only the final ADCG score and band.
- NO RISK SCORE (non-negotiable): ADCG does not score risk. Never compute, state or mention a numeric risk score
  (0–100, "Derived Risk Score", "(10 − ADCG) × 10") or a risk-register score, even where the skill text describes one.
  Highlight risks qualitatively — ranked, with severity / likelihood labels, evidence, mitigants and diligence questions.
- HOW TO USE THE SOURCES (non-negotiable) — BOTH the deal materials and the web, together, at every step. The deal
  lead's flow: (1) read the materials; (2) SUMMARISE THE OPPORTUNITY from the materials AND the web — what the company
  does, how it makes money, customers, value chain, competition, history, management, the deal; (3) ANALYSE with both —
  the business plan against history and peers, the market, competition, valuation, pros and cons; (4) risks; (5) score;
  (6) memo.
  1. DESCRIBING THE BUSINESS: the information memorandum (IM / CIM / SIM) usually explains a private company best — what
     it sells, to whom, how it delivers, how it earns money, its sites, people and history. Use it as the primary
     description, in plain words, and verify and sharpen it on the web (website, filings, press, customers, competitors).
     For a private, unglamorous business (e.g. facility management, testing, distribution) the reader must finish the
     overview knowing exactly what the company does day to day and why customers pay it. Never let the IM's adjectives or
     marketing claims ("market leader", "recurring", TAM) stand unchallenged — test them.
  2. THE WEB adds what the materials can't: the independent view of the industry and market, competitors beyond the
     IM's list, comparable companies and transactions, precedent deals and how sponsors fared, people checks, news,
     regulation and litigation. Use it to test the materials, not to drown them: no generic background, no padding; keep
     only facts that change the view.
  3. THE NUMBERS ONLY THE COMPANY HAS come from the IM and the other uploads, and replace any public estimate: historical
     actuals (FY-3 … LTM: revenue, growth organic vs M&A, margins, adjusted vs reported EBITDA and every add-back, capex,
     cash conversion, net debt), management's business plan for the next ~5 years (the projections are prepared by the
     management team and are usually well grounded — use them as the base case, then test them against history and
     peers), where the growth comes from (volume, price, margin / cost savings, new business lines, M&A and its spend),
     the management team, the deal terms, the ownership history and the exit assumptions (hold period, exit year,
     exit multiple, returns). Venture: round terms, cap table, bookings / revenue, burn, investor list.
  4. Reconcile the key figures across the IM, model, QoE / financial DD and market study (same metric, period,
     definition). Flag gaps > 2% and definitional differences — the reconciliation is a diligence finding.
  5. Every upload is prepared by the seller or the sponsor to sell the deal to ADCG as co-investor: management
     projections are the base case, but marketing claims (market leadership, "recurring", TAM) need independent proof.
  6. RISKS come from two places and both are mandatory: the risks the IM discloses, AND independently researched risks
     it understates or omits — second- and third-order risks (macro, competition, regulation, labour and input costs,
     technology, customer behaviour, capital structure) and above all the PE track record of this sub-sector / theme
     (precedent sponsor-backed deals, roll-up failures, bankruptcies, write-downs, distressed exits — e.g. dental /
     veterinary / physician-practice roll-ups, car-wash roll-ups). Balanced, not a devil's advocate: rank by
     materiality and say what would mitigate each.
  7. SOURCE TAGS instead of page numbers: tag figures HARD (public / verified), IM (data room), MGMT (unsupported
     management claim) or ESTIMATE (our triangulation). Do not litter the text with page references; cite a page only
     where documents disagree. Name web sources in plain words (e.g. "per Forbes", "JCI release, 11-Nov-26").
- Write for an investment committee: skeptical, decision-oriented, non-promotional, every number source-tagged,
  named comps with specific multiples, severity tags on every risk, and plain-English explanations a generalist can follow.
"""

TRACK_RULE = """\
Track selection (three frameworks): a continuation vehicle or other GP-led secondary (the sponsor sells the asset from
its old fund into a new vehicle it also manages; single- or multi-asset) → **cv** track (ADCG CV). Any other deal with
positive EBITDA + leverage + sponsor control (buyout, co-invest alongside a sponsor, LP-led secondary of a buyout
position) → **buyout** track (ADCG Buyout). A venture- or growth-stage company raising or recently raising a priced
round (Seed → pre-IPO, venture co-invest, startup secondary) → **vg** track (ADCG Venture Growth).
"""


def framework(track: str) -> str:
    """Framework text for a track ('buyout', 'vg', or 'auto' = both, for research) from the editable Framework tab."""
    from . import frameworks
    if track in frameworks.KEYS:
        body = frameworks.prompt_text(track)
    else:  # auto (research): Buyout + VG in full; CV shares Buyout's structure, so only its sections are summarised
        cv = frameworks.get('cv')
        body = (frameworks.prompt_text('buyout') + '\n\n' + frameworks.prompt_text('vg') + f'\n\n# {cv.name.upper()} (for '
                f'continuation vehicles / GP-led secondaries) — same structure as ADCG Buyout; sections: '
                + ', '.join(f'{x["name"]} {x["weight"]:g}' for x in cv.config.get('sections') or []) + '.')
    house = frameworks.house_text(track)
    gps = frameworks.gps_text(track)
    return body + ('\n\n' + gps if gps else '') + ('\n\n' + house if house else '') + '\n\n' + fw('lens.md')


def system_blocks(track: str, extra: str = '') -> list[dict]:
    """System prompt as cacheable blocks (the framework is ~10-15K tokens and is reused by every stage)."""
    blocks = [{'type': 'text', 'text': APP_CONTEXT + '\n' + TRACK_RULE + '\n' + framework(track),
               'cache_control': {'type': 'ephemeral'}}]
    if extra:
        blocks.append({'type': 'text', 'text': extra})
    return blocks


def deal_brief(deal) -> str:
    rows = [f'Company / deal: {deal.name}']
    if deal.website:
        rows.append(f'Website: {deal.website}')
    if deal.sponsor:
        rows.append(f'Sponsor / lead investors (as entered): {deal.sponsor}')
    rows.append(f'Requested track: {deal.get_track_display()}')
    if deal.notes:
        rows.append(f'Deal lead notes / terms:\n{deal.notes}')
    n = deal.files.count() if deal.pk else 0
    rows.append(f'Data room: {n} uploaded file(s) — VDR access.' if n else
                'Data room: NONE — no VDR access. This is a public-information analysis: every company figure is HARD (if '
                'published) or ESTIMATE (triangulated, show how); say so in the Caveats, and turn what only a data room '
                'could answer into the open questions.')
    return '\n'.join(rows)


def materials_block(deal, files) -> dict:
    """All per-file digests as one cacheable user block — CIM first, each labelled with its role."""
    from .roles import LABEL, ORDER
    if not files:
        txt = '<materials>\nNo deal materials were uploaded — rely on public sources and flag every gap.\n</materials>'
    else:
        files = sorted(files, key=lambda f: (ORDER.get(f.doc_role or 'other', 99), f.name))
        has_cim = any(f.doc_role == 'cim' for f in files)
        parts = []
        for f in files:
            cov = f.coverage or {}
            gap = ('' if f.status == 'digested' else
                   ' coverage="PARTIAL — not read: ' + '; '.join(x['label'] for x in cov.get('failed', [])) + '"')
            role = LABEL.get(f.doc_role or 'other', 'Other')
            parts.append(f'<digest file="{f.name}" role="{role}" pages="{f.pages or ""}"{gap}>\n{f.digest}\n</digest>')
        head = (f'<materials count="{len(files)}">\nFact sheets written from each uploaded file (source tag: IM). '
                'All are seller/sponsor-prepared.\n'
                + ('' if has_cim else 'NOTE: no file is marked as the CIM — say so in Caveats and use the most complete '
                   'seller document as the anchor, naming it.\n'))
        txt = head + '\n\n'.join(parts) + '\n</materials>'
    return {'type': 'text', 'text': txt, 'cache_control': {'type': 'ephemeral'}}


# ── stage 1: digest one file ──────────────────────────────────────────────────
DIGEST_SYSTEM = """\
You read one deal document for an investment-committee analysis and write a dense, faithful fact sheet that later
stages will rely on instead of the original. Precision over prose; never invent or round numbers.

Output markdown with these headings (omit empty ones):
## Document — type (CIM, teaser, lender presentation, model, QoE, management accounts, term sheet, IC memo, press…),
   author/preparer, date, period covered, confidentiality.
## Deal terms — EV, equity, price, multiple, leverage/debt package, structure, round size, pre/post-money, leads,
   participants, preferences, timetable, process.
## Company — what it does, history, ownership, management (names, roles, tenure), footprint, headcount.
## Business model & value chain — revenue mechanics, pricing, customers (named, concentration), suppliers, contracts.
## Financials — tables with exact figures, units, currency, periods; reported vs adjusted (list every add-back);
   organic vs M&A growth; margins; cash conversion; capex; working capital; ARR/NRR/burn for venture.
## KPIs & projections — management case vs history; key assumptions.
## Business plan & value creation — the projections table year by year (revenue, EBITDA, margin, capex, cash flow) as
   given; the growth sources (organic volume, price, margin / cost savings, new business lines, M&A pipeline and spend);
   hold period, exit year, exit multiple and returns case if stated.
## Market & competition — claims made, named competitors, market size and source.
## Valuation & comps — any comps or precedents cited.
## Risks & red flags — stated or implied; aggressive adjustments; inconsistencies between pages or with other figures.
## Open questions — what an investor must verify.

Rules: tag the location of every figure — [p. 12], [sheet "P&L"], [slide 7]; label seller/company-prepared figures as
MGMT; keep to ≤ 2,500 words; no preamble.
"""


def digest_user(deal, file_name: str, part: str) -> str:
    return (f'Deal: {deal.name}{f" ({deal.website})" if deal.website else ""}.\n'
            f'Document: "{file_name}"{f" — part {part}" if part else ""}. Write its fact sheet.')


# ── stage 2: research dossier ─────────────────────────────────────────────────
OVERVIEW_TASK = """\
Stage 2 of 7 — SUMMARISE THE OPPORTUNITY from the deal materials AND the web, together. Start from the materials above
(the IM / CIM / SIM usually describes a private company best), then use a FEW targeted web searches to confirm the
company and sharpen the picture (its website, recent news, customers, the competitors it names and any it doesn't).
Where the materials are silent or there are none, the web fills in — tag those figures HARD or ESTIMATE.

Write an OPPORTUNITY SUMMARY in markdown — clear, plain English, the way a good IM's executive summary reads, but
neutral (no seller adjectives):
1. In one paragraph: what the company does, for whom, where, how big, who owns it, and what the deal is.
2. What it sells and how it delivers — the services / products, a typical contract or customer engagement, sites,
   headcount, how the work is done day to day. A reader who has never seen this industry must understand it.
3. How it makes money — revenue model (contracted / recurring / project / transactional), pricing, contract length,
   revenue mix by service, customer type and geography; key numbers (revenue, EBITDA, margins, growth) with tags.
4. Customers and end markets — named customers where known, concentration, why they buy and what keeps them.
5. Value chain — who supplies it, who it competes with for the customer, who captures the margin; where the company sits.
6. Competition — the IM's peer list AND the competitors found on the web, with a line on how each differs.
7. History, ownership and management — founding, owners and transactions, the team (prior roles, tenure), and the
   sponsor: who they are, fund and strategy, where they invest, their track record (CV: also the lead secondaries
   investor). Take these from the materials first, then check them on the web.
8. The deal / round and management's plan in headline (what they say happens next and why) — detail comes later.
9. What the materials claim that needs testing — the 5–8 statements the analysis must check.
Tag figures IM / HARD / MGMT / ESTIMATE. Keep it to what a reader needs to understand the opportunity — about 2–3 pages.

Finish with ONE fenced ```json block:
{"track": "buyout" | "cv" | "vg", "track_reason": "...", "company_name": "...", "website": "...", "sector": "...",
 "sub_sector": "...", "sources": ["https://…", …]}
"""

RESEARCH_TASK = """\
Stage 3 of 7 — RESEARCH & ANALYSIS, using the materials AND the web together. The OPPORTUNITY SUMMARY above already
describes the company — do NOT re-describe it. Research what the materials can't tell you and test what they claim,
with targeted web searches (primary sources first; search each competitor, comparable and executive separately;
filings, company and partner releases, regulators, rated-debt reports, credible trade press; venture: funding
databases and investor announcements). Use the materials' numbers wherever they exist; triangulate an ESTIMATE only
where neither source has it, and show how.

Write a RESEARCH & ANALYSIS section in markdown, organised like the memo blueprint for this track, with facts, numbers,
names and sources (URLs inline):
1. Industry / technology from first principles — the binding constraint, why now, an analogy, a worked
   unit-economics example with numbers (the company's own where the materials give them).
2. Market — size in physical units × $/unit, growth, drivers. CONTEST the materials' industry story with reliable
   external sources (independent market reports, listed peers, industry bodies): is the growth real, how intense is
   competition, how many sponsors chase these assets and at what multiples (valuation hype), what structural threats
   exist. Neutral: say where the materials hold up and where they don't.
3. Competitive landscape — the IM's peers plus those it omits; for each: latest revenue, locations, customer base,
   ownership, latest valuation, how it competes (use any market study in the data room plus the web); who else runs
   the same playbook; the company's real position and moat.
4. Customers and suppliers — what the web says about the named customers / partners and their leverage.
5. People checks — founders / executives / board: prior roles, exits, controversies.
6. Ownership / funding history as reported publicly (buyout: each owner, date, EV, multiple; venture: every round).
7. Valuation — named trading AND transaction comps with specific multiples; the deal's multiple against them;
   first view on fair value and exit maths.
8. Testing the claims — for each "claim to test" in the summary: what the evidence says.
9. Regulation and litigation.
Tag every figure IM / HARD / MGMT / ESTIMATE; show ranges where sources diverge and say which you believe. Be concise —
facts that change the view, not background.

Finish with ONE fenced ```json block: {"sources": ["https://…", …]}
"""

# ── stage 2b: independent risk review ─────────────────────────────────────────
RISK_TASK = """\
Stage 4 of 7 — RISK REVIEW. Find what could go wrong, independently of what the materials choose to disclose: use web
search (filings, credit-rating reports, court records, trade press, regulators, sector studies, news on comparable
companies and deals) on top of the opportunity summary and research above. Whether the materials disclose each risk is
judged at the next stage.

Research, searching each item separately:
1. PE track record in this exact sub-sector / theme: precedent sponsor-backed deals (names, sponsors, years, entry
   multiples where known) and how they ended — bankruptcies, restructurings, write-downs, failed exits, successful exits.
   Is this a known "graveyard" theme (e.g. dental / vet / physician-practice roll-ups, car-wash roll-ups)? Why did
   failures fail (leverage, labour, reimbursement, integration, multiple arbitrage)? Does this company share those features?
2. The sponsor's / lead investors' own record in the sector and with this asset (including prior funds / CVs).
3. Second- and third-order risks: macro and rates (refinancing, consumer spend), competition (new entrants, pricing,
   PE-backed rivals bidding up bolt-ons), regulation and reimbursement, labour availability and wage inflation, input
   costs, technology / AI disruption, customer concentration and behaviour, supplier power, ESG / litigation, FX.
4. Capital-structure and exit risks: refinancing wall, covenant headroom, multiple compression, buyer universe.
5. For venture: hype-cycle timing vs public anchors, financing / dilution, key-person and governance.

Write the review in markdown: a short "Bottom line" (3 bullets), then the material risks ranked by severity × likelihood
and the sub-sector track-record table. Cite every external claim with its URL. Be balanced: say when a feared risk does
NOT apply here and why, and give the mitigant or diligence question for each risk.

Finish with ONE fenced ```json block:
{"risks": [{"risk": "≤ 90 chars", "category": "Sector track record|Macro|Competition|Regulation|Labour|Input costs|Technology|Customers|Capital structure|Exit|Sponsor|Governance|Other",
            "order": "1st|2nd|3rd", "severity": "HIGH|MEDIUM|LOW", "likelihood": "HIGH|MEDIUM|LOW",
            "why": "≤ 220 chars, with the evidence", "mitigant": "≤ 140 chars", "diligence": "the question to ask, ≤ 140 chars",
            "source": "url"}],
 "track_record": [{"deal": "...", "sponsor": "...", "years": "...", "outcome": "Bankruptcy|Restructuring|Write-down|Loss|Flat|Good exit|Ongoing", "lesson": "≤ 140 chars", "source": "url"}],
 "theme_verdict": "≤ 300 chars: is this a sub-sector where sponsors have tended to lose money, and does this company avoid the failure pattern?"}
Rank risks most material first; 8–15 risks.
"""

NO_DATAROOM_TASK = """\
Stage 5 of 7 — NO DATA ROOM. There is no VDR access for this deal, so there is nothing to integrate. Finalise the
headline facts from the independent research (public figures tagged HARD, otherwise "Est."), and write a short
"No data-room access" note in markdown: the 5–8 numbers or documents a data room would have to provide (e.g. audited
revenue and margin, cap table and preferences, backlog, management plan) and which conclusions they could change.
Do not search.

HEADLINE FACTS — exactly these keys, in this order. Buyout: "Transaction", "Enterprise value", "EV / EBITDA",
"Adj. EBITDA", "Net leverage", "Sponsor". Venture/Growth: "Round", "Post-money", "Raise", "EV / Revenue",
"Lead investor", "Last round". "v" is ONE short value ≤ 22 characters (no ranges); "src" a short tag ("Press",
"Company release", "Filing", "Est."); "note" optional ≤ 120 characters; unknown → "n/d".

Finish with ONE fenced ```json block:
{"sponsor": "...", "one_liner": "≤ 25 words: what it is + the key tension", "ev": "...", "multiple": "...",
 "leverage": "... or n/a", "facts": [{"k": "...", "v": "...", "src": "...", "note": "..."}, … 6 items]}
"""

# ── stage 2c: bring in the data room ─────────────────────────────────────────
INTEGRATE_TASK = """\
Stage 5 of 7 — BUSINESS PLAN, ACTUALS & RECONCILIATION. Above are the fact sheets of every uploaded file, the
opportunity summary and research & analysis (built from the materials and the web together) and the risk review.
Now go deep on the numbers only the company has, test them against the research and peers, and reconcile.

Write a BUSINESS PLAN & RECONCILIATION section in markdown:
1. Identity check — one line: the materials and the web describe the same company (or what differs).
2. Numbers that replace estimates — a table: Metric · Independent estimate · Data room figure (IM / model / QoE) ·
   Comment. Every ESTIMATE in the dossier that the materials answer.
3. Historical actuals (FY-3 … LTM) — REPLICATED EXACTLY from the materials (the source of truth; copy the figures, do
   not round differently or recompute): revenue, growth (organic vs M&A), gross profit and gross margin, adj. EBITDA and
   margin, reported EBITDA, add-backs, capex, free cash flow and cash conversion, net debt and leverage; note the
   document and page / tab. Venture: revenue / ARR / bookings / burn / cash as disclosed.
4. Management business plan (FY+1 … exit) year by year from the model / IM; hold period, exit year, exit multiple,
   returns case; any earlier business plan in the materials and how it compares. Then HISTORY vs PLAN: historical
   CAGR and margins vs planned; the bridge from today's EBITDA to exit EBITDA by driver (organic volume, price, margin /
   cost savings, new business lines, M&A and its spend); for each driver a neutral read from the company's record and
   the market (e.g. planned acquired EBITDA vs what was bought historically; exposure to an end market and its real
   prospects). Then our case — which assumptions we would change and the effect (ESTIMATE).
5. Transaction facts REPLICATED from the materials: structure (buyout / co-invest / single- or multi-asset CV /
   minority), EV, LTM EBITDA adjusted and reported, multiples, net leverage, debt package (instruments, quantum, pricing,
   maturity, covenants), interest coverage, equity cheque, CV size and unfunded commitment, ADCG ticket, sources & uses
   table, fees / carry, governance, rollover. Venture: round terms in full. Plus management and ownership details the
   research did not have.
6. Where the materials and the independent research DISAGREE (market size, growth, competitive position, customer
   claims, margins) — say which you believe and why.
7. Reconciliation across the uploads (IM vs model vs QoE vs market study: same metric, period, definition; gaps > 2%).
8. Risks the materials disclose that the independent review did not cover, and for each independent risk whether the
   materials disclose it, understate it, or omit it.
Use at most a few web searches, only to check a specific claim in the materials. Tag figures IM / HARD / MGMT /
ESTIMATE; no page references except where documents disagree.

HEADLINE FACTS (shown as a strip at the top of the deal page — must be clean):
- Exactly these keys, in this order. Buyout: "Transaction", "Enterprise value", "EV / EBITDA", "Adj. EBITDA",
  "Net leverage", "Sponsor". Venture/Growth: "Round", "Post-money", "Raise", "EV / Revenue", "Lead investor", "Last round".
- "v" is ONE short value, ≤ 22 characters: a single number with its unit or a short label — e.g. "$531m", "12.7×",
  "$41.8m (LTM Dec-25)", "5.4×", "Single-asset CV", "Halifax Group". Never ranges, alternatives or explanations.
  EV / EBITDA is EV ÷ the IM's headline (adjusted) LTM EBITDA — one number.
- "src": a short source tag — "IM", "IM FY25A", "Model", "Company release", "Press", "Est.". No page numbers.
- "note": optional ≤ 120 characters for the nuance (e.g. "15.2× on reported EBITDA; adjustments = 16% of Adj.").
- Unknown → "v": "n/d".

Finish with ONE fenced ```json block:
{"sponsor": "sponsor or lead investors, short", "one_liner": "≤ 25 words: what it is + the key tension",
 "ev": "short EV or post-money, e.g. $531m", "multiple": "one headline multiple, e.g. 12.7×", "leverage": "e.g. 5.4× or n/a",
 "facts": [{"k": "...", "v": "...", "src": "...", "note": "..."}, … 6 items per the rules above],
 "risk_disclosure": [{"risk": "exact text of an independent risk", "in_cim": "yes|understated|no"}],
 "materials_risks": [{"risk": "≤ 90 chars", "category": "...", "order": "1st", "in_cim": "yes", "severity": "HIGH|MEDIUM|LOW",
                      "likelihood": "HIGH|MEDIUM|LOW", "why": "≤ 220 chars", "mitigant": "≤ 140 chars", "diligence": "≤ 140 chars", "source": "IM"}],
 "reconciliation": [{"metric": "...", "cim": "...", "other": "value [file]", "gap": "...", "comment": "..."}],
 "sources": ["https://…"]}
"""

TRACK_SHORT = {'buyout': 'Buyout', 'cv': 'CV', 'vg': 'VG'}
TRACK_NAME = {'buyout': 'Buyout', 'cv': 'CV (continuation vehicle)', 'vg': 'Venture / Growth'}


def base(track: str) -> str:
    """Template family for a track: CV deals use the buyout memo / scoring templates."""
    return 'vg' if track == 'vg' else 'buyout'


# ── stage 3: scorecard JSON ──────────────────────────────────────────────────
SCORE_TASK = {
    'buyout': """\
Stage 5 — SCORE on the ADCG Buyout framework exactly as defined in the SCORECARD DEFINITION block (no new
searching). Identify sector → sub-sector, reuse or build the sector-library block, set the per-deal section weights
(sum 100; start from the defaults and apply the weighting rules) and score every criterion 1–10 with a one-line
rationale; `null` for undisclosed (keep each section's criteria count). Calibrate against the anchors and the prior deals
listed below — do not drift more than ~0.3 from a close analogue without a reason.

Return ONLY one fenced ```json block in the OUTPUT JSON SCHEMA, plus these keys:
"weights_rationale": [{"section": "...", "default": n, "deal": n, "why": "..."}],
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5).
""",
    'cv': """\
Stage 5 — SCORE on the ADCG CV framework exactly as defined in the SCORECARD DEFINITION block (no new searching). This is
a continuation vehicle / GP-led secondary: score the underlying asset(s) and the transaction (price vs NAV and
comps, GP alignment — rollover, carry crystallisation, fairness opinion, price-setting process). Trophy Asset asks whether this is
the sponsor's STAR asset — one of the top performers in its fund, kept by choice to compound — or an asset put into a
CV because no sponsor or strategic would pay a good price: look for its rank and returns within the source fund, any
earlier sale or IPO attempt, the GP's own fresh money and rolled carry, and the existing-LP roll rate. Identify sector →
sub-sector, reuse or build the sector-library block, set the per-deal section weights (sum 100; start from the defaults
and apply the weighting rules) and score every criterion 1–10 with a one-line rationale; `null` for undisclosed (keep
each section's criteria count). Calibrate against the anchors and the prior deals listed below — do not drift more
than ~0.3 from a close analogue without a reason.

Return ONLY one fenced ```json block in the OUTPUT JSON SCHEMA, plus these keys:
"weights_rationale": [{"section": "...", "default": n, "deal": n, "why": "..."}],
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5).
""",
    'vg': """\
Stage 5 — SCORE on the ADCG Venture Growth framework exactly as defined in the SCORECARD DEFINITION block (no new
searching): its sections, fixed weights and criteria in order. Name the theme in sub_sector. For the auto "marquee"
criterion give {"name": ..., "auto": "marquee", "rationale": "…"} and list every investor with its tier in "investors"
— each {"name", "domain" (the firm's own website, e.g. foundersfund.com), "tier", "role": "lead|part"} — the engine
matches each FIRM on its website (not on words in its name) and computes the index. Give "valuation_evolution" for the VJR: {"val_from", "val_to", "metric": "ARR", "metric_from", "metric_to",
"gm_from", "gm_to" (gross margins at each round, % — so the VJR is measured on gross profit), "months", "milestone"
(the major technology breakthrough, if any, that a step-up rests on)}. Theme: judge whether this is a theme ADCG must not
miss — early signals before it is crowded, a real technology step-change, and fast revenue / TAM growth across the theme
over the last 2–3 years. Valuation: judge the multiple against margins and moat (EV / gross profit, not only EV /
revenue) and check that every round's step-up was earned by ARR growth or a major milestone. Do not score a risk register (ADCG does not score risk). Calibrate against the anchors and the prior deals listed below.

Return ONLY one fenced ```json block in the OUTPUT JSON SCHEMA, plus these keys:
"weights_rationale": [{"section": "...", "default": n, "deal": n, "why": "..."}],
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5).
""",
}

# ── stage 4: memo ─────────────────────────────────────────────────────────────
MEMO_CSS_NOTE = ('\n\n# MEMO BLUEPRINT — follow this structure and these components exactly\n\n' + fw('memo_blueprint.md')
                 + '\n\n# MEMO CSS-CLASS CHEATSHEET + MANDATORY PROS/CONS DIMENSIONS (ignore this file\'s section order)\n\n'
                 + fw('memo_structure.md'))

MEMO_RULES = """\
Rules: use the materials and the web together, with the lead source per topic set out in the MEMO BLUEPRINT
("WHERE EACH PART COMES FROM"): describe the company, its management, ownership and sponsor from the materials first
(verified on the web, with anything material the web adds); contest the materials' industry claims with reliable
external sources; combine both for the business model, value chain and competition; REPLICATE the transaction facts,
sources & uses, debt terms and historical financials exactly from the materials (they are the source of truth for
actuals); present the business plan alongside the history and test each driver neutrally. Section titles exactly as
written below, even where the framework guidance names them differently (it is "Industry primer", never "technology
primer"). Write it as a story that flows — a short lead per section, connected paragraphs, the key point in bold, easy
on the eye, never mechanical — with real depth: numbers, names, worked examples and our own judgement. Follow the MEMO BLUEPRINT for the {track_name} track — every named table, diagram and callout for these sections,
with real names and numbers from the dossier, the risk review and the materials. Write like a deep-research report:
explain from first principles, give analogies and worked examples, and say what each fact means for the decision.
Source-tag figures with the small .src pills (HARD / IM / MGMT / ESTIMATE); a document / page reference goes inside the
pill ("IM p.7") or in <span class="ref">…</span>, never as bracketed text in the sentence. Use the
scores and numbers given below exactly; never recompute or contradict the engine. HTML fragment only (no
<html>/<head>/<body>, no <style>, no markdown) inside ONE ```html fenced block.
"""

PC_REC = """
  PROS &amp; CONS — the heart of the memo. Two stacked numbered lists, never side by side: <h3>Pros</h3>
  <ol class="pc-list pros"> with 7–10 items, THEN <h3>Cons</h3><ol class="pc-list cons"> with 7–10 items. Each <li>: a
  bold one-line claim, then 2–4 sentences of evidence (numbers, named customers / competitors / comparable deals, source
  tags), then "Why it matters:" — the effect on returns, downside or exit — then the conviction (pros) or severity
  (cons) tag. Pros by conviction, cons by severity. Then <h3>Net assessment</h3>: one paragraph weighing the strongest
  pro against the strongest con.
  KEY RISKS — NOT a table. A two-sentence bottom line, then <ol class="risk-list"> of 6–10 numbered paragraphs, most
  material first; each starts with the risk area in bold (<b>Valuation —</b>, <b>Technology —</b>, <b>Competition —</b>,
  <b>Financing &amp; dilution —</b>, <b>Regulation —</b> …) followed by 2–4 plain sentences: what could go wrong and why,
  with evidence; how likely and how severe, in words; whether the materials disclose it; what would mitigate it or what
  to ask. Close with one short paragraph on how sponsors have fared in this theme (named precedents). Up to a page.
  RECOMMENDATION — balanced and neutral, about HALF A PAGE, not a rigid call: one bold line with the leaning (e.g. "On
  balance we lean towards investing, provided…" or "Hard to support at this price unless…") and the ticket / price
  stance if known; "Why" — 2–3 plain bullets weighing both sides; "What would change our view" — at most 3 bullets;
  "Next step" — one sentence; then one or two lines on what we don't know yet. No gates, kill criteria, Contrarian note
  or Prior Deals appendix.
  LENGTH — the whole memo ~20–28 pages of real substance. Tables where readers compare numbers across rows; otherwise
  connected paragraphs that flow as a story, with the key point in bold.
"""

MEMO_TASKS = {
    'vg': [
        ('Writing memo — company, founders, funding history, theme primer, value chain',
         """Stage 4a — WRITE THE MEMO, PART 1 of 3: sections 1–3.
  <h2>1 · Company overview</h2> (incl. Founders &amp; management, the GAP callout, Funding &amp; valuation history)
  <h2>2 · Industry primer</h2> (first principles, analogy, flow diagram, product ladder, worked example, how
  competitors are built differently; the materials' market claims contested with reliable external sources — crowding,
  valuation hype, real growth)
  <h2>3 · Business model, value chain &amp; competitive landscape</h2> (value-chain strip, named customers, suppliers,
  competitor table with latest marks, why strategics back the field, market sizing in the right units,
  first-principles test of the multiple)"""),
        ('Writing memo — latest round, key findings, financials, valuation evolution',
         """Stage 4b — WRITE THE MEMO, PART 2 of 3: sections 4–5, continuing Part 1 below.
  <h2>4 · Latest fund raise &amp; key findings</h2> (.kf key-facts grid replicated from the materials; only the 3–6
  findings that matter)
  <h2>5 · Financials, valuation &amp; business plan</h2> (current valuation first; historical operating numbers replicated
  exactly from the materials; the plan and history vs plan, tested neutrally; valuation evolution — SVG chart OR a short
  table; comparables; exit maths; fair value) per the MEMO BLUEPRINT.
  Stop after section 5 — the app adds section 6 (the score bars) itself."""),
        ('Writing memo — verdict, pros & cons, recommendation, risk review',
         """Stage 4c — WRITE THE MEMO, PART 3 of 3, consistent with Parts 1–2 below and the computed scores.
  <h2>7 · Verdict</h2> (.tldr), <h2>8 · Pros &amp; Cons (IC voice)</h2> (see PROS &amp; CONS below),
  <h2>9 · Recommendation</h2> (see RECOMMENDATION below), then <h2>10 · Key risks</h2> (see KEY RISKS below).
""" + PC_REC),
    ],
    'buyout': [
        ('Writing memo — company, management, ownership history, industry primer, value chain',
         """Stage 4a — WRITE THE MEMO, PART 1 of 3: sections 1–3.
  <h2>1 · Company overview</h2> (summarised from the materials, verified on the web: service lines, customers,
  footprint, history; Management table, GAP callout; The sponsor — who they are, where they invest, track record;
  Ownership &amp; transaction history with the multiple each owner paid)
  <h2>2 · Industry primer</h2> (first principles, analogy, flow diagram, service / product ladder, worked
  unit-economics example; "Is this a good industry to own?" — the materials' market claims contested with reliable
  external sources: real growth, competition, sponsor crowding and valuation hype, structural threats)
  <h2>3 · Business model, value chain &amp; competitive landscape</h2> (value-chain strip, named customers, suppliers,
  competitor table with latest revenues / locations / customers from the web and any market study in the data room,
  market sizing anchored on the materials and cross-checked externally, who else runs this playbook)"""),
        ('Writing memo — transaction, key findings, financials, business plan, valuation',
         """Stage 4b — WRITE THE MEMO, PART 2 of 3: sections 4–5, continuing Part 1 below.
  <h2>4 · The transaction &amp; key findings</h2> (.kf key-facts grid — structure, EV, EBITDA adjusted and reported,
  multiple, net leverage, equity, CV size and unfunded commitment, ADCG ticket; debt package with pricing, maturity,
  covenants and interest coverage; sources &amp; uses replicated from the materials as the .su visual; then only the
  3–6 findings that matter, leading with where the sponsor may be overestimating)
  <h2>5 · Financials, valuation &amp; business plan</h2> (historical financials replicated EXACTLY from the materials —
  revenue, growth organic vs M&amp;A, gross profit and margin, adjusted and reported EBITDA, capex, cash conversion, net
  debt and leverage; the business plan alongside — year by year to exit, hold period, exit multiple, returns; history
  vs plan growth and margins; how the plan gets met — bridge by driver from the materials, then a neutral
  market-evidence read on each driver; our case (ESTIMATE); reconciliation; comps; returns &amp; exit maths; fair value)
  per the MEMO BLUEPRINT.
  Stop after section 5 — the app adds section 6 (the score bars) itself."""),
        ('Writing memo — verdict, risk review, pros & cons, recommendation',
         """Stage 4c — WRITE THE MEMO, PART 3 of 3, consistent with Parts 1–2 below and the computed scores.
  <h2>7 · Verdict</h2> (.tldr: ADCG score/band and stance; the business and where it sits; the one thing that matters
  most; the action), <h2>8 · Key risks — what the materials don't tell you</h2> (see KEY RISKS below; say for each
  whether the IM discloses, understates or omits it), <h2>9 · Pros &amp; Cons (IC voice)</h2> (see PROS &amp; CONS below; cons include the top
  independent risks), <h2>10 · Recommendation</h2> (see RECOMMENDATION below).
""" + PC_REC),
    ],
}


def ledger_text(rows) -> str:
    if not rows:
        return 'Prior deals in the pipeline: none yet.'
    head = '| Company | Track | Sponsor / round | EV | Multiple | Lev | ADCG | One-liner |\n|---|---|---|---|---|---|---|---|'
    body = '\n'.join(
        f'| {d.name} | {TRACK_SHORT.get(d.track_resolved, "Buyout")} | {d.sponsor[:80]} | {d.ev[:40]} | {d.multiple[:40]} | '
        f'{d.leverage[:20]} | {d.adcg_score if d.adcg_score is not None else "n/d"} | '
        f'{d.one_liner[:160]} |' for d in rows)
    return ('Prior deals already scored in the pipeline (calibration set — Buyout and VG scores are not comparable '
            'with each other):\n' + head + '\n' + body)


# ── revise: apply the deal lead's review comments (no new research) ──────────
STANCE_LABEL = {'agree': 'Agrees', 'disagree': 'Disagrees', 'context': 'Comment', 'question': 'Asks',
                'change': 'Requests a change'}


def comments_block(comments) -> str:
    rows = []
    for c in comments:
        who = (c.author.full_name or c.author.username) if c.author else 'deal lead'
        rows.append(f'<comment id="{c.pk}" stance="{c.stance}" by="{who}" section="{c.section}">\n'
                    + (f'<on_passage>{c.quote[:1200]}</on_passage>\n' if c.quote else '')
                    + f'{STANCE_LABEL.get(c.stance, c.stance)}: {c.text}\n</comment>')
    return ('<deal_lead_comments>\nThe deal lead read the memo and left these comments — on a highlighted passage (<on_passage>) or on the memo '
            'overall. Work out from each one whether they agree, disagree, add information, ask a question or want a change. '
            'They know the deal, the sponsor and the materials first-hand: treat what they state as evidence (tag it "DEAL LEAD"), but say plainly if a comment '
            'conflicts with hard evidence and keep both views.\n' + '\n\n'.join(rows) + '\n</deal_lead_comments>')


REVISE_SCORE_TASK = """\
REVISE THE SCORES (no new research). Above are the current scorecard JSON, the research, and the deal lead's comments.
Change a criterion's score or rationale ONLY where a comment gives a reason to; leave everything else exactly as it is.
Keep the same schema, sections, criteria names and weights (the framework weights are fixed). No risk score.
Keep "house_fit" (the ADCG preferences ratings) — change a fit only where a comment gives a reason to.

Return ONE fenced ```json block: the full updated scorecard JSON, plus a key
"changes": [{"criterion": "...", "from": n, "to": n, "why": "≤ 160 chars", "comment_ids": [id, …]}]  ([] if none).
"""

REVISE_MEMO_TASK = """\
REVISE THE MEMO (no new research). Above are the current memo (HTML, the scorecard replaced by a placeholder), the
research, the score changes just made, and the deal lead's comments. Rewrite ONLY the sections the comments (or the
score changes) affect — e.g. a disagreement with a finding, new information about management or terms, a question to
answer, a requested change. Integrate each point properly: correct the argument, the tables and the numbers, mark new
facts from the deal lead with <span class="src mgmt">DEAL LEAD</span>, and keep the house style and components. If
scores changed, update the Verdict and the weights table so every number matches the new scores.

Output each revised section as its own ```html fenced block that STARTS with that section's original <h2> heading,
exactly as it appears in the memo (same number and words), followed by the complete new content of that section.
Do not output unchanged sections, the scorecard or the Prior Deals appendix. No risk score.

Then ONE fenced ```json block:
{"responses": [{"id": comment id, "response": "≤ 240 chars: what changed in the memo, or why nothing changed"}],
 "summary": "≤ 300 chars: what this revision changed overall"}
"""
