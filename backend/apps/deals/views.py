"""Deal pipeline API (all endpoints need a signed-in user; changes need admin/analyst)."""
from __future__ import annotations

import hashlib
import mimetypes

from django.conf import settings
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import engine, suggest, usage
from .extract import ACCEPTED, ext_of, inspect
from .roles import LABEL as ROLE_LABEL, ROLES, guess_role
from .models import AnalysisJob, Deal, DealFile, MemoVersion, Stage, Status, Track

EDIT_FIELDS = ['name', 'website', 'track', 'sponsor', 'sector', 'sub_sector', 'notes', 'stage', 'ev', 'multiple',
               'leverage', 'one_liner', 'recommendation']


def can_edit(user) -> bool:
    return bool(user and (user.is_staff or getattr(user, 'role', '') in ('admin', 'analyst')))


def job_json(j: AnalysisJob | None):
    if not j:
        return None
    return {'id': j.id, 'status': j.status, 'stage': j.stage, 'stage_detail': j.stage_detail, 'model': j.model,
            'cost': round(j.cost, 4), 'searches': j.searches, 'input_tokens': j.input_tokens, 'output_tokens': j.output_tokens,
            'error': j.error, 'log': j.log[-40:], 'allow_partial': j.allow_partial, 'created_at': j.created_at, 'started_at': j.started_at,
            'finished_at': j.finished_at, 'instructions': j.instructions, 'framework_version': j.framework_version, 'mode': j.mode}


def file_missing(f: DealFile) -> bool:
    try:
        return not f.file.storage.exists(f.file.name)
    except Exception:
        return False


def file_json(f: DealFile, check_missing: bool = False):
    return {'missing': file_missing(f) if check_missing and not f.archived_at else False, 'archived_at': f.archived_at,
            'doc_role': f.doc_role or 'other', 'doc_role_label': ROLE_LABEL.get(f.doc_role or 'other', 'Other'),
            'role_set_by_user': f.role_set_by_user,'id': f.id, 'name': f.name, 'size': f.size, 'status': f.status, 'method': f.method, 'pages': f.pages,
            'chars': f.chars, 'error': f.error, 'uploaded_at': f.uploaded_at, 'has_digest': bool(f.digest),
            'readability': f.readability, 'coverage': f.coverage}


def row(d: Deal, job=None):
    return {'id': str(d.id), 'name': d.name, 'website': d.website, 'track': d.track, 'track_resolved': d.track_resolved,
            'sponsor': d.sponsor, 'sector': d.sector, 'sub_sector': d.sub_sector, 'stage': d.stage, 'status': d.status,
            'ev': d.ev, 'multiple': d.multiple, 'leverage': d.leverage, 'one_liner': d.one_liner,
            'adcg_score': d.adcg_score, 'risk_score': d.risk_score, 'band': d.band, 'legacy': d.legacy,
            'file_count': getattr(d, 'n_files', None), 'has_memo': bool(d.memo_html) if hasattr(d, 'memo_html') else None,
            'analyzed_at': d.analyzed_at, 'updated_at': d.updated_at, 'created_at': d.created_at,
            'total_cost': round(d.total_cost, 2), 'job': job}


def meta():
    return {'models': [{'id': k, 'label': v['label']} for k, v in settings.ANALYSIS_MODELS.items()],
            'default_model': settings.ANALYSIS_MODEL, 'digest_model': settings.DIGEST_MODEL,
            'stages': [{'id': s.value, 'label': s.label} for s in Stage],
            'tracks': [{'id': t.value, 'label': t.label} for t in Track],
            'accepted': ACCEPTED, 'max_upload_mb': settings.MAX_UPLOAD_MB, 'max_files': settings.MAX_FILES_PER_DEAL,
            'api_key_set': bool(settings.ANTHROPIC_API_KEY),
            'storage': 's3' if settings.S3_BUCKET else 'disk', 'storage_persistent': settings.STORAGE_PERSISTENT,
            'doc_roles': [{'id': k, 'label': v} for k, v in ROLES],
            'recent_costs': recent_costs()}


def recent_costs() -> dict:
    """Actual cost of the last 10 completed runs per model (calibrates the estimate on the New deal page)."""
    out = {}
    for m in settings.ANALYSIS_MODELS:
        c = list(AnalysisJob.objects.filter(model=m, status=Status.DONE, cost__gt=0).order_by('-finished_at')
                 .values_list('cost', flat=True)[:10])
        if c:
            out[m] = {'n': len(c), 'avg': round(sum(c) / len(c), 2), 'min': round(min(c), 2), 'max': round(max(c), 2)}
    return out


class DealList(APIView):
    def get(self, request):
        qs = Deal.objects.annotate(n_files=Count('files')).defer('research', 'memo_html', 'scorecard')
        running = {j.deal_id: job_json(j) for j in AnalysisJob.objects.filter(status__in=[Status.QUEUED, Status.RUNNING])}
        return Response({'deals': [row(d, running.get(d.id)) for d in qs], 'meta': meta(), 'can_edit': can_edit(request.user)})

    def post(self, request):
        if not can_edit(request.user):
            return Response({'detail': 'Only admins and analysts can add deals.'}, status=403)
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'detail': 'Company / deal name is required.'}, status=400)
        d = Deal(created_by=request.user)
        for f in EDIT_FIELDS:
            if f in request.data and f != 'stage':
                setattr(d, f, str(request.data.get(f) or '').strip())
        if d.track not in Track.values:
            d.track = Track.AUTO
        d.save()
        return Response(row(d), status=201)


def criteria_basis(d: Deal) -> dict | None:
    """The framework definition this deal was scored against (the version its last scoring run used), so the Criteria tab
    can show which criteria are standard, which were tailored to the deal, and how the weights moved."""
    from .models import FrameworkVersion
    from . import frameworks
    if not (isinstance(d.scorecard, dict) and d.scorecard.get('sections')):
        return None
    key = d.track_resolved if d.track_resolved in frameworks.KEYS else 'buyout'
    fw = frameworks.get(key)
    job = d.jobs.filter(status='done', framework_version__isnull=False).exclude(mode='revise').first() \
        or d.jobs.filter(framework_version__isnull=False).first()
    ver = job.framework_version if job else None
    src = job.framework_source if job else ''
    snap = None if (job and job.framework_config) or src else (FrameworkVersion.objects.filter(framework=fw, version=ver).first() if ver else None)
    cfg = (job.framework_config if job and job.framework_config else None) or (snap.config if snap else fw.config)
    lib = cfg.get('sector_library') or []
    sub = (d.sub_sector or d.scorecard.get('sub_sector') or '').lower()
    match = next((b for b in lib if b.get('name') and any(w in sub for w in b['name'].lower().replace('/', ' ').split() if len(w) > 4)), None)
    return {'key': key, 'name': snap.name if snap else fw.name, 'version': ver or fw.version, 'source': src, 'flex': cfg.get('weights_flex', key != 'vg'),
            'sections': [{'name': s['name'], 'weight': s['weight'], 'description': s.get('description', ''),
                          'criteria': [c['name'] for c in s.get('criteria') or []]} for s in cfg.get('sections') or []],
            'sector_block': match.get('name') if match else None}


class DealDetail(APIView):
    def get(self, request, pk):
        d = get_object_or_404(Deal, pk=pk)
        out = row(d, job_json(d.jobs.first()))
        out.update({'notes': d.notes, 'recommendation': d.recommendation, 'facts': d.facts, 'summary': d.summary,
                    'scorecard': d.scorecard, 'research': d.research, 'sources': d.sources,
                    'risk_review': d.risk_review, 'risk_items': d.risk_items,
                    'has_memo': bool(d.memo_html), 'memo_count': d.memos.count(),
                    'last_memo_at': d.memos.values_list('created_at', flat=True).first(), 'files': [file_json(f, check_missing=True) for f in d.files.all()],
                    'jobs': [job_json(j) for j in d.jobs.all()[:10]], 'can_edit': can_edit(request.user),
                    'open_comments': d.comments.filter(status='open').count(),
                    'criteria_basis': criteria_basis(d),
                    'meta': meta()})
        return Response(out)

    def patch(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        d = get_object_or_404(Deal, pk=pk)
        for f in EDIT_FIELDS:
            if f in request.data:
                v = str(request.data.get(f) or '').strip()
                if f == 'stage' and v not in Stage.values:
                    return Response({'detail': 'Unknown stage.'}, status=400)
                if f == 'track' and v not in Track.values:
                    return Response({'detail': 'Unknown track.'}, status=400)
                setattr(d, f, v)
        d.save()
        return Response(row(d))

    def delete(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        d = get_object_or_404(Deal, pk=pk)
        for f in d.files.all():
            f.file.delete(save=False)
        d.delete()
        return Response(status=204)


class DealFiles(APIView):
    """One file per request: the browser uploads 15-20 files in parallel with per-file progress and retries."""
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        d = get_object_or_404(Deal, pk=pk)
        up = request.FILES.get('file')
        if not up:
            return Response({'detail': 'No file in the request (field "file").'}, status=400)
        if d.files.count() >= settings.MAX_FILES_PER_DEAL:
            return Response({'detail': f'A deal can hold up to {settings.MAX_FILES_PER_DEAL} files.'}, status=400)
        if up.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            return Response({'detail': f'{up.name} is over {settings.MAX_UPLOAD_MB} MB.'}, status=400)
        if ext_of(up.name) not in ACCEPTED:
            return Response({'detail': f'{up.name}: file type not supported ({", ".join(ACCEPTED)}).'}, status=400)
        h = hashlib.sha256()
        for chunk in up.chunks():
            h.update(chunk)
        sha = h.hexdigest()
        dup = d.files.filter(sha256=sha).first()
        if dup:
            return Response(file_json(dup), status=200)
        # readability check before the file is accepted (local, no API cost)
        up.seek(0)
        chk = inspect(up.name, up.read())
        if chk['status'] == 'block':
            return Response({'detail': f'{up.name}: {chk["summary"]}', 'readability': chk}, status=422)
        up.seek(0)
        f = DealFile(deal=d, name=up.name[:255], size=up.size, content_type=up.content_type or '', sha256=sha,
                     uploaded_by=request.user, readability=chk, doc_role=guess_role(up.name))
        f.file.save(up.name, up, save=False)
        f.save()
        Deal.objects.filter(pk=d.pk).update(updated_at=timezone.now())
        return Response(file_json(f), status=201)


class DealFileDetail(APIView):
    def get(self, request, pk, fid):
        f = get_object_or_404(DealFile, pk=fid, deal_id=pk)
        if request.query_params.get('digest'):
            return Response({'id': f.id, 'name': f.name, 'digest': f.digest})
        if f.archived_at:
            return Response({'detail': 'The original was deleted to free space; its fact sheet is kept.'}, status=410)
        ctype = f.content_type or mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        return FileResponse(f.file.open('rb'), as_attachment=True, filename=f.name, content_type=ctype)

    def patch(self, request, pk, fid):
        """Set what the document is (e.g. mark the CIM) — the CIM anchors every headline fact."""
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        f = get_object_or_404(DealFile, pk=fid, deal_id=pk)
        role = str(request.data.get('doc_role') or '')
        if role not in ROLE_LABEL:
            return Response({'detail': 'Unknown document type.'}, status=400)
        f.doc_role, f.role_set_by_user = role, True
        f.save(update_fields=['doc_role', 'role_set_by_user'])
        return Response(file_json(f))

    def delete(self, request, pk, fid):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        f = get_object_or_404(DealFile, pk=fid, deal_id=pk)
        f.file.delete(save=False)
        f.delete()
        return Response(status=204)


class DealAnalyze(APIView):
    def post(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        d = get_object_or_404(Deal, pk=pk)
        if not settings.ANTHROPIC_API_KEY:
            return Response({'detail': 'Set ANTHROPIC_API_KEY in the Railway service variables to run analyses.'}, status=400)
        if d.jobs.filter(status__in=[Status.QUEUED, Status.RUNNING]).exists():
            return Response({'detail': 'An analysis is already running for this deal.'}, status=409)
        paused = usage.credit_guard()
        if paused and not request.data.get('override_credit'):
            return Response({'detail': paused, 'code': 'credit_paused'}, status=409)
        if request.data.get('redigest'):
            d.files.filter(archived_at__isnull=True).update(status='uploaded', digest='', coverage={}, error='')
        job = engine.queue(d, request.user, request.data.get('model') or '', str(request.data.get('instructions') or '')[:8000],
                           allow_partial=bool(request.data.get('allow_partial')))
        return Response(job_json(job), status=202)


class DealCancel(APIView):
    def post(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        n = AnalysisJob.objects.filter(deal_id=pk, status__in=[Status.QUEUED, Status.RUNNING]).update(
            status=Status.ERROR, error='Cancelled', finished_at=timezone.now())
        Deal.objects.filter(pk=pk, status__in=[Status.QUEUED, Status.RUNNING]).update(status=Status.DRAFT)
        return Response({'cancelled': n})


def memo_meta(m: MemoVersion, n: int, latest_id: int | None) -> dict:
    return {'id': m.id, 'number': n, 'created_at': m.created_at, 'adcg_score': m.adcg_score, 'risk_score': m.risk_score,
            'band': m.band, 'model': m.model, 'framework_version': m.framework_version, 'is_latest': m.id == latest_id}


class DealMemo(APIView):
    """GET → latest memo + version list; ?version=<id> → that version; ?list=1 → versions only."""
    def get(self, request, pk):
        d = get_object_or_404(Deal, pk=pk)
        vs = list(d.memos.only('id', 'created_at', 'adcg_score', 'risk_score', 'band', 'model', 'framework_version'))
        latest_id = vs[0].id if vs else None
        versions = [memo_meta(m, len(vs) - i, latest_id) for i, m in enumerate(vs)]
        if request.query_params.get('list'):
            return Response({'versions': versions, 'name': d.name})
        want = request.query_params.get('version')
        if want:
            m = get_object_or_404(MemoVersion, pk=want, deal=d)
            cur = next(v for v in versions if v['id'] == m.id)
            return Response({'html': m.html, 'name': d.name, 'version': cur, 'versions': versions})
        if vs:
            m = d.memos.first()
            return Response({'html': m.html, 'name': d.name, 'version': versions[0], 'versions': versions})
        if d.memo_html:  # legacy memo without a version row
            return Response({'html': d.memo_html, 'name': d.name, 'version': None, 'versions': []})
        return Response({'detail': 'No memo yet.'}, status=404)


class PipelineStats(APIView):
    def get(self, request):
        agg = Deal.objects.aggregate(n=Count('id'), analyzed=Count('id', filter=Q(adcg_score__isnull=False)))
        return Response(agg)


class CompanySuggest(APIView):
    """GET ?q= → {pipeline: [deals matching], companies: [{name, domain, description}]} for the search boxes."""
    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'pipeline': [], 'companies': []})
        mine = Deal.objects.filter(Q(name__icontains=q) | Q(website__icontains=q) | Q(sponsor__icontains=q)).only(
            'id', 'name', 'website', 'track', 'track_resolved', 'adcg_score', 'stage')[:6]
        pipeline = [{'id': str(d.id), 'name': d.name, 'domain': suggest.domain_of(d.website), 'track': d.track_resolved or d.track,
                     'adcg_score': d.adcg_score, 'stage': d.stage} for d in mine]
        companies = [] if request.query_params.get('pipeline_only') else suggest.external(q)
        have = {p['domain'] for p in pipeline if p['domain']}
        return Response({'pipeline': pipeline, 'companies': [c for c in companies if c['domain'] not in have]})


class DealFreeSpace(APIView):
    """Delete a deal's original files (fact sheets, research, scores and memo are kept)."""
    def post(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        d = get_object_or_404(Deal, pk=pk)
        if d.status in (Status.QUEUED, Status.RUNNING):
            return Response({'detail': 'Wait for the running analysis to finish.'}, status=409)
        n, freed = usage.archive_deal_files(d)
        return Response({'files': n, 'freed': freed})


class UsageView(APIView):
    def get(self, request):
        out = usage.compute()
        out['can_edit'] = can_edit(request.user)
        return Response(out)

    def patch(self, request):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        try:
            if request.data.get('console_balance') not in (None, ''):
                usage.record_balance(float(request.data['console_balance']), request.user, str(request.data.get('note') or ''))
            elif request.data.get('topup') not in (None, ''):
                if float(request.data['topup']) <= 0:
                    return Response({'detail': 'Enter the amount you added.'}, status=400)
                usage.record_topup(float(request.data['topup']), request.user, str(request.data.get('note') or ''))
            else:
                usage.save_settings(request.data)
        except (TypeError, ValueError) as e:
            return Response({'detail': str(e) if 'Console' in str(e) else 'Enter numbers only.'}, status=400)
        out = usage.compute()
        out['can_edit'] = can_edit(request.user)
        return Response(out)

    def post(self, request):
        """Free space from every approved / passed / on-hold deal (or the given deal ids)."""
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        ids = request.data.get('deal_ids')
        qs = Deal.objects.filter(pk__in=ids) if ids else Deal.objects.filter(stage__in=[Stage.APPROVED, Stage.PASSED, Stage.ON_HOLD])
        n = freed = 0
        for d in qs.exclude(status__in=[Status.QUEUED, Status.RUNNING]):
            a, b = usage.archive_deal_files(d)
            n, freed = n + a, freed + b
        return Response({'files': n, 'freed': freed})


class DealFileReplace(APIView):
    """Re-upload a file into the same slot (lost copy, or a corrected version). Same content → fact sheet kept."""
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk, fid):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        f = get_object_or_404(DealFile, pk=fid, deal_id=pk)
        if f.deal.status in (Status.QUEUED, Status.RUNNING):
            return Response({'detail': 'Wait for the running analysis to finish.'}, status=409)
        up = request.FILES.get('file')
        if not up:
            return Response({'detail': 'No file in the request (field "file").'}, status=400)
        if up.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            return Response({'detail': f'{up.name} is over {settings.MAX_UPLOAD_MB} MB.'}, status=400)
        if ext_of(up.name) not in ACCEPTED:
            return Response({'detail': f'{up.name}: file type not supported.'}, status=400)
        h = hashlib.sha256()
        for chunk in up.chunks():
            h.update(chunk)
        sha = h.hexdigest()
        up.seek(0)
        chk = inspect(up.name, up.read())
        if chk['status'] == 'block':
            return Response({'detail': f'{up.name}: {chk["summary"]}', 'readability': chk}, status=422)
        up.seek(0)
        same = bool(f.sha256) and sha == f.sha256 and f.status == 'digested' and bool(f.digest)
        try:
            if f.file and f.file.storage.exists(f.file.name):
                f.file.delete(save=False)
        except Exception:
            pass
        f.file.save(up.name, up, save=False)
        f.size, f.sha256, f.readability, f.archived_at = up.size, sha, chk, None
        f.content_type = up.content_type or f.content_type
        if not same:  # new content → read and verify again on the next run
            f.name = up.name[:255]
            f.status, f.digest, f.coverage, f.error, f.method, f.pages, f.chars = 'uploaded', '', {}, '', '', None, None
        f.uploaded_by = request.user
        f.save()
        Deal.objects.filter(pk=pk).update(updated_at=timezone.now())
        out = file_json(f, check_missing=True)
        out['kept_fact_sheet'] = same
        return Response(out)


# ── memo review comments + revise-only runs ──────────────────────────────────
def comment_json(c) -> dict:
    return {'id': c.id, 'stance': c.stance, 'text': c.text, 'quote': c.quote, 'section': c.section, 'via': c.via,
            'status': c.status, 'response': c.response, 'memo_id': c.memo_id, 'applied_in': c.applied_in_id,
            'author': (c.author.full_name or c.author.username) if c.author else '', 'author_id': str(c.author_id) if c.author_id else None,
            'created_at': c.created_at, 'updated_at': c.updated_at}


class DealComments(APIView):
    """GET → all review comments on the deal's memos; POST {text, stance, quote, section, via, memo_id} adds one."""
    def get(self, request, pk):
        d = get_object_or_404(Deal, pk=pk)
        return Response({'comments': [comment_json(c) for c in d.comments.select_related('author')]})

    def post(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Your role cannot comment.'}, status=403)
        from .models import MemoComment
        d = get_object_or_404(Deal, pk=pk)
        text = str(request.data.get('text') or '').strip()
        if not text:
            return Response({'detail': 'Write or dictate the comment first.'}, status=400)
        stance = request.data.get('stance') if request.data.get('stance') in MemoComment.STANCES else 'context'
        memo_id = request.data.get('memo_id') or (d.memos.values_list('id', flat=True).first())
        c = MemoComment.objects.create(deal=d, memo_id=memo_id if d.memos.filter(pk=memo_id).exists() else None,
                                       author=request.user, stance=stance, text=text[:8000],
                                       quote=str(request.data.get('quote') or '')[:4000], section=str(request.data.get('section') or '')[:200],
                                       via='voice' if request.data.get('via') == 'voice' else 'typed')
        return Response(comment_json(c), status=201)


class DealCommentDetail(APIView):
    """PATCH {text, stance, status: open|dismissed} · DELETE (author or admin; applied comments stay as history)."""
    def _get(self, request, pk, cid):
        from .models import MemoComment
        return get_object_or_404(MemoComment.objects.select_related('author'), pk=cid, deal_id=pk)

    def patch(self, request, pk, cid):
        c = self._get(request, pk, cid)
        if not can_edit(request.user):
            return Response({'detail': 'Your role cannot edit comments.'}, status=403)
        if c.status == 'applied':
            return Response({'detail': 'This comment is already applied in a memo version; add a new comment instead.'}, status=400)
        from .models import MemoComment
        if 'text' in request.data and str(request.data['text']).strip():
            c.text = str(request.data['text']).strip()[:8000]
        if request.data.get('stance') in MemoComment.STANCES:
            c.stance = request.data['stance']
        if request.data.get('status') in ('open', 'dismissed'):
            c.status = request.data['status']
        c.save()
        return Response(comment_json(c))

    def delete(self, request, pk, cid):
        c = self._get(request, pk, cid)
        from apps.users.views import is_admin
        if c.status == 'applied':
            return Response({'detail': 'Applied comments are kept as the record of the revision.'}, status=400)
        if c.author_id != request.user.pk and not is_admin(request.user):
            return Response({'detail': 'Only the author or an admin can delete a comment.'}, status=403)
        c.delete()
        return Response(status=204)


class DealRevise(APIView):
    """POST {model} → a revise-only run: re-scores and rewrites the affected memo sections from the open comments."""
    def post(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Your role cannot run analyses.'}, status=403)
        d = get_object_or_404(Deal, pk=pk)
        if not settings.ANTHROPIC_API_KEY:
            return Response({'detail': 'Set ANTHROPIC_API_KEY in the Railway service variables to run analyses.'}, status=400)
        if not d.memo_html:
            return Response({'detail': 'There is no memo to revise yet — run the analysis first.'}, status=400)
        n = d.comments.filter(status='open').count()
        if not n:
            return Response({'detail': 'Add at least one comment to the memo first.'}, status=400)
        if d.jobs.filter(status__in=[Status.QUEUED, Status.RUNNING]).exists():
            return Response({'detail': 'An analysis is already running for this deal.'}, status=409)
        paused = usage.credit_guard()
        if paused and not request.data.get('override_credit'):
            return Response({'detail': paused, 'code': 'credit_paused'}, status=409)
        last = d.jobs.filter(status=Status.DONE).first()
        job = engine.queue(d, request.user, request.data.get('model') or (last.model if last else ''), mode='revise',
                           instructions=f'Revise from {n} review comment(s)')
        return Response(job_json(job), status=202)
