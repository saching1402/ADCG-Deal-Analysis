import { Fragment, useRef, useState } from 'react'
import type { Meta } from '../types'
import { bytes } from '../lib/format'
import { type UploadItem, toItems } from '../lib/upload'

export default function FilePicker({ meta, items, setItems, disabled, existing = 0 }: {
  meta: Meta; items: UploadItem[]; setItems: (f: (x: UploadItem[]) => UploadItem[]) => void; disabled?: boolean; existing?: number
}) {
  const ref = useRef<HTMLInputElement>(null)
  const anyRef = useRef<HTMLInputElement>(null)   // no type filter: for files the browser greys out
  const [over, setOver] = useState(false)
  const [warn, setWarn] = useState<string | null>(null)

  function add(list: FileList | null) {
    if (!list) return
    const max = meta.max_upload_mb * 1024 * 1024
    const ok: File[] = [], bad: string[] = []
    for (const f of Array.from(list)) {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
      if (!meta.accepted.includes(ext)) bad.push(`${f.name} (.${ext || '?'} is not a supported type — save it as PDF or .xlsx)`)
      else if (f.size > max) bad.push(`${f.name} (> ${meta.max_upload_mb} MB)`)
      else ok.push(f)
    }
    setItems(xs => {
      const keys = new Set(xs.map(x => x.key))
      const next = [...xs, ...toItems(ok).filter(x => !keys.has(x.key))]
      const room = meta.max_files - existing
      if (next.length > room) bad.push(`only ${room} more file(s) allowed per deal`)
      return next.slice(0, Math.max(0, room))
    })
    setWarn(bad.length ? `Skipped: ${bad.join(', ')}` : null)
  }

  const total = items.reduce((a, x) => a + x.file.size, 0)
  return (
    <div>
      <div className={`drop${over ? ' on' : ''}`} onClick={() => !disabled && ref.current?.click()}
        onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); if (!disabled) add(e.dataTransfer.files) }}>
        <div className="drop-t">Drop the data room here, or click to choose files</div>
        <div className="note" style={{ marginTop: 4 }}>Each file is checked on upload — password-protected, damaged or empty files are rejected with the reason. CIM, teaser, model, QoE, lender deck, management accounts, term sheet… · PDF, Word, Excel (.xlsx .xlsm .xlsb .xls, templates), PowerPoint, Numbers / Keynote, CSV, text, images · up to {meta.max_upload_mb} MB each, {meta.max_files} per deal</div>
        <input ref={ref} type="file" multiple hidden accept={meta.accepted.map(e => `.${e}`).join(',')}
          onChange={e => { add(e.target.files); e.target.value = '' }} />
        <input ref={anyRef} type="file" multiple hidden onChange={e => { add(e.target.files); e.target.value = '' }} />
      </div>
      {!disabled && <div className="note" style={{ marginTop: 6 }}>Can't see a file in the window?{' '}
        <button type="button" className="linkish" onClick={() => anyRef.current?.click()}>Show all file types</button>
        {' '}— or drag it straight onto the box.</div>}
      {warn && <div className="warn-box" style={{ marginTop: 8 }}>{warn}</div>}
      {items.length > 0 && (
        <>
          <div className="flist">
            {items.map(it => (
              <Fragment key={it.key}><div className="frow">
                <span className="fn" title={it.file.name}>{it.file.name}</span>
                <span className="note">{bytes(it.file.size)}</span>
                {it.state === 'uploading' && <div className="bar"><div style={{ width: `${Math.round(it.progress * 100)}%` }} /></div>}
                {it.state === 'done' && <span className="badge badge-green">Uploaded</span>}
                {it.state === 'error' && <span className="badge badge-red" title={it.error}>Rejected — press Retry</span>}
                {(it.state === 'waiting' || it.state === 'error') && !disabled && <button className="x" onClick={() => setItems(xs => xs.filter(x => x.key !== it.key))} aria-label="Remove">✕</button>}
              </div>
              {it.state === 'error' && it.error && <div className="frow-err">{it.error}</div>}
              </Fragment>
            ))}
          </div>
          <div className="note" style={{ marginTop: 6 }}>{items.length} file(s) · {bytes(total)}</div>
        </>
      )}
    </div>
  )
}
