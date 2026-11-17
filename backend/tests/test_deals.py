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
    assert 6 < s['overall'] < 7 and 'risk' not in s                  # ADCG does not score risk
    assert 'Risk Score' not in frag and 'risk score' not in frag.lower() and 'gauge' not in frag and '6 · ADCG scoring' in frag
    assert 'Criteria detail' not in frag and 'Contrarian' not in frag and 'class="bars"' in frag   # memo shows only the bars
    assert 'scorecard' in frag and clean['sections'][0]['score'] > 0


def test_vg_score_fixed_weights_marquee_vjr():
    s, frag, clean = score(VG, 'vg')
    assert [x['weight'] for x in clean['sections']] == [25, 25, 25, 10, 10, 5]
    assert s['marquee_pts'] == 4.5 and s['marquee_score'] == 3.7
    assert s['vjr'] == pytest.approx(2.33, 0.01)
    assert 'risk' not in s and 'Risk Score' not in frag and 'risk register' not in frag.lower()
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


def fake_ask(job, *, model, system, content, max_tokens, searches=0, label='', think=False):
    if label.startswith('digest'):
        return '## Financials\nRevenue €120m [p. 3] (MGMT); EBITDA €41.8m FY25. ' + 'Detail 2025. ' * 40
    if label == 'research':
        assert '<materials' not in json.dumps(content)        # independent: the data room is withheld
        return 'Dossier with https://example.com/a\n```json\n' + json.dumps({
            'track': 'buyout', 'sector': 'Industrials', 'sub_sector': 'TIC', 'sources': ['https://example.com/b']}) + '\n```'
    if label == 'integrate':
        assert '<materials' in json.dumps(content) and '<independent_research>' in json.dumps(content)
        return 'Actuals table from the IM.\n```json\n' + json.dumps({
            'one_liner': 'Test inspector', 'ev': '€1bn', 'multiple': '12x', 'leverage': '3x', 'sponsor': 'PAI',
            'risk_disclosure': [{'risk': 'Dental roll-ups have a poor PE record', 'in_cim': 'understated'}],
            'materials_risks': [{'risk': 'Customer concentration (top 3 = 40%)', 'severity': 'MEDIUM', 'in_cim': 'yes', 'source': 'IM'}],
            'reconciliation': [{'metric': 'Adj. EBITDA', 'cim': '41.8', 'other': '40.1 [QoE]'}],
            'facts': [{'k': 'EV / EBITDA', 'v': '12.7–13.5× Adj. / 15.2–16.1× reported (EST); 12.4× on 2026E', 'src': 'CIM p.83'},
                      {'k': 'Enterprise value', 'v': '$531m', 'src': 'CIM p.5'}]}) + '\n```'
    if label == 'risk':
        assert '<materials' not in json.dumps(content)
        return 'Bottom line: roll-up risk. https://example.com/risk\n```json\n' + json.dumps({
            'risks': [{'risk': 'Dental roll-ups have a poor PE record', 'in_cim': 'no', 'severity': 'HIGH', 'source': 'https://example.com/dso'}],
            'track_record': [{'deal': 'Western Dental', 'sponsor': 'X', 'outcome': 'Restructuring'}],
            'theme_verdict': 'Graveyard theme', 'reconciliation': [{'metric': 'Adj. EBITDA', 'cim': '41.8', 'other': '40.1 [QoE]'}]}) + '\n```'
    if label == 'score':
        return '```json\n' + json.dumps(BUYOUT) + '\n```'
    if label == 'memo part 1':
        return '```html\n<h2>1 · Company overview</h2><p>x</p>\n```'
    return '```html\n<h2>7 · Verdict</h2>\n```'


def test_full_pipeline(client, monkeypatch):
    monkeypatch.setattr(engine, 'ask', fake_ask)
    monkeypatch.setattr(engine, 'preflight', lambda: None)
    r = client.post('/api/v1/deals/', {'name': 'TestCo', 'track': 'auto'}, format='json')
    assert r.status_code == 201
    did = r.data['id']
    for n in range(3):
        f = SimpleUploadedFile(f'doc{n}.txt', (f'content {n} revenue 2025 ' * 10).encode(), content_type='text/plain')
        assert client.post(f'/api/v1/deals/{did}/files/', {'file': f}, format='multipart').status_code == 201
    dup = SimpleUploadedFile('copy.txt', ('content 0 revenue 2025 ' * 10).encode())
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
    assert d['adcg_score'] and 'https://example.com/a' in d['sources'] and 'https://example.com/dso' in d['sources']
    assert d['risk_items']['theme_verdict'] == 'Graveyard theme' and 'roll-up risk' in d['risk_review']
    assert [r['in_cim'] for r in d['risk_items']['risks']] == ['understated', 'yes']
    assert d['risk_items']['reconciliation'][0]['metric'] == 'Adj. EBITDA' and '# Data-room integration' in d['research']
    ev = next(f for f in d['facts'] if f['k'] == 'EV / EBITDA')
    assert ev['v'] == '12.7×' and '15.2' in ev['note'] and ev['src'] == 'CIM p.83'
    memo = client.get(f'/api/v1/deals/{did}/memo/').data['html']
    assert '1 · Company overview' in memo and 'Appendix — Prior Deals' not in memo and '{{' not in memo
    assert memo.index('1 · Company overview') < memo.index('6 · ADCG scoring')
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


def test_frameworks_edit_and_use(client):
    User.objects.filter(username='a@b.com').update(role='admin')            # the main framework is admin-edited
    client.force_authenticate(User.objects.get(username='a@b.com'))
    from apps.deals import frameworks, prompts
    r = client.get('/api/v1/frameworks/').data
    assert [f['key'] for f in r['frameworks']] == ['buyout', 'cv', 'vg'] and r['frameworks'][2]['version'] == 1
    vg = client.get('/api/v1/frameworks/vg/').data
    cfg = vg['config']
    assert [s['weight'] for s in cfg['sections']] == [25, 15, 25, 20, 10, 5]
    # bad weights rejected
    bad = json.loads(json.dumps(cfg)); bad['sections'][0]['weight'] = 30
    assert client.put('/api/v1/frameworks/vg/', {'config': bad}, format='json').status_code == 400
    # edit: move 5 points Theme → Competition, rename a criterion, add a T1 member, change slope
    cfg['sections'][0]['weight'] = 20; cfg['sections'][4]['weight'] = 15
    cfg['sections'][4]['criteria'][0]['name'] = 'Funded rival density'
    cfg['tiers'][0]['members'].append('Accel Growth')
    cfg['marquee']['slope'] = 1.0
    r = client.put('/api/v1/frameworks/vg/', {'config': cfg, 'note': 'test', 'base_version': 1}, format='json')
    assert r.status_code == 200 and r.data['version'] == 2
    assert client.put('/api/v1/frameworks/vg/', {'config': cfg, 'base_version': 1}, format='json').status_code == 409
    text = prompts.framework('vg')
    assert 'Funded rival density' in text and 'Competition — weight 15' in text
    s, _, clean = score(VG, 'vg', frameworks.get('vg').config)
    assert [x['weight'] for x in clean['sections']] == [20, 15, 25, 20, 15, 5]
    assert s['marquee_score'] == 5.5  # 4.5 pts × slope 1.0 + 1
    hist = client.get('/api/v1/frameworks/vg/history/').data['versions']
    assert [h['version'] for h in hist] == [2, 1]
    assert client.post('/api/v1/frameworks/vg/restore/', {'version': 1}, format='json').data['version'] == 3
    assert frameworks.get('vg').config['marquee']['slope'] == 0.6
    assert client.post('/api/v1/frameworks/buyout/restore/', {'reset': True}, format='json').data['version'] == 2


def test_preflight_bad_key(settings):
    settings.ANTHROPIC_API_KEY = 'sachin-ganeshan-api-key'
    with pytest.raises(engine.AnalysisError, match='sk-ant-'):
        engine.preflight()


def test_usage_meters_and_free_space(client):
    from apps.deals.models import AnalysisJob, DealFile
    d = Deal.objects.create(name='Done Co', stage='approved', status='done')
    for i in range(2):
        f = SimpleUploadedFile(f'f{i}.txt', b'Revenue 2025 grew. ' * 50)
        DealFile.objects.create(deal=d, file=f, name=f'f{i}.txt', size=600 * 1024 * 1024, status='digested', digest='fact sheet 2025 ' * 30)
    AnalysisJob.objects.create(deal=d, status='done', model='claude-sonnet-5-5', cost=4.0)
    AnalysisJob.objects.create(deal=d, status='done', model='claude-opus-5-5', cost=9.0)
    client.patch('/api/v1/usage/', {'storage_capacity_gb': 1.2}, format='json')
    u = client.get('/api/v1/usage/').data
    s, m = u['storage'], u['model']
    assert s['files'] == 2 and s['level'] == 'critical' and s['reclaimable'] == 1200 * 1024 * 1024
    assert m['month_cost'] == 13.0 and m['remaining'] is None and m['level'] == 'unknown'
    titles = ' '.join(x['title'] for x in u['suggestions'])
    assert 'Free 1.2 GB' in titles and 'almost full' in titles
    r = client.post('/api/v1/usage/', {}, format='json').data
    assert r['files'] == 2
    u = client.get('/api/v1/usage/').data
    assert u['storage']['files'] == 0 and u['storage']['archived_files'] == 2
    f = DealFile.objects.first()
    assert f.digest and f.archived_at
    assert client.get(f'/api/v1/deals/{d.id}/files/{f.id}/').status_code == 410



def test_credit_meter_is_user_controlled(client):
    from apps.deals.models import AnalysisJob
    d = Deal.objects.create(name='Credit Co')
    u = client.get('/api/v1/usage/').data
    assert u['model']['balance'] is None and 'Enter your Claude credit balance' in u['suggestions'][0]['title']
    # deal lead types the Console balance; app then counts down
    client.patch('/api/v1/usage/', {'console_balance': 26.49}, format='json')
    AnalysisJob.objects.create(deal=d, status='done', model='claude-sonnet-5-5', cost=4.0)
    m = client.get('/api/v1/usage/').data['model']
    assert m['remaining'] == 22.49 and m['spent_since'] == 4.0 and m['runs_left'] == 5
    # top-up adds to the estimate
    m = client.patch('/api/v1/usage/', {'topup': 50}, format='json').data['model']
    assert m['remaining'] == 72.49 and m['events'][0]['kind'] == 'topup'
    # stop level pauses NEW analyses only; blank turns it off
    client.patch('/api/v1/usage/', {'stop_below': 80}, format='json')
    f = SimpleUploadedFile('a.txt', b'Revenue 2025 grew strongly. ' * 20)
    client.post(f'/api/v1/deals/{d.id}/files/', {'file': f}, format='multipart')
    r = client.post(f'/api/v1/deals/{d.id}/analyze/', {}, format='json')
    assert r.status_code == 409 and r.data['code'] == 'credit_paused'
    assert client.post(f'/api/v1/deals/{d.id}/analyze/', {'override_credit': True}, format='json').status_code == 202
    client.patch('/api/v1/usage/', {'stop_below': ''}, format='json')
    assert client.get('/api/v1/usage/').data['settings']['stop_below'] is None
    # re-sync with the Console logs the drift between estimate and reality
    m = client.patch('/api/v1/usage/', {'console_balance': 70}, format='json').data['model']
    assert m['remaining'] == 70 and m['events'][0]['estimate'] == 72.49


def test_doc_roles():
    from apps.deals.roles import guess_role
    assert guess_role('1.1.1_Project BLADE - Confidential Information Presentation.pdf') == 'cim'
    assert guess_role('2.2.1_Project Blade - Financial Due Diligence Report.pdf') == 'qoe'
    assert guess_role('2.3.1_Project Blade - Market Study.pdf') == 'market'
    assert guess_role('1.2.1_Project Blade - Net Returns Model.xlsx') == 'model'
    assert guess_role('1.6.1_Project Blade - Transaction Structure.pdf') == 'structure'
    assert guess_role('26-07_Project_Blade_Co-investor Memo_vff.pdf') == 'sponsor_memo'


def test_memo_versions(client, monkeypatch):
    monkeypatch.setattr(engine, 'ask', fake_ask)
    monkeypatch.setattr(engine, 'preflight', lambda: None)
    did = client.post('/api/v1/deals/', {'name': 'Versioned Co'}, format='json').data['id']
    client.post(f'/api/v1/deals/{did}/files/', {'file': SimpleUploadedFile('cim.txt', b'Revenue 2025 120m. ' * 20)}, format='multipart')
    for _ in range(2):
        client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json')
        engine.run_job(engine.claim_next())
    r = client.get(f'/api/v1/deals/{did}/memo/').data
    assert len(r['versions']) == 2 and r['version']['is_latest'] and r['version']['number'] == 2
    old = r['versions'][1]
    r2 = client.get(f'/api/v1/deals/{did}/memo/?version={old["id"]}').data
    assert r2['version']['number'] == 1 and not r2['version']['is_latest']
    assert client.get(f'/api/v1/deals/{did}/').data['memo_count'] == 2


def test_ask_continues_cut_off_replies(settings, db, monkeypatch):
    """A reply that hits max_tokens is continued, not truncated; an empty one is retried with more room."""
    import types
    import anthropic
    settings.ANTHROPIC_API_KEY = 'sk-ant-test'
    d = Deal.objects.create(name='Ask Co')
    job = engine.queue(d)
    script = [('', 'max_tokens'), ('Part one of the fact sheet ', 'max_tokens'), ('and part two. Done.', 'end_turn')]
    seen = []

    class Stream:
        def __init__(self, kw):
            seen.append(kw)
            self.text, self.stop = script.pop(0)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get_final_message(self):
            u = types.SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0, server_tool_use=None)
            blocks = [types.SimpleNamespace(type='text', text=self.text)] if self.text else []
            return types.SimpleNamespace(content=blocks, stop_reason=self.stop, usage=u)

    class Client:
        def __init__(self, **kw):
            self.messages = types.SimpleNamespace(stream=lambda **kw: Stream(kw))
    monkeypatch.setattr(anthropic, 'Anthropic', Client)
    out = engine.ask(job, model='claude-haiku-5-5', system='s', content=[{'type': 'text', 'text': 'x'}], max_tokens=1000, label='digest t')
    assert out == 'Part one of the fact sheet and part two. Done.'
    assert seen[1]['max_tokens'] == 2000                       # empty reply → retried with more room
    assert seen[2]['messages'][-1]['content'] == engine.CONTINUE  # cut-off reply → continued
    assert seen[0]['thinking'] == {'type': 'disabled'}            # reading runs without thinking on Haiku 5.5


def test_thinking_options():
    assert engine.thinking_opts('claude-haiku-5-5', 12000, False) == ({'thinking': {'type': 'disabled'}}, 12000)
    assert engine.thinking_opts('claude-sonnet-5-5', 20000, False) == ({'thinking': {'type': 'between_tools'}}, 20000)
    extra, mt = engine.thinking_opts('claude-sonnet-5-5', 32000, True)
    assert 'thinking' not in extra and mt == 48000                # reasoning stages keep thinking + extra room
    extra, mt = engine.thinking_opts('claude-opus-5-5', 12000, False)
    assert extra == {'output_config': {'effort': 'low'}} and mt == 28000   # Opus can't switch thinking off


def test_run_without_data_room(client, monkeypatch):
    """Venture deals often have no VDR: name only → web-only analysis, no file reading, facts from public research."""
    seen = []

    def ask(job, **kw):
        seen.append(kw['label'])
        if kw['label'] == 'integrate':
            assert 'Data room: NONE' in json.dumps(kw['content'])
            return 'Needs audited revenue.\n```json\n' + json.dumps({'one_liner': 'Edge AI DCs', 'ev': '$2.2bn',
                   'facts': [{'k': 'Post-money', 'v': '$2.21bn', 'src': 'Press'}]}) + '\n```'
        return fake_ask(job, **kw)
    monkeypatch.setattr(engine, 'ask', ask)
    monkeypatch.setattr(engine, 'preflight', lambda: None)
    did = client.post('/api/v1/deals/', {'name': 'Armada', 'website': 'armada.ai', 'track': 'vg'}, format='json').data['id']
    assert client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json').status_code == 202
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert job.status == 'done', job.error
    assert not any(x.startswith('digest') for x in seen) and 'integrate' in seen
    d = client.get(f'/api/v1/deals/{did}/').data
    assert d['facts'][0]['v'] == '$2.21bn' and 'No data-room access' in d['research']
    assert all(r['in_cim'] == 'n/a' for r in d['risk_items']['risks'])


def test_comments_and_revise_only_run(client, monkeypatch):
    """Comments made while reading → a cheap revise run: re-score + rewrite only affected sections, no research."""
    from apps.deals.models import MemoComment, MemoVersion
    monkeypatch.setattr(engine, 'preflight', lambda: None)
    monkeypatch.setattr(engine, 'ask', lambda job, **kw: ('ok\n```json\n{"facts": []}\n```' if kw['label'] == 'integrate'
                                                         else fake_ask(job, **kw)))
    did = client.post('/api/v1/deals/', {'name': 'Rev Co', 'track': 'buyout'}, format='json').data['id']
    client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json')
    job = engine.claim_next(); engine.run_job(job)
    d = Deal.objects.get(pk=did)
    d.memo_html = d.memo_html.replace('<footer', '<h2>4 · The transaction &amp; key findings</h2><p>Old findings.</p>'
                                     '<h2>7 · Verdict</h2><p>Old verdict.</p><footer', 1)
    d.save()
    assert client.post(f'/api/v1/deals/{did}/revise/', {}, format='json').status_code == 400        # no comments yet
    r = client.post(f'/api/v1/deals/{did}/comments/', {'text': 'Management has run two prior exits; not a gap.',
                    'stance': 'disagree', 'quote': 'Old findings.', 'section': '4 · The transaction', 'via': 'voice'}, format='json')
    assert r.status_code == 201 and r.data['status'] == 'open'
    cid = r.data['id']
    assert client.get(f'/api/v1/deals/{did}/').data['open_comments'] == 1
    calls = []

    def revise_ask(job, **kw):
        calls.append(kw['label'])
        assert 'Management has run two prior exits' in json.dumps(kw['content'])
        if kw['label'] == 'revise score':
            data = dict(Deal.objects.get(pk=did).scorecard)
            data['changes'] = [{'criterion': 'x', 'from': 5, 'to': 6, 'why': 'mgmt', 'comment_ids': [cid]}]
            return '```json\n' + json.dumps(data) + '\n```'
        return ('```html\n<h2>4 · The transaction &amp; key findings</h2><p>New findings with <span class="src mgmt">DEAL LEAD</span>.</p>\n```\n'
                '```json\n' + json.dumps({'responses': [{'id': cid, 'response': 'Finding 3 rewritten'}], 'summary': 's'}) + '\n```')
    monkeypatch.setattr(engine, 'ask', revise_ask)
    n0 = MemoVersion.objects.filter(deal_id=did).count()
    assert client.post(f'/api/v1/deals/{did}/revise/', {}, format='json').status_code == 202
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert job.status == 'done', job.error
    assert calls == ['revise score', 'revise memo']                     # no digest / research / risk / integrate
    d = Deal.objects.get(pk=did)
    assert 'New findings' in d.memo_html and '<p>Old findings.</p>' not in d.memo_html and 'Old verdict' in d.memo_html
    assert 'Deal lead review — comments applied' in d.memo_html and 'Finding 3 rewritten' in d.memo_html
    assert MemoVersion.objects.filter(deal_id=did).count() == n0 + 1
    c = MemoComment.objects.get(pk=cid)
    assert c.status == 'applied' and c.applied_in_id == d.memos.first().id
    assert client.patch(f'/api/v1/deals/{did}/comments/{cid}/', {'text': 'x'}, format='json').status_code == 400
    from apps.audit.models import AuditEvent
    assert AuditEvent.objects.filter(action='memo.comment', deal_id=did).exists()
    assert AuditEvent.objects.filter(action='analysis.revised', deal_id=did).exists()


def test_three_frameworks_buyout_cv(client):
    from apps.deals import frameworks, prompts
    b, cv = frameworks.get('buyout'), frameworks.get('cv')
    assert (b.name, cv.name) == ('ADCG Buyout', 'ADCG CV')
    bn = [x['name'] for x in b.config['sections']]
    cn = [x['name'] for x in cv.config['sections']]
    assert 'Sponsor Quality' in bn and 'Trophy Asset' not in bn and 'Trophy Asset' in cn and 'Sponsor Quality' not in cn
    al = next(x for x in b.config['sections'] if x['name'] == 'Alignment')
    assert all('sponsor' not in c['name'].lower() for c in al['criteria'])
    assert sum(x['weight'] for x in b.config['sections']) == 100
    assert 'ADCG CV' in prompts.framework('cv') and 'Sponsor Quality' in prompts.framework('buyout')
    assert '"cv"' in prompts.RESEARCH_TASK and 'cv' in prompts.SCORE_TASK


def test_house_preferences_adjust_and_prompt(client):
    from apps.deals import frameworks, prompts
    from apps.deals.scoring import score
    h = frameworks.house_cfg('buyout')
    ids = [p['id'] for p in h['preferences']]
    assert 'marquee-gps' in ids and 'frontier-selective' not in ids          # frontier applies to VG only
    assert 'frontier-selective' in [p['id'] for p in frameworks.house_cfg('vg')['preferences']]
    txt = prompts.framework('buyout')
    assert 'ADCG HOUSE PREFERENCES' in txt and 'house_fit' in txt
    crit = lambda n: [{'name': f'{n} {i}', 'score': 6} for i in range(3)]
    deal = {'deal': {'name': 'X'}, 'sections': [{'name': n, 'weight': w, 'criteria': crit(n)} for n, w in
            [('Sector Focus', 15), ('Sponsor Quality', 20), ('Business Quality', 25), ('Valuation & Leverage', 25), ('Alignment', 15)]],
            'house_fit': [{'id': i, 'fit': 2, 'why': 'fits'} for i in ids]}
    summary, frag, clean = score(deal, 'buyout', frameworks.get('buyout').config, h)
    assert summary['framework_overall'] == 6.0 and summary['house_adj'] == 0.5 and summary['overall'] == 6.5
    assert clean['house']['items'][0]['fit'] == 2 and 'ADCG preferences adjustment' in frag
    deal['house_fit'] = [{'id': ids[0], 'fit': -2}]                         # only one rated → full weight on it
    summary, _, _ = score(deal, 'buyout', frameworks.get('buyout').config, h)
    assert summary['house_adj'] == -0.5
    r = client.get('/api/v1/frameworks/house/')
    assert r.status_code == 200 and len(r.data['config']['preferences']) == 5


def test_gp_tiers_score_sponsor_and_secondary(client):
    from apps.deals import frameworks
    from apps.deals.scoring import score
    g = frameworks.get('gps')
    cfg = dict(g.config)
    cfg['sponsor_tiers'][0]['members'] = [{'name': 'TPG', 'domain': 'tpg.com'}, 'Hellman & Friedman']
    cfg['sponsor_tiers'][1]['members'] = []
    cfg['sponsor_tiers'][2]['members'] = [{'name': 'The Sterling Group', 'domain': 'sterling-group.com'}]
    cfg['secondary_tiers'][0]['members'] = [{'name': 'Ares Management', 'domain': 'aresmgmt.com', 'aliases': ['Ares']}]
    frameworks.save('gps', config=cfg, guidance='', name=g.name, description=g.description, note='t', user=None)
    gps = frameworks.gps_cfg()
    cv = frameworks.get('cv').config
    al = next(s for s in cv['sections'] if s['name'] == 'Alignment')
    assert [c.get('auto') for c in al['criteria']][:2] == ['sponsor_tier', 'secondary_tier']
    assert any(c.get('auto') == 'sponsor_tier' for s in frameworks.get('buyout').config['sections'] for c in s['criteria'])
    crit = lambda s: [{'name': c['name'], 'auto': c.get('auto'), 'score': 6} for c in s['criteria']]
    deal = {'deal': {'name': 'X'}, 'sponsor_gp': 'TPG Capital', 'sponsor_gp_domain': 'https://www.tpg.com/', 'secondary_lead': 'Ares',
            'sections': [{'name': s['name'], 'weight': s['weight'], 'criteria': crit(s)} for s in cv['sections']]}
    _, _, clean = score(deal, 'cv', cv, None, gps)
    al = next(s for s in clean['sections'] if s['name'] == 'Alignment')
    assert al['criteria'][0]['score'] == 9 and 'Tier 1' in al['criteria'][0]['rationale']
    assert al['criteria'][1]['score'] == 9 and 'P1' in al['criteria'][1]['rationale']
    assert 'tpg.com' in al['criteria'][0]['rationale']
    deal['sponsor_gp'], deal['sponsor_gp_domain'], deal['secondary_lead'] = 'Unknown Partners', '', ''
    _, _, clean = score(deal, 'cv', cv, None, gps)
    al = next(s for s in clean['sections'] if s['name'] == 'Alignment')
    assert al['criteria'][0]['score'] == 6                                 # not listed → the scorer's own score stands
    # identity, not words: a different Sterling (its own website) is NOT The Sterling Group; a bare shared word isn't either
    for nm, dom in (('Sterling Investment Partners', 'sterlinglp.com'), ('Sterling', ''), ('TPG Capital', '')):
        deal['sponsor_gp'], deal['sponsor_gp_domain'] = nm, dom
        _, _, clean = score(deal, 'cv', cv, None, gps)
        assert next(s for s in clean['sections'] if s['name'] == 'Alignment')['criteria'][0]['score'] == 6, nm
    deal['sponsor_gp'], deal['sponsor_gp_domain'] = 'Sterling Group', ''   # exact name / alias still matches
    _, _, clean = score(deal, 'cv', cv, None, gps)
    assert next(s for s in clean['sections'] if s['name'] == 'Alignment')['criteria'][0]['score'] == 5
    stored = frameworks.gps_cfg()['sponsor_tiers'][0]['members']
    assert stored[1] == {'name': 'Hellman & Friedman', 'domain': ''} and stored[0]['domain'] == 'tpg.com'
    text = __import__('apps.deals.prompts', fromlist=['x']).framework('cv')
    assert 'ADCG GP TIERS' in text and 'Hellman & Friedman' in text and 'TPG (tpg.com)' in text and 'DUAL MANAGER CHECK' in text
    assert 'sponsor_gp_domain' in text
    assert 'ADCG GP TIERS' not in __import__('apps.deals.prompts', fromlist=['x']).framework('vg')


def test_gp_entities_defaults_vg_matching_and_lookup(client, monkeypatch):
    from apps.deals import frameworks, suggest
    from apps.deals.framework import gp_entities as gpe
    from apps.deals.scoring import assign_tiers
    g = frameworks.get('gps').config
    t1 = {m['domain'] for m in g['sponsor_tiers'][0]['members']}
    assert {'gtcr.com', 'cdr-inc.com', 'synova.pe', 'capvest.com'} <= t1 and len(t1) == 19
    t2 = g['sponsor_tiers'][1]['members']
    assert len(t2) == 47 and all(m['domain'] for m in t2)
    vg = frameworks.get('vg').config['tiers']
    assert all(isinstance(m, dict) for t in vg for m in t['members'])
    inv = [{'name': 'Founders Fund LLC', 'domain': 'foundersfund.com', 'tier': 'X'},
           {'name': 'Founders Capital', 'domain': 'founderscap.example', 'tier': 'X'},
           {'name': 'Google', 'tier': 'X'}]
    assign_tiers(inv, vg)
    assert [i['tier'] for i in inv] == ['T1', 'X', 'S']
    # old string members still load (personal copies saved before entities)
    assert gpe.as_member('NVentures / NVIDIA') == {'name': 'NVentures', 'domain': 'nvidia.com', 'aliases': ['NVIDIA']}
    monkeypatch.setattr(suggest, 'external', lambda q: [{'name': 'GTCR LLC', 'domain': 'gtcr.com', 'source': 'clearbit'},
                                                         {'name': 'Graycliff Partners', 'domain': 'graycliffpartners.com', 'source': 'clearbit'}])
    from apps.users.models import User
    u = User.objects.create_user(username='gl', password='pw-long-enough-1')
    client.force_login(u)
    from rest_framework.test import APIClient
    api = APIClient(); api.force_authenticate(u)
    r = api.get('/api/v1/frameworks/gp-lookup/?q=gtcr').json()['results']
    assert r[0]['domain'] == 'gtcr.com' and r[0]['listed'] == ['Buyout sponsors · Tier 1']
    assert any(x['domain'] == 'graycliffpartners.com' and not x['listed'] for x in r)
    # proposals describe GP tier moves in plain English
    new = __import__('copy').deepcopy(g)
    gt = new['sponsor_tiers'][0]['members'].pop(0)
    new['sponsor_tiers'][1]['members'].append(gt)
    assert any('moves Inflexion Tier 1 → Tier 2' in x for x in frameworks.diff('gps', g, new))
