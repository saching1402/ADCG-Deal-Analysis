import { useCallback, useEffect, useRef, useState } from 'react'
import { go } from '../lib/route'
import type { DealRow } from '../types'
import { Logo } from './Logo'
import { StatusBadge, TrackBadge } from './bits'

/* Swipeable deal cards: one glossy card per deal, the centred one highlighted. Swipe / drag / trackpad / arrow keys move
   between them; click the centred card to open the deal, click a side card to bring it to the centre. */

const ACCENT: Record<string, [string, string]> = {
  vg: ['#e9efff', '#d9e3ff'], cv: ['#e6f5f0', '#d2ece3'], buyout: ['#fbf1de', '#f4e2bd'], '': ['#eef0f5', '#e3e6ee'],
}
const scoreCol = (s: number | null) => (s == null ? '#9aa3b2' : s >= 6.5 ? '#1f7a4c' : s >= 5 ? '#b7862c' : '#b3141f')

function Ring({ score, band }: { score: number | null; band: string }) {
  const r = 34, c = 2 * Math.PI * r, f = score == null ? 0 : Math.max(0, Math.min(1, score / 10))
  return (
    <div className="dc-ring">
      <svg viewBox="0 0 84 84" width="84" height="84" aria-hidden>
        <circle cx="42" cy="42" r={r} fill="none" stroke="rgba(15,35,71,.08)" strokeWidth="6" />
        <circle cx="42" cy="42" r={r} fill="none" stroke={scoreCol(score)} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={`${c * f} ${c}`} transform="rotate(-90 42 42)" />
      </svg>
      <div className="dc-ring-v"><b style={{ color: scoreCol(score) }}>{score == null ? '—' : score.toFixed(2)}</b><span>{score == null ? 'not scored' : band || 'ADCG'}</span></div>
    </div>
  )
}

export default function DealCards({ rows, stageLabel }: { rows: DealRow[]; stageLabel: Record<string, string> }) {
  const track = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)
  const drag = useRef<{ x: number; left: number; moved: boolean } | null>(null)

  const paint = useCallback(() => {
    const el = track.current
    if (!el) return
    const mid = el.scrollLeft + el.clientWidth / 2
    let best = 0, bestD = Infinity
    Array.from(el.children).forEach((n, i) => {
      const c = n as HTMLElement
      const d = (c.offsetLeft + c.offsetWidth / 2 - mid) / c.offsetWidth
      const a = Math.min(Math.abs(d), 2.2)
      c.style.setProperty('--s', String(1 - a * 0.085))
      c.style.setProperty('--o', String(1 - a * 0.3))
      c.style.setProperty('--ry', `${Math.max(-1, Math.min(1, d)) * -7}deg`)
      if (Math.abs(d) < bestD) { bestD = Math.abs(d); best = i }
    })
    setActive(best)
  }, [])
  useEffect(() => {
    const el = track.current
    if (!el) return
    let raf = 0
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(paint) }
    paint(); el.addEventListener('scroll', on, { passive: true }); window.addEventListener('resize', on)
    return () => { el.removeEventListener('scroll', on); window.removeEventListener('resize', on); cancelAnimationFrame(raf) }
  }, [paint, rows.length])
  useEffect(() => { track.current?.scrollTo({ left: 0 }) }, [rows.length])

  const goTo = useCallback((i: number) => {
    const el = track.current, c = el?.children[Math.max(0, Math.min(rows.length - 1, i))] as HTMLElement | undefined
    if (el && c) el.scrollTo({ left: c.offsetLeft + c.offsetWidth / 2 - el.clientWidth / 2, behavior: 'smooth' })
  }, [rows.length])

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest?.('input,textarea,select')) return
      if (e.key === 'ArrowRight') { e.preventDefault(); goTo(active + 1) }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(active - 1) }
      else if (e.key === 'Enter' && rows[active]) go(`deal-${rows[active].id}`)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [active, goTo, rows])

  /* mouse drag (touch and trackpads scroll natively) */
  const down = (e: React.PointerEvent) => {
    if (e.pointerType !== 'mouse' || !track.current) return
    drag.current = { x: e.clientX, left: track.current.scrollLeft, moved: false }
    track.current.classList.add('dragging')
  }
  const move = (e: React.PointerEvent) => {
    const d = drag.current
    if (!d || !track.current) return
    if (Math.abs(e.clientX - d.x) > 4) d.moved = true
    track.current.scrollLeft = d.left - (e.clientX - d.x)
  }
  const up = () => {
    const el = track.current
    if (!drag.current || !el) return
    el.classList.remove('dragging')
    setTimeout(() => { drag.current = null }, 0)
    goTo(active)
  }
  const click = (i: number, id: string) => {
    if (drag.current?.moved) return
    if (i === active) go(`deal-${id}`); else goTo(i)
  }

  return (
    <div className="dc-wrap">
      <button className="dc-arrow l" aria-label="Previous deal" disabled={active <= 0} onClick={() => goTo(active - 1)}>‹</button>
      <div className="dc-track" ref={track} data-lenis-prevent-touch onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerLeave={up}>
        {rows.map((d, i) => {
          const t = d.track_resolved || d.track
          const [a, b] = ACCENT[t] ?? ACCENT['']
          const running = d.status === 'queued' || d.status === 'running' || d.status === 'error' || d.status === 'blocked'
          return (
            <article key={d.id} className={`dc-card${i === active ? ' on' : ''}`} style={{ ['--a' as string]: a, ['--b' as string]: b }}
              onClick={() => click(i, d.id)} role="button" tabIndex={-1} aria-label={`${d.name}${i === active ? ' — open' : ''}`}>
              <div className="dc-shine" />
              <div className="dc-top">
                <Logo url={d.website} name={d.name} size={56} />
                <div className="dc-badges"><TrackBadge t={t} /><span className="badge badge-gray">{stageLabel[d.stage] ?? d.stage}</span></div>
              </div>
              <div className="dc-name">{d.name}</div>
              <div className="dc-sector">{d.sub_sector || d.sector || '—'}</div>
              <p className="dc-line">{d.one_liner || ' '}</p>
              <div className="dc-foot">
                <Ring score={d.adcg_score} band={d.band} />
                <dl className="dc-facts">
                  {d.sponsor && <><dt>{t === 'vg' ? 'Round' : 'Sponsor'}</dt><dd>{d.sponsor}</dd></>}
                  {d.ev && <><dt>{t === 'vg' ? 'Post-money' : 'EV'}</dt><dd>{d.ev}</dd></>}
                  {d.multiple && <><dt>Multiple</dt><dd>{d.multiple}</dd></>}
                </dl>
              </div>
              {running && <div className="dc-status"><StatusBadge d={d} /></div>}
              <div className="dc-open">Open deal →</div>
            </article>
          )
        })}
      </div>
      <button className="dc-arrow r" aria-label="Next deal" disabled={active >= rows.length - 1} onClick={() => goTo(active + 1)}>›</button>
      <div className="dc-count"><b>{active + 1}</b> / {rows.length}<span>Swipe, drag or use ← → · click the centre card to open</span></div>
    </div>
  )
}
