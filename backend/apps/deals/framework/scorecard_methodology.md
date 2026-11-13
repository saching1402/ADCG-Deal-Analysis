# ADCG Scorecard — Methodology, Sector Library & JSON Schema

Companion to SKILL.md. Read when building the scorecard for a deal.

## 1. The framework

- **5 sections**, each with **5 criteria** = 25 criteria. Every criterion scored **1–10**.
- **Two-level weighted roll-up.** Section score = weighted mean of its 5 criteria (equal weights
  unless you set per-criterion weights). Overall ADCG = Σ (section_weight/100 × section_score).
- **Per-deal section weights** (must sum to 100). Default: Sector Focus **15** / Trophy Asset
  **20** / Business Quality **25** / Valuation & Leverage **25** / Alignment **15**. Adjust to the
  deal (see §2).
- **Undisclosed items:** set `"score": null` → the engine drops the item and renormalises the
  section across the remaining criteria (the live app's "zero-and-renormalise" behaviour).
- **Verdict bands:** Strong ≥8.0 · Positive 6.5–7.9 · Neutral 5.0–6.4 · Weak <5.0.
- **Derived Risk Score = (10 − ADCG) × 10**, on 0–100, **higher = riskier** (Contrarian convention).

The five sections (canonical):
1. **Sector Focus** — is the sub-sector structurally attractive? (growth vs GDP, defensiveness,
   demand drivers, regulatory direction, profit-pool health / who holds pricing power).
2. **Trophy Asset** — is this a scarce, high-quality asset? (category rank/share, scarcity,
   brand/customer entrenchment, franchise durability / switching costs).
3. **Business Quality** — margins, growth quality (organic vs M&A), cash conversion / capital
   intensity, input-cost resilience, operational/integration execution.
4. **Valuation & Leverage** — entry vs transaction comps, entry vs trading comps, leverage level
   & headroom, return reliance (growth vs re-rating), equity cushion / downside.
5. **Alignment** — sponsor track record, management quality/continuity, structure/governance
   (for a CV: price-setting conflict, GP rollover, carry crystallisation), mark credibility.

## 2. Dynamic weighting by transaction type

- **Continuation vehicle / secondary:** raise **Alignment** (→ ~20–22) and **Valuation & Leverage**
  (→ ~26–28); the price is sponsor-set and the mark is the crux. Trim Sector Focus.
- **Buyout (control):** the default split is a good start.
- **Growth / venture:** raise **Business Quality** and **Sector Focus**; Valuation shifts to
  revenue/ARR multiples and burn/runway; leverage often n/a (score null).
- **Fund / GP commitment:** **Alignment** dominates (conflicts, key-person, LPA terms, GP commit);
  "Business Quality" → track record by vintage (DPI/TVPI/net IRR vs benchmark); "Trophy Asset" →
  franchise/brand of the manager.
- **Co-invest / minority:** add governance/control criteria under Alignment (board rights, drag/tag,
  information rights) — a minority stake in a controlled asset is a standing risk (cf. Apave).

## 3. Sector-metric library (reuse a block or extend it)

Each block below lists the **sub-sector-specific** criteria that replace generic ones, plus the
comp anchors. Reuse verbatim if the deal fits; otherwise adapt and **add a new block** (recipe in
§4). Keep this library growing — it is the whole point of the skill.

### TIC / Industrial Inspection & Certification  (anchor: Apave — 6.16 / risk 38)
Sector-specific criteria: regulatory-mandate demand engine (NIS2/CRA/CSRD/energy-transition/
nuclear); accreditation moats (COFRAC/CEFRI/CE); trainer–inspector flywheel; **margin-vs-majors
gap** (18–23% benchmark for BV/SGS/Intertek/Eurofins — the core tension if the target sits ~10%);
asset-light high-cash-conversion; professional-liability / negligent-certification tail;
minority-vs-control governance in CV structures; US integration risk.
Comps: listed TIC median ~12–12.9× / LTA ~14.2× / premium UL·ALS >18×; txns 10–14.5×
(UL-E&E 14.5×, Certania-Ica 10×). Market >$230bn, no player >5% share.

### Snow / Exterior Facility Services  (anchor: Case FMS — 5.9 / risk 41)
Sector-specific criteria: weather/snowfall demand dependence; seasonality & weather-normalised
EBITDA volatility; managed-vendor network reliability & disintermediation / payment-reputation
risk; slip-and-fall liability & snow anti-indemnity statutes; H-2B / 1099 labour exposure; founder
rollover alignment.
Comps: BrightView ~8×; snow add-ons 7–9.5×; integrated platforms 9–12×. Market $124bn, ~2.9% CAGR,
BV #1 at ~1.5% share.

### Home / Specialty Infusion (healthcare services)  (anchor: Acelpa — 6.1 / risk 39)
Sector-specific criteria: reimbursement risk (Medicare/Medicaid budget & policy); home-infusion vs
hospital site-of-care shift; de-novo opening economics; fragmentation & roll-up runway; payor/drug
pricing & margin pressure; clinical/accreditation & compliance; PE-ownership track record in the space.
Comps: home/specialty infusion ~12–13× EV/LTM EBITDA (named peers incl. AOM Infusion).

### UK Chilled / Convenience Private-Label Food Manufacturing  (anchor: Compleat — 5.4 / risk 46)
Sector-specific criteria: category volume-vs-price growth & defensiveness; private-label trade-down
tailwind; **retailer-concentration profit-pool squeeze** (the "squeezed middle" value-chain
position); HFSS/UPF + EPR/packaging-tax/employer-NIC/BTOM regulatory drag; buy-and-build multiple-
arbitrage in a fragmenting sector; thin ~8–9% EBITDA margins & high capex/WC/D&A capital intensity
(sale-and-leaseback tell); input-cost pass-through lag; re-tenderable own-label "recurring" revenue;
single-asset-CV price-setting conflict; US-expansion trap.
Comps: UK chilled/convenience txns ~7.5–7.9× (Bakkavor take-out); listed Cranswick ~8.9× / Hilton
Food ~5.4× / Greencore; branded Hormel ~11×; commodity Tyson ~7.5× / Pilgrim's ~5.2×; AgriFood avg
~10.6×. Rule: further from commodity, closer to brand/spec → higher multiple.

### Sketches to expand when next hit
Industrial manufacturing; Software/SaaS (ARR growth, NRR, rule-of-40, gross margin, retention,
churn, valuation on ARR). Build them out on first use.

## 4. Recipe for a new sub-sector block

1. Name the demand engine (what structurally grows the top line) and score it under Sector Focus.
2. Identify the 2–3 moats/risks unique to the sub-sector (accreditation, weather, reimbursement,
   retailer power, HFSS…) and turn each into a criterion.
3. Pin the margin benchmark and the capital-intensity/cash-conversion profile for Business Quality.
4. Gather **named** trading and transaction comps and the market size/growth/fragmentation.
5. Add the block here with its comp anchors, and set the calibration anchor once scored.

## 5. Calibration anchors (keep new deals comparable)

Apave 6.16 / 38 · Acelpa 6.1 / 39 · Case FMS 5.9 / 41 · Compleat 5.4 / 46.
A leveraged, full-priced deal should sit lower (toward Compleat); an asset-light, well-aligned,
reasonably-priced platform higher (toward Apave). Don't drift more than ~0.3 from where a close
analogue landed without a reason.

## 6. deal.json schema (input to adcg_scorecard.py)

```json
{
  "deal": {
    "name": "The Compleat Food Group",
    "recommendation": "Proceed to confirmatory DD — conditional",
    "facts": [
      {"k": "Enterprise Value", "v": "€1,163m"},
      {"k": "Adj. EBITDA", "v": "€133m"},
      {"k": "EV / EBITDA", "v": "8.8×"},
      {"k": "Net Leverage", "v": "4.9×"},
      {"k": "PAI Mark", "v": "3.2× MOIC"}
    ]
  },
  "sector": "Food & Consumer",
  "sub_sector": "UK Chilled / Convenience Private-Label Food Manufacturing",
  "recommendation": "Proceed to confirmatory DD — conditional",
  "verdict_note": "2 hard gates",
  "calibration": "Riskiest of recent set vs Apave 38 / Acelpa 39 / Case 41 …",
  "contrarian": {"loaded": false, "text": "Not loaded in Contrarian app — skill-derived; reconcile to live ADCG app."},
  "sections": [
    {"name": "Sector Focus", "weight": 15, "criteria": [
      {"name": "…", "score": 5.5, "rationale": "…"},
      {"name": "…", "score": null, "rationale": "undisclosed — excluded & renormalised"}
    ]}
  ]
}
```

Rules: exactly 5 sections; weights sum to 100; 5 criteria per section (use `null` scores rather
than dropping a criterion so the shape stays 5×5); scores 1–10; keep rationales to one line.
Run: `python3 scripts/adcg_scorecard.py deal.json --out /tmp/scorecard.html`.
