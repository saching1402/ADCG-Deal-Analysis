from django.db import migrations


def backfill(apps, schema_editor):
    Deal = apps.get_model('deals', 'Deal')
    MemoVersion = apps.get_model('deals', 'MemoVersion')
    AnalysisJob = apps.get_model('deals', 'AnalysisJob')
    for d in Deal.objects.exclude(memo_html=''):
        if MemoVersion.objects.filter(deal=d).exists():
            continue
        job = AnalysisJob.objects.filter(deal=d, status='done').order_by('-finished_at').first()
        MemoVersion.objects.create(deal=d, job=job, html=d.memo_html, adcg_score=d.adcg_score, risk_score=d.risk_score,
                                   band=d.band, model=job.model if job else '',
                                   created_at=(job.finished_at if job and job.finished_at else d.analyzed_at or d.updated_at))


class Migration(migrations.Migration):
    dependencies = [('deals', '0009_memo_versions')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
