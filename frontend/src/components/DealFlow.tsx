/** "How a deal is analysed" — the deal lead's flow (18-Nov-26), drawn on top of every framework page.
 *  Mirrors engine._run_job (digest → overview → research → risk → integrate → score → memo) and the memo structure in
 *  framework/memo_blueprint.md — keep the three in sync. */
import { useState } from 'react'

type Key = 'buyout' | 'cv' | 'vg'
type Src = 'mat' | 'web'
interface Step { n: number; title: string; src: Src[]; lead: string; does: string[]; out: string; kind?: 'plan' | 'out' }

const NAME: Record<Key, string> = { buyout: 'ADCG Buyout', cv: 'ADCG CV', vg: 'ADCG Venture Growth' }
const SECTIONS: Record<Key, string[]> = {
  buyout: ['Sector Focus', 'Sponsor Quality', 'Business Quality', 'Valuation & Leverage', 'Alignment'],
  cv: ['Sector Focus', 'Trophy Asset', 'Business Quality', 'Valuation & Leverage', 'Alignment'],
  vg: ['Theme', 'Valuation & Evolution', 'Investor Syndicate', 'Company & Management', 'Competition', 'Venture Fundamentals'],
}
const TERMS: Record<Key, { title: string; items: string[] }> = {
  buyout: { title: 'Buyout / co-invest terms', items: ['Structure', 'EV', 'Adj. & reported EBITDA', 'Multiple', 'Leverage & debt terms',
    'Interest cover', 'Equity & sponsor cheque', 'Rollover / MIP', 'Fees & carry', 'Governance'] },
  cv: { title: 'CV terms', items: ['Single / multi-asset', 'CV size & unfunded', 'Price vs NAV', 'Lead secondaries investor',
    'LP election & roll rate', 'GP commitment & carry roll', 'CV fee, carry & hurdle', 'Term', 'Fairness opinion', 'Underlying EV / leverage'] },
  vg: { title: 'Round terms', items: ['Instrument', 'Pre / post-money', 'Raise', 'Valuation cap & discount', 'Liquidation preference',
    'Anti-dilution', 'Pro-rata', 'Board', 'Option pool', 'Leads & insiders'] },
}

function steps(k: Key): Step[] {
  const vg = k === 'vg'
  return [
    { n: 1, title: 'Read the materials', src: ['mat'], lead: 'Every file read in full', out: 'Files tab',
      does: ['IM / CIM / SIM, market study, model, QoE, other reports', 'Unreadable or partly read files stop the run'] },
    { n: 2, title: 'Summarise the opportunity', src: ['mat'], lead: 'Mostly from the materials — the factual base', out: 'Research tab · Opportunity summary',
      does: ['Deal summary — every key term for the deal type', 'Company summary', 'Industry primer — the materials’ view', 'The claims to test'] },
    { n: 3, title: 'Independent market assessment', src: ['web', 'mat'], lead: 'The web contests the story', out: 'Research tab · Research & analysis',
      does: ['Is the industry growing at the rate claimed?', 'Claim by claim: confirmed · partly · not supported',
        'Competition beyond the IM, sponsor crowding, valuation hype', 'Risks to the industry · exitability'] },
    { n: 4, title: 'Risk review', src: ['mat', 'web'], lead: 'Sponsor’s risks, then the rest', out: 'Risk review tab',
      does: ['Risks the sponsor flags', 'Risks found across all the materials', 'Sense-checked on the web: regulation, disruption, rates, macro, tariffs',
        '2nd- & 3rd-order effects · how sponsors fared'] },
    { n: 5, title: vg ? 'Plan, round & returns' : 'Business plan & returns', src: ['mat'], kind: 'plan', lead: 'History and plan together', out: 'Research tab · Business plan',
      does: [vg ? 'ARR, growth, margin, burn — history + plan' : 'Historicals + projections in one table', 'Every case: sponsor · management · ' + (k === 'cv' ? 'secondary lead' : 'other'),
        'What drives the returns — 3–4 points', 'Returns across scenarios', 'What looks overstated · our sensitivities'] },
    { n: 6, title: `Score — ${NAME[k]}`, src: [], kind: 'out', lead: 'Framework 90% · this deal 10%', out: 'Scorecard & Criteria tabs',
      does: ['Framework sections, scaled to 90%', '2–4 deal-specific factors picked for the sub-sector (10%)', vg ? 'Marquee GP Index · VJR' : 'GP tiers (sponsor' + (k === 'cv' ? ' + lead secondaries' : '') + ')',
        'ADCG preferences (±0.5) · no risk score'] },
    { n: 7, title: 'Write the IC memo', src: [], kind: 'out', lead: 'Structure below', out: 'IC memo tab', does: ['I · II · III · IV · Appendix'] },
  ]
}

function Memo({ k }: { k: Key }) {
  const part = (r: string, t: string, items?: string[], cls = '') => (
    <div className={`fm-part ${cls}`}>
      <div className="fm-ph"><span>{r}</span>{t}</div>
      {items && <ol>{items.map(i => <li key={i}>{i}</li>)}</ol>}
    </div>
  )
  return (
    <div className="fm">
      <div className="fm-h">The IC memo</div>
      <div className="fm-grid">
        {part('I', 'Summary and Analysis', ['Deal Overview', 'Company Overview', 'Industry Primer and Independent Market Assessment',
          'Business Model, Value Chain, Competitive Landscape and Exitability', 'Value Creation Plan', 'Financials and Business Plan',
          'Valuation Analysis', 'Returns Analysis and Independent Sensitivities'], 'wide')}
        {part('II', 'Investment Pros and Cons', ['Pros', 'Cons', 'Net assessment', 'Key risks'])}
        {part('III', `${NAME[k]} Deal Scoring`, [...SECTIONS[k], 'Framework Scoring Summary'])}
        {part('IV', 'Recommendation and Next Steps')}
        {part('A', 'Appendix', ['Sources and References', 'Definitions and Methodology'])}
      </div>
    </div>
  )
}

export function DealFlow({ fkey }: { fkey: Key }) {
  const [open, setOpen] = useState(() => { try { return localStorage.getItem('fw-flow') !== 'closed' } catch { return true } })
  const toggle = () => setOpen(o => { try { localStorage.setItem('fw-flow', o ? 'closed' : 'open') } catch { /* private mode */ } return !o })
  const terms = TERMS[fkey]
  return (
    <section className={`flow${open ? '' : ' closed'}`} aria-label="How a deal is analysed">
      <div className="flow-h">
        <div>
          <div className="eyebrow">How a deal is analysed</div>
          <div className="flow-sub">The sponsor’s materials are the <b>factual base</b> — reviewed by many sophisticated LPs, so the numbers and
            terms are summarised faithfully. The <b>web is the sense check</b>: it tests the industry story, the competition and anything the
            manager may have oversold.</div>
        </div>
        <div className="grow" />
        <button className="btn btn-sm btn-ghost" onClick={toggle}>{open ? 'Hide' : 'Show'}</button>
      </div>
      {open && <>
        <div className="flow-lanes">
          <div className="flow-lane mat">
            <div className="fl-h"><span className="fsrc mat">Materials</span>The factual base</div>
            <div className="fl-chips">{['Information memorandum', 'Market study', 'Financial model', 'QoE & other reports'].map(c => <span key={c}>{c}</span>)}</div>
            <div className="fl-n">Deal terms · company · historicals · business plan · sponsor cases</div>
          </div>
          <div className="flow-lane web">
            <div className="fl-h"><span className="fsrc web">Web</span>The sense check</div>
            <div className="fl-chips">{['Independent market reports', 'Listed peers & filings', 'Comps & precedents', 'News & people checks'].map(c => <span key={c}>{c}</span>)}</div>
            <div className="fl-n">Industry growth · competition · exits · risks the materials leave out</div>
          </div>
        </div>
        <ol className="flow-steps">
          {steps(fkey).map(s => (
            <li key={s.n} className={`flow-step${s.kind ? ' ' + s.kind : ''}`}>
              <div className="flow-feed">
                <i className={s.src.includes('mat') ? 'on mat' : ''} title="Materials" /><i className={s.src.includes('web') ? 'on web' : ''} title="Web" />
              </div>
              <div className="flow-n">{s.n}</div>
              <div className="flow-t">{s.title}</div>
              <div className="flow-lead">{s.lead}</div>
              <ul>{s.does.map(d => <li key={d}>{d}</li>)}</ul>
              <div className="flow-out">→ {s.out}</div>
            </li>
          ))}
        </ol>
        <div className="flow-detail">
          <div className="fd-card">
            <div className="fd-h"><b>2</b> The summary — deal, company, industry</div>
            <div className="fd-sub">{terms.title}, replicated from the materials (“not disclosed” where missing)</div>
            <div className="fd-chips">{terms.items.map(t => <span key={t}>{t}</span>)}</div>
          </div>
          <div className="fd-card">
            <div className="fd-h"><b>4</b> The risk review — three layers</div>
            <div className="rk-layers">
              <div><span className="rk-n">A</span><b>Sponsor-flagged</b> the IM’s own risk section and mitigants</div>
              <div><span className="rk-n">B</span><b>Across the materials</b> QoE, legal / commercial DD, market study, model</div>
              <div className="web"><span className="rk-n">C</span><b>Independent, on the web</b> what the sponsor may have missed</div>
            </div>
            <div className="fd-chips">{['Regulatory pressure', 'Disruption & AI', 'Interest rates & refinancing', 'Capital structure', 'Macro & recession',
              'Geopolitics & tariffs', 'Input costs & labour', '2nd- & 3rd-order effects', 'Sponsor graveyard themes'].map(t => <span key={t}>{t}</span>)}</div>
          </div>
          <div className="fd-card plan">
            <div className="fd-h"><b>5</b> The business plan</div>
            <div className="bp-viz" aria-hidden>
              {['FY-3', 'FY-2', 'FY-1', 'LTM'].map((y, i) => <div key={y} className="bpb act" style={{ height: 26 + i * 7 }}><em>{y}</em></div>)}
              {['FY+1', 'FY+2', 'FY+3', 'FY+4', 'Exit'].map((y, i) => <div key={y} className="bpb plan" style={{ height: 56 + i * 9 }}><em>{y}</em></div>)}
            </div>
            <div className="bp-leg"><span className="act">Historicals — exactly as in the materials</span><span className="plan">Sponsor projections — model, tied to the IM</span></div>
            <div className="bp-rows">
              <div><b>Cases</b> sponsor · management{fkey === 'cv' ? ' · secondary lead’s haircut case' : ' · any other in the materials'} — side by side</div>
              <div><b>What drives the returns</b> 3–4 points: {fkey === 'vg' ? 'ARR growth · milestones · multiple · dilution' : 'organic · bolt-on M&A · transformational M&A · margin'}</div>
              <div><b>Returns across scenarios</b> MOIC / IRR for every case, as presented</div>
              <div className="ovr"><b>What looks overstated</b> e.g. plan +15% p.a. vs market +5% · $140m of M&A EBITDA planned vs $70m bought to date</div>
              <div className="indep"><b>ADCG independent review</b> our case and sensitivities — {fkey === 'vg' ? 'exit valuation × dilution → MOIC' : 'exit multiple × EBITDA → MOIC / IRR'}</div>
            </div>
          </div>
          <div className="fd-card">
            <div className="fd-h"><b>6</b> The score</div>
            <div className="sc-mock">
              <div className="scm-l"><span>{NAME[fkey]}</span><b>7.2</b><em>Positive</em></div>
              <div className="scm-r">
                <div><span>{fkey === 'vg' ? 'Marquee GP Index' : fkey === 'cv' ? 'Sponsor · lead secondaries' : 'Sponsor'}</span><i>{fkey === 'vg' ? '8.2 / 10' : fkey === 'cv' ? 'Tier 1 · P1' : 'Tier 1'}</i></div>
                <div><span>Deal-specific</span><i>picked per deal</i></div>
              </div>
            </div>
            <div className="wbar ds-bar" style={{ marginTop: 10 }}>
              {SECTIONS[fkey].map((n, i) => <div key={n} style={{ flex: '1 0 0', background: ['#0f2347', '#b38728', '#2453a6', '#1d7a47', '#8a6412', '#5b6678'][i] }} title={n} />)}
              <div className="ds" style={{ flex: `${SECTIONS[fkey].length / 9} 0 0` }}>10%</div>
            </div>
            <div className="sub" style={{ marginTop: 6 }}>Framework sections share 90%; 10% goes to factors picked for the deal’s sub-sector — e.g. pharma: patent cliff;
              software: net revenue retention. The memo’s Part III opens with the total score and the GP tier.</div>
          </div>
        </div>
        <Memo k={fkey} />
        <div className="flow-foot">No data room? Steps 2–4 use public sources only, step 5 lists what a data room would have to answer, and every
          company figure is tagged HARD or ESTIMATE.</div>
      </>}
    </section>
  )
}
