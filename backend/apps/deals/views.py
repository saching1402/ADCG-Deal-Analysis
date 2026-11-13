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

from . import engine
from .extract import ACCEPTED, ext_of
from .models import AnalysisJob, Deal, DealFile, Stage, Status, Track

EDIT_FIELDS = ['name', 'website', 'track', 'sponsor', 'sector', 'sub_sector', 'notes', 'stage', 'ev', 'multiple',
               'leverage', 'one_liner', 'recommendation']


def can_edit(user) -> bool:
    return bool(user and (user.is_staff or getattr(user, 'role', '') in ('admin', 'analyst')))


def job_json(j: AnalysisJob | None):
    if not j:
        return None
    return {'id': j.id, 'status': j.status, 'stage': j.stage, 'stage_detail': j.stage_detail, 'model': j.model,
            'cost': round(j.cost, 4), 'searches': j.searches, 'input_tokens': j.input_tokens, 'output_tokens': j.output_tokens,
            'error': j.error, 'log': j.log[-30:], 'created_at': j.created_at, 'started_at': j.started_at,
            'finished_at': j.finished_at, 'instructions': j.instructions}


def file_json(f: DealFile):
    return {'id': f.id, 'name': f.name, 'size': f.size, 'status': f.status, 'method': f.method, 'pages': f.pages,
            'chars': f.chars, 'error': f.error, 'uploaded_at': f.uploaded_at, 'has_digest': bool(f.digest)}


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
            'storage': 's3' if settings.S3_BUCKET else 'disk'}


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


class DealDetail(APIView):
    def get(self, request, pk):
        d = get_object_or_404(Deal, pk=pk)
        out = row(d, job_json(d.jobs.first()))
        out.update({'notes': d.notes, 'recommendation': d.recommendation, 'facts': d.facts, 'summary': d.summary,
                    'scorecard': d.scorecard, 'research': d.research, 'sources': d.sources,
                    'has_memo': bool(d.memo_html), 'files': [file_json(f) for f in d.files.all()],
                    'jobs': [job_json(j) for j in d.jobs.all()[:10]], 'can_edit': can_edit(request.user),
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
        up.seek(0)
        f = DealFile(deal=d, name=up.name[:255], size=up.size, content_type=up.content_type or '', sha256=sha,
                     uploaded_by=request.user)
        f.file.save(up.name, up, save=False)
        f.save()
        Deal.objects.filter(pk=d.pk).update(updated_at=timezone.now())
        return Response(file_json(f), status=201)


class DealFileDetail(APIView):
    def get(self, request, pk, fid):
        f = get_object_or_404(DealFile, pk=fid, deal_id=pk)
        if request.query_params.get('digest'):
            return Response({'id': f.id, 'name': f.name, 'digest': f.digest})
        ctype = f.content_type or mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        return FileResponse(f.file.open('rb'), as_attachment=True, filename=f.name, content_type=ctype)

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
        if request.data.get('redigest'):
            d.files.update(status='uploaded', digest='')
        job = engine.queue(d, request.user, request.data.get('model') or '', str(request.data.get('instructions') or '')[:8000])
        return Response(job_json(job), status=202)


class DealCancel(APIView):
    def post(self, request, pk):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        n = AnalysisJob.objects.filter(deal_id=pk, status__in=[Status.QUEUED, Status.RUNNING]).update(
            status=Status.ERROR, error='Cancelled', finished_at=timezone.now())
        Deal.objects.filter(pk=pk, status__in=[Status.QUEUED, Status.RUNNING]).update(status=Status.DRAFT)
        return Response({'cancelled': n})


class DealMemo(APIView):
    def get(self, request, pk):
        d = get_object_or_404(Deal, pk=pk)
        if not d.memo_html:
            return Response({'detail': 'No memo yet.'}, status=404)
        return Response({'html': d.memo_html, 'name': d.name})


class PipelineStats(APIView):
    def get(self, request):
        agg = Deal.objects.aggregate(n=Count('id'), analyzed=Count('id', filter=Q(adcg_score__isnull=False)))
        return Response(agg)
