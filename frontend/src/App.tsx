import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from './store/auth'
import { useHash, go } from './lib/route'
import { api } from './lib/api'
import Login from './pages/Login'
import Pipeline from './pages/Pipeline'
import DealPage from './pages/DealPage'
import NewDealPage from './pages/NewDealPage'
import FrameworkPage from './pages/FrameworkPage'
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
  useEffect(() => { void boot() }, [boot])
  if (booting) return <div className="empty">Loading…</div>
  if (!access) return <Login />
  return <Shell hash={hash} email={email} logout={logout} />
}

function Shell({ hash, email, logout }: { hash: string; email: string | null; logout: () => void }) {
  const { data } = useDeals()
  const m = hash.match(/^deal-([0-9a-f-]{36})(?:\/(\w+))?/)
  const isNew = hash.startsWith('new')
  const isFw = hash.startsWith('framework')
  const newQ = isNew ? decodeURIComponent(hash.split('q=')[1] ?? '') : ''
  const running = data?.deals.filter(d => d.status === 'queued' || d.status === 'running').length ?? 0
  const scored = data?.deals.filter(d => d.adcg_score != null).length ?? 0
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <header id="app-header">
        <span className="logo" onClick={() => go('')} style={{ cursor: 'pointer' }}>Mindari <em>/</em> Deal Analysis</span>
        <span className="logo-tag">ADCG &nbsp;·&nbsp; Pipeline &amp; IC analysis</span>
        <div className="hdr-space" />
        {data && <span className="hdr-asof">{data.deals.length} deals · {scored} scored{running ? ` · ${running} analysing` : ''}</span>}
        <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 14px' }} />
        {email && <span className="hdr-email">{email}</span>}
        <button className="hdr-btn" onClick={logout}>Sign out</button>
      </header>
      <nav id="app-tabnav">
        <button className={`tab-item${!m && !isNew && !isFw ? ' active' : ''}`} onClick={() => go('')}>Pipeline</button>
        <button className={`tab-item${isFw ? ' active' : ''}`} onClick={() => go('framework')}>Framework</button>
        {m && <button className="tab-item active">{data?.deals.find(d => d.id === m[1])?.name ?? 'Deal'}</button>}
        {data?.can_edit && <button className={`tab-item new-tab${isNew ? ' active' : ''}`} onClick={() => go('new')}>+ New deal</button>}
      </nav>
      {data && !data.meta.storage_persistent && (
        <div className="storage-alert">
          <b>Uploaded files are not being stored permanently.</b> No Railway Volume is attached, so every redeploy deletes the data-room files.
          In Railway → this service → <b>Volumes</b> (or right-click the service → Attach volume), mount a volume at <code>/data</code>, then re-upload missing files.
        </div>
      )}
      <main id="main">
        {m ? <DealPage id={m[1]} tab={m[2] || 'memo'} />
          : isNew ? <NewDealPage initialQ={newQ} />
          : isFw ? <FrameworkPage key={hash} fkey={hash === 'framework/vg' ? 'vg' : 'buyout'} />
          : <Pipeline />}
      </main>
    </div>
  )
}
