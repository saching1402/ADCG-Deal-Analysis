import { api, errorText } from './api'
import type { DealFile } from '../types'

export interface UploadItem {
  key: string; file: File; progress: number; state: 'waiting' | 'uploading' | 'done' | 'error'; error?: string
}

/**
 * Upload files one per request, 3 at a time, each retried twice. Many small requests instead of
 * one huge multipart body means 15-20 large files never hit a request-size or timeout limit, and a
 * single failure only retries that file.
 */
export async function uploadAll(
  dealId: string, items: UploadItem[], onChange: (key: string, patch: Partial<UploadItem>) => void, concurrency = 3,
): Promise<{ ok: number; failed: number }> {
  let i = 0, ok = 0, failed = 0
  async function one(it: UploadItem) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        onChange(it.key, { state: 'uploading', progress: 0, error: undefined })
        const fd = new FormData()
        fd.append('file', it.file, it.file.name)
        await api.post<DealFile>(`/deals/${dealId}/files/`, fd, {
          timeout: 0,
          onUploadProgress: e => onChange(it.key, { progress: e.total ? e.loaded / e.total : 0 }),
        })
        onChange(it.key, { state: 'done', progress: 1 })
        ok++
        return
      } catch (e) {
        const status = (e as { response?: { status?: number } }).response?.status
        if (status && status < 500) { onChange(it.key, { state: 'error', error: errorText(e) }); failed++; return }
        if (attempt === 2) { onChange(it.key, { state: 'error', error: errorText(e) }); failed++; return }
        await new Promise(r => setTimeout(r, 1500 * (attempt + 1)))
      }
    }
  }
  const queue = items.filter(x => x.state !== 'done')
  await Promise.all(Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
    while (i < queue.length) await one(queue[i++])
  }))
  return { ok, failed }
}

export const toItems = (files: FileList | File[]): UploadItem[] =>
  Array.from(files).map(f => ({ key: `${f.name}-${f.size}-${f.lastModified}`, file: f, progress: 0, state: 'waiting' }))

/** Re-upload into an existing file slot (lost copy or corrected version). */
export async function replaceFile(dealId: string, fileId: number, file: File, onProgress?: (p: number) => void) {
  const fd = new FormData()
  fd.append('file', file, file.name)
  const r = await api.post<DealFile & { kept_fact_sheet: boolean }>(`/deals/${dealId}/files/${fileId}/replace/`, fd, {
    timeout: 0, onUploadProgress: e => onProgress?.(e.total ? e.loaded / e.total : 0),
  })
  return r.data
}

/** Loose filename key for matching re-uploads to missing files. */
export const nameKey = (n: string) => n.toLowerCase().replace(/\.[^.]+$/, '').replace(/[^a-z0-9]+/g, '')
