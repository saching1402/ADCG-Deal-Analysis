"""Tidy headline facts written before the clean format: one short value each, detail moved to the note."""
from django.db import migrations


def tidy(apps, schema_editor):
    from apps.deals.engine import clean_facts
    Deal = apps.get_model('deals', 'Deal')
    for d in Deal.objects.exclude(facts=[]):
        if isinstance(d.facts, list) and d.facts:
            d.facts = clean_facts(d.facts)
            d.save(update_fields=['facts'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0007_guess_roles')]
    operations = [migrations.RunPython(tidy, migrations.RunPython.noop)]
