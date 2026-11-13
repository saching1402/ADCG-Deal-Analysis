"""
Company name autocomplete for the New deal page.

Sources (all keyless, queried in parallel with short timeouts, results merged by domain):
  1. deals already in this pipeline
  2. Clearbit Autocomplete (name + domain; still open without a key)
  3. Clearout public autocomplete (name + domain + confidence)
  4. Wikidata (well-known / listed companies; official website property P856)
Any source that fails is skipped silently. Logos are rendered client-side from the domain.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger('apps.deals')
UA = {'User-Agent': 'MindariDealAnalysis/1.0 (+deal pipeline autocomplete)'}
_cache: dict[str, tuple[float, list]] = {}
TTL = 6 * 3600


def _get(url: str, timeout: float = 3.0):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def domain_of(url: str) -> str:
    if not url:
        return ''
    host = urllib.parse.urlparse(url if '://' in url else f'https://{url}').hostname or ''
    return re.sub(r'^www\d?\.', '', host.lower())


def clearbit(q: str) -> list[dict]:
    data = _get('https://autocomplete.clearbit.com/v1/companies/suggest?query=' + urllib.parse.quote(q))
    return [{'name': x.get('name') or '', 'domain': x.get('domain') or '', 'source': 'clearbit'}
            for x in data if isinstance(x, dict) and x.get('domain')]


def clearout(q: str) -> list[dict]:
    data = _get('https://api.clearout.io/public/companies/autocomplete?query=' + urllib.parse.quote(q))
    rows = data.get('data') if isinstance(data, dict) else data
    out = []
    for x in rows or []:
        if isinstance(x, dict) and x.get('domain') and (x.get('confidence_score') or 100) >= 40:
            out.append({'name': x.get('name') or '', 'domain': domain_of(x['domain']), 'source': 'clearout'})
    return out


def wikidata(q: str) -> list[dict]:
    s = _get('https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=8&search='
             + urllib.parse.quote(q))
    hits = s.get('search') or []
    if not hits:
        return []
    ids = '|'.join(h['id'] for h in hits)
    e = _get(f'https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims|labels|descriptions&languages=en&ids={ids}')
    out = []
    for h in hits:
        ent = (e.get('entities') or {}).get(h['id']) or {}
        sites = ent.get('claims', {}).get('P856') or []
        url = ''
        for c in sites:
            try:
                url = c['mainsnak']['datavalue']['value']
                break
            except (KeyError, TypeError):
                continue
        if not url:
            continue  # without an official website it is rarely a company
        out.append({'name': h.get('label') or '', 'domain': domain_of(url),
                    'description': h.get('description') or '', 'source': 'wikidata'})
    return out


def external(q: str) -> list[dict]:
    key = q.lower().strip()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(f, q) for f in (clearbit, clearout, wikidata)]
        for f in futs:
            try:
                rows = f.result(timeout=4)
            except Exception as ex:  # one source down must not break the box
                log.info('suggest source failed: %s', ex)
                continue
            for r in rows:
                d = r['domain']
                if d and d not in results:
                    results[d] = r
                elif d and r.get('description') and not results[d].get('description'):
                    results[d]['description'] = r['description']
    ql = key
    ranked = sorted(results.values(), key=lambda r: (not r['name'].lower().startswith(ql), ql not in r['name'].lower(), len(r['name'])))[:8]
    _cache[key] = (time.time(), ranked)
    return ranked
