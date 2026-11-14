export type Track = 'auto' | 'buyout' | 'vg'
export type DealStatus = 'draft' | 'queued' | 'running' | 'done' | 'error' | 'blocked'

export interface Job {
  id: number; status: DealStatus; stage: string; stage_detail: string; model: string; cost: number
  searches: number; input_tokens: number; output_tokens: number; error: string
  log: { t: string; msg: string }[]; created_at: string; started_at: string | null; finished_at: string | null
  instructions: string; allow_partial?: boolean; framework_version?: number | null
}

export interface DealRow {
  id: string; name: string; website: string; track: Track; track_resolved: '' | 'buyout' | 'vg'
  sponsor: string; sector: string; sub_sector: string; stage: string; status: DealStatus
  ev: string; multiple: string; leverage: string; one_liner: string
  adcg_score: number | null; risk_score: number | null; band: string; legacy: boolean
  file_count: number | null; analyzed_at: string | null; updated_at: string; created_at: string
  total_cost: number; job: Job | null
}

export interface Readability {
  status: 'ok' | 'warn' | 'block'; summary: string; notes: string[]; pages?: number; text_pages?: number; sheets?: number; rows?: number
}
export interface Coverage { parts: number; ok: number; failed: { label: string; why: string }[]; notes?: string[] }
export interface DealFile {
  id: number; name: string; size: number; status: 'uploaded' | 'digesting' | 'digested' | 'partial' | 'error'
  method: string; pages: number | null; chars: number | null; error: string; uploaded_at: string; has_digest: boolean
  readability: Readability | Record<string, never>; coverage: Coverage | Record<string, never>; missing?: boolean
}

export interface Criterion { name: string; score: number | null; rationale: string; auto?: string }
export interface Section { name: string; weight: number; score?: number; criteria: Criterion[] }

export interface Scorecard {
  sections?: Section[]
  weights_rationale?: { section: string; default: number; deal: number; why: string }[]
  key_risks?: { criterion: string; severity: string; why: string }[]
  investors?: { name: string; tier: string; role?: string; prior_round_only?: boolean }[]
  risk_register?: { name: string; weight: number; severity: number; rationale: string }[]
  verdict_note?: string; calibration?: string
}

export interface Meta {
  models: { id: string; label: string }[]; default_model: string; digest_model: string
  stages: { id: string; label: string }[]; tracks: { id: Track; label: string }[]
  accepted: string[]; max_upload_mb: number; max_files: number; api_key_set: boolean; storage: string; storage_persistent: boolean
}

export interface DealDetail extends DealRow {
  notes: string; recommendation: string; facts: { k: string; v: string }[]
  summary: { overall?: number; risk?: number; band?: string; sections?: Record<string, number>; vjr?: number | null; vjr_text?: string; marquee_pts?: number; marquee_score?: number; derived_risk?: number }
  scorecard: Scorecard; research: string; sources: string[]; has_memo: boolean
  files: DealFile[]; jobs: Job[]; can_edit: boolean; meta: Meta
}
