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
  /* memo structure (Nov-26): part banners, history + plan table, ADCG independent review */
  .part-h{display:flex;align-items:baseline;gap:12px;margin:42px 0 6px;padding:12px 0 8px;border-top:2px solid #1a1c1a;border-bottom:1px solid #d9d4c7;font-family:ui-monospace,monospace;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#7a2230;font-weight:700}
  .part-h span{font-size:22px;letter-spacing:0;color:#1a1c1a}
  h2.part{border-top:2px solid #1a1c1a;padding-top:14px;margin-top:42px}
  table.bp th.plan,table.bp td.plan{background:#f6efdc}
  table.bp th.plan{color:#7a5a12}
  .indep{background:#eef3fa;border:1px solid #cfdcf3;border-left:4px solid #2752a8;border-radius:0 8px 8px 0;padding:12px 16px;margin:14px 0}
  .indep>b:first-child{display:block;font-family:ui-monospace,monospace;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:#2752a8;margin-bottom:4px}
  @media print{.part-h{break-after:avoid}.indep,table.bp{break-inside:avoid}}
  /* Part III score panel (deal lead, 18-Nov-26) */
  .sc-head{display:grid;grid-template-columns:200px 1fr;gap:0;border:1px solid #d9d4c7;border-radius:8px;overflow:hidden;margin:16px 0 22px;background:#fffdf8}
  .sh-score{background:#1a1c1a;color:#f6f4ee;padding:18px 18px 16px;display:flex;flex-direction:column;justify-content:center;gap:2px}
  .sh-score span{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.14em;text-transform:uppercase;opacity:.75}
  .sh-score b{font-size:46px;line-height:1;font-variant-numeric:tabular-nums;font-weight:700}
  .sh-score em{font-style:normal;font-family:ui-monospace,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#e3c27a}
  .sh-side{padding:10px 18px;display:flex;flex-direction:column;justify-content:center}
  .sh-row{display:grid;grid-template-columns:190px 1fr auto;gap:10px;align-items:baseline;padding:7px 0;border-top:1px dashed #e4dfd2;font-size:13.5px}
  .sh-row:first-child{border-top:0}
  .sh-row span{font-family:ui-monospace,monospace;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:#8a877d}
  .sh-row em{font-style:normal;font-size:12px;color:#3d423d}
  .sh-tier{background:#7a2230;color:#fff!important;border-radius:3px;padding:1px 7px;font-family:ui-monospace,monospace;font-size:10.5px!important;letter-spacing:.05em}
  .overstated{border:1px solid #ebcdbf;border-left:4px solid #b8892c;background:#fdf8ee;border-radius:0 8px 8px 0;padding:10px 16px;margin:12px 0}
  .overstated>b:first-child{display:block;font-family:ui-monospace,monospace;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:#8a5a12;margin-bottom:4px}
  .overstated ol{margin:4px 0;padding-left:20px}.overstated li{margin:5px 0}
  @media(max-width:720px){.sc-head{grid-template-columns:1fr}.sh-row{grid-template-columns:1fr}}
  @media print{.sc-head,.overstated{break-inside:avoid}}
  /* figures redrawn from the materials (deal lead, 18-Nov-26) */
  figure.fig{margin:18px 0 20px;padding:14px 16px 10px;background:#fffdf8;border:1px solid #d9d4c7;border-radius:8px}
  figure.fig svg{display:block;width:100%;height:auto;max-height:340px}
  figure.fig figcaption{font-size:13px;color:#3d423d;margin-top:8px;line-height:1.45}
  figure.fig figcaption b{color:#1a1c1a}
  @media print{figure.fig{break-inside:avoid}}
  @media(max-width:720px){.su{grid-template-columns:1fr}.kf{grid-template-columns:1fr 1fr}}
  @media print{.su,.kf{break-inside:avoid}.kf{grid-template-columns:repeat(4,1fr)}.su{grid-template-columns:1fr 1fr}}
</style>"""


def patch(html: str) -> str:
    if not html or 'id="memo-css-patch"' in html:
        return html
    return re.sub(r'</head>', PATCH + '\n</head>', html, count=1, flags=re.I) if re.search(r'</head>', html, re.I) \
        else PATCH + html
