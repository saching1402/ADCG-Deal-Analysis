import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import { ago } from '../lib/format'
import { Logo, WithLogo } from '../components/Logo'

export type Level = 'ok' | 'warn' | 'high' | 'critical' | 'unknown'
export interface Usage {
  settings: { storage_capacity_gb: number; db_capacity_gb: number; plan: string; credit_balance: number | null; credit_as_of: string | null; warn_below: number | null; stop_below: number | null }
  storage: {
    where: 'volume' | 'bucket' | 'container' | 'local'; persistent: boolean; capacity: number; used: number; files_bytes: number
    files: number; frac: number | null; level: Level; capacity_source: string; avg_per_deal: number; deals_left: number | null
    reclaimable: number; archived_files: number; archived_bytes: number
    deals: { id: string; name: string; website: string; stage: string; status: string; n: number; b: number; reclaimable: boolean; updated_at: string }[]
  }
  database: { used: number | null; capacity: number; frac: number | null; level: Level }
  model: {
    month_cost: number; projected: number; balance: number | null; as_of: string | null; spent_since: number; remaining: number | null
    frac: number | null; warn_below: number | null; stop_below: number | null; paused: boolean; level: Level
    runs_month: number; done_month: number; avg_run: number; all_time: number; runs_left: number | null; wasted_month: number
    burn_30d: number; days_left: number | null
    by_model: { model: string; cost: number; runs: number }[]; history: { month: string; cost: number; runs: number }[]; key_set: boolean
    events: { t: string; kind: 'sync' | 'topup'; balance: number; amount?: number; estimate?: number | null; by?: string | null; note?: string }[]
  }
  suggestions: { level: 'critical' | 'high' | 'warn' | 'info'; area: string; title: string; text: string; action?: string }[]
  can_edit: boolean
}

export const useUsage = () => useQuery({
  queryKey: ['usage'], queryFn: async () => (await api.get<Usage>('/usage/')).data, refetchInterval: 60_000, staleTime: 30_000,
})

export const money = (x: number) => (x < 0 ? `−$${Math.abs(x).toFixed(2)}` : `$${x.toFixed(2)}`)
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
  const [form, setForm] = useState({ storage_capacity_gb: '', db_capacity_gb: '', plan: 'hobby' })
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => {
    if (u) setForm({ storage_capacity_gb: String(u.settings.storage_capacity_gb), db_capacity_gb: String(u.settings.db_capacity_gb), plan: u.settings.plan })
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
  const maxHist = Math.max(1, ...m.history.map(h => h.cost))

  return (
    <div className="page">
      <div className="fw-top" style={{ alignItems: 'center' }}>
        <div><div className="eyebrow">Usage &amp; capacity</div><div className="h1">Storage, database and model spend</div></div>
        <div className="grow" />
        {u.can_edit && <button className="btn btn-sm" onClick={() => setEdit(e => !e)}>{edit ? 'Close settings' : 'Storage capacity settings'}</button>}
      </div>
      {msg && <div className={msg.ok ? 'ok-box' : 'err-box'} style={{ marginBottom: 12 }}>{msg.text}</div>}

      {edit && (
        <div className="fw-card">
          <div className="grid3">
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
        <CreditCard m={m} canEdit={u.can_edit} onChange={async () => { await refetch(); void qc.invalidateQueries({ queryKey: ['usage'] }) }} />
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
          <div className="fw-h"><span>Claude spend by month</span><span className="sub">this month ${m.month_cost.toFixed(2)} · ${m.burn_30d.toFixed(2)} in the last 30 days</span></div>
          <div className="hbars">
            {m.history.map(h => (
              <div key={h.month} className="hbar">
                <div className="hbar-v">${h.cost.toFixed(0)}</div>
                <div className="hbar-col"><div style={{ height: `${(h.cost / maxHist) * 100}%` }} /></div>
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

function CreditCard({ m, canEdit, onChange }: { m: Usage['model']; canEdit: boolean; onChange: () => Promise<void> }) {
  const [mode, setMode] = useState<'none' | 'sync' | 'topup' | 'limits'>(m.balance == null ? 'sync' : 'none')
  const [val, setVal] = useState('')
  const [warn, setWarn] = useState(m.warn_below == null ? '' : String(m.warn_below))
  const [stop, setStop] = useState(m.stop_below == null ? '' : String(m.stop_below))
  const [err, setErr] = useState<string | null>(null)
  const [hist, setHist] = useState(false)
  async function send(body: object) {
    setErr(null)
    try { await api.patch('/usage/', body); setVal(''); setMode('none'); await onChange() } catch (e) { setErr(errorText(e)) }
  }
  const remFrac = m.balance ? Math.max(0, (m.remaining ?? 0) / m.balance) : null
  return (
    <div className={`mcard lv-${m.level}`}>
      <div className="kpi-lbl">Claude credit {m.paused && <span className="badge badge-red" style={{ marginLeft: 6 }}>new runs paused</span>}</div>
      {m.remaining == null ? (
        <><div className="mval">Not set</div>
          <div className="sub" style={{ marginBottom: 8 }}>Type the balance shown at the top right of platform.claude.com. The app then counts down as analyses run — nothing is read from your card or set for you.</div></>
      ) : (
        <>
          <div className="mval">{money(m.remaining)} <span>{m.remaining < 0 ? 'over — ' : 'left of '}${m.balance!.toFixed(2)}{m.remaining < 0 ? ' recorded' : ''}</span></div>
          <div className={`meter2 lv-${m.level}`}>
            <div className="meter2-fill" style={{ width: `${Math.min(100, (m.frac ?? 0) * 100)}%` }} />
            {m.warn_below != null && m.balance! > 0 && <span className="meter2-mark warnm" style={{ left: `${Math.min(100, (1 - m.warn_below / m.balance!) * 100)}%` }} title={`warn below $${m.warn_below}`} />}
            {m.stop_below != null && m.balance! > 0 && <span className="meter2-mark stopm" style={{ left: `${Math.min(100, (1 - m.stop_below / m.balance!) * 100)}%` }} title={`stop below $${m.stop_below}`} />}
          </div>
          <div className="mrow"><span>${m.spent_since.toFixed(2)} used since {m.as_of ? new Date(m.as_of).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '—'} ({remFrac != null ? `${Math.round((1 - remFrac) * 100)}%` : '—'})</span>
            <b>{m.runs_left != null ? `≈ ${m.runs_left} analyses` : ''}{m.days_left != null ? ` · ~${m.days_left} days` : ''}</b></div>
          <div className="sub">Warn {m.warn_below != null ? `below $${m.warn_below}` : 'off'} · Stop new runs {m.stop_below != null ? `below $${m.stop_below}` : 'off'} · avg ${m.avg_run.toFixed(2)} per analysis</div>
        </>
      )}
      {canEdit && (
        <div className="credit-actions">
          <button className={`btn btn-sm${mode === 'sync' ? ' btn-primary' : ''}`} onClick={() => setMode(mode === 'sync' ? 'none' : 'sync')}>Update from Console</button>
          {m.balance != null && <button className={`btn btn-sm${mode === 'topup' ? ' btn-primary' : ''}`} onClick={() => setMode(mode === 'topup' ? 'none' : 'topup')}>I added credit</button>}
          <button className={`btn btn-sm btn-ghost${mode === 'limits' ? ' on' : ''}`} onClick={() => setMode(mode === 'limits' ? 'none' : 'limits')}>Warn / stop levels</button>
          {m.events.length > 0 && <button className="btn btn-sm btn-ghost" onClick={() => setHist(h => !h)}>History</button>}
        </div>
      )}
      {mode === 'sync' && canEdit && (
        <div className="credit-form">
          <label className="lbl">Balance shown in the Claude Console now ($)</label>
          <div style={{ display: 'flex', gap: 6 }}><input className="inp num" type="number" step={0.01} min={0} autoFocus value={val} onChange={e => setVal(e.target.value)} placeholder="e.g. 26.49" />
            <button className="btn btn-primary btn-sm" disabled={val === ''} onClick={() => void send({ console_balance: val })}>Save</button></div>
          <div className="sub">Resets the meter to the real figure. Do this now and then — the app's count is an estimate from token usage.</div>
        </div>
      )}
      {mode === 'topup' && canEdit && (
        <div className="credit-form">
          <label className="lbl">Amount you just added in the Console ($)</label>
          <div style={{ display: 'flex', gap: 6 }}><input className="inp num" type="number" step={1} min={0} autoFocus value={val} onChange={e => setVal(e.target.value)} placeholder="e.g. 50" />
            <button className="btn btn-primary btn-sm" disabled={!val} onClick={() => void send({ topup: val })}>Add</button></div>
        </div>
      )}
      {mode === 'limits' && canEdit && (
        <div className="credit-form">
          <div className="grid2">
            <div><label className="lbl">Warn me below ($)</label><input className="inp num" type="number" min={0} value={warn} onChange={e => setWarn(e.target.value)} placeholder="off" /></div>
            <div><label className="lbl">Stop new analyses below ($)</label><input className="inp num" type="number" min={0} value={stop} onChange={e => setStop(e.target.value)} placeholder="off" /></div>
          </div>
          <div className="sub" style={{ margin: '6px 0' }}>Leave blank to turn off. Stopping only blocks new runs (you can still override per run); running analyses finish.</div>
          <button className="btn btn-primary btn-sm" onClick={() => void send({ warn_below: warn, stop_below: stop })}>Save levels</button>
        </div>
      )}
      {err && <div className="err-box" style={{ marginTop: 8 }}>{err}</div>}
      {hist && (
        <table className="fw-tbl" style={{ marginTop: 8 }}><tbody>
          {m.events.map((e, i) => (
            <tr key={i}><td className="sub">{new Date(e.t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</td>
              <td>{e.kind === 'topup' ? `Added $${e.amount?.toFixed(2)}` : `Console balance $${e.balance.toFixed(2)}`}
                {e.kind === 'sync' && e.estimate != null && <span className="sub"> · app estimated ${e.estimate.toFixed(2)} ({e.balance - e.estimate >= 0 ? '+' : ''}{(e.balance - e.estimate).toFixed(2)})</span>}</td>
              <td className="r mono">${e.balance.toFixed(2)}</td></tr>
          ))}
        </tbody></table>
      )}
    </div>
  )
}
