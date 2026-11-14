"""
Turn an uploaded deal file into something Claude can read — and prove it can be read.

Two steps per file:

1. ``inspect(name, data)`` — fast, local, no API cost; runs at upload. Opens the file, counts pages / sheets /
   slides, measures the text layer, detects encryption, scanned pages, formula-only spreadsheets, corrupt files.
   Returns a ``check`` dict shown in the Files tab: ``ok`` | ``warn`` | ``block`` + plain-English notes.

2. ``prepare(name, data)`` — builds the digest requests ("parts"). Every page is covered:
   * PDF (any size) → decrypted if it only has an owner password → split into native-PDF parts of
     ≤ ``PART_PAGES`` pages and ≤ ``PART_MB`` MB, so Claude sees text, tables, charts AND scanned pages.
     A single page too heavy for a part is rasterised to JPEG and sent as an image.
   * PowerPoint / legacy Word / RTF → converted to PDF with LibreOffice (keeps charts & layout) → as PDF.
   * Excel → every sheet, every used row (cached values; workbooks saved without values are recalculated
     through LibreOffice first) → text parts. Legacy .xls → converted to .xlsx first.
   * Word (.docx) → paragraphs + tables in document order.
   * Images → image blocks. CSV / text / HTML / email → text.
   A part whose digest comes back empty or "can't read" is retried by ``fallback_blocks`` (page images).
"""
from __future__ import annotations

import base64
import csv
import email
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

log = logging.getLogger('apps.deals')

PART_PAGES = 40            # pages per native-PDF digest call (Claude accepts up to 100; smaller = more thorough)
PART_MB = 18               # bytes per native-PDF part (API request limit is 32 MB incl. base64 overhead)
IMG_DPI = 110              # rasterisation DPI for heavy / unreadable pages
IMG_PER_CALL = 20          # page images per fallback call
CHUNK_CHARS = 150_000      # ~40K tokens per text digest call
MAX_TEXT_CHARS = 3_000_000  # hard cap (~20 parts); flagged as a warning if hit
XLSX_MAX_ROWS = 20_000     # per sheet — effectively "all"; long sheets are split across parts
SOFFICE_TIMEOUT = 240

IMAGE_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}
OFFICE_TO_PDF = {'pptx', 'ppt', 'doc', 'rtf', 'odt', 'odp', 'key'}
ACCEPTED = ['pdf', 'docx', 'doc', 'rtf', 'odt', 'xlsx', 'xlsm', 'xls', 'ods', 'csv', 'pptx', 'ppt', 'odp',
            'txt', 'md', 'json', 'html', 'htm', 'eml', *IMAGE_TYPES]


class Unreadable(ValueError):
    """The file cannot be read at all (corrupt, password-protected, empty)."""


@dataclass
class Part:
    label: str                     # "pages 1–40", "sheet P&L rows 1–900", "image"
    blocks: list[dict]             # content blocks for one digest call
    pages: tuple[int, int] | None = None  # 1-based inclusive page range for PDFs (enables image fallback)


@dataclass
class Prepared:
    method: str                    # native-pdf | text | image | converted-pdf
    parts: list[Part] = field(default_factory=list)
    pages: int | None = None
    chars: int | None = None
    pdf: bytes | None = None       # the (decrypted / converted) PDF, for image fallback
    notes: list[str] = field(default_factory=list)

    @property
    def blocks(self):  # backwards compatibility with tests
        return [p.blocks for p in self.parts]


def ext_of(name: str) -> str:
    return (name.rsplit('.', 1)[-1] if '.' in name else '').lower()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# ── helpers: PDF ──────────────────────────────────────────────────────────────
def _open_pdf(data: bytes):
    """Return (reader, plain_bytes). Removes owner-password / copy-protection; raises Unreadable for open passwords."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError
    if not data.lstrip()[:5].startswith(b'%PDF'):
        if data[:4] == b'PK\x03\x04' or data[:8] == OLE_MAGIC:
            raise Unreadable('This is not a PDF — it looks like an Office file saved with a .pdf name. Upload it with its real extension.')
        raise Unreadable('This is not a valid PDF (the file has no PDF header). Re-download or re-export it.')
    try:
        reader = PdfReader(io.BytesIO(data))
    except DependencyError as e:
        raise Unreadable(f'This PDF uses encryption the server cannot open yet ({e}).')
    except Exception as e:
        raise Unreadable(f'The PDF structure could not be read ({str(e)[:120]}). Re-export it (Print → Save as PDF) and upload again.')
    if reader.is_encrypted:
        try:
            ok = reader.decrypt('')
        except DependencyError as e:
            raise Unreadable(f'This PDF uses encryption the server cannot open yet ({e}).')
        except Exception:
            ok = 0
        if not ok:
            raise Unreadable('The PDF needs a password to open. Upload an unlocked copy (open it with the password, then Print → Save as PDF).')
        w = PdfWriter()
        try:
            for p in reader.pages:
                w.add_page(p)
            buf = io.BytesIO()
            w.write(buf)
        except (FileNotDecryptedError, PdfReadError) as e:
            raise Unreadable(f'The PDF is protected and could not be unlocked ({str(e)[:120]}). Upload an unlocked copy.')
        data = buf.getvalue()
        reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) == 0:
        raise Unreadable('The PDF has no pages.')
    return reader, data


def _page_texts(reader) -> list[str]:
    out = []
    for p in reader.pages:
        try:
            out.append(p.extract_text() or '')
        except Exception:
            out.append('')
    return out


def _subset(reader, start: int, end: int) -> bytes:
    """Pages start..end (0-based, exclusive end) as a standalone PDF."""
    from pypdf import PdfWriter
    w = PdfWriter()
    for i in range(start, end):
        w.add_page(reader.pages[i])
    try:
        w.compress_identical_objects()
    except Exception:
        pass
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def render_pages(pdf: bytes, first: int, last: int, dpi: int = IMG_DPI) -> list[bytes]:
    """Rasterise 1-based pages first..last to JPEGs with poppler's pdftoppm."""
    if not shutil.which('pdftoppm'):
        raise Unreadable('Page rendering is unavailable on this server (poppler-utils missing).')
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, 'in.pdf')
        with open(src, 'wb') as fh:
            fh.write(pdf)
        subprocess.run(['pdftoppm', '-jpeg', '-jpegopt', 'quality=72', '-r', str(dpi), '-f', str(first), '-l', str(last),
                        src, os.path.join(td, 'p')], check=True, capture_output=True, timeout=600)
        files = sorted(f for f in os.listdir(td) if f.startswith('p') and f.endswith('.jpg'))
        return [open(os.path.join(td, f), 'rb').read() for f in files]


def _image_block(jpg: bytes) -> dict:
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64(jpg)}}


def fallback_blocks(prep: Prepared, part: Part) -> list[list[dict]]:
    """Page images for a PDF part whose native read failed (one list per call, ≤ IMG_PER_CALL pages)."""
    if not prep.pdf or not part.pages:
        return []
    a, b = part.pages
    calls = []
    for s in range(a, b + 1, IMG_PER_CALL):
        e = min(b, s + IMG_PER_CALL - 1)
        imgs = render_pages(prep.pdf, s, e)
        calls.append([{'type': 'text', 'text': f'Pages {s}–{e} of the document, as images:'}] + [_image_block(i) for i in imgs])
    return calls


def _pdf_parts(name: str, data: bytes, method: str = 'native-pdf') -> Prepared:
    reader, plain = _open_pdf(data)
    n = len(reader.pages)
    prep = Prepared(method, pages=n, pdf=plain)
    limit = PART_MB * 1024 * 1024
    start = 0
    while start < n:
        end = min(n, start + PART_PAGES)
        chunk = _subset(reader, start, end)
        while len(chunk) > limit and end - start > 1:  # shrink until it fits
            end = start + max(1, (end - start) // 2)
            chunk = _subset(reader, start, end)
        label = f'pages {start + 1}–{end}' if end - start > 1 else f'page {start + 1}'
        if len(chunk) > limit:  # one enormous page (huge scan / embedded image) → render it
            jpg = render_pages(plain, start + 1, start + 1)
            prep.parts.append(Part(label + ' (rendered)', [_image_block(j) for j in jpg], (start + 1, end)))
            prep.notes.append(f'{label} is very large; read as an image.')
        else:
            prep.parts.append(Part(label, [{'type': 'document', 'title': f'{name} — {label}',
                                             'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': b64(chunk)}}],
                                   (start + 1, end)))
        start = end
    return prep


# ── helpers: protected / mislabelled Office files ────────────────────────────
OLE_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
OOXML = {'xlsx', 'xlsm', 'docx', 'pptx'}
LEGACY_OF = {'xlsx': 'xls', 'xlsm': 'xls', 'docx': 'doc', 'pptx': 'ppt'}
DEFAULT_PASSWORDS = ['VelvetSweatshop', '']  # Excel's built-in "encrypt without asking" password; empty password


def unwrap_office(name: str, data: bytes) -> tuple[str, bytes, list[str]]:
    """Modern Office files are ZIPs. An OLE container under a .xlsx/.docx/.pptx name is either an ENCRYPTED file
    (decrypt with Excel's default password when it opens without asking) or a legacy binary saved with the new
    extension. Returns (effective_ext, bytes, notes); raises Unreadable with the real reason."""
    ext = ext_of(name)
    if ext not in OOXML or data[:8] != OLE_MAGIC:
        return ext, data, []
    import msoffcrypto
    import olefile
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
        streams = ['/'.join(s) for s in ole.listdir(streams=True, storages=True)]
    except Exception:
        streams = []
    if any('DRMEncrypted' in s or 'DRMContent' in s for s in streams):
        raise Unreadable('The file is protected by a company sensitivity label / rights management (IRM), which only your '
                         'Office account can open. Open it on your laptop and save an unprotected copy (or export to PDF), then upload that.')
    if 'EncryptedPackage' in streams or 'EncryptionInfo' in streams:
        for pw in DEFAULT_PASSWORDS:
            try:
                f = msoffcrypto.OfficeFile(io.BytesIO(data))
                f.load_key(password=pw)
                out = io.BytesIO()
                f.decrypt(out)
                return ext, out.getvalue(), ['File was encrypted without a password prompt; unlocked for reading.']
            except Exception:
                continue
        raise Unreadable('The file is password-protected. Open it on your laptop, remove the password (File → Info → Protect → '
                         'Encrypt with password → clear it) or save an unprotected copy, then upload that.')
    # not encrypted: a legacy binary file with a modern extension
    return LEGACY_OF[ext], data, [f'Legacy .{LEGACY_OF[ext]} file saved with a .{ext} name; converted before reading.']


# ── helpers: Office via LibreOffice ──────────────────────────────────────────
_LO_RECALC = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="ODFRecalcMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>
'''

def soffice_convert(data: bytes, ext: str, target: str) -> bytes:
    exe = shutil.which('soffice') or shutil.which('libreoffice')
    if not exe:
        raise Unreadable(f'.{ext} files need LibreOffice on the server to convert; upload a PDF or the modern format instead.')
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, f'in.{ext}')
        with open(src, 'wb') as fh:
            fh.write(data)
        os.makedirs(os.path.join(td, 'profile', 'user'), exist_ok=True)
        with open(os.path.join(td, 'profile', 'user', 'registrymodifications.xcu'), 'w') as fh:
            fh.write(_LO_RECALC)  # always recalculate formulas on load (OOXML + ODF)
        try:
            subprocess.run([exe, '--headless', '--norestore', f'-env:UserInstallation=file://{td}/profile',
                            '--convert-to', target, '--outdir', os.path.join(td, 'out'), src], check=True, capture_output=True, timeout=SOFFICE_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise Unreadable(f'Converting the .{ext} file timed out.')
        except subprocess.CalledProcessError as e:
            raise Unreadable(f'The .{ext} file could not be converted ({(e.stderr or b"").decode()[:160]}).')
        out = os.path.join(td, 'out', f'in.{target.split(":")[0]}')
        if not os.path.exists(out):
            raise Unreadable(f'The .{ext} file could not be converted (no output).')
        return open(out, 'rb').read()


# ── helpers: text ─────────────────────────────────────────────────────────────
def _decode(b: bytes) -> str:
    if b[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return b.decode('utf-16', 'ignore')
    for enc in ('utf-8', 'cp1252', 'latin-1'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode('utf-8', 'ignore')


def _text_parts(name: str, text: str, unit: str = 'part') -> Prepared:
    text = re.sub(r'[ \t]+', ' ', text or '').strip()
    prep = Prepared('text', chars=len(text))
    if len(text) > MAX_TEXT_CHARS:
        prep.notes.append(f'Very long file: only the first {MAX_TEXT_CHARS // 1000:,}K characters were read.')
        text = text[:MAX_TEXT_CHARS]
    chunks = [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)]
    for k, ch in enumerate(chunks, 1):
        label = f'{unit} {k} of {len(chunks)}' if len(chunks) > 1 else 'full text'
        prep.parts.append(Part(label, [{'type': 'text', 'text': f'<file name="{name}" {unit}="{k}/{len(chunks)}">\n{ch}\n</file>'}]))
    return prep


def _xlsx_text(data: bytes) -> tuple[str, dict]:
    import openpyxl
    stats = {'sheets': 0, 'rows': 0, 'formula_cells': 0, 'empty_formulas': 0}
    wb_v = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    try:
        wb_f = openpyxl.load_workbook(io.BytesIO(data), data_only=False, read_only=True)
    except Exception:
        wb_f = None
    out = []
    for ws in wb_v.worksheets:
        stats['sheets'] += 1
        state = getattr(ws, 'sheet_state', 'visible')
        out.append(f'\n## Sheet: {ws.title}' + (' (hidden)' if state != 'visible' else ''))
        fws = wb_f[ws.title] if wb_f is not None else None
        frows = fws.iter_rows(values_only=True) if fws is not None else None
        for n, row in enumerate(ws.iter_rows(values_only=True)):
            frow = next(frows, None) if frows is not None else None
            if n >= XLSX_MAX_ROWS:
                out.append(f'… (rows beyond {XLSX_MAX_ROWS:,} omitted)')
                break
            cells = []
            for j, v in enumerate(row):
                f = frow[j] if frow is not None and j < len(frow) else None
                if isinstance(f, str) and f.startswith('='):
                    stats['formula_cells'] += 1
                    if v is None:
                        stats['empty_formulas'] += 1
                cells.append('' if v is None else (f'{v:.6g}' if isinstance(v, float) else str(v)))
            while cells and cells[-1] == '':
                cells.pop()
            if any(cells):
                stats['rows'] += 1
                out.append(f'r{n + 1}: ' + ' | '.join(cells))
    return '\n'.join(out), stats


def _docx_text(data: bytes) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(io.BytesIO(data))
    out = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit('}', 1)[-1]
        if tag == 'p':
            t = Paragraph(child, d).text
            if t.strip():
                out.append(t)
        elif tag == 'tbl':
            for row in Table(child, d).rows:
                out.append(' | '.join(c.text.strip() for c in row.cells))
    for s in d.sections:  # headers/footers often carry dates and confidentiality
        for p in s.header.paragraphs:
            if p.text.strip():
                out.insert(0, f'[header] {p.text}')
    return '\n'.join(out)


def _html_text(s: str) -> str:
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<br\s*/?>|</p>|</tr>|</h\d>', '\n', s, flags=re.I)
    return re.sub(r'<[^>]+>', ' ', s)


# ── public API ────────────────────────────────────────────────────────────────
def prepare(name: str, data: bytes) -> Prepared:
    if not data:
        raise Unreadable('The file is empty (0 bytes).')
    ext, data, pre_notes = unwrap_office(name, data)
    prep = _prepare(name, ext, data)
    prep.notes = pre_notes + prep.notes
    return prep


def _prepare(name: str, ext: str, data: bytes) -> Prepared:
    if ext in IMAGE_TYPES:
        return Prepared('image', [Part('image', [{'type': 'image', 'source': {'type': 'base64', 'media_type': IMAGE_TYPES[ext], 'data': b64(data)}}])])
    if ext == 'pdf':
        return _pdf_parts(name, data)
    if ext in OFFICE_TO_PDF or ext == 'pptx':
        pdf = soffice_convert(data, ext, 'pdf')
        p = _pdf_parts(name, pdf, 'converted-pdf')
        p.notes.append(f'.{ext} converted to PDF so charts and layout are read.')
        return p
    if ext in ('xlsx', 'xlsm', 'xls', 'ods'):
        if ext in ('xls', 'ods'):
            data = soffice_convert(data, ext, 'xlsx')
        text, st = _xlsx_text(data)
        notes = []
        if st['formula_cells'] and st['empty_formulas'] > 0.3 * st['formula_cells']:
            try:  # saved without calculated values → recalculate via LibreOffice
                text, st = _xlsx_text(soffice_convert(data, 'xlsx', 'xlsx:Calc MS Excel 2007 XML'))
                notes.append('Formulas had no saved values; workbook recalculated before reading.')
            except Unreadable as e:
                notes.append(f'Formulas had no saved values and recalculation failed ({e}).')
        p = _text_parts(name, text, 'part')
        p.notes += notes
        return p
    if ext == 'docx':
        return _text_parts(name, _docx_text(data))
    if ext == 'csv':
        return _text_parts(name, '\n'.join(' | '.join(r) for r in csv.reader(io.StringIO(_decode(data)))))
    if ext in ('html', 'htm'):
        return _text_parts(name, _html_text(_decode(data)))
    if ext == 'eml':
        msg = email.message_from_bytes(data)
        parts = [f'From: {msg.get("from")}\nTo: {msg.get("to")}\nDate: {msg.get("date")}\nSubject: {msg.get("subject")}']
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain':
                parts.append(_decode(part.get_payload(decode=True) or b''))
            elif ct == 'text/html':
                parts.append(_html_text(_decode(part.get_payload(decode=True) or b'')))
        return _text_parts(name, '\n\n'.join(parts))
    return _text_parts(name, _decode(data))


def inspect(name: str, data: bytes) -> dict:
    """Local readability check at upload. Never calls the API. {status ok|warn|block, summary, notes[], …}."""
    ext = ext_of(name)
    notes: list[str] = []
    res: dict = {'status': 'ok', 'notes': notes, 'kind': ext}
    try:
        if not data:
            raise Unreadable('The file is empty (0 bytes).')
        ext, data, pre = unwrap_office(name, data)
        notes += pre
        if ext == 'pdf':
            reader, _ = _open_pdf(data)
            n = len(reader.pages)
            texts = _page_texts(reader)
            text_pages = sum(1 for t in texts if len(t.strip()) > 80)
            res.update(pages=n, text_pages=text_pages)
            parts = max(1, -(-n // PART_PAGES))
            res['summary'] = f'{n} pages · read natively in {parts} part{"s" if parts > 1 else ""}'
            if text_pages < n:
                scanned = n - text_pages
                notes.append(f'{scanned} of {n} pages have little or no text layer (scanned or image pages) — Claude reads them visually.')
            from pypdf import PdfReader as _R
            if _R(io.BytesIO(data)).is_encrypted:
                notes.append('Copy/print protection removed for reading.')
        elif ext in ('xlsx', 'xlsm', 'xls', 'ods'):
            text, st = _xlsx_text(soffice_convert(data, ext, 'xlsx') if ext in ('xls', 'ods') else data)
            res.update(sheets=st['sheets'], rows=st['rows'], chars=len(text))
            res['summary'] = f'{st["sheets"]} sheet(s) · {st["rows"]:,} rows with data'
            if st['rows'] == 0:
                raise Unreadable('The workbook has no cell values.')
            if st['formula_cells'] and st['empty_formulas'] > 0.3 * st['formula_cells']:
                notes.append(f'{st["empty_formulas"]:,} formulas have no saved values — the workbook will be recalculated before reading.')
                res['status'] = 'warn'
        elif ext == 'docx':
            t = _docx_text(data)
            res.update(chars=len(t))
            res['summary'] = f'{len(t):,} characters of text'
            if len(t.strip()) < 200:
                notes.append('Very little text found — if this is a scanned document, upload it as a PDF.')
                res['status'] = 'warn'
        elif ext in ('pptx', 'ppt', 'odp', 'doc', 'rtf', 'odt', 'key'):
            res['summary'] = f'.{ext} → converted to PDF and read with charts and layout'
            if not (shutil.which('soffice') or shutil.which('libreoffice')):
                raise Unreadable(f'.{ext} needs LibreOffice on the server; upload a PDF instead.')
        elif ext in IMAGE_TYPES:
            res['summary'] = 'image · read visually'
        else:
            t = _decode(data)
            res.update(chars=len(t))
            res['summary'] = f'{len(t):,} characters of text'
            if len(t.strip()) < 50:
                raise Unreadable('The file has no readable text.')
    except Unreadable as e:
        res['status'] = 'block'
        res['summary'] = str(e)
    except Exception as e:
        log.exception('inspect failed for %s', name)
        res['status'] = 'block'
        res['summary'] = (f'The file could not be opened ({type(e).__name__}: {str(e)[:140]}). If it opens on your laptop, '
                          'save a fresh copy (File → Save As) and upload that, and send this message to support.')
    if notes and res['status'] == 'ok':
        res['status'] = 'ok'  # informational notes only
    return res


# ── digest quality check ─────────────────────────────────────────────────────
_FAIL = re.compile(
    r"(unable|cannot|can't|could not|couldn't|not able) to (read|access|extract|view|open|see|process)"
    r"|no (readable|extractable|legible|visible) (text|content)"
    r"|(document|file|pdf|page|pages|content) (is|are|appears to be|appear to be|seems to be) (blank|empty|unreadable|illegible|corrupt)"
    r"|(blank|empty) (document|file|pages?)\b"
    r"|no content (was )?(provided|available|found)", re.I)


def digest_ok(text: str, part: Part) -> tuple[bool, str]:
    """A digest is accepted only if it has real content and doesn't say the input was unreadable."""
    t = (text or '').strip()
    if len(t) < 300:
        return False, 'the summary came back empty'
    head = t[:1500]
    if _FAIL.search(head) and len(t) < 2500:
        return False, 'Claude reported it could not read this part'
    if not re.search(r'\d', t):
        return False, 'no figures or dates were extracted'
    return True, ''
