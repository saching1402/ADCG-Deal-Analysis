import { api } from './api'

/** Start an analysis; if the deal lead's credit stop level is hit, ask before overriding it. */
export async function startAnalysis(dealId: string, body: Record<string, unknown>) {
  try {
    return await api.post(`/deals/${dealId}/analyze/`, body)
  } catch (e) {
    const r = (e as { response?: { status?: number; data?: { code?: string; detail?: string } } }).response
    if (r?.status === 409 && r.data?.code === 'credit_paused') {
      if (window.confirm(`${r.data.detail}\n\nRun this analysis anyway?`)) return api.post(`/deals/${dealId}/analyze/`, { ...body, override_credit: true })
    }
    throw e
  }
}
