"""
Deterministic ADCG scoring — the same engines the two ADCG skills run.

* Buyout track: ``adcg_scorecard.py`` (5 sections x 5 criteria, per-deal weights, risk = (10 - ADCG) x 10)
* Venture/Growth track: the ADCG-VG engine from the Venture Growth skill (6 sections, fixed
  25/25/25/10/10/5 weights, Marquee GP Index from the investor list, VJR, weighted venture risk register).

Claude scores each criterion; this module does every roll-up so the numbers are reproducible.
"""
from __future__ import annotations

import copy
import html

from . import adcg_scorecard as eng

VG_WEIGHTS = {'Theme': 25, 'Valuation & Evolution': 25, 'Investor Syndicate': 25,
              'Company & Management': 10, 'Competition': 10, 'Venture Fundamentals': 5}

PTS = {('T1', 'lead'): 3.0, ('T1', 'part'): 1.5, ('T2', 'lead'): 2.0, ('T2', 'part'): 1.0,
       ('T3', 'lead'): 1.0, ('T3', 'part'): 0.5, ('X', 'lead'): 0.5, ('X', 'part'): 0.25,
       ('S', 'lead'): 1.0, ('S', 'part'): 0.5}


class ScoringError(ValueError):
    pass


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(1.0, min(10.0, f))


def _clean(deal: dict, track: str) -> dict:
    """Validate shape and clamp scores so a slightly-off model reply still scores."""
    d = copy.deepcopy(deal)
    secs = d.get('sections')
    if not isinstance(secs, list) or not secs:
        raise ScoringError('Scorecard JSON has no sections.')
    for s in secs:
        s['name'] = str(s.get('name') or 'Section')
        crits = [c for c in (s.get('criteria') or []) if isinstance(c, dict)]
        for c in crits:
            c['name'] = str(c.get('name') or 'Criterion')
            c['rationale'] = str(c.get('rationale') or '')
            if c.get('auto') != 'marquee':
                c['score'] = _num(c.get('score'))
        s['criteria'] = crits
        try:
            s['weight'] = float(s.get('weight') or 0)
        except (TypeError, ValueError):
            s['weight'] = 0.0
    if track == 'vg':
        for s in secs:  # weights are fixed by the skill
            if s['name'] in VG_WEIGHTS:
                s['weight'] = VG_WEIGHTS[s['name']]
    total = sum(s['weight'] for s in secs) or 1
    if abs(total - 100) > 0.6:  # renormalise rather than fail
        for s in secs:
            s['weight'] = round(s['weight'] * 100 / total, 1)
    for s in secs:
        if float(s['weight']).is_integer():
            s['weight'] = int(s['weight'])
    d.setdefault('deal', {})
    d['deal'].setdefault('name', '')
    d['deal'].setdefault('facts', [])
    return d


def marquee(investors):
    live = [i for i in investors or [] if isinstance(i, dict) and not i.get('prior_round_only')]
    core = sum(PTS.get((i.get('tier'), i.get('role', 'part')), 0) for i in live if i.get('tier') != 'X')
    tail = min(1.5, sum(PTS.get(('X', i.get('role', 'part')), 0) for i in live if i.get('tier') == 'X'))
    p = core + tail
    return round(p, 2), round(max(1.0, min(10.0, 1 + 0.6 * p)), 1)


def vjr(v):
    if not v or not v.get('val_from') or not v.get('val_to'):
        return None, 'n/a'
    try:
        up = float(v['val_to']) / float(v['val_from'])
    except (TypeError, ValueError, ZeroDivisionError):
        return None, 'n/a'
    f0, f1 = v.get('metric_from'), v.get('metric_to')
    if not f0 or not f1:
        return round(up, 2), (f'{up:.1f}x valuation step-up, no fundamental step-up evidenced (pre-revenue) - '
                              'treat VJR as >3 (red flag) unless milestone-justified')
    r = up / (float(f1) / float(f0))
    flag = 'OK' if r <= 1.5 else ('CAUTION' if r <= 3 else 'RED FLAG')
    return round(r, 2), (f"{up:.1f}x valuation vs {float(f1) / float(f0):.1f}x {v.get('metric', 'ARR')} over "
                         f"{v.get('months', '?')} months => VJR {r:.2f} ({flag})")


def risk_register(rr):
    rows = [r for r in rr or [] if isinstance(r, dict) and r.get('weight') and r.get('severity') is not None]
    tw = sum(float(r['weight']) for r in rows)
    if not tw:
        return None
    return round(sum(float(r['weight']) * float(r['severity']) for r in rows) / tw * 10)


def score(deal: dict, track: str) -> tuple[dict, str, dict]:
    """Return (summary, scorecard HTML fragment, cleaned deal JSON with computed fields)."""
    d = _clean(deal, track)
    if track != 'vg':
        d = eng.compute(d)
        summary = {'overall': d['_overall'], 'risk': d['_risk'], 'band': d['_band'][0],
                   'sections': {s['name']: round(s['_score'], 2) for s in d['sections']}}
        frag = eng.render(d)
        return summary, frag, _strip(d)

    mpts, mscore = marquee(d.get('investors'))
    for s in d['sections']:
        for c in s['criteria']:
            if c.get('auto') == 'marquee':
                c['score'] = mscore
                c['rationale'] = f'Marquee GP Index {mpts} pts -> {mscore}/10. ' + c.get('rationale', '')
    v_r, v_txt = vjr(d.get('valuation_evolution'))
    d = eng.compute(d)
    derived = d['_risk']
    reg = risk_register(d.get('risk_register'))
    if reg is not None:
        d['_risk'] = reg
    frag = eng.render(d).replace('Derived risk score', 'Venture risk score (risk register)').replace(
        'Derived Risk Score', 'Venture Risk Score')
    rows = ''.join(f'<tr><td>{html.escape(str(r.get("name", "")))}</td><td class="num">{r.get("weight")}%</td>'
                   f'<td class="num">{r.get("severity")}</td><td>{html.escape(str(r.get("rationale", "")))}</td></tr>'
                   for r in d.get('risk_register') or [] if isinstance(r, dict))
    inv = ''.join(f'<tr><td>{html.escape(str(i.get("name", "")))}</td><td>{i.get("tier")}</td><td>{i.get("role", "part")}</td>'
                  f'<td class="num">{PTS.get((i.get("tier"), i.get("role", "part")), 0)}</td></tr>'
                  for i in d.get('investors') or [] if isinstance(i, dict) and not i.get('prior_round_only'))
    extra = (f'<h3 class="sc-h3">Marquee GP Index (Venture GP Atlas tiers)</h3><table><tr><th>Investor</th><th>Tier</th><th>Role</th><th>Pts</th></tr>{inv}'
             f'<tr class="hl"><td colspan="3"><strong>Total -> score</strong></td><td class="num">{mpts} -> {mscore}</td></tr></table>'
             f'<h3 class="sc-h3">Valuation Justification Ratio</h3><p>{html.escape(v_txt)}</p>')
    if reg is not None:
        extra += (f'<h3 class="sc-h3">Venture risk register (severity 1-10, higher = worse)</h3>'
                  f'<table><tr><th>Risk</th><th>Weight</th><th>Severity</th><th>Rationale</th></tr>{rows}'
                  f'<tr class="hl"><td colspan="2"><strong>Venture Risk Score</strong></td><td class="num">{reg}</td>'
                  f'<td>Cross-check: (10 - ADCG) x 10 = {derived}. Gap {reg - derived:+d}.</td></tr></table>')
    frag = frag.replace('</section>', extra + '</section>')
    summary = {'overall': d['_overall'], 'risk': d['_risk'], 'band': d['_band'][0], 'derived_risk': derived,
               'marquee_pts': mpts, 'marquee_score': mscore, 'vjr': v_r, 'vjr_text': v_txt,
               'sections': {s['name']: round(s['_score'], 2) for s in d['sections']}}
    return summary, frag, _strip(d)


def _strip(d: dict) -> dict:
    out = copy.deepcopy(d)
    out.pop('_band', None)
    for s in out.get('sections', []):
        s['score'] = round(s.pop('_score', 0.0), 2)
    out['overall'] = out.pop('_overall', None)
    out['risk'] = out.pop('_risk', None)
    return out
