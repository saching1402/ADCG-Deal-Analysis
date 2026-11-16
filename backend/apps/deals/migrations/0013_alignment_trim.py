"""Deal lead (Nov-26): drop Mark credibility and Minority protections / information rights from Alignment in every
framework (ADCG Buyout and ADCG CV have them; Venture Growth never did), as a new framework version."""
from django.db import migrations

NOTE = 'Removed Mark credibility and Minority protections / information rights from Alignment (deal lead).'


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import drop_alignment_extras
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    for fw in Framework.objects.all():
        new = drop_alignment_extras(fw.config)
        if new == fw.config:
            continue
        fw.config = new
        fw.version += 1
        fw.save()
        Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                               config=fw.config, guidance=fw.guidance, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [('deals', '0012_three_frameworks')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
