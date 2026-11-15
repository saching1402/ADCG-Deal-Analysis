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
export const nameOf = (u: Pick<Me, 'full_name' | 'username' | 'email'>) => u.full_name || u.username || u.email
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
      <Profile me={me} />
      <Password me={me} />
      {me.is_admin && <Team me={me} />}
    </div>
  )
}

function Profile({ me }: { me: Me }) {
  const qc = useQueryClient()
  const [f, setF] = useState({ full_name: me.full_name, username: me.username, email: me.email })
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null)
  const dirty = f.full_name !== me.full_name || f.username !== me.username || f.email !== me.email
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
        <label>Username — sign in with this or your email<input className="inp" value={f.username} onChange={e => setF({ ...f, username: e.target.value })} /></label>
        <label>Email<input className="inp" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></label>
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
        <span className="sub">At least 12 characters; not a common password and not like your name or email.</span>
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
  const [add, setAdd] = useState<{ username: string; full_name: string; email: string; role: string; password: string } | null>(null)
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
        {!add && <button className="btn btn-sm" onClick={() => setAdd({ username: '', full_name: '', email: '', role: 'analyst', password: '' })}>+ Add user</button>}</div>
      <table className="tbl team-tbl">
        <thead><tr><th>Name</th><th>Sign in as</th><th>Role</th><th>Password</th><th>Last sign-in</th><th /></tr></thead>
        <tbody>
          {data?.users.map(u => (
            <tr key={u.id} className={u.is_active ? '' : 'off'}>
              <td><b>{nameOf(u)}</b>{u.id === me.id && <span className="sub"> (you)</span>}{!u.is_active && <span className="badge badge-gray" style={{ marginLeft: 6 }}>deactivated</span>}</td>
              <td className="mono">{u.username || '—'}<div className="sub">{u.email}</div></td>
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
          <label>Email <span className="sub">(optional)</span><input className="inp" value={add.email} onChange={e => setAdd({ ...add, email: e.target.value })} /></label>
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
