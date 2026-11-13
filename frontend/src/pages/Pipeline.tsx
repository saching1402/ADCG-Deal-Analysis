import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import { ago, bandClass, riskClass } from '../lib/format'
import type { DealRow, Meta } from '../types'
import NewDealDialog from '../components/NewDealDialog'
import { StatusBadge, TrackBadge } from '../components/bits'

interface ListResp { deals: DealRow[]; meta: Meta; can_edit: boolean }
type SortKey = 'updated' | 'name' | 'score' | 'risk' | 'stage'

export default function Pipeline() {
  const [adding, setAdding] = useState(false)
  const [view, setView] = useState<'table' | 'board'>('table')
  const [q, setQ] = useState('')
  const [track, setTrack] = useState('')
  const [stage, setStage] = useState('')
  const [sort, setSort] = useState<{ k: SortKey; desc: boolean }>({ k: 'updated', desc: true })

  const { data, error, isLoading } = useQuery({
    queryKey: ['deals'],
    queryFn: async () => (await api.get<ListResp>('/deals/')).data,
    refetchInterval: d => (d.state.data?.deals.some(x => x.status === 'queued' || x.status === 'running') ? 5000 : false),
    staleTime: 10_000,
  })

  const stageLabel = useMemo(() => Object.fromEntries((data?.meta.stages ?? []).map(s => [s.id, s.label])), [data])
  const stageOrder = useMemo(() => Object.fromEntries((data?.meta.stages ?? []).map((s, i) => [s.id, i])), [data])

  const rows = useMemo(() => {
    let r = data?.deals ?? []
    const needle = q.trim().toLowerCase()
    if (needle) r = r.filter(d => [d.name, d.sponsor, d.sector, d.sub_sector, d.one_liner].join(' ').toLowerCase().includes(needle))
    if (track) r = r.filter(d => (d.track_resolved || d.track) === track)
    if (stage) r = r.filter(d => d.stage === stage)
    const val = (d: DealRow): string | number => {
      switch (sort.k) {
        case 'name': return d.name.toLowerCase()
        case 'score': return d.adcg_score ?? -1
        case 'risk': return d.risk_score ?? -1
        case 'stage': return stageOrder[d.stage] ?? 0
        default: return d.updated_at
      }
    }
    return [...r].sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * (sort.desc ? -1 : 1) })
  }, [data, q, track, stage, sort, stageOrder])

  const all = data?.deals ?? []
  const scored = all.filter(d => d.adcg_score != null)
  const inIc = all.filter(d => ['internal', 'pre_ic', 'final_ic'].includes(d.stage)).length
  const running = all.filter(d => d.status === 'queued' || d.status === 'running').length
  const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null)
  const avgB = avg(scored.filter(d => d.track_resolved !== 'vg').map(d => d.adcg_score!))
  const avgV = avg(scored.filter(d => d.track_resolved === 'vg').map(d => d.adcg_score!))

  const th = (k: SortKey, label: string, cls = '') => (
    <th className={cls} onClick={() => setSort(s => ({ k, desc: s.k === k ? !s.desc : k !== 'name' }))}>
      {label}{sort.k === k ? (sort.desc ? ' ↓' : ' ↑') : ''}
    </th>
  )

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Deal pipeline</div>
          <div className="h1">Deals analysed on the ADCG framework</div>
          <div className="lead">Every deal scored on the ADCG Buyout or ADCG Venture Growth framework. Add a deal, drop in the
            data room, and Claude reads the files, researches the web, scores it and writes the IC memo.</div>
        </div>
        <div className="grow" />
        {data?.can_edit && <button className="btn btn-gold" onClick={() => setAdding(true)}>+ New deal</button>}
      </div>

      {data && !data.meta.api_key_set && (
        <div className="warn-box" style={{ marginBottom: 14 }}>ANTHROPIC_API_KEY is not set on the Railway service — you can add deals and upload files, but analyses won't run until it is.</div>
      )}

      <div className="kpis">
        <div className="kpi dk"><div className="kpi-l">Deals in pipeline</div><div className="kpi-v">{all.length}</div><div className="kpi-s">{scored.length} scored</div></div>
        <div className="kpi"><div className="kpi-l">In IC process</div><div className="kpi-v">{inIc}</div><div className="kpi-s">Internal · Pre-IC · Final IC</div></div>
        <div className="kpi"><div className="kpi-l">Analysing now</div><div className="kpi-v">{running}</div><div className="kpi-s">{running ? 'updates live' : 'queue empty'}</div></div>
        <div className="kpi"><div className="kpi-l">Avg ADCG · Buyout</div><div className="kpi-v">{avgB?.toFixed(2) ?? '—'}</div><div className="kpi-s">{scored.filter(d => d.track_resolved !== 'vg').length} deals</div></div>
        <div className="kpi"><div className="kpi-l">Avg ADCG-VG · Venture</div><div className="kpi-v">{avgV?.toFixed(2) ?? '—'}</div><div className="kpi-s">{scored.filter(d => d.track_resolved === 'vg').length} deals · not comparable</div></div>
      </div>

      <div className="toolbar">
        <input className="inp" placeholder="Search company, sponsor, sector…" value={q} onChange={e => setQ(e.target.value)} />
        <select className="sel" value={track} onChange={e => setTrack(e.target.value)}>
          <option value="">All tracks</option><option value="buyout">Buyout</option><option value="vg">Venture / Growth</option>
        </select>
        <select className="sel" value={stage} onChange={e => setStage(e.target.value)}>
          <option value="">All stages</option>
          {data?.meta.stages.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <div className="grow" />
        <div className="seg">
          <button className={view === 'table' ? 'on' : ''} onClick={() => setView('table')}>Table</button>
          <button className={view === 'board' ? 'on' : ''} onClick={() => setView('board')}>Board</button>
        </div>
      </div>

      {isLoading && <div className="empty">Loading pipeline…</div>}
      {error && <div className="err-box">{errorText(error)}</div>}
      {data && rows.length === 0 && (
        <div className="empty"><div className="h1">No deals match</div><div>Clear the filters or add a new deal.</div></div>
      )}

      {data && rows.length > 0 && view === 'table' && (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead><tr>
              {th('name', 'Company')}<th>Track</th><th>Sponsor / round</th><th>EV / post-money</th><th>Multiple</th>
              {th('score', 'ADCG', 'r')}{th('risk', 'Risk', 'r')}{th('stage', 'Stage')}<th>Status</th>{th('updated', 'Updated', 'r')}
            </tr></thead>
            <tbody>
              {rows.map(d => (
                <tr key={d.id} onClick={() => go(`deal-${d.id}`)}>
                  <td><div className="co-name">{d.name}</div><div className="co-sub">{d.one_liner || d.sub_sector || d.sector}</div></td>
                  <td><TrackBadge t={d.track_resolved || d.track} /></td>
                  <td><div className="cell-sm">{d.sponsor || '—'}</div></td>
                  <td><div className="cell-sm">{d.ev || '—'}</div></td>
                  <td><div className="cell-sm">{d.multiple || '—'}</div></td>
                  <td className="r"><span className={`score ${bandClass(d.adcg_score)}`}>{d.adcg_score?.toFixed(2) ?? '—'}</span></td>
                  <td className="r"><span className={`score ${riskClass(d.risk_score)}`}>{d.risk_score ?? '—'}</span></td>
                  <td><span className="badge badge-gray">{stageLabel[d.stage] ?? d.stage}</span></td>
                  <td><StatusBadge d={d} /></td>
                  <td className="r note">{ago(d.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && rows.length > 0 && view === 'board' && (
        <div className="board">
          {data.meta.stages.map(s => {
            const items = rows.filter(d => d.stage === s.id)
            return (
              <div className="col" key={s.id}>
                <div className="col-h"><span>{s.label}</span><span>{items.length}</span></div>
                {items.map(d => (
                  <div className="card" key={d.id} onClick={() => go(`deal-${d.id}`)}>
                    <div className="co-name">{d.name}</div>
                    <div className="co-sub" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{d.one_liner || d.sector}</div>
                    <div className="card-row">
                      <TrackBadge t={d.track_resolved || d.track} />
                      <div className="grow" />
                      <span className={`score ${bandClass(d.adcg_score)}`}>{d.adcg_score?.toFixed(2) ?? '—'}</span>
                      <span className={`score ${riskClass(d.risk_score)}`}>{d.risk_score ?? '—'}</span>
                    </div>
                    {(d.status === 'queued' || d.status === 'running' || d.status === 'error') && <div className="card-row"><StatusBadge d={d} /></div>}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}

      {adding && data && <NewDealDialog meta={data.meta} onClose={() => setAdding(false)} />}
    </div>
  )
}
