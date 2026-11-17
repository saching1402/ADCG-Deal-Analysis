"""Deal lead (Nov-26): lead secondaries investors for CVs — verified P1 (8) and P2 (10) firms with websites + logos."""
from django.db import migrations

NOTE = 'Loaded the deal lead’s verified lead secondaries investors: P1 (8) and P2 (10).'


def forward(apps, schema_editor):
    from apps.deals.framework.gp_entities import load_secondary_lists
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    for fw in Framework.objects.filter(key='gps'):
        new = load_secondary_lists(fw.config)
        if new != fw.config:
            fw.config = new
            fw.version += 1
            fw.save()
            Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                                   config=fw.config, guidance=fw.guidance, note=NOTE)
    for pf in apps.get_model('deals', 'PersonalFramework').objects.filter(key='gps'):
        new = load_secondary_lists(pf.config)
        if new != pf.config:
            pf.config = new
            pf.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0021_gp_entities')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
