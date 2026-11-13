import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Logo } from './Logo'
import { TrackBadge } from './bits'

export interface PipelineHit { id: string; name: string; domain: string; track: string; adcg_score: number | null; stage: string }
export interface CompanyHit { name: string; domain: string; description?: string; source?: string }
interface Resp { pipeline: PipelineHit[]; companies: CompanyHit[] }

/**
 * Search box with a suggestion dropdown.
 * mode "pipeline": suggests deals already in the pipeline + "Analyse <q> as a new deal".
 * mode "company":  suggests real companies (name + website) for a new deal, flagging ones already in the pipeline.
 */
export default function CompanySearch({ mode, value, onChange, onPickDeal, onPickCompany, onNewDeal, placeholder, autoFocus, big }: {
  mode: 'pipeline' | 'company'; value: string; onChange: (v: string) => void
  onPickDeal: (id: string) => void; onPickCompany?: (c: CompanyHit) => void; onNewDeal?: (q: string) => void
  placeholder?: string; autoFocus?: boolean; big?: boolean
}) {
  const [data, setData] = useState<Resp>({ pipeline: [], companies: [] })
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hi, setHi] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const seq = useRef(0)

  useEffect(() => {
    const q = value.trim()
    if (q.length < 2) { setData({ pipeline: [], companies: [] }); return }
    const n = ++seq.current
    setLoading(true)
    const t = setTimeout(async () => {
      try {
        const r = await api.get<Resp>('/deals/suggest/', { params: { q, pipeline_only: mode === 'pipeline' ? 1 : undefined } })
        if (n === seq.current) { setData(r.data); setHi(0) }
      } catch { if (n === seq.current) setData({ pipeline: [], companies: [] }) }
      finally { if (n === seq.current) setLoading(false) }
    }, mode === 'pipeline' ? 120 : 280)
    return () => clearTimeout(t)
  }, [value, mode])

  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  type Item = { kind: 'deal'; d: PipelineHit } | { kind: 'co'; c: CompanyHit } | { kind: 'new'; q: string }
  const q = value.trim()
  const items: Item[] = [
    ...data.pipeline.map(d => ({ kind: 'deal' as const, d })),
    ...(mode === 'company' ? data.companies.map(c => ({ kind: 'co' as const, c })) : []),
    ...(q.length >= 2 && onNewDeal ? [{ kind: 'new' as const, q }] : []),
  ]
  function pick(it: Item) {
    setOpen(false)
    if (it.kind === 'deal') onPickDeal(it.d.id)
    else if (it.kind === 'co') onPickCompany?.(it.c)
    else onNewDeal?.(it.q)
  }
  function key(e: React.KeyboardEvent) {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) { setOpen(true); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi(h => Math.min(items.length - 1, h + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi(h => Math.max(0, h - 1)) }
    else if (e.key === 'Enter' && items[hi]) { e.preventDefault(); pick(items[hi]) }
    else if (e.key === 'Escape') setOpen(false)
  }

  let idx = -1
  const row = (it: Item, body: React.ReactNode) => {
    idx++
    const i = idx
    return (
      <div key={i} className={`sg-item${i === hi ? ' on' : ''}`} onMouseEnter={() => setHi(i)} onMouseDown={e => { e.preventDefault(); pick(it) }}>
        {body}
      </div>
    )
  }

  return (
    <div className={`sg${big ? ' sg-big' : ''}`} ref={box}>
      <span className="sg-icon" aria-hidden>⌕</span>
      <input className="sg-input" type="search" value={value} placeholder={placeholder} autoFocus={autoFocus}
        onChange={e => { onChange(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)} onKeyDown={key}
        role="combobox" aria-expanded={open} aria-autocomplete="list" />
      {loading && <span className="sg-spin" />}
      {open && q.length >= 2 && (items.length > 0 || !loading) && (
        <div className="sg-pop" role="listbox">
          {data.pipeline.length > 0 && <div className="sg-h">{mode === 'company' ? 'Already in your pipeline' : 'Deals'}</div>}
          {data.pipeline.map(d => row({ kind: 'deal', d }, <>
            <Logo domain={d.domain} name={d.name} size={26} />
            <div className="sg-main"><div className="sg-name">{d.name}</div><div className="sg-sub">{d.domain || 'no website'}</div></div>
            <TrackBadge t={d.track} />
            {d.adcg_score != null && <span className="score b-none">{d.adcg_score.toFixed(2)}</span>}
          </>))}
          {mode === 'company' && data.companies.length > 0 && <div className="sg-h">Companies</div>}
          {mode === 'company' && data.companies.map(c => row({ kind: 'co', c }, <>
            <Logo domain={c.domain} name={c.name} size={26} />
            <div className="sg-main"><div className="sg-name">{c.name}</div><div className="sg-sub">{c.domain}{c.description ? ` · ${c.description}` : ''}</div></div>
          </>))}
          {mode === 'company' && !loading && data.companies.length === 0 && data.pipeline.length === 0 && (
            <div className="sg-empty">No matches found — you can still use “{q}” as typed.</div>
          )}
          {onNewDeal && row({ kind: 'new', q }, <>
            <span className="sg-plus">+</span>
            <div className="sg-main"><div className="sg-name">{mode === 'company' ? `Use “${q}” as typed` : `Analyse “${q}” as a new deal`}</div></div>
          </>)}
        </div>
      )}
    </div>
  )
}
