import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.deals.models import Deal
from apps.users.models import User

PW = 'Shared-Starter-2026'


@pytest.fixture(autouse=True)
def no_throttle_carryover():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def team(db, monkeypatch):
    monkeypatch.setenv('DJANGO_SUPERUSER_EMAIL', 'owner@x.com')
    monkeypatch.setenv('DJANGO_SUPERUSER_PASSWORD', PW)
    User.objects.create_superuser(email='owner@x.com', password=PW, full_name='Admin')
    call_command('seed_team')


def login(who, pw=PW):
    c = APIClient()
    r = c.post('/api/v1/auth/token/', {'email': who, 'password': pw}, format='json')
    if r.status_code == 200:
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {r.data["access"]}')
    return c, r


def test_team_seeded_and_login_by_username(team):
    assert set(User.objects.values_list('username', flat=True)) == {'sachin', 'ali', 'ray', 'lyees', 'admin'}
    assert User.objects.get(username='admin').role == 'admin'
    assert User.objects.get(username='sachin').full_name == 'Sachin'
    call_command('seed_team')                                  # idempotent, never resets
    assert User.objects.count() == 5
    c, r = login('Ali')
    assert r.status_code == 200
    me = c.get('/api/v1/users/me/').data
    assert me['username'] == 'ali' and me['starter_password'] is True
    assert login('owner@x.com')[1].status_code == 200
    assert login('ray', 'wrong-password')[1].status_code == 401
    assert AuditEvent.objects.filter(action='auth.login_failed', target='ray').exists()
    assert AuditEvent.objects.filter(action='auth.login', actor__username='ali').exists()


def test_change_password_and_profile(team):
    c, _ = login('lyees')
    assert c.post('/api/v1/users/me/password/', {'current_password': 'nope', 'new_password': 'x'}, format='json').status_code == 400
    assert c.post('/api/v1/users/me/password/', {'current_password': PW, 'new_password': 'Lyees-own-pass-77'}, format='json').status_code == 200
    assert login('lyees')[1].status_code == 401
    c2, r = login('lyees', 'Lyees-own-pass-77')
    assert r.status_code == 200 and c2.get('/api/v1/users/me/').data['starter_password'] is False
    assert c2.patch('/api/v1/users/me/', {'full_name': 'Lyees K', 'email': 'lyees@adcg.ae'}, format='json').status_code == 200
    assert login('lyees@adcg.ae', 'Lyees-own-pass-77')[1].status_code == 200
    ev = AuditEvent.objects.filter(action='account.password').first()
    assert ev and ev.actor.username == 'lyees' and '••••' not in str(ev.changes) and PW not in str(ev.changes)


def test_admin_manages_users(team):
    a, _ = login('admin')
    r = a.post('/api/v1/users/', {'username': 'new.person', 'full_name': 'New', 'password': 'Another-pass-123'}, format='json')
    assert r.status_code == 201
    uid = r.data['id']
    assert a.patch(f'/api/v1/users/{uid}/', {'is_active': False}, format='json').status_code == 200
    assert login('new.person', 'Another-pass-123')[1].status_code == 401
    c, _ = login('ray')
    assert c.post('/api/v1/users/', {'username': 'x', 'password': 'Another-pass-123'}, format='json').status_code == 403
    assert a.post(f'/api/v1/users/{uid}/reset-password/', {'password': 'Reset-pass-4567'}, format='json').status_code == 200
    assert AuditEvent.objects.filter(action='user.reset_password').exists()


def test_every_change_is_logged(team, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    c, _ = login('ray')
    r = c.post('/api/v1/deals/', {'name': 'Logged Co', 'sector': 'Software'}, format='json')
    did = r.data['id']
    c.patch(f'/api/v1/deals/{did}/', {'sector': 'Vertical SaaS', 'stage': 'internal'}, format='json')
    from django.core.files.uploadedfile import SimpleUploadedFile
    up = c.post(f'/api/v1/deals/{did}/files/', {'file': SimpleUploadedFile('cim.txt', b'Revenue $120m EBITDA $30m ' * 40)}, format='multipart')
    assert up.status_code in (200, 201)
    fid = up.data['id']
    c.get(f'/api/v1/deals/{did}/files/{fid}/')
    c.delete(f'/api/v1/deals/{did}/files/{fid}/')
    c.delete(f'/api/v1/deals/{did}/')
    acts = list(AuditEvent.objects.filter(deal_id=did).order_by('at', 'id').values_list('action', flat=True))
    assert acts == ['deal.create', 'deal.update', 'file.upload', 'file.download', 'file.delete', 'deal.delete']
    upd = AuditEvent.objects.get(action='deal.update')
    assert upd.changes['sector'] == ['Software', 'Vertical SaaS'] and upd.actor.username == 'ray' and upd.deal_name == 'Logged Co'
    assert not Deal.objects.filter(pk=did).exists()
    feed = c.get(f'/api/v1/audit/?deal={did}').data['events']
    assert len(feed) == 6 and feed[0]['action'] == 'deal.delete' and feed[0]['actor'] == 'Ray'
    csv = c.get('/api/v1/audit/?export=csv')
    assert csv.status_code == 200 and b'Logged Co' in csv.content
