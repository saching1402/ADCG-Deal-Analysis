"""Main framework (admin) vs personal frameworks (everyone else) + change requests."""
import copy

import pytest
from django.core.management import call_command

from apps.deals import frameworks
from apps.deals.models import FrameworkProposal, PersonalFramework
from apps.users.models import User
from tests.test_accounts import PW, login, no_throttle_carryover  # noqa: F401


@pytest.fixture
def team(db, monkeypatch):
    monkeypatch.setenv('DJANGO_SUPERUSER_EMAIL', 'owner@x.com')
    monkeypatch.setenv('DJANGO_SUPERUSER_PASSWORD', PW)
    User.objects.create_superuser(email='owner@x.com', password=PW, full_name='Admin')
    call_command('seed_team')


def bump(cfg, sec='Business Quality', w=5):
    c = copy.deepcopy(cfg)
    names = [s['name'] for s in c['sections']]
    i, j = names.index(sec), names.index('Sector Focus')
    c['sections'][i]['weight'] += w
    c['sections'][j]['weight'] -= w
    return c


def test_personal_copy_does_not_touch_main(team):
    ali, _ = login('ali')
    main_v = frameworks.main('buyout').version
    r = ali.get('/api/v1/frameworks/buyout/')
    assert r.data['scope'] == 'mine' and r.data['personal'] is False and r.data['can_edit']
    r = ali.put('/api/v1/frameworks/buyout/', {'config': bump(r.data['config']), 'guidance': r.data['guidance']}, format='json')
    assert r.status_code == 200 and r.data['personal'] and r.data['differs']
    assert frameworks.main('buyout').version == main_v                       # main untouched
    ray, _ = login('ray')
    assert ray.get('/api/v1/frameworks/buyout/').data['personal'] is False   # Ray still sees the main
    assert ali.put('/api/v1/frameworks/buyout/?scope=main', {'config': r.data['config']}, format='json').status_code == 403
    # an analysis started by Ali scores on Ali's copy; anyone else on the main
    ali_u = User.objects.get(username='ali')
    tok = frameworks.ACTIVE_USER.set(ali_u.pk)
    try:
        fw = frameworks.get('buyout')
        assert frameworks.source_of(fw) == 'ali' and fw.config == r.data['config']
    finally:
        frameworks.ACTIVE_USER.reset(tok)
    assert frameworks.source_of(frameworks.get('buyout')) == ''
    # reset → back on the main
    assert ali.post('/api/v1/frameworks/buyout/reset-mine/').data['personal'] is False
    assert not PersonalFramework.objects.filter(user=ali_u).exists()


def test_propose_and_admin_approves(team):
    ali, _ = login('ali')
    cfg = ali.get('/api/v1/frameworks/vg/').data['config']
    new = copy.deepcopy(cfg)
    new['sections'][1]['weight'] += 5
    new['sections'][0]['weight'] -= 5
    assert ali.put('/api/v1/frameworks/vg/', {'config': new}, format='json').status_code == 200
    assert ali.post('/api/v1/frameworks/vg/propose/', {'note': 'More weight on valuation'}, format='json').status_code == 201
    p = FrameworkProposal.objects.get()
    assert p.status == 'pending' and any('weight' in c for c in p.changes)
    # Ray can't approve; the admin can
    ray, _ = login('ray')
    assert ray.get('/api/v1/frameworks/proposals/').data['proposals'] == []
    assert ray.post(f'/api/v1/frameworks/proposals/{p.id}/', {'action': 'approve'}, format='json').status_code == 403
    adm, r = login('admin')
    assert r.status_code == 200
    lst = adm.get('/api/v1/frameworks/proposals/').data
    assert lst['is_admin'] and lst['proposals'][0]['user'] and lst['proposals'][0]['status'] == 'pending'
    v0 = frameworks.main('vg').version
    r = adm.post(f'/api/v1/frameworks/proposals/{p.id}/', {'action': 'approve', 'response': 'Agreed'}, format='json')
    assert r.status_code == 200 and r.data['status'] == 'approved' and r.data['applied_version'] == v0 + 1
    assert frameworks.main('vg').config['sections'][1]['weight'] == cfg['sections'][1]['weight'] + 5
    assert not PersonalFramework.objects.filter(key='vg').exists()          # Ali follows the main again
    assert 'Approved' in frameworks.main('vg').versions.first().note


def test_reject_and_viewer_read_only(team):
    lyes, _ = login('lyes')
    cfg = lyes.get('/api/v1/frameworks/cv/').data['config']
    lyes.put('/api/v1/frameworks/cv/', {'config': bump(cfg)}, format='json')
    pid = lyes.post('/api/v1/frameworks/cv/propose/', {}, format='json').data['id']
    adm, _ = login('admin')
    v0 = frameworks.main('cv').version
    assert adm.post(f'/api/v1/frameworks/proposals/{pid}/', {'action': 'reject', 'response': 'Not now'}, format='json').data['status'] == 'rejected'
    assert frameworks.main('cv').version == v0 and PersonalFramework.objects.filter(key='cv').exists()
    u = User.objects.get(username='ray'); u.role = 'viewer'; u.save()
    ray, _ = login('ray')
    assert ray.get('/api/v1/frameworks/cv/').data['can_edit'] is False
    assert ray.put('/api/v1/frameworks/cv/', {'config': cfg}, format='json').status_code == 403
