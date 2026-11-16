import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { ago } from '../lib/format'
import { go } from '../lib/route'

export interface Me {
  id: string; email: string; username: string; full_name: string; role: string; is_active: boolean
  is_admin: boolean; last_login: string | null; date_joined: string; starter_password: boolean
}
export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: async () => (await api.get<Me>('/users/me/')).data, staleTime: 60_000 })
}
export const nameOf = (u: Pick<Me, 'full_name' | 'username'>) => u.full_name || u.username
const ROLE: Record<string, string> = { admin: 'Admin — everything, incl. managing users', analyst: 'Analyst — add & edit deals, run analyses', viewer: 'Viewer — read only' }

export default function AccountPage() {
  const { data: me } = useMe()
  if (!me) return <div className="empty">Loading…</div>
  return (
    <div className="page-narrow">
      <div className="page-h"><div className="h1">Account</div>
        <button className="btn btn-sm" onClick={() => go(`activity?user=${me.id}`)}>My activity</button></div>
      {me.starter_password && (
        <div className="memo-old"><b>You are still on the shared starter password.</b> Set your own below — until you do, anyone who knows it can sign in as you, and the activity log can't tell you apart.</div>
      )}
      {me.is_admin && <Requests admin />}
      <Profile me={me} />
      <Password me={me} />
      {!me.is_admin && <Requests admin={false} />}
      {me.is_admin && <Team me={me} />}
    </div>
  )
}

function Profile({ me }: { me: Me }) {
  const qc = useQueryClient()
  const [f, setF] = useState({ full_name: me.full_name, username: me.username })
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null)
  const dirty = f.full_name !== me.full_name || f.username !== me.username
  async function save() {
    setMsg(null)
    try { await api.patch('/users/me/', f); setMsg({ ok: true, t: 'Saved.' }); void qc.invalidateQueries({ queryKey: ['me'] }) }
    catch (e) { setMsg({ ok: false, t: errorText(e) }) }
  }
  return (
    <div className="panel">
      <div className="panel-t">Profile</div>
      <div className="form-grid">
        <label>Name<input className="inp" value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} /></label>
        <label>Username — what you sign in with<input className="inp" value={f.username} onChange={e => setF({ ...f, username: e.target.value })} /></label>
        <label>Role<div className="ro">{ROLE[me.role] ?? me.role}</div></label>
      </div>
      <div className="row-end">
        {msg && <span className={msg.ok ? 'ok-t' : 'err-t'}>{msg.t}</span>}
        <span className="sub">Last sign-in {ago(me.last_login)} · member since {new Date(me.date_joined).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
        <button className="btn btn-primary btn-sm" disabled={!dirty} onClick={() => void save()}>Save profile</button>
      </div>
    </div>
  )
}

function Password({ me }: { me: Me }) {
  const qc = useQueryClient()
  const [cur, setCur] = useState(''); const [nw, setNw] = useState(''); const [nw2, setNw2] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null)
  const mismatch = !!nw2 && nw !== nw2
  async function save() {
    setMsg(null)
    try {
      await api.post('/users/me/password/', { current_password: cur, new_password: nw })
      setCur(''); setNw(''); setNw2(''); setMsg({ ok: true, t: 'Password changed. Use it next time you sign in.' })
      void qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) { setMsg({ ok: false, t: errorText(e) }) }
  }
  return (
    <div className="panel">
      <div className="panel-t">Change password</div>
      <div className="form-grid">
        <label>Current password<input className="inp" type="password" autoComplete="current-password" value={cur} onChange={e => setCur(e.target.value)} /></label>
        <span />
        <label>New password<input className="inp" type="password" autoComplete="new-password" value={nw} onChange={e => setNw(e.target.value)} /></label>
        <label>Repeat new password<input className={`inp${mismatch ? ' bad' : ''}`} type="password" autoComplete="new-password" value={nw2} onChange={e => setNw2(e.target.value)} /></label>
      </div>
      <div className="row-end">
        <span className="sub">At least 12 characters; not a common password and not like your name.</span>
        {msg && <span className={msg.ok ? 'ok-t' : 'err-t'}>{msg.t}</span>}
        {mismatch && <span className="err-t">The new passwords don't match.</span>}
        <button className="btn btn-primary btn-sm" disabled={!cur || !nw || nw !== nw2} onClick={() => void save()}>{me.starter_password ? 'Set my own password' : 'Change password'}</button>
      </div>
    </div>
  )
}

function Team({ me }: { me: Me }) {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['users'], queryFn: async () => (await api.get<{ users: Me[] }>('/users/')).data })
  const [err, setErr] = useState<string | null>(null)
  const [add, setAdd] = useState<{ username: string; full_name: string; role: string; password: string } | null>(null)
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['users'] }) }
  async function patch(u: Me, body: Record<string, unknown>) {
    setErr(null)
    try { await api.patch(`/users/${u.id}/`, body); refresh() } catch (e) { setErr(errorText(e)) }
  }
  async function reset(u: Me) {
    const pw = window.prompt(`New starter password for ${nameOf(u)} (they should change it after signing in):`)
    if (!pw) return
    setErr(null)
    try { await api.post(`/users/${u.id}/reset-password/`, { password: pw }); refresh(); window.alert(`Password for ${nameOf(u)} reset.`) }
    catch (e) { setErr(errorText(e)) }
  }
  async function create() {
    if (!add) return
    setErr(null)
    try { await api.post('/users/', add); setAdd(null); refresh() } catch (e) { setErr(errorText(e)) }
  }
  return (
    <div className="panel">
      <div className="panel-t" style={{ display: 'flex', alignItems: 'center' }}>Team <span className="grow" />
        {!add && <button className="btn btn-sm" onClick={() => setAdd({ username: '', full_name: '', role: 'analyst', password: '' })}>+ Add user</button>}</div>
      <table className="tbl team-tbl">
        <thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Password</th><th>Last sign-in</th><th /></tr></thead>
        <tbody>
          {data?.users.map(u => (
            <tr key={u.id} className={u.is_active ? '' : 'off'}>
              <td><b>{nameOf(u)}</b>{u.id === me.id && <span className="sub"> (you)</span>}{!u.is_active && <span className="badge badge-gray" style={{ marginLeft: 6 }}>deactivated</span>}</td>
              <td className="mono">{u.username}</td>
              <td><select className="sel" value={u.role} disabled={u.id === me.id} onChange={e => void patch(u, { role: e.target.value })}>
                <option value="admin">Admin</option><option value="analyst">Analyst</option><option value="viewer">Viewer</option></select></td>
              <td>{u.starter_password ? <span className="badge badge-amber">starter</span> : <span className="badge badge-green">own</span>}</td>
              <td className="sub">{u.last_login ? ago(u.last_login) : 'never'}</td>
              <td style={{ whiteSpace: 'nowrap', textAlign: 'right' }}>
                <button className="btn btn-sm btn-ghost" onClick={() => go(`activity?user=${u.id}`)}>Activity</button>
                <button className="btn btn-sm btn-ghost" onClick={() => void reset(u)}>Reset password</button>
                {u.id !== me.id && <button className="btn btn-sm btn-ghost" onClick={() => void patch(u, { is_active: !u.is_active })}>{u.is_active ? 'Deactivate' : 'Reactivate'}</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {add && (
        <div className="form-grid" style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <label>Name<input className="inp" value={add.full_name} onChange={e => setAdd({ ...add, full_name: e.target.value })} /></label>
          <label>Username<input className="inp" value={add.username} onChange={e => setAdd({ ...add, username: e.target.value })} /></label>
          <label>Role<select className="sel" value={add.role} onChange={e => setAdd({ ...add, role: e.target.value })}>
            <option value="analyst">Analyst</option><option value="admin">Admin</option><option value="viewer">Viewer</option></select></label>
          <label>Starter password<input className="inp" type="text" value={add.password} onChange={e => setAdd({ ...add, password: e.target.value })} /></label>
          <div className="row-end" style={{ alignSelf: 'end' }}>
            <button className="btn btn-sm btn-ghost" onClick={() => setAdd(null)}>Cancel</button>
            <button className="btn btn-primary btn-sm" disabled={!add.username || !add.password} onClick={() => void create()}>Create user</button>
          </div>
        </div>
      )}
      {err && <div className="err-box" style={{ marginTop: 8 }}>{err}</div>}
      <div className="sub" style={{ marginTop: 8 }}>Deactivated users can't sign in; their history stays in the activity log.</div>
    </div>
  )
}

interface Proposal {
  id: number; key: string; framework: string; user: string; username: string; note: string; changes: string[]
  status: 'pending' | 'approved' | 'rejected' | 'withdrawn'; response: string; created_at: string
  decided_by: string | null; decided_at: string | null; base_version: number; main_version: number
  applied_version: number | null; stale: boolean
}
const ST: Record<string, string> = { pending: 'badge-gold', approved: 'badge-green', rejected: 'badge-red', withdrawn: 'badge-gray' }

/** Framework change requests: admins approve or reject; everyone else sees what happened to theirs. */
function Requests({ admin }: { admin: boolean }) {
  const qc = useQueryClient()
  const { data, refetch } = useQuery({ queryKey: ['fw-proposals'], queryFn: async () => (await api.get<{ proposals: Proposal[] }>('/frameworks/proposals/')).data })
  const [reply, setReply] = useState<Record<number, string>>({})
  const [err, setErr] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const rows = data?.proposals ?? []
  const pending = rows.filter(p => p.status === 'pending')
  const done = rows.filter(p => p.status !== 'pending')
  if (!admin && rows.length === 0) return null
  async function decide(p: Proposal, action: 'approve' | 'reject' | 'withdraw') {
    if (action === 'approve' && !window.confirm(`Adopt ${p.user}'s ${p.framework} as the new main framework (version ${p.main_version + 1})?` +
      (p.stale ? `\n\nNote: the main framework changed (v${p.base_version} → v${p.main_version}) after this was proposed — approving replaces those changes with ${p.user}'s version.` : ''))) return
    setErr(null)
    try {
      await api.post(`/frameworks/proposals/${p.id}/`, { action, response: reply[p.id] || '' })
      await refetch(); void qc.invalidateQueries({ queryKey: ['framework'] })
    } catch (e) { setErr(errorText(e)) }
  }
  const Card = ({ p }: { p: Proposal }) => (
    <div className={`req ${p.status}`}>
      <div className="req-h">
        <b>{admin ? p.user : p.framework}</b>
        <span className="note">{admin ? `wants to change ${p.framework}` : 'change request'} · {ago(p.created_at)}</span>
        <div className="grow" />
        <span className={`badge ${ST[p.status]}`}>{p.status}</span>
      </div>
      {p.note && <div className="req-note">“{p.note}”</div>}
      <ul className="req-changes">{p.changes.slice(0, 14).map((c, i) => <li key={i}>{c}</li>)}{p.changes.length > 14 && <li className="note">…and {p.changes.length - 14} more</li>}</ul>
      {p.stale && <div className="note" style={{ color: 'var(--amber)' }}>The main framework has changed since this was sent (v{p.base_version} → v{p.main_version}).</div>}
      {p.status === 'pending' && admin && (
        <div className="req-act">
          <input className="inp" placeholder="Reply to them (optional)" value={reply[p.id] ?? ''} onChange={e => setReply(r => ({ ...r, [p.id]: e.target.value }))} />
          <button className="btn btn-sm" onClick={() => void decide(p, 'reject')}>Reject</button>
          <button className="btn btn-sm btn-gold" onClick={() => void decide(p, 'approve')}>Approve → main framework</button>
        </div>
      )}
      {p.status === 'pending' && !admin && <div className="req-act"><span className="note">Waiting for the admin.</span><div className="grow" /><button className="btn btn-sm btn-ghost" onClick={() => void decide(p, 'withdraw')}>Withdraw</button></div>}
      {p.status !== 'pending' && (p.decided_by || p.response) && (
        <div className="note" style={{ marginTop: 6 }}>{p.status === 'approved' ? `Approved by ${p.decided_by} — now main version ${p.applied_version}` : p.decided_by ? `${p.status === 'rejected' ? 'Rejected' : 'Closed'} by ${p.decided_by}` : ''}{p.decided_at ? ` · ${ago(p.decided_at)}` : ''}{p.response ? ` — “${p.response}”` : ''}</div>
      )}
    </div>
  )
  return (
    <div className="panel">
      <div className="panel-t" style={{ display: 'flex', alignItems: 'center' }}>{admin ? 'Framework change requests' : 'My framework change requests'}
        {pending.length > 0 && <span className="badge badge-gold" style={{ marginLeft: 8 }}>{pending.length} pending</span>}</div>
      {admin && <div className="sub" style={{ marginBottom: 10 }}>Team members edit their own copy of each framework (only their analyses use it). When they want a change in the main framework, it lands here for you to approve or reject.</div>}
      {err && <div className="err-box" style={{ marginBottom: 10 }}>{err}</div>}
      {admin && pending.length === 0 && <div className="note">No requests waiting.</div>}
      {pending.map(p => <Card key={p.id} p={p} />)}
      {done.length > 0 && <button className="btn btn-sm btn-ghost" style={{ marginTop: 8 }} onClick={() => setShowAll(v => !v)}>{showAll ? 'Hide' : 'Show'} past requests ({done.length})</button>}
      {showAll && done.map(p => <Card key={p.id} p={p} />)}
    </div>
  )
}
