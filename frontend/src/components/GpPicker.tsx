/** GP tier members as real firms — logo chips, and a small voice / type picker that looks the firm up on the web so the
 *  deal lead adds the right manager (by its website) to a tier. */
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useDictation } from '../lib/dictation'
import { Logo } from './Logo'

export interface GpMember { name: string; domain?: string; aliases?: string[]; note?: string; heard?: string }
export type MemberIn = GpMember | string
interface Hit { name: string; domain: string; aliases: string[]; description: string; source: string; listed: string[] }

/** Old plain-string members ('NVentures / NVIDIA', 'DCVC (deep tech)') read as firms without a website. */
export function asMember(m: MemberIn): GpMember {
  if (typeof m !== 'string') return m
  const note = /\((.*?)\)/.exec(m)?.[1]
  const [name, ...aliases] = m.replace(/\(.*?\)/, '').split('/').map(s => s.trim()).filter(Boolean)
  return { name: name || m, domain: '', ...(aliases.length ? { aliases } : {}), ...(note ? { note } : {}) }
}
const keyOf = (m: GpMember) => (m.domain || '').toLowerCase() || `name:${m.name.toLowerCase()}`
export const sameFirm = (a: MemberIn, b: MemberIn) => keyOf(asMember(a)) === keyOf(asMember(b))

/** Logo chips for a tier. A firm without a website shows initials and a small "no website" flag. */
export function MemberChips({ members, ro, onRemove }: { members: MemberIn[]; ro: boolean; onRemove: (i: number) => void }) {
  if (!members.length) return <div className="gp-chips"><span className="note">No managers yet.</span></div>
  return (
    <div className="gp-chips">
      {members.map((raw, i) => {
        const m = asMember(raw)
        const tip = [m.domain || 'No website yet — re-add it with the GP finder so it matches by identity', m.note,
          m.aliases?.length ? `also: ${m.aliases.join(', ')}` : '', m.heard ? `you said “${m.heard}”` : ''].filter(Boolean).join(' · ')
        return (
          <span className={`gp-chip${m.domain ? '' : ' nodom'}`} key={keyOf(m) + i} title={tip}>
            <Logo domain={m.domain} name={m.name} size={18} />
            <span className="gp-chip-n">{m.name}</span>
            {!ro && <button aria-label={`Remove ${m.name}`} onClick={() => onRemove(i)}>×</button>}
          </span>
        )
      })}
    </div>
  )
}

export interface Target { key: string; label: string; cls?: string }

/** Small mic/search button that opens the GP finder: say or type a manager, pick the right firm, drop it into a tier. */
export function GpPicker({ targets, current, onPick }: {
  targets: Target[]
  current: (m: GpMember) => string | null      // which target already holds this firm (by website / name), if any
  onPick: (m: GpMember, target: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<Hit[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [manualDom, setManualDom] = useState('')
  const [done, setDone] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const inp = useRef<HTMLInputElement>(null)
  const voice = useDictation(t => setQ(t), { continuous: false, onInterim: t => setQ(t) })

  useEffect(() => {
    if (!open) return
    const off = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', off); document.addEventListener('keydown', esc)
    setTimeout(() => inp.current?.focus(), 30)
    return () => { document.removeEventListener('mousedown', off); document.removeEventListener('keydown', esc) }
  }, [open])
  useEffect(() => {
    const s = q.trim()
    if (s.length < 2) { setHits(null); return }
    let live = true
    setBusy(true)
    const t = setTimeout(async () => {
      try { const r = await api.get<{ results: Hit[] }>('/frameworks/gp-lookup/', { params: { q: s } }); if (live) setHits(r.data.results) }
      catch { if (live) setHits([]) }
      if (live) setBusy(false)
    }, voice.listening ? 450 : 280)
    return () => { live = false; clearTimeout(t) }
  }, [q, voice.listening])

  const pick = (m: GpMember, t: Target) => { onPick(m, t.key); setDone(`${m.name} → ${t.label}`) }
  const row = (m: GpMember, sub: string, listed: string[]) => {
    const at = current(m)
    return (
      <div className="gpf-row" key={keyOf(m)}>
        <Logo domain={m.domain} name={m.name} size={30} />
        <div className="gpf-who"><b>{m.name}</b><span>{[m.domain || 'no website', sub].filter(Boolean).join(' · ')}</span>
          {listed.length > 0 && <em>On the list: {listed.join(' · ')}</em>}</div>
        <div className="gpf-tiers">
          {targets.map(t => <button key={t.key} className={`gpf-t ${t.cls ?? ''}${at === t.key ? ' on' : ''}`} disabled={at === t.key}
            title={at === t.key ? `Already in ${t.label}` : at ? `Move to ${t.label}` : `Add to ${t.label}`} onClick={() => pick(m, t)}>{t.label}</button>)}
        </div>
      </div>
    )
  }
  return (
    <div className="gpf" ref={box}>
      <button type="button" className={`gpf-btn${open ? ' on' : ''}`} onClick={() => { setOpen(o => !o); setDone(null) }}
        title="Find a GP — say or type the name" aria-label="Find a GP by voice or name">
        <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden><rect x="9" y="3" width="6" height="11" rx="3" fill="none" stroke="currentColor" strokeWidth="1.7" />
          <path d="M6 11a6 6 0 0 0 12 0M12 17v4" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>
        <span>Find GP</span>
      </button>
      {open && (
        <div className="gpf-pop" role="dialog" aria-label="Find a GP">
          <div className="gpf-search">
            <input ref={inp} className="inp" value={q} placeholder={voice.listening ? 'Listening…' : 'Say or type a manager, e.g. Gridiron Capital'}
              onChange={e => { setQ(e.target.value); setDone(null) }} />
            {voice.supported && <button type="button" className={`gpf-mic${voice.listening ? ' on' : ''}`} onClick={() => { if (!voice.listening) setQ(''); voice.toggle() }}
              aria-label={voice.listening ? 'Stop listening' : 'Say the GP name'} title={voice.listening ? 'Stop' : 'Speak'}>
              <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden><rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
                <path d="M6 11a6 6 0 0 0 12 0M12 17v4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg></button>}
          </div>
          {voice.err && <div className="gpf-note err">{voice.err}</div>}
          {done && <div className="gpf-note ok">Added {done} — save the tiers to keep it.</div>}
          <div className="gpf-list">
            {busy && !hits && <div className="gpf-note">Looking up firms…</div>}
            {hits?.map(h => row({ name: h.name, domain: h.domain, ...(h.aliases?.length ? { aliases: h.aliases } : {}) },
              h.listed.length ? '' : (h.description || 'web'), h.listed))}
            {hits && q.trim().length >= 2 && (
              <div className="gpf-manual">
                <div className="note">Not the right firm? Add “{q.trim()}” with its website:</div>
                <div className="gpf-mrow"><input className="inp" value={manualDom} placeholder="firm-website.com" onChange={e => setManualDom(e.target.value)} />
                  {targets.map(t => <button key={t.key} className={`gpf-t ${t.cls ?? ''}`} disabled={!/\.[a-z]{2,}/i.test(manualDom)}
                    onClick={() => pick({ name: q.trim(), domain: manualDom.trim().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0].toLowerCase() }, t)}>{t.label}</button>)}</div>
              </div>
            )}
          </div>
          <div className="gpf-foot note">Matched in deals by the firm's website, not by words in its name.</div>
        </div>
      )}
    </div>
  )
}
