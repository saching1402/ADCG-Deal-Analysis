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
import re
import threading

from . import adcg_scorecard as eng
from ..framework import gp_entities as gpe

_lock = threading.Lock()

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


def _clean(deal: dict, track: str, cfg: dict | None = None) -> dict:
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
    fixed = {}
    if cfg and not cfg.get('weights_flex', track in ('buyout', 'cv')):
        fixed = {_key(x['name']): x['weight'] for x in cfg.get('sections') or []}
    elif not cfg and track == 'vg':
        fixed = {_key(k): v for k, v in VG_WEIGHTS.items()}
    for s in secs:  # fixed-weight frameworks: weights come from the framework, not the model
        if _key(s['name']) in fixed:
            s['weight'] = fixed[_key(s['name'])]
    secs[:] = [s for s in secs if _key(s['name']) != _key(DS_NAME)]   # rebuilt below from "deal_specific"
    total = sum(s['weight'] for s in secs) or 1
    if abs(total - 100) > 0.6:  # renormalise rather than fail
        for s in secs:
            s['weight'] = round(s['weight'] * 100 / total, 1)
    ds_w = float(((cfg or {}).get('deal_specific') or {}).get('weight') or 0)
    ds = [c for c in (deal.get('deal_specific') or []) if isinstance(c, dict) and str(c.get('name') or '').strip()]
    if ds_w > 0 and ds:   # framework sections share (100 − w)%, the deal's own factors the rest
        for s in secs:
            s['weight'] = round(s['weight'] * (100 - ds_w) / 100, 2)
        secs.append({'name': DS_NAME, 'weight': ds_w, 'deal_specific': True,
                     'criteria': [{'name': str(c['name']).strip()[:120], 'score': _num(c.get('score')),
                                   'rationale': (str(c.get('why') or '').strip() + (' — ' if c.get('why') and c.get('rationale') else '')
                                                 + str(c.get('rationale') or '')).strip()} for c in ds[:8]]})
    for s in secs:
        if float(s['weight']).is_integer():
            s['weight'] = int(s['weight'])
    d.setdefault('deal', {})
    d['deal'].setdefault('name', '')
    d['deal'].setdefault('facts', [])
    return d


DS_NAME = 'Deal-specific factors'


def _key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(name).lower())


def _norm_member(m: str) -> str:
    return _key(re.sub(r'\(.*?\)', '', m))


def tier_table(cfg: dict | None) -> tuple[dict, dict, list]:
    """(points by (tier, role), caps by tier, tiers with their member firms) from the framework, or the skill defaults."""
    if not cfg or not cfg.get('tiers'):
        return PTS, {'X': 1.5}, []
    pts, caps = {}, {}
    for t in cfg['tiers']:
        pts[(t['id'], 'lead')] = float(t.get('lead', 0))
        pts[(t['id'], 'part')] = float(t.get('part', 0))
        if t.get('cap'):
            caps[t['id']] = float(t['cap'])
    return pts, caps, cfg['tiers']


def assign_tiers(investors, tiers: list) -> None:
    """Re-check the model's tier against the framework lists by identity — the investor's website, else its exact
    name or a listed alias (no word matching). The framework wins when the firm is listed."""
    for i in investors or []:
        if not isinstance(i, dict):
            continue
        t, m = gpe.find(tiers, i.get('name', ''), i.get('domain', ''))
        if t:
            i['tier'] = t['id']
            i['matched'] = m['name']


# Deal lead (20-Nov-26): in venture a CLUSTER of marquee names is what matters — one tier-1 manager is very good, two are
# excellent; the smaller or unlisted VCs and founder-friendly angels who always come along never pull the score down.
MARQUEE_FLOORS = {'t1_one': 8.0, 't1_two': 9.0, 't1_three': 9.5, 'good_three': 8.0}


def marquee(investors, cfg: dict | None = None):
    pts, caps, _ = tier_table(cfg)
    mq = (cfg or {}).get('marquee') or {'base': 1.0, 'slope': 0.6}
    live = [i for i in investors or [] if isinstance(i, dict) and not i.get('prior_round_only')]
    total = 0.0
    for tier in {i.get('tier') for i in live}:
        sub = sum(pts.get((tier, i.get('role', 'part')), 0) for i in live if i.get('tier') == tier)
        total += min(caps[tier], sub) if tier in caps else sub
    score = max(1.0, min(10.0, mq['base'] + mq['slope'] * total))
    fl = {**MARQUEE_FLOORS, **(mq.get('floors') or {})}
    names = lambda tiers: len({(i.get('matched') or i.get('name') or '').strip().lower() for i in live if i.get('tier') in tiers} - {''})
    t1, good = names({'T1'}), names({'T1', 'T2', 'S'})
    floor = max([0.0] + [fl['t1_three']] * (t1 >= 3) + [fl['t1_two']] * (t1 >= 2) + [fl['t1_one']] * (t1 >= 1)
                + [fl['good_three']] * (good >= 3))
    return round(total, 2), round(max(score, min(10.0, floor)), 1)


def vjr(v, cfg: dict | None = None):
    """Valuation step-up ÷ fundamental step-up. The fundamental is GROSS PROFIT (metric × gross margin) when both gross
    margins are given — so margin expansion counts and thin-margin revenue counts for less — else the metric (ARR)."""
    th = (cfg or {}).get('vjr') or {'ok': 1.5, 'caution': 3.0}
    if not v or not v.get('val_from') or not v.get('val_to'):
        return None, 'n/a'
    try:
        up = float(v['val_to']) / float(v['val_from'])
    except (TypeError, ValueError, ZeroDivisionError):
        return None, 'n/a'
    f0, f1 = v.get('metric_from'), v.get('metric_to')
    if not f0 or not f1:
        why = f"; milestone cited: {v['milestone']}" if v.get('milestone') else ''
        return round(up, 2), (f'{up:.1f}x valuation step-up, no fundamental step-up evidenced (pre-revenue) - '
                              f'treat VJR as >{th["caution"]:g} (red flag) unless milestone-justified{why}')
    metric = v.get('metric', 'ARR')
    try:
        g0, g1 = float(v.get('gm_from') or 0), float(v.get('gm_to') or 0)
        if g0 > 1: g0 /= 100
        if g1 > 1: g1 /= 100
        fund = (float(f1) * g1) / (float(f0) * g0) if g0 > 0 and g1 > 0 else float(f1) / float(f0)
        basis = f'gross profit ({metric} × gross margin {g0:.0%}→{g1:.0%})' if g0 > 0 and g1 > 0 else metric
        r = up / fund
    except (TypeError, ValueError, ZeroDivisionError):
        return round(up, 2), 'n/a'
    flag = 'OK' if r <= th['ok'] else ('CAUTION' if r <= th['caution'] else 'RED FLAG')
    return round(r, 2), (f"{up:.1f}x valuation vs {fund:.1f}x {basis} over {v.get('months', '?')} months => VJR {r:.2f} ({flag})"
                         + (f"; milestone: {v['milestone']}" if v.get('milestone') else ''))


def apply_register_weights(rr, cfg: dict | None) -> None:
    """Framework register weights win over the model's (matched by name)."""
    reg = ((cfg or {}).get('risk') or {}).get('register') or []
    want = {_key(r['name']): r['weight'] for r in reg}
    for r in rr or []:
        if not isinstance(r, dict):
            continue
        k = _key(r.get('name', ''))
        w = want.get(k) or next((v for n, v in want.items() if n[:24] and (n[:24] in k or k[:24] in n)), None)
        if w is not None:
            r['weight'] = w


def band_fn(cfg: dict | None):
    bands = (cfg or {}).get('bands')
    if not bands:
        return eng.band_of
    classes = ['band-strong', 'band-positive', 'band-neutral', 'band-weak']
    ordered = sorted(bands, key=lambda b: -float(b['min']))

    def f(score):
        for n, b in enumerate(ordered):
            if score >= float(b['min']):
                cls = classes[min(n, 3)] if n < len(ordered) - 1 else 'band-weak'
                colour = eng.TEAL if cls in ('band-strong', 'band-positive') else eng.GOLD if cls == 'band-neutral' else eng.OXBLOOD
                return (b['label'], colour, cls)
        return (ordered[-1]['label'], eng.OXBLOOD, 'band-weak')
    return f


def risk_register(rr):
    rows = [r for r in rr or [] if isinstance(r, dict) and r.get('weight') and r.get('severity') is not None]
    tw = sum(float(r['weight']) for r in rows)
    if not tw:
        return None
    return round(sum(float(r['weight']) * float(r['severity']) for r in rows) / tw * 10)


def score(deal: dict, track: str, cfg: dict | None = None, house: dict | None = None,
          gps: dict | None = None) -> tuple[dict, str, dict]:
    """Return (summary, scorecard HTML fragment, cleaned deal JSON). `cfg` = the framework config (Framework tab);
    `house` = the ADCG preferences that apply to this track (capped overall adjustment)."""
    with _lock:  # band_of is patched per framework while computing/rendering
        orig = eng.band_of
        eng.band_of = band_fn(cfg)
        try:
            return _score(deal, track, cfg, house, gps)
        finally:
            eng.band_of = orig


IMPORTANCE = {'high': 3, 'medium': 2, 'low': 1}


def apply_house(d: dict, house: dict | None) -> None:
    """ADCG preferences: each applicable preference gets a fit of -2..+2 from the scorer; the importance-weighted
    average fit (-1..+1) × max_adjust moves the overall score (default ±0.5). Records the breakdown in d['house']."""
    if not house or not house.get('preferences'):
        return
    given = {str(x.get('id')): x for x in d.get('house_fit') or [] if isinstance(x, dict)}
    items, num, den = [], 0.0, 0.0
    for p in house['preferences']:
        g = given.get(p['id']) or {}
        fit = g.get('fit')
        try:
            fit = None if fit is None else max(-2.0, min(2.0, float(fit)))
        except (TypeError, ValueError):
            fit = None
        w = IMPORTANCE.get(p.get('importance'), 2)
        if fit is not None:
            num += w * fit
            den += w * 2
        items.append({'id': p['id'], 'title': p['title'], 'importance': p.get('importance', 'medium'), 'fit': fit,
                      'why': str(g.get('why') or '')[:600]})
    fit_idx = round(num / den, 3) if den else 0.0
    cap = float(house.get('max_adjust', 0.5))
    adj = round(fit_idx * cap, 2)
    base = d['_overall']
    d['_overall'] = round(max(1.0, min(10.0, base + adj)), 2)
    d['_band'] = eng.band_of(d['_overall'])
    d['house'] = {'items': items, 'fit_index': fit_idx, 'adjustment': adj, 'max_adjust': cap, 'framework_overall': base}


def _house_note(frag: str, d: dict) -> str:
    h = d.get('house')
    if not h or not h['adjustment']:
        return frag
    return frag.replace('<p class="sc-meta"><small>', f'<p class="sc-meta"><small>Overall includes the ADCG preferences '
                        f'adjustment ({h["adjustment"]:+.2f}; framework score {h["framework_overall"]:.2f}). ', 1)


def gp_tier(name: str, tiers: list, domain: str = '') -> dict | None:
    """The tier listing this firm — matched on its website, else its exact name or alias (never on shared words)."""
    return gpe.find(tiers, name, domain)[0]


def apply_gp_tiers(d: dict, gps: dict | None) -> None:
    """Score the [auto: sponsor_tier] / [auto: secondary_tier] criteria from the ADCG GP list. A manager not on any list
    keeps the scorer's own score (or the unlisted score if the scorer gave none)."""
    if not gps:
        return
    # buyouts / CVs have one or two sponsors (deal lead, 20-Nov-26): check each against the tiers; the stronger one sets
    # the score and both are named in the rationale
    co = [(d.get('co_sponsor_gp') or '').strip(), (d.get('co_sponsor_gp_domain') or '').strip()]
    who = {'sponsor_tier': (d.get('sponsor_gp') or (d.get('deal') or {}).get('sponsor') or '', d.get('sponsor_gp_domain') or '',
                            gps.get('sponsor_tiers'), 'GP list'),
           'secondary_tier': (d.get('secondary_lead') or '', d.get('secondary_lead_domain') or '', gps.get('secondary_tiers'),
                              'secondaries list')}
    for s in d.get('sections') or []:
        for c in s.get('criteria') or []:
            a = c.get('auto')
            if a not in who:
                continue
            name, dom, tiers, lst = who[a]
            t, m = gpe.find(tiers, name, dom)
            if a == 'sponsor_tier' and co[0]:
                t2, m2 = gpe.find(tiers, co[0], co[1])
                d['co_sponsor_tier'] = ({'firm': (m2.get('name') if isinstance(m2, dict) else '') or co[0], 'tier': t2['label'],
                                         'score': t2['score']} if t2 else {'firm': co[0], 'tier': 'Not listed', 'score': None})
                if t2 and (not t or t2['score'] > t['score']):
                    name, (t, m), (t2, m2) = co[0], (t2, m2), (t, m)   # the stronger sponsor sets the score
                if t2:
                    c['rationale'] = (f'Co-sponsor {gpe.label(m2)}: {t2["label"]} → {t2["score"]:g}/10. ' + (c.get('rationale') or ''))
                elif t:
                    other = d['co_sponsor_tier']['firm'] if d['co_sponsor_tier']['firm'] != name else (d.get('sponsor_gp') or '')
                    c['rationale'] = f'Co-sponsor {other}: not on the ADCG {lst}. ' + (c.get('rationale') or '')
            d.setdefault('gp_tiers', {})[a] = ({'firm': (m.get('name') if isinstance(m, dict) else '') or gpe.label(m), 'tier': t['label'], 'score': t['score'], 'list': lst}
                                                if t else {'firm': name, 'tier': 'Not listed', 'score': None, 'list': lst}) if name else None
            if t:
                c['score'] = float(t['score'])
                firm = gpe.label(m)
                c['rationale'] = f'{firm}: {t["label"]} on the ADCG {lst} → {t["score"]:g}/10. ' + (c.get('rationale') or '')
            elif c.get('score') is None and name and gps.get('unlisted_score') is not None:
                c['score'] = float(gps['unlisted_score'])
                c['rationale'] = f'{name}: not on the ADCG {lst} → {gps["unlisted_score"]:g}/10. ' + (c.get('rationale') or '')


def _house_summary(d: dict) -> dict:
    h = d.get('house')
    return {'framework_overall': h['framework_overall'], 'house_adj': h['adjustment']} if h else {}


def _score(deal: dict, track: str, cfg: dict | None, house: dict | None = None,
           gps: dict | None = None) -> tuple[dict, str, dict]:
    d = _clean(deal, track, cfg)
    if track != 'vg':
        apply_gp_tiers(d, gps)
        d = eng.compute(d)
        apply_house(d, house)
        summary = {'overall': d['_overall'], 'band': d['_band'][0],
                   'sections': {s['name']: round(s['_score'], 2) for s in d['sections']}, **_house_summary(d)}
        frag = _house_note(memo_bars(no_risk(eng.render(d)), track, len(d['sections'])), d)
        return summary, frag, _strip(d)

    pts, _, tiers = tier_table(cfg)
    assign_tiers(d.get('investors'), tiers)
    apply_register_weights(d.get('risk_register'), cfg)
    mpts, mscore = marquee(d.get('investors'), cfg)
    for s in d['sections']:
        for c in s['criteria']:
            if c.get('auto') == 'marquee':
                c['score'] = mscore
                c['rationale'] = f'Marquee GP Index {mpts} pts -> {mscore}/10. ' + c.get('rationale', '')
    v_r, v_txt = vjr(d.get('valuation_evolution'), cfg)
    d = eng.compute(d)
    apply_house(d, house)
    frag = no_risk(eng.render(d))
    inv = ''.join(f'<tr><td>{html.escape(str(i.get("name", "")))}</td><td>{i.get("tier")}</td><td>{i.get("role", "part")}</td>'
                  f'<td class="num">{pts.get((i.get("tier"), i.get("role", "part")), 0)}</td></tr>'
                  for i in d.get('investors') or [] if isinstance(i, dict) and not i.get('prior_round_only'))
    extra = (f'<h3 class="sc-h3">Marquee GP Index (ADCG GP tiers)</h3><table><tr><th>Investor</th><th>Tier</th><th>Role</th><th>Pts</th></tr>{inv}'
             f'<tr class="hl"><td colspan="3"><strong>Total -> score</strong></td><td class="num">{mpts} -> {mscore}</td></tr></table>'
             f'<h3 class="sc-h3">Valuation Justification Ratio</h3><p>{html.escape(v_txt)}</p>')
    frag = _house_note(memo_bars(frag, track, len(d['sections'])), d)
    summary = {'overall': d['_overall'], 'band': d['_band'][0],
               'marquee_pts': mpts, 'marquee_score': mscore, 'vjr': v_r, 'vjr_text': v_txt,
               'sections': {s['name']: round(s['_score'], 2) for s in d['sections']}, **_house_summary(d)}
    return summary, frag, _strip(d)


def memo_bars(frag: str, track: str = 'buyout', n_sections: int | None = None) -> str:
    """The memo shows only the section score bars + overall (the deal lead's choice); criteria detail, weights
    rationale, Marquee GP Index and VJR are shown in the app's Scorecard tab."""
    i = frag.find('<h2 class="sc-h">')
    j = frag.find('<h3 class="sc-h3">', i)
    bars = frag[i:j if j > 0 else None] if i >= 0 else ''
    n = (n_sections or (6 if track == 'vg' else 5)) + 1        # Part III: one sub-section per framework section, then this
    head = f'III.{n} · Framework Scoring Summary'
    return (f'<h2>{head}</h2>\n<section class="scorecard">{bars}'
            '<p class="sc-meta"><small>Criteria scores and rationales, section weightings'
            + (', Marquee GP Index and VJR' if track == 'vg' else '') + ' are in the Scorecard tab.</small></p></section>')


def no_risk(frag: str) -> str:
    """ADCG does not score risk: drop the risk card, the risk gauge and the risk formula from the rendered scorecard."""
    frag = re.sub(r'<div class="vcard"><div class="k">Derived Risk Score</div>.*?</span></div>\s*', '', frag, flags=re.S)
    frag = re.sub(r'<div class="gauge-wrap">.*?</div>\s*<div><svg.*?</svg></div>\s*</div>', '', frag, flags=re.S)
    frag = frag.replace('\n    Risk = (10 − ADCG) × 10.', '').replace(' Risk = (10 − ADCG) × 10.', '')
    return frag.replace('<div class="verdict">', '<div class="verdict two">')


def _strip(d: dict) -> dict:
    out = copy.deepcopy(d)
    out.pop('_band', None)
    for s in out.get('sections', []):
        s['score'] = round(s.pop('_score', 0.0), 2)
    out['overall'] = out.pop('_overall', None)
    out.pop('_risk', None)
    out.pop('risk_register', None)
    return out


def score_header(sc: dict, summary: dict, track: str) -> str:
    """The panel at the top of the memo's Part III (deal lead, 18-Nov-26): the total score and band on the left; the
    GP tier(s), the framework score before ADCG preferences and the deal-specific factors on the right."""
    esc = html.escape
    name = {'buyout': 'ADCG Buyout', 'cv': 'ADCG CV', 'vg': 'ADCG Venture Growth'}.get(track, 'ADCG')
    overall, band = summary.get('overall'), summary.get('band', '')
    rows = []
    gp = (sc or {}).get('gp_tiers') or {}
    for key, label in (('sponsor_tier', 'Sponsor' if track == 'buyout' else 'Underlying sponsor'),
                       ('secondary_tier', 'Lead secondaries investor')):
        g = gp.get(key)
        if g:
            tier = esc(str(g.get('tier') or ''))
            sc_ = f' · {g["score"]:g}/10' if g.get('score') is not None else ''
            rows.append(f'<div class="sh-row"><span>{label}</span><b>{esc(str(g.get("firm") or ""))}</b>'
                        f'<em class="sh-tier">{tier}{sc_}</em></div>')
    co = (sc or {}).get('co_sponsor_tier')
    if co:
        sc_ = f' · {co["score"]:g}/10' if co.get('score') is not None else ''
        rows.append(f'<div class="sh-row"><span>Co-sponsor</span><b>{esc(str(co.get("firm") or ""))}</b>'
                    f'<em class="sh-tier">{esc(str(co.get("tier") or ""))}{sc_}</em></div>')
    if track == 'vg' and summary.get('marquee_score') is not None:
        rows.append(f'<div class="sh-row"><span>Marquee GP Index</span><b>{summary["marquee_score"]:g}/10</b>'
                    f'<em class="sh-tier">{summary.get("marquee_pts", 0):g} pts</em></div>')
    if summary.get('house_adj'):
        rows.append(f'<div class="sh-row"><span>Framework score</span><b>{summary["framework_overall"]:.2f}</b>'
                    f'<em>ADCG preferences {summary["house_adj"]:+.2f}</em></div>')
    ds = next((s for s in (sc or {}).get('sections') or [] if s.get('deal_specific') or s.get('name') == DS_NAME), None)
    if ds:
        rows.append(f'<div class="sh-row"><span>Deal-specific factors ({ds.get("weight", 0):g}%)</span>'
                    f'<b>{"; ".join(esc(c["name"]) for c in ds.get("criteria") or [])}</b></div>')
    num = f'{overall:.2f}' if isinstance(overall, (int, float)) else '—'
    return (f'<div class="sc-head"><div class="sh-score"><span>{esc(name)}</span><b>{num}</b><em>{esc(band)}</em></div>'
            f'<div class="sh-side">{"".join(rows) or "<div class=sh-row><span>Scored on the framework below</span></div>"}</div></div>')
