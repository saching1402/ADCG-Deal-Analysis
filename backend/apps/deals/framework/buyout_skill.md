---
name: "adcg-buyout-skill"
description: "ADCG Buyout Skill — IC memo + sector-tailored ADCG Deal Score + Risk Score (HTML + PDF) for buyouts, co-invests alongside a sponsor, secondaries and continuation vehicles. Venture/growth rounds: use the ADCG Venture Growth Skill (adcg-risk-package-venture-growth)."
---

# ADCG Buyout Skill

Scope: **buyouts, co-investments alongside a sponsor, fund/GP-led secondaries and continuation vehicles**.
For venture and growth rounds (Seed → pre-IPO, venture co-invests, startup secondaries) use the
**ADCG Venture Growth Skill** (`adcg-risk-package-venture-growth`), which reuses this skill's scripts and assets.
Do not rename or move this skill's `scripts/` or `assets/` folders.

One skill that combines three things the user previously ran separately: the **IC diligence
memo** (Pros/Cons, mandatory dimensions, staged gates), the **ADCG Deal Score card** (5
sections × 25 sector-tailored criteria, weighted roll-up, verdict band), and the **derived
Risk Score** (0–100). It outputs a single institutional deliverable as **HTML + PDF**, wires
in the **Contrarian app** when the deal is available there, and keeps the sector-metric library
growing. It supersedes the separate `ic-diligence-memo` and `adcg-deal-scorecard` skills.

## Core stance (do not drift)

Skeptical, decision-oriented, non-promotional — the memo a senior LP puts in front of an IC:
- **Educate first, then judge.** The memo ALWAYS opens with the Company Overview and the Industry/Technology Primer, then the details, then the scoring and weightings, then the verdict. Never open with the verdict, a TL;DR or the scorecard (user's standing instruction; see "Mandatory memo order", which overrides any other ordering in this skill or its references).
- **Always teach with worked examples** — every primer concept gets a concrete numeric example, a plain-English analogy, and a comparison table of how named players differ.
- **Grade everything** — every risk gets a severity tag `[HIGH/MEDIUM-HIGH/MEDIUM/LOW]`; every
  Pro a conviction tag `(HIGH/MEDIUM/LOW)`. A memo with no severity signals has failed.
- **Separate fact from inference** — mark every private-company number **HARD** (filing, rated
  debt, court record, company disclosure) vs **ESTIMATE/PROXY** (trade press, broker, inference).
  Never launder an estimate into a fact. Show ranges when sources diverge; say which you trust.
- **Name names** — valuation and competition need **named comps and specific multiples**
  (e.g. "Bakkavor take-out ~7.5–7.9× vs this deal 8.8×"), never a generic band.
- **Push back on soft framing** and give the bear case. The user wants the critical view.
- **Flag data gaps** as explicit diligence questions, not glossed.

## Mandatory memo order (non-negotiable; overrides references/memo-structure.md)

1. **Company overview** — genesis, management (and gaps), footprint, headcount, ownership history and deal/funding history table (HARD/EST).
2. **Industry & technology primer** — how the business and industry work from first principles, with worked numeric examples, analogies and inline SVG visuals; a table of how named competitors differ.
3. **Business model, value chain & competitive landscape** — value capture; value-chain diagram with named examples, margins per layer and who holds pricing power; 2–3 named customers; 4–5 named suppliers; competitor table; entry threat; market sizing in the right units; first-principles multiple test.
4. **Latest transaction & key findings** — full deal terms (EV, EBITDA, multiple, leverage, structure; filings vs press), then 6–9 tagged findings.
5. **Financials & valuation** — financials table, named-comps table, implied band, deal rationale (benign vs skeptical).
6. **ADCG scoring — section weightings & why** — default vs deal weights table with reasons, THEN the scorecard fragment.
7. **Verdict** (TL;DR box). 8. **Pros & Cons (IC voice)**. 9. **Recommendation — staged gates with kill criteria**, Caveats, Contrarian note, Appendix — Prior Deals.

The header subtitle names the deal; it never leads with the score.

## Workflow

1. **Confirm the entity** if the name is ambiguous (one quick question) and **capture the deal
   facts**: transaction type (buyout / growth / secondary / co-invest / fund / **CV**), EV,
   Adj. EBITDA, multiple, net leverage, equity %, mark (MOIC), sponsor, sector. Compute the
   obvious derived figures (net debt, equity, implied margin) and reconcile the multiple.
2. **Research hard** (IC-grade). Prioritise primary sources: filings/Companies House, rated
   debt, sponsor/company releases, regulator sites, broker notes, credible trade press. Search
   each competitor / comparable **separately**. Cover: business model & value-chain position,
   historical financials (organic vs M&A), named trading **and** transaction comps, competition,
   industry TAM/growth, regulatory tailwinds/headwinds, management, ownership history, and the
   deal-specific angle (for a CV: why the sponsor is launching it, the price-setting conflict).
   See `references/memo-structure.md` for the full section template and the mandatory Pros/Cons
   dimensions.
3. **Select the sector-dynamic scorecard.** Identify sector → sub-sector, then pull or derive the
   **25 criteria and the per-deal section weights** from `references/scorecard-methodology.md`
   (it holds the growing sector-metric library and the recipe for a new sub-sector). Criteria and
   weights MUST reflect the sub-sector — reuse an existing block if it fits, otherwise build one
   and add it to the library.
4. **Query the Contrarian app.** Follow `references/contrarian-integration.md`: if the deal is
   loaded there, pull its risks/contrarian view and fold them in; if not, state the scores are
   skill-derived and offer to add it. Either way, note reconciliation to the live ADCG app.
5. **Score & compute (deterministic).** Score each of the 25 criteria 1–10 with a one-line
   rationale; write the deal JSON (schema in `references/scorecard-methodology.md`); run the
   engine to get the roll-up, band, risk score, and the static scorecard fragment:
   ```bash
   cd <skill-dir>
   python3 scripts/adcg_scorecard.py <deal.json> --out /tmp/scorecard.html
   ```
   The printed JSON gives overall / risk / band / section scores — use those numbers in the prose.
6. **Write the memo prose in the Mandatory memo order** (CSS cheatsheet in `references/memo-structure.md`;
   ignore that file's section order). Write `/tmp/top_prose.html` = sections 1–5 + the weightings table,
   then `cat /tmp/top_prose.html /tmp/scorecard.html > /tmp/top.html`. Write `/tmp/body.html` = sections
   7–9 (Verdict TL;DR → Pros & Cons with all 8 mandatory dimensions → gates → Caveats → Contrarian →
   Appendix).
7. **Assemble → HTML → PDF → present.** Inject the fragment and body into the shell, render the
   PDF, and present BOTH files:
   ```bash
   python3 scripts/assemble_memo.py --shell assets/memo_shell.html \
       --scorecard /tmp/top.html --body /tmp/body.html \
       --title "…" --subtitle "…" --eyebrow "…" --classif "Confidential · IC Draft" \
       --footer "…" --out /mnt/user-data/outputs/<slug>-ic-memo.html
   python3 scripts/html_to_pdf.py /mnt/user-data/outputs/<slug>-ic-memo.html \
       /mnt/user-data/outputs/<slug>-ic-memo.pdf
   ```
   Then call `present_files` with the HTML first, then the PDF. If `assemble_memo.py` isn't used,
   a plain string-replace of `{{TITLE}} {{SUBTITLE}} {{EYEBROW}} {{CLASSIF}} {{SCORECARD}}
   {{BODY}} {{FOOTER}}` in the shell is equivalent.

## Sector-dynamic weighting (the point of the skill)

The 25 criteria and the 5 section weights are **not fixed**. Default section weights are
Sector Focus 15 / Trophy Asset 20 / Business Quality 25 / Valuation & Leverage 25 / Alignment 15,
but shift them to the deal: for a **CV / secondary**, raise Alignment and Valuation & Leverage
(price-setting conflict, mark credibility, leverage); for a **growth/venture** deal, raise
Business Quality and Sector Focus; for a **fund commitment**, Alignment dominates (conflicts,
key-person, track record). Then swap in sub-sector-specific criteria — e.g. weather/seasonality
and slip-and-fall liability for snow services; HFSS/UPF and retailer-concentration squeeze for UK
chilled food; accreditation moats and margin-vs-majors for TIC. `references/scorecard-methodology.md`
has the library and the recipe. Undisclosed criteria: set `"score": null` to exclude and
renormalise the section (the engine does this automatically).

## Calibration (keep scores comparable across deals)

Recent skill-derived anchors: **Apave 6.16 / risk 38**, **Acelpa 6.1 / risk 39**,
**Case FMS 5.9 / risk 41**, **Compleat 5.4 / risk 46**. A new deal that feels "about like Apave
but with more leverage" should land near it, not two points away. Sanity-check the overall against
these before finalising.

## Reconcile to the live app

The scores here are **skill-derived**. The live ADCG app
(`adcg-deal-scorecard-production.up.railway.app`) remains the source of truth — tell the user to
reconcile, and (if not already there) offer to load the deal into it and the Contrarian app.

## After delivering — update the sector library & log

Per the user's standing instruction, append to memory `/areas/adcg-scorecard-metrics.md`: (a) a
one-paragraph scoring-log entry for the deal (metrics, key tension, ADCG/risk, verdict), and (b)
if a new sub-sector block was built, a summary of its criteria and comps. Keep numbers HARD vs
ESTIMATE. (Do not store anything the memory privacy rules exclude — not an issue for deal facts.)

## Self-check before delivering

- Page 1 opens with **1 · Company overview**, then **2 · Industry & technology primer** (worked examples,
  visuals, competitor table); scoring only after the details; verdict after scoring? (The shell renders
  `{{SCORECARD}}` first, so always pass `top.html`, never the bare scorecard. Rasterise page 1 to confirm.)
- Every risk severity-tagged; cons ordered by severity? All 8 mandatory Pros/Cons dimensions
  present (industry attractiveness, competition, M&A/roll-up, revenue visibility, valuation,
  regulatory, historical financials, market position)?
- Private numbers marked HARD vs ESTIMATE, with ranges where sources diverge?
- **Named** comps with **specific** multiples (not a generic band)?
- Criteria & weights are sector-specific, not generic? Overall calibrated vs the anchors above?
- Recommendation **staged with gates and kill criteria**?
- Contrarian app checked and reconciliation to the live app stated?
- **Both** HTML and PDF produced and presented?

## Files

- `scripts/adcg_scorecard.py` — deterministic roll-up + risk + static-SVG scorecard fragment.
- `scripts/assemble_memo.py` — inject scorecard + body into the shell.
- `scripts/html_to_pdf.py` — Chromium (Playwright) with wkhtmltopdf fallback.
- `assets/memo_shell.html` — institutional template (placeholders; print/PDF-optimised).
- `references/scorecard-methodology.md` — framework, weighting recipe, sector library, JSON schema.
- `references/memo-structure.md` — memo sections, mandatory dimensions, CSS-class cheatsheet.
- `references/contrarian-integration.md` — Contrarian app usage, roster, reconciliation.