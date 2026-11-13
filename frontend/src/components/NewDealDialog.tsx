import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import type { DealRow, Meta, Track } from '../types'
import { type UploadItem, uploadAll } from '../lib/upload'
import FilePicker from './FilePicker'

export default function NewDealDialog({ meta, onClose }: { meta: Meta; onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [website, setWebsite] = useState('')
  const [track, setTrack] = useState<Track>('auto')
  const [sponsor, setSponsor] = useState('')
  const [notes, setNotes] = useState('')
  const [model, setModel] = useState(meta.default_model)
  const [analyze, setAnalyze] = useState(meta.api_key_set)
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const patch = (key: string, p: Partial<UploadItem>) => setItems(xs => xs.map(x => (x.key === key ? { ...x, ...p } : x)))

  async function submit() {
    if (!name.trim() || busy) return
    setErr(null)
    try {
      setBusy('Creating deal…')
      const { data: deal } = await api.post<DealRow>('/deals/', { name, website, track, sponsor, notes })
      if (items.length) {
        setBusy(`Uploading ${items.length} file(s)…`)
        const r = await uploadAll(deal.id, items, patch)
        if (r.failed) {
          setErr(`${r.failed} file(s) failed to upload — the deal was created; open it to retry or add them later.`)
        }
      }
      if (analyze) {
        setBusy('Starting analysis…')
        await api.post(`/deals/${deal.id}/analyze/`, { model })
      }
      await qc.invalidateQueries({ queryKey: ['deals'] })
      onClose()
      go(`deal-${deal.id}`)
    } catch (e) {
      setErr(errorText(e))
      setBusy(null)
    }
  }

  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget && !busy) onClose() }}>
      <div className="modal">
        <div className="modal-h">
          <div className="grow">
            <div className="eyebrow">New deal</div>
            <div className="h1" style={{ fontSize: 20 }}>Add a deal to analyse</div>
            <div className="note" style={{ marginTop: 4 }}>Claude reads every file, researches the company on the web, scores it on the ADCG framework and writes the IC memo — typically 10–25 minutes.</div>
          </div>
          <button className="x" onClick={onClose} disabled={!!busy} aria-label="Close">✕</button>
        </div>
        <div className="modal-b">
          <div className="grid2">
            <div className="field">
              <label className="lbl" htmlFor="nd-name">Company / deal name *</label>
              <input id="nd-name" className="inp" autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Apave or Baseten Series G" />
            </div>
            <div className="field">
              <label className="lbl" htmlFor="nd-web">Website</label>
              <input id="nd-web" className="inp" value={website} onChange={e => setWebsite(e.target.value)} placeholder="company.com" />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label className="lbl">Framework</label>
              <div className="seg">
                {([['auto', 'Auto-detect'], ['buyout', 'ADCG Buyout'], ['vg', 'ADCG Venture Growth']] as [Track, string][]).map(([v, l]) => (
                  <button key={v} type="button" className={track === v ? 'on' : ''} onClick={() => setTrack(v)}>{l}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <label className="lbl" htmlFor="nd-sp">Sponsor / lead investors</label>
              <input id="nd-sp" className="inp" value={sponsor} onChange={e => setSponsor(e.target.value)} placeholder="e.g. PAI Partners (CV) · or Thrive-led Series C" />
            </div>
          </div>
          <div className="field">
            <label className="lbl" htmlFor="nd-notes">Deal terms &amp; context (optional)</label>
            <textarea id="nd-notes" className="inp" rows={3} value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="EV, EBITDA, multiple, leverage, round size, pre/post, structure, what you want tested…" />
          </div>
          <div className="field">
            <label className="lbl">Deal materials</label>
            <FilePicker meta={meta} items={items} setItems={setItems} disabled={!!busy} />
          </div>
          <div className="grid2" style={{ alignItems: 'end' }}>
            <div className="field">
              <label className="lbl" htmlFor="nd-model">Analysis model</label>
              <select id="nd-model" className="sel" style={{ width: '100%' }} value={model} onChange={e => setModel(e.target.value)}>
                {meta.models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer', fontSize: 12.5 }}>
                <input type="checkbox" checked={analyze} disabled={!meta.api_key_set} onChange={e => setAnalyze(e.target.checked)} />
                Start the analysis as soon as files are uploaded
              </label>
            </div>
          </div>
          {err && <div className="err-box">{err}</div>}
        </div>
        <div className="modal-f">
          <span className="note">{busy ?? `Files are read by ${meta.models.find(m => m.id === meta.digest_model)?.label ?? meta.digest_model}; research, scoring and memo by the model above.`}</span>
          <div className="grow" />
          <button className="btn" onClick={onClose} disabled={!!busy}>Cancel</button>
          <button className="btn btn-primary" onClick={submit} disabled={!name.trim() || !!busy}>
            {busy ? 'Working…' : analyze ? 'Add deal & analyse →' : 'Add deal'}
          </button>
        </div>
      </div>
    </div>
  )
}
