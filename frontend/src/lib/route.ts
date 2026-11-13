import { useEffect, useState } from 'react'

/** Hash routes: '' (pipeline) | 'deal-<uuid>' | 'deal-<uuid>/<tab>' */
export function useHash(): string {
  const [h, setH] = useState(() => window.location.hash.slice(1))
  useEffect(() => {
    const on = () => setH(window.location.hash.slice(1))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return h
}
export const go = (h: string) => { window.location.hash = h }
