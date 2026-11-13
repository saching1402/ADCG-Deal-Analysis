#!/usr/bin/env python3
"""
ADCG Deal Score + Risk Score engine.

Takes a deal JSON (deal facts + 5 sections x 5 sector-tailored criteria, each 1-10,
with per-deal section weights that sum to 100) and:
  1. Computes each section score (weighted mean of its criteria; equal weights unless
     a per-criterion "weight" is given), the overall ADCG (sum of section_weight x
     section_score), the verdict band, and the derived Risk Score = (10 - ADCG) x 10.
  2. Renders a self-contained HTML scorecard *fragment* to embed in the memo shell:
     verdict cards, a deal fact strip, five section bars, a risk gauge, and the full
     criteria-detail table. All visuals are static (CSS widths + inline SVG computed
     here) so the fragment renders identically in a browser AND in a headless-PDF pass
     with no JavaScript. Colours follow the verdict band.

Undisclosed criteria: set "score": null to exclude the item and renormalise the section
across the remaining criteria (mirrors the live app's zero-and-renormalise rule).

Usage:
    python adcg_scorecard.py deal.json --out scorecard_fragment.html
    python adcg_scorecard.py deal.json                 # prints computed summary only

Verdict bands:  Strong >=8.0 | Positive 6.5-7.9 | Neutral 5.0-6.4 | Weak <5.0
Risk convention: 0-100, higher = riskier (per the Contrarian app).
"""
import json, sys, argparse, html

# ---- palette (matches the memo shell) -------------------------------------
TEAL, GOLD, OXBLOOD, INK, MUTED = "#1f5a54", "#b3892f", "#9b2f2f", "#1a1c1a", "#8a877d"

def band_of(score):
    if score >= 8.0:  return ("Strong", TEAL, "band-strong")
    if score >= 6.5:  return ("Positive", TEAL, "band-positive")
    if score >= 5.0:  return ("Neutral", GOLD, "band-neutral")
    return ("Weak", OXBLOOD, "band-weak")

def colour_for(score):
    if score >= 6.5: return TEAL
    if score >= 5.0: return GOLD
    return OXBLOOD

# ---- computation -----------------------------------------------------------
def compute(deal):
    sections = deal["sections"]
    wsum = sum(s["weight"] for s in sections)
    if abs(wsum - 100) > 0.6:
        print(f"WARNING: section weights sum to {wsum}, expected 100.", file=sys.stderr)
    overall = 0.0
    for s in sections:
        crits = [c for c in s["criteria"] if c.get("score") is not None]
        if not crits:
            s["_score"] = 0.0; continue
        cw = sum(c.get("weight", 1) for c in crits)
        s["_score"] = sum(c["score"] * c.get("weight", 1) for c in crits) / cw
        overall += (s["weight"] / 100.0) * s["_score"]
    deal["_overall"] = round(overall, 2)
    deal["_risk"] = round((10 - overall) * 10)
    deal["_band"] = band_of(overall)
    return deal

# ---- static risk gauge (semicircle, computed here so no JS is needed) -------
def gauge_svg(risk):
    import math
    R, cx, cy = 70, 90, 90
    def pt(a):
        r = (a - 180) * math.pi / 180
        return cx + R*math.cos(r), cy + R*math.sin(r)
    def arc(a0, a1, col, w):
        x0, y0 = pt(a0); x1, y1 = pt(a1); large = 1 if (a1-a0) > 180 else 0
        return (f'<path d="M {x0:.1f} {y0:.1f} A {R} {R} 0 {large} 1 {x1:.1f} {y1:.1f}" '
                f'fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round"/>')
    ang = 180 + (risk/100.0)*180
    nx, ny = pt(ang)
    return (f'<svg viewBox="0 0 180 112" width="100%" style="max-width:230px">'
            f'{arc(180,240,TEAL,13)}{arc(240,300,GOLD,13)}{arc(300,360,OXBLOOD,13)}'
            f'{arc(180,ang,INK,3)}'
            f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="6" fill="{INK}"/>'
            f'<text x="90" y="86" text-anchor="middle" font-size="23" font-weight="700" '
            f'font-family="Georgia,serif">{risk}</text>'
            f'<text x="18" y="106" font-size="8" fill="{MUTED}">low</text>'
            f'<text x="150" y="106" font-size="8" fill="{MUTED}">high</text></svg>')

# ---- fragment renderer -----------------------------------------------------
def esc(x): return html.escape(str(x))

def render(deal):
    band_name, band_col, band_cls = deal["_band"]
    overall, risk = deal["_overall"], deal["_risk"]
    d = deal["deal"]

    facts = "".join(
        f'<div><div class="k">{esc(f["k"])}</div><div class="v">{esc(f["v"])}</div></div>'
        for f in d.get("facts", [])[:5])

    # section bars
    bars = ""
    for s in deal["sections"]:
        sc = s["_score"]; col = colour_for(sc)
        bars += (f'<div class="score-row"><div class="lbl">{esc(s["name"])}'
                 f'<small>section weight {s["weight"]}%</small></div>'
                 f'<div class="track"><div class="fill" style="width:{sc*10:.0f}%;background:{col}"></div></div>'
                 f'<div class="val" style="color:{col}">{sc:.1f}</div></div>')
    bar_col = TEAL if overall >= 6.5 else (GOLD if overall >= 5.0 else OXBLOOD)
    bars += (f'<div class="score-row overall"><div class="lbl"><strong>OVERALL</strong>'
             f'<small>weighted roll-up · {esc(band_name)} band</small></div>'
             f'<div class="track" style="height:18px"><div class="fill" '
             f'style="width:{overall*10:.0f}%;background:{bar_col}"></div></div>'
             f'<div class="val" style="font-size:17px">{overall:.1f}</div></div>')

    # criteria table
    rows = ""
    for s in deal["sections"]:
        crits = s["criteria"]; n = len(crits)
        for i, c in enumerate(crits):
            sc = "n/d" if c.get("score") is None else f'{c["score"]:.1f}'
            first = (f'<td rowspan="{n}"><strong>{esc(s["name"])}</strong><br>'
                     f'<small>({s["weight"]}%) · {s["_score"]:.1f}</small></td>') if i == 0 else ""
            rows += (f'<tr>{first}<td>{esc(c["name"])}</td>'
                     f'<td class="num">{sc}</td><td>{esc(c.get("rationale",""))}</td></tr>')

    contr = deal.get("contrarian", {})
    contr_html = (f'<div class="sc-note"><strong>Contrarian app:</strong> {esc(contr.get("text",""))}</div>'
                  if contr.get("text") else "")

    calib = f'<p class="sc-cal"><small>{esc(deal.get("calibration",""))}</small></p>' if deal.get("calibration") else ""

    return f'''
<section class="scorecard">
  <div class="verdict">
    <div class="vcard"><div class="k">ADCG Deal Score</div>
      <div class="big" style="color:{band_col}">{overall:.1f}<span class="slash">/10</span></div>
      <span class="tag {band_cls}">{esc(band_name).upper()} band</span></div>
    <div class="vcard"><div class="k">Derived Risk Score</div>
      <div class="big">{risk}<span class="slash">/100</span></div>
      <span class="tag risk">higher = riskier</span></div>
    <div class="vcard"><div class="k">Recommendation</div>
      <div class="rec">{esc(d.get("recommendation", deal.get("recommendation","")))}</div>
      <span class="tag recc">{esc(deal.get("verdict_note",""))}</span></div>
  </div>
  <p class="sc-meta"><small>ADCG framework · 5 sections · 25 sector-tailored criteria · 1–10 ·
    two-level weighted roll-up. Bands: Strong ≥8.0 · Positive 6.5–7.9 · Neutral 5.0–6.4 · Weak &lt;5.0.
    Risk = (10 − ADCG) × 10. Sector: <strong>{esc(deal.get("sub_sector", deal.get("sector","")))}</strong>.</small></p>

  <div class="facts">{facts}</div>

  <h2 class="sc-h">ADCG deal scorecard — {esc(deal.get("sub_sector","sector-tailored"))}</h2>
  <div class="bars">{bars}</div>

  <div class="gauge-wrap">
    <div><div class="eyebrow">Derived risk score</div>
      <div class="riskbig">{risk}<span class="slash">/100</span></div>
      {calib}</div>
    <div>{gauge_svg(risk)}</div>
  </div>

  <h3 class="sc-h3">Criteria detail</h3>
  <table class="crit"><tr><th>Section (wt)</th><th>Criterion</th><th>Score</th><th>Rationale</th></tr>
    {rows}</table>
  {contr_html}
</section>'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deal_json")
    ap.add_argument("--out", help="write HTML scorecard fragment here")
    a = ap.parse_args()
    deal = compute(json.load(open(a.deal_json)))
    summary = {"overall": deal["_overall"], "risk": deal["_risk"],
               "band": deal["_band"][0],
               "sections": {s["name"]: round(s["_score"], 2) for s in deal["sections"]}}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if a.out:
        open(a.out, "w").write(render(deal))
        print(f"\nfragment -> {a.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
