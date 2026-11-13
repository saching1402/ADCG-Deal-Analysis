import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { go } from '../lib/route'
import { bytes } from '../lib/format'
import type { DealRow, Track } from '../types'
import { useDeals } from '../App'
import { type UploadItem, uploadAll } from '../lib/upload'
import FilePicker from '../components/FilePicker'
import CompanySearch, { type CompanyHit } from '../components/CompanySearch'
import { Logo, domainOf } from '../components/Logo'

/** Rough per-deal cost: Haiku reads the files (~$0.06 per file + ~$0.012 per MB), the chosen model does research, scoring and memo. */
function estimate(model: string, files: number, mb: number): [number, number] {
  const base = model.includes('opus') ? 6 : model.includes('haiku') ? 0.6 : 2.6
  const read = files * 0.06 + mb * 0.012
  const lo = base * 0.8 + read * 0.8, hi = base * 1.6 + read * 1.5
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
  const [analyze, setAnalyze] = useState(true)
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  if (!meta) return <div className="empty">Loading…</div>
  const mdl = model || meta.default_model
  const canRun = meta.api_key_set && analyze
  const patch = (key: string, p: Partial<UploadItem>) => setItems(xs => xs.map(x => (x.key === key ? { ...x, ...p } : x)))
  const totalMb = items.reduce((a, x) => a + x.file.size, 0) / 1048576
  const [lo, hi] = estimate(mdl, items.length, totalMb)

  function choose(c: CompanyHit) { setPicked(c); setName(c.name); setWebsite(c.domain); setQ(c.name) }
  function useTyped(s: string) { setPicked(null); setName(s); setQ(s) }
  function reset() { setPicked(null); setName(''); setWebsite(''); setQ('') }

  async function submit() {
    if (!name.trim() || busy) return
    setErr(null)
    try {
      setBusy('Creating deal…')
      const { data: deal } = await api.post<DealRow>('/deals/', { name, website, track, sponsor, notes })
      if (items.length) {
        setBusy(`Uploading ${items.length} file(s)…`)
        const r = await uploadAll(deal.id, items, patch)
        if (r.failed) setErr(`${r.failed} file(s) failed to upload — the deal was created; retry them from its Files tab.`)
      }
      if (canRun) { setBusy('Starting analysis…'); await api.post(`/deals/${deal.id}/analyze/`, { model: mdl }) }
      await qc.invalidateQueries({ queryKey: ['deals'] })
      go(`deal-${deal.id}`)
    } catch (e) { setErr(errorText(e)); setBusy(null) }
  }

  const domain = domainOf(website)
  return (
    <div className="page">
      <div className="nd-head">
        <div className="eyebrow">New deal</div>
        <div className="h1">Analyse a company on the ADCG framework</div>
        <div className="lead">Find the company, add the deal terms and drop in the data room. Claude reads every file, researches the web,
          scores the deal on the ADCG Buyout or Venture Growth framework and writes the IC memo — usually 15–25 minutes.</div>
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
              <div className="sub">Files read by {meta.models.find(m => m.id === meta.digest_model)?.label.split(' ·')[0] ?? 'Haiku'}; research, scoring &amp; memo by the model above. Exact cost shows in the deal's Runs tab.</div>
            </div>
            <label className="nd-chk">
              <input type="checkbox" checked={canRun} disabled={!meta.api_key_set} onChange={e => setAnalyze(e.target.checked)} />
              Start the analysis once files are uploaded
            </label>
            {!meta.api_key_set && <div className="warn-box" style={{ marginTop: 8 }}>Set ANTHROPIC_API_KEY on Railway to run analyses.</div>}
            {err && <div className="err-box" style={{ marginTop: 10 }}>{err}</div>}
            <button className="btn btn-primary nd-go" onClick={submit} disabled={!name.trim() || !!busy}>
              {busy ?? (canRun ? 'Add deal & analyse →' : 'Add deal')}
            </button>
            <button className="btn btn-ghost" style={{ width: '100%', justifyContent: 'center', marginTop: 6 }} onClick={() => go('')} disabled={!!busy}>Cancel</button>
          </div>
        </aside>
      </div>
    </div>
  )
}
