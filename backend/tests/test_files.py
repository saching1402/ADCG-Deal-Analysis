"""Every uploaded file must be readable — and proven read — before analysis starts."""
import io
import os
import shutil
import subprocess
import tempfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.deals import engine
from apps.deals.extract import PART_PAGES, inspect, prepare
from apps.deals.models import AnalysisJob, DealFile

HAS_SOFFICE = bool(shutil.which('soffice'))
HAS_POPPLER = bool(shutil.which('pdftoppm'))


def soffice(src_bytes: bytes, ext: str, target: str) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, f'in.{ext}')
        open(p, 'wb').write(src_bytes)
        subprocess.run(['soffice', '--headless', f'-env:UserInstallation=file://{td}/u', '--convert-to', target, '--outdir', td, p],
                       check=True, capture_output=True, timeout=240)
        return open(os.path.join(td, 'in.' + target.split(':')[0]), 'rb').read()


@pytest.fixture(scope='module')
def long_pdf():
    if not HAS_SOFFICE:
        pytest.skip('LibreOffice not installed')
    lines = '\n'.join(f'Page block {i}: FY25 revenue £{i}.2m, EBITDA margin {i % 30}%.\f' for i in range(1, 131))
    return soffice(lines.encode(), 'txt', 'pdf')


def scanned_pdf(n=3) -> bytes:
    from PIL import Image, ImageDraw
    imgs = []
    for i in range(n):
        im = Image.new('RGB', (850, 1100), 'white')
        ImageDraw.Draw(im).text((80, 80), f'Scanned page {i + 1}: EBITDA 41.8m', fill='black')
        imgs.append(im)
    buf = io.BytesIO()
    imgs[0].save(buf, 'PDF', save_all=True, append_images=imgs[1:])
    return buf.getvalue()


def encrypted(data: bytes, user_pw: str) -> bytes:
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for p in PdfReader(io.BytesIO(data)).pages:
        w.add_page(p)
    w.encrypt(user_password=user_pw, owner_password='owner-secret')
    b = io.BytesIO(); w.write(b)
    return b.getvalue()


def test_long_pdf_split_natively_every_page_covered(long_pdf):
    chk = inspect('fdd.pdf', long_pdf)
    assert chk['status'] == 'ok' and chk['pages'] >= 130
    prep = prepare('fdd.pdf', long_pdf)
    assert prep.method == 'native-pdf' and all(p.blocks[0]['type'] == 'document' for p in prep.parts)
    covered = [pg for p in prep.parts for pg in range(p.pages[0], p.pages[1] + 1)]
    assert covered == list(range(1, chk['pages'] + 1))   # every page exactly once
    assert len(prep.parts) == -(-chk['pages'] // PART_PAGES)


def test_scanned_pdf_flagged_and_read_visually():
    data = scanned_pdf()
    chk = inspect('scan.pdf', data)
    assert chk['status'] == 'ok' and chk['text_pages'] == 0 and 'visually' in ' '.join(chk['notes'])
    assert prepare('scan.pdf', data).parts[0].blocks[0]['type'] == 'document'


@pytest.mark.skipif(not HAS_POPPLER, reason='poppler missing')
def test_page_image_fallback():
    from apps.deals.extract import fallback_blocks
    prep = prepare('scan.pdf', scanned_pdf(3))
    calls = fallback_blocks(prep, prep.parts[0])
    assert len(calls) == 1 and sum(1 for b in calls[0] if b['type'] == 'image') == 3


def test_encrypted_pdfs():
    base = scanned_pdf(1)
    assert inspect('locked.pdf', encrypted(base, ''))['status'] == 'ok'          # copy-protected only → unlocked
    chk = inspect('pw.pdf', encrypted(base, 'pw'))                                # real password → blocked at upload
    assert chk['status'] == 'block' and 'password' in chk['summary']
    assert inspect('broken.pdf', b'%PDF-1.4 garbage')['status'] == 'block'
    assert inspect('empty.pdf', b'')['status'] == 'block'


@pytest.mark.skipif(not HAS_SOFFICE, reason='LibreOffice not installed')
def test_excel_formulas_without_values_recalculated():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'P&L'
    ws.append(['Revenue', 100]); ws.append(['Costs', 60]); ws.append(['EBITDA', '=B1-B2'])
    b = io.BytesIO(); wb.save(b)
    chk = inspect('model.xlsx', b.getvalue())
    assert chk['status'] == 'warn' and 'recalculated' in chk['notes'][0]
    text = prepare('model.xlsx', b.getvalue()).parts[0].blocks[0]['text']
    assert 'EBITDA | 40' in text and 'Sheet: P&L' in text


@pytest.mark.skipif(not HAS_SOFFICE, reason='LibreOffice not installed')
def test_pptx_converted_to_pdf():
    from pptx import Presentation
    prs = Presentation()
    for i in range(3):
        s = prs.slides.add_slide(prs.slide_layouts[1]); s.shapes.title.text = f'Slide {i}: ARR $12m'
    b = io.BytesIO(); prs.save(b)
    prep = prepare('deck.pptx', b.getvalue())
    assert prep.method == 'converted-pdf' and prep.pages == 3


# ── the gate ──────────────────────────────────────────────────────────────────
GOOD = '## Financials\nRevenue €120m [p. 3] (MGMT); EBITDA €41.8m; margin 14.0% FY25. ' + 'Detail line 2025. ' * 30


@pytest.fixture
def client(db, settings, tmp_path):
    from rest_framework.test import APIClient
    from apps.users.models import User
    settings.MEDIA_ROOT = str(tmp_path)
    settings.ANTHROPIC_API_KEY = 'sk-ant-test'
    settings.DIGEST_CONCURRENCY = 1
    u = User.objects.create_user('a@b.com', 'pw-long-enough-1', role='analyst')
    c = APIClient(); c.force_authenticate(u)
    return c


def test_upload_rejects_unreadable(client):
    did = client.post('/api/v1/deals/', {'name': 'X'}, format='json').data['id']
    r = client.post(f'/api/v1/deals/{did}/files/', {'file': SimpleUploadedFile('pw.pdf', encrypted(scanned_pdf(1), 'pw'))}, format='multipart')
    assert r.status_code == 422 and 'password' in r.data['detail']
    assert client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json').status_code == 400   # no readable files
    r = client.post(f'/api/v1/deals/{did}/files/', {'file': SimpleUploadedFile('scan.pdf', scanned_pdf(2))}, format='multipart')
    assert r.status_code == 201 and r.data['readability']['pages'] == 2


def test_gate_blocks_then_allows(client, monkeypatch):
    calls = []

    def fake_ask(job, *, model, system, content, max_tokens, searches=0, label=''):
        calls.append(label)
        if label.startswith('digest bad.txt'):
            return 'I cannot read this document; it appears to be blank.'
        if label.startswith('digest'):
            return GOOD
        raise AssertionError('research must not start while files are unreadable')
    monkeypatch.setattr(engine, 'ask', fake_ask)
    monkeypatch.setattr(engine, 'preflight', lambda: None)
    did = client.post('/api/v1/deals/', {'name': 'Gate Co'}, format='json').data['id']
    for n, body in (('good.txt', b'Revenue 2025: 120m. ' * 20), ('bad.txt', b'Some content here 2025 ' * 20)):
        assert client.post(f'/api/v1/deals/{did}/files/', {'file': SimpleUploadedFile(n, body)}, format='multipart').status_code == 201
    client.post(f'/api/v1/deals/{did}/analyze/', {}, format='json')
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert job.status == 'blocked' and 'bad.txt' in job.error
    assert any('retry' in c for c in calls)                       # a failed part is retried before giving up
    assert DealFile.objects.get(name='bad.txt').status == 'error'
    assert DealFile.objects.get(name='good.txt').status == 'digested'
    d = client.get(f'/api/v1/deals/{did}/').data
    assert d['status'] == 'blocked'

    # deal lead chooses to proceed without the unreadable file: no re-read, research starts
    monkeypatch.setattr(engine, 'stage_research', lambda job, files: (_ for _ in ()).throw(RuntimeError(f'research with {[f.name for f in files]}')))
    client.post(f'/api/v1/deals/{did}/analyze/', {'allow_partial': True}, format='json')
    n_before = len(calls)
    job = engine.claim_next(); engine.run_job(job); job.refresh_from_db()
    assert "research with ['good.txt']" in job.error and len(calls) == n_before
    assert AnalysisJob.objects.filter(deal_id=did).count() == 2
