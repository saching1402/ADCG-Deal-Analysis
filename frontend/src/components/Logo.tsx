/** Company logos from each website's icon (Google favicon service), with an initials fallback. */
import { useState, type ReactNode } from 'react'

export function domainOf(url?: string | null): string {
  if (!url) return ''
  try {
    const host = new URL(url.includes('://') ? url : `https://${url}`).hostname.toLowerCase()
    return host.replace(/^www\d?\./, '')
  } catch { return '' }
}

const failed = new Set<string>()

function initials(name: string): string {
  const words = name.replace(/\(.*?\)/g, '').replace(/[^\p{L}\p{N} &]/gu, ' ').split(/\s+/).filter(w => w && w !== '&' && !/^the$/i.test(w))
  return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? '?').slice(0, 2)).toUpperCase()
}

export function Logo({ url, domain, name, size = 28 }: { url?: string | null; domain?: string; name: string; size?: number }) {
  const d = domain || domainOf(url)
  const [bad, setBad] = useState(!d || failed.has(d))
  const box = { width: size, height: size, minWidth: size, borderRadius: Math.round(size / 4.5) }
  if (bad || !d) return <span className="co-logo logo-ph" style={{ ...box, fontSize: Math.max(8, size * 0.36) }} aria-hidden>{initials(name)}</span>
  return (
    <img className="co-logo" style={box} src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(d)}&sz=128`} alt=""
      width={size} height={size} loading="lazy" referrerPolicy="no-referrer"
      onError={() => { failed.add(d); setBad(true) }}
      onLoad={e => { if ((e.currentTarget as HTMLImageElement).naturalWidth <= 16) { failed.add(d); setBad(true) } }} />
  )
}

export function WithLogo({ logo, children }: { logo: ReactNode; children: ReactNode }) {
  return <span className="with-logo">{logo}<span className="with-logo-body">{children}</span></span>
}
