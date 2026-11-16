"""python manage.py seed_frameworks — create the three editable frameworks from the ADCG skill defaults if missing."""
from django.core.management.base import BaseCommand

from apps.deals import frameworks


class Command(BaseCommand):
    help = 'Ensure the ADCG Buyout, CV and Venture Growth frameworks exist.'

    def handle(self, **opts):
        for k in frameworks.ALL_KEYS:
            fw = frameworks.ensure(k)
            self.stdout.write(f'{fw.name}: version {fw.version}')
