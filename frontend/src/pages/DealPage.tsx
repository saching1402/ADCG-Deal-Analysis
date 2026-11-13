import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { marked } from 'marked'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import { STAGE_STEPS, ago, bandClass, bytes, riskClass } from '../lib/format'
import type { DealDetail, DealFile, Job } from '../types'
import { TrackBadge } from '../components/bits'
import FilePicker from '../components/FilePicker'
import { Logo } from '../components/Logo'
import { type UploadItem, uploadAll } from '../lib/upload'

const TABS = [['memo', 'IC memo'], ['scorecard', 'Scorecard'], ['research', 'Research dossier'], ['files', 'Files'], ['runs', 'Runs']] as const

export default function DealPage({ id, tab }: { id: string; tab: string }) {
  const qc = useQueryClient()
  const { data: d, error, refetch } = useQuery({
    queryKey: ['deal', id],
    queryFn: async () => (await api.get<DealDetail>(`/deals/${id}/`)).data,
    refetchInterval: q => {
      const s = q.state.data
      return s && (s.status === 'queued' || s.status === 'running' || s.files.some(f => f.status === 'digesting')) ? 4000 : false
    },
    staleTime: 0,
  })
  const [rerun, setRerun] = useState(false)
  const [editing, setEditing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const running = d?.status === 'queued' || d?.status === 'running'
  const prevRunning = useRef(running)
  useEffect(() => {
    if (prevRunning.current && !running) { void qc.invalidateQueries({ queryKey: ['memo', id] }); void qc.invalidateQueries({ queryKey: ['deals'] }) }
    prevRunning.current = running
  }, [running, id, qc])

  if (error) return <div className="page"><div className="err-box">{errorText(error)}</div></div>
  if (!d) return <div className="empty">Loading deal…</div>

  const track = d.track_resolved || d.track
  async function patch(body: Partial<DealDetail>) {
    try { await api.patch(`/deals/${id}/`, body); await refetch(); void qc.invalidateQueries({ queryKey: ['deals'] }) } catch (e) { setMsg(errorText(e)) }
  }
  async function cancel() { await api.post(`/deals/${id}/cancel/`); await refetch() }
  async function remove() {
    if (!window.confirm(`Delete ${d!.name} and all its files? This cannot be undone.`)) return
    await api.delete(`/deals/${id}/`); await qc.invalidateQueries({ queryKey: ['deals'] }); go('')
  }

  return (
    <div className="page">
            <div className="deal-head">
        <Logo url={d.website} name={d.name} size={64} />
        <div style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <TrackBadge t={track} />
            {d.sub_sector && <span className="note">{d.sub_sector}</span>}
          </div>
          <div className="h1">{d.name}</div>
          {d.one_liner && <div className="lead">{d.one_liner}</div>}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 12, flexWrap: 'wrap' }}>
            <select className="sel" value={d.stage} disabled={!d.can_edit} onChange={e => void patch({ stage: e.target.value })}>
              {d.meta.stages.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            {d.can_edit && !running && <button className="btn btn-primary btn-sm" onClick={() => setRerun(true)} disabled={!d.meta.api_key_set}>{d.has_memo || d.legacy ? 'Re-analyse' : 'Analyse'}</button>}
            {d.can_edit && running && <button className="btn btn-sm" onClick={cancel}>Cancel run</button>}
            {d.can_edit && <button className="btn btn-sm" onClick={() => setEditing(true)}>Edit details</button>}
            {d.can_edit && <button className="btn btn-sm btn-ghost btn-danger" onClick={remove}>Delete</button>}
            {d.website && <a className="note" href={/^https?:/.test(d.website) ? d.website : `https://${d.website}`} target="_blank" rel="noreferrer">{d.website}</a>}
          </div>
        </div>
        <div className="big-score">
          <div className="bs"><div className="bs-l">{track === 'vg' ? 'ADCG-VG score' : 'ADCG score'}</div>
            <div className={`bs-v`}><span className={`score ${bandClass(d.adcg_score)}`} style={{ fontSize: 24, padding: '2px 10px' }}>{d.adcg_score?.toFixed(2) ?? '—'}</span></div>
            <div className="note" style={{ marginTop: 4 }}>{d.band || 'not scored'}</div></div>
          <div className="bs"><div className="bs-l">{track === 'vg' ? 'Venture risk' : 'Risk score'}</div>
            <div className="bs-v"><span className={`score ${riskClass(d.risk_score)}`} style={{ fontSize: 24, padding: '2px 10px' }}>{d.risk_score ?? '—'}</span></div>
            <div className="note" style={{ marginTop: 4 }}>0–100 · higher = riskier</div></div>
        </div>
      </div>

      {msg && <div className="err-box" style={{ marginBottom: 12 }}>{msg}</div>}
      {(running || d.jobs[0]?.status === 'error') && d.jobs[0] && <Progress job={d.jobs[0]} />}

      {(d.facts?.length > 0 || d.ev) && (
        <div className="facts">
          {(d.facts?.length ? d.facts : [{ k: 'EV / post-money', v: d.ev }, { k: 'Multiple', v: d.multiple }, { k: 'Leverage', v: d.leverage }].filter(f => f.v))
            .map(f => <div key={f.k}><div className="k">{f.k}</div><div className="v">{f.v}</div></div>)}
          {d.sponsor && <div><div className="k">Sponsor / round</div><div className="v">{d.sponsor}</div></div>}
        </div>
      )}

      <div className="tabs">
        {TABS.map(([k, l]) => (
          <button key={k} className={`tab${tab === k ? ' on' : ''}`} onClick={() => go(`deal-${id}/${k}`)}>
            {l}{k === 'files' ? ` (${d.files.length})` : ''}
          </button>
        ))}
      </div>

      {tab === 'memo' && <MemoTab d={d} />}
      {tab === 'scorecard' && <ScorecardTab d={d} />}
      {tab === 'research' && <ResearchTab d={d} />}
      {tab === 'files' && <FilesTab d={d} refetch={() => void refetch()} />}
      {tab === 'runs' && <RunsTab d={d} />}

      {editing && <EditDialog d={d} onClose={() => setEditing(false)} onSave={async b => { await patch(b); setEditing(false) }} />}
      {rerun && <RerunDialog d={d} onClose={() => setRerun(false)} onDone={() => { setRerun(false); void refetch(); void qc.invalidateQueries({ queryKey: ['deals'] }) }} />}
    </div>
  )
}

function Progress({ job }: { job: Job }) {
  const idx = STAGE_STEPS.findIndex(s => s.id === job.stage)
  const failed = job.status === 'error'
  return (
    <div className="panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div className="panel-t" style={{ marginBottom: 0 }}>{failed ? (job.error === 'Cancelled' ? 'Run cancelled' : 'Analysis failed') : job.status === 'queued' ? 'Queued' : 'Analysing'}</div>
        {!failed && <span className="dot" />}
        <div className="grow" />
        <span className="note">{job.model} · {job.searches} searches · ${job.cost.toFixed(2)}</span>
      </div>
      <div className="steps">
        {STAGE_STEPS.map((s, i) => (
          <div key={s.id} className={`step${i < idx || job.status === 'done' ? ' done' : i === idx && !failed ? ' cur' : ''}`}>
            <span className="n">{i < idx ? '✓' : i + 1}</span>{s.label}{i < STAGE_STEPS.length - 1 && <span className="ln" />}
          </div>
        ))}
      </div>
      {job.stage_detail && !failed && <div className="note" style={{ marginBottom: 8 }}>{job.stage_detail}</div>}
      {failed && job.error !== 'Cancelled' && <div className="err-box" style={{ marginBottom: 8 }}>{job.error}</div>}
      {job.log.length > 0 && <div className="log">{job.log.map((l, i) => <div key={i}>{l.t.slice(11, 19)} · {l.msg}</div>)}</div>}
    </div>
  )
}

function MemoTab({ d }: { d: DealDetail }) {
  const frame = useRef<HTMLIFrameElement>(null)
  const { data, isLoading } = useQuery({
    queryKey: ['memo', d.id], enabled: d.has_memo,
    queryFn: async () => (await api.get<{ html: string; name: string }>(`/deals/${d.id}/memo/`)).data,
  })
  if (!d.has_memo) {
    return (
      <div className="panel empty">
        <div className="h1">No IC memo yet</div>
        <div>{d.legacy ? 'This deal came from the prior ADCG ledger (scores only). Re-analyse it to generate the full memo here.'
          : d.status === 'running' || d.status === 'queued' ? 'The memo appears here when the analysis finishes.'
            : 'Upload the deal materials in the Files tab, then press Analyse.'}</div>
      </div>
    )
  }
  if (isLoading || !data) return <div className="empty">Loading memo…</div>
  function download() {
    const url = URL.createObjectURL(new Blob([data!.html], { type: 'text/html' }))
    const a = document.createElement('a'); a.href = url; a.download = `${d.name.replace(/[^\w]+/g, '-').toLowerCase()}-ic-memo.html`; a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div>
      <div className="toolbar">
        <span className="note">Skill-derived — reconcile to the live ADCG scorecard app. {d.analyzed_at && `Analysed ${ago(d.analyzed_at)}.`}</span>
        <div className="grow" />
        <button className="btn btn-sm" onClick={() => frame.current?.contentWindow?.print()}>Print / Save as PDF</button>
        <button className="btn btn-sm" onClick={download}>Download HTML</button>
      </div>
      <iframe ref={frame} className="memo-frame" title="IC memo" srcDoc={data.html} sandbox="allow-same-origin allow-modals" />
    </div>
  )
}

function ScorecardTab({ d }: { d: DealDetail }) {
  const sc = d.scorecard
  if (!sc?.sections?.length) {
    return <div className="panel">{d.summary?.sections ? null : <div className="note">{d.legacy ? 'Ledger deal: headline scores only — re-analyse for the full 25/30-criteria scorecard.' : 'Not scored yet.'}</div>}</div>
  }
  const col = (s: number | null | undefined) => (s == null ? 'var(--subtle)' : s >= 6.5 ? 'var(--green)' : s >= 5 ? 'var(--gold)' : 'var(--red)')
  return (
    <div>
      {sc.key_risks && sc.key_risks.length > 0 && (
        <div className="panel">
          <div className="panel-t">Key risks driving the score</div>
          <table className="tbl"><tbody>
            {sc.key_risks.map((r, i) => (
              <tr key={i} style={{ cursor: 'default' }}><td style={{ width: 120 }}><span className={`badge ${/HIGH/.test(r.severity) && !/MEDIUM/.test(r.severity) ? 'badge-red' : 'badge-buyout'}`}>{r.severity}</span></td>
                <td><strong>{r.criterion}</strong><div className="co-sub" style={{ maxWidth: 'none' }}>{r.why}</div></td></tr>
            ))}
          </tbody></table>
          <div className="note" style={{ marginTop: 8 }}>Disagree with a risk? Use Re-analyse and add your rationale — the scorer applies it on the next run.</div>
        </div>
      )}
      <div className="panel">
        <div className="panel-t">Sections &amp; criteria</div>
        {sc.sections.map(s => (
          <div className="sc-sec" key={s.name}>
            <div className="sc-sec-h">
              <span className="t">{s.name}</span><span className="note">weight {s.weight}%</span>
              <div className="meter"><div style={{ width: `${(s.score ?? 0) * 10}%`, background: col(s.score) }} /></div>
              <span className="mono" style={{ color: col(s.score), fontWeight: 600 }}>{s.score?.toFixed(2)}</span>
            </div>
            <table className="tbl"><tbody>
              {s.criteria.map((c, i) => (
                <tr key={i} style={{ cursor: 'default' }}>
                  <td style={{ width: '32%' }}>{c.name}</td>
                  <td className="r mono" style={{ width: 60, color: col(c.score), fontWeight: 600 }}>{c.score == null ? 'n/d' : c.score.toFixed(1)}</td>
                  <td className="co-sub" style={{ maxWidth: 'none' }}>{c.rationale}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
        ))}
        {d.summary?.vjr_text && <div className="note">VJR: {d.summary.vjr_text}</div>}
        {sc.calibration && <div className="note" style={{ marginTop: 6 }}>Calibration: {sc.calibration}</div>}
      </div>
      {sc.weights_rationale && sc.weights_rationale.length > 0 && (
        <div className="panel">
          <div className="panel-t">Section weightings &amp; why</div>
          <table className="tbl"><thead><tr><th>Section</th><th className="r">Default</th><th className="r">This deal</th><th>Why</th></tr></thead><tbody>
            {sc.weights_rationale.map((w, i) => <tr key={i} style={{ cursor: 'default' }}><td>{w.section}</td><td className="r mono">{w.default}</td><td className="r mono">{w.deal}</td><td className="co-sub" style={{ maxWidth: 'none' }}>{w.why}</td></tr>)}
          </tbody></table>
        </div>
      )}
    </div>
  )
}

function ResearchTab({ d }: { d: DealDetail }) {
  const html = useMemo(() => (d.research ? marked.parse(d.research, { async: false }) as string : ''), [d.research])
  if (!d.research) return <div className="panel note">The research dossier appears here after the web-research stage.</div>
  return (
    <div>
      <div className="panel"><div className="md" dangerouslySetInnerHTML={{ __html: html }} /></div>
      {d.sources.length > 0 && (
        <div className="panel"><details><summary className="panel-t" style={{ cursor: 'pointer' }}>Sources ({d.sources.length})</summary>
          <ul style={{ paddingLeft: 18, marginTop: 6 }}>{d.sources.map(u => <li key={u} style={{ margin: '2px 0' }}><a href={u} target="_blank" rel="noreferrer">{u}</a></li>)}</ul>
        </details></div>
      )}
    </div>
  )
}

function FilesTab({ d, refetch }: { d: DealDetail; refetch: () => void }) {
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [digest, setDigest] = useState<string>('')
  const patchItem = (key: string, p: Partial<UploadItem>) => setItems(xs => xs.map(x => (x.key === key ? { ...x, ...p } : x)))

  async function upload() {
    setBusy(true)
    await uploadAll(d.id, items, patchItem)
    setBusy(false)
    setItems(xs => xs.filter(x => x.state !== 'done'))
    refetch()
  }
  async function download(f: DealFile) {
    const r = await api.get(`/deals/${d.id}/files/${f.id}/`, { responseType: 'blob', timeout: 0 })
    const url = URL.createObjectURL(r.data as Blob)
    const a = document.createElement('a'); a.href = url; a.download = f.name; a.click(); URL.revokeObjectURL(url)
  }
  async function del(f: DealFile) {
    if (!window.confirm(`Remove ${f.name}?`)) return
    await api.delete(`/deals/${d.id}/files/${f.id}/`); refetch()
  }
  async function show(f: DealFile) {
    if (open === f.id) { setOpen(null); return }
    const r = await api.get<{ digest: string }>(`/deals/${d.id}/files/${f.id}/?digest=1`)
    setDigest(r.data.digest); setOpen(f.id)
  }
  const undigested = d.files.filter(f => f.status !== 'digested').length

  return (
    <div>
      {d.can_edit && (
        <div className="panel">
          <div className="panel-t">Add materials</div>
          <FilePicker meta={d.meta} items={items} setItems={setItems} disabled={busy} existing={d.files.length} />
          {items.some(x => x.state !== 'done') && (
            <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
              <button className="btn btn-primary btn-sm" onClick={upload} disabled={busy}>{busy ? 'Uploading…' : `Upload ${items.filter(x => x.state !== 'done').length} file(s)`}</button>
              <button className="btn btn-sm" onClick={() => setItems([])} disabled={busy}>Clear</button>
            </div>
          )}
          {undigested > 0 && !items.length && <div className="note" style={{ marginTop: 10 }}>{undigested} file(s) not yet read — press Re-analyse to fold them into the memo (already-read files are reused).</div>}
        </div>
      )}
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>File</th><th className="r">Size</th><th>Read as</th><th>Status</th><th>Uploaded</th><th /></tr></thead>
          <tbody>
            {d.files.length === 0 && <tr><td colSpan={6} className="note" style={{ textAlign: 'center', padding: 30 }}>No files yet.</td></tr>}
            {d.files.map(f => (
              <Fragment key={f.id}>
                <tr style={{ cursor: 'default' }}>
                  <td><div className="co-name" style={{ fontWeight: 500 }}>{f.name}</div>{f.error && <div className="co-sub" style={{ color: 'var(--red)' }}>{f.error.slice(0, 200)}</div>}</td>
                  <td className="r note">{bytes(f.size)}</td>
                  <td className="note">{f.method === 'native-pdf' ? `PDF (native${f.pages ? `, ${f.pages}p` : ''})` : f.method === 'text' ? `text${f.chars ? ` · ${(f.chars / 1000).toFixed(0)}k chars` : ''}` : f.method || '—'}</td>
                  <td>{f.status === 'digested' ? <span className="badge badge-green">Read</span> : f.status === 'digesting' ? <span className="badge badge-run"><span className="dot" />Reading</span> : f.status === 'error' ? <span className="badge badge-red">Error</span> : <span className="badge badge-gray">Not read yet</span>}</td>
                  <td className="note">{ago(f.uploaded_at)}</td>
                  <td className="r" style={{ whiteSpace: 'nowrap' }}>
                    {f.has_digest && <button className="btn btn-sm btn-ghost" onClick={() => void show(f)}>{open === f.id ? 'Hide' : 'Fact sheet'}</button>}
                    <button className="btn btn-sm btn-ghost" onClick={() => void download(f)}>Download</button>
                    {d.can_edit && <button className="btn btn-sm btn-ghost btn-danger" onClick={() => void del(f)}>Remove</button>}
                  </td>
                </tr>
                {open === f.id && <tr><td colSpan={6} style={{ background: 'var(--surface2)' }}><div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(digest, { async: false }) as string }} /></td></tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RunsTab({ d }: { d: DealDetail }) {
  if (!d.jobs.length) return <div className="panel note">No analysis runs yet.</div>
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead><tr><th>Started</th><th>Model</th><th>Status</th><th className="r">Searches</th><th className="r">Tokens in / out</th><th className="r">Cost</th><th>Notes</th></tr></thead>
        <tbody>
          {d.jobs.map(j => (
            <tr key={j.id} style={{ cursor: 'default' }}>
              <td className="note">{ago(j.created_at)}</td><td className="mono">{j.model}</td>
              <td>{j.status === 'done' ? <span className="badge badge-green">Done</span> : j.status === 'error' ? <span className="badge badge-red" title={j.error}>{j.error === 'Cancelled' ? 'Cancelled' : 'Error'}</span> : <span className="badge badge-run">{j.status}</span>}</td>
              <td className="r mono">{j.searches}</td>
              <td className="r mono">{(j.input_tokens / 1000).toFixed(0)}k / {(j.output_tokens / 1000).toFixed(0)}k</td>
              <td className="r mono">${j.cost.toFixed(2)}</td>
              <td className="co-sub">{j.instructions || (j.error && j.error !== 'Cancelled' ? j.error.slice(0, 160) : '')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="note" style={{ padding: '8px 12px' }}>Total spend on this deal: ${d.total_cost.toFixed(2)}</div>
    </div>
  )
}

function RerunDialog({ d, onClose, onDone }: { d: DealDetail; onClose: () => void; onDone: () => void }) {
  const [model, setModel] = useState(d.jobs[0]?.model || d.meta.default_model)
  const [instructions, setInstructions] = useState('')
  const [redigest, setRedigest] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function go2() {
    setBusy(true); setErr(null)
    try { await api.post(`/deals/${d.id}/analyze/`, { model, instructions, redigest }); onDone() } catch (e) { setErr(errorText(e)); setBusy(false) }
  }
  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal" style={{ maxWidth: 600 }}>
        <div className="modal-h"><div className="grow"><div className="eyebrow">{d.has_memo ? 'Re-analyse' : 'Analyse'}</div><div className="h1" style={{ fontSize: 19 }}>{d.name}</div></div>
          <button className="x" onClick={onClose}>✕</button></div>
        <div className="modal-b">
          <div className="field">
            <label className="lbl" htmlFor="rr-model">Model</label>
            <select id="rr-model" className="sel" style={{ width: '100%' }} value={model} onChange={e => setModel(e.target.value)}>
              {d.meta.models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label className="lbl" htmlFor="rr-ins">Your rationale / steer for this run (optional)</label>
            <textarea id="rr-ins" className="inp" rows={5} value={instructions} onChange={e => setInstructions(e.target.value)}
              placeholder="e.g. Management confirmed organic growth was 7% not 2% (see QoE p.14) — rescore Business Quality. Treat leverage as 4.5x after the equity cure. Focus the gates on customer concentration." />
          </div>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5, cursor: 'pointer' }}>
            <input type="checkbox" checked={redigest} onChange={e => setRedigest(e.target.checked)} />
            Re-read every file from scratch (otherwise only new files are read)
          </label>
          {err && <div className="err-box" style={{ marginTop: 10 }}>{err}</div>}
        </div>
        <div className="modal-f"><div className="grow" /><button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={go2} disabled={busy}>{busy ? 'Starting…' : 'Run analysis →'}</button></div>
      </div>
    </div>
  )
}

function EditDialog({ d, onClose, onSave }: { d: DealDetail; onClose: () => void; onSave: (b: Partial<DealDetail>) => Promise<void> }) {
  const [f, setF] = useState({ name: d.name, website: d.website, sponsor: d.sponsor, sector: d.sector, ev: d.ev, multiple: d.multiple, leverage: d.leverage, one_liner: d.one_liner, notes: d.notes })
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF(s => ({ ...s, [k]: e.target.value }))
  const fld = (k: keyof typeof f, l: string, ph = '') => (
    <div className="field"><label className="lbl">{l}</label><input className="inp" value={f[k]} onChange={set(k)} placeholder={ph} /></div>
  )
  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal" style={{ maxWidth: 640 }}>
        <div className="modal-h"><div className="grow"><div className="eyebrow">Edit details</div><div className="h1" style={{ fontSize: 19 }}>{d.name}</div></div>
          <button className="x" onClick={onClose}>✕</button></div>
        <div className="modal-b">
          <div className="grid2">{fld('name', 'Name')}{fld('website', 'Website', 'company.com')}</div>
          <div className="grid2">{fld('sponsor', 'Sponsor / round')}{fld('sector', 'Sector')}</div>
          <div className="grid2">{fld('ev', 'EV / post-money')}{fld('multiple', 'Multiple')}</div>
          <div className="grid2">{fld('leverage', 'Leverage')}{fld('one_liner', 'One-liner')}</div>
          <div className="field"><label className="lbl">Terms &amp; notes (fed to the next analysis)</label><textarea className="inp" rows={3} value={f.notes} onChange={set('notes')} /></div>
        </div>
        <div className="modal-f"><div className="grow" /><button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !f.name.trim()} onClick={async () => { setBusy(true); await onSave(f); setBusy(false) }}>Save</button></div>
      </div>
    </div>
  )
}
