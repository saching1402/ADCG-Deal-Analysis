"""python manage.py analysis_worker — runs queued deal analyses (started by start.sh)."""
import datetime as dt
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from apps.deals.engine import claim_next, run_job
from apps.deals.models import AnalysisJob, Deal, DealFile, Status

log = logging.getLogger('apps.deals')


def _work() -> bool:
    close_old_connections()
    job = claim_next()
    if job is None:
        return False
    log.info('Analysis %s started: %s', job.id, job.deal.name)
    run_job(job)
    log.info('Analysis %s finished: %s', job.id, job.status)
    close_old_connections()
    return True


class Command(BaseCommand):
    help = 'Process queued deal analyses.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Drain the queue once, then exit')

    def handle(self, once=False, **opts):
        # jobs left running by a previous container (redeploy mid-analysis) are re-queued; digests already done are kept
        stale = timezone.now() - dt.timedelta(minutes=2)
        ids = list(AnalysisJob.objects.filter(status=Status.RUNNING, started_at__lt=stale).values_list('id', flat=True))
        if ids:
            AnalysisJob.objects.filter(id__in=ids).update(status=Status.QUEUED)
            DealFile.objects.filter(status='digesting').update(status='uploaded')
            log.info('Re-queued %s interrupted analyses', len(ids))
        workers = max(1, settings.ANALYSIS_CONCURRENCY)
        self.stdout.write(f'Analysis worker running ({workers} parallel, model {settings.ANALYSIS_MODEL}, '
                          f'API key {"set" if settings.ANTHROPIC_API_KEY else "MISSING"})')
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while True:
                busy = list(pool.map(lambda _: _work(), range(workers)))
                if once and not any(busy):
                    return
                if not any(busy):
                    time.sleep(3)
