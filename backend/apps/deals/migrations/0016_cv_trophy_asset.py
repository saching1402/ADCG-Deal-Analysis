"""Deal lead (Nov-26): ADCG CV's Trophy Asset = the sponsor's star asset — a top performer in its fund that it keeps to
compound returns, not one moved into a CV because it could not find a buyer. New criteria, same weight; new main version."""
from django.db import migrations

NOTE = ('Trophy Asset redefined as the sponsor\'s star asset kept to compound (performance within the fund; kept by choice, '
        'not a failed sale; compounding runway; value creation so far; market position) — deal lead.')


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import redefine_trophy
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    fw = Framework.objects.filter(key='cv').first()
    if not fw:
        return
    new = redefine_trophy(fw.config)
    if new == fw.config:
        return
    fw.config = new
    fw.version += 1
    fw.save()
    Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                           config=fw.config, guidance=fw.guidance, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [('deals', '0015_personal_frameworks')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
