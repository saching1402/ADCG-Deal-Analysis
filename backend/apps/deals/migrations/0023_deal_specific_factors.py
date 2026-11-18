"""Deal lead (18-Nov-26): every framework keeps its sections in their usual proportions but scales them to 90%; the other
10% is scored on 2–4 factors picked for each deal's sub-sector (e.g. pharma: patent cliff; software: net revenue
retention). Adds `deal_specific` to the main frameworks and to personal copies."""
from django.db import migrations

NOTE = 'Deal-specific factors: framework sections share 90%; 10% on 2–4 factors picked for each deal (deal lead).'


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import DEAL_SPECIFIC
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    Personal = apps.get_model('deals', 'PersonalFramework')
    for fw in Framework.objects.filter(key__in=['buyout', 'cv', 'vg']):
        if 'deal_specific' in (fw.config or {}):
            continue
        fw.config = {**fw.config, 'deal_specific': dict(DEAL_SPECIFIC)}
        fw.version += 1
        fw.save()
        Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                               config=fw.config, guidance=fw.guidance, note=NOTE)
    for pf in Personal.objects.filter(key__in=['buyout', 'cv', 'vg']):
        if 'deal_specific' not in (pf.config or {}):
            pf.config = {**pf.config, 'deal_specific': dict(DEAL_SPECIFIC)}
            pf.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0022_secondary_tiers')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
