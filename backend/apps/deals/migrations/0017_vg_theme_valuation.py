"""Deal lead (Nov-26): ADCG Venture Growth — Theme = themes we must not miss (early signals, technology step-change,
TAM & revenue momentum, crowding & timing, value capture, durability); Valuation & Evolution adds a quality-adjusted
(margins & moat) multiple and round-by-round evolution; the VJR uses gross profit when margins are known. Live weights kept."""
from django.db import migrations

NOTE = ('Theme and Valuation & Evolution redefined (early signals, step-change, TAM momentum, crowding; quality-adjusted '
        'multiple, VJR on gross profit, evolution across rounds) — deal lead. Weights unchanged.')


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import redefine_vg
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    fw = Framework.objects.filter(key='vg').first()
    if not fw:
        return
    new = redefine_vg(fw.config)
    if new == fw.config:
        return
    fw.config = new
    fw.version += 1
    fw.save()
    Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                           config=fw.config, guidance=fw.guidance, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [('deals', '0016_cv_trophy_asset')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
