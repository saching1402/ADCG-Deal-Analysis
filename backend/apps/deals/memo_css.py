"""Memo CSS that also applies to memos generated before a style change (added at read time: preview + PDF)."""
import re

PATCH = """<style id="memo-css-patch">
  /* source pills: small and quiet so they never interrupt reading (deal lead, Nov-26) */
  .src{font-size:7.5px!important;font-weight:600!important;letter-spacing:.03em!important;padding:0 4px!important;
    border-radius:2px!important;vertical-align:1.5px!important;opacity:.82;line-height:1.5}
  .ref{font-family:ui-monospace,monospace;font-size:7.5px;color:#8a877d;vertical-align:1.5px;white-space:nowrap;margin-left:2px}
  /* sources & uses */
  .su{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
  .su-col{background:#fffdf8;border:1px solid #d9d4c7;border-radius:8px;padding:12px 16px}
  .su-h{font-family:ui-monospace,monospace;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:#7a2230;font-weight:700;margin-bottom:6px}
  .su-row{display:grid;grid-template-columns:1fr auto 52px;gap:10px;padding:6px 0;border-top:1px dashed #e4dfd2;font-size:14px;align-items:baseline}
  .su-row:first-of-type{border-top:0}.su-row b{font-variant-numeric:tabular-nums}
  .su-row em{font-style:normal;color:#8a877d;font-size:12px;text-align:right}
  .su-row.tot{border-top:1.5px solid #1a1c1a;font-weight:700}
  /* key facts grid */
  .kf{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#d9d4c7;border:1px solid #d9d4c7;border-radius:8px;overflow:hidden;margin:14px 0}
  .kf>div{background:#fffdf8;padding:11px 13px;display:flex;flex-direction:column;gap:2px}
  .kf span{font-family:ui-monospace,monospace;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:#8a877d}
  .kf b{font-size:17px;font-variant-numeric:tabular-nums}.kf em{font-style:normal;font-size:12px;color:#3d423d}
  @media(max-width:720px){.su{grid-template-columns:1fr}.kf{grid-template-columns:1fr 1fr}}
  @media print{.su,.kf{break-inside:avoid}.kf{grid-template-columns:repeat(4,1fr)}.su{grid-template-columns:1fr 1fr}}
</style>"""


def patch(html: str) -> str:
    if not html or 'id="memo-css-patch"' in html:
        return html
    return re.sub(r'</head>', PATCH + '\n</head>', html, count=1, flags=re.I) if re.search(r'</head>', html, re.I) \
        else PATCH + html
