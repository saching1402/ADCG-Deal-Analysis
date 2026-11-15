import { ActivityFeed } from './ActivityPage'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { marked } from 'marked'
import { api, errorText } from '../lib/api'
import { startAnalysis } from '../lib/analyze'
import { go } from '../lib/route'
import { STAGE_STEPS, ago, bandClass, bytes, riskClass } from '../lib/format'
import type { DealDetail, DealFile, Job } from '../types'
import { TrackBadge } from '../components/bits'
import FilePicker from '../components/FilePicker'
import { Logo } from '../components/Logo'
import { type UploadItem, nameKey, replaceFile, uploadAll } from '../lib/upload'

const TABS = [['memo', 'IC memo'], ['scorecard', 'Scorecard'], ['risk', 'Risk review'], ['research', 'Research dossier'], ['files', 'Files'], ['runs', 'Runs'], ['activity', 'Activity']] as const

export default function DealPage({ id, tab }: { id: string; tab: string }) {
  const qc = useQueryClient()
  const { data: d, error, refetch } = useQuery({
    queryKey: ['deal', id],
    queryFn: async () => (await api.get<DealDetail>(`/deals/${id}/`)).data,
    refetchInterval: q => {
      const s = q.state.data
      return s && (s.status === 'queued' || s.status === 'running' || s.files.some(f => f.status === 'digesting')) ? 4000 : false
    },
    staleTime: 0,
  })
  const [rerun, setRerun] = useState(false)
  const [editing, setEditing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const running = d?.status === 'queued' || d?.status === 'running'
  const prevRunning = useRef(running)
  useEffect(() => {
    if (prevRunning.current && !running) { void qc.invalidateQueries({ queryKey: ['memo', id] }); void qc.invalidateQueries({ queryKey: ['deals'] }) }
    prevRunning.current = running
  }, [running, id, qc])

  if (error) return <div className="page"><div className="err-box">{errorText(error)}</div></div>
  if (!d) return <div className="empty">Loading deal…</div>

  const track = d.track_resolved || d.track
  async function patch(body: Partial<DealDetail>) {
    try { await api.patch(`/deals/${id}/`, body); await refetch(); void qc.invalidateQueries({ queryKey: ['deals'] }) } catch (e) { setMsg(errorText(e)) }
  }
  async function cancel() { await api.post(`/deals/${id}/cancel/`); await refetch() }
  async function remove() {
    if (!window.confirm(`Delete ${d!.name} and all its files? This cannot be undone.`)) return
    await api.delete(`/deals/${id}/`); await qc.invalidateQueries({ queryKey: ['deals'] }); go('')
  }

  return (
    <div className="page">
            <div className="deal-head">
        <Logo url={d.website} name={d.name} size={64} />
        <div style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <TrackBadge t={track} />
            {d.sub_sector && <span className="note">{d.sub_sector}</span>}
          </div>
          <div className="h1">{d.name}</div>
          {d.one_liner && <div className="lead">{d.one_liner}</div>}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 12, flexWrap: 'wrap' }}>
            <select className="sel" value={d.stage} disabled={!d.can_edit} onChange={e => void patch({ stage: e.target.value })}>
              {d.meta.stages.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            {d.can_edit && !running && <button className="btn btn-primary btn-sm" onClick={() => setRerun(true)} disabled={!d.meta.api_key_set}>{d.has_memo || d.legacy ? 'Re-analyse' : 'Analyse'}</button>}
            {d.can_edit && running && <button className="btn btn-sm" onClick={cancel}>Cancel run</button>}
            {d.can_edit && <button className="btn btn-sm" onClick={() => setEditing(true)}>Edit details</button>}
            {d.can_edit && <button className="btn btn-sm btn-ghost btn-danger" onClick={remove}>Delete</button>}
            {d.website && <a className="note" href={/^https?:/.test(d.website) ? d.website : `https://${d.website}`} target="_blank" rel="noreferrer">{d.website}</a>}
          </div>
        </div>
        <div className="big-score">
          <div className="bs"><div className="bs-l">{track === 'vg' ? 'ADCG-VG score' : 'ADCG score'}</div>
            <div className={`bs-v`}><span className={`score ${bandClass(d.adcg_score)}`} style={{ fontSize: 24, padding: '2px 10px' }}>{d.adcg_score?.toFixed(2) ?? '—'}</span></div>
            <div className="note" style={{ marginTop: 4 }}>{d.band || 'not scored'}</div>
            {(running || (d.jobs[0] && d.jobs[0].status !== 'done')) && d.adcg_score != null && <div className="prev-note">previous run{d.last_memo_at ? ` · ${ago(d.last_memo_at)}` : ''}</div>}</div>
          <div className="bs"><div className="bs-l">{track === 'vg' ? 'Venture risk' : 'Risk score'}</div>
            <div className="bs-v"><span className={`score ${riskClass(d.risk_score)}`} style={{ fontSize: 24, padding: '2px 10px' }}>{d.risk_score ?? '—'}</span></div>
            <div className="note" style={{ marginTop: 4 }}>0–100 · higher = riskier</div>
            {(running || (d.jobs[0] && d.jobs[0].status !== 'done')) && d.risk_score != null && <div className="prev-note">previous run{d.last_memo_at ? ` · ${ago(d.last_memo_at)}` : ''}</div>}</div>
        </div>
      </div>

      {msg && <div className="err-box" style={{ marginBottom: 12 }}>{msg}</div>}
      {!running && d.files.length > 0 && (d.jobs[0]?.status === 'blocked' || d.files.some(f => f.status !== 'digested' && !f.archived_at))
        ? <FilesStatus d={d} onRun={() => setRerun(true)} onDone={() => { void refetch(); void qc.invalidateQueries({ queryKey: ['deals'] }) }} />
        : (running || d.jobs[0]?.status === 'error') && d.jobs[0] && <Progress job={d.jobs[0]} />}

      {(d.facts?.length > 0 || d.ev) && (
        <div className="facts2">
          {(d.facts?.length ? d.facts : ([{ k: 'Enterprise value', v: d.ev }, { k: 'Multiple', v: d.multiple }, { k: 'Leverage', v: d.leverage }, { k: 'Sponsor', v: d.sponsor }] as DealDetail['facts']).filter(f => f.v))
            .map(f => (
              <div key={f.k} title={f.note || undefined}>
                <div className="k">{f.k}</div>
                <div className="v">{f.v || 'n/d'}{f.note && <span className="fnote" aria-hidden>ⓘ</span>}</div>
                {f.src && <div className="src">{f.src}</div>}
              </div>
            ))}
        </div>
      )}

      <div className="tabs">
        {TABS.map(([k, l]) => (
          <button key={k} className={`tab${tab === k ? ' on' : ''}`} onClick={() => go(`deal-${id}/${k}`)}>
            {l}{k === 'files' ? ` (${d.files.length})` : ''}
          </button>
        ))}
      </div>

      {tab === 'memo' && <MemoTab d={d} />}
      {tab === 'scorecard' && <ScorecardTab d={d} />}
      {tab === 'research' && <ResearchTab d={d} />}
      {tab === 'risk' && <RiskTab d={d} />}
      {tab === 'files' && <FilesTab d={d} refetch={() => void refetch()} />}
      {tab === 'runs' && <RunsTab d={d} />}
      {tab === 'activity' && <ActivityFeed dealId={d.id} />}

      {editing && <EditDialog d={d} onClose={() => setEditing(false)} onSave={async b => { await patch(b); setEditing(false) }} />}
      {rerun && <RerunDialog d={d} onClose={() => setRerun(false)} onDone={() => { setRerun(false); void refetch(); void qc.invalidateQueries({ queryKey: ['deals'] }) }} />}
    </div>
  )
}

function Progress({ job }: { job: Job }) {
  const idx = STAGE_STEPS.findIndex(s => s.id === job.stage)
  const failed = job.status === 'error'
  return (
    <div className="panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div className="panel-t" style={{ marginBottom: 0 }}>{failed ? (job.error === 'Cancelled' ? 'Run cancelled' : 'Analysis failed') : job.status === 'queued' ? 'Queued' : 'Analysing'}</div>
        {!failed && <span className="dot" />}
        <div className="grow" />
        <span className="note">{job.model} · {job.searches} searches · ${job.cost.toFixed(2)}</span>
      </div>
      <div className="steps">
        {STAGE_STEPS.map((s, i) => (
          <div key={s.id} className={`step${i < idx || job.status === 'done' ? ' done' : i === idx && !failed ? ' cur' : ''}`}>
            <span className="n">{i < idx ? '✓' : i + 1}</span>{s.label}{i < STAGE_STEPS.length - 1 && <span className="ln" />}
          </div>
        ))}
      </div>
      {job.stage_detail && !failed && <div className="note" style={{ marginBottom: 8 }}>{job.stage_detail}</div>}
      {failed && job.error !== 'Cancelled' && <div className="err-box" style={{ marginBottom: 8 }}>{job.error}</div>}
      {job.log.length > 0 && <div className="log">{job.log.map((l, i) => <div key={i}>{l.t.slice(11, 19)} · {l.msg}</div>)}</div>}
    </div>
  )
}

interface MemoVer { id: number; number: number; created_at: string; adcg_score: number | null; risk_score: number | null; band: string; model: string; framework_version: number | null; is_latest: boolean }
interface MemoResp { html: string; name: string; version: MemoVer | null; versions: MemoVer[] }
const when = (iso: string) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function MemoTab({ d }: { d: DealDetail }) {
  const frame = useRef<HTMLIFrameElement>(null)
  const [pick, setPick] = useState<number | null>(null)       // a version chosen from History
  const job = d.jobs[0]
  const inFlight = d.status === 'running' || d.status === 'queued'
  const unfinished = !!job && job.status !== 'done' && !(job.status === 'error' && job.error === 'Cancelled' && !inFlight)
  // while a run is in progress (or the latest run didn't finish), never show the previous memo unless asked
  const showLatest = !unfinished
  const { data: list } = useQuery({
    queryKey: ['memo-list', d.id, d.memo_count], enabled: d.has_memo,
    queryFn: async () => (await api.get<MemoResp>(`/deals/${d.id}/memo/?list=1`)).data,
  })
  const wantId = pick ?? (showLatest ? list?.versions[0]?.id ?? -1 : null)
  const { data, isLoading } = useQuery({
    queryKey: ['memo', d.id, wantId, d.memo_count], enabled: d.has_memo && wantId !== null,
    queryFn: async () => (await api.get<MemoResp>(`/deals/${d.id}/memo/${wantId && wantId > 0 ? `?version=${wantId}` : ''}`)).data,
  })
  const versions = list?.versions ?? []

  const History = () => versions.length > 0 ? (
    <div className="memo-hist">
      <div className="kpi-lbl" style={{ marginBottom: 6 }}>Memo history</div>
      {versions.map(v => (
        <button key={v.id} className={`memo-ver${data?.version?.id === v.id && wantId !== null ? ' on' : ''}`} onClick={() => setPick(v.id)}>
          <b>v{v.number}</b><span>{when(v.created_at)}</span><span className="sub">{ago(v.created_at)}</span>
          {v.adcg_score != null && <span className={`score ${bandClass(v.adcg_score)}`}>{v.adcg_score.toFixed(2)}</span>}
          {v.risk_score != null && <span className={`score ${riskClass(v.risk_score)}`}>{v.risk_score}</span>}
          <span className="sub">{v.model.replace('claude-', '')}</span>
          {v.is_latest && <span className="badge badge-green">latest</span>}
        </button>
      ))}
    </div>
  ) : null

  if (!d.has_memo && !inFlight) {
    return (
      <div className="panel empty">
        <div className="h1">No IC memo yet</div>
        <div>{d.legacy ? 'This deal came from the prior ADCG ledger (scores only). Run the analysis to generate the full memo here.' : 'Press Analyse to run it — with data-room files if you have VDR access, or on public information only.'}</div>
      </div>
    )
  }
  if (wantId === null) {
    const last = versions[0]
    return (
      <div>
        <div className={`panel memo-wait ${inFlight ? '' : 'stopped'}`}>
          <div className="panel-t">{inFlight ? 'A new memo is being generated' : 'The latest run did not finish'}</div>
          <div className="sub" style={{ color: 'var(--text)' }}>
            {inFlight
              ? <>Started {ago(job?.started_at || job?.created_at)} · now: {STAGE_STEPS.find(x => x.id === job?.stage)?.label ?? 'queued'}. It will appear here when it is done (usually 15–25 minutes).</>
              : <>See the status above. Nothing newer than the previous memo exists yet.</>}
            {last && <> The previous memo (v{last.number}, {ago(last.created_at)}) is kept in the history below — open it only if you need it.</>}
          </div>
        </div>
        <History />
      </div>
    )
  }
  if (isLoading || !data) return <div className="empty">Loading memo…</div>
  const v = data.version
  const old = v && !v.is_latest
  function download() {
    const url = URL.createObjectURL(new Blob([data!.html], { type: 'text/html' }))
    const a = document.createElement('a'); a.href = url
    a.download = `${d.name.replace(/[^\w]+/g, '-').toLowerCase()}-ic-memo${v ? `-v${v.number}` : ''}.html`; a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div>
      {(old || unfinished) && (
        <div className="memo-old">
          <b>{old ? `Older memo — v${v!.number}, generated ${when(v!.created_at)} (${ago(v!.created_at)}).` : `Previous memo — generated ${v ? when(v.created_at) : ''}.`}</b>
          {' '}{unfinished ? 'A newer run is in progress or did not finish.' : 'Not the latest version.'}
          {!unfinished && <button className="btn btn-sm" style={{ marginLeft: 10 }} onClick={() => setPick(null)}>Back to latest</button>}
          {unfinished && <button className="btn btn-sm" style={{ marginLeft: 10 }} onClick={() => setPick(null)}>Close</button>}
        </div>
      )}
      <div className="toolbar">
        {v && <span className="memo-tag">v{v.number}{v.is_latest ? ' · latest' : ''}</span>}
        <span className="note">{v ? `Generated ${when(v.created_at)} (${ago(v.created_at)}) · ${v.model.replace('claude-', '')}${v.framework_version ? ` · framework v${v.framework_version}` : ''}` : ''} · skill-derived — reconcile to the live ADCG scorecard app.</span>
        <div className="grow" />
        {versions.length > 1 && (
          <select className="sel" value={v?.id ?? ''} onChange={e => setPick(Number(e.target.value))}>
            {versions.map(x => <option key={x.id} value={x.id}>v{x.number} · {when(x.created_at)}{x.is_latest ? ' (latest)' : ''}</option>)}
          </select>
        )}
        <button className="btn btn-sm" onClick={() => frame.current?.contentWindow?.print()}>Print / Save as PDF</button>
        <button className="btn btn-sm" onClick={download}>Download HTML</button>
      </div>
      <iframe ref={frame} className="memo-frame" title="IC memo" srcDoc={data.html} sandbox="allow-same-origin allow-modals" />
    </div>
  )
}

function ScorecardTab({ d }: { d: DealDetail }) {
  const sc = d.scorecard
  if (!sc?.sections?.length) {
    return <div className="panel">{d.summary?.sections ? null : <div className="note">{d.legacy ? 'Ledger deal: headline scores only — re-analyse for the full 25/30-criteria scorecard.' : 'Not scored yet.'}</div>}</div>
  }
  const col = (s: number | null | undefined) => (s == null ? 'var(--subtle)' : s >= 6.5 ? 'var(--green)' : s >= 5 ? 'var(--gold)' : 'var(--red)')
  return (
    <div>
      {sc.key_risks && sc.key_risks.length > 0 && (
        <div className="panel">
          <div className="panel-t">Key risks driving the score</div>
          <table className="tbl"><tbody>
            {sc.key_risks.map((r, i) => (
              <tr key={i} style={{ cursor: 'default' }}><td style={{ width: 120 }}><span className={`badge ${/HIGH/.test(r.severity) && !/MEDIUM/.test(r.severity) ? 'badge-red' : 'badge-buyout'}`}>{r.severity}</span></td>
                <td><strong>{r.criterion}</strong><div className="co-sub" style={{ maxWidth: 'none' }}>{r.why}</div></td></tr>
            ))}
          </tbody></table>
          <div className="note" style={{ marginTop: 8 }}>Disagree with a risk? Use Re-analyse and add your rationale — the scorer applies it on the next run.</div>
        </div>
      )}
      <div className="panel">
        <div className="panel-t">Sections &amp; criteria</div>
        {sc.sections.map(s => (
          <div className="sc-sec" key={s.name}>
            <div className="sc-sec-h">
              <span className="t">{s.name}</span><span className="note">weight {s.weight}%</span>
              <div className="meter"><div style={{ width: `${(s.score ?? 0) * 10}%`, background: col(s.score) }} /></div>
              <span className="mono" style={{ color: col(s.score), fontWeight: 600 }}>{s.score?.toFixed(2)}</span>
            </div>
            <table className="tbl"><tbody>
              {s.criteria.map((c, i) => (
                <tr key={i} style={{ cursor: 'default' }}>
                  <td style={{ width: '32%' }}>{c.name}</td>
                  <td className="r mono" style={{ width: 60, color: col(c.score), fontWeight: 600 }}>{c.score == null ? 'n/d' : c.score.toFixed(1)}</td>
                  <td className="co-sub" style={{ maxWidth: 'none' }}>{c.rationale}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
        ))}
        {d.summary?.vjr_text && <div className="note">VJR: {d.summary.vjr_text}</div>}
        {sc.calibration && <div className="note" style={{ marginTop: 6 }}>Calibration: {sc.calibration}</div>}
      </div>
      {sc.weights_rationale && sc.weights_rationale.length > 0 && (
        <div className="panel">
          <div className="panel-t">Section weightings &amp; why</div>
          <table className="tbl"><thead><tr><th>Section</th><th className="r">Default</th><th className="r">This deal</th><th>Why</th></tr></thead><tbody>
            {sc.weights_rationale.map((w, i) => <tr key={i} style={{ cursor: 'default' }}><td>{w.section}</td><td className="r mono">{w.default}</td><td className="r mono">{w.deal}</td><td className="co-sub" style={{ maxWidth: 'none' }}>{w.why}</td></tr>)}
          </tbody></table>
        </div>
      )}
    </div>
  )
}

function ResearchTab({ d }: { d: DealDetail }) {
  const html = useMemo(() => (d.research ? marked.parse(d.research, { async: false }) as string : ''), [d.research])
  if (!d.research) return <div className="panel note">The research dossier appears here after the web-research stage.</div>
  return (
    <div>
      <div className="panel"><div className="md" dangerouslySetInnerHTML={{ __html: html }} /></div>
      {d.sources.length > 0 && (
        <div className="panel"><details><summary className="panel-t" style={{ cursor: 'pointer' }}>Sources ({d.sources.length})</summary>
          <ul style={{ paddingLeft: 18, marginTop: 6 }}>{d.sources.map(u => <li key={u} style={{ margin: '2px 0' }}><a href={u} target="_blank" rel="noreferrer">{u}</a></li>)}</ul>
        </details></div>
      )}
    </div>
  )
}

function FilesTab({ d, refetch }: { d: DealDetail; refetch: () => void }) {
  const [items, setItems] = useState<UploadItem[]>([])
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [digest, setDigest] = useState<string>('')
  const patchItem = (key: string, p: Partial<UploadItem>) => setItems(xs => xs.map(x => (x.key === key ? { ...x, ...p } : x)))

  async function upload() {
    setBusy(true)
    // a file with the same name as a missing / unreadable one goes back into that slot instead of becoming a duplicate
    const slots = new Map(d.files.filter(f => f.missing || f.status === 'error' || f.status === 'partial').map(f => [nameKey(f.name), f]))
    const fresh: UploadItem[] = []
    for (const it of items.filter(x => x.state !== 'done')) {
      const slot = slots.get(nameKey(it.file.name))
      if (!slot) { fresh.push(it); continue }
      slots.delete(nameKey(it.file.name))
      patchItem(it.key, { state: 'uploading', progress: 0, error: undefined })
      try {
        await replaceFile(d.id, slot.id, it.file, p => patchItem(it.key, { progress: p }))
        patchItem(it.key, { state: 'done', progress: 1 })
      } catch (e) { patchItem(it.key, { state: 'error', error: errorText(e) }) }
    }
    if (fresh.length) await uploadAll(d.id, fresh, patchItem)
    setBusy(false)
    setItems(xs => xs.filter(x => x.state !== 'done'))
    refetch()
  }
  async function download(f: DealFile) {
    const r = await api.get(`/deals/${d.id}/files/${f.id}/`, { responseType: 'blob', timeout: 0 })
    const url = URL.createObjectURL(r.data as Blob)
    const a = document.createElement('a'); a.href = url; a.download = f.name; a.click(); URL.revokeObjectURL(url)
  }
  async function del(f: DealFile) {
    if (!window.confirm(`Remove ${f.name}?`)) return
    await api.delete(`/deals/${d.id}/files/${f.id}/`); refetch()
  }
  async function show(f: DealFile) {
    if (open === f.id) { setOpen(null); return }
    const r = await api.get<{ digest: string }>(`/deals/${d.id}/files/${f.id}/?digest=1`)
    setDigest(r.data.digest); setOpen(f.id)
  }
  const undigested = d.files.filter(f => f.status !== 'digested').length
  const missing = d.files.filter(f => f.missing)
  const hasCim = d.files.some(f => f.doc_role === 'cim')
  async function setRole(f: DealFile, role: string) {
    await api.patch(`/deals/${d.id}/files/${f.id}/`, { doc_role: role }); refetch()
  }
  const [rep, setRep] = useState<Record<number, string>>({})   // per-file re-upload progress / result
  const [repMsg, setRepMsg] = useState<string | null>(null)
  async function reupload(f: DealFile, file: File) {
    setRep(r => ({ ...r, [f.id]: '0%' }))
    try {
      const out = await replaceFile(d.id, f.id, file, p => setRep(r => ({ ...r, [f.id]: `${Math.round(p * 100)}%` })))
      setRep(r => ({ ...r, [f.id]: out.kept_fact_sheet ? 'Restored · fact sheet kept' : 'Uploaded · will be read' }))
    } catch (e) { setRep(r => ({ ...r, [f.id]: `Failed: ${errorText(e)}` })) }
    refetch()
  }
  async function reuploadMany(list: FileList | null) {
    if (!list?.length) return
    const byExact = new Map(missing.map(f => [f.name.toLowerCase(), f]))
    const byKey = new Map(missing.map(f => [nameKey(f.name), f]))
    const extras: File[] = []
    let matched = 0
    for (const file of Array.from(list)) {
      const hit = byExact.get(file.name.toLowerCase()) ?? byKey.get(nameKey(file.name))
      if (hit) { matched++; byExact.delete(hit.name.toLowerCase()); byKey.delete(nameKey(hit.name)); await reupload(hit, file) }
      else extras.push(file)
    }
    if (extras.length && window.confirm(`${extras.length} file(s) did not match a missing file by name:\n${extras.map(x => x.name).join('\n')}\n\nAdd them to this deal as new files?`)) {
      const items = extras.map(f => ({ key: `${f.name}-${f.size}`, file: f, progress: 0, state: 'waiting' as const }))
      await uploadAll(d.id, items, () => {})
    }
    const left = missing.length - matched
    setRepMsg(`${matched} missing file(s) re-uploaded${left > 0 ? ` · ${left} still missing` : ''}.`)
    refetch()
  }
  async function freeSpace() {
    if (!window.confirm(`Delete the original files of ${d.name}? Fact sheets, research, scores and the memo are kept; re-analysis still works from the fact sheets.`)) return
    await api.post(`/deals/${d.id}/free-space/`); refetch()
  }

  return (
    <div>
      {d.files.length > 0 && !hasCim && (
        <div className="warn-box" style={{ marginBottom: 12 }}><b>No file is marked as the CIM.</b> Every headline fact is taken from the CIM and the other files are reconciled to it —
          set the right file to “CIM / information memorandum” in the Document type column before running the analysis.</div>
      )}
      {missing.length > 0 && (
        <div className="panel blocked">
          <div className="panel-t" style={{ color: 'var(--red)' }}>{missing.length} file{missing.length === 1 ? ' is' : 's are'} missing from storage</div>
          <div className="sub" style={{ color: 'var(--text)', marginBottom: 10 }}>The stored copies were lost (most likely a redeploy before a storage volume was attached). Re-upload the same files:
            they go back into their original place, and when the content is identical the existing fact sheet is kept, so nothing is re-read or re-charged.</div>
          {d.can_edit && <label className="btn btn-primary btn-sm" style={{ cursor: 'pointer' }}>
            Re-upload missing files…
            <input type="file" multiple hidden accept={d.meta.accepted.map(e => `.${e}`).join(',')} onChange={e => { void reuploadMany(e.target.files); e.target.value = '' }} />
          </label>}
          <span className="sub" style={{ marginLeft: 10 }}>Select several at once — they are matched to the missing files by name.</span>
          {repMsg && <div className="ok-box" style={{ marginTop: 10 }}>{repMsg}</div>}
        </div>
      )}
      {d.can_edit && (
        <div className="panel">
          <div className="panel-t">Add materials</div>
          <FilePicker meta={d.meta} items={items} setItems={setItems} disabled={busy} existing={d.files.length} />
          {items.some(x => x.state !== 'done') && (
            <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
              <button className="btn btn-primary btn-sm" onClick={upload} disabled={busy}>{busy ? 'Uploading…' : items.some(x => x.state === 'error') ? `Retry ${items.filter(x => x.state !== 'done').length} file(s)` : `Upload ${items.filter(x => x.state !== 'done').length} file(s)`}</button>
              <button className="btn btn-sm" onClick={() => setItems([])} disabled={busy}>Clear</button>
            </div>
          )}
          {d.files.some(f => !f.archived_at && f.has_digest) && (
            <div className="free-row">
              <span className="sub">Done with this deal? Delete the original files to free storage — fact sheets, research, scores and the memo are kept.</span>
              <button className="btn btn-sm" disabled={busy} onClick={() => void freeSpace()}>Free up {bytes(d.files.filter(f => !f.archived_at && f.has_digest).reduce((a, f) => a + f.size, 0))}</button>
            </div>
          )}
          {undigested > 0 && !items.length && <div className="note" style={{ marginTop: 10 }}>{undigested} file(s) not yet read — press Re-analyse to fold them into the memo (already-read files are reused).</div>}
        </div>
      )}
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>File</th><th>Document type</th><th className="r">Size</th><th>Readability check</th><th>Status</th><th>Uploaded</th><th /></tr></thead>
          <tbody>
            {d.files.length === 0 && <tr><td colSpan={7} className="note" style={{ textAlign: 'center', padding: 30 }}>No files yet.</td></tr>}
            {d.files.map(f => (
              <Fragment key={f.id}>
                <tr style={{ cursor: 'default' }}>
                  <td><div className="co-name" style={{ fontWeight: 500 }}>{f.name}</div>
                    {f.missing ? <div className="co-sub" style={{ color: 'var(--red)' }}>Stored copy missing — re-upload this file.</div>
                      : f.error && <div className="co-sub" style={{ color: 'var(--red)', maxWidth: 520 }}>{f.error.slice(0, 400)}</div>}
                    {rep[f.id] && <div className="co-sub" style={{ color: rep[f.id].startsWith('Failed') ? 'var(--red)' : 'var(--green)' }}>{rep[f.id]}</div>}</td>
                  <td>
                    <select className={`sel role-sel${f.doc_role === 'cim' ? ' is-cim' : ''}`} value={f.doc_role} disabled={!d.can_edit}
                      onChange={e => void setRole(f, e.target.value)} title={f.role_set_by_user ? 'Set by you' : 'Detected from the file name and content — change if wrong'}>
                      {d.meta.doc_roles.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                    </select>
                  </td>
                  <td className="r note">{bytes(f.size)}</td>
                  <td style={{ maxWidth: 380 }}><Readable f={f} /></td>
                  <td>{f.archived_at ? <span className="badge badge-gray" title="Original deleted to free space; its fact sheet is kept">Original freed · fact sheet kept</span> : f.missing ? <span className="badge badge-red" title="The stored copy was lost — upload it again">File missing — re-upload</span> : f.status === 'digested' ? <span className="badge badge-green">✓ Read &amp; verified</span>
                    : f.status === 'digesting' ? <span className="badge badge-run"><span className="dot" />Reading</span>
                      : f.status === 'partial' ? <span className="badge badge-red">Partly unreadable</span>
                        : f.status === 'error' ? <span className="badge badge-red">Unreadable</span>
                          : <span className="badge badge-gray">Not read yet</span>}</td>
                  <td className="note">{ago(f.uploaded_at)}</td>
                  <td className="r" style={{ whiteSpace: 'nowrap' }}>
                    {f.has_digest && <button className="btn btn-sm btn-ghost" onClick={() => void show(f)}>{open === f.id ? 'Hide' : 'Fact sheet'}</button>}
                    {d.can_edit && (f.missing || f.status === 'error' || f.status === 'partial') && (
                      <label className="btn btn-sm" style={{ cursor: 'pointer' }} title="Upload this file again into the same slot">
                        Re-upload
                        <input type="file" hidden accept={d.meta.accepted.map(e => `.${e}`).join(',')} onChange={e => { const x = e.target.files?.[0]; if (x) void reupload(f, x); e.target.value = '' }} />
                      </label>
                    )}
                    {!f.archived_at && !f.missing && <button className="btn btn-sm btn-ghost" onClick={() => void download(f)}>Download</button>}
                    {d.can_edit && <button className="btn btn-sm btn-ghost btn-danger" onClick={() => void del(f)}>Remove</button>}
                  </td>
                </tr>
                {open === f.id && <tr><td colSpan={7} style={{ background: 'var(--surface2)' }}><div className="md" dangerouslySetInnerHTML={{ __html: marked.parse(digest, { async: false }) as string }} /></td></tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RunsTab({ d }: { d: DealDetail }) {
  if (!d.jobs.length) return <div className="panel note">No analysis runs yet.</div>
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead><tr><th>Started</th><th>Model</th><th>Status</th><th className="r">Searches</th><th className="r">Tokens in / out</th><th className="r">Cost</th><th>Notes</th></tr></thead>
        <tbody>
          {d.jobs.map(j => (
            <tr key={j.id} style={{ cursor: 'default' }}>
              <td className="note">{ago(j.created_at)}</td><td className="mono">{j.model}</td>
              <td>{j.status === 'done' ? <span className="badge badge-green">Done</span> : j.status === 'error' ? <span className="badge badge-red" title={j.error}>{j.error === 'Cancelled' ? 'Cancelled' : 'Error'}</span> : <span className="badge badge-run">{j.status}</span>}</td>
              <td className="r mono">{j.searches}</td>
              <td className="r mono">{(j.input_tokens / 1000).toFixed(0)}k / {(j.output_tokens / 1000).toFixed(0)}k</td>
              <td className="r mono">${j.cost.toFixed(2)}</td>
              <td className="co-sub">{j.instructions || (j.error && j.error !== 'Cancelled' ? j.error.slice(0, 160) : '')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="note" style={{ padding: '8px 12px' }}>Total spend on this deal: ${d.total_cost.toFixed(2)}</div>
    </div>
  )
}

function RerunDialog({ d, onClose, onDone }: { d: DealDetail; onClose: () => void; onDone: () => void }) {
  const [model, setModel] = useState(d.jobs[0]?.model || d.meta.default_model)
  const [instructions, setInstructions] = useState('')
  const [redigest, setRedigest] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function go2() {
    setBusy(true); setErr(null)
    try { await startAnalysis(d.id, { model, instructions, redigest }); onDone() } catch (e) { setErr(errorText(e)); setBusy(false) }
  }
  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal" style={{ maxWidth: 600 }}>
        <div className="modal-h"><div className="grow"><div className="eyebrow">{d.has_memo ? 'Re-analyse' : 'Analyse'}</div><div className="h1" style={{ fontSize: 19 }}>{d.name}</div></div>
          <button className="x" onClick={onClose}>✕</button></div>
        <div className="modal-b">
          <div className="field">
            <label className="lbl" htmlFor="rr-model">Model</label>
            <select id="rr-model" className="sel" style={{ width: '100%' }} value={model} onChange={e => setModel(e.target.value)}>
              {d.meta.models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label className="lbl" htmlFor="rr-ins">Your rationale / steer for this run (optional)</label>
            <textarea id="rr-ins" className="inp" rows={5} value={instructions} onChange={e => setInstructions(e.target.value)}
              placeholder="e.g. Management confirmed organic growth was 7% not 2% (see QoE p.14) — rescore Business Quality. Treat leverage as 4.5x after the equity cure. Focus the gates on customer concentration." />
          </div>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5, cursor: 'pointer' }}>
            <input type="checkbox" checked={redigest} onChange={e => setRedigest(e.target.checked)} />
            Re-read every file from scratch (otherwise only new files are read)
          </label>
          {err && <div className="err-box" style={{ marginTop: 10 }}>{err}</div>}
        </div>
        <div className="modal-f"><div className="grow" /><button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={go2} disabled={busy}>{busy ? 'Starting…' : 'Run analysis →'}</button></div>
      </div>
    </div>
  )
}

function EditDialog({ d, onClose, onSave }: { d: DealDetail; onClose: () => void; onSave: (b: Partial<DealDetail>) => Promise<void> }) {
  const [f, setF] = useState({ name: d.name, website: d.website, sponsor: d.sponsor, sector: d.sector, ev: d.ev, multiple: d.multiple, leverage: d.leverage, one_liner: d.one_liner, notes: d.notes })
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF(s => ({ ...s, [k]: e.target.value }))
  const fld = (k: keyof typeof f, l: string, ph = '') => (
    <div className="field"><label className="lbl">{l}</label><input className="inp" value={f[k]} onChange={set(k)} placeholder={ph} /></div>
  )
  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal" style={{ maxWidth: 640 }}>
        <div className="modal-h"><div className="grow"><div className="eyebrow">Edit details</div><div className="h1" style={{ fontSize: 19 }}>{d.name}</div></div>
          <button className="x" onClick={onClose}>✕</button></div>
        <div className="modal-b">
          <div className="grid2">{fld('name', 'Name')}{fld('website', 'Website', 'company.com')}</div>
          <div className="grid2">{fld('sponsor', 'Sponsor / round')}{fld('sector', 'Sector')}</div>
          <div className="grid2">{fld('ev', 'EV / post-money')}{fld('multiple', 'Multiple')}</div>
          <div className="grid2">{fld('leverage', 'Leverage')}{fld('one_liner', 'One-liner')}</div>
          <div className="field"><label className="lbl">Terms &amp; notes (fed to the next analysis)</label><textarea className="inp" rows={3} value={f.notes} onChange={set('notes')} /></div>
        </div>
        <div className="modal-f"><div className="grow" /><button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !f.name.trim()} onClick={async () => { setBusy(true); await onSave(f); setBusy(false) }}>Save</button></div>
      </div>
    </div>
  )
}

function Readable({ f }: { f: DealFile }) {
  const r = f.readability as Partial<import('../types').Readability>
  const c = f.coverage as Partial<import('../types').Coverage>
  return (
    <div className="sub" style={{ color: 'var(--text)' }}>
      {r?.summary ? <div>{r.status === 'warn' ? '⚠ ' : ''}{r.summary}</div> : <div className="note">checked when read</div>}
      {r?.notes?.map((n, i) => <div key={i} className="note">{n}</div>)}
      {c?.parts ? <div className={c.failed?.length ? '' : 'note'} style={c.failed?.length ? { color: 'var(--red)' } : undefined}>
        Read {c.ok}/{c.parts} part{c.parts > 1 ? 's' : ''}{c.failed?.length ? ` — not read: ${c.failed.map(x => x.label).join(', ')}` : ' — all verified'}
      </div> : null}
    </div>
  )
}

/** A file only blocks the analysis if it still has to be read and can't be: unreadable, partly read, or its stored copy is gone. */
const needsFix = (f: DealFile) => f.status === 'error' || f.status === 'partial' || (f.missing && f.status !== 'digested')

function FilesStatus({ d, onRun, onDone }: { d: DealDetail; onRun: () => void; onDone: () => void }) {
  const [err, setErr] = useState<string | null>(null)
  const [busyF, setBusyF] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const fix = d.files.filter(needsFix)
  const ready = d.files.filter(f => !needsFix(f))
  const toRead = ready.filter(f => f.status !== 'digested' && !f.archived_at).length
  const job = d.jobs[0]
  async function again(f: DealFile, file: File) {
    setBusyF(f.id); setErr(null)
    try { await replaceFile(d.id, f.id, file) } catch (e) { setErr(errorText(e)) }
    setBusyF(null); onDone()
  }
  async function remove(f: DealFile) {
    if (!window.confirm(`Remove ${f.name} from this deal?`)) return
    await api.delete(`/deals/${d.id}/files/${f.id}/`); onDone()
  }
  async function runWithout() {
    if (!window.confirm(`Run without ${fix.length === 1 ? fix[0].name : `these ${fix.length} files`}? The memo will state what was not read.`)) return
    setBusy(true); setErr(null)
    try { await startAnalysis(d.id, { model: job?.model, instructions: job?.instructions, allow_partial: true }); onDone() }
    catch (e) { setErr(errorText(e)) }
    setBusy(false)
  }
  const ok = fix.length === 0
  const missing = fix.filter(f => f.missing).length
  const canRetry = !ok && missing === 0          // read failures (not lost files) are re-read on the next run
  return (
    <div className={`panel fstat ${ok ? 'ok' : 'warn'}`}>
      <div className="fstat-h">
        <div>
          <div className="fstat-t">{ready.length} of {d.files.length} files ready{ok ? '' : ` · ${fix.length} need${fix.length === 1 ? 's' : ''} attention`}</div>
          <div className="sub">{ok
            ? (toRead ? `${toRead} new file(s) will be read and verified first; ${ready.length - toRead} already read are reused.` : 'All files are read and verified — re-running reuses them, so only research, scoring and the memo are redone.')
            : canRetry ? `Re-read ${fix.length === 1 ? 'this file' : `these ${fix.length} files`} and run, or re-upload / remove them. Nothing is researched or scored until every file is read.`
            : 'Re-upload or remove the missing files, or run without them. Nothing is researched or scored until every file is read.'}</div>
        </div>
        <div className="grow" />
        {d.can_edit && <button className="btn btn-primary" onClick={onRun} disabled={!(ok || canRetry) || !d.meta.api_key_set}>{canRetry ? `Re-read ${fix.length} file${fix.length === 1 ? '' : 's'} & run` : d.has_memo ? 'Re-run analysis' : 'Run analysis'}</button>}
      </div>
      <div className="fstat-list">
        {d.files.map(f => {
          const bad = needsFix(f)
          return (
            <div key={f.id} className={`fstat-row${bad ? ' bad' : ''}`}>
              <span className="fstat-ic">{bad ? '!' : '✓'}</span>
              <span className="fstat-name" title={f.name}>{f.name}</span>
              <span className={`badge ${f.doc_role === 'cim' ? 'badge-buyout' : 'badge-gray'}`}>{f.doc_role_label}</span>
              <span className="sub fstat-why">{bad ? (f.missing ? 'Stored copy missing — re-upload' : (f.error || 'Unreadable').slice(0, 140))
                : f.status === 'digested' ? (f.pages ? `${f.pages} pages read` : 'Read') : 'Will be read on the next run'}</span>
              {bad && d.can_edit && <>
                <label className="btn btn-sm" style={{ cursor: 'pointer' }}>{busyF === f.id ? 'Uploading…' : 'Re-upload'}
                  <input type="file" hidden accept={d.meta.accepted.map(e => `.${e}`).join(',')} onChange={e => { const x = e.target.files?.[0]; if (x) void again(f, x); e.target.value = '' }} />
                </label>
                <button className="btn btn-sm btn-ghost btn-danger" onClick={() => void remove(f)}>Remove</button>
              </>}
            </div>
          )
        })}
      </div>
      {err && <div className="err-box" style={{ marginTop: 8 }}>{err}</div>}
      {!ok && d.can_edit && ready.some(f => f.status === 'digested') && (
        <button className="btn btn-sm btn-ghost" style={{ marginTop: 8 }} disabled={busy} onClick={() => void runWithout()}>Run without the files that need attention</button>
      )}
    </div>
  )
}

function RiskTab({ d }: { d: DealDetail }) {
  const r = d.risk_items || {}
  const [full, setFull] = useState(false)
  const html = useMemo(() => (d.risk_review ? marked.parse(d.risk_review, { async: false }) as string : ''), [d.risk_review])
  if (!d.risk_review) return <div className="panel note">The independent risk review appears here after the analysis runs. It looks beyond the seller and sponsor materials — sector track record, macro, competition, regulation — for risks the CIM understates or leaves out.</div>
  const sev = (x?: string) => (x === 'HIGH' ? 'badge-red' : x === 'MEDIUM' ? 'badge-buyout' : 'badge-gray')
  const cim = (x?: string) => (x === 'n/a' ? <span className="badge badge-gray">No data room</span> : x === 'no' ? <span className="badge badge-red">Not in CIM</span> : x === 'understated' ? <span className="badge badge-buyout">Understated</span> : <span className="badge badge-gray">In CIM</span>)
  const out = (x?: string) => (/bankrupt|restruct|loss|write/i.test(x || '') ? 'badge-red' : /good/i.test(x || '') ? 'badge-green' : 'badge-gray')
  return (
    <div>
      {r.theme_verdict && <div className="panel verdict-panel"><div className="kpi-lbl">Sub-sector verdict</div><div style={{ fontSize: 14, color: 'var(--navy)', fontWeight: 600, marginTop: 4 }}>{r.theme_verdict}</div></div>}
      {r.risks && r.risks.length > 0 && (
        <div className="panel">
          <div className="panel-t">Material risks — ranked</div>
          <div className="sub" style={{ marginBottom: 8 }}>{r.risks.every(x => x.in_cim === 'n/a') ? 'Researched independently on the web — no data room for this deal.'
            : `${r.risks.filter(x => x.in_cim === 'no' || x.in_cim === 'understated').length} of ${r.risks.length} are not disclosed or are understated in the seller / sponsor materials.`}</div>
          <table className="tbl"><thead><tr><th>Risk</th><th>Severity</th><th>Likelihood</th><th>Materials</th><th>Mitigant · diligence question</th></tr></thead><tbody>
            {r.risks.map((x, i) => (
              <tr key={i} style={{ cursor: 'default' }}>
                <td style={{ maxWidth: 420 }}><div className="nm" style={{ fontSize: 12.5 }}>{x.risk}</div>
                  <div className="co-sub" style={{ maxWidth: 'none' }}>{x.why}{x.source && /^https?:/.test(x.source) && <> · <a href={x.source} target="_blank" rel="noreferrer">source</a></>}{x.source && !/^https?:/.test(x.source) && <> · {x.source}</>}</div>
                  <div className="sub">{[x.category, x.order && `${x.order}-order`].filter(Boolean).join(' · ')}</div></td>
                <td><span className={`badge ${sev(x.severity)}`}>{x.severity}</span></td>
                <td><span className={`badge ${sev(x.likelihood)}`}>{x.likelihood}</span></td>
                <td>{cim(x.in_cim)}</td>
                <td className="co-sub" style={{ maxWidth: 320 }}>{x.mitigant}{x.diligence && <div style={{ marginTop: 3, color: 'var(--navy)' }}>Ask: {x.diligence}</div>}</td>
              </tr>
            ))}
          </tbody></table>
        </div>
      )}
      {r.track_record && r.track_record.length > 0 && (
        <div className="panel">
          <div className="panel-t">How sponsors have fared in this sub-sector</div>
          <table className="tbl"><thead><tr><th>Deal</th><th>Sponsor</th><th>Years</th><th>Outcome</th><th>Lesson</th></tr></thead><tbody>
            {r.track_record.map((x, i) => (
              <tr key={i} style={{ cursor: 'default' }}>
                <td className="nm" style={{ fontSize: 12.5 }}>{x.source ? <a href={x.source} target="_blank" rel="noreferrer">{x.deal}</a> : x.deal}</td>
                <td className="cell-sm">{x.sponsor}</td><td className="sub">{x.years}</td>
                <td><span className={`badge ${out(x.outcome)}`}>{x.outcome}</span></td>
                <td className="co-sub" style={{ maxWidth: 380 }}>{x.lesson}</td>
              </tr>
            ))}
          </tbody></table>
        </div>
      )}
      {r.reconciliation && r.reconciliation.length > 0 && (
        <div className="panel">
          <div className="panel-t">CIM reconciliation</div>
          <table className="tbl"><thead><tr><th>Metric</th><th>CIM</th><th>Other documents</th><th>Gap</th><th>Comment</th></tr></thead><tbody>
            {r.reconciliation.map((x, i) => <tr key={i} style={{ cursor: 'default' }}><td className="nm" style={{ fontSize: 12.5 }}>{x.metric}</td><td className="mono">{x.cim}</td><td className="cell-sm">{x.other}</td><td className="mono">{x.gap}</td><td className="co-sub" style={{ maxWidth: 360 }}>{x.comment}</td></tr>)}
          </tbody></table>
        </div>
      )}
      <div className="panel">
        <button className="btn btn-sm" onClick={() => setFull(f => !f)}>{full ? 'Hide' : 'Show'} the full written review</button>
        {full && <div className="md" style={{ marginTop: 12 }} dangerouslySetInnerHTML={{ __html: html }} />}
      </div>
    </div>
  )
}
