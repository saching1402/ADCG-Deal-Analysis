"""Logs every change made through the API (POST/PUT/PATCH/DELETE) plus file downloads, with who, what, when, from
where and — for edits — the old and new values. Runs after the view, so DRF's JWT user is known."""
import json
import logging

from django.urls import Resolver404, resolve

from .models import record

log = logging.getLogger(__name__)
SECRET = {'password', 'new_password', 'current_password', 'refresh', 'access', 'token', 'api_key'}
DEAL_FIELDS = ['name', 'website', 'track', 'sponsor', 'sector', 'sub_sector', 'notes', 'stage', 'ev', 'multiple',
               'leverage', 'one_liner', 'recommendation']


def _ip(request) -> str | None:
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() or request.META.get('REMOTE_ADDR')) or None


def _body(request) -> dict:
    if 'json' not in (request.content_type or ''):
        return {}
    try:
        data = json.loads(request.body or b'{}')
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: ('••••' if k in SECRET else v) for k, v in data.items()}


def _short(v, n=300):
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + '…'


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith('/api/v1/'):
            return self.get_response(request)
        try:
            match = resolve(path)
        except Resolver404:
            return self.get_response(request)
        view = getattr(match.func, 'view_class', None)
        vname = view.__name__ if view else ''
        method = request.method
        download = method == 'GET' and vname == 'DealFileDetail'
        if method not in ('POST', 'PUT', 'PATCH', 'DELETE') and not download:
            return self.get_response(request)
        if vname in ('TokenRefreshView', 'TokenVerifyView'):
            return self.get_response(request)
        body = _body(request) if method != 'GET' else {}
        before = self._before(vname, method, match.kwargs, body)
        response = self.get_response(request)
        try:
            self._log(request, response, vname, method, match.kwargs, body, before, download)
        except Exception:
            log.exception('audit middleware failed for %s %s', method, path)
        return response

    # snapshot what a change is about to overwrite or delete
    def _before(self, vname, method, kw, body):
        from apps.deals.models import Deal, DealFile
        try:
            if vname == 'DealDetail' and method in ('PATCH', 'PUT', 'DELETE'):
                d = Deal.objects.filter(pk=kw['pk']).first()
                if d:
                    keys = [k for k in body if hasattr(d, k)] if method != 'DELETE' else []
                    return {'deal': d, 'old': {k: getattr(d, k) for k in keys}}
            if vname in ('DealFileDetail', 'DealFileReplace'):
                f = DealFile.objects.filter(pk=kw['fid'], deal_id=kw['pk']).select_related('deal').first()
                if f:
                    return {'deal': f.deal, 'file': f.name, 'role': f.doc_role}
            if 'pk' in kw:
                d = Deal.objects.filter(pk=kw['pk']).first()
                return {'deal': d} if d else {}
        except Exception:
            pass
        return {}

    def _log(self, request, response, vname, method, kw, body, before, download):
        user = getattr(request, 'user', None)
        code = response.status_code
        ok = code < 400
        data = getattr(response, 'data', None)
        data = data if isinstance(data, dict) else {}
        deal = before.get('deal')
        fname = before.get('file') or data.get('name') or ''
        changes: dict = {}
        action, summary, target = '', '', ''
        from apps.deals.models import Deal

        if vname == 'ThrottledTokenObtainPairView':
            from apps.users.models import User
            who = str(body.get('email', ''))
            u = User.objects.filter(email__iexact=who).first() or User.objects.filter(username__iexact=who).first()
            action = 'auth.login' if ok else 'auth.login_failed'
            summary = 'Signed in' if ok else f'Failed sign-in attempt as "{who}"'
            user = u if ok else None
            target = who
        elif vname == 'DealList' and method == 'POST':
            deal = Deal.objects.filter(pk=data.get('id')).first() if ok else None
            action, summary = 'deal.create', f'Added deal {data.get("name") or body.get("name", "")}'
        elif vname == 'DealDetail' and method == 'DELETE':
            action, summary = 'deal.delete', f'Deleted deal {deal.name if deal else ""}'
        elif vname == 'DealDetail':
            old = before.get('old', {})
            if deal is not None and ok:
                deal.refresh_from_db()
                changes = {k: [_short(old.get(k)), _short(getattr(deal, k))] for k in old if old.get(k) != getattr(deal, k)}
            action = 'deal.stage' if set(changes) == {'stage'} else 'deal.update'
            summary = ('Moved stage ' + ' → '.join(changes['stage'])) if action == 'deal.stage' else \
                      ('Edited ' + ', '.join(changes) if changes else 'Saved deal details (no change)')
        elif vname == 'DealFiles':
            action = 'file.upload' if ok else 'file.rejected'
            summary = f'Uploaded {fname}' if ok else f'Upload rejected: {_short(data.get("detail", ""), 200)}'
            target = fname
        elif vname == 'DealFileDetail' and method == 'GET':
            action = 'file.digest_view' if request.GET.get('digest') else 'file.download'
            summary = ('Opened fact sheet of ' if request.GET.get('digest') else 'Downloaded ') + fname
            target = fname
        elif vname == 'DealFileDetail' and method == 'PATCH':
            action, target = 'file.role', fname
            summary = f'Changed document type of {fname}: {before.get("role")} → {body.get("doc_role")}'
            changes = {'doc_role': [before.get('role'), body.get('doc_role')]}
        elif vname == 'DealFileDetail' and method == 'DELETE':
            action, summary, target = 'file.delete', f'Removed {fname}', fname
        elif vname == 'DealFileReplace':
            action, summary, target = 'file.replace', f'Re-uploaded {fname}', fname
        elif vname == 'DealAnalyze':
            action = 'analysis.start'
            bits = [f'model {body.get("model") or "default"}']
            if body.get('redigest'): bits.append('re-read all files')
            if body.get('allow_partial'): bits.append('run without unreadable files')
            if body.get('override_credit'): bits.append('override credit stop')
            summary = 'Started analysis (' + ', '.join(bits) + ')'
            if body.get('instructions'):
                changes = {'instructions': _short(body['instructions'], 2000)}
        elif vname == 'DealCancel':
            action, summary = 'analysis.cancel', 'Cancelled the running analysis'
        elif vname == 'DealFreeSpace':
            action, summary = 'storage.free', 'Freed storage (deleted original files, kept fact sheets and memos)'
        elif vname == 'FrameworkDetail':
            action, target = 'framework.update', kw.get('key', '')
            summary = f'Edited the {kw.get("key")} framework' + (f' → v{data.get("version")}' if data.get('version') else '') + \
                      (f': {body.get("note")}' if body.get('note') else '')
        elif vname == 'FrameworkRestore':
            action, target = 'framework.restore', kw.get('key', '')
            summary = f'{"Reset" if body.get("reset") else "Restored"} the {kw.get("key")} framework' + \
                      (f' to v{body.get("version")}' if body.get('version') else ' to defaults' if body.get('reset') else '')
        elif vname == 'UsageView':
            if 'console_balance' in body:
                action, summary = 'credit.sync', f'Recorded Claude Console balance ${body["console_balance"]}'
            elif 'topup' in body:
                action, summary = 'credit.topup', f'Recorded a top-up of ${body["topup"]}'
            elif method == 'POST':
                action, summary = 'storage.free', 'Freed storage on finished deals'
            else:
                action, summary = 'usage.settings', 'Changed usage settings: ' + ', '.join(f'{k}={v}' for k, v in body.items())
        elif vname == 'PasswordView':
            action, summary = 'account.password', 'Changed own password'
        elif vname == 'MeView':
            action, summary = 'account.update', 'Updated own profile: ' + ', '.join(f'{k}={v}' for k, v in body.items())
        elif vname == 'UserList':
            action, target = 'user.create', str(body.get('username') or body.get('email') or '')
            summary = f'Created user {target} ({body.get("role", "analyst")})'
        elif vname == 'UserDetail':
            target = str(data.get('username') or data.get('email') or kw.get('pk'))
            action, summary = 'user.update', f'Changed user {target}: ' + ', '.join(f'{k}={v}' for k, v in body.items())
        elif vname == 'UserResetPassword':
            target = str(data.get('username') or kw.get('pk'))
            action, summary = 'user.reset_password', f'Reset the password of {target}'
        else:
            action, summary = f'{method.lower()} {vname or "api"}', f'{method} {request.path}'
            if body:
                changes = {'request': {k: _short(v) for k, v in body.items()}}

        if not ok and action not in ('auth.login_failed', 'file.rejected'):
            summary = f'FAILED ({code}): {summary}' + (f' — {_short(data.get("detail"), 200)}' if data.get('detail') else '')
        record(action, summary, actor=user, deal=deal, target=target, changes=changes, ok=ok, status_code=code,
               method=method, path=request.path[:300], ip=_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', '')[:300])
