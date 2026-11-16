"""Framework tab API. The MAIN framework (admins) is the team default; every other person edits their own PERSONAL copy,
which only their analyses use, and can propose it to the main framework for an admin to approve."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from . import frameworks
from .models import AnalysisJob, Deal, FrameworkProposal, FrameworkVersion, PersonalFramework
from .views import can_edit
from apps.users.views import is_admin


def fw_json(fw):
    used = AnalysisJob.objects.filter(framework_version__isnull=False, deal__track_resolved=fw.key)
    return {'key': fw.key, 'name': fw.name, 'description': fw.description, 'config': fw.config, 'guidance': fw.guidance,
            'version': fw.version, 'updated_at': fw.updated_at,
            'updated_by': (fw.updated_by.full_name or fw.updated_by.username) if fw.updated_by else None,
            'deals_scored': Deal.objects.filter(track_resolved=fw.key, adcg_score__isnull=False).count(),
            'runs_on_this_version': used.filter(framework_version=fw.version).count()}


class FrameworkList(APIView):
    def get(self, request):
        return Response({'frameworks': [fw_json(frameworks.get(k)) for k in frameworks.KEYS], 'can_edit': can_edit(request.user)})


def who(u) -> str:
    return (u.full_name or u.username) if u else ''


def scope_json(request, key: str, scope: str) -> dict:
    """Main framework for admins (or on request); otherwise the person's own copy (main content until they save one)."""
    m = frameworks.main(key)
    pf = None if scope == 'main' else frameworks.personal(request.user, key)
    out = fw_json(m)
    if pf:
        out.update({'name': pf.name, 'description': pf.description, 'config': pf.config, 'guidance': pf.guidance,
                    'version': pf.version, 'updated_at': pf.updated_at, 'updated_by': who(request.user)})
    admin = is_admin(request.user)
    pend = FrameworkProposal.objects.filter(user=request.user, key=key, status='pending').first()
    out.update({'scope': scope, 'personal': bool(pf), 'main_version': m.version, 'base_version': pf.base_version if pf else m.version,
                'is_admin': admin,
                'can_edit': can_edit(request.user) and (admin if scope == 'main' else True),
                'my_proposal': {'id': pend.id, 'created_at': pend.created_at, 'changes': pend.changes} if pend else None,
                'pending_proposals': FrameworkProposal.objects.filter(status='pending').count() if admin else 0,
                'differs': bool(pf) and bool(frameworks.diff(key, m.config, pf.config))})
    return out


def scope_of(request) -> str:
    s = request.query_params.get('scope') or (request.data.get('scope') if isinstance(request.data, dict) else None)
    if s in ('main', 'mine'):
        return s
    return 'main' if is_admin(request.user) else 'mine'


class FrameworkDetail(APIView):
    def get(self, request, key):
        if key not in frameworks.ALL_KEYS:
            return Response({'detail': 'Unknown framework.'}, status=404)
        scope = scope_of(request)
        out = scope_json(request, key, scope)
        if request.query_params.get('preview'):
            pf = None if scope == 'main' else frameworks.personal(request.user, key)
            fw = frameworks.as_framework(pf) if pf else frameworks.main(key)
            if key == frameworks.HOUSE:
                tok = frameworks.ACTIVE_USER.set(request.user.pk if pf else None)
                try:
                    out['prompt_preview'] = frameworks.house_text('all')
                finally:
                    frameworks.ACTIVE_USER.reset(tok)
            else:
                out['prompt_preview'] = frameworks.render(fw)
        else:
            out['prompt_preview'] = None
        return Response(out)

    def put(self, request, key):
        if key not in frameworks.ALL_KEYS:
            return Response({'detail': 'Unknown framework.'}, status=404)
        if not can_edit(request.user):
            return Response({'detail': 'Your account is read-only.'}, status=403)
        scope = scope_of(request)
        base = request.data.get('base_version')
        try:
            if scope == 'main':
                if not is_admin(request.user):
                    return Response({'detail': 'Only an admin can change the main framework — save it to your own framework and propose it instead.'}, status=403)
                cur = frameworks.main(key)
                if base is not None and int(base) != cur.version:
                    return Response({'detail': f'Someone saved version {cur.version} while you were editing. Reload to see it, then re-apply your changes.'}, status=409)
                frameworks.save(key, config=request.data.get('config'), guidance=request.data.get('guidance', cur.guidance),
                                name=request.data.get('name') or cur.name, description=request.data.get('description', cur.description),
                                note=str(request.data.get('note') or ''), user=request.user)
            else:
                pf = frameworks.personal(request.user, key)
                cur_v = pf.version if pf else frameworks.main(key).version
                if base is not None and pf and int(base) != cur_v:
                    return Response({'detail': 'Your framework was saved from another window. Reload, then re-apply your changes.'}, status=409)
                src = pf or frameworks.main(key)
                frameworks.save_personal(request.user, key, config=request.data.get('config'),
                                         guidance=request.data.get('guidance', src.guidance), name=request.data.get('name') or src.name,
                                         description=request.data.get('description', src.description))
        except frameworks.FrameworkError as e:
            return Response({'detail': str(e)}, status=400)
        return Response(scope_json(request, key, scope))


class FrameworkResetMine(APIView):
    """Drop my personal copy → my analyses use the main framework again."""
    def post(self, request, key):
        PersonalFramework.objects.filter(user=request.user, key=key).delete()
        FrameworkProposal.objects.filter(user=request.user, key=key, status='pending').update(status='withdrawn')
        return Response(scope_json(request, key, 'mine'))


def proposal_json(p: FrameworkProposal) -> dict:
    m = frameworks.main(p.key)
    return {'id': p.id, 'key': p.key, 'framework': m.name, 'user': who(p.user), 'username': p.user.username, 'note': p.note,
            'changes': p.changes, 'status': p.status, 'response': p.response, 'created_at': p.created_at,
            'decided_by': who(p.decided_by) if p.decided_by else None, 'decided_at': p.decided_at,
            'base_version': p.base_version, 'main_version': m.version, 'applied_version': p.applied_version,
            'stale': p.status == 'pending' and p.base_version != m.version}


class FrameworkPropose(APIView):
    """POST {note} → ask the admin to adopt my personal copy of this framework into the main framework."""
    def post(self, request, key):
        pf = frameworks.personal(request.user, key)
        if not pf:
            return Response({'detail': 'Save a change to your framework first — then propose it.'}, status=400)
        m = frameworks.main(key)
        changes = frameworks.diff(key, m.config, pf.config)
        if not changes:
            return Response({'detail': 'Your framework is the same as the main framework — nothing to propose.'}, status=400)
        FrameworkProposal.objects.filter(user=request.user, key=key, status='pending').update(status='withdrawn')
        p = FrameworkProposal.objects.create(user=request.user, key=key, name=pf.name, description=pf.description, config=pf.config,
                                             guidance=pf.guidance, note=str(request.data.get('note') or '')[:2000],
                                             base_version=m.version, changes=changes)
        return Response(proposal_json(p), status=201)


class ProposalList(APIView):
    """Admins: every request (pending first). Others: their own."""
    def get(self, request):
        qs = FrameworkProposal.objects.select_related('user', 'decided_by')
        if not is_admin(request.user):
            qs = qs.filter(user=request.user)
        rows = sorted(qs[:200], key=lambda p: (p.status != 'pending', -p.created_at.timestamp()))
        return Response({'proposals': [proposal_json(p) for p in rows], 'is_admin': is_admin(request.user)})


class ProposalDecide(APIView):
    """POST {action: approve|reject|withdraw, response}. Approve = the proposer's framework becomes the new main version."""
    def post(self, request, pid):
        p = get_object_or_404(FrameworkProposal.objects.select_related('user'), pk=pid)
        action = request.data.get('action')
        if p.status != 'pending':
            return Response({'detail': f'This request is already {p.status}.'}, status=409)
        if action == 'withdraw':
            if p.user_id != request.user.pk:
                return Response({'detail': 'Only the person who sent it can withdraw it.'}, status=403)
            p.status = 'withdrawn'
            p.save(update_fields=['status'])
            return Response(proposal_json(p))
        if not is_admin(request.user):
            return Response({'detail': 'Only an admin can approve or reject framework changes.'}, status=403)
        p.response = str(request.data.get('response') or '')[:2000]
        p.decided_by, p.decided_at = request.user, timezone.now()
        if action == 'approve':
            try:
                fw = frameworks.save(p.key, config=p.config, guidance=p.guidance, name=frameworks.main(p.key).name,
                                     description=frameworks.main(p.key).description,
                                     note=f'Approved {who(p.user)}\'s proposal' + (f': {p.note}' if p.note else ''), user=request.user)
            except frameworks.FrameworkError as e:
                return Response({'detail': str(e)}, status=400)
            p.status, p.applied_version = 'approved', fw.version
            pf = frameworks.personal(p.user, p.key)
            if pf and not frameworks.diff(p.key, fw.config, pf.config):
                pf.delete()  # their copy is now the main framework — they follow the main again
        elif action == 'reject':
            p.status = 'rejected'
        else:
            return Response({'detail': 'action must be approve, reject or withdraw.'}, status=400)
        p.save()
        return Response(proposal_json(p))


class FrameworkHistory(APIView):
    def get(self, request, key):
        fw = frameworks.get(key)
        rows = fw.versions.select_related('created_by')[:100]
        return Response({'versions': [{'version': v.version, 'note': v.note, 'created_at': v.created_at,
                                       'by': (v.created_by.full_name or v.created_by.username) if v.created_by else None,
                                       'runs': AnalysisJob.objects.filter(framework_version=v.version, deal__track_resolved=key).count()}
                                      for v in rows]})


class FrameworkRestore(APIView):
    """MAIN framework only (admins). POST {version} → saves that version's content as a new version. POST {reset: true} → skill defaults."""
    def post(self, request, key):
        if not is_admin(request.user):
            return Response({'detail': 'Only an admin can restore the main framework.'}, status=403)
        fw = frameworks.get(key)
        if request.data.get('reset'):
            d = frameworks.default(key)
            new = frameworks.save(key, config=d['config'], guidance=d['guidance'], name=d['name'], description=d['description'],
                                  note='Reset to the ADCG skill defaults', user=request.user)
        else:
            v = get_object_or_404(FrameworkVersion, framework=fw, version=int(request.data.get('version') or 0))
            new = frameworks.save(key, config=v.config, guidance=v.guidance, name=v.name, description=v.description,
                                  note=f'Restored version {v.version}', user=request.user)
        return Response(scope_json(request, key, 'main'))
