import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { marked } from 'marked'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import { ago } from '../lib/format'
import { openPrefs, type HouseCfg } from './HousePrefs'
import { GpPicker, MemberChips, sameFirm, type GpMember, type MemberIn } from '../components/GpPicker'

type Key = 'buyout' | 'cv' | 'vg'
interface Crit { name: string; guidance: string; auto?: string }
interface Sec { name: string; weight: number; description: string; criteria: Crit[] }
interface Tier { id: string; label: string; lead: number; part: number; cap?: number; members: MemberIn[] }
interface Cfg {
  weights_flex?: boolean; sections: Sec[]; bands: { label: string; min: number }[]
  risk: { method: 'derived' | 'register'; formula?: string; register?: { name: string; weight: number }[] }
  overlays?: string[]; weighting_rules?: { when: string; rule: string }[]
  sector_library?: { name: string; anchor: string; criteria: string; comps: string }[]
  tiers?: Tier[]; marquee?: { base: number; slope: number }; vjr?: { ok: number; caution: number }
  anchors?: { deal: string; score: number; risk: number; note: string }[]; calibration_note?: string
}
interface Fw {
  key: Key; name: string; description: string; config: Cfg; guidance: string; version: number
  updated_at: string; updated_by: string | null; deals_scored: number; can_edit: boolean; prompt_preview: string | null
  scope: 'main' | 'mine'; personal: boolean; main_version: number; base_version: number; is_admin: boolean; differs: boolean
  pending_proposals: number; my_proposal: { id: number; created_at: string; changes: string[] } | null
}
interface Ver { version: number; note: string; created_at: string; by: string | null; runs: number }

const COLORS = ['#0f2347', '#b38728', '#2453a6', '#1d7a47', '#8a6412', '#5b6678', '#b7282e', '#27467d']
const sum = (xs: number[]) => xs.reduce((a, b) => a + (Number(b) || 0), 0)
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))
const L = (i: number) => String.fromCharCode(97 + i)
function move<T>(arr: T[], i: number, d: number) { const j = i + d; if (j < 0 || j >= arr.length) return; [arr[i], arr[j]] = [arr[j], arr[i]] }

export default function FrameworkPage({ fkey }: { fkey: Key }) {
  const qc = useQueryClient()
  const [viewMain, setViewMain] = useState(false)
  const { data: fw, error, refetch } = useQuery({
    queryKey: ['framework', fkey, viewMain ? 'main' : 'auto'],
    queryFn: async () => (await api.get<Fw>(`/frameworks/${fkey}/${viewMain ? '?scope=main' : ''}`)).data,
  })
  const [draft, setDraft] = useState<Fw | null>(null)
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [panel, setPanel] = useState<'none' | 'history' | 'preview'>('none')
  const [gPreview, setGPreview] = useState(false)

  useEffect(() => { if (fw) { setDraft(clone(fw)); setMsg(null) } }, [fw])
  const dirty = useMemo(() => !!(fw && draft && JSON.stringify([fw.config, fw.guidance, fw.name, fw.description]) !== JSON.stringify([draft.config, draft.guidance, draft.name, draft.description])), [fw, draft])

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  if (error) return <div className="page"><div className="err-box">{errorText(error)}</div></div>
  if (!fw || !draft) return <div className="empty">Loading framework…</div>

  const ro = !fw.can_edit
  const c = draft.config
  const edit = (f: (c: Cfg) => void) => setDraft(d => { const n = clone(d!); f(n.config); return n })
  const total = sum(c.sections.map(s => s.weight))

  async function save() {
    setSaving(true); setMsg(null)
    try {
      await api.put(`/frameworks/${fkey}/`, { scope: fw!.scope, config: draft!.config, guidance: draft!.guidance, name: draft!.name, description: draft!.description, note, base_version: fw!.version })
      setNote(''); setMsg({ ok: true, text: 'Saved — the next analysis on this framework uses this version.' })
      await refetch(); void qc.invalidateQueries({ queryKey: ['fw-history', fkey] })
    } catch (e) { setMsg({ ok: false, text: errorText(e) }) }
    setSaving(false)
  }
  async function restore(body: object, confirmText: string) {
    if (!window.confirm(confirmText)) return
    try { await api.post(`/frameworks/${fkey}/restore/`, body); await refetch(); void qc.invalidateQueries({ queryKey: ['fw-history', fkey] }); setMsg({ ok: true, text: 'Restored as a new version.' }) }
    catch (e) { setMsg({ ok: false, text: errorText(e) }) }
  }
  function switchTo(k: Key) {
    if (dirty && !window.confirm('Discard unsaved changes?')) return
    go(k === 'buyout' ? 'framework' : `framework/${k}`)
  }

  const NAV = [['fw-sections', 'Sections & weights'], ...(fkey !== 'vg' ? [['fw-gps', 'GP tiers']] : []), ['fw-prefs', 'ADCG preferences'], ['fw-bands', 'Verdict bands'], 
    ...(fkey === 'vg' ? [['fw-tiers', 'GP tiers & VJR']] : [['fw-rules', 'Weighting rules'], ['fw-library', 'Sector library']]),
    ['fw-anchors', 'Calibration'], ['fw-guidance', 'Analyst guidance']]

  return (
    <div className="page fw-page">
      <div className="fw-top">
        <div>
          <div className="eyebrow">Scoring framework</div>
          <div className="seg" style={{ marginTop: 6 }}>
            <button className={fkey === 'buyout' ? 'on' : ''} onClick={() => switchTo('buyout')}>ADCG Buyout</button>
            <button className={fkey === 'cv' ? 'on' : ''} onClick={() => switchTo('cv')}>ADCG CV</button>
            <button className={fkey === 'vg' ? 'on' : ''} onClick={() => switchTo('vg')}>ADCG Venture Growth</button>
          </div>
        </div>
        <div className="grow" />
        <div className="fw-ver">
          <div className="nm">Version {fw.version}</div>
          <div className="sub">saved {ago(fw.updated_at)}{fw.updated_by ? ` by ${fw.updated_by}` : ''} · {fw.deals_scored} deals scored on this track</div>
        </div>
        <button className={`btn btn-sm${panel === 'history' ? ' btn-primary' : ''}`} onClick={() => setPanel(p => (p === 'history' ? 'none' : 'history'))}>History</button>
        <button className={`btn btn-sm${panel === 'preview' ? ' btn-primary' : ''}`} onClick={() => setPanel(p => (p === 'preview' ? 'none' : 'preview'))}>What Claude sees</button>
        {fw.is_admin && fw.scope === 'main' && <button className="btn btn-sm btn-ghost" onClick={() => restore({ reset: true }, 'Reset this framework to the original ADCG skill defaults? Your current version stays in History.')}>Reset to defaults</button>}
      </div>
      <ScopeBar fw={fw} viewMain={viewMain} setViewMain={v => { if (!dirty || window.confirm('Discard unsaved changes?')) setViewMain(v) }}
        onChanged={async (t) => { await refetch(); void qc.invalidateQueries({ queryKey: ['framework'] }); setMsg({ ok: true, text: t }) }}
        onError={t => setMsg({ ok: false, text: t })} />

      {msg && <div className={msg.ok ? 'ok-box' : 'err-box'} style={{ marginBottom: 12 }}>{msg.text}</div>}
      {ro && !viewMain && <div className="warn-box" style={{ marginBottom: 12 }}>Read-only — ask an admin to give your account the analyst role to edit frameworks.</div>}
      {panel === 'history' && <History fkey={fkey} current={fw.main_version} ro={!fw.is_admin} onRestore={v => restore({ version: v }, `Restore version ${v}? It will be saved as a new version.`)} />}
      {panel === 'preview' && <Preview fkey={fkey} version={fw.version} dirty={dirty} />}

      <div className="fw-layout">
        <nav className="fw-nav">
          {NAV.map(([id, l]) => <a key={id} onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{l}</a>)}
        </nav>

        <div className="fw-body">
          <section className="fw-card">
            <div className="grid2">
              <div className="field"><label className="lbl">Framework name</label>
                <input className="inp" disabled={ro} value={draft.name} onChange={e => setDraft(d => ({ ...d!, name: e.target.value }))} /></div>
              <div className="field"><label className="lbl">Section weights</label>
                <div className="seg">
                  <button disabled={ro} className={c.weights_flex ? 'on' : ''} onClick={() => edit(x => { x.weights_flex = true })}>Defaults — flex per deal</button>
                  <button disabled={ro} className={!c.weights_flex ? 'on' : ''} onClick={() => edit(x => { x.weights_flex = false })}>Fixed</button>
                </div></div>
            </div>
            <div className="field" style={{ marginBottom: 0 }}><label className="lbl">Scope — when this framework applies</label>
              <input className="inp" disabled={ro} value={draft.description} onChange={e => setDraft(d => ({ ...d!, description: e.target.value }))} /></div>
          </section>

          {/* sections & weights */}
          <section className="fw-card" id="fw-sections">
            <div className="fw-h"><span>Sections &amp; weights</span>
              <span className={`fw-total ${Math.abs(total - 100) < 0.01 ? 'ok' : 'bad'}`}>Total {total.toFixed(total % 1 ? 1 : 0)} / 100</span></div>
            <div className="wbar">
              {c.sections.map((s, i) => <div key={i} style={{ flex: `${Math.max(0, s.weight)} 0 0`, background: COLORS[i % COLORS.length] }} title={`${s.name} ${s.weight}`}>{s.weight >= 6 ? `${s.name} ${s.weight}` : ''}</div>)}
            </div>
            <div className="sub" style={{ margin: '6px 0 14px' }}>Overall score = Σ weight × section score. Section score = average of its criteria (1–10; undisclosed criteria are skipped).</div>
            {c.sections.map((s, si) => (
              <div className="fw-sec" key={si} style={{ borderLeftColor: COLORS[si % COLORS.length] }}>
                <div className="fw-sec-h">
                  <span className="fw-n">{si + 1}</span>
                  <input className="inp fw-sec-name" disabled={ro} value={s.name} onChange={e => edit(x => { x.sections[si].name = e.target.value })} />
                  <label className="fw-w"><input className="inp" type="number" min={0} max={100} step={1} disabled={ro} value={s.weight}
                    onChange={e => edit(x => { x.sections[si].weight = Number(e.target.value) })} /><span>%</span></label>
                  {!ro && <div className="fw-ctl">
                    <button className="x" title="Move up" onClick={() => edit(x => move(x.sections, si, -1))}>↑</button>
                    <button className="x" title="Move down" onClick={() => edit(x => move(x.sections, si, 1))}>↓</button>
                    <button className="x" title="Delete section" onClick={() => { if (window.confirm(`Delete section ${s.name}?`)) edit(x => { x.sections.splice(si, 1) }) }}>✕</button>
                  </div>}
                </div>
                <input className="inp fw-desc" disabled={ro} placeholder="What this section asks (shown to Claude)" value={s.description}
                  onChange={e => edit(x => { x.sections[si].description = e.target.value })} />
                <div className="fw-crits">
                  {s.criteria.map((cr, ci) => (
                    <div className="fw-crit" key={ci}>
                      <span className="fw-l">{L(ci)}</span>
                      <input className="inp" disabled={ro} value={cr.name} placeholder="Criterion" onChange={e => edit(x => { x.sections[si].criteria[ci].name = e.target.value })} />
                      <input className="inp" disabled={ro} value={cr.guidance} placeholder="How to score it — what a 2, 5 and 9 look like" onChange={e => edit(x => { x.sections[si].criteria[ci].guidance = e.target.value })} />
                      {cr.auto ? <span className="badge badge-vg" title="Computed by the engine">auto</span> : <span />}
                      {!ro ? <div className="fw-ctl">
                        <button className="x" onClick={() => edit(x => move(x.sections[si].criteria, ci, -1))}>↑</button>
                        <button className="x" onClick={() => edit(x => move(x.sections[si].criteria, ci, 1))}>↓</button>
                        <button className="x" onClick={() => edit(x => { x.sections[si].criteria.splice(ci, 1) })}>✕</button>
                      </div> : <span />}
                    </div>
                  ))}
                  {!ro && <button className="btn btn-sm btn-ghost" onClick={() => edit(x => { x.sections[si].criteria.push({ name: '', guidance: '' }) })}>+ Add criterion</button>}
                </div>
              </div>
            ))}
            {!ro && <button className="btn btn-sm" onClick={() => edit(x => { x.sections.push({ name: 'New section', weight: 0, description: '', criteria: [{ name: '', guidance: '' }] }) })}>+ Add section</button>}
          </section>

          {fkey !== 'vg' && <GpTiersSection fkey={fkey} />}
          <PrefsSection fkey={fkey} />

          {/* bands */}
          <section className="fw-card" id="fw-bands">
            <div className="fw-h"><span>Verdict bands</span></div>
            <table className="fw-tbl"><thead><tr><th>Label</th><th className="r">From score</th><th /></tr></thead><tbody>
              {c.bands.map((b, i) => (
                <tr key={i}>
                  <td><input className="inp" disabled={ro} value={b.label} onChange={e => edit(x => { x.bands[i].label = e.target.value })} /></td>
                  <td className="r" style={{ width: 130 }}><input className="inp num" type="number" step={0.1} min={0} max={10} disabled={ro} value={b.min} onChange={e => edit(x => { x.bands[i].min = Number(e.target.value) })} /></td>
                  <td style={{ width: 40 }}>{!ro && <button className="x" onClick={() => edit(x => { x.bands.splice(i, 1) })}>✕</button>}</td>
                </tr>))}
            </tbody></table>
            {!ro && <button className="btn btn-sm btn-ghost" onClick={() => edit(x => { x.bands.push({ label: 'New band', min: 0 }) })}>+ Add band</button>}
          </section>


          {fkey === 'vg' && c.tiers && (
            <section className="fw-card" id="fw-tiers">
              <div className="fw-h"><span>GP tiers — Marquee GP Index</span>
                {!ro && <GpPicker targets={c.tiers.map(t => ({ key: t.id, label: t.id }))}
                  current={m => c.tiers!.find(t => t.members.some(x => sameFirm(x, m)))?.id ?? null}
                  onPick={(m, tid) => edit(x => { x.tiers!.forEach(t => { t.members = t.members.filter(y => !sameFirm(y, m)) }); x.tiers!.find(t => t.id === tid)!.members.push(m) })} />}
              </div>
              <div className="sub" style={{ marginBottom: 10 }}>Points per investor in the current round. Each investor in a deal is matched to these firms by its website (not by words in its name), so adding a manager here changes how it scores.</div>
              {c.tiers.map((t, ti) => (
                <div className="fw-tier" key={ti}>
                  <div className="fw-tier-h">
                    <span className="badge badge-buyout">{t.id}</span>
                    <input className="inp" disabled={ro} value={t.label} onChange={e => edit(x => { x.tiers![ti].label = e.target.value })} />
                    <label className="fw-pt">Lead<input className="inp num" type="number" step={0.25} disabled={ro} value={t.lead} onChange={e => edit(x => { x.tiers![ti].lead = Number(e.target.value) })} /></label>
                    <label className="fw-pt">Participant<input className="inp num" type="number" step={0.25} disabled={ro} value={t.part} onChange={e => edit(x => { x.tiers![ti].part = Number(e.target.value) })} /></label>
                    <label className="fw-pt">Cap<input className="inp num" type="number" step={0.25} disabled={ro} value={t.cap ?? ''} placeholder="—" onChange={e => edit(x => { x.tiers![ti].cap = e.target.value === '' ? undefined : Number(e.target.value) })} /></label>
                  </div>
                  <MemberChips members={t.members} ro={ro} onRemove={i => edit(x => { x.tiers![ti].members.splice(i, 1) })} />
                </div>
              ))}
              <div className="grid2" style={{ marginTop: 12 }}>
                <div className="field"><label className="lbl">Marquee score = min(10, base + slope × points)</label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <label className="fw-pt">Base<input className="inp num" type="number" step={0.1} disabled={ro} value={c.marquee?.base ?? 1} onChange={e => edit(x => { x.marquee = { ...x.marquee!, base: Number(e.target.value) } })} /></label>
                    <label className="fw-pt">Slope<input className="inp num" type="number" step={0.05} disabled={ro} value={c.marquee?.slope ?? 0.6} onChange={e => edit(x => { x.marquee = { ...x.marquee!, slope: Number(e.target.value) } })} /></label>
                  </div></div>
                <div className="field"><label className="lbl">Valuation Justification Ratio thresholds</label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <label className="fw-pt">OK ≤<input className="inp num" type="number" step={0.1} disabled={ro} value={c.vjr?.ok ?? 1.5} onChange={e => edit(x => { x.vjr = { ...x.vjr!, ok: Number(e.target.value) } })} /></label>
                    <label className="fw-pt">Red flag &gt;<input className="inp num" type="number" step={0.1} disabled={ro} value={c.vjr?.caution ?? 3} onChange={e => edit(x => { x.vjr = { ...x.vjr!, caution: Number(e.target.value) } })} /></label>
                  </div></div>
              </div>
            </section>
          )}

          {fkey !== 'vg' && (
            <>
              <section className="fw-card" id="fw-rules">
                <div className="fw-h"><span>Weighting rules by transaction type</span></div>
                <div className="sub" style={{ marginBottom: 8 }}>How Claude should move the default weights for a given deal type.</div>
                <table className="fw-tbl"><thead><tr><th style={{ width: 220 }}>When</th><th>Rule</th><th /></tr></thead><tbody>
                  {(c.weighting_rules ?? []).map((r, i) => (
                    <tr key={i}>
                      <td><input className="inp" disabled={ro} value={r.when} onChange={e => edit(x => { x.weighting_rules![i].when = e.target.value })} /></td>
                      <td><textarea className="inp" rows={2} disabled={ro} value={r.rule} onChange={e => edit(x => { x.weighting_rules![i].rule = e.target.value })} /></td>
                      <td style={{ width: 40 }}>{!ro && <button className="x" onClick={() => edit(x => { x.weighting_rules!.splice(i, 1) })}>✕</button>}</td>
                    </tr>))}
                </tbody></table>
                {!ro && <button className="btn btn-sm btn-ghost" onClick={() => edit(x => { (x.weighting_rules ||= []).push({ when: '', rule: '' }) })}>+ Add rule</button>}
              </section>
              <section className="fw-card" id="fw-library">
                <div className="fw-h"><span>Sector library</span><span className="sub">{(c.sector_library ?? []).length} sub-sectors</span></div>
                <div className="sub" style={{ marginBottom: 10 }}>Sub-sector criteria and comps Claude reuses when a deal fits. Add a block when you see a new sub-sector.</div>
                {(c.sector_library ?? []).map((b, i) => (
                  <details className="fw-lib" key={i}>
                    <summary><span className="nm">{b.name || 'Untitled sub-sector'}</span>{b.anchor && <span className="sub"> · anchor {b.anchor}</span>}</summary>
                    <div className="grid2" style={{ marginTop: 10 }}>
                      <div className="field"><label className="lbl">Sub-sector</label><input className="inp" disabled={ro} value={b.name} onChange={e => edit(x => { x.sector_library![i].name = e.target.value })} /></div>
                      <div className="field"><label className="lbl">Calibration anchor</label><input className="inp" disabled={ro} value={b.anchor} placeholder="e.g. Apave — 6.16 / risk 38" onChange={e => edit(x => { x.sector_library![i].anchor = e.target.value })} /></div>
                    </div>
                    <div className="field"><label className="lbl">Sector-specific criteria</label><textarea className="inp" rows={3} disabled={ro} value={b.criteria} onChange={e => edit(x => { x.sector_library![i].criteria = e.target.value })} /></div>
                    <div className="field"><label className="lbl">Comps</label><textarea className="inp" rows={2} disabled={ro} value={b.comps} onChange={e => edit(x => { x.sector_library![i].comps = e.target.value })} /></div>
                    {!ro && <button className="btn btn-sm btn-ghost btn-danger" onClick={() => edit(x => { x.sector_library!.splice(i, 1) })}>Remove block</button>}
                  </details>
                ))}
                {!ro && <button className="btn btn-sm" onClick={() => edit(x => { (x.sector_library ||= []).push({ name: '', anchor: '', criteria: '', comps: '' }) })}>+ Add sub-sector</button>}
              </section>
            </>
          )}

          <section className="fw-card" id="fw-anchors">
            <div className="fw-h"><span>Calibration anchors</span></div>
            <div className="sub" style={{ marginBottom: 8 }}>Reference deals that keep new scores comparable.</div>
            <table className="fw-tbl"><thead><tr><th>Deal</th><th className="r">Score</th><th>Why it sits there</th><th /></tr></thead><tbody>
              {(c.anchors ?? []).map((a, i) => (
                <tr key={i}>
                  <td style={{ width: 220 }}><input className="inp" disabled={ro} value={a.deal} onChange={e => edit(x => { x.anchors![i].deal = e.target.value })} /></td>
                  <td style={{ width: 90 }}><input className="inp num" type="number" step={0.01} disabled={ro} value={a.score} onChange={e => edit(x => { x.anchors![i].score = Number(e.target.value) })} /></td>
                  <td><input className="inp" disabled={ro} value={a.note} onChange={e => edit(x => { x.anchors![i].note = e.target.value })} /></td>
                  <td style={{ width: 40 }}>{!ro && <button className="x" onClick={() => edit(x => { x.anchors!.splice(i, 1) })}>✕</button>}</td>
                </tr>))}
            </tbody></table>
            {!ro && <button className="btn btn-sm btn-ghost" onClick={() => edit(x => { (x.anchors ||= []).push({ deal: '', score: 5, risk: 50, note: '' }) })}>+ Add anchor</button>}
            <div className="field" style={{ marginTop: 10, marginBottom: 0 }}><label className="lbl">Calibration note</label>
              <textarea className="inp" rows={2} disabled={ro} value={c.calibration_note ?? ''} onChange={e => edit(x => { x.calibration_note = e.target.value })} /></div>
          </section>

          <section className="fw-card" id="fw-guidance">
            <div className="fw-h"><span>Analyst guidance</span>
              <div className="seg"><button className={!gPreview ? 'on' : ''} onClick={() => setGPreview(false)}>Edit</button><button className={gPreview ? 'on' : ''} onClick={() => setGPreview(true)}>Preview</button></div></div>
            <div className="sub" style={{ marginBottom: 8 }}>Stance, mandatory memo order and workflow Claude follows when researching and writing the memo (Markdown).</div>
            {gPreview
              ? <div className="md fw-md" dangerouslySetInnerHTML={{ __html: marked.parse(draft.guidance, { async: false }) as string }} />
              : <textarea className="inp mono fw-guid" disabled={ro} value={draft.guidance} onChange={e => setDraft(d => ({ ...d!, guidance: e.target.value }))} />}
          </section>
        </div>
      </div>

      {dirty && !ro && (
        <div className="fw-savebar">
          <span className="nm">Unsaved changes</span>
          {Math.abs(total - 100) > 0.01 && <span className="badge badge-red">Section weights total {total}</span>}
          <input className="inp" style={{ maxWidth: 360 }} placeholder="What changed? (shown in History)" value={note} onChange={e => setNote(e.target.value)} />
          <div className="grow" />
          <button className="btn" onClick={() => { setDraft(clone(fw)); setMsg(null) }} disabled={saving}>Discard</button>
          <button className="btn btn-gold" onClick={save} disabled={saving}>{saving ? 'Saving…' : fw.scope === 'main' ? `Save main framework as version ${fw.version + 1}` : 'Save to my framework'}</button>
        </div>
      )}
    </div>
  )
}

function ListEditor({ title, items, ro, placeholder, onChange }: { title: string; items: string[]; ro: boolean; placeholder: string; onChange: (v: string[]) => void }) {
  if (!items.length && ro) return null
  return (
    <div style={{ marginTop: 14 }}>
      <label className="lbl">{title}</label>
      {items.map((o, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
          <input className="inp" disabled={ro} value={o} placeholder={placeholder} onChange={e => { const n = [...items]; n[i] = e.target.value; onChange(n) }} />
          {!ro && <button className="x" onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button>}
        </div>
      ))}
      {!ro && <button className="btn btn-sm btn-ghost" onClick={() => onChange([...items, ''])}>+ Add</button>}
    </div>
  )
}

export function History({ fkey, current, ro, onRestore }: { fkey: string; current: number; ro: boolean; onRestore: (v: number) => void }) {
  const { data } = useQuery({ queryKey: ['fw-history', fkey], queryFn: async () => (await api.get<{ versions: Ver[] }>(`/frameworks/${fkey}/history/`)).data })
  return (
    <div className="fw-card" style={{ marginBottom: 14 }}>
      <div className="fw-h"><span>Version history</span></div>
      <table className="fw-tbl"><thead><tr><th>Version</th><th>When</th><th>By</th><th>What changed</th><th className="r">Analyses run</th><th /></tr></thead><tbody>
        {data?.versions.map(v => (
          <tr key={v.version}>
            <td className="mono">v{v.version}{v.version === current && <span className="badge badge-green" style={{ marginLeft: 6 }}>live</span>}</td>
            <td className="sub">{ago(v.created_at)}</td><td className="sub">{v.by ?? '—'}</td><td>{v.note || <span className="sub">—</span>}</td>
            <td className="r mono">{v.runs}</td>
            <td className="r">{!ro && v.version !== current && <button className="btn btn-sm" onClick={() => onRestore(v.version)}>Restore</button>}</td>
          </tr>))}
      </tbody></table>
    </div>
  )
}

export function Preview({ fkey, version, dirty }: { fkey: string; version: number; dirty: boolean }) {
  const { data } = useQuery({ queryKey: ['fw-preview', fkey, version], queryFn: async () => (await api.get<Fw>(`/frameworks/${fkey}/?preview=1`)).data })
  return (
    <div className="fw-card" style={{ marginBottom: 14 }}>
      <div className="fw-h"><span>What Claude sees — scorecard definition (v{version})</span></div>
      {dirty && <div className="warn-box" style={{ marginBottom: 8 }}>Showing the saved version — save to include your current edits.</div>}
      <pre className="fw-pre">{data?.prompt_preview ?? 'Loading…'}</pre>
    </div>
  )
}

/** The ADCG preferences that apply to this framework (shared across frameworks; edited in the ADCG preferences panel). */
function PrefsSection({ fkey }: { fkey: Key }) {
  const { data } = useQuery({ queryKey: ['framework', 'house'], queryFn: async () => (await api.get<{ config: HouseCfg }>('/frameworks/house/')).data })
  const prefs = (data?.config.preferences ?? []).filter(p => p.applies.includes(fkey))
  const other = (data?.config.preferences.length ?? 0) - prefs.length
  return (
    <section className="fw-card" id="fw-prefs">
      <div className="fw-h"><span>ADCG preferences</span><div className="grow" /><button className="btn btn-sm" onClick={openPrefs}>Edit ADCG preferences</button></div>
      <div className="sub" style={{ marginBottom: 10 }}>What ADCG likes and avoids on this kind of deal. Claude weighs these on every deal on this framework and
        works them into the memo; together they move the overall score by at most ±{data?.config.max_adjust ?? 0.5}.
        {other > 0 && ` ${other} other preference${other === 1 ? '' : 's'} appl${other === 1 ? 'ies' : 'y'} to other frameworks only.`}</div>
      {!data && <div className="note">Loading…</div>}
      {data && prefs.length === 0 && <div className="note">None apply to this framework yet.</div>}
      {prefs.map((p, i) => (
        <div className="hp-row" key={p.id || i}>
          <span className="hp-n">{i + 1}</span>
          <div className="hp-rm"><div className="hp-rt">{p.title} <span className={`hp-imp ${p.importance}`}>{p.importance}</span></div>
            <div className="hp-rg">{p.guidance}</div></div>
        </div>
      ))}
    </section>
  )
}

/** Whose framework this is: the MAIN framework (admins edit it; the team default) or the person's OWN copy. */
function ScopeBar({ fw, viewMain, setViewMain, onChanged, onError }: {
  fw: Fw; viewMain: boolean; setViewMain: (v: boolean) => void; onChanged: (t: string) => Promise<void>; onError: (t: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const act = async (f: () => Promise<unknown>, ok: string) => { setBusy(true); try { await f(); await onChanged(ok) } catch (e) { onError(errorText(e)) } setBusy(false) }
  if (fw.is_admin) {
    return (
      <div className="scope-bar main">
        <span className="scope-tag">Main framework</span>
        <span className="scope-txt">The team default — every analysis uses it unless the person running it has their own copy. Only admins change it.</span>
        <div className="grow" />
        {fw.pending_proposals > 0 && <button className="btn btn-sm btn-gold" onClick={() => go('account')}>{fw.pending_proposals} change request{fw.pending_proposals === 1 ? '' : 's'} to review →</button>}
      </div>
    )
  }
  if (viewMain) {
    return (
      <div className="scope-bar main">
        <span className="scope-tag">Main framework · read-only</span>
        <span className="scope-txt">This is the team default (version {fw.main_version}), set by the admin.</span>
        <div className="grow" />
        <button className="btn btn-sm" onClick={() => setViewMain(false)}>← Back to my framework</button>
      </div>
    )
  }
  const behind = fw.personal && fw.main_version > fw.base_version
  return (
    <div className={`scope-bar mine${fw.personal ? ' has' : ''}`}>
      <span className="scope-tag">{fw.personal ? 'My framework' : 'My framework · same as main'}</span>
      <span className="scope-txt">{fw.personal
        ? <>Only your analyses use it — nobody else sees these changes. Copied from main version {fw.base_version}{behind ? <b> · the main framework has since moved to version {fw.main_version}</b> : null}.</>
        : <>You're seeing the main framework. Save any change and it becomes your own copy — the main framework and everyone else stay as they are.</>}</span>
      <div className="grow" />
      <button className="btn btn-sm btn-ghost" onClick={() => setViewMain(true)}>View main</button>
      {fw.personal && <button className="btn btn-sm" disabled={busy} onClick={() => window.confirm('Drop your copy and go back to the main framework? Your changes will be lost.') &&
        void act(() => api.post(`/frameworks/${fw.key}/reset-mine/`), 'You are back on the main framework.')}>Reset to main</button>}
      {fw.personal && fw.differs && (fw.my_proposal
        ? <span className="badge badge-gold" title={fw.my_proposal.changes.join('\n')}>Proposal sent {ago(fw.my_proposal.created_at)} · awaiting admin</span>
        : <button className="btn btn-sm btn-gold" disabled={busy} onClick={() => {
            const note = window.prompt('Propose your framework to the admin for the main framework. Add a short reason (optional):', '')
            if (note !== null) void act(() => api.post(`/frameworks/${fw.key}/propose/`, { note }), 'Sent to the admin for approval — you will see the decision on your Account page.')
          }}>Propose to main framework</button>)}
    </div>
  )
}

interface GpTier { id: string; label: string; score: number; members: MemberIn[] }
interface GpsCfg { sponsor_tiers: GpTier[]; secondary_tiers: GpTier[]; unlisted_score: number | null }
interface GpsFw { config: GpsCfg; version: number; scope: 'main' | 'mine'; can_edit: boolean; is_admin: boolean; personal: boolean; name: string; description: string }

/** ADCG GP tiers — ONE list shared by ADCG Buyout and ADCG CV: buyout sponsors (Tier 1–3) and, for CVs, the lead
 *  secondaries investors (P1–P3). The engine scores the tier criteria from it. */
function GpTiersSection({ fkey }: { fkey: Key }) {
  const qc = useQueryClient()
  const { data: g, refetch } = useQuery({ queryKey: ['framework', 'gps'], queryFn: async () => (await api.get<GpsFw>('/frameworks/gps/')).data })
  const [d, setD] = useState<GpsCfg | null>(null)
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (g) setD(clone(g.config)) }, [g])
  if (!g || !d) return <section className="fw-card" id="fw-gps"><div className="note">Loading GP tiers…</div></section>
  const ro = !g.can_edit
  const dirty = JSON.stringify(d) !== JSON.stringify(g.config)
  const upd = (f: (c: GpsCfg) => void) => setD(x => { const n = clone(x!); f(n); return n })
  type Grp = 'sponsor_tiers' | 'secondary_tiers'
  const grps: Grp[] = fkey === 'cv' ? ['sponsor_tiers', 'secondary_tiers'] : ['sponsor_tiers']
  const targets = grps.flatMap(grp => d[grp].map((t, i) => ({ key: `${grp}:${i}`, label: t.id, cls: grp === 'secondary_tiers' ? 'sec' : '' })))
  const current = (m: GpMember) => {
    for (const grp of grps) { const i = d[grp].findIndex(t => t.members.some(x => sameFirm(x, m))); if (i >= 0) return `${grp}:${i}` }
    return null
  }
  const pick = (m: GpMember, key: string) => {
    const [grp, i] = key.split(':') as [Grp, string]
    upd(c => { c[grp].forEach(t => { t.members = t.members.filter(x => !sameFirm(x, m)) }); c[grp][Number(i)].members.push(m) })
  }
  async function save() {
    setBusy(true); setMsg(null)
    try {
      await api.put('/frameworks/gps/', { scope: g!.scope, config: d, guidance: '', name: g!.name, description: g!.description, note: 'GP tiers updated', base_version: g!.version })
      await refetch(); void qc.invalidateQueries({ queryKey: ['framework', 'gps'] })
      setMsg({ ok: true, t: g!.scope === 'main' ? 'Saved — the next Buyout and CV analyses use these tiers.' : 'Saved to your GP tiers — only your analyses use them.' })
    } catch (e) { setMsg({ ok: false, t: errorText(e) }) }
    setBusy(false)
  }
  const Group = ({ grp, title, sub }: { grp: 'sponsor_tiers' | 'secondary_tiers'; title: string; sub: string }) => (
    <div className="gp-grp">
      <div className="gp-gt">{title}</div><div className="sub" style={{ marginBottom: 8 }}>{sub}</div>
      {d[grp].map((t, i) => (
        <div className="gp-tier" key={t.id}>
          <div className="gp-th"><span className={`gp-badge t${i + 1}`}>{t.label}</span>
            <span className="note">scores</span>
            <input className="inp gp-score" type="number" min={1} max={10} step={0.5} disabled={ro} value={t.score} onChange={e => upd(c => { c[grp][i].score = Number(e.target.value) })} />
            <span className="note">/10 · {t.members.length} manager{t.members.length === 1 ? '' : 's'}</span></div>
          <MemberChips members={t.members} ro={ro} onRemove={j => upd(c => { c[grp][i].members.splice(j, 1) })} />
        </div>
      ))}
    </div>
  )
  return (
    <section className="fw-card" id="fw-gps">
      <div className="fw-h"><span>GP tiers</span>{!ro && <GpPicker targets={targets} current={current} onPick={pick} />}
        <div className="grow" />{g.scope === 'mine' && g.personal && <span className="badge badge-gold">My copy</span>}</div>
      <div className="sub" style={{ marginBottom: 12 }}>One list shared by ADCG Buyout and ADCG CV. The engine scores the
        {fkey === 'cv' ? ' “Underlying sponsor tier” and “Lead secondaries investor tier” criteria (the dual manager check)' : ' “Sponsor tier” criterion'} from it;
        a manager not on any list is scored by Claude from the evidence. Firms are matched by their website — The Sterling Group is
        not Sterling Investment Partners. Use <b>Find GP</b> to say or type a manager and drop it into a tier.</div>
      {Group({ grp: 'sponsor_tiers', title: 'Buyout sponsors', sub: fkey === 'cv' ? 'The underlying sponsor running the asset.' : 'The sponsor running the company.' })}
      {fkey === 'cv'
        ? Group({ grp: 'secondary_tiers', title: 'Lead secondaries investors', sub: 'Who is leading the CV transaction — the secondaries managers ADCG trusts most.' })
        : <div className="note" style={{ marginTop: 6 }}>Lead secondaries investors (P1–P3) are set on the ADCG CV page.</div>}
      {msg && <div className={msg.ok ? 'ok-box' : 'err-box'} style={{ marginTop: 10 }}>{msg.t}</div>}
      {dirty && !ro && <div className="gp-save"><span className="note">Unsaved GP tier changes</span><div className="grow" />
        <button className="btn btn-sm" onClick={() => setD(clone(g.config))} disabled={busy}>Discard</button>
        <button className="btn btn-sm btn-gold" onClick={() => void save()} disabled={busy}>{busy ? 'Saving…' : g.scope === 'main' ? 'Save GP tiers' : 'Save to my GP tiers'}</button></div>}
    </section>
  )
}
