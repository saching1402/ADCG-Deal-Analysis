"""Editable ADCG frameworks: load, validate, save (versioned) and render for the prompts."""
from __future__ import annotations

import contextvars
import copy

from django.db import transaction

from .framework import gp_entities as gpe
from .framework.defaults import DEFAULTS, SCHEMA
from .models import Framework, FrameworkProposal, FrameworkVersion, PersonalFramework

KEYS = ('buyout', 'cv', 'vg')
PE_KEYS = ('buyout', 'cv')  # flexible-weight, sector-library frameworks
HOUSE = 'house'             # ADCG preferences: shared by every framework (not a scoring framework itself)
GPS = 'gps'                 # ADCG GP tiers: shared by ADCG Buyout and ADCG CV
ALL_KEYS = KEYS + (HOUSE, GPS)
IMPORTANCE = {'high': 3, 'medium': 2, 'low': 1}


class FrameworkError(ValueError):
    pass


def default(key: str) -> dict:
    d = DEFAULTS[key]
    return {'key': key, 'name': d['name'], 'description': d['description'],
            'config': copy.deepcopy(d['config']), 'guidance': d['guidance']()}


def ensure(key: str) -> Framework:
    fw = Framework.objects.filter(pk=key).first()
    if fw:
        return fw
    d = default(key)
    with transaction.atomic():
        fw = Framework.objects.create(key=key, name=d['name'], description=d['description'], config=d['config'],
                                      guidance=d['guidance'], version=1)
        FrameworkVersion.objects.create(framework=fw, version=1, name=fw.name, description=fw.description,
                                        config=fw.config, guidance=fw.guidance, note='Initial version from the ADCG skills')
    return fw


# Whose framework an analysis uses: set by the worker for the duration of a job (None = the main framework).
ACTIVE_USER: contextvars.ContextVar = contextvars.ContextVar('framework_user', default=None)


def main(key: str) -> Framework:
    """The main (admin) framework — the team default."""
    return ensure(key if key in ALL_KEYS else 'buyout')


def as_framework(pf: PersonalFramework) -> Framework:
    """An unsaved Framework carrying a personal copy's content, so the rest of the code can use it unchanged."""
    fw = Framework(key=pf.key, name=pf.name, description=pf.description, config=pf.config, guidance=pf.guidance,
                   version=pf.version)
    fw.personal = pf
    return fw


def personal(user, key: str) -> PersonalFramework | None:
    uid = getattr(user, 'pk', user)
    return PersonalFramework.objects.filter(user_id=uid, key=key).select_related('user').first() if uid else None


def get(key: str) -> Framework:
    """The framework in force: the active user's personal copy during their analysis, else the main framework."""
    key = key if key in ALL_KEYS else 'buyout'
    uid = ACTIVE_USER.get()
    if uid:
        pf = personal(uid, key)
        if pf:
            return as_framework(pf)
    return main(key)


def source_of(fw: Framework) -> str:
    pf = getattr(fw, 'personal', None)
    return pf.user.username if pf else ''


def save_personal(user, key: str, *, config: dict, guidance: str, name: str = '', description: str = '') -> PersonalFramework:
    cfg = validate(key, config)
    m = main(key)
    pf, made = PersonalFramework.objects.get_or_create(user=user, key=key, defaults={
        'name': (name or m.name).strip()[:120], 'description': description or m.description, 'config': cfg,
        'guidance': str(guidance or ''), 'version': 1, 'base_version': m.version})
    if not made:
        pf.config, pf.guidance = cfg, str(guidance or '')
        pf.name = (name or pf.name).strip()[:120]
        pf.description = description if description is not None else pf.description
        pf.version += 1
        pf.save()
    return pf


def _crit(sec: dict) -> dict:
    return {c.get('name', ''): c for c in sec.get('criteria') or []}


def diff(key: str, old: dict, new: dict) -> list[str]:
    """Plain-English list of what differs between two framework configs (main → proposed)."""
    out: list[str] = []
    if key == HOUSE:
        o = {p['id']: p for p in old.get('preferences') or []}
        n = {p['id']: p for p in new.get('preferences') or []}
        for i in n:
            if i not in o:
                out.append(f'Adds preference “{n[i]["title"]}” ({n[i]["importance"]})')
        for i in o:
            if i not in n:
                out.append(f'Removes preference “{o[i]["title"]}”')
        for i in set(o) & set(n):
            a, b = o[i], n[i]
            if a.get('title') != b.get('title'):
                out.append(f'Renames “{a["title"]}” → “{b["title"]}”')
            if a.get('importance') != b.get('importance'):
                out.append(f'“{b["title"]}”: importance {a.get("importance")} → {b.get("importance")}')
            if sorted(a.get('applies') or []) != sorted(b.get('applies') or []):
                out.append(f'“{b["title"]}”: applies to {", ".join(b.get("applies") or [])}')
            if (a.get('guidance') or '').strip() != (b.get('guidance') or '').strip():
                out.append(f'“{b["title"]}”: guidance reworded')
        if old.get('max_adjust') != new.get('max_adjust'):
            out.append(f'Maximum effect on the score ±{old.get("max_adjust")} → ±{new.get("max_adjust")}')
        return out
    if key == GPS:
        for grp, nm in (('sponsor_tiers', 'Buyout sponsors'), ('secondary_tiers', 'Lead secondaries')):
            def where(c):
                return {gpe.norm_domain(m.get('domain')) or gpe.name_key(m['name']): (t['label'], m['name'])
                        for t in c.get(grp) or [] for m in gpe.clean_members(t.get('members'))}
            a, b = where(old), where(new)
            for k, (tl, n) in b.items():
                if k not in a:
                    out.append(f'{nm}: adds {n} to {tl}')
                elif a[k][0] != tl:
                    out.append(f'{nm}: moves {n} {a[k][0]} → {tl}')
            out += [f'{nm}: removes {n}' for k, (tl, n) in a.items() if k not in b]
            ot = {t['id']: t.get('score') for t in old.get(grp) or []}
            out += [f'{nm}: {t["label"]} score {ot[t["id"]]:g} → {t["score"]:g}' for t in new.get(grp) or []
                    if t['id'] in ot and ot[t['id']] != t.get('score')]
        return out
    os_ = {s['name']: s for s in old.get('sections') or []}
    ns = {s['name']: s for s in new.get('sections') or []}
    for nm in ns:
        if nm not in os_:
            out.append(f'Adds section “{nm}” ({ns[nm].get("weight")}%) with {len(ns[nm].get("criteria") or [])} criteria')
    for nm in os_:
        if nm not in ns:
            out.append(f'Removes section “{nm}”')
    for nm in [x for x in ns if x in os_]:
        a, b = os_[nm], ns[nm]
        if float(a.get('weight', 0)) != float(b.get('weight', 0)):
            out.append(f'{nm}: weight {a.get("weight"):g}% → {b.get("weight"):g}%')
        ca, cb = _crit(a), _crit(b)
        for c in cb:
            if c not in ca:
                out.append(f'{nm}: adds criterion “{c}”')
        for c in ca:
            if c not in cb:
                out.append(f'{nm}: removes criterion “{c}”')
        for c in set(ca) & set(cb):
            if (ca[c].get('guidance') or '').strip() != (cb[c].get('guidance') or '').strip():
                out.append(f'{nm}: “{c}” guidance reworded')
    if [(b.get('label'), b.get('min')) for b in old.get('bands') or []] != [(b.get('label'), b.get('min')) for b in new.get('bands') or []]:
        out.append('Changes the verdict bands')
    for k, label in (('weighting_rules', 'weighting rules'), ('sector_library', 'sector library'), ('tiers', 'GP tiers'),
                     ('anchors', 'calibration anchors'), ('marquee', 'Marquee GP Index'), ('vjr', 'VJR thresholds'),
                     ('overlays', 'overlays'), ('weights_flex', 'weights mode'), ('calibration_note', 'calibration note')):
        if old.get(k) != new.get(k):
            out.append(f'Changes the {label}')
    return out


def _num(v, lo=None, hi=None, name='value'):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise FrameworkError(f'{name} must be a number.')
    if (lo is not None and f < lo) or (hi is not None and f > hi):
        raise FrameworkError(f'{name} must be between {lo} and {hi}.')
    return f


def validate_house(cfg: dict) -> dict:
    import re
    prefs, seen = [], set()
    for p in cfg.get('preferences') or []:
        if not isinstance(p, dict) or not str(p.get('title') or '').strip():
            continue
        pid = str(p.get('id') or '').strip() or re.sub(r'[^a-z0-9]+', '-', p['title'].lower()).strip('-')[:40]
        while pid in seen:
            pid += '-2'
        seen.add(pid)
        applies = [k for k in p.get('applies') or [] if k in KEYS] or list(KEYS)
        imp = p.get('importance') if p.get('importance') in IMPORTANCE else 'medium'
        prefs.append({'id': pid, 'title': str(p['title']).strip()[:200], 'importance': imp, 'applies': applies,
                      'guidance': str(p.get('guidance') or '').strip()})
    return {'max_adjust': _num(cfg.get('max_adjust', 0.5), 0, 2, 'Maximum adjustment'), 'preferences': prefs}


def validate_gps(cfg: dict) -> dict:
    def tiers(rows, prefix):
        out = []
        for i, t in enumerate(rows or []):
            if not isinstance(t, dict):
                continue
            mem = gpe.clean_members(t.get('members'))
            out.append({'id': str(t.get('id') or f'{prefix}{i + 1}')[:8], 'label': str(t.get('label') or t.get('id') or '')[:60],
                        'score': _num(t.get('score', 5), 1, 10, f'{t.get("label") or "Tier"} score'), 'members': mem})
        return out
    u = cfg.get('unlisted_score', 4)
    return {'sponsor_tiers': tiers(cfg.get('sponsor_tiers'), 'T'), 'secondary_tiers': tiers(cfg.get('secondary_tiers'), 'P'),
            'unlisted_score': None if u in (None, '') else _num(u, 1, 10, 'Unlisted score')}


def gps_cfg() -> dict:
    return get(GPS).config or {}


def gps_text(track: str) -> str:
    """The GP tier lists for Buyout / CV prompts, and what the scorer must name."""
    if track not in PE_KEYS:
        return ''
    c = gps_cfg()
    fmt = lambda rows: '\n'.join(f'- {t["label"]} (scores {t["score"]:g}): ' + ('; '.join(gpe.label(m) for m in t['members'])
                                                                              or '(none listed yet)') for t in rows or [])
    out = ['# ADCG GP TIERS (set by the deal lead — use these, do not invent tiers)',
           'Buyout sponsors:', fmt(c.get('sponsor_tiers'))]
    ask = '"sponsor_gp": "<the sponsor running the company>", "sponsor_gp_domain": "<its official website, e.g. gtcr.com>"'
    if track == 'cv':
        out += ['Lead secondaries investors (who leads the CV transaction):', fmt(c.get('secondary_tiers')),
                'CV = a DUAL MANAGER CHECK: assess both the underlying sponsor running the asset and the secondaries investor '
                'leading the transaction.']
        ask += (', "secondary_lead": "<the secondaries investor leading the CV>", '
                '"secondary_lead_domain": "<its official website>"')
    out.append(f'When scoring, also return {ask}. Criteria marked [auto: sponsor_tier] / [auto: secondary_tier] are scored '
               'by the engine from these lists — give them "auto" and a rationale only; if the manager is not on any list, '
               'score it yourself from the evidence. The engine matches the FIRM by its website, not by words in its name: '
               'name the actual investor and its own website (e.g. The Sterling Group = sterling-group.com is not Sterling '
               'Investment Partners = sterlinglp.com).')
    return '\n'.join(out)


def validate(key: str, cfg: dict) -> dict:
    """Light validation + normalisation; raises FrameworkError with a readable message."""
    if not isinstance(cfg, dict):
        raise FrameworkError('Config must be an object.')
    if key == HOUSE:
        return validate_house(cfg)
    if key == GPS:
        return validate_gps(cfg)
    cfg = copy.deepcopy(cfg)
    secs = cfg.get('sections')
    if not isinstance(secs, list) or not secs:
        raise FrameworkError('Add at least one section.')
    names = set()
    for s in secs:
        s['name'] = str(s.get('name') or '').strip()
        if not s['name']:
            raise FrameworkError('Every section needs a name.')
        if s['name'].lower() in names:
            raise FrameworkError(f'Duplicate section name: {s["name"]}.')
        names.add(s['name'].lower())
        s['weight'] = _num(s.get('weight'), 0, 100, f'Weight of {s["name"]}')
        s['description'] = str(s.get('description') or '')
        crits = [c for c in s.get('criteria') or [] if isinstance(c, dict) and str(c.get('name') or '').strip()]
        if not crits:
            raise FrameworkError(f'{s["name"]}: add at least one criterion.')
        s['criteria'] = [{**c, 'name': str(c['name']).strip(), 'guidance': str(c.get('guidance') or '')} for c in crits]
    total = sum(s['weight'] for s in secs)
    if abs(total - 100) > 0.01:
        raise FrameworkError(f'Section weights must add up to 100 (now {total:g}).')
    bands = sorted([{'label': str(b.get('label') or '').strip(), 'min': _num(b.get('min'), 0, 10, 'Band threshold')}
                    for b in cfg.get('bands') or [] if isinstance(b, dict)], key=lambda b: -b['min'])
    if not bands or bands[-1]['min'] > 0:
        raise FrameworkError('Verdict bands need a lowest band starting at 0.')
    cfg['bands'] = bands
    risk = cfg.get('risk') or {}
    if risk.get('method') == 'register':
        reg = [{'name': str(r.get('name') or '').strip(), 'weight': _num(r.get('weight'), 0, 100, 'Risk weight')}
               for r in risk.get('register') or [] if isinstance(r, dict) and str(r.get('name') or '').strip()]
        if not reg:
            raise FrameworkError('Add at least one risk to the register.')
        rt = sum(r['weight'] for r in reg)
        if abs(rt - 100) > 0.01:
            raise FrameworkError(f'Risk-register weights must add up to 100 (now {rt:g}).')
        risk['register'] = reg
    cfg['risk'] = risk
    if key == 'vg':
        for t in cfg.get('tiers') or []:
            t['lead'] = _num(t.get('lead'), 0, 20, f'{t.get("id")} lead points')
            t['part'] = _num(t.get('part'), 0, 20, f'{t.get("id")} participant points')
            t['members'] = gpe.clean_members(t.get('members'))
        m = cfg.get('marquee') or {}
        cfg['marquee'] = {'base': _num(m.get('base', 1), 0, 10, 'Marquee base'), 'slope': _num(m.get('slope', 0.6), 0, 10, 'Marquee slope')}
        v = cfg.get('vjr') or {}
        cfg['vjr'] = {'ok': _num(v.get('ok', 1.5), 0, 100, 'VJR OK threshold'), 'caution': _num(v.get('caution', 3), 0, 100, 'VJR caution threshold')}
    return cfg


def save(key: str, *, config: dict, guidance: str, name: str = '', description: str = '', note: str = '', user=None) -> Framework:
    cfg = validate(key, config)
    with transaction.atomic():
        fw = Framework.objects.select_for_update().get(pk=ensure(key).pk)
        fw.config, fw.guidance = cfg, str(guidance or '')
        fw.name = (name or fw.name).strip()[:120]
        fw.description = description if description is not None else fw.description
        fw.version += 1
        fw.updated_by = user if getattr(user, 'pk', None) else None
        fw.save()
        FrameworkVersion.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                                        config=fw.config, guidance=fw.guidance, note=note[:500], created_by=fw.updated_by)
    return fw


# ── prompt rendering ──────────────────────────────────────────────────────────
def render(fw: Framework) -> str:
    c = fw.config
    flex = c.get('weights_flex', fw.key in PE_KEYS)
    out = [f'# {fw.name.upper()} — SCORECARD DEFINITION (version {fw.version})',
           'Set by the PE team in the app\'s Framework tab. It is AUTHORITATIVE: where any text elsewhere in this prompt '
           'gives different sections, weights, criteria, bands, tiers or risk weights, follow this block.', '']
    out.append(f'Scope: {fw.description}')
    out.append('Scores are 1–10 per criterion; section score = mean of its scored criteria (null = undisclosed, excluded and '
               'renormalised); overall = Σ section weight/100 × section score.')
    out.append('Section weights: ' + ('DEFAULTS — adjust per deal using the weighting rules (must still sum to 100) and explain each change.'
                                      if flex else 'FIXED — use exactly these weights.'))
    out.append('')
    for i, s in enumerate(c.get('sections') or [], 1):
        out.append(f'## {i}. {s["name"]} — weight {s["weight"]:g}' + (f' — {s["description"]}' if s.get('description') else ''))
        for j, cr in enumerate(s.get('criteria') or []):
            a = cr.get('auto')
            auto = f' [auto: {a} — computed by the engine; give "auto": "{a}"]' if a else ''
            out.append(f'  ({chr(97 + j)}) {cr["name"]}{auto}' + (f' — {cr["guidance"]}' if cr.get('guidance') else ''))
    if fw.key in PE_KEYS:
        out.append('\nUse the criteria above as the default set; swap in sub-sector-specific criteria from the sector library '
                   'where they fit better, keeping the same number of criteria per section. Competitive intensity & pricing pressure, '
                   'Disruption risk, and Moat & barriers to entry are ALWAYS scored (never swapped out); make each one specific '
                   'to this deal — name the competitors, the disruptive threat and the source of the moat.')
    else:
        out.append('\nUse these criteria by name, in this order.')
    out.append('\nVerdict bands: ' + ' · '.join(f'{b["label"]} ≥ {b["min"]:g}' for b in c.get('bands') or []))
    out.append('\nRisk: NO risk score. Do not compute or state any numeric risk score or risk-register score; risks are '
               'highlighted qualitatively (severity / likelihood labels) in the risk review and Pros & Cons.')
    if c.get('overlays'):
        out.append('\nRecommendation overlays:')
        out += [f'  - {o}' for o in c['overlays']]
    if c.get('weighting_rules'):
        out.append('\nWeighting rules by transaction type:')
        out += [f'  - {r["when"]}: {r["rule"]}' for r in c['weighting_rules']]
    if c.get('tiers'):
        out.append('\nGP tiers for the Marquee GP Index (assign every current-round investor a tier and give its official website as "domain"; the engine re-checks each FIRM against these lists by website):')
        for t in c['tiers']:
            cap = f', capped at {t["cap"]:g} in total' if t.get('cap') else ''
            out.append(f'  - {t["id"]} ({t.get("label", "")}): lead {t["lead"]:g} / participant {t["part"]:g} pts{cap}. Members: {"; ".join(gpe.label(m) for m in t.get("members") or []) or "—"}')
        m = c.get('marquee') or {}
        out.append(f'  Marquee score = min(10, {m.get("base", 1):g} + {m.get("slope", 0.6):g} × points). Earlier-round-only investors: "prior_round_only": true.')
    if c.get('vjr'):
        v = c['vjr']
        out.append(f'\nVJR thresholds: ≤{v["ok"]:g} OK · {v["ok"]:g}–{v["caution"]:g} caution · >{v["caution"]:g} red flag.')
    if c.get('sector_library'):
        out.append('\nSector-metric library (reuse a block if the deal fits; otherwise build a new one the same way):')
        for b in c['sector_library']:
            out.append(f'  ### {b["name"]}' + (f' (anchor: {b["anchor"]})' if b.get('anchor') else ''))
            if b.get('criteria'):
                out.append(f'  Criteria: {b["criteria"]}')
            if b.get('comps'):
                out.append(f'  Comps: {b["comps"]}')
    if c.get('anchors'):
        out.append('\nCalibration anchors: ' + ' · '.join(f'{a["deal"]} {a["score"]}' + (f' ({a["note"]})' if a.get('note') else '')
                                                          for a in c['anchors']))
    if c.get('calibration_note'):
        out.append(c['calibration_note'])
    out.append('\n# OUTPUT JSON SCHEMA (app-internal)\n' + SCHEMA[fw.key])
    return '\n'.join(out)


def prompt_text(key: str) -> str:
    fw = get(key)
    return f'# {fw.name.upper()} — ANALYST GUIDANCE\n\n{fw.guidance}\n\n{render(fw)}'


# ── ADCG house preferences ───────────────────────────────────────────────────
def house_cfg(track: str | None = None) -> dict:
    """The preferences that apply to `track` (all of them when track is None) + max_adjust."""
    c = get(HOUSE).config or {}
    prefs = [p for p in c.get('preferences') or [] if track is None or track not in KEYS or track in (p.get('applies') or KEYS)]
    return {'max_adjust': float(c.get('max_adjust', 0.5)), 'preferences': prefs}


def house_text(track: str) -> str:
    h = house_cfg(track)
    if not h['preferences']:
        return ''
    out = ['# ADCG HOUSE PREFERENCES — how ADCG looks at every deal (set by the deal lead in the Framework tab)',
           'Apply these in every stage: research the evidence for them, test them in the risk review and the data-room '
           'integration, rate them when scoring, and reflect them in the memo. In the MEMO, weave them into the narrative '
           'where they belong (sponsor / investors, valuation and comps, exit, the value-trap test, the Pros & Cons, the '
           'recommendation) and say plainly why the deal does or does not fit — NEVER as a list of "ADCG preferences", '
           'never a section or heading of their own, and never name the house-fit score or adjustment.']
    for i, p in enumerate(h['preferences'], 1):
        out.append(f'{i}. [{p["id"]}] {p["title"]} (importance: {p["importance"]}) — {p["guidance"]}')
    out.append(f'When scoring, also return "house_fit": one entry per preference above — '
               f'{{"id": "<id>", "fit": -2..2 or null, "why": "one line with the evidence"}} (+2 = strongly fits what ADCG '
               f'likes, 0 = neutral, -2 = clearly what ADCG avoids, null = cannot judge). The engine turns these into a capped '
               f'adjustment of at most ±{h["max_adjust"]:g} on the overall score; do not adjust criterion scores for them as well.')
    return '\n'.join(out)
