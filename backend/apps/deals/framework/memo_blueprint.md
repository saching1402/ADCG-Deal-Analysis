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
- **Transaction, historical financials, sources & uses, debt terms**: **replicate from the materials exactly** — these
  are hard facts and the materials are the source of truth. Never alter a backward-looking number.
- **Business plan**: from the materials (model, IM), then tested — history vs plan, each driver checked against the
  company's record and the market (neutral, evidence-based feedback). Our own alternative case may change assumptions
  (tag ESTIMATE); it never changes the actuals.

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
- Key-facts grid for the transaction: `<div class="kf"><div><span>Enterprise value</span><b>$531m</b><em>12.7× LTM adj. EBITDA</em></div>…</div>`
- Severity `s-high|s-medhigh|s-med|s-low`, conviction `<span class="conv">MED-HIGH</span>`, pros/cons `.pc`,
  caveats `.caveat`, TL;DR `.tldr` — as in the CSS cheatsheet.

## Venture / Growth memo — sections and what each must contain
**1 · Company overview** — summarised from the company's materials (deck, data room) and verified on the web — 2–3
paragraphs: what it builds, for whom, in plain words, its own tagline, founding date/place,
where it is today (sites, factories, product status, headcount range with conflicting sources). Identity confirmation if
the name is ambiguous. Then:
- *Founders & management* table: Person · Role · Background (prior companies, exits, controversies) · Read (one-line
  judgement: strength, gap, reference-check item). Include board members of note. Then a `.gap` callout for missing
  roles (CFO, manufacturing, sales lead) relative to what the plan now requires.
- *Funding & valuation history* table: Round · Date · Amount · Pre / Post · Lead(s) · Participants · Tag (HARD/ESTIMATE)
  — every round from seed, a Total row, and a note where sources disagree.
**2 · Industry primer** — *What problem it solves, from first principles* (the binding constraint,
why now), an `.explain` analogy box, a two-lane `.flow` diagram (the incumbent way vs the company's way, with time and
"best at / weak at"), a *product ladder* table (Unit · Size/spec · Typical use · Example customer), the software layer in
one paragraph, a *worked example* table (what one real order is worth and who captures each layer: Layer · $/unit ·
$ on this order · Who captures it · Indicative GM) followed by "What this means" in bold, and *How competitors are built
differently* (Player · Architecture/model · What it optimises · Example use · Where it struggles).
**3 · Business model, value chain & competitive landscape** — `.chain` strip with margins per layer and the squeeze line;
*Named customers — what they need* as `.cards` (3–6, each with the need and the fragility, e.g. "depends on project
finance"); *Named suppliers / partners* table (Supplier · What it buys · Leverage); *Competitor table (latest marks)*
(Company · Status / latest valuation · Scale signal · How it differs); *Why strategics back the field / the incumbent
threat* (paragraph); *Market sizing in the right units* (physical units × capturable $/unit, not a headline TAM);
*First-principles test: does the model deserve its multiple?* (which multiple class it deserves and what the price assumes).
**4 · Latest fund raise & key findings** — the round as a `.kf` key-facts grid (round, amount, pre / post-money, leads,
new strategic investors, existing re-ups, primary / secondary split, instrument and key terms — preference, ratchets,
pro-rata — and use of proceeds, replicated from the materials), then ONLY the findings that matter (3–6), each with a
bold claim, numbers and a severity / conviction tag — especially where the company or lead investor may be overstating.
**5 · Financials, valuation & business plan** — the numbers story. Open with the current valuation (post-money, date,
lead) and the multiple it implies. Then:
- *Historical operating numbers*, replicated exactly from the materials (revenue / ARR, growth, gross margin, burn,
  cash, bookings / backlog by year or quarter) — what the company has actually done.
- *The plan* — what management says happens next (revenue, margins, burn, milestones to the next round / exit) and what
  it requires (hires, capacity, capital); historical growth vs planned growth, and whether that is credible given the
  market and peers — neutral, evidence-based.
- *Valuation evolution* — every round's post-money against the fundamentals at the time (SVG bar chart or a short
  table, not both) and what the step-up says.
- *Comparables* — trading and private marks (≤ 8 names: Company · Valuation · Multiple · Read-across), the implied band.
- *Exit maths and fair value* — a paragraph each, with numbers.
**6 · ADCG-VG scoring** — written by the app: the section score bars only (criteria detail, weights rationale,
Marquee GP Index and VJR live in the app's Scorecard tab).
**7 · Verdict** — `.tldr` with 3–4 bold-led paragraphs: ADCG score/band and the one-line stance; the business in one
breath and where it sits in the value chain; the one thing that matters most; the action.
**8 · Pros & Cons (IC voice)** — the heart of the memo, written as two stacked numbered lists — ALL pros first
(`<h3>Pros</h3><ol class="pc-list pros">`), THEN all cons (`<h3>Cons</h3><ol class="pc-list cons">`); never side by side. 7–10 pros and 7–10 cons. Each item = bold claim,
2–4 sentences of evidence (numbers, named customers / competitors / deals, tags), "Why it matters:" (returns,
downside, exit), conviction / severity tag and dimension. Pros by dimension (industry attractiveness, market position,
revenue visibility, syndicate, regulatory/sovereign, capital efficiency, valuation, exit); cons severity-ordered
(historical financials, competition, value-chain position, execution, valuation, customer quality, governance /
key-person, price discovery, M&A). Then *Net assessment* — which side wins and why.
**9 · Recommendation** — balanced and neutral, about HALF A PAGE. Not a rigid call: state the leaning (e.g. "On
balance we lean towards investing, provided…", or "This looks hard to support at the current price unless…") in one
bold line with the ticket / price stance if known; *Why* (2–3 plain bullets that weigh both sides); *What would change
our view* (≤ 3 plain bullets); *Next step* (one sentence). A short *What we don't know yet* line or two. No gates, no
kill criteria, no Contrarian note.
**10 · Key risks** — from the independent risk review, written like Pros & Cons, NOT as a table: a two-sentence
bottom line, then `<ol class="risk-list">` of 6–10 numbered paragraphs, most material first. Each starts with the risk
area in bold (e.g. **Valuation —**, **Technology —**, **Financing & dilution —**, **Competition —**, **Regulation —**),
then 2–4 plain sentences: what could go wrong and why (evidence, named examples), how likely and how severe in words,
whether the materials disclose it, and what would mitigate it or what to ask. Close with one short paragraph on how
sponsors have fared in this theme (named precedents). Up to a page. No risk score.

## Buyout memo — same storytelling, plus the IM's business plan
**1 · Company overview** — what the business does in plain words, summarised from the materials (IM / SIM /
management presentation) and verified on the web: service lines / business units and what each does, how the work is
delivered day to day, customers and end markets, footprint (sites, regions, headcount), history and scale, market
position. Then:
- *Management* table: Person · Role · Tenure · Background · Read; board and sponsor operating partners; `.gap` for
  missing or new-to-role executives relative to the plan.
- *The sponsor* — who they are, fund and vintage, strategy and where they invest, track record in the sector (named
  deals and outcomes), from the materials first, checked on the web. CV: the lead secondaries investor too.
- *Ownership & transaction history* table: Date · Event (founding, PE entry, add-ons, recap, CV) · Owner(s) · EV ·
  EV/EBITDA · Tag — the multiple each owner paid, so the reader sees the multiple evolution.
**2 · Industry primer** — how the industry works from first principles (who pays, why, what drives demand,
cyclicality / seasonality, regulation), an `.explain` analogy, a `.flow` of how a job / contract / site makes money vs
the alternative model, a *service / product ladder* table, a *worked unit-economics example* (one site / contract /
customer: revenue · cost lines · margin · payback). Then *Is this a good industry to own?* — the materials' market
claims (size, growth, fragmentation) set against reliable external sources, with a clear neutral read: growth that
holds up vs claims that don't, intensity of competition, how many sponsors are chasing the same assets and at what
multiples (valuation hype), structural threats.
**3 · Business model, value chain & competitive landscape** — `.chain` with margin and pricing power per layer; named
customers as `.cards` (need, concentration, contract terms); suppliers table with leverage; competitor table (Company ·
Owner / sponsor · Scale: latest revenue, sites / locations, customer base · Latest deal or valuation · How it differs) —
start from the IM's names and any market study in the data room, then research beyond them (other sponsor-backed
platforms, listed peers, new entrants); market sizing anchored on the materials and cross-checked externally; who else is
running the same buy-and-build playbook; valuation evolution of the asset or its closest peers where available.
**4 · The transaction & key findings** — the hard facts first, replicated from the materials:
- `.kf` key-facts grid: structure (buyout · co-invest · single-asset CV · multi-asset CV · minority), enterprise value,
  LTM EBITDA (adjusted and reported), EV/EBITDA on both, net leverage, equity cheque, CV size and unfunded commitment
  (CVs), ADCG ticket, sponsor and fund.
- *Debt package* — instruments, quantum, pricing (margin / coupon, floors, OID), maturity, covenants (or cov-lite),
  interest coverage (EBITDA / cash interest) if available.
- *Sources & uses* — replicated from the materials as the `.su` visual (and a capital-structure bar if it helps).
- Governance, co-invest rights, fees & carry, rollover, timetable — a short paragraph.
Then *Key findings* — only the ones that matter (3–6), each a bold claim with numbers and a severity / conviction tag;
lead with where the sponsor may be overestimating (EBITDA add-backs, pipeline, synergies, exit multiple).
**5 · Financials, valuation & business plan** — the most important analytical section; the historical financials and
the business plan are presented together.
- Open with the valuation in one sentence (EV, multiple on adjusted and reported EBITDA).
- *Historical financials* — replicated exactly from the materials (they are the source of truth for actuals): FY-3 … LTM
  revenue, growth (organic vs M&A), gross profit and gross margin, adjusted and reported EBITDA and margin, add-backs,
  capex, free cash flow and cash conversion, net debt and leverage. Tag IM / QoE / Model; if documents disagree, show
  both and say which is right. Follow with a short paragraph on how the company has actually performed.
- *The business plan* — a high-level overview of what the company will do over the hold to generate the returns: the
  plan table year by year to the exit year (revenue, growth, EBITDA, margin, capex, cash conversion, leverage), hold
  period, exit year, exit multiple and returns case. Mark the exit year.
- *History vs plan* — historical CAGR vs planned CAGR, margin path vs history (e.g. "grew ~20% p.a. FY21–24, the plan
  assumes 14% — reasonable"); compare against any earlier business plan in the materials.
- *How the plan gets met* — the bridge from today's EBITDA to exit EBITDA by driver (organic volume, price, margin /
  cost savings, new service lines, M&A and its spend) as an SVG bridge or table, from the materials; then a neutral,
  evidence-based read on each driver from the company's record and the market (e.g. "assumes $40m of acquired EBITDA vs
  $12m bought in the last three years"; "data-centre demand drives 30% of growth — power and permitting constraints
  are a real brake").
- *Our case* — where we would change assumptions and what that does to EBITDA and returns (tag ESTIMATE).
- *Reconciliation* — material gaps between documents only.
- *Comparables* — trading AND transaction comps (≤ 8 names: Company / deal · Multiple · Read-across), implied band;
  valuation evolution of the asset where available.
- *Returns & exit maths* and *Fair value* — a paragraph each, with numbers.
**6 · ADCG scoring** — written by the app: the section score bars only (detail lives in the Scorecard tab).
**7 · Verdict** — as for VG.
**8 · Key risks — what the materials don't tell you** — as for VG section 10: numbered paragraphs with the risk area
in bold, no table; say for each whether the IM discloses it, understates it or omits it; close with a short paragraph
on the sub-sector PE track record (named precedent deals and how they ended) and the theme verdict. Up to a page.
**9 · Pros & Cons (IC voice)** — as for VG (7–10 each, evidence, "Why it matters", tags, Net assessment), covering all
eight mandatory dimensions; cons include the top independent risks.
**10 · Recommendation** — as for VG: balanced and neutral, about half a page.

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
