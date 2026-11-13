---
name: "adcg-venture-growth-skill"
description: "ADCG Venture Growth Skill — IC memo + Theme/Valuation-Evolution/Investor-Syndicate/Company/Competition scorecard + venture risk register (HTML + PDF) for Seed–pre-IPO rounds, venture co-invests and startup secondaries. Buyouts/CVs: use the ADCG Buyout Skill (adcg-score-risk-package)."
---

# ADCG Venture Growth Skill

The venture/growth twin of the **ADCG Buyout Skill** (`adcg-score-risk-package`, which stays the skill for **buyouts, co-investments
in sponsor-controlled companies, and continuation vehicles**). Use THIS skill whenever the target is a
venture- or growth-stage company raising (or recently raised) a priced round: Seed → Series A–F → pre-IPO,
including venture co-invests and secondaries in such companies. If unsure which skill applies: positive
EBITDA + leverage + sponsor control → buyout skill; otherwise this one.

Everything about the deliverable is the same as the buyout skill — institutional IC memo, HTML artifact +
PDF, skeptical non-promotional stance, HARD vs ESTIMATE tagging, named comps, severity/conviction tags,
staged gates with kill criteria, Contrarian-app check, reconciliation to the live ADCG app, ledger + log
updates. **What changes is the scoring lens and the risk model** (below).

## Dependency

This skill reuses the buyout skill's shell, assembler, PDF renderer and scoring engine. Locate it:
```bash
P=$(dirname $(dirname $(find / -path '*/scripts/adcg_scorecard.py' 2>/dev/null | head -1)))
```
If `$P` is empty, tell the user the ADCG Buyout Skill (`adcg-score-risk-package`) must be installed and stop.
Also read `$P/references/memo-structure.md` for the CSS-class cheatsheet only (NOT its section order).

## Core stance

- **Educate first, then judge.** Overview and primer first, scoring after, verdict after scoring.
- **Always teach with worked numeric examples**, a plain-English analogy, and comparison tables of how
  named competitors differ (architecture/product, what each optimises, example use, where it struggles).
- **Grade everything** (severity on risks/cons, conviction on pros). **Separate fact from inference**
  (HARD = filings/Companies House/Delaware/company release; ESTIMATE = press/Bloomberg/Sacra/our maths).
- **Rebuild the valuation from primary filings where possible** (Companies House SH01 share prices ×
  statement of capital; Delaware/Form D) and reconcile to the press headline; flag fully-diluted gaps and
  in-round price dispersion.
- **Valuation must be earned**: a big step-up without matching ARR/revenue/milestone growth is a red flag.
- Push back on hype. The user wants the critical view.

## Mandatory memo order (non-negotiable)

1. **Company overview** — genesis, founders & management (gaps flagged), HQ/footprint, headcount,
   full **funding & valuation history table** (round, date, amount, pre/post, leads, participants, HARD/EST).
2. **Theme, industry & technology primer** — first-principles explanation of how the product and its
   theme work, with worked numbers, analogies, inline SVG visuals, and a competitor-architecture table.
3. **Business model, value chain & competitive landscape** — how value is captured; value-chain diagram
   with named players, indicative margins and who holds pricing power; 2–3 named customers (needs);
   4–5 named suppliers (terms); competitor table with latest valuations; incumbent/hyperscaler threat and
   why strategics back the field; market sizing in the right units; first-principles multiple test.
4. **Latest fund raise & key findings** — the most recent round in full (amount, pre/post, leads,
   participants, filings vs press, tranches, secondary component), then 6–9 tagged findings.
5. **Financials, valuation & valuation evolution** — ARR/revenue/bookings history; named private AND
   public comps table; ARR/revenue multiples; **valuation-evolution chart/table (each round vs fundamentals
   at that date)**; Valuation Justification Ratio; exit maths.
6. **ADCG-VG scoring** — weights table (with a one-line reason per section) → scorecard fragment
   (criteria, Marquee GP Index table, VJR, risk register).
7. **Verdict** (TL;DR box). 8. **Pros & Cons (IC voice)**. 9. **Recommendation — staged gates with kill
   criteria**, Caveats, Contrarian note, **Appendix — Prior Venture Deals** (ledger rows tagged [VG]).

The header subtitle names the company and round; it never leads with the score.

## The ADCG-VG scorecard (6 sections × 5 criteria, 1–10)

Fixed weights (user-set, do not flex): **Theme 25 · Valuation & Evolution 25 · Investor Syndicate 25 ·
Company & Management 10 · Competition 10 · Venture Fundamentals 5** = 100.

### 1. Theme (25)
Theme taxonomy (name the theme on the scorecard): Frontier models / LLMs · World models & physical AI /
robotics · AI infrastructure (inference, compute, semis, networking, memory) · AI dev tools & agents ·
Vertical AI applications · Quantum computing · Autonomous vehicles & autonomy · Defense tech · Space ·
Bio × AI / techbio · Energy for AI (fusion, nuclear, grid) · Fintech/crypto infrastructure · Other (define).
Criteria: (a) structural momentum of the theme (b) position & value capture within the theme
(picks-and-shovels vs application; who holds the profit pool) (c) **hype-cycle timing** — private marks vs
public-anchor trend (e.g. Cerebras −55% while private inference marks peaked) (d) theme durability &
addressable spend (in the right units) (e) policy / sovereign / regulatory direction. (Rival crowding is
scored under Competition, not here.)

### 2. Valuation & Evolution (25)
Criteria: (a) **entry multiple vs named comps** — EV/ARR, EV/NTM revenue, EV/bookings (pre-revenue: peer
marks at the same stage), private AND public (b) **Valuation Justification Ratio (VJR)** = valuation
step-up ÷ fundamental step-up (ARR, revenue or bookings) over the same window. ≤1.5 OK (score 7–9); 1.5–3
caution (4–6); >3 red flag (1–3); pre-revenue with a large step-up = treat as >3 unless a hard milestone
(tape-out, FDA clearance, signed binding contract) justifies it (c) growth-adjusted multiple
(EV/NTM ARR ÷ growth %) or, pre-revenue, milestone progress since the last mark (d) round structure &
terms — preferences, ratchets, tranching, in-round price dispersion, primary vs secondary, FD gap vs filings
(e) **exit maths** — the exit value needed for 3× net of expected dilution vs public trading comps and
M&A precedents.

### 3. Investor Syndicate (25)
Criteria: (a) **Marquee GP depth** — `auto: "marquee"` (computed by the engine from the investor list)
(b) lead quality & price-setter — who led and set the price, size of the lead cheque (c) insider conviction
— existing investors re-upping / taking pro-rata vs selling secondary (d) strategic investor validation —
customers, suppliers, hyperscalers, NVentures, labs (validation vs conflict) (e) signal quality vs herd —
penalise crossover/tourist capital and scarce-allocation FOMO at early technical stages; reward
theme-specialist conviction.

**ADCG GP tiers** (self-contained list maintained in this app; do not look up any external roster):
- **T1 — marquee:** a16z, Sequoia, Founders Fund, Thrive Capital, Benchmark, Accel, Lightspeed, General
  Catalyst, Index Ventures, Kleiner Perkins, Greylock, Khosla Ventures. For deep-tech themes also T1: DCVC,
  Lux Capital, Playground Global, Radical Ventures.
- **T2 — strong multi-stage / growth:** Coatue, ICONIQ, Dragoneer, IVP, NEA, Bessemer, Menlo, Insight
  Partners, TCV, Spark Capital, Eclipse, Battery, Bain Capital Ventures, Ribbit, Redpoint, Felicis,
  Conviction, DST Global, Greenoaks, Elad Gil (fund), Sound Ventures; (non-deep-tech themes: DCVC, Lux,
  Playground, Radical).
- **T3 — tracked specialists / regional:** 8VC, Factorial Funds, SparkLabs, AlleyCorp, True Ventures, SOSV,
  Walden Catalyst, Deerfield, JMI, Tiger Global, Inovia, Balderton, HyT Capital, Monolith, and other
  other established specialist managers not listed above.
- **S — strategic:** NVentures/NVIDIA, CapitalG/GV/Google, Microsoft/M12, Amazon, Samsung, SK hynix, Arm,
  Intel Capital, Qualcomm, frontier labs (OpenAI, Anthropic) and major customers.
- **X — other:** crossover/public-market funds (BlackRock, T. Rowe, Fidelity, Wellington), sovereign and
  government funds, angels, other VCs. X points are capped at 1.5 in total.
Points: T1 lead 3 / participant 1.5 · T2 lead 2 / 1 · T3 lead 1 / 0.5 · S lead 1 / 0.5 · X lead 0.5 / 0.25.
Marquee score = min(10, 1 + 0.6 × points). Count the current round. Mark earlier-round-only investors
`"prior_round_only": true` (shown for context, not scored).

### 4. Company & Management (10)
(a) founder quality & founder-market fit (b) team completeness — CTO/CFO/ops/GTM, key hires vs stage
(c) execution vs stated milestones (promises kept, pivots, slips) (d) product / technical moat & IP
(e) customer traction quality — logos, NRR/GRR, concentration, contract binding status.

### 5. Competition (10)
(a) competitive intensity — funded rivals in the same niche and their latest marks (b) relative position
vs category leaders (share, benchmarks, shipped product, ARR) (c) durability of differentiation — how fast
rivals can copy it (d) incumbent / hyperscaler / model-lab displacement risk (e) competitor funding & pricing
pressure. Always include a named competitor table with latest valuation, status and how each differs.

### 6. Venture Fundamentals (5)
(a) capital efficiency & runway — burn multiple (net burn ÷ net new ARR), months of runway (b) gross-margin
trajectory and COGS dependence (GPU/API/model-supplier costs) (c) revenue quality — recurring vs usage vs
one-off, NRR (null if pre-revenue) (d) ADCG access, rights & terms — pro-rata, info rights, co-invest
access (null if undisclosed) (e) exit route & liquidity — IPO window, strategic M&A appetite, secondary
market depth.

Verdict bands as in the buyout skill: Strong ≥8.0 · Positive 6.5–7.9 · Neutral 5.0–6.4 · Weak <5.0.

## Venture Risk Register → Venture Risk Score (0–100, higher = riskier)

The Risk Score is NOT (10 − ADCG) × 10. It is a weighted register of venture-specific risks, each scored
for severity 1–10, so attractiveness and risk can diverge (a marquee-backed deal can still be very risky).
The engine shows the derived figure only as a cross-check.

| Risk | Weight |
|---|---|
| Valuation risk — level AND velocity (VJR) | 15 |
| AI hype / theme-cycle risk — narrative premium, public-anchor de-rating, crowding | 12 |
| Technology / execution risk — unproven product, tape-out, regulatory clearance, scale-up | 12 |
| Commercial traction & customer concentration | 10 |
| Competitive & incumbent / hyperscaler / model-lab displacement | 10 |
| Financing & dilution risk — capital intensity, next-round dependence, burn | 10 |
| Structure, governance & liquidity — prefs, ratchets, FD gap, info rights, exit timing | 10 |
| Business-model / margin & supplier dependence (GPUs, model APIs, memory, foundry) | 8 |
| Regulatory / geopolitical — export controls, AI regulation, China/Taiwan, data/privacy | 7 |
| Key-person / team risk | 6 |

Recommendation overlays: Venture Risk ≥65 → no direct primary at the current price (consider secondary
at a discount, a fund look-through, or waiting for a milestone); VJR red flag + pre-revenue → gate on the
milestone that would justify the mark; Venture Risk ≤35 with ADCG-VG ≥6.5 → candidate for a sized co-invest.

## Workflow

1. Confirm the entity; capture round facts (amount, pre/post, leads, participants, date, primary vs
   secondary, prior rounds with valuations and the ARR/revenue at each).
2. Research IC-grade: company/press releases, Companies House / Delaware / Form D filings, Bloomberg/
   Reuters/The Information via press, Sacra/Dealroom, each competitor separately, public comps,
   M&A precedents. Read memory `/areas/adcg-assessment-lens.md`, `/areas/adcg-deal-ledger.md` and the
   venture blocks in `/areas/adcg-scorecard-metrics-2.md`.
3. Contrarian app: query if reachable; otherwise state the scores are skill-derived.
4. Write the deal JSON (schema below) and run the engine (code below). Use its printed numbers in the prose.
5. Write `/tmp/top_prose.html` (sections 1–5 + the weights table) and `/tmp/body.html` (sections 7–9).
   `cat /tmp/top_prose.html /tmp/vg_scorecard.html > /tmp/top.html`.
6. Assemble and render:
   ```bash
   python3 $P/scripts/assemble_memo.py --shell $P/assets/memo_shell.html --scorecard /tmp/top.html \
     --body /tmp/body.html --title "<Co> — ADCG Venture/Growth Score + Risk Package" \
     --subtitle "<theme> · <round> · <date>" --eyebrow "Venture / Growth · IC memo" \
     --classif "Confidential · IC Draft" --footer "ADCG · skill-derived — reconcile to live ADCG app" \
     --out outputs/<slug>-vg-ic-memo.html
   python3 $P/scripts/html_to_pdf.py outputs/<slug>-vg-ic-memo.html outputs/<slug>-vg-ic-memo.pdf
   ```
   (The shell renders `{{SCORECARD}}` before `{{BODY}}`, so ALWAYS pass `top.html`, never the bare
   scorecard.) Rasterise pages 1–3 and confirm page 1 opens with "1 · Company overview".
7. Publish the HTML as an artifact; send the PDF.
8. Memory: append a ledger row to `/areas/adcg-deal-ledger.md` tagged `[VG]` (company, round/leads,
   post-money, multiple/VJR, ADCG-VG, Venture Risk, theme one-liner) and a scoring-log entry to
   `/areas/adcg-scorecard-metrics-2.md` (or a new continuation file if full).

## Calibration

Venture/Growth scores are NOT comparable to buyout-framework scores. Anchor set (grow with each run):
**Fractile (Series C, Nov-26): ADCG-VG 5.65 / Venture Risk 74** — Theme 6.9, Valuation 3.6, Syndicate 7.4
(Marquee 20.5 pts → 10), Company 5.2, Competition 4.1, Fundamentals 4.8; VJR red flag (7× in 6 months,
pre-revenue). A marquee syndicate cannot rescue a VJR red flag: valuation and risk carry it.

## Self-check

- Page 1 = Company overview; primer with worked examples + visuals + competitor table before any score?
- Latest round fully captured; valuation rebuilt from filings where available; FD gap flagged?
- Valuation-evolution table per round vs fundamentals; VJR computed and stated?
- Investor list complete and tiered; Marquee GP Index shown?
- Weights exactly 25/25/25/10/10/5?
- Risk register scored; Venture Risk vs derived cross-check explained if the gap is >15?
- Named private + public comps with specific multiples; staged gates with kill criteria?
- HTML artifact + PDF delivered; ledger + log updated?

## deal_vg.json schema

```json
{
  "deal": {"name": "…", "recommendation": "…", "facts": [{"k": "Round", "v": "Series C $720m"}]},
  "sector": "Venture / Growth", "sub_sector": "Theme: AI Infrastructure — Inference Silicon",
  "verdict_note": "…", "calibration": "…", "contrarian": {"loaded": false, "text": "…"},
  "valuation_evolution": {"val_from": 1.0, "val_to": 7.0, "metric": "ARR", "metric_from": 0.1, "metric_to": 0.3, "months": 6},
  "investors": [{"name": "Thrive Capital", "tier": "T1", "role": "lead"}, {"name": "Accel", "tier": "T1"}],
  "sections": [
    {"name": "Theme", "weight": 25, "criteria": [{"name": "…", "score": 8.5, "rationale": "…"}]},
    {"name": "Valuation & Evolution", "weight": 25, "criteria": []},
    {"name": "Investor Syndicate", "weight": 25, "criteria": [{"name": "Marquee GP depth (ADCG GP tier index)", "auto": "marquee", "rationale": "…"}]},
    {"name": "Company & Management", "weight": 10, "criteria": []},
    {"name": "Competition", "weight": 10, "criteria": []},
    {"name": "Venture Fundamentals", "weight": 5, "criteria": []}
  ],
  "risk_register": [{"name": "Valuation risk (level + velocity / VJR)", "weight": 15, "severity": 9, "rationale": "…"}]
}
```
Six sections, five criteria each (use `"score": null` for undisclosed; the engine renormalises). Weights sum to 100.

## Engine — write to /tmp/vg_engine.py, then `python3 /tmp/vg_engine.py deal_vg.json --out /tmp/vg_scorecard.html`

```python
#!/usr/bin/env python3
import json, sys, glob, html, argparse, importlib.util

def load_parent():
    hits = glob.glob("/root/.claude/skills/**/scripts/adcg_scorecard.py", recursive=True) \
        or glob.glob("/**/scripts/adcg_scorecard.py", recursive=True)
    if not hits: sys.exit("ADCG Buyout Skill (adcg-score-risk-package) not found - its scripts are required.")
    spec = importlib.util.spec_from_file_location("adcg", hits[0]); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m

PTS = {("T1","lead"):3.0, ("T1","part"):1.5, ("T2","lead"):2.0, ("T2","part"):1.0,
       ("T3","lead"):1.0, ("T3","part"):0.5, ("X","lead"):0.5, ("X","part"):0.25,
       ("S","lead"):1.0, ("S","part"):0.5}

def marquee(investors):
    live = [i for i in investors if not i.get("prior_round_only")]
    core = sum(PTS.get((i["tier"], i.get("role","part")), 0) for i in live if i["tier"] != "X")
    tail = min(1.5, sum(PTS.get(("X", i.get("role","part")), 0) for i in live if i["tier"] == "X"))
    p = core + tail
    return round(p,2), round(max(1.0, min(10.0, 1 + 0.6*p)), 1)

def vjr(v):
    if not v or not v.get("val_from") or not v.get("val_to"): return None, "n/a"
    up = v["val_to"]/v["val_from"]; f0, f1 = v.get("metric_from"), v.get("metric_to")
    if not f0 or not f1:
        return round(up,2), f"{up:.1f}x valuation step-up, no fundamental step-up evidenced (pre-revenue) - treat VJR as >3 (red flag) unless milestone-justified"
    r = up/(f1/f0); flag = "OK" if r <= 1.5 else ("CAUTION" if r <= 3 else "RED FLAG")
    return round(r,2), f"{up:.1f}x valuation vs {f1/f0:.1f}x {v.get('metric','ARR')} over {v.get('months','?')} months => VJR {r:.2f} ({flag})"

def risk_register(rr):
    tw = sum(r["weight"] for r in rr)
    return round(sum(r["weight"]*r["severity"] for r in rr)/tw*10)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("deal"); ap.add_argument("--out"); a = ap.parse_args()
    eng = load_parent(); deal = json.load(open(a.deal))
    mpts, mscore = marquee(deal.get("investors", []))
    for s in deal["sections"]:
        for c in s["criteria"]:
            if c.get("auto") == "marquee":
                c["score"] = mscore; c["rationale"] = f"Marquee GP Index {mpts} pts -> {mscore}/10. " + c.get("rationale","")
    v_r, v_txt = vjr(deal.get("valuation_evolution"))
    deal = eng.compute(deal)
    derived = deal["_risk"]; reg = risk_register(deal["risk_register"]); deal["_risk"] = reg
    frag = eng.render(deal).replace("Derived risk score", "Venture risk score (risk register)")
    rows = "".join(f'<tr><td>{html.escape(r["name"])}</td><td class="num">{r["weight"]}%</td>'
                   f'<td class="num">{r["severity"]}</td><td>{html.escape(r["rationale"])}</td></tr>' for r in deal["risk_register"])
    inv = "".join(f'<tr><td>{html.escape(i["name"])}</td><td>{i["tier"]}</td><td>{i.get("role","part")}</td>'
                  f'<td class="num">{PTS.get((i["tier"], i.get("role","part")),0)}</td></tr>'
                  for i in deal.get("investors", []) if not i.get("prior_round_only"))
    extra = (f'<h3 class="sc-h3">Marquee GP Index (ADCG GP tiers)</h3><table><tr><th>Investor</th><th>Tier</th><th>Role</th><th>Pts</th></tr>{inv}'
             f'<tr class="hl"><td colspan="3"><strong>Total -> score</strong></td><td class="num">{mpts} -> {mscore}</td></tr></table>'
             f'<h3 class="sc-h3">Valuation Justification Ratio</h3><p>{html.escape(v_txt)}</p>'
             f'<h3 class="sc-h3">Venture risk register (severity 1-10, higher = worse)</h3>'
             f'<table><tr><th>Risk</th><th>Weight</th><th>Severity</th><th>Rationale</th></tr>{rows}'
             f'<tr class="hl"><td colspan="2"><strong>Venture Risk Score</strong></td><td class="num">{reg}</td>'
             f'<td>Cross-check: (10 - ADCG) x 10 = {derived}. Gap {reg-derived:+d}.</td></tr></table>')
    frag = frag.replace("</section>", extra + "</section>")
    print(json.dumps({"overall": deal["_overall"], "band": deal["_band"][0], "venture_risk": reg, "derived_risk": derived,
                      "marquee_pts": mpts, "marquee_score": mscore, "vjr": v_r,
                      "sections": {s["name"]: round(s["_score"],2) for s in deal["sections"]}}, indent=2))
    if a.out: open(a.out, "w").write(frag)

if __name__ == "__main__": main()
```