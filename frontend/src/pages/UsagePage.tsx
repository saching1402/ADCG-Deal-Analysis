import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import { ago } from '../lib/format'
import { Logo, WithLogo } from '../components/Logo'

export type Level = 'ok' | 'warn' | 'high' | 'critical' | 'unknown'
export interface Usage {
  settings: { monthly_budget_usd: number; storage_capacity_gb: number; db_capacity_gb: number; plan: string }
  storage: {
    where: 'volume' | 'bucket' | 'container' | 'local'; persistent: boolean; capacity: number; used: number; files_bytes: number
    files: number; frac: number | null; level: Level; capacity_source: string; avg_per_deal: number; deals_left: number | null
    reclaimable: number; archived_files: number; archived_bytes: number
    deals: { id: string; name: string; website: string; stage: string; status: string; n: number; b: number; reclaimable: boolean; updated_at: string }[]
  }
  database: { used: number | null; capacity: number; frac: number | null; level: Level }
  model: {
    month_cost: number; projected: number; budget: number; frac: number | null; projected_frac: number | null; level: Level
    runs_month: number; done_month: number; avg_run: number; all_time: number; runs_left: number | null; wasted_month: number
    by_model: { model: string; cost: number; runs: number }[]; history: { month: string; cost: number; runs: number }[]; key_set: boolean
  }
  suggestions: { level: 'critical' | 'high' | 'warn' | 'info'; area: string; title: string; text: string; action?: string }[]
  can_edit: boolean
}

export const useUsage = () => useQuery({
  queryKey: ['usage'], queryFn: async () => (await api.get<Usage>('/usage/')).data, refetchInterval: 60_000, staleTime: 30_000,
})

export const fmtBytes = (b: number | null | undefined) =>
  b == null ? '—' : b >= 1024 ** 3 ? `${(b / 1024 ** 3).toFixed(2)} GB` : b >= 1024 ** 2 ? `${(b / 1024 ** 2).toFixed(0)} MB` : `${Math.max(0, Math.round(b / 1024))} KB`
const pct = (f: number | null | undefined) => (f == null ? '—' : `${Math.round(f * 100)}%`)
const STAGE: Record<string, string> = { new: 'New', analyzed: 'Analyzed', internal: 'Internal', pre_ic: 'Pre-IC', final_ic: 'Final IC', approved: 'Approved', passed: 'Passed', on_hold: 'On hold' }
const WHERE: Record<string, string> = { volume: 'Railway Volume (/data)', bucket: 'S3-compatible bucket', container: 'Temporary container disk — NOT persistent', local: 'Local disk' }

function Meter({ frac, level, marks = true }: { frac: number | null; level: Level; marks?: boolean }) {
  return (
    <div className={`meter2 lv-${level}`}>
      <div className="meter2-fill" style={{ width: `${Math.min(100, (frac ?? 0) * 100)}%` }} />
      {marks && [70, 85, 95].map(m => <span key={m} className="meter2-mark" style={{ left: `${m}%` }} title={`${m}%`} />)}
    </div>
  )
}

export default function UsagePage() {
  const qc = useQueryClient()
  const { data: u, error, refetch } = useUsage()
  const [edit, setEdit] = useState(false)
  const [form, setForm] = useState({ monthly_budget_usd: '', storage_capacity_gb: '', db_capacity_gb: '', plan: 'hobby' })
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => {
    if (u) setForm({ monthly_budget_usd: String(u.settings.monthly_budget_usd), storage_capacity_gb: String(u.settings.storage_capacity_gb), db_capacity_gb: String(u.settings.db_capacity_gb), plan: u.settings.plan })
  }, [u])
  if (error) return <div className="page"><div className="err-box">{errorText(error)}</div></div>
  if (!u) return <div className="empty">Loading usage…</div>
  const { storage: s, model: m, database: d } = u

  async function saveSettings() {
    try { await api.patch('/usage/', form); setEdit(false); await refetch(); setMsg({ ok: true, text: 'Settings saved.' }) }
    catch (e) { setMsg({ ok: false, text: errorText(e) }) }
  }
  async function freeAll() {
    if (!window.confirm(`Delete the original files of every approved / passed / on-hold deal (${fmtBytes(s.reclaimable)})?\n\nFact sheets, research, scores and memos are kept, and the deals can still be re-analysed from the fact sheets.`)) return
    const r = (await api.post<{ files: number; freed: number }>('/usage/', {})).data
    setMsg({ ok: true, text: `Freed ${fmtBytes(r.freed)} from ${r.files} file(s).` }); await refetch(); void qc.invalidateQueries({ queryKey: ['deals'] })
  }
  async function freeDeal(id: string, name: string, b: number) {
    if (!window.confirm(`Delete the original files of ${name} (${fmtBytes(b)})? Fact sheets, research, scores and the memo are kept.`)) return
    const r = (await api.post<{ files: number; freed: number }>(`/deals/${id}/free-space/`)).data
    setMsg({ ok: true, text: `Freed ${fmtBytes(r.freed)} from ${name}.` }); await refetch()
  }
  const maxHist = Math.max(1, ...m.history.map(h => h.cost), m.budget || 0)

  return (
    <div className="page">
      <div className="fw-top" style={{ alignItems: 'center' }}>
        <div><div className="eyebrow">Usage &amp; capacity</div><div className="h1">Storage, database and model spend</div></div>
        <div className="grow" />
        {u.can_edit && <button className="btn btn-sm" onClick={() => setEdit(e => !e)}>{edit ? 'Close settings' : 'Budget & capacity settings'}</button>}
      </div>
      {msg && <div className={msg.ok ? 'ok-box' : 'err-box'} style={{ marginBottom: 12 }}>{msg.text}</div>}

      {edit && (
        <div className="fw-card">
          <div className="grid4">
            <div className="field"><label className="lbl">Monthly model budget (USD)</label><input className="inp num" type="number" min={0} value={form.monthly_budget_usd} onChange={e => setForm(f => ({ ...f, monthly_budget_usd: e.target.value }))} /></div>
            <div className="field"><label className="lbl">File storage capacity (GB)</label><input className="inp num" type="number" min={0} step={0.5} value={form.storage_capacity_gb} onChange={e => setForm(f => ({ ...f, storage_capacity_gb: e.target.value }))} />
              <div className="sub">{s.capacity_source === 'volume' ? 'Read from the mounted volume — this value is only a fallback.' : 'Used for the meter.'}</div></div>
            <div className="field"><label className="lbl">Database capacity (GB)</label><input className="inp num" type="number" min={0} step={0.5} value={form.db_capacity_gb} onChange={e => setForm(f => ({ ...f, db_capacity_gb: e.target.value }))} /></div>
            <div className="field"><label className="lbl">Railway plan</label>
              <select className="sel" style={{ width: '100%' }} value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value }))}>
                <option value="hobby">Hobby (5 GB volumes)</option><option value="pro">Pro (resizable volumes)</option><option value="bucket">Files in a bucket</option>
              </select><div className="sub">Changes the advice only.</div></div>
          </div>
          <button className="btn btn-primary btn-sm" onClick={saveSettings}>Save</button>
        </div>
      )}

      <div className="meters">
        <div className={`mcard lv-${s.level}`}>
          <div className="kpi-lbl">File storage</div>
          <div className="mval">{s.where === 'bucket' ? fmtBytes(s.files_bytes) : <>{fmtBytes(s.used)} <span>/ {fmtBytes(s.capacity)}</span></>}</div>
          {s.where !== 'bucket' && <Meter frac={s.frac} level={s.level} />}
          <div className="mrow"><span>{s.where === 'bucket' ? 'Bucket — no fixed limit' : `${pct(s.frac)} used`}</span><b>{s.deals_left != null && s.where !== 'bucket' ? `≈ ${s.deals_left} more deals` : ''}</b></div>
          <div className="sub">{WHERE[s.where]} · {s.files} files · avg {fmtBytes(s.avg_per_deal)} per deal{s.archived_files ? ` · ${s.archived_files} originals freed (${fmtBytes(s.archived_bytes)})` : ''}</div>
        </div>
        <div className={`mcard lv-${m.level}`}>
          <div className="kpi-lbl">Claude model spend · this month</div>
          <div className="mval">${m.month_cost.toFixed(2)} <span>/ ${m.budget.toFixed(0)} budget</span></div>
          <Meter frac={m.frac} level={m.level} />
          <div className="mrow"><span>{pct(m.frac)} of budget · projected ${m.projected.toFixed(0)}</span><b>{m.runs_left != null ? `≈ ${m.runs_left} more analyses` : ''}</b></div>
          <div className="sub">{m.runs_month} runs this month ({m.done_month} completed) · avg ${m.avg_run.toFixed(2)} per analysis · ${m.all_time.toFixed(2)} all time</div>
        </div>
        <div className={`mcard lv-${d.level}`}>
          <div className="kpi-lbl">Database (Postgres)</div>
          <div className="mval">{fmtBytes(d.used)} <span>/ {fmtBytes(d.capacity)}</span></div>
          <Meter frac={d.frac} level={d.level} />
          <div className="mrow"><span>{pct(d.frac)} used</span><b /></div>
          <div className="sub">Memos, research, scores and file fact sheets</div>
        </div>
      </div>

      <div className="fw-card">
        <div className="fw-h"><span>Suggestions</span><span className="sub">warnings at 70% · 85% · 95%</span></div>
        {u.suggestions.map((x, i) => (
          <div key={i} className={`sugg sg-${x.level}`}>
            <span className="sugg-tag">{x.level === 'info' ? x.area : x.level}</span>
            <div className="grow"><div className="nm">{x.title}</div><div className="sub" style={{ color: 'var(--text)' }}>{x.text}</div></div>
            {x.action === 'free_all' && u.can_edit && <button className="btn btn-sm btn-gold" onClick={freeAll}>Free {fmtBytes(s.reclaimable)}</button>}
          </div>
        ))}
      </div>

      <div className="grid2" style={{ alignItems: 'start' }}>
        <div className="fw-card">
          <div className="fw-h"><span>Model spend — last 6 months</span><span className="sub">monthly budget ${m.budget.toFixed(0)}</span></div>
          <div className="hbars">
            {m.history.map(h => (
              <div key={h.month} className="hbar">
                <div className="hbar-v">${h.cost.toFixed(0)}</div>
                <div className="hbar-col"><div className={h.cost > m.budget && m.budget > 0 ? 'over' : ''} style={{ height: `${(h.cost / maxHist) * 100}%` }} /></div>
                <div className="sub">{h.month}</div><div className="sub">{h.runs} runs</div>
              </div>
            ))}
          </div>
          <table className="fw-tbl" style={{ marginTop: 12 }}><thead><tr><th>Model (this month)</th><th className="r">Runs</th><th className="r">Spend</th></tr></thead><tbody>
            {m.by_model.length === 0 && <tr><td colSpan={3} className="sub">No runs this month.</td></tr>}
            {m.by_model.map(r => <tr key={r.model}><td className="mono">{r.model}</td><td className="r mono">{r.runs}</td><td className="r mono">${r.cost.toFixed(2)}</td></tr>)}
          </tbody></table>
        </div>
        <div className="fw-card">
          <div className="fw-h"><span>Storage by deal</span><span className="sub">{s.deals.length} deals hold files</span></div>
          <table className="fw-tbl"><thead><tr><th>Deal</th><th>Stage</th><th className="r">Files</th><th className="r">Size</th><th /></tr></thead><tbody>
            {s.deals.length === 0 && <tr><td colSpan={5} className="sub">No stored files yet.</td></tr>}
            {s.deals.map(r => (
              <tr key={r.id}>
                <td><a onClick={() => go(`deal-${r.id}/files`)} style={{ cursor: 'pointer' }}><WithLogo logo={<Logo url={r.website} name={r.name} size={22} />}><span className="nm" style={{ fontSize: 12.5 }}>{r.name}</span></WithLogo></a>
                  <div className="sub">updated {ago(r.updated_at)}</div></td>
                <td><span className="badge badge-gray">{STAGE[r.stage] ?? r.stage}</span></td>
                <td className="r mono">{r.n}</td>
                <td className="r mono">{fmtBytes(r.b)}<div className="sbar"><div style={{ width: `${Math.min(100, (r.b / Math.max(1, s.capacity)) * 100 * 4)}%` }} /></div></td>
                <td className="r">{u.can_edit && <button className={`btn btn-sm${r.reclaimable ? '' : ' btn-ghost'}`} onClick={() => void freeDeal(r.id, r.name, r.b)}
                  title={r.reclaimable ? 'Deal is approved / passed / on hold' : 'Deal is still active — only do this if you are sure'}>Free up</button>}</td>
              </tr>
            ))}
          </tbody></table>
        </div>
      </div>
    </div>
  )
}
