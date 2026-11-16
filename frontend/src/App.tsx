import { useEffect, useRef, useState } from 'react'
import Lenis from 'lenis'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from './store/auth'
import { useHash, go } from './lib/route'
import { api } from './lib/api'
import Login from './pages/Login'
import Pipeline from './pages/Pipeline'
import DealPage from './pages/DealPage'
import NewDealPage from './pages/NewDealPage'
import HomePage from './pages/HomePage'
import FrameworkPage from './pages/FrameworkPage'
import UsagePage, { useUsage, fmtBytes, money } from './pages/UsagePage'
import AccountPage, { useMe, nameOf } from './pages/AccountPage'
import ActivityPage from './pages/ActivityPage'
import type { DealRow, Meta } from './types'

export interface ListResp { deals: DealRow[]; meta: Meta; can_edit: boolean }

export function useDeals() {
  return useQuery({
    queryKey: ['deals'],
    queryFn: async () => (await api.get<ListResp>('/deals/')).data,
    refetchInterval: d => (d.state.data?.deals.some(x => x.status === 'queued' || x.status === 'running') ? 5000 : false),
    staleTime: 10_000,
  })
}

export default function App() {
  const { access, booting, boot, logout, email } = useAuthStore()
  const hash = useHash()
  const qc = useQueryClient()
  useEffect(() => { void boot() }, [boot])
  useEffect(() => { if (!access) qc.clear() }, [access, qc])   // never show the previous user's data after sign-out
  if (booting) return <div className="empty">Loading…</div>
  if (!access) return <Login />
  return <Shell hash={hash} email={email} logout={logout} />
}

function Shell({ hash, email, logout }: { hash: string; email: string | null; logout: () => void }) {
  const { data } = useDeals()
  const m = hash.match(/^deal-([0-9a-f-]{36})(?:\/(\w+))?/)
  const isNew = hash.startsWith('new')
  const isPipeline = hash.startsWith('pipeline')
  const isHome = hash === ''
  const isFw = hash.startsWith('framework')
  const isUsage = hash === 'usage'
  const isAccount = hash === 'account'
  const isActivity = hash.startsWith('activity')
  const { data: me } = useMe()
  const { data: usage } = useUsage()
  const newP = new URLSearchParams(isNew ? hash.split('?')[1] ?? '' : '')
  const newQ = newP.get('q') ?? ''
  const newW = newP.get('w') ?? ''
  const [scrolled, setScrolled] = useState(false)
  const mainRef = useRef<HTMLElement>(null)
  useReveal(mainRef, hash)
  const route = m ? `deal-${m[1]}` : hash.split('?')[0]
  useSmoothScroll(mainRef, route)
  const running = data?.deals.filter(d => d.status === 'queued' || d.status === 'running').length ?? 0
  const scored = data?.deals.filter(d => d.adcg_score != null).length ?? 0
  return (
    <div className="app-shell">
      <div className={`topbar${scrolled ? ' scrolled' : ''}`}>
      <header id="app-header">
        <span className="logo" onClick={() => go('')} style={{ cursor: 'pointer' }}>Mindari <em>/</em> Deal Analysis</span>
        <span className="logo-tag">ADCG &nbsp;·&nbsp; Pipeline &amp; IC analysis</span>
        <div className="hdr-space" />
        {data && <span className="hdr-asof">{data.deals.length} deals · {scored} scored{running ? ` · ${running} analysing` : ''}</span>}
        {usage && <>
          <button className={`hdr-meter lv-${usage.storage.persistent ? usage.storage.level : 'critical'}`} onClick={() => go('usage')}
            title={`File storage: ${fmtBytes(usage.storage.used)} of ${fmtBytes(usage.storage.capacity)}`}>
            <span>Storage</span><i><b style={{ width: `${Math.min(100, (usage.storage.frac ?? 0) * 100)}%` }} /></i>
            <em>{usage.storage.where === 'bucket' ? 'bucket' : !usage.storage.persistent ? 'not saved!' : `${Math.round((usage.storage.frac ?? 0) * 100)}%`}</em>
          </button>
          <button className={`hdr-meter lv-${usage.model.level}`} onClick={() => go('usage')} title="Estimated Claude credit left (from the balance you entered)">
            <span>Claude credit</span><i><b style={{ width: `${Math.min(100, (usage.model.frac ?? 0) * 100)}%` }} /></i>
            <em>{usage.model.remaining == null ? 'set up' : money(usage.model.remaining)}</em>
          </button>
        </>}
        <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 14px' }} />
        {(me || email) && <button className={`hdr-user${isAccount ? ' on' : ''}`} onClick={() => go('account')} title="Your account">
          <span className="hdr-av">{(me ? nameOf(me) : email ?? '?').slice(0, 1).toUpperCase()}</span>{me ? nameOf(me) : email}</button>}
        <button className="hdr-btn" onClick={logout}>Sign out</button>
      </header>
      <nav id="app-tabnav">
        <button className={`tab-item${isPipeline ? ' active' : ''}`} onClick={() => go('pipeline')}>Pipeline</button>
        <button className={`tab-item${isFw ? ' active' : ''}`} onClick={() => go('framework')}>Framework</button>
        <button className={`tab-item${isUsage ? ' active' : ''}`} onClick={() => go('usage')}>Usage</button>
        <button className={`tab-item${isActivity ? ' active' : ''}`} onClick={() => go('activity')}>Activity</button>
        {isAccount && <button className="tab-item active">Account</button>}
        {m && <button className="tab-item active">{data?.deals.find(d => d.id === m[1])?.name ?? 'Deal'}</button>}
        {data?.can_edit && <button className={`tab-item new-tab${isNew ? ' active' : ''}`} onClick={() => go('new')}>+ New deal</button>}
      </nav>
      </div>
      <main id="main" ref={mainRef} onScroll={e => setScrolled((e.target as HTMLElement).scrollTop > 8)}>
        <div className="route" key={route}>
      {me?.starter_password && !isAccount && (
          <div className="storage-alert" style={{ cursor: 'pointer', background: 'var(--amber-bg)', color: 'var(--amber)', borderColor: '#ecdcae' }} onClick={() => go('account')}>
            <b>You're signed in with the shared starter password.</b> Set your own in Account so the activity log is truly yours →
          </div>
        )}
        {data && !data.meta.storage_persistent && (
          <div className="storage-alert">
            <b>Uploaded files are not being stored permanently.</b> No Railway Volume is attached, so every redeploy deletes the data-room files.
            In Railway → this service → <b>Volumes</b> (or right-click the service → Attach volume), mount a volume at <code>/data</code>, then re-upload missing files.
          </div>
        )}
        {usage && usage.storage.persistent && usage.storage.level === 'critical' && (
          <div className="storage-alert" style={{ cursor: 'pointer' }} onClick={() => go('usage')}>
            <b>File storage is {Math.round((usage.storage.frac ?? 0) * 100)}% full</b> — uploads will start failing soon. Open Usage to free space or upgrade.
          </div>
        )}

        {m ? <DealPage id={m[1]} tab={m[2] || 'memo'} />
          : isNew ? <NewDealPage initialQ={newQ} initialWebsite={newW} />
          : isUsage ? <UsagePage />
          : isAccount ? <AccountPage />
          : isActivity ? <ActivityPage key={hash} query={hash.split('?')[1] ?? ''} />
          : isFw ? <FrameworkPage key={hash} fkey={hash === 'framework/vg' ? 'vg' : 'buyout'} />
          : isPipeline ? <Pipeline />
          : <HomePage />}
        </div>
      </main>
    </div>
  )
}


/** Fade-and-rise cards into view as they scroll in (once), with a short stagger between siblings. */
function useReveal(root: React.RefObject<HTMLElement>, key: string) {
  useEffect(() => {
    const el = root.current
    if (!el || typeof IntersectionObserver === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const SEL = '.panel,.kpi,.fw-card,.nd-sec,.nd-card,.dcard,.fstat,.act-list,.facts2>div'
    const io = new IntersectionObserver(entries => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target) }
    }, { root: el, rootMargin: '0px 0px -6% 0px', threshold: 0.04 })
    const tag = () => {
      el.querySelectorAll<HTMLElement>(SEL).forEach(n => {
        if (n.dataset.rv) return
        n.dataset.rv = '1'
        const r = n.getBoundingClientRect()
        if (r.top < window.innerHeight * 0.9) return            // already on screen: no flash
        const sib = n.parentElement ? Array.from(n.parentElement.children).indexOf(n) : 0
        n.style.setProperty('--d', `${Math.min(sib, 6) * 60}ms`)
        n.classList.add('rv-reveal'); io.observe(n)
      })
    }
    tag()
    const mo = new MutationObserver(tag)
    mo.observe(el, { childList: true, subtree: true })
    return () => { mo.disconnect(); io.disconnect() }
  }, [root, key])
}


/** Inertia ("buttery") wheel scrolling on the main scroller, like lsvp.com. Native scroll stays for touch, keyboard
 *  and for inner scrollers (comment list, logs, dropdowns, dialogs, the memo iframe). */
function useSmoothScroll(root: React.RefObject<HTMLElement>, key: string) {
  useEffect(() => {
    const wrapper = root.current
    const content = wrapper?.firstElementChild as HTMLElement | null
    if (!wrapper || !content || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const lenis = new Lenis({
      // matched to lsvp.com (Locomotive Scroll): one 100px wheel tick travels ~72px and settles in ~0.85s
      // (≈52% after 8 frames, ≈79% after 17 → lerp ≈ 0.088 per frame)
      wrapper, content, lerp: 0.088, wheelMultiplier: 0.72, touchMultiplier: 1.2, smoothWheel: true,
      prevent: (n: HTMLElement) => !!n.closest?.('.rv-list,.log,.sg-pop,.overlay,.fw-pre,textarea,select,[data-lenis-prevent]'),
    })
    let raf = 0
    const loop = (t: number) => { lenis.raf(t); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => { cancelAnimationFrame(raf); lenis.destroy() }
  }, [root, key])
}
