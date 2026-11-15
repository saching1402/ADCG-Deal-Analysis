import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { startAnalysis } from '../lib/analyze'
import { go } from '../lib/route'
import { bytes } from '../lib/format'
import type { DealRow, Track } from '../types'
import { useDeals } from '../App'
import { type UploadItem, uploadAll } from '../lib/upload'
import FilePicker from '../components/FilePicker'
import CompanySearch, { type CompanyHit } from '../components/CompanySearch'
import { Logo, domainOf } from '../components/Logo'

/** Rough per-deal cost (Nov-26 pipeline): Haiku 5.5 reads the files (~$0.025 per file + ~$0.003 per MB); the chosen
 *  model does independent research (≤40 searches), the risk review (≤18), data-room integration, scoring and a 3-part memo. */
function estimate(model: string, files: number, mb: number): [number, number] {
  const base = model.includes('opus') ? 13 : model.includes('haiku') ? 0.9 : 6.5
  const read = files * 0.025 + mb * 0.003
  const lo = base * 0.85 + read * 0.7, hi = base * 1.5 + read * 1.5
  return [Math.max(0.3, lo), hi]
}

export default function NewDealPage({ initialQ }: { initialQ: string }) {
  const qc = useQueryClient()
  const { data } = useDeals()
  const meta = data?.meta
  const [q, setQ] = useState(initialQ)
  const [picked, setPicked] = useState<CompanyHit | null>(null)
  const [name, setName] = useState(initialQ)
  const [website, setWebsite] = useState('')
  const [track, setTrack] = useState<Track>('auto')
  const [sponsor, setSponsor] = useState('')
  const [notes, setNotes] = useState('')
  const [model, setModel] = useState<string>('')
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [createdId, setCreatedId] = useState<string | null>(null)  // deal already created (an upload was rejected)

  if (!meta) return <div className="empty">Loading…</div>
  const mdl = model || meta.default_model
  const canRun = meta.api_key_set && !!name.trim() && items.some(x => x.state !== 'error')
  const patch = (key: string, p: Partial<UploadItem>) => setItems(xs => xs.map(x => (x.key === key ? { ...x, ...p } : x)))
  const totalMb = items.reduce((a, x) => a + x.file.size, 0) / 1048576
  const [lo, hi] = estimate(mdl, items.length, totalMb)

  function choose(c: CompanyHit) { setPicked(c); setName(c.name); setWebsite(c.domain); setQ(c.name) }
  function useTyped(s: string) { setPicked(null); setName(s); setQ(s) }
  function reset() { setPicked(null); setName(''); setWebsite(''); setQ('') }

  /** Nothing is created or run until the user presses Save draft or Run analysis. */
  async function submit(run: boolean) {
    if (!name.trim() || busy || (run && !canRun)) return
    setErr(null)
    try {
      let id = createdId
      if (!id) {
        setBusy('Creating deal…')
        id = (await api.post<DealRow>('/deals/', { name, website, track, sponsor, notes })).data.id
        setCreatedId(id)
      } else {
        await api.patch(`/deals/${id}/`, { name, website, track, sponsor, notes })
      }
      const pending = items.filter(x => x.state !== 'done')
      if (pending.length) {
        setBusy(`Uploading and checking ${pending.length} file(s)…`)
        const r = await uploadAll(id, items, patch)
        if (r.failed) {
          // never start an analysis with a file that failed its readability check
          setErr(`${r.failed} file(s) were rejected — see the reason next to each file. Remove them or upload a readable copy, then press ${run ? 'Run analysis' : 'Save'} again.`)
          setBusy(null)
          await qc.invalidateQueries({ queryKey: ['deals'] })
          return
        }
      }
      if (run) { setBusy('Starting analysis…'); await startAnalysis(id, { model: mdl }) }
      await qc.invalidateQueries({ queryKey: ['deals'] })
      go(`deal-${id}`)
    } catch (e) { setErr(errorText(e)); setBusy(null) }
  }

  const domain = domainOf(website)
  return (
    <div className="page">
      <div className="nd-head">
        <div className="eyebrow">New deal</div>
        <div className="h1">Analyse a company on the ADCG framework</div>
        <div className="lead">Find the company, add the deal terms and drop in the data room. Claude reads every file, researches the web,
          scores the deal on the ADCG Buyout or Venture Growth framework and writes the IC memo — usually 15–25 minutes. Nothing runs until you press <b>Run analysis</b>.</div>
      </div>

      <div className="nd-grid">
        <div>
          <section className="nd-sec">
            <div className="nd-step"><span>1</span>Company</div>
            {name && (picked || website) ? (
              <div className="nd-co">
                <Logo domain={domain} name={name} size={52} />
                <div className="grow">
                  <div className="nd-co-name">{name}</div>
                  <div className="sub">{domain || 'no website'}{picked?.description ? ` · ${picked.description}` : ''}</div>
                </div>
                <button className="btn btn-sm" onClick={reset}>Change</button>
              </div>
            ) : (
              <CompanySearch mode="company" big autoFocus value={q} onChange={v => { setQ(v); setName(v) }}
                placeholder="Search for a company — e.g. Apave, Baseten, Cognition…"
                onPickDeal={id => go(`deal-${id}`)} onPickCompany={choose} onNewDeal={useTyped} />
            )}
            <div className="grid2" style={{ marginTop: 14 }}>
              <div className="field">
                <label className="lbl" htmlFor="nd-name">Deal name</label>
                <input id="nd-name" className="inp" value={name} onChange={e => setName(e.target.value)} placeholder="Company or deal name" />
              </div>
              <div className="field">
                <label className="lbl" htmlFor="nd-web">Website</label>
                <input id="nd-web" className="inp" value={website} onChange={e => setWebsite(e.target.value)} placeholder="company.com — used for the logo and research" />
              </div>
            </div>
          </section>

          <section className="nd-sec">
            <div className="nd-step"><span>2</span>Deal details</div>
            <div className="field">
              <label className="lbl">Framework</label>
              <div className="seg">
                {([['auto', 'Auto-detect'], ['buyout', 'ADCG Buyout'], ['vg', 'ADCG Venture Growth']] as [Track, string][]).map(([v, l]) => (
                  <button key={v} type="button" className={track === v ? 'on' : ''} onClick={() => setTrack(v)}>{l}</button>
                ))}
              </div>
              <div className="sub" style={{ marginTop: 6 }}>Auto-detect: buyouts, co-invests, CVs and secondaries → Buyout; priced Seed–pre-IPO rounds → Venture Growth.</div>
            </div>
            <div className="field">
              <label className="lbl" htmlFor="nd-sp">Sponsor / lead investors</label>
              <input id="nd-sp" className="inp" value={sponsor} onChange={e => setSponsor(e.target.value)} placeholder="e.g. PAI Partners (single-asset CV) · or Thrive-led Series C" />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label className="lbl" htmlFor="nd-notes">Terms &amp; what to test</label>
              <textarea id="nd-notes" className="inp" rows={4} value={notes} onChange={e => setNotes(e.target.value)}
                placeholder="EV, EBITDA, multiple, leverage, round size, pre/post-money, structure, your initial view, what the memo must answer…" />
            </div>
          </section>

          <section className="nd-sec">
            <div className="nd-step"><span>3</span>Data room</div>
            <FilePicker meta={meta} items={items} setItems={setItems} disabled={!!busy} />
          </section>
        </div>

        <aside className="nd-side">
          <div className="nd-card">
            <div className="kpi-lbl">Summary</div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', margin: '8px 0 12px' }}>
              <Logo domain={domain} name={name || '?'} size={36} />
              <div><div className="nm">{name || 'No company yet'}</div><div className="sub">{domain || '—'}</div></div>
            </div>
            <div className="nd-kv"><span>Framework</span><b>{track === 'vg' ? 'Venture Growth' : track === 'buyout' ? 'Buyout' : 'Auto-detect'}</b></div>
            <div className="nd-kv"><span>Files</span><b>{items.length} · {bytes(Math.round(totalMb * 1048576))}</b></div>
            <div className="field" style={{ margin: '12px 0 10px' }}>
              <label className="lbl" htmlFor="nd-model">Analysis model</label>
              <select id="nd-model" className="sel" style={{ width: '100%' }} value={mdl} onChange={e => setModel(e.target.value)}>
                {meta.models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </div>
            <div className="nd-cost">
              <div className="kpi-lbl">Estimated cost</div>
              <div className="nd-cost-v">${lo.toFixed(lo < 2 ? 1 : 0)}–{hi.toFixed(hi < 2 ? 1 : 0)}</div>
              <div className="sub">Files read by {meta.models.find(m => m.id === meta.digest_model)?.label.split(' ·')[0] ?? 'Haiku'}; research, scoring &amp; memo by the model above. Exact cost shows in the deal's Runs tab.
                {meta.recent_costs?.[mdl] && <> Your last {meta.recent_costs[mdl].n} completed run{meta.recent_costs[mdl].n === 1 ? '' : 's'} on this model averaged <b>${meta.recent_costs[mdl].avg.toFixed(2)}</b> (${meta.recent_costs[mdl].min.toFixed(2)}–{meta.recent_costs[mdl].max.toFixed(2)}).</>}</div>
            </div>
            <div className="nd-check">
              <div className={name.trim() ? 'ok' : ''}>{name.trim() ? '✓' : '○'} Company selected</div>
              <div className={items.length ? 'ok' : ''}>{items.length ? '✓' : '○'} Data-room files attached ({items.length})</div>
              <div className={notes.trim() || sponsor.trim() ? 'ok' : 'opt'}>{notes.trim() || sponsor.trim() ? '✓' : '○'} Deal terms &amp; sponsor <span className="sub">(optional)</span></div>
            </div>
            {!meta.api_key_set && <div className="warn-box" style={{ marginTop: 8 }}>Set ANTHROPIC_API_KEY on Railway to run analyses.</div>}
            {err && <div className="err-box" style={{ marginTop: 10 }}>{err}</div>}
            <button className="btn btn-primary nd-go" onClick={() => submit(true)} disabled={!canRun || !!busy}
              title={canRun ? '' : 'Add the company and at least one file first'}>
              {busy ?? 'Run analysis →'}
            </button>
            {!canRun && !busy && <div className="sub" style={{ textAlign: 'center', marginTop: 6 }}>Unlocks once the company and at least one file are added.</div>}
            <button className="btn" style={{ width: '100%', justifyContent: 'center', marginTop: 8 }} onClick={() => submit(false)} disabled={!name.trim() || !!busy}>
              Save as draft (don't run)
            </button>
            <button className="btn btn-ghost" style={{ width: '100%', justifyContent: 'center', marginTop: 6 }} onClick={() => go('')} disabled={!!busy}>Cancel</button>
          </div>
        </aside>
      </div>
    </div>
  )
}
