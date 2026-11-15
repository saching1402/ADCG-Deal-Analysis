"""
Usage meters: file storage (Railway Volume / bucket), Postgres, and Claude model spend — with projections and
plain-English suggestions that change as limits approach.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
from collections import defaultdict

from django.conf import settings
from django.db import connection
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import AnalysisJob, AppSetting, Deal, DealFile, Stage, Status

GB = 1024 ** 3
MB = 1024 ** 2
DEFAULTS = {
    # Claude credit — entered by the deal lead from the Claude Console; nothing is set or detected automatically
    'credit_balance': None,           # balance shown in the Console at credit_as_of (USD)
    'credit_as_of': None,             # ISO time of that reading
    'warn_below': None,               # optional: warn when estimated remaining credit falls below this
    'stop_below': None,               # optional: refuse NEW analyses below this (running ones finish)
    'storage_capacity_gb': 5.0,       # Railway Hobby volume; used when the real volume size can't be read
    'db_capacity_gb': 5.0,            # Railway Hobby Postgres volume
    'plan': 'hobby',                  # hobby | pro | bucket — only changes the advice
}
WARN, HIGH, CRIT = 0.70, 0.85, 0.95


def get_settings() -> dict:
    row = AppSetting.objects.filter(pk='usage').first()
    return {**DEFAULTS, **(row.value if row else {})}


NUM_KEYS = ('storage_capacity_gb', 'db_capacity_gb')
OPTIONAL_KEYS = ('warn_below', 'stop_below')


def save_settings(data: dict) -> dict:
    cur = get_settings()
    for k in NUM_KEYS:
        if k in data and data[k] not in (None, ''):
            cur[k] = max(0.0, float(data[k]))
    for k in OPTIONAL_KEYS:  # blank = off
        if k in data:
            cur[k] = None if data[k] in (None, '') else max(0.0, float(data[k]))
    if data.get('plan'):
        cur['plan'] = str(data['plan'])
    AppSetting.objects.update_or_create(pk='usage', defaults={'value': cur})
    return cur


def _log(entry: dict) -> None:
    row, _ = AppSetting.objects.get_or_create(pk='credit_log', defaults={'value': {'events': []}})
    events = (row.value or {}).get('events', [])
    row.value = {'events': ([entry] + events)[:100]}
    row.save()


def credit_events() -> list[dict]:
    row = AppSetting.objects.filter(pk='credit_log').first()
    return (row.value or {}).get('events', []) if row else []


def spent_since(iso: str | None) -> float:
    if not iso:
        return 0.0
    t = dt.datetime.fromisoformat(iso)
    return float(AnalysisJob.objects.filter(created_at__gte=t).aggregate(s=Sum('cost'))['s'] or 0)


def remaining(cfg: dict | None = None) -> float | None:
    cfg = cfg or get_settings()
    if cfg.get('credit_balance') is None:
        return None
    return float(cfg['credit_balance']) - spent_since(cfg.get('credit_as_of'))


def record_balance(balance: float, user=None, note: str = '') -> dict:
    """The deal lead typed the balance shown in the Claude Console → new anchor; logs the drift vs the app's estimate."""
    cfg = get_settings()
    est = remaining(cfg)
    now = timezone.now().isoformat()
    cfg['credit_balance'], cfg['credit_as_of'] = round(float(balance), 2), now
    AppSetting.objects.update_or_create(pk='usage', defaults={'value': cfg})
    _log({'t': now, 'kind': 'sync', 'balance': round(float(balance), 2), 'estimate': None if est is None else round(est, 2),
          'by': (getattr(user, 'full_name', '') or getattr(user, 'username', None)), 'note': note[:200]})
    return cfg


def record_topup(amount: float, user=None, note: str = '') -> dict:
    """The deal lead added credit in the Console → remaining + amount becomes the new anchor."""
    cfg = get_settings()
    rem = remaining(cfg)
    if rem is None:
        raise ValueError('Enter your current Console balance first.')
    now = timezone.now().isoformat()
    new = round(rem + float(amount), 2)
    cfg['credit_balance'], cfg['credit_as_of'] = new, now
    AppSetting.objects.update_or_create(pk='usage', defaults={'value': cfg})
    _log({'t': now, 'kind': 'topup', 'amount': round(float(amount), 2), 'balance': new, 'by': (getattr(user, 'full_name', '') or getattr(user, 'username', None)), 'note': note[:200]})
    return cfg


def credit_guard() -> str | None:
    """Message if new analyses are paused by the deal lead's stop level, else None."""
    cfg = get_settings()
    rem, stop = remaining(cfg), cfg.get('stop_below')
    if rem is not None and stop is not None and rem < float(stop):
        return (f'New analyses are paused: estimated Claude credit ${rem:.2f} is below your stop level ${float(stop):.2f}. '
                'Add credit in the Claude Console and record it on the Usage tab, or lower the stop level.')
    return None


def level(frac: float | None) -> str:
    if frac is None:
        return 'unknown'
    return 'critical' if frac >= CRIT else 'high' if frac >= HIGH else 'warn' if frac >= WARN else 'ok'


def _volume() -> tuple[int | None, int | None, str]:
    """(total, used) bytes of the volume holding MEDIA_ROOT if it is a mounted Railway Volume, else (None, None)."""
    root = str(settings.MEDIA_ROOT)
    if settings.S3_BUCKET:
        return None, None, 'bucket'
    if root.startswith('/data') and os.path.exists('/data'):
        try:
            du = shutil.disk_usage('/data')
            return du.total, du.used, 'volume'
        except OSError:
            pass
    return None, None, 'container' if settings.ON_RAILWAY else 'local'


def _db_size() -> int | None:
    try:
        with connection.cursor() as c:
            if connection.vendor == 'postgresql':
                c.execute('SELECT pg_database_size(current_database())')
                return int(c.fetchone()[0])
            if connection.vendor == 'sqlite':
                name = connection.settings_dict['NAME']
                return os.path.getsize(name) if os.path.exists(str(name)) else None
    except Exception:
        return None
    return None


def compute() -> dict:
    cfg = get_settings()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── storage ──
    live = DealFile.objects.filter(archived_at__isnull=True)
    files_bytes = live.aggregate(s=Sum('size'))['s'] or 0
    n_files = live.count()
    archived = DealFile.objects.filter(archived_at__isnull=False).aggregate(n=Count('id'), s=Sum('size'))
    vol_total, vol_used, where = _volume()
    cap = vol_total or int(cfg['storage_capacity_gb'] * GB)
    used = vol_used if vol_used is not None else files_bytes
    per_deal = list(Deal.objects.annotate(
        n=Count('files', filter=Q(files__archived_at__isnull=True)),
        b=Sum('files__size', filter=Q(files__archived_at__isnull=True))).filter(n__gt=0).values(
        'id', 'name', 'website', 'stage', 'status', 'n', 'b', 'updated_at').order_by('-b'))
    for r in per_deal:
        r['id'] = str(r['id'])
        r['b'] = r['b'] or 0
        r['reclaimable'] = r['stage'] in (Stage.APPROVED, Stage.PASSED, Stage.ON_HOLD) and r['status'] not in (Status.QUEUED, Status.RUNNING)
    deals_with_files = len(per_deal)
    avg_deal = (files_bytes / deals_with_files) if deals_with_files else 60 * MB
    free = max(0, cap - used)
    reclaim = sum(r['b'] for r in per_deal if r['reclaimable'])
    storage = {
        'where': where, 'persistent': settings.STORAGE_PERSISTENT, 'capacity': cap, 'used': used,
        'files_bytes': files_bytes, 'files': n_files, 'frac': (used / cap) if cap else None,
        'capacity_source': 'volume' if vol_total else 'setting',
        'avg_per_deal': int(avg_deal), 'deals_left': int(free // avg_deal) if avg_deal else None,
        'reclaimable': reclaim, 'archived_files': archived['n'] or 0, 'archived_bytes': archived['s'] or 0,
        'deals': per_deal[:50],
    }
    storage['level'] = level(storage['frac']) if where != 'bucket' else 'ok'

    # ── database ──
    db = _db_size()
    db_cap = int(cfg['db_capacity_gb'] * GB)
    database = {'used': db, 'capacity': db_cap, 'frac': (db / db_cap) if db and db_cap else None}
    database['level'] = level(database['frac'])

    # ── model spend ──
    jobs = AnalysisJob.objects.all()
    month = jobs.filter(created_at__gte=month_start)
    m_cost = month.aggregate(s=Sum('cost'))['s'] or 0.0
    done_month = month.filter(status=Status.DONE)
    days = (now - month_start).total_seconds() / 86400
    nxt = (month_start + dt.timedelta(days=32)).replace(day=1)
    month_days = (nxt - month_start).days
    projected = (m_cost / days * month_days) if days >= 1 else m_cost
    done = jobs.filter(status=Status.DONE)
    avg_run = (done.aggregate(s=Sum('cost'))['s'] or 0) / max(1, done.count())
    by_model = defaultdict(lambda: {'cost': 0.0, 'runs': 0})
    for j in month.values('model', 'cost'):
        by_model[j['model'] or '—']['cost'] += j['cost'] or 0
        by_model[j['model'] or '—']['runs'] += 1
    starts = [month_start]
    for _ in range(5):
        starts.insert(0, (starts[0] - dt.timedelta(days=1)).replace(day=1))
    history = []
    for a in starts:
        b = (a + dt.timedelta(days=32)).replace(day=1)
        c = jobs.filter(created_at__gte=a, created_at__lt=b).aggregate(s=Sum('cost'), n=Count('id'))
        history.append({'month': a.strftime('%b %y'), 'cost': round(c['s'] or 0, 2), 'runs': c['n']})
    wasted = month.filter(status__in=[Status.ERROR, Status.BLOCKED]).aggregate(s=Sum('cost'))['s'] or 0
    bal = cfg.get('credit_balance')
    spent = spent_since(cfg.get('credit_as_of')) if bal is not None else 0.0
    rem = (float(bal) - spent) if bal is not None else None
    burn30 = float(jobs.filter(created_at__gte=now - dt.timedelta(days=30)).aggregate(s=Sum('cost'))['s'] or 0)
    model = {
        'month_cost': round(m_cost, 2), 'projected': round(projected, 2),
        'balance': bal, 'as_of': cfg.get('credit_as_of'), 'spent_since': round(spent, 2),
        'remaining': None if rem is None else round(rem, 2),
        'frac': (spent / float(bal)) if bal else None,   # share of the recorded credit already used
        'warn_below': cfg.get('warn_below'), 'stop_below': cfg.get('stop_below'),
        'paused': credit_guard() is not None,
        'runs_month': month.count(), 'done_month': done_month.count(), 'avg_run': round(avg_run, 2),
        'all_time': round(jobs.aggregate(s=Sum('cost'))['s'] or 0, 2),
        'by_model': sorted(({'model': k, **{x: round(y, 2) if x == 'cost' else y for x, y in v.items()}}
                            for k, v in by_model.items()), key=lambda r: -r['cost']),
        'history': history, 'wasted_month': round(wasted, 2), 'burn_30d': round(burn30, 2),
        'days_left': int(rem / (burn30 / 30)) if rem is not None and burn30 > 0 and rem > 0 else None,
        'runs_left': int(max(0.0, rem) // avg_run) if rem is not None and avg_run else None,
        'events': credit_events()[:20], 'key_set': bool(settings.ANTHROPIC_API_KEY),
    }
    if rem is None:
        model['level'] = 'unknown'
    elif (cfg.get('stop_below') is not None and rem < float(cfg['stop_below'])) or rem <= 0:
        model['level'] = 'critical'
    elif cfg.get('warn_below') is not None and rem < float(cfg['warn_below']):
        model['level'] = 'high'
    else:
        model['level'] = level(model['frac'])

    return {'settings': cfg, 'storage': storage, 'database': database, 'model': model,
            'suggestions': suggestions(cfg, storage, database, model)}


def _gb(b: float) -> str:
    return f'{b / GB:.1f} GB' if b >= GB else f'{b / MB:.0f} MB'


def suggestions(cfg, s, d, m) -> list[dict]:
    """[{level: critical|high|warn|info, area, title, text, action?}] — ordered most urgent first."""
    out = []
    pro = cfg['plan'] == 'pro'
    if not s['persistent']:
        out.append({'level': 'critical', 'area': 'storage', 'title': 'Uploads are not stored permanently',
                    'text': 'No Railway Volume is attached, so every redeploy deletes the data-room files. In Railway, right-click the '
                            'service → Attach Volume → mount path /data.'})
    elif s['where'] != 'bucket':
        f = s['frac'] or 0
        left = s['deals_left']
        avg = _gb(s['avg_per_deal'])
        if s['reclaimable'] and f >= WARN:
            out.append({'level': 'high' if f >= HIGH else 'warn', 'area': 'storage', 'action': 'free_all',
                        'title': f'Free {_gb(s["reclaimable"])} from approved / passed / on-hold deals',
                        'text': 'Their original files can be deleted — fact sheets, research, scores and memos are kept, and re-analysis '
                                'still works from the fact sheets.'})
        if f >= CRIT:
            out.append({'level': 'critical', 'area': 'storage', 'title': 'Storage almost full — uploads will start failing',
                        'text': (f'{_gb(s["used"])} of {_gb(s["capacity"])} used. ' +
                                 ('Increase the volume size in Railway → Volume → Settings (live resize, no downtime).' if pro else
                                  'Hobby volumes max out at 5 GB: upgrade to Railway Pro (50 GB+, resizable to 1 TB, ~$0.15/GB-month) '
                                  'or move files to a Cloudflare R2 bucket (10 GB free) — set S3_BUCKET and the S3_* variables.'))})
        elif f >= HIGH:
            out.append({'level': 'high', 'area': 'storage', 'title': f'Plan the storage upgrade now — about {left} more deal(s) fit',
                        'text': (f'At your average of {avg} per deal. ' +
                                 ('Grow the volume in Railway → Volume → Settings before it fills.' if pro else
                                  'Options: Railway Pro ($20/month, 50 GB volume) or a Cloudflare R2 bucket (10 GB free, then cheap per GB).'))})
        elif f >= WARN:
            out.append({'level': 'warn', 'area': 'storage', 'title': f'Storage {f:.0%} used — about {left} more deal(s) fit',
                        'text': f'Average data room here is {avg}. No action needed yet; upgrade or free space when this passes 85%.'})
        else:
            out.append({'level': 'info', 'area': 'storage', 'title': f'Room for about {left} more deal(s)',
                        'text': f'{_gb(s["used"])} of {_gb(s["capacity"])} used; average data room {avg}. You will be warned at 70%, 85% and 95%.'})
    if d['frac'] and d['frac'] >= WARN:
        out.append({'level': 'high' if d['frac'] >= HIGH else 'warn', 'area': 'database',
                    'title': f'Database {d["frac"]:.0%} of its volume',
                    'text': 'Memos, research and fact sheets live in Postgres. Grow the Postgres volume in Railway (Pro) or delete old test deals.'})
    if m['remaining'] is None:
        out.append({'level': 'warn', 'area': 'credit', 'title': 'Enter your Claude credit balance to start the meter',
                    'text': 'Copy the balance shown at the top right of platform.claude.com into "Update from Console" below. '
                            'The app then counts down as analyses run. Nothing is read from your card or set automatically.'})
    else:
        rem = m['remaining']
        if m['paused']:
            out.append({'level': 'critical', 'area': 'credit', 'title': f'New analyses paused — estimated credit {"−$" + format(-rem, ".2f") if rem < 0 else "$" + format(rem, ".2f")} left',
                        'text': f'Below your stop level of ${m["stop_below"]:.2f}. Add credit in the Console, then click "I added credit".'})
        elif rem <= 0:
            out.append({'level': 'critical', 'area': 'credit', 'title': 'Claude credit is probably used up',
                        'text': 'Runs will fail with a credit error. Add credit in the Console and record it here.'})
        elif m['warn_below'] is not None and rem < m['warn_below']:
            out.append({'level': 'high', 'area': 'credit', 'title': f'About ${rem:.2f} credit left — below your warning level',
                        'text': f'Roughly {m["runs_left"]} more analyses at your average of ${m["avg_run"]:.2f}.'
                                + (f' At the last 30 days\' pace that lasts about {m["days_left"]} days.' if m['days_left'] else '')})
        elif m['avg_run'] and m['runs_left'] is not None:
            out.append({'level': 'info', 'area': 'credit', 'title': f'About {m["runs_left"]} more analyses on your current credit',
                        'text': f'${rem:.2f} estimated left at an average of ${m["avg_run"]:.2f} per analysis.'
                                + (f' About {m["days_left"]} days at the last 30 days\' pace.' if m['days_left'] else '')})
        if m['as_of']:
            age = (timezone.now() - dt.datetime.fromisoformat(m['as_of'])).days
            if age >= 14:
                out.append({'level': 'info', 'area': 'credit', 'title': f'Balance last checked {age} days ago',
                            'text': 'The meter is the app\'s own estimate from token counts. Re-enter the Console balance now and then to keep it exact '
                                    '(and to catch any other use of the same account).'})
        if m['stop_below'] is None:
            out.append({'level': 'info', 'area': 'credit', 'title': 'No stop level set',
                        'text': 'Optional: set "Stop new analyses below" so a deal never starts when credit is nearly gone.'})
    opus = next((r for r in m['by_model'] if 'opus' in r['model']), None)
    if opus and m['month_cost'] and opus['cost'] / m['month_cost'] > 0.6 and m['runs_month'] >= 3:
        out.append({'level': 'info', 'area': 'model', 'title': 'Most spend this month is on Opus',
                    'text': 'Opus costs about twice Sonnet for the research, scoring and memo steps. Sonnet is usually enough for a first screen.'})
    if m['wasted_month'] >= 2:
        out.append({'level': 'info', 'area': 'model', 'title': f'${m["wasted_month"]:.2f} spent on runs that failed or paused this month',
                    'text': 'Fix files flagged in "Files need attention" before re-running; already-read files are reused, so retries cost less.'})
    rank = {'critical': 0, 'high': 1, 'warn': 2, 'info': 3}
    return sorted(out, key=lambda x: rank[x['level']])


def archive_deal_files(deal: Deal) -> tuple[int, int]:
    """Delete original files whose fact sheets exist (keep digests). Returns (files, bytes freed)."""
    n = freed = 0
    for f in deal.files.filter(archived_at__isnull=True, status__in=['digested', 'partial']).exclude(digest=''):
        try:
            f.file.delete(save=False)
        except Exception:
            pass
        freed += f.size
        n += 1
        DealFile.objects.filter(pk=f.pk).update(archived_at=timezone.now())
    return n, freed
