"""Deal lead (Nov-26): GP tier members become real firms {name, domain, aliases} — shown with their logos and matched on
the firm's website, not on words in its name. Loads the verified Tier 1 / Tier 2 buyout sponsors into the ADCG GP tiers
and converts the Venture Growth tier members (main framework and personal copies)."""
from django.db import migrations

NOTE = {'gps': 'Loaded the deal lead’s verified Tier 1 (19) and Tier 2 (47) buyout sponsors — firms with websites + logos, matched by website.',
        'vg': 'GP tier members are now firms with websites + logos; matched by website, not by words in the name.'}


def forward(apps, schema_editor):
    from apps.deals.framework.gp_entities import entity_tiers, load_sponsor_lists
    conv = {'gps': load_sponsor_lists, 'vg': entity_tiers}
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    for fw in Framework.objects.filter(key__in=list(conv)):
        new = conv[fw.key](fw.config)
        if new == fw.config:
            continue
        fw.config = new
        fw.version += 1
        fw.save()
        Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                               config=fw.config, guidance=fw.guidance, note=NOTE[fw.key])
    for pf in apps.get_model('deals', 'PersonalFramework').objects.filter(key__in=list(conv)):
        new = conv[pf.key](pf.config)
        if new != pf.config:
            pf.config = new
            pf.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0020_gp_tier_criteria')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
