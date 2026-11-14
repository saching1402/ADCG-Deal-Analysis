import type { DealRow } from '../types'
import { STAGE_STEPS } from '../lib/format'

export function TrackBadge({ t }: { t: string }) {
  if (t === 'vg') return <span className="badge badge-vg">Venture / Growth</span>
  if (t === 'buyout') return <span className="badge badge-buyout">Buyout</span>
  return <span className="badge badge-auto">Auto</span>
}

export function StatusBadge({ d }: { d: Pick<DealRow, 'status' | 'job' | 'legacy' | 'file_count'> }) {
  if (d.status === 'running' || d.status === 'queued') {
    const step = STAGE_STEPS.find(s => s.id === d.job?.stage)
    return <span className="badge badge-run"><span className="dot" />{d.status === 'queued' ? 'Queued' : step?.label ?? 'Running'}</span>
  }
  if (d.status === 'error') return <span className="badge badge-red">Error</span>
  if (d.status === 'blocked') return <span className="badge badge-red">Files need attention</span>
  if (d.status === 'draft') return <span className="badge badge-gray">Draft{d.file_count ? ` · ${d.file_count} files` : ''}</span>
  if (d.legacy) return <span className="badge badge-gray">Ledger</span>
  return <span className="badge badge-green">Memo ready</span>
}
