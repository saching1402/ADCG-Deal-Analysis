import { useState } from 'react'
import CompanySearch from '../components/CompanySearch'
import { go } from '../lib/route'
import { useDeals } from '../App'
import { useMe, nameOf } from './AccountPage'

const greet = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }

/** The landing page: a quiet, glossy canvas with one thing to do — analyse a new deal. Everything else is in the tabs. */
export default function HomePage() {
  const [q, setQ] = useState('')
  const { data } = useDeals()
  const { data: me } = useMe()
  const canEdit = data?.can_edit ?? true
  const start = (name: string, domain = '') => go(`new?q=${encodeURIComponent(name)}${domain ? `&w=${encodeURIComponent(domain)}` : ''}`)
  const running = data?.deals.filter(d => d.status === 'queued' || d.status === 'running') ?? []
  return (
    <div className="home">
      <div className="home-orb o1" /><div className="home-orb o2" /><div className="home-orb o3" />
      <div className="home-inner">
        <div className="home-eyebrow">{greet()}{me ? `, ${nameOf(me)}` : ''}</div>
        <h1 className="home-title">What are we<br /><span>looking at</span> today?</h1>
        <p className="home-sub">Name a company. Add the data room if you have it, or run it on public information alone.</p>
        {canEdit ? (
          <div className="home-search">
            <CompanySearch mode="company" big value={q} onChange={setQ} placeholder="Company name or website…" autoFocus
              onPickDeal={id => go(`deal-${id}`)} onPickCompany={c => start(c.name, c.domain)} onNewDeal={s => start(s)} />
            <button className="home-go" disabled={!q.trim()} onClick={() => start(q.trim())}>Analyse a new deal <i>→</i></button>
          </div>
        ) : <p className="home-sub">Your role is read-only — open the Pipeline to browse deals.</p>}
        <div className="home-links">
          <button onClick={() => go('pipeline')}>Pipeline<em>{data ? data.deals.length : ''}</em></button>
          <button onClick={() => go('framework')}>Framework</button>
          <button onClick={() => go('usage')}>Usage</button>
          <button onClick={() => go('activity')}>Activity</button>
        </div>
        {running.length > 0 && (
          <div className="home-live">
            <span className="dot" />{running.length === 1 ? `${running[0].name} is being analysed` : `${running.length} deals are being analysed`}
            <button onClick={() => go(running.length === 1 ? `deal-${running[0].id}` : 'pipeline')}>Follow →</button>
          </div>
        )}
      </div>
    </div>
  )
}
