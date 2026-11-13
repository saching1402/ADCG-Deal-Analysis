import { useEffect } from 'react'
import { useAuthStore } from './store/auth'
import { useHash, go } from './lib/route'
import Login from './pages/Login'
import Pipeline from './pages/Pipeline'
import DealPage from './pages/DealPage'

export default function App() {
  const { access, booting, boot, logout, email } = useAuthStore()
  const hash = useHash()
  useEffect(() => { void boot() }, [boot])
  if (booting) return <div className="empty">Loading…</div>
  if (!access) return <Login />
  const m = hash.match(/^deal-([0-9a-f-]{36})(?:\/(\w+))?/)
  return (
    <>
      <header id="hdr">
        <div className="logo" onClick={() => go('')}>Mindari <em>/</em> Deal Analysis</div>
        <div className="logo-tag">ADCG · Pipeline &amp; IC analysis</div>
        <div className="hdr-space" />
        {email && <span className="hdr-user">{email}</span>}
        <button className="hdr-btn" onClick={logout}>Sign out</button>
      </header>
      <main id="main">
        {m ? <DealPage id={m[1]} tab={m[2] || 'memo'} /> : <Pipeline />}
      </main>
    </>
  )
}
