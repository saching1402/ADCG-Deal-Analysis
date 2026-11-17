"""GP tier members as real firms — {name, domain, aliases, note} — so a deal's investor is matched on WHO it is (its
website), not on words in its name. 'The Sterling Group' (sterling-group.com) and 'Sterling Investment Partners'
(sterlinglp.com) are different firms; word matching would merge them.

Sponsor lists dictated by the deal lead (Nov-26) and checked against each firm's website; where a dictated name was
unclear the verified firm is noted in `heard`.
"""
from __future__ import annotations

import re


def _e(name, domain, aliases=(), note='', heard=''):
    m = {'name': name, 'domain': domain}
    if aliases:
        m['aliases'] = list(aliases)
    if note:
        m['note'] = note
    if heard:
        m['heard'] = heard
    return m


SPONSOR_T1 = [
    _e('Inflexion', 'inflexion.com', ['Inflexion Private Equity']),
    _e('CapVest', 'capvest.com', ['CapVest Partners'], heard='CapWest'),
    _e('Oakley Capital', 'oakleycapital.com'),
    _e('Waterland Private Equity', 'waterlandpe.com', ['Waterland']),
    _e('Alpine Investors', 'alpineinvestors.com', ['Alpine']),
    _e('Nautic Partners', 'nautic.com', ['Nautic']),
    _e('Arlington Capital Partners', 'arlingtoncap.com', ['Arlington Capital']),
    _e('BV Investment Partners', 'bvlp.com', ['Boston Ventures'], note='formerly Boston Ventures',
       heard='Boston Ventures Investment Partners'),
    _e('Sentinel Capital Partners', 'sentinelpartners.com', ['Sentinel']),
    _e('Gemspring Capital', 'gemspring.com', ['Gemspring']),
    _e('Falfurrias Management Partners', 'falfurrias.com', ['Falfurrias Capital Partners', 'Falfurrias'],
       heard="Falfuria's Management Partners"),
    _e('Renovus Capital Partners', 'renovuscapital.com', ['Renovus'], heard='Renovis Capital'),
    _e('DC Capital Partners', 'dccapitalpartners.com', ['DC Capital']),
    _e('Carousel Capital', 'carouselcapital.com'),
    _e('Synova', 'synova.pe', ['Synova Capital'], heard='Sinova Capital'),
    _e('GTCR', 'gtcr.com'),
    _e('Clayton, Dubilier & Rice', 'cdr-inc.com', ['CD&R', 'CDR'], heard='CDNR'),
    _e('Genstar Capital', 'gencap.com', ['Genstar']),
    _e('CVC Capital Partners', 'cvc.com', ['CVC']),
]

SPONSOR_T2 = [
    _e('Graham Partners', 'grahampartners.net'),
    _e('CenterOak Partners', 'centeroakpartners.com', ['CenterOak'], heard='Center Oak Partners'),
    _e('The Sterling Group', 'sterling-group.com', ['Sterling Group'], note='Houston'),
    _e('Sterling Investment Partners', 'sterlinglp.com', note='Westport, CT'),
    _e('Levine Leichtman Capital Partners', 'llcp.com', ['LLCP']),
    _e('Clearview Capital', 'clearviewcap.com'),
    _e('Peak Rock Capital', 'peakrockcapital.com', ['Peak Rock']),
    _e('Altor', 'altor.com', ['Altor Equity Partners']),
    _e('Verdane', 'verdane.com'),
    _e('Norvestor', 'norvestor.com', ['Norvestor Equity'], heard='Norvester Equity'),
    _e('FSN Capital', 'fsncapital.com', ['FSN Capital Partners']),
    _e('Adelis Equity Partners', 'adelisequity.com', ['Adelis', 'Adelis Equity']),
    _e('Hudson Ferry Capital', 'hudsonferry.com', ['Hudson Ferry']),
    _e('IK Partners', 'ikpartners.com', ['IK Investment Partners', 'IK']),
    _e('Keensight Capital', 'keensightcapital.com', ['Keensight'], heard='Keenside Capital'),
    _e('Pollen Street', 'pollenstreetgroup.com', ['Pollen Street Capital']),
    _e('Seidler Equity Partners', 'sepfunds.com', ['Seidler', 'SEP'], heard='Seedler Equity Partners'),
    _e('Epiris', 'epiris.co.uk', note='formerly Electra Partners', heard='Epirus'),
    _e('Impilo', 'impilo.se', note='Nordic healthcare', heard='Empilo'),
    _e('Wynnchurch Capital', 'wynnchurch.com', ['Wynnchurch'], heard='Windchurch'),
    _e('BU (Bregal Unternehmerkapital)', 'bu-partners.com', ['BU', 'Bregal Unternehmerkapital', 'BU Bregal Unternehmerkapital'],
       note='DACH mid-market', heard='German-based BU'),
    _e('JF Lehman & Company', 'jflpartners.com', ['JFL', 'J.F. Lehman', 'JF Lehman']),
    _e('Rivean Capital', 'riveancapital.com', ['Gilde Buy Out Partners'], note='formerly Gilde Buy Out Partners',
       heard='Rivian Capital'),
    _e('GHO Capital', 'ghocapital.com', ['GHO Capital Partners']),
    _e('Systematic Growth', 'systematic-growth.com', note='Stockholm'),
    _e('Dominus Capital', 'dominuscap.com', ['Dominus']),
    _e('Monomoy Capital Partners', 'mcpfunds.com', ['Monomoy']),
    _e('VSS Capital Partners', 'vss.com', ['VSS', 'Veronis Suhler Stevenson']),
    _e('Marlin Equity Partners', 'marlinequity.com', ['Marlin Equity']),
    _e('Chicago Pacific Founders', 'cpfounders.com', ['CPF']),
    _e('Atlantic Street Capital', 'atlanticstreetcapital.com'),
    _e('ARCHIMED', 'archimed.group', ['ArchiMed'], note='healthcare'),
    _e('Gridiron Capital', 'gridironcapital.com', ['Gridiron']),
    _e('Ridgemont Equity Partners', 'ridgemontep.com', ['Ridgemont']),
    _e('Five Arrows', 'fivearrows.com', ['Five Arrows Principal Investments'], note='Rothschild & Co'),
    _e('Parthenon Capital', 'parthenoncapital.com', ['Parthenon Capital Partners']),
    _e('Greenbriar Equity Group', 'greenbriarequity.com', ['Greenbriar']),
    _e('Clarion Capital Partners', 'clarion-capital.com', ['Clarion Capital']),
    _e('Great Hill Partners', 'greathillpartners.com', ['Great Hill']),
    _e('American Industrial Partners', 'americanindustrial.com', ['AIP']),
    _e('New Mountain Capital', 'newmountaincapital.com', ['New Mountain']),
    _e('Court Square Capital Partners', 'courtsquare.com', ['Court Square'], heard='Code Square'),
    _e('Vitruvian Partners', 'vitruvianpartners.com', ['Vitruvian']),
    _e('Lindsay Goldberg', 'lindsaygoldbergllc.com'),
    _e('One Equity Partners', 'oneequity.com', ['OEP']),
    _e('Apollo', 'apollo.com', ['Apollo Global Management']),
    _e('ICG', 'icgam.com', ['Intermediate Capital Group']),
]

# Venture Growth tier members (names already on the framework) → the firm's website, so they show logos and match on it.
VG_DOMAINS = {
    'a16z': ('a16z.com', ['Andreessen Horowitz']), 'sequoia': ('sequoiacap.com', ['Sequoia Capital']),
    'founders fund': ('foundersfund.com', []), 'thrive capital': ('thrivecap.com', ['Thrive']),
    'benchmark': ('benchmark.com', []), 'accel': ('accel.com', []), 'lightspeed': ('lsvp.com', ['Lightspeed Venture Partners']),
    'general catalyst': ('generalcatalyst.com', []), 'index ventures': ('indexventures.com', []),
    'kleiner perkins': ('kleinerperkins.com', ['KP']), 'greylock': ('greylock.com', ['Greylock Partners']),
    'khosla ventures': ('khoslaventures.com', ['Khosla']), 'dcvc': ('dcvc.com', ['Data Collective']),
    'lux capital': ('luxcapital.com', ['Lux']), 'playground global': ('playground.global', ['Playground']),
    'radical ventures': ('radical.vc', ['Radical']), 'alleycorp': ('alleycorp.com', []),
    'coatue': ('coatue.com', ['Coatue Management']), 'iconiq': ('iconiqcapital.com', ['ICONIQ Growth', 'ICONIQ Capital']),
    'dragoneer': ('dragoneer.com', ['Dragoneer Investment Group']), 'ivp': ('ivp.com', ['Institutional Venture Partners']),
    'nea': ('nea.com', ['New Enterprise Associates']), 'bessemer': ('bvp.com', ['Bessemer Venture Partners', 'BVP']),
    'menlo': ('menlovc.com', ['Menlo Ventures']), 'insight partners': ('insightpartners.com', ['Insight']),
    'tcv': ('tcv.com', ['Technology Crossover Ventures']), 'spark capital': ('sparkcapital.com', []),
    'eclipse': ('eclipse.vc', ['Eclipse Ventures']), 'battery': ('battery.com', ['Battery Ventures']),
    'bain capital ventures': ('baincapitalventures.com', ['BCV']), 'ribbit': ('ribbitcap.com', ['Ribbit Capital']),
    'redpoint': ('redpoint.com', ['Redpoint Ventures']), 'felicis': ('felicis.com', ['Felicis Ventures']),
    'conviction': ('conviction.com', []), 'dst global': ('dst-global.com', ['DST']),
    'greenoaks': ('greenoaks.com', ['Greenoaks Capital']), 'elad gil': ('eladgil.com', []),
    'sound ventures': ('soundventures.com', []), '8vc': ('8vc.com', []), 'factorial funds': ('factorialfunds.com', ['Factorial']),
    'true ventures': ('trueventures.com', []), 'sosv': ('sosv.com', []), 'monolith': ('monolith.vc', ['Monolith VC']),
    'sparklabs': ('sparklabs.co.kr', ['SparkLabs Group']), 'walden catalyst': ('waldencatalyst.com', []),
    'deerfield': ('deerfield.com', ['Deerfield Management']), 'jmi': ('jmi.com', ['JMI Equity']),
    'tiger global': ('tigerglobal.com', ['Tiger']), 'inovia': ('inovia.vc', ['Inovia Capital']),
    'balderton': ('balderton.com', ['Balderton Capital']), 'hyt capital': ('', []),
    'nventures': ('nvidia.com', ['NVIDIA']), 'capitalg': ('capitalg.com', ['GV', 'Google', 'Google Ventures']),
    'microsoft': ('microsoft.com', ['M12']), 'amazon': ('amazon.com', ['Amazon Industrial Innovation Fund']),
    'samsung': ('samsung.com', ['Samsung Ventures', 'Samsung NEXT']), 'sk hynix': ('skhynix.com', []),
    'arm': ('arm.com', []), 'intel capital': ('intelcapital.com', []), 'qualcomm': ('qualcomm.com', ['Qualcomm Ventures']),
    'openai': ('openai.com', ['OpenAI Startup Fund']), 'anthropic': ('anthropic.com', ['Anthropic Anthology Fund']),
    'blackrock': ('blackrock.com', []), 't rowe price': ('troweprice.com', ['T. Rowe Price']),
    'fidelity': ('fidelity.com', ['Fidelity Investments']), 'wellington': ('wellington.com', ['Wellington Management']),
}


# ---------------------------------------------------------------- normalising members and matching on identity
_SUFFIX = r'\b(the|llc|llp|lp|l p|ltd|limited|inc|co|ag|gmbh|bv|b v|sa|sas|ab|as|plc)\b'


def name_key(n: str) -> str:
    """Strict name key: case, punctuation, '&'/'and' and legal suffixes only. Never drops words like 'Capital' or
    'Partners' — 'Sterling Group' and 'Sterling Investment Partners' stay different."""
    n = re.sub(r'\(.*?\)', ' ', str(n or '').lower()).replace('&', ' and ')
    n = re.sub(r'[^a-z0-9 ]+', ' ', n)
    n = re.sub(_SUFFIX, ' ', n)
    return ' '.join(n.split())


def norm_domain(d: str) -> str:
    d = str(d or '').strip().lower()
    d = re.sub(r'^[a-z]+://', '', d).split('/')[0].split('?')[0]
    return re.sub(r'^www\d?\.', '', d).strip('.')


def same_domain(a: str, b: str) -> bool:
    a, b = norm_domain(a), norm_domain(b)
    return bool(a and b) and (a == b or a.endswith('.' + b) or b.endswith('.' + a))


def as_member(m) -> dict | None:
    """A tier member from either the old plain-string form ('NVentures / NVIDIA', 'DCVC (deep tech)') or the entity form."""
    if isinstance(m, dict):
        name = str(m.get('name') or '').strip()
        if not name:
            return None
        out = {'name': name[:120], 'domain': norm_domain(m.get('domain'))[:120]}
        al = [str(a).strip()[:120] for a in m.get('aliases') or [] if str(a).strip()]
        if al:
            out['aliases'] = al[:12]
        for k in ('note', 'heard'):
            if str(m.get(k) or '').strip():
                out[k] = str(m[k]).strip()[:120]
        return out
    s = str(m or '').strip()
    if not s:
        return None
    note = ''
    mt = re.search(r'\((.*?)\)', s)
    if mt:
        note, s = mt.group(1).strip(), (s[:mt.start()] + s[mt.end():]).strip()
    parts = [p.strip() for p in re.split(r'\s*/\s*', s) if p.strip()]
    name, aliases = parts[0], parts[1:]
    dom, extra = VG_DOMAINS.get(name_key(name), ('', []))
    out = {'name': name, 'domain': dom}
    al = aliases + [a for a in extra if a not in aliases]
    if al:
        out['aliases'] = al
    if note:
        out['note'] = note
    return out


def clean_members(rows) -> list[dict]:
    """Entity members, de-duplicated by website (else by name)."""
    out, doms, names = [], set(), set()
    for r in rows or []:
        m = as_member(r)
        if not m:
            continue
        d, k = norm_domain(m.get('domain')), name_key(m['name'])
        if (d and d in doms) or (not d and k in names):
            continue
        if d:
            doms.add(d)
        names.add(k)
        out.append(m)
    return out


def label(m) -> str:
    m = as_member(m) or {}
    return m.get('name', '') + (f' ({m["domain"]})' if m.get('domain') else '')


def matches(m, name: str = '', domain: str = '') -> bool:
    """Is this investor the same firm as the member? Website first; else the exact name or a listed alias."""
    m = as_member(m)
    if not m:
        return False
    if domain and m.get('domain'):
        return same_domain(domain, m['domain'])
    k = name_key(name)
    return bool(k) and k in {name_key(x) for x in [m['name'], *(m.get('aliases') or [])]}


def find(tiers, name: str = '', domain: str = ''):
    """(tier, member) for the investor, or (None, None). A website match anywhere beats a name match."""
    if domain:
        for t in tiers or []:
            for m in t.get('members') or []:
                mm = as_member(m)
                if mm and mm.get('domain') and same_domain(domain, mm['domain']):
                    return t, mm
    for t in tiers or []:
        for m in t.get('members') or []:
            mm = as_member(m)
            if not mm or (domain and mm.get('domain')):  # a different website = a different firm, whatever the name
                continue
            if matches({**mm, 'domain': ''}, name):
                return t, mm
    return None, None


def load_sponsor_lists(cfg: dict) -> dict:
    """Merge the deal lead's verified Tier 1 / Tier 2 sponsors into an ADCG GP tiers config (a firm already listed moves
    to the dictated tier)."""
    import copy
    cfg = copy.deepcopy(cfg or {})
    tiers = cfg.setdefault('sponsor_tiers', [])
    for t in tiers:
        t['members'] = clean_members(t.get('members'))
    for tid, rows in (('T1', SPONSOR_T1), ('T2', SPONSOR_T2)):
        dest = next((t for t in tiers if t.get('id') == tid), None)
        if dest is None:
            continue
        for e in rows:
            for t in tiers:
                t['members'] = [m for m in t['members'] if not (same_domain(m.get('domain'), e['domain'])
                                                                 or name_key(m['name']) == name_key(e['name']))]
            dest['members'].append(dict(e))
    for k in ('secondary_tiers',):
        for t in cfg.get(k) or []:
            t['members'] = clean_members(t.get('members'))
    return cfg


def entity_tiers(cfg: dict) -> dict:
    """Venture Growth config with entity members."""
    import copy
    cfg = copy.deepcopy(cfg or {})
    for t in cfg.get('tiers') or []:
        t['members'] = clean_members(t.get('members'))
    return cfg
