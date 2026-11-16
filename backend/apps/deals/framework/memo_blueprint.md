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
**5 · Financials, valuation & valuation evolution** — concise. Open with ONE sentence that states the current
valuation (post-money, date, lead) and the multiple it implies. Then ONE compact table of the known operating numbers
(≤ 6 rows: revenue / ARR, growth, gross margin, burn, bookings or backlog — tagged). The valuation history as ONE short
table (Round · Date · Post-money · What the business looked like then — ≤ 6 rows) or the SVG bar chart, not both.
Comparables as ONE compact table (≤ 6 names: Company · Valuation · Multiple · One-line read-across). Exit maths and fair
value in a short paragraph each — no further tables.
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
**5 · Financials, business plan & valuation** — this is where the IM leads, but keep it concise. Open with ONE
sentence on the valuation (EV, multiple on adjusted and reported EBITDA). Then:
- ONE financials table: actuals FY-2 … LTM and the management plan to the exit year side by side (≤ 8 rows: revenue,
  growth, adj. EBITDA, margin, capex, cash conversion, net debt / leverage) — tagged IM / QoE; mark the exit year.
- *Where the growth comes from* — a short paragraph (or a small bridge if it really helps): organic, price, margin /
  cost savings, new lines, M&A; how much is contracted or evidenced.
- *Plan vs reality* — a paragraph; say plainly when the plan looks achievable.
- *Reconciliation* — only material gaps between documents, as a few sentences (a table only if there are 3+ gaps).
- *Comparables* — ONE compact table (≤ 6 names: Company / deal · Multiple · One-line read-across) and the implied band.
- *Returns & exit maths* and *Fair value* — a short paragraph each.
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
Aim for ~12–16 pages. Use a table only where the reader genuinely compares numbers across rows (financials, comps,
funding history, management); everything else is short paragraphs with the key point in bold. Never more than one
table for the same information, and keep tables ≤ 8 rows.

## Voice
Short declarative sentences. Numbers in every paragraph. Say what a fact *means* for the decision. Name names — people,
customers, competitors, sponsors, deals. No marketing adjectives copied from the IM. When the IM and the world disagree,
say so and say which you believe.
