import { useRef, useState } from 'react'
import { useDictation } from '../lib/dictation'
import CompanySearch from '../components/CompanySearch'
import { go } from '../lib/route'
import { useDeals } from '../App'
import { useMe, nameOf } from './AccountPage'

const greet = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }

/** The landing page: a quiet, glossy canvas with one thing to do — analyse a new deal. Everything else is in the tabs. */
export default function HomePage() {
  const [q, setQ] = useState('')
  const [openSig, setOpenSig] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const clean = (t: string) => t.replace(/[.?!,]+$/, '').trim()
  const voice = useDictation(t => { setQ(clean(t)); setOpenSig(n => n + 1); input.current?.focus() },
                             { continuous: false, onInterim: t => setQ(clean(t)) })
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
            <CompanySearch mode="company" big value={q} onChange={setQ} autoFocus inputRef={input} openSignal={openSig}
              placeholder={voice.listening ? 'Listening… say the company name' : 'Company name or website…'}
              trailing={voice.supported ? <MicButton on={voice.listening} onClick={() => { if (!voice.listening) setQ(''); voice.toggle() }} /> : null}
              onPickDeal={id => go(`deal-${id}`)} onPickCompany={c => start(c.name, c.domain)} onNewDeal={s => start(s)} />
            <button className="home-go" disabled={!q.trim()} onClick={() => start(q.trim())}>Analyse a new deal <i>→</i></button>
          </div>
        ) : <p className="home-sub">Your role is read-only — open Deals to browse them.</p>}
        {canEdit && voice.err && <div className="home-voice-err">{voice.err}</div>}
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

/** A glowing silver microphone: press, say the company, pick it from the list. */
function MicButton({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`mic${on ? ' on' : ''}`} onClick={onClick} onMouseDown={e => e.preventDefault()}
      title={on ? 'Stop listening' : 'Say the company name'} aria-label={on ? 'Stop listening' : 'Search by voice'} aria-pressed={on}>
      <span className="mic-ring r1" /><span className="mic-ring r2" />
      <svg viewBox="0 0 24 24" width="19" height="19" aria-hidden>
        <defs>
          <linearGradient id="micg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffffff" /><stop offset=".45" stopColor="#c9ced6" /><stop offset="1" stopColor="#7d8591" />
          </linearGradient>
        </defs>
        <rect x="8.5" y="2.5" width="7" height="12" rx="3.5" fill="url(#micg)" stroke="#5b6370" strokeWidth=".9" />
        <path d="M5.5 11.2a6.5 6.5 0 0 0 13 0M12 17.7v3.3M8.6 21h6.8" fill="none" stroke="#5b6370" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      {on && <span className="mic-bars" aria-hidden><i /><i /><i /><i /></span>}
    </button>
  )
}
