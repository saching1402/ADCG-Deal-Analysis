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
        if if_empty and Deal.objects.exists():
            self.stdout.write('Deals present — skipping ledger seed.')
            return
        n = 0
        for r in json.loads(Path(file).read_text(encoding='utf-8')):
            if Deal.objects.filter(name=r['name']).exists():
                continue
            Deal.objects.create(track=r['track_resolved'], stage=Stage.ANALYZED, status=Status.DONE, legacy=True,
                                band=eng.band_of(r['adcg_score'])[0], **r)
            n += 1
        self.stdout.write(f'Seeded {n} prior deals.')
