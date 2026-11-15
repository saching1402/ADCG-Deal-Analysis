# IC memo blueprint — the house format (modelled on the Armada VG memo, Nov-26)

The memo reads like a **deep-research report written by an investor who has understood the business from first
principles**, then tested the seller's story against the world. Storytelling (what the company does, the industry, the
technology, the value chain, customers, competitors, the market) comes from **independent research**; the information
memorandum (IM / CIM) supplies the **numbers only the company has** (actuals, plan, deal terms, management, exit case).

## Source tags (instead of page numbers)
Tag figures with a small pill, never with page references in running text:
`<span class="src hard">HARD</span>` public / verified (filings, company release, regulator, credible press)
`<span class="src im">IM</span>` from the information memorandum, model, QoE or other data-room file
`<span class="src mgmt">MGMT</span>` management / sponsor claim with no independent support (percentages, targets)
`<span class="src est">ESTIMATE</span>` our triangulation. Ranges where sources disagree, and say why.
A page reference is allowed only where a figure is contested between documents (e.g. in the reconciliation table).

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
- Severity `s-high|s-medhigh|s-med|s-low`, conviction `<span class="conv">MED-HIGH</span>`, pros/cons `.pc`,
  caveats `.caveat`, TL;DR `.tldr` — as in the CSS cheatsheet.

## Venture / Growth memo — sections and what each must contain
**1 · Company overview** — 2 paragraphs: what it builds, for whom, in plain words, its own tagline, founding date/place,
where it is today (sites, factories, product status, headcount range with conflicting sources). Identity confirmation if
the name is ambiguous. Then:
- *Founders & management* table: Person · Role · Background (prior companies, exits, controversies) · Read (one-line
  judgement: strength, gap, reference-check item). Include board members of note. Then a `.gap` callout for missing
  roles (CFO, manufacturing, sales lead) relative to what the plan now requires.
- *Funding & valuation history* table: Round · Date · Amount · Pre / Post · Lead(s) · Participants · Tag (HARD/ESTIMATE)
  — every round from seed, a Total row, and a note where sources disagree.
**2 · Theme, industry & technology primer** — *What problem it solves, from first principles* (the binding constraint,
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
**4 · Latest fund raise & key findings** — round table (Item · Detail · Source tag: round, amount, valuation, leads,
new strategic investors, existing re-ups, primary/secondary, paired announcements), then 6–9 numbered findings each with
a bold claim, numbers and a severity / conviction tag.
**5 · Financials, valuation & valuation evolution** — *What is known about the operating numbers* (Metric · Value · Tag),
*Comparables* (Comp · Type · Valuation · Multiple · Read-across, public and private, plus M&A precedents), an SVG bar
chart of post-money by round, *Valuation evolution vs fundamentals at each mark* table (Mark · Post-money ·
Fundamentals at the date · Step-up vs prior), the VJR sentence, *Exit maths* (what exit value and revenue a 3× net
needs after dilution, and the more plausible strategic exit), and *Fair value on current evidence* (a range).
**6 · ADCG-VG scoring** — written by the app: the section score bars only (criteria detail, weights rationale,
Marquee GP Index and VJR live in the app's Scorecard tab).
**7 · Verdict** — `.tldr` with 3–4 bold-led paragraphs: ADCG score/band and the one-line stance; the business in one
breath and where it sits in the value chain; the one thing that matters most; the action.
**8 · Pros & Cons (IC voice)** — the heart of the memo: `.pc` with 7–10 pros and 7–10 cons. Each item = bold claim,
2–4 sentences of evidence (numbers, named customers / competitors / deals, tags), "Why it matters:" (returns,
downside, exit), conviction / severity tag and dimension. Pros by dimension (industry attractiveness, market position,
revenue visibility, syndicate, regulatory/sovereign, capital efficiency, valuation, exit); cons severity-ordered
(historical financials, competition, value-chain position, execution, valuation, customer quality, governance /
key-person, price discovery, M&A). Then *Net assessment* — which side wins and why.
**9 · Recommendation** — simple, for any audience: the decision in one bold line (Invest · Invest, subject to a few
confirmations · Pass) with ticket / price stance; *Why* (3 plain bullets); *What we still need to confirm* (≤ 3);
*Next step* (one sentence); *What we don't know yet* (short list of estimates and gaps). No gates, no kill criteria,
no Contrarian note.
**10 · Independent risk review** — from the risk-review stage: bottom line, risk table, theme track record.

## Buyout memo — same storytelling, plus the IM's business plan
**1 · Company overview** — what the business does in plain words (from research, not the IM's marketing), history,
footprint, scale (sites, customers, headcount), market position. Then:
- *Management* table: Person · Role · Tenure · Background · Read; board and sponsor operating partners; `.gap` for
  missing or new-to-role executives relative to the plan.
- *Ownership & transaction history* table: Date · Event (founding, PE entry, add-ons, recap, CV) · Owner(s) · EV ·
  EV/EBITDA · Tag — the multiple each owner paid, so the reader sees the multiple evolution.
**2 · Industry & business primer** — how the industry works from first principles (who pays, why, what drives demand,
cyclicality/seasonality, regulation), an `.explain` analogy, a `.flow` of how a job / contract / site makes money vs the
alternative model, a *service / product ladder* table, a *worked unit-economics example* (one site / contract /
customer: revenue · cost lines · margin · payback) and *How competitors are built differently*.
**3 · Business model, value chain & competitive landscape** — `.chain` with margin and pricing power per layer; named
customers as `.cards` (need, concentration, contract terms); suppliers table with leverage; competitor table (Company ·
Owner / sponsor · Scale · Latest deal or valuation · How it differs) — start from the names in the IM but research beyond
them (other sponsor-backed platforms, listed peers, new entrants); market sizing in the right units; who else is running
the same buy-and-build playbook.
**4 · The transaction & key findings** — deal table (Item · Detail · Tag: structure / type, EV, EV/EBITDA on adjusted
and reported, equity cheque and ADCG ticket, leverage and debt package, sponsor and fund, governance / co-invest
rights, fees & carry, timetable), then 6–9 numbered findings with severity / conviction tags.
**5 · Financials, business plan & valuation** — this is where the IM leads:
- *Historical financials* table, actuals FY-3 … LTM: revenue, growth (organic vs M&A), gross margin, adj. EBITDA and
  margin, reported EBITDA, add-backs, capex, cash conversion, net debt — tagged IM / QoE.
- *Management business plan* table FY+1 … FY+5 (the IM's own projections; mark the hold period and exit year).
- *Where the growth comes from* — a value-creation bridge (SVG bar or table) from entry EBITDA to exit EBITDA:
  organic volume, price, margin / cost savings, new business lines, M&A (with the M&A spend), and what share of the
  bridge is already contracted or evidenced.
- *Plan vs reality* — the plan's growth and margin against history and peers; our haircut case if needed (say plainly
  when the plan looks achievable).
- *CIM reconciliation* table (Metric · IM · Other file · Gap · Comment).
- *Comparables*: trading comps and precedent transactions (named, with multiples), the implied band, and the multiple
  evolution across owners.
- *Returns & exit maths* — sponsor case IRR/MOIC, exit multiple and year, what has to be true; the downside case.
- *Fair value on current evidence*.
**6 · ADCG scoring** — written by the app: the section score bars only (detail lives in the Scorecard tab).
**7 · Verdict** — as for VG.
**8 · Independent risk review — what the materials don't tell you** — bottom line, risk table (severity, likelihood, in
IM yes/understated/no, mitigant, diligence question), the sub-sector PE track-record table and the theme verdict.
**9 · Pros & Cons (IC voice)** — as for VG (7–10 each, evidence, "Why it matters", tags, Net assessment), covering all
eight mandatory dimensions; cons include the top independent risks.
**10 · Recommendation** — as for VG: simple decision, why, what to confirm, next step, what we don't know yet.

## Risk
No risk score anywhere (no 0–100 number, no risk register score). Risks are highlighted — ranked, severity /
likelihood labels, evidence, mitigant, diligence question.

## Voice
Short declarative sentences. Numbers in every paragraph. Say what a fact *means* for the decision. Name names — people,
customers, competitors, sponsors, deals. No marketing adjectives copied from the IM. When the IM and the world disagree,
say so and say which you believe.
