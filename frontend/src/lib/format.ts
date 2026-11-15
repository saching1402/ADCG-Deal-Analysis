export const bandClass = (s: number | null | undefined) =>
  s == null ? 'b-none' : s >= 8 ? 'b-strong' : s >= 6.5 ? 'b-pos' : s >= 5 ? 'b-neu' : 'b-weak'
export const riskClass = (r: number | null | undefined) =>
  r == null ? 'b-none' : r >= 65 ? 'b-weak' : r >= 45 ? 'b-neu' : 'b-pos'
export const trackLabel = (t: string) => (t === 'vg' ? 'Venture / Growth' : t === 'buyout' ? 'Buyout' : 'Auto')
export const bytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`
export const ago = (iso?: string | null) => {
  if (!iso) return '—'
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  if (s < 86400 * 30) return `${Math.round(s / 86400)}d ago`
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' })
}
export const STAGE_STEPS = [
  { id: 'digest', label: 'Read & verify files' },
  { id: 'research', label: 'Independent research' },
  { id: 'risk', label: 'Independent risks' },
  { id: 'integrate', label: 'Bring in data room' },
  { id: 'score', label: 'Score' },
  { id: 'memo', label: 'Write memo' },
]
