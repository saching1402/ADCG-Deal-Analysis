import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { ago } from '../lib/format'
import { History, Preview } from './FrameworkPage'

type Imp = 'high' | 'medium' | 'low'
type Track = 'buyout' | 'cv' | 'vg' | 'fund'
export interface Pref { id: string; title: string; importance: Imp; applies: Track[]; guidance: string }
interface House {
  key: 'house'; name: string; version: number; updated_at: string; updated_by: string | null; can_edit: boolean
  config: { max_adjust: number; preferences: Pref[] }; guidance: string; description: string
  scope: 'main' | 'mine'; personal: boolean; is_admin: boolean; differs: boolean; main_version: number; base_version: number
  my_proposal: { id: number; created_at: string } | null; pending_proposals: number
}
const TRACKS: [Track, string][] = [['buyout', 'Buyout'], ['cv', 'CV'], ['vg', 'Venture Growth'], ['fund', 'Fund Manager']]
const IMPS: [Imp, string, number][] = [['high', 'High', 3], ['medium', 'Medium', 2], ['low', 'Low', 1]]
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))

export interface HouseCfg { max_adjust: number; preferences: Pref[] }
export const openPrefs = () => window.dispatchEvent(new Event('adcg-open-prefs'))

/** ADCG preferences: what ADCG likes and avoids, applied across the frameworks. Shown as a slide-out panel. */
export default function HousePrefs({ onClose }: { onClose: () => void }) {
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

  async function save() {
    setSaving(true); setMsg(null)
    try {
      await api.put('/frameworks/house/', { scope: fw!.scope, config: draft!.config, guidance: '', name: fw!.name, description: fw!.description, note, base_version: fw!.version })
      setNote(''); setMsg({ ok: true, text: fw!.scope === 'main' ? 'Saved — the next analysis on every framework uses these preferences.' : 'Saved to your preferences — only your analyses use them.' })
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
    <div className="hp-shade" onClick={() => { if (!dirty || window.confirm('Discard unsaved changes?')) onClose() }}>
    <aside className="hp-drawer" onClick={e => e.stopPropagation()} role="dialog" aria-label="ADCG preferences">
      <div className="hp-dtop">
        <div><div className="eyebrow">Applied across the frameworks</div><div className="hp-title">ADCG preferences</div>
          <div className="sub">Version {fw.version} · saved {ago(fw.updated_at)}{fw.updated_by ? ` by ${fw.updated_by}` : ''}</div></div>
        <div className="grow" />
        <button className={`btn btn-sm${panel === 'history' ? ' btn-primary' : ''}`} onClick={() => setPanel(p => (p === 'history' ? 'none' : 'history'))}>History</button>
        <button className={`btn btn-sm${panel === 'preview' ? ' btn-primary' : ''}`} onClick={() => setPanel(p => (p === 'preview' ? 'none' : 'preview'))}>What Claude sees</button>
        <button className="hp-x" aria-label="Close" onClick={() => { if (!dirty || window.confirm('Discard unsaved changes?')) onClose() }}>✕</button>
      </div>
      <div className="hp-dbody">
      {fw.is_admin
        ? <div className="scope-bar main"><span className="scope-tag">Main preferences</span><span className="scope-txt">The team default. Team members can keep their own and propose changes to you.</span></div>
        : <div className={`scope-bar mine${fw.personal ? ' has' : ''}`}>
            <span className="scope-tag">{fw.personal ? 'My preferences' : 'My preferences · same as main'}</span>
            <span className="scope-txt">{fw.personal ? 'Only your analyses use these — nobody else sees them.' : 'Save any change and it becomes your own copy; the main preferences stay as they are.'}</span>
            {fw.personal && <button className="btn btn-sm" onClick={async () => { if (window.confirm('Go back to the main preferences? Your changes will be lost.')) { await api.post('/frameworks/house/reset-mine/'); await refetch(); setMsg({ ok: true, text: 'Back on the main preferences.' }) } }}>Reset to main</button>}
            {fw.personal && fw.differs && (fw.my_proposal ? <span className="badge badge-gold">Proposal sent · awaiting admin</span>
              : <button className="btn btn-sm btn-gold" onClick={async () => {
                  const n = window.prompt('Propose your preferences to the admin. A short reason (optional):', '')
                  if (n === null) return
                  try { await api.post('/frameworks/house/propose/', { note: n }); await refetch(); setMsg({ ok: true, text: 'Sent to the admin for approval.' }) } catch (e) { setMsg({ ok: false, text: errorText(e) }) }
                }}>Propose to main</button>)}
          </div>}
      {msg && <div className={msg.ok ? 'ok-box' : 'err-box'} style={{ marginBottom: 12 }}>{msg.text}</div>}
      {ro && <div className="warn-box" style={{ marginBottom: 12 }}>Read-only — ask an admin for the analyst role to edit these.</div>}
      {panel === 'history' && <History fkey="house" current={fw.main_version} ro={!fw.is_admin} onRestore={v => restore({ version: v }, `Restore version ${v}? It will be saved as a new version.`)} />}
      {panel === 'preview' && <Preview fkey="house" version={fw.version} dirty={dirty} />}

      <section className="fw-card hp-intro">
        <p style={{ marginTop: 0 }}>What ADCG likes — and avoids. Each preference applies to the frameworks you tick; each framework shows its own in its
          <b> ADCG preferences</b> section. Claude researches them, tests them in the risk review, and works
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

      </div>
      {dirty && !ro && (
        <div className="hp-savebar">
          <span className="nm">Unsaved changes</span>
          <input className="inp" style={{ maxWidth: 360 }} placeholder="What changed? (shown in History)" value={note} onChange={e => setNote(e.target.value)} />
          <div className="grow" />
          <button className="btn" onClick={() => { setDraft(clone(fw)); setMsg(null) }} disabled={saving}>Discard</button>
          <button className="btn btn-gold" onClick={() => void save()} disabled={saving}>{saving ? 'Saving…' : fw.scope === 'main' ? `Save as version ${fw.version + 1}` : 'Save to my preferences'}</button>
        </div>
      )}
    </aside>
    </div>
  )
}
