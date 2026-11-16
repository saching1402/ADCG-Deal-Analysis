"""Three frameworks (Nov-26): the original ADCG Buyout framework becomes ADCG CV (content + history copied), and
ADCG Buyout is rebuilt from it with Sponsor Quality in place of Trophy Asset. Adds the 'cv' track."""
from django.db import migrations, models

NOTE = ('ADCG Buyout rebuilt from the original framework (now "ADCG CV"): Trophy Asset → Sponsor Quality; '
        'Sponsor track record moved out of Alignment. Weights to be set by the deal lead.')


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import buyout_from_cv
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    old = Framework.objects.filter(pk='buyout').first()
    if not old or Framework.objects.filter(pk='cv').exists():
        return  # fresh install: seed_frameworks creates all three from the defaults
    cv = Framework.objects.create(key='cv', name='ADCG CV',
                                  description='Continuation vehicles and GP-led secondaries (single- and multi-asset).',
                                  config=old.config, guidance=old.guidance, version=old.version, updated_by=old.updated_by)
    for v in Version.objects.filter(framework=old):
        Version.objects.create(framework=cv, version=v.version, name='ADCG CV', description=cv.description,
                               config=v.config, guidance=v.guidance, note=v.note, created_by=v.created_by)
    Version.objects.filter(framework=cv, version=cv.version).update(
        note=('Renamed from ADCG Buyout. ' + (Version.objects.get(framework=cv, version=cv.version).note or ''))[:500])
    old.config = buyout_from_cv(old.config)
    old.name = 'ADCG Buyout'
    old.description = 'Buyouts and co-investments alongside a sponsor.'
    old.version += 1
    old.save()
    Version.objects.create(framework=old, version=old.version, name=old.name, description=old.description,
                           config=old.config, guidance=old.guidance, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [('deals', '0011_memo_comments')]
    operations = [
        migrations.AlterField('deal', 'track', models.CharField(
            choices=[('auto', 'Auto-detect'), ('buyout', 'Buyout / co-invest'), ('cv', 'CV / GP-led secondary'), ('vg', 'Venture / Growth')],
            default='auto', max_length=10)),
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
