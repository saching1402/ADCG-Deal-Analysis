"""Deal lead (Nov-26): Business Quality in ADCG Buyout and ADCG CV adds Competitive intensity & pricing pressure,
Disruption risk, and Moat & barriers to entry — as a new framework version."""
from django.db import migrations

NOTE = 'Business Quality: added Competitive intensity & pricing pressure, Disruption risk, Moat & barriers to entry (deal lead).'


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import add_competition
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    for fw in Framework.objects.filter(key__in=['buyout', 'cv']):
        new = add_competition(fw.config)
        if new == fw.config:
            continue
        fw.config = new
        fw.version += 1
        fw.save()
        Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                               config=fw.config, guidance=fw.guidance, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [('deals', '0013_alignment_trim')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
