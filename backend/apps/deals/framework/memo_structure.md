# IC Memo Structure, Mandatory Dimensions & CSS Cheatsheet

Companion to SKILL.md. The scorecard fragment is injected first (at `{{SCORECARD}}`); this file
covers the **prose body** that goes at `{{BODY}}`.

## Section order (operating company / asset / CV)

1. **TL;DR** — 3 bold bullets: the verdict; the model/edge in one line; the single gating item.
2. **Key Findings** — 6–9 numbered, each a headline claim + number + sourcing tag (HARD/ESTIMATE)
   + severity tag. Identity confirmation first if the name is ambiguous.
3. **Details:**
   - Company summary & genesis (founding, owners, HQ, footprint, scale, leadership).
   - **Business model & value-chain position** — revenue mechanics AND cost/vendor mechanics;
     where the margin sits; who holds pricing power at each node; working capital; seasonality;
     who bears the key risk. A model-comparison table vs the main alternative model helps.
   - **Historical financials** — revenue & growth split **organic vs M&A**, margins, EBITDA, cash
     conversion / capex intensity, leverage. Mark estimates. A small table is expected.
   - **Valuation** — a **named-comps table** (trading AND transaction) with the implied band and
     the premium/discount reasoning. This is the centrepiece of the valuation view.
   - **Deal/CV rationale** — for a CV: why the sponsor is launching it (benign vs skeptical
     reading), the price-setting conflict, the mark.
4. **Pros & Cons (IC voice)** — two lists, as if the committee is deliberating. Every Con a
   severity tag, ordered highest-first; every Pro a conviction tag. **Tag each bullet with the IC
   dimension it addresses.**
5. **Recommendation** — a **staged diligence plan with explicit gates and kill criteria** (each
   stage: what to verify, the gate, the number/finding that makes you pass). End with the valuation
   anchor and structuring asks.
6. **Caveats** — enumerate data gaps, undisclosed terms, unverified sources.
7. **Contrarian note** — loaded/not-loaded, what it added, reconciliation to the live ADCG app.

**Fund/GP variant:** swap Business model → strategy/economics/fee-layering; Financials → AUM &
track record by vintage (DPI/TVPI/MOIC/net IRR vs benchmark); Ownership → GP ownership, key-person,
LPA terms, **conflicts of interest**; Competition → named peer managers. Demand GIPS-compliant,
vehicle-level track records.

## Mandatory Pros/Cons dimensions (the floor, all eight must appear)

1. **Industry attractiveness** — secular tailwinds/headwinds, TAM, growth; is the market itself a
   tailwind or must growth come from share gains?
2. **Competition** — named rivals, which flanks, and whether the target benefits from or is hurt by it.
3. **M&A / roll-up potential** — is the sub-segment suited to buy-and-build? Multiple arbitrage?
   Are other sponsors running the same playbook (name them) — optionality or asset competition?
4. **Revenue visibility** — recurring vs transactional; contract tenure; renewal/re-bid; NRR. Don't
   accept a "recurring" label at face value.
5. **Valuation** — expensive/attractive vs **named** comps, with the implied band and premium/
   discount reasoning. If EBITDA is unverified, say it's un-anchorable and gate on QoE.
6. **Regulatory tailwinds/headwinds** — the specific statutes/programs that help or bite; net direction.
7. **Historical financial performance** — revenue, growth (organic vs M&A), EBITDA, margins to the
   extent verifiable; mark estimates.
8. **Market position** — genuine market leadership vs niche/category leadership in a fragmented market.
Add target-specific points (weather, vendor dependency, key-man, capital intensity, US-expansion
trap, CV conflict) alongside these. If a dimension is genuinely immaterial, say briefly why.

## CSS-class cheatsheet (write the body with these — they match the shell)

- TL;DR box: `<div class="tldr"><ul><li>…</li></ul></div>`
- Section header: `<h2>Bottom line</h2>` (mono, oxblood, rule above). Sub-head: `<h3>…</h3>`.
- Key findings: `<ol class="findings"><li>…<span class="sev s-high">HIGH</span></li></ol>`
- Severity tags: `s-high` (HIGH), `s-medhigh` (MEDIUM-HIGH), `s-med` (MEDIUM), `s-low` (LOW).
  Conviction tag: `<span class="conv">HIGH</span>`.
- Tables: plain `<table>`; highlight the target row with `<tr class="hl">`; numeric cells `td.num`.
- Pros/Cons block:
  ```html
  <div class="pc">
    <div class="col pros"><h4>▲ Pros (conviction-tagged)</h4><ul>
      <li><span class="dim">Market position · conviction HIGH</span>… <span class="conv">HIGH</span></li>
    </ul></div>
    <div class="col cons"><h4>▼ Cons (severity-tagged, ordered)</h4><ul>
      <li><span class="dim">Leverage</span>… <span class="sev s-high">HIGH SEVERITY</span></li>
    </ul></div>
  </div>
  ```
- Staged gate: `<div class="gate"><div class="stage">Gate 1 — …</div><p>Verify: … <span class="kill">Kill if:</span> …</p></div>`
- Caveats: `<div class="caveat"><strong>Treat as ESTIMATE…</strong> …</div>`
- Keep the body as HTML fragments only (no `<html>/<head>/<body>` — the shell supplies those).

## Copyright / sourcing discipline

Paraphrase; never paste source paragraphs. Short attributed quotes only (<15 words), one per
source. Attribute inline in plain text ("per Davy", "RBC note", "The Grocer") — the artifact can't
use chat citation tags. Never invent attributions; omit if unsure.
