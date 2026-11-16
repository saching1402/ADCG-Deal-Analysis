import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import { ago } from '../lib/format'
import { History, Preview } from './FrameworkPage'

type Imp = 'high' | 'medium' | 'low'
type Track = 'buyout' | 'cv' | 'vg'
interface Pref { id: string; title: string; importance: Imp; applies: Track[]; guidance: string }
interface House {
  key: 'house'; name: string; version: number; updated_at: string; updated_by: string | null; can_edit: boolean
  config: { max_adjust: number; preferences: Pref[] }; guidance: string; description: string
}
const TRACKS: [Track, string][] = [['buyout', 'Buyout'], ['cv', 'CV'], ['vg', 'Venture Growth']]
const IMPS: [Imp, string, number][] = [['high', 'High', 3], ['medium', 'Medium', 2], ['low', 'Low', 1]]
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))

/** ADCG preferences: what ADCG likes and avoids, applied to every deal on every framework. */
export default function HousePrefs() {
  const qc = useQueryClient()
  const { data: fw, error, refetch } = useQuery({ queryKey: ['framework', 'house'], queryFn: async () => (await api.get<House>('/frameworks/house/')).data })
  const [draft, setDraft] = useState<House | null>(null)
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [panel, setPanel] = useState<'none' | 'history' | 'preview'>('none')
  useEffect(() => { if (fw) setDraft(clone(fw)) }, [fw])
  const dirty = useMemo(() => !!(fw && draft && JSON.stringify(fw.config) !== JSON.stringify(draft.config)), [fw, draft])

  if (error) return <div className="page"><div className="err-box">{errorText(error)}</div></div>
  if (!fw || !draft) return <div className="empty">Loading ADCG preferences…</div>
  const ro = !fw.can_edit
  const prefs = draft.config.preferences
  const edit = (f: (p: Pref[], d: House) => void) => setDraft(d => { const n = clone(d!); f(n.config.preferences, n); return n })
  const leave = (k: string) => { if (!dirty || window.confirm('Discard unsaved changes?')) go(k) }

  async function save() {
    setSaving(true); setMsg(null)
    try {
      await api.put('/frameworks/house/', { config: draft!.config, guidance: '', name: fw!.name, description: fw!.description, note, base_version: fw!.version })
      setNote(''); setMsg({ ok: true, text: 'Saved — the next analysis on every framework uses these preferences.' })
      await refetch(); void qc.invalidateQueries({ queryKey: ['fw-history', 'house'] })
    } catch (e) { setMsg({ ok: false, text: errorText(e) }) }
    setSaving(false)
  }
  async function restore(body: object, text: string) {
    if (!window.confirm(text)) return
    try { await api.post('/frameworks/house/restore/', body); await refetch(); void qc.invalidateQueries({ queryKey: ['fw-history', 'house'] }); setMsg({ ok: true, text: 'Restored as a new version.' }) }
    catch (e) { setMsg({ ok: false, text: errorText(e) }) }
  }

  return (
    <div className="page fw-page">
      <div className="fw-top">
        <div>
          <div className="eyebrow">Scoring framework</div>
          <div className="seg" style={{ marginTop: 6 }}>
            <button onClick={() => leave('framework')}>ADCG Buyout</button>
            <button onClick={() => leave('framework/cv')}>ADCG CV</button>
            <button onClick={() => leave('framework/vg')}>ADCG Venture Growth</button>
            <button className="on">ADCG preferences</button>
          </div>
        </div>
        <div className="grow" />
        <div className="fw-ver"><div className="nm">Version {fw.version}</div>
          <div className="sub">saved {ago(fw.updated_at)}{fw.updated_by ? ` by ${fw.updated_by}` : ''} · applies to every framework</div></div>
        <button className={`btn btn-sm${panel === 'history' ? ' btn-primary' : ''}`} onClick={() => setPanel(p => (p === 'history' ? 'none' : 'history'))}>History</button>
        <button className={`btn btn-sm${panel === 'preview' ? ' btn-primary' : ''}`} onClick={() => setPanel(p => (p === 'preview' ? 'none' : 'preview'))}>What Claude sees</button>
      </div>
      {msg && <div className={msg.ok ? 'ok-box' : 'err-box'} style={{ marginBottom: 12 }}>{msg.text}</div>}
      {ro && <div className="warn-box" style={{ marginBottom: 12 }}>Read-only — ask an admin for the analyst role to edit these.</div>}
      {panel === 'history' && <History fkey="house" current={fw.version} ro={ro} onRestore={v => restore({ version: v }, `Restore version ${v}? It will be saved as a new version.`)} />}
      {panel === 'preview' && <Preview fkey="house" version={fw.version} dirty={dirty} />}

      <section className="fw-card hp-intro">
        <div className="hp-title">What ADCG likes — and avoids</div>
        <p>These apply to every deal, whatever the framework. Claude researches them, tests them in the risk review, and works
          them into the memo where they belong — the sponsor, the valuation and comps, the exit, the Pros &amp; Cons — never as a
          separate list.</p>
        <div className="hp-how">
          <div><b>How they count in the score</b>
            <span>For each preference, Claude rates the deal from <b>−2</b> (what we avoid) to <b>+2</b> (what we like). The ratings are
              averaged, weighted by importance (High 3 · Medium 2 · Low 1), and move the overall score by at most
              <b> ±{draft.config.max_adjust}</b>. Each deal's Criteria tab shows every rating and its reason.</span></div>
          <label className="hp-cap">Maximum effect on the overall score
            <span><input className="inp" type="number" min={0} max={2} step={0.1} disabled={ro} value={draft.config.max_adjust}
              onChange={e => setDraft(d => ({ ...d!, config: { ...d!.config, max_adjust: Number(e.target.value) } }))} /> points</span></label>
        </div>
      </section>

      {prefs.map((p, i) => (
        <section className="fw-card hp-card" key={i}>
          <div className="hp-head">
            <span className="hp-n">{i + 1}</span>
            <input className="inp hp-name" disabled={ro} value={p.title} onChange={e => edit(x => { x[i].title = e.target.value })} />
            {!ro && <button className="btn btn-sm btn-ghost" title="Remove" onClick={() => window.confirm(`Remove “${p.title}”?`) && edit(x => { x.splice(i, 1) })}>✕</button>}
          </div>
          <div className="hp-meta">
            <div><span className="lbl">Importance</span>
              <div className="seg">{IMPS.map(([k, l]) => <button key={k} disabled={ro} className={p.importance === k ? 'on' : ''} onClick={() => edit(x => { x[i].importance = k })}>{l}</button>)}</div></div>
            <div><span className="lbl">Applies to</span>
              <div className="hp-tracks">{TRACKS.map(([k, l]) => {
                const on = p.applies.includes(k)
                return <button key={k} disabled={ro} className={`hp-chip${on ? ' on' : ''}`}
                  onClick={() => edit(x => { const a = x[i].applies; x[i].applies = on ? (a.length > 1 ? a.filter(t => t !== k) : a) : [...a, k] })}>{on ? '✓ ' : ''}{l}</button>
              })}</div></div>
          </div>
          <textarea className="inp hp-text" disabled={ro} rows={4} value={p.guidance} placeholder="What we look for, in plain words — Claude reads this on every deal."
            onChange={e => edit(x => { x[i].guidance = e.target.value })} />
        </section>
      ))}
      {!ro && <button className="btn" style={{ marginBottom: 18 }} onClick={() => edit(x => { x.push({ id: '', title: 'New preference', importance: 'medium', applies: ['buyout', 'cv', 'vg'], guidance: '' }) })}>+ Add a preference</button>}

      {dirty && !ro && (
        <div className="fw-savebar">
          <span className="nm">Unsaved changes</span>
          <input className="inp" style={{ maxWidth: 360 }} placeholder="What changed? (shown in History)" value={note} onChange={e => setNote(e.target.value)} />
          <div className="grow" />
          <button className="btn" onClick={() => { setDraft(clone(fw)); setMsg(null) }} disabled={saving}>Discard</button>
          <button className="btn btn-gold" onClick={() => void save()} disabled={saving}>{saving ? 'Saving…' : `Save as version ${fw.version + 1}`}</button>
        </div>
      )}
    </div>
  )
}
