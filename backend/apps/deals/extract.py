"""
Turn an uploaded deal file into something Claude can read.

* PDF up to ``NATIVE_PDF_MAX_PAGES`` pages / ``NATIVE_PDF_MAX_MB`` → sent as a native document block, so
  Claude sees tables, charts and scanned pages (CIMs, teasers, lender decks).
* Bigger PDFs, Word, Excel, PowerPoint, CSV, text, HTML, email → text extracted here and split into chunks.
* Images → image block.
"""
from __future__ import annotations

import base64
import csv
import email
import io
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger('apps.deals')

NATIVE_PDF_MAX_PAGES = 100
NATIVE_PDF_MAX_MB = 30
CHUNK_CHARS = 160_000      # ~40K tokens per digest call
MAX_TEXT_CHARS = 1_600_000  # ~10 chunks; anything beyond is truncated and flagged
XLSX_MAX_ROWS = 400        # per sheet

IMAGE_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}
ACCEPTED = ['pdf', 'docx', 'doc', 'xlsx', 'xlsm', 'xls', 'csv', 'pptx', 'txt', 'md', 'json', 'html', 'htm', 'eml', 'rtf',
            *IMAGE_TYPES]


@dataclass
class Prepared:
    method: str                       # native-pdf | text | image
    blocks: list[list[dict]] = field(default_factory=list)  # one content list per digest call
    pages: int | None = None
    chars: int | None = None
    truncated: bool = False


def ext_of(name: str) -> str:
    return (name.rsplit('.', 1)[-1] if '.' in name else '').lower()


def prepare(name: str, data: bytes) -> Prepared:
    ext = ext_of(name)
    if ext in IMAGE_TYPES:
        return Prepared('image', [[{'type': 'image', 'source': {'type': 'base64', 'media_type': IMAGE_TYPES[ext],
                                                                 'data': base64.b64encode(data).decode()}}]])
    if ext == 'pdf':
        pages = None
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages = len(reader.pages)
        except Exception as e:  # unreadable / encrypted → still try native
            log.warning('pypdf could not open %s: %s', name, e)
            reader = None
        if (pages or 0) <= NATIVE_PDF_MAX_PAGES and len(data) <= NATIVE_PDF_MAX_MB * 1024 * 1024:
            return Prepared('native-pdf', [[{'type': 'document', 'source': {
                'type': 'base64', 'media_type': 'application/pdf', 'data': base64.b64encode(data).decode()},
                'title': name}]], pages=pages)
        text = _pdf_text(reader) if reader else ''
        p = _chunks(name, text)
        p.pages = pages
        return p
    return _chunks(name, to_text(name, ext, data))


def _pdf_text(reader) -> str:
    out = []
    for i, page in enumerate(reader.pages, 1):
        try:
            out.append(f'\n[page {i}]\n{page.extract_text() or ""}')
        except Exception:
            out.append(f'\n[page {i}] (unreadable)')
    return ''.join(out)


def _chunks(name: str, text: str) -> Prepared:
    text = re.sub(r'[ \t]+', ' ', text or '').strip()
    truncated = len(text) > MAX_TEXT_CHARS
    text = text[:MAX_TEXT_CHARS]
    parts = [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)] or ['(no extractable text)']
    blocks = [[{'type': 'text', 'text': f'<file name="{name}" part="{n}/{len(parts)}">\n{part}\n</file>'}]
              for n, part in enumerate(parts, 1)]
    return Prepared('text', blocks, chars=len(text), truncated=truncated)


def to_text(name: str, ext: str, data: bytes) -> str:
    if ext == 'docx':
        import docx
        d = docx.Document(io.BytesIO(data))
        out = [p.text for p in d.paragraphs if p.text.strip()]
        for t in d.tables:
            for row in t.rows:
                out.append(' | '.join(c.text.strip() for c in row.cells))
        return '\n'.join(out)
    if ext in ('xlsx', 'xlsm'):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        out = []
        for ws in wb.worksheets:
            out.append(f'\n## Sheet: {ws.title}')
            for n, row in enumerate(ws.iter_rows(values_only=True)):
                if n >= XLSX_MAX_ROWS:
                    out.append(f'… (rows beyond {XLSX_MAX_ROWS} omitted)')
                    break
                cells = ['' if v is None else str(v) for v in row]
                if any(cells):
                    out.append(' | '.join(cells).rstrip(' |'))
        return '\n'.join(out)
    if ext == 'pptx':
        from pptx import Presentation
        prs = Presentation(io.BytesIO(data))
        out = []
        for i, slide in enumerate(prs.slides, 1):
            out.append(f'\n[slide {i}]')
            for shp in slide.shapes:
                if getattr(shp, 'has_text_frame', False) and shp.text_frame.text.strip():
                    out.append(shp.text_frame.text)
                if getattr(shp, 'has_table', False):
                    for row in shp.table.rows:
                        out.append(' | '.join(c.text for c in row.cells))
        return '\n'.join(out)
    if ext == 'csv':
        rows = csv.reader(io.StringIO(_decode(data)))
        return '\n'.join(' | '.join(r) for r in rows)
    if ext in ('html', 'htm'):
        t = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', _decode(data), flags=re.S | re.I)
        return re.sub(r'<[^>]+>', ' ', t)
    if ext == 'eml':
        msg = email.message_from_bytes(data)
        parts = [f'From: {msg.get("from")}\nTo: {msg.get("to")}\nDate: {msg.get("date")}\nSubject: {msg.get("subject")}']
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                parts.append(_decode(part.get_payload(decode=True) or b''))
        return '\n\n'.join(parts)
    if ext in ('doc', 'xls', 'rtf'):
        # legacy binary formats: keep printable runs (good enough for most memos); ask for docx/xlsx for fidelity
        return ' '.join(re.findall(r'[\x20-\x7E]{4,}', data.decode('latin-1')))
    return _decode(data)


def _decode(b: bytes) -> str:
    for enc in ('utf-8', 'utf-16', 'latin-1'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode('utf-8', 'ignore')
