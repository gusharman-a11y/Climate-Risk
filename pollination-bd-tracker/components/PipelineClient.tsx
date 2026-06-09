'use client'

import Link from 'next/link'
import type { Company, PipelineStage } from '@/lib/types'
import { PIPELINE_STAGE_LABELS, relationshipBadge } from '@/lib/types'
import { Badge, ScorePill } from '@/components/Badge'

interface Props { companies: Company[] }

const STAGES: PipelineStage[] = ['watch', 'prospect', 'qualified', 'proposal', 'negotiation', 'mandated', 'missed']

const STAGE_COLORS: Record<PipelineStage, string> = {
  watch: 'border-t-slate-400',
  prospect: 'border-t-blue-400',
  qualified: 'border-t-[#00579B]',
  proposal: 'border-t-amber-400',
  negotiation: 'border-t-orange-500',
  mandated: 'border-t-green-500',
  missed: 'border-t-slate-300',
}

const STAGE_COUNT_COLORS: Record<PipelineStage, string> = {
  watch: 'bg-slate-100 text-slate-600',
  prospect: 'bg-blue-100 text-blue-700',
  qualified: 'bg-[#00579B]/10 text-[#00579B]',
  proposal: 'bg-amber-100 text-amber-700',
  negotiation: 'bg-orange-100 text-orange-700',
  mandated: 'bg-green-100 text-green-700',
  missed: 'bg-slate-100 text-slate-400',
}

export default function PipelineClient({ companies }: Props) {
  const byStage = STAGES.reduce<Record<string, Company[]>>((acc, s) => {
    acc[s] = companies.filter(c => c.pipeline_stage === s)
    return acc
  }, {})

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="border-b border-slate-200 bg-white px-6 py-4 sticky top-0 z-10">
        <h1 className="text-lg font-bold text-slate-900">Pipeline</h1>
        <p className="text-xs text-slate-500 mt-0.5">{companies.length} companies in active BD</p>
      </div>

      {/* Kanban board */}
      <div className="flex-1 overflow-x-auto">
        <div className="flex gap-4 p-5 min-w-max h-full">
          {STAGES.map(stage => {
            const rows = byStage[stage] ?? []
            return (
              <div key={stage} className="w-56 flex-shrink-0 flex flex-col">
                {/* Column header */}
                <div className={`bg-white border border-slate-200 border-t-4 ${STAGE_COLORS[stage]} rounded-lg mb-3 px-3 py-2.5 flex items-center justify-between`}>
                  <span className="text-xs font-semibold text-slate-700">{PIPELINE_STAGE_LABELS[stage]}</span>
                  <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${STAGE_COUNT_COLORS[stage]}`}>
                    {rows.length}
                  </span>
                </div>

                {/* Cards */}
                <div className="flex flex-col gap-2 flex-1">
                  {rows.map(company => {
                    const rb = relationshipBadge(company.relationship_status)
                    return (
                      <Link
                        key={company.id}
                        href={`/companies/${company.id}`}
                        className="bg-white border border-slate-200 rounded-lg p-3 hover:border-[#00579B]/40 hover:shadow-sm transition-all block"
                      >
                        <p className="text-sm font-medium text-slate-900 leading-tight mb-1">{company.name}</p>
                        {company.asx_code && (
                          <p className="text-[10px] font-mono text-slate-400 mb-2">{company.asx_code}</p>
                        )}
                        <div className="flex items-center justify-between">
                          <ScorePill score={company.score_overall} />
                          <Badge label={rb.label} className={rb.className} />
                        </div>
                        {company.pipeline_notes && (
                          <p className="text-[11px] text-slate-500 mt-2 line-clamp-2">{company.pipeline_notes}</p>
                        )}
                        {company.pipeline_owner && (
                          <p className="text-[10px] text-slate-400 mt-1">{company.pipeline_owner}</p>
                        )}
                      </Link>
                    )
                  })}

                  {rows.length === 0 && (
                    <div className="border-2 border-dashed border-slate-200 rounded-lg p-4 text-center">
                      <p className="text-xs text-slate-300">No companies</p>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
