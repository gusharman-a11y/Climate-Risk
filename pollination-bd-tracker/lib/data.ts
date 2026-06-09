import { supabase } from './supabase'
import type { Company, Signal } from './types'

const HOT_SHEET_COLS = 'id,name,asx_code,sector,asrs_group,score_overall,score_asrs,score_target_gap,score_risk,score_intent,score_relationship,top_signal,relationship_status,relationship_lead,pipeline_stage,mandatory_from,sbti_status,sbti_date_updated'

// ── Hot Sheet ─────────────────────────────────────────────────────────────────

export async function getHotSheet(): Promise<{ main: Company[]; sbtiV2: Company[] }> {
  // Main hot sheet — exclude current clients, active pipeline, and SBTi-validated companies
  const [mainRes, sbtiRes] = await Promise.all([
    supabase
      .from('companies')
      .select(HOT_SHEET_COLS)
      .not('relationship_status', 'eq', 'current_client')
      .not('pipeline_stage', 'in', '("mandated","negotiation","proposal")')
      .not('sbti_status', 'eq', 'Targets set')
      .not('asrs_group', 'eq', 'Unclassified')
      .gt('score_overall', 0)
      .order('score_overall', { ascending: false })
      .limit(300),

    // SBTi V2 refresh group — validated companies, oldest first
    supabase
      .from('companies')
      .select(HOT_SHEET_COLS)
      .eq('sbti_status', 'Targets set')
      .not('relationship_status', 'eq', 'current_client')
      .order('sbti_date_updated', { ascending: true })
      .limit(100),
  ])

  if (mainRes.error) throw mainRes.error
  if (sbtiRes.error) throw sbtiRes.error

  return {
    main: (mainRes.data ?? []) as Company[],
    sbtiV2: (sbtiRes.data ?? []) as Company[],
  }
}

// ── Full universe with filters ─────────────────────────────────────────────

export async function getCompanies(filters?: {
  asrs_group?: string
  sector?: string
  relationship_status?: string
  min_score?: number
  search?: string
}): Promise<Company[]> {
  let query = supabase.from('companies').select(
    'id,name,asx_code,sector,asrs_group,score_overall,target_classification,target_description,target_scope,target_year,net_zero_year,nzt_end_year,relationship_status,relationship_lead,pipeline_stage,mandatory_from,sbti_status,sbti_date_updated'
  )

  if (filters?.asrs_group) query = query.eq('asrs_group', filters.asrs_group)
  if (filters?.sector) query = query.eq('sector', filters.sector)
  if (filters?.relationship_status) query = query.eq('relationship_status', filters.relationship_status)
  if (filters?.min_score) query = query.gte('score_overall', filters.min_score)
  if (filters?.search) query = query.ilike('name', `%${filters.search}%`)

  const { data, error } = await query.order('score_overall', { ascending: false })
  if (error) throw error
  return (data ?? []) as Company[]
}

// ── Single company ─────────────────────────────────────────────────────────

export async function getCompany(id: string): Promise<Company | null> {
  const { data, error } = await supabase
    .from('companies')
    .select('*')
    .eq('id', id)
    .single()

  if (error) return null
  return data as Company
}

// ── Signals for a company ──────────────────────────────────────────────────

export async function getSignals(companyId: string): Promise<Signal[]> {
  const { data, error } = await supabase
    .from('signals')
    .select('*')
    .eq('company_id', companyId)
    .order('signal_date', { ascending: false })

  if (error) throw error
  return (data ?? []) as Signal[]
}

// ── Pipeline ───────────────────────────────────────────────────────────────

export async function getPipelineCompanies(): Promise<Company[]> {
  const { data, error } = await supabase
    .from('companies')
    .select('*')
    .not('pipeline_stage', 'is', null)
    .order('score_overall', { ascending: false })

  if (error) throw error
  return (data ?? []) as Company[]
}

// ── Update pipeline stage ──────────────────────────────────────────────────

export async function updatePipelineStage(
  companyId: string,
  stage: string | null,
  notes?: string,
  owner?: string,
): Promise<void> {
  const { error } = await supabase
    .from('companies')
    .update({ pipeline_stage: stage, pipeline_notes: notes, pipeline_owner: owner, updated_at: new Date().toISOString() })
    .eq('id', companyId)

  if (error) throw error
}

// ── Update relationship ────────────────────────────────────────────────────

export async function updateRelationship(
  companyId: string,
  patch: Partial<Pick<Company, 'relationship_status' | 'relationship_lead' | 'relationship_contacts' | 'relationship_notes' | 'last_interaction_date'>>,
): Promise<void> {
  const { error } = await supabase
    .from('companies')
    .update({ ...patch, updated_at: new Date().toISOString() })
    .eq('id', companyId)

  if (error) throw error
}

// ── Add manual signal ──────────────────────────────────────────────────────

export async function addSignal(signal: Omit<Signal, 'id' | 'created_at'>): Promise<void> {
  const { error } = await supabase.from('signals').insert(signal)
  if (error) throw error
}

// ── Filter options ─────────────────────────────────────────────────────────

export async function getSectors(): Promise<string[]> {
  const { data } = await supabase
    .from('companies')
    .select('sector')
    .not('sector', 'is', null)
  const sectors = [...new Set((data ?? []).map((d: { sector: string }) => d.sector))].sort()
  return sectors as string[]
}
