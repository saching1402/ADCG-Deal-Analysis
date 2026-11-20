/** "How a deal is analysed" — the deal lead's flow (18-Nov-26), drawn on top of every framework page.
 *  Mirrors engine._run_job (digest → overview → research → risk → integrate → score → memo) and the memo structure in
 *  framework/memo_blueprint.md — keep the three in sync. */
import { useState } from 'react'

type Key = 'buyout' | 'cv' | 'vg' | 'fund'
type DKey = Exclude<Key, 'fund'>
type Src = 'mat' | 'web'
interface Step { n: number; title: string; src: Src[]; lead: string; does: string[]; out: string; kind?: 'plan' | 'out' }

const NAME: Record<Key, string> = { buyout: 'ADCG Buyout', cv: 'ADCG CV', vg: 'ADCG Venture Growth', fund: 'ADCG Fund Manager Evaluation' }
const SECTIONS: Record<DKey, string[]> = {
  buyout: ['Sector Focus', 'Sponsor Quality', 'Business Quality', 'Valuation & Leverage', 'Alignment'],
  cv: ['Sector Focus', 'Trophy Asset', 'Business Quality', 'Valuation & Leverage', 'Alignment'],
  vg: ['Theme', 'Valuation & Evolution', 'Investor Syndicate', 'Company & Management', 'Competition', 'Venture Fundamentals'],
}
const TERMS: Record<DKey, { title: string; items: string[] }> = {
  buyout: { title: 'Buyout / co-invest terms', items: ['Structure', 'EV', 'Adj. & reported EBITDA', 'Multiple', 'Leverage & debt terms',
    'Interest cover', 'Equity & sponsor cheque', 'Rollover / MIP', 'Fees & carry', 'Governance'] },
  cv: { title: 'CV terms', items: ['Single / multi-asset', 'CV size & unfunded', 'Price vs NAV', 'Lead secondaries investor',
    'LP election & roll rate', 'GP commitment & carry roll', 'CV fee, carry & hurdle', 'Term', 'Fairness opinion', 'Underlying EV / leverage'] },
  vg: { title: 'Round terms', items: ['Instrument', 'Pre / post-money', 'Raise', 'Valuation cap & discount', 'Liquidation preference',
    'Anti-dilution', 'Pro-rata', 'Board', 'Option pool', 'Leads & insiders'] },
}

function steps(k: DKey): Step[] {
  const vg = k === 'vg'
  return [
    { n: 1, title: 'Read the materials', src: ['mat'], lead: 'Every file read in full', out: 'Files tab',
      does: ['IM / CIM / SIM, market study, model, QoE, other reports', 'Notes the charts worth reusing, with their numbers', 'Unreadable or partly read files stop the run'] },
    { n: 2, title: 'Summarise the opportunity', src: ['mat'], lead: 'Mostly from the materials — the factual base', out: 'Research tab · Opportunity summary',
      does: ['Deal summary — every key term for the deal type', 'Company summary', 'Industry primer — the materials’ view', 'The claims to test'] },
    { n: 3, title: 'Independent market assessment', src: ['web', 'mat'], lead: 'The web contests the story', out: 'Research tab · Research & analysis',
      does: ['Is the industry growing at the rate claimed?', 'Claim by claim: confirmed · partly · not supported',
        'Competition beyond the IM, sponsor crowding, valuation hype', 'Risks to the industry · exitability'] },
    { n: 4, title: 'Risk review', src: ['mat', 'web'], lead: 'Every risk, all together', out: 'Risk review tab',
      does: ['One ranked list — the sponsor’s risks included', 'Everything the materials show', 'Everything the web shows: regulation, disruption, rates, macro, tariffs',
        '2nd- & 3rd-order effects · how sponsors fared'] },
    { n: 5, title: vg ? 'Plan, round & returns' : 'Business plan & returns', src: ['mat'], kind: 'plan', lead: 'History and plan together', out: 'Research tab · Business plan',
      does: [vg ? 'ARR, growth, margin, burn — history + plan' : 'Historicals + projections in one table', 'Every case: sponsor · management · ' + (k === 'cv' ? 'secondary lead' : 'other'),
        'What drives the returns — 3–4 points', 'Returns across scenarios', 'What looks overstated · our sensitivities'] },
    { n: 6, title: `Score — ${NAME[k]}`, src: [], kind: 'out', lead: 'Framework 90% · this deal 10%', out: 'Scorecard & Criteria tabs',
      does: ['Framework sections, scaled to 90%', '2–4 deal-specific factors picked for the sub-sector (10%)', vg ? 'Marquee GP Index · VJR' : 'GP tiers (sponsor' + (k === 'cv' ? ' + lead secondaries' : '') + ')',
        'ADCG preferences (±0.5) · no risk score'] },
    { n: 7, title: 'Write the IC memo', src: [], kind: 'out', lead: 'Structure below', out: 'IC memo tab', does: ['I · II · III · IV · Appendix', 'Key charts from the materials redrawn — bridge, history + plan, market — only where they help'] },
  ]
}

function Memo({ k }: { k: DKey }) {
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

const FUND_SECTIONS = ['Strategy & Positioning', 'Track Record', 'Underlying Portfolio Quality', 'Team & Stability', 'DDQ, ODD & Governance', 'Terms & Market Standing']
const FUND_STEPS: Step[] = [
  { n: 1, title: 'Read the data room', src: ['mat'], lead: 'Every file read in full', out: 'Files tab',
    does: ['PPM / pitch book, DDQ, ODD report, LPA & side letter', 'Track-record & portfolio workbook (deal-level, cash flows)', 'Unreadable files stop the run'] },
  { n: 2, title: 'The manager & strategy', src: ['mat', 'web'], lead: 'From the PPM, verified on the web', out: 'Research tab · Opportunity summary',
    does: ['Who: AUM, team size, HQ & offices, history', 'Strategy: segment, sectors, regions', 'Average EV & equity cheque · portfolio mix', 'Fund terms'] },
  { n: 3, title: 'Track record analytics', src: ['mat'], kind: 'plan', lead: 'Computed by the app from the workbook', out: 'Memo §3–4 · dashboard',
    does: ['Fund table: size, vintage, gross/net IRR, TVPI, DPI, quartile', 'Pooled MOIC / IRR · loss ratio · ex-top-2', 'By sector · deal lead · vintage', 'Dispersion & outliers'] },
  { n: 4, title: 'Background & standing', src: ['web'], lead: 'Independent checks on the web', out: 'Research tab',
    does: ['Partners: litigation, regulatory actions, press', 'Departures vs the DDQ', 'Peer ranking: HEC–Dow Jones, awards, quartile data', 'How the strategy is crowded'] },
  { n: 5, title: 'DDQ & ODD check', src: ['mat', 'web'], lead: 'What the manager disclosed vs what we found', out: 'Risk review tab',
    does: ['Litigation & key-person leavers', 'Operations, valuation policy, admin & audit', 'Conflicts, cyber, compliance', 'Red / amber / green summary'] },
  { n: 6, title: 'Score — ADCG Fund Manager', src: [], kind: 'out', lead: 'Framework 90% · this fund 10%', out: 'Scorecard & Criteria tabs',
    does: ['Six sections, scaled to 90%', '2–4 fund-specific factors (10%)', 'Manager tier from the ADCG GP lists', 'ADCG preferences · no risk score'] },
  { n: 7, title: 'Write the IC memo', src: [], kind: 'out', lead: 'Structure below + dashboard', out: 'IC memo tab', does: ['I · II · III · IV · Appendix', 'Track-record charts in the memo / PDF; HTML dashboard to download'] },
]

function FundFlow({ open, toggle }: { open: boolean; toggle: () => void }) {
  const part = (r: string, t: string, items?: string[], cls = '') => (
    <div className={`fm-part ${cls}`}><div className="fm-ph"><span>{r}</span>{t}</div>{items && <ol>{items.map(i => <li key={i}>{i}</li>)}</ol>}</div>
  )
  return (
    <section className={`flow${open ? '' : ' closed'}`} aria-label="How a fund manager is evaluated">
      <div className="flow-h">
        <div>
          <div className="eyebrow">How a fund manager is evaluated</div>
          <div className="flow-sub">The manager’s <b>data room</b> is the factual base — PPM, DDQ, ODD and the deal-level track record. The
            <b> app computes</b> the track-record numbers itself from the workbook (never estimated). The <b>web is the independent check</b>:
            people, litigation, departures and where the manager really ranks.</div>
        </div>
        <div className="grow" />
        <button className="btn btn-sm btn-ghost" onClick={toggle}>{open ? 'Hide' : 'Show'}</button>
      </div>
      {open && <>
        <div className="flow-lanes">
          <div className="flow-lane mat">
            <div className="fl-h"><span className="fsrc mat">Data room</span>The factual base</div>
            <div className="fl-chips">{['PPM / pitch book', 'DDQ', 'ODD report', 'Track-record workbook', 'LPA & terms'].map(c => <span key={c}>{c}</span>)}</div>
            <div className="fl-n">Manager · strategy · funds · every deal · cash flows · team · terms</div>
          </div>
          <div className="flow-lane web">
            <div className="fl-h"><span className="fsrc web">Web</span>The independent check</div>
            <div className="fl-chips">{['Court & regulator records', 'News & people checks', 'HEC–Dow Jones & rankings', 'Awards & LP commitments'].map(c => <span key={c}>{c}</span>)}</div>
            <div className="fl-n">Background · departures · litigation · peer standing</div>
          </div>
        </div>
        <ol className="flow-steps">
          {FUND_STEPS.map(s => (
            <li key={s.n} className={`flow-step${s.kind ? ' ' + s.kind : ''}`}>
              <div className="flow-feed"><i className={s.src.includes('mat') ? 'on mat' : ''} title="Data room" /><i className={s.src.includes('web') ? 'on web' : ''} title="Web" /></div>
              <div className="flow-n">{s.n}</div><div className="flow-t">{s.title}</div><div className="flow-lead">{s.lead}</div>
              <ul>{s.does.map(d => <li key={d}>{d}</li>)}</ul><div className="flow-out">→ {s.out}</div>
            </li>
          ))}
        </ol>
        <div className="flow-detail">
          <div className="fd-card plan">
            <div className="fd-h"><b>3</b> Track record — what the app computes</div>
            <div className="fd-chips">{['Pooled MOIC & IRR (cash-flow XIRR)', 'Loss ratio', 'Ex-top-1 / 2 / 3', 'Top-2 share of gains', 'By fund', 'By sector',
              'By deal lead', 'By vintage', 'MOIC vs cheque size', 'Outcome distribution', 'Realised share'].map(t => <span key={t}>{t}</span>)}</div>
            <div className="sub" style={{ marginTop: 6 }}>Charts go into the memo and PDF; the full sortable dashboard downloads from the memo toolbar.</div>
          </div>
          <div className="fd-card">
            <div className="fd-h"><b>5</b> DDQ & ODD — disclosed vs found</div>
            <div className="fd-chips">{['Litigation', 'Key people who left', 'Valuation policy', 'Fund admin & audit', 'Conflicts & allocation', 'Cyber & compliance',
              'Regulatory actions'].map(t => <span key={t}>{t}</span>)}</div>
          </div>
          <div className="fd-card">
            <div className="fd-h"><b>6</b> The score</div>
            <div className="wbar ds-bar" style={{ marginTop: 6 }}>
              {FUND_SECTIONS.map((n, i) => <div key={n} style={{ flex: '1 0 0', background: ['#0f2347', '#b38728', '#2453a6', '#1d7a47', '#8a6412', '#5b6678'][i] }} title={n} />)}
              <div className="ds" style={{ flex: `${FUND_SECTIONS.length / 9} 0 0` }}>10%</div>
            </div>
            <div className="sub" style={{ marginTop: 6 }}>{FUND_SECTIONS.join(' · ')} — share 90%; 10% for factors specific to this fund.</div>
          </div>
        </div>
        <div className="fm">
          <div className="fm-h">The IC memo</div>
          <div className="fm-grid">
            {part('I', 'Summary and Analysis', ['Introduction to the Manager', 'Strategy', 'Track Record', 'Underlying Portfolio Analysis',
              'Team and Management Biographies', 'Independent Background Verification', 'DDQ Check', 'Operational Due Diligence',
              'Market Standing and Peer Ranking', 'Fund Terms and Alignment'], 'wide')}
            {part('II', 'Investment Pros and Cons', ['Pros', 'Cons', 'Net assessment', 'Key risks'])}
            {part('III', 'ADCG Fund Manager Evaluation Scoring', [...FUND_SECTIONS, 'Framework Scoring Summary'])}
            {part('IV', 'Recommendation and Next Steps')}
            {part('A', 'Appendix', ['Sources and References', 'Definitions and Methodology'])}
          </div>
        </div>
      </>}
    </section>
  )
}

export function DealFlow({ fkey }: { fkey: Key }) {
  const [open, setOpen] = useState(() => { try { return localStorage.getItem('fw-flow') !== 'closed' } catch { return true } })
  const toggle = () => setOpen(o => { try { localStorage.setItem('fw-flow', o ? 'closed' : 'open') } catch { /* private mode */ } return !o })
  if (fkey === 'fund') return <FundFlow open={open} toggle={toggle} />
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
            <div className="fd-h"><b>4</b> The risk review — every risk, in one list</div>
            <div className="sub" style={{ margin: '4px 0 0' }}>All sources at the same time, ranked only by how material each risk is — the sponsor’s own risks included.</div>
            <div className="rk-layers">
              <div><b>Flagged by the sponsor</b> the IM’s risk section and mitigants</div>
              <div><b>Found in the materials</b> QoE, legal / commercial DD, market study, model</div>
              <div className="web"><b>Found on the web</b> industry reports, filings, news — what the sponsor may have missed</div>
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
