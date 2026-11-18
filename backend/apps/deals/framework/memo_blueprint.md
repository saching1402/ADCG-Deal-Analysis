# IC memo blueprint — the house format (modelled on the Armada VG memo, Nov-26)

The memo reads like a **deep-research report that flows like a story** — written by an investor who has understood
the business from first principles and then tested the seller's story against the world. Each section opens with a
short plain-English lead (what you need to know), then builds the argument in connected paragraphs; tables, diagrams
and callouts support the story, they don't replace it. It must have real substance (numbers, names, worked examples,
our own judgement) AND be easy on the eye: short paragraphs, clear sub-heads, the key point of each paragraph in bold,
generous white space, no walls of bullets, nothing mechanical.

WHERE EACH PART COMES FROM (deal lead, Nov-26) — the materials and the web together, with a clear lead per topic:
- **Describing the company** (what it does, products / service lines, business units, customers, footprint,
  management and their roles, ownership history, the sponsor — who they are, where they invest, their track record):
  **the materials first** — the IM / SIM / CIM, management presentation and sponsor memo describe how the business is
  run better than anyone. Summarise from them, verify against the web, and add anything material the web shows that the
  materials leave out.
- **Industry primer**: start from the materials' market section, then **contest it** with reliable external sources
  (independent market reports, listed-peer disclosures, industry bodies, credible press). Sellers present every sector
  as the greatest; say plainly where the evidence is weaker (slower growth, heavy competition, crowding of sponsors,
  valuation hype, structural headwinds such as AI pressure on software) and where it holds up.
- **Business model, value chain & competition**: a combination — the materials for how the company earns money and its
  named customers; the web AND any market study in the data room for competitors' latest revenues, customers,
  locations and ownership. Market sizing: anchor on the materials, extrapolate and cross-check with external sources.
- **Transaction terms, historical financials, sources & uses, debt terms, fees & carry**: **replicate from the
  materials exactly** — these are hard facts and the materials are the source of truth. Never alter a backward-looking
  number.
- **Business plan**: from the materials (model, IM), then tested — history vs plan, each driver checked against the
  company's record and the market (neutral, evidence-based feedback). The sponsor's cases are shown as presented; our
  own case and sensitivities are labelled "ADCG independent review" (tag ESTIMATE); they never change the actuals.

## Source tags (small, out of the way)
Tag figures with the small pills — they are deliberately tiny so they don't interrupt reading:
`<span class="src hard">HARD</span>` public / verified (filings, company release, regulator, credible press)
`<span class="src im">IM</span>` from the information memorandum, model, QoE or other data-room file
`<span class="src mgmt">MGMT</span>` management / sponsor claim with no independent support (percentages, targets)
`<span class="src est">ESTIMATE</span>` our triangulation. Ranges where sources disagree, and say why.
A document / page reference (e.g. "SIM p.7", "Model · P&L tab") goes INSIDE the pill or in `<span class="ref">SIM p.7</span>`
— never as bracketed text in the sentence. Use page references sparingly: for hard facts lifted from a document
(financials, sources & uses, debt terms) and where documents disagree.

## Components (CSS classes in the shell)
- Tables: plain `<table>`; target row `<tr class="hl">`; numbers `<td class="num">`; the last column is often a
  short "Read" / "So what" column — one line of judgement per row.
- Gap callout (missing people, data, disclosure): `<div class="gap"><b>GAP</b> …</div>`
- Plain-English box (analogy / "what this means"): `<div class="explain"><b>Analogy:</b> …</div>`
- Flow / comparison diagram, two lanes:
  `<div class="flow"><div class="lane"><div class="lane-h">Conventional …</div><div class="steps"><span>Permit</span><span>Grid tie-in</span>…</div><div class="lane-n">Typical time … · Best at …</div></div><div class="lane alt">…</div></div>`
- Value-chain strip (5–6 layers, left→right, target layer highlighted):
  `<div class="chain"><div class="node"><b>Silicon</b><span>NVIDIA</span><em>GM ~75% · pricing power</em></div>…<div class="node me">…</div></div>`
  then one bold line on where the power sits and who squeezes whom.
- Customer cards: `<div class="cards"><div class="card"><b>US Navy</b> — what they use it for. <i>Needs:</i> … <i>Watch:</i> …</div>…</div>`
- Numbered findings: `<ol class="findings"><li><b>Headline claim.</b> evidence with numbers … <span class="sev s-high">HIGH</span></li></ol>`
- Bar chart (valuation evolution, revenue/EBITDA bridge): inline `<svg viewBox="0 0 640 220">` with simple rects,
  value labels on the bars and the axis in `$bn`/`$m`; one caption line underneath on fundamentals at each mark.
- Sources & uses (replicated from the materials, shown visually):
  `<div class="su"><div class="su-col"><div class="su-h">Sources</div><div class="su-row"><span>Senior term loan</span><b>$300m</b><em>48%</em></div>…<div class="su-row tot"><span>Total</span><b>$625m</b></div></div><div class="su-col">…Uses…</div></div>`
  plus, where it helps, a single stacked SVG bar of the capital structure (debt vs equity) with the leverage multiple.
- Part banner: `<div class="part-h"><span>III</span>ADCG CV Deal Scoring</div>`; II / IV headings `<h2 class="part">`.
- History + plan table: `<table class="bp">` with plan columns `<th class="plan">` / `<td class="plan">`.
- Our own view: `<div class="indep"><b>ADCG independent review</b> …</div>` (assumptions, our case, sensitivities).
- Key-facts grid for the transaction: `<div class="kf"><div><span>Enterprise value</span><b>$531m</b><em>12.7× LTM adj. EBITDA</em></div>…</div>`
- Severity `s-high|s-medhigh|s-med|s-low`, conviction `<span class="conv">MED-HIGH</span>`, pros/cons `.pc`,
  caveats `.caveat`, TL;DR `.tldr` — as in the CSS cheatsheet.

## The memo structure (deal lead, 18-Nov-26 — the same for all three frameworks)
Headings exactly as below. Part banners are `<div class="part-h"><span>I</span>Summary and Analysis</div>` (I, III and
Appendix); every numbered section is an `<h2>`; II and IV are `<h2 class="part">…</h2>`. Section III's title and its
sub-sections follow the framework the deal is scored on (ADCG Buyout · ADCG CV · ADCG Venture Growth).

```
I. Summary and Analysis
   1 · Deal Overview
   2 · Company Overview
   3 · Industry Primer and Independent Market Assessment
   4 · Business Model, Value Chain, Competitive Landscape and Exitability
   5 · Value Creation Plan
   6 · Financials and Business Plan
   7 · Valuation Analysis
   8 · Returns Analysis and Independent Sensitivities
II · Investment Pros and Cons
III. ADCG <Buyout | CV | Venture Growth> Deal Scoring
   III.1 … III.5 (III.6 for VG) · one sub-section per framework section, in framework order
   III.n · Framework Scoring Summary   ← written by the app (score bars + overall)
IV · Recommendation and Next Steps
Appendix
   A.1 · Sources and References
   A.2 · Definitions and Methodology
```

HOW THE SOURCES ARE USED: the sponsor / GP materials (IM, market study, model, QoE, other reports) are the factual
base — they are reviewed by many sophisticated LPs (pension funds, endowments, sovereign funds), so the numbers and terms
are taken as reasonably true and summarised faithfully. What gets contested is the story: industry growth, market
position, competition, and anything the manager may have oversold — that is where the web comes in.

**1 · Deal Overview** — the transaction summary, replicated from the materials. A two-sentence lead (what we are being
asked to invest in, at what price, alongside whom), then the `.kf` key-facts grid and the key terms for the deal type:
- *Buyout / co-invest*: structure, seller and why now, EV, LTM EBITDA adjusted and reported, EV/EBITDA on both, net
  leverage, debt package (instruments, quantum, pricing, maturity, covenants), interest cover, equity cheque and the
  sponsor's own commitment, management rollover and MIP, ADCG ticket, **fees and carry on the co-invest** (management
  fee, carry, hurdle — or no fee / no carry), governance and information rights, timetable.
- *CV / GP-led secondary*: single- or multi-asset; the asset(s) and selling fund (vintage, remaining life); CV size,
  fresh money and unfunded commitment; price vs NAV (premium / discount) and reference date; lead secondaries investor
  and syndicate; LP election (roll / sell / status quo) and expected roll rate; GP commitment and carry rollover /
  crystallisation; **CV economics** — management fee and its basis, carry, hurdle, tiered carry, fee offsets; CV term and
  extensions; fairness opinion, LPAC; the underlying deal terms (EV, multiple, leverage, debt); ADCG ticket.
- *Venture / growth round*: round and date, instrument (priced preferred, SAFE, note), pre- and post-money, raise,
  primary / secondary split, **valuation cap and discount** (SAFEs / notes), **liquidation preference** (multiple,
  participating or not, seniority), anti-dilution, pro-rata, board and protective provisions, option pool, leads and
  new / returning investors, use of proceeds, ADCG ticket and SPV fee / carry if any.
Then *Sources & uses* as the `.su` visual (buyout / CV), and the 3–6 key findings that matter (`ol.findings`), leading
with where the sponsor may be overestimating. Terms the materials don't give: "not disclosed", and say which matter.

**2 · Company Overview** — summarised from the materials, verified on the web: what the company does in plain words,
service lines / products and what each does, how the work is delivered day to day, customers and end markets, footprint
(sites, regions, headcount), history and scale. *Management* table (Person · Role · Tenure · Background · Read) with a
`.gap` callout; *The sponsor* (who, fund, strategy, where they invest, track record — CV: also the lead secondaries
investor; VG: founders and the lead investors); *Ownership & transaction history* table (buyout / CV: each owner, EV,
multiple; VG: every round with pre / post-money, leads).

**3 · Industry Primer and Independent Market Assessment** — first the primer (how the industry works from first
principles, an `.explain` analogy, a `.flow` diagram, a service / product ladder, a worked unit-economics example), then
the **independent market assessment**: every material market claim in the materials (size, growth rate, fragmentation,
margin trend, tailwinds) set against reliable external sources in a table — Claim · Materials say · Independent evidence ·
Verdict (Confirmed / Partly supported / Not supported) — then a neutral read on competition intensity, how many sponsors
chase these assets and at what multiples (valuation hype), and the **risks to the industry** (structural threats,
regulation, technology / AI, cyclicality). Say plainly where the manager has oversold it.

**4 · Business Model, Value Chain, Competitive Landscape and Exitability** — how it earns money (revenue model, pricing,
contract length, mix); the `.chain` value-chain strip with margin and pricing power per layer; named customers as
`.cards`; suppliers and their leverage; the competitor table (Company · Owner / sponsor · Scale — revenue, sites,
customers · Latest deal or valuation · How it differs) from the IM, any data-room market study and the web; market
sizing anchored on the materials and cross-checked externally. Then **Exitability**: who buys this at exit (strategics,
sponsors, IPO — VG: IPO window, strategic M&A appetite, secondary market), recent exits in the sub-sector with their
multiples, and how big the buyer universe is at the exit size the plan assumes.

**5 · Value Creation Plan** — open with **3–4 numbered points on what drives the returns**, biggest first, each with its
share of the value creation: organic growth, bolt-on M&A, a transformational acquisition, EBITDA-margin improvement,
deleveraging, multiple expansion (VG: ARR growth, milestones, multiple, dilution). Then the bridge from today's EBITDA to
exit EBITDA (SVG or table) and a short neutral read on each lever — the company's record, the sponsor's record running
the playbook, and the market (e.g. "assumes $40m of acquired EBITDA vs $12m bought in the last three years"). Concise.

**6 · Financials and Business Plan** — ONE table with the history and the plan side by side: historical years (FY-3 …
LTM) replicated EXACTLY from the materials, then the projections year by year to the exit year, from the IM or the
model and tied between them (`<table class="bp">`, plan columns `<th class="plan">` / `<td class="plan">`, exit year
marked). Rows as the sponsor presents them: revenue, growth (organic vs M&A), gross profit and margin, adjusted EBITDA and
margin (and reported), net profit where given, capex, free cash flow and cash conversion, net debt and leverage (VG:
revenue / ARR, growth, gross margin, burn, cash, runway). Then **the cases** — every case in the materials in one compact
table (revenue / EBITDA / margin at exit, exit multiple): the sponsor case, the management case and any other — in a CV
the lead secondaries investor's case, usually a haircut to the sponsor's; a lender or vendor-DD case — with who prepared
each and why they differ. Then *History vs plan* and a *Reconciliation* note only for material gaps.

**7 · Valuation Analysis** — entry valuation on adjusted and reported EBITDA (CV: price vs NAV and the implied multiple;
VG: EV / ARR, EV / gross profit and the valuation evolution across rounds as an SVG chart or a short table); trading
comps and transaction comps (≤ 8 names each: Company / deal · Date · Multiple · Read-across), the implied band, where the
price sits in it and our view of fair value.

**8 · Returns Analysis and Independent Sensitivities** — **returns across scenarios**: one table of every case as the
materials present it (exit year, exit EBITDA, exit multiple, gross MOIC and IRR, net to ADCG after fees and carry where the
terms allow). Then **What looks overstated** — `<div class="overstated"><b>What looks overstated</b><ol>…</ol></div>`: 3–6
crisp sense-checks with numbers on both sides and a one-word verdict each (plausible / stretched / overstated), e.g.
"revenue +15% p.a. in the plan vs the market at ~5% — implies sustained share gains"; "$140m of acquired EBITDA planned vs
$70m bought to date"; "margin +400bp vs peers flat"; "exit multiple above entry with no re-rating evidence". Not clumsy —
only what matters. Then the **ADCG independent review** — clearly labelled as ours
(`<div class="indep"><b>ADCG independent review</b> …</div>`, figures tagged ESTIMATE): the assumptions we would change
and why, our case, and **sensitivity tables** built from the model — e.g. exit multiple × exit EBITDA (or EBITDA CAGR) →
MOIC and IRR, with the sponsor base case and our case highlighted; plus a downside showing what has to go wrong to lose
money. VG: exit value needed for 3× net of dilution, and MOIC under different exit valuations and dilution paths. Never
alter a historical number.

**II · Investment Pros and Cons** — the heart of the memo: two stacked numbered lists — all pros first
(`<h3>Pros</h3><ol class="pc-list pros">`), THEN all cons (`<h3>Cons</h3><ol class="pc-list cons">`); 7–10 each. Each
item = bold claim, 2–4 sentences of evidence (numbers, named customers / competitors / deals, tags), "Why it matters:",
conviction / severity tag. Then *Net assessment*. Then `<h3>Key risks — what the materials don't tell you</h3>`: a
two-sentence bottom line and `<ol class="risk-list">` of 6–10 numbered paragraphs led by the risk area in bold, drawn from
the three layers of the risk review — the risks the sponsor flags, those found across all the materials, and those only
the independent web review found (regulatory pressure, disruption incl. AI, interest rates and the capital structure,
macro, geopolitics and tariffs, input costs and labour) — each with its second- / third-order effects, whether the
sponsor flagged it, and what would mitigate it; close with how sponsors have fared in this theme (named precedents). No
risk score.

**III · ADCG <framework> Deal Scoring** — the app puts a score panel right under the banner (`.sc-head`: total score and
band on the left; the GP tier — sponsor, lead secondaries investor, or the Marquee GP Index — the framework score before
ADCG preferences and the deal-specific factors on the right); do not repeat it. Then one `<h2>III.n · <Section></h2>` per
section of the scorecard, in order — the framework sections (scaled to 90%) and, when present, **Deal-specific factors**
(10%: 2–4 factors picked for this deal's sub-sector — e.g. pharma: patent cliff; software: net revenue retention — opening
with why they were chosen):
a one-line lead with the section score and weight exactly as computed (e.g. "Scores **7.4 / 10** · weight 25%"), a
compact table Criterion · Score · Why (plain-English reason from the scorecard rationales, with the key evidence), and a
line on what would move the score. GP-tier criteria say which tier list the firm sits on. No weight arithmetic, no VJR or
Marquee point maths. The app adds the last sub-section, *Framework Scoring Summary* (score bars + overall, ADCG
preferences adjustment), itself.

**IV · Recommendation and Next Steps** — open with the `.tldr` (ADCG score and band, the one-line stance, the one thing
that matters most). Then balanced and neutral, about half a page: the leaning in one bold line with the ticket / price
stance; *Why* (2–3 bullets weighing both sides); *What would change our view* (≤ 3); *Next steps* — the confirmatory
diligence and the decision timetable (2–5 bullets); *What we don't know yet*. No gates, kill criteria or Contrarian note.

**A.1 · Sources and References** — the data-room documents relied on (file name · type · what it was used for), then the
external sources grouped by topic (industry, competitors, comps & precedents, people, news), as links.
**A.2 · Definitions and Methodology** — the source tags (HARD / IM / MGMT / ESTIMATE), metric definitions used (adjusted vs
reported EBITDA, net leverage, MOIC, IRR, NAV, ARR …), how the ADCG framework scores (1–10 criteria, weighted sections,
bands, ADCG preferences ±0.5, no risk score), and how the independent review and sensitivities were built.

## Risk
No risk score anywhere (no 0–100 number, no risk register score). Risks are highlighted — ranked, severity /
likelihood labels, evidence, mitigant, diligence question.

## Length & tables
Aim for ~20–28 pages with real substance — depth comes from analysis, numbers and named evidence, not repetition. Use
tables where readers compare numbers across rows (financials, plan, sources & uses, comps, management, ownership
history); everything else is connected prose with the key point in bold. Never two tables for the same information.

## Voice
Write so it flows: each section opens with a short lead and ends with what it means for the decision; link
sections ("which is why the plan leans on M&A — section 5"). Never mechanical, never a list of the deal lead's rules.
Short declarative sentences. Numbers in every paragraph. Say what a fact *means* for the decision. Name names — people,
customers, competitors, sponsors, deals. No marketing adjectives copied from the IM. When the IM and the world disagree,
say so and say which you believe.
