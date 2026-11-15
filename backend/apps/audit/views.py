import csv

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditEvent

GROUPS = {'deals': 'deal.', 'files': 'file.', 'analysis': 'analysis.', 'framework': 'framework.', 'auth': 'auth.',
          'users': ('user.', 'account.'), 'usage': ('credit.', 'usage.', 'storage.')}


def row(e: AuditEvent) -> dict:
    return {'id': e.id, 'at': e.at, 'actor': e.actor_name or 'unknown', 'actor_id': str(e.actor_id) if e.actor_id else None,
            'action': e.action, 'summary': e.summary, 'deal_id': str(e.deal_id) if e.deal_id else None,
            'deal_name': e.deal_name, 'target': e.target, 'changes': e.changes, 'ok': e.ok, 'ip': e.ip}


class AuditList(APIView):
    """GET ?deal=<uuid>&user=<uuid>&group=deals|files|…&q=&before=<iso>&limit= ; ?export=csv exports the filtered log."""
    def get(self, request):
        qs = AuditEvent.objects.all()
        p = request.query_params
        if p.get('deal'):
            qs = qs.filter(deal_id=p['deal'])
        if p.get('user'):
            qs = qs.filter(actor_id=p['user'])
        if p.get('group') in GROUPS:
            pre = GROUPS[p['group']]
            from django.db.models import Q
            q = Q()
            for x in (pre if isinstance(pre, tuple) else (pre,)):
                q |= Q(action__startswith=x)
            qs = qs.filter(q)
        if p.get('q'):
            from django.db.models import Q
            t = p['q']
            qs = qs.filter(Q(summary__icontains=t) | Q(deal_name__icontains=t) | Q(actor_name__icontains=t) | Q(target__icontains=t))
        if p.get('before') and parse_datetime(p['before']):
            qs = qs.filter(at__lt=parse_datetime(p['before']))
        if p.get('export') == 'csv':
            resp = HttpResponse(content_type='text/csv')
            resp['Content-Disposition'] = 'attachment; filename="deal-analysis-activity-log.csv"'
            w = csv.writer(resp)
            w.writerow(['time (UTC)', 'user', 'action', 'deal', 'what', 'details', 'ok', 'ip'])
            for e in qs[:50000]:
                w.writerow([e.at.isoformat(), e.actor_name, e.action, e.deal_name, e.summary, e.changes or '', e.ok, e.ip or ''])
            return resp
        limit = min(int(p.get('limit') or 100), 500)
        items = list(qs[:limit + 1])
        return Response({'events': [row(e) for e in items[:limit]], 'more': len(items) > limit})
