"""Deal lead (Nov-26): GP tiers — AlleyCorp → Tier 1; 8VC, Factorial Funds, True Ventures, SOSV, Monolith → Tier 2."""
from django.db import migrations

NOTE = 'GP tiers: AlleyCorp → T1; 8VC, Factorial Funds, True Ventures, SOSV, Monolith → T2 (deal lead).'


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import move_tiers
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    fw = Framework.objects.filter(key='vg').first()
    if not fw:
        return
    new = move_tiers(fw.config)
    if new == fw.config:
        return
    fw.config = new
    fw.version += 1
    fw.save()
    Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                           config=fw.config, guidance=fw.guidance, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [('deals', '0018_vg_syndicate_management')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
