"""Deal lead (Nov-26): shared ADCG GP tiers for Buyout and CV. Buyout: 'Sponsor tier' under Sponsor Quality. CV: dual
manager check under Alignment — underlying sponsor tier + lead secondaries investor tier. Both scored from the list."""
from django.db import migrations

NOTE = {'buyout': 'Sponsor Quality: added Sponsor tier (scored from the ADCG GP tiers) — deal lead.',
        'cv': 'Alignment: added the dual manager check — underlying sponsor tier + lead secondaries investor tier (scored from the ADCG lists) — deal lead.'}


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import add_gp_tier_criteria
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    for fw in Framework.objects.filter(key__in=['buyout', 'cv']):
        new = add_gp_tier_criteria(fw.key, fw.config)
        if new == fw.config:
            continue
        fw.config = new
        fw.version += 1
        fw.save()
        Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                               config=fw.config, guidance=fw.guidance, note=NOTE[fw.key])


class Migration(migrations.Migration):
    dependencies = [('deals', '0019_vg_tier_moves')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
