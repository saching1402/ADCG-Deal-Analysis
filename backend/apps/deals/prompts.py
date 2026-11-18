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
  the deal lead removed them from the memo. In the memo, never show score calculations — no Valuation Justification
  Ratio (VJR) or Marquee GP Index arithmetic, no weight arithmetic. Section and criterion scores appear only in the
  memo's Part III (ADCG Deal Scoring), exactly as computed by the engine, each with its plain-English reason.
- NO RISK SCORE (non-negotiable): ADCG does not score risk. Never compute, state or mention a numeric risk score
  (0–100, "Derived Risk Score", "(10 − ADCG) × 10") or a risk-register score, even where the skill text describes one.
  Highlight risks qualitatively — ranked, with severity / likelihood labels, evidence, mitigants and diligence questions.
- HOW TO USE THE SOURCES (non-negotiable) — BOTH the deal materials and the web, together, at every step. The deal
  lead's flow: (1) read the materials; (2) SUMMARISE THE OPPORTUNITY from the materials — the deal (all key terms for its
  type), the company and the industry; (3) the INDEPENDENT MARKET ASSESSMENT on the web — contest the materials' industry
  story, competition and exitability; (4) risks; (5) the BUSINESS PLAN — history and projections together, the value-
  creation levers, the sponsor's cases and our independent review with sensitivities; (6) score; (7) memo.
  THE SPONSOR / GP MATERIALS ARE THE FACTUAL BASE: the IM, market study, model, QoE and other reports are reviewed by
  many sophisticated LPs (pension funds, endowments, sovereign funds) and sponsors cannot misstate the numbers, so treat
  the figures and terms as reasonably true and summarise them faithfully. What you contest is the narrative — industry
  growth, market size, competitive position, "market leader" claims, and anything the manager may have oversold.
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
  5. Every upload is prepared by the seller or the sponsor to sell the deal: the numbers, terms and projections are
     the base case (the projections are management's and the sponsor's cases, shown as presented), but marketing
     claims (market leadership, "recurring", TAM, the industry growth rate) need independent proof. Our own view is
     always labelled "ADCG independent review" and tagged ESTIMATE.
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
DEAL_TERMS = """\
KEY TERMS BY DEAL TYPE — replicate every term the materials give; write "not disclosed" for the ones they don't and say
which of those matter:
- BUYOUT / CO-INVEST: structure (control buyout, co-invest alongside the sponsor, minority); seller and why now; EV;
  LTM EBITDA adjusted and reported; EV/EBITDA on both; net leverage; debt package (instruments, quantum, pricing,
  maturity, covenants); interest cover; equity cheque and the sponsor's own commitment; management rollover and MIP;
  ADCG ticket; co-invest FEES AND CARRY (management fee, carry, hurdle — or no fee / no carry); governance and
  information rights; timetable.
- CONTINUATION VEHICLE / GP-LED SECONDARY: single- or multi-asset; the asset(s) and the selling fund (vintage, remaining
  life); CV size, fresh money and unfunded commitment; price vs NAV (premium / discount) and the reference date; lead
  secondaries investor and syndicate; LP election (roll / sell / status quo) and expected roll rate; GP commitment and
  carry rollover or crystallisation; CV ECONOMICS — management fee and its basis, carry, hurdle, tiered carry, fee
  offsets; CV term and extensions; fairness opinion, LPAC approval; the underlying deal terms (EV, multiple, leverage,
  debt); ADCG ticket.
- VENTURE / GROWTH ROUND: round and date; instrument (priced preferred, SAFE, convertible note); pre- and post-money;
  raise; primary / secondary split; VALUATION CAP and discount (SAFEs / notes); LIQUIDATION PREFERENCE (multiple,
  participating or not, seniority / stacking); anti-dilution; pro-rata; board seats and protective provisions; option
  pool; leads and new / returning investors; use of proceeds; ADCG ticket and SPV fee / carry if any.
"""

OVERVIEW_TASK = """\
Stage 2 of 7 — SUMMARISE THE OPPORTUNITY, mostly from the deal materials. The sponsor / GP materials (IM, market study,
model, other reports) are the factual base — summarise them faithfully. Use a FEW targeted web searches only to confirm
the company and sharpen the picture (its website, recent news, the competitors it names and any it doesn't). Where the
materials are silent or there are none, the web fills in — tag those figures HARD or ESTIMATE.

Decide the deal type first (buyout / co-invest, continuation vehicle, or venture / growth round) and write an
OPPORTUNITY SUMMARY in markdown — clear, plain English, neutral (no seller adjectives) — in three parts:

## A. Deal summary
One paragraph on what we are being asked to invest in, at what price, alongside whom and why now. Then every key term
for the deal type (see KEY TERMS BY DEAL TYPE below) as a compact table Term · Value · Source, sources & uses where given,
and the sponsor's headline returns case (exit year, multiple, MOIC / IRR).
## B. Company summary
1. What it sells and how it delivers — services / products, a typical contract or customer engagement, sites,
   headcount, how the work is done day to day. A reader who has never seen this industry must understand it.
2. How it makes money — revenue model, pricing, contract length, mix by service / customer / geography; key numbers
   (revenue, EBITDA, margins, growth) with tags.
3. Customers and end markets — named customers, concentration, why they buy and what keeps them.
4. Value chain and competition — where it sits; the IM's peer list AND competitors found on the web.
5. History, ownership and management — founding, owners and transactions, the team, and the sponsor (who they are,
   fund, strategy, where they invest, track record; CV: also the lead secondaries investor; VG: founders and leads).
6. The plan in headline — what management and the sponsor say happens next and the value-creation levers.
## C. Industry primer (the materials' view)
How the industry works, its size, growth, drivers and structure as the materials present them, with the market study's
figures where there is one. Then the 5–8 industry and company claims the independent market assessment must test
(growth rate, market size, fragmentation, share, margin trend, tailwinds).
Tag figures IM / HARD / MGMT / ESTIMATE. About 3–4 pages.

{deal_terms}

Finish with ONE fenced ```json block:
{"track": "buyout" | "cv" | "vg", "track_reason": "...", "company_name": "...", "website": "...", "sector": "...",
 "sub_sector": "...", "sources": ["https://…", …]}
"""

RESEARCH_TASK = """\
Stage 3 of 7 — RESEARCH & INDEPENDENT MARKET ASSESSMENT, the web against the materials. The OPPORTUNITY SUMMARY above
already describes the deal, the company and the materials' view of the industry — do NOT re-describe them. The numbers
in the materials are reasonably true; the STORY may be oversold. Research what the materials can't tell you and test
what they claim,
with targeted web searches (primary sources first; search each competitor, comparable and executive separately;
filings, company and partner releases, regulators, rated-debt reports, credible trade press; venture: funding
databases and investor announcements). Use the materials' numbers wherever they exist; triangulate an ESTIMATE only
where neither source has it, and show how.

Write a RESEARCH & ANALYSIS section in markdown, organised like the memo blueprint for this track, with facts, numbers,
names and sources (URLs inline):
1. Industry / technology from first principles — the binding constraint, why now, an analogy, a worked
   unit-economics example with numbers (the company's own where the materials give them).
2. INDEPENDENT MARKET ASSESSMENT — size in physical units × $/unit, growth, drivers. CONTEST the materials' industry
   story with reliable external sources (independent market reports, listed peers' disclosures, industry bodies,
   regulators, credible press): a table Claim · Materials say · Independent evidence (with source) · Verdict
   (Confirmed / Partly supported / Not supported) for every claim to test. Then: is the growth real, how intense is
   competition, how many sponsors chase these assets and at what multiples (valuation hype), and the RISKS TO THE
   INDUSTRY (structural threats, regulation, technology / AI, cyclicality). Neutral: say plainly where the manager has
   oversold it and where the materials hold up.
3. Competitive landscape — the IM's peers plus those it omits; for each: latest revenue, locations, customer base,
   ownership, latest valuation, how it competes (use any market study in the data room plus the web); who else runs
   the same playbook; the company's real position and moat.
4. Customers and suppliers — what the web says about the named customers / partners and their leverage.
5. People checks — founders / executives / board: prior roles, exits, controversies.
6. Ownership / funding history as reported publicly (buyout: each owner, date, EV, multiple; venture: every round).
7. Valuation — named trading AND transaction comps with specific multiples; the deal's multiple against them;
   first view on fair value.
7b. Exitability — who buys this at exit (strategics, sponsors, IPO; venture: IPO window, strategic M&A, secondaries),
   recent exits in the sub-sector with their multiples, and the buyer universe at the exit size the plan assumes.
8. Testing the claims — for each "claim to test" in the summary: what the evidence says.
9. Regulation and litigation.
Tag every figure IM / HARD / MGMT / ESTIMATE; show ranges where sources diverge and say which you believe. Be concise —
facts that change the view, not background.

Finish with ONE fenced ```json block: {"sources": ["https://…", …]}
"""

# ── stage 2b: independent risk review ─────────────────────────────────────────
RISK_TASK = """\
Stage 4 of 7 — RISK REVIEW (deal lead, 18-Nov-26): ONE complete review of every risk that applies to the deal, all at
the same time — the risks the sponsor flags are INCLUDED alongside everything else, not handled first or separately. The
sponsor will not always have captured every risk, so draw on all of these together and rank purely by materiality:
- the risks the sponsor flags (the IM / sponsor memo risk section, with their mitigants — say whether the framing holds);
- what the other documents reveal even where the IM is silent: the QoE (add-backs, working capital, one-offs), legal /
  tax / commercial DD, the market study, the model (sensitivities, covenant headroom), management presentations;
- an INDEPENDENT SENSE-CHECK ON THE WEB (filings, credit-rating reports, industry reports, regulators, court records, trade
   press, news on comparable companies and deals) — search each item separately:
   1. PE track record in this exact sub-sector / theme: precedent sponsor-backed deals (names, sponsors, years, entry
      multiples) and how they ended — bankruptcies, restructurings, write-downs, failed or good exits. Is this a known
      "graveyard" theme (e.g. dental / vet / physician-practice roll-ups, car-wash roll-ups)? Does this company share the
      failure pattern?
   2. The sponsor's / lead investors' own record in the sector and with this asset (prior funds / CVs).
   3. Regulatory pressure — rules, reimbursement, licensing, antitrust, data / privacy, ESG.
   4. Disruption — technology and AI (e.g. a frontier lab such as Anthropic or OpenAI moving into software or services
      and compressing pricing or seats), new delivery models, new entrants, customer behaviour shifts.
   5. Second- and third-order effects — follow each first-order risk through to what it does to customers, suppliers,
      pricing, labour and the exit.
   6. Capital structure — interest rates and the cost of floating-rate debt, refinancing wall, covenant headroom,
      interest cover under stress, dividend recaps, multiple compression at exit.
   7. Macro and geopolitics — recession and end-market demand, tariffs and trade policy, supply-chain and sanctions
      exposure, FX, energy and input costs, labour availability and wage inflation.
   8. Venture: hype-cycle timing vs public anchors, financing / dilution, key-person and governance.
Write the review in markdown: a short "Bottom line" (3 bullets); then ALL the material risks in ONE list ranked by
severity × likelihood (never grouped by source), each tagged with where it was found (Sponsor-flagged / Materials /
Independent — a risk can be flagged by the sponsor and also found independently) and, for sponsor-flagged risks, whether
the sponsor's framing holds up; then the sub-sector track-record table. Cite every external claim with its URL. Be balanced: say when a feared risk does
NOT apply here and why, and give the mitigant or diligence question for each risk.

Finish with ONE fenced ```json block:
{"risks": [{"risk": "≤ 90 chars", "category": "Sector track record|Macro|Geopolitics & tariffs|Interest rates|Competition|Regulation|Disruption|Labour|Input costs|Technology|Customers|Capital structure|Exit|Sponsor|Governance|Other",
            "flagged_by": "sponsor|materials|independent",
            "order": "1st|2nd|3rd", "severity": "HIGH|MEDIUM|LOW", "likelihood": "HIGH|MEDIUM|LOW",
            "why": "≤ 220 chars, with the evidence", "mitigant": "≤ 140 chars", "diligence": "the question to ask, ≤ 140 chars",
            "source": "url"}],
 "track_record": [{"deal": "...", "sponsor": "...", "years": "...", "outcome": "Bankruptcy|Restructuring|Write-down|Loss|Flat|Good exit|Ongoing", "lesson": "≤ 140 chars", "source": "url"}],
 "theme_verdict": "≤ 300 chars: is this a sub-sector where sponsors have tended to lose money, and does this company avoid the failure pattern?"}
Rank risks most material first, one list; 10–18 risks.
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
4. BUSINESS PLAN — ONE table with the history (item 3) and the sponsor's projections side by side, year by year to the
   exit year, from the model and tied back to the IM (flag any figure where the model and IM differ); rows as the
   sponsor presents them (revenue, growth, gross margin, EBITDA and margin, net profit where given, capex, FCF, net
   debt). Hold period, exit year, exit multiple; any earlier business plan and how it compares. HISTORY vs PLAN:
   historical CAGR and margins vs planned, and whether the step-up is credible.
4a. THE CASES — every case the materials give, side by side (revenue, EBITDA, margin by year to exit; exit multiple):
   the sponsor case, the management case, and any other — e.g. in a CV the lead secondaries investor's case, often a
   haircut to the sponsor's; a lender / QoE / vendor-DD case. Say who prepared each and how and why they differ.
4b. VALUE CREATION PLAN — the levers and their contribution to exit EBITDA (organic volume, price, share-of-wallet /
   cross-sell, new services or geographies, margin and cost programmes, M&A and its spend / multiples): a bridge from
   today's EBITDA to exit EBITDA. For each lever a neutral read from the company's record, the sponsor's record with the
   playbook and the market (e.g. planned acquired EBITDA vs what was bought historically).
   Then rank WHAT DRIVES THE RETURNS in 3–4 points with the share of value creation each explains — organic growth,
   bolt-on M&A, a transformational acquisition, EBITDA-margin improvement, deleveraging, multiple expansion.
4c. RETURNS ACROSS SCENARIOS — one table of every case in 4a (exit year, exit EBITDA, exit multiple, gross and net MOIC /
   IRR, net to ADCG after fees and carry where the terms allow), exactly as presented.
4d. WHAT LOOKS OVERSTATED — 3–6 short, specific sense-checks, numbers on both sides, each with a one-line verdict
   (plausible / stretched / overstated). E.g. "plan grows revenue 15% p.a.; the market grows ~5% — implies sustained
   share gains"; "plan assumes $140m of acquired EBITDA vs $70m bought to date"; "margin rises 400bp vs peers flat";
   "exit multiple above entry with no re-rating evidence". Keep it crisp — only what matters. Then the ADCG INDEPENDENT REVIEW
   (label it so; tag ESTIMATE), building on 4d: the assumptions we would change and why, our case, and SENSITIVITY TABLES built from the
   model — exit multiple × exit EBITDA (or EBITDA CAGR) → MOIC and IRR, with the sponsor base case and our case marked —
   plus the downside that loses money. Venture: exit value needed for 3× net of dilution; MOIC under exit valuations ×
   dilution paths.
5. Transaction terms REPLICATED from the materials — every term for the deal type (KEY TERMS BY DEAL TYPE below),
   sources & uses table, fees and carry; anything the opportunity summary missed or got wrong. Plus management and
   ownership details the research did not have.
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

OVERVIEW_TASK = OVERVIEW_TASK.replace('{deal_terms}', DEAL_TERMS)
INTEGRATE_TASK = INTEGRATE_TASK + '\n' + DEAL_TERMS

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
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5),
"deal_specific": [...] per DEAL-SPECIFIC FACTORS in the SCORECARD DEFINITION.
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
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5),
"deal_specific": [...] per DEAL-SPECIFIC FACTORS in the SCORECARD DEFINITION.
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
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5),
"deal_specific": [...] per DEAL-SPECIFIC FACTORS in the SCORECARD DEFINITION.
""",
}

# ── stage 4: memo ─────────────────────────────────────────────────────────────
MEMO_CSS_NOTE = ('\n\n# MEMO BLUEPRINT — follow this structure and these components exactly\n\n' + fw('memo_blueprint.md')
                 + '\n\n# MEMO CSS-CLASS CHEATSHEET + MANDATORY PROS/CONS DIMENSIONS (ignore this file\'s section order)\n\n'
                 + fw('memo_structure.md'))

MEMO_RULES = """\
Rules: follow the memo structure in the MEMO BLUEPRINT exactly — the headings as written there, the part banners
(<div class="part-h"><span>I</span>Summary and Analysis</div>), the numbered <h2> sections. Use the materials and the
web together with the lead source per topic ("WHERE EACH PART COMES FROM"): the sponsor / GP materials are the factual
base — summarise the deal, the company and the numbers from them faithfully and REPLICATE the transaction terms, fees and
carry, sources & uses, debt terms and historical financials exactly; contest the industry story with reliable external
sources; show the business plan alongside the history, the sponsor's cases as presented, and our own view labelled
"ADCG independent review" (ESTIMATE) with sensitivities. Write it as a story that flows — a short lead per section,
connected paragraphs, the key point in bold, easy on the eye, never mechanical — with real depth: numbers, names, worked
examples and our own judgement, explained from first principles for the {track_name} track. Source-tag figures with the
small .src pills (HARD / IM / MGMT / ESTIMATE); a document / page reference goes inside the pill ("IM p.7") or in
<span class="ref">…</span>, never as bracketed text. Use the scores and numbers given below exactly; never recompute or
contradict the engine. HTML fragment only (no <html>/<head>/<body>, no <style>, no markdown) inside ONE ```html fenced
block. LENGTH — the whole memo ~22–30 pages of real substance; tables where readers compare numbers, otherwise prose.
"""

PROS_CONS = """
  <h2 class="part">II · Investment Pros and Cons</h2> — the heart of the memo. Two stacked numbered lists, never side
  by side: <h3>Pros</h3><ol class="pc-list pros"> with 7–10 items, THEN <h3>Cons</h3><ol class="pc-list cons"> with
  7–10 items. Each <li>: a bold one-line claim, 2–4 sentences of evidence (numbers, named customers / competitors /
  comparable deals, source tags), "Why it matters:" — the effect on returns, downside or exit — then the conviction (pros)
  or severity (cons) tag; cons include the top independent risks. Then <h3>Net assessment</h3>: one paragraph weighing
  the strongest pro against the strongest con. Then <h3>Key risks</h3>: a
  two-sentence bottom line and <ol class="risk-list"> of 6–10 numbered paragraphs, most material first, each led by the
  risk area in bold (<b>Valuation —</b>, <b>Disruption —</b>, <b>Rates &amp; capital structure —</b>, <b>Tariffs &amp;
  geopolitics —</b> …): what could go wrong and why, with evidence and its second- / third-order effects; how likely and
  how severe, in words; whether the sponsor flagged it, the materials show it, or only the independent review found it;
  what would mitigate it. Close with one
  short paragraph on how sponsors have fared in this theme (named precedents). No risk score."""


def scoring_title(track: str) -> str:
    return {'buyout': 'ADCG Buyout Deal Scoring', 'cv': 'ADCG CV Deal Scoring', 'vg': 'ADCG Venture Growth Deal Scoring'}.get(
        track, 'ADCG Buyout Deal Scoring')


def memo_tasks(track: str, sections: list[str]) -> list[tuple[str, str]]:
    """The memo in four calls, in the deal lead's structure (18-Nov-26). `sections` = the framework's section names in
    order; Part III gets one sub-section per section and the app adds the last one (Framework Scoring Summary)."""
    vg = track == 'vg'
    cv = track == 'cv'
    sub = '\n'.join(f'  <h2>III.{i} · {html_escape(n)}</h2>' for i, n in enumerate(sections, 1))
    terms = ('the round terms — instrument, pre / post-money, raise, valuation cap and discount, liquidation preference, '
             'anti-dilution, pro-rata, board, option pool, leads' if vg else
             'the CV terms — single / multi-asset, CV size, fresh money and unfunded, price vs NAV, lead secondaries '
             'investor and syndicate, LP election and roll rate, GP commitment and carry rollover, CV management fee, carry '
             'and hurdle, term, fairness opinion — and the underlying deal terms (EV, multiple, leverage, debt)' if cv else
             'the buyout terms — structure, EV, EBITDA adjusted and reported, multiple, net leverage, debt package, '
             'interest cover, equity and sponsor commitment, rollover / MIP, ADCG ticket, co-invest fees and carry')
    who = ' / lead investors and founders' if vg else ' and the lead secondaries investor' if cv else ''
    return [
        ('Writing memo — deal, company, industry, business model',
         f"""Stage 7a — WRITE THE MEMO, PART 1 of 4. Start with the part banner
  <div class="part-h"><span>I</span>Summary and Analysis</div>, then:
  <h2>1 · Deal Overview</h2> (lead; .kf key-facts grid; {terms} — replicated from the materials, "not disclosed" where
  missing; {'' if vg else 'sources &amp; uses as the .su visual; '}the 3–6 key findings that matter)
  <h2>2 · Company Overview</h2> (from the materials, verified on the web; management table + .gap; the sponsor{who}; ownership / funding history)
  <h2>3 · Industry Primer and Independent Market Assessment</h2> (primer from first principles; then the claims table —
  Claim · Materials say · Independent evidence · Verdict — competition, sponsor crowding and valuation hype, risks to the
  industry; say plainly where the manager oversold it)
  <h2>4 · Business Model, Value Chain, Competitive Landscape and Exitability</h2> (revenue model, .chain, customer .cards,
  suppliers, competitor table, market sizing; exitability — buyer universe and recent exits with multiples)"""),
        ('Writing memo — value creation, financials & plan, valuation, returns & sensitivities',
         f"""Stage 7b — WRITE THE MEMO, PART 2 of 4, continuing Part 1 below (no part banner):
  <h2>5 · Value Creation Plan</h2> (lead with 3–4 numbered points on WHAT DRIVES THE RETURNS, biggest first, each with
  its share of value creation — {'milestones to the next round / exit and what they need' if vg else 'organic growth, bolt-on M&amp;A, a transformational acquisition, EBITDA-margin improvement, deleveraging, multiple expansion'}; then {'' if vg else 'the SVG bridge or table from today’s EBITDA to exit EBITDA and '}a short neutral read on each lever from the company's and sponsor's record and the market)
  <h2>6 · Financials and Business Plan</h2> (ONE <table class="bp">: historical years replicated EXACTLY from the
  materials, then the sponsor's projections to the exit year in <td class="plan"> columns, from the IM or the model and
  tied between them; rows as the sponsor presents them. Then THE CASES — sponsor, management and any other case in the
  materials (e.g. the lead secondaries investor's haircut case in a CV; a lender or vendor-DD case) in one compact table,
  with who prepared each and why they differ; then history vs plan and a reconciliation note for material gaps only)
  <h2>7 · Valuation Analysis</h2> ({'EV / ARR and EV / gross profit, valuation evolution across rounds (SVG or short table)' if vg else 'price vs NAV and the implied multiple' if cv else 'entry multiple on adjusted and reported EBITDA'}; trading and transaction comps; implied band; fair value)
  <h2>8 · Returns Analysis and Independent Sensitivities</h2> (RETURNS ACROSS SCENARIOS — one table of every case as
  presented: exit EBITDA, exit multiple, gross and net MOIC / IRR; then <div class="overstated"><b>What looks
  overstated</b><ol>…</ol></div> — 3–6 crisp sense-checks with numbers on both sides and a one-word verdict each (plausible /
  stretched / overstated), e.g. plan growth vs market growth, planned vs historical acquired EBITDA, margin path vs peers,
  exit vs entry multiple; then
  <div class="indep"><b>ADCG independent review</b> …</div> — our assumptions and why, our case, sensitivity tables
  {'(exit valuation × dilution → MOIC; exit value needed for 3× net)' if vg else '(exit multiple × exit EBITDA or EBITDA CAGR → MOIC and IRR, net of fees and carry where the terms allow)'} with the sponsor base case and our case marked, and the downside that loses money; all ESTIMATE)"""),
        ('Writing memo — pros & cons, key risks, framework scoring',
         f"""Stage 7c — WRITE THE MEMO, PART 3 of 4, consistent with Parts 1–2 below and the computed scores.
{PROS_CONS}
  Then the part banner <div class="part-h"><span>III</span>{scoring_title(track)}</div> and one sub-section per
  framework section, in this order:
{sub}
  The app puts the score panel (total score, band, GP tier) right under the banner — do not repeat it. The
  "Deal-specific factors" sub-section, when present, says first why these factors were chosen for this deal.
  Each: a one-line lead with the section score and weight exactly as in <computed_scores> / <scorecard_json> (e.g.
  "Scores <b>7.4 / 10</b> · weight 25%"), a compact table Criterion · Score · Why (the plain-English reason and key
  evidence from the scorecard rationales; GP-tier criteria say which tier list the firm sits on), and one line on what
  would move the score. No weight arithmetic, no VJR or Marquee point maths. Stop there — the app adds
  <h2>III.{len(sections) + 1} · Framework Scoring Summary</h2> (score bars and overall) itself."""),
        ('Writing memo — recommendation, next steps, appendix',
         """Stage 7d — WRITE THE MEMO, PART 4 of 4, consistent with Parts 1–3 below and the computed scores.
  <h2 class="part">IV · Recommendation and Next Steps</h2> — open with a .tldr (ADCG score and band, the one-line
  stance, the one thing that matters most). Then balanced and neutral, about half a page: one bold line with the leaning
  (e.g. "On balance we lean towards investing, provided…") and the ticket / price stance; "Why" — 2–3 bullets weighing
  both sides; "What would change our view" — at most 3 bullets; "Next steps" — the confirmatory diligence and the decision
  timetable, 2–5 bullets; "What we don't know yet" — one or two lines. No gates, kill criteria or Contrarian note.
  Then the banner <div class="part-h"><span>A</span>Appendix</div> and
  <h2>A.1 · Sources and References</h2> (the data-room documents relied on — file · type · used for — then the external
  sources grouped by topic, as <a href> links)
  <h2>A.2 · Definitions and Methodology</h2> (source tags; metric definitions used — adjusted vs reported EBITDA, net
  leverage, MOIC, IRR, NAV, ARR as relevant; how the ADCG framework scores — 1–10 criteria, weighted sections, bands,
  ADCG preferences ±0.5, no risk score; how the independent review and sensitivities were built)"""),
    ]


def html_escape(t: str) -> str:
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


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
scores changed, update the Part III sub-sections for the changed framework sections and the recommendation's .tldr so
every number matches the new scores.

Output each revised section as its own ```html fenced block that STARTS with that section's original <h2> heading,
exactly as it appears in the memo (same number and words), followed by the complete new content of that section.
Do not output unchanged sections, the scorecard or the Prior Deals appendix. No risk score.

Then ONE fenced ```json block:
{"responses": [{"id": comment id, "response": "≤ 240 chars: what changed in the memo, or why nothing changed"}],
 "summary": "≤ 300 chars: what this revision changed overall"}
"""
