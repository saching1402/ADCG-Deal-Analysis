"""Deal lead (22-Nov-26): the fund track record is compared with its OWN vintage-year quartiles for the right peer group
(e.g. Europe buyout) — the manager's benchmark first, else published thresholds found on the web; the app places each
fund and checks the manager's claims. Updates the criterion guidance in the main Fund framework and personal copies."""
from django.db import migrations

CRIT = 'Net IRR / TVPI vs vintage quartile'
NOTE = 'Track record compared with vintage-year quartiles for the peer group; the app places each fund (deal lead).'


def _update(cfg):
    from apps.deals.framework.defaults import QUARTILE_GUIDE
    cfg = dict(cfg or {})
    changed = False
    secs = []
    for s in cfg.get('sections') or []:
        crits = []
        for c in s.get('criteria') or []:
            if c.get('name') == CRIT and c.get('guidance') != QUARTILE_GUIDE:
                c = {**c, 'guidance': QUARTILE_GUIDE}; changed = True
            crits.append(c)
        secs.append({**s, 'criteria': crits})
    cfg['sections'] = secs
    return cfg, changed


def forward(apps, schema_editor):
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    Personal = apps.get_model('deals', 'PersonalFramework')
    for fw in Framework.objects.filter(key='fund'):
        cfg, changed = _update(fw.config)
        if changed:
            fw.config = cfg
            fw.version += 1
            fw.save()
            Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                                   config=fw.config, guidance=fw.guidance, note=NOTE)
    for pf in Personal.objects.filter(key='fund'):
        cfg, changed = _update(pf.config)
        if changed:
            pf.config = cfg
            pf.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0025_fund_manager_track')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
