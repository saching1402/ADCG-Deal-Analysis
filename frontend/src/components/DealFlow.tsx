/** "How a deal is analysed" — the deal lead's flow, shown on top of every framework page. Mirrors engine._run_job. */
import { useState } from 'react'

type Key = 'buyout' | 'cv' | 'vg'
type Src = 'mat' | 'web'
interface Step { n: number; title: string; src: Src[]; web?: string; does: string[]; out: string }

const NAME: Record<Key, string> = { buyout: 'ADCG Buyout', cv: 'ADCG CV', vg: 'ADCG Venture Growth' }
const MEMO: Record<Key, string> = {
  buyout: 'Company overview · Industry primer · Business model, value chain & competition · Transaction & key findings · Financials, plan & valuation · Scores · Verdict · Key risks · Pros & Cons · Recommendation',
  cv: 'Company overview · Industry primer · Business model, value chain & competition · Transaction & key findings · Financials, plan & valuation · Scores · Verdict · Key risks · Pros & Cons · Recommendation',
  vg: 'Company overview · Theme & technology primer · Business model, value chain & competition · Latest round & key findings · Financials & valuation evolution · Scores · Verdict · Pros & Cons · Recommendation · Key risks',
}

function steps(k: Key): Step[] {
  return [
    { n: 1, title: 'Read the materials', src: ['mat'], out: 'Files tab — a fact sheet per file',
      does: ['Every file read in full — IM / CIM / SIM, model, QoE, market study', 'Unreadable or partly read files stop the run'] },
    { n: 2, title: 'Summarise the opportunity', src: ['mat', 'web'], web: '≤ 10 searches', out: 'Research tab — Opportunity summary',
      does: ['What the company does, for whom, how it delivers', 'How it makes money · customers · value chain',
        'Competition (the IM’s list + the web’s) · history · management · the deal', 'The IM leads the description; the web verifies it'] },
    { n: 3, title: 'Research & analysis', src: ['mat', 'web'], web: '≤ 28 searches', out: 'Research tab — Research & analysis',
      does: [k === 'vg' ? 'Theme & technology from first principles' : 'Industry from first principles', 'Market, competitors beyond the IM, people checks',
        'Comps & valuation', 'Tests every claim the materials make'] },
    { n: 4, title: 'Risk review', src: ['web', 'mat'], web: '≤ 18 searches', out: 'Risk review tab',
      does: ['How sponsors fared in this sub-sector', 'Sponsor / investor record', '2nd- & 3rd-order risks, capital structure, exit'] },
    { n: 5, title: k === 'vg' ? 'Plan, round & reconciliation' : 'Business plan & reconciliation', src: ['mat'], web: '≤ 6 checks', out: 'Research tab · headline facts',
      does: ['Actuals and management’s 5-year plan vs history & peers', 'Where growth comes from · terms',
        'Reconciles IM, model, QoE', 'Which risks the IM discloses, understates or omits'] },
    { n: 6, title: `Score — ${NAME[k]}`, src: [], out: 'Scorecard & Criteria tabs',
      does: ['Sections & criteria below, weighted', k === 'vg' ? 'Marquee GP Index from the GP tiers · VJR' : 'GP tiers (sponsor' + (k === 'cv' ? ' + lead secondaries' : '') + ')',
        'ADCG preferences (±0.5)', 'No risk score — risks are highlighted'] },
    { n: 7, title: 'Write the IC memo', src: [], out: 'IC memo tab', does: [MEMO[k]] },
  ]
}

export function DealFlow({ fkey }: { fkey: Key }) {
  const [open, setOpen] = useState(() => { try { return localStorage.getItem('fw-flow') !== 'closed' } catch { return true } })
  const toggle = () => setOpen(o => { try { localStorage.setItem('fw-flow', o ? 'closed' : 'open') } catch { /* private mode */ } return !o })
  return (
    <section className={`flow${open ? '' : ' closed'}`} aria-label="How a deal is analysed">
      <div className="flow-h">
        <div>
          <div className="eyebrow">How a deal is analysed</div>
          <div className="flow-sub">Every run follows these steps. The deal materials and the web are used <b>together</b> — the materials describe the
            business and give the numbers only the company has; the web verifies them and adds the market, competition, comps and risks.</div>
        </div>
        <div className="grow" />
        <div className="flow-key"><span className="fsrc mat">Materials</span><span className="fsrc web">Web</span></div>
        <button className="btn btn-sm btn-ghost" onClick={toggle}>{open ? 'Hide' : 'Show'}</button>
      </div>
      {open && <>
        <ol className="flow-steps">
          {steps(fkey).map(s => (
            <li key={s.n} className={`flow-step${s.n >= 6 ? ' out' : ''}`}>
              <div className="flow-n">{s.n}</div>
              <div className="flow-t">{s.title}</div>
              <div className="flow-srcs">
                {s.src.map(x => <span key={x} className={`fsrc ${x}`}>{x === 'mat' ? 'Materials' : 'Web'}</span>)}
                {s.web && <span className="flow-web">{s.web}</span>}
              </div>
              <ul>{s.does.map(d => <li key={d}>{d}</li>)}</ul>
              <div className="flow-out">→ {s.out}</div>
            </li>
          ))}
        </ol>
        <div className="flow-foot">No data room? Steps 2–4 use public sources only, step 5 lists what a data room would have to answer, and every
          company figure is tagged HARD or ESTIMATE.</div>
      </>}
    </section>
  )
}
