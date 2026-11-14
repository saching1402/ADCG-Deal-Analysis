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
    'monthly_budget_usd': 100.0,      # model spend budget (team-set)
    'storage_capacity_gb': 5.0,       # Railway Hobby volume; used when the real volume size can't be read
    'db_capacity_gb': 5.0,            # Railway Hobby Postgres volume
    'plan': 'hobby',                  # hobby | pro | bucket — only changes the advice
}
WARN, HIGH, CRIT = 0.70, 0.85, 0.95


def get_settings() -> dict:
    row = AppSetting.objects.filter(pk='usage').first()
    return {**DEFAULTS, **(row.value if row else {})}


def save_settings(data: dict) -> dict:
    cur = get_settings()
    for k in DEFAULTS:
        if k in data and data[k] not in (None, ''):
            cur[k] = str(data[k]) if k == 'plan' else max(0.0, float(data[k]))
    AppSetting.objects.update_or_create(pk='usage', defaults={'value': cur})
    return cur


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
    budget = float(cfg['monthly_budget_usd'])
    model = {
        'month_cost': round(m_cost, 2), 'projected': round(projected, 2), 'budget': budget,
        'frac': (m_cost / budget) if budget else None, 'projected_frac': (projected / budget) if budget else None,
        'runs_month': month.count(), 'done_month': done_month.count(), 'avg_run': round(avg_run, 2),
        'all_time': round(jobs.aggregate(s=Sum('cost'))['s'] or 0, 2),
        'by_model': sorted(({'model': k, **{x: round(y, 2) if x == 'cost' else y for x, y in v.items()}}
                            for k, v in by_model.items()), key=lambda r: -r['cost']),
        'history': history, 'wasted_month': round(wasted, 2),
        'runs_left': int(max(0, budget - m_cost) // avg_run) if avg_run and budget else None,
        'key_set': bool(settings.ANTHROPIC_API_KEY),
    }
    model['level'] = level(max(model['frac'] or 0, (model['projected_frac'] or 0) * 0.9) if budget else None)

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
    if m['budget']:
        if (m['frac'] or 0) >= 1:
            out.append({'level': 'critical', 'area': 'model', 'title': 'Monthly model budget used up',
                        'text': f'${m["month_cost"]:.0f} of ${m["budget"]:.0f} spent this month. Raise the budget below, or use Haiku/Sonnet for screening runs.'})
        elif (m['projected_frac'] or 0) >= 1:
            out.append({'level': 'high', 'area': 'model', 'title': f'On track to spend ${m["projected"]:.0f} this month (budget ${m["budget"]:.0f})',
                        'text': 'Screen new deals on Sonnet and keep Opus for deals going to Pre-IC; avoid "re-read every file" unless files changed.'})
        elif (m['frac'] or 0) >= WARN:
            out.append({'level': 'warn', 'area': 'model', 'title': f'{m["frac"]:.0%} of this month\'s model budget used',
                        'text': f'About {m["runs_left"]} more analyses fit at your average of ${m["avg_run"]:.2f} per run.'})
    opus = next((r for r in m['by_model'] if 'opus' in r['model']), None)
    if opus and m['month_cost'] and opus['cost'] / m['month_cost'] > 0.6 and m['runs_month'] >= 3:
        out.append({'level': 'info', 'area': 'model', 'title': 'Most spend this month is on Opus',
                    'text': 'Opus costs about twice Sonnet for the research, scoring and memo steps. Sonnet is usually enough for a first screen.'})
    if m['wasted_month'] >= 2:
        out.append({'level': 'info', 'area': 'model', 'title': f'${m["wasted_month"]:.2f} spent on runs that failed or paused this month',
                    'text': 'Fix files flagged in "Files need attention" before re-running; already-read files are reused, so retries cost less.'})
    out.append({'level': 'info', 'area': 'model', 'title': 'Set a hard spend cap in the Claude Console',
                'text': 'This budget is a warning inside the app. For a hard stop, set a monthly limit in platform.claude.com → Settings → Limits.'})
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
