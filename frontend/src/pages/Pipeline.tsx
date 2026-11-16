import { useMemo, useRef, useState } from 'react'
import { errorText } from '../lib/api'
import { go } from '../lib/route'
import { ago, bandClass } from '../lib/format'
import type { DealRow } from '../types'
import { useDeals } from '../App'
import { StatusBadge, TrackBadge } from '../components/bits'
import { Logo, WithLogo } from '../components/Logo'
import CompanySearch from '../components/CompanySearch'

type SortKey = 'updated' | 'name' | 'score' | 'stage'

export default function Pipeline() {
  const [view, setView] = useState<'table' | 'board'>('table')
  const [q, setQ] = useState('')
  const [track, setTrack] = useState('')
  const [stage, setStage] = useState('')
  const [sort, setSort] = useState<{ k: SortKey; desc: boolean }>({ k: 'updated', desc: true })
  const { data, error, isLoading } = useDeals()

  const stageLabel = useMemo(() => Object.fromEntries((data?.meta.stages ?? []).map(s => [s.id, s.label])), [data])
  const stageOrder = useMemo(() => Object.fromEntries((data?.meta.stages ?? []).map((s, i) => [s.id, i])), [data])

  const rows = useMemo(() => {
    let r = data?.deals ?? []
    const needle = q.trim().toLowerCase()
    if (needle) r = r.filter(d => [d.name, d.sponsor, d.sector, d.sub_sector, d.one_liner, d.website].join(' ').toLowerCase().includes(needle))
    if (track) r = r.filter(d => (d.track_resolved || d.track) === track)
    if (stage) r = r.filter(d => d.stage === stage)
    const val = (d: DealRow): string | number => {
      switch (sort.k) {
        case 'name': return d.name.toLowerCase()
        case 'score': return d.adcg_score ?? -1
        case 'stage': return stageOrder[d.stage] ?? 0
        default: return d.updated_at
      }
    }
    return [...r].sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * (sort.desc ? -1 : 1) })
  }, [data, q, track, stage, sort, stageOrder])

  const all = data?.deals ?? []
  const scored = all.filter(d => d.adcg_score != null)
  const buy = scored.filter(d => d.track_resolved !== 'vg'), vg = scored.filter(d => d.track_resolved === 'vg')
  const avg = (xs: DealRow[]) => (xs.length ? xs.reduce((a, b) => a + (b.adcg_score ?? 0), 0) / xs.length : null)
  const inIc = all.filter(d => ['internal', 'pre_ic', 'final_ic'].includes(d.stage)).length
  const running = all.filter(d => d.status === 'queued' || d.status === 'running').length
  const best = [...scored].sort((a, b) => (b.adcg_score ?? 0) - (a.adcg_score ?? 0))[0]

  const th = (k: SortKey, label: string, cls = '') => (
    <th className={`${cls}${sort.k === k ? ' sact' : ''}`} onClick={() => setSort(s => ({ k, desc: s.k === k ? !s.desc : k !== 'name' }))}>
      {label}{sort.k === k ? (sort.desc ? ' ↓' : ' ↑') : ''}
    </th>
  )

  return (
    <div className="page">
      {data && !data.meta.api_key_set && (
        <div className="warn-box" style={{ marginBottom: 14 }}>ANTHROPIC_API_KEY is not set on the Railway service — deals and files can be added, but analyses won't run until it is.</div>
      )}

      <div className="kpi-row">
        <div className="kpi-card dk"><div className="kpi-lbl">Deals</div><div className="kpi-val">{all.length}</div><div className="kpi-sub">{scored.length} scored on ADCG</div></div>
        <div className="kpi-card"><div className="kpi-lbl">In IC process</div><div className="kpi-val">{inIc}</div><div className="kpi-sub">Internal · Pre-IC · Final IC</div></div>
        <div className="kpi-card"><div className="kpi-lbl">Analysing now</div><div className="kpi-val">{running}</div><div className="kpi-sub">{running ? 'updates live' : 'queue empty'}</div></div>
        <div className="kpi-card gold-val"><div className="kpi-lbl">Avg ADCG · Buyout</div><div className="kpi-val">{avg(buy)?.toFixed(2) ?? '—'}</div><div className="kpi-sub">{buy.length} deals</div></div>
        <div className="kpi-card gold-val"><div className="kpi-lbl">Avg ADCG-VG · Venture</div><div className="kpi-val">{avg(vg)?.toFixed(2) ?? '—'}</div><div className="kpi-sub">{vg.length} deals · separate scale</div></div>
        <div className="kpi-card"><div className="kpi-lbl">Highest score</div>
          <div className="kpi-val" style={{ fontSize: 16, marginTop: 4 }}>{best ? <WithLogo logo={<Logo url={best.website} name={best.name} size={22} />}>{best.name}</WithLogo> : '—'}</div>
          <div className="kpi-sub">{best ? `${best.adcg_score?.toFixed(2)}${best.band ? ` · ${best.band}` : ''}` : ''}</div></div>
      </div>

      <div className="tbl-wrap">
        <div className="tbl-bar">
          <CompanySearch mode="pipeline" value={q} onChange={setQ} placeholder="Search deals, sponsors, sectors…"
            onPickDeal={id => go(`deal-${id}`)} onNewDeal={data?.can_edit ? s => go(`new?q=${encodeURIComponent(s)}`) : undefined} />
          <select className="sel" value={track} onChange={e => setTrack(e.target.value)}>
            <option value="">All tracks</option><option value="buyout">Buyout</option><option value="vg">Venture / Growth</option>
          </select>
          <select className="sel" value={stage} onChange={e => setStage(e.target.value)}>
            <option value="">All stages</option>
            {data?.meta.stages.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <div className="seg">
            <button className={view === 'table' ? 'on' : ''} onClick={() => setView('table')}>Table</button>
            <button className={view === 'board' ? 'on' : ''} onClick={() => setView('board')}>Board</button>
          </div>
          <span className="tbl-ct">{rows.length} of {all.length} deals</span>
          {data?.can_edit && <button className="btn btn-gold btn-sm" onClick={() => go('new')}>+ New deal</button>}
        </div>

        {isLoading && <div className="empty">Loading deals…</div>}
        {error && <div className="err-box" style={{ margin: 12 }}>{errorText(error)}</div>}
        {data && rows.length === 0 && <div className="empty"><div className="h1">No deals match</div><div>Clear the filters, or add it as a new deal.</div></div>}

        {data && rows.length > 0 && view === 'table' && (
          <div style={{ overflowX: 'auto', padding: '0 0 6px' }}>
            <RowGlowTable>
              <thead><tr>
                {th('name', 'Company')}<th>Track</th><th>Sponsor / round</th><th>EV / post-money</th><th>Multiple</th>
                {th('score', 'ADCG', 'r')}{th('stage', 'Stage')}<th>Status</th>{th('updated', 'Updated', 'r')}
              </tr></thead>
              <tbody>
                {rows.map(d => (
                  <tr key={d.id} onClick={() => go(`deal-${d.id}`)}>
                    <td style={{ minWidth: 300 }}>
                      <WithLogo logo={<Logo url={d.website} name={d.name} size={30} />}>
                        <div className="nm">{d.name}</div><div className="sub clamp2">{d.one_liner || d.sub_sector || d.sector}</div>
                      </WithLogo>
                    </td>
                    <td><TrackBadge t={d.track_resolved || d.track} /></td>
                    <td><div className="cell-sm">{d.sponsor || '—'}</div></td>
                    <td><div className="cell-sm">{d.ev || '—'}</div></td>
                    <td><div className="cell-sm">{d.multiple || '—'}</div></td>
                    <td className="r"><span className={`score ${bandClass(d.adcg_score)}`}>{d.adcg_score?.toFixed(2) ?? '—'}</span></td>
                    <td><span className="badge badge-gray">{stageLabel[d.stage] ?? d.stage}</span></td>
                    <td><StatusBadge d={d} /></td>
                    <td className="r sub" style={{ whiteSpace: 'nowrap' }}>{ago(d.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </RowGlowTable>
          </div>
        )}

        {data && rows.length > 0 && view === 'board' && (
          <div className="board">
            {data.meta.stages.map(s => {
              const items = rows.filter(d => d.stage === s.id)
              return (
                <div className="col" key={s.id}>
                  <div className="col-h"><span>{s.label}</span><span className="col-n">{items.length}</span></div>
                  {items.map(d => (
                    <div className="dcard" key={d.id} onClick={() => go(`deal-${d.id}`)}>
                      <WithLogo logo={<Logo url={d.website} name={d.name} size={28} />}>
                        <div className="nm">{d.name}</div><div className="sub">{d.sector || d.sub_sector}</div>
                      </WithLogo>
                      <div className="sub clamp2" style={{ marginTop: 6 }}>{d.one_liner}</div>
                      <div className="card-row">
                        <TrackBadge t={d.track_resolved || d.track} /><div className="grow" />
                        <span className={`score ${bandClass(d.adcg_score)}`}>{d.adcg_score?.toFixed(2) ?? '—'}</span>
                      </div>
                      {(d.status === 'queued' || d.status === 'running' || d.status === 'error' || d.status === 'blocked') && <div className="card-row"><StatusBadge d={d} /></div>}
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}


/** A single floating highlight that glides behind whichever row is hovered — shadow, pastel wash and a glossy
 *  sweep — so the row "pops out" (one continuous surface instead of per-cell backgrounds). */
function RowGlowTable({ children }: { children: React.ReactNode }) {
  const box = useRef<HTMLDivElement>(null)
  const [g, setG] = useState<{ top: number; height: number; n: number } | null>(null)
  const last = useRef<Element | null>(null)
  function move(e: React.MouseEvent) {
    const tr = (e.target as HTMLElement).closest('tbody tr')
    if (!tr || !box.current) return
    if (tr === last.current) return
    last.current = tr
    const r = tr.getBoundingClientRect(), b = box.current.getBoundingClientRect()
    setG(x => ({ top: r.top - b.top - 4, height: r.height + 6, n: (x?.n ?? 0) + 1 }))   // a little taller than the row: it reads as lifted
  }
  return (
    <div className="glow-box" ref={box} onMouseMove={move} onMouseLeave={() => { last.current = null; setG(x => (x ? { ...x, height: 0 } : null)) }}>
      {g && <div className={`row-glow${g.height ? ' on' : ''}`} style={{ transform: `translateY(${g.top}px)`, height: g.height || undefined }}><i key={g.n} /></div>}
      <table className="tbl tbl-glow">{children}</table>
    </div>
  )
}
