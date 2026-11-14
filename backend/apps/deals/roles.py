"""What each uploaded document is — so the CIM anchors the facts and everything else is reconciled to it."""
import re

ROLES = [
    ('cim', 'CIM / information memorandum'),
    ('model', 'Financial model'),
    ('qoe', 'QoE / financial due diligence'),
    ('market', 'Market study / CDD'),
    ('structure', 'Transaction structure / term sheet'),
    ('sponsor_memo', 'Sponsor / co-investor memo'),
    ('legal', 'Legal / tax / other DD'),
    ('financials', 'Management accounts / financials'),
    ('other', 'Other'),
]
LABEL = dict(ROLES)
ORDER = {k: i for i, (k, _) in enumerate(ROLES)}

_RULES = [
    ('cim', r'\bcim\b|\bcip\b|confidential information (memorandum|presentation)|information memorandum|\bim\b|offering memorandum|teaser|'
            r'investment memorandum|vendor presentation|management presentation'),
    ('qoe', r'\bqoe\b|quality of earnings|financial due diligence|\bfdd\b|\bvdd\b|vendor due diligence'),
    ('market', r'market study|commercial due diligence|\bcdd\b|market report|industry report'),
    ('model', r'model|returns|\blbo\b|projections|forecast'),
    ('structure', r'structure|term ?sheet|\bspa\b|\blpa\b|waterfall|transaction steps'),
    ('sponsor_memo', r'co-?invest(or|ment)? memo|ic memo|investment committee|sponsor memo|gp memo|recommendation memo'),
    ('legal', r'legal|tax|insurance|environmental|\bldd\b|\btdd\b|\besg\b|cyber|it dd'),
    ('financials', r'management accounts|financial statements|annual report|accounts|audited|budget|\bp&l\b|balance sheet'),
]


def guess_role(name: str, digest: str = '') -> str:
    n = name.lower().replace('_', ' ')
    ext = n.rsplit('.', 1)[-1]
    for role, rx in _RULES:
        if re.search(rx, n):
            if role == 'model' and ext not in ('xlsx', 'xlsm', 'xls', 'csv', 'ods'):
                continue  # "returns" in a PDF title is rarely the model
            return role
    head = (digest or '')[:600].lower()
    for role, rx in _RULES:
        if re.search(rx, head):
            return role
    if ext in ('xlsx', 'xlsm', 'xls', 'ods'):
        return 'model'
    return 'other'
