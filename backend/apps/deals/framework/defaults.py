"""
Default content for the two editable ADCG frameworks (seeded into the `Framework` table on first start).

Each framework = structured `config` (sections, weights, criteria, bands, risk model, tiers, sector library,
calibration anchors) + free-text `guidance` (stance, memo order, workflow). The structured parts are taken
from the ADCG Buyout / Venture Growth skills; the guidance is the skill text minus what is now structured.
The JSON schemas the scorer must emit are app-internal (SCHEMA) and not editable.
"""
from __future__ import annotations

import re
from pathlib import Path

FW = Path(__file__).resolve().parent


def _read(name: str) -> str:
    return (FW / name).read_text(encoding='utf-8')


def _strip_frontmatter(md: str) -> str:
    return re.sub(r'^---\n.*?\n---\n', '', md, count=1, flags=re.S).strip()


def _sections(md: str) -> list[tuple[str, str]]:
    """Split on '## ' headings → [(heading, block incl. heading)]; text before the first heading has heading ''."""
    parts = re.split(r'(?m)^(?=## )', md)
    out = []
    for p in parts:
        m = re.match(r'## (.+)', p)
        out.append((m.group(1).strip() if m else '', p.rstrip()))
    return out


def _drop(md: str, prefixes: list[str]) -> str:
    return '\n\n'.join(b for h, b in _sections(md) if not any(h.startswith(x) for x in prefixes)).strip()


def _keep(md: str, prefix: str) -> str:
    return next((b for h, b in _sections(md) if h.startswith(prefix)), '')


# ── app-internal JSON schemas (what the scorer must return) ───────────────────
_method = _read('scorecard_methodology.md')
_vg = _strip_frontmatter(_read('venture_growth_skill.md'))
SCHEMA = {
    'buyout': _keep(_method, '6. deal.json schema'),
    'vg': _keep(_vg, 'deal_vg.json schema'),
}


def _sector_library() -> list[dict]:
    block = _keep(_method, '3. Sector-metric library')
    out = []
    for m in re.finditer(r'(?ms)^### (.+?)\n(.*?)(?=^### |\Z)', block):
        title, body = m.group(1).strip(), m.group(2).strip()
        a = re.search(r'\(anchor:\s*(.+?)\)\s*$', title)
        name = re.sub(r'\s*\(anchor:.*\)\s*$', '', title).strip()
        crit = re.search(r'Sector-specific criteria:\s*(.*?)(?=\nComps:|\Z)', body, re.S)
        comps = re.search(r'Comps:\s*(.*)', body, re.S)
        out.append({'name': name, 'anchor': a.group(1).strip() if a else '',
                    'criteria': re.sub(r'\s+', ' ', crit.group(1)).strip() if crit else re.sub(r'\s+', ' ', body),
                    'comps': re.sub(r'\s+', ' ', comps.group(1)).strip() if comps else ''})
    return out


def _weighting_rules() -> list[dict]:
    block = _keep(_method, '2. Dynamic weighting')
    rules = []
    for m in re.finditer(r'(?ms)^- \*\*(.+?):\*\*\s*(.*?)(?=^- \*\*|\Z)', block):
        rules.append({'when': m.group(1).strip(), 'rule': re.sub(r'\s+', ' ', m.group(2)).strip()})
    return rules


BANDS = [{'label': 'Strong', 'min': 8.0}, {'label': 'Positive', 'min': 6.5},
         {'label': 'Neutral', 'min': 5.0}, {'label': 'Weak', 'min': 0.0}]


def _c(name, guidance=''):
    return {'name': name, 'guidance': guidance}


BUYOUT_CONFIG = {
    'weights_flex': True,
    'sections': [
        {'name': 'Sector Focus', 'weight': 15, 'description': 'Is the sub-sector structurally attractive?', 'criteria': [
            _c('Structural growth vs GDP', 'Demand engine and long-run growth of the sub-sector vs GDP.'),
            _c('Defensiveness / cyclicality', 'Resilience through downturns; non-discretionary demand scores high.'),
            _c('Demand drivers', 'Regulation, outsourcing, demographics, technology shifts that grow the top line.'),
            _c('Regulatory direction', 'Tailwind vs headwind from regulation and policy.'),
            _c('Profit-pool health / pricing power', 'Who in the value chain holds pricing power; is the pool growing?')]},
        {'name': 'Trophy Asset', 'weight': 20, 'description': 'Is this a scarce, high-quality asset?', 'criteria': [
            _c('Category rank / market share', 'Leader or clear #2 scores high; sub-scale scores low.'),
            _c('Scarcity of the asset', 'How many comparable assets could a buyer own instead?'),
            _c('Brand / customer entrenchment', 'Embedded relationships, contracts, accreditation.'),
            _c('Franchise durability / switching costs', 'How hard it is for customers to leave.'),
            _c('Exit appeal / strategic scarcity', 'Depth of strategic and sponsor buyers at exit.')]},
        {'name': 'Business Quality', 'weight': 25, 'description': 'Margins, growth quality, cash conversion, resilience, execution.', 'criteria': [
            _c('Margins vs peers', 'On HARD / agency-defined EBITDA, not company-adjusted; compare with named majors.'),
            _c('Growth quality (organic vs M&A)', 'Distrust M&A- or price-manufactured growth with thin organic growth.'),
            _c('Cash conversion / capital intensity', 'FCF conversion, capex and working-capital needs.'),
            _c('Input-cost resilience', 'Ability to pass through labour, energy and raw-material inflation.'),
            _c('Operational / integration execution', 'Track record integrating bolt-ons and delivering plans.')]},
        {'name': 'Valuation & Leverage', 'weight': 25, 'description': 'Entry price, leverage and what the return relies on.', 'criteria': [
            _c('Entry vs transaction comps', 'Named precedents with specific multiples; use the right peer set.'),
            _c('Entry vs trading comps', 'Named listed peers; services sit below asset owners.'),
            _c('Leverage level & headroom', 'Penalise heavily above ~5x on thin-margin or capital-intensive assets.'),
            _c('Return reliance (growth vs re-rating)', 'Returns from earnings growth score higher than multiple expansion.'),
            _c('Equity cushion / downside', 'Equity % of EV, covenant headroom, downside case.')]},
        {'name': 'Alignment', 'weight': 15, 'description': 'Sponsor, management, structure and governance.', 'criteria': [
            _c('Sponsor track record', 'Sector and strategy record; realised results.'),
            _c('Management quality / continuity', 'Depth, tenure, gaps, rollover.'),
            _c('Structure / governance', 'For a CV: price-setting conflict, GP rollover, carry crystallisation, fairness opinion.'),
            _c('Mark credibility', 'Is the mark supported by comps and recent trading?'),
            _c('Minority protections / information rights', 'Board rights, drag/tag, information rights for a co-invest or minority.')]},
    ],
    'bands': BANDS,
    'risk': {'method': 'derived', 'formula': 'Risk = (10 − ADCG) × 10, on 0–100, higher = riskier'},
    'weighting_rules': _weighting_rules(),
    'sector_library': _sector_library(),
    'anchors': [
        {'deal': 'Apave', 'score': 6.16, 'risk': 38, 'note': 'Asset-light, low leverage (2.9x), CV minority — rated great by the deal lead'},
        {'deal': 'Acelpa Health', 'score': 6.1, 'risk': 39, 'note': 'Home infusion roll-up; reimbursement risk'},
        {'deal': 'Case FMS', 'score': 5.9, 'risk': 41, 'note': 'Snow services; weather dependence'},
        {'deal': 'The Compleat Food Group', 'score': 5.4, 'risk': 46, 'note': '4.9x leverage, thin organic growth — rated great by the deal lead'},
    ],
    'calibration_note': 'A leveraged, full-priced deal should sit lower (toward Compleat); an asset-light, well-aligned, '
                        'reasonably-priced platform higher (toward Apave). Don\'t drift more than ~0.3 from a close analogue without a reason.',
}

VG_CONFIG = {
    'weights_flex': False,
    'sections': [
        {'name': 'Theme', 'weight': 25, 'description': 'Name the theme on the scorecard (frontier models, AI infra, physical AI/robotics, quantum, defense tech, space, bio × AI, energy for AI, fintech infra, other).', 'criteria': [
            _c('Structural momentum of the theme'),
            _c('Position & value capture within the theme', 'Picks-and-shovels vs application; who holds the profit pool.'),
            _c('Hype-cycle timing', 'Private marks vs the public-anchor trend.'),
            _c('Theme durability & addressable spend', 'Sized in the right units.'),
            _c('Policy / sovereign / regulatory direction')]},
        {'name': 'Valuation & Evolution', 'weight': 25, 'description': 'Entry price vs comps and whether the step-ups are earned.', 'criteria': [
            _c('Entry multiple vs named comps', 'EV/ARR, EV/NTM revenue, EV/bookings; private AND public comps.'),
            _c('Valuation Justification Ratio (VJR)', 'Valuation step-up ÷ fundamental step-up. ≤1.5 OK (7–9); 1.5–3 caution (4–6); >3 red flag (1–3).'),
            _c('Growth-adjusted multiple / milestone progress'),
            _c('Round structure & terms', 'Preferences, ratchets, tranching, in-round price dispersion, primary vs secondary, FD gap.'),
            _c('Exit maths', 'Exit value needed for 3x net of dilution vs public comps and M&A precedents.')]},
        {'name': 'Investor Syndicate', 'weight': 25, 'description': 'Who is backing it and how much conviction they show.', 'criteria': [
            {'name': 'Marquee GP depth (ADCG GP tier index)', 'guidance': 'Computed by the engine from the tiered investor list.', 'auto': 'marquee'},
            _c('Lead quality & price-setter', 'Who led and set the price; size of the lead cheque.'),
            _c('Insider conviction', 'Existing investors re-upping / taking pro-rata vs selling secondary.'),
            _c('Strategic investor validation', 'Customers, suppliers, hyperscalers, labs — validation vs conflict.'),
            _c('Signal quality vs herd', 'Penalise tourist/crossover FOMO at early technical stages; reward theme-specialist conviction.')]},
        {'name': 'Company & Management', 'weight': 10, 'description': '', 'criteria': [
            _c('Founder quality & founder-market fit'), _c('Team completeness', 'CTO/CFO/ops/GTM and key hires vs stage.'),
            _c('Execution vs stated milestones'), _c('Product / technical moat & IP'),
            _c('Customer traction quality', 'Logos, NRR/GRR, concentration, binding contracts.')]},
        {'name': 'Competition', 'weight': 10, 'description': 'Always include a named competitor table with latest valuation and how each differs.', 'criteria': [
            _c('Competitive intensity', 'Funded rivals in the same niche and their latest marks.'),
            _c('Relative position vs category leaders'), _c('Durability of differentiation'),
            _c('Incumbent / hyperscaler / model-lab displacement risk'), _c('Competitor funding & pricing pressure')]},
        {'name': 'Venture Fundamentals', 'weight': 5, 'description': '', 'criteria': [
            _c('Capital efficiency & runway', 'Burn multiple, months of runway.'),
            _c('Gross-margin trajectory & COGS dependence', 'GPU / API / model-supplier costs.'),
            _c('Revenue quality', 'Recurring vs usage vs one-off; NRR (null if pre-revenue).'),
            _c('ADCG access, rights & terms', 'Pro-rata, info rights, co-invest access (null if undisclosed).'),
            _c('Exit route & liquidity')]},
    ],
    'bands': BANDS,
    'risk': {'method': 'register', 'register': [
        {'name': 'Valuation risk — level AND velocity (VJR)', 'weight': 15},
        {'name': 'AI hype / theme-cycle risk — narrative premium, public-anchor de-rating, crowding', 'weight': 12},
        {'name': 'Technology / execution risk — unproven product, tape-out, regulatory clearance, scale-up', 'weight': 12},
        {'name': 'Commercial traction & customer concentration', 'weight': 10},
        {'name': 'Competitive & incumbent / hyperscaler / model-lab displacement', 'weight': 10},
        {'name': 'Financing & dilution risk — capital intensity, next-round dependence, burn', 'weight': 10},
        {'name': 'Structure, governance & liquidity — prefs, ratchets, FD gap, info rights, exit timing', 'weight': 10},
        {'name': 'Business-model / margin & supplier dependence (GPUs, model APIs, memory, foundry)', 'weight': 8},
        {'name': 'Regulatory / geopolitical — export controls, AI regulation, China/Taiwan, data/privacy', 'weight': 7},
        {'name': 'Key-person / team risk', 'weight': 6},
    ]},
    'overlays': [
        'Venture Risk ≥65 → no direct primary at the current price (consider a secondary at a discount, a fund look-through, or waiting for a milestone).',
        'VJR red flag + pre-revenue → gate on the milestone that would justify the mark.',
        'Venture Risk ≤35 with ADCG-VG ≥6.5 → candidate for a sized co-invest.',
    ],
    'tiers': [
        {'id': 'T1', 'label': 'Marquee', 'lead': 3.0, 'part': 1.5, 'members': [
            'a16z', 'Sequoia', 'Founders Fund', 'Thrive Capital', 'Benchmark', 'Accel', 'Lightspeed', 'General Catalyst',
            'Index Ventures', 'Kleiner Perkins', 'Greylock', 'Khosla Ventures', 'DCVC (deep tech)', 'Lux Capital (deep tech)',
            'Playground Global (deep tech)', 'Radical Ventures (deep tech)']},
        {'id': 'T2', 'label': 'Strong multi-stage / growth', 'lead': 2.0, 'part': 1.0, 'members': [
            'Coatue', 'ICONIQ', 'Dragoneer', 'IVP', 'NEA', 'Bessemer', 'Menlo', 'Insight Partners', 'TCV', 'Spark Capital',
            'Eclipse', 'Battery', 'Bain Capital Ventures', 'Ribbit', 'Redpoint', 'Felicis', 'Conviction', 'DST Global',
            'Greenoaks', 'Elad Gil', 'Sound Ventures']},
        {'id': 'T3', 'label': 'Tracked specialists / regional', 'lead': 1.0, 'part': 0.5, 'members': [
            '8VC', 'Factorial Funds', 'SparkLabs', 'AlleyCorp', 'True Ventures', 'SOSV', 'Walden Catalyst', 'Deerfield', 'JMI',
            'Tiger Global', 'Inovia', 'Balderton', 'HyT Capital', 'Monolith']},
        {'id': 'S', 'label': 'Strategic', 'lead': 1.0, 'part': 0.5, 'members': [
            'NVentures / NVIDIA', 'CapitalG / GV / Google', 'Microsoft / M12', 'Amazon', 'Samsung', 'SK hynix', 'Arm',
            'Intel Capital', 'Qualcomm', 'OpenAI', 'Anthropic']},
        {'id': 'X', 'label': 'Other (crossover, sovereign, angels, other VCs)', 'lead': 0.5, 'part': 0.25, 'cap': 1.5, 'members': [
            'BlackRock', 'T. Rowe Price', 'Fidelity', 'Wellington']},
    ],
    'marquee': {'base': 1.0, 'slope': 0.6},
    'vjr': {'ok': 1.5, 'caution': 3.0},
    'anchors': [
        {'deal': 'Fractile (Series C, Nov-26)', 'score': 5.65, 'risk': 74,
         'note': 'Marquee syndicate cannot rescue a VJR red flag (7x in 6 months, pre-revenue); valuation and risk carry it.'},
    ],
    'calibration_note': 'Venture/Growth scores are NOT comparable to buyout-framework scores.',
}


def guidance_buyout() -> str:
    md = _strip_frontmatter(_read('buyout_skill.md'))
    return _drop(md, ['Sector-dynamic weighting', 'Calibration', 'After delivering', 'Files', 'Self-check'])


def guidance_vg() -> str:
    return _drop(_vg, ['Dependency', 'The ADCG-VG scorecard', 'Venture Risk Register', 'Calibration', 'Self-check',
                       'deal_vg.json schema', 'Engine'])


DEFAULTS = {
    'buyout': {'name': 'ADCG Buyout', 'description': 'Buyouts, co-investments alongside a sponsor, fund/GP-led secondaries and continuation vehicles.',
               'config': BUYOUT_CONFIG, 'guidance': guidance_buyout},
    'vg': {'name': 'ADCG Venture Growth', 'description': 'Venture and growth rounds — Seed to pre-IPO, venture co-invests and startup secondaries.',
           'config': VG_CONFIG, 'guidance': guidance_vg},
}
