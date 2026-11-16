import { useCallback, useEffect, useRef, useState } from 'react'

/* Voice input via the Web Speech API (Chrome, Edge, Safari). Audio is handled by the browser's own speech service. */
type SR = { start(): void; stop(): void; abort(): void; continuous: boolean; interimResults: boolean; lang: string
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null }

/** `continuous` (default) keeps listening until stopped — for dictating notes. `continuous: false` = one phrase, then stops
 *  by itself — for saying a company name. `onInterim` gets the words live while the person is still speaking. */
export function useDictation(onFinal: (text: string) => void, opts: { continuous?: boolean; onInterim?: (text: string) => void } = {}) {
  const continuous = opts.continuous ?? true
  const Ctor = (window as unknown as Record<string, unknown>).SpeechRecognition ?? (window as unknown as Record<string, unknown>).webkitSpeechRecognition
  const supported = typeof Ctor === 'function'
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const rec = useRef<SR | null>(null)
  const want = useRef(false)
  const final = useRef(onFinal)
  final.current = onFinal
  const mid = useRef(opts.onInterim)
  mid.current = opts.onInterim

  const stop = useCallback(() => { want.current = false; rec.current?.stop(); setListening(false); setInterim('') }, [])
  const start = useCallback(() => {
    if (!supported) return
    setErr(null)
    const r = new (Ctor as new () => SR)()
    r.continuous = continuous; r.interimResults = true; r.lang = navigator.language || 'en-US'
    r.onresult = e => {
      let fin = '', part = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) fin += res[0].transcript; else part += res[0].transcript
      }
      if (fin.trim()) final.current(fin.trim())
      setInterim(part)
      if (part.trim()) mid.current?.(part.trim())
    }
    r.onerror = e => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') { setErr('Microphone access is blocked — allow it in the browser address bar.'); want.current = false }
      else if (e.error === 'no-speech') { if (!continuous) setErr("Didn't catch that — tap the mic and try again.") }
      else if (e.error !== 'aborted') setErr(`Voice input stopped (${e.error}).`)
    }
    r.onend = () => {
      if (want.current && continuous) { try { r.start() } catch { /* restarting too fast */ } }
      else { want.current = false; setListening(false); setInterim('') }
    }
    rec.current = r; want.current = true
    try { r.start(); setListening(true) } catch (e) { setErr(String(e)) }
  }, [Ctor, supported, continuous])
  useEffect(() => () => { want.current = false; rec.current?.abort() }, [])
  return { supported, listening, interim, err, start, stop, toggle: () => (want.current ? stop() : start()) }
}
