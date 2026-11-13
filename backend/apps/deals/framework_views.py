"""Framework tab API: view, edit (versioned), history, restore, reset to the skill defaults."""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from . import frameworks
from .models import AnalysisJob, Deal, FrameworkVersion
from .views import can_edit


def fw_json(fw):
    used = AnalysisJob.objects.filter(framework_version__isnull=False, deal__track_resolved=fw.key)
    return {'key': fw.key, 'name': fw.name, 'description': fw.description, 'config': fw.config, 'guidance': fw.guidance,
            'version': fw.version, 'updated_at': fw.updated_at,
            'updated_by': getattr(fw.updated_by, 'email', None),
            'deals_scored': Deal.objects.filter(track_resolved=fw.key, adcg_score__isnull=False).count(),
            'runs_on_this_version': used.filter(framework_version=fw.version).count()}


class FrameworkList(APIView):
    def get(self, request):
        return Response({'frameworks': [fw_json(frameworks.get(k)) for k in frameworks.KEYS], 'can_edit': can_edit(request.user)})


class FrameworkDetail(APIView):
    def get(self, request, key):
        if key not in frameworks.KEYS:
            return Response({'detail': 'Unknown framework.'}, status=404)
        out = fw_json(frameworks.get(key))
        out['can_edit'] = can_edit(request.user)
        out['prompt_preview'] = frameworks.render(frameworks.get(key)) if request.query_params.get('preview') else None
        return Response(out)

    def put(self, request, key):
        if key not in frameworks.KEYS:
            return Response({'detail': 'Unknown framework.'}, status=404)
        if not can_edit(request.user):
            return Response({'detail': 'Only admins and analysts can edit frameworks.'}, status=403)
        cur = frameworks.get(key)
        base = request.data.get('base_version')
        if base is not None and int(base) != cur.version:
            return Response({'detail': f'Someone saved version {cur.version} while you were editing. Reload to see it, then re-apply your changes.'}, status=409)
        try:
            fw = frameworks.save(key, config=request.data.get('config'), guidance=request.data.get('guidance', cur.guidance),
                                 name=request.data.get('name') or cur.name, description=request.data.get('description', cur.description),
                                 note=str(request.data.get('note') or ''), user=request.user)
        except frameworks.FrameworkError as e:
            return Response({'detail': str(e)}, status=400)
        return Response(fw_json(fw))


class FrameworkHistory(APIView):
    def get(self, request, key):
        fw = frameworks.get(key)
        rows = fw.versions.select_related('created_by')[:100]
        return Response({'versions': [{'version': v.version, 'note': v.note, 'created_at': v.created_at,
                                       'by': getattr(v.created_by, 'email', None),
                                       'runs': AnalysisJob.objects.filter(framework_version=v.version, deal__track_resolved=key).count()}
                                      for v in rows]})


class FrameworkRestore(APIView):
    """POST {version} → saves that version's content as a new version. POST {reset: true} → skill defaults."""
    def post(self, request, key):
        if not can_edit(request.user):
            return Response({'detail': 'Read-only account.'}, status=403)
        fw = frameworks.get(key)
        if request.data.get('reset'):
            d = frameworks.default(key)
            new = frameworks.save(key, config=d['config'], guidance=d['guidance'], name=d['name'], description=d['description'],
                                  note='Reset to the ADCG skill defaults', user=request.user)
        else:
            v = get_object_or_404(FrameworkVersion, framework=fw, version=int(request.data.get('version') or 0))
            new = frameworks.save(key, config=v.config, guidance=v.guidance, name=v.name, description=v.description,
                                  note=f'Restored version {v.version}', user=request.user)
        return Response(fw_json(new))
