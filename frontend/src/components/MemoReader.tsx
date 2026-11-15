import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorText } from '../lib/api'
import { ago } from '../lib/format'
import type { DealDetail } from '../types'

/* ───────────────────────── types ───────────────────────── */
export type Stance = 'agree' | 'disagree' | 'context' | 'question' | 'change'
export interface MemoComment {
  id: number; stance: Stance; text: string; quote: string; section: string; via: 'typed' | 'voice'
  status: 'open' | 'applied' | 'dismissed'; response: string; memo_id: number | null; applied_in: number | null
  author: string; author_id: string | null; created_at: string; updated_at: string
}
export const STANCES: { id: Stance; label: string; icon: string; hint: string }[] = [
  { id: 'agree', label: 'Agree', icon: '✓', hint: 'Agree — say why, if it should be stronger' },
  { id: 'disagree', label: 'Disagree', icon: '✕', hint: "Disagree — what's wrong and what you know instead" },
  { id: 'context', label: 'Add info', icon: '+', hint: 'Information the memo is missing' },
  { id: 'question', label: 'Question', icon: '?', hint: 'A question the revision should answer' },
  { id: 'change', label: 'Change', icon: '✎', hint: 'A change to wording, structure or a number' },
]

/* ───────────────────────── voice dictation (Web Speech API) ───────────────────────── */
type SR = { start(): void; stop(): void; abort(): void; continuous: boolean; interimResults: boolean; lang: string
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null }

function useDictation(onFinal: (text: string) => void) {
  const Ctor = (window as unknown as Record<string, unknown>).SpeechRecognition ?? (window as unknown as Record<string, unknown>).webkitSpeechRecognition
  const supported = typeof Ctor === 'function'
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const rec = useRef<SR | null>(null)
  const want = useRef(false)
  const final = useRef(onFinal)
  final.current = onFinal

  const stop = useCallback(() => { want.current = false; rec.current?.stop(); setListening(false); setInterim('') }, [])
  const start = useCallback(() => {
    if (!supported) return
    setErr(null)
    const r = new (Ctor as new () => SR)()
    r.continuous = true; r.interimResults = true; r.lang = navigator.language || 'en-US'
    r.onresult = e => {
      let fin = '', mid = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) fin += res[0].transcript; else mid += res[0].transcript
      }
      if (fin.trim()) final.current(fin.trim())
      setInterim(mid)
    }
    r.onerror = e => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') { setErr('Microphone access is blocked — allow it in the browser address bar.'); want.current = false }
      else if (e.error !== 'no-speech' && e.error !== 'aborted') setErr(`Voice input stopped (${e.error}).`)
    }
    r.onend = () => { if (want.current) { try { r.start() } catch { /* restarting too fast */ } } else setListening(false) }
    rec.current = r; want.current = true
    try { r.start(); setListening(true) } catch (e) { setErr(String(e)) }
  }, [Ctor, supported])
  useEffect(() => () => { want.current = false; rec.current?.abort() }, [])
  return { supported, listening, interim, err, start, stop, toggle: () => (want.current ? stop() : start()) }
}

/* ───────────────────────── text ⇄ range helpers (inside the memo iframe) ───────────────────────── */
function findRange(doc: Document, quote: string): Range | null {
  const q = quote.replace(/\s+/g, '')
  if (q.length < 4 || !doc.body) return null
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT)
  const nodes: Text[] = []; const starts: number[] = []; let flat = ''; const map: number[] = []
  let raw = 0
  for (let n = walker.nextNode() as Text | null; n; n = walker.nextNode() as Text | null) {
    if (n.parentElement?.closest('style,script,head')) continue
    nodes.push(n); starts.push(raw)
    const t = n.data
    for (let i = 0; i < t.length; i++) if (!/\s/.test(t[i])) { flat += t[i]; map.push(raw + i) }
    raw += t.length
  }
  let at = flat.indexOf(q)
  let len = q.length
  if (at < 0 && q.length > 80) { at = flat.indexOf(q.slice(0, 80)); len = 80 }
  if (at < 0) return null
  const pos = (r: number) => {
    let lo = 0, hi = starts.length - 1
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (starts[mid] <= r) lo = mid; else hi = mid - 1 }
    return { node: nodes[lo], off: r - starts[lo] }
  }
  const a = pos(map[at]), b = pos(map[at + len - 1])
  const range = doc.createRange()
  range.setStart(a.node, a.off); range.setEnd(b.node, b.off + 1)
  return range
}

function sectionOf(doc: Document, node: Node): string {
  let found = ''
  doc.querySelectorAll('h2').forEach(h => {
    if (h.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING || h.contains(node)) found = (h.textContent || '').trim()
  })
  return found.slice(0, 200)
}

/* ───────────────────────── the reader ───────────────────────── */
interface Props { d: DealDetail; html: string; memoId: number | null; isLatest: boolean; frameRef: React.RefObject<HTMLIFrameElement> }

export default function MemoReader({ d, html, memoId, isLatest, frameRef }: Props) {
  const qc = useQueryClient()
  const canComment = d.can_edit && isLatest
  const [panel, setPanel] = useState(true)
  const [sel, setSel] = useState<{ text: string; section: string; x: number; y: number } | null>(null)
  const [draft, setDraft] = useState<{ stance: Stance; text: string; quote: string; section: string; via: 'typed' | 'voice' }>(
    { stance: 'context', text: '', quote: '', section: '', via: 'typed' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [focus, setFocus] = useState<number | null>(null)
  const [editing, setEditing] = useState<number | null>(null)
  const [revise, setRevise] = useState(false)
  const [showApplied, setShowApplied] = useState(false)
  const ranges = useRef(new Map<number, Range>())
  const box = useRef<HTMLTextAreaElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ['comments', d.id],
    queryFn: async () => (await api.get<{ comments: MemoComment[] }>(`/deals/${d.id}/comments/`)).data.comments,
  })
  const comments = useMemo(() => data ?? [], [data])
  const open = comments.filter(c => c.status === 'open')
  const applied = comments.filter(c => c.status === 'applied')

  const dict = useDictation(t => {
    setDraft(x => ({ ...x, text: (x.text ? x.text.replace(/\s*$/, ' ') : '') + t, via: 'voice' }))
  })

  /* wire the iframe: selection bubble, highlight clicks, highlight paint */
  const paint = useCallback(() => {
    const win = frameRef.current?.contentWindow as (Window & { CSS: typeof CSS; Highlight?: typeof Highlight }) | null
    const doc = frameRef.current?.contentDocument
    if (!win || !doc?.body) return
    ranges.current.clear()
    const openR: Range[] = [], doneR: Range[] = [], focusR: Range[] = []
    for (const c of comments) {
      if (!c.quote || c.status === 'dismissed') continue
      const r = findRange(doc, c.quote)
      if (!r) continue
      ranges.current.set(c.id, r)
      ;(c.status === 'open' ? openR : doneR).push(r)
      if (c.id === focus) focusR.push(r)
    }
    const hl = win.CSS?.highlights
    if (hl && win.Highlight) {
      hl.set('rv-open', new win.Highlight(...openR))
      hl.set('rv-done', new win.Highlight(...doneR))
      hl.set('rv-focus', new win.Highlight(...focusR))
    }
  }, [comments, focus, frameRef])

  /* The memo frame is sandboxed without scripts (memo HTML is model-written), so events inside it can't reach us.
     Instead we read its selection a few times a second: a text selection shows the bubble (following scroll),
     and a click (collapsed selection) on a highlighted passage focuses that note. */
  const lastSel = useRef('')
  const lastCaret = useRef('')
  useEffect(() => {
    const t = window.setInterval(() => {
      const frame = frameRef.current; const doc = frame?.contentDocument
      const s = doc?.getSelection()
      if (!frame || !doc || !s || s.rangeCount === 0) { if (lastSel.current) { lastSel.current = ''; setSel(null) } return }
      const range = s.getRangeAt(0)
      const text = s.toString().replace(/\s+/g, ' ').trim()
      if (!s.isCollapsed && text.length >= 4 && canComment && document.activeElement === frame) {
        const rr = range.getBoundingClientRect(), fr = frame.getBoundingClientRect()
        const visible = rr.bottom > 0 && rr.top < fr.height
        const key = `${text}|${Math.round(rr.top)}|${Math.round(rr.left)}`
        if (key !== lastSel.current) {
          lastSel.current = key
          setSel(visible ? { text: text.slice(0, 1200), section: sectionOf(doc, range.startContainer), x: fr.left + rr.left + rr.width / 2, y: fr.top + Math.max(rr.top, 8) } : null)
        }
        return
      }
      if (lastSel.current) { lastSel.current = ''; setSel(null) }
      if (s.isCollapsed && s.anchorNode) {
        const caret = `${s.anchorOffset}|${s.anchorNode.textContent?.slice(0, 40)}`
        if (caret === lastCaret.current) return
        lastCaret.current = caret
        for (const [id, r] of ranges.current) {
          try {
            if (r.isPointInRange(s.anchorNode, s.anchorOffset)) {
              setFocus(id); setPanel(true)
              listRef.current?.querySelector(`[data-cid="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
              return
            }
          } catch { /* range from an old document */ }
        }
      }
    }, 220)
    return () => window.clearInterval(t)
  }, [canComment, frameRef])

  const onLoad = useCallback(() => {
    const doc = frameRef.current?.contentDocument
    if (!doc?.head) return
    const st = doc.createElement('style')
    st.textContent = `::highlight(rv-open){background:rgba(212,168,67,.32)}::highlight(rv-done){background:rgba(29,122,71,.14)}
      ::highlight(rv-focus){background:rgba(212,168,67,.75)}::selection{background:rgba(39,70,125,.22)}
      html{scroll-behavior:smooth}`
    doc.head.appendChild(st)
    paint()
  }, [frameRef, paint])
  useEffect(() => { paint() }, [paint])

  function jumpTo(c: MemoComment) {
    setFocus(c.id)
    const r = ranges.current.get(c.id); const win = frameRef.current?.contentWindow
    if (r && win) win.scrollTo({ top: r.getBoundingClientRect().top + win.scrollY - 140, behavior: 'smooth' })
  }
  function startFromSelection(stance: Stance) {
    if (!sel) return
    setDraft({ stance, text: '', quote: sel.text, section: sel.section, via: 'typed' })
    setSel(null); setPanel(true); lastSel.current = ''
    frameRef.current?.contentDocument?.getSelection()?.removeAllRanges()
    setTimeout(() => box.current?.focus(), 60)
  }
  async function save() {
    if (!draft.text.trim()) return
    dict.stop(); setBusy(true); setErr(null)
    try {
      if (editing) await api.patch(`/deals/${d.id}/comments/${editing}/`, { text: draft.text, stance: draft.stance })
      else await api.post(`/deals/${d.id}/comments/`, { ...draft, memo_id: memoId })
      setDraft({ stance: 'context', text: '', quote: '', section: '', via: 'typed' }); setEditing(null)
      await qc.invalidateQueries({ queryKey: ['comments', d.id] }); void qc.invalidateQueries({ queryKey: ['deal', d.id] })
    } catch (e) { setErr(errorText(e)) }
    setBusy(false)
  }
  async function remove(c: MemoComment) {
    if (!window.confirm('Delete this comment?')) return
    try { await api.delete(`/deals/${d.id}/comments/${c.id}/`); await qc.invalidateQueries({ queryKey: ['comments', d.id] }); void qc.invalidateQueries({ queryKey: ['deal', d.id] }) }
    catch (e) { setErr(errorText(e)) }
  }

  const bySection = useMemo(() => {
    const g = new Map<string, MemoComment[]>()
    for (const c of (showApplied ? comments.filter(x => x.status !== 'dismissed') : open)) {
      const k = c.section || 'General'
      g.set(k, [...(g.get(k) ?? []), c])
    }
    return [...g.entries()]
  }, [comments, open, showApplied])

  return (
    <div className={`reader${panel ? ' with-panel' : ''}`}>
      <div className="reader-doc">
        <iframe ref={frameRef} className="memo-frame" title="IC memo" srcDoc={html} sandbox="allow-same-origin allow-modals" onLoad={onLoad} />
        {!panel && <button className="rv-fab" onClick={() => setPanel(true)}>✎ Comments{open.length ? <b>{open.length}</b> : null}</button>}
      </div>

      {sel && (
        <div className="rv-bubble" style={{ left: sel.x, top: sel.y }} onMouseDown={e => e.preventDefault()}>
          <button onClick={() => startFromSelection('context')}><i>+</i>Comment on this</button>
        </div>
      )}

      {panel && (
        <aside className="rv-panel">
          <div className="rv-head">
            <div>
              <div className="rv-title">Comments</div>
              <div className="sub">{canComment ? 'Highlight text in the memo to comment on it, or add a general comment below.' : isLatest ? 'Read-only for your role.' : 'Comments go on the latest version.'}</div>
            </div>
            <div className="grow" />
            <button className="rv-x" onClick={() => setPanel(false)} title="Hide panel">→</button>
          </div>
          <div className="rv-tabs">
            <button className={!showApplied ? 'on' : ''} onClick={() => setShowApplied(false)}>Open <b>{open.length}</b></button>
            <button className={showApplied ? 'on' : ''} onClick={() => setShowApplied(true)}>All <b>{open.length + applied.length}</b></button>
          </div>

          <div className="rv-list" ref={listRef}>
            {bySection.length === 0 && (
              <div className="rv-empty">
                <div className="rv-empty-ic">✎</div>
                <b>No comments yet</b>
                <span>Highlight any text in the memo and press “Comment on this”, or type or speak a general comment below. When you're done, revise the memo with just your comments.</span>
              </div>
            )}
            {bySection.map(([sec, list]) => (
              <div key={sec} className="rv-sec">
                <div className="rv-sec-h">{sec === 'General' ? 'General comments' : sec}</div>
                {list.map(c => {
                  return (
                    <div key={c.id} data-cid={c.id} className={`rv-card${c.quote ? ' quoted' : ''}${focus === c.id ? ' focus' : ''}${c.status === 'applied' ? ' applied' : ''}`}
                      onClick={() => jumpTo(c)}>
                      <div className="rv-card-top">
                        <span className="sub">{c.author} · {ago(c.created_at)}{c.via === 'voice' ? ' · 🎙' : ''}</span>
                        <div className="grow" />
                        {c.status === 'open' && canComment && <>
                          <button className="rv-mini" onClick={e => { e.stopPropagation(); setEditing(c.id); setDraft({ stance: c.stance, text: c.text, quote: c.quote, section: c.section, via: c.via }); box.current?.focus() }}>Edit</button>
                          <button className="rv-mini" onClick={e => { e.stopPropagation(); void remove(c) }}>✕</button>
                        </>}
                      </div>
                      {c.quote && <blockquote>“{c.quote.length > 220 ? c.quote.slice(0, 220) + '…' : c.quote}”</blockquote>}
                      <div className="rv-text">{c.text}</div>
                      {c.status === 'applied' && <div className="rv-applied"><b>Applied</b>{c.response ? ` — ${c.response}` : ''}</div>}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>

          {canComment && (
            <div className="rv-compose">
              {draft.quote && (
                <div className="rv-quote"><span>On “{draft.quote.length > 140 ? draft.quote.slice(0, 140) + '…' : draft.quote}”</span>
                  <button onClick={() => setDraft(x => ({ ...x, quote: '', section: '' }))}>✕</button></div>
              )}
              <div className={`rv-input${dict.listening ? ' live' : ''}`}>
                <textarea ref={box} rows={3} value={draft.text + (dict.interim ? (draft.text ? ' ' : '') + dict.interim : '')}
                  placeholder={dict.listening ? 'Listening… speak your comment' : draft.quote ? 'Your comment on the highlighted text (⌘/Ctrl + Enter to add)' : 'A general comment on the memo (⌘/Ctrl + Enter to add)'}
                  onChange={e => setDraft(x => ({ ...x, text: e.target.value }))}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void save() } }} />
                <div className="rv-input-bar">
                  <button className={`rv-mic${dict.listening ? ' on' : ''}`} disabled={!dict.supported} onClick={dict.toggle}
                    title={dict.supported ? (dict.listening ? 'Stop dictation' : 'Dictate (speak your comment)') : 'Voice typing needs Chrome, Edge or Safari'}>
                    <span className="rv-mic-ic" />{dict.listening ? 'Stop' : 'Speak'}
                  </button>
                  {dict.listening && <span className="rv-wave"><i /><i /><i /><i /></span>}
                  <div className="grow" />
                  {editing && <button className="btn btn-sm btn-ghost" onClick={() => { setEditing(null); setDraft({ stance: 'context', text: '', quote: '', section: '', via: 'typed' }) }}>Cancel</button>}
                  <button className="btn btn-sm btn-primary" disabled={!draft.text.trim() || busy} onClick={() => void save()}>{editing ? 'Save' : 'Add comment'}</button>
                </div>
              </div>
              {(err || dict.err) && <div className="err-t" style={{ marginTop: 6 }}>{err || dict.err}</div>}
              <button className="rv-revise" disabled={!open.length || d.status === 'running' || d.status === 'queued'} onClick={() => setRevise(true)}>
                <span>Revise memo with {open.length || 'your'} comment{open.length === 1 ? '' : 's'}</span>
                <em>Only the affected sections · no new research</em>
              </button>
            </div>
          )}
        </aside>
      )}
      {revise && <ReviseDialog d={d} count={open.length} onClose={() => setRevise(false)} />}
    </div>
  )
}

/* ───────────────────────── revise-only run ───────────────────────── */
function ReviseDialog({ d, count, onClose }: { d: DealDetail; count: number; onClose: () => void }) {
  const qc = useQueryClient()
  const last = d.jobs.find(j => j.status === 'done')
  const [model, setModel] = useState(last?.model || d.meta.default_model)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const est = model.includes('opus') ? '$0.40–1.50' : model.includes('haiku') ? '$0.05–0.20' : '$0.20–0.80'
  async function go(override = false) {
    setBusy(true); setErr(null)
    try {
      await api.post(`/deals/${d.id}/revise/`, { model, override_credit: override })
      await qc.invalidateQueries({ queryKey: ['deal', d.id] }); void qc.invalidateQueries({ queryKey: ['deals'] })
      onClose()
    } catch (e) {
      const r = (e as { response?: { data?: { code?: string; detail?: string } } }).response?.data
      if (r?.code === 'credit_paused' && window.confirm(`${r.detail}\n\nRun anyway?`)) { setBusy(false); return go(true) }
      setErr(errorText(e))
    }
    setBusy(false)
  }
  return (
    <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal" style={{ maxWidth: 520 }}>
        <div className="modal-h"><div className="h1" style={{ fontSize: 19 }}>Revise with your comments</div></div>
        <div className="modal-b">
          <p style={{ marginBottom: 12, lineHeight: 1.55 }}>
            Applies your <b>{count} open comment{count === 1 ? '' : 's'}</b> to the latest memo: re-scores the criteria your comments affect, then
            rewrites only the sections they touch. No file reading, web research or risk review is redone. The current memo stays in History,
            and the new version lists every comment and how it was handled.
          </p>
          <div className="rv-est">
            <div><span className="kpi-lbl">Estimated cost</span><b>{est}</b><span className="sub">vs ~$6–20 for a full re-run</span></div>
            <div><span className="kpi-lbl">Time</span><b>2–5 min</b></div>
          </div>
          <label className="lbl" style={{ marginTop: 12, display: 'block' }}>Model</label>
          <select className="sel" value={model} onChange={e => setModel(e.target.value)}>
            {d.meta.models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          {err && <div className="err-box" style={{ marginTop: 10 }}>{err}</div>}
        </div>
        <div className="modal-f">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy} onClick={() => void go()}>{busy ? 'Starting…' : 'Revise memo →'}</button>
        </div>
      </div>
    </div>
  )
}
