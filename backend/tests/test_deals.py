import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.deals import engine
from apps.deals.extract import prepare
from apps.deals.models import Deal
from apps.deals.scoring import score
from apps.users.models import User

BUYOUT = {
    'deal': {'name': 'TestCo', 'recommendation': 'Proceed — conditional', 'facts': [{'k': 'EV', 'v': '€1bn'}]},
    'sector': 'Industrials', 'sub_sector': 'TIC', 'verdict_note': '2 gates', 'calibration': 'near Apave',
    'sections': [{'name': n, 'weight': w, 'criteria': [{'name': f'{n} {i}', 'score': 6 + (i % 2), 'rationale': 'r'} for i in range(5)]}
                 for n, w in [('Sector Focus', 15), ('Trophy Asset', 20), ('Business Quality', 25), ('Valuation & Leverage', 25), ('Alignment', 15)]],
    'key_risks': [{'criterion': 'Leverage', 'severity': 'HIGH', 'why': 'x'}],
}
VG = {
    'deal': {'name': 'VCo', 'recommendation': 'Wait', 'facts': []}, 'sub_sector': 'Theme: AI infra',
    'valuation_evolution': {'val_from': 1, 'val_to': 7, 'metric': 'ARR', 'metric_from': 0.1, 'metric_to': 0.3, 'months': 6},
    'investors': [{'name': 'Thrive Capital', 'tier': 'T1', 'role': 'lead'}, {'name': 'Accel', 'tier': 'T1'}],
    'sections': [{'name': n, 'weight': 1, 'criteria': ([{'name': 'Marquee GP depth', 'auto': 'marquee', 'rationale': ''}] if n == 'Investor Syndicate' else [])
                  + [{'name': f'{n} {i}', 'score': 5, 'rationale': 'r'} for i in range(4 if n == 'Investor Syndicate' else 5)]}
                 for n in ['Theme', 'Valuation & Evolution', 'Investor Syndicate', 'Company & Management', 'Competition', 'Venture Fundamentals']],
    'risk_register': [{'name': 'Valuation', 'weight': 15, 'severity': 9, 'rationale': 'r'}, {'name': 'Tech', 'weight': 12, 'severity': 7, 'rationale': 'r'}],
}


def test_buyout_score():
    s, frag, clean = score(BUYOUT, 'buyout')
    assert 6 < s['overall'] < 7 and s['risk'] == round((10 - s['overall']) * 10)
    assert 'scorecard' in frag and clean['sections'][0]['score'] > 0


def test_vg_score_fixed_weights_marquee_vjr():
    s, frag, clean = score(VG, 'vg')
    assert [x['weight'] for x in clean['sections']] == [25, 25, 25, 10, 10, 5]
    assert s['marquee_pts'] == 4.5 and s['marquee_score'] == 3.7
    assert s['vjr'] == pytest.approx(2.33, 0.01)
    assert s['risk'] == round((15 * 9 + 12 * 7) / 27 * 10)
    assert 'Marquee GP Index' in frag


def test_extract_formats():
    import docx, openpyxl
    d = docx.Document(); d.add_paragraph('Revenue 2025: €120m'); b = io.BytesIO(); d.save(b)
    p = prepare('cim.docx', b.getvalue()); assert p.method == 'text' and '€120m' in p.blocks[0][0]['text']
    wb = openpyxl.Workbook(); wb.active.append(['EBITDA', 42]); b = io.BytesIO(); wb.save(b)
    p = prepare('model.xlsx', b.getvalue()); assert 'EBITDA | 42' in p.blocks[0][0]['text']
    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(200, 200); b = io.BytesIO(); w.write(b)
    p = prepare('teaser.pdf', b.getvalue()); assert p.method == 'native-pdf' and p.pages == 1
    p = prepare('huge.txt', b'x' * 400_000); assert len(p.blocks) == 3


@pytest.fixture
def client(db, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.ANTHROPIC_API_KEY = 'test'
    settings.DIGEST_CONCURRENCY = 1
    u = User.objects.create_user('a@b.com', 'pw-long-enough-1', role='analyst')
    c = APIClient(); c.force_authenticate(u)
    return c


def fake_ask(job, *, model, system, content, max_tokens, searches=0, label=''):
    if label.startswith('digest'):
        return '## Financials\nRevenue €120m [p. 3] (MGMT)'
    if label == 'research':
        return 'Dossier with https://example.com/a\n```json\n' + json.dumps({
            'track': 'buyout', 'sector': 'Industrials', 'sub_sector': 'TIC', 'one_liner': 'Test inspector',
            'ev': '€1bn', 'multiple': '12x', 'leverage': '3x', 'sponsor': 'PAI',
            'facts': [{'k': 'EV', 'v': '€1bn'}], 'sources': ['https://example.com/b']}) + '\n```'
    if label == 'score':
        return '```json\n' + json.dumps(BUYOUT) + '\n```'
    if label == 'memo part 1':
        return '```html\n<h2>1 · Company overview</h2><p>x</p>\n```'
    return '```html\n<h2>7 · Verdict</h2>\n```'


def test_full_pipeline(client, monkeypatch):
    monkeypatch.setattr(engine, 'ask', fake_ask)
    r = client.post('/api/v1/deals/', {'name': 'TestCo', 'track': 'auto'}, format='json')
    assert r.status_code == 201
    did = r.data['id']
    for n in range(3):
        f = SimpleUploadedFile(f'doc{n}.txt', f'content {n}'.encode(), content_type='text/plain')
        assert client.post(f'/api/v1/deals/{did}/files/', {'file': f}, format='multipart').status_code == 201
    dup = SimpleUploadedFile('copy.txt', b'content 0')
    assert client.post(f'/api/v1/deals/{did}/files/', {'file': dup}, format='multipart').status_code == 200
    bad = SimpleUploadedFile('x.exe', b'MZ')
    assert client.post(f'/api/v1/deals/{did}/files/', {'file': bad}, format='multipart').status_code == 400
    assert client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json').status_code == 202
    assert client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json').status_code == 409
    job = engine.claim_next()
    engine.run_job(job)
    job.refresh_from_db()
    assert job.status == 'done', job.error
    d = client.get(f'/api/v1/deals/{did}/').data
    assert d['status'] == 'done' and d['stage'] == 'analyzed' and d['track_resolved'] == 'buyout'
    assert all(f['status'] == 'digested' for f in d['files'])
    assert d['adcg_score'] and 'https://example.com/a' in d['sources']
    memo = client.get(f'/api/v1/deals/{did}/memo/').data['html']
    assert '1 · Company overview' in memo and 'Appendix — Prior Deals' in memo and '{{' not in memo
    lst = client.get('/api/v1/deals/').data
    assert lst['deals'][0]['file_count'] == 3
    assert client.patch(f'/api/v1/deals/{did}/', {'stage': 'pre_ic'}, format='json').data['stage'] == 'pre_ic'
    assert client.delete(f'/api/v1/deals/{did}/').status_code == 204
    assert not Deal.objects.filter(pk=did).exists()


def test_suggest(client, monkeypatch):
    from apps.deals import suggest
    monkeypatch.setattr(suggest, 'external', lambda q: [{'name': 'Apave', 'domain': 'apave.com'}, {'name': 'APA Corp', 'domain': 'apacorp.com'}])
    Deal.objects.create(name='Apave', website='apave.com')
    r = client.get('/api/v1/deals/suggest/?q=apa').data
    assert [p['name'] for p in r['pipeline']] == ['Apave']
    assert [c['domain'] for c in r['companies']] == ['apacorp.com']  # already-in-pipeline domain removed
    assert client.get('/api/v1/deals/suggest/?q=a').data == {'pipeline': [], 'companies': []}
