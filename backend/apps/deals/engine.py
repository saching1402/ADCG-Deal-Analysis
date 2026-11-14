"""
Analysis pipeline — runs on the background worker, never inside a web request.

  1. digest   each uploaded file → a fact sheet (map step; native PDF reading, parallel, cached per file)
  2. research web search + materials → research dossier + track / headline facts
  3. score    ADCG Buyout or ADCG-VG scorecard JSON → deterministic roll-up (apps.deals.scoring)
  4. memo     IC memo HTML in the skills' mandatory order → assembled into the memo shell + Prior Deals appendix

Why map-reduce: 15-20 CIMs, models and decks can be millions of tokens. Each file is read once by the digest model
and reduced to a ≤2.5K-word fact sheet with page references; later stages read the fact sheets (≈50-80K tokens for
20 files), which fits comfortably and is prompt-cached across stages. Adding files later only digests the new ones.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import F
from django.utils import timezone

from . import prompts as P
from .extract import Unreadable, digest_ok, fallback_blocks, inspect, prepare
from .models import AnalysisJob, Deal, DealFile, Stage, Status
from .roles import guess_role
from .scoring import ScoringError, score

log = logging.getLogger('apps.deals')


class AnalysisError(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


class FilesBlocked(RuntimeError):
    """One or more files could not be read; the analysis stops until the deal lead decides."""


KEY_HELP = ('Anthropic rejected the API key ({why}). In Railway → this service → Variables, set ANTHROPIC_API_KEY to the '
            'full key from platform.claude.com → Settings → API keys (it starts with "sk-ant-api03-", no quotes or spaces), '
            'make sure the Console account has credit, redeploy, then press Analyse again — uploaded files are kept.')


def preflight() -> None:
    """Fail fast with a readable message when the key is missing, wrong or the account can't be billed."""
    if not settings.ANTHROPIC_API_KEY:
        raise AnalysisError('ANTHROPIC_API_KEY is not set on the Railway service.')
    key = settings.ANTHROPIC_API_KEY
    if not key.startswith('sk-ant-'):
        raise AnalysisError(KEY_HELP.format(why=f'the value saved starts with "{key[:6]}…", not "sk-ant-"'))
    import anthropic
    try:
        anthropic.Anthropic(api_key=key, max_retries=2, timeout=30).models.list(limit=1)
    except anthropic.AuthenticationError:
        raise AnalysisError(KEY_HELP.format(why=f'invalid key ending …{key[-4:]}'))
    except anthropic.PermissionDeniedError as e:
        raise AnalysisError(f'The API key is valid but not allowed to use the API ({e}). Check the key\'s workspace and the account\'s credit in the Claude Console.')


# ── Claude call ───────────────────────────────────────────────────────────────
def request_cost(model: str, u) -> tuple[int, int, int, float]:
    p = settings.ANALYSIS_MODELS.get(model, {}).get('price') or (2.0, 10.0, 2.0, 10.0)
    cache_read = getattr(u, 'cache_read_input_tokens', 0) or 0
    cache_write = getattr(u, 'cache_creation_input_tokens', 0) or 0
    tin = (u.input_tokens or 0) + cache_read + cache_write
    tout = u.output_tokens or 0
    searches = getattr(getattr(u, 'server_tool_use', None), 'web_search_requests', 0) or 0
    pin, pout = (p[0], p[1]) if tin <= 100_000 else (p[2], p[3])
    cost = ((u.input_tokens or 0) * pin + cache_read * pin * 0.1 + cache_write * pin * 1.25 + tout * pout) / 1e6 \
        + searches * settings.SEARCH_PRICE
    return tin, tout, searches, cost


def ask(job: AnalysisJob, *, model: str, system, content: list[dict], max_tokens: int,
        searches: int = 0, label: str = '') -> str:
    """One conversation turn (streamed; follows pause_turn for web search). Returns the final text."""
    if not settings.ANTHROPIC_API_KEY:
        raise AnalysisError('Analysis is off: set ANTHROPIC_API_KEY in the Railway service variables.')
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=4, timeout=1800)
    tools = [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': searches}] if searches else []
    messages: list[dict[str, Any]] = [{'role': 'user', 'content': content}]
    blocks: list[Any] = []
    for _ in range(8):  # initial turn + pause_turn continuations
        kwargs = dict(model=model, max_tokens=max_tokens, system=system, messages=messages)
        if tools:
            kwargs['tools'] = tools
        with client.messages.stream(**kwargs) as stream:
            resp = stream.get_final_message()
        tin, tout, n_search, cost = request_cost(model, resp.usage)
        AnalysisJob.objects.filter(pk=job.pk).update(
            input_tokens=F('input_tokens') + tin, output_tokens=F('output_tokens') + tout,
            searches=F('searches') + n_search, cost=F('cost') + cost)
        job.input_tokens += tin
        job.output_tokens += tout
        job.searches += n_search
        job.cost += cost
        blocks.extend(resp.content)
        if resp.stop_reason != 'pause_turn':
            if resp.stop_reason == 'max_tokens':
                note(job, f'{label}: reply hit max_tokens; output may be truncated')
            break
        messages = [messages[0], {'role': 'assistant', 'content': blocks}]
        check_cancel(job)
    return ''.join(b.text for b in blocks if getattr(b, 'type', '') == 'text')


def fenced(text: str, lang: str) -> str:
    blocks = re.findall(rf'```{lang}\s*(.*?)```', text, re.S)
    if blocks:
        return max(blocks, key=len).strip() if lang == 'html' else blocks[-1].strip()
    return text.strip()


def parse_json(text: str) -> dict:
    raw = fenced(text, 'json')
    if not raw.startswith('{'):
        raw = text[text.find('{'): text.rfind('}') + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AnalysisError(f'Reply was not valid JSON ({e}).') from e
    if not isinstance(data, dict):
        raise AnalysisError('Reply was not a JSON object.')
    return data


# ── job bookkeeping ───────────────────────────────────────────────────────────
def note(job: AnalysisJob, msg: str) -> None:
    job.log = (job.log or []) + [{'t': timezone.now().isoformat(timespec='seconds'), 'msg': msg}]
    AnalysisJob.objects.filter(pk=job.pk).update(log=job.log)
    log.info('Deal job %s: %s', job.pk, msg)


def set_stage(job: AnalysisJob, stage: str, detail: str = '') -> None:
    check_cancel(job)
    job.stage, job.stage_detail = stage, detail
    AnalysisJob.objects.filter(pk=job.pk).update(stage=stage, stage_detail=detail)


def check_cancel(job: AnalysisJob) -> None:
    if AnalysisJob.objects.filter(pk=job.pk, status=Status.ERROR, error='Cancelled').exists():
        raise Cancelled()


def claim_next() -> AnalysisJob | None:
    with transaction.atomic():
        job = (AnalysisJob.objects.select_for_update(skip_locked=True)
               .filter(status=Status.QUEUED).order_by('created_at').first())
        if job is None:
            return None
        job.status, job.started_at = Status.RUNNING, timezone.now()
        job.save(update_fields=['status', 'started_at'])
        Deal.objects.filter(pk=job.deal_id).update(status=Status.RUNNING)
        return job


def queue(deal: Deal, user=None, model: str = '', instructions: str = '', allow_partial: bool = False) -> AnalysisJob:
    model = model if model in settings.ANALYSIS_MODELS else settings.ANALYSIS_MODEL
    job = AnalysisJob.objects.create(deal=deal, model=model, digest_model=settings.DIGEST_MODEL,
                                     instructions=instructions, allow_partial=allow_partial, created_by=user if getattr(user, 'pk', None) else None)
    deal.status = Status.QUEUED
    deal.save(update_fields=['status', 'updated_at'])
    return job


# ── stage 1: read & verify every file ─────────────────────────────────────────
RETRY_NOTE = ('This part is NOT empty — an earlier read returned nothing usable. Read every page carefully (text, tables, '
              'charts, scanned pages) and write the fact sheet. Only if a page is genuinely blank, say which page.')


def _digest_part(job: AnalysisJob, f: DealFile, prep, part, n: int, k: int) -> tuple[str, str]:
    """Digest one part; verify; retry (page images / stronger model). Returns (text, failure_reason or '')."""
    label = f'{k}/{n} ({part.label})' if n > 1 else ''
    model = job.digest_model or settings.DIGEST_MODEL
    text = ask(job, model=model, system=P.DIGEST_SYSTEM, max_tokens=6000, label=f'digest {f.name} {part.label}',
               content=part.blocks + [{'type': 'text', 'text': P.digest_user(job.deal, f.name, label)}])
    ok, why = digest_ok(text, part)
    if ok:
        return text, ''
    note(job, f'{f.name} — {part.label}: {why}; retrying')
    # retry 1: page images for PDF parts (scans, odd fonts, broken text layers); otherwise same input, stronger model
    calls = []
    try:
        calls = fallback_blocks(prep, part)
    except Exception as e:  # rendering failed — fall through to the stronger-model retry
        log.warning('render fallback failed for %s %s: %s', f.name, part.label, e)
    if calls:
        outs = [ask(job, model=model, system=P.DIGEST_SYSTEM, max_tokens=6000, label=f'digest {f.name} {part.label} images',
                    content=c + [{'type': 'text', 'text': P.digest_user(job.deal, f.name, label) + '\n' + RETRY_NOTE}])
                for c in calls]
        text = '\n\n'.join(o.strip() for o in outs)
    else:
        text = ask(job, model=job.model, system=P.DIGEST_SYSTEM, max_tokens=6000, label=f'digest {f.name} {part.label} retry',
                   content=part.blocks + [{'type': 'text', 'text': P.digest_user(job.deal, f.name, label) + '\n' + RETRY_NOTE}])
    ok, why2 = digest_ok(text, part)
    if ok or (len(text.strip()) >= 800 and 'figures' in why2):
        return text, ''
    return text, why2


def digest_file(job: AnalysisJob, f: DealFile, threaded: bool = True) -> None:
    if threaded:
        close_old_connections()
    try:
        DealFile.objects.filter(pk=f.pk).update(status='digesting', error='')
        try:
            with f.file.open('rb') as fh:
                data = fh.read()
        except (FileNotFoundError, OSError):
            raise Unreadable('The stored copy of this file is missing — it was lost when the server redeployed because '
                             'no persistent storage is attached (Railway Volume at /data). Remove it and upload it again.')
        if not f.readability:
            DealFile.objects.filter(pk=f.pk).update(readability=inspect(f.name, data))
        prep = prepare(f.name, data)
        n = len(prep.parts)
        texts, failed = [], []
        for k, part in enumerate(prep.parts, 1):
            check_cancel(job)
            text, why = _digest_part(job, f, prep, part, n, k)
            if why:
                failed.append({'label': part.label, 'why': why})
            else:
                texts.append(text.strip() if n == 1 else f'### Part {k}/{n} — {part.label}\n{text.strip()}')
        cov = {'parts': n, 'ok': n - len(failed), 'failed': failed, 'notes': prep.notes}
        digest = '\n\n'.join(texts)
        if prep.notes:
            digest += '\n\n> Reading notes: ' + ' '.join(prep.notes)
        if failed and not texts:
            DealFile.objects.filter(pk=f.pk).update(status='error', digest='', coverage=cov, method=prep.method, pages=prep.pages,
                                                    chars=prep.chars, error='Could not read any part: ' + '; '.join(
                                                        f"{x['label']} — {x['why']}" for x in failed))
        elif failed:
            DealFile.objects.filter(pk=f.pk).update(status='partial', digest=digest, coverage=cov, method=prep.method, pages=prep.pages,
                                                    chars=prep.chars, error='Unreadable: ' + '; '.join(
                                                        f"{x['label']} — {x['why']}" for x in failed))
        else:
            DealFile.objects.filter(pk=f.pk).update(status='digested', digest=digest, coverage=cov, method=prep.method,
                                                    pages=prep.pages, chars=prep.chars, error='')
        if not f.role_set_by_user and digest:
            DealFile.objects.filter(pk=f.pk).update(doc_role=guess_role(f.name, digest))
    except Cancelled:
        DealFile.objects.filter(pk=f.pk).update(status='uploaded')
        raise
    except Unreadable as e:
        DealFile.objects.filter(pk=f.pk).update(status='error', error=str(e)[:2000], coverage={'parts': 0, 'ok': 0, 'failed': [{'label': 'whole file', 'why': str(e)}]})
    except Exception as e:  # one bad file must not sink the read of the others — but a bad key / no credit must
        import anthropic
        if isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)) or 'credit balance' in str(e).lower():
            DealFile.objects.filter(pk=f.pk).update(status='uploaded', error='')
            raise
        log.exception('Digest failed for %s', f.name)
        DealFile.objects.filter(pk=f.pk).update(status='error', error=f'{type(e).__name__}: {str(e)[:1800]}')
    finally:
        if threaded:
            close_old_connections()


def stage_digest(job: AnalysisJob) -> list[DealFile]:
    redo = ['uploaded', 'digesting'] + ([] if job.allow_partial else ['error', 'partial'])
    todo = list(job.deal.files.filter(status__in=redo))
    total = job.deal.files.count()
    set_stage(job, 'digest', f'Reading and verifying {len(todo)} file(s) of {total}')
    if todo and settings.DIGEST_CONCURRENCY <= 1:
        for f in todo:
            digest_file(job, f, threaded=False)
    elif todo:
        with ThreadPoolExecutor(max_workers=settings.DIGEST_CONCURRENCY) as pool:
            list(pool.map(lambda f: digest_file(job, f), todo))
    check_cancel(job)

    # ── gate: every file must be fully read before the analysis starts ──
    files = list(job.deal.files.all())
    bad = [f for f in files if f.status in ('error', 'partial')]
    good = [f for f in files if f.status in ('digested', 'partial')]
    pages = sum(f.pages or 0 for f in files if f.status == 'digested')
    note(job, f'Verified {len([f for f in files if f.status == "digested"])} of {len(files)} file(s) fully read'
              + (f' ({pages:,} PDF pages)' if pages else ''))
    if bad and not job.allow_partial:
        raise FilesBlocked('; '.join(f'{f.name}: {f.error or "unreadable"}' for f in bad))
    if bad:
        note(job, 'Proceeding at the deal lead\'s request without: ' + ', '.join(f.name for f in bad))
    return good


# ── stage 2: research ─────────────────────────────────────────────────────────
def stage_research(job: AnalysisJob, files) -> dict:
    deal = job.deal
    set_stage(job, 'research', 'Web research + materials → research dossier')
    content = [P.materials_block(deal, files),
               {'type': 'text', 'text': P.deal_brief(deal) + (f'\n\nExtra instructions for this run:\n{job.instructions}'
                                                             if job.instructions else '') + '\n\n' + P.RESEARCH_TASK}]
    text = ask(job, model=job.model, system=P.system_blocks('auto' if deal.track == 'auto' else deal.track),
               content=content, max_tokens=32000, searches=settings.ANALYSIS_MAX_SEARCHES, label='research')
    try:
        meta = parse_json(text)
    except AnalysisError:
        meta = {}
        note(job, 'Research reply had no metadata JSON; using the requested track')
    dossier = re.sub(r'```json.*?```', '', text, flags=re.S).strip()
    track = deal.track if deal.track in ('buyout', 'vg') else (meta.get('track') if meta.get('track') in ('buyout', 'vg') else 'buyout')
    deal.research = dossier
    deal.track_resolved = track
    for fld in ('sector', 'sub_sector', 'one_liner', 'ev', 'multiple', 'leverage'):
        val = str(meta.get(fld) or '')[:500]
        if val:
            setattr(deal, fld, val if fld == 'one_liner' else val[:255])
    if meta.get('sponsor') and not deal.sponsor:
        deal.sponsor = str(meta['sponsor'])[:500]
    if meta.get('website') and not deal.website:
        deal.website = str(meta['website'])[:500]
    if isinstance(meta.get('facts'), list):
        deal.facts = clean_facts(meta['facts'])
    urls = [u for u in meta.get('sources') or [] if isinstance(u, str)]
    urls += re.findall(r'https?://[^\s)\]>"]+', dossier)
    deal.sources = list(dict.fromkeys(u.rstrip('.,;') for u in urls))[:150]
    deal.save()
    note(job, f'Research done → {"Venture / Growth" if track == "vg" else "Buyout"} track'
              + (f' ({meta.get("track_reason")})' if meta.get('track_reason') and deal.track == 'auto' else ''))
    return meta


_RANGE = re.compile(r'^(~?[$€£]?\d[\d.,]*)\s*[–—-]\s*[$€£]?\d[\d.,]*\s*(×|x|%|m|bn|k)?', re.I)
_SRC = re.compile(r'\[([^\]]{2,40})\]')


def short_value(v: str) -> tuple[str, str]:
    """(short value ≤ 28 chars, remainder for the note)."""
    full = re.sub(r'\s+', ' ', v).strip()
    t = _SRC.sub('', full).strip()
    m = _RANGE.match(t)
    if m:  # "12.7–13.5× Adj. / 15.2×…" → "12.7×" (range kept in the note)
        return f'{m.group(1)}{m.group(2) or ""}', full
    head = re.split(r'\s*(?:[:;(/]|\s[–—]\s|\s-\s|,\s(?=[a-z]))', t, maxsplit=1)[0].strip()
    head = re.sub(r'\b(headline|approx\.?|c\.)\s*$', '', head, flags=re.I).strip()
    head = re.sub(r'^the\s+', '', head, flags=re.I)
    if len(head) > 28:
        head = head[:27].rsplit(' ', 1)[0] + '…'
    return head or 'n/d', (full if full != head else '')


def clean_facts(raw) -> list[dict]:
    """Headline strip: one short value + source per box; detail moves to the note (shown on hover)."""
    out = []
    for x in raw or []:
        if not isinstance(x, dict) or not x.get('k'):
            continue
        v = re.sub(r'\s+', ' ', str(x.get('v') or 'n/d')).strip()
        src = str(x.get('src') or '').strip()
        note = str(x.get('note') or '').strip()
        if not src:
            m = _SRC.search(v)
            if m:
                src = m.group(1).split(';')[0].split(',')[0].strip()
            elif re.search(r'\bEST\b', v):
                src = 'Est.'
        if len(v) > 22 or _RANGE.match(v):
            short, rest = short_value(v)
            if rest:
                note = (rest if not note else f'{rest} — {note}')
            v = short
        k = re.sub(r'\s*\(.*?\)\s*$', '', str(x['k'])).strip() if len(str(x['k'])) > 22 else str(x['k'])
        out.append({'k': k[:28], 'v': v[:28], 'src': src[:24], 'note': note[:240]})
    return out[:6]


# ── stage 2b: independent risk review ─────────────────────────────────────────
def stage_risk(job: AnalysisJob, files) -> None:
    deal = job.deal
    set_stage(job, 'risk', 'Independent risk review — sector track record, macro, competition (web)')
    content = [P.materials_block(deal, files),
               {'type': 'text', 'text': P.deal_brief(deal) + '\n\n<research_dossier>\n' + deal.research + '\n</research_dossier>\n\n'
                + P.RISK_TASK}]
    text = ask(job, model=job.model, system=P.system_blocks(deal.track_resolved or 'buyout'), content=content,
               max_tokens=24000, searches=settings.RISK_MAX_SEARCHES, label='risk')
    try:
        items = parse_json(text)
    except AnalysisError:
        items = {}
        note(job, 'Risk review had no structured table; keeping the written review only')
    deal.risk_review = re.sub(r'```json.*?```', '', text, flags=re.S).strip()
    deal.risk_items = {k: items.get(k) for k in ('risks', 'track_record', 'theme_verdict', 'reconciliation') if items.get(k)}
    urls = re.findall(r'https?://[^\s)\]>"]+', deal.risk_review)
    urls += [r.get('source', '') for r in (items.get('risks') or []) + (items.get('track_record') or []) if isinstance(r, dict)]
    deal.sources = list(dict.fromkeys([*deal.sources, *(u.rstrip('.,;') for u in urls if str(u).startswith('http'))]))[:250]
    deal.save(update_fields=['risk_review', 'risk_items', 'sources', 'updated_at'])
    n = len(items.get('risks') or [])
    off = sum(1 for r in items.get('risks') or [] if isinstance(r, dict) and r.get('in_cim') in ('no', 'understated'))
    note(job, f'Risk review: {n} material risks ({off} not disclosed or understated in the materials)')


def risk_context(deal: Deal) -> str:
    if not deal.risk_review:
        return ''
    return ('\n\n<independent_risk_review>\n' + deal.risk_review + '\n</independent_risk_review>\n<risk_items_json>\n'
            + json.dumps(deal.risk_items, ensure_ascii=False) + '\n</risk_items_json>')


# ── stage 3: score ────────────────────────────────────────────────────────────
def prior_deals(deal: Deal):
    return list(Deal.objects.exclude(pk=deal.pk).filter(adcg_score__isnull=False).order_by('-analyzed_at', 'name')[:40])


def stage_score(job: AnalysisJob, files) -> tuple[dict, str]:
    deal = job.deal
    track = deal.track_resolved or 'buyout'
    from . import frameworks
    fw = frameworks.get(track)
    AnalysisJob.objects.filter(pk=job.pk).update(framework_version=fw.version)
    set_stage(job, 'score', f'Scoring on {fw.name} (framework v{fw.version})')
    content = [P.materials_block(deal, files),
               {'type': 'text', 'text': P.deal_brief(deal) + '\n\n<research_dossier>\n' + deal.research + '\n</research_dossier>'
                + risk_context(deal) + '\n\nKey risks and the risk-related criteria must reflect the independent risk review, not '
                'only the risks the materials disclose.\n\n' + P.ledger_text(prior_deals(deal)) + (f'\n\nExtra instructions for this run (apply them to the scores):\n{job.instructions}'
                                                      if job.instructions else '') + '\n\n' + P.SCORE_TASK[track]}]
    last_err = None
    for attempt in range(2):
        text = ask(job, model=job.model, system=P.system_blocks(track), content=content, max_tokens=16000, label='score')
        try:
            data = parse_json(text)
            summary, frag, clean = score(data, track, fw.config)
            break
        except (AnalysisError, ScoringError, KeyError, TypeError) as e:
            last_err = e
            note(job, f'Scorecard attempt {attempt + 1} unusable ({e}); retrying')
    else:
        raise AnalysisError(f'Could not produce a valid scorecard: {last_err}')

    deal.scorecard = clean
    deal.summary = summary
    deal.adcg_score = summary['overall']
    deal.risk_score = summary['risk']
    deal.band = summary['band']
    d = clean.get('deal') or {}
    deal.recommendation = str(d.get('recommendation') or clean.get('recommendation') or '')[:2000]
    if d.get('facts') and not deal.facts:
        deal.facts = clean_facts(d['facts'])
    if clean.get('sub_sector'):
        deal.sub_sector = str(clean['sub_sector'])[:500]
    deal.save()
    note(job, f'Scored {summary["overall"]:.2f} ({summary["band"]}) · risk {summary["risk"]}')
    return summary, frag


# ── stage 4: memo ─────────────────────────────────────────────────────────────
def score_context(deal: Deal, summary: dict) -> str:
    return ('<computed_scores>\n' + json.dumps(summary, ensure_ascii=False) + '\n</computed_scores>\n'
            '<scorecard_json>\n' + json.dumps(deal.scorecard, ensure_ascii=False) + '\n</scorecard_json>')


def appendix(deal: Deal) -> str:
    rows = [deal] + prior_deals(deal)
    tr = []
    for d in rows:
        cls = ' class="hl"' if d.pk == deal.pk else ''
        tag = ' [VG]' if d.track_resolved == 'vg' else ''
        tr.append(f'<tr{cls}><td>{html.escape(d.name)}{tag}</td><td>{html.escape(d.sponsor[:120])}</td>'
                  f'<td>{html.escape(d.ev[:60])}</td><td>{html.escape(d.multiple[:60])}</td><td>{html.escape(d.leverage[:30])}</td>'
                  f'<td class="num">{"" if d.adcg_score is None else f"{d.adcg_score:.2f}"}</td>'
                  f'<td class="num">{"" if d.risk_score is None else d.risk_score}</td>'
                  f'<td>{html.escape(d.one_liner[:220])}</td></tr>')
    return ('<h2>Appendix — Prior Deals</h2><p><small>From the Mindari / Deal Analysis pipeline; skill-derived scores, '
            'reconcile to the live ADCG app. Buyout and Venture/Growth [VG] scores are not comparable. '
            'Higher risk = riskier (0–100).</small></p><table><tr><th>Company</th><th>Sponsor / round</th><th>EV</th>'
            '<th>Multiple</th><th>Net lev</th><th>ADCG</th><th>Risk</th><th>One-line description</th></tr>'
            + ''.join(tr) + '</table>')


def stage_memo(job: AnalysisJob, files, summary: dict, frag: str) -> None:
    deal = job.deal
    track = deal.track_resolved or 'buyout'
    system = P.system_blocks(track, P.MEMO_CSS_NOTE)
    base = [P.materials_block(deal, files),
            {'type': 'text', 'text': P.deal_brief(deal) + '\n\n<research_dossier>\n' + deal.research
             + '\n</research_dossier>' + risk_context(deal) + '\n\n' + score_context(deal, summary),
             'cache_control': {'type': 'ephemeral'}}]

    set_stage(job, 'memo', 'Writing memo — overview, primer, value chain, financials')
    top = fenced(ask(job, model=job.model, system=system, label='memo part 1', max_tokens=40000,
                     content=base + [{'type': 'text', 'text': P.MEMO_TOP_TASK.format(**P.HEADINGS[track])}]), 'html')
    set_stage(job, 'memo', 'Writing memo — verdict, pros & cons, gates')
    body = fenced(ask(job, model=job.model, system=system, label='memo part 2', max_tokens=20000,
                      content=base + [{'type': 'text', 'text': '<memo_part_1>\n' + top + '\n</memo_part_1>\n\n' + P.MEMO_BODY_TASK}]), 'html')

    shell = P.fw('memo_shell.html')
    vg = track == 'vg'
    today = dt.date.today().strftime('%d %b %Y')
    title = f'{deal.name} — ' + ('ADCG Venture/Growth Score + Risk Package' if vg else 'ADCG Score + Risk Package')
    subtitle = ' · '.join(x for x in [deal.sub_sector or deal.sector, deal.sponsor[:120], today] if x)
    out = (shell.replace('{{TITLE}}', html.escape(title)).replace('{{SUBTITLE}}', html.escape(subtitle))
           .replace('{{EYEBROW}}', 'Venture / Growth · IC memo' if vg else 'Buyout · IC memo')
           .replace('{{CLASSIF}}', 'Confidential · IC Draft')
           .replace('{{SCORECARD}}', top + frag)
           .replace('{{BODY}}', body + appendix(deal))
           .replace('{{FOOTER}}', f'ADCG · Mindari / Deal Analysis · skill-derived ({job.model}) — reconcile to live ADCG app · {today}'))
    deal.memo_html = out
    deal.save(update_fields=['memo_html', 'updated_at'])
    note(job, 'Memo assembled')


# ── orchestration ─────────────────────────────────────────────────────────────
def run_job(job: AnalysisJob) -> None:
    deal = job.deal
    try:
        set_stage(job, 'digest', 'Checking the Anthropic API key')
        preflight()
        files = stage_digest(job)
        stage_research(job, files)
        stage_risk(job, files)
        summary, frag = stage_score(job, files)
        stage_memo(job, files, summary, frag)
        job.status, job.stage, job.stage_detail = Status.DONE, 'done', ''
        deal.refresh_from_db()
        deal.status = Status.DONE
        deal.analyzed_at = timezone.now()
        if deal.stage == Stage.NEW:
            deal.stage = Stage.ANALYZED
    except Cancelled:
        job.status, job.error = Status.ERROR, 'Cancelled'
        deal.refresh_from_db()
        deal.status = Status.DONE if deal.memo_html else Status.DRAFT
    except FilesBlocked as e:
        job.status, job.error = Status.BLOCKED, str(e)[:4000]
        note(job, 'Stopped before research: some files could not be read. Fix or remove them, or choose to run without them.')
        deal.refresh_from_db()
        deal.status = Status.BLOCKED
    except Exception as e:
        log.exception('Deal job %s failed', job.pk)
        import anthropic
        msg = str(e)
        if isinstance(e, anthropic.AuthenticationError):
            msg = KEY_HELP.format(why='invalid x-api-key')
        elif 'credit balance' in msg.lower():
            msg = 'The Claude Console account is out of credit — add credit at platform.claude.com → Billing, then press Analyse again.'
        job.status, job.error = Status.ERROR, msg[:4000]
        deal.refresh_from_db()
        deal.status = Status.ERROR
    job.finished_at = timezone.now()
    job.save(update_fields=['status', 'stage', 'stage_detail', 'error', 'finished_at'])
    deal.total_cost = sum(AnalysisJob.objects.filter(deal=deal).values_list('cost', flat=True))
    deal.save()
