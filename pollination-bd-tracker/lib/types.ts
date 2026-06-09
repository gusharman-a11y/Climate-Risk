// Pure types — no server-only imports. Safe to use in client components.

export type AsrsGroup = 'Group 1' | 'Group 2' | 'Group 3' | 'Unclassified'

export type RelationshipStatus =
  | 'current_client'
  | 'past_client'
  | 'warm_contact'
  | 'none'

export type PipelineStage =
  | 'watch'
  | 'prospect'
  | 'qualified'
  | 'proposal'
  | 'negotiation'
  | 'mandated'
  | 'missed'

export type SignalType =
  | 'asrs_window_open'
  | 'safeguard_obligation'
  | 'sbti_removed'
  | 'sbti_vintage_old'
  | 'no_public_target'
  | 'no_published_plan'
  | 'behind_delivery'
  | 'greenwashing_case'
  | 'shareholder_resolution'
  | 'target_year_imminent'
  | 'nzt_low_integrity'
  | 'agm_climate_item'
  | 'new_director'
  | 'asrs_mentioned_report'
  | 'merger_acquisition'
  | 'manual'

export interface Company {
  id: string
  abn: string | null
  name: string
  asx_code: string | null
  sector: string | null
  industry: string | null
  is_listed: boolean
  is_private: boolean
  // Size
  market_cap_tier: string | null
  revenue_aud: number | null
  assets_aud: number | null
  employee_count: number | null
  // ASRS
  asrs_group: AsrsGroup
  mandatory_from: string | null
  // Emissions
  nger_scope1_tco2e: number | null
  nger_year: string | null
  safeguard_covered: boolean
  safeguard_baseline: number | null
  // Target
  sbti_status: string | null
  sbti_date_updated: string | null
  target_classification: string | null
  target_year: number | null
  net_zero_year: number | null
  // NZT
  nzt_end_target: string | null
  nzt_end_year: number | null
  nzt_status: string | null
  nzt_interim_pct: number | null
  nzt_published_plan: boolean | null
  nzt_race_to_zero: boolean | null
  // Relationship
  relationship_status: RelationshipStatus
  relationship_lead: string | null
  relationship_contacts: string | null
  relationship_notes: string | null
  last_interaction_date: string | null
  // Pipeline
  pipeline_stage: PipelineStage | null
  pipeline_owner: string | null
  pipeline_notes: string | null
  pipeline_next_action: string | null
  pipeline_next_action_date: string | null
  // Scores (computed)
  score_asrs: number | null
  score_target_gap: number | null
  score_risk: number | null
  score_intent: number | null
  score_relationship: number | null
  score_overall: number | null
  top_signal: string | null
  created_at: string
  updated_at: string
}

export interface Signal {
  id: string
  company_id: string
  signal_type: SignalType
  signal_date: string
  headline: string
  body: string | null
  source_url: string | null
  source: string | null
  score_delta: number
  created_at: string
}

// Score display helpers
export function scoreColor(score: number | null): string {
  if (!score) return 'score-1'
  if (score >= 4.5) return 'score-5'
  if (score >= 3.5) return 'score-4'
  if (score >= 2.5) return 'score-3'
  if (score >= 1.5) return 'score-2'
  return 'score-1'
}

export function scoreRowClass(score: number | null): string {
  if (!score) return 'row-score-1'
  if (score >= 4.5) return 'row-score-5'
  if (score >= 3.5) return 'row-score-4'
  if (score >= 2.5) return 'row-score-3'
  if (score >= 1.5) return 'row-score-2'
  return 'row-score-1'
}

export function relationshipBadge(status: RelationshipStatus): { label: string; className: string } {
  switch (status) {
    case 'current_client':
      return { label: 'Current client', className: 'bg-[#d4f4e2] text-[#007038]' }
    case 'past_client':
      return { label: 'Past client', className: 'bg-[#cce5ff] text-[#0060c0]' }
    case 'warm_contact':
      return { label: 'Warm contact', className: 'bg-[#ffe5b4] text-[#c47c00]' }
    default:
      return { label: 'Cold', className: 'bg-[#f6f7fb] text-[#676879]' }
  }
}

export function asrsGroupBadge(group: AsrsGroup): { label: string; className: string } {
  switch (group) {
    case 'Group 1':
      return { label: 'Group 1', className: 'bg-[#ffd3d9] text-[#c0253d]' }
    case 'Group 2':
      return { label: 'Group 2', className: 'bg-[#ffe5b4] text-[#c47c00]' }
    case 'Group 3':
      return { label: 'Group 3', className: 'bg-[#fff3cd] text-[#8a6300]' }
    default:
      return { label: 'Unclassified', className: 'bg-[#f6f7fb] text-[#676879]' }
  }
}

export const PIPELINE_STAGE_LABELS: Record<PipelineStage, string> = {
  watch: 'Watching',
  prospect: 'Prospect',
  qualified: 'Qualified',
  proposal: 'Proposal',
  negotiation: 'Negotiation',
  mandated: 'Mandated',
  missed: 'Missed',
}
