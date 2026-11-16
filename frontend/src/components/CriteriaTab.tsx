import type { DealDetail } from '../types'

/* "How this deal was scored": which criteria came from the framework as standard, which were tailored to this deal's
   sector, which defaults were swapped out, and how the section weights moved from the framework defaults (and why). */

const norm = (s: string) => s.toLowerCase().replace(/\(.*?\)/g, ' ').replace(/[^a-z0-9 ]+/g, ' ').split(/\s+/).filter(w => w.length > 2 && !['and', 'the', 'for', 'with', 'per', 'vs'].includes(w))
function same(a: string, b: string) {
  const x = norm(a), y = norm(b)
  if (!x.length || !y.length) return false
  if (x.join(' ') === y.join(' ')) return true
  const hit = x.filter(w => y.some(v => v.startsWith(w.slice(0, 5)) || w.startsWith(v.slice(0, 5)))).length
  return hit / Math.min(x.length, y.length) >= 0.6
}
const col = (s: number | null | undefined) => (s == null ? 'var(--subtle)' : s >= 6.5 ? 'var(--green)' : s >= 5 ? 'var(--gold)' : 'var(--red)')
const FIT = (f: number | null) => (f == null ? 'Not judged' : f >= 1.5 ? 'Strong fit' : f >= 0.5 ? 'Fits' : f > -0.5 ? 'Neutral' : f > -1.5 ? 'Against' : 'Strongly against')
const PAL = ['#0f2347', '#b7862c', '#2752a8', '#1f7a4c', '#8a5a14', '#6b4fa0']

export default function CriteriaTab({ d }: { d: DealDetail }) {
  const sc = d.scorecard, fb = d.criteria_basis
  if (!sc?.sections?.length || !fb) {
    return <div className="panel"><div className="note">{d.legacy ? 'Ledger deal: headline scores only — re-analyse to see the criteria used.' : 'Not scored yet — the criteria appear here after the analysis.'}</div></div>
  }
  const wr = sc.weights_rationale ?? []
  const secs = sc.sections.map(s => {
    const def = fb.sections.find(x => same(x.name, s.name))
    const used = s.criteria.map(c => ({ ...c, std: !!def?.criteria.some(n => same(n, c.name)) }))
    const dropped = (def?.criteria ?? []).filter(n => !s.criteria.some(c => same(n, c.name)))
    const why = wr.find(w => same(w.section, s.name))
    return { s, def, used, dropped, why, dw: def?.weight ?? why?.default ?? s.weight }
  })
  const nStd = secs.reduce((a, x) => a + x.used.filter(c => c.std).length, 0)
  const nAll = secs.reduce((a, x) => a + x.used.length, 0)
  const moved = secs.filter(x => Math.abs(x.s.weight - x.dw) >= 0.5).length
  const sector = [d.sector, d.sub_sector].filter(Boolean).join(' → ')

  const Bar = ({ label, vals }: { label: string; vals: number[] }) => (
    <div className="cr-bar"><span className="cr-bar-l">{label}</span>
      <div className="cr-bar-t">{vals.map((v, i) => v > 0 && <div key={i} style={{ width: `${v}%`, background: PAL[i % PAL.length] }} title={`${secs[i].s.name} ${v}%`}><span>{v >= 8 ? v : ''}</span></div>)}</div>
    </div>
  )

  return (
    <div className="cr">
      <div className="panel cr-head">
        <div className="cr-eyebrow">How this deal was scored</div>
        <div className="cr-title">{fb.name} <span className="note">framework v{fb.version}</span></div>
        {sector && <div className="cr-sector">Sector: <b>{sector}</b>{fb.sector_block && <> · sector playbook: <b>{fb.sector_block}</b></>}</div>}
        <div className="cr-chips">
          <span className="cr-chip"><b>{nAll}</b> criteria scored</span>
          <span className="cr-chip std"><b>{nStd}</b> standard</span>
          <span className="cr-chip tl"><b>{nAll - nStd}</b> tailored to this deal</span>
          <span className="cr-chip"><b>{moved}</b> section weight{moved === 1 ? '' : 's'} moved</span>
        </div>
        <p className="cr-intro">The five sections are the same for every {fb.key === 'vg' ? 'venture' : 'buyout and CV'} deal. Inside each one, <b>standard</b> criteria come
          straight from the framework; <b>tailored</b> criteria were chosen for this deal's sector because they matter more here than the
          default they replace. {fb.flex ? 'Section weights start from the framework defaults and move with the deal; each move is explained.' : 'Section weights are fixed for this framework.'}</p>
      </div>

      <div className="panel">
        <div className="panel-t">Section weights — framework default vs this deal</div>
        <Bar label="Default" vals={secs.map(x => x.dw)} />
        <Bar label="This deal" vals={secs.map(x => x.s.weight)} />
        <div className="cr-legend">{secs.map((x, i) => {
          const dlt = Math.round((x.s.weight - x.dw) * 10) / 10
          return <span key={i}><i style={{ background: PAL[i % PAL.length] }} />{x.s.name} <b className="mono">{x.s.weight}%</b>{dlt !== 0 && <em className={dlt > 0 ? 'up' : 'dn'}>{dlt > 0 ? '+' : ''}{dlt}</em>}</span>
        })}</div>
      </div>

      {secs.map((x, i) => (
        <div className="panel cr-sec" key={x.s.name} style={{ borderLeftColor: PAL[i % PAL.length] }}>
          <div className="cr-sec-h">
            <span className="cr-n" style={{ background: PAL[i % PAL.length] }}>{i + 1}</span>
            <div className="cr-sec-t"><div className="t">{x.s.name}</div>{x.def?.description && <div className="note">{x.def.description}</div>}</div>
            <div className="cr-w"><span className="note">weight</span> {x.dw !== x.s.weight && <s className="mono">{x.dw}%</s>} <b className="mono">{x.s.weight}%</b></div>
            <div className="cr-score mono" style={{ color: col(x.s.score) }}>{x.s.score?.toFixed(2) ?? '—'}</div>
          </div>
          {x.why && x.dw !== x.s.weight && <div className="cr-why"><b>Why the weight moved:</b> {x.why.why}</div>}
          <div className="cr-list">
            {x.used.map((c, j) => (
              <div className="cr-row" key={j}>
                <span className={`cr-tag ${c.std ? 'std' : 'tl'}`}>{c.std ? 'Standard' : 'Tailored'}</span>
                <div className="cr-main"><div className="cr-name">{c.name}</div>{c.rationale && <div className="cr-what">{c.rationale}</div>}</div>
                <span className="cr-pill mono" style={{ color: col(c.score), borderColor: col(c.score) }}>{c.score == null ? 'n/d' : c.score.toFixed(1)}</span>
              </div>
            ))}
          </div>
          {x.dropped.length > 0 && <div className="cr-dropped">Framework defaults not used for this deal: {x.dropped.map((n, j) => <span key={j}>{n}</span>)}</div>}
        </div>
      ))}
      {sc.house && sc.house.items.length > 0 && (
        <div className="panel hp-deal">
          <div className="panel-t">ADCG preferences — how this deal fits</div>
          <div className="hp-sum">
            <span>Framework score <b className="mono">{sc.house.framework_overall.toFixed(2)}</b></span>
            <span className={`hp-adj ${sc.house.adjustment > 0 ? 'up' : sc.house.adjustment < 0 ? 'dn' : ''}`}>ADCG preferences <b className="mono">{sc.house.adjustment >= 0 ? '+' : ''}{sc.house.adjustment.toFixed(2)}</b></span>
            <span>Final score <b className="mono">{(d.adcg_score ?? 0).toFixed(2)}</b></span>
            <span className="note">capped at ±{sc.house.max_adjust}</span>
          </div>
          {sc.house.items.map(it => (
            <div className="cr-row" key={it.id}>
              <span className={`hp-fit f${it.fit == null ? 'na' : it.fit > 0 ? 'p' : it.fit < 0 ? 'n' : 'z'}`}>{FIT(it.fit)}</span>
              <div className="cr-main"><div className="cr-name">{it.title} <span className="note">· {it.importance} importance</span></div>{it.why && <div className="cr-what">{it.why}</div>}</div>
            </div>
          ))}
        </div>
      )}
      <div className="note" style={{ margin: '4px 2px 20px' }}>Disagree with a criterion or a weight? Add a comment in the IC memo and press <b>Revise memo with your comments</b> — it re-scores without re-running the research.</div>
    </div>
  )
}
