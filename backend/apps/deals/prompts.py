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
  the memo shell, builds the "Appendix — Prior Deals" from its own pipeline, and renders the PDF.
- The Contrarian app is not reachable from here: say the scores are skill-derived and should be reconciled to the live
  ADCG scorecard app (adcg-deal-scorecard-production.up.railway.app).
- Evidence priority: the uploaded deal materials are the primary source for facts and figures (revenue, EBITDA, terms,
  management, KPIs) — cite them as [file name, p./sheet/slide]. Reliable independent external sources are primary for
  risks, competition, comps and market context. Where the two disagree, show both and say which you trust and why.
  Company/seller-prepared figures are MGMT claims until verified — never launder them into HARD facts.
- Write for an investment committee: skeptical, decision-oriented, non-promotional, every number tagged HARD or
  ESTIMATE, named comps with specific multiples, severity tags on every risk.
"""

TRACK_RULE = """\
Track selection: positive EBITDA + leverage + sponsor control (buyout, co-invest alongside a sponsor, fund/GP-led
secondary, continuation vehicle) → **buyout** track (ADCG Buyout Skill). A venture- or growth-stage company raising or
recently raising a priced round (Seed → pre-IPO, venture co-invest, startup secondary) → **vg** track (ADCG Venture
Growth Skill).
"""


def framework(track: str) -> str:
    """Framework text for a track ('buyout', 'vg', or 'auto' = both, for research) from the editable Framework tab."""
    from . import frameworks
    if track in ('buyout', 'vg'):
        body = frameworks.prompt_text(track)
    else:
        body = frameworks.prompt_text('buyout') + '\n\n' + frameworks.prompt_text('vg')
    return body + '\n\n' + fw('lens.md')


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
    return '\n'.join(rows)


def materials_block(deal, files) -> dict:
    """All per-file digests as one cacheable user block."""
    if not files:
        txt = '<materials>\nNo deal materials were uploaded — rely on public sources and flag every gap.\n</materials>'
    else:
        parts = []
        for f in files:
            cov = f.coverage or {}
            gap = ('' if f.status == 'digested' else
                   ' coverage="PARTIAL — not read: ' + '; '.join(x['label'] for x in cov.get('failed', [])) + '"')
            parts.append(f'<digest file="{f.name}" pages="{f.pages or ""}"{gap}>\n{f.digest}\n</digest>')
        txt = (f'<materials count="{len(files)}">\nFact sheets written from each uploaded file '
               '(cite as [file, location]).\n' + '\n\n'.join(parts) + '\n</materials>')
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
RESEARCH_TASK = """\
Stage 2 of 4 — RESEARCH. Research this deal to IC grade using web search, following the framework's workflow
(primary sources first; search each competitor and comparable separately; filings, rated debt, releases, regulators,
broker notes, credible trade press; for venture: funding history, Companies House/Delaware/Form D, investor lists).
Combine what you find with the uploaded materials above.

Write a RESEARCH DOSSIER in markdown that a memo writer can work from without searching again. Cover, with numbers
and sources (URLs inline):
1. Entity confirmation and the transaction / latest round in full (terms, filings vs press).
2. Company overview — genesis, management (gaps), footprint, headcount, ownership & deal/funding history table.
3. Industry & technology primer notes — how the business works from first principles, worked numeric examples.
4. Business model, value chain (layers, named players, margins, pricing power), 2–3 named customers, 4–5 named
   suppliers, competitor table (named, latest valuation/scale, how each differs), entry threat, market sizing in the
   right units.
5. Financials — history (organic vs M&A), margins, cash conversion, leverage; venture: ARR/revenue at each round.
6. Valuation — named trading AND transaction comps with specific multiples (private and public for venture),
   implied band; venture: valuation evolution per round vs fundamentals.
7. Regulatory tailwinds/headwinds, litigation, key risks with severity.
8. Investors (venture): every investor in the current round with role (lead/participant) and earlier-round investors.
9. Data gaps → explicit diligence questions.
Tag every private-company figure HARD or ESTIMATE; show ranges where sources diverge.

Finish with ONE fenced ```json block:
{"track": "buyout" | "vg", "track_reason": "...", "company_name": "...", "website": "...", "sector": "...",
 "sub_sector": "...", "sponsor": "sponsor or lead investors, short", "one_liner": "≤ 25 words: what it is + the key tension",
 "ev": "EV or post-money with HARD/EST", "multiple": "headline multiple", "leverage": "net leverage or n/a",
 "facts": [{"k": "Enterprise Value", "v": "…"}, … up to 5],
 "sources": ["https://…", …]}
"""

# ── stage 3: scorecard JSON ──────────────────────────────────────────────────
SCORE_TASK = {
    'buyout': """\
Stage 3 of 4 — SCORE on the ADCG Buyout framework exactly as defined in the SCORECARD DEFINITION block (no new
searching). Identify sector → sub-sector, reuse or build the sector-library block, set the per-deal section weights
(sum 100; start from the defaults and apply the weighting rules) and score every criterion 1–10 with a one-line
rationale; `null` for undisclosed (keep each section's criteria count). Calibrate against the anchors and the prior deals
listed below — do not drift more than ~0.3 from a close analogue without a reason.

Return ONLY one fenced ```json block in the OUTPUT JSON SCHEMA, plus these keys:
"weights_rationale": [{"section": "...", "default": n, "deal": n, "why": "..."}],
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5).
""",
    'vg': """\
Stage 3 of 4 — SCORE on the ADCG Venture Growth framework exactly as defined in the SCORECARD DEFINITION block (no new
searching): its sections, fixed weights and criteria in order. Name the theme in sub_sector. For the auto "marquee"
criterion give {"name": ..., "auto": "marquee", "rationale": "…"} and list every investor with its tier in "investors"
(the engine computes the index). Give "valuation_evolution" for the VJR and score every risk-register row by its exact
name (severity 1–10). Calibrate against the anchors and the prior deals listed below.

Return ONLY one fenced ```json block in the OUTPUT JSON SCHEMA, plus these keys:
"weights_rationale": [{"section": "...", "default": n, "deal": n, "why": "..."}],
"key_risks": [{"criterion": "...", "severity": "HIGH|MEDIUM-HIGH|MEDIUM|LOW", "why": "..."}]  (top 5).
""",
}

# ── stage 4: memo ─────────────────────────────────────────────────────────────
MEMO_CSS_NOTE = '\n\n# MEMO CSS-CLASS CHEATSHEET (use these classes; ignore this file\'s section order)\n\n' + fw('memo_structure.md')

MEMO_TOP_TASK = """\
Stage 4a — WRITE THE MEMO, PART 1 (HTML fragment). Follow the framework's Mandatory memo order and write sections
1–5 in full, then section 6's weightings table:
  <h2>1 · Company overview</h2> … <h2>2 · {primer}</h2> … <h2>3 · Business model, value chain &amp; competitive landscape</h2> …
  <h2>4 · {latest}</h2> … <h2>5 · {fin}</h2> … <h2>6 · {scoring} — section weightings &amp; why</h2> (weights table only;
  the app inserts the scorecard right after it).
Educate first: worked numeric examples, plain-English analogies, comparison tables of how named players differ, and
at least two inline <svg> visuals (value chain; plus market/valuation evolution) styled with simple strokes/fills.
Use the scores and numbers given below exactly — never recompute or contradict the engine. Tag HARD/ESTIMATE, severity
and conviction as the framework requires; cite uploaded files as [file, location] and web sources inline by name.
HTML fragment only (no <html>/<head>/<body>, no <style>, no markdown) inside ONE ```html fenced block.
"""

MEMO_BODY_TASK = """\
Stage 4b — WRITE THE MEMO, PART 2 (HTML fragment), consistent with Part 1 below and the computed scores:
  <h2>7 · Verdict</h2> with the TL;DR box (3 bold bullets: verdict with ADCG score/band and risk; the model/edge in one
  line; the single gating item), then <h2>8 · Pros &amp; Cons (IC voice)</h2> covering ALL 8 mandatory dimensions
  (tag each bullet with its dimension; cons severity-ordered, pros conviction-tagged), then
  <h2>9 · Recommendation — staged gates with kill criteria</h2> (3–5 gates, each: verify / gate / kill-if; end with
  the valuation anchor and structuring asks), then <h3>Caveats</h3> (data gaps, undisclosed terms) and
  <h3>Contrarian note</h3> (not loaded — skill-derived; reconcile to the live ADCG app).
Do NOT write the Prior Deals appendix — the app appends it.
HTML fragment only inside ONE ```html fenced block.
"""

HEADINGS = {
    'buyout': {'primer': 'Industry &amp; technology primer', 'latest': 'Latest transaction &amp; key findings',
               'fin': 'Financials &amp; valuation', 'scoring': 'ADCG scoring'},
    'vg': {'primer': 'Theme, industry &amp; technology primer', 'latest': 'Latest fund raise &amp; key findings',
           'fin': 'Financials, valuation &amp; valuation evolution', 'scoring': 'ADCG-VG scoring'},
}


def ledger_text(rows) -> str:
    if not rows:
        return 'Prior deals in the pipeline: none yet.'
    head = '| Company | Track | Sponsor / round | EV | Multiple | Lev | ADCG | Risk | One-liner |\n|---|---|---|---|---|---|---|---|---|'
    body = '\n'.join(
        f'| {d.name} | {"VG" if d.track_resolved == "vg" else "Buyout"} | {d.sponsor[:80]} | {d.ev[:40]} | {d.multiple[:40]} | '
        f'{d.leverage[:20]} | {d.adcg_score if d.adcg_score is not None else "n/d"} | {d.risk_score if d.risk_score is not None else "n/d"} | '
        f'{d.one_liner[:160]} |' for d in rows)
    return ('Prior deals already scored in the pipeline (calibration set — Buyout and VG scores are not comparable '
            'with each other):\n' + head + '\n' + body)
