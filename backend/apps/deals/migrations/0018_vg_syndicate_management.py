"""Deal lead (Nov-26): ADCG Venture Growth — Investor Syndicate (tier-1 leads per round, insiders doubling down,
strategics, tier-1 concentration) and Company & Management (founder track record, pedigree & network, moat, customer
quality & scaling) redefined; weights Theme 25 · Valuation 15 · Syndicate 25 · Company & Management 20 · Competition 10 ·
Fundamentals 5."""
from django.db import migrations

NOTE = ('Weights: Theme 25 · Valuation & Evolution 15 · Investor Syndicate 25 · Company & Management 20 · Competition 10 · '
        'Venture Fundamentals 5. Syndicate and Company & Management criteria redefined (deal lead).')


def forward(apps, schema_editor):
    from apps.deals.framework.defaults import reweight_vg
    from apps.deals.frameworks import validate
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    fw = Framework.objects.filter(key='vg').first()
    if not fw:
        return
    new = reweight_vg(fw.config)
    if abs(sum(s['weight'] for s in new['sections']) - 100) > 0.01:
        return  # a section was renamed on the live site — leave it for the deal lead rather than save a broken framework
    if new == fw.config:
        return
    fw.config = validate('vg', new)
    fw.version += 1
    fw.save()
    Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                           config=fw.config, guidance=fw.guidance, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [('deals', '0017_vg_theme_valuation')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
