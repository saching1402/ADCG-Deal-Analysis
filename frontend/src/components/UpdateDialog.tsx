import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { type UploadItem, rejectedText, uploadAll } from '../lib/upload'
import type { DealDetail } from '../types'
import FilePicker from './FilePicker'

/** Fold a few NEW data-room files into the existing memo — reads only the new files, works out what they change,
 *  re-scores and rewrites only the affected sections (open comments are applied too). Not a full re-run. */
export function UpdateDialog({ d, onClose }: { d: DealDetail; onClose: () => void }) {
  const qc = useQueryClient()
  const last = d.jobs.find(j => j.status === 'done')
  const [model, setModel] = useState(last?.model || d.meta.default_model)
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const waiting = d.files.filter(f => !f.archived_at && f.status !== 'digested')
  const pending = items.filter(x => x.state !== 'done')
  const count = waiting.length + pending.length
  const comments = d.open_comments || 0
  const est = model.includes('opus') ? '$1.50–5' : model.includes('haiku') ? '$0.20–0.80' : '$0.60–2.50'
  const patch = (key: string, p: Partial<UploadItem>) => setItems(xs => xs.map(x => (x.key === key ? { ...x, ...p } : x)))

  async function go(override = false) {
    setErr(null)
    if (pending.length) {
      setBusy(`Uploading ${pending.length} file(s)…`)
      const r = await uploadAll(d.id, pending, patch)
      if (r.failed) { setBusy(null); setErr(rejectedText(r.rejected)); return }
    }
    setBusy('Starting the update…')
    try {
      await api.post(`/deals/${d.id}/update/`, { model, override_credit: override })
      await qc.invalidateQueries({ queryKey: ['deal', d.id] }); void qc.invalidateQueries({ queryKey: ['deals'] })
      onClose()
    } catch (e) {
      const r = (e as { response?: { data?: { code?: string; detail?: string } } }).response?.data
      if (r?.code === 'credit_paused' && window.confirm(`${r.detail}\n\nRun anyway?`)) { setBusy(null); return go(true) }
      setErr(errorText(e)); await qc.invalidateQueries({ queryKey: ['deal', d.id] })
    }
    setBusy(null)
  }
  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget && !busy) onClose() }}>
      <div className="modal" style={{ maxWidth: 640 }}>
        <div className="modal-h"><div className="h1" style={{ fontSize: 19 }}>Update the memo with new materials</div></div>
        <div className="modal-b">
          <p style={{ marginBottom: 12, lineHeight: 1.55 }}>
            Reads <b>only the new files</b> (each checked like any upload), works out what they change against the current memo — numbers old → new,
            a revised model year by year, open questions now answered, new risks — then re-scores and rewrites <b>only the affected sections</b>.
            No re-reading of the rest of the data room, no new web research.{comments > 0 && <> Your <b>{comments} open comment{comments === 1 ? '' : 's'}</b> are applied in the same pass.</>}
            {' '}The current memo stays in History; the new one logs what changed.
          </p>
          {waiting.length > 0 && (
            <div className="upd-wait">
              <div className="kpi-lbl" style={{ marginBottom: 4 }}>Already on the deal, not yet in the memo</div>
              {waiting.map(f => <div key={f.id} className="upd-row"><span>{f.name}</span>
                {(f.status === 'error' || f.status === 'partial') ? <span className="badge badge-red" title={f.error}>Can’t be read — will stop the update</span> : <span className="badge badge-gray">Will be read</span>}</div>)}
            </div>
          )}
          <div className="kpi-lbl" style={{ margin: '12px 0 4px' }}>Add files</div>
          <FilePicker meta={d.meta} items={items} setItems={setItems} disabled={!!busy} existing={d.files.length} />
          <div className="rv-est" style={{ marginTop: 12 }}>
            <div><span className="kpi-lbl">Estimated cost</span><b>{est}</b><span className="sub">vs ~$6–20 for a full re-run</span></div>
            <div><span className="kpi-lbl">Time</span><b>3–8 min</b></div>
          </div>
          <label className="lbl" style={{ marginTop: 12, display: 'block' }}>Model</label>
          <select className="sel" value={model} onChange={e => setModel(e.target.value)} disabled={!!busy}>
            {d.meta.models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          {err && <div className="err-box" style={{ marginTop: 10 }}>{err}</div>}
        </div>
        <div className="modal-f">
          <button className="btn btn-ghost" onClick={onClose} disabled={!!busy}>Cancel</button>
          <button className="btn btn-primary" disabled={!!busy || count === 0 || !d.meta.api_key_set} onClick={() => void go()}>
            {busy ?? (count ? `Update memo with ${count} file${count === 1 ? '' : 's'} →` : 'Add a file to update')}</button>
        </div>
      </div>
    </div>
  )
}
