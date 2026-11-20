"""Deal lead (20-Nov-26): venture syndicates are judged on the CLUSTER of marquee names — one tier-1 manager is very good,
two are excellent; smaller or unlisted VCs alongside them never lower the score (Marquee GP Index floors + guidance).
Buyout / CV: up to two sponsors are each checked against the tiers (guidance). Updates the main frameworks and personal copies."""
from django.db import migrations

FLOORS = {'t1_one': 8.0, 't1_two': 9.0, 't1_three': 9.5, 'good_three': 8.0}
NOTE = 'Syndicate clusters: 1 tier-1 manager ≥ 8, 2 ≥ 9, 3+ ≥ 9.5, 3 good names ≥ 8; co-sponsors checked (deal lead).'


def _update(key, cfg):
    from apps.deals.framework.defaults import SPONSOR_TIER_CRIT, SYN_CRITERIA
    cfg = dict(cfg or {})
    changed = False
    if key == 'vg':
        m = dict(cfg.get('marquee') or {'base': 1.0, 'slope': 0.6})
        if 'floors' not in m:
            m['floors'] = dict(FLOORS); cfg['marquee'] = m; changed = True
        guide = {c['name']: c['guidance'] for c in SYN_CRITERIA}
    else:
        guide = {SPONSOR_TIER_CRIT['name']: SPONSOR_TIER_CRIT['guidance']}
    secs = []
    for s in cfg.get('sections') or []:
        crits = []
        for c in s.get('criteria') or []:
            g = guide.get(c.get('name'))
            if g and c.get('guidance') != g:
                c = {**c, 'guidance': g}; changed = True
            crits.append(c)
        secs.append({**s, 'criteria': crits})
    cfg['sections'] = secs
    return cfg, changed


def forward(apps, schema_editor):
    Framework = apps.get_model('deals', 'Framework')
    Version = apps.get_model('deals', 'FrameworkVersion')
    Personal = apps.get_model('deals', 'PersonalFramework')
    for fw in Framework.objects.filter(key__in=['buyout', 'cv', 'vg']):
        cfg, changed = _update(fw.key, fw.config)
        if changed:
            fw.config = cfg
            fw.version += 1
            fw.save()
            Version.objects.create(framework=fw, version=fw.version, name=fw.name, description=fw.description,
                                   config=fw.config, guidance=fw.guidance, note=NOTE)
    for pf in Personal.objects.filter(key__in=['buyout', 'cv', 'vg']):
        cfg, changed = _update(pf.key, pf.config)
        if changed:
            pf.config = cfg
            pf.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [('deals', '0023_deal_specific_factors')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
