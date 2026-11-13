"""python manage.py seed_ledger [--if-empty] — load the prior ADCG deal ledger into the pipeline."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.deals.models import Deal, Stage, Status
from apps.deals.scoring import adcg_scorecard as eng


class Command(BaseCommand):
    help = 'Seed the pipeline with previously scored deals (scores only).'

    def add_arguments(self, parser):
        parser.add_argument('--if-empty', action='store_true')
        parser.add_argument('--file', default=str(Path(settings.BASE_DIR) / 'data' / 'ledger_seed.json'))

    def handle(self, if_empty=False, file='', **opts):
        rows = json.loads(Path(file).read_text(encoding='utf-8'))
        if if_empty and Deal.objects.exists():
            # never re-add deals the team deleted; only backfill websites (for logos) on ledger rows
            n = 0
            for r in rows:
                if r.get('website'):
                    n += Deal.objects.filter(name=r['name'], legacy=True, website='').update(website=r['website'])
            self.stdout.write(f'Deals present — ledger seed skipped; {n} website(s) backfilled.')
            return
        n = 0
        for r in rows:
            if Deal.objects.filter(name=r['name']).exists():
                continue
            Deal.objects.create(track=r['track_resolved'], stage=Stage.ANALYZED, status=Status.DONE, legacy=True,
                                band=eng.band_of(r['adcg_score'])[0], **r)
            n += 1
        self.stdout.write(f'Seeded {n} prior deals.')
