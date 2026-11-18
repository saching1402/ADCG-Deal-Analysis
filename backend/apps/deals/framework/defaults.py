"""
Default content for the three editable ADCG frameworks (ADCG Buyout, ADCG CV, ADCG Venture Growth) (seeded into the `Framework` table on first start).

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
    'cv': _keep(_method, '6. deal.json schema'),
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


# Competition, disruption and moat (deal lead, Nov-26) — part of Business Quality in Buyout and CV. Examples are pointers
# only: the actual threat is idiosyncratic to the deal and sector, so name it specifically each time.
COMPETITION_CRITERIA = [
    _c('Competitive intensity & pricing pressure',
       'Who competes for the same customers and how hard: can rivals undercut on price and win share; is a large, '
       'well-funded player (e.g. a tech major, a scaled incumbent or a low-cost entrant) a credible threat; is the company '
       'gaining or losing share. Name the competitors and the evidence.'),
    _c('Disruption risk',
       'Could the business model be displaced — by a new technology, a different delivery model, regulation or a shift in '
       'customer behaviour — within the hold period? Identify the specific threat for THIS business and sector (for example, '
       'AI-native products replacing traditional software is one pattern, not a default test) and how fast it could bite.'),
    _c('Moat & barriers to entry',
       'How hard is it to replicate the business: scale economics, accumulated know-how and process advantage (yields, '
       'cost per unit), network effects, proprietary data or IP, licences and accreditations, switching costs. A deep moat '
       '(like a leading foundry\'s decades of scale and yield learning) scores high; a business a funded entrant could copy '
       'in a few years scores low.'),
]

# ADCG CV — Trophy Asset (deal lead, Nov-26): a trophy / star asset is one of the best performers in the sponsor's fund,
# which the sponsor is KEEPING because it can compound further — not an asset pushed into a CV because no sponsor or
# strategic would pay a good price.
TROPHY_DESC = ("Is this the sponsor's star asset — a top performer in its fund that it is keeping by choice to compound "
               "returns, not one moved into a CV because it couldn't find a buyer?")
TROPHY_CRITERIA = [
    _c('Performance within the sponsor\'s fund',
       'Is it one of the top return generators in the source fund — gross MOIC / IRR to date, share of fund NAV and of '
       'value created, rank among the fund\'s holdings (e.g. top 2–3 of 15)? A star asset scores high; a middling or '
       'lagging holding scores low.'),
    _c('Why a CV — kept by choice, not a failed sale',
       'Evidence the sponsor is holding on by conviction: no failed or pulled sale process, strong inbound or auction '
       'interest it chose not to take, a competitive secondary process, the GP rolling its carry and committing fresh '
       'money, a high existing-LP roll rate. Signs it could not find a sponsor or strategic buyer at a good price, a '
       'stalled IPO, or a fund-life / liquidity-driven CV score low.'),
    _c('Compounding runway',
       'How much value is left to create and how credible the plan is: organic growth, margin expansion, add-on M&A '
       'pipeline, new markets — why more time in the sponsor\'s hands earns a further multiple, not just a re-rating.'),
    _c('Value creation delivered so far',
       'What the sponsor has already achieved since entry: EBITDA growth, margin expansion and cash generation earned '
       'operationally (not via multiple expansion or leverage), and delivery against the original plan.'),
    _c('Market position & franchise quality',
       'Category rank and market share, scarcity of comparable assets, customer entrenchment and switching costs — the '
       'leader or a clear #2 with a durable franchise scores high.'),
]

CV_CONFIG = {  # the original ADCG Buyout framework, renamed ADCG CV (Nov-26)
    'weights_flex': True,
    'sections': [
        {'name': 'Sector Focus', 'weight': 15, 'description': 'Is the sub-sector structurally attractive?', 'criteria': [
            _c('Structural growth vs GDP', 'Demand engine and long-run growth of the sub-sector vs GDP.'),
            _c('Defensiveness / cyclicality', 'Resilience through downturns; non-discretionary demand scores high.'),
            _c('Demand drivers', 'Regulation, outsourcing, demographics, technology shifts that grow the top line.'),
            _c('Regulatory direction', 'Tailwind vs headwind from regulation and policy.'),
            _c('Profit-pool health / pricing power', 'Who in the value chain holds pricing power; is the pool growing?')]},
        {'name': 'Trophy Asset', 'weight': 20, 'description': TROPHY_DESC, 'criteria': TROPHY_CRITERIA},
        {'name': 'Business Quality', 'weight': 25, 'description': 'Margins, growth quality, cash conversion, resilience, execution — and competition, disruption risk and moat.', 'criteria': [
            _c('Margins vs peers', 'On HARD / agency-defined EBITDA, not company-adjusted; compare with named majors.'),
            _c('Growth quality (organic vs M&A)', 'Distrust M&A- or price-manufactured growth with thin organic growth.'),
            _c('Cash conversion / capital intensity', 'FCF conversion, capex and working-capital needs.'),
            _c('Input-cost resilience', 'Ability to pass through labour, energy and raw-material inflation.'),
            _c('Operational / integration execution', 'Track record integrating bolt-ons and delivering plans.'),
            *COMPETITION_CRITERIA]},
        {'name': 'Valuation & Leverage', 'weight': 25, 'description': 'Entry price, leverage and what the return relies on.', 'criteria': [
            _c('Entry vs transaction comps', 'Named precedents with specific multiples; use the right peer set.'),
            _c('Entry vs trading comps', 'Named listed peers; services sit below asset owners.'),
            _c('Leverage level & headroom', 'Penalise heavily above ~5x on thin-margin or capital-intensive assets.'),
            _c('Return reliance (growth vs re-rating)', 'Returns from earnings growth score higher than multiple expansion.'),
            _c('Equity cushion / downside', 'Equity % of EV, covenant headroom, downside case.')]},
        {'name': 'Alignment', 'weight': 15, 'description': 'Sponsor, management, structure and governance.', 'criteria': [
            _c('Sponsor track record', 'Sector and strategy record; realised results.'),
            _c('Management quality / continuity', 'Depth, tenure, gaps, rollover.'),
            _c('Structure / governance', 'For a CV: price-setting conflict, GP rollover, carry crystallisation, fairness opinion.')]},  # Mark credibility and Minority protections / information rights removed (deal lead, Nov-26)
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

DROPPED_ALIGNMENT = ('mark credibility', 'minority protections')
CO_INVEST_RULE = ('Raise Sponsor Quality / Alignment: a minority stake in a controlled asset is a standing risk (cf. Apave). '
                  'Cover governance terms under Structure / governance; do not add separate minority-protection or '
                  'information-rights criteria.')


def drop_alignment_extras(cfg: dict) -> dict:
    """Remove Mark credibility and Minority protections / information rights from Alignment (deal lead, Nov-26) and stop
    the co-invest weighting rule from adding them back."""
    import copy
    cfg = copy.deepcopy(cfg)
    for s in cfg.get('sections') or []:
        if s.get('name', '').lower() == 'alignment':
            keep = [c for c in s.get('criteria') or [] if not c.get('name', '').lower().startswith(DROPPED_ALIGNMENT)]
            s['criteria'] = keep or s.get('criteria')
    for r in cfg.get('weighting_rules') or []:
        if 'information rights' in r.get('rule', '').lower():
            has_sq = any(x.get('name', '').lower() == 'sponsor quality' for x in cfg.get('sections') or [])
            r['rule'] = CO_INVEST_RULE if has_sq else CO_INVEST_RULE.replace('Raise Sponsor Quality / Alignment', 'Raise Alignment')
    return cfg


VG_WEIGHTS = {'theme': 25, 'valuation & evolution': 15, 'investor syndicate': 25, 'company & management': 20,
              'competition': 10, 'venture fundamentals': 5}


# ADCG GP tiers (deal lead, Nov-26) — ONE shared list for ADCG Buyout and ADCG CV (key 'gps').
# Buyout sponsors in Tier 1/2/3; lead secondaries investors (CV) in P1/P2/P3. The deal lead supplies the names.
GPS_CONFIG = {
    'sponsor_tiers': [
        {'id': 'T1', 'label': 'Tier 1', 'score': 9, 'members': []},
        {'id': 'T2', 'label': 'Tier 2', 'score': 7, 'members': []},
        {'id': 'T3', 'label': 'Tier 3', 'score': 5, 'members': []},
    ],
    'secondary_tiers': [
        {'id': 'P1', 'label': 'P1', 'score': 9, 'members': []},
        {'id': 'P2', 'label': 'P2', 'score': 7, 'members': []},
        {'id': 'P3', 'label': 'P3', 'score': 5, 'members': []},
    ],
    'unlisted_score': 4,
}
# Members are firms {name, domain, aliases} (gp_entities) — the verified Tier 1 / Tier 2 sponsors from the deal lead.
from .gp_entities import entity_tiers, load_secondary_lists, load_sponsor_lists  # noqa: E402
GPS_CONFIG = load_secondary_lists(load_sponsor_lists(GPS_CONFIG))
SPONSOR_TIER_CRIT = {'name': 'Sponsor tier (ADCG GP list)', 'auto': 'sponsor_tier',
                     'guidance': 'Scored by the engine from the ADCG GP tiers: the sponsor running the company.'}
SECONDARY_TIER_CRIT = {'name': 'Lead secondaries investor tier (ADCG list)', 'auto': 'secondary_tier',
                       'guidance': 'Scored by the engine from the ADCG P1–P3 list: who is leading the CV transaction.'}


def add_gp_tier_criteria(key: str, cfg: dict) -> dict:
    """Buyout: Sponsor tier under Sponsor Quality. CV: the dual manager check under Alignment (underlying sponsor tier +
    lead secondaries investor tier)."""
    import copy
    cfg = copy.deepcopy(cfg)
    want = ({'sponsor quality': [SPONSOR_TIER_CRIT]} if key == 'buyout' else
            {'alignment': [dict(SPONSOR_TIER_CRIT, name='Underlying sponsor tier (ADCG GP list)'), SECONDARY_TIER_CRIT]})
    for s in cfg.get('sections') or []:
        have = {x.get('auto') for x in s.get('criteria') or []}
        add = [copy.deepcopy(c) for c in want.get(s.get('name', '').lower(), []) if c['auto'] not in have]
        if add:
            s['criteria'] = add + list(s.get('criteria') or [])
    return cfg


TIER_MOVES = {'AlleyCorp': 'T1', '8VC': 'T2', 'Factorial Funds': 'T2', 'True Ventures': 'T2', 'SOSV': 'T2', 'Monolith': 'T2'}


def move_tiers(cfg: dict, moves: dict = TIER_MOVES) -> dict:
    """Move named GPs between Venture Growth tiers (deal lead, Nov-26). Matches names case-insensitively."""
    import copy
    cfg = copy.deepcopy(cfg)
    tiers = cfg.get('tiers') or []
    low = {k.lower(): (k, v) for k, v in moves.items()}
    nm = lambda m: (m.get('name') if isinstance(m, dict) else str(m)).lower()
    moved = {}
    for t in tiers:
        keep = []
        for m in t.get('members') or []:
            (moved.__setitem__(nm(m), m) if nm(m) in low else keep.append(m))
        t['members'] = keep
    for key, (name, tid) in low.items():
        t = next((x for x in tiers if x.get('id') == tid), None)
        if t is not None and key not in {nm(m) for m in t['members']}:
            t['members'].append(moved.get(key, name))
    return cfg


def reweight_vg(cfg: dict) -> dict:
    """ADCG Venture Growth (Nov-26): new Investor Syndicate and Company & Management criteria; weights Theme 25 ·
    Valuation & Evolution 15 · Investor Syndicate 25 · Company & Management 20 · Competition 10 · Venture Fundamentals 5."""
    import copy
    cfg = copy.deepcopy(cfg)
    for s in cfg.get('sections') or []:
        n = s.get('name', '').lower()
        if n in VG_WEIGHTS:
            s['weight'] = VG_WEIGHTS[n]
        if n == 'investor syndicate':
            s['description'], s['criteria'] = SYN_DESC, copy.deepcopy(SYN_CRITERIA)
        elif n == 'company & management':
            s['description'], s['criteria'] = CM_DESC, copy.deepcopy(CM_CRITERIA)
    return cfg


def redefine_vg(cfg: dict) -> dict:
    """ADCG Venture Growth: replace the Theme and Valuation & Evolution criteria (Nov-26), keeping the live weights."""
    import copy
    cfg = copy.deepcopy(cfg)
    for s in cfg.get('sections') or []:
        n = s.get('name', '').lower()
        if n == 'theme':
            s['description'], s['criteria'] = THEME_DESC, copy.deepcopy(THEME_CRITERIA)
        elif n.startswith('valuation'):
            s['description'], s['criteria'] = VAL_DESC, copy.deepcopy(VAL_CRITERIA)
    return cfg


def redefine_trophy(cfg: dict) -> dict:
    """ADCG CV: replace the Trophy Asset section's description and criteria with the star-asset definition (Nov-26),
    keeping its weight."""
    import copy
    cfg = copy.deepcopy(cfg)
    for s in cfg.get('sections') or []:
        if 'trophy' in s.get('name', '').lower():
            s['description'] = TROPHY_DESC
            s['criteria'] = copy.deepcopy(TROPHY_CRITERIA)
    return cfg


def add_competition(cfg: dict) -> dict:
    """Add the competition / disruption / moat criteria to Business Quality if missing (live configs, Nov-26)."""
    import copy
    cfg = copy.deepcopy(cfg)
    for s in cfg.get('sections') or []:
        if s.get('name', '').lower() == 'business quality':
            have = {c.get('name', '').lower() for c in s.get('criteria') or []}
            s['criteria'] = (s.get('criteria') or []) + [copy.deepcopy(c) for c in COMPETITION_CRITERIA if c['name'].lower() not in have]
            if 'competition' not in s.get('description', '').lower():
                s['description'] = 'Margins, growth quality, cash conversion, resilience, execution — and competition, disruption risk and moat.'
    return cfg


def buyout_from_cv(cv: dict) -> dict:
    """ADCG Buyout (Nov-26) = the CV framework with Trophy Asset replaced by Sponsor Quality (same weight until the deal
    lead sets weights) and Sponsor track record moved out of Alignment. Works on the live (possibly edited) CV config."""
    import copy
    cfg = copy.deepcopy(cv)
    out = []
    for s in cfg.get('sections') or []:
        n = s.get('name', '').lower()
        if 'trophy' in n:
            s = copy.deepcopy(SPONSOR_QUALITY) | {'weight': s.get('weight', 20)}
        elif n == 'alignment':
            s['description'] = 'Management, structure and governance.'
            s['criteria'] = [c for c in s.get('criteria') or [] if 'sponsor' not in c.get('name', '').lower()] or s.get('criteria')
            for c in s['criteria']:
                if c.get('name') == 'Structure / governance':
                    c['guidance'] = 'Deal structure, governance rights, management incentive plan, fees and carry on the co-invest.'
        out.append(s)
    cfg['sections'] = out
    return cfg


SPONSOR_QUALITY = {'name': 'Sponsor Quality', 'description': 'Who is the sponsor and how good are they at this kind of deal?', 'criteria': [
    _c('Sponsor track record in the sector / strategy', 'Realised results on comparable deals (named exits, DPI); losses and write-downs count.'),
    _c('Fund performance & position', 'Quartile of recent funds (TVPI / DPI / IRR), fund size vs deal size, dry powder and fundraising momentum.'),
    _c('Deal team & stability', 'Seniority and continuity of the team running the deal; key-person and turnover risk.'),
    _c('Value-creation capability', 'Operating partners, playbook and evidence of earnings growth (not just multiple expansion) in past deals.'),
    _c('Sponsor alignment & commitment', 'Size of the sponsor\'s own equity cheque and GP commitment, co-invest economics, LP reputation and governance.')]}


# ADCG Venture Growth — Theme and Valuation & Evolution (deal lead, Nov-26).
# Theme = the themes ADCG must not miss: spot them early (before they are crowded), with a real technology step-change
# and real, fast TAM / ARR growth across the theme — even before it is profitable.
THEME_DESC = ('Is this a theme ADCG must not miss — a real technology step-change with fast-growing revenue across the '
              'theme, caught early, before it is crowded? Name the theme (frontier models, AI infra, physical AI / '
              'robotics, quantum, defense tech, space, bio × AI, energy for AI, fintech infra, other).')
THEME_CRITERIA = [
    _c('Early signals', 'Leading indicators that show up before consensus: top researchers and repeat founders moving in; '
       'theme-specialist and marquee investors making first bets; usage, developer or customer adoption compounding; '
       'benchmark or cost-curve breakthroughs. Strong signals while the theme is still early scores high (think frontier '
       'models before they were crowded).'),
    _c('Technology step-change', 'Is there a genuine discontinuity — a new capability or a break in the cost curve that '
       'opens new spend — rather than an incremental improvement?'),
    _c('TAM expansion & revenue momentum', 'Is the market itself growing fast: ARR of the leading companies in the theme '
       'compounding over the last 2–3 years, new budgets being created, the theme in its growth phase even if not yet '
       'profitable? Sized in the right units.'),
    _c('Crowding & timing', 'How early are we: number and latest marks of funded rivals, generalist / crossover money '
       'piling in, private marks vs the public-anchor trend. Early-but-validated scores high; late and crowded scores low.'),
    _c('Position & value capture within the theme', 'Who holds the profit pool — e.g. a frontier lab vs an inference '
       'reseller; picks-and-shovels vs application; how much of the theme\'s growth this company keeps.'),
    _c('Durability & policy direction', 'Will the theme still be growing in 5–10 years; sovereign, policy and regulatory '
       'tailwinds or headwinds.'),
]
# Valuation & Evolution = price against quality-adjusted comps, and step-ups earned by fundamentals.
VAL_DESC = ('Is the price right for the quality of the revenue, and has every step-up in valuation been earned by '
            'fundamentals (ARR) or a major technology milestone?')
VAL_CRITERIA = [
    _c('Entry multiple vs named comps', 'EV/ARR, EV/NTM revenue vs the most relevant private AND public comps.'),
    _c('Quality-adjusted multiple (margins & moat)',
       'A revenue multiple is only fair for the margins and moat behind it. Compare EV / gross profit as well as EV / '
       'revenue, and the expected long-run EBITDA / net margin. A frontier lab with high, rising gross margins and a deep '
       'moat can justify 25–30× revenue; a neocloud or inference reseller with thin gross margins and commodity GPU '
       'exposure cannot command the same multiple.'),
    _c('Valuation Justification Ratio (VJR)',
       'Valuation step-up ÷ fundamental step-up (gross profit where margins are known, else ARR / revenue). ≤1.5 OK (7–9); '
       '1.5–3 caution (4–6); >3 red flag (1–3). A step-up is only earned by ARR growth or a major technology milestone.'),
    _c('Valuation evolution across rounds',
       'Round by round, did each step-up track the improvement in fundamentals over the whole funding history — not just '
       'the latest round? Repeated step-ups with flat ARR and no breakthrough score low.'),
    _c('Round structure & terms', 'Preferences, ratchets, tranching, in-round price dispersion, primary vs secondary, FD gap.'),
    _c('Exit maths', 'Exit value needed for 3x net of dilution vs public comps and M&A precedents.'),
]

# Investor Syndicate (deal lead, Nov-26): who led each round, whether tier-1 insiders keep coming back, strategic
# validation, and how many tier-1 GPs are crowding in.
SYN_DESC = ('Who is backing it, round by round: tier-1 leads (especially early), insiders doubling down, strategic '
            'investors, and how many tier-1 GPs are in the syndicate.')
SYN_CRITERIA = [
    {'name': 'Marquee GP depth (ADCG GP tier index)', 'guidance': 'Computed by the engine from the tiered investor list.', 'auto': 'marquee'},
    _c('Tier-1 lead in each round', 'Who led and set the price in every round — especially the early ones. A lead from a '
       'marquee, theme-specialist manager (e.g. Founders Fund, Lux Capital, DCVC and their peers) is a strong signal; '
       'note the size of the lead cheque.'),
    _c('Insiders doubling down', 'Do the earlier (ideally tier-1) investors come back in each subsequent round — taking '
       'pro-rata or more, leading again — rather than selling secondary? Repeated insider re-ups are among the best signals.'),
    _c('Strategic investor validation', 'Strategics such as Nvidia, AMD, Broadcom, Google, Microsoft or a leading lab in '
       'the cap table show real conviction (and often a commercial relationship); note any conflict it creates.'),
    _c('Tier-1 concentration in the syndicate', 'How many tier-1 GPs are crowding into the cap table, and how much of the '
       'round they hold, versus tourist / crossover money chasing momentum. More tier-1 conviction scores higher.'),
]
# Company & Management (deal lead, Nov-26): founder track record first; pedigree and network; moat; quality of customers.
CM_DESC = ('Who is building it and who is buying it: founders with exits or top-lab pedigree, the technical moat, and '
           'whether leading companies — not random buyers — are paying and scaling their spend. Founder track record and '
           'customer quality matter most.')
CM_CRITERIA = [
    _c('Founder track record', 'MOST IMPORTANT. Serial founders who have built and sold companies to the right buyers '
       '(e.g. Naveen Rao — several companies built and sold before Unconventional) score highest; first-time founders '
       'without an operating record score lower.'),
    _c('Founder pedigree & network', 'Founders spun out of the best tech firms or AI labs; deep domain credibility; the '
       'network the business needs (e.g. government and defense relationships for a defense company).'),
    _c('Product / technical moat & IP', 'What is genuinely hard to copy — proprietary technology, IP, data, '
       'performance lead — and how long it lasts.'),
    _c('Customer quality & scaling', 'MOST IMPORTANT. Who the end customers are and whether they are scaling their spend: '
       'leading labs and enterprises (e.g. an inference platform serving Anthropic or Writer) score high; small or random '
       'buyers score low. Look at logos, expansion (NRR), concentration and binding contracts.'),
    _c('Execution vs stated milestones', 'Has the team shipped what it said it would, when it said it would?'),
    _c('Team completeness', 'Key hires (CTO / CFO / GTM / ops) for the stage — weigh it by what this business needs.'),
]

VG_CONFIG = {
    'weights_flex': False,
    'sections': [
        {'name': 'Theme', 'weight': 25, 'description': THEME_DESC, 'criteria': THEME_CRITERIA},
        {'name': 'Valuation & Evolution', 'weight': 15, 'description': VAL_DESC, 'criteria': VAL_CRITERIA},
        {'name': 'Investor Syndicate', 'weight': 25, 'description': SYN_DESC, 'criteria': SYN_CRITERIA},
        {'name': 'Company & Management', 'weight': 20, 'description': CM_DESC, 'criteria': CM_CRITERIA},
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
            'Playground Global (deep tech)', 'Radical Ventures (deep tech)', 'AlleyCorp']},
        {'id': 'T2', 'label': 'Strong multi-stage / growth', 'lead': 2.0, 'part': 1.0, 'members': [
            'Coatue', 'ICONIQ', 'Dragoneer', 'IVP', 'NEA', 'Bessemer', 'Menlo', 'Insight Partners', 'TCV', 'Spark Capital',
            'Eclipse', 'Battery', 'Bain Capital Ventures', 'Ribbit', 'Redpoint', 'Felicis', 'Conviction', 'DST Global',
            'Greenoaks', 'Elad Gil', 'Sound Ventures', '8VC', 'Factorial Funds', 'True Ventures', 'SOSV', 'Monolith']},
        {'id': 'T3', 'label': 'Tracked specialists / regional', 'lead': 1.0, 'part': 0.5, 'members': [
            'SparkLabs', 'Walden Catalyst', 'Deerfield', 'JMI',
            'Tiger Global', 'Inovia', 'Balderton', 'HyT Capital']},
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
VG_CONFIG = entity_tiers(VG_CONFIG)  # tier members as firms with websites (logos + identity matching)


def guidance_buyout() -> str:
    md = _strip_frontmatter(_read('buyout_skill.md'))
    return _drop(md, ['Sector-dynamic weighting', 'Calibration', 'After delivering', 'Files', 'Self-check'])


def guidance_vg() -> str:
    return _drop(_vg, ['Dependency', 'The ADCG-VG scorecard', 'Venture Risk Register', 'Calibration', 'Self-check',
                       'deal_vg.json schema', 'Engine'])


BUYOUT_CONFIG = add_gp_tier_criteria('buyout', buyout_from_cv(CV_CONFIG))
CV_CONFIG = add_gp_tier_criteria('cv', CV_CONFIG)

# ── ADCG house preferences (deal lead, Nov-26): apply to every framework; weighted as a capped overall adjustment ──
HOUSE_CONFIG = {
    'max_adjust': 0.5,
    'preferences': [
        {'id': 'marquee-gps', 'title': 'Back established, marquee GPs — not independent sponsors', 'importance': 'high',
         'applies': ['buyout', 'cv', 'vg'],
         'guidance': 'We do not like independent sponsors. On buyouts and CVs we prefer very established, marquee GPs with a '
                     'long realised record. On venture and growth deals we want to invest alongside marquee investors — '
                     'Thrive, Founders Fund, Khosla Ventures, Radical Ventures and their peers — ideally as the lead or a '
                     'significant participant in the round.'},
        {'id': 'frontier-selective', 'title': "Be selective in frontier tech — but don't miss the category winners",
         'importance': 'high', 'applies': ['vg'],
         'guidance': 'Frontier technology (quantum computing, large language models, world models, biotech, robotics and '
                     'similar): do not pay hefty valuations for companies without a real moat. But do not miss the category '
                     'winners: we looked at Anthropic at $60bn and $180bn and missed it. Winners usually show a marquee '
                     'investor list and exceptional ARR growth; a multi-fold step-up can be justified when growth is '
                     'phenomenal (e.g. Higgsfield). Prefer getting in earlier rather than later.'},
        {'id': 'proper-comps', 'title': 'Triangulate valuation with proper trading comps', 'importance': 'high',
         'applies': ['buyout', 'cv', 'vg'],
         'guidance': "Check the sponsor's or company's comparables against our own set of genuinely comparable listed peers "
                     '(no random peers) and against recent transactions. Read across what the public market is saying now — '
                     'e.g. a listed FM peer that is struggling, or listed memory names that have re-rated sharply — and say '
                     'how that affects the entry price and the exit multiple.'},
        {'id': 'exitability', 'title': 'Exitability', 'importance': 'medium', 'applies': ['buyout', 'cv', 'vg'],
         'guidance': 'Venture / growth: is an IPO the natural outcome, and will institutional and retail investors want this '
                     'theme when it lists? Buyouts and CVs: we prefer smaller deals — EV below roughly $3bn (a guide, not a '
                     'hard rule) — because very large assets can only exit through a trade sale or a large sponsor '
                     'consortium. Assess the depth of the strategic and sponsor buyer universe at exit.'},
        {'id': 'value-trap', 'title': 'Avoid value traps', 'importance': 'high', 'applies': ['buyout', 'cv', 'vg'],
         'guidance': 'A low price is not a reason to invest. Test whether a cheap entry multiple is hiding a weak or '
                     'deteriorating business (structural decline, losing share, margin erosion, customer churn, stretched '
                     'balance sheet). Cheap and bad is worse than fairly priced and good.'},
    ],
}

DEFAULTS = {
    'buyout': {'name': 'ADCG Buyout', 'description': 'Buyouts and co-investments alongside a sponsor.',
               'config': BUYOUT_CONFIG, 'guidance': guidance_buyout},
    'cv': {'name': 'ADCG CV', 'description': 'Continuation vehicles and GP-led secondaries (single- and multi-asset).',
           'config': CV_CONFIG, 'guidance': guidance_buyout},
    'gps': {'name': 'ADCG GP tiers', 'description': 'Buyout sponsors (Tier 1–3) and lead secondaries investors (P1–P3) — shared by ADCG Buyout and ADCG CV.',
            'config': GPS_CONFIG, 'guidance': lambda: ''},
    'house': {'name': 'ADCG preferences', 'description': 'What ADCG likes and avoids — applied to every deal on every framework.',
              'config': HOUSE_CONFIG, 'guidance': lambda: ''},
    'vg': {'name': 'ADCG Venture Growth', 'description': 'Venture and growth rounds — Seed to pre-IPO, venture co-invests and startup secondaries.',
           'config': VG_CONFIG, 'guidance': guidance_vg},
}


# Deal-specific factors (deal lead, 18-Nov-26): the framework sections keep their relative weights but share
# (100 − weight)%; the remaining slice is scored on 2–4 criteria the analysis picks for THIS deal's sub-sector
# (e.g. pharma: patent cliff; software: net revenue retention). Off when weight = 0.
DEAL_SPECIFIC = {'weight': 10, 'min': 2, 'max': 4,
                 'guidance': 'Pick the 2–4 factors that decide this particular deal and are not already scored by the '
                             'framework criteria — idiosyncratic to the sub-sector and the asset (e.g. pharma: patent cliff '
                             'and pipeline; software: net revenue retention and gross churn; healthcare services: '
                             'reimbursement exposure; industrials: tariff and input-cost exposure; consumer: brand '
                             'repeat-purchase). Say why each matters for this deal.'}


def with_deal_specific(cfg: dict) -> dict:
    if 'deal_specific' in cfg:
        return cfg
    return {**cfg, 'deal_specific': dict(DEAL_SPECIFIC)}


BUYOUT_CONFIG = with_deal_specific(BUYOUT_CONFIG)
CV_CONFIG = with_deal_specific(CV_CONFIG)
VG_CONFIG = with_deal_specific(VG_CONFIG)
