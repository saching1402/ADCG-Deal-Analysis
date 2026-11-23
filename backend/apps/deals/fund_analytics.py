"""Track-record analytics for ADCG Fund Manager Evaluation (deal lead, 20-Nov-26).

Reads the manager's portfolio / track-record workbook from the data room — the deal-by-deal schedule, the fund-level
table and, when present, dated cash flows (long or wide layout) — and computes everything deterministically:
pooled MOIC and IRR by fund, sector, deal lead and vintage, loss ratio, results excluding the top deals, dispersion,
concentration of gains. Renders the memo charts (inline SVG) and a standalone HTML dashboard.

The model never computes these numbers; when no workbook can be parsed, the integrate stage extracts the deal schedule
from the fact sheets into the same shape and this module computes from that.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import json
import math
import re
from collections import defaultdict

# ── header detection ─────────────────────────────────────────────────────────
SYN = {
    'name': ['portfolio company', 'company', 'investment', 'deal name', 'deal', 'asset', 'platform', 'name', 'holding'],
    'fund': ['fund', 'vehicle', 'fund name'],
    'sector': ['sector', 'industry', 'vertical', 'theme'],
    'lead': ['deal lead', 'lead partner', 'deal partner', 'lead', 'partner', 'deal team'],
    'region': ['region', 'geography', 'country', 'hq'],
    'entry': ['entry date', 'investment date', 'date invested', 'initial investment date', 'acquisition date',
              'date of investment', 'close date', 'entry', 'invested date', 'initial date'],
    'exit': ['exit date', 'realization date', 'realisation date', 'date exited', 'exit'],
    'invested': ['total invested', 'invested capital', 'capital invested', 'equity invested', 'amount invested',
                 'invested', 'total cost', 'cost', 'equity'],
    'realized': ['realized proceeds', 'realised proceeds', 'realized value', 'realised value', 'realized', 'realised',
                 'proceeds', 'distributions'],
    'unrealized': ['unrealized value', 'unrealised value', 'remaining value', 'fair value', 'unrealized', 'unrealised',
                   'nav', 'residual value'],
    'total': ['total value', 'total'],
    'moic': ['gross moic', 'moic', 'gross multiple', 'multiple', 'tvpi', 'gross tvpi', 'mom'],
    'irr': ['gross irr', 'irr'],
    'ev': ['enterprise value', 'entry ev', 'ev at entry', 'tev', 'ev', 'deal size'],
    'status': ['status', 'realization status', 'realized / unrealized', 'realised / unrealised'],
}
FUND_SYN = {
    'fund': ['fund', 'fund name', 'vehicle'],
    'vintage': ['vintage', 'vintage year', 'year'],
    'size': ['fund size', 'commitments', 'committed capital', 'size'],
    'invested': ['invested', 'invested capital', 'paid-in', 'paid in', 'called'],
    'gross_irr': ['gross irr'],
    'net_irr': ['net irr'],
    'gross_moic': ['gross moic', 'gross multiple', 'gross tvpi'],
    'net_tvpi': ['net tvpi', 'net moic', 'net multiple', 'tvpi'],
    'dpi': ['dpi', 'net dpi'],
    'quartile': ['quartile', 'benchmark quartile'],
}
SKIP_ROW = re.compile(r'^(total|subtotal|sub-total|grand total|fund total|portfolio total|realized total|unrealized total|'
                      r'realised total|unrealised total|weighted|average|mean|median|n/?a)\b', re.I)


def _norm(v) -> str:
    return re.sub(r'\s+', ' ', str(v or '').strip().lower()).replace('\n', ' ')


def _match(header: str, syns: list[str]) -> int:
    """Higher = better match; 0 = none."""
    h = _norm(header)
    if not h:
        return 0
    for i, s in enumerate(syns):
        if h == s:
            return 100 - i
    for i, s in enumerate(syns):
        if re.search(r'(^|[^a-z])' + re.escape(s) + r'([^a-z]|$)', h):
            return 50 - i
    return 0


def _map_header(cells: list, syn: dict) -> dict:
    """Column index for each field (best match, each column used once; net columns never mapped to gross fields)."""
    cand = []
    for ci, c in enumerate(cells):
        h = _norm(c)
        if not h or len(h) > 60:
            continue
        for f, s in syn.items():
            sc = _match(h, s)
            if sc and not (f in ('irr', 'moic', 'gross_irr', 'gross_moic') and 'net' in h):
                cand.append((sc, f, ci))
    out, used = {}, set()
    for sc, f, ci in sorted(cand, reverse=True):
        if f not in out and ci not in used:
            out[f] = ci
            used.add(ci)
    return out


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    s = str(v).strip().replace(',', '').replace('$', '').replace('€', '').replace('£', '')
    neg = s.startswith('(') and s.endswith(')')
    s = s.strip('()').rstrip('x×X').strip()
    pct = s.endswith('%')
    s = s.rstrip('%').strip()
    try:
        f = float(s)
    except ValueError:
        return None
    f = -f if neg else f
    return f / 100 if pct else f


def _date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and 20000 < v < 80000:  # Excel serial
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    s = str(v or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%b-%y', '%b %Y', '%Y', '%d-%b-%Y', '%d-%b-%y', '%B %Y', '%m/%Y'):
        try:
            d = dt.datetime.strptime(s, fmt).date()
            return d
        except ValueError:
            pass
    m = re.match(r'^(?:q([1-4])\s*)?((?:19|20)\d{2})$', s, re.I)
    if m:
        return dt.date(int(m.group(2)), 3 * int(m.group(1) or 1), 1)
    return None


def _pct(v):
    """IRR cells come as 0.25, 25 or '25%'."""
    f = _num(v)
    if f is None:
        return None
    return f / 100 if abs(f) > 3 else f


# ── workbook reading ─────────────────────────────────────────────────────────
def _rows(ws, limit=4000):
    out = []
    for r in ws.iter_rows(values_only=True):
        out.append(list(r))
        if len(out) >= limit:
            break
    return out


def _deal_table(rows) -> list[dict]:
    best = None
    for hi, r in enumerate(rows[:40]):
        m = _map_header(r, SYN)
        if 'name' in m and 'invested' in m and ({'realized', 'unrealized', 'total', 'moic'} & set(m)):
            score = len(m)
            if not best or score > best[0]:
                best = (score, hi, m)
    if not best:
        return []
    _, hi, m = best
    out, blank = [], 0
    for r in rows[hi + 1:]:
        name = str(r[m['name']] if m['name'] < len(r) else '' or '').strip() if m['name'] < len(r) else ''
        if not name or name.lower() == 'none':
            blank += 1
            if blank > 3 and out:
                break
            continue
        blank = 0
        if SKIP_ROW.match(name):
            continue
        g = lambda f: r[m[f]] if f in m and m[f] < len(r) else None
        inv = _num(g('invested'))
        if not inv or inv <= 0:
            continue
        d = {'name': name[:120], 'fund': str(g('fund') or '').strip()[:60], 'sector': str(g('sector') or '').strip()[:60],
             'lead': str(g('lead') or '').strip()[:60], 'region': str(g('region') or '').strip()[:40],
             'entry': _date(g('entry')), 'exit': _date(g('exit')), 'invested': inv,
             'realized': _num(g('realized')), 'unrealized': _num(g('unrealized')), 'total': _num(g('total')),
             'moic': _num(g('moic')), 'irr': _pct(g('irr')), 'ev': _num(g('ev')),
             'status': str(g('status') or '').strip()[:30]}
        out.append(d)
    return out


def _fund_table(rows) -> list[dict]:
    for hi, r in enumerate(rows[:40]):
        m = _map_header(r, FUND_SYN)
        if 'fund' in m and ({'net_irr', 'net_tvpi', 'dpi'} & set(m)) and len(m) >= 3:
            out = []
            for rr in rows[hi + 1:hi + 40]:
                name = str(rr[m['fund']] if m['fund'] < len(rr) else '' or '').strip()
                if not name or name.lower() == 'none':
                    if out:
                        break
                    continue
                g = lambda f: rr[m[f]] if f in m and m[f] < len(rr) else None
                vint = g('vintage')
                out.append({'fund': name[:60], 'vintage': int(_num(vint)) if _num(vint) and 1980 < _num(vint) < 2100 else None,
                            'size': _num(g('size')), 'invested': _num(g('invested')), 'gross_irr': _pct(g('gross_irr')),
                            'net_irr': _pct(g('net_irr')), 'gross_moic': _num(g('gross_moic')), 'net_tvpi': _num(g('net_tvpi')),
                            'dpi': _num(g('dpi')), 'quartile': str(g('quartile') or '').strip()[:20]})
            if out:
                return out
    return []


def _cashflows(rows, names: set[str]) -> dict[str, list[tuple[dt.date, float]]]:
    """Long (date, deal, amount) or wide (dates down, deals across) layouts. Sign: invested negative, proceeds positive
    (flipped if the sheet records contributions as positive and distributions as negative is not knowable — we assume
    the common LP convention: contributions negative)."""
    keys = {_norm(n): n for n in names}
    # long layout
    for hi, r in enumerate(rows[:30]):
        hs = [_norm(c) for c in r]
        di = next((i for i, h in enumerate(hs) if h in ('date', 'cash flow date', 'transaction date', 'value date')), None)
        ai = next((i for i, h in enumerate(hs) if h in ('amount', 'cash flow', 'cashflow', 'net cash flow', 'value', 'flow')), None)
        ni = next((i for i, h in enumerate(hs) if _match(h, SYN['name']) >= 40), None)
        if di is not None and ai is not None and ni is not None:
            out = defaultdict(list)
            for rr in rows[hi + 1:]:
                d, a = _date(rr[di] if di < len(rr) else None), _num(rr[ai] if ai < len(rr) else None)
                n = keys.get(_norm(rr[ni] if ni < len(rr) else ''))
                if d and a is not None and n:
                    out[n].append((d, a))
            if out:
                return dict(out)
    # wide layout: header row with ≥3 deal names, first column dates
    for hi, r in enumerate(rows[:30]):
        cols = {i: keys[_norm(c)] for i, c in enumerate(r) if _norm(c) in keys}
        if len(cols) >= 3:
            out = defaultdict(list)
            for rr in rows[hi + 1:]:
                d = _date(rr[0]) if rr else None
                if not d:
                    continue
                for i, n in cols.items():
                    a = _num(rr[i] if i < len(rr) else None)
                    if a:
                        out[n].append((d, a))
            if out:
                return dict(out)
    return {}


def read_workbook(data: bytes) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheets = [(ws.title, _rows(ws)) for ws in wb.worksheets]
    deals, src = [], ''
    for title, rows in sheets:
        t = _deal_table(rows)
        if len(t) > len(deals):
            deals, src = t, title
    funds = next((f for _, rows in sheets if (f := _fund_table(rows))), [])
    cfs = {}
    if deals:
        names = {d['name'] for d in deals}
        for title, rows in sheets:
            if title == src:
                continue
            cfs = _cashflows(rows, names)
            if cfs:
                break
    return {'deals': deals, 'funds': funds, 'cashflows': cfs, 'sheet': src}


def from_files(files) -> dict | None:
    """Best workbook in the data room (most deals parsed)."""
    from .extract import SHEETS, SHEETS_CONVERT, ext_of, soffice_convert
    best = None
    for f in files:
        ext = ext_of(f.original_name)
        if ext not in SHEETS:
            continue
        try:
            with f.file.open('rb') as fh:
                data = fh.read()
            if ext in SHEETS_CONVERT:
                data = soffice_convert(data, ext, 'xlsx')
            r = read_workbook(data)
        except Exception:  # noqa: BLE001 — a workbook we can't parse is simply skipped
            continue
        if r['deals'] and (not best or len(r['deals']) > len(best['deals'])):
            best = {**r, 'file': f.original_name}
    return best


# ── maths ────────────────────────────────────────────────────────────────────
def xirr(flows: list[tuple[dt.date, float]]) -> float | None:
    flows = sorted((d, a) for d, a in flows if a)
    if len(flows) < 2 or not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        return None
    t0 = flows[0][0]
    yrs = [((d - t0).days / 365.25, a) for d, a in flows]
    f = lambda r: sum(a / (1 + r) ** t for t, a in yrs)
    lo, hi = -0.99, 10.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < 1e-7:
            break
        if flo * fm < 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return round(mid, 4)


def _value(d: dict) -> float:
    if d.get('total') is not None:
        return d['total']
    if d.get('realized') is not None or d.get('unrealized') is not None:
        return (d.get('realized') or 0) + (d.get('unrealized') or 0)
    if d.get('moic') is not None:
        return d['invested'] * d['moic']
    return 0.0


def _synth_flows(d: dict) -> list[tuple[dt.date, float]]:
    """Two-point flows when only entry / exit dates are known (unrealised value dated at the valuation date)."""
    if not d.get('entry'):
        return []
    end = d.get('exit') or d.get('_asof')
    if not end or end <= d['entry']:
        return []
    return [(d['entry'], -d['invested']), (end, _value(d))]


def compute(src: dict, as_of: dt.date | None = None) -> dict:
    """Analytics from {'deals', 'funds', 'cashflows'}; deals may come from a workbook or from the integrate JSON."""
    as_of = as_of or dt.date.today()
    cfs = src.get('cashflows') or {}
    deals = []
    for d in src.get('deals') or []:
        d = dict(d)
        for k in ('entry', 'exit'):
            if isinstance(d.get(k), str):
                d[k] = _date(d[k])
        d['invested'] = _num(d.get('invested')) or 0
        if d['invested'] <= 0:
            continue
        for k in ('realized', 'unrealized', 'total', 'moic', 'ev'):
            d[k] = _num(d.get(k)) if not isinstance(d.get(k), float) else d[k]
        d['irr'] = _pct(d.get('irr')) if not isinstance(d.get('irr'), float) else d['irr']
        d['_asof'] = as_of
        d['value'] = round(_value(d), 4)
        d['moic_c'] = round(d['value'] / d['invested'], 2)
        flows = cfs.get(d['name']) or []
        d['irr_c'] = xirr(flows) if flows else None
        if d['irr_c'] is None and d.get('irr') is None:
            d['irr_c'] = xirr(_synth_flows(d))
        d['irr_best'] = d['irr_c'] if d['irr_c'] is not None else d.get('irr')
        d['vintage'] = d['entry'].year if d.get('entry') else None
        d['realised'] = bool(d.get('exit')) or (d.get('unrealized') in (0, 0.0) and (d.get('realized') or 0) > 0) \
            or 'realized' == _norm(d.get('status')) or 'realised' == _norm(d.get('status'))
        d['_flows'] = flows or _synth_flows(d)
        deals.append(d)
    if not deals:
        return {}

    def pool(ds: list[dict]) -> dict:
        inv = sum(x['invested'] for x in ds)
        val = sum(x['value'] for x in ds)
        flows = [f for x in ds for f in x['_flows']]
        irr = xirr(flows) if flows else None
        wirr = None
        w = [(x['invested'], x['irr_best']) for x in ds if x.get('irr_best') is not None]
        if w and irr is None:
            wirr = round(sum(a * b for a, b in w) / sum(a for a, _ in w), 4)
        losses = sum(x['invested'] for x in ds if x['moic_c'] < 1.0)
        return {'n': len(ds), 'invested': round(inv, 2), 'value': round(val, 2), 'moic': round(val / inv, 2) if inv else None,
                'irr': irr if irr is not None else wirr, 'irr_basis': 'cash flows' if irr is not None else ('invested-weighted deal IRRs' if wirr is not None else ''),
                'loss_ratio': round(losses / inv, 3) if inv else None,
                'realised_share': round(sum(x['value'] for x in ds if x['realised']) / val, 3) if val else None}

    def group(key):
        g = defaultdict(list)
        for x in deals:
            g[str(x.get(key) or '—')].append(x)
        return {k: pool(v) for k, v in sorted(g.items(), key=lambda kv: (kv[0] == '—', kv[0]))}

    overall = pool(deals)
    by_gain = sorted(deals, key=lambda x: x['value'] - x['invested'], reverse=True)
    total_gain = sum(max(x['value'] - x['invested'], 0) for x in deals)      # gross gains (losses not netted off)
    ex = {f'ex_top_{n}': {**pool(by_gain[n:]), 'excluded': [x['name'] for x in by_gain[:n]]}
          for n in (1, 2, 3) if len(deals) > n + 2}
    buckets = [('< 0.5×', 0, 0.5), ('0.5–1.0×', 0.5, 1.0), ('1.0–2.0×', 1.0, 2.0), ('2.0–3.0×', 2.0, 3.0),
               ('3.0–5.0×', 3.0, 5.0), ('≥ 5.0×', 5.0, 1e9)]
    dist = [{'bucket': b, 'n': sum(1 for x in deals if lo <= x['moic_c'] < hi),
             'invested': round(sum(x['invested'] for x in deals if lo <= x['moic_c'] < hi), 2)} for b, lo, hi in buckets]
    moics = sorted(x['moic_c'] for x in deals)
    q = lambda p: moics[min(len(moics) - 1, int(p * (len(moics) - 1) + 0.5))]
    top2 = sum(x['value'] - x['invested'] for x in by_gain[:2])
    out = {
        'as_of': as_of.isoformat(), 'source': src.get('file') or src.get('source') or '', 'sheet': src.get('sheet', ''),
        'irr_basis': overall['irr_basis'], 'cashflows': bool(cfs),
        'overall': overall, **ex,
        'by_fund': group('fund'), 'by_sector': group('sector'), 'by_lead': group('lead'),
        'by_vintage': group('vintage'), 'by_region': group('region'),
        'distribution': dist,
        'dispersion': {'p25': q(0.25), 'median': q(0.5), 'p75': q(0.75), 'max': moics[-1], 'min': moics[0],
                       'share_above_2x': round(sum(1 for m in moics if m >= 2) / len(moics), 3),
                       'share_above_3x': round(sum(1 for m in moics if m >= 3) / len(moics), 3)},
        'concentration': {'top2_share_of_gains': round(top2 / total_gain, 3) if total_gain > 0 else None,
                          'top2': [x['name'] for x in by_gain[:2]]},
        'funds': src.get('funds') or [],
        'deals': [{k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in x.items() if not k.startswith('_')}
                  for x in sorted(deals, key=lambda x: (str(x.get('fund') or ''), x.get('entry') or dt.date.min))],
    }
    return out


def brief(a: dict) -> str:
    """Compact text for the prompts (the model must use these numbers exactly)."""
    if not a or not a.get('overall'):
        return 'TRACK-RECORD ANALYTICS: no deal-by-deal schedule could be parsed from the data room.'
    f = lambda x: '—' if x is None else (f'{x:.1%}' if isinstance(x, float) and abs(x) < 3 else f'{x:,.2f}')
    m = lambda x: '—' if x is None else f'{x:.2f}×'
    o = a['overall']
    lines = [f'TRACK-RECORD ANALYTICS (computed by the app from {a.get("source") or "the deal schedule"}'
             f'{" / sheet " + a["sheet"] if a.get("sheet") else ""}; IRR basis: {a.get("irr_basis") or "n/a"}) — use EXACTLY:',
             f'- All deals: {o["n"]} deals, invested {o["invested"]:,.1f}, value {o["value"]:,.1f}, gross MOIC {m(o["moic"])}, '
             f'gross IRR {f(o["irr"])}, loss ratio {f(o["loss_ratio"])}, realised share of value {f(o["realised_share"])}']
    for n in (1, 2, 3):
        e = a.get(f'ex_top_{n}')
        if e:
            lines.append(f'- Excluding top {n} ({", ".join(e["excluded"])}): MOIC {m(e["moic"])}, IRR {f(e["irr"])}')
    c = a.get('concentration') or {}
    if c.get('top2_share_of_gains') is not None:
        lines.append(f'- Top 2 deals = {f(c["top2_share_of_gains"])} of total gains')
    dsp = a.get('dispersion') or {}
    lines.append(f'- MOIC dispersion: min {m(dsp.get("min"))}, P25 {m(dsp.get("p25"))}, median {m(dsp.get("median"))}, '
                 f'P75 {m(dsp.get("p75"))}, max {m(dsp.get("max"))}; ≥2× {f(dsp.get("share_above_2x"))}, ≥3× {f(dsp.get("share_above_3x"))}')
    for title, key in (('By fund', 'by_fund'), ('By sector', 'by_sector'), ('By deal lead', 'by_lead'), ('By vintage', 'by_vintage')):
        g = a.get(key) or {}
        if len(g) > 1 or (g and '—' not in g):
            lines.append(f'- {title}: ' + '; '.join(f'{k}: {v["n"]} deals, {m(v["moic"])}, IRR {f(v["irr"])}, loss {f(v["loss_ratio"])}'
                                                    for k, v in g.items()))
    if a.get('funds'):
        lines.append('- Fund table (from the workbook): ' + '; '.join(
            f'{x["fund"]} ({x.get("vintage") or "?"}): net IRR {f(x.get("net_irr"))}, net TVPI {m(x.get("net_tvpi"))}, DPI {m(x.get("dpi"))}'
            for x in a['funds']))
    return '\n'.join(lines)


# ── vintage-year quartile benchmarking ──────────────────────────────────────
# The model supplies the BENCHMARK THRESHOLDS (from the manager's own materials first, else found on the web for the right
# peer group and vintage); the app places each fund in its quartile — the model never asserts a quartile itself.
QMETRICS = (('net_irr', 'Net IRR', True), ('net_tvpi', 'Net TVPI', False), ('dpi', 'DPI', False))


def _thr(b: dict, metric: str, pct: bool) -> dict | None:
    """{uq, med, lq} for one metric from a benchmark row (accepts several spellings); None if incomplete."""
    src = b.get(metric) or {}
    if not isinstance(src, dict):
        return None
    conv = _pct if pct else _num
    out = {}
    for k, alts in (('uq', ('uq', 'upper_quartile', 'top_quartile', 'q1')), ('med', ('med', 'median', 'q2')),
                    ('lq', ('lq', 'lower_quartile', 'bottom_quartile', 'q3'))):
        v = next((conv(src[x]) for x in alts if src.get(x) not in (None, '')), None)
        out[k] = v
    if out['uq'] is None or out['med'] is None:
        return None
    if out['lq'] is not None and not (out['lq'] <= out['med'] <= out['uq']):
        return None                                          # inconsistent thresholds — do not use
    return out


def _quartile(v, t) -> int | None:
    if v is None or not t:
        return None
    if v >= t['uq']:
        return 1
    if v >= t['med']:
        return 2
    if t['lq'] is None:
        return 3                                             # below median; Q3 vs Q4 undeterminable → treated as Q3
    return 3 if v >= t['lq'] else 4


def _fund_key(x) -> str:
    return re.sub(r'[^a-z0-9]', '', str(x or '').lower())


def _claimed(q) -> int | None:
    s = str(q or '').lower()
    m = re.search(r'\b(?:q|quartile\s*)([1-4])\b|([1-4])(?:st|nd|rd|th)\s*quartile', s)
    if m:
        return int(m.group(1) or m.group(2))
    if 'top' in s or 'first' in s or 'upper' in s:
        return 1
    if 'second' in s:
        return 2
    if 'third' in s:
        return 3
    if 'bottom' in s or 'fourth' in s or 'lower' in s:
        return 4
    return None


def benchmark(funds: list[dict], benchmarks: list[dict], as_of: dt.date | None = None) -> dict:
    """Place every fund in its vintage-year quartile for each metric. Returns {peer_group, rows[], summary{}}."""
    as_of = as_of or dt.date.today()
    bm = [b for b in benchmarks or [] if isinstance(b, dict)]
    by_fund = {_fund_key(b.get('fund')): b for b in bm if b.get('fund')}
    by_vint = {}
    for b in bm:
        v = _num(b.get('vintage'))
        if v:
            by_vint.setdefault(int(v), b)
    rows = []
    for f in funds or []:
        vint = int(_num(f.get('vintage'))) if _num(f.get('vintage')) else None
        b = by_fund.get(_fund_key(f.get('fund'))) or (by_vint.get(vint) if vint else None)
        row = {'fund': f.get('fund'), 'vintage': vint, 'claimed': str(f.get('quartile') or '')[:30],
               'age': (as_of.year - vint) if vint else None, 'metrics': {}, 'benchmark': None}
        if b:
            row['benchmark'] = {k: b.get(k) for k in ('peer_group', 'source', 'as_of', 'origin', 'note')}
        for key, label, pct in QMETRICS:
            val = _pct(f.get(key)) if pct else _num(f.get(key))
            t = _thr(b, key, pct) if b else None
            row['metrics'][key] = {'value': val, 'thr': t, 'q': _quartile(val, t)}
        qs = [row['metrics'][k]['q'] for k in ('net_irr', 'net_tvpi') if row['metrics'][k]['q']]
        row['q'] = int(sum(qs) / len(qs) + 0.5) if qs else None   # IRR & TVPI; a split rounds to the more conservative quartile
        row['q_tvpi'] = row['metrics']['net_tvpi']['q']
        row['q_irr'] = row['metrics']['net_irr']['q']
        c = _claimed(row['claimed'])
        row['claim_check'] = (None if c is None or row['q'] is None else
                              'confirmed' if c == row['q'] else 'better than claimed' if row['q'] < c else 'overstated')
        row['too_early'] = bool(row['age'] is not None and row['age'] < 4)
        rows.append(row)
    rated = [r for r in rows if r['q']]
    summary = {'funds': len(rows), 'rated': len(rated),
               'top_quartile': sum(1 for r in rated if r['q'] == 1), 'top_half': sum(1 for r in rated if r['q'] <= 2),
               'overstated': [r['fund'] for r in rows if r['claim_check'] == 'overstated'],
               'no_benchmark': [r['fund'] for r in rows if not r['benchmark']]}
    peer = next((b.get('peer_group') for b in bm if b.get('peer_group')), '')
    return {'peer_group': peer, 'rows': rows, 'summary': summary}


QLAB = {1: '1st quartile', 2: '2nd quartile', 3: '3rd quartile', 4: '4th quartile'}
QCOL = {1: '#1d7a47', 2: '#8fb35a', 3: '#d99a2b', 4: '#7a2230'}


def svg_quartiles(q: dict, metric='net_tvpi') -> str:
    """One row per fund: the LQ–median–UQ band of its vintage and the fund's own value as a dot."""
    rows = [r for r in q.get('rows') or [] if r['metrics'][metric]['thr'] and r['metrics'][metric]['value'] is not None]
    if not rows:
        return ''
    pct = metric == 'net_irr'
    vals = [v for r in rows for v in (r['metrics'][metric]['value'], *[x for x in r['metrics'][metric]['thr'].values() if x is not None])]
    lo, hi = min(0.0, min(vals)), max(vals) * 1.12 or 1
    W, L, R, T, rh = 640, 150, 70, 26, 34
    H = T + rh * len(rows) + 30
    X = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    fmt = (lambda v: f'{v:.0%}') if pct else (lambda v: f'{v:.2f}×')
    g = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Sans,Arial" role="img">']
    for i, r in enumerate(rows):
        m = r['metrics'][metric]; t = m['thr']; y = T + i * rh
        lq = t['lq'] if t['lq'] is not None else lo
        g.append(f'<text x="{L - 10}" y="{y + 15}" text-anchor="end" font-size="11" fill="#1a1c1a">{_esc(str(r["fund"])[:22])}'
                 f'{" (" + str(r["vintage"]) + ")" if r["vintage"] else ""}</text>')
        g.append(f'<rect x="{X(lo):.1f}" y="{y + 6}" width="{X(lq) - X(lo):.1f}" height="14" fill="#f1e3e5"/>')
        g.append(f'<rect x="{X(lq):.1f}" y="{y + 6}" width="{X(t["med"]) - X(lq):.1f}" height="14" fill="#f6e7c8"/>')
        g.append(f'<rect x="{X(t["med"]):.1f}" y="{y + 6}" width="{X(t["uq"]) - X(t["med"]):.1f}" height="14" fill="#dfe9cf"/>')
        g.append(f'<rect x="{X(t["uq"]):.1f}" y="{y + 6}" width="{X(hi) - X(t["uq"]):.1f}" height="14" fill="#cfe5d6"/>')
        g.append(f'<line x1="{X(t["med"]):.1f}" x2="{X(t["med"]):.1f}" y1="{y + 3}" y2="{y + 23}" stroke="#6b6b6b" stroke-width="1"/>')
        col = QCOL.get(m['q'], '#5b6678')
        g.append(f'<circle cx="{X(m["value"]):.1f}" cy="{y + 13}" r="6.5" fill="{col}" stroke="#fff" stroke-width="1.5">'
                 f'<title>{_esc(r["fund"])}: {fmt(m["value"])} — UQ {fmt(t["uq"])}, median {fmt(t["med"])}'
                 f'{", LQ " + fmt(t["lq"]) if t["lq"] is not None else ""}</title></circle>')
        g.append(f'<text x="{W - R + 8}" y="{y + 17}" font-size="11" font-weight="600" fill="{col}">{fmt(m["value"])} · Q{m["q"]}</text>')
    for v in (lo, (lo + hi) / 2, hi):
        g.append(f'<text x="{X(v):.1f}" y="{H - 12}" text-anchor="middle" font-size="9" fill="#6b6b6b">{fmt(v)}</text>')
    g.append(f'<text x="{L}" y="12" font-size="9" fill="#6b6b6b">Bands = the vintage\'s quartiles: red 4th · amber 3rd · light green 2nd '
             f'· green 1st; tick = median</text></svg>')
    return ''.join(g)


def quartile_block(q: dict) -> str:
    """Memo §3: quartile table + charts, inserted by the app under '3 · Track Record'."""
    if not q or not q.get('rows'):
        return ''
    pct = lambda v: '—' if v is None else f'{v:.1%}'
    mx = lambda v: '—' if v is None else f'{v:.2f}×'
    def cell(r, k, f):
        m = r['metrics'][k]
        if m['value'] is None:
            return '<td class="num">—</td>'
        if not m['thr']:
            return f'<td class="num">{f(m["value"])}</td>'
        return (f'<td class="num">{f(m["value"])} <span class="qpill q{m["q"]}">Q{m["q"]}</span>'
                f'<span class="ref">UQ {f(m["thr"]["uq"])} · med {f(m["thr"]["med"])}</span></td>')
    trs = ''
    for r in q['rows']:
        b = r.get('benchmark') or {}
        chk = {'confirmed': 'Confirmed', 'better than claimed': 'Better than claimed', 'overstated': 'Overstated'}.get(r['claim_check'] or '', '')
        early = ' <span class="ref">too early to judge</span>' if r['too_early'] else ''
        check = f' <b class="qchk {r["claim_check"].split()[0]}">{chk}</b>' if chk else ''
        asof = (' · ' + _esc(b['as_of'])) if b.get('as_of') else ''
        origin = {'materials': " · manager's materials", 'web': ' · web'}.get(b.get('origin') or '', '')
        trs += (f'<tr><td>{_esc(r["fund"])}{early}</td>'
                f'<td>{r["vintage"] or ""}</td>{cell(r, "net_irr", pct)}{cell(r, "net_tvpi", mx)}{cell(r, "dpi", mx)}'
                f'<td>{_esc(r["claimed"]) or "—"}{check}</td>'
                f'<td class="ref">{_esc(b.get("source") or "No benchmark found")}{asof}{origin}</td></tr>')
    s = q['summary']
    head = (f'<div class="fa-kpis"><div><span>Peer group</span><b style="font-size:15px">{_esc(q.get("peer_group") or "—")}</b></div>'
            f'<div><span>Top-quartile funds</span><b>{s["top_quartile"]} / {s["rated"]}</b></div>'
            f'<div><span>Top-half funds</span><b>{s["top_half"]} / {s["rated"]}</b></div>'
            f'<div><span>Claims overstated</span><b>{len(s["overstated"])}</b></div></div>')
    table = ('<table class="qtab"><tr><th>Fund</th><th>Vintage</th><th>Net IRR</th><th>Net TVPI</th><th>DPI</th>'
             '<th>Manager’s claim</th><th>Benchmark</th></tr>' + trs + '</table>')
    figs = ''
    for k, title in (('net_tvpi', 'Net TVPI vs the vintage-year quartiles'), ('net_irr', 'Net IRR vs the vintage-year quartiles')):
        svg = svg_quartiles(q, k)
        if svg:
            figs += _fig(svg, title, f'peer group: {q.get("peer_group") or "as stated"}', 'ADCG analysis; benchmark sources in the table')
    gap = ''
    if s['no_benchmark']:
        gap = ('<div class="gap"><b>No vintage benchmark found for:</b> ' + ', '.join(_esc(x) for x in s['no_benchmark'])
               + '. Quartile not assessed — ask the manager for its benchmark or obtain Cambridge / Burgiss / Preqin data.</div>')
    return '<div class="fa fa-q">' + head + table + figs + gap + '</div>'


def quartile_brief(q: dict) -> str:
    if not q or not q.get('rows'):
        return 'VINTAGE QUARTILES: no fund table or no benchmarks — quartile position NOT assessed.'
    f = lambda v, p: '—' if v is None else (f'{v:.1%}' if p else f'{v:.2f}×')
    out = [f'VINTAGE QUARTILES (computed by the app; peer group: {q.get("peer_group") or "as stated"}) — use EXACTLY:']
    for r in q['rows']:
        parts = []
        for k, lab, p in QMETRICS:
            m = r['metrics'][k]
            if m['value'] is None:
                continue
            parts.append(f'{lab} {f(m["value"], p)}' + (f' = Q{m["q"]} (UQ {f(m["thr"]["uq"], p)}, median {f(m["thr"]["med"], p)}'
                         + (f', LQ {f(m["thr"]["lq"], p)}' if m['thr']['lq'] is not None else '') + ')' if m['thr'] else ' (no benchmark)'))
        b = r.get('benchmark') or {}
        out.append(f'- {r["fund"]} ({r["vintage"] or "?"}): ' + '; '.join(parts)
                   + f'; overall Q{r["q"] or "?"}; manager claims "{r["claimed"] or "—"}"'
                   + (f' → {r["claim_check"].upper()}' if r['claim_check'] else '')
                   + (' — TOO EARLY TO JUDGE (<4 years)' if r['too_early'] else '')
                   + (f' [benchmark: {b.get("source")}, {b.get("as_of") or "date n/a"}, from {b.get("origin") or "?"}]' if b else ' [NO BENCHMARK]'))
    s = q['summary']
    out.append(f'- Summary: {s["top_quartile"]} of {s["rated"]} rated funds top quartile; {s["top_half"]} top half'
               + (f'; claims OVERSTATED for {", ".join(s["overstated"])}' if s['overstated'] else ''))
    return '\n'.join(out)


# ── charts (inline SVG, house style) ─────────────────────────────────────────
PAL = ['#0f2347', '#b38728', '#2453a6', '#1d7a47', '#8a6412', '#7a2230', '#5b6678', '#3c8dbc']


def _esc(s) -> str:
    return html.escape(str(s))


def svg_scatter(a: dict) -> str:
    deals = a['deals']
    funds = sorted({d.get('fund') or '—' for d in deals})
    col = {f: PAL[i % len(PAL)] for i, f in enumerate(funds)}
    W, H, L, B, T, R = 640, 300, 54, 34, 14, 14
    xmax = max(d['invested'] for d in deals) * 1.08
    ymax = max(3.5, max(d['moic_c'] for d in deals) * 1.08)
    X = lambda v: L + (W - L - R) * v / xmax
    Y = lambda v: H - B - (H - B - T) * v / ymax
    g = [f'<line x1="{L}" y1="{Y(1):.1f}" x2="{W - R}" y2="{Y(1):.1f}" stroke="#b33" stroke-dasharray="4 3" stroke-width="1"/>',
         f'<text x="{W - R}" y="{Y(1) - 4:.1f}" text-anchor="end" font-size="9" fill="#b33">1.0× (capital back)</text>']
    for t in range(0, int(ymax) + 1):
        g.append(f'<line x1="{L}" y1="{Y(t):.1f}" x2="{W - R}" y2="{Y(t):.1f}" stroke="#e4dfd2" stroke-width="0.6"/>'
                 f'<text x="{L - 6}" y="{Y(t) + 3:.1f}" text-anchor="end" font-size="9" fill="#6b6b6b">{t}×</text>')
    for i in range(5):
        v = xmax * i / 4
        g.append(f'<text x="{X(v):.1f}" y="{H - B + 14}" text-anchor="middle" font-size="9" fill="#6b6b6b">{v:,.0f}</text>')
    for d in deals:
        r = 3.5 + 7 * math.sqrt(d['invested'] / xmax)
        g.append(f'<circle cx="{X(d["invested"]):.1f}" cy="{Y(min(d["moic_c"], ymax)):.1f}" r="{r:.1f}" fill="{col[d.get("fund") or "—"]}" '
                 f'fill-opacity="0.72" stroke="#fff" stroke-width="0.8"><title>{_esc(d["name"])} — {d["moic_c"]:.2f}× on {d["invested"]:,.1f}</title></circle>')
    placed = []                                                     # label the biggest gains; nudge labels apart
    for d in sorted(deals, key=lambda x: x['value'] - x['invested'], reverse=True)[:3]:
        nm = _esc(d['name'][:22]); w = 5.2 * len(d['name'][:22])
        x0 = X(d['invested']) + 9; y0 = Y(min(d['moic_c'], ymax)) + 3
        anchor = 'start'
        if x0 + w > W - 4:                                          # no room on the right → label to the left
            x0 = X(d['invested']) - 9; anchor = 'end'
        for _ in range(6):
            lo, hi = (x0, x0 + w) if anchor == 'start' else (x0 - w, x0)
            if not any(abs(y0 - py) < 11 and lo < phi and hi > plo for plo, phi, py in placed):
                break
            y0 -= 12
        placed.append(((x0, x0 + w) if anchor == 'start' else (x0 - w, x0)) + (y0,))
        g.append(f'<text x="{x0:.1f}" y="{y0:.1f}" text-anchor="{anchor}" font-size="9" fill="#1a1c1a">{nm}</text>')
    leg = ''.join(f'<rect x="{L + 4 + i * 110}" y="{T - 10}" width="9" height="9" fill="{col[f]}"/><text x="{L + 17 + i * 110}" y="{T - 2}" font-size="9">{_esc(f[:16])}</text>'
                  for i, f in enumerate(funds[:5]))
    return (f'<svg viewBox="0 0 {W} {H + 14}" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Sans, Arial">{leg}{"".join(g)}'
            f'<text x="{(W + L) / 2}" y="{H + 10}" text-anchor="middle" font-size="9.5" fill="#3d423d">Invested capital</text>'
            f'<text x="12" y="{(H - B) / 2}" font-size="9.5" fill="#3d423d" transform="rotate(-90 12 {(H - B) / 2})" text-anchor="middle">Gross MOIC</text></svg>')


def svg_bars(rows: list[tuple[str, float, str]], unit='×', ref: float | None = 1.0, W=640) -> str:
    """Horizontal bars: (label, value, sub-label)."""
    if not rows:
        return ''
    H = 26 * len(rows) + 20
    L = 170
    vmax = max(max(v for _, v, _ in rows), ref or 0) * 1.15 or 1
    X = lambda v: L + (W - L - 150) * v / vmax
    g = []
    if ref:
        g.append(f'<line x1="{X(ref):.1f}" y1="4" x2="{X(ref):.1f}" y2="{H - 14}" stroke="#b33" stroke-dasharray="3 3" stroke-width="1"/>')
    for i, (lab, v, sub) in enumerate(rows):
        y = 10 + i * 26
        c = '#7a2230' if ref and v < ref else '#0f2347'
        g.append(f'<text x="{L - 8}" y="{y + 12}" text-anchor="end" font-size="10.5" fill="#1a1c1a">{_esc(lab[:28])}</text>'
                 f'<rect x="{L}" y="{y}" width="{max(1, X(v) - L):.1f}" height="16" rx="2" fill="{c}"/>'
                 f'<text x="{X(v) + 6:.1f}" y="{y + 12}" font-size="10.5" font-weight="600">{v:.2f}{unit}</text>'
                 f'<text x="{X(v) + 50:.1f}" y="{y + 12}" font-size="9" fill="#6b6b6b">{_esc(sub)}</text>')
    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Sans, Arial">{"".join(g)}</svg>'


def svg_hist(a: dict) -> str:
    dist = a['distribution']
    W, H, L, B = 640, 220, 40, 34
    n = max(1, max(x['n'] for x in dist))
    bw = (W - L - 20) / len(dist)
    g = []
    for i, x in enumerate(dist):
        h = (H - B - 20) * x['n'] / n
        c = '#7a2230' if i < 2 else ('#b38728' if i == 2 else '#0f2347')
        xx = L + i * bw + 6
        g.append(f'<rect x="{xx:.1f}" y="{H - B - h:.1f}" width="{bw - 12:.1f}" height="{h:.1f}" rx="2" fill="{c}"/>'
                 f'<text x="{xx + (bw - 12) / 2:.1f}" y="{H - B - h - 5:.1f}" text-anchor="middle" font-size="11" font-weight="600">{x["n"]}</text>'
                 f'<text x="{xx + (bw - 12) / 2:.1f}" y="{H - B + 14}" text-anchor="middle" font-size="10">{_esc(x["bucket"])}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Sans, Arial">{"".join(g)}'
            f'<text x="{W / 2}" y="{H - 4}" text-anchor="middle" font-size="9.5" fill="#3d423d">Number of deals by gross MOIC</text></svg>')


def _grp_rows(g: dict, limit=10) -> list[tuple[str, float, str]]:
    rows = [(k, v['moic'], f'{v["n"]} deals · IRR {v["irr"]:.0%}' if v.get('irr') is not None else f'{v["n"]} deals')
            for k, v in g.items() if v.get('moic') is not None and k != '—']
    return sorted(rows, key=lambda r: -r[1])[:limit]


def _fig(svg: str, title: str, take: str, ref: str) -> str:
    return (f'<figure class="fig">{svg}<figcaption><b>{_esc(title)}</b> — {_esc(take)} '
            f'<span class="ref">{_esc(ref)}</span></figcaption></figure>') if svg else ''


def memo_block(a: dict) -> str:
    """Section 4 charts + KPI strip, inserted by the app under '4 · Underlying Portfolio Analysis'."""
    if not a or not a.get('overall'):
        return ('<!--fa--><div class="gap"><b>No deal-by-deal schedule could be read from the data room.</b> Upload the portfolio / '
                'track-record workbook (company, fund, sector, deal lead, entry / exit, invested, realised, unrealised) to get '
                'the dispersion, loss-ratio and ex-top-deal analysis.</div><!--/fa-->')
    o = a['overall']
    pct = lambda x: '—' if x is None else f'{x:.0%}'
    ref = f'ADCG analysis of {a.get("source") or "the deal schedule"}'
    kpi = [('Deals', f'{o["n"]}'), ('Gross MOIC', f'{o["moic"]:.2f}×'), ('Gross IRR', pct(o.get('irr'))),
           ('Loss ratio', pct(o.get('loss_ratio')))]
    e2 = a.get('ex_top_2')
    if e2:
        kpi.append(('MOIC ex-top 2', f'{e2["moic"]:.2f}×'))
    c = (a.get('concentration') or {}).get('top2_share_of_gains')
    if c is not None:
        kpi.append(('Top-2 share of gains', pct(c)))
    tiles = ''.join(f'<div><span>{_esc(k)}</span><b>{_esc(v)}</b></div>' for k, v in kpi)
    ex_rows = [('All deals', o['moic'], f'IRR {pct(o.get("irr"))}')] + [
        (f'Excluding top {n}', a[f'ex_top_{n}']['moic'], f'IRR {pct(a[f"ex_top_{n}"].get("irr"))}')
        for n in (1, 2, 3) if a.get(f'ex_top_{n}')]
    parts = [f'<div class="fa-kpis">{tiles}</div>',
             _fig(svg_scatter(a), 'Deal dispersion — gross MOIC vs capital invested',
                  f'median {a["dispersion"]["median"]:.2f}×; {pct(a["dispersion"]["share_above_3x"])} of deals at 3× or better', ref),
             _fig(svg_hist(a), 'Distribution of outcomes', f'loss ratio {pct(o.get("loss_ratio"))} of invested capital in deals below 1.0×', ref),
             _fig(svg_bars(ex_rows), 'Reliance on the best deals',
                  ('excluding ' + ', '.join(e2['excluded']) + f' the record falls to {e2["moic"]:.2f}×') if e2 else 'all deals', ref)]
    for key, title in (('by_sector', 'By sector'), ('by_vintage', 'By vintage (entry year)'), ('by_lead', 'By deal lead'), ('by_fund', 'By fund')):
        rows = _grp_rows(a.get(key) or {})
        if len(rows) > 1:
            parts.append(_fig(svg_bars(rows), f'Pooled gross MOIC — {title.lower()}', f'{len(rows)} groups; IRR basis: {a.get("irr_basis") or "n/a"}', ref))
    return '<!--fa--><div class="fa">' + ''.join(parts) + '</div><!--/fa-->'


def _n0(v) -> str:
    return '' if v is None else f'{v:,.0f}'


def _p0(v) -> str:
    return '' if v is None else f'{v:.0%}'


def dashboard_html(deal_name: str, a: dict) -> str:
    """Standalone, sortable HTML dashboard (opens on its own; not the sandboxed memo frame)."""
    deals = a.get('deals') or []
    cols = [('name', 'Company'), ('fund', 'Fund'), ('sector', 'Sector'), ('lead', 'Deal lead'), ('entry', 'Entry'),
            ('exit', 'Exit'), ('invested', 'Invested'), ('value', 'Value'), ('moic_c', 'MOIC'), ('irr_best', 'IRR')]
    fmt = lambda k, v: ('' if v in (None, '') else f'{v:.0%}' if k == 'irr_best' else f'{v:.2f}×' if k == 'moic_c'
                        else f'{v:,.1f}' if isinstance(v, (int, float)) else _esc(v))
    rows = ''.join('<tr>' + ''.join(f'<td data-v="{_esc(d.get(k) if d.get(k) is not None else "")}" class="{"num" if k in ("invested", "value", "moic_c", "irr_best") else ""}'
                                    f'{" neg" if k == "moic_c" and (d.get(k) or 0) < 1 else ""}">{fmt(k, d.get(k))}</td>' for k, _ in cols) + '</tr>' for d in deals)
    funds = ''
    if a.get('funds'):
        fx = lambda v, p=False: '' if v is None else (f'{v:.1%}' if p else f'{v:.2f}×' if isinstance(v, float) else _esc(v))
        funds = ('<h2>Fund-level track record</h2><table><tr><th>Fund</th><th>Vintage</th><th>Size</th><th>Gross IRR</th><th>Net IRR</th>'
                 '<th>Gross MOIC</th><th>Net TVPI</th><th>DPI</th><th>Quartile</th></tr>' + ''.join(
                     f'<tr><td>{_esc(x["fund"])}</td><td>{x.get("vintage") or ""}</td><td class="num">{_n0(x.get("size"))}</td>'
                     f'<td class="num">{fx(x.get("gross_irr"), True)}</td><td class="num">{fx(x.get("net_irr"), True)}</td><td class="num">{fx(x.get("gross_moic"))}</td>'
                     f'<td class="num">{fx(x.get("net_tvpi"))}</td><td class="num">{fx(x.get("dpi"))}</td><td>{_esc(x.get("quartile") or "")}</td></tr>' for x in a['funds'])
                 + '</table>')

    def grp(title, g):
        if not g:
            return ''
        return (f'<h3>{_esc(title)}</h3><table><tr><th></th><th>Deals</th><th>Invested</th><th>Value</th><th>MOIC</th><th>IRR</th><th>Loss ratio</th></tr>'
                + ''.join(f'<tr><td>{_esc(k)}</td><td class="num">{v["n"]}</td><td class="num">{v["invested"]:,.1f}</td><td class="num">{v["value"]:,.1f}</td>'
                          f'<td class="num">{v["moic"]:.2f}×</td><td class="num">{_p0(v.get("irr"))}</td>'
                          f'<td class="num">{_p0(v.get("loss_ratio"))}</td></tr>'
                          for k, v in g.items()) + '</table>')
    groups = ''.join(grp(t, a.get(k)) for t, k in (('By fund', 'by_fund'), ('By sector', 'by_sector'), ('By deal lead', 'by_lead'),
                                                    ('By vintage', 'by_vintage'), ('By region', 'by_region')) if len(a.get(k) or {}) > 1)
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{_esc(deal_name)} — track-record dashboard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;background:#f6f4ee;color:#1a1c1a;font:14px/1.5 "IBM Plex Sans",Arial,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 28px 60px}}
h1{{font:600 28px "Bricolage Grotesque",Georgia,serif;margin:0 0 4px}} h2{{font:600 19px Georgia,serif;margin:30px 0 10px;border-top:2px solid #1a1c1a;padding-top:12px}}
h3{{font-size:14px;margin:20px 0 6px}} .sub{{color:#6b6b6b;font-size:12.5px}}
.fa-kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:18px 0}}
.fa-kpis div{{background:#fffdf8;border:1px solid #d9d4c7;border-radius:8px;padding:10px 12px}}
.fa-kpis span{{display:block;font:600 9.5px ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:#8a877d}}
.fa-kpis b{{font-size:24px}}
figure.fig{{margin:14px 0;padding:12px 14px;background:#fffdf8;border:1px solid #d9d4c7;border-radius:8px}} figure svg{{width:100%;height:auto}}
figcaption{{font-size:12.5px;color:#3d423d}} .ref{{color:#8a877d;font-size:11px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} @media(max-width:860px){{.grid{{grid-template-columns:1fr}}}}
table{{width:100%;border-collapse:collapse;background:#fffdf8;font-size:12.5px}} th,td{{padding:6px 8px;border-bottom:1px solid #e4dfd2;text-align:left}}
th{{background:#1a1c1a;color:#f6f4ee;font-weight:600;cursor:pointer;position:sticky;top:0}} td.num{{text-align:right;font-variant-numeric:tabular-nums}}
td.neg{{color:#7a2230;font-weight:600}} .qpill{{display:inline-block;font-size:10px;font-weight:700;padding:1px 6px;border-radius:9px;color:#fff;margin-left:4px}} .q1{{background:#1d7a47}} .q2{{background:#8fb35a}} .q3{{background:#d99a2b}} .q4{{background:#7a2230}} td .ref{{display:block}} .qchk.overstated{{color:#7a2230}} .qchk.confirmed,.qchk.better{{color:#1d7a47}} .gap{{background:#fbf1dc;border-left:3px solid #b38728;padding:8px 12px;margin:10px 0}} input{{padding:7px 10px;border:1px solid #d9d4c7;border-radius:6px;width:260px;font:inherit}}
</style></head><body><div class="wrap">
<div class="sub">ADCG Fund Manager Evaluation · track-record dashboard · as of {_esc(a.get("as_of", ""))}</div>
<h1>{_esc(deal_name)}</h1>
<div class="sub">Computed from {_esc(a.get("source") or "the deal schedule")}{(" · sheet " + _esc(a["sheet"])) if a.get("sheet") else ""} · IRR basis: {_esc(a.get("irr_basis") or "n/a")}. Gross figures unless stated.</div>
{memo_block(a)}
{funds}
{('<h2>Vintage-year quartiles</h2>' + quartile_block(a['quartiles'])) if a.get('quartiles') else ''}
<h2>Breakdown</h2><div class="grid">{groups}</div>
<h2>Deal-by-deal</h2><p><input id="q" placeholder="Filter by company, fund, sector, lead…"></p>
<table id="t"><thead><tr>{"".join(f"<th>{_esc(h)}</th>" for _, h in cols)}</tr></thead><tbody>{rows}</tbody></table>
</div><script>
const t=document.getElementById('t'),q=document.getElementById('q');
q.oninput=()=>{{const s=q.value.toLowerCase();for(const r of t.tBodies[0].rows)r.style.display=r.textContent.toLowerCase().includes(s)?'':'none'}};
[...t.tHead.rows[0].cells].forEach((th,i)=>{{let asc=false;th.onclick=()=>{{asc=!asc;const rs=[...t.tBodies[0].rows];
rs.sort((a,b)=>{{const x=a.cells[i].dataset.v,y=b.cells[i].dataset.v,nx=parseFloat(x),ny=parseFloat(y);
return (isNaN(nx)||isNaN(ny)?x.localeCompare(y):nx-ny)*(asc?1:-1)}});rs.forEach(r=>t.tBodies[0].appendChild(r))}}}});
</script></body></html>'''


def dumps(a: dict) -> dict:
    """JSON-safe copy for the model field."""
    return json.loads(json.dumps(a, default=str))
