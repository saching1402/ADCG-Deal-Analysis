import { Fragment, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { ago } from '../lib/format'
import { go } from '../lib/route'
import type { Me } from './AccountPage'
import { nameOf } from './AccountPage'

interface Ev {
  id: number; at: string; actor: string; actor_id: string | null; action: string; summary: string
  deal_id: string | null; deal_name: string; target: string; changes: Record<string, unknown>; ok: boolean; ip: string | null
}
const GROUPS: [string, string][] = [['', 'Everything'], ['deals', 'Deals'], ['files', 'Files'], ['analysis', 'Analyses'],
  ['framework', 'Framework'], ['usage', 'Credit & storage'], ['users', 'Users & accounts'], ['auth', 'Sign-ins']]
const ICON: Record<string, string> = { deal: '◆', file: '▤', analysis: '▶', framework: '⚙', auth: '→', user: '☺', account: '☺', credit: '$', usage: '$', storage: '▣' }
const time = (iso: string) => new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
const day = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })

export default function ActivityPage({ query }: { query: string }) {
  const params = new URLSearchParams(query)
  return (
    <div className="page-narrow" style={{ maxWidth: 1100 }}>
      <div className="page-h"><div className="h1">Activity log</div>
        <span className="sub">Every change anyone makes — deals, files, analyses, framework edits, credit, users and sign-ins. Entries can't be edited or deleted.</span></div>
      <ActivityFeed initialUser={params.get('user') ?? ''} />
    </div>
  )
}

export function ActivityFeed({ dealId, initialUser = '' }: { dealId?: string; initialUser?: string }) {
  const [user, setUser] = useState(initialUser)
  const [group, setGroup] = useState('')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<number | null>(null)
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: async () => (await api.get<{ users: Me[] }>('/users/')).data })
  const qs = (before?: string) => {
    const p = new URLSearchParams()
    if (dealId) p.set('deal', dealId)
    if (user) p.set('user', user)
    if (group) p.set('group', group)
    if (q.trim()) p.set('q', q.trim())
    if (before) p.set('before', before)
    return p.toString()
  }
  const feed = useInfiniteQuery({
    queryKey: ['audit', dealId, user, group, q.trim()],
    initialPageParam: '',
    queryFn: async ({ pageParam }) => (await api.get<{ events: Ev[]; more: boolean }>(`/audit/?${qs(pageParam || undefined)}`)).data,
    getNextPageParam: last => (last.more && last.events.length ? last.events[last.events.length - 1].at : undefined),
    refetchInterval: 20_000,
  })
  const events = feed.data?.pages.flatMap(p => p.events) ?? []
  async function exportCsv() {
    try {
      const r = await api.get(`/audit/?${qs()}&export=csv`, { responseType: 'blob' })
      const url = URL.createObjectURL(r.data as Blob); const a = document.createElement('a')
      a.href = url; a.download = `activity-log-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(url)
    } catch (e) { window.alert(errorText(e)) }
  }
  let lastDay = ''
  return (
    <div>
      <div className="toolbar">
        <select className="sel" value={user} onChange={e => setUser(e.target.value)}>
          <option value="">All users</option>
          {users?.users.map(u => <option key={u.id} value={u.id}>{nameOf(u)}</option>)}
        </select>
        <select className="sel" value={group} onChange={e => setGroup(e.target.value)}>
          {GROUPS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <input className="inp" style={{ width: 220 }} placeholder="Search…" value={q} onChange={e => setQ(e.target.value)} />
        <div className="grow" />
        <button className="btn btn-sm" onClick={() => void exportCsv()}>Export CSV</button>
      </div>
      {feed.isLoading ? <div className="empty">Loading…</div> : !events.length ? <div className="panel empty">Nothing logged yet{user || group || q ? ' for these filters' : ''}.</div> : (
        <div className="act-list">
          {events.map(e => {
            const d = day(e.at); const head = d !== lastDay; lastDay = d
            const hasDetail = e.changes && Object.keys(e.changes).length > 0
            return (
              <Fragment key={e.id}>
                {head && <div className="act-day">{d}</div>}
                <div className={`act-row${e.ok ? '' : ' bad'}`} onClick={() => hasDetail && setOpen(open === e.id ? null : e.id)} style={{ cursor: hasDetail ? 'pointer' : 'default' }}>
                  <span className="act-time" title={new Date(e.at).toLocaleString()}>{time(e.at)}<span className="sub">{ago(e.at)}</span></span>
                  <span className="act-ic">{ICON[e.action.split('.')[0]] ?? '•'}</span>
                  <span className="act-who">{e.actor}</span>
                  <span className="act-what">{e.summary}
                    {!dealId && e.deal_name && <> · {e.deal_id ? <a onClick={ev => { ev.stopPropagation(); go(`deal-${e.deal_id}`) }}>{e.deal_name}</a> : e.deal_name}</>}
                    {hasDetail && <span className="sub"> {open === e.id ? '▾' : '▸'} details</span>}
                  </span>
                  <span className="act-ip sub">{e.ip ?? ''}</span>
                </div>
                {open === e.id && hasDetail && (
                  <div className="act-detail">
                    {Object.entries(e.changes).map(([k, v]) => (
                      <div key={k}><b>{k}</b>: {Array.isArray(v) && v.length === 2
                        ? <><s>{String(v[0] ?? '—')}</s> → {String(v[1] ?? '—')}</>
                        : <span style={{ whiteSpace: 'pre-wrap' }}>{typeof v === 'string' ? v : JSON.stringify(v)}</span>}</div>
                    ))}
                  </div>
                )}
              </Fragment>
            )
          })}
          {feed.hasNextPage && <button className="btn btn-sm" style={{ margin: '10px auto', display: 'block' }} disabled={feed.isFetchingNextPage} onClick={() => void feed.fetchNextPage()}>{feed.isFetchingNextPage ? 'Loading…' : 'Load older'}</button>}
        </div>
      )}
    </div>
  )
}
