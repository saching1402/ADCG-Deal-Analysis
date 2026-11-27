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
    assert 'Risk Score' not in frag and 'risk score' not in frag.lower() and 'gauge' not in frag and 'III.6 · Framework Scoring Summary' in frag
    assert 'Criteria detail' not in frag and 'Contrarian' not in frag and 'class="bars"' in frag   # memo shows only the bars
    assert 'scorecard' in frag and clean['sections'][0]['score'] > 0


def test_vg_score_fixed_weights_marquee_vjr():
    s, frag, clean = score(VG, 'vg')
    assert [x['weight'] for x in clean['sections']] == [25, 25, 25, 10, 10, 5]
    assert s['marquee_pts'] == 4.5 and s['marquee_score'] == 9.0   # formula 3.7, lifted: two tier-1 managers (Thrive, Accel)
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
    if label == 'overview':                               # materials AND web together, from the start
        assert '<materials' in json.dumps(content) and searches == engine.OVERVIEW_SEARCHES
        return 'Inspects lifts for building owners. https://example.com/o\n```json\n' + json.dumps({
            'track': 'buyout', 'sector': 'Industrials', 'sub_sector': 'TIC', 'sources': ['https://example.com/b']}) + '\n```'
    if label == 'research':
        c = json.dumps(content)
        assert '<materials' in c and '<opportunity_summary>' in c and 'Inspects lifts' in c
        return 'Dossier with https://example.com/a\n```json\n{"sources": []}\n```'
    if label == 'integrate':
        assert '<materials' in json.dumps(content) and '<research_dossier>' in json.dumps(content)
        return 'Actuals table from the IM.\n```json\n' + json.dumps({
            'one_liner': 'Test inspector', 'ev': '€1bn', 'multiple': '12x', 'leverage': '3x', 'sponsor': 'PAI',
            'risk_disclosure': [{'risk': 'Dental roll-ups have a poor PE record', 'in_cim': 'understated'}],
            'materials_risks': [{'risk': 'Customer concentration (top 3 = 40%)', 'severity': 'MEDIUM', 'in_cim': 'yes', 'source': 'IM'}],
            'reconciliation': [{'metric': 'Adj. EBITDA', 'cim': '41.8', 'other': '40.1 [QoE]'}],
            'facts': [{'k': 'EV / EBITDA', 'v': '12.7–13.5× Adj. / 15.2–16.1× reported (EST); 12.4× on 2026E', 'src': 'CIM p.83'},
                      {'k': 'Enterprise value', 'v': '$531m', 'src': 'CIM p.5'}]}) + '\n```'
    if label == 'risk':
        assert '<materials' in json.dumps(content) and '# Research & analysis' in json.dumps(content)
        return 'Bottom line: roll-up risk. https://example.com/risk\n```json\n' + json.dumps({
            'risks': [{'risk': 'Dental roll-ups have a poor PE record', 'in_cim': 'no', 'severity': 'HIGH', 'source': 'https://example.com/dso'}],
            'track_record': [{'deal': 'Western Dental', 'sponsor': 'X', 'outcome': 'Restructuring'}],
            'theme_verdict': 'Graveyard theme', 'reconciliation': [{'metric': 'Adj. EBITDA', 'cim': '41.8', 'other': '40.1 [QoE]'}]}) + '\n```'
    if label == 'score':
        return '```json\n' + json.dumps(BUYOUT) + '\n```'
    if label == 'memo part 1':
        return '```html\n<div class="part-h"><span>I</span>Summary and Analysis</div><h2>1 · Deal Overview</h2><p>x</p>\n```'
    if label == 'memo part 3':
        return '```html\n<h2 class="part">II · Investment Pros and Cons</h2><h2>III.1 · Sector Focus</h2>\n```'
    if label == 'memo part 4':
        return '```html\n<h2 class="part">IV · Recommendation and Next Steps</h2><h2>A.1 · Sources and References</h2>\n```'
    return '```html\n<h2>5 · Value Creation Plan</h2>\n```'


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
    assert d['risk_items']['reconciliation'][0]['metric'] == 'Adj. EBITDA' and '# Business plan, actuals & reconciliation' in d['research'] and d['research'].startswith('# Opportunity summary')
    ev = next(f for f in d['facts'] if f['k'] == 'EV / EBITDA')
    assert ev['v'] == '12.7×' and '15.2' in ev['note'] and ev['src'] == 'CIM p.83'
    memo = client.get(f'/api/v1/deals/{did}/memo/').data['html']
    assert '1 · Deal Overview' in memo and 'Appendix — Prior Deals' not in memo and '{{' not in memo
    order = ['1 · Deal Overview', '5 · Value Creation Plan', 'II · Investment Pros and Cons', 'III.1 · Sector Focus',
             'III.6 · Framework Scoring Summary', 'IV · Recommendation and Next Steps', 'A.1 · Sources and References']
    assert [memo.index(h) for h in order] == sorted(memo.index(h) for h in order)
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
    assert [f['key'] for f in r['frameworks']] == ['buyout', 'cv', 'vg', 'fund'] and r['frameworks'][2]['version'] == 1
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
    cfg['marquee']['floors'] = {'t1_one': 0, 't1_two': 0, 't1_three': 0, 'good_three': 0}   # test the formula alone
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
    assert '"cv"' in prompts.OVERVIEW_TASK and 'cv' in prompts.SCORE_TASK


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
    cfg['secondary_tiers'][1]['members'] = []
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
    p1 = {m['domain'] for m in g['secondary_tiers'][0]['members']}
    assert {'lexingtonpartners.com', 'alpinvest.com', 'lgtcp.com', 'leonardgreen.com'} <= p1 and len(p1) == 8
    assert len(g['secondary_tiers'][1]['members']) == 10
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


def test_memo_pdf_download_named_after_asset(client, monkeypatch):
    from apps.deals import memo_pdf
    from apps.deals.models import Deal, MemoVersion
    from apps.audit.models import AuditEvent
    seen = {}
    monkeypatch.setattr(memo_pdf, 'render', lambda html: seen.setdefault('html', memo_pdf.prepare(html)) and b'%PDF-1.7 fake')
    d = Deal.objects.create(name='KSFM Solutions')
    assert client.get(f'/api/v1/deals/{d.id}/memo/pdf/').status_code == 404
    MemoVersion.objects.create(deal=d, html='<html><head><style>@page{size:A4;margin:12mm}body{background:#fff}</style></head><body>x</body></html>')
    MemoVersion.objects.create(deal=d, html='<html><head></head><body>y</body></html>')
    r = client.get(f'/api/v1/deals/{d.id}/memo/pdf/')
    assert r.status_code == 200 and r['Content-Type'] == 'application/pdf' and r.content.startswith(b'%PDF')
    assert 'KSFM Solutions' in r['Content-Disposition'] and 'Mindari IC memo v2.pdf' in r['Content-Disposition']
    first = MemoVersion.objects.filter(deal=d).order_by('created_at').first()
    r = client.get(f'/api/v1/deals/{d.id}/memo/pdf/?version={first.id}')
    assert 'v1.pdf' in r['Content-Disposition']
    assert '#f6f4ee' in seen['html'] and 'margin:12mm' not in seen['html'] and 'print-color-adjust: exact' in seen['html']
    assert AuditEvent.objects.filter(action='memo.download_pdf').exists()


def test_memo_brief_sections_and_small_source_tags(client):
    from apps.deals import prompts, memo_css
    from apps.deals.models import Deal, MemoVersion
    bp = prompts.fw('memo_blueprint.md')
    assert 'WHERE EACH PART COMES FROM' in bp and 'Industry primer' in bp and 'technology primer' not in bp
    for track, secs in (('buyout', ['Sector Focus', 'Sponsor Quality']), ('cv', ['Trophy Asset']), ('vg', ['Theme'])):
        tasks = ' '.join(t for _, t in prompts.memo_tasks(track, secs))
        for h in ('1 · Deal Overview', '3 · Industry Primer and Independent Market Assessment', '5 · Value Creation Plan',
                  '6 · Financials and Business Plan', '8 · Returns Analysis and Independent Sensitivities',
                  'II · Investment Pros and Cons', 'IV · Recommendation and Next Steps', 'A.2 · Definitions and Methodology',
                  'III.1 · ' + secs[0], prompts.scoring_title(track), 'ADCG independent review'):
            assert h in tasks, (track, h)
    assert 'CV ECONOMICS' in prompts.OVERVIEW_TASK and 'LIQUIDATION PREFERENCE' in prompts.OVERVIEW_TASK and '{deal_terms}' not in prompts.OVERVIEW_TASK
    assert 'REPLICATED EXACTLY' in prompts.INTEGRATE_TASK and 'CONTEST' in prompts.RESEARCH_TASK and 'ADCG INDEPENDENT REVIEW' in prompts.INTEGRATE_TASK
    assert 'The memo structure' in bp and 'Returns Analysis and Independent Sensitivities' in bp
    d = Deal.objects.create(name='KSFM Solutions')
    MemoVersion.objects.create(deal=d, html='<html><head><style>.src{font-size:9.5px}</style></head><body>x</body></html>')
    html = client.get(f'/api/v1/deals/{d.id}/memo/').json()['html']
    assert 'memo-css-patch' in html and html.count('memo-css-patch') == 1 and memo_css.patch(html) == html


def test_deal_specific_factors_and_score_panel():
    """Framework sections share 90%; 10% goes to factors the scorer picks for the deal; Part III opens with the score."""
    from apps.deals.framework.defaults import BUYOUT_CONFIG, VG_CONFIG
    from apps.deals.scoring import score_header, DS_NAME
    from apps.deals import frameworks, prompts
    assert BUYOUT_CONFIG['deal_specific']['weight'] == 10 and VG_CONFIG['deal_specific']['weight'] == 10
    deal = json.loads(json.dumps(BUYOUT))
    deal['deal_specific'] = [{'name': 'Patent cliff', 'why': 'two blockbusters lose exclusivity in 2028', 'score': 4, 'rationale': 'r'},
                             {'name': 'Pipeline depth', 'score': 7, 'rationale': 'r'}]
    s, frag, clean = score(deal, 'buyout', BUYOUT_CONFIG)
    secs = {x['name']: x for x in clean['sections']}
    assert secs[DS_NAME]['weight'] == 10 and abs(sum(x['weight'] for x in clean['sections']) - 100) < 0.05
    assert 'two blockbusters' in secs[DS_NAME]['criteria'][0]['rationale']
    assert 'III.7 · Framework Scoring Summary' in frag          # 5 framework sections + deal-specific, then the summary
    s0, _, clean0 = score(BUYOUT, 'buyout', BUYOUT_CONFIG)       # no factors returned → framework weights unchanged
    assert DS_NAME not in {x['name'] for x in clean0['sections']}
    head = score_header(clean, s, 'buyout')
    assert 'sc-head' in head and f'{s["overall"]:.2f}' in head and 'Patent cliff' in head
    assert 'DEAL-SPECIFIC FACTORS' in frameworks.render(type('F', (), {'config': BUYOUT_CONFIG, 'key': 'buyout', 'name': 'ADCG Buyout',
                                                                       'version': 1, 'description': ''})())
    assert 'flagged_by' in prompts.RISK_TASK and 'tariffs' in prompts.RISK_TASK and 'WHAT LOOKS OVERSTATED' in prompts.INTEGRATE_TASK


@pytest.mark.django_db
def test_rerun_replaces_headline_figures():
    """A re-run's latest materials overwrite a ledger deal's EV / multiple / leverage / sponsor and log the change."""
    from apps.deals.models import AnalysisJob
    d = Deal.objects.create(name='Circet Group', ev='~€3.25bn', multiple='~9.1–9.5×', leverage='~6.0×', sponsor='ICG', legacy=True)
    job = AnalysisJob.objects.create(deal=d, model='claude-sonnet-5-5')
    engine.refresh_headline(job, d, {'ev': '€3.6bn', 'multiple': '10.2×', 'leverage': '5.1×', 'sponsor': 'ICG / CVC',
                                     'facts': [{'k': 'Enterprise value', 'v': '€3.6bn', 'src': 'IM'}]})
    assert (d.ev, d.multiple, d.leverage, d.sponsor) == ('€3.6bn', '10.2×', '5.1×', 'ICG / CVC') and d.facts[0]['v'] == '€3.6bn'
    job.refresh_from_db()
    log_txt = json.dumps(job.log, ensure_ascii=False)
    assert 'EV ~€3.25bn → €3.6bn' in log_txt and 'Leverage ~6.0× → 5.1×' in log_txt


def test_marquee_cluster_floors_and_co_sponsor():
    """VG: one tier-1 manager ≥ 8, two ≥ 9, small unlisted VCs never drag the score down. Buyout: the stronger of two
    sponsors sets the sponsor-tier score."""
    from apps.deals.scoring import marquee, apply_gp_tiers
    from apps.deals.framework.defaults import VG_CONFIG, GPS_CONFIG
    small = [{'name': f'Seed fund {i}', 'tier': 'X', 'role': 'part'} for i in range(6)]
    one = [{'name': 'Sequoia', 'tier': 'T1', 'role': 'part'}] + small
    two = one + [{'name': 'Founders Fund', 'tier': 'T1', 'role': 'part'}]
    assert marquee(one, VG_CONFIG)[1] >= 8.0 and marquee(two, VG_CONFIG)[1] >= 9.0
    assert marquee(small, VG_CONFIG)[1] < 8.0
    good3 = [{'name': n, 'tier': 'T2', 'role': 'part'} for n in ('Coatue', 'ICONIQ', 'IVP')]
    assert marquee(good3, VG_CONFIG)[1] >= 8.0
    d = {'sponsor_gp': 'Unknown Partners', 'sponsor_gp_domain': 'unknown-partners.example',
         'co_sponsor_gp': 'GTCR', 'co_sponsor_gp_domain': 'gtcr.com',
         'sections': [{'name': 'Sponsor Quality', 'criteria': [{'name': 'Sponsor tier', 'auto': 'sponsor_tier', 'score': None, 'rationale': ''}]}]}
    apply_gp_tiers(d, GPS_CONFIG)
    c = d['sections'][0]['criteria'][0]
    assert c['score'] == 9.0 and 'Co-sponsor' in c['rationale'] and d['gp_tiers']['sponsor_tier']['firm'] == 'GTCR'



def _track_record_xlsx() -> bytes:
    import io, datetime as dt, openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Funds'
    ws.append(['Fund', 'Vintage', 'Fund Size', 'Net IRR', 'Net TVPI', 'DPI'])
    ws.append(['Fund I', 2016, 375, 0.719, 4.0, 2.9]); ws.append(['Fund II', 2019, 850, 0.31, 2.1, 0.8])
    d = wb.create_sheet('Deals')
    d.append(['Company', 'Fund', 'Sector', 'Deal Lead', 'Investment Date', 'Exit Date', 'Invested', 'Realized', 'Unrealized'])
    rows = [('Alpha', 'Fund I', 'Software', 'A', dt.date(2016, 5, 1), dt.date(2020, 6, 1), 40, 400, 0),
            ('Beta', 'Fund I', 'Software', 'B', dt.date(2017, 3, 1), dt.date(2021, 6, 1), 30, 90, 0),
            ('Gamma', 'Fund I', 'Industrials', 'A', dt.date(2017, 9, 1), dt.date(2022, 6, 1), 50, 20, 0),
            ('Delta', 'Fund II', 'Healthcare', 'C', dt.date(2019, 4, 1), None, 60, 10, 110),
            ('Epsilon', 'Fund II', 'Industrials', 'B', dt.date(2020, 2, 1), None, 45, 0, 40),
            ('Zeta', 'Fund II', 'Software', 'C', dt.date(2020, 8, 1), dt.date(2024, 3, 1), 35, 105, 0)]
    for r in rows:
        d.append(list(r))
    d.append(['Total', '', '', '', None, None, 260, 625, 150])
    b = io.BytesIO(); wb.save(b)
    return b.getvalue()


def test_fund_analytics_workbook_and_memo_block():
    """Fund Manager Evaluation: the portfolio workbook is parsed and analysed by the app (not the model)."""
    import datetime as dt
    from apps.deals import fund_analytics as fa, prompts
    r = fa.read_workbook(_track_record_xlsx())
    assert len(r['deals']) == 6 and r['funds'][0]['net_irr'] == 0.719 and r['sheet'] == 'Deals'
    a = fa.compute(r, as_of=dt.date(2026, 9, 30))
    o = a['overall']
    assert o['n'] == 6 and o['moic'] == round((625 + 150) / 260, 2)
    assert a['ex_top_2']['excluded'] == ['Alpha', 'Zeta'] and a['ex_top_2']['moic'] < o['moic']
    assert o['loss_ratio'] == round((50 + 45) / 260, 3)            # Gamma 0.4x, Epsilon 0.89x
    assert set(a['by_sector']) == {'Software', 'Industrials', 'Healthcare'} and o['irr'] is not None
    blk = fa.memo_block(a)
    assert 'class="fa"' in blk and blk.count('<figure class="fig">') >= 5 and 'Excluding top 2' in blk
    assert 'Alpha' in fa.dashboard_html('Test Fund III', a) and 'loss ratio' in fa.brief(a)
    tasks = ' '.join(t for _, t in prompts.memo_tasks('fund', ['Strategy & Positioning', 'Track Record']))
    for h in ('1 · Introduction to the Manager', '3 · Track Record', '4 · Underlying Portfolio Analysis',
              '5 · Team and Management Biographies', '6 · Independent Background Verification', '7 · DDQ Check',
              '8 · Operational Due Diligence', '9 · Market Standing and Peer Ranking', 'III.1 · Strategy &amp; Positioning'):
        assert h in tasks, h
    assert prompts.task('integrate', 'fund') is prompts.FUND_INTEGRATE_TASK and prompts.task('integrate', 'buyout') is prompts.INTEGRATE_TASK


@pytest.mark.django_db
def test_fund_framework_and_dashboard_endpoint(client):
    from apps.deals import frameworks, engine
    fw = frameworks.get('fund')
    assert fw.name == 'ADCG Fund Manager Evaluation' and sum(s['weight'] for s in fw.config['sections']) == 100
    assert 'TRACK RECORD' in frameworks.prompt_text('fund').upper()
    d = Deal.objects.create(name='Test Capital Fund IV', track='fund', track_resolved='fund')
    assert client.get(f'/api/v1/deals/{d.id}/dashboard/').status_code == 404
    from apps.deals import fund_analytics as fa
    d.analytics = fa.dumps(fa.compute(fa.read_workbook(_track_record_xlsx())))
    d.save()
    r = client.get(f'/api/v1/deals/{d.id}/dashboard/')
    assert r.status_code == 200 and b'Alpha' in r.content and 'track-record dashboard' in r['Content-Disposition']
    part = '<h2>4 · Underlying Portfolio Analysis</h2><p>text</p>'
    assert engine.insert_analytics(part, d.analytics).index('class="fa"') > part.index('</h2>')


def test_fund_vintage_quartiles():
    """Each fund is placed against its own vintage thresholds; the manager's claim is checked; missing = not assessed."""
    import datetime as dt
    from apps.deals import fund_analytics as fa, engine
    funds = [{'fund': 'Fund I', 'vintage': 2016, 'net_irr': 0.25, 'net_tvpi': 2.4, 'dpi': 1.9, 'quartile': 'Top quartile'},
             {'fund': 'Fund II', 'vintage': 2019, 'net_irr': '11%', 'net_tvpi': 1.6, 'dpi': 0.6, 'quartile': '1st quartile'},
             {'fund': 'Fund III', 'vintage': 2023, 'net_irr': 0.08, 'net_tvpi': 1.1, 'dpi': 0.0, 'quartile': ''}]
    bm = [{'fund': 'Fund I', 'vintage': 2016, 'peer_group': 'Europe buyout', 'source': 'Test benchmark', 'as_of': 'Q2 2026', 'origin': 'web',
           'net_irr': {'uq': '20%', 'med': '14%', 'lq': '8%'}, 'net_tvpi': {'uq': 2.2, 'med': 1.8, 'lq': 1.4}, 'dpi': {'uq': 1.8, 'med': 1.3, 'lq': 0.9}},
          {'vintage': 2019, 'peer_group': 'Europe buyout', 'source': 'Test benchmark', 'origin': 'materials',
           'net_irr': {'uq': 0.19, 'med': 0.13, 'lq': 0.07}, 'net_tvpi': {'uq': 1.9, 'med': 1.5, 'lq': 1.25}}]
    q = fa.benchmark(funds, bm, as_of=dt.date(2026, 9, 30))
    r1, r2, r3 = q['rows']
    assert r1['q'] == 1 and r1['claim_check'] == 'confirmed' and r1['metrics']['dpi']['q'] == 1
    assert r2['q_irr'] == 3 and r2['q_tvpi'] == 2 and r2['claim_check'] == 'overstated'   # matched by vintage
    assert r2['metrics']['dpi']['thr'] is None and r3['benchmark'] is None and r3['too_early']
    assert q['summary']['overstated'] == ['Fund II'] and q['summary']['no_benchmark'] == ['Fund III'] and q['peer_group'] == 'Europe buyout'
    blk = fa.quartile_block(q)
    assert 'fa-q' in blk and blk.count('<svg') == 2 and 'Overstated' in blk and 'No vintage benchmark found for' in blk
    assert 'OVERSTATED' in fa.quartile_brief(q) and 'NO BENCHMARK' in fa.quartile_brief(q)
    part = '<h2>3 · Track Record</h2><p>x</p>'
    assert engine.insert_quartiles(part, {'quartiles': q}).index('fa-q') > part.index('</h2>')
    bad = fa.benchmark(funds[:1], [{'fund': 'Fund I', 'net_irr': {'uq': 0.1, 'med': 0.2, 'lq': 0.05}}])   # inconsistent → unused
    assert bad['rows'][0]['q'] is None


def test_backend_compiles_on_production_python():
    """Production runs Python 3.11 (Dockerfile): newer syntax (e.g. backslashes inside f-string expressions) takes the
    whole site down at start-up. Compile every backend module with 3.11 when it is installed."""
    import shutil, subprocess, pathlib
    py = shutil.which('python3.11')
    if not py:
        pytest.skip('python3.11 not installed')
    root = pathlib.Path(__file__).resolve().parents[1]
    files = [str(p) for p in root.rglob('*.py') if 'site-packages' not in str(p) and 'node_modules' not in str(p)]
    code = 'import sys, ast\nbad = []\nfor f in sys.argv[1:]:\n    try:\n        compile(open(f, encoding="utf-8").read(), f, "exec")\n    except SyntaxError as e:\n        bad.append(f"{f}:{e.lineno} {e.msg}")\nprint("\\n".join(bad))\nsys.exit(1 if bad else 0)'
    r = subprocess.run([py, '-c', code, *files], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


@pytest.mark.django_db
def test_update_with_new_files_only(client, monkeypatch):
    """Two more files after the memo exists → an UPDATE run: read only the new files, work out what changed, re-score,
    rewrite only the affected sections. No overview / research / risk / integrate."""
    from apps.deals.models import MemoVersion
    monkeypatch.setattr(engine, 'preflight', lambda: None)
    monkeypatch.setattr(engine, 'ask', fake_ask)
    did = client.post('/api/v1/deals/', {'name': 'Upd Co', 'track': 'buyout'}, format='json').data['id']
    f0 = SimpleUploadedFile('cim.txt', ('CIM revenue 2025 EBITDA 41.8 ' * 20).encode(), content_type='text/plain')
    client.post(f'/api/v1/deals/{did}/files/', {'file': f0}, format='multipart')
    client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json')
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert job.status == 'done', job.error
    d = Deal.objects.get(pk=did)
    d.memo_html = d.memo_html.replace('<footer', '<h2>6 · Financials and Business Plan</h2><p>EBITDA 41.8 (old model).</p>'
                                     '<h2>7 · Valuation Analysis</h2><p>Untouched.</p><footer', 1)
    d.save()
    assert client.post(f'/api/v1/deals/{did}/update/', {}, format='json').status_code == 400     # no new files yet
    f1 = SimpleUploadedFile('Model v2 (Nov).txt', ('Updated model revenue 2026 EBITDA 45.0 ' * 20).encode(), content_type='text/plain')
    assert client.post(f'/api/v1/deals/{did}/files/', {'file': f1}, format='multipart').status_code == 201
    calls = []

    def upd_ask(job, **kw):
        calls.append(kw['label'])
        c = json.dumps(kw['content'])
        if kw['label'].startswith('digest'):
            return fake_ask(job, **kw)
        if kw['label'] == 'update':
            assert 'Model v2 (Nov).txt' in c and '<current_memo_text>' in c and 'EBITDA 41.8 (old model)' in c
            assert 'cim.txt' not in c.split('<new_materials>')[1]                      # only the NEW file is "new"
            return ('## What changes\n| EBITDA | 41.8 | 45.0 | Model v2 |\n```json\n' + json.dumps(
                {'summary': 'Model v2 lifts FY26 EBITDA to 45.0', 'changes': [{'item': 'EBITDA', 'before': '41.8', 'now': '45.0', 'source': 'Model v2'}],
                 'answered': ['FY26 plan bridge'], 'headline': {'ev': '€1.1bn', 'facts': []}}) + '\n```')
        assert '<new_materials_update>' in c and 'EBITDA | 41.8 | 45.0' in c
        if kw['label'] == 'revise score':
            return '```json\n' + json.dumps(dict(Deal.objects.get(pk=did).scorecard, changes=[])) + '\n```'
        return ('```html\n<h2>6 · Financials and Business Plan</h2><p>EBITDA 45.0 <span class="src im">MODEL v2</span>.</p>\n```\n'
                '```json\n{"responses": [], "summary": "Financials updated to Model v2"}\n```')
    monkeypatch.setattr(engine, 'ask', upd_ask)
    n0 = MemoVersion.objects.filter(deal_id=did).count()
    r = client.post(f'/api/v1/deals/{did}/update/', {}, format='json')
    assert r.status_code == 202 and r.data['mode'] == 'update'
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert job.status == 'done', job.error
    assert [c for c in calls if not c.startswith('digest')] == ['update', 'revise score', 'revise memo']
    assert sum(c.startswith('digest') for c in calls) >= 1
    d = Deal.objects.get(pk=did)
    assert 'EBITDA 45.0' in d.memo_html and 'old model' not in d.memo_html and 'Untouched.' in d.memo_html
    assert 'Updates from new materials' in d.memo_html and 'Model v2 (Nov).txt' in d.memo_html
    assert '# Updates from new materials' in d.research and d.ev == '€1.1bn'
    assert job.result['files'] == ['Model v2 (Nov).txt'] and job.result['version'] == n0 + 1
    assert MemoVersion.objects.filter(deal_id=did).count() == n0 + 1
    from apps.audit.models import AuditEvent
    assert AuditEvent.objects.filter(action='analysis.updated', deal_id=did).exists()


def test_fund_dashboard_operating_metrics_and_qualitative_layers():
    """Operating read-through (entry vs current), capital lost split, exposure; portfolio map / team / background checks."""
    import io, datetime as dt, openpyxl
    from apps.deals import fund_analytics as fa, engine
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(['Company', 'Fund', 'Sector', 'Deal Lead', 'Investment Date', 'Status', 'Invested', 'Gross MOIC', 'Entry EV',
               'Entry Revenue', 'Entry EBITDA', 'Current Revenue', 'Current EBITDA', 'Current EV', 'Hold (months)', 'Add-ons', 'Sourcing'])
    ws.append(['Alpha', 'Fund I', 'Software', 'A', dt.date(2017, 1, 1), 'Realized', 20, 5.0, 100, 50, 10, 120, 30, 400, 48, 3, 'Proprietary'])
    ws.append(['Beta', 'Fund I', 'Services', 'B', dt.date(2018, 1, 1), 'Realized', 30, 0.0, 120, 80, 15, 60, 2, 20, 50, 1, 'Auction'])
    ws.append(['Gamma', 'Fund II', 'Services', 'A', dt.date(2022, 1, 1), 'Unrealized', 50, 0.6, 200, 100, 20, 110, 18, 160, 40, 0, 'Auction'])
    ws.append(['Delta', 'Fund II', 'Software', 'C', dt.date(2023, 1, 1), 'Unrealized', 40, 1.8, 150, 40, 12, 60, 18, 260, 30, 2, 'Proprietary'])
    b = io.BytesIO(); wb.save(b)
    a = fa.compute(fa.read_workbook(b.getvalue()), as_of=dt.date(2026, 9, 30))
    o = a['overall']
    assert o['lost_realised'] == round(30 / 140, 3) and o['lost_unrealised'] == round(50 * 0.4 / 140, 3) and o['writeoffs'] == 1
    assert o['realised_moic'] == round(100 / 50, 2) and a['by_sector']['Software']['share'] == round(60 / 140, 3)
    alpha = next(d for d in a['deals'] if d['name'] == 'Alpha')
    assert alpha['ent_mult'] == 10.0 and alpha['cur_mult'] == round(400 / 30, 2) and alpha['rev_growth'] == 1.4 and alpha['sourcing'] == 'Proprietary'
    vc = a['value_creation']
    assert vc['addons'] == 6 and vc['agg_rev_growth'] == round(350 / 270 - 1, 4) and a['lead_concentration']['top2'][0] == 'A'
    ql = fa.qualitative({'portfolio_map': [{'company': 'Alpha', 'theme': 'Vertical software', 'playbook': '<b>SaaS</b> roll-up', 'recurrence': 'subscription'}],
                         'themes': [{'name': 'Vertical software', 'thesis': 't'}],
                         'manager_profile': {'overview': 'A firm.', 'stats': [['$5bn', 'AUM']]},
                         'team': [{'name': 'Jane Roe', 'title': 'Partner', 'led': ['Alpha']}],
                         'background_checks': [{'name': 'Jane Roe', 'role': 'Partner', 'verdict': 'FLAG', 'findings': 'SEC order 2019',
                                                'checks': ['SEC'], 'sources': ['https://sec.gov/x', 'not-a-url']},
                                               {'name': 'Firm LLC', 'type': 'firm', 'verdict': 'clean', 'findings': 'None'}]})
    assert ql['map'][0]['playbook'] == 'SaaS roll-up' and ql['map'][0]['recurrence'] == 'Contracted / subscription'
    assert ql['checks'][0]['verdict'] == 'flag' and ql['checks'][0]['sources'] == ['https://sec.gov/x']
    a = fa.dumps(a); a.update(ql)
    page = fa.dashboard_html('Test Capital', a)
    assert "['map', 'Portfolio map'" in page and 'Jane Roe' in page and '</script>' in page and '<\\/' not in page.split('const A =')[0]
    assert 'fa-chk' in fa.checks_block(a) and 'fa-thm' in fa.theme_block(a)
    memo = fa.memo_block(a)
    assert 'Capital deployment by vintage' in memo and 'exposure and returns' in memo and 'Value creation' in memo
    part = '<h2>2 · Strategy</h2><p>x</p><h2>6 · Independent Background Verification</h2><p>y</p>'
    out = engine.insert_fund_blocks(part, a)
    assert out.index('fa-thm') < out.index('<p>x</p>') and out.index('fa-chk') < out.index('<p>y</p>')


@pytest.mark.django_db
def test_fund_from_files_reads_uploaded_workbook(client):
    """Regression: the integrate stage reads the workbook from real DealFile rows (it used a missing attribute)."""
    from apps.deals import fund_analytics as fa
    from apps.deals.models import DealFile
    did = client.post('/api/v1/deals/', {'name': 'Upload Fund II', 'track': 'fund'}, format='json').data['id']
    f = SimpleUploadedFile('Track record.xlsx', _track_record_xlsx(),
                           content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    assert client.post(f'/api/v1/deals/{did}/files/', {'file': f}, format='multipart').status_code == 201
    src = fa.from_files(list(DealFile.objects.filter(deal_id=did)))
    assert src and len(src['deals']) == 6 and src['file'] == 'Track record.xlsx'


@pytest.mark.django_db
def test_failed_run_resumes_after_risk_review(client, monkeypatch):
    """A run that failed at the business-plan step resumes there: no new overview / research / risk calls."""
    monkeypatch.setattr(engine, 'preflight', lambda: None)
    did = client.post('/api/v1/deals/', {'name': 'Resume Co', 'track': 'buyout'}, format='json').data['id']
    f = SimpleUploadedFile('cim.txt', ('CIM revenue 2025 EBITDA 41.8 ' * 20).encode(), content_type='text/plain')
    client.post(f'/api/v1/deals/{did}/files/', {'file': f}, format='multipart')
    labels = []

    def ask(job, **kw):
        labels.append(kw['label'])
        return fake_ask(job, **kw)
    monkeypatch.setattr(engine, 'ask', ask)
    real = engine.stage_integrate
    def broken(job, files):
        engine.set_stage(job, 'integrate', 'Business plan')
        raise AttributeError("'DealFile' object has no attribute 'original_name'")
    monkeypatch.setattr(engine, 'stage_integrate', broken)
    client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json')
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert job.status == 'error' and job.stage == 'integrate'
    assert any(l.startswith('overview') for l in labels) and any(l.startswith('risk') for l in labels)
    monkeypatch.setattr(engine, 'stage_integrate', real)
    labels.clear()
    client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json')
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert job.status == 'done', job.error
    assert not any(l.startswith(('overview', 'research', 'risk')) for l in labels), labels
    assert any('Resuming the run' in str(x) for x in job.log)
