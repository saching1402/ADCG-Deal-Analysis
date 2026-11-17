"""IC memo → PDF exactly as the preview looks (paper colour, cards, charts), rendered by headless Chromium on the server.

The browser's own Print / Save as PDF dropped the paper colour (the shell's print CSS set a white body and browsers skip
backgrounds by default). Here the colours are forced on and the page margin is painted the same paper colour.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from django.conf import settings

PAPER = '#f6f4ee'
PDF_CSS = f"""<style id="pdf-export">
  @page {{ size: A4; margin: 13mm 0 14mm; background: {PAPER}; }}
  html, body {{ background: {PAPER} !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
  * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
  @media print {{
    body {{ background: {PAPER} !important; }}
    .wrap {{ max-width: 100% !important; padding: 1mm 15mm 2mm !important; }}
  }}
</style>"""


class PdfError(RuntimeError):
    pass


def chromium() -> str:
    for c in (getattr(settings, 'CHROMIUM_PATH', ''), os.environ.get('CHROMIUM_PATH', ''),
              'chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable'):
        p = c and (c if os.path.isabs(c) and os.path.exists(c) else shutil.which(c))
        if p:
            return p
    raise PdfError('PDF export is not available on this server (Chromium is not installed).')


def prepare(html: str) -> str:
    """The memo with the PDF colour/page rules added last so they win (older memos carry a white print body and a
    12 mm page margin — both neutralised)."""
    html = re.sub(r'@page\s*\{[^}]*\}', '', html)
    return re.sub(r'</head>', PDF_CSS + '\n</head>', html, count=1, flags=re.I) if re.search(r'</head>', html, re.I) \
        else PDF_CSS + html


def render(html: str, timeout: int = 90) -> bytes:
    exe = chromium()
    with tempfile.TemporaryDirectory(prefix='memo-pdf-') as tmp:
        src, out = os.path.join(tmp, 'memo.html'), os.path.join(tmp, 'memo.pdf')
        with open(src, 'w', encoding='utf-8') as fh:
            fh.write(prepare(html))
        cmd = [exe, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--hide-scrollbars',
               '--no-first-run', '--no-default-browser-check', f'--user-data-dir={os.path.join(tmp, "profile")}',
               '--no-pdf-header-footer', '--print-to-pdf-no-header', '--run-all-compositor-stages-before-draw',
               '--virtual-time-budget=10000', f'--print-to-pdf={out}', 'file://' + src]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise PdfError('PDF rendering timed out') from e
        if not os.path.exists(out) or os.path.getsize(out) < 500:
            raise PdfError('PDF rendering failed: ' + (r.stderr or b'').decode(errors='ignore')[-400:])
        with open(out, 'rb') as fh:
            return fh.read()


def filename(deal_name: str, number: int | None, ext: str = 'pdf') -> str:
    """'KSFM Solutions – Mindari IC memo v3.pdf' — always the asset's name."""
    name = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', deal_name or 'Deal').strip() or 'Deal'
    return f'{name} – Mindari IC memo' + (f' v{number}' if number else '') + f'.{ext}'
